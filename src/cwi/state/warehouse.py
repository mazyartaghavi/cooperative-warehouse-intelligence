"""A tiny, explicitly synthetic observed-state fixture for M1."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Operator:
    identifier: str = "demo-operator"
    role: Literal["operator", "supervisor"] = "operator"


@dataclass(frozen=True)
class Tote:
    identifier: str
    color: str
    source: str
    weight_kg: float


@dataclass(frozen=True)
class Warehouse:
    totes: tuple[Tote, ...] = (
        Tote("T17", "blue", "A", 12.0),
        Tote("T23", "blue", "A", 8.0),
        Tote("T31", "red", "B", 80.0),
        Tote("T42", "green", "B", 15.0),
    )
    destinations: tuple[str, ...] = ("P1", "P2", "Q1")
    restricted_destinations: tuple[str, ...] = ("Q1",)
    max_payload_kg: float = 50.0
