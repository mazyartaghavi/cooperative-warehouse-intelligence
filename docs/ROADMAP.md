# Capability status and roadmap

## Current snapshot

- Completed: approved subject, title, GenAI-first design, recruiter-facing project overview, directory/module outlines, and initial repository publication.
- Current milestone: M1 text-to-task implementation, prepared for PR review.
- Next: validate an installed local model, then implement M2 robot execution simulation.
- Implemented: text API, synthetic observed state, lexical retrieval, clarification/correction, deterministic policy checks, confirmation, and a runnable offline baseline.
- Experimental: Ollama structured extraction adapter is contract-tested; live-model evaluation is pending.
- Planned: speech, persistent LangGraph orchestration, hybrid retrieval, dynamic robotics, optimization, and RL.

## Milestones

| Milestone | Scope | Completion evidence | Status |
| --- | --- | --- | --- |
| M0 | Documentation and repository scaffold | Reviewed files and verified GitHub publication | Published |
| M1 | Text conversation, procedure retrieval, validated task extraction and clarification | Runnable baseline, source citations, 35 passing tests; live LLM validation pending | Implemented baseline; LLM adapter experimental |
| M2 | Three-robot dynamic warehouse and planning | End-to-end task execution, changing obstacles, observable status, and reservation checks | Planned |
| M3 | Recorded and live voice | Transcription, spoken replies, corrections, and measured identifier/noise errors | Planned |
| M4 | Agent reliability | Recovery, cancellation, conflicting orders, duplicate protection, persistence, and reconnect scenarios | Planned |
| M5 | RL clarification study | Fixed-rule baselines, held-out evaluation, multiple seeds, and transparent reports | Planned |
| M6 | Hardware preparation | Documented adapter contract and physical validation plan | Planned |

## Next milestone and known issues

- Review the M1 PR and validate an installed Ollama model against the annotated task scenarios.
- Then M2: connect accepted specifications to a three-robot simulation and constrained planning.
- Speech, vector retrieval, LangGraph persistence, model-quality benchmarks, and production deployment remain absent.
- Local test dependencies emit two upstream deprecation warnings (Starlette/httpx and AnyIO); tests pass. These warnings are not suppressed.
- One demo token maps to one server-configured operator; sessions are in memory and requests serialized. This is not multi-user production authentication.
- Software license, hardware access, and model compute budget remain open decisions.

## Planned experiments

1. Procedure-grounding ablation with and without retrieval.
2. Fixed clarification rules versus learned clarification, measuring operator workload and task correctness.
3. Persistent agent recovery versus a single planning call on identical injected failures.
4. Robustness to unseen layouts/procedures, stale observations, speech noise, and ambiguous identifiers.

Keep all benchmark inputs separated from policy training. Do not treat an LLM's self-reported confidence as a calibrated uncertainty estimate. Report simulated-human and real-human evaluations separately.

## Milestone completion policy

Replace a module outline only when its implementation is reviewable. Record verification evidence, update this file and README status in the same change, and use a focused branch/PR. Do not add passing badges, fabricated screenshots, or placeholder benchmark values. Future automation should reflect actual tests rather than tests of empty stubs.
