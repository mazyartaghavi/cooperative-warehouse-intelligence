"""Small lexical retrieval baseline over versioned, synthetic procedures."""

import math
import re
from collections import Counter
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
    Procedure(
        "INSPECTION",
        "Blocked-aisle inspection",
        "When a previously observed obstruction prevents routing, a robot may inspect nearby "
        "aisles before asking the operator. Inspection consumes energy, stays local, and never "
        "authorizes a transport or overrides a protective limit. Unresolved instructions need "
        "human clarification, not a guessed destination.",
    ),
)


class Retriever:
    def __init__(self, documents: tuple[Procedure, ...] = PROCEDURES) -> None:
        active_ids = [d.identifier for d in documents if d.active and d.warehouse == "demo"]
        if len(set(active_ids)) != len(active_ids):
            raise ValueError("Multiple active procedure versions; resolve before startup.")
        self.documents = documents

    def search(self, query: str, limit: int = 3) -> list[Citation]:
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        active = [d for d in self.documents if d.active and d.warehouse == "demo"]
        counts = [
            Counter(re.findall(r"[a-z0-9]+", (d.title + " " + d.text).lower())) for d in active
        ]
        average = sum(sum(c.values()) for c in counts) / max(1, len(counts))
        scores = []
        for doc, count in zip(active, counts, strict=True):
            score = 0.0
            length = sum(count.values())
            for term in terms:
                frequency = count[term]
                if not frequency:
                    continue
                df = sum(term in c for c in counts)
                idf = math.log(1 + (len(active) - df + 0.5) / (df + 0.5))
                score += (
                    idf
                    * frequency
                    * 2.5
                    / (frequency + 1.5 * (0.25 + 0.75 * length / max(average, 1)))
                )
            if score:
                scores.append((score, doc.identifier, doc))
        scores.sort(key=lambda x: (-x[0], x[1]))
        return [doc.citation() for _, _, doc in scores[:limit]]

    def required(self, identifier: str) -> Citation:
        for doc in self.documents:
            if doc.identifier == identifier and doc.active and doc.warehouse == "demo":
                return doc.citation()
        raise ValueError("Required policy evidence is unavailable")
