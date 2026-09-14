# Assignment and routing

`scheduler.py` models one-job/one-robot assignment in OR-Tools CP-SAT and provides BFS grid routes. Battery/route feasibility is computed by the simulator before candidate edges are supplied. Global multi-agent routing is a conservative heuristic, not an optimal MAPF solver.

See the [project README](../../../README.md) for startup, evidence and scope.
