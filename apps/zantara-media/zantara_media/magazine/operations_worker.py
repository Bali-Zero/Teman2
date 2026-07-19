"""Pro-side executor for closed Bali Zero Magazine operation intents."""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, cast

OperationKind = Literal[
    "rerun_collector",
    "rebuild_edition",
    "quarantine_story",
    "release_story",
    "refresh_research_job",
]
JournalPhase = Literal[
    "claimed",
    "safe_retry",
    "attested",
    "effect_started",
    "effect_completed",
    "receipt_acknowledged",
]

_KINDS = frozenset(
    {
        "rerun_collector",
        "rebuild_edition",
        "quarantine_story",
        "release_story",
        "refresh_research_job",
    }
)
_COLLECTORS = frozenset({"intel-lake", "mata-garuda", "regulatory-watcher", "notebooklm"})
_REASONS = {
    "rerun_collector": "collector_recovery",
    "rebuild_edition": "edition_recovery",
    "quarantine_story": "content_safety",
    "release_story": "gates_reverified",
    "refresh_research_job": "research_recovery",
}
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_-]{15,127}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_IDS = {
    "intent": re.compile(r"^ops-intent-[A-Za-z0-9-]{16,112}$"),
    "collector_run": re.compile(r"^collector-run-[a-z0-9][a-z0-9-]{15,79}$"),
    "edition": re.compile(r"^edition-[a-z0-9][a-z0-9-]{15,79}$"),
    "story": re.compile(r"^story-[a-z0-9][a-z0-9-]{15,79}$"),
    "research": re.compile(r"^research-job-[a-z0-9][a-z0-9-]{15,79}$"),
}
_PHASE_ORDER: dict[JournalPhase, int] = {
    "claimed": 0,
    "safe_retry": 1,
    "attested": 1,
    "effect_started": 2,
    "effect_completed": 3,
    "receipt_acknowledged": 4,
}


class OperationsWorkerError(ValueError):
    """Closed-contract, fencing, or journal invariant violation."""


class OperationsLeaseLostError(RuntimeError):
    """The current claim lost its lease or fencing authority."""


class OperationsTransport(Protocol):
    async def claim_operation_intent(
        self, *, worker_id: str, lease_seconds: int
    ) -> Mapping[str, Any] | None: ...

    async def start_operation_intent(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def heartbeat_operation_intent(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def attest_operation_intent(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def submit_operation_result(
        self, *, intent_id: str, result: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...


class OperationsDomainService(Protocol):
    async def prepare(self, kind: str, params: Mapping[str, Any]) -> None: ...

    async def execute(
        self,
        kind: str,
        params: Mapping[str, Any],
        *,
        target_key: str,
        fencing_token: int,
        target_fencing_token: int,
        effect_token: str,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class JournalRecord:
    intent_id: str
    request_hash: str
    target_key: str
    fencing_token: int
    phase: JournalPhase
    result: Mapping[str, Any] | None


class OperationsJournal:
    """SQLite action journal with monotonic fences and metadata-only payloads."""

    def __init__(self, path: Path) -> None:
        if not path.is_absolute() or path.is_symlink():
            raise OperationsWorkerError("invalid operations journal path")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._locks = path.with_suffix(path.suffix + ".locks")
        self._locks.mkdir(mode=0o700, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with contextlib.closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS operations_journal (
                      intent_id TEXT PRIMARY KEY,
                      request_hash TEXT NOT NULL,
                      target_key TEXT NOT NULL,
                      fencing_token INTEGER NOT NULL,
                      phase TEXT NOT NULL CHECK (phase IN ('claimed', 'safe_retry', 'attested', 'effect_started', 'effect_completed', 'receipt_acknowledged')),
                      result_json TEXT,
                      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS operations_target_fences (
                      target_key TEXT PRIMARY KEY,
                      target_fencing_token INTEGER NOT NULL CHECK (target_fencing_token > 0),
                      effect_token TEXT NOT NULL UNIQUE,
                      consumed_at TEXT NOT NULL
                    )
                    """
                )

    def _load_sync(self, intent_id: str) -> JournalRecord | None:
        with contextlib.closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT intent_id, request_hash, target_key, fencing_token, phase, result_json FROM operations_journal WHERE intent_id = ?",
                (intent_id,),
            ).fetchone()
        if row is None:
            return None
        result = json.loads(row[5]) if row[5] is not None else None
        return JournalRecord(
            intent_id=row[0],
            request_hash=row[1],
            target_key=row[2],
            fencing_token=row[3],
            phase=cast(JournalPhase, row[4]),
            result=cast(Mapping[str, Any] | None, result),
        )

    async def load(self, intent_id: str) -> JournalRecord | None:
        return await asyncio.to_thread(self._load_sync, intent_id)

    def _record_sync(
        self,
        *,
        intent_id: str,
        request_hash: str,
        target_key: str,
        fencing_token: int,
        phase: JournalPhase,
        result: Mapping[str, Any] | None,
    ) -> None:
        if _SHA256.fullmatch(request_hash) is None or fencing_token < 1:
            raise OperationsWorkerError("invalid journal binding")
        serialized = (
            None if result is None else json.dumps(result, sort_keys=True, separators=(",", ":"))
        )
        with contextlib.closing(self._connect()) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT request_hash, target_key, fencing_token, phase FROM operations_journal WHERE intent_id = ?",
                    (intent_id,),
                ).fetchone()
                if row is not None:
                    if row[0] != request_hash or row[1] != target_key:
                        raise OperationsWorkerError("journal binding conflict")
                    if fencing_token < row[2]:
                        raise OperationsWorkerError("stale fence")
                    old_phase = cast(JournalPhase, row[3])
                    if (
                        old_phase
                        in {
                            "effect_started",
                            "effect_completed",
                            "receipt_acknowledged",
                        }
                        and fencing_token > row[2]
                    ):
                        raise OperationsWorkerError("possible effect cannot be replayed")
                    if fencing_token == row[2] and _PHASE_ORDER[phase] < _PHASE_ORDER[old_phase]:
                        raise OperationsWorkerError("journal phase regression")
                connection.execute(
                    """
                    INSERT INTO operations_journal(intent_id, request_hash, target_key, fencing_token, phase, result_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(intent_id) DO UPDATE SET
                      fencing_token = excluded.fencing_token,
                      phase = excluded.phase,
                      result_json = excluded.result_json,
                      updated_at = CURRENT_TIMESTAMP
                    """,
                    (intent_id, request_hash, target_key, fencing_token, phase, serialized),
                )

    async def record(
        self,
        *,
        intent_id: str,
        request_hash: str,
        target_key: str,
        fencing_token: int,
        phase: JournalPhase,
        result: Mapping[str, Any] | None,
    ) -> None:
        await asyncio.to_thread(
            self._record_sync,
            intent_id=intent_id,
            request_hash=request_hash,
            target_key=target_key,
            fencing_token=fencing_token,
            phase=phase,
            result=result,
        )

    def _authorize_effect_sync(
        self,
        *,
        target_key: str,
        target_fencing_token: int,
        effect_token: str,
        expires_at: str,
        now: str,
    ) -> None:
        if (
            not target_key
            or target_fencing_token < 1
            or _TOKEN.fullmatch(effect_token) is None
            or _parse_iso(expires_at) <= _parse_iso(now)
        ):
            raise OperationsWorkerError("invalid effect attestation")
        with contextlib.closing(self._connect()) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT target_fencing_token, effect_token FROM operations_target_fences WHERE target_key = ?",
                    (target_key,),
                ).fetchone()
                if row is not None:
                    if target_fencing_token < row[0]:
                        raise OperationsWorkerError("stale target fence")
                    if target_fencing_token == row[0]:
                        raise OperationsWorkerError("effect authority replay")
                try:
                    connection.execute(
                        """
                        INSERT INTO operations_target_fences(target_key, target_fencing_token, effect_token, consumed_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(target_key) DO UPDATE SET
                          target_fencing_token = excluded.target_fencing_token,
                          effect_token = excluded.effect_token,
                          consumed_at = excluded.consumed_at
                        """,
                        (target_key, target_fencing_token, effect_token, now),
                    )
                except sqlite3.IntegrityError as exc:
                    raise OperationsWorkerError("effect authority replay") from exc

    async def authorize_effect(
        self,
        *,
        target_key: str,
        target_fencing_token: int,
        effect_token: str,
        expires_at: str,
        now: str,
    ) -> None:
        await asyncio.to_thread(
            self._authorize_effect_sync,
            target_key=target_key,
            target_fencing_token=target_fencing_token,
            effect_token=effect_token,
            expires_at=expires_at,
            now=now,
        )

    @asynccontextmanager
    async def target_lock(self, target_key: str):
        digest = hashlib.sha256(target_key.encode()).hexdigest()
        lock_path = self._locks / f"{digest}.lock"
        handle = await asyncio.to_thread(open, lock_path, "a+b")
        try:
            await asyncio.to_thread(fcntl.flock, handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            await asyncio.to_thread(fcntl.flock, handle.fileno(), fcntl.LOCK_UN)
            await asyncio.to_thread(handle.close)


def _exact(value: Mapping[str, Any], keys: set[str]) -> None:
    if set(value) != keys:
        raise OperationsWorkerError("invalid operation intent")


def _positive_int(value: Any, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise OperationsWorkerError("invalid operation intent")
    return value


def _identifier(value: Any, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise OperationsWorkerError("invalid operation intent")
    return value


def _parse_iso(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise OperationsWorkerError("invalid effect attestation") from exc
    if parsed.tzinfo is None:
        raise OperationsWorkerError("invalid effect attestation")
    return parsed.astimezone(UTC)


class OperationsWorker:
    """Execute a fixed handler map only after a fresh Sites authorization attestation."""

    def __init__(
        self,
        *,
        transport: OperationsTransport,
        domain: OperationsDomainService,
        journal: OperationsJournal,
        now: Callable[[], str],
        worker_id: str = "worker:pro-magazine",
        lease_seconds: int = 120,
        heartbeat_interval_seconds: float | None = None,
    ) -> None:
        self._transport = transport
        self._domain = domain
        self.journal = journal
        self._now = now
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._heartbeat_interval = heartbeat_interval_seconds or max(1.0, lease_seconds / 3)
        if self._heartbeat_interval <= 0:
            raise OperationsWorkerError("invalid heartbeat interval")

    @staticmethod
    def validate_intent(value: Mapping[str, Any]) -> Mapping[str, Any]:
        _exact(
            value,
            {
                "schema_version",
                "intent_id",
                "intent_kind",
                "params",
                "target_id",
                "target_key",
                "actor_key",
                "request_hash",
                "reason_code",
                "status",
                "claim_token",
                "fencing_token",
                "target_fencing_token",
                "lease_deadline",
                "attempt_count",
            },
        )
        kind = value.get("intent_kind")
        params = value.get("params")
        if (
            value.get("schema_version") != "ops-claim-result.v1"
            or kind not in _KINDS
            or not isinstance(params, Mapping)
            or value.get("reason_code") != _REASONS.get(cast(str, kind))
            or value.get("status") != "claimed"
            or _IDS["intent"].fullmatch(cast(str, value.get("intent_id", ""))) is None
            or _SHA256.fullmatch(cast(str, value.get("request_hash", ""))) is None
            or _SHA256.fullmatch(cast(str, value.get("actor_key", ""))) is None
            or _TOKEN.fullmatch(cast(str, value.get("claim_token", ""))) is None
        ):
            raise OperationsWorkerError("invalid operation intent")
        _positive_int(value.get("fencing_token"))
        _positive_int(value.get("target_fencing_token"))
        _positive_int(value.get("attempt_count"))
        if kind == "rerun_collector":
            _exact(params, {"collector_id", "failed_run_id"})
            if params.get("collector_id") not in _COLLECTORS:
                raise OperationsWorkerError("invalid operation intent")
            target = _identifier(params.get("failed_run_id"), _IDS["collector_run"])
        elif kind == "rebuild_edition":
            _exact(params, {"edition_id", "expected_revision"})
            target = _identifier(params.get("edition_id"), _IDS["edition"])
            _positive_int(params.get("expected_revision"), allow_zero=True)
        elif kind in {"quarantine_story", "release_story"}:
            _exact(params, {"story_id", "story_version", "expected_visibility_seq"})
            target = _identifier(params.get("story_id"), _IDS["story"])
            _positive_int(params.get("story_version"))
            _positive_int(params.get("expected_visibility_seq"), allow_zero=True)
        else:
            _exact(params, {"research_job_id"})
            target = _identifier(params.get("research_job_id"), _IDS["research"])
        if value.get("target_id") != target:
            raise OperationsWorkerError("invalid operation intent")
        expected_target_key = {
            "rerun_collector": "collector",
            "rebuild_edition": "edition",
            "quarantine_story": "story",
            "release_story": "story",
            "refresh_research_job": "research",
        }[cast(str, kind)]
        if value.get("target_key") != f"{expected_target_key}:{target}":
            raise OperationsWorkerError("invalid operation intent")
        return value

    async def _heartbeat(self, intent: Mapping[str, Any]) -> None:
        await self._transport.heartbeat_operation_intent(
            intent_id=intent["intent_id"],
            claim_token=intent["claim_token"],
            fencing_token=intent["fencing_token"],
            lease_seconds=self._lease_seconds,
        )

    async def _heartbeat_loop(self, intent: Mapping[str, Any]) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            await self._heartbeat(intent)

    async def _run_with_heartbeat(self, intent: Mapping[str, Any], operation: Any) -> None:
        try:
            await self._heartbeat(intent)
        except Exception as exc:
            raise OperationsLeaseLostError("operations lease lost") from exc
        heartbeat = asyncio.create_task(self._heartbeat_loop(intent))
        effect = asyncio.create_task(operation())
        try:
            done, _ = await asyncio.wait({heartbeat, effect}, return_when=asyncio.FIRST_COMPLETED)
            if effect in done:
                await effect
                return
            effect.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await effect
            raise OperationsLeaseLostError("operations lease lost") from heartbeat.exception()
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat

    async def run_once(self) -> bool:
        claimed = await self._transport.claim_operation_intent(
            worker_id=self._worker_id, lease_seconds=self._lease_seconds
        )
        if claimed is None:
            return False
        intent = self.validate_intent(claimed)
        kind = cast(str, intent["intent_kind"])
        params = cast(Mapping[str, Any], intent["params"])
        target_key = cast(str, intent["target_key"])
        binding = {
            "intent_id": cast(str, intent["intent_id"]),
            "request_hash": cast(str, intent["request_hash"]),
            "target_key": target_key,
            "fencing_token": cast(int, intent["fencing_token"]),
        }
        await self.journal.record(**binding, phase="claimed", result=None)
        try:
            await self._domain.prepare(kind, params)
        except Exception:
            await self.journal.record(**binding, phase="safe_retry", result=None)
            return False

        async with self.journal.target_lock(target_key):
            await self._transport.start_operation_intent(
                intent_id=intent["intent_id"],
                claim_token=intent["claim_token"],
                fencing_token=intent["fencing_token"],
            )

            async def operation() -> None:
                attestation_response = await self._transport.attest_operation_intent(
                    intent_id=intent["intent_id"],
                    claim_token=intent["claim_token"],
                    fencing_token=intent["fencing_token"],
                )
                attestation = attestation_response.get("attestation")
                if not isinstance(attestation, Mapping):
                    raise OperationsLeaseLostError("invalid authorization attestation")
                if attestation.get("authorized") is not True:
                    return
                if set(attestation) != {
                    "schema_version",
                    "authorized",
                    "status",
                    "intent_id",
                    "request_hash",
                    "actor_key",
                    "target_id",
                    "target_key",
                    "fencing_token",
                    "target_fencing_token",
                    "policy_version",
                    "effect_token",
                    "attested_at",
                    "expires_at",
                }:
                    raise OperationsWorkerError("invalid effect attestation")
                effect_token = attestation.get("effect_token")
                policy_version = attestation.get("policy_version")
                expires_at = attestation.get("expires_at")
                if (
                    attestation.get("schema_version") != "ops-effect-attestation.v1"
                    or attestation.get("status") != "running"
                    or attestation.get("intent_id") != intent["intent_id"]
                    or attestation.get("request_hash") != intent["request_hash"]
                    or attestation.get("actor_key") != intent["actor_key"]
                    or attestation.get("target_id") != intent["target_id"]
                    or attestation.get("target_key") != intent["target_key"]
                    or attestation.get("fencing_token") != intent["fencing_token"]
                    or attestation.get("target_fencing_token") != intent["target_fencing_token"]
                    or not isinstance(effect_token, str)
                    or _TOKEN.fullmatch(effect_token) is None
                    or not isinstance(policy_version, str)
                    or not isinstance(expires_at, str)
                    or _parse_iso(expires_at) <= _parse_iso(self._now())
                ):
                    raise OperationsWorkerError("invalid effect attestation")
                await self.journal.record(**binding, phase="attested", result=None)
                await self.journal.authorize_effect(
                    target_key=target_key,
                    target_fencing_token=cast(int, intent["target_fencing_token"]),
                    effect_token=effect_token,
                    expires_at=expires_at,
                    now=self._now(),
                )
                await self.journal.record(**binding, phase="effect_started", result=None)
                try:
                    domain_receipt = await self._domain.execute(
                        kind,
                        params,
                        target_key=target_key,
                        fencing_token=cast(int, intent["fencing_token"]),
                        target_fencing_token=cast(int, intent["target_fencing_token"]),
                        effect_token=effect_token,
                    )
                    expected_receipt = {
                        "schema_version": "ops-domain-receipt.v1",
                        "code": "effect_acknowledged",
                        "intent_kind": kind,
                        "target_id": intent["target_id"],
                        "target_key": target_key,
                        "fencing_token": intent["fencing_token"],
                        "target_fencing_token": intent["target_fencing_token"],
                        "effect_token": effect_token,
                    }
                    if dict(domain_receipt) != expected_receipt:
                        raise RuntimeError("invalid domain receipt")
                    status = "succeeded"
                    receipt: Mapping[str, Any] | None = expected_receipt
                    failure = None
                except Exception:
                    status = "outcome_unknown"
                    receipt = None
                    failure = {"code": "outcome_ambiguous"}
                result = {
                    "schema_version": "ops-result.v1",
                    "intent_id": intent["intent_id"],
                    "request_hash": intent["request_hash"],
                    "status": status,
                    "completed_at": self._now(),
                    "receipt": receipt,
                    "failure": failure,
                    "claim_token": intent["claim_token"],
                    "fencing_token": intent["fencing_token"],
                    "target_fencing_token": intent["target_fencing_token"],
                    "actor_key": intent["actor_key"],
                    "target_key": intent["target_key"],
                    "target_id": intent["target_id"],
                    "effect_token": effect_token,
                    "attested_policy_version": policy_version,
                    "attestation_expires_at": expires_at,
                }
                await self.journal.record(**binding, phase="effect_completed", result=result)
                await self._transport.submit_operation_result(
                    intent_id=cast(str, intent["intent_id"]), result=result
                )
                await self.journal.record(**binding, phase="receipt_acknowledged", result=result)

            await self._run_with_heartbeat(intent, operation)
        return True
