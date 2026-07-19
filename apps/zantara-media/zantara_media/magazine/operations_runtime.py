"""Production composition root for the outbound-only Magazine operations worker."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from zantara_media.magazine.operations_worker import (
    OperationsDomainService,
    OperationsJournal,
    OperationsWorker,
)
from zantara_media.magazine.reconciler import DurableOutcomeJournal
from zantara_media.magazine.transport import MagazineTransport, TransportConfig


class OperationsRuntimeConfigError(RuntimeError):
    """A content-free fail-closed operations runtime error."""


class CapabilityUnavailableError(RuntimeError):
    """A required, explicitly wired local capability is unavailable."""


class FixedOperationsDomainService:
    """Fixed five-handler map; it cannot dispatch shell, paths, or URLs."""

    def __init__(self, handlers: Mapping[str, Any]) -> None:
        expected = {
            "rerun_collector",
            "rebuild_edition",
            "quarantine_story",
            "release_story",
            "refresh_research_job",
        }
        if set(handlers) != expected or any(not callable(item) for item in handlers.values()):
            raise OperationsRuntimeConfigError("invalid operations capability map")
        self._handlers = dict(handlers)

    async def prepare(self, kind: str, params: Mapping[str, Any]) -> None:
        del params
        if kind not in self._handlers or self._handlers[kind] is _unavailable:
            raise CapabilityUnavailableError("operation capability unavailable")

    async def execute(self, kind: str, params: Mapping[str, Any], *, fencing_token: int) -> str:
        handler = self._handlers.get(kind)
        if handler is None:
            raise CapabilityUnavailableError("operation capability unavailable")
        result = await handler(params, fencing_token=fencing_token)
        if result != "effect_acknowledged":
            raise CapabilityUnavailableError("operation capability unavailable")
        return result


async def _unavailable(_params: Mapping[str, Any], *, fencing_token: int) -> str:
    del fencing_token
    raise CapabilityUnavailableError("operation capability unavailable")


def build_operations_domain_service() -> OperationsDomainService:
    """Return the audited production map; absent capabilities fail closed."""
    return FixedOperationsDomainService(
        {
            "rerun_collector": _unavailable,
            "rebuild_edition": _unavailable,
            "quarantine_story": _unavailable,
            "release_story": _unavailable,
            "refresh_research_job": _unavailable,
        }
    )


@dataclass(slots=True)
class OperationsRuntime:
    worker: OperationsWorker
    transport: MagazineTransport

    async def aclose(self) -> None:
        await self.transport.aclose()


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value is None or not value.strip():
        raise OperationsRuntimeConfigError("missing operations runtime configuration")
    return value


def _path(env: Mapping[str, str], name: str) -> Path:
    value = Path(_required(env, name))
    if not value.is_absolute() or value.is_symlink():
        raise OperationsRuntimeConfigError("invalid operations runtime configuration")
    return value


def _integer(env: Mapping[str, str], name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(env.get(name, str(default)))
    except ValueError as exc:
        raise OperationsRuntimeConfigError("invalid operations runtime configuration") from exc
    if not minimum <= value <= maximum:
        raise OperationsRuntimeConfigError("invalid operations runtime configuration")
    return value


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def create_operations_runtime(*, env: Mapping[str, str] | None = None) -> OperationsRuntime:
    environment = dict(os.environ if env is None else env)
    try:
        config = TransportConfig(
            base_url=_required(environment, "MAGAZINE_BASE_URL"),
            siwc_bearer_token=_required(environment, "MAGAZINE_SIWC_BEARER_TOKEN"),
            hmac_key_id=_required(environment, "MAGAZINE_HMAC_KEY_ID"),
            hmac_secret=_required(environment, "MAGAZINE_HMAC_SECRET"),
            audience=_required(environment, "MAGAZINE_HMAC_AUDIENCE"),
        )
        transport = MagazineTransport(
            config,
            journal=DurableOutcomeJournal(
                _path(environment, "MAGAZINE_OPERATIONS_OUTCOME_JOURNAL")
            ),
        )
        lease_seconds = _integer(environment, "MAGAZINE_OPERATIONS_LEASE_SECONDS", 120, 30, 300)
        worker = OperationsWorker(
            transport=transport,
            domain=build_operations_domain_service(),
            journal=OperationsJournal(_path(environment, "MAGAZINE_OPERATIONS_ACTION_JOURNAL")),
            now=_now,
            worker_id=environment.get("MAGAZINE_OPERATIONS_WORKER_ID", "worker:pro-magazine"),
            lease_seconds=lease_seconds,
            heartbeat_interval_seconds=_integer(
                environment,
                "MAGAZINE_OPERATIONS_HEARTBEAT_SECONDS",
                max(1, lease_seconds // 3),
                1,
                100,
            ),
        )
    except OperationsRuntimeConfigError:
        raise
    except (ValueError, ValidationError) as exc:
        raise OperationsRuntimeConfigError("invalid operations runtime configuration") from exc
    return OperationsRuntime(worker=worker, transport=transport)
