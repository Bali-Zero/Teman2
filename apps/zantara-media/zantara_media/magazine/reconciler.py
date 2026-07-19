"""Durable outcome states used to prevent blind mutation retries."""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class OutcomeState(StrEnum):
    pending = "pending"
    completed = "completed"
    absent = "absent"
    unknown = "outcome_unknown"


class OutcomeUnknownError(RuntimeError):
    """Raised when remote state cannot be proven before a retry."""


class OutcomeJournal(Protocol):
    async def set(self, operation_id: str, state: OutcomeState) -> None: ...

    async def get(self, operation_id: str) -> OutcomeState | None: ...


class InMemoryOutcomeJournal:
    def __init__(self) -> None:
        self._states: dict[str, OutcomeState] = {}
        self._lock = asyncio.Lock()

    async def set(self, operation_id: str, state: OutcomeState) -> None:
        async with self._lock:
            self._states[operation_id] = state

    async def get(self, operation_id: str) -> OutcomeState | None:
        async with self._lock:
            return self._states.get(operation_id)


class DurableOutcomeJournal:
    """Append-only JSONL outcome journal with fsync on every transition."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()

    async def set(self, operation_id: str, state: OutcomeState) -> None:
        row = json.dumps(
            {"operation_id": operation_id, "state": state.value},
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode() + b"\n"
        async with self._lock:
            await asyncio.to_thread(self._append_sync, row)

    async def get(self, operation_id: str) -> OutcomeState | None:
        async with self._lock:
            rows = await asyncio.to_thread(self._read_sync)
        for row in reversed(rows):
            if row.get("operation_id") == operation_id:
                return OutcomeState(row["state"])
        return None

    def _append_sync(self, row: bytes) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            view = memoryview(row)
            while view:
                view = view[os.write(descriptor, view) :]
            os.fsync(descriptor)
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read_sync(self) -> list[dict[str, str]]:
        if not self._path.exists():
            return []
        with self._path.open("rb") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                return [json.loads(line) for line in handle if line.strip()]
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
