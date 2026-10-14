"""The /v1 REST API: languages, playground runs, questions with scenarios, tests, submissions."""
from __future__ import annotations

import random
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from api import schemas
from api.auth import client_id
from api.ui import mount_ui
from core.db import get_session
from core.languages import load_languages
from core.models import Problem, Scenario, Submission, Test, TestQuestion
from core.config import settings
from core.queue import enqueue, queue_depth
from core.ratelimit import hit

app = FastAPI(
    title="Code Playground API",
    version="0.1.0",
    description="Run code in any supported language and judge it against test cases.",
)


# --- errors -----------------------------------------------------------------


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code, detail={"code": code, "message": message})


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        error = exc.detail
    else:
        codes = {401: "unauthorized", 404: "not_found", 413: "too_large", 429: "rate_limited"}
        error = {"code": codes.get(exc.status_code, "error"), "message": str(exc.detail)}
    return JSONResponse({"error": error}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    too_long = any(e["type"] == "string_too_long" and e["loc"][-1] == "source_code" for e in exc.errors())
    if too_long:
        error = {"code": "source_too_large", "message": "source_code is larger than 64 KB"}
        return JSONResponse({"error": error}, status_code=413)
    error = {"code": "invalid_request", "message": "request body is invalid", "details": exc.errors()}
    return JSONResponse({"error": jsonable_encoder(error)}, status_code=400)


# --- helpers ----------------------------------------------------------------


def rate_limit(client: str) -> None:
    """Limit how many runs and submissions each API key starts per minute.

    The web UI's own key is exempt: its proxy limits each visitor instead.
    """
    if settings.ui_api_key and client == settings.api_keys.get(settings.ui_api_key):
        return
    retry_after = hit(f"client:{client}", settings.rate_limit_per_minute)
    if retry_after is not None:
        raise HTTPException(
            429,
            detail={"code": "rate_limited", "message": f"too many runs; retry in {retry_after} s"},
            headers={"Retry-After": str(retry_after)},
        )


def check_language(language: str, allowed: str | None = None) -> None:
    if language not in load_languages():
        supported = ", ".join(load_languages())
        raise api_error(400, "unsupported_language", f"'{language}' is not supported; use one of: {supported}")
    if allowed is not None and language != allowed:
        raise api_error(400, "language_not_allowed", f"this problem is solved in {allowed}")


def language_template(language: str) -> str:
    lang = load_languages().get(language)
    return lang.template if lang else ""


def get_problem(session: Session, problem_id: uuid.UUID) -> Problem:
    problem = session.get(Problem, problem_id, options=[selectinload(Problem.scenarios)])
    if problem is None:
        raise api_error(404, "problem_not_found", f"no problem with id {problem_id}")
    return problem


def get_own_submission(session: Session, submission_id: uuid.UUID, client: str, run: bool) -> Submission:
    submission = session.get(Submission, submission_id, options=[selectinload(Submission.results)])
    if submission is None or submission.client_id != client or submission.is_run != run:
        kind = "run" if run else "submission"
        raise api_error(404, f"{kind}_not_found", f"no {kind} with id {submission_id}")
    return submission


def problem_fields(problem: Problem) -> dict:
    visible = [s for s in problem.scenarios if not s.hidden]
    starter = problem.starter_code
    if problem.kind == "code" and starter is None:
        starter = language_template(problem.language)
    return dict(
        id=problem.id,
        slug=problem.slug,
        title=problem.title,
        kind=problem.kind,
        status=problem.status,
        statement=problem.statement,
        timer_seconds=problem.timer_seconds,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
        comparator=problem.comparator,
        language=problem.language,
        level=problem.level,
        starter_code=starter,
        choices=problem.choices,
        multiple=len(problem.correct_choices or []) > 1,
        scenarios=[schemas.ScenarioOut.model_validate(s) for s in visible],
        hidden_scenarios=len(problem.scenarios) - len(visible),
    )


def problem_out(problem: Problem) -> schemas.ProblemOut:
    return schemas.ProblemOut(**problem_fields(problem))


def problem_full(problem: Problem) -> schemas.ProblemFull:
    fields = problem_fields(problem)
    fields["scenarios"] = [schemas.ScenarioOut.model_validate(s) for s in problem.scenarios]
    return schemas.ProblemFull(**fields, correct_choices=problem.correct_choices)


def check_question(problem: Problem) -> None:
    """Rules that span fields, checked after a create or an update."""
    if problem.kind == "code":
        check_language(problem.language)
    try:
        schemas.check_qcm_fields(
            problem.kind, problem.choices, problem.correct_choices, problem.scenarios if problem.kind == "qcm" else None
        )
    except ValueError as exc:
        raise api_error(400, "invalid_question", str(exc))


def get_own_test(session: Session, test_id: uuid.UUID, client: str) -> Test:
    test = session.get(Test, test_id)
    if test is None or test.client_id != client:
        raise api_error(404, "test_not_found", f"no test with id {test_id}")
    return test


def test_out(test: Test) -> schemas.TestOut:
    return schemas.TestOut(
        id=test.id,
        scope=test.scope,
        external_ref=test.external_ref,
        recipe=test.recipe,
        questions=[problem_out(q.problem) for q in test.questions],
        created_at=test.created_at,
    )


def submission_out(submission: Submission) -> schemas.SubmissionOut:
    results, hidden_count = [], 0
    for r in submission.results:
        if r.hidden:
            hidden_count += 1
            # Hidden test cases report a verdict only: never their input or output.
            results.append(
                schemas.ResultOut(
                    scenario=f"Hidden #{hidden_count}",
                    verdict=r.verdict,
                    hidden=True,
                    time_ms=r.time_ms,
                    memory_kb=r.memory_kb,
                )
            )
        else:
            results.append(
                schemas.ResultOut(
                    scenario=r.name,
                    verdict=r.verdict,
                    time_ms=r.time_ms,
                    memory_kb=r.memory_kb,
                    exit_code=r.exit_code,
                    stdout=r.stdout,
                    stderr=r.stderr,
                    expected_output=r.expected_output,
                )
            )
    return schemas.SubmissionOut(
        id=submission.id,
        problem_id=submission.problem_id,
        user_id=submission.user_id,
        language=submission.language,
        status=submission.status,
        verdict=submission.verdict,
        score=submission.score,
        max_score=submission.max_score,
        passed=submission.passed,
        total=submission.total,
        compile_output=submission.compile_output,
        source_code=submission.source_code,
        results=results,
        created_at=submission.created_at,
        finished_at=submission.finished_at,
    )


def run_out(run: Submission) -> schemas.RunOut:
    out = schemas.RunOut(
        id=run.id,
        status=run.status,
        language=run.language,
        verdict=run.verdict,
        compile_output=run.compile_output,
        created_at=run.created_at,
        finished_at=run.finished_at,
    )
    if run.results:
        r = run.results[0]
        out.stdout, out.stderr, out.exit_code = r.stdout, r.stderr, r.exit_code
        out.time_ms, out.memory_kb = r.time_ms, r.memory_kb
    return out


# --- languages & health -----------------------------------------------------


@app.get("/v1/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "queue_depth": queue_depth()}


@app.get("/v1/languages", response_model=list[schemas.LanguageOut], tags=["meta"])
def list_languages(_: str = Depends(client_id)) -> list[schemas.LanguageOut]:
    return [
        schemas.LanguageOut(
            id=lang.id,
            display_name=lang.display_name,
            compiled=lang.compile is not None,
            time_multiplier=lang.time_multiplier,
            template=lang.template,
        )
        for lang in load_languages().values()
    ]


# --- playground runs --------------------------------------------------------


@app.post("/v1/runs", status_code=202, response_model=schemas.Accepted, tags=["runs"])
def create_run(
    body: schemas.RunIn, client: str = Depends(client_id), session: Session = Depends(get_session)
) -> schemas.Accepted:
    check_language(body.language)
    rate_limit(client)
    run = Submission(
        client_id=client,
        user_id=body.user_id,
        language=body.language,
        source_code=body.source_code,
        stdin=body.stdin,
        status="queued",
    )
    session.add(run)
    session.commit()
    enqueue(run.id)
    return schemas.Accepted(id=run.id, status=run.status)


@app.get("/v1/runs/{run_id}", response_model=schemas.RunOut, tags=["runs"])
def read_run(
    run_id: uuid.UUID, client: str = Depends(client_id), session: Session = Depends(get_session)
) -> schemas.RunOut:
    return run_out(get_own_submission(session, run_id, client, run=True))


# --- problems & scenarios ---------------------------------------------------


@app.get("/v1/problems", response_model=list[schemas.ProblemSummary], tags=["problems"])
def list_problems(
    language: str | None = None,
    level: int | None = Query(default=None, ge=1, le=5),
    kind: schemas.Kind | None = None,
    status: schemas.Status | None = None,
    _: str = Depends(client_id),
    session: Session = Depends(get_session),
) -> list[Problem]:
    """List questions, easiest first, optionally for one language or topic, level, kind and/or status."""
    query = select(Problem).order_by(Problem.language, Problem.level, Problem.created_at)
    if language is not None:
        query = query.where(Problem.language == language)
    if level is not None:
        query = query.where(Problem.level == level)
    if kind is not None:
        query = query.where(Problem.kind == kind)
    if status is not None:
        query = query.where(Problem.status == status)
    return list(session.scalars(query))


@app.post("/v1/problems", status_code=201, response_model=schemas.ProblemOut, tags=["problems"])
def create_problem(
    body: schemas.ProblemIn, _: str = Depends(client_id), session: Session = Depends(get_session)
) -> schemas.ProblemOut:
    problem = Problem(**body.model_dump(exclude={"scenarios"}))
    problem.scenarios = [Scenario(order=i, **s.model_dump()) for i, s in enumerate(body.scenarios)]
    check_question(problem)
    session.add(problem)
    try:
        session.commit()
    except IntegrityError:
        raise api_error(409, "slug_taken", f"a problem with slug '{body.slug}' already exists")
    return problem_out(problem)


@app.get("/v1/problems/{problem_id}", response_model=schemas.ProblemOut, tags=["problems"])
def read_problem(
    problem_id: uuid.UUID, _: str = Depends(client_id), session: Session = Depends(get_session)
) -> schemas.ProblemOut:
    return problem_out(get_problem(session, problem_id))


@app.get("/v1/problems/{problem_id}/full", response_model=schemas.ProblemFull, tags=["problems"])
def read_problem_full(
    problem_id: uuid.UUID, _: str = Depends(client_id), session: Session = Depends(get_session)
) -> schemas.ProblemFull:
    """The whole question, hidden test cases and right answers included. Never reachable from the web UI."""
    return problem_full(get_problem(session, problem_id))


@app.patch("/v1/problems/{problem_id}", response_model=schemas.ProblemOut, tags=["problems"])
def update_problem(
    problem_id: uuid.UUID,
    body: schemas.ProblemUpdate,
    _: str = Depends(client_id),
    session: Session = Depends(get_session),
) -> schemas.ProblemOut:
    problem = get_problem(session, problem_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(problem, field, value)
    check_question(problem)
    session.commit()
    return problem_out(problem)


@app.delete("/v1/problems/{problem_id}", status_code=204, tags=["problems"])
def delete_problem(
    problem_id: uuid.UUID, _: str = Depends(client_id), session: Session = Depends(get_session)
) -> None:
    session.delete(get_problem(session, problem_id))
    try:
        session.commit()
    except IntegrityError:
        raise api_error(409, "problem_in_use", "this question is part of a test; reject it instead of deleting it")


@app.post(
    "/v1/problems/{problem_id}/scenarios", status_code=201, response_model=list[schemas.ScenarioOut], tags=["problems"]
)
def add_scenarios(
    problem_id: uuid.UUID,
    body: list[schemas.ScenarioIn],
    _: str = Depends(client_id),
    session: Session = Depends(get_session),
) -> list[Scenario]:
    problem = get_problem(session, problem_id)
    if problem.kind != "code":
        raise api_error(400, "invalid_question", "only code questions have scenarios")
    start = max((s.order for s in problem.scenarios), default=-1) + 1
    added = [Scenario(order=start + i, **s.model_dump()) for i, s in enumerate(body)]
    problem.scenarios.extend(added)
    session.commit()
    return added


@app.patch(
    "/v1/problems/{problem_id}/scenarios/{scenario_id}", response_model=schemas.ScenarioOut, tags=["problems"]
)
def update_scenario(
    problem_id: uuid.UUID,
    scenario_id: uuid.UUID,
    body: schemas.ScenarioUpdate,
    _: str = Depends(client_id),
    session: Session = Depends(get_session),
) -> Scenario:
    scenario = session.get(Scenario, scenario_id)
    if scenario is None or scenario.problem_id != problem_id:
        raise api_error(404, "scenario_not_found", f"no scenario with id {scenario_id} in this problem")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(scenario, field, value)
    session.commit()
    return scenario


@app.delete("/v1/problems/{problem_id}/scenarios/{scenario_id}", status_code=204, tags=["problems"])
def delete_scenario(
    problem_id: uuid.UUID,
    scenario_id: uuid.UUID,
    _: str = Depends(client_id),
    session: Session = Depends(get_session),
) -> None:
    scenario = session.get(Scenario, scenario_id)
    if scenario is None or scenario.problem_id != problem_id:
        raise api_error(404, "scenario_not_found", f"no scenario with id {scenario_id} in this problem")
    session.delete(scenario)
    session.commit()


# --- question stock & tests -------------------------------------------------


@app.get("/v1/stock", response_model=list[schemas.StockOut], tags=["tests"])
def stock(
    language: str | None = None, _: str = Depends(client_id), session: Session = Depends(get_session)
) -> list[schemas.StockOut]:
    """How many approved questions exist per language (or topic) and level, by kind."""
    query = (
        select(Problem.language, Problem.level, Problem.kind, func.count())
        .where(Problem.status == "approved")
        .group_by(Problem.language, Problem.level, Problem.kind)
    )
    if language is not None:
        query = query.where(Problem.language == language)
    counts: dict[tuple[str, int], schemas.StockOut] = {}
    for lang, level, kind, n in session.execute(query):
        row = counts.setdefault((lang, level), schemas.StockOut(language=lang, level=level, code=0, qcm=0))
        setattr(row, kind, n)
    return [counts[k] for k in sorted(counts)]


@app.post("/v1/tests", status_code=201, response_model=schemas.TestOut, tags=["tests"])
def create_test(
    body: schemas.TestIn, client: str = Depends(client_id), session: Session = Depends(get_session)
) -> schemas.TestOut:
    """Draws the questions for one candidate from the approved questions and freezes them.

    Each recipe row asks for some code and some QCM questions of one language
    (or topic) and level. Questions no earlier test in the same scope used are
    picked first; used ones fill the gap only when there are not enough fresh
    ones. A question never appears twice in one test, and a test is never
    created short: if any row cannot be filled the answer is 409 with what is
    missing.
    """
    used: set[uuid.UUID] = set()
    if body.scope is not None:
        used = set(
            session.scalars(
                select(TestQuestion.problem_id).join(Test).where(Test.client_id == client, Test.scope == body.scope)
            )
        )
    rng = random.SystemRandom()
    picked: list[uuid.UUID] = []
    shortages: list[schemas.ShortRow] = []
    for row in body.recipe:
        for kind, needed in (("code", row.code), ("qcm", row.qcm)):
            if needed == 0:
                continue
            pool = list(
                session.scalars(
                    select(Problem.id).where(
                        Problem.language == row.language,
                        Problem.level == row.level,
                        Problem.kind == kind,
                        Problem.status == "approved",
                    )
                )
            )
            fresh = [p for p in pool if p not in used]
            chosen = rng.sample(fresh, min(needed, len(fresh)))
            if len(chosen) < needed:
                seen = [p for p in pool if p in used]
                chosen += rng.sample(seen, min(needed - len(chosen), len(seen)))
            if len(chosen) < needed:
                shortages.append(
                    schemas.ShortRow(language=row.language, level=row.level, kind=kind, needed=needed, available=len(pool))
                )
            picked += chosen
    if shortages:
        raise HTTPException(
            409,
            detail={
                "code": "not_enough_questions",
                "message": "there are not enough approved questions for this recipe",
                "shortages": [s.model_dump() for s in shortages],
            },
        )
    test = Test(
        client_id=client,
        scope=body.scope,
        external_ref=body.external_ref,
        recipe=[r.model_dump() for r in body.recipe],
        questions=[TestQuestion(problem_id=pid, position=i) for i, pid in enumerate(picked)],
    )
    session.add(test)
    session.commit()
    session.refresh(test)
    return test_out(test)


@app.get("/v1/tests/{test_id}", response_model=schemas.TestOut, tags=["tests"])
def read_test(
    test_id: uuid.UUID, client: str = Depends(client_id), session: Session = Depends(get_session)
) -> schemas.TestOut:
    """The frozen test as the candidate sees it: no hidden test cases, no right answers."""
    return test_out(get_own_test(session, test_id, client))


# --- submissions ------------------------------------------------------------


@app.post("/v1/submissions", status_code=202, response_model=schemas.Accepted, tags=["submissions"])
def create_submission(
    body: schemas.SubmissionIn, client: str = Depends(client_id), session: Session = Depends(get_session)
) -> schemas.Accepted:
    problem = get_problem(session, body.problem_id)
    if problem.kind != "code":
        raise api_error(400, "not_code", "only code questions take submissions")
    check_language(body.language, problem.language)
    if not problem.scenarios:
        raise api_error(400, "no_scenarios", "this problem has no test cases yet")
    rate_limit(client)
    submission = Submission(
        client_id=client,
        user_id=body.user_id,
        problem_id=problem.id,
        language=body.language,
        source_code=body.source_code,
        callback_url=str(body.callback_url) if body.callback_url else None,
        status="queued",
        total=len(problem.scenarios),
        max_score=sum(s.weight for s in problem.scenarios),
    )
    session.add(submission)
    session.commit()
    enqueue(submission.id)
    return schemas.Accepted(id=submission.id, status=submission.status)


@app.get("/v1/submissions/{submission_id}", response_model=schemas.SubmissionOut, tags=["submissions"])
def read_submission(
    submission_id: uuid.UUID, client: str = Depends(client_id), session: Session = Depends(get_session)
) -> schemas.SubmissionOut:
    return submission_out(get_own_submission(session, submission_id, client, run=False))


@app.get("/v1/submissions", response_model=list[schemas.SubmissionSummary], tags=["submissions"])
def list_submissions(
    user_id: str | None = None,
    problem_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    client: str = Depends(client_id),
    session: Session = Depends(get_session),
) -> list[schemas.SubmissionSummary]:
    query = select(Submission).where(Submission.client_id == client, Submission.problem_id.is_not(None))
    if user_id is not None:
        query = query.where(Submission.user_id == user_id)
    if problem_id is not None:
        query = query.where(Submission.problem_id == problem_id)
    rows = session.scalars(query.order_by(Submission.created_at.desc()).limit(limit))
    return [
        schemas.SubmissionSummary(
            id=s.id,
            problem_id=s.problem_id,
            user_id=s.user_id,
            language=s.language,
            status=s.status,
            verdict=s.verdict,
            passed=s.passed,
            total=s.total,
            score=s.score,
            max_score=s.max_score,
            created_at=s.created_at,
        )
        for s in rows
    ]


# Last, so the UI's catch-all static mount never shadows an API route.
mount_ui(app)
