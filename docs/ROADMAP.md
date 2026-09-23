# Milestones and validation

The approved subject is **Cooperative Warehouse Intelligence**, with GenAI, agentic
workflows, LLMs and RAG as the primary focus. Implementation is simulation-first.

| Milestone | Delivered software | Evidence |
|---|---|---|
| Foundation | Installable Python package, quality tooling, GitHub root README | Original foundation and PR #1 |
| Grounded conversations | Strict intents, active procedures, clarification, corrections, confirmation and role checks | Behavioral and mocked model-contract tests |
| Cooperative execution | Three robots, CP-SAT assignment, partially observed obstacles, routing, charging, SQLite checkpoints | Static/dynamic delivery scenarios and collision/restart tests |
| Operator interface | Browser dashboard, microphone/file controls, transcription adapter, text-to-speech controls, grounded Q&A | API/adapter contracts; real browser smoke workflow |
| Mission interruption | Owner/supervisor pause, resume, status and cancellation; return carried totes; durable recovery | Control, authorization and rollback tests; extended browser workflow |
| Learned assistance | Seeded Q-learning, fixed-policy baselines, bounded active inspection or operator feedback | Synthetic experiments and integrated stale-obstacle fixture |
| Research package | Mathematical model, documented assumptions, recorded JSON results, live model evaluation command | Reproduction commands and verification record |

## Current status

[Progress log](PROGRESS.md) · [Live validation guide](live-validation.md)

Installed-runtime checks, a multi-turn conversation-to-delivery suite, speech
corpus evaluation and combined recorded-voice-to-delivery evaluation are implemented.
The offline grammar now passes the 12-case regression fixture; the local software
suite passes 123 tests. Language evaluation now checks specific rejection policies
and can retain bounded model diagnostics. Revised prompts and citation constraints
need actual model evaluation. Speech validation requires local weights and recordings.

## External validation still required

- Install and evaluate actual LLM and speech model weights on the intended machine;
  measure instruction accuracy, uncertainty handling, noisy speech and response latency.
- Add broader layouts/workloads, held-out linguistic examples, retrieval ablations,
  alternative MAPF/scheduling baselines and calibrated human interruption costs.
- Validate human interaction with actual operators before claiming fluent industrial use.
- Physical deployment requires localization, perception, robot drivers, docking,
  continuous control, protected stopping and human-separation validation. This is
  a separate engineering program, not a completed feature of the 2D prototype.

The software milestones above replace the original placeholders. They do not imply
completion of live-model studies, industrial safety validation, or real warehouse
hardware integration. See [verification](verification.md) for checks actually run.
