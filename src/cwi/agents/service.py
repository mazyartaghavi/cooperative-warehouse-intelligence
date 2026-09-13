"""Bounded text-to-task workflow; M1 never dispatches a physical command."""

import threading
from dataclasses import dataclass, field
from uuid import uuid4

from cwi.conversation.backends import Backend, BackendError, BaselineBackend
from cwi.conversation.models import Reply, Task
from cwi.policy.validation import validate
from cwi.retrieval.service import Retriever
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
    ) -> None:
        self.backend = backend
        self.operator = operator or Operator()
        self.warehouse = warehouse or Warehouse()
        self.retriever = retriever or Retriever()
        self.sessions: dict[str, Session] = {}
        self.lock = threading.Lock()

    def new_session(self) -> str:
        with self.lock:
            if len(self.sessions) >= 1000:
                raise ValueError("Demo session limit reached; restart the service.")
            identifier = str(uuid4())
            self.sessions[identifier] = Session()
            return identifier

    def reply(self, identifier: str, text: str) -> Reply:
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
                session.final = Reply(
                    session_id=identifier,
                    status="accepted",
                    backend=self.backend.name,
                    message="Task specification accepted. Planning and robot dispatch are not "
                    "implemented in M1; no robot has moved.",
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
            evidence = self.retriever.search(" ".join(turns))
            trace = ["retrieve_procedures", "extract_intent", "validate_policy"]
            intent = self.backend.extract(turns, evidence)
            # Independently reject explicit protective-bypass phrases recognized by the baseline.
            try:
                if BaselineBackend().extract([text], []).disable_safety:
                    intent.disable_safety = True
            except BackendError:
                pass
            decision = validate(intent, turns, self.warehouse, self.operator)
            cited = {c.document_id: c for c in evidence}
            cited[decision.document] = self.retriever.required(decision.document)
            session.turns = turns
            session.pending = decision.task
            return Reply.model_validate(
                {
                    "session_id": identifier,
                    "status": decision.status,
                    "message": decision.message,
                    "backend": self.backend.name,
                    "task": decision.task,
                    "citations": list(cited.values()),
                    "trace": trace,
                }
            )
