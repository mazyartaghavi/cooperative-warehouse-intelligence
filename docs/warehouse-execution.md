# Warehouse execution milestone

The API factory enables a deterministic 12 × 8 warehouse with three robots and local
Manhattan-radius-one obstacle sensing. The planner never receives hidden obstacles. Active inspection can extend local sensing to radius three at a one-unit energy cost.
Observations are shared between robots; a changing obstacle is added or removed from
the shared map only when observed. Initial tote inventory and station coordinates
are trusted fixtures, not inferred camera detections.

Accepted, confirmed transport requests enter an idempotent job queue. CP-SAT maximizes
the number of feasible assignments, then minimizes travel and weighted predicted
lateness, with an aging term. One robot carries one tote. Feasibility includes travel
to pickup, delivery, and the robot's own charger, plus an eight-unit battery reserve.
All totes have a 50 kg payload ceiling. Grid routing uses breadth-first search over
known obstacles. Each time step reserves occupied starting cells and accepted target
cells, preventing both vertex collisions and edge swaps. Robot precedence rotates.
This conservative heuristic is not globally optimal multi-agent pathfinding and can
wait indefinitely in a blocked layout; the event log makes that limitation visible.
New detours can invalidate an earlier energy estimate; zero-energy robots stop and request assistance.

SQLite atomically checkpoints sessions, jobs, robots, observations, and simulator
state. The configured service is single-process; multiple workers are unsupported.
No physical commands are issued. HTTP `POST /warehouse/advance` controls simulated
time explicitly, and `POST /warehouse/obstacles` changes the environment without
revealing the change to the planner. `GET /warehouse` returns observable state.

The conversation uses a LangGraph retrieve → extract → validate workflow, followed
by a separate explicit confirmation and dispatch boundary. Procedures are seeded
into SQLite; the deterministic policy validator remains authoritative. Stored text
cannot change hard-coded protective constraints or the server-configured operator role.

## Operator interruption and cargo recovery

`GET /jobs/{id}` reads a job's current state. `POST /jobs/{id}/actions` accepts
`pause`, `resume`, or `cancel` for the requesting operator or a supervisor.
The original conversation accepts the same explicit phrases after dispatch.

| Situation | Result of cancellation |
|---|---|
| Queued or travelling to pickup | Mark cancelled, unlock the tote, release the unladen robot |
| Carrying a tote | Mark returning, route to the original source, keep the tote reserved |
| Returning after an earlier cancellation | No additional action; a paused return remains paused |
| Returned to source | Mark cancelled, record a return event, release the robot and tote |
| Already delivered | Reject cancellation; retain the completed delivery record |

Pause is a separate job flag, preserving whether pickup, delivery or return is
pending. A paused robot retains its occupied grid cell and cargo; other missions
continue. A paused queued job is excluded from assignment. The simulator has no
idle battery drain. A blocked or depleted return can remain pending and request
assistance; cancellation never teleports cargo or guarantees recovery from every
layout. Cancellation counts are separate from completed deliveries and lateness.

The inventory retains the last station location while a tote is carried, and the
active-job lock prevents a second assignment. Old checkpoints load with default
unpaused state. Pauses, returns, cancellation timestamps and issuer audit events
are persisted; failed writes roll back the entire attempted control action.
Destination changes and direct robot-to-robot reassignment remain extensions.
