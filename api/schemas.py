"""Request and response bodies for the /v1 API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

MAX_SOURCE_BYTES = 64 * 1024
MAX_STDIN_BYTES = 1024 * 1024
MAX_IO_BYTES = 8 * 1024 * 1024

Comparator = Literal["exact", "trim", "tokens", "float"]


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


class ProblemIn(BaseModel):
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=1, max_length=200)
    statement: str = ""
    time_limit_ms: int = Field(default=2000, ge=100, le=10_000)
    memory_limit_mb: int = Field(default=256, ge=32, le=1024)
    comparator: Comparator = "trim"
    languages: list[str] = Field(default_factory=list, description="Allowed languages; empty means all")
    scenarios: list[ScenarioIn] = Field(default_factory=list)


class ProblemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    statement: str | None = None
    time_limit_ms: int | None = Field(default=None, ge=100, le=10_000)
    memory_limit_mb: int | None = Field(default=None, ge=32, le=1024)
    comparator: Comparator | None = None
    languages: list[str] | None = None


class ProblemSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str


class ProblemOut(ProblemSummary):
    statement: str
    time_limit_ms: int
    memory_limit_mb: int
    comparator: str
    languages: list[str]
    scenarios: list[ScenarioOut]
    hidden_scenarios: int = Field(description="How many hidden test cases exist (not returned)")


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
