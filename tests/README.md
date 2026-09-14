# Behavioral verification

Run `uv run pytest -q`. Tests cover grounding, role/payload constraints, confirmation invalidation, model failures, authenticated API flows, assignment quality, collision invariants, partial observation, energy feasibility, persistence/restart/idempotency, failed-checkpoint rollback, speech contracts and learned inspection in the warehouse.

HTTP model and transcription doubles verify integration contracts. They do not measure live LLM or speech quality. `scripts/browser-smoke.cjs` separately exercises the actual dashboard with Playwright.
