"""Runner worker: takes submission ids off the queue, judges them, stores results.

    python -m runner.worker
"""
from __future__ import annotations

import json
import logging
import signal
import urllib.request
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import selectinload

from core.db import SessionLocal
from core.languages import get_language
from core.models import Problem, ScenarioResult, Submission
from core.queue import dequeue
from runner import judge as judging

log = logging.getLogger("runner.worker")
CALLBACK_TIMEOUT_S = 5


def process(submission_id: uuid.UUID) -> None:
    """Judge one submission or run and store the outcome."""
    with SessionLocal() as session:
        submission = session.get(Submission, submission_id)
        if submission is None or submission.status != "queued":
            return
        submission.status = "running"
        session.commit()

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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("worker started")
    while not stopping:
        submission_id = dequeue(timeout=2)
        if submission_id is not None:
            process(submission_id)
    log.info("worker stopped")


if __name__ == "__main__":
    main()
