"""Database tables: questions (problems), their scenarios (test cases), tests, submissions and results."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class Problem(Base):
    """A question. kind "code" is judged against its scenarios; kind "qcm" is multiple choice.

    For code, language is the language it is solved in. For a QCM it is the
    topic, which may be a language (python) or anything else (docker).
    """

    __tablename__ = "problems"
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 5", name="ck_problems_level"),
        CheckConstraint("kind IN ('code', 'qcm')", name="ck_problems_kind"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_problems_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str] = mapped_column(Text, default="")
    time_limit_ms: Mapped[int] = mapped_column(Integer, default=2000)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256)
    comparator: Mapped[str] = mapped_column(String(20), default="trim")
    language: Mapped[str] = mapped_column(String(30), index=True)
    level: Mapped[int] = mapped_column(Integer, default=1, server_default="1", index=True)  # 1 beginner .. 5 master
    kind: Mapped[str] = mapped_column(String(10), default="code", server_default="code", index=True)
    # Only approved questions go into tests.
    status: Mapped[str] = mapped_column(String(20), default="approved", server_default="approved", index=True)
    timer_seconds: Mapped[int] = mapped_column(Integer, default=180, server_default="180")
    starter_code: Mapped[str | None] = mapped_column(Text)  # code only; None = the language's template
    choices: Mapped[list[str] | None] = mapped_column(JSON)  # qcm only
    correct_choices: Mapped[list[int] | None] = mapped_column(JSON)  # qcm only, indexes into choices; never public
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scenarios: Mapped[list[Scenario]] = relationship(
        back_populates="problem", cascade="all, delete-orphan", order_by="Scenario.order"
    )


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    order: Mapped[int] = mapped_column(Integer, default=0)
    input: Mapped[str] = mapped_column(Text, default="")
    expected_output: Mapped[str] = mapped_column(Text, default="")
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    weight: Mapped[int] = mapped_column(Integer, default=1)

    problem: Mapped[Problem] = relationship(back_populates="scenarios")


class Test(Base):
    """The questions drawn for one candidate, frozen when the test is created.

    scope groups tests whose questions should not repeat (a company): new
    tests prefer questions no earlier test in the same scope used.
    """

    __tablename__ = "tests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[str] = mapped_column(String(100), index=True)
    scope: Mapped[str | None] = mapped_column(String(200), index=True)
    external_ref: Mapped[str | None] = mapped_column(String(200), index=True)
    recipe: Mapped[list[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    questions: Mapped[list[TestQuestion]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="TestQuestion.position"
    )


class TestQuestion(Base):
    __tablename__ = "test_questions"
    __table_args__ = (UniqueConstraint("test_id", "problem_id", name="uq_test_questions_problem"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("problems.id", ondelete="RESTRICT"), index=True)
    position: Mapped[int] = mapped_column(Integer)

    test: Mapped[Test] = relationship(back_populates="questions")
    problem: Mapped[Problem] = relationship(lazy="joined")


class Submission(Base):
    """A judged submission, or a playground run when problem_id is null."""

    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[str] = mapped_column(String(100), index=True)
    user_id: Mapped[str | None] = mapped_column(String(200), index=True)
    problem_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("problems.id", ondelete="SET NULL"), index=True)
    language: Mapped[str] = mapped_column(String(30))
    source_code: Mapped[str] = mapped_column(Text)
    stdin: Mapped[str | None] = mapped_column(Text)  # playground runs only
    callback_url: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued, running, completed, failed
    verdict: Mapped[str | None] = mapped_column(String(40))
    score: Mapped[int] = mapped_column(Integer, default=0)
    max_score: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    compile_output: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text)  # internal failure detail, never the user's fault
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    results: Mapped[list[ScenarioResult]] = relationship(
        back_populates="submission", cascade="all, delete-orphan", order_by="ScenarioResult.order"
    )

    @property
    def is_run(self) -> bool:
        return self.problem_id is None


class ScenarioResult(Base):
    __tablename__ = "scenario_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scenarios.id", ondelete="SET NULL"))
    order: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(200))
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    verdict: Mapped[str] = mapped_column(String(40))
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    expected_output: Mapped[str | None] = mapped_column(Text)
    exit_code: Mapped[int] = mapped_column(Integer, default=0)
    time_ms: Mapped[int] = mapped_column(Integer, default=0)
    memory_kb: Mapped[int] = mapped_column(Integer, default=0)

    submission: Mapped[Submission] = relationship(back_populates="results")
