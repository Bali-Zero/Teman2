"""SSE/WebSocket event schemas for real-time frontend streaming."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class StreamEventType(StrEnum):
    NODE_START = "node_start"
    NODE_END = "node_end"
    NODE_ERROR = "node_error"
    ANSWER_CHUNK = "answer_chunk"
    GRADE_RESULT = "grade_result"
    CORRECTION_START = "correction_start"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATE_UPDATE = "state_update"
    DONE = "done"
    ERROR = "error"


class StreamNodeEvent(BaseModel):
    """Event emitted by each graph node for real-time frontend updates."""

    run_id: str
    event_type: StreamEventType
    node: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    sequence: int = 0  # monotonically increasing per run


class SSEMessage(BaseModel):
    """Formatted SSE message ready for HTTP streaming."""

    event: str
    data: str  # JSON-serialized StreamNodeEvent
    id: str | None = None
    retry: int | None = None

    def to_sse(self) -> str:
        lines = [f"event: {self.event}", f"data: {self.data}"]
        if self.id:
            lines.append(f"id: {self.id}")
        if self.retry:
            lines.append(f"retry: {self.retry}")
        return "\n".join(lines) + "\n\n"
