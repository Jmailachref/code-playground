"""API tests against real Postgres, Redis and Docker sandboxes.

Needs the services from docker-compose (or any Postgres/Redis) and the
language images. Set TEST_DATABASE_URL to point at a throwaway database.
"""
import os

os.environ.setdefault("DATABASE_URL", os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://codeplay:codeplay@localhost:5432/codeplay_test"
))
os.environ.setdefault("QUEUE_NAME", "codeplay:test-jobs")
os.environ.setdefault("API_KEYS", "ui:ui-key,other:other-key")
os.environ.setdefault("UI_API_KEY", "ui-key")

import json  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from core.db import Base, engine  # noqa: E402
from core.queue import dequeue, get_redis  # noqa: E402
from core.config import settings  # noqa: E402
from runner.worker import process  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROBLEM = json.loads((ROOT / "examples" / "sum-of-two.json").read_text())
AUTH = {"Authorization": "Bearer ui-key"}
OTHER = {"Authorization": "Bearer other-key"}


@pytest.fixture(autouse=True)
def fresh_state():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    get_redis().delete(settings.queue_name)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def work_queue():
    """Act as the runner worker: judge everything waiting in the queue."""
    while (job := dequeue(timeout=1)) is not None:
        process(job)


def create_problem(client):
    response = client.post("/v1/problems", json=PROBLEM, headers=AUTH)
    assert response.status_code == 201, response.text
    return response.json()


def test_requires_api_key(client):
    response = client.get("/v1/languages")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_lists_languages(client):
    ids = [lang["id"] for lang in client.get("/v1/languages", headers=AUTH).json()]
    assert ids == ["cpp", "go", "java", "javascript", "python"]


def test_playground_run(client):
    response = client.post(
        "/v1/runs",
        json={"language": "python", "source_code": "print(input()[::-1])", "stdin": "hello\n"},
        headers=AUTH,
    )
    assert response.status_code == 202
    run_id = response.json()["id"]
    assert client.get(f"/v1/runs/{run_id}", headers=AUTH).json()["status"] == "queued"

    work_queue()

    run = client.get(f"/v1/runs/{run_id}", headers=AUTH).json()
    assert run["status"] == "completed"
    assert run["verdict"] == "accepted"
    assert run["stdout"] == "olleh\n"
    assert run["time_ms"] is not None


def test_run_with_compile_error(client):
    run_id = client.post(
        "/v1/runs", json={"language": "cpp", "source_code": "int main( {"}, headers=AUTH
    ).json()["id"]
    work_queue()
    run = client.get(f"/v1/runs/{run_id}", headers=AUTH).json()
    assert run["verdict"] == "compilation_error"
    assert "error" in run["compile_output"]


def test_problem_hides_hidden_scenarios(client):
    problem = create_problem(client)
    assert [s["name"] for s in problem["scenarios"]] == ["Simple", "Negatives"]
    assert problem["hidden_scenarios"] == 1
    fetched = client.get(f"/v1/problems/{problem['id']}", headers=AUTH).json()
    assert "1000000000" not in json.dumps(fetched)
    listed = client.get("/v1/problems", headers=AUTH).json()
    assert listed == [{"id": problem["id"], "slug": "sum-of-two", "title": "Sum of two"}]


def test_duplicate_slug_is_rejected(client):
    create_problem(client)
    response = client.post("/v1/problems", json=PROBLEM, headers=AUTH)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "slug_taken"


def test_edit_scenarios(client):
    problem = create_problem(client)
    added = client.post(
        f"/v1/problems/{problem['id']}/scenarios",
        json=[{"name": "Zeros", "input": "0 0\n", "expected_output": "0\n"}],
        headers=AUTH,
    ).json()
    assert added[0]["order"] == 3
    sid = added[0]["id"]
    patched = client.patch(
        f"/v1/problems/{problem['id']}/scenarios/{sid}", json={"hidden": True}, headers=AUTH
    ).json()
    assert patched["hidden"] is True
    assert client.delete(f"/v1/problems/{problem['id']}/scenarios/{sid}", headers=AUTH).status_code == 204
    assert client.get(f"/v1/problems/{problem['id']}", headers=AUTH).json()["hidden_scenarios"] == 1


def test_submission_is_judged_and_saved(client):
    problem = create_problem(client)
    code = (ROOT / "examples" / "solutions" / "sum.cpp").read_text()
    response = client.post(
        "/v1/submissions",
        json={"problem_id": problem["id"], "language": "cpp", "source_code": code, "user_id": "alice"},
        headers=AUTH,
    )
    assert response.status_code == 202
    sub_id = response.json()["id"]

    work_queue()

    sub = client.get(f"/v1/submissions/{sub_id}", headers=AUTH).json()
    assert sub["status"] == "completed"
    assert sub["verdict"] == "accepted"
    assert (sub["passed"], sub["total"], sub["score"], sub["max_score"]) == (3, 3, 3, 3)
    assert sub["source_code"] == code
    visible, hidden = sub["results"][:2], sub["results"][2]
    assert visible[0] == {
        "scenario": "Simple", "verdict": "accepted", "hidden": False, "time_ms": visible[0]["time_ms"],
        "memory_kb": visible[0]["memory_kb"], "exit_code": 0, "stdout": "3\n", "stderr": "",
        "expected_output": "3\n",
    }
    assert hidden["scenario"] == "Hidden #1"
    assert hidden["stdout"] is None and hidden["expected_output"] is None


def test_wrong_answer_and_history(client):
    problem = create_problem(client)
    for code in ["print(3)", "a, b = map(int, input().split())\nprint(a + b)"]:
        client.post(
            "/v1/submissions",
            json={"problem_id": problem["id"], "language": "python", "source_code": code, "user_id": "bob"},
            headers=AUTH,
        )
    work_queue()

    history = client.get(
        "/v1/submissions", params={"user_id": "bob", "problem_id": problem["id"]}, headers=AUTH
    ).json()
    assert [(h["verdict"], h["passed"]) for h in history] == [("accepted", 3), ("wrong_answer", 1)]
    assert client.get("/v1/submissions", params={"user_id": "alice"}, headers=AUTH).json() == []


def test_submissions_are_private_to_their_client(client):
    problem = create_problem(client)
    sub_id = client.post(
        "/v1/submissions",
        json={"problem_id": problem["id"], "language": "python", "source_code": "print(3)"},
        headers=AUTH,
    ).json()["id"]
    assert client.get(f"/v1/submissions/{sub_id}", headers=OTHER).status_code == 404
    assert client.get("/v1/submissions", headers=OTHER).json() == []


def test_validation_errors(client):
    problem = create_problem(client)
    bad_lang = client.post(
        "/v1/submissions",
        json={"problem_id": problem["id"], "language": "cobol", "source_code": "x"},
        headers=AUTH,
    )
    assert bad_lang.status_code == 400
    assert bad_lang.json()["error"]["code"] == "unsupported_language"

    too_big = client.post(
        "/v1/runs", json={"language": "python", "source_code": "#" * (64 * 1024 + 1)}, headers=AUTH
    )
    assert too_big.status_code == 413

    missing = client.get("/v1/problems/00000000-0000-0000-0000-000000000000", headers=AUTH)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "problem_not_found"


def test_restricted_languages(client):
    problem = create_problem(client)
    client.patch(f"/v1/problems/{problem['id']}", json={"languages": ["python"]}, headers=AUTH)
    response = client.post(
        "/v1/submissions",
        json={"problem_id": problem["id"], "language": "go", "source_code": "package main"},
        headers=AUTH,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "language_not_allowed"


def test_ui_proxy_forwards_allowed_calls_without_a_key(client):
    problem = create_problem(client)
    listed = client.get("/ui-api/problems")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == problem["id"]
    run_id = client.post("/ui-api/runs", json={"language": "python", "source_code": "print(1)"}).json()["id"]
    work_queue()
    assert client.get(f"/ui-api/runs/{run_id}").json()["stdout"] == "1\n"


def test_ui_proxy_blocks_admin_calls(client):
    problem = create_problem(client)
    assert client.post("/ui-api/problems", json=PROBLEM).status_code == 404
    assert client.post(f"/ui-api/problems/{problem['id']}/scenarios", json=[]).status_code == 404
    assert client.get("/ui-api/health").status_code == 404
