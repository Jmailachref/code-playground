"""Compile a submission once, run it against scenarios and decide verdicts."""
from __future__ import annotations

import math
import signal
from dataclasses import dataclass, field
from enum import Enum

from core.languages import Language
from runner.sandbox import ProcessResult, Sandbox

COMPILE_CPU_MS = 10_000
COMPILE_WALL_MS = 20_000
COMPILE_FILE_BYTES = 256 * 1024 * 1024  # compilers write large binaries
OUTPUT_LIMIT_BYTES = 1024 * 1024  # more than this is output_limit_exceeded
STORED_OUTPUT_BYTES = 64 * 1024  # what we keep and return per stream
OOM_HINTS = (b"MemoryError", b"OutOfMemoryError", b"std::bad_alloc", b"out of memory", b"heap out of memory")


class Verdict(str, Enum):
    COMPILATION_ERROR = "compilation_error"
    RUNTIME_ERROR = "runtime_error"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"
    WRONG_ANSWER = "wrong_answer"
    ACCEPTED = "accepted"


# Most severe first; a submission's overall verdict is its most severe one.
SEVERITY = list(Verdict)


class Comparator(str, Enum):
    EXACT = "exact"
    TRIM = "trim"
    TOKENS = "tokens"
    FLOAT = "float"


@dataclass
class Limits:
    time_limit_ms: int = 2000
    memory_limit_mb: int = 256


@dataclass
class Scenario:
    name: str
    input: str
    expected_output: str | None = None  # None for a playground run
    hidden: bool = False
    weight: int = 1


@dataclass
class ScenarioResult:
    scenario: str
    verdict: Verdict
    stdout: str
    stderr: str
    exit_code: int
    time_ms: int
    memory_kb: int
    hidden: bool = False
    weight: int = 1


@dataclass
class JudgeResult:
    verdict: Verdict
    compile_output: str = ""
    results: list[ScenarioResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(r.verdict is Verdict.ACCEPTED for r in self.results)

    @property
    def score(self) -> int:
        return sum(r.weight for r in self.results if r.verdict is Verdict.ACCEPTED)


def outputs_match(actual: str, expected: str, comparator: Comparator = Comparator.TRIM) -> bool:
    if comparator is Comparator.EXACT:
        return actual == expected
    if comparator is Comparator.TRIM:
        return _trim(actual) == _trim(expected)
    tokens_a, tokens_e = actual.split(), expected.split()
    if comparator is Comparator.TOKENS:
        return tokens_a == tokens_e
    if len(tokens_a) != len(tokens_e):
        return False
    return all(_float_token_equal(a, e) for a, e in zip(tokens_a, tokens_e))


def _trim(text: str) -> list[str]:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _float_token_equal(actual: str, expected: str, tolerance: float = 1e-6) -> bool:
    try:
        a, e = float(actual), float(expected)
    except ValueError:
        return actual == expected
    return math.isclose(a, e, rel_tol=tolerance, abs_tol=tolerance)


def classify(proc: ProcessResult, cpu_limit_ms: int, memory_limit_mb: int) -> Verdict | None:
    """Verdict from how the process ended, or None if it ended normally."""
    if proc.timed_out or proc.cpu_ms > cpu_limit_ms or proc.signal == signal.SIGXCPU:
        return Verdict.TIME_LIMIT_EXCEEDED
    # Some runtimes (Python) ignore SIGXFSZ and fail the write instead, so a
    # stream that reached the cap counts as too much output either way.
    if proc.signal == signal.SIGXFSZ or max(len(proc.stdout), len(proc.stderr)) >= OUTPUT_LIMIT_BYTES:
        return Verdict.OUTPUT_LIMIT_EXCEEDED
    if proc.signal == signal.SIGKILL and proc.memory_kb >= memory_limit_mb * 1024 * 0.8:
        return Verdict.MEMORY_LIMIT_EXCEEDED
    if proc.exit_code != 0 or proc.signal:
        if any(hint in proc.stderr for hint in OOM_HINTS):
            return Verdict.MEMORY_LIMIT_EXCEEDED
        return Verdict.RUNTIME_ERROR
    return None


def judge(
    language: Language,
    source_code: str,
    scenarios: list[Scenario],
    limits: Limits | None = None,
    comparator: Comparator = Comparator.TRIM,
) -> JudgeResult:
    """Compile once, then run every scenario in the same sandbox.

    Scenarios without an expected output (playground runs) are accepted when
    the program exits cleanly within limits.
    """
    limits = limits or Limits()
    cpu_ms = int(limits.time_limit_ms * language.time_multiplier)
    wall_ms = max(cpu_ms * 3, cpu_ms + 1000)

    with Sandbox(language, limits.memory_limit_mb) as box:
        box.prepare()
        box.write_file(language.source_file, source_code.encode())

        compile_output = ""
        if language.compile:
            proc = box.execute(
                language.compile, b"", COMPILE_CPU_MS, COMPILE_WALL_MS, OUTPUT_LIMIT_BYTES, COMPILE_FILE_BYTES
            )
            compile_output = _text(proc.stdout + proc.stderr)
            if proc.exit_code != 0 or proc.timed_out or proc.signal:
                if proc.timed_out:
                    compile_output += "\nCompilation timed out."
                return JudgeResult(Verdict.COMPILATION_ERROR, compile_output)

        results = []
        for scenario in scenarios:
            proc = box.execute(
                language.run, scenario.input.encode(), cpu_ms, wall_ms, OUTPUT_LIMIT_BYTES, OUTPUT_LIMIT_BYTES
            )
            stdout = _text(proc.stdout)
            verdict = classify(proc, cpu_ms, box.memory_mb)
            if verdict is None:
                if scenario.expected_output is None or outputs_match(stdout, scenario.expected_output, comparator):
                    verdict = Verdict.ACCEPTED
                else:
                    verdict = Verdict.WRONG_ANSWER
            results.append(
                ScenarioResult(
                    scenario=scenario.name,
                    verdict=verdict,
                    stdout=stdout,
                    stderr=_text(proc.stderr),
                    exit_code=proc.exit_code,
                    time_ms=proc.cpu_ms,
                    memory_kb=proc.memory_kb,
                    hidden=scenario.hidden,
                    weight=scenario.weight,
                )
            )

    overall = min((r.verdict for r in results), key=SEVERITY.index, default=Verdict.ACCEPTED)
    return JudgeResult(overall, compile_output, results)


def _text(data: bytes) -> str:
    return data[:STORED_OUTPUT_BYTES].decode("utf-8", errors="replace")
