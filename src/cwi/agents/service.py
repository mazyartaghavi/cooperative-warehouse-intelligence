"""Bounded text-to-task workflow; M1 never dispatches a physical command."""

import threading
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from cwi.agents.workflow import Workflow
from cwi.conversation.backends import Backend
from cwi.conversation.models import Reply, Task
from cwi.policy.validation import validate
from cwi.retrieval.service import Retriever
from cwi.simulation.world import World
from cwi.state.store import Store
from cwi.state.warehouse import Operator, Warehouse


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
            if session.final:
                return session.final.model_copy(deep=True)
            normalized = text.strip().lower().rstrip(".! ")
            if normalized == "cancel":
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
