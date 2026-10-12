# Code Playground

Run code in any supported language inside a locked-down Docker sandbox and
judge it against test cases (input + expected output), through a REST API
that other projects can call and a web UI for writing and testing code in the
browser. This is the engine for a CodinGame-style platform.

Supported languages: Python 3.13, JavaScript (Node.js 22), Java 21,
C++20 (GCC 14), Go 1.23.

## Try it in the browser (no Docker needed)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Jmailachref/code-playground)

The Codespace builds the sandbox images, starts the stack and loads the
sample questions on its own (the first start takes several minutes). Then
open the **Ports** tab and click the globe next to port 8000 for the web UI;
add `/docs` for the API, authorizing with `dev-key`.

## Run the stack

Needs Docker with Compose.

```sh
sh languages/build.sh                                    # sandbox images, once
docker compose up -d                                     # Postgres, Redis, API + UI on :8000, one worker
docker compose exec api python -m api.seed examples/*.json   # three sample questions
open http://localhost:8000                               # web UI
open http://localhost:8000/docs                          # interactive API docs
```

`API_KEYS` is a comma-separated list of `client:key` pairs, one per calling
project; set your own before exposing the stack (the defaults are
`dev:dev-key,ui:ui-key`). Every request sends `Authorization: Bearer <key>`. Submissions are
private to the client that created them; problems are shared.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `API_KEYS` | `dev:dev-key` | Comma-separated `client:key` pairs, one per calling project |
| `UI_API_KEY` | empty (UI off) | Key the web UI's proxy uses; must be one of `API_KEYS` |
| `RATE_LIMIT_PER_MINUTE` | 60 | Runs plus submissions per API key per minute (0 = off) |
| `UI_RATE_LIMIT_PER_MINUTE` | 20 | Runs plus submissions per web UI visitor (IP) per minute |
| `DATABASE_URL` | local Postgres | SQLAlchemy URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Queue and rate-limit counters |

Going over a limit returns `429` with a `Retry-After` header. Behind a reverse
proxy, start uvicorn with `--proxy-headers` so the UI limit sees real visitor
IPs.

Workers recover lost jobs on their own: every minute they put back on the
queue any job left `running` for over 5 minutes (its worker died) or `queued`
but missing from Redis (Redis restarted). Each job is claimed atomically, so
it is judged once even if it is queued twice.

## Before going public

The sandbox shares the host kernel, so a kernel exploit inside a submission
could escape the container. Before exposing the API or UI to untrusted users,
run the worker on its own VM and switch sandbox containers to
[gVisor](https://gvisor.dev) (`--runtime runsc` on the Docker daemon). The
worker also holds the Docker socket, which is root on its host.

## Web UI

- **Playground:** pick a language, write code, give it stdin and run it.
  Output, errors, time and memory come back in the side panel.
- **Questions:** read the statement and the visible test cases, run your code
  against one of them, or submit to judge it against all of them, hidden ones
  included. Each test case shows pass or fail with your output next to the
  expected one, and **My submissions** lists past attempts with their code.

The UI asks for a display name and sends it as `user_id`; there are no
accounts yet. It talks to the API through `/ui-api/...`, a proxy in the API
service that adds `UI_API_KEY` on the server, so no key reaches the browser.
The proxy only allows what the UI needs (languages, runs, reading questions,
submissions); creating or editing questions still requires a real API key.

To work on the UI with hot reload, run the API on :8000 and then:

```sh
cd ui && npm install && npm run dev    # http://localhost:5173, proxies /ui-api to :8000
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /v1/languages | Supported languages and starter templates |
| POST | /v1/runs | Playground: run code once with custom stdin |
| GET | /v1/runs/{id} | Run status and output |
| GET, POST | /v1/problems | List questions, or create one with its test cases |
| GET, PATCH, DELETE | /v1/problems/{id} | Read (visible test cases only), edit, delete |
| POST | /v1/problems/{id}/scenarios | Add test cases |
| PATCH, DELETE | /v1/problems/{id}/scenarios/{sid} | Edit or remove a test case |
| POST | /v1/submissions | Judge code against every test case; saved with results |
| GET | /v1/submissions/{id} | Status, verdict, score and per-test-case results |
| GET | /v1/submissions?user_id=&problem_id= | A user's past submissions, newest first |
| GET | /v1/health | Liveness and queue depth |

Runs and submissions are asynchronous: `POST` returns `202` with an id, then
poll `GET` until `status` is `completed` (or `failed` for a platform error).
Submissions can also pass a `callback_url` that receives a summary when
judging finishes. Hidden test cases report only a verdict, never their input
or output.

```sh
curl -H "Authorization: Bearer change-me" -H "Content-Type: application/json" \
     -d @examples/sum-of-two.json localhost:8000/v1/problems
curl -H "Authorization: Bearer change-me" -H "Content-Type: application/json" \
     -d '{"problem_id": "<id>", "language": "python", "user_id": "alice",
          "source_code": "a, b = map(int, input().split())\nprint(a + b)"}' \
     localhost:8000/v1/submissions
curl -H "Authorization: Bearer change-me" localhost:8000/v1/submissions/<submission id>
```

## Develop without Compose

Needs Docker and Python 3.11+.

```sh
pip install -r requirements.txt
sh languages/build.sh            # builds the sandbox helper and one image per language
python -m runner.cli languages
python -m runner.cli run python examples/solutions/sum.py --stdin "1 2"
python -m runner.cli judge cpp examples/solutions/sum.cpp examples/sum-of-two.json
python -m pytest                 # end-to-end tests against real containers
```

`tests/test_api.py` also needs Postgres and Redis on localhost (for example
`docker compose up -d postgres redis` with ports published) and a database
named `codeplay_test`, or set `TEST_DATABASE_URL`.

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
api/         FastAPI app: routes, schemas, API keys, UI proxy, seed script
ui/          React + TypeScript + Monaco web UI (Vite)
core/        shared code: settings, database models, queue, language registry
runner/      sandbox driver, judge, CLI, queue worker
migrations/  Alembic database migrations
languages/   one folder per language + the runbox helper
examples/    sample problem and solutions in every language
tests/       end-to-end tests
```
