# Behavioral verification

Run `uv run pytest -q`. Tests cover grounding, role/payload constraints, confirmation invalidation, model failures, authenticated API flows, assignment quality, collision invariants, partial observation, energy feasibility, persistence/restart/idempotency, failed-checkpoint rollback, speech contracts and learned inspection in the warehouse.

HTTP model and transcription doubles verify integration contracts. They do not measure live LLM or speech quality. `scripts/browser-smoke.cjs` separately exercises the actual dashboard with Playwright.

`test_job_control.py` checks mission pause/resume, source return, blocked cancellation,
ownership and transactional recovery. `test_voice_workflow.py` uses explicit speech
doubles to verify wrong identifiers and failed transcription cannot reach scripted
confirmation. The recorded rules fixture is also run in CI.
