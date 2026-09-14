"""Three-robot, discrete-time simulation with local sensing and conservative reservations.

Only the simulator knows hidden obstacles. Planning sees shared sensor discoveries.
Robots cannot enter another robot's current cell, even if that robot plans to leave.
"""

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from cwi.conversation.models import Task
from cwi.planning.scheduler import Assignment, Cell, assign, route
from cwi.rl.clarification import Action, ClarificationPolicy
from cwi.state.warehouse import Warehouse


@dataclass
class Robot:
    identifier: str
    cell: Cell
    home: Cell
    battery: int = 100
    job: str | None = None
    phase: str = "idle"
    inspection_attempts: int = 0
    last_assistance: int = -10


@dataclass
class Job:
    identifier: str
    task: Task
    created: int
    deadline: int
    status: str = "queued"
    completed: int | None = None


class World:
    width = 12
    height = 8
    reserve = 8

    def __init__(self, assistance_mode: str = "inspect_when_possible") -> None:
        if assistance_mode not in {"q_learning", "always_ask", "inspect_when_possible"}:
            raise ValueError("Unknown assistance policy")
        self.assistance_mode = assistance_mode
        self.operator_busy = False
        self.assistance_policy = ClarificationPolicy.load(
            Path(__file__).parent.parent / "rl" / "default_policy.json"
        )
        self.inspections = 0
        self.operator_questions = 0
        self.warehouse = Warehouse()
        self.locations: dict[str, Cell] = {
            "A": (3, 2),
            "B": (3, 5),
            "P1": (10, 1),
            "P2": (10, 6),
            "Q1": (10, 4),
        }
        self.robots = [Robot(f"R{i + 1}", (0, y), (0, y)) for i, y in enumerate((1, 3, 6))]
        self.walls: set[Cell] = {(5, y) for y in (1, 2, 4, 5, 6)}
        self.hidden: set[Cell] = set()
        self.known: set[Cell] = set()
        self.jobs: dict[str, Job] = {}
        self.tick = 0
        self.distance = 0
        self.waits = 0
        self.events: list[dict[str, Any]] = []

    def event(self, kind: str, **data: Any) -> None:
        self.events.append({"tick": self.tick, "kind": kind, **data})
        self.events = self.events[-1000:]

    def submit(self, identifier: str, task: Task) -> None:
        if identifier in self.jobs:
            if self.jobs[identifier].task != task:
                raise ValueError("Idempotency key already belongs to a different task.")
            return
        if any(
            j.task.tote_id == task.tote_id and j.status != "completed" for j in self.jobs.values()
        ):
            raise ValueError("This tote already has an active transport task.")
        tote = next((t for t in self.warehouse.totes if t.identifier == task.tote_id), None)
        if tote is None or tote.source != task.source or tote.weight_kg > 50:
            raise ValueError("Tote state changed or payload is infeasible; clarify again.")
        if task.source not in self.locations or task.destination not in self.locations:
            raise ValueError("Unknown transport location.")
        self.jobs[identifier] = Job(
            identifier, task, self.tick, self.tick + (20 if task.priority == "urgent" else 50)
        )
        self.event("submitted", job=identifier)

    def obstacle(self, cell: Cell, present: bool) -> None:
        if not (0 <= cell[0] < self.width and 0 <= cell[1] < self.height):
            raise ValueError("Obstacle outside warehouse.")
        if (
            cell in self.locations.values()
            or cell in self.walls
            or any(cell == r.cell or cell == r.home for r in self.robots)
        ):
            raise ValueError("Cannot place obstacle on a station, wall, or robot.")
        if present:
            self.hidden.add(cell)
        else:
            self.hidden.discard(cell)
        # Do not reveal an external environmental change to the planner here.

    def observe(self, robot: Robot, radius: int) -> None:
        visible = {
            (x, y)
            for x in range(self.width)
            for y in range(self.height)
            if abs(x - robot.cell[0]) + abs(y - robot.cell[1]) <= radius
        }
        discoveries = (self.hidden & visible) - self.known
        removed = (self.known & visible) - self.hidden
        self.known = (self.known - visible) | (self.hidden & visible)
        if discoveries or removed:
            self.event(
                "observation",
                robot=robot.identifier,
                added=sorted(discoveries),
                removed=sorted(removed),
            )

    def sense(self) -> None:
        for robot in self.robots:
            self.observe(robot, 1)

    def resolve_uncertainty(self, robot: Robot) -> None:
        """Active inspection or operator feedback; never authorizes a movement."""
        if self.tick - robot.last_assistance < 5:
            return
        robot.last_assistance = self.tick
        action: Action
        if self.assistance_mode == "q_learning":
            action = self.assistance_policy.choose((1, int(self.operator_busy)))
        else:
            action = "ask" if self.assistance_mode == "always_ask" else "inspect"
        # Resource guard is independent of learned values.
        if action == "inspect" and (
            robot.battery <= self.reserve or robot.inspection_attempts >= 2
        ):
            action = "ask"
        if action == "inspect":
            robot.battery -= 1
            robot.inspection_attempts += 1
            self.inspections += 1
            self.observe(robot, 3)
            message = f"{robot.identifier} is inspecting nearby aisles before replanning."
        else:
            self.operator_questions += 1
            message = (
                f"{robot.identifier} needs assistance (battery {robot.battery}). "
                "Please check nearby aisle obstructions and clear a route if appropriate."
            )
        self.event(
            "assistance",
            robot=robot.identifier,
            action=action,
            policy=self.assistance_mode,
            message=message,
        )

    def plan(self) -> None:
        costs: list[Assignment] = []
        blocked = self.walls | self.known
        for robot in self.robots:
            if robot.job is not None or robot.phase == "charging":
                continue
            for job in self.jobs.values():
                if job.status != "queued":
                    continue
                source, destination = (
                    self.locations[job.task.source],
                    self.locations[job.task.destination],
                )
                legs = [
                    route(robot.cell, source, blocked, self.width, self.height),
                    route(source, destination, blocked, self.width, self.height),
                    route(destination, robot.home, blocked, self.width, self.height),
                ]
                if not all(legs):
                    continue
                lengths = [len(p) - 1 for p in legs]
                if sum(lengths) + self.reserve > robot.battery:
                    continue
                tardiness = max(0, self.tick + sum(lengths[:2]) + 2 - job.deadline)
                priority = 4 if job.task.priority == "urgent" else 1
                costs.append(
                    Assignment(
                        robot.identifier,
                        job.identifier,
                        2 * sum(lengths[:2])
                        + priority * 10 * tardiness
                        - priority * (self.tick - job.created),
                    )
                )
        for assignment in assign(costs):
            robot = next(r for r in self.robots if r.identifier == assignment.robot)
            robot.job, robot.phase = assignment.job, "pickup"
            robot.inspection_attempts = 0
            self.jobs[assignment.job].status = "assigned"
            self.event("assigned", robot=robot.identifier, job=assignment.job)

    def step(self, count: int = 1) -> None:
        if not 1 <= count <= 500:
            raise ValueError("Advance between 1 and 500 ticks.")
        for _ in range(count):
            self.sense()
            self.plan()
            occupied = {r.cell for r in self.robots}
            reserved: set[Cell] = set()
            for offset in range(len(self.robots)):
                robot = self.robots[(self.tick + offset) % len(self.robots)]
                if robot.job is None:
                    if robot.battery < 90 or robot.cell != robot.home:
                        robot.phase = "charging"
                        goal = robot.home
                    else:
                        robot.phase = "idle"
                        continue
                else:
                    job = self.jobs[robot.job]
                    goal = self.locations[
                        job.task.source if robot.phase == "pickup" else job.task.destination
                    ]
                if robot.cell == goal:
                    if robot.job is None:
                        robot.battery = min(100, robot.battery + 10)
                        if robot.battery == 100:
                            robot.phase = "idle"
                    elif robot.phase == "pickup":
                        robot.phase = "delivery"
                        self.jobs[robot.job].status = "carrying"
                        self.event("picked_up", robot=robot.identifier, job=robot.job)
                    else:
                        job = self.jobs[robot.job]
                        job.status, job.completed = "completed", self.tick
                        self.warehouse = replace(
                            self.warehouse,
                            totes=tuple(
                                replace(t, source=job.task.destination)
                                if t.identifier == job.task.tote_id
                                else t
                                for t in self.warehouse.totes
                            ),
                        )
                        self.event("delivered", robot=robot.identifier, job=robot.job)
                        robot.job, robot.phase = None, "idle"
                    continue
                path = route(
                    robot.cell,
                    goal,
                    self.walls | self.known | (occupied - {robot.cell}) | reserved,
                    self.width,
                    self.height,
                )
                if len(path) > 1 and robot.battery > 0:
                    next_cell = path[1]
                    # Sensing covers every candidate adjacent cell; this is a simulation invariant.
                    assert next_cell not in self.hidden
                    robot.cell = next_cell
                    reserved.add(next_cell)
                    robot.battery -= 1
                    self.distance += 1
                else:
                    self.waits += 1
                    # Traffic reservations alone are not an observation problem.
                    globally_blocked = not route(
                        robot.cell, goal, self.walls | self.known, self.width, self.height
                    )
                    if globally_blocked or robot.battery == 0:
                        self.resolve_uncertainty(robot)
                    self.event(
                        "waiting", robot=robot.identifier, reason="blocked_or_energy_depleted"
                    )
            assert len({r.cell for r in self.robots}) == len(self.robots)
            self.tick += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "assistance_mode": self.assistance_mode,
            "operator_busy": self.operator_busy,
            "width": self.width,
            "height": self.height,
            "robots": [asdict(r) for r in self.robots],
            "locations": self.locations,
            "walls": sorted(self.walls),
            "observed_obstacles": sorted(self.known),
            "totes": [asdict(t) for t in self.warehouse.totes],
            "jobs": [{**asdict(j), "task": j.task.model_dump()} for j in self.jobs.values()],
            "metrics": {
                "distance": self.distance,
                "inspections": self.inspections,
                "operator_questions": self.operator_questions,
                "waits": self.waits,
                "completed": sum(j.status == "completed" for j in self.jobs.values()),
                "tardiness": sum(
                    max(0, (j.completed or 0) - j.deadline)
                    for j in self.jobs.values()
                    if j.completed is not None
                ),
            },
            "events": self.events[-100:],
        }

    def checkpoint(self) -> dict[str, Any]:
        return {
            **self.snapshot(),
            "hidden": sorted(self.hidden),
            "all_events": [dict(event) for event in self.events],
        }

    @classmethod
    def restore(cls, data: dict[str, Any]) -> "World":
        world = cls(data.get("assistance_mode", "inspect_when_possible"))
        world.operator_busy = data.get("operator_busy", False)
        world.inspections = data["metrics"].get("inspections", 0)
        world.operator_questions = data["metrics"].get("operator_questions", 0)
        world.tick = data["tick"]
        world.distance = data["metrics"]["distance"]
        world.waits = data["metrics"]["waits"]
        world.known = {tuple(c) for c in data["observed_obstacles"]}
        world.hidden = {tuple(c) for c in data["hidden"]}
        world.robots = [
            Robot(**{**r, "cell": tuple(r["cell"]), "home": tuple(r["home"])})
            for r in data["robots"]
        ]
        from cwi.state.warehouse import Tote

        world.warehouse = replace(world.warehouse, totes=tuple(Tote(**t) for t in data["totes"]))
        world.jobs = {
            j["identifier"]: Job(**{**j, "task": Task.model_validate(j["task"])})
            for j in data["jobs"]
        }
        world.events = data["all_events"]
        return world
