# Project progress

Last updated: **2026-09-21**. This file distinguishes delivered software from external
validation still required. Reports should cite commits and CI, and state when no new
work has occurred; daily reporting does not imply continuous background execution.

## Completed

- Conversational coordinator, grounded procedure retrieval, local LLM adapter and
  operator confirmation with deterministic authorization checks.
- Three-robot warehouse simulation, changing/partially observed obstacles, constrained
  assignment, route reservations, charging and persistent state.
- Operator dashboard, recording/upload and reviewed-transcript interfaces, optional
  local transcription, browser spoken replies and experimental learned inspection.
- Reproducible synthetic experiments and a 64-second demo linked from the root README.
- Expanded validation tools: installed-runtime check, 12 multi-turn conversation-to-
  delivery scenarios, three source-presence checks and a local speech corpus evaluator.
- Fixed offline parsing of `urgently`, which previously proposed normal priority.

## Current milestone: live-model validation

The evaluation tooling is implemented. Local quality checks on 2026-09-17 pass:
**70 tests**, Ruff and strict mypy. Speech/model test doubles validate evaluation
logic; they are not live quality measurements.

The actual rules-baseline run passes **11/12** scenarios and **3/3** source checks;
five scenarios execute and complete their transport. The unsupported `please bring`
paraphrase is retained as a failure. See [raw result](../assets/language-baseline.json).

## Blockers

The development environment has no running Ollama service, selected model or local
speech-model files. No microphone corpus or physical robot hardware is available.
No live inference, speech quality, industrial productivity or hardware safety result
is claimed. See [live validation instructions](live-validation.md).

## Next milestone

1. Identify the machine and installed LLM/speech models for actual inference tests.
2. Run the live suite; fix measured errors without weakening independent guards.
3. Collect authorized, labeled operator recordings and evaluate speech/noise effects.
4. Test the combined voice-to-simulated-delivery workflow with human operators.

## Planned experiments

- Rules versus actual grounded LLM inference on identical held-out scenarios.
- Retrieval and persistent-agent ablations; evidence faithfulness review.
- Human/synthetic speech results separated by speaker and recording condition.
- Broader layouts and workloads, strong planning baselines, and learned clarification
  versus the existing inspection heuristic. Current results do not show an RL advantage
  over that heuristic.

## Known limits

The rules grammar is deliberately restricted. The speech interface is turn-based,
not continuous full-duplex conversation. Post-dispatch cancellation/reassignment,
distributed control, calibrated uncertainty and hardware integration remain extensions.
The prototype and synthetic tests do not establish readiness for a real warehouse.

## Integration review — 2026-09-21

- Reviewed the roadmap, published PR #3, recent main-branch commits and its
  exact head `3700fd9084efeacdde0af4231aad4d5e9cc6ef13`.
- GitHub Actions [run 35250872144](https://github.com/mazyartaghavi/cooperative-warehouse-intelligence/actions/runs/35250872144)
  passed both quality and browser jobs: lint, formatting, strict typing, pytest,
  simulation demo, synthetic evaluation and dashboard smoke checks.
- These are existing CI results, freshly verified today, not a new local test run.
  Local reproduction is blocked: the previous virtual environment is unusable and
  the offline dependency cache lacks pinned packages (including NumPy 2.5.3).
- The default local Ollama endpoint at localhost:11434 refused connection.
  No live-model, speech or hardware measurement was performed.
- This update records the integration review. Merge remains conditional on checks
  passing for the updated PR head. The next technical milestone remains measured
  live-model evaluation; do not replace missing inference evidence with baseline scores.
