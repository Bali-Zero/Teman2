"""Durable, operation-bound outcome states for mutation reconciliation."""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import hashlib
from contextlib import asynccontextmanager
from enum import StrEnum
from pathlib import Path
from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict


class OutcomeState(StrEnum):
    pending = "pending"
    staged = "staged"
    completed = "completed"
    absent = "absent"
    unknown = "outcome_unknown"


class OutcomeUnknownError(RuntimeError):
    """Raised when remote state cannot be proven before a retry."""


class OutcomeBindingError(RuntimeError):
    """Raised when an operation id is reused for different request bytes."""


class OutcomeRecord(BaseModel):
    """Closed journal row binding a mutation identity to exact request bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["magazine-outcome.v1"] = "magazine-outcome.v1"
    operation_id: str
    path: str
    body_sha256: str
    state: OutcomeState
    response: dict[str, Any] | None


class ReconcileResult(BaseModel):
    """Server-side result for a previously attempted operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: OutcomeState
    response: dict[str, Any] | None = None


class OutcomeJournal(Protocol):
    def claim(self, operation_id: str) -> AsyncIterator[None]: ...

    async def record(self, record: OutcomeRecord) -> None: ...

    async def get(self, operation_id: str) -> OutcomeRecord | None: ...


class InMemoryOutcomeJournal:
    """Explicit test/development journal; production must use durable storage."""

    def __init__(self) -> None:
        self._records: dict[str, OutcomeRecord] = {}
        self._lock = asyncio.Lock()
        self._claim_locks: dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def claim(self, operation_id: str) -> AsyncIterator[None]:
        lock = self._claim_locks.setdefault(operation_id, asyncio.Lock())
        async with lock:
            yield

    async def record(self, record: OutcomeRecord) -> None:
        async with self._lock:
            previous = self._records.get(record.operation_id)
            _validate_binding(previous, record)
            self._records[record.operation_id] = record

    async def get(self, operation_id: str) -> OutcomeRecord | None:
        async with self._lock:
            return self._records.get(operation_id)


class DurableOutcomeJournal:
    """Strict append-only JSONL journal with cross-process locking and fsync."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()
        self._claim_locks: dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def claim(self, operation_id: str) -> AsyncIterator[None]:
        """Hold one operation lease across preflight, send and durable outcome write."""

        local = self._claim_locks.setdefault(operation_id, asyncio.Lock())
        async with local:
            lock_name = hashlib.sha256(operation_id.encode()).hexdigest() + ".lock"
            lock_path = self._path.parent / f"{self._path.name}.claims" / lock_name
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            try:
                await asyncio.to_thread(fcntl.flock, descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    async def record(self, record: OutcomeRecord) -> None:
        row = (
            json.dumps(
                record.model_dump(mode="json"),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
        async with self._lock:
            await asyncio.to_thread(self._append_sync, record, row)

    async def get(self, operation_id: str) -> OutcomeRecord | None:
        async with self._lock:
            rows = await asyncio.to_thread(self._read_sync)
        for row in reversed(rows):
            if row.operation_id == operation_id:
                return row
        return None

    def _append_sync(self, record: OutcomeRecord, row: bytes) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            existing = self._read_descriptor(descriptor)
            previous = next(
                (item for item in reversed(existing) if item.operation_id == record.operation_id),
                None,
            )
            _validate_binding(previous, record)
            os.lseek(descriptor, 0, os.SEEK_END)
            view = memoryview(row)
            while view:
                view = view[os.write(descriptor, view) :]
            os.fsync(descriptor)
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read_sync(self) -> list[OutcomeRecord]:
        if not self._path.exists():
            return []
        descriptor = os.open(self._path, os.O_RDONLY)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH)
            return self._read_descriptor(descriptor)
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @staticmethod
    def _read_descriptor(descriptor: int) -> list[OutcomeRecord]:
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 65_536):
            chunks.append(chunk)
        raw = b"".join(chunks)
        if not raw:
            return []
        if not raw.endswith(b"\n"):
            raise ValueError("truncated final record")
        rows: list[OutcomeRecord] = []
        for line in raw.splitlines():
            if not line:
                raise ValueError("blank journal record")
            rows.append(OutcomeRecord.model_validate_json(line))
        return rows


def _validate_binding(
    previous: OutcomeRecord | None, current: OutcomeRecord
) -> None:
    if previous is None:
        return
    if previous.path != current.path or previous.body_sha256 != current.body_sha256:
        raise OutcomeBindingError("operation binding mismatch")
