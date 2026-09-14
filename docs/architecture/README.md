# Architecture and trust boundaries

The application has one coordinator and three simulated robot executors. Robot
cooperation uses a central allocator and shared observations; it is not distributed
consensus or three independent LLM agents.

## Request lifecycle

1. The authenticated operator starts a session. Its ID is the task idempotency key.
2. Typed text or reviewed transcription enters the same strict message contract.
3. LangGraph retrieves active procedures and current inventory observations.
4. The selected backend proposes an `Intent`. Ollama receives a JSON schema;
   the offline baseline uses a restricted English grammar.
5. The policy validator checks explicit identifiers, ambiguity, payload, and role.
6. The operator resolves ambiguity and confirms the complete task. Every correction
   clears the prior pending proposal, including extraction failures.
7. Confirmation revalidates the current inventory and role, then submits exactly one
   job. Session acceptance and simulator state are checkpointed together.
8. Each requested simulation tick senses, assigns feasible work, routes, reserves
   movement, changes robot state, records events, and checkpoints the result.

## State ownership

| State | Owner | Consumer |
|---|---|---|
| Hidden dynamic obstacles | Simulator | Local sensor model only |
| Shared observed obstacles | Sensor updates | Planner and dashboard |
| Procedure records and versions | SQLite corpus | Retriever and citations |
| Authoritative access/payload rules | Policy validator | Confirmation boundary |
| Operator role | Server configuration | Validator |
| Pending task and conversation turns | Conversation service | Model and confirmation |
| Robot pose, battery, job phase | Simulator | Allocator, routes and UI |
| Generated procedure answer | Knowledge service | Operator, never executor |

A global reentrant lock serializes mutations. SQLite uses WAL and one atomic JSON
checkpoint record; this keeps the small prototype understandable but is not an
unbounded production event store. Persisted state contains conversations and should
be treated as operational data. Hidden simulator state is persisted for replay but
excluded from the public observation endpoint.

## Failure behavior

Invalid model JSON, provider errors, missing policy evidence, and invalid corrections
cannot dispatch work. Unknown sessions return 404; unauthorized API requests return
401. Pending confirmation is invalidated on correction before model inference.
Duplicate confirmation returns the same accepted response and does not enqueue again.
A persistence failure rolls back successful in-memory task/step mutation.

The scheduler can leave work queued if no feasible assignment exists. Conservative
routing can wait in congested or blocked configurations. Events expose waiting;
there is no claim of deadlock freedom. A new obstacle cannot be placed on an occupied
robot cell, station, charger, or static wall in this discrete fixture.

## Voice and generated answers

Audio transcribes to text without creating a task. The operator reviews the text,
then sends it through the ordinary task boundary. Recorded audio is deleted after
local decoding; conversation text is persisted. Browser speech synthesis is optional
and may use operating-system services. Procedure Q&A validates cited source IDs but
cannot prove that the generated prose is entailed by those sources. The canonical
policy decision and explicit task summary remain the execution authority.
