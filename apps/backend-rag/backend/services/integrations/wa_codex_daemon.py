"""WA codex broker daemon — the Pro-side leg of the BOT-V4 S2 broker.

Runs on Pro as the dedicated login-less user ``zantara-codex`` (spec §4.1,
`research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md`), under
a launchd LaunchDAEMON (`UserName` demotion — a LaunchAgent for a user who
never logs in never runs) whose wrapper exec's THIS module as the real
blocking payload (scar family #7: ``KeepAlive.SuccessfulExit=false`` and the
payload never exits on its own, so launchd never restart-storms).

Single-flight by design (spec §2.1, ``MAX_DEPTH=1`` server-side): one claim,
one exec, one completion, then the next poll. Every ``POST /claim`` — job or
no job — IS the daemon's liveness heartbeat: the server upserts its broker
gauge on each poll, and a daemon that stops polling converges to
``BROKER_ABSENT`` server-side with zero daemon-side cooperation. That is
also why the version-pin pause below deliberately stops CLAIMING rather
than inventing a separate "paused" signal: no polls → stale gauge → the
server-side breaker opens (chaos row 8's convergence path).

Binding invariants:

1.  **The broker key lives in the env only** (``WA_BROKER_KEY``), is sent
    only as the ``X-API-Key`` header on the persistent HTTP client, and is
    never placed on argv, never logged, never echoed into an error message
    (scar family #4; W115 argv lesson).
2.  **No client text in logs or spool** (PII boundary, SYMBIOSIS Law 2):
    this module logs job ids (UUIDs), typed outcome words, durations and
    HTTP statuses — never the package wire, never the model's answer.
3.  **The exec budget comes from SERVER fields only** (chaos row 6):
    ``budget = (deadline_at - server_now) - net_margin`` computed once per
    claim from the claim response's own two timestamps, then counted down
    on ``time.monotonic()``. Pro's wall clock is never consulted — a Pro
    clock skewed by hours changes nothing.
4.  **The CLI version is pinned** (chaos row 8): ``WA_CODEX_CLI_VERSION_PIN``
    is mandatory; a mismatch at startup refuses to start, a mismatch
    discovered mid-run stops claiming (state-change logged once) while the
    loop stays alive re-checking — an operator updating the pin file and
    restarting, or the binary reverting, resumes claiming without manual
    intervention beyond the restart.
5.  **Completion is idempotent by key** (chaos row 3): ``completion_key``
    is minted once per exec attempt (``uuid4().hex``); a lost HTTP response
    is retried with the SAME key, and the server answers ``replay`` — never
    a double-send. ``409`` is a protocol violation (logged ERROR, no
    retry); ``410`` means the lease expired server-side and the job's fold
    already happened there (move on).

Deliberately NOT here (declared non-goals, PR-6): ``policy_refusal``
production (S1.5 classifier lane), the seat-sentinel cron's full
implementation, and any execution of the provisioning steps themselves —
`scripts/provision_zantara_codex.sh` prepares the host, the operator runs
the one-time ``codex login`` (spec §Solo-operatore).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import signal
import time
import uuid
from dataclasses import dataclass
from datetime import datetime

import httpx

from backend.llm.codex_exec_client import (
    _ALLOWED_MODELS,
    MODEL_TERRA,
    CodexExecAuthError,
    CodexExecClient,
    CodexExecCommunicationError,
    CodexExecOutputShapeError,
    CodexExecProcessError,
    CodexExecQuotaError,
    CodexExecTimeoutError,
    CodexExecUnavailableError,
)

logger = logging.getLogger(__name__)

# Server-side transport bounds, BOTH enforced HERE before posting (a breach
# is reported as error_class="oversized_output", never truncated-and-sent —
# a silently truncated answer is a corrupt answer wearing the success shape):
#
# 1. `_RESULT_TEXT_MAX` mirrors the router's Pydantic `max_length=65536`,
#    which counts CHARACTERS.
# 2. `_RESULT_BYTES_MAX` guards the router's SEPARATE stream cap
#    `_MAX_BODY_BYTES = 128 KiB`, which counts JSON-ENCODED BYTES — a
#    60,000-char answer of 3-byte UTF-8 characters passes the char cap and
#    still encodes to ~180 KB (measured, Kimi round-1 F1), which the router
#    413s and the daemon's 4xx-never-retry branch would then abandon
#    untyped. The pre-check measures with EXACTLY the encoding `_complete`
#    sends (see `_encode_body`), so what is measured is what goes on the
#    wire. 120 KiB leaves declared headroom (~8 KiB) for the JSON envelope
#    (ids, key, exec_ms) under the router's 128 KiB.
_RESULT_TEXT_MAX = 65536
_RESULT_BYTES_MAX = 120 * 1024


def _encode_body(body: dict[str, object]) -> bytes:
    """The ONE encoder for /complete bodies — also the measuring stick for
    `_RESULT_BYTES_MAX`. Matches what httpx's `json=` would produce today
    (`ensure_ascii=False, separators=(",", ":")`), but owned here so the
    byte pre-check can never drift from the bytes actually sent if httpx
    changes its encoder."""
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )

# How often the CLI version pin is re-verified while the loop runs.
_VERSION_RECHECK_S = 300.0

# Completion POST retry ladder for LOST responses (transport errors / 5xx):
# total attempts including the first, and the sleeps between them. Same
# completion_key on every attempt — the server's replay path makes this safe.
_COMPLETE_ATTEMPTS = 3
_COMPLETE_BACKOFF_S = (0.5, 1.0)

# First semver-looking token in `codex --version` output. The pin is the
# bare semver (e.g. "0.147.0"); no token found = mismatch (fail-closed).
_SEMVER_RE = re.compile(r"(\d+\.\d+\.\d+)")


@dataclass(frozen=True)
class DaemonConfig:
    """Immutable env-derived configuration, validated fail-fast at startup."""

    base_url: str
    broker_key: str
    version_pin: str
    model: str = MODEL_TERRA
    poll_s: float = 2.0
    net_margin_s: float = 1.0
    codex_bin: str | None = None
    codex_home: str | None = None

    @classmethod
    def from_env(cls) -> DaemonConfig:
        """Read and validate every knob. Raises ``ValueError`` on any
        missing/invalid value — the daemon must refuse to start rather than
        run half-configured (scar family #2: a daemon that starts and
        cannot work is green theater)."""
        base_url = (os.environ.get("WA_BROKER_BASE_URL") or "").strip().rstrip("/")
        if not base_url:
            raise ValueError("WA_BROKER_BASE_URL is required")
        broker_key = (os.environ.get("WA_BROKER_KEY") or "").strip()
        if not broker_key:
            raise ValueError("WA_BROKER_KEY is required (env only — never argv)")
        version_pin = (os.environ.get("WA_CODEX_CLI_VERSION_PIN") or "").strip()
        if not version_pin:
            raise ValueError(
                "WA_CODEX_CLI_VERSION_PIN is required — the daemon never runs unpinned "
                "(chaos row 8: a silently upgraded CLI changes behavior under live traffic)"
            )
        model = (os.environ.get("WA_CODEX_MODEL") or MODEL_TERRA).strip()
        if model not in _ALLOWED_MODELS:
            raise ValueError(
                f"WA_CODEX_MODEL not allowed: {model!r} — must be one of {sorted(_ALLOWED_MODELS)}"
            )
        try:
            poll_s = float(os.environ.get("WA_BROKER_POLL_S", "2.0"))
            net_margin_s = float(os.environ.get("WA_BROKER_NET_MARGIN_S", "1.0"))
        except ValueError as exc:
            raise ValueError("WA_BROKER_POLL_S / WA_BROKER_NET_MARGIN_S must be numbers") from exc
        if poll_s <= 0 or net_margin_s < 0:
            raise ValueError("WA_BROKER_POLL_S must be > 0 and WA_BROKER_NET_MARGIN_S >= 0")
        return cls(
            base_url=base_url,
            broker_key=broker_key,
            version_pin=version_pin,
            model=model,
            poll_s=poll_s,
            net_margin_s=net_margin_s,
            codex_bin=os.environ.get("WA_CODEX_BIN") or None,
            codex_home=os.environ.get("CODEX_HOME") or None,
        )


def compute_budget_s(deadline_at: str, server_now: str, net_margin_s: float) -> float:
    """Exec budget in seconds from the claim response's OWN two timestamps.

    Pure function of server fields (chaos row 6): the local wall clock is
    never an input, so Pro clock skew cannot shrink or inflate the budget.
    The result is counted down on ``time.monotonic()`` by the exec timeout.
    Raises ``ValueError`` on unparseable timestamps and ``TypeError`` on an
    aware/naive mix (Kimi round-2 L3 — both fields come from one server
    serializer, so the mix is a server bug) — a malformed claim is a
    contract break, not a zero budget.

    ``net_margin_s`` does DOUBLE DUTY, declared (Kimi round-1 F5): it
    absorbs both the claim response's return transit (``server_now`` is
    stamped before the response travels back to Pro — that transit is real
    deadline time this function cannot see) and any residual margin for the
    completion POST. A claim leg slower than the margin means the exec can
    outlive the lease and complete into a 410 — convergent (the server-side
    fold already happened), just wasted work. Size ``WA_BROKER_NET_MARGIN_S``
    against measured claim latency, not hope.
    """
    deadline = datetime.fromisoformat(deadline_at)
    now = datetime.fromisoformat(server_now)
    return (deadline - now).total_seconds() - net_margin_s


@dataclass(frozen=True)
class _Claim:
    job_id: str
    fence_token: str
    package: str
    package_hash: str
    deadline_at: str
    server_now: str


class WaCodexDaemon:
    """Single-flight claim → exec → complete loop against the WA broker."""

    def __init__(
        self,
        config: DaemonConfig,
        *,
        codex_client: CodexExecClient | None = None,
        http_client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._codex = codex_client or CodexExecClient(
            binary=config.codex_bin,
            model=config.model,
            codex_home=config.codex_home,
        )
        # Persistent client (Golden Rule #10). The key rides ONLY here.
        # `transport` exists for tests: it lets them drive THIS construction
        # path (header attachment included) against a MockTransport instead
        # of bypassing it with a pre-built client.
        self._http = http_client or httpx.AsyncClient(  # golden-rule-10-exempt: daemon-lifetime persistent client, closed in run_forever's finally
            base_url=config.base_url,
            headers={"X-API-Key": config.broker_key},
            timeout=httpx.Timeout(10.0, read=20.0),
            transport=transport,
        )
        self._owns_http = http_client is None
        self._stop = asyncio.Event()
        self._version_ok = False
        self._version_checked_at = 0.0
        self._last_exec_ms: int | None = None

    def request_stop(self) -> None:
        """Graceful stop: the current iteration (exec + completion included)
        finishes, then the loop exits — a leased job is never abandoned by
        shutdown."""
        self._stop.set()

    # -- CLI version pin (chaos row 8) ---------------------------------

    async def _read_cli_version(self) -> str | None:
        """Return the first semver token from ``codex --version``, or None
        on any failure (missing binary, non-zero exit, no token) —
        fail-closed: None never matches a pin."""
        binary = self._config.codex_bin or shutil.which("codex")
        if not binary:
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                binary,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            except asyncio.TimeoutError:
                # A hung `codex --version` is precisely the broken-binary
                # state this probe guards — without the kill it would leak
                # one child per re-check, forever (Kimi round-1 F3).
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                with contextlib.suppress(asyncio.TimeoutError, OSError):
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                return None
        except OSError:
            return None
        if proc.returncode != 0:
            return None
        match = _SEMVER_RE.search(stdout_b.decode("utf-8", errors="replace"))
        return match.group(1) if match else None

    async def _recheck_version(self) -> None:
        """Re-verify the pin; log ONCE per state change (a paused daemon
        that logs every poll drowns the signal — scar family #2)."""
        observed = await self._read_cli_version()
        ok = observed is not None and observed == self._config.version_pin
        if ok and not self._version_ok:
            logger.info(
                "wa-codex-daemon: CLI version %s matches pin — claiming %s",
                observed,
                "resumed" if self._version_checked_at else "enabled",
            )
        elif not ok and (self._version_ok or not self._version_checked_at):
            logger.error(
                "wa-codex-daemon: CLI version %r does not match pin %r — claiming STOPPED "
                "(the stale heartbeat gauge opens the server-side breaker; update the pin "
                "or the binary and restart, or wait for this re-check to see them agree)",
                observed,
                self._config.version_pin,
            )
        self._version_ok = ok
        self._version_checked_at = time.monotonic()

    # -- broker HTTP ----------------------------------------------------

    async def _claim(self) -> _Claim | None:
        try:
            response = await self._http.post(
                "/api/wa-broker/claim",
                json={"in_flight": 0, "last_exec_ms": self._last_exec_ms},
            )
        except httpx.HTTPError as exc:
            logger.warning("wa-codex-daemon: claim transport error: %s", type(exc).__name__)
            return None
        if response.status_code != 200:
            logger.warning("wa-codex-daemon: claim HTTP %s", response.status_code)
            return None
        try:
            data = response.json()
        except ValueError:
            # A 200 whose body is not JSON (an LB error page, a truncated
            # response) is a transport blip, not a loop crash — treat it
            # like any failed claim (Kimi round-1 named test gap).
            logger.warning("wa-codex-daemon: claim returned non-JSON 200")
            return None
        if not data.get("job_id"):
            return None
        try:
            return _Claim(
                job_id=str(data["job_id"]),
                fence_token=str(data["fence_token"]),
                package=str(data["package"]),
                package_hash=str(data["package_hash"]),
                deadline_at=str(data["deadline_at"]),
                server_now=str(data["server_now"]),
            )
        except KeyError as exc:
            # A job_id with missing siblings is a contract break — there is
            # no fence to complete under, so nothing can be reported; the
            # lease reaper folds it server-side at deadline.
            logger.error("wa-codex-daemon: claim response missing field %s", exc)
            return None

    async def _complete(
        self,
        claim: _Claim,
        completion_key: str,
        *,
        result_text: str | None,
        error_class: str | None,
        exec_ms: int | None,
    ) -> None:
        """Idempotent completion POST (chaos row 3): retries a LOST response
        (transport error / 5xx) with the SAME completion_key; a 4xx is never
        retried — the same body would fail identically (W104: judge the
        reply, and a retry loop on a deterministic refusal is theater)."""
        body = {
            "job_id": claim.job_id,
            "fence_token": claim.fence_token,
            "completion_key": completion_key,
            "result_text": result_text,
            "error_class": error_class,
            "exec_ms": exec_ms,
        }
        encoded = _encode_body(body)
        for attempt in range(_COMPLETE_ATTEMPTS):
            try:
                response = await self._http.post(
                    "/api/wa-broker/complete",
                    content=encoded,
                    headers={"Content-Type": "application/json"},
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "wa-codex-daemon: complete transport error (attempt %d/%d, job %s): %s",
                    attempt + 1,
                    _COMPLETE_ATTEMPTS,
                    claim.job_id,
                    type(exc).__name__,
                )
                if attempt < _COMPLETE_ATTEMPTS - 1:
                    await asyncio.sleep(_COMPLETE_BACKOFF_S[min(attempt, len(_COMPLETE_BACKOFF_S) - 1)])
                continue
            if response.status_code == 200:
                try:
                    status = response.json().get("status")
                except ValueError:
                    # A 200 whose body is not JSON (LB error page) — same
                    # guard as the claim side (Kimi round-2 L1). If the 200
                    # was fake and the completion never landed, the lease
                    # reaper folds the job; a re-POST would be same-key-safe
                    # but a 200 is the server's word that it processed us.
                    status = "unknown-non-json-200"
                logger.info(
                    "wa-codex-daemon: completion %s for job %s (outcome=%s)",
                    status,
                    claim.job_id,
                    error_class or "result",
                )
                return
            if response.status_code == 409:
                # Someone else completed under our fence — a protocol
                # violation worth a human's eyes; retrying cannot help.
                logger.error(
                    "wa-codex-daemon: 409 conflicting completion for job %s — protocol violation",
                    claim.job_id,
                )
                return
            if response.status_code == 410:
                # Lease expired server-side; the reaper already folded it.
                logger.info("wa-codex-daemon: 410 lease gone for job %s — moving on", claim.job_id)
                return
            if 500 <= response.status_code < 600:
                logger.warning(
                    "wa-codex-daemon: complete HTTP %s (attempt %d/%d, job %s)",
                    response.status_code,
                    attempt + 1,
                    _COMPLETE_ATTEMPTS,
                    claim.job_id,
                )
                if attempt < _COMPLETE_ATTEMPTS - 1:
                    await asyncio.sleep(_COMPLETE_BACKOFF_S[min(attempt, len(_COMPLETE_BACKOFF_S) - 1)])
                continue
            # Remaining 4xx (422 etc.): our bug, deterministic — never retry.
            logger.error(
                "wa-codex-daemon: complete rejected HTTP %s for job %s — not retrying",
                response.status_code,
                claim.job_id,
            )
            return
        logger.error(
            "wa-codex-daemon: completion for job %s LOST after %d attempts — "
            "the lease reaper will fold it at deadline",
            claim.job_id,
            _COMPLETE_ATTEMPTS,
        )

    # -- exec ------------------------------------------------------------

    async def _execute_and_complete(self, claim: _Claim) -> None:
        # Minted once per exec attempt; every completion POST for this
        # attempt (including retries of a lost response) reuses it.
        completion_key = uuid.uuid4().hex

        if not self._version_ok:
            # Guard against a KNOWN-drifted state reaching an exec. Honest
            # scope (Kimi round-1 F4): this reads the CACHED verdict, so a
            # binary upgraded between two re-checks executes for up to
            # `_VERSION_RECHECK_S` before the flip — the guard catches
            # drift the daemon has already SEEN, and chaos row 8's bound is
            # the re-check interval, not zero. A per-exec version probe
            # would close that window at the cost of a subprocess inside
            # every job's budget; deliberately not taken.
            await self._complete(
                claim, completion_key, result_text=None, error_class="cli_version_mismatch", exec_ms=None
            )
            return

        try:
            budget_s = compute_budget_s(claim.deadline_at, claim.server_now, self._config.net_margin_s)
        except (ValueError, TypeError):
            logger.error(
                "wa-codex-daemon: unparseable deadline fields for job %s — contract break",
                claim.job_id,
            )
            await self._complete(
                claim, completion_key, result_text=None, error_class="cli_failure", exec_ms=None
            )
            return
        if budget_s <= 0:
            # Already out of time at claim (clock margin consumed by the
            # claim round-trip): report the timeout without spawning.
            await self._complete(
                claim, completion_key, result_text=None, error_class="exec_timeout", exec_ms=None
            )
            return

        started = time.monotonic()
        error_class: str | None = None
        result_text: str | None = None
        # `result` non-None ⟺ generate returned ⟺ no except ran ⟺ error_class
        # is None — branching on it below keeps the variable definitely
        # initialized (CodeQL cannot track the error_class correlation).
        result = None
        try:
            result = await self._codex.generate(claim.package, timeout_s=budget_s)
        except CodexExecTimeoutError:
            error_class = "exec_timeout"
        except CodexExecUnavailableError:
            error_class = "spawn_failure"
        except CodexExecAuthError:
            # The seat's login died — every subsequent job will fail the
            # same way until the operator re-runs `codex login`. Loud, but
            # typed like any CLI failure on the wire (the vocabulary is
            # closed; the sentinel reads THIS log line).
            logger.error(
                "wa-codex-daemon: codex seat AUTH DEATH detected — operator must re-login "
                "as zantara-codex (job %s reported as cli_failure)",
                claim.job_id,
            )
            error_class = "cli_failure"
        except CodexExecQuotaError:
            # The seat's ChatGPT/Codex quota is exhausted — every subsequent
            # job will fail the same way until the usage window resets or
            # the operator switches seats. Twin of the AUTH DEATH arm above
            # (owner packet item 13, 2026-08-26): distinct from a generic
            # CLI failure so the operator can tell "seat is out of quota"
            # from "something broke", even though the wire value is
            # unchanged — wa_broker.ALLOWED_ERROR_CLASSES (the closed
            # vocabulary the router validates against) has no QUOTA member
            # today, only the separate, unwired F3 vocabulary in
            # codex_broker_wire.py does. Widening ALLOWED_ERROR_CLASSES is
            # a deliberate, reviewed diff this unit does not make.
            logger.error(
                "wa-codex-daemon: codex seat QUOTA EXHAUSTED — operator must wait "
                "for the usage window to reset or switch seats (job %s reported "
                "as cli_failure)",
                claim.job_id,
            )
            error_class = "cli_failure"
        except (CodexExecProcessError, CodexExecCommunicationError, CodexExecOutputShapeError):
            error_class = "cli_failure"
        except Exception as exc:
            logger.error(
                "wa-codex-daemon: unexpected exec failure for job %s: %s",
                claim.job_id,
                type(exc).__name__,
            )
            error_class = "cli_failure"
        exec_ms = int((time.monotonic() - started) * 1000)
        self._last_exec_ms = exec_ms

        if result is not None:
            text = result.text
            if not text.strip():
                error_class = "empty_output"
            elif "\x00" in text:
                # PostgreSQL TEXT cannot store U+0000; the router 422s it
                # with instructions to report cli_failure — pre-scan here so
                # the job fails TYPED and fast instead of folding at the
                # lease deadline behind an unretried 422 (Kimi round-1 F2).
                logger.warning(
                    "wa-codex-daemon: result for job %s contains NUL — cli_failure",
                    claim.job_id,
                )
                error_class = "cli_failure"
            elif len(text) > _RESULT_TEXT_MAX:
                # Char cap (router Pydantic max_length). BEFORE posting;
                # never truncate-and-send.
                logger.warning(
                    "wa-codex-daemon: result for job %s exceeds %d chars — oversized_output",
                    claim.job_id,
                    _RESULT_TEXT_MAX,
                )
                error_class = "oversized_output"
            elif len(_encode_body({"result_text": text})) > _RESULT_BYTES_MAX:
                # Byte cap (router stream cap) measured with the SAME
                # encoder `_complete` sends with — a multibyte-heavy answer
                # can pass the char cap and still 413 at the router, where
                # the 4xx-never-retry branch would abandon it untyped
                # (Kimi round-1 F1, measured: 60k chars -> ~180KB).
                logger.warning(
                    "wa-codex-daemon: result for job %s exceeds %d encoded bytes — oversized_output",
                    claim.job_id,
                    _RESULT_BYTES_MAX,
                )
                error_class = "oversized_output"
            else:
                result_text = text

        await self._complete(
            claim,
            completion_key,
            result_text=result_text,
            error_class=error_class,
            exec_ms=exec_ms,
        )

    # -- main loop ---------------------------------------------------------

    async def run_forever(self) -> None:
        """Blocking loop. Raises ``RuntimeError`` at startup when the CLI
        version does not match the pin — a daemon that cannot legally exec
        must not sit green (scar family #2)."""
        await self._recheck_version()
        if not self._version_ok:
            raise RuntimeError(
                "wa-codex-daemon: startup refused — CLI version does not match "
                f"WA_CODEX_CLI_VERSION_PIN={self._config.version_pin!r}"
            )
        logger.info(
            "wa-codex-daemon: started (model=%s, poll=%.1fs, margin=%.1fs)",
            self._config.model,
            self._config.poll_s,
            self._config.net_margin_s,
        )
        try:
            while not self._stop.is_set():
                try:
                    if time.monotonic() - self._version_checked_at >= _VERSION_RECHECK_S:
                        await self._recheck_version()
                    if not self._version_ok:
                        await self._sleep(self._config.poll_s)
                        continue
                    claim = await self._claim()
                    if claim is None:
                        await self._sleep(self._config.poll_s)
                        continue
                    await self._execute_and_complete(claim)
                except Exception as exc:
                    logger.error(
                        "wa-codex-daemon: loop iteration failed: %s", type(exc).__name__
                    )
                    await self._sleep(self._config.poll_s)
        finally:
            if self._owns_http:
                await self._http.aclose()
            logger.info("wa-codex-daemon: stopped")

    async def _sleep(self, seconds: float) -> None:
        """Sleep that wakes immediately on stop — shutdown never waits out
        a poll interval."""
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass  # timeout = the normal poll-interval wake; stop stays unset


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = DaemonConfig.from_env()
    daemon = WaCodexDaemon(config)

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, daemon.request_stop)
        await daemon.run_forever()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
