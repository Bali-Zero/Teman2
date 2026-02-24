"""Tool call schemas for the reason/tools nodes."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ToolStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class ToolCallRecord(BaseModel):
    """Record of a tool invocation during reasoning."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    status: ToolStatus = ToolStatus.PENDING
    error_message: str | None = None
    duration_ms: float | None = None
