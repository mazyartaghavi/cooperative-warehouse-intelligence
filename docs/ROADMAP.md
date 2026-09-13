# Capability status and roadmap

## Current snapshot

- Completed: approved subject, title, GenAI-first design, recruiter-facing project overview, directory/module outlines, and initial repository publication.
- Current milestone: M0 repository scaffold. Next implementation milestone: M1.
- Implemented application capabilities: none.
- Experimental capabilities: none executed.
- Planned capabilities: all runtime modules described below.

## Milestones

| Milestone | Scope | Completion evidence | Status |
| --- | --- | --- | --- |
| M0 | Documentation and repository scaffold | Reviewed files and verified GitHub publication | Published |
| M1 | Text conversation, procedure retrieval, validated task extraction and clarification | Reproducible text scenario, citations, failure cases, and meaningful tests | Planned |
| M2 | Three-robot dynamic warehouse and planning | End-to-end task execution, changing obstacles, observable status, and reservation checks | Planned |
| M3 | Recorded and live voice | Transcription, spoken replies, corrections, and measured identifier/noise errors | Planned |
| M4 | Agent reliability | Recovery, cancellation, conflicting orders, duplicate protection, persistence, and reconnect scenarios | Planned |
| M5 | RL clarification study | Fixed-rule baselines, held-out evaluation, multiple seeds, and transparent reports | Planned |
| M6 | Hardware preparation | Documented adapter contract and physical validation plan | Planned |

## Next implementation milestone

M1: a narrow text request → retrieve evidence → clarify → produce a validated task flow. Robot dispatch remains unavailable until the execution backend exists. Select and pin dependencies only when required for this milestone.

## Known issues and open decisions

- LLM, speech models, vector backend, and compute budget have not been benchmarked or selected.
- Runtime packaging, CI, tests, and deployment artifacts are absent intentionally.
- Software license is not selected.
- Hardware equipment and physical validation access are unspecified.

## Planned experiments

1. Procedure-grounding ablation with and without retrieval.
2. Fixed clarification rules versus learned clarification, measuring operator workload and task correctness.
3. Persistent agent recovery versus a single planning call on identical injected failures.
4. Robustness to unseen layouts/procedures, stale observations, speech noise, and ambiguous identifiers.

Keep all benchmark inputs separated from policy training. Do not treat an LLM's self-reported confidence as a calibrated uncertainty estimate. Report simulated-human and real-human evaluations separately.

## Milestone completion policy

Replace a module outline only when its implementation is reviewable. Record verification evidence, update this file and README status in the same change, and use a focused branch/PR. Do not add passing badges, fabricated screenshots, or placeholder benchmark values. Future automation should reflect actual tests rather than tests of empty stubs.
