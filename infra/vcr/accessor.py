"""infra/vcr/accessor.py — the ONE enforced entry point (R1/R2/R6/§5.4).

Consumers never read ~/.organism/arsenal/last.json or the VCR observation log
directly — they call get_state(seat, host, auth_context). Fails CLOSED: any
axis outside {truth=TRUE, freshness=CURRENT, coverage=PRESENT, verifier=HEALTHY}
is a real, explicit non-healthy state — never silently promoted to healthy.

Dedup rule (load-bearing, see records.ClaimObservation.source_report_ts): a new
observation is appended ONLY when the underlying arsenal_probe report's own
`ts` differs from the last stored observation's source_report_ts. A cache-only
re-read of the SAME report must never append again — otherwise repeated reads
of one flaky probe result would fake the "2 consecutive observations" the
materializer's hysteresis debounce exists to require (R2).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

try:
    import fcntl  # POSIX-only (macOS/Linux) — matches the rest of this stack
except ImportError:  # pragma: no cover — defensive, never expected on this fleet
    fcntl = None

from infra.vcr import store
from infra.vcr.materializer import derive_truth_state
from infra.vcr.records import (
    CURRENT,
    EXPIRED,
    FALSE,
    HEALTHY,
    ClaimContext,
    ClaimObservation,
    MaterializedState,
    MISSING,
    PRESENT,
    STALE,
    TRUE,
    UNVERIFIED,
)
from infra.vcr.registry import ExpectedClaim, load_registry, lookup
from infra.vcr.verifier import check_verifier

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARSENAL_PROBE_PATH = REPO_ROOT / "scripts" / "arsenal_probe.py"
ARSENAL_REPORT_PATH_DEFAULT = Path.home() / ".organism" / "arsenal" / "last.json"


class UnregisteredClaimError(ValueError):
    """(seat, host, auth_context) is not in the expected-claim registry — a
    caller error distinct from a registered claim with no observations yet
    (that is coverage_state=MISSING, not an exception)."""


def local_machine_label(prober_path: Path = ARSENAL_PROBE_PATH) -> str:
    """Reuse arsenal_probe's own machine detection — two tools that must agree
    on 'what machine is this' must not invent two independent answers."""
    spec = importlib.util.spec_from_file_location("arsenal_probe", prober_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.machine_label()


def _read_report(report_path: Path) -> Optional[dict]:
    if not report_path.is_file():
        return None
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _seat_entry(report: Optional[dict], seat: str) -> Optional[dict]:
    if not report:
        return None
    for s in report.get("seats", []):
        if s.get("seat") == seat:
            return s
    return None


def derive_freshness(age_s: Optional[float], ttl_s: int) -> str:
    """CURRENT within TTL, STALE up to 3x TTL, EXPIRED beyond that or absent."""
    if age_s is None:
        return EXPIRED
    if age_s <= ttl_s:
        return CURRENT
    if age_s <= ttl_s * 3:
        return STALE
    return EXPIRED


def _report_age_s(report: Optional[dict], report_path: Path, now_ts: float) -> Optional[float]:
    """Freshness is measured from the report's OWN `ts` field (content) — never
    filesystem mtime, which is a PROXY that a copy/touch can promote to
    "fresh" while the underlying content stays stale (scar #9, the same
    disease as W88/W106: verify by content, never by proxy — Codex red-team,
    2026-08-03). Falls back to mtime only when the report is unreadable or
    genuinely lacks a parseable `ts` (defense for a malformed/legacy file)."""
    if report:
        ts_raw = report.get("ts")
        if ts_raw:
            try:
                dt = datetime.strptime(str(ts_raw), "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
                return now_ts - dt.timestamp()
            except ValueError:
                pass  # unparseable ts — fall through to mtime
    if report_path.is_file():
        return now_ts - report_path.stat().st_mtime
    return None


def default_run_probe(seat: str, timeout_s: float, prober_path: Path = ARSENAL_PROBE_PATH) -> int:
    """Triggers a live arsenal_probe re-check for exactly one seat. Returns exit code."""
    try:
        proc = subprocess.run(
            [sys.executable, str(prober_path), "--seats", seat, "--quiet"],
            capture_output=True, text=True, timeout=timeout_s,
        )
        return proc.returncode
    except subprocess.TimeoutExpired:
        return -1


def _dedup_key(report_ts: str, entry: dict) -> str:
    """The dedup key is normally the report's own `ts`. A report lacking `ts`
    must NOT collapse to a single empty-string key for every read — two
    distinct raw entries (e.g. LIVE then AUTH_DEAD) both missing `ts` would
    otherwise be read as "the same report" and the second, genuinely new,
    observation would silently never be logged (Codex red-team,
    2026-08-03: dedup must key off CONTENT, never an absent proxy — scar
    #9). Falls back to a content hash of the seat entry itself."""
    if report_ts:
        return report_ts
    digest = hashlib.sha256(json.dumps(entry, sort_keys=True).encode("utf-8")).hexdigest()
    return f"nocontentts:{digest[:16]}"


def _maybe_append(
    seat: str, context: ClaimContext, entry: dict, report_ts: str, now_ts: float
) -> None:
    """Appends a new observation ONLY if the report's dedup key differs from
    the last logged observation's (dedup rule, see module docstring).

    Locked (flock) around the read-then-append critical section: two
    concurrent cache-only callers (e.g. an interactive `cli.py check` and a
    cron'd proprioception sweep) racing this check-and-append without a lock
    could both read the same "last observation" and both append — faking a
    second hysteresis-confirming sample from ONE real probe event (Codex
    red-team, 2026-08-03, reproduced live: a single report produced two
    "new,new" rows under concurrent callers)."""
    dedup_key = _dedup_key(report_ts, entry)
    log_path = store.log_path(seat, context)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = log_path.with_suffix(log_path.suffix + ".lock")

    def _do_append() -> None:
        existing, _errors = store.read_observations(seat, context, limit=1)
        if existing and existing[-1].source_report_ts == dedup_key:
            return
        raw_status = entry.get("status", "UNKNOWN_ERR")
        obs = ClaimObservation(
            claim_id=f"{seat}::{context.key()}",
            claim_type="seat_health",
            subject_id=seat,
            context=context,
            observed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts)),
            raw_status=raw_status,
            raw_evidence=entry.get("evidence", ""),
            latency_ms=int(entry.get("latency_ms", 0)),
            truth_state=(TRUE if raw_status == "LIVE" else FALSE),
            truth_reason=f"observed report ts={report_ts or '(missing, content-hash dedup)'}",
            source_report_ts=dedup_key,
        )
        store.append_observation(obs)

    if fcntl is None:  # pragma: no cover — non-POSIX defensive fallback
        _do_append()
        return
    with open(lock_path, "a", encoding="utf-8") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        try:
            _do_append()
        finally:
            fcntl.flock(lockfile, fcntl.LOCK_UN)


def get_state(
    seat: str,
    host: str,
    auth_context: str,
    allow_probe: bool = True,
    *,
    registry: Optional[list[ExpectedClaim]] = None,
    report_path: Optional[Path] = None,
    prober_path: Path = ARSENAL_PROBE_PATH,
    now: Optional[float] = None,
    run_probe_fn: Callable[[str, float, Path], int] = default_run_probe,
    machine_label_fn: Callable[[Path], str] = local_machine_label,
    check_verifier_fn: Callable[[Path, Optional[str]], tuple[str, str]] = check_verifier,
) -> MaterializedState:
    reg = registry if registry is not None else load_registry()
    claim = lookup(reg, seat, host, auth_context)
    context = ClaimContext(host=host, auth_context=auth_context)
    if claim is None:
        raise UnregisteredClaimError(
            f"({seat}, {host}, {auth_context}) is not in the expected-claim registry"
        )

    verifier_state, verifier_detail = check_verifier_fn(prober_path, claim.certified_hash)

    if verifier_state != HEALTHY:
        # Return BEFORE calling machine_label_fn (imports+execs the prober
        # module) or run_probe_fn (subprocess-execs it again) — checking the
        # hash and THEN running the file anyway defeats the entire point of
        # the check (Codex red-team, 2026-08-03: the old code ran both
        # regardless of verifier_state). verifier.py's own docstring: "NO
        # observation from this run can be trusted, regardless of what the
        # raw probe returned" — that has to mean before-execution, not just
        # a field in the returned state.
        return MaterializedState(
            seat=seat, context=context, truth_state=UNVERIFIED, freshness_state=EXPIRED,
            coverage_state=MISSING, verifier_state=verifier_state, reason=verifier_detail,
            observed_at=None,
        )

    local_machine = machine_label_fn(prober_path)
    if host != local_machine:
        return MaterializedState(
            seat=seat, context=context, truth_state=UNVERIFIED, freshness_state=EXPIRED,
            coverage_state=MISSING, verifier_state=verifier_state,
            reason=(
                f"host '{host}' != this machine ('{local_machine}') — remote-context "
                "resolution is out of scope for this pilot; cannot verify from here"
            ),
            observed_at=None,
        )

    now_ts = now if now is not None else time.time()
    report_p = report_path or ARSENAL_REPORT_PATH_DEFAULT
    report = _read_report(report_p)
    age_s = _report_age_s(report, report_p, now_ts)
    freshness = derive_freshness(age_s, claim.ttl_s)
    entry = _seat_entry(report, seat)

    if (entry is None or freshness != CURRENT) and allow_probe:
        run_probe_fn(seat, claim.latency_budget_ms / 1000.0, prober_path)
        report = _read_report(report_p)
        age_s = _report_age_s(report, report_p, now_ts)
        freshness = derive_freshness(age_s, claim.ttl_s)
        entry = _seat_entry(report, seat)

    if entry is None:
        return MaterializedState(
            seat=seat, context=context, truth_state=UNVERIFIED, freshness_state=freshness,
            coverage_state=MISSING, verifier_state=verifier_state,
            reason="no observation for this seat exists yet on this machine",
            observed_at=None,
        )

    report_ts = str(report.get("ts", "")) if report else ""
    _maybe_append(seat, context, entry, report_ts, now_ts)

    # Full history, NOT a windowed slice (R2 fix, Codex red-team 2026-08-03):
    # derive_truth_state() treats observations[0] as the debounce baseline
    # with no prior history — a fixed limit=20 slid the window forward on
    # every new sample, silently discarding whatever had been confirmed
    # before it, and could flip the reported truth_state on a single new
    # observation in the OPPOSITE direction from what that observation said
    # (reproduced live: TFTF...TF confirmed TRUE, +1 new TRUE -> FALSE).
    # Bounded here by pilot scope (3 seats, append only on report ts change
    # per the dedup rule above) — a rollout beyond "one pilot" would need a
    # persisted-checkpoint materializer instead of a full-history re-fold.
    observations, _obs_errors = store.read_observations(seat, context, limit=None)
    truth_state, truth_reason = derive_truth_state(observations)

    reason = truth_reason
    if _obs_errors:
        reason = f"{reason}; {len(_obs_errors)} corrupt observation log line(s) skipped"
    return MaterializedState(
        seat=seat, context=context, truth_state=truth_state, freshness_state=freshness,
        coverage_state=PRESENT, verifier_state=verifier_state, reason=reason,
        observed_at=observations[-1].observed_at if observations else None,
    )
