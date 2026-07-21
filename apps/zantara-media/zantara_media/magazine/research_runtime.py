"""Production composition root and outbound polling loop for Magazine research."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from zantara_media.magazine.reconciler import DurableOutcomeJournal
from zantara_media.magazine.research_adapters import (
    NotebookQueryClient,
    ResearchSourceUnavailableError,
    build_production_adapters,
)
from zantara_media.magazine.research_sources import load_research_source_registry
from zantara_media.magazine.research_worker import Clock, DlpGate, ResearchTransport, ResearchWorker
from zantara_media.magazine.transport import MagazineTransport, TransportConfig

logger = logging.getLogger(__name__)
_WORKER_ID = re.compile(r"^worker:[a-z0-9]+(?:-[a-z0-9]+)*$")


class ResearchRuntimeConfigError(RuntimeError):
    """A content-free startup error for fail-closed runtime configuration."""


class PollWorker(Protocol):
    async def run_once(self) -> bool: ...


Sleep = Callable[[float], Awaitable[None]]


class PollSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_backoff_seconds: float = Field(default=1.0, gt=0, le=60)
    max_backoff_seconds: float = Field(default=30.0, gt=0, le=300)

    def model_post_init(self, __context: Any) -> None:
        if self.max_backoff_seconds < self.min_backoff_seconds:
            raise ValueError("maximum poll backoff must not be below minimum")


class AsyncNlmClient:
    """Bounded async argv-only adapter for the authenticated Pro-local ``nlm`` CLI."""

    def __init__(
        self,
        *,
        binary: Path,
        timeout_seconds: int = 45,
        max_output_bytes: int = 64_000,
    ) -> None:
        if (
            not binary.is_absolute()
            or not binary.is_file()
            or not os.access(binary, os.X_OK)
            or not 1 <= timeout_seconds <= 300
            or not 256 <= max_output_bytes <= 1_000_000
        ):
            raise ResearchRuntimeConfigError("invalid NotebookLM runtime configuration")
        self._binary = binary
        self._timeout_seconds = timeout_seconds
        self._max_output_bytes = max_output_bytes

    async def query(self, notebook_ref: str, prompt: str) -> str:
        if (
            not notebook_ref
            or len(notebook_ref) > 256
            or any(character.isspace() for character in notebook_ref)
            or not prompt
            or len(prompt.encode()) > 16_000
        ):
            raise ResearchSourceUnavailableError("notebook source unavailable")
        process: asyncio.subprocess.Process | None = None
        try:
            process = await asyncio.create_subprocess_exec(
                str(self._binary),
                "query",
                "notebook",
                notebook_ref,
                prompt,
                "--timeout",
                str(self._timeout_seconds),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                limit=self._max_output_bytes + 1,
            )
            if process.stdout is None:
                raise RuntimeError("missing subprocess output stream")
            body = await asyncio.wait_for(
                self._read_bounded(process), timeout=self._timeout_seconds + 2
            )
            if process.returncode != 0:
                raise RuntimeError("NotebookLM command failed")
            wrapper = json.loads(body)
            value = wrapper.get("value", wrapper) if isinstance(wrapper, dict) else None
            answer = value.get("answer") if isinstance(value, dict) else None
            if not isinstance(answer, str) or not answer:
                raise ValueError("NotebookLM response has no answer")
            return answer
        except asyncio.CancelledError:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            raise
        except Exception as exc:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            raise ResearchSourceUnavailableError("notebook source unavailable") from exc

    async def _read_bounded(self, process: asyncio.subprocess.Process) -> bytes:
        if process.stdout is None:
            raise RuntimeError("missing subprocess output stream")
        body = bytearray()
        while True:
            remaining = self._max_output_bytes - len(body)
            chunk = await process.stdout.read(min(65_536, remaining + 1))
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > self._max_output_bytes:
                raise ValueError("NotebookLM response exceeds output limit")
        await process.wait()
        return bytes(body)


@dataclass(slots=True)
class ResearchRuntime:
    worker: ResearchWorker
    _owned_transport: MagazineTransport | None = None

    async def aclose(self) -> None:
        if self._owned_transport is not None:
            await self._owned_transport.aclose()


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value is None or not value.strip():
        raise ResearchRuntimeConfigError("missing research runtime configuration")
    return value


def _integer(env: Mapping[str, str], name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ResearchRuntimeConfigError("invalid research runtime configuration") from exc
    if not minimum <= value <= maximum:
        raise ResearchRuntimeConfigError("invalid research runtime configuration")
    return value


def _default_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _journal_path(env: Mapping[str, str]) -> Path:
    path = Path(_required(env, "MAGAZINE_RESEARCH_OUTCOME_JOURNAL"))
    if not path.is_absolute() or path.is_symlink():
        raise ResearchRuntimeConfigError("invalid research transport configuration")
    return path


def _worker_id(env: Mapping[str, str]) -> str:
    value = env.get("MAGAZINE_RESEARCH_WORKER_ID", "worker:pro-magazine")
    if _WORKER_ID.fullmatch(value) is None:
        raise ResearchRuntimeConfigError("invalid research runtime configuration")
    return value


def create_research_runtime(
    *,
    env: Mapping[str, str] | None = None,
    transport: ResearchTransport | None = None,
    nlm_client: NotebookQueryClient | None = None,
    dlp_gate: DlpGate | None = None,
    now: Clock = _default_now,
) -> ResearchRuntime:
    """Build all four production adapters and, unless injected, the signed transport."""

    environment = dict(os.environ if env is None else env)
    try:
        registry = load_research_source_registry(
            Path(_required(environment, "MAGAZINE_RESEARCH_SOURCE_CONFIG"))
        )
    except ResearchRuntimeConfigError:
        raise
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        raise ResearchRuntimeConfigError("invalid research source configuration") from exc

    notebook_client = nlm_client
    if notebook_client is None:
        notebook_client = AsyncNlmClient(
            binary=Path(_required(environment, "MAGAZINE_RESEARCH_NLM_BIN")),
            timeout_seconds=_integer(
                environment,
                "MAGAZINE_RESEARCH_NLM_TIMEOUT_SECONDS",
                45,
                minimum=1,
                maximum=300,
            ),
            max_output_bytes=_integer(
                environment,
                "MAGAZINE_RESEARCH_NLM_MAX_OUTPUT_BYTES",
                64_000,
                minimum=256,
                maximum=1_000_000,
            ),
        )

    owned_transport: MagazineTransport | None = None
    worker_transport = transport
    if worker_transport is None:
        try:
            config = TransportConfig(
                base_url=_required(environment, "MAGAZINE_BASE_URL"),
                siwc_bearer_token=_required(environment, "MAGAZINE_SIWC_BEARER_TOKEN"),
                hmac_key_id=_required(environment, "MAGAZINE_HMAC_KEY_ID"),
                hmac_secret=_required(environment, "MAGAZINE_HMAC_SECRET"),
                audience=_required(environment, "MAGAZINE_HMAC_AUDIENCE"),
            )
            owned_transport = MagazineTransport(
                config,
                journal=DurableOutcomeJournal(_journal_path(environment)),
            )
            worker_transport = owned_transport
        except ResearchRuntimeConfigError:
            raise
        except (ValueError, ValidationError) as exc:
            raise ResearchRuntimeConfigError("invalid research transport configuration") from exc

    lease_seconds = _integer(
        environment,
        "MAGAZINE_RESEARCH_LEASE_SECONDS",
        120,
        minimum=30,
        maximum=900,
    )
    heartbeat_seconds = _integer(
        environment,
        "MAGAZINE_RESEARCH_HEARTBEAT_SECONDS",
        max(1, lease_seconds // 3),
        minimum=1,
        maximum=max(1, lease_seconds - 1),
    )
    worker_kwargs: dict[str, Any] = {
        "transport": worker_transport,
        "adapters": build_production_adapters(registry=registry, nlm_client=notebook_client),
        "now": now,
        "worker_id": _worker_id(environment),
        "lease_seconds": lease_seconds,
        "heartbeat_interval_seconds": float(heartbeat_seconds),
    }
    if dlp_gate is not None:
        worker_kwargs["dlp_gate"] = dlp_gate
    return ResearchRuntime(
        worker=ResearchWorker(**worker_kwargs),
        _owned_transport=owned_transport,
    )


async def run_poll_loop(
    worker: PollWorker,
    *,
    settings: PollSettings | None = None,
    stop_event: asyncio.Event | None = None,
    sleep: Sleep = asyncio.sleep,
    max_cycles: int | None = None,
) -> None:
    """Poll outbound with deterministic bounded backoff and graceful cancellation."""

    policy = settings or PollSettings()
    if max_cycles is not None and max_cycles < 1:
        raise ValueError("max_cycles must be positive")
    delay = policy.min_backoff_seconds
    cycles = 0
    while stop_event is None or not stop_event.is_set():
        if max_cycles is not None and cycles >= max_cycles:
            return
        try:
            claimed = await worker.run_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("magazine research poll cycle failed")
            claimed = False
        cycles += 1
        if claimed:
            delay = policy.min_backoff_seconds
        current_delay = delay
        if not claimed:
            delay = min(policy.max_backoff_seconds, delay * 2)
        if stop_event is not None and stop_event.is_set():
            return
        await sleep(current_delay)
