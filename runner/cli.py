"""Command line entry point for the runner.

    python -m runner.cli run python main.py --stdin "hello"
    python -m runner.cli judge cpp main.cpp examples/sum-of-two.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from core.languages import get_language, load_languages
from runner.judge import Comparator, Limits, Scenario, judge


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="runner")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("languages", help="list supported languages")

    run = sub.add_parser("run", help="run code once with stdin")
    run.add_argument("language")
    run.add_argument("source", type=Path)
    run.add_argument("--stdin", default="")
    run.add_argument("--time-limit-ms", type=int, default=2000)
    run.add_argument("--memory-limit-mb", type=int, default=256)

    jdg = sub.add_parser("judge", help="judge code against a problem file")
    jdg.add_argument("language")
    jdg.add_argument("source", type=Path)
    jdg.add_argument("problem", type=Path, help="JSON problem with scenarios")

    args = parser.parse_args(argv)

    if args.command == "languages":
        for lang in load_languages().values():
            print(f"{lang.id:12} {lang.display_name}")
        return 0

    language = get_language(args.language)
    source = args.source.read_text()

    if args.command == "run":
        limits = Limits(args.time_limit_ms, args.memory_limit_mb)
        result = judge(language, source, [Scenario("run", args.stdin)], limits)
    else:
        problem = json.loads(args.problem.read_text())
        limits = Limits(problem.get("time_limit_ms", 2000), problem.get("memory_limit_mb", 256))
        scenarios = [
            Scenario(s["name"], s["input"], s["expected_output"], s.get("hidden", False), s.get("weight", 1))
            for s in problem["scenarios"]
        ]
        comparator = Comparator(problem.get("comparator", "trim"))
        result = judge(language, source, scenarios, limits, comparator)

    output = asdict(result) | {"passed": result.passed, "total": len(result.results), "score": result.score}
    json.dump(output, sys.stdout, indent=2, default=str)
    print()
    return 0 if result.verdict == "accepted" else 1


if __name__ == "__main__":
    sys.exit(main())
