# Agent coordination

`workflow.py` compiles the LangGraph retrieve/extract/validate graph. `service.py` owns clarification, corrections, confirmation revalidation, idempotent dispatch and SQLite checkpoints. Generated fields cannot execute outside this boundary.

See the [project README](../../../README.md) for startup, evidence and scope.
