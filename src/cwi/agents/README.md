# Agent coordination

`workflow.py` compiles the LangGraph retrieve/extract/validate graph. `service.py` owns clarification, corrections, confirmation revalidation, idempotent dispatch and SQLite checkpoints. Generated fields cannot execute outside this boundary.

Accepted conversations remain linked to their job for deterministic status, pause,
resume and cancellation commands. Ownership is checked against the server identity,
and current simulator state supplies status. A carried tote must return before
cancellation completes; task control and persistence use the same serialized service
boundary as dispatch and simulation advancement.

See the [project README](../../../README.md) for startup, evidence and scope.
