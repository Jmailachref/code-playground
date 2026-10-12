# Code Playground

Run code in any supported language inside a locked-down Docker sandbox and
judge it against test cases (input + expected output). This is the execution
engine for a CodinGame-style platform; the REST API and web UI come next.

Supported languages: Python 3.13, JavaScript (Node.js 22), Java 21,
C++20 (GCC 14), Go 1.23.

## Quick start

Needs Docker and Python 3.11+.

```sh
pip install -r requirements.txt
sh languages/build.sh            # builds the sandbox helper and one image per language
python -m runner.cli languages
python -m runner.cli run python examples/solutions/sum.py --stdin "1 2"
python -m runner.cli judge cpp examples/solutions/sum.cpp examples/sum-of-two.json
python -m pytest                 # end-to-end tests against real containers
```

## How a submission runs

1. One container is started from the language image with no network, a
   read-only root filesystem, 1 CPU, a memory cap, at most 64 processes,
   user `nobody` and all Linux capabilities dropped. Only `/code` and `/tmp`
   (in-memory) are writable.
2. The source is written to `/code`, then compiled once if the language
   needs it (10 s CPU limit).
3. Each test case runs through `runbox` (`languages/runbox/runbox.c`), a
   small static helper that enforces CPU and wall-clock limits, caps every
   written file at 1 MB and reports exit code, signal, CPU time and peak
   memory.
4. The runner turns that into a verdict and compares stdout with the
   expected output. The container is removed afterwards.

Verdicts, most severe first: `compilation_error`, `runtime_error`,
`time_limit_exceeded`, `memory_limit_exceeded`, `output_limit_exceeded`,
`wrong_answer`, `accepted`.

Output comparators: `exact`, `trim` (default: ignores trailing spaces and
blank lines), `tokens` (whitespace-insensitive), `float` (1e-6 tolerance).

## Adding a language

Create `languages/<id>/Dockerfile` (copy `runbox` in from
`codeplay/runbox:latest`) and `languages/<id>/config.yaml` with the source
file name, compile and run commands, then run `sh languages/build.sh`.

## Layout

```text
core/        shared code: language registry
runner/      sandbox driver, judge, CLI
languages/   one folder per language + the runbox helper
examples/    sample problem and solutions in every language
tests/       end-to-end tests
```
