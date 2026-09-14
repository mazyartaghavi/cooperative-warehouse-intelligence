"""Bounded optimal assignment and obstacle-aware grid routing."""

from collections import deque
from dataclasses import dataclass

from ortools.sat.python import cp_model

Cell = tuple[int, int]


def route(start: Cell, goal: Cell, blocked: set[Cell], width: int, height: int) -> list[Cell]:
    if goal in blocked:
        return []
    frontier = deque([start])
    parent: dict[Cell, Cell | None] = {start: None}
    while frontier:
        cell = frontier.popleft()
        if cell == goal:
            path = [cell]
            while parent[path[-1]] is not None:
                previous = parent[path[-1]]
                assert previous is not None
                path.append(previous)
            return path[::-1]
        x, y = cell
        for neighbor in ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)):
            if (
                0 <= neighbor[0] < width
                and 0 <= neighbor[1] < height
                and neighbor not in blocked
                and neighbor not in parent
            ):
                parent[neighbor] = cell
                frontier.append(neighbor)
    return []


@dataclass(frozen=True)
class Assignment:
    robot: str
    job: str
    cost: int


def assign(costs: list[Assignment]) -> list[Assignment]:
    """Maximize served jobs first, then minimize integer cost, subject to one job/robot."""
    if not costs:
        return []
    model = cp_model.CpModel()
    variables = [model.new_bool_var(f"a{i}") for i in range(len(costs))]
    for robot in sorted({c.robot for c in costs}):
        model.add(sum(v for v, c in zip(variables, costs, strict=True) if c.robot == robot) <= 1)
    for job in sorted({c.job for c in costs}):
        model.add(sum(v for v, c in zip(variables, costs, strict=True) if c.job == job) <= 1)
    bonus = sum(abs(c.cost) for c in costs) + 1
    model.maximize(sum(v * (bonus - c.cost) for v, c in zip(variables, costs, strict=True)))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 1.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return []
    return [c for v, c in zip(variables, costs, strict=True) if solver.value(v)]
