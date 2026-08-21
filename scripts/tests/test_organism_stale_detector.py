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
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from organism_stale_detector import (  # noqa: E402
    scan_sidecars,
    sync_cross_host_sidecars,
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
    findings = scan_sidecars(d, stale_days=7, host="nuzantara")
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
    findings = scan_sidecars(d, stale_days=7, host="nuzantara")
    assert len(findings) == 1
    assert findings[0].organ_id == "pro.sentinel"
    assert 19 <= findings[0].age_days <= 21


def test_corrupt_sidecar_flagged_not_skipped(tmp_path):
    """A guard that silently skips a broken sidecar is blind (#2)."""
    d = str(tmp_path)
    _write(d, "pro.broken", "{not valid json")
    findings = scan_sidecars(d, stale_days=7, host="nuzantara")
    assert len(findings) == 1
    assert findings[0].kind == "corrupt"


def test_innocence_many_fresh_one_stale(tmp_path):
    """The real shape: ~108 fresh, a handful stale — only the stale flagged."""
    d = str(tmp_path)
    now = time.time()
    for i in range(20):
        _write(d, f"pro.healthy_{i}", {"ts": now - 60, "status": "ok"})
    _write(d, "infra.pg_bridge_watchdog", {"ts": now - 22 * 86400, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7, host="nuzantara")
    assert len(findings) == 1
    assert findings[0].organ_id == "infra.pg_bridge_watchdog"


def test_threshold_boundary(tmp_path):
    """Just under threshold = innocent; just over = guilty."""
    d = str(tmp_path)
    now = time.time()
    _write(d, "pro.just_under", {"ts": now - 6 * 86400, "status": "ok"})
    _write(d, "pro.just_over", {"ts": now - 8 * 86400, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7, host="nuzantara")
    ids = {f.organ_id for f in findings}
    assert ids == {"pro.just_over"}


def test_missing_dir_returns_empty(tmp_path):
    findings = scan_sidecars(str(tmp_path / "does_not_exist"), stale_days=7)
    assert findings == []


# ---------------------------------------------------------------------------
# .worktrees/-sourced runtime-stamp exemption (sibling fix to
# organism_digest.py::stale_heartbeats(), PR #3486 2026-07-30). That PR patched
# only organism_digest.py; this detector reads the same ~/.organism/last_seen/
# sidecars and had the identical bug — found live 2026-08-02 via proprioception
# on Mini: wr2.html_apply.runtime flagged "stale 7.4d" from a reaped
# .worktrees/docs-inventory-check-blocker2-surgical-0725 stamp while the
# canonical Pro deploy-clone's own stamp was minutes old.
# ---------------------------------------------------------------------------


def test_innocence_worktree_sourced_stamp_not_flagged_stale(tmp_path):
    """A wr2_runtime_stamp whose `checkout` is under .worktrees/ is a one-off
    stamp from a reaped ephemeral agent sandbox — its mtime aging forever is
    not a broken promise, so it must NOT be flagged stale."""
    d = str(tmp_path)
    old = time.time() - 30 * 86400
    _write(
        d, "wr2.html_apply.runtime",
        {
            "ts": old,
            "status": "ok",
            "checkout": "/Users/nuzantara/nuzantara/.worktrees/some-reaped-lane",
        },
    )
    findings = scan_sidecars(d, stale_days=7)
    assert findings == [], f"worktree-sourced stamp wrongly flagged: {findings}"


def test_guilt_canonical_checkout_stamp_still_flags_stale(tmp_path):
    """Same organ, but stamped from a CANONICAL (non-worktree) checkout — e.g.
    the real deploy-clone daemon — must still flag when stale. Proves the
    exemption is scoped to .worktrees/, not to any file carrying a `checkout`
    field."""
    d = str(tmp_path)
    old = time.time() - 30 * 86400
    _write(
        d, "wr2.html_apply.runtime",
        {"ts": old, "status": "ok", "checkout": "/Users/nuzantara/nuzantara-deploy"},
    )
    findings = scan_sidecars(d, stale_days=7)
    assert len(findings) == 1
    assert findings[0].organ_id == "wr2.html_apply.runtime"
    assert findings[0].kind == "stale"


# ---------------------------------------------------------------------------
# arsenal_probe non-primary-node exemption (sibling fix to organism_digest.py::
# stale_heartbeats()'s existing ARSENAL_PROBE_PRIMARY_NODE check — same class
# as the .worktrees/ exemption above). docs/runbooks/arsenal-probe.md §How it
# is armed: only Mini has a recurring healer-armed refresh; M5/Pro reports are
# on-demand only (a manual `--table` run or infra/vcr/cli.py's `check` path).
# organism_digest.py already skips m5/pro's arsenal_probe stamp when computing
# its "silent Nh" digest line; this detector read the SAME sidecar dir with the
# SAME blanket 7-day rule and had no such exemption — found live 2026-08-21 when
# m5.arsenal_probe.json (last refreshed 2026-08-12, 8.7d old) was reported as a
# dead cron even though no cron for it has ever existed on M5 (CLAUDE.md: M5 has
# no daemon/cron H24 by design).
# ---------------------------------------------------------------------------


def test_innocence_m5_arsenal_probe_stamp_not_flagged_stale(tmp_path):
    """M5's arsenal_probe heartbeat has no recurring promise — an old stamp is
    an unrefreshed on-demand snapshot, not a broken cron, and must NOT flag."""
    d = str(tmp_path)
    old = time.time() - 9 * 86400
    _write(d, "m5.arsenal_probe", {"ts": old, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7)
    assert findings == [], f"m5 arsenal_probe stamp wrongly flagged stale: {findings}"


def test_guilt_mini_arsenal_probe_stamp_still_flags_stale(tmp_path):
    """Mini IS the primary/healer-armed node — its stamp going stale for 9 days
    IS a broken promise and must still flag. Proves the exemption is scoped to
    the non-primary machine, not to the arsenal_probe organ family at large."""
    d = str(tmp_path)
    old = time.time() - 9 * 86400
    _write(d, "mini.arsenal_probe", {"ts": old, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7, host="mini-pro2")
    assert len(findings) == 1
    assert findings[0].organ_id == "mini.arsenal_probe"
    assert findings[0].kind == "stale"


def test_innocence_pro_arsenal_probe_stamp_not_flagged_stale(tmp_path):
    """Pro is also non-primary per the runbook — same exemption applies."""
    d = str(tmp_path)
    old = time.time() - 9 * 86400
    _write(d, "pro.arsenal_probe", {"ts": old, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7, host="nuzantara")
    assert findings == [], f"pro arsenal_probe stamp wrongly flagged stale: {findings}"


def test_innocence_unrelated_organ_named_like_arsenal_probe_prefix_still_flags(tmp_path):
    """The stem regex is anchored (^...$) — an unrelated organ that merely
    starts with a machine label must not accidentally match and get exempted."""
    d = str(tmp_path)
    old = time.time() - 9 * 86400
    _write(d, "m5.arsenal_probe_extra", {"ts": old, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7)
    assert len(findings) == 1
    assert findings[0].organ_id == "m5.arsenal_probe_extra"


def test_finding_is_serializable(tmp_path):
    d = str(tmp_path)
    _write(d, "pro.x", {"ts": time.time() - 30 * 86400, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7, host="nuzantara")
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
    findings = scan_sidecars_status(d, now=time.time(), host="nuzantara")
    assert any(f.organ_id == "pro.real_degraded" and f.kind == "unhealthy" for f in findings)


def test_stale_failed_not_double_counted(tmp_path):
    """A STALE failed organ is a stale finding, not also an unhealthy one.

    Stale dominates: if it hasn't breathed in days, the heartbeat-channel problem
    is the headline, not the last-reported status."""
    d = str(tmp_path)
    old = time.time() - 30 * 86400
    _write(d, "pro.old_and_failed", {"ts": old, "status": "failed"})
    findings = scan_sidecars_status(d, now=time.time(), host="nuzantara")
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


# --- cross-host sidecar sync (2026-07-17, PENDING-ARMS "infra.eventbus_redis_mini
# heartbeat frozen 7.9d"): infra.eventbus_redis_mini is probed and written by a
# cron resident on Pro, never on Mini — Mini's local sidecar could freeze forever
# with nothing local able to refresh it. sync_cross_host_sidecars() closes that
# gap with a read-only ssh pull. All ssh calls are mocked: never touch a real
# network in this suite. ---


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


def test_cross_host_sync_guilt_refreshes_stale_local_mirror(tmp_path, monkeypatch):
    """GUILT: a blind-host mirror older than the refresh interval is replaced by
    the fresher remote receipt — the actual cure for the frozen-heartbeat bug."""
    d = str(tmp_path)
    old_ts = time.time() - 999_999
    p = _write(
        d, "infra.eventbus_redis_mini",
        {"organ_id": "infra.eventbus_redis_mini", "ts": old_ts, "status": "ok"},
    )
    os.utime(p, (old_ts, old_ts))

    fresh_ts = time.time()
    remote_payload = json.dumps(
        {"organ_id": "infra.eventbus_redis_mini", "ts": fresh_ts, "status": "ok"}
    )
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _FakeCompletedProcess(returncode=0, stdout=remote_payload)

    monkeypatch.setattr(subprocess, "run", fake_run)

    sync_cross_host_sidecars(d, host="mini-pro2", now=fresh_ts)

    assert len(calls) == 1
    with open(p, encoding="utf-8") as fh:
        written = json.load(fh)
    assert written["ts"] == fresh_ts

    # the whole point: scan_sidecars must now see it as fresh, not stale.
    findings = scan_sidecars(d, stale_days=7, now=fresh_ts)
    assert findings == [], f"still flagged stale after sync: {findings}"


def test_cross_host_sync_guilt_creates_missing_local_mirror(tmp_path, monkeypatch):
    """GUILT: no local sidecar at all is also worth fetching, not just a stale one."""
    d = str(tmp_path)
    fresh_ts = time.time()
    remote_payload = json.dumps(
        {"organ_id": "infra.eventbus_redis_mini", "ts": fresh_ts, "status": "ok"}
    )
    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, **kw: _FakeCompletedProcess(returncode=0, stdout=remote_payload),
    )

    sync_cross_host_sidecars(d, host="mini-pro2", now=fresh_ts)

    local_path = os.path.join(d, "infra.eventbus_redis_mini.json")
    assert os.path.exists(local_path)
    with open(local_path, encoding="utf-8") as fh:
        assert json.load(fh)["ts"] == fresh_ts


def test_cross_host_sync_innocence_fresh_mirror_skips_ssh(tmp_path, monkeypatch):
    """INNOCENCE: a mirror refreshed within the last cycle must not trigger an ssh
    round-trip on every single invocation (the SessionStart-hook-adjacent path)."""
    d = str(tmp_path)
    now = time.time()
    _write(
        d, "infra.eventbus_redis_mini",
        {"organ_id": "infra.eventbus_redis_mini", "ts": now, "status": "ok"},
    )
    calls = []
    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, **kw: calls.append(cmd) or _FakeCompletedProcess(),
    )

    sync_cross_host_sidecars(d, host="mini-pro2", now=now, min_interval_sec=240.0)

    assert calls == [], "ssh invoked despite an already-fresh local mirror"


def test_cross_host_sync_innocence_non_blind_host_is_noop(tmp_path, monkeypatch):
    """INNOCENCE: running on Pro (the host that already writes this organ's
    receipt locally) must never shell out — this is a Mini-only blind spot."""
    d = str(tmp_path)
    calls = []
    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, **kw: calls.append(cmd) or _FakeCompletedProcess(),
    )

    sync_cross_host_sidecars(d, host="nuzantara")

    assert calls == []


def test_cross_host_sync_graceful_on_ssh_failure(tmp_path, monkeypatch):
    """A failed ssh pull (unreachable host, no key, etc.) must never clobber the
    existing local file — scan_sidecars still reports it honestly as stale."""
    d = str(tmp_path)
    old_ts = time.time() - 999_999
    p = _write(
        d, "infra.eventbus_redis_mini",
        {"organ_id": "infra.eventbus_redis_mini", "ts": old_ts, "status": "ok"},
    )
    os.utime(p, (old_ts, old_ts))
    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, **kw: _FakeCompletedProcess(returncode=255, stdout=""),
    )

    sync_cross_host_sidecars(d, host="mini-pro2", now=time.time())

    with open(p, encoding="utf-8") as fh:
        assert json.load(fh)["ts"] == old_ts


def test_cross_host_sync_graceful_on_bad_json(tmp_path, monkeypatch):
    """A remote receipt that fails to parse must never clobber the existing
    local file either — same graceful-degradation contract as an ssh failure."""
    d = str(tmp_path)
    old_ts = time.time() - 999_999
    p = _write(
        d, "infra.eventbus_redis_mini",
        {"organ_id": "infra.eventbus_redis_mini", "ts": old_ts, "status": "ok"},
    )
    os.utime(p, (old_ts, old_ts))
    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, **kw: _FakeCompletedProcess(returncode=0, stdout="not-json{{{"),
    )

    sync_cross_host_sidecars(d, host="mini-pro2", now=time.time())

    with open(p, encoding="utf-8") as fh:
        assert json.load(fh)["ts"] == old_ts


def test_cross_host_sync_graceful_on_timeout(tmp_path, monkeypatch):
    """An ssh call that times out must be caught, not propagate — the caller
    (organism_stale_detector's main(), potentially SessionStart-adjacent) must
    never crash or hang because Pro is unreachable."""
    d = str(tmp_path)
    old_ts = time.time() - 999_999
    p = _write(
        d, "infra.eventbus_redis_mini",
        {"organ_id": "infra.eventbus_redis_mini", "ts": old_ts, "status": "ok"},
    )
    os.utime(p, (old_ts, old_ts))

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=3)

    monkeypatch.setattr(subprocess, "run", fake_run)

    sync_cross_host_sidecars(d, host="mini-pro2", now=time.time())

    with open(p, encoding="utf-8") as fh:
        assert json.load(fh)["ts"] == old_ts


# ---------------------------------------------------------------------------
# Jurisdiction scoping (2026-08-07): scan_sidecars() read every file in the
# local ~/.organism/last_seen/ with no host/jurisdiction scoping, so a Pro
# sidecar orphaned on M5 since 2026-07-21 (pro.translate_hourly, frozen wall-
# clock, never refreshed by anything on M5) reported "heartbeat frozen 17.0d"
# as a phantom P1 while the real Pro organ ran fine that same day. Straight
# port of proprioception.py::probe_guardian_freshness()'s per-item machine
# scoping (same 2026-07-17 "jurisdiction, not divergence" lesson).
# ---------------------------------------------------------------------------

from organism_stale_detector import _is_foreign_jurisdiction, _machine_label  # noqa: E402


def test_guilt_pro_sidecar_orphaned_on_m5_not_flagged(tmp_path):
    """GUILT (of the OLD code / innocence of the NEW code): a pro.* sidecar
    frozen 17d, present in the local last_seen dir, must NOT be reported when
    running on M5 — it is not M5's organ to judge (jurisdiction, not
    divergence). This is the exact live shape of pro.translate_hourly.json."""
    d = str(tmp_path)
    old = time.time() - 17 * 86400
    _write(d, "pro.translate_hourly", {"ts": old, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7, host="air-m5")
    assert findings == [], f"foreign-host sidecar wrongly flagged on M5: {findings}"


def test_guilt_pro_sidecar_still_flags_on_pro(tmp_path):
    """GUILT (of the finding surviving): the SAME frozen pro.* sidecar MUST
    still be reported when scanned from Pro itself — jurisdiction skip must
    not silently delete a real alarm on the machine that owns it."""
    d = str(tmp_path)
    old = time.time() - 17 * 86400
    _write(d, "pro.translate_hourly", {"ts": old, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7, host="nuzantara")
    assert len(findings) == 1
    assert findings[0].organ_id == "pro.translate_hourly"
    assert findings[0].kind == "stale"


def test_innocence_cross_host_allowlisted_organ_still_flags_on_m5(tmp_path):
    """INNOCENCE (the W94 under-match twin): infra.eventbus_redis_mini is the
    one legitimately cross-host-mirrored organ (CROSS_HOST_SIDECAR_SOURCES) —
    silencing it via the new jurisdiction skip would be exactly the under-match
    failure mode this repo has scarred on before. It must STILL be flagged
    stale on M5 even though its organ_id prefix ("infra.") resolves to "pro"."""
    d = str(tmp_path)
    old = time.time() - 30 * 86400
    _write(d, "infra.eventbus_redis_mini", {"ts": old, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7, host="air-m5")
    assert len(findings) == 1
    assert findings[0].organ_id == "infra.eventbus_redis_mini"


def test_innocence_m5_own_sidecar_still_flags_on_m5(tmp_path):
    """INNOCENCE: an m5.* sidecar scanned on M5 is squarely in-jurisdiction —
    the new skip must never suppress a machine's own organs.

    Deliberately NOT named "m5.arsenal_probe" here: that specific organ_id
    is now exempt on its own separate grounds (the arsenal_probe
    non-primary-node exemption above, 2026-08-21) regardless of jurisdiction
    — using it would conflate two independent exemptions in one assertion.
    """
    d = str(tmp_path)
    old = time.time() - 30 * 86400
    _write(d, "m5.some_other_organ", {"ts": old, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7, host="air-m5")
    assert len(findings) == 1
    assert findings[0].organ_id == "m5.some_other_organ"


def test_innocence_unrecognised_prefix_keeps_reporting(tmp_path):
    """INNOCENCE: attribute-or-report, never attribute-or-drop. An organ_id
    whose prefix isn't in ORGAN_PREFIX_HOST (or has no prefix at all) is not
    evidence the sidecar is foreign — today's behaviour (report it) must be
    unchanged regardless of which machine is scanning."""
    d = str(tmp_path)
    old = time.time() - 30 * 86400
    _write(d, "auth-sentinel", {"ts": old, "status": "ok"})
    _write(d, "wr2.html_apply.runtime", {"ts": old, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7, host="air-m5")
    ids = {f.organ_id for f in findings}
    assert ids == {"auth-sentinel", "wr2.html_apply.runtime"}


def test_scan_sidecars_status_does_not_reclassify_foreign_stale_as_unhealthy(tmp_path):
    """GUILT of the two-loop consistency fix: scan_sidecars_status() must skip
    a foreign-jurisdiction sidecar in ITS OWN unhealthy loop too — otherwise a
    clean jurisdiction skip in scan_sidecars() turns into a misclassified
    'unhealthy' finding one loop later (worse than the original bug: it fires
    on the SAME data with a DIFFERENT, less legible verdict)."""
    from organism_stale_detector import scan_sidecars_status

    d = str(tmp_path)
    _write(d, "pro.some_failed_organ", {"ts": time.time(), "status": "failed"})
    findings = scan_sidecars_status(d, now=time.time(), host="air-m5")
    assert findings == [], f"foreign sidecar reclassified as unhealthy: {findings}"


def test_machine_label_recognises_all_three_hosts():
    assert _machine_label("air-m5") == "m5"
    assert _machine_label("Air-M5.local") == "m5"
    assert _machine_label("mini-pro2") == "mini"
    assert _machine_label("nuzantara") == "pro"
    assert _machine_label("some-ci-runner") == "some-ci-runner"


def test_is_foreign_jurisdiction_unit():
    assert _is_foreign_jurisdiction("pro.translate_hourly", "m5") is True
    assert _is_foreign_jurisdiction("pro.translate_hourly", "pro") is False
    assert _is_foreign_jurisdiction("infra.eventbus_redis_mini", "m5") is False
    assert _is_foreign_jurisdiction("m5.arsenal_probe", "m5") is False
    assert _is_foreign_jurisdiction("auth-sentinel", "m5") is False
