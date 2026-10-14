"""Check sample questions before they go into the bank.

    python -m api.check_examples                       # every file under examples/
    python -m api.check_examples examples/python/*.json

Each file must be a valid question with a unique slug. A code question must
have a reference solution at examples/solutions/<language>/<slug>.<ext> that
passes every one of its test cases, hidden ones included, in the sandbox.
Exits 1 if anything fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import ValidationError

from api.schemas import ProblemIn
from core.languages import get_language
from runner.judge import Comparator, Limits, Scenario, judge

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
EXTENSIONS = {"python": "py", "javascript": "js", "java": "java", "cpp": "cpp", "go": "go", "sql": "sql"}


def question_files() -> list[Path]:
    return sorted(p for p in EXAMPLES.glob("*/*.json") if p.parent.name != "solutions")


def solution_path(problem: ProblemIn) -> Path:
    return EXAMPLES / "solutions" / problem.language / f"{problem.slug}.{EXTENSIONS.get(problem.language, problem.language)}"


def check(path: Path, run_solutions: bool = True) -> list[str]:
    """Problems found in one file; empty when it is fine."""
    try:
        problem = ProblemIn.model_validate(json.loads(path.read_text()))
    except (ValueError, ValidationError) as exc:
        return [f"not a valid question: {exc}"]
    errors = []
    if path.stem != problem.slug:
        errors.append(f"file name should be {problem.slug}.json")
    if problem.kind == "qcm":
        if len(set(problem.choices)) != len(problem.choices):
            errors.append("two choices are the same")
        return errors
    if not problem.scenarios:
        return errors + ["a code question needs test cases"]
    if not any(s.hidden for s in problem.scenarios) or all(s.hidden for s in problem.scenarios):
        errors.append("needs at least one visible and one hidden test case")
    solution = solution_path(problem)
    if not solution.is_file():
        return errors + [f"no reference solution at {solution.relative_to(ROOT)}"]
    if run_solutions:
        result = judge(
            get_language(problem.language),
            solution.read_text(),
            [Scenario(s.name, s.input, s.expected_output, s.hidden, s.weight) for s in problem.scenarios],
            Limits(problem.time_limit_ms, problem.memory_limit_mb),
            Comparator(problem.comparator),
        )
        for r in result.results:
            if r.verdict != "accepted":
                errors.append(f"reference solution fails {r.scenario!r}: {r.verdict}")
        if result.compile_output and result.verdict == "compilation_error":
            errors.append(f"reference solution does not compile: {result.compile_output[:300]}")
    return errors


def main(argv: list[str]) -> int:
    paths = [Path(p).resolve() for p in argv] or question_files()
    slugs: dict[str, Path] = {}
    for p in question_files():
        slug = json.loads(p.read_text()).get("slug")
        if slug in slugs:
            print(f"FAIL {p.relative_to(ROOT)}: slug {slug!r} is also used by {slugs[slug].relative_to(ROOT)}")
            return 1
        slugs[slug] = p
    failed = 0
    for path in paths:
        errors = check(path)
        name = path.relative_to(ROOT)
        if errors:
            failed += 1
            for e in errors:
                print(f"FAIL {name}: {e}")
        else:
            print(f"ok   {name}")
    print(f"{len(paths) - failed}/{len(paths)} questions ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
