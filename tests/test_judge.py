"""End-to-end tests: real Docker sandboxes, real language images.

Build the images first with `sh languages/build.sh`.
"""
import json
from pathlib import Path

import pytest

from core.languages import get_language
from runner.judge import Comparator, Limits, Scenario, Verdict, judge, outputs_match

ROOT = Path(__file__).resolve().parent.parent
PROBLEM = json.loads((ROOT / "examples" / "python" / "sum-of-two.json").read_text())
SCENARIOS = [
    Scenario(s["name"], s["input"], s["expected_output"], s.get("hidden", False)) for s in PROBLEM["scenarios"]
]
SOLUTIONS = {
    "python": "sum.py",
    "javascript": "sum.js",
    "java": "Sum.java",
    "cpp": "sum.cpp",
    "go": "sum.go",
}


def run(language: str, code: str, stdin: str = "", **limits) -> "ScenarioResult":
    result = judge(get_language(language), code, [Scenario("run", stdin)], Limits(**limits))
    return result


@pytest.mark.parametrize("language", SOLUTIONS)
def test_sum_of_two_is_accepted_in_every_language(language):
    code = (ROOT / "examples" / "solutions" / SOLUTIONS[language]).read_text()
    result = judge(get_language(language), code, SCENARIOS)
    assert result.verdict is Verdict.ACCEPTED, result
    assert result.passed == 3


def test_wrong_answer():
    result = judge(get_language("python"), "print(42)", SCENARIOS)
    assert result.verdict is Verdict.WRONG_ANSWER
    assert [r.verdict for r in result.results] == [Verdict.WRONG_ANSWER] * 3


@pytest.mark.parametrize(
    "language, code",
    [
        ("cpp", "int main() { return x; }"),
        ("java", "public class Main { void broken( }"),
        ("go", "package main\nfunc main() { undefined() }"),
    ],
)
def test_compilation_error(language, code):
    result = judge(get_language(language), code, SCENARIOS)
    assert result.verdict is Verdict.COMPILATION_ERROR
    assert result.compile_output
    assert result.results == []


def test_runtime_error():
    result = run("python", "raise ValueError('boom')")
    assert result.verdict is Verdict.RUNTIME_ERROR
    assert "ValueError: boom" in result.results[0].stderr


def test_infinite_loop_is_time_limit_exceeded():
    result = run("cpp", "int main() { volatile long i = 0; while (true) i++; }", time_limit_ms=500)
    assert result.verdict is Verdict.TIME_LIMIT_EXCEEDED


def test_sleeping_program_hits_the_wall_clock():
    result = run("python", "import time\ntime.sleep(60)", time_limit_ms=500)
    assert result.verdict is Verdict.TIME_LIMIT_EXCEEDED


@pytest.mark.parametrize(
    "language, code",
    [
        ("python", "x = bytearray(1024 * 1024 * 1024)\nprint(len(x))"),
        ("cpp", "#include <vector>\n#include <cstdio>\nint main(){std::vector<char> v(1<<30, 1); printf(\"%d\", v[5]);}"),
        ("javascript", "const a = []; while (true) a.push(new Array(1e6).fill(1));"),
    ],
)
def test_memory_bomb_is_memory_limit_exceeded(language, code):
    result = run(language, code, memory_limit_mb=128, time_limit_ms=5000)
    assert result.verdict is Verdict.MEMORY_LIMIT_EXCEEDED, result.results[0]


def test_heavy_compile_fits_a_small_memory_limit():
    # g++ needs ~250 MB for <bits/stdc++.h>; the program itself still gets only 128 MB.
    ok = run("cpp", "#include <bits/stdc++.h>\nint main(){ std::cout << 1; }", memory_limit_mb=128)
    assert ok.verdict is Verdict.ACCEPTED, ok
    code = "#include <bits/stdc++.h>\nint main(){ std::vector<char> v(512u << 20, 1); std::cout << (int)v[7]; }"
    bomb = run("cpp", code, memory_limit_mb=128, time_limit_ms=5000)
    assert bomb.verdict is Verdict.MEMORY_LIMIT_EXCEEDED, bomb.results[0]


def test_long_output_is_compared_in_full():
    expected = "".join(f"{i}\n" for i in range(50_000))  # ~290 KB, more than is stored
    result = judge(
        get_language("python"), "for i in range(50_000): print(i)", [Scenario("long", "", expected)]
    )
    assert result.verdict is Verdict.ACCEPTED, result.results[0].verdict
    assert len(result.results[0].stdout) == 64 * 1024


SQL_SETUP = "CREATE TABLE people (name TEXT, age INTEGER);\nINSERT INTO people VALUES ('Nora', 34), ('Hugo', NULL);\n"


def test_sql_runs_queries_against_the_setup_script():
    code = "SELECT name, age FROM people ORDER BY name;\nSELECT 'a;b';"
    result = judge(get_language("sql"), code, [Scenario("people", SQL_SETUP, "Hugo|\nNora|34\na;b\n")])
    assert result.verdict is Verdict.ACCEPTED, result.results[0]


def test_sql_error_and_endless_query():
    error = run("sql", "SELECT nme FROM people;", SQL_SETUP)
    assert error.verdict is Verdict.RUNTIME_ERROR
    assert "no such column: nme" in error.results[0].stderr
    endless = "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) SELECT count(*) FROM n;"
    assert run("sql", endless, time_limit_ms=500).verdict is Verdict.TIME_LIMIT_EXCEEDED


def test_output_flood_is_output_limit_exceeded():
    result = run("python", "while True: print('x' * 1000)")
    assert result.verdict is Verdict.OUTPUT_LIMIT_EXCEEDED


def test_fork_bomb_is_contained():
    code = "import os\nwhile True:\n    try:\n        os.fork()\n    except OSError:\n        pass"
    result = run("python", code, time_limit_ms=1000)
    assert result.verdict in (Verdict.TIME_LIMIT_EXCEEDED, Verdict.RUNTIME_ERROR)


def test_no_network():
    code = "import socket\nsocket.create_connection(('1.1.1.1', 80), timeout=2)\nprint('connected')"
    result = run("python", code)
    assert result.verdict is Verdict.RUNTIME_ERROR
    assert "connected" not in result.results[0].stdout


def test_root_filesystem_is_read_only_and_user_is_not_root():
    code = "import os\nprint(os.getuid())\nopen('/etc/hacked', 'w')"
    result = run("python", code)
    assert result.results[0].stdout.strip() == "65534"
    assert result.verdict is Verdict.RUNTIME_ERROR


def test_playground_run_returns_stdout():
    result = run("python", "print(input()[::-1])", stdin="hello\n")
    assert result.verdict is Verdict.ACCEPTED
    assert result.results[0].stdout == "olleh\n"


@pytest.mark.parametrize(
    "actual, expected, comparator, match",
    [
        ("3\n", "3", Comparator.TRIM, True),
        ("3  \n\n", "3\n", Comparator.TRIM, True),
        ("3\n", "3", Comparator.EXACT, False),
        ("1 2\n3", "1\n2 3", Comparator.TOKENS, True),
        ("0.3333333", "0.33333333", Comparator.FLOAT, True),
        ("0.34", "0.33", Comparator.FLOAT, False),
    ],
)
def test_comparators(actual, expected, comparator, match):
    assert outputs_match(actual, expected, comparator) is match
