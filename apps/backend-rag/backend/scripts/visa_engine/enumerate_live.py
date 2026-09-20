"""Slice B2' — the live runner for the B1 interview-space enumeration.

Reads the manifest ``enumerate-interview-space.ts`` (Slice B1'') writes --
every covering walk in ``manifest["coveringSubset"]["walks"]``, already an
engine-ready wire payload (``schema_version``/``assessment_id``/
``collected_at``/``facts``/optional ``disclosed_review_flags``) built by the
production fact-mapper for synthetic personas only -- and posts each one to
``POST /api/visa-oracle/evaluate`` as ``traffic_source=synthetic_driver``,
the same driver-token custody idiom as ``probe_evaluate.py``
(``X-Visa-Driver-Token``, read from a file, chmod-checked, never logged).
``gold_replay_driver.py`` shares the header/query-param shape but NOT the
chmod check -- do not assume it does.

Fail-closed by construction (G2-b / the B2 risk row):

* ``--max-requests`` has NO default -- an unbudgeted live run is refused
  before any network call. ``--rate-per-minute`` defaults to 25 and must
  stay below the router's own dedicated 30/min bucket
  (``visa_oracle_evaluate.py``), which this module never imports.
* HTTP 429 and connection errors are HARNESS reds, never engine verdicts --
  a rate-limited or flaky transport must not poison the report with a false
  "the engine said X". Both classes get bounded retries with backoff, and
  EVERY attempt (retries included) is charged against ``--max-requests``.

Circuit breakers (B2', after gate REWORK-BUILD on #6861 -- OBS-2):
a bad/rotated token, a blanket 4xx, or a hard-down engine must not drain the
whole budget against production.

* HTTP 401/403 stops the run IMMEDIATELY -- exactly one request is spent,
  the run exits non-zero, and the log names the status and says the token
  FILE is the likely cause (never the token value).
* Any other harness red (5xx, timeout, connection error, a blanket 4xx, an
  invalid 200 body) stops the run after ``--max-consecutive-harness-reds``
  (default 3) CONSECUTIVE harness reds; an engine verdict resets the
  counter to zero.
* HTTP 429 keeps its own rule, unchanged: bounded retries with backoff,
  then an immediate stop -- it never counts toward the consecutive tally
  because it already stops on its own.

Resume (B2', after OBS-3/OBS-7):

* The report is rewritten to disk after every walk (atomic per-process
  temp-name + rename -- OBS-7), so a kill mid-run costs nothing. Only an
  ENGINE VERDICT is a terminal result: re-running with the same ``--report``
  skips walks already resolved to an engine verdict, but RE-ATTEMPTS any
  walk whose latest recorded result is a harness red -- a poisoned run
  (e.g. a bad token) is cured by fixing the cause and re-running, never by
  discarding the report. Every attempt for a walk, harness or engine, is
  kept in that walk's own ``attempts_history`` -- no attempt is silently
  overwritten.
* An exclusive kernel-held lock (``<report>.lock``) enforces one runner per
  report; a second runner is refused with one line and no traceback. The
  ``--break-stale-lock`` flag is gone because a kernel-held lock has no stale
  state to break.
* The report's header pins the manifest's own sha256 -- resuming against a
  DIFFERENT manifest (a different walk set) is refused, not silently
  merged.
* ``requests_used_this_run`` and ``requests_used_total`` are both tracked
  (per-run and cumulative across every resume against this report); the two
  ``/health`` GETs per run stay outside the ``--max-requests`` budget, and
  that exclusion is declared in both ``--dry-run``'s plan line and the
  report header.
* The report carries no request facts beyond the walk's own ``label`` (the
  manifest's id for it) -- personas are synthetic, but this stays
  PII-shaped-safe by construction, never by promise.

This module never imports the FastAPI app -- pure HTTP client CLI, same
offline-ops posture as its ``visa_engine`` script siblings.

The manifest is not a checked-in input: produce it with ``cd apps/mouth && npm run visa-oracle:enumerate`` (the ``npx tsx scripts/visa-oracle/enumerate-interview-space.ts`` script), then run this module.

Declared lock limits: the lock is advisory, so a writer that never calls ``ReportLock`` is not stopped by it.
The lock is local-filesystem-only; ``flock`` over NFS/SMB is not guaranteed to be exclusive.
The lock is POSIX-only because it uses ``fcntl`` and does not support Windows.
A SIGKILL landing inside ``atomic_write_json``'s write can leave an orphan ``<report>.<pid>.tmp``.

Usage (from ``apps/backend-rag``)::

    PYTHONPATH=. .venv/bin/python -m backend.scripts.visa_engine.enumerate_live \\
      --manifest ../../research/operations/visa-oracle-interview-space-manifest.json \\
      --report /tmp/visa-oracle-live-enumeration-report.json \\
      --max-requests 60 --rate-per-minute 25 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import stat
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx

from backend.scripts.visa_engine.report_lock import ReportLock, ReportLockError, atomic_write_json

logger = logging.getLogger("visa_engine.enumerate_live")

DEFAULT_URL = "https://nuzantara-rag.fly.dev/api/visa-oracle/evaluate"
URL_ENV = "VISA_ORACLE_ENUMERATE_URL"
DEFAULT_HEALTH_URL = "https://nuzantara-rag.fly.dev/health"
HEALTH_URL_ENV = "VISA_ORACLE_ENUMERATE_HEALTH_URL"

DEFAULT_DRIVER_TOKEN_FILE = Path.home() / ".config" / "nuzantara" / "visa-signing" / "driver-token"
DRIVER_TOKEN_FILE_ENV = "VISA_ENGINE_DRIVER_TOKEN_FILE"
DRIVER_TOKEN_HEADER = "X-Visa-Driver-Token"

#: This runner has no ``--as-real`` escape hatch at all (the B2 risk row's
#: PII rule) -- every request is labelled exactly this, never configurable.
TRAFFIC_SOURCE = "synthetic_driver"

DEFAULT_RATE_PER_MINUTE = 25.0
#: The evaluate router's own dedicated bucket is 30/min
#: (``backend/app/routers/visa_oracle_evaluate.py``) -- this runner refuses
#: to arm a rate at or above that ceiling so it can never be the cause of
#: the 429s it is watching for.
RATE_CEILING_PER_MINUTE = 30.0

DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 2.0
DEFAULT_TIMEOUT_SECONDS = 30.0

#: W1 -- consecutive-harness-red circuit breaker default. 401/403 have their
#: own always-immediate rule and never consult this constant.
DEFAULT_MAX_CONSECUTIVE_HARNESS_REDS = 3

#: W4 -- the two /health GETs (start + end) are outside --max-requests by
#: design; declared here once so --dry-run and the report header read the
#: same number.
HEALTH_PROBES_OUTSIDE_BUDGET = 2

REPORT_VERSION = 2

#: Group/other permission bits -- same posture as probe_evaluate.py's token
#: check (cicatrix family #4 "secret in the clear").
_GROUP_OTHER_BITS = stat.S_IRWXG | stat.S_IRWXO

#: HTTP statuses that stop the run IMMEDIATELY (W1 / OBS-2) -- a rotated or
#: revoked driver token, never retried, never counted toward the N-consecutive
#: breaker below (it has its own always-fires rule).
_AUTH_CIRCUIT_BREAKER_STATUSES = frozenset({401, 403})


class EnumerateLiveError(RuntimeError):
    """A fail-closed condition this runner refuses to proceed past."""


# ---------------------------------------------------------------------------
# Overridable seams (monkeypatched by tests -- same idiom as probe_evaluate.py's
# ``_post_evaluate``: module-level functions, never constructor injection).
# ---------------------------------------------------------------------------


async def _post_evaluate(
    client: httpx.AsyncClient,
    *,
    url: str,
    headers: Mapping[str, str],
    json_body: Mapping[str, Any],
    timeout: float,
) -> httpx.Response:
    return await client.post(
        url, params={"traffic_source": TRAFFIC_SOURCE}, headers=dict(headers), json=json_body, timeout=timeout
    )


async def _get_health(client: httpx.AsyncClient, *, url: str, timeout: float) -> httpx.Response:
    return await client.get(url, timeout=timeout)


async def _sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


def _monotonic() -> float:
    return time.monotonic()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Driver token custody -- identical fail-closed posture to probe_evaluate.py
# ---------------------------------------------------------------------------


def _check_token_file_permissions(path: Path, mode: int) -> None:
    if mode & _GROUP_OTHER_BITS:
        raise EnumerateLiveError(
            f"driver token file {path} has mode {oct(mode)} -- refusing to read a "
            "group/other-accessible secret. `chmod 0600` it first."
        )


def load_driver_token(path: Path) -> str:
    """Load the driver credential from disk. Fail-closed, never logged."""

    try:
        file_stat = path.stat()
    except FileNotFoundError as exc:
        raise EnumerateLiveError(f"driver token file not found: {path}") from exc
    except OSError as exc:
        raise EnumerateLiveError(f"cannot stat driver token file {path}: {exc}") from exc
    if not stat.S_ISREG(file_stat.st_mode):
        raise EnumerateLiveError(f"driver token file {path} is not a regular file")
    _check_token_file_permissions(path, file_stat.st_mode)
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise EnumerateLiveError(f"cannot read driver token file {path}: {exc}") from exc
    if not token:
        raise EnumerateLiveError(f"driver token file {path} is empty")
    return token


# ---------------------------------------------------------------------------
# Manifest + report I/O
# ---------------------------------------------------------------------------


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EnumerateLiveError(f"cannot read manifest {path}: {exc}") from exc
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EnumerateLiveError(f"manifest {path} is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise EnumerateLiveError(f"manifest {path} must be a JSON object")
    return manifest


def manifest_digest(manifest: Mapping[str, Any]) -> str:
    """A stable identity for the manifest's covering-subset walks -- the
    report header names it (requirement 3) so a report can never be read
    against, or resumed into, the wrong walk set.
    """

    covering = manifest.get("coveringSubset")
    walks = covering.get("walks") if isinstance(covering, Mapping) else None
    canonical = json.dumps(walks, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def extract_walks(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    covering = manifest.get("coveringSubset")
    walks = covering.get("walks") if isinstance(covering, Mapping) else None
    if not isinstance(walks, list) or not walks:
        raise EnumerateLiveError("manifest has no coveringSubset.walks to enumerate")
    for walk in walks:
        if not isinstance(walk, dict) or not walk.get("label"):
            raise EnumerateLiveError("manifest walk is missing a 'label' id")
    return walks


def build_request_body(walk: Mapping[str, Any]) -> dict[str, Any]:
    """The wire body for one walk -- drops the enumerator-only ``label``/
    ``asked`` bookkeeping fields, keeping only what the evaluate endpoint's
    request schema accepts.
    """

    body: dict[str, Any] = {
        "schema_version": walk["schema_version"],
        "assessment_id": walk["assessment_id"],
        "collected_at": walk["collected_at"],
        "facts": walk["facts"],
    }
    flags = walk.get("disclosed_review_flags")
    if flags:
        body["disclosed_review_flags"] = flags
    return body


def load_report(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EnumerateLiveError(f"cannot read report {path}: {exc}") from exc
    try:
        report = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EnumerateLiveError(f"report {path} is not valid JSON: {exc}") from exc
    if not isinstance(report, dict):
        raise EnumerateLiveError(f"report {path} must be a JSON object")
    return report


# ---------------------------------------------------------------------------
# Budget + rate limiting
# ---------------------------------------------------------------------------


def validate_budget(
    max_requests: int | None,
    rate_per_minute: float,
    max_consecutive_harness_reds: int,
) -> None:
    if max_requests is None:
        raise EnumerateLiveError(
            "--max-requests is required (no default): a live run against production "
            "with no explicit budget is refused, fail-closed. Pass an explicit "
            "--max-requests."
        )
    if max_requests <= 0:
        raise EnumerateLiveError("--max-requests must be a positive integer")
    if rate_per_minute <= 0:
        raise EnumerateLiveError("--rate-per-minute must be a positive number")
    if rate_per_minute >= RATE_CEILING_PER_MINUTE:
        raise EnumerateLiveError(
            "--rate-per-minute must stay below the evaluate router's own dedicated "
            f"{RATE_CEILING_PER_MINUTE:g}/min bucket -- got {rate_per_minute:g}"
        )
    if max_consecutive_harness_reds < 1:
        raise EnumerateLiveError("--max-consecutive-harness-reds must be >= 1")
    if max_consecutive_harness_reds > max_requests:
        raise EnumerateLiveError(
            f"--max-consecutive-harness-reds ({max_consecutive_harness_reds}) must be <= "
            f"--max-requests ({max_requests})"
        )


class RateLimiter:
    """Spaces requests at least ``60 / rate_per_minute`` seconds apart."""

    def __init__(self, rate_per_minute: float) -> None:
        self._min_interval = 60.0 / rate_per_minute
        self._last: float | None = None

    async def wait(self) -> None:
        now = _monotonic()
        if self._last is not None:
            remaining = self._min_interval - (now - self._last)
            if remaining > 0:
                await _sleep(remaining)
        self._last = _monotonic()


class RequestBudget:
    """Hard cap on HTTP attempts -- retries count against it too."""

    def __init__(self, max_requests: int) -> None:
        self._max = max_requests
        self.used = 0

    def reserve(self) -> bool:
        if self.used >= self._max:
            return False
        self.used += 1
        return True


# ---------------------------------------------------------------------------
# Per-walk result + classification
# ---------------------------------------------------------------------------

Classification = Literal["engine_verdict", "harness_red"]


@dataclass(frozen=True)
class WalkResult:
    walk_id: str
    classification: Classification
    http_status: int | None
    engine_state: str | None
    reason_codes: dict[str, list[str]]
    rule_pack: dict[str, Any] | None
    harness_detail: str | None
    retries: int
    latency_ms: float
    timestamp: str

    def to_json(self) -> dict[str, Any]:
        return {
            "walk_id": self.walk_id,
            "classification": self.classification,
            "http_status": self.http_status,
            "engine_state": self.engine_state,
            "reason_codes": self.reason_codes,
            "rule_pack": self.rule_pack,
            "harness_detail": self.harness_detail,
            "retries": self.retries,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
        }


def _merge_attempt(existing_row: dict[str, Any] | None, result: WalkResult) -> dict[str, Any]:
    """W2 (OBS-3) -- fold one new terminal attempt into a walk's row.

    The row's top-level fields always mirror the LATEST attempt (so old
    readers/tests that read ``row["classification"]`` keep working); every
    attempt ever recorded for this walk, including the latest, is kept in
    ``attempts_history`` in chronological order -- each history row carries
    the same keys as the walk's own top-level row minus ``attempts`` and
    ``attempts_history`` themselves (it is a ``WalkResult.to_json()`` dict).
    No attempt is silently overwritten, and ``attempts`` is simply that
    list's length.
    """

    attempt = result.to_json()
    history: list[dict[str, Any]] = list(existing_row["attempts_history"]) if existing_row else []
    history.append(attempt)
    row = dict(attempt)
    row["attempts"] = len(history)
    row["attempts_history"] = history
    return row


def _reason_codes(decision: Mapping[str, Any]) -> dict[str, list[str]]:
    def codes(key: str) -> list[str]:
        items = decision.get(key) or []
        return [item["code"] for item in items if isinstance(item, Mapping) and item.get("code")]

    return {
        "review_reasons": codes("review_reasons"),
        "no_path_reasons": codes("no_path_reasons"),
        "notices": codes("notices"),
    }


def _harness_result(
    walk_id: str,
    detail: str,
    *,
    http_status: int | None,
    attempts: int,
    latency_ms: float,
) -> WalkResult:
    return WalkResult(
        walk_id=walk_id,
        classification="harness_red",
        http_status=http_status,
        engine_state=None,
        reason_codes={},
        rule_pack=None,
        harness_detail=detail,
        retries=attempts - 1,
        latency_ms=round(latency_ms, 2),
        timestamp=_utcnow().isoformat(),
    )


def _retry_after_seconds(response: httpx.Response, default: float) -> float:
    value = response.headers.get("Retry-After")
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


async def run_walk(
    client: httpx.AsyncClient,
    walk: Mapping[str, Any],
    *,
    url: str,
    headers: Mapping[str, str],
    timeout: float,
    max_retries: int,
    backoff_seconds: float,
    budget: RequestBudget,
    limiter: RateLimiter,
) -> WalkResult | None:
    """Drive one walk to a terminal result, or ``None`` if the budget ran
    out before this walk could even start its first attempt -- the caller
    stops the run and leaves the walk unrecorded for the next resume.

    Unchanged from the gate-verified #6861 head: 429/5xx/timeout/connection
    errors retry with backoff up to ``max_retries``; every other non-200
    (401/403 included) is terminal on the FIRST attempt -- zero retries.
    That "no retry" behavior is exactly what W1's 401/403 circuit breaker
    depends on (one request spent), so it stays untouched here; W1's
    stop-the-run decision lives in the caller, ``run_live_enumeration``.
    """

    walk_id = walk["label"]
    body = build_request_body(walk)
    attempts = 0
    while True:
        if not budget.reserve():
            return None
        attempts += 1
        await limiter.wait()
        started = _monotonic()
        try:
            response = await _post_evaluate(client, url=url, headers=headers, json_body=body, timeout=timeout)
        except httpx.TimeoutException as exc:
            latency_ms = (_monotonic() - started) * 1000
            if attempts > max_retries:
                return _harness_result(walk_id, "timeout", http_status=None, attempts=attempts, latency_ms=latency_ms)
            logger.warning("walk=%s timeout attempt=%d: %s -- backing off", walk_id, attempts, exc)
            await _sleep(backoff_seconds * attempts)
            continue
        except httpx.TransportError as exc:
            latency_ms = (_monotonic() - started) * 1000
            if attempts > max_retries:
                return _harness_result(
                    walk_id, "connection_error", http_status=None, attempts=attempts, latency_ms=latency_ms
                )
            logger.warning("walk=%s connection error attempt=%d: %s -- backing off", walk_id, attempts, exc)
            await _sleep(backoff_seconds * attempts)
            continue

        latency_ms = (_monotonic() - started) * 1000

        if response.status_code == 429:
            if attempts > max_retries:
                return _harness_result(walk_id, "http_429", http_status=429, attempts=attempts, latency_ms=latency_ms)
            logger.warning("walk=%s HTTP 429 attempt=%d -- backing off, not an engine verdict", walk_id, attempts)
            await _sleep(_retry_after_seconds(response, backoff_seconds * attempts))
            continue

        if response.status_code >= 500:
            if attempts > max_retries:
                return _harness_result(
                    walk_id, "http_5xx", http_status=response.status_code, attempts=attempts, latency_ms=latency_ms
                )
            await _sleep(backoff_seconds * attempts)
            continue

        if response.status_code != 200:
            return _harness_result(
                walk_id,
                f"http_{response.status_code}",
                http_status=response.status_code,
                attempts=attempts,
                latency_ms=latency_ms,
            )

        try:
            payload = response.json()
        except ValueError:
            return _harness_result(
                walk_id, "invalid_json_body", http_status=200, attempts=attempts, latency_ms=latency_ms
            )
        decision = payload.get("decision") if isinstance(payload, Mapping) else None
        if not isinstance(decision, Mapping):
            return _harness_result(
                walk_id, "missing_decision", http_status=200, attempts=attempts, latency_ms=latency_ms
            )

        return WalkResult(
            walk_id=walk_id,
            classification="engine_verdict",
            http_status=200,
            engine_state=decision.get("state"),
            reason_codes=_reason_codes(decision),
            rule_pack=decision.get("rule_pack") if isinstance(decision.get("rule_pack"), Mapping) else None,
            harness_detail=None,
            retries=attempts - 1,
            latency_ms=round(latency_ms, 2),
            timestamp=_utcnow().isoformat(),
        )


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def _new_report(
    *,
    manifest_path: Path,
    digest: str,
    total_walks: int,
    url: str,
    max_requests: int,
    rate_per_minute: float,
    max_consecutive_harness_reds: int,
) -> dict[str, Any]:
    return {
        "report_version": REPORT_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": digest,
        "manifest_walk_count": total_walks,
        "url": url,
        "traffic_source": TRAFFIC_SOURCE,
        "max_requests": max_requests,
        "rate_per_minute": rate_per_minute,
        "max_consecutive_harness_reds": max_consecutive_harness_reds,
        "started_at": _utcnow().isoformat(),
        "finished_at": None,
        "stopped_reason": None,
        "health": {"start": None, "end": None, "probes_outside_budget": HEALTH_PROBES_OUTSIDE_BUDGET},
        "requests_used_this_run": 0,
        "requests_used_total": 0,
        "walks": [],
        "summary": None,
    }


def _summarize(walks: list[dict[str, Any]], total_walks: int) -> dict[str, Any]:
    """Two SEPARATE tallies, never added together (requirement 4): an engine
    verdict and a harness red answer different questions and a combined
    count would hide which one moved. Reads each row's LATEST classification
    (top-level fields), not its ``attempts_history``.
    """

    engine_verdicts: dict[str, int] = {}
    harness_reds: dict[str, int] = {}
    for row in walks:
        if row["classification"] == "engine_verdict":
            state = row.get("engine_state") or "UNKNOWN"
            engine_verdicts[state] = engine_verdicts.get(state, 0) + 1
        else:
            detail = row.get("harness_detail") or "unknown"
            harness_reds[detail] = harness_reds.get(detail, 0) + 1
    return {
        "total_walks": total_walks,
        "recorded": len(walks),
        "pending": total_walks - len(walks),
        "engine_verdicts": engine_verdicts,
        "harness_reds": harness_reds,
    }


async def _probe_health(client: httpx.AsyncClient, url: str, *, timeout: float) -> dict[str, Any]:
    try:
        response = await _get_health(client, url=url, timeout=timeout)
    except httpx.HTTPError as exc:
        return {"http_status": None, "build_sha": None, "error": str(type(exc).__name__)}
    build_sha = None
    try:
        body = response.json()
        if isinstance(body, Mapping):
            build_sha = body.get("build_sha")
    except ValueError:
        pass
    return {"http_status": response.status_code, "build_sha": build_sha}


def _dry_run_plan(
    *,
    manifest_path: Path,
    report_path: Path,
    digest: str,
    total_walks: int,
    never_attempted: int,
    retryable_harness_reds: int,
    engine_verdicts_recorded: int,
    max_requests: int,
    rate_per_minute: float,
    max_consecutive_harness_reds: int,
) -> dict[str, Any]:
    pending = never_attempted + retryable_harness_reds
    requests_this_run = min(pending, max_requests)
    estimated_minutes = round(requests_this_run / rate_per_minute, 2) if rate_per_minute else None
    return {
        "dry_run": True,
        "manifest_path": str(manifest_path),
        "manifest_sha256": digest,
        "report_path": str(report_path),
        "total_walks": total_walks,
        "already_recorded": engine_verdicts_recorded,
        "pending_walks": pending,
        "never_attempted": never_attempted,
        "retryable_harness_reds": retryable_harness_reds,
        "max_requests": max_requests,
        "rate_per_minute": rate_per_minute,
        "max_consecutive_harness_reds": max_consecutive_harness_reds,
        "health_probes_outside_budget": HEALTH_PROBES_OUTSIDE_BUDGET,
        "estimated_minutes": estimated_minutes,
    }


def _load_existing_and_pending(
    report_path: Path, walks: list[dict[str, Any]], digest: str
) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Load the existing report (if any) and split ``walks`` into terminal
    (engine-verdict) vs pending. W2: a harness red is NOT terminal -- it is
    pending again, same as a walk never attempted at all.
    """

    existing: dict[str, Any] | None = None
    if report_path.exists():
        existing = load_report(report_path)
        report_version = existing.get("report_version", "missing")
        if report_version != REPORT_VERSION:
            raise EnumerateLiveError(
                f"existing report {report_path} has report_version={report_version!r}; "
                f"current REPORT_VERSION={REPORT_VERSION} -- refusing to resume"
            )
        existing_digest = existing.get("manifest_sha256")
        if existing_digest != digest:
            raise EnumerateLiveError(
                f"existing report {report_path} was built against manifest "
                f"sha256={existing_digest!r}; the current manifest is {digest!r} -- "
                "refusing to resume against a mismatched walk set"
            )

    walks_by_id: dict[str, dict[str, Any]] = {
        row["walk_id"]: row for row in (existing or {}).get("walks", [])
    }
    terminal_ids = {wid for wid, row in walks_by_id.items() if row.get("classification") == "engine_verdict"}
    pending_walks = [w for w in walks if w["label"] not in terminal_ids]
    return existing, walks_by_id, pending_walks


async def run_live_enumeration(
    *,
    manifest_path: Path,
    report_path: Path,
    url: str,
    health_url: str,
    driver_token_file: Path,
    max_requests: int,
    rate_per_minute: float,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    max_consecutive_harness_reds: int = DEFAULT_MAX_CONSECUTIVE_HARNESS_REDS,
    dry_run: bool = False,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    walks = extract_walks(manifest)
    digest = manifest_digest(manifest)

    if dry_run:
        load_driver_token(driver_token_file)  # validates the credential without sending it anywhere
        _, walks_by_id, pending_walks = _load_existing_and_pending(report_path, walks, digest)
        retryable = sum(1 for w in pending_walks if w["label"] in walks_by_id)
        return _dry_run_plan(
            manifest_path=manifest_path,
            report_path=report_path,
            digest=digest,
            total_walks=len(walks),
            never_attempted=len(pending_walks) - retryable,
            retryable_harness_reds=retryable,
            engine_verdicts_recorded=len(walks) - len(pending_walks),
            max_requests=max_requests,
            rate_per_minute=rate_per_minute,
            max_consecutive_harness_reds=max_consecutive_harness_reds,
        )

    lock = ReportLock(report_path)
    lock.acquire()
    try:
        existing, walks_by_id, pending_walks = _load_existing_and_pending(report_path, walks, digest)
        requests_used_total_before = (existing or {}).get("requests_used_total", 0)

        token = load_driver_token(driver_token_file)
        headers = {"Content-Type": "application/json", DRIVER_TOKEN_HEADER: token}

        report = existing or _new_report(
            manifest_path=manifest_path,
            digest=digest,
            total_walks=len(walks),
            url=url,
            max_requests=max_requests,
            rate_per_minute=rate_per_minute,
            max_consecutive_harness_reds=max_consecutive_harness_reds,
        )
        report["url"] = url
        report["max_requests"] = max_requests
        report["rate_per_minute"] = rate_per_minute
        report["max_consecutive_harness_reds"] = max_consecutive_harness_reds

        def _flush() -> None:
            report["walks"] = [walks_by_id[w["label"]] for w in walks if w["label"] in walks_by_id]
            report["requests_used_this_run"] = budget.used
            report["requests_used_total"] = requests_used_total_before + budget.used
            atomic_write_json(report_path, report)

        budget = RequestBudget(max_requests)
        limiter = RateLimiter(rate_per_minute)
        stopped_reason = "completed"
        consecutive_harness_reds = 0

        async with httpx.AsyncClient() as client:
            report["health"]["start"] = await _probe_health(client, health_url, timeout=timeout)
            _flush()

            for walk in pending_walks:
                result = await run_walk(
                    client,
                    walk,
                    url=url,
                    headers=headers,
                    timeout=timeout,
                    max_retries=max_retries,
                    backoff_seconds=backoff_seconds,
                    budget=budget,
                    limiter=limiter,
                )
                if result is None:
                    stopped_reason = "max_requests_exhausted"
                    break

                walks_by_id[result.walk_id] = _merge_attempt(walks_by_id.get(result.walk_id), result)
                _flush()

                if result.classification == "engine_verdict":
                    consecutive_harness_reds = 0
                    continue

                # W1 -- circuit breakers. 401/403 always stop immediately;
                # 429 keeps its own always-stops rule; everything else
                # accumulates toward max_consecutive_harness_reds.
                if result.http_status in _AUTH_CIRCUIT_BREAKER_STATUSES:
                    logger.error(
                        "circuit breaker: HTTP %s on walk=%s -- the token FILE is the likely "
                        "cause (never the token value itself); stopping after exactly one request.",
                        result.http_status,
                        result.walk_id,
                    )
                    stopped_reason = "auth_error_circuit_breaker"
                    break
                if result.harness_detail == "http_429":
                    stopped_reason = "rate_limited_harness_red"
                    break
                consecutive_harness_reds += 1
                if consecutive_harness_reds >= max_consecutive_harness_reds:
                    logger.error(
                        "circuit breaker: %d consecutive harness reds (latest: walk=%s detail=%s) "
                        "-- stopping.",
                        consecutive_harness_reds,
                        result.walk_id,
                        result.harness_detail,
                    )
                    stopped_reason = "consecutive_harness_reds_circuit_breaker"
                    break

            report["health"]["end"] = await _probe_health(client, health_url, timeout=timeout)

        report["stopped_reason"] = stopped_reason
        report["finished_at"] = _utcnow().isoformat()
        report["summary"] = _summarize(report["walks"], len(walks))
        _flush()
    finally:
        lock.release()
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Live runner for the B1 interview-space enumeration manifest: posts every "
            "covering walk to POST /api/visa-oracle/evaluate as traffic_source=synthetic_driver, "
            "bounded, rate-limited and circuit-broken, writing a resumable enumeration report."
        )
    )
    parser.add_argument("--manifest", required=True, help="Path to the B1 manifest JSON")
    parser.add_argument(
        "--report",
        required=True,
        help="Path to the enumeration report JSON (read to resume, rewritten after every walk)",
    )
    parser.add_argument("--url", default=os.environ.get(URL_ENV, DEFAULT_URL))
    parser.add_argument("--health-url", default=os.environ.get(HEALTH_URL_ENV, DEFAULT_HEALTH_URL))
    parser.add_argument(
        "--driver-token-file",
        default=os.environ.get(DRIVER_TOKEN_FILE_ENV, str(DEFAULT_DRIVER_TOKEN_FILE)),
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        default=None,
        help="Hard cap on HTTP attempts this run, retries included (required -- fail-closed, no default)",
    )
    parser.add_argument(
        "--rate-per-minute",
        type=float,
        default=DEFAULT_RATE_PER_MINUTE,
        help=f"Requests/minute ceiling, must stay below {RATE_CEILING_PER_MINUTE:g} (default {DEFAULT_RATE_PER_MINUTE:g})",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--backoff-seconds", type=float, default=DEFAULT_BACKOFF_SECONDS)
    parser.add_argument(
        "--max-consecutive-harness-reds",
        type=int,
        default=DEFAULT_MAX_CONSECUTIVE_HARNESS_REDS,
        help=(
            "Stop after this many CONSECUTIVE harness reds (401/403 and 429 have their own "
            f"always-stop rules and never consult this); >=1 and <= --max-requests "
            f"(default {DEFAULT_MAX_CONSECUTIVE_HARNESS_REDS})"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate input + budget and print the plan without any network call",
    )
    return parser


def _parse_args(argv: list[str]) -> argparse.Namespace:
    return _build_arg_parser().parse_args(argv)


def run(args: argparse.Namespace) -> int:
    try:
        validate_budget(args.max_requests, args.rate_per_minute, args.max_consecutive_harness_reds)
    except EnumerateLiveError as exc:
        logger.error("%s", exc)
        return 2

    try:
        result = asyncio.run(
            run_live_enumeration(
                manifest_path=Path(args.manifest),
                report_path=Path(args.report),
                url=args.url,
                health_url=args.health_url,
                driver_token_file=Path(args.driver_token_file).expanduser(),
                max_requests=args.max_requests,
                rate_per_minute=args.rate_per_minute,
                timeout=args.timeout,
                max_retries=args.max_retries,
                backoff_seconds=args.backoff_seconds,
                max_consecutive_harness_reds=args.max_consecutive_harness_reds,
                dry_run=args.dry_run,
            )
        )
    except ReportLockError as exc:
        logger.error("%s", exc)
        return 2
    except EnumerateLiveError as exc:
        logger.error("%s", exc)
        return 2

    if args.dry_run:
        print(
            "plan: pending={pending_walks} total={total_walks} already_recorded={already_recorded} "
            "never_attempted={never_attempted} retryable_harness_reds={retryable_harness_reds} "
            "max_requests={max_requests} rate_per_minute={rate_per_minute} "
            "max_consecutive_harness_reds={max_consecutive_harness_reds} "
            "health_probes_outside_budget={health_probes_outside_budget} "
            "estimated_minutes={estimated_minutes}".format(**result)
        )
        return 0

    print(
        "wrote {recorded}/{total} walks to {path} (stopped_reason={reason}, "
        "requests_used_this_run={this_run}, requests_used_total={total_requests})".format(
            recorded=len(result["walks"]),
            total=result["manifest_walk_count"],
            path=args.report,
            reason=result["stopped_reason"],
            this_run=result["requests_used_this_run"],
            total_requests=result["requests_used_total"],
        )
    )
    harness_red_count = sum(result["summary"]["harness_reds"].values())
    return 0 if harness_red_count == 0 and result["stopped_reason"] == "completed" else 1


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
