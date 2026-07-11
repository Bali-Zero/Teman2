"""Tests for organism_stale_detector — the heartbeat-channel watcher.

The detector is the RECEPTOR that ends the 28-day blindness (2026-06-28):
core organs ran green (launchd exit 0) while their heartbeat sidecar froze for
weeks, and nobody noticed because no guardian read the alert channel.

Contract (guilt + innocence, per cicatrix-superscar #2 antidote):
  - GUILT: an organ whose sidecar is older than its threshold is flagged STALE.
  - GUILT: an organ whose expected sidecar is MISSING is flagged DEAD-CHANNEL.
  - INNOCENCE: a fresh organ is NOT flagged.
  - SCHEMA-TOLERANT (superscar #9): both sidecar formats parse —
      A) {"ts": <float epoch>, "status": ...}            (~/scripts/_organism_lib.sh)
      B) {"ts": "<ISO8601 Z>", "status": ...}            (scripts/lib/heartbeat.sh)
  - ROBUST: a corrupt/unparseable sidecar is flagged (never silently skipped).
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from organism_stale_detector import (  # noqa: E402
    StaleFinding,
    scan_sidecars,
)


def _write(d, name, payload):
    p = os.path.join(d, f"{name}.json")
    with open(p, "w") as fh:
        fh.write(payload if isinstance(payload, str) else json.dumps(payload))
    return p


def test_fresh_organ_not_flagged(tmp_path):
    d = str(tmp_path)
    _write(d, "pro.fresh_organ", {"ts": time.time(), "status": "ok"})
    findings = scan_sidecars(d, stale_days=7)
    assert findings == [], f"fresh organ wrongly flagged: {findings}"


def test_stale_float_ts_flagged_guilt(tmp_path):
    d = str(tmp_path)
    old = time.time() - 28 * 86400
    _write(d, "pro.dlq_autopilot", {"ts": old, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7)
    assert len(findings) == 1
    f = findings[0]
    assert f.organ_id == "pro.dlq_autopilot"
    assert f.kind == "stale"
    assert 27 <= f.age_days <= 29, f.age_days


def test_stale_iso_ts_flagged_schema_tolerant(tmp_path):
    """Format B (ISO8601) must parse identically — superscar #9 guard."""
    d = str(tmp_path)
    iso_old = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 20 * 86400)
    )
    _write(d, "pro.sentinel", {"ts": iso_old, "status": "degraded"})
    findings = scan_sidecars(d, stale_days=7)
    assert len(findings) == 1
    assert findings[0].organ_id == "pro.sentinel"
    assert 19 <= findings[0].age_days <= 21


def test_corrupt_sidecar_flagged_not_skipped(tmp_path):
    """A guard that silently skips a broken sidecar is blind (#2)."""
    d = str(tmp_path)
    _write(d, "pro.broken", "{not valid json")
    findings = scan_sidecars(d, stale_days=7)
    assert len(findings) == 1
    assert findings[0].kind == "corrupt"


def test_innocence_many_fresh_one_stale(tmp_path):
    """The real shape: ~108 fresh, a handful stale — only the stale flagged."""
    d = str(tmp_path)
    now = time.time()
    for i in range(20):
        _write(d, f"pro.healthy_{i}", {"ts": now - 60, "status": "ok"})
    _write(d, "infra.pg_bridge_watchdog", {"ts": now - 22 * 86400, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7)
    assert len(findings) == 1
    assert findings[0].organ_id == "infra.pg_bridge_watchdog"


def test_threshold_boundary(tmp_path):
    """Just under threshold = innocent; just over = guilty."""
    d = str(tmp_path)
    now = time.time()
    _write(d, "pro.just_under", {"ts": now - 6 * 86400, "status": "ok"})
    _write(d, "pro.just_over", {"ts": now - 8 * 86400, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7)
    ids = {f.organ_id for f in findings}
    assert ids == {"pro.just_over"}


def test_missing_dir_returns_empty(tmp_path):
    findings = scan_sidecars(str(tmp_path / "does_not_exist"), stale_days=7)
    assert findings == []


def test_finding_is_serializable(tmp_path):
    d = str(tmp_path)
    _write(d, "pro.x", {"ts": time.time() - 30 * 86400, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7)
    blob = json.dumps([f.to_dict() for f in findings])
    assert "pro.x" in blob


# ---------------------------------------------------------------------------
# Status-aware detection (2026-06-28 extension): a fresh organ that reports
# status=failed/degraded is "breathing but crying". The receptor must surface
# the genuine ones WITHOUT injecting the known false-positives (organs
# intentionally disabled, decommissioned, or exit-1-by-design) the triage found
# — else every session gets alert-fatigue (the next blindness).
# ---------------------------------------------------------------------------

from organism_stale_detector import (  # noqa: E402
    KNOWN_BENIGN_FAILED,
    scan_sidecars_status,
)


def test_fresh_failed_organ_flagged_unhealthy(tmp_path):
    """GUILT: a fresh organ reporting failed (not in allow-list) is flagged."""
    d = str(tmp_path)
    _write(d, "mata_garuda.consumer_lag_check", {"ts": time.time(), "status": "failed"})
    findings = scan_sidecars_status(d, now=time.time())
    ids = {f.organ_id for f in findings if f.kind == "unhealthy"}
    assert "mata_garuda.consumer_lag_check" in ids


def test_fresh_ok_organ_not_flagged_unhealthy(tmp_path):
    """INNOCENCE: a fresh organ reporting ok is not an unhealthy finding."""
    d = str(tmp_path)
    _write(d, "pro.something", {"ts": time.time(), "status": "ok"})
    findings = scan_sidecars_status(d, now=time.time())
    assert [f for f in findings if f.kind == "unhealthy"] == []


def test_known_benign_failed_suppressed(tmp_path):
    """INNOCENCE: an intentionally-disabled organ reporting failed is NOT flagged.

    These are the false-positives from the triage (codex.spark_*, decommissioned
    wr2 organs, by-design exit-1 auditors). Flagging them = alert-fatigue = the next
    blindness. The allow-list must suppress them.
    """
    d = str(tmp_path)
    for organ in ("codex.spark_loop", "wr2.telegram_gate", "pro.audit_launchd_daily"):
        _write(d, organ, {"ts": time.time(), "status": "failed"})
    findings = scan_sidecars_status(d, now=time.time())
    flagged = {f.organ_id for f in findings if f.kind == "unhealthy"}
    assert flagged == set(), f"benign organs wrongly flagged: {flagged}"


def test_degraded_status_flagged(tmp_path):
    """degraded (not just failed) is also surfaced if not benign."""
    d = str(tmp_path)
    _write(d, "pro.real_degraded", {"ts": time.time(), "status": "degraded"})
    findings = scan_sidecars_status(d, now=time.time())
    assert any(f.organ_id == "pro.real_degraded" and f.kind == "unhealthy" for f in findings)


def test_stale_failed_not_double_counted(tmp_path):
    """A STALE failed organ is a stale finding, not also an unhealthy one.

    Stale dominates: if it hasn't breathed in days, the heartbeat-channel problem
    is the headline, not the last-reported status."""
    d = str(tmp_path)
    old = time.time() - 30 * 86400
    _write(d, "pro.old_and_failed", {"ts": old, "status": "failed"})
    findings = scan_sidecars_status(d, now=time.time())
    kinds = {f.kind for f in findings if f.organ_id == "pro.old_and_failed"}
    assert kinds == {"stale"}, f"expected only stale, got {kinds}"


def test_allow_list_is_documented_not_empty():
    """The allow-list must be non-empty (the triage found several) and each entry
    should be a real organ_id string, so drift is auditable."""
    assert isinstance(KNOWN_BENIGN_FAILED, (set, frozenset, tuple))
    assert len(KNOWN_BENIGN_FAILED) >= 6
    assert "codex.spark_loop" in KNOWN_BENIGN_FAILED


def test_ollama_pro_program_path_collision_suppressed(tmp_path):
    """INNOCENCE: infra.ollama_pro reports failed (launchd exit 1) while the daemon
    is actually alive — the launchd job binds the same :11434 the real `ollama serve`
    already owns, so it exits 1 and keepalive re-spawns forever. The bridge tags it
    'failed' from the launchd exit code, but the organ breathes (6 models served on
    :11434). This is the same family as the other bridge false-positives: a non-zero
    launchd exit that does NOT mean the organ is dead. (Live triage 2026-06-28.)
    """
    d = str(tmp_path)
    _write(
        d,
        "infra.ollama_pro",
        {"ts": time.time(), "status": "failed", "last_error": "daemon not running"},
    )
    findings = scan_sidecars_status(d, now=time.time())
    flagged = {f.organ_id for f in findings if f.kind == "unhealthy"}
    assert "infra.ollama_pro" not in flagged, f"ollama false-positive not suppressed: {flagged}"
