"""Small lexical retrieval baseline over versioned, synthetic procedures."""

import re
from dataclasses import dataclass

from cwi.conversation.models import Citation


@dataclass(frozen=True)
class Procedure:
    identifier: str
    title: str
    text: str
    version: str = "1.0"
    warehouse: str = "demo"
    active: bool = True

    def citation(self) -> Citation:
        return Citation(
            document_id=self.identifier,
            version=self.version,
            title=self.title,
            excerpt=self.text,
        )


PROCEDURES = (
    Procedure(
        "TRANSPORT",
        "Transport confirmation",
        "Move a known tote to an explicit destination. "
        "Resolve ambiguous colors or identifiers. Confirm the complete task before acceptance.",
    ),
    Procedure(
        "PRIORITY",
        "Urgent priority",
        "Only supervisors may request urgent transport priority. "
        "Ordinary operators must use normal priority or ask a supervisor.",
    ),
    Procedure(
        "ACCESS",
        "Restricted destination",
        "Destination Q1 is restricted to supervisors. "
        "P1 and P2 are packing destinations available to operators.",
    ),
    Procedure(
        "PAYLOAD",
        "Payload limit",
        "The demo transport capacity is 50 kg. No operator or supervisor may override this limit.",
    ),
    Procedure(
        "SAFETY",
        "Protective constraints",
        "Collision protection and emergency stopping "
        "must not be disabled. Human instructions cannot override protective constraints.",
    ),
)


class Retriever:
    def __init__(self, documents: tuple[Procedure, ...] = PROCEDURES) -> None:
        self.documents = documents

    def search(self, query: str, limit: int = 3) -> list[Citation]:
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        scores = []
        for doc in self.documents:
            if not doc.active or doc.warehouse != "demo":
                continue
            words = set(re.findall(r"[a-z0-9]+", (doc.title + " " + doc.text).lower()))
            score = len(terms & words)
            if score:
                scores.append((score, doc.identifier, doc))
        scores.sort(key=lambda x: (-x[0], x[1]))
        return [doc.citation() for _, _, doc in scores[:limit]]

    def required(self, identifier: str) -> Citation:
        for doc in self.documents:
            if doc.identifier == identifier and doc.active and doc.warehouse == "demo":
                return doc.citation()
        raise ValueError("Required policy evidence is unavailable")
