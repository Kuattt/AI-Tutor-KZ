# AI Tutor KZ — Backend v1.1

FastAPI backend for local multi-turn tutoring through Ollama and
`qwen3.5:9b`. All student content stays on this computer.

## Requirements

- Windows 11
- Python 3.12+
- Ollama listening on `http://127.0.0.1:11434`
- `qwen3.5:9b` installed locally

## Setup in PowerShell

```powershell
cd "C:\Users\parpi\OneDrive\Рабочий стол\sdhjshdhsud\ai-tutor-kz\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
Copy-Item .env.example .env
```

The application works with defaults when `.env` is absent. `.env` is ignored
by Git.

## Configuration

Key environment variables:

```env
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
APP_LOG_LEVEL=INFO
APP_CORS_ORIGINS=["http://127.0.0.1:3000","http://localhost:3000"]

OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_CONNECT_TIMEOUT_SECONDS=10
OLLAMA_READ_TIMEOUT_SECONDS=180

TUTOR_MAX_HISTORY_MESSAGES=30
TUTOR_MAX_GENERATION_TOKENS=450
TUTOR_TEMPERATURE=0.1
TUTOR_SESSION_TTL_MINUTES=60
TUTOR_SESSION_CLEANUP_INTERVAL_SECONDS=300
TUTOR_DISCONNECT_POLL_INTERVAL_SECONDS=0.25
```

Keep both FastAPI and Ollama bound to localhost during this development
milestone.

## Start the backend

```powershell
.\.venv\Scripts\python.exe -m app
```

This launcher reads `APP_HOST` and `APP_PORT` from configuration and rejects
non-loopback bind addresses. For development auto-reload, the equivalent
explicit command is:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

OpenAPI interfaces:

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>

## Run automated tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Automated tests use an injected fake provider and do not wait for the real
model. The Ollama HTTP parser is tested with `httpx.MockTransport`.

## Run the real smoke test

Start Ollama and the backend, then in another PowerShell window run:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

The script checks both health endpoints, creates a session, prints two real
responses as SSE chunks arrive, verifies that the second request shares the
first request's history, and reports first-token/total timing.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | FastAPI process liveness |
| `GET` | `/health/ollama` | Ollama reachability and configured model availability |
| `POST` | `/api/v1/tutor/sessions` | Create an in-memory tutor session |
| `GET` | `/api/v1/tutor/sessions/{session_id}` | Inspect a development session |
| `DELETE` | `/api/v1/tutor/sessions/{session_id}` | Delete a session |
| `POST` | `/api/v1/tutor/sessions/{session_id}/messages` | Stream a tutor response with SSE |
| `GET` | `/api/v1/internal/metrics` | Process-local generation/session metrics |

The streaming endpoint emits `start`, one or more `delta`, `metadata`, and
`done` events. If generation fails after streaming starts, it emits `error`
instead and does not store a partial assistant response.

If the HTTP client disconnects, the service notices through Starlette's
`Request.is_disconnected()`, closes the active upstream response, releases the
session lock, and does not persist partial assistant output. Detection uses a
low-frequency configurable check (250 ms by default). Closing the HTTP stream
signals cancellation to Ollama, although the Ollama runner may take a short,
implementation-dependent time to release CPU work internally.

## Current persistence boundary

Sessions live only in process memory and disappear whenever the backend
restarts. Inactive sessions expire after `TUTOR_SESSION_TTL_MINUTES`; a
lifespan-managed task removes them every
`TUTOR_SESSION_CLEANUP_INTERVAL_SECONDS`. Active generations are protected
from cleanup. History is limited by `TUTOR_MAX_HISTORY_MESSAGES`. The
`TutorSessionStore` interface is the future seam for PostgreSQL or Redis.

## Operational metrics

`GET /api/v1/internal/metrics` returns local development counters:

- generations: total, successful, failed, cancelled, currently active;
- average total and first-token latency plus most recent duration;
- generated token and character totals;
- sessions created and currently active.

No prompts or response text are stored in metrics. Counters reset whenever the
backend restarts and are not intended as a production monitoring system.

## Repeated guided-policy smoke test

With Ollama and Backend v1.1 running:

```powershell
.\.venv\Scripts\python.exe scripts\guided_policy_smoke.py --runs 5
```

The script runs the same four-turn algebra lesson in five fresh sessions,
checks rejection of a wrong intermediate result, early answer leakage, division
guidance, and final confirmation, then writes:

```text
results/backend_v1_1_guided_smoke_YYYYMMDD_HHMMSS.json
```

This is an explicit real-model test. Normal `pytest` runs never call Ollama.

