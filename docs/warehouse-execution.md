# Warehouse execution milestone

The API factory enables a deterministic 12 × 8 warehouse with three robots and local
Manhattan-radius-one obstacle sensing. The planner never receives hidden obstacles.
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
New detours can invalidate an earlier energy estimate; zero-energy robots stop.

SQLite atomically checkpoints sessions, jobs, robots, observations, and simulator
state. The configured service is single-process; multiple workers are unsupported.
No physical commands are issued. HTTP `POST /warehouse/advance` controls simulated
time explicitly, and `POST /warehouse/obstacles` changes the environment without
revealing the change to the planner. `GET /warehouse` returns observable state.

The conversation uses a LangGraph retrieve → extract → validate workflow, followed
by a separate explicit confirmation and dispatch boundary. Procedures are seeded
into SQLite; the deterministic policy validator remains authoritative. Stored text
cannot change hard-coded protective constraints or the server-configured operator role.
