"""Load example problems into the database, skipping slugs that already exist.

    python -m api.seed examples/*.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import select

from api.schemas import ProblemIn
from core.db import SessionLocal
from core.models import Problem, Scenario


def seed(paths: list[Path]) -> None:
    with SessionLocal() as session:
        for path in paths:
            body = ProblemIn.model_validate(json.loads(path.read_text()))
            if session.scalar(select(Problem).where(Problem.slug == body.slug)):
                print(f"skip   {body.slug} (exists)")
                continue
            problem = Problem(**body.model_dump(exclude={"scenarios"}))
            problem.scenarios = [Scenario(order=i, **s.model_dump()) for i, s in enumerate(body.scenarios)]
            session.add(problem)
            print(f"added  {body.slug}")
        session.commit()


if __name__ == "__main__":
    seed([Path(p) for p in sys.argv[1:]])
