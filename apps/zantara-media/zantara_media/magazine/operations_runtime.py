"""Production composition root for the outbound-only Magazine operations worker."""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Awaitable, Callable, Mapping
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
_MAX_CONFIG_BYTES = 32 * 1024
_MAX_COMMAND_INPUT_BYTES = 8 * 1024
_MAX_COMMAND_OUTPUT_BYTES = 8 * 1024
_COMMAND_TIMEOUT_SECONDS = 120

CapabilityHandler = Callable[..., Awaitable[str]]


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
    elif kind in {"quarantine_story", "release_story"}:
        valid = (
            set(value) == {"story_id", "story_version", "expected_visibility_seq"}
            and isinstance(value.get("story_id"), str)
            and _IDS["story"].fullmatch(value["story_id"]) is not None
            and _revision(value.get("story_version"))
            and _revision(value.get("expected_visibility_seq"), allow_zero=True)
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


def _safe_command_environment() -> dict[str, str]:
    environment = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
    }
    for name in ("HOME", "TMPDIR", "TZ"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    environment.update(
        {
            name: value
            for name, value in os.environ.items()
            if name.startswith("MAGAZINE_CAPABILITY_")
        }
    )
    return environment


class FixedJsonCommand:
    """A preconfigured argv adapter with bounded JSON stdin/stdout and no shell."""

    def __init__(self, *, kind: str, argv: tuple[str, ...]) -> None:
        self._kind = kind
        self._argv = argv

    async def __call__(
        self,
        params: Mapping[str, Any],
        *,
        fencing_token: int,
        target_fencing_token: int,
        effect_token: str,
    ) -> str:
        if fencing_token < 1 or target_fencing_token < 1 or _TOKEN.fullmatch(effect_token) is None:
            raise CapabilityUnavailableError("operation capability unavailable")
        safe_params = _validated_params(self._kind, params)
        target_id = _target_id(self._kind, safe_params)
        payload = json.dumps(
            {
                "schema_version": "ops-domain-command.v1",
                "intent_kind": self._kind,
                "target_id": target_id,
                "params": safe_params,
                "authority": {
                    "fencing_token": fencing_token,
                    "target_fencing_token": target_fencing_token,
                    "effect_token": effect_token,
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        if len(payload) > _MAX_COMMAND_INPUT_BYTES:
            raise CapabilityUnavailableError("operation capability unavailable")

        try:
            process = await asyncio.create_subprocess_exec(
                *self._argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=_safe_command_environment(),
            )
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write(payload)
            await process.stdin.drain()
            process.stdin.close()
            output = await asyncio.wait_for(
                process.stdout.read(_MAX_COMMAND_OUTPUT_BYTES + 1),
                timeout=_COMMAND_TIMEOUT_SECONDS,
            )
            return_code = await asyncio.wait_for(process.wait(), timeout=_COMMAND_TIMEOUT_SECONDS)
        except (OSError, TimeoutError, asyncio.TimeoutError) as exc:
            if "process" in locals() and process.returncode is None:
                process.kill()
                await process.wait()
            raise CapabilityUnavailableError("operation capability unavailable") from exc

        if return_code != 0 or len(output) > _MAX_COMMAND_OUTPUT_BYTES:
            raise CapabilityUnavailableError("operation capability unavailable")
        try:
            receipt = json.loads(output)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CapabilityUnavailableError("operation capability unavailable") from exc
        if (
            not isinstance(receipt, dict)
            or set(receipt) != {"schema_version", "code", "target_id"}
            or receipt.get("schema_version") != "ops-domain-receipt.v1"
            or receipt.get("code") != "effect_acknowledged"
            or receipt.get("target_id") != target_id
        ):
            raise CapabilityUnavailableError("operation capability unavailable")
        return "effect_acknowledged"


class FixedOperationsDomainService:
    """Fixed five-handler map; it cannot dispatch shell, paths, or URLs."""

    def __init__(self, handlers: Mapping[str, CapabilityHandler]) -> None:
        if set(handlers) != set(_KINDS) or any(not callable(item) for item in handlers.values()):
            raise OperationsRuntimeConfigError("invalid operations capability map")
        self._handlers = dict(handlers)

    async def prepare(self, kind: str, params: Mapping[str, Any]) -> None:
        if kind not in self._handlers:
            raise CapabilityUnavailableError("operation capability unavailable")
        _target_id(kind, params)

    async def execute(
        self,
        kind: str,
        params: Mapping[str, Any],
        *,
        fencing_token: int,
        target_fencing_token: int,
        effect_token: str,
    ) -> str:
        handler = self._handlers.get(kind)
        if handler is None:
            raise CapabilityUnavailableError("operation capability unavailable")
        result = await handler(
            params,
            fencing_token=fencing_token,
            target_fencing_token=target_fencing_token,
            effect_token=effect_token,
        )
        if result != "effect_acknowledged":
            raise CapabilityUnavailableError("operation capability unavailable")
        return result


def _parse_capability_map(raw: str | None) -> dict[str, tuple[str, ...]]:
    if raw is None or not raw.strip() or len(raw.encode()) > _MAX_CONFIG_BYTES:
        raise OperationsRuntimeConfigError("invalid operations capability map")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OperationsRuntimeConfigError("invalid operations capability map") from exc
    if not isinstance(value, dict) or set(value) != set(_KINDS):
        raise OperationsRuntimeConfigError("invalid operations capability map")
    parsed: dict[str, tuple[str, ...]] = {}
    for kind in _KINDS:
        argv = value.get(kind)
        if (
            not isinstance(argv, list)
            or not 1 <= len(argv) <= 16
            or any(not isinstance(item, str) or not item or len(item) > 1024 for item in argv)
        ):
            raise OperationsRuntimeConfigError("invalid operations capability map")
        executable = Path(argv[0])
        if (
            not executable.is_absolute()
            or not executable.is_file()
            or not os.access(executable, os.X_OK)
        ):
            raise OperationsRuntimeConfigError("invalid operations capability map")
        parsed[kind] = tuple(argv)
    return parsed


def build_operations_domain_service(capabilities_json: str | None) -> OperationsDomainService:
    """Build the closed five-capability map from preconfigured executable argv values."""
    commands = _parse_capability_map(capabilities_json)
    return FixedOperationsDomainService(
        {kind: FixedJsonCommand(kind=kind, argv=commands[kind]) for kind in _KINDS}
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
            domain=build_operations_domain_service(
                _required(environment, "MAGAZINE_OPERATIONS_CAPABILITIES_JSON")
            ),
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
