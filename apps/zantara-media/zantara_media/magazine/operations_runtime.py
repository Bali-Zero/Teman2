"""Production composition root for the outbound-only Magazine operations worker."""

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

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


_KINDS = (
    "rerun_collector",
    "rebuild_edition",
    "quarantine_story",
    "release_story",
    "refresh_research_job",
)
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_-]{15,127}$")
_COLLECTORS = frozenset({"intel-lake", "mata-garuda", "regulatory-watcher", "notebooklm"})
_IDS = {
    "collector_run": re.compile(r"^collector-run-[a-z0-9][a-z0-9-]{15,79}$"),
    "edition": re.compile(r"^edition-[a-z0-9][a-z0-9-]{15,79}$"),
    "story": re.compile(r"^story-[a-z0-9][a-z0-9-]{15,79}$"),
    "research": re.compile(r"^research-job-[a-z0-9][a-z0-9-]{15,79}$"),
}
_COMMAND_TIMEOUT_SECONDS = 120

_COLLECTOR_LABELS = {
    "intel-lake": "com.balizero.intel-radar-daily-digest",
    "mata-garuda": "com.matagaruda.watcher.daily",
    "regulatory-watcher": "com.balizero.regulatory-watcher.daily",
    "notebooklm": "com.matagaruda.nlm-feeder-stream.hourly",
}
_EDITION_LABEL = "com.balizero.magazine.publisher"
_RESEARCH_LABEL = "com.balizero.magazine.research-worker"


def _revision(value: Any, *, allow_zero: bool = False) -> bool:
    minimum = 0 if allow_zero else 1
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _validated_params(kind: str, params: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(params)
    if kind == "rerun_collector":
        valid = (
            set(value) == {"collector_id", "failed_run_id"}
            and value.get("collector_id") in _COLLECTORS
            and isinstance(value.get("failed_run_id"), str)
            and _IDS["collector_run"].fullmatch(value["failed_run_id"]) is not None
        )
    elif kind == "rebuild_edition":
        valid = (
            set(value) == {"edition_id", "expected_revision"}
            and isinstance(value.get("edition_id"), str)
            and _IDS["edition"].fullmatch(value["edition_id"]) is not None
            and _revision(value.get("expected_revision"), allow_zero=True)
        )
    elif kind == "quarantine_story":
        valid = (
            set(value) == {"story_id", "story_version", "expected_visibility_seq"}
            and isinstance(value.get("story_id"), str)
            and _IDS["story"].fullmatch(value["story_id"]) is not None
            and _revision(value.get("story_version"))
            and _revision(value.get("expected_visibility_seq"), allow_zero=True)
        )
    elif kind == "release_story":
        valid = (
            set(value)
            == {
                "story_id",
                "story_version",
                "expected_visibility_seq",
                "release_attestation_id",
            }
            and isinstance(value.get("story_id"), str)
            and _IDS["story"].fullmatch(value["story_id"]) is not None
            and _revision(value.get("story_version"))
            and _revision(value.get("expected_visibility_seq"), allow_zero=True)
            and isinstance(value.get("release_attestation_id"), str)
            and re.fullmatch(
                r"release-attestation-[a-z0-9][a-z0-9-]{15,79}",
                value["release_attestation_id"],
            )
            is not None
        )
    elif kind == "refresh_research_job":
        valid = (
            set(value) == {"research_job_id"}
            and isinstance(value.get("research_job_id"), str)
            and _IDS["research"].fullmatch(value["research_job_id"]) is not None
        )
    else:
        valid = False
    if not valid:
        raise CapabilityUnavailableError("operation capability unavailable")
    return value


def _target_id(kind: str, params: Mapping[str, Any]) -> str:
    value = _validated_params(kind, params)
    field = {
        "rerun_collector": "failed_run_id",
        "rebuild_edition": "edition_id",
        "quarantine_story": "story_id",
        "release_story": "story_id",
        "refresh_research_job": "research_job_id",
    }[kind]
    return str(value[field])


class EffectTransport(Protocol):
    async def apply_operation_effect(self, effect: Mapping[str, Any]) -> Mapping[str, Any]: ...


class EffectRunner(Protocol):
    async def kickstart(self, label: str) -> None: ...


class LaunchdEffectRunner:
    """Kick only dispatcher-owned launchd labels; no request value reaches argv."""

    async def kickstart(self, label: str) -> None:
        if label not in {*_COLLECTOR_LABELS.values(), _EDITION_LABEL, _RESEARCH_LABEL}:
            raise CapabilityUnavailableError("operation capability unavailable")
        try:
            process = await asyncio.create_subprocess_exec(
                "/bin/launchctl",
                "kickstart",
                "-k",
                f"gui/{os.getuid()}/{label}",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            return_code = await asyncio.wait_for(process.wait(), timeout=_COMMAND_TIMEOUT_SECONDS)
        except (OSError, TimeoutError, asyncio.TimeoutError) as exc:
            raise CapabilityUnavailableError("operation capability unavailable") from exc
        if return_code != 0:
            raise CapabilityUnavailableError("operation capability unavailable")


class CodeOwnedOperationsDomainService:
    """Immutable dispatcher for the five reviewed operational effect boundaries."""

    def __init__(self, *, transport: EffectTransport, runner: EffectRunner | None) -> None:
        if runner is None or not hasattr(transport, "apply_operation_effect"):
            raise OperationsRuntimeConfigError("invalid operations capability map")
        self._transport = transport
        self._runner = runner

    async def prepare(self, kind: str, params: Mapping[str, Any]) -> None:
        if kind not in _KINDS:
            raise CapabilityUnavailableError("operation capability unavailable")
        _target_id(kind, params)

    async def execute(
        self,
        kind: str,
        params: Mapping[str, Any],
        *,
        target_key: str,
        fencing_token: int,
        target_fencing_token: int,
        effect_token: str,
    ) -> Mapping[str, Any]:
        if kind not in _KINDS:
            raise CapabilityUnavailableError("operation capability unavailable")
        safe_params = _validated_params(kind, params)
        target_id = _target_id(kind, safe_params)
        expected_prefix = {
            "rerun_collector": "collector",
            "rebuild_edition": "edition",
            "quarantine_story": "story",
            "release_story": "story",
            "refresh_research_job": "research",
        }[kind]
        if (
            target_key != f"{expected_prefix}:{target_id}"
            or fencing_token < 1
            or target_fencing_token < 1
            or _TOKEN.fullmatch(effect_token) is None
        ):
            raise CapabilityUnavailableError("operation capability unavailable")
        authority = {
            "schema_version": "ops-domain-effect.v1",
            "intent_kind": kind,
            "target_id": target_id,
            "target_key": target_key,
            "params": safe_params,
            "fencing_token": fencing_token,
            "target_fencing_token": target_fencing_token,
            "effect_token": effect_token,
        }
        if kind == "rerun_collector":
            await self._runner.kickstart(_COLLECTOR_LABELS[str(safe_params["collector_id"])])
            result: Mapping[str, Any] = self._receipt(authority)
        elif kind == "rebuild_edition":
            await self._runner.kickstart(_EDITION_LABEL)
            result = self._receipt(authority)
        elif kind == "refresh_research_job":
            await self._runner.kickstart(_RESEARCH_LABEL)
            result = self._receipt(authority)
        else:
            result = await self._transport.apply_operation_effect(authority)
        expected = self._receipt(authority)
        if dict(result) != expected:
            raise CapabilityUnavailableError("operation capability unavailable")
        return expected

    @staticmethod
    def _receipt(authority: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": "ops-domain-receipt.v1",
            "code": "effect_acknowledged",
            **{
                key: authority[key]
                for key in (
                    "intent_kind",
                    "target_id",
                    "target_key",
                    "fencing_token",
                    "target_fencing_token",
                    "effect_token",
                )
            },
        }


def build_operations_domain_service(
    *, transport: EffectTransport, runner: EffectRunner | None = None
) -> OperationsDomainService:
    """Build the immutable five-effect dispatcher; deployment cannot supply argv."""
    return CodeOwnedOperationsDomainService(
        transport=transport, runner=runner or LaunchdEffectRunner()
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
            domain=build_operations_domain_service(transport=transport),
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
