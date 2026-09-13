"""Deterministic guards for the synthetic warehouse, independent of the model."""

import re
from dataclasses import dataclass

from cwi.conversation.models import Intent, Task
from cwi.state.warehouse import Operator, Warehouse


@dataclass(frozen=True)
class Decision:
    status: str
    message: str
    document: str
    task: Task | None = None


def validate(
    intent: Intent, turns: list[str], warehouse: Warehouse, operator: Operator
) -> Decision:
    transcript = " ".join(turns).upper()
    if intent.disable_safety:
        return Decision("rejected", "Protective constraints cannot be disabled.", "SAFETY")
    if intent.action != "transport":
        return Decision("clarification", "Please request one tote transport task.", "TRANSPORT")
    # An LLM cannot supply a known ID that the operator never actually mentioned.
    for value in [intent.tote_id, intent.destination]:
        if value and not re.search(r"\b" + re.escape(value.upper()) + r"\b", transcript):
            return Decision(
                "clarification",
                "Please explicitly state the tote and destination IDs.",
                "TRANSPORT",
            )
    tote = None
    if intent.tote_id:
        tote = next((t for t in warehouse.totes if t.identifier == intent.tote_id.upper()), None)
        if tote is None:
            return Decision(
                "clarification",
                "That tote is unknown. Please provide a known tote ID.",
                "TRANSPORT",
            )
    elif intent.color:
        matches = [t for t in warehouse.totes if t.color == intent.color.lower()]
        if len(matches) == 1:
            tote = matches[0]
        else:
            ids = ", ".join(t.identifier for t in matches) or "no matching totes"
            return Decision(
                "clarification", f"Which tote do you mean? Observed: {ids}.", "TRANSPORT"
            )
    if tote is None:
        return Decision("clarification", "Which tote should be transported?", "TRANSPORT")
    destination = (intent.destination or "").upper()
    if destination not in warehouse.destinations:
        return Decision(
            "clarification", "Please specify a known destination: P1, P2, or Q1.", "TRANSPORT"
        )
    if tote.weight_kg > warehouse.max_payload_kg:
        return Decision("rejected", "This tote exceeds the 50 kg demo payload limit.", "PAYLOAD")
    if destination in warehouse.restricted_destinations and operator.role != "supervisor":
        return Decision("rejected", "Q1 requires supervisor authorization.", "ACCESS")
    if intent.priority == "urgent" and operator.role != "supervisor":
        return Decision(
            "rejected",
            "Urgent priority requires a supervisor; request normal priority.",
            "PRIORITY",
        )
    task = Task(
        tote_id=tote.identifier,
        source=tote.source,
        destination=destination,
        priority=intent.priority,
        requested_by=operator.identifier,
    )
    return Decision(
        "awaiting_confirmation",
        f"Confirm {task.tote_id} from {task.source} to "
        f"{task.destination}, {task.priority} priority? Reply 'confirm' or correct it.",
        "TRANSPORT",
        task,
    )
