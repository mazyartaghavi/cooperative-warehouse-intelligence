# Development and operation

## Install and run

Python 3.12 is required. Install uv, clone the repository, then run:

```sh
uv sync --locked
uv run cwi-demo
```

The offline demo uses the restricted English baseline and executes a confirmed
transport in the dynamic simulator. It needs no model service or robot hardware.

For the dashboard, set `CWI_API_TOKEN` to a private local string of at least 16
characters, then run:

```sh
uv run uvicorn cwi.api.app:app_factory --factory --host 127.0.0.1 --port 8000 --workers 1
```

Open http://127.0.0.1:8000 and enter that token. API documentation is at `/docs`.
In PowerShell, set `$env:CWI_API_TOKEN = "your-private-local-token"`. In bash,
use `export CWI_API_TOKEN="your-private-local-token"`. `.env.example` documents keys;
it is not loaded automatically. The token is local demo authentication, not a
GitHub credential.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CWI_API_TOKEN` | Required | One local demo operator's API token |
| `CWI_BACKEND` | `baseline` | `baseline` or local `ollama` |
| `CWI_OPERATOR_ROLE` | `operator` | `operator` or `supervisor`, set by server |
| `CWI_DB` | `data/local/cwi.db` | Durable SQLite checkpoint and synthetic procedures |
| `CWI_OLLAMA_MODEL` | Empty | Name of an installed local Ollama model |
| `CWI_OLLAMA_URL` | `http://localhost:11434` | Local HTTP endpoint only |
| `CWI_WHISPER_MODEL` | Empty | Existing local faster-whisper model directory |
| `CWI_ASSISTANCE_POLICY` | `inspect_when_possible` | `q_learning`, `always_ask`, or fixed inspection baseline |

Start a new session for each task. Confirmed and cancelled sessions are terminal.
A correction clears the pending proposal even if language extraction fails.
The demo caps sessions at 1,000 and extraction turns per session at 40. For a fresh
experiment, set `CWI_DB` to a new file; do not delete operational data casually.
Requests, including model calls, are serialized. Run one server process and worker.

## End-to-end walkthrough

1. Connect and request `Move the blue tote to P2`.
2. Clarify `T17`, review the full task summary, and confirm.
3. Start a new task, request `Move T23 to P1`, and confirm.
4. Start a third task, request `Move T42 to P2`, and confirm.
5. Add an obstacle at `(4, 2)`, then run or step the simulation.
6. Inspect robot positions, battery levels, deliveries, and observation events.
7. Ask the procedure panel `Who can request urgent priority?`.
8. Try `Move T31 to P1` to see payload rejection. An ordinary operator's request
   for Q1 or urgent priority is also rejected.

The simulator owns hidden obstacles. Adding one through the environment control is
an experiment intervention, not an operator assertion that updates the robot map.
Local active inspection can reveal a wider area when a known obstruction blocks a
route. The learned policy is trained on synthetic transitions; the default remains
the strong fixed inspection baseline. The dashboard can mark the operator busy,
which changes the learned interruption-cost state. At most two active inspections
per assignment are allowed, with an independent battery guard.

## Language and speech

Start Ollama separately and install a suitable model. Set `CWI_BACKEND=ollama` and
`CWI_OLLAMA_MODEL` before starting the API. Requests carry the JSON output schema,
conversation turns, procedure evidence and observed inventory. There is no silent
fallback to the rules backend on model failure.

Task-facing responses are canonical validated summaries. The procedure panel uses
generated, citation-bearing answers in Ollama mode, and extractive answers in baseline
mode. Citation-ID checks do not prove the correctness of every generated statement.

For local speech, run `uv sync --locked --extra voice` and set `CWI_WHISPER_MODEL`
to an existing converted faster-whisper model directory. Startup fails clearly if
the configured dependency or model is absent; no model is downloaded automatically.
Use a supported browser on localhost/HTTPS, allow microphone access, and record or
upload an utterance. Review the transcription and send it. Utterances are limited
to 60 seconds and 10 MiB. The adapter deletes temporary audio after decoding. A reverse
proxy should also enforce a request-body size limit before multipart parsing if the
service is exposed beyond localhost.

`Read replies aloud` uses browser speech synthesis. Voice availability and possible
remote speech services depend on the browser and OS. This is utterance-based speech,
not uninterrupted full-duplex dialogue. No microphone audio or model-quality result
is included in automated fixture tests.

## API surface

All routes except `/`, `/health`, and API documentation require `X-CWI-Token`.

| Method and path | Effect |
|---|---|
| `POST /sessions` | Create a durable task conversation |
| `POST /sessions/{id}/messages` | Propose, clarify, correct, confirm, or cancel |
| `POST /knowledge` | Retrieve/generate an informational answer; never dispatch |
| `POST /speech/transcribe` | Decode audio to reviewed text; never dispatch |
| `GET /warehouse` | Shared observed state, jobs, metrics and recent events |
| `POST /warehouse/advance` | Advance 1–500 simulated ticks and persist |
| `POST /warehouse/obstacles` | Add/remove an environmental obstacle |
| `POST /warehouse/operator-workload` | Set `{ "busy": true }` for assistance decisions |

Health reports configured capabilities, not measured model readiness. Errors include
401 authentication, 404 unknown session, 409 disabled simulation, 413 large audio,
422 invalid input, 429 session cap, and 503 backend failure. Unsupported baseline
grammar also yields 503. `cancel` cancels an unaccepted conversation; it does not
recall a robot after an accepted transport. Dashboard pause stops future tick
requests; one already in flight may complete.

## Checks and research commands

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
uv run cwi-evaluate --output outputs/evaluation.json --policy outputs/clarification-policy.json
uv run cwi-evaluate-llm --model INSTALLED_MODEL --output outputs/live-language.json
```

The last command needs live Ollama. It records actual responses and errors. Ordinary
CI has no model and must not be presented as an inference benchmark.

## Container

The Dockerfile packages the CPU simulation/API without optional speech models:

```sh
docker build -t cooperative-warehouse-intelligence .
docker run --rm -p 127.0.0.1:8000:8000 -e CWI_API_TOKEN \
  -v cwi-data:/app/data cooperative-warehouse-intelligence
```

The container runs as an unprivileged user. The token must be exported in the host
shell. The image exposes the rules baseline; the local-only Ollama URL is resolved
inside the container, so a host Ollama server is not automatically accessible. Use
the native startup path for local model work. Container execution is not claimed
verified unless recorded in the verification document.

## Expanded model validation

Use `uv run cwi-check-runtime --model INSTALLED_MODEL` before inference tests.
See the [live validation guide](live-validation.md) for multi-turn delivery checks,
the explicit baseline comparator, audio manifests and speech-quality measurement.
