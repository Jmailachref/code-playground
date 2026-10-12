"""Runner worker: takes submission ids off the queue, judges them, stores results.

    python -m runner.worker
"""
from __future__ import annotations

import json
import logging
import signal
import urllib.request
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from core.db import SessionLocal
from core.languages import get_language
from core.models import Problem, ScenarioResult, Submission
from core.queue import dequeue, enqueue, is_queued
from runner import judge as judging

log = logging.getLogger("runner.worker")
CALLBACK_TIMEOUT_S = 5
SWEEP_EVERY_S = 60
# A job running longer than this was lost with its worker (judging takes seconds).
STALE_RUNNING = timedelta(minutes=5)
# A queued job missing from Redis this long was lost (for example a Redis restart).
LOST_QUEUED = timedelta(minutes=2)


def claim(session, submission_id: uuid.UUID) -> bool:
    """Atomically move a job from queued to running, so only one worker takes it."""
    claimed = session.execute(
        update(Submission)
        .where(Submission.id == submission_id, Submission.status == "queued")
        .values(status="running", started_at=datetime.now(timezone.utc))
    )
    session.commit()
    return claimed.rowcount == 1


def process(submission_id: uuid.UUID) -> None:
    """Judge one submission or run and store the outcome."""
    with SessionLocal() as session:
        if not claim(session, submission_id):
            return
        submission = session.get(Submission, submission_id)

        try:
            language = get_language(submission.language)
            if submission.is_run:
                scenarios = [judging.Scenario("run", submission.stdin or "")]
                limits, comparator = judging.Limits(), judging.Comparator.TRIM
                stored = [None]
            else:
                problem = session.get(Problem, submission.problem_id, options=[selectinload(Problem.scenarios)])
                if problem is None:
                    raise LookupError("problem was deleted before judging")
                stored = list(problem.scenarios)
                scenarios = [
                    judging.Scenario(s.name, s.input, s.expected_output, s.hidden, s.weight) for s in stored
                ]
                limits = judging.Limits(problem.time_limit_ms, problem.memory_limit_mb)
                comparator = judging.Comparator(problem.comparator)

            result = judging.judge(language, submission.source_code, scenarios, limits, comparator)
        except Exception as exc:  # anything here is a platform failure, not a verdict
            log.exception("submission %s failed", submission_id)
            submission.status = "failed"
            submission.error = str(exc)
        else:
            submission.status = "completed"
            submission.verdict = result.verdict.value
            submission.compile_output = result.compile_output
            submission.passed = result.passed
            submission.total = len(scenarios)
            submission.score = result.score
            submission.max_score = sum(s.weight for s in scenarios)
            submission.results = [
                ScenarioResult(
                    scenario_id=row.id if row else None,
                    order=i,
                    name=r.scenario,
                    hidden=r.hidden,
                    verdict=r.verdict.value,
                    stdout=r.stdout,
                    stderr=r.stderr,
                    expected_output=row.expected_output if row else None,
                    exit_code=r.exit_code,
                    time_ms=r.time_ms,
                    memory_kb=r.memory_kb,
                )
                for i, (r, row) in enumerate(zip(result.results, stored))
            ]
        submission.finished_at = datetime.now(timezone.utc)
        session.commit()
        log.info("submission %s: %s %s", submission_id, submission.status, submission.verdict or "")

        if submission.callback_url:
            send_callback(submission)


def send_callback(submission: Submission) -> None:
    """POST a short summary to the caller's webhook; the full result stays on GET."""
    body = {
        "id": str(submission.id),
        "status": submission.status,
        "verdict": submission.verdict,
        "passed": submission.passed,
        "total": submission.total,
        "score": submission.score,
        "max_score": submission.max_score,
    }
    request = urllib.request.Request(
        submission.callback_url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=CALLBACK_TIMEOUT_S).close()
    except OSError as exc:
        log.warning("callback for %s failed: %s", submission.id, exc)


def recover_lost_jobs() -> int:
    """Put back on the queue any job a dead worker or a lost queue left behind."""
    now = datetime.now(timezone.utc)
    requeued = 0
    with SessionLocal() as session:
        stale = session.scalars(
            select(Submission).where(Submission.status == "running", Submission.started_at < now - STALE_RUNNING)
        ).all()
        for submission in stale:
            submission.status = "queued"
            submission.started_at = None
        session.commit()
        waiting = session.scalars(
            select(Submission.id).where(Submission.status == "queued", Submission.created_at < now - LOST_QUEUED)
        ).all()
        for submission_id in waiting:
            if not is_queued(submission_id):
                enqueue(submission_id)
                requeued += 1
    if requeued:
        log.warning("requeued %d lost job(s)", requeued)
    return requeued


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("worker started")
    next_sweep = 0.0
    while not stopping:
        if time.monotonic() >= next_sweep:
            recover_lost_jobs()
            next_sweep = time.monotonic() + SWEEP_EVERY_S
        submission_id = dequeue(timeout=2)
        if submission_id is not None:
            process(submission_id)
    log.info("worker stopped")


if __name__ == "__main__":
    main()
