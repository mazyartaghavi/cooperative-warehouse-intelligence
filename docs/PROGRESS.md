# Project progress

Last updated: **2026-09-24**. This file distinguishes delivered software from external
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
- Added task pause/resume, evidence-based status and cancellation through the API,
  dashboard and linked conversation. Carrying robots return totes before cancellation
  completes; ownership checks, idempotence and restart/failed-save recovery are enforced.
- Added a recorded-voice-to-delivery evaluator with expected-task checks before
  scripted confirmation, transcription failures in the denominator and separate
  human/synthetic groups. Its tests use explicit doubles, not live speech.
- Added `bring` to the bounded offline grammar and retained negation rejection.
- Added a Windows launcher and cross-platform `cwi-validate-local` command with
  a small-model profile, shared inference resource limits and timestamped ZIP reports.
  The report preserves blocked/interrupted states and keeps actual inference separate
  from the rules comparator; no model download or upload happens in the evaluator.

## Current milestone: live-model validation

The evaluation tooling is implemented. Local quality checks on 2026-09-23 pass:
**127 tests**, Ruff and strict mypy for 33 source files. Speech/model test doubles validate evaluation
logic; they are not live quality measurements.

The actual rules-baseline run now passes **12/12** scenarios and **3/3** source checks;
six scenarios execute and complete their transport. The previously unsupported
`please bring` request is covered by the grammar and regression test. See the
[raw result](../assets/language-baseline.json). This does not measure broad language
generalization or live-model quality.

Version-2 scoring checks the actual policy behind each rejection. Prompt/schema
changes and bounded raw-response diagnostics are implemented; their effectiveness
requires actual inference. Private evaluation reports are not published here.

## Remaining validation

The development environment has no running Ollama service, selected model or local
speech-model files. No microphone corpus or physical robot hardware is available.
No live-model improvement, speech-quality, industrial-productivity or hardware-safety
claim follows from the automated tests. See [live validation instructions](live-validation.md).

## Windows rerun reliability milestone - 2026-09-23

- A rerun from an extracted Windows project copy installed dependencies but stopped
  before evaluation, so it correctly produced no `outputs` folder. No second live
  score is claimed from that attempt.
- The Windows launcher now prepares the pinned environment explicitly in the short
  `%LOCALAPPDATA%\cwi-validation-venv` path and defaults uv to copy mode. This avoids
  fragile cross-drive hard links and deeply nested project-local environments while
  retaining explicit environment overrides.
- Setup failures now stop with a distinct explanation before the evaluator runs.
  The Windows CI smoke test verifies both external-environment creation and the
  diagnostic ZIP path. Local verification passes **123 tests**, Ruff lint and format
  checks, and strict mypy for 33 source files. Hosted Python, browser and Windows
  checks pass in [run 35902494666](https://github.com/mazyartaghavi/cooperative-warehouse-intelligence/actions/runs/35902494666).
- The rerun with actual `qwen2.5:1.5b` remains external evidence still required.

## Next milestone

1. Rerun the updated [Windows validation](windows-local-model.md) with the same
   model and resource limits; retain the new diagnostic ZIP alongside the original.
2. Run the live suite; fix measured errors without weakening independent guards.
3. Collect authorized, labeled operator recordings and evaluate speech/noise effects.
4. Test the combined voice-to-simulated-delivery workflow with human operators.

## Repeated live-inference measurement milestone - 2026-09-24

- Added an optional `--repetitions` setting (1–10) to the local validation bundle;
  the default remains one to avoid increasing the ordinary Windows run time.
- Repeated runs retain every full model result and add descriptive complete-run,
  per-scenario and source-presence stability rates. A lucky pass cannot replace a
  failed repetition, and exit code 0 requires all completed repetitions to pass.
- Deterministic HTTP doubles verify report separation, aggregation and bounds. They
  do not measure Qwen stability. An actual repeated local-model result remains external
  evidence still required.

## Planned experiments

- Rules versus actual grounded LLM inference on identical held-out scenarios.
- Retrieval and persistent-agent ablations; evidence faithfulness review.
- Human/synthetic speech results separated by speaker and recording condition.
- Broader layouts and workloads, strong planning baselines, and learned clarification
  versus the existing inspection heuristic. Current results do not show an RL advantage
  over that heuristic.

## Known limits

The rules grammar is deliberately restricted. The speech interface is turn-based,
not continuous full-duplex conversation. Post-dispatch destination changes/reassignment,
distributed control, calibrated uncertainty and hardware integration remain extensions.
The prototype and synthetic tests do not establish readiness for a real warehouse.

## Windows local-model setup milestone - 2026-09-22

- Started from published `main` commit `fef997b15a7b612699e6ebc32696e17e1cba5eba`.
- Added a Windows command that works with a downloaded project ZIP or Git checkout.
  Its initial profile is `qwen2.5:1.5b`, 4,096 context tokens, 512 output tokens and
  a 180-second HTTP timeout. Actual fit/speed on 8 GB RAM remains to be measured.
- Both intent extraction and grounded Q&A honor explicit resource limits. Ordinary
  API/evaluator settings can come from the environment; the bundled runner records
  its explicit CLI settings, model digest, source hash and per-turn latency.
- Added blocked, failed, interrupted and successful report-path tests with explicit
  HTTP doubles, plus a hosted Windows job for the launcher, dependency installation,
  path handling with spaces and diagnostic ZIP verification.
- Local validation: 113 tests, Ruff and strict mypy pass. An actual invocation of
  the new command produced a blocked report because this development machine has
  no running Ollama service. The baseline passed; no live score was invented.
- Next evidence needed: a ZIP from actual Ollama inference, followed by speech-model
  and authorized recording evaluation. The runner does not upload anything.

## Operator control and voice workflow milestone - 2026-09-22

- Started from published `main` commit `6a8562f925bb0d54033219dd549b7b4cf098d140`
  in an isolated worktree, preserving earlier media work.
- Implemented mission interruption and combined voice workflow evaluation described
  above. Updated the root README, API guide, roadmap and validation documentation.
- Local tests, lint, formatting, typing, offline demo, language fixture and synthetic
  warehouse/RL experiments pass. Hosted browser coverage now exercises per-task
  pause/resume and cancellation with cargo return, in addition to ordinary delivery.
- Runtime check remains blocked: no configured LLM, unavailable local Ollama service,
  no speech weights or recordings. Direct model-download probes timed out. No live
  inference result was substituted with a baseline result.
- Next technical work is measured live-model and speech evaluation on a machine
  with installed runtimes; then human interaction and broader scenario experiments.

## Integration review — 2026-09-21

- Reviewed the roadmap, published PR #3, recent main-branch commits and its
  code head `3700fd9084efeacdde0af4231aad4d5e9cc6ef13`.
- GitHub Actions [run 35250872144](https://github.com/mazyartaghavi/cooperative-warehouse-intelligence/actions/runs/35250872144)
  passed both quality and browser jobs: lint, formatting, strict typing, pytest,
  simulation demo, synthetic evaluation and dashboard smoke checks.
- Restored the local environment with `uv sync --locked` after an initial offline
  cache miss. Fresh local verification: **70 tests passed**, Ruff lint and format
  checks passed, strict mypy passed for 31 source files. The local code tree matched
  the published code head; no new feature implementation is claimed in this review.
- The runtime readiness command exited 2: no selected LLM and the default local
  Ollama inventory endpoint was unavailable (`ConnectError`). No speech model
  was configured. No live-model, speech or hardware measurement was performed.
- This update records the integration review. Merge remains conditional on checks
  passing for the updated PR head. The next technical milestone remains measured
  live-model evaluation; do not replace missing inference evidence with baseline scores.
