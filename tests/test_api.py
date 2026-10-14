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
        {
            "id": problem["id"], "slug": "sum-of-two", "title": "Sum of two", "kind": "code",
            "language": "python", "level": 1, "status": "approved",
        }
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
    too_hard = client.post("/v1/problems", json={**PROBLEM, "level": 6}, headers=AUTH)
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


# --- QCM questions and tests --------------------------------------------------


def qcm(slug, language="docker", level=2, **overrides):
    return {
        "slug": slug,
        "title": f"Question {slug}",
        "statement": "Which command lists running containers?",
        "kind": "qcm",
        "language": language,
        "level": level,
        "choices": ["docker ps", "docker ls", "docker images"],
        "correct_choices": [0],
        **overrides,
    }


def add(client, body):
    response = client.post("/v1/problems", json=body, headers=AUTH)
    assert response.status_code == 201, response.text
    return response.json()


def test_qcm_question_hides_its_answer(client):
    question = add(client, qcm("ps", correct_choices=[0, 2]))
    assert question["choices"] == ["docker ps", "docker ls", "docker images"]
    assert question["multiple"] is True and question["starter_code"] is None
    assert "correct_choices" not in client.get(f"/v1/problems/{question['id']}", headers=AUTH).json()
    full = client.get(f"/v1/problems/{question['id']}/full", headers=AUTH).json()
    assert full["correct_choices"] == [0, 2]


def test_full_view_shows_hidden_scenarios_but_not_through_the_web_ui(client):
    problem = create_problem(client)
    full = client.get(f"/v1/problems/{problem['id']}/full", headers=AUTH).json()
    assert len(full["scenarios"]) == 3 and any(s["hidden"] for s in full["scenarios"])
    assert client.get(f"/ui-api/problems/{problem['id']}/full").status_code == 404


@pytest.mark.parametrize(
    "body, message",
    [
        (qcm("a", choices=None), "needs choices"),
        (qcm("b", correct_choices=[3]), "indexes"),
        (qcm("c", correct_choices=[0, 0]), "distinct"),
        (qcm("d", scenarios=[{"name": "x", "expected_output": "y"}]), "no scenarios"),
        ({**PROBLEM, "slug": "e", "choices": ["a", "b"]}, "only qcm"),
    ],
)
def test_qcm_fields_are_validated(client, body, message):
    response = client.post("/v1/problems", json=body, headers=AUTH)
    assert response.status_code == 400
    assert message in json.dumps(response.json())


def test_qcm_topic_need_not_be_a_language_but_code_must(client):
    add(client, qcm("k8s", language="kubernetes"))
    assert client.post(
        "/v1/problems", json={**PROBLEM, "language": "docker"}, headers=AUTH
    ).json()["error"]["code"] == "unsupported_language"
    question = add(client, qcm("fix-me"))
    bad = client.patch(f"/v1/problems/{question['id']}", json={"correct_choices": [9]}, headers=AUTH)
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_question"


def test_qcm_takes_no_submissions_or_scenarios(client):
    question = add(client, qcm("ps"))
    sub = client.post(
        "/v1/submissions",
        json={"problem_id": question["id"], "language": "python", "source_code": "print(1)"},
        headers=AUTH,
    )
    assert sub.json()["error"]["code"] == "not_code"
    scen = client.post(
        f"/v1/problems/{question['id']}/scenarios", json=[{"name": "x", "expected_output": "y"}], headers=AUTH
    )
    assert scen.status_code == 400


def test_stock_counts_approved_questions_by_kind(client):
    create_problem(client)
    create_problem(client, slug="sum-2")
    add(client, qcm("py-qcm", language="python", level=1))
    add(client, qcm("pending", language="python", level=1, status="pending"))
    add(client, qcm("ps"))
    stock = client.get("/v1/stock", headers=AUTH).json()
    assert stock == [
        {"language": "docker", "level": 2, "code": 0, "qcm": 1},
        {"language": "python", "level": 1, "code": 2, "qcm": 1},
    ]
    assert len(client.get("/v1/stock", params={"language": "python"}, headers=AUTH).json()) == 1


def test_test_draws_the_recipe_and_hides_answers(client):
    for i in range(3):
        create_problem(client, slug=f"sum-{i}")
    for i in range(4):
        add(client, qcm(f"docker-{i}"))
    add(client, qcm("never", status="rejected"))
    recipe = [{"language": "python", "level": 1, "code": 2}, {"language": "docker", "level": 2, "qcm": 3}]
    response = client.post("/v1/tests", json={"recipe": recipe, "external_ref": "session-1"}, headers=AUTH)
    assert response.status_code == 201, response.text
    test = response.json()
    kinds = [(q["kind"], q["language"]) for q in test["questions"]]
    assert kinds == [("code", "python")] * 2 + [("qcm", "docker")] * 3
    assert len({q["id"] for q in test["questions"]}) == 5
    assert "never" not in [q["slug"] for q in test["questions"]]
    text = json.dumps(test)
    assert "correct_choices" not in text and "1000000000" not in text
    # Frozen: reading it again gives the same questions.
    again = client.get(f"/v1/tests/{test['id']}", headers=AUTH).json()
    assert [q["id"] for q in again["questions"]] == [q["id"] for q in test["questions"]]
    assert client.get(f"/v1/tests/{test['id']}", headers=OTHER).status_code == 404


def test_test_is_never_short(client):
    create_problem(client)
    add(client, qcm("only-one"))
    recipe = [{"language": "python", "level": 1, "code": 1}, {"language": "docker", "level": 2, "qcm": 2}]
    response = client.post("/v1/tests", json={"recipe": recipe}, headers=AUTH)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "not_enough_questions"
    assert error["shortages"] == [{"language": "docker", "level": 2, "kind": "qcm", "needed": 2, "available": 1}]


def test_tests_in_one_scope_prefer_unused_questions(client):
    for i in range(4):
        add(client, qcm(f"q-{i}"))
    recipe = [{"language": "docker", "level": 2, "qcm": 2}]
    first = client.post("/v1/tests", json={"recipe": recipe, "scope": "acme"}, headers=AUTH).json()
    second = client.post("/v1/tests", json={"recipe": recipe, "scope": "acme"}, headers=AUTH).json()
    ids = lambda t: {q["id"] for q in t["questions"]}  # noqa: E731
    assert not ids(first) & ids(second)
    # Everything used: questions repeat rather than leave the test short.
    third = client.post("/v1/tests", json={"recipe": recipe, "scope": "acme"}, headers=AUTH)
    assert third.status_code == 201


def test_recipe_is_validated(client):
    dup = [{"language": "python", "level": 1, "code": 1}, {"language": "python", "level": 1, "qcm": 1}]
    assert client.post("/v1/tests", json={"recipe": dup}, headers=AUTH).status_code == 400
    empty = [{"language": "python", "level": 1}]
    assert client.post("/v1/tests", json={"recipe": empty}, headers=AUTH).status_code == 400


def test_question_in_a_test_cannot_be_deleted(client):
    question = add(client, qcm("ps"))
    client.post("/v1/tests", json={"recipe": [{"language": "docker", "level": 2, "qcm": 1}]}, headers=AUTH)
    response = client.delete(f"/v1/problems/{question['id']}", headers=AUTH)
    assert response.status_code == 409
