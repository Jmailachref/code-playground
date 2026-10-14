"""Request and response bodies for the /v1 API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

MAX_SOURCE_BYTES = 64 * 1024
MAX_STDIN_BYTES = 1024 * 1024
MAX_IO_BYTES = 8 * 1024 * 1024

Comparator = Literal["exact", "trim", "tokens", "float"]
Level = Annotated[
    int, Field(ge=1, le=5, description="Difficulty: 1 beginner, 2 intermediate, 3 advanced, 4 expert, 5 master")
]
Kind = Literal["code", "qcm"]
Status = Literal["pending", "approved", "rejected"]
Topic = Annotated[
    str,
    Field(
        min_length=1,
        max_length=30,
        pattern=r"^[a-z0-9][a-z0-9+#.-]*$",
        description="Code: the language it is solved in (python). QCM: its topic, a language or anything else (docker)",
    ),
]
Choices = Annotated[list[Annotated[str, Field(min_length=1, max_length=2000)]], Field(min_length=2, max_length=10)]


class LanguageOut(BaseModel):
    id: str
    display_name: str
    compiled: bool
    time_multiplier: float
    template: str


class ScenarioIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    input: str = Field(default="", max_length=MAX_IO_BYTES)
    expected_output: str = Field(max_length=MAX_IO_BYTES)
    hidden: bool = False
    weight: int = Field(default=1, ge=0, le=1000)


class ScenarioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    input: str | None = Field(default=None, max_length=MAX_IO_BYTES)
    expected_output: str | None = Field(default=None, max_length=MAX_IO_BYTES)
    hidden: bool | None = None
    weight: int | None = Field(default=None, ge=0, le=1000)
    order: int | None = None


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    order: int
    input: str
    expected_output: str
    hidden: bool
    weight: int


def check_qcm_fields(kind: str, choices: list[str] | None, correct: list[int] | None, scenarios: list | None) -> None:
    if kind == "qcm":
        if not choices or not correct:
            raise ValueError("a qcm question needs choices and correct_choices")
        if len(set(correct)) != len(correct) or any(i < 0 or i >= len(choices) for i in correct):
            raise ValueError("correct_choices must be distinct indexes into choices")
        if scenarios:
            raise ValueError("a qcm question has no scenarios")
    elif choices is not None or correct is not None:
        raise ValueError("only qcm questions have choices")


class ProblemIn(BaseModel):
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=1, max_length=200)
    statement: str = ""
    kind: Kind = "code"
    status: Status = "approved"
    time_limit_ms: int = Field(default=2000, ge=100, le=10_000)
    memory_limit_mb: int = Field(default=256, ge=32, le=1024)
    comparator: Comparator = "trim"
    language: Topic
    level: Level = 1
    timer_seconds: int = Field(default=180, ge=10, le=7200, description="Time the candidate gets for this question")
    starter_code: str | None = Field(
        default=None, max_length=MAX_SOURCE_BYTES, description="Pre-filled editor code; null uses the language template"
    )
    choices: Choices | None = Field(default=None, description="QCM only: the options shown")
    correct_choices: list[int] | None = Field(default=None, description="QCM only: indexes of the right options")
    scenarios: list[ScenarioIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def qcm_fields(self) -> ProblemIn:
        check_qcm_fields(self.kind, self.choices, self.correct_choices, self.scenarios)
        return self


class ProblemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    statement: str | None = None
    time_limit_ms: int | None = Field(default=None, ge=100, le=10_000)
    memory_limit_mb: int | None = Field(default=None, ge=32, le=1024)
    comparator: Comparator | None = None
    language: Topic | None = None
    level: Level | None = None
    status: Status | None = None
    timer_seconds: int | None = Field(default=None, ge=10, le=7200)
    starter_code: str | None = Field(default=None, max_length=MAX_SOURCE_BYTES)
    choices: Choices | None = None
    correct_choices: list[int] | None = None


class ProblemSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    kind: str
    language: str
    level: int
    status: str


class ProblemOut(ProblemSummary):
    """What a candidate may see: no hidden test cases, no right answers."""

    statement: str
    timer_seconds: int
    time_limit_ms: int
    memory_limit_mb: int
    comparator: str
    starter_code: str | None = Field(description="Code to pre-fill the editor with (code questions)")
    choices: list[str] | None = Field(description="The options (QCM questions)")
    multiple: bool = Field(description="QCM: more than one option is right")
    scenarios: list[ScenarioOut]
    hidden_scenarios: int = Field(description="How many hidden test cases exist (not returned)")


class ProblemFull(ProblemOut):
    """Everything, for whoever writes questions: hidden test cases and right answers included."""

    correct_choices: list[int] | None


class StockOut(BaseModel):
    language: str
    level: int
    code: int = Field(description="Approved code questions")
    qcm: int = Field(description="Approved QCM questions")


class RecipeRow(BaseModel):
    language: Topic
    level: Level
    code: int = Field(default=0, ge=0, le=50, description="How many code questions to draw")
    qcm: int = Field(default=0, ge=0, le=50, description="How many QCM questions to draw")


class TestIn(BaseModel):
    recipe: list[RecipeRow] = Field(min_length=1, max_length=30)
    scope: str | None = Field(
        default=None, max_length=200, description="Tests in one scope (a company) avoid repeating questions"
    )
    external_ref: str | None = Field(default=None, max_length=200, description="Your id for this test, e.g. a session")

    @model_validator(mode="after")
    def rows_are_distinct(self) -> TestIn:
        keys = [(r.language, r.level) for r in self.recipe]
        if len(set(keys)) != len(keys):
            raise ValueError("each language and level appears once in a recipe")
        if not any(r.code or r.qcm for r in self.recipe):
            raise ValueError("a recipe asks for at least one question")
        return self


class TestOut(BaseModel):
    id: uuid.UUID
    scope: str | None
    external_ref: str | None
    recipe: list[RecipeRow]
    questions: list[ProblemOut]
    created_at: datetime


class ShortRow(BaseModel):
    language: str
    level: int
    kind: str
    needed: int
    available: int


class RunIn(BaseModel):
    language: str
    source_code: str = Field(max_length=MAX_SOURCE_BYTES)
    stdin: str = Field(default="", max_length=MAX_STDIN_BYTES)
    user_id: str | None = Field(default=None, max_length=200)


class SubmissionIn(BaseModel):
    problem_id: uuid.UUID
    language: str
    source_code: str = Field(max_length=MAX_SOURCE_BYTES)
    user_id: str | None = Field(default=None, max_length=200)
    callback_url: HttpUrl | None = None


class Accepted(BaseModel):
    id: uuid.UUID
    status: str


class RunOut(BaseModel):
    id: uuid.UUID
    status: str
    language: str
    verdict: str | None = None
    stdout: str = ""
    stderr: str = ""
    compile_output: str = ""
    exit_code: int | None = None
    time_ms: int | None = None
    memory_kb: int | None = None
    created_at: datetime
    finished_at: datetime | None = None


class ResultOut(BaseModel):
    scenario: str
    verdict: str
    hidden: bool = False
    time_ms: int
    memory_kb: int
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    expected_output: str | None = None


class SubmissionOut(BaseModel):
    id: uuid.UUID
    problem_id: uuid.UUID | None
    user_id: str | None
    language: str
    status: str
    verdict: str | None
    score: int
    max_score: int
    passed: int
    total: int
    compile_output: str
    source_code: str
    results: list[ResultOut]
    created_at: datetime
    finished_at: datetime | None


class SubmissionSummary(BaseModel):
    id: uuid.UUID
    problem_id: uuid.UUID | None
    user_id: str | None
    language: str
    status: str
    verdict: str | None
    passed: int
    total: int
    score: int
    max_score: int
    created_at: datetime
