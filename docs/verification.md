# M1 engineering verification

Verified locally on 2026-09-13 with Python 3.12.14 and uv 0.12.11 on Linux.

| Check | Observed outcome |
| --- | --- |
| `uv sync --locked` | Package builds and installs from the lockfile |
| `uv run pytest -q` | 35 tests passed |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed |
| `uv run mypy` | Passed for 15 source files |
| `uv run cwi-demo` | Ambiguity → clarification → confirmation → accepted specification |
| Live local uvicorn HTTP smoke | Health, session creation, and all three conversation turns succeeded |
| Robot dispatch | Unavailable; every response reports `execution_dispatched=false` |

Tests cover policy rejection, correction invalidation, confirmation-time state changes, cancellation, repeated confirmation, session isolation, unknown identifiers, model-invented identifiers, strict API input validation, authentication, retrieval filtering, and Ollama contract failures.

Two upstream deprecation warnings were observed in the test client stack: Starlette's httpx integration and the AnyIO BlockingPortal alias. They are not suppressed and did not fail the checks.

## What this evidence does not establish

- No live Ollama model was available in this environment. The adapter was tested with deterministic HTTP responses, not with real language-model inference.
- The offline demo is a controlled English rules baseline. It does not measure fluent conversation, semantic understanding, or RAG answer quality.
- No physical robots, dynamic simulation, speech pipeline, optimizer, or RL training were exercised.
- There are no measured performance improvements, production deployment claims, or human-user study results.
- Hosted CI outcomes must be checked on the actual GitHub Actions run; local results do not imply a hosted run passed.

The captured console demonstration is in `assets/m1-demo.txt`. Run the commands above to reproduce the software checks; changing dependencies, models, or runtime can change outcomes.
