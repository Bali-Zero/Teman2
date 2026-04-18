"""Protocol and result type for remediation actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ActionResult:
    success: bool
    detail: str | None = None
    error: str | None = None


class RemediationAction(Protocol):
    name: str
    target_check: str

    async def run(self) -> ActionResult: ...
