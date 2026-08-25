"""BackendClient — the ONE persistent httpx.AsyncClient every tool
executor shares to reach the Fly backend.

RECON (docs/plans/2026-08-25-due-bot-live/RECON-domains-2-4.md, domain 4):
"Reuse the internal REST endpoints directly ... The team bot is a local
process already calling that backend, so routing through MCP adds a
process and transport hop and inherits a ``@require_role`` model built
for Claude-desktop conventions rather than F5's typed-tool contract." This
class is that direct path: a thin, dependency-minimal (only ``httpx`` —
see ``../../pyproject.toml``) HTTP transport, nothing else.

CLAUDE.md Golden Rule 10: "Async HTTP Clients — NEVER httpx.AsyncClient()
in methods/loops. Persistent _get_client, close in lifespan." This app has
no FastAPI lifespan yet (the webhook/runtime unit is a separate B3 piece,
not built here), so there is nothing to hook a lifespan callback into
today — but the class itself is built so that mistake cannot happen from
the inside: exactly one ``httpx.AsyncClient`` is created in ``__init__``
and reused for every call this instance ever makes; there is no per-call
client construction anywhere in this module. Whichever unit eventually
owns the running app's startup/shutdown is responsible for constructing
ONE ``BackendClient`` and calling ``aclose()`` at shutdown (or using it as
an async context manager, which this class also supports).

This module deliberately stops at the TRANSPORT layer: it returns a
``BackendCallResult`` (status code + parsed JSON body, or a network-layer
failure tag) and does not know about ``ToolResult``, ``ExecutorErrorCode``,
or any tool's specific response shape. Mapping a raw HTTP outcome into the
closed error vocabulary is ``response_mapping.py``'s job, one layer up —
kept separate so that mapping logic serves every future tool the same
way, rather than being re-derived per call site.

Author: Claude Sonnet 5 (lane B9 — team-bot executor seam)
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType

import httpx

logger = logging.getLogger(__name__)

__all__ = [
    "BACKEND_BASE_URL_ENV_VAR",
    "DEFAULT_CONNECT_TIMEOUT_S",
    "DEFAULT_READ_TIMEOUT_S",
    "BackendCallResult",
    "BackendClient",
    "BackendClientConfig",
]

BACKEND_BASE_URL_ENV_VAR = "TEAM_BOT_BACKEND_BASE_URL"

# Deliberately short: an interactive WhatsApp reply is waiting on this call
# (F4: the team bot answers a staff member in a live chat), and MANDATE.md
# F11 names p95 latency as a first-class tripwire metric — a slow backend
# should surface as UPSTREAM_TIMEOUT quickly, not hang the whole turn.
DEFAULT_CONNECT_TIMEOUT_S = 3.0
DEFAULT_READ_TIMEOUT_S = 8.0


@dataclass(frozen=True)
class BackendClientConfig:
    """Where the backend lives and how patient this process is with it.

    No hardcoded default for ``base_url`` on purpose (CLAUDE.md §8 rule 6,
    "No Hardcoded Secrets — env vars", applied here to the equally
    environment-specific question of WHICH backend this process talks to
    — Mini/Pro/staging/production are different hosts, and a wrong silent
    default is worse than a loud startup failure). ``from_env`` is the
    only way to get a config with no ``base_url`` argument supplied, and
    it raises if the required env var is unset or empty.
    """

    base_url: str
    connect_timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S
    read_timeout_s: float = DEFAULT_READ_TIMEOUT_S

    @classmethod
    def from_env(cls) -> BackendClientConfig:
        base_url = os.getenv(BACKEND_BASE_URL_ENV_VAR, "").strip()
        if not base_url:
            raise RuntimeError(
                f"{BACKEND_BASE_URL_ENV_VAR} is unset or empty — refusing to construct a "
                "BackendClient with no known backend host. Set it explicitly (Mini/Pro/staging/"
                "production each have a different value); there is no safe default to fall back to."
            )
        return cls(base_url=base_url)


@dataclass(frozen=True)
class BackendCallResult:
    """The raw outcome of one HTTP round trip. Exactly one of three shapes:

    - a real HTTP response: ``status_code`` set, ``json_body`` set to the
      parsed body (or ``None`` if the body was empty or not valid JSON —
      ``response_mapping.py`` treats an empty/non-JSON 200 as
      ``INVALID_RESPONSE``, never as success), ``network_error`` ``None``.
    - a timeout: ``status_code``/``json_body`` ``None``,
      ``network_error="timeout"``.
    - any other network-layer failure (DNS, connection refused, TLS,
      protocol error): ``status_code``/``json_body`` ``None``,
      ``network_error="network_error"``.

    Deliberately NOT ``ToolResult`` — this is the transport-layer shape,
    one layer below the closed error vocabulary.
    """

    status_code: int | None
    json_body: object | None
    network_error: str | None


class BackendClient:
    """One shared ``httpx.AsyncClient`` per instance. Construct once, reuse
    for every call, ``aclose()`` (or use as an ``async with`` block) at
    shutdown.

    ``transport`` is the ONE seam this class exposes for tests: pass an
    ``httpx.MockTransport`` to fake the network at the HTTP boundary
    (never touching a real socket — this repo's B6 law that no test may
    reach a real network), while every line of THIS class's own request/
    response handling still runs for real. Left ``None`` in production,
    where ``httpx`` picks its normal transport.
    """

    def __init__(self, config: BackendClientConfig, *, transport: httpx.BaseTransport | None = None) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=httpx.Timeout(
                connect=config.connect_timeout_s,
                read=config.read_timeout_s,
                write=config.read_timeout_s,
                pool=config.connect_timeout_s,
            ),
            transport=transport,
            follow_redirects=False,
        )

    async def get(self, path: str, *, headers: Mapping[str, str] | None = None) -> BackendCallResult:
        """Issue one GET. Never raises — every ``httpx`` exception this
        library can throw for a well-formed request is caught here and
        turned into a ``BackendCallResult`` with ``network_error`` set, so
        callers (``tool_executor.py``) never need a bare ``try/except``
        around a network call themselves."""
        try:
            response = await self._client.get(path, headers=dict(headers or {}))
        except httpx.TimeoutException:
            logger.warning("team_bot.executor.http_client: timeout calling GET %s", path)
            return BackendCallResult(status_code=None, json_body=None, network_error="timeout")
        except httpx.HTTPError as exc:
            # Exception TYPE name only — never the exception's own message,
            # which for some httpx errors can echo back request details.
            # Never PII either way (this transport carries no client name/
            # phone/passport data), but keeping the log line minimal is the
            # cheaper discipline to hold uniformly across every future tool.
            logger.warning(
                "team_bot.executor.http_client: network error (%s) calling GET %s",
                type(exc).__name__,
                path,
            )
            return BackendCallResult(status_code=None, json_body=None, network_error="network_error")

        body: object | None
        if not response.content:
            body = None
        else:
            try:
                body = response.json()
            except ValueError:
                body = None
        return BackendCallResult(status_code=response.status_code, json_body=body, network_error=None)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> BackendClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
