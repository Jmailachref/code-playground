"""The /v1 REST API: languages, playground runs, problems with scenarios, submissions."""
from __future__ import annotations

import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from api import schemas
from api.auth import client_id
from api.ui import mount_ui
from core.db import get_session
from core.languages import load_languages
from core.models import Problem, Scenario, Submission
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


def check_language(language: str, allowed: list[str] | None = None) -> None:
    if language not in load_languages():
        supported = ", ".join(load_languages())
        raise api_error(400, "unsupported_language", f"'{language}' is not supported; use one of: {supported}")
    if allowed and language not in allowed:
        raise api_error(400, "language_not_allowed", f"this problem accepts: {', '.join(allowed)}")


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


def problem_out(problem: Problem) -> schemas.ProblemOut:
    visible = [s for s in problem.scenarios if not s.hidden]
    return schemas.ProblemOut(
        id=problem.id,
        slug=problem.slug,
        title=problem.title,
        statement=problem.statement,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
        comparator=problem.comparator,
        languages=problem.languages,
        scenarios=[schemas.ScenarioOut.model_validate(s) for s in visible],
        hidden_scenarios=len(problem.scenarios) - len(visible),
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
def list_problems(_: str = Depends(client_id), session: Session = Depends(get_session)) -> list[Problem]:
    return list(session.scalars(select(Problem).order_by(Problem.created_at)))


@app.post("/v1/problems", status_code=201, response_model=schemas.ProblemOut, tags=["problems"])
def create_problem(
    body: schemas.ProblemIn, _: str = Depends(client_id), session: Session = Depends(get_session)
) -> schemas.ProblemOut:
    for language in body.languages:
        check_language(language)
    problem = Problem(**body.model_dump(exclude={"scenarios"}))
    problem.scenarios = [Scenario(order=i, **s.model_dump()) for i, s in enumerate(body.scenarios)]
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


@app.patch("/v1/problems/{problem_id}", response_model=schemas.ProblemOut, tags=["problems"])
def update_problem(
    problem_id: uuid.UUID,
    body: schemas.ProblemUpdate,
    _: str = Depends(client_id),
    session: Session = Depends(get_session),
) -> schemas.ProblemOut:
    problem = get_problem(session, problem_id)
    for language in body.languages or []:
        check_language(language)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(problem, field, value)
    session.commit()
    return problem_out(problem)


@app.delete("/v1/problems/{problem_id}", status_code=204, tags=["problems"])
def delete_problem(
    problem_id: uuid.UUID, _: str = Depends(client_id), session: Session = Depends(get_session)
) -> None:
    session.delete(get_problem(session, problem_id))
    session.commit()


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


# --- submissions ------------------------------------------------------------


@app.post("/v1/submissions", status_code=202, response_model=schemas.Accepted, tags=["submissions"])
def create_submission(
    body: schemas.SubmissionIn, client: str = Depends(client_id), session: Session = Depends(get_session)
) -> schemas.Accepted:
    problem = get_problem(session, body.problem_id)
    check_language(body.language, problem.languages)
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
