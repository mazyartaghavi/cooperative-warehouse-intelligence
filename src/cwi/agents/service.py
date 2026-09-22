"""Durable conversation and operator controls for simulated warehouse missions."""

import threading
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from cwi.agents.workflow import Workflow
from cwi.conversation.backends import Backend
from cwi.conversation.models import JobAction, JobUpdate, Reply, Task
from cwi.policy.validation import validate
from cwi.retrieval.service import Retriever
from cwi.simulation.world import World
from cwi.state.store import Store
from cwi.state.warehouse import Operator, Warehouse

JOB_COMMANDS: dict[str, JobAction] = {
    phrase: action
    for action in ("pause", "resume", "cancel")
    for phrase in (action, f"{action} task", f"{action} the task", f"{action} my task")
}
STATUS_COMMANDS = {"status", "task status", "what is the task status", "what is the status"}


@dataclass
class Session:
    turns: list[str] = field(default_factory=list)
    pending: Task | None = None
    final: Reply | None = None


class ConversationService:
    def __init__(
        self,
        backend: Backend,
        operator: Operator | None = None,
        warehouse: Warehouse | None = None,
        retriever: Retriever | None = None,
        world: World | None = None,
        store: Store | None = None,
    ) -> None:
        self.backend = backend
        self.operator = operator or Operator()
        self.warehouse = warehouse or Warehouse()
        self.retriever = retriever or Retriever()
        self.sessions: dict[str, Session] = {}
        self.lock = threading.RLock()
        self.world = world
        self.store = store
        if world is not None:
            self.warehouse = world.warehouse
        self.workflow = Workflow(self.backend, self.retriever, self.operator)
        if store is not None:
            saved = store.load()
            if saved:
                self.restore(saved)

    def new_session(self) -> str:
        with self.lock:
            if len(self.sessions) >= 1000:
                raise ValueError("Demo session limit reached; restart the service.")
            identifier = str(uuid4())
            self.sessions[identifier] = Session()
            try:
                self.persist()
            except Exception:
                del self.sessions[identifier]
                raise
            return identifier

    def checkpoint(self) -> dict[str, Any]:
        return {
            "sessions": {
                sid: {
                    "turns": s.turns,
                    "pending": s.pending.model_dump() if s.pending else None,
                    "final": s.final.model_dump() if s.final else None,
                }
                for sid, s in self.sessions.items()
            },
            "world": self.world.checkpoint() if self.world else None,
        }

    def restore(self, data: dict[str, Any]) -> None:
        self.sessions = {
            sid: Session(
                s["turns"],
                Task.model_validate(s["pending"]) if s["pending"] else None,
                Reply.model_validate(s["final"]) if s["final"] else None,
            )
            for sid, s in data["sessions"].items()
        }
        if data["world"] is not None:
            mode = (
                self.world.assistance_mode
                if self.world
                else data["world"].get("assistance_mode", "inspect_when_possible")
            )
            self.world = World.restore(data["world"])
            self.world.assistance_mode = mode
            self.warehouse = self.world.warehouse

    def persist(self) -> None:
        if self.store is not None:
            self.store.save(self.checkpoint())

    def job_update(self, identifier: str) -> JobUpdate:
        """Read actual execution state; never infer completion from an acceptance receipt."""
        with self.lock:
            if self.world is None:
                raise ValueError("Simulation is disabled")
            job = self.world.jobs[identifier]
            if (
                job.task.requested_by != self.operator.identifier
                and self.operator.role != "supervisor"
            ):
                raise PermissionError(
                    "Only the requesting operator or a supervisor may control this job."
                )
            robot = next((r for r in self.world.robots if r.job == identifier), None)
            messages = {
                "queued": "Task is queued; no robot has picked up the tote.",
                "assigned": "A robot is travelling to collect the tote.",
                "carrying": "The robot is carrying the tote to its confirmed destination.",
                "returning": "Cancellation pending: the robot must return the tote to its source.",
                "cancelled": (
                    "Task cancelled without delivery. Any carried tote was returned to its source."
                ),
                "completed": "Delivery completed, confirmed by the simulator.",
            }
            message = messages[job.status]
            if job.paused:
                message = (
                    f"Task paused during {job.status}; the robot holds position and any cargo."
                    if robot
                    else "Task paused in the queue; no robot is assigned."
                )
            return JobUpdate(
                job_id=identifier,
                status=job.status,
                paused=job.paused,
                task=job.task.model_copy(deep=True),
                robot_id=robot.identifier if robot else None,
                tick=self.world.tick,
                message=message,
            )

    def control_job(self, identifier: str, action: JobAction) -> JobUpdate:
        with self.lock:
            self.job_update(identifier)  # Authorize before any mutation.
            assert self.world is not None
            previous = self.checkpoint()
            try:
                self.world.control(identifier, action, self.operator.identifier)
                self.persist()
                return self.job_update(identifier)
            except Exception:
                self.restore(previous)
                raise

    def reply(self, identifier: str, text: str) -> Reply:
        with self.lock:
            if self.world:
                self.warehouse = self.world.warehouse
            previous = self.checkpoint()
            try:
                result = self._reply(identifier, text)
            except Exception:
                self.persist()  # Retain invalidation of old confirmation on extraction failure.
                raise
            try:
                self.persist()
            except Exception:
                self.restore(previous)
                raise
            return result

    def _reply(self, identifier: str, text: str) -> Reply:
        if not text.strip() or len(text) > 2000:
            raise ValueError("Messages must contain 1–2000 nonblank characters.")
        with self.lock:
            session = self.sessions[identifier]
            normalized = text.strip().lower().rstrip(".!? ")
            if session.final:
                if self.world is None or identifier not in self.world.jobs:
                    return session.final.model_copy(deep=True)
                update = self.job_update(identifier)
                # Retries of the initial confirmation return the same acceptance receipt.
                if (
                    normalized in {"confirm", "yes"}
                    and update.status == "queued"
                    and not update.paused
                ):
                    return session.final.model_copy(deep=True)
                action = JOB_COMMANDS.get(normalized)
                if action is not None:
                    self.world.control(identifier, action, self.operator.identifier)
                    update = self.job_update(identifier)
                elif normalized not in STATUS_COMMANDS and normalized not in {"confirm", "yes"}:
                    update.message += (
                        " No task change was made. Use status, pause, resume or cancel; "
                        "start a new conversation for a different transport."
                    )
                return Reply(
                    session_id=identifier,
                    status="job_update",
                    backend=self.backend.name,
                    message=update.message,
                    task=update.task,
                    job_id=identifier,
                    job=update,
                    trace=["job_authorization", "job_control" if action else "execution_status"],
                )
            if normalized in STATUS_COMMANDS or JOB_COMMANDS.get(normalized) in {"pause", "resume"}:
                return Reply(
                    session_id=identifier,
                    status="clarification",
                    backend=self.backend.name,
                    message="No job was dispatched. Review and confirm a task first.",
                    trace=["job_guard"],
                )
            if JOB_COMMANDS.get(normalized) == "cancel":
                session.pending = None
                session.final = Reply(
                    session_id=identifier,
                    status="cancelled",
                    backend=self.backend.name,
                    message="Conversation cancelled. No robot command was dispatched.",
                    trace=["cancel"],
                )
                return session.final.model_copy(deep=True)
            if normalized in {"confirm", "yes"}:
                if session.pending is None:
                    return Reply(
                        session_id=identifier,
                        status="clarification",
                        backend=self.backend.name,
                        message="There is no task to confirm.",
                        trace=["confirmation_guard"],
                    )
                # Revalidate observed state and authorization at the acceptance boundary.
                from cwi.conversation.models import Intent

                pending = session.pending
                checked = validate(
                    Intent(
                        action="transport",
                        tote_id=pending.tote_id,
                        destination=pending.destination,
                        priority=pending.priority,
                    ),
                    [f"{pending.tote_id} {pending.destination}"],
                    self.warehouse,
                    self.operator,
                )
                session.pending = None
                if checked.task is None:
                    return Reply(
                        session_id=identifier,
                        status="rejected",
                        backend=self.backend.name,
                        message=checked.message,
                        citations=[self.retriever.required(checked.document)],
                        trace=["confirmation_guard", "revalidate"],
                    )
                if checked.task != pending:
                    return Reply(
                        session_id=identifier,
                        status="clarification",
                        backend=self.backend.name,
                        message="Observed task details changed. Please restate your request.",
                        trace=["confirmation_guard", "revalidate"],
                    )
                if self.world is not None:
                    self.world.submit(identifier, pending)
                session.final = Reply(
                    session_id=identifier,
                    status="accepted",
                    backend=self.backend.name,
                    message=(
                        "Task queued for simulated robot execution. "
                        "Watch the warehouse for progress."
                        if self.world is not None
                        else "Task specification accepted; execution is disabled."
                    ),
                    execution_dispatched=self.world is not None,
                    job_id=identifier if self.world is not None else None,
                    task=pending,
                    citations=[self.retriever.required("TRANSPORT")],
                    trace=["confirmation_guard", "revalidate", "accept_specification"],
                )
                return session.final.model_copy(deep=True)
            # A correction invalidates earlier confirmation even when extraction fails.
            session.pending = None
            if len(session.turns) >= 40:
                raise ValueError("Demo turn limit reached; start a new session.")
            turns = session.turns + [text]
            result = self.workflow.run(turns, self.warehouse)
            decision = result["decision"]
            session.turns = turns
            session.pending = decision.task
            return Reply.model_validate(
                {
                    "session_id": identifier,
                    "status": decision.status,
                    "message": decision.message,
                    "backend": self.backend.name,
                    "task": decision.task,
                    "citations": result["evidence"],
                    "trace": result["trace"],
                }
            )
