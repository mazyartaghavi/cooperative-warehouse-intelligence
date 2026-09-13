"""Validated contracts: model output is a proposal, never an execution command."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Intent(StrictModel):
    action: Literal["transport", "unknown"] = "unknown"
    tote_id: str | None = None
    color: str | None = None
    destination: str | None = None
    priority: Literal["normal", "urgent"] = "normal"
    disable_safety: bool = False


class Task(StrictModel):
    tote_id: str
    source: str
    destination: str
    priority: Literal["normal", "urgent"]
    requested_by: str


class Citation(StrictModel):
    document_id: str
    version: str
    title: str
    excerpt: str


class Reply(StrictModel):
    session_id: str
    status: Literal["clarification", "awaiting_confirmation", "accepted", "rejected", "cancelled"]
    message: str
    backend: str
    task: Task | None = None
    citations: list[Citation] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)
    execution_dispatched: bool = False


class Message(StrictModel):
    text: str = Field(min_length=1, max_length=2000)
