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
    CodexExecTimeoutError,
    CodexExecUnavailableError,
)

logger = logging.getLogger(__name__)

# Server-side transport bound (wa_broker router: `result_text` max_length
# 65536). Enforced HERE as well, BEFORE posting: a longer result is reported
# as error_class="oversized_output", never truncated-and-sent — a silently
# truncated answer is a corrupt answer wearing the success shape.
_RESULT_TEXT_MAX = 65536

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
    Raises ``ValueError`` on unparseable timestamps — a malformed claim is
    a contract break, not a zero budget.
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
            stdout_b, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
        except (OSError, asyncio.TimeoutError):
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
        data = response.json()
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
        for attempt in range(_COMPLETE_ATTEMPTS):
            try:
                response = await self._http.post("/api/wa-broker/complete", json=body)
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
                status = response.json().get("status")
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
            # Unreachable in the plain single-flight order (the loop checks
            # before claiming), kept as a guard so a claimed job is NEVER
            # executed on a drifted binary if the ordering ever changes.
            await self._complete(
                claim, completion_key, result_text=None, error_class="cli_version_mismatch", exec_ms=None
            )
            return

        try:
            budget_s = compute_budget_s(claim.deadline_at, claim.server_now, self._config.net_margin_s)
        except ValueError:
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

        if error_class is None:
            text = result.text
            if not text.strip():
                error_class = "empty_output"
            elif len(text) > _RESULT_TEXT_MAX:
                # Cap BEFORE posting; never truncate-and-send.
                logger.warning(
                    "wa-codex-daemon: result for job %s exceeds %d chars — oversized_output",
                    claim.job_id,
                    _RESULT_TEXT_MAX,
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
            pass


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
