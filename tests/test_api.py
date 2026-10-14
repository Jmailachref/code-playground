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

import dataclasses  # noqa: E402
import json  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from core.db import Base, engine  # noqa: E402
from core.queue import dequeue, get_redis  # noqa: E402
from core.config import settings  # noqa: E402
from core.db import SessionLocal  # noqa: E402
from core.models import Submission  # noqa: E402
from core.queue import is_queued  # noqa: E402
from runner.worker import process, recover_lost_jobs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROBLEM = json.loads((ROOT / "examples" / "python" / "sum-of-two.json").read_text())
AUTH = {"Authorization": "Bearer ui-key"}
OTHER = {"Authorization": "Bearer other-key"}


@pytest.fixture(autouse=True)
def fresh_state():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    redis = get_redis()
    redis.delete(settings.queue_name, *redis.keys("codeplay:rate:*"))
    yield


@pytest.fixture
def client():
    return TestClient(app)


def work_queue():
    """Act as the runner worker: judge everything waiting in the queue."""
    while (job := dequeue(timeout=1)) is not None:
        process(job)


def create_problem(client, **overrides):
    response = client.post("/v1/problems", json={**PROBLEM, **overrides}, headers=AUTH)
    assert response.status_code == 201, response.text
    return response.json()


def test_requires_api_key(client):
    response = client.get("/v1/languages")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_lists_languages(client):
    ids = [lang["id"] for lang in client.get("/v1/languages", headers=AUTH).json()]
    assert ids == ["cpp", "go", "java", "javascript", "python", "sql"]


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
    assert listed == [
        {"id": problem["id"], "slug": "sum-of-two", "title": "Sum of two", "language": "python", "level": 1}
    ]


def test_questions_have_a_language_and_level(client):
    create_problem(client)
    create_problem(client, slug="sum-cpp", language="cpp", level=2, starter_code=None)
    create_problem(client, slug="sum-hard", level=3)
    listed = client.get("/v1/problems", headers=AUTH).json()
    assert [(p["slug"], p["language"], p["level"]) for p in listed] == [
        ("sum-cpp", "cpp", 2), ("sum-of-two", "python", 1), ("sum-hard", "python", 3)
    ]
    python = client.get("/v1/problems", params={"language": "python"}, headers=AUTH).json()
    assert [p["slug"] for p in python] == ["sum-of-two", "sum-hard"]
    hard = client.get("/v1/problems", params={"language": "python", "level": 3}, headers=AUTH).json()
    assert [p["slug"] for p in hard] == ["sum-hard"]

    cpp = next(p for p in listed if p["slug"] == "sum-cpp")
    fetched = client.get(f"/v1/problems/{cpp['id']}", headers=AUTH).json()
    assert "int main()" in fetched["starter_code"]  # no starter code: the language template
    own = client.get(f"/v1/problems/{listed[1]['id']}", headers=AUTH).json()
    assert own["starter_code"] == PROBLEM["starter_code"]


def test_question_language_and_level_are_validated(client):
    assert client.post(
        "/v1/problems", json={**PROBLEM, "language": "cobol"}, headers=AUTH
    ).json()["error"]["code"] == "unsupported_language"
    too_hard = client.post("/v1/problems", json={**PROBLEM, "level": 5}, headers=AUTH)
    assert too_hard.status_code == 400 and too_hard.json()["error"]["code"] == "invalid_request"
    no_language = {k: v for k, v in PROBLEM.items() if k != "language"}
    assert client.post("/v1/problems", json=no_language, headers=AUTH).status_code == 400
    assert client.get("/v1/problems", params={"level": 0}, headers=AUTH).status_code == 400


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
    problem = create_problem(client, language="cpp")
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


def test_submissions_must_use_the_question_language(client):
    problem = create_problem(client)
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


def test_ui_index_is_revalidated_and_assets_are_cached(tmp_path):
    from fastapi import FastAPI
    from api.ui import UIFiles

    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html></html>")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)")
    ui = FastAPI()
    ui.mount("/", UIFiles(directory=tmp_path, html=True))
    browser = TestClient(ui)
    assert browser.get("/").headers["cache-control"] == "no-cache"
    assert browser.get("/index.html").headers["cache-control"] == "no-cache"
    assert "immutable" in browser.get("/assets/index-abc123.js").headers["cache-control"]


def test_ui_proxy_blocks_admin_calls(client):
    problem = create_problem(client)
    assert client.post("/ui-api/problems", json=PROBLEM).status_code == 404
    assert client.post(f"/ui-api/problems/{problem['id']}/scenarios", json=[]).status_code == 404
    assert client.get("/ui-api/health").status_code == 404


def test_runs_are_rate_limited_per_api_key(client, monkeypatch):
    monkeypatch.setattr("api.main.settings", dataclasses.replace(settings, rate_limit_per_minute=2))
    body = {"language": "python", "source_code": "print(1)"}
    assert [client.post("/v1/runs", json=body, headers=OTHER).status_code for _ in range(3)] == [202, 202, 429]
    limited = client.post("/v1/runs", json=body, headers=OTHER)
    assert limited.json()["error"]["code"] == "rate_limited"
    assert int(limited.headers["Retry-After"]) > 0
    # Another key has its own budget.
    other = dataclasses.replace(settings, rate_limit_per_minute=2, api_keys={**settings.api_keys, "third": "third"})
    monkeypatch.setattr("api.main.settings", other)
    monkeypatch.setattr("api.auth.settings", other)
    assert client.post("/v1/runs", json=body, headers={"Authorization": "Bearer third"}).status_code == 202


def test_ui_proxy_is_rate_limited_per_visitor(client, monkeypatch):
    monkeypatch.setattr("api.ui.settings", dataclasses.replace(settings, ui_rate_limit_per_minute=1))
    body = {"language": "python", "source_code": "print(1)"}
    assert client.post("/ui-api/runs", json=body).status_code == 202
    assert client.post("/ui-api/runs", json=body).status_code == 429
    # Reading results is never limited.
    assert client.get("/ui-api/problems").status_code == 200


def test_lost_jobs_are_requeued(client):
    long_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
    with SessionLocal() as session:
        lost_in_queue = Submission(
            client_id="ui", language="python", source_code="print(1)", stdin="", status="queued", created_at=long_ago
        )
        dead_worker = Submission(
            client_id="ui", language="python", source_code="print(2)", stdin="", status="running",
            created_at=long_ago, started_at=long_ago,
        )
        fresh = Submission(client_id="ui", language="python", source_code="print(3)", stdin="", status="running",
                           started_at=datetime.now(timezone.utc))
        session.add_all([lost_in_queue, dead_worker, fresh])
        session.commit()

    assert recover_lost_jobs() == 2
    assert is_queued(lost_in_queue.id) and is_queued(dead_worker.id) and not is_queued(fresh.id)
    assert recover_lost_jobs() == 0  # already queued: not pushed twice

    work_queue()
    out = client.get(f"/v1/runs/{dead_worker.id}", headers=AUTH).json()
    assert (out["status"], out["stdout"]) == ("completed", "2\n")


def test_a_job_is_judged_once_even_if_queued_twice(client):
    run_id = client.post("/v1/runs", json={"language": "python", "source_code": "print(1)"}, headers=AUTH).json()["id"]
    get_redis().lpush(settings.queue_name, run_id)
    work_queue()
    with SessionLocal() as session:
        assert len(session.get(Submission, run_id).results) == 1
