# Run the M1 text-to-task milestone

## Prerequisites and installation

Use Python 3.12 and uv. Dependencies are pinned in `pyproject.toml` and `uv.lock`.
From the repository root:

```sh
uv sync --locked
uv run cwi-demo
```

The demo uses a controlled English rules baseline, not an LLM. It asks which blue tote is intended, retains the destination, confirms the resolved task, and accepts its specification. It does not plan a route or dispatch a robot.

## API on Windows PowerShell

Generate a temporary token locally and set the environment variables in the same terminal:

```powershell
$env:CWI_API_TOKEN = (python -c "import secrets; print(secrets.token_urlsafe(32))")
$env:CWI_BACKEND = "baseline"
$env:CWI_OPERATOR_ROLE = "operator"
uv run uvicorn cwi.api.app:app_factory --factory --host 127.0.0.1 --port 8000
```

The equivalent POSIX shell setup uses `export CWI_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"`, `export CWI_BACKEND=baseline`, and the same uvicorn command.

Open http://127.0.0.1:8000/docs. `POST /sessions` creates a conversation; pass the configured token in the `x-cwi-token` header. Copy its `session_id` into `POST /sessions/{session_id}/messages` and send these JSON bodies in sequence:

1. `{"text":"Move the blue tote to P2"}`
2. `{"text":"T17"}`
3. `{"text":"confirm"}`

Use a token available to you locally; do not paste it into a public issue or this repository. `.env.example` lists configuration keys but is not loaded automatically. If using Swagger UI, you can set your own temporary token in PowerShell instead of generating one, provided it has at least 16 characters.

`GET /health` reports the selected backend and that robot dispatch is unavailable. It does not check model readiness. API errors: 401 for missing/wrong token, 404 for unknown session, 422 for invalid input, 429 for session capacity, and 503 when extraction fails. In the baseline, unsupported grammar also produces 503; this is a demo limitation.

## Optional local LLM

Run Ollama separately and install a model of your choice. No model is downloaded automatically. In the API terminal before starting uvicorn:

```powershell
$env:CWI_BACKEND = "ollama"
$env:CWI_OLLAMA_MODEL = "YOUR_INSTALLED_MODEL_NAME"
$env:CWI_OLLAMA_URL = "http://localhost:11434"
```

The adapter sends operator turns and retrieved synthetic procedures to Ollama's local `/api/chat` endpoint using the `Intent` JSON schema. Outputs are validated before policy checks and confirmation. There is no silent fallback if Ollama fails. Only a local HTTP endpoint is accepted in this milestone; no paid service is invoked.

The adapter's request/response contract is covered by HTTP test doubles. Live-model accuracy, latency, prompt-injection robustness, and fluent dialogue have **not** been validated. The model extracts intent; user-facing replies are deterministic templates in M1. An LLM extraction error may still produce a wrong candidate, so operators must review the confirmation summary.

Reference: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

## Supported offline grammar

- A single transport request: `Move T17 to P2` or `Move the blue tote to P2`.
- A clarification: `T17`.
- A correction: `P1 instead` or `T23 instead`.
- Priority: `urgent` or `normal`; urgency is restricted to the server-configured supervisor.
- `confirm` or `yes` confirms a pending candidate; `cancel` cancels the conversation.

This is not general natural-language understanding. Complex sentences, multiple tasks, arbitrary negation, and implicit references are unsupported. The model backend is the extension point for broader language understanding.

## Verification

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Local M1 evidence is recorded in `docs/verification.md`. CI runs the same checks without an LLM server. Do not treat contract tests with mocked model responses as a live-model benchmark.

## Runtime scope

This is a single-process local demo. One configured token maps to one operator role; session memory is lost on restart. Use one uvicorn worker. Requests are serialized, including model calls, and sessions are capped at 1000 with 40 extraction turns each. Accepted/cancelled conversations are terminal; start a new session for a new task. No production authentication, persistent workflow, audio, dynamic simulation, optimization solver, or RL policy is implemented here.
