"""Single-process SQLite checkpoints and versioned procedure records."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from cwi.retrieval.service import PROCEDURES, Procedure


class Store:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS checkpoint (id INTEGER PRIMARY KEY, data TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS procedures (id TEXT, version TEXT, "
            "data TEXT NOT NULL, "
            "PRIMARY KEY(id, version))"
        )
        with self.connection:
            for doc in PROCEDURES:
                from dataclasses import asdict

                self.connection.execute(
                    "INSERT OR IGNORE INTO procedures VALUES (?, ?, ?)",
                    (doc.identifier, doc.version, json.dumps(asdict(doc))),
                )

    def procedures(self) -> tuple[Procedure, ...]:
        return tuple(
            Procedure(**json.loads(row[0]))
            for row in self.connection.execute("SELECT data FROM procedures ORDER BY id, version")
        )

    def load(self) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT data FROM checkpoint WHERE id=1").fetchone()
        return json.loads(row[0]) if row else None

    def save(self, state: dict[str, Any]) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO checkpoint VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (json.dumps(state),),
            )
