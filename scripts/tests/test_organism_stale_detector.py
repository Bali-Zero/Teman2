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
    # host pinned to Pro: without it this reads as innocent on any non-Pro host
    # because the organ is dropped as foreign BEFORE the freshness logic runs —
    # the assertion would then be satisfied by jurisdiction, not by freshness.
    findings = scan_sidecars(d, stale_days=7, host="nuzantara")
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
    # host pinned to M5, or jurisdiction drops the organ first and this passes
    # even with the arsenal_probe exemption block deleted outright.
    findings = scan_sidecars(d, stale_days=7, host="air-m5")
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
    starts with a machine label must not accidentally match and get exempted.

    `host` is pinned because the subject is an `m5.`-prefixed organ: without it
    the call inherits socket.gethostname(), so the test asserted the anchored
    regex ONLY on M5 and elsewhere asserted nothing — on Pro, on Mini and on any
    CI runner the organ is out-of-jurisdiction, scan_sidecars skips it before the
    regex is ever consulted, and `len(findings) == 1` fails. Green on exactly one
    machine in the fleet from the day it was written (2026-08-20, #4467) — NOT
    from 2026-08-07, which is when the jurisdiction MECHANISM landed (111049e8c);
    an earlier draft of this note conflated the two, and a fact-check caught it.
    Either way it was invisible, because no workflow named this corpus; the
    arming step added in this PR failed on its first real run and produced this.
    Pinning restores what the docstring claims to test.
    """
    d = str(tmp_path)
    old = time.time() - 9 * 86400
    _write(d, "m5.arsenal_probe_extra", {"ts": old, "status": "ok"})
    findings = scan_sidecars(d, stale_days=7, host="air-m5")
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
    # host pinned: otherwise the organ is foreign and never reaches the
    # status check this test exists to exercise.
    findings = scan_sidecars_status(d, now=time.time(), host="nuzantara")
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
    # host pinned to Pro for the third fixture: unpinned, pro.audit_launchd_daily
    # is dropped as foreign before the allow-list is consulted, so removing it
    # from KNOWN_BENIGN_FAILED would not be caught here.
    findings = scan_sidecars_status(d, now=time.time(), host="nuzantara")
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
    # host pinned: `infra.` maps to Pro, so unpinned this suppression test is
    # satisfied by jurisdiction on every other host.
    findings = scan_sidecars_status(d, now=time.time(), host="nuzantara")
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


# ---------------------------------------------------------------------------
# 2026-08-22 — `warning` was a note to nobody, and the note itself was dropped.
#
# Measured on the live fleet the day these landed: three organs write
# status="warning" (one per node) and this reader knew none of them; and 57 of
# the 58 note-bearing sidecars put `note` at the TOP level while the reader
# looked only under `metadata`. The organ that proves both is
# mini.vercel_autopromote, whose three not-working paths all write
# {"status":"warning","note":"<why>"} — flat, and with the word this reader
# could not see. Guilt + innocence, per cicatrix-superscar #2's antidote.
# ---------------------------------------------------------------------------


def test_warning_status_is_seen_and_kept_apart_from_unhealthy(tmp_path):
    """GUILT: status=warning produces a finding (it used to produce silence),
    and INNOCENCE-OF-SEVERITY: it is NOT spelled the same as failed."""
    from organism_stale_detector import scan_sidecars_status

    d = str(tmp_path)
    _write(d, "blind_organ", {"ts": time.time(), "status": "warning"})
    _write(d, "broken_organ", {"ts": time.time(), "status": "failed"})
    findings = scan_sidecars_status(d, now=time.time(), host="air-m5")
    kinds = {f.organ_id: f.kind for f in findings}
    assert kinds.get("blind_organ") == "warning", (
        f"status=warning silently dropped by the receptor: {findings}"
    )
    assert kinds.get("broken_organ") == "unhealthy"
    assert kinds["blind_organ"] != kinds["broken_organ"], (
        "warning and failed must not be spelled the same way — that collapse is "
        "the defect, in the opposite direction"
    )


def test_warning_carries_the_organs_own_reason(tmp_path):
    """GUILT: the finding must repeat WHY, not only THAT.

    The real payload shape from mini.vercel_autopromote's degrade path.
    """
    from organism_stale_detector import scan_sidecars_status

    d = str(tmp_path)
    _write(
        d,
        "mini.vercel_autopromote",
        {
            "ts": time.time(),
            "status": "warning",
            "note": "degraded target — git could not be asked",
        },
    )
    findings = scan_sidecars_status(d, now=time.time(), host="mini-pro2")
    assert len(findings) == 1, findings
    assert "git could not be asked" in findings[0].detail, (
        f"the organ's own reason was dropped from the finding: {findings[0].detail!r}"
    )


def test_top_level_note_is_read_not_only_metadata_note(tmp_path):
    """GUILT of the 57-of-58 measurement: a flat `note` must reach the detail.

    Both shapes are honoured — picking one silently loses the other population.
    """
    from organism_stale_detector import scan_sidecars_status

    d = str(tmp_path)
    _write(d, "flat_note_organ", {"ts": time.time(), "status": "failed", "note": "flat-reason"})
    _write(
        d,
        "nested_note_organ",
        {"ts": time.time(), "status": "failed", "metadata": {"note": "nested-reason"}},
    )
    findings = {f.organ_id: f.detail for f in scan_sidecars_status(d, now=time.time(), host="air-m5")}
    assert "flat-reason" in findings["flat_note_organ"], findings
    assert "nested-reason" in findings["nested_note_organ"], findings


def test_metadata_note_still_wins_when_both_are_present(tmp_path):
    """INNOCENCE for the pre-existing population: adding the flat fallback must
    not change what a metadata-bearing sidecar reports."""
    from organism_stale_detector import scan_sidecars_status

    d = str(tmp_path)
    _write(
        d,
        "both_organ",
        {
            "ts": time.time(),
            "status": "error",
            "note": "flat-loses",
            "metadata": {"note": "metadata-wins"},
        },
    )
    (finding,) = scan_sidecars_status(d, now=time.time(), host="air-m5")
    assert "metadata-wins" in finding.detail
    assert "flat-loses" not in finding.detail


def test_ok_and_disabled_stay_silent(tmp_path):
    """INNOCENCE: widening the vocabulary must not start accusing healthy organs.

    `disabled` is what every node-guard writes on the wrong node — if that ever
    became a finding, every organ would alarm on two machines out of three.
    """
    from organism_stale_detector import scan_sidecars_status

    d = str(tmp_path)
    _write(d, "ok_organ", {"ts": time.time(), "status": "ok"})
    _write(d, "ok_note_organ", {"ts": time.time(), "status": "ok", "note": "promoted"})
    _write(d, "disabled_organ", {"ts": time.time(), "status": "disabled", "note": "wrong-node"})
    _write(d, "no_status_organ", {"ts": time.time()})
    assert scan_sidecars_status(d, now=time.time(), host="air-m5") == []


def test_stale_still_dominates_a_warning(tmp_path):
    """INNOCENCE for the documented precedence: a frozen channel is the headline,
    never also reported as a warning about its last-known status."""
    from organism_stale_detector import scan_sidecars_status

    d = str(tmp_path)
    old = time.time() - 30 * 86400
    _write(d, "frozen_organ", {"ts": old, "status": "warning"})
    findings = scan_sidecars_status(d, stale_days=7, now=time.time(), host="air-m5")
    assert [f.kind for f in findings] == ["stale"], findings


def test_human_report_separates_warning_from_unhealthy(tmp_path):
    """GUILT at the surface a human actually reads: the two must not merge into
    one group, or the split above is invisible where it matters."""
    from organism_stale_detector import _human_report, scan_sidecars_status

    d = str(tmp_path)
    _write(d, "blind_organ", {"ts": time.time(), "status": "warning", "note": "why-blind"})
    _write(d, "broken_organ", {"ts": time.time(), "status": "failed", "note": "why-broken"})
    report = _human_report(scan_sidecars_status(d, now=time.time(), host="air-m5"))
    assert "breathing but unhealthy" in report
    assert "not working this tick" in report
    assert "why-blind" in report and "why-broken" in report

    # And it must appear ONCE, in that group only. The grouping predicate is an
    # exclusion list: forget to exclude "warning" from it and the organ is ALSO
    # rendered under "not breathing" as `🫥 blind_organ: stale -1.0d` — a
    # breathing organ described as mute, with an invented negative age. Caught by
    # mutation (M7), which the two membership asserts above let through.
    assert "not breathing" not in report, report
    assert report.count("blind_organ") == 1, report
    assert "-1.0d" not in report and "🫥" not in report, report


def test_proprioception_exempts_warning_from_p1():
    """CROSS-ARTIFACT PIN: the severity split lives in TWO files and is only true
    if both agree. If proprioception's organs_heartbeat entry loses its
    verdict_key/ok_values, the three permanent advisories become a P1 on every
    node forever — the alert-fatigue this split exists to prevent.
    """
    import re

    here = os.path.dirname(__file__)
    src = open(os.path.join(here, "..", "proprioception.py"), encoding="utf-8").read()
    block = re.search(r'"id":\s*"organs_heartbeat".*?\n    \}', src, re.S)
    assert block, "organs_heartbeat probe entry not found in proprioception.py"
    body = block.group(0)
    assert '"verdict_key": "kind"' in body, body[-400:]
    assert '"ok_values": ["warning"]' in body, body[-400:]

    from organism_stale_detector import WARNING_STATUSES

    assert "warning" in WARNING_STATUSES


def test_this_corpus_has_a_named_executor_in_ci():
    """The corpus must be RUN, not merely present.

    Until 2026-08-22 no workflow named this file: it executed only inside the
    `scripts/tests/` sweep, which is continue-on-error and therefore green by
    construction — 44 cases that could not fail. That is the same shape the
    detector under test exists to catch, one floor up (W108), and it is why the
    warning-blindness could sit live with a full corpus sitting next to it.

    organ-conformance.yml gates on TWO filters and the file must be in BOTH: the
    `on.push.paths` list decides whether the workflow runs post-merge at all, the
    in-job `git diff` pathspec decides whether its steps do any work. In one and
    not the other = armed for pull_request only, silently skipped after merge —
    the workflow's own comment records that exact regression happening before.
    """
    here = os.path.dirname(__file__)
    wf = os.path.join(here, "..", "..", ".github", "workflows", "organ-conformance.yml")
    assert os.path.exists(wf), wf
    src = open(wf, encoding="utf-8").read()

    me = "scripts/tests/test_organism_stale_detector.py"
    subject = "scripts/organism_stale_detector.py"

    # 1) a step actually runs it
    assert f"pytest \\\n            {me}" in src or f"pytest {me}" in src, (
        "no run-step names this corpus — the sweep does not count"
    )
    # 2) both trigger filters carry the corpus AND its subject
    quoted, listed = f"'{me}'", f'- "{me}"'
    assert quoted in src and listed in src, "corpus missing from one of the two filters"
    assert f"'{subject}'" in src and f'- "{subject}"' in src, (
        "the code under test is missing from one of the two filters — a PR "
        "touching only the detector would skip its own corpus"
    )


# ---------------------------------------------------------------------------
# 2026-08-22, round 2 — an independent refuter chose the mutations this time.
# The author choosing his own mutants is the wrong person choosing them: the
# first round killed 12 of 12, and a refuter with fresh context then found three
# survivors in ten minutes. All three are pinned below.
# ---------------------------------------------------------------------------


def test_refused_is_not_silent(tmp_path):
    """GUILT: `status="refused"` must produce a finding.

    Found by grepping the fleet for the vocabulary organs actually write — the
    same method that found `warning`, applied once more instead of assumed done.
    Two REGISTERED organs emit it from 8 call sites (wa-codex-broker /
    wa-codex-seat-probe wrappers) and in every one it means the organ refused to
    START and then exited 78. Neither vocabulary held it, so the loudest thing an
    organ can say produced silence.
    """
    from organism_stale_detector import scan_sidecars_status

    d = str(tmp_path)
    _write(d, "pro.wa_codex_broker", {"ts": time.time(), "status": "refused",
                                      "note": "env file missing"})
    (finding,) = scan_sidecars_status(d, now=time.time(), host="nuzantara")
    assert finding.kind == "unhealthy", (
        "a refusal to start is not 'not working this tick' — it is not working "
        f"until a human changes something; got kind={finding.kind!r}"
    )
    assert "env file missing" in finding.detail


def test_warn_short_form_is_recognised(tmp_path):
    """GUILT: the short form must be in the vocabulary too.

    No fixture anywhere used `warn`, so dropping it from WARNING_STATUSES
    survived every test. Live blast radius is zero today only because
    scripts/lib/heartbeat.sh normalises warn -> warning before the JSON reaches
    disk — a normaliser upstream is not a reason for the reader to be deaf, it is
    one more thing that can change without this reader noticing.
    """
    from organism_stale_detector import scan_sidecars_status

    d = str(tmp_path)
    _write(d, "some_organ", {"ts": time.time(), "status": "warn", "note": "short form"})
    (finding,) = scan_sidecars_status(d, now=time.time(), host="air-m5")
    assert finding.kind == "warning"
    assert "short form" in finding.detail


def test_note_falls_back_to_last_error(tmp_path):
    """GUILT: `last_error` is half of `_sidecar_note`'s contract and was untested.

    Deleting the `or src.get("last_error")` clause passed every test in round 1.
    Both keys are honoured, at both nesting levels, and `note` wins within a
    level — assert all four corners, not just the one the happy path uses.
    """
    from organism_stale_detector import scan_sidecars_status

    d = str(tmp_path)
    _write(d, "flat_err", {"ts": time.time(), "status": "failed", "last_error": "flat-err"})
    _write(d, "nested_err", {"ts": time.time(), "status": "failed",
                             "metadata": {"last_error": "nested-err"}})
    _write(d, "note_beats_err", {"ts": time.time(), "status": "failed",
                                 "note": "the-note", "last_error": "the-error"})
    got = {f.organ_id: f.detail for f in scan_sidecars_status(d, now=time.time(), host="air-m5")}
    assert "flat-err" in got["flat_err"], got
    assert "nested-err" in got["nested_err"], got
    assert "the-note" in got["note_beats_err"] and "the-error" not in got["note_beats_err"], got


def test_proprioception_findings_list_actually_splits_severity(tmp_path):
    """BEHAVIOURAL pin on the mechanism this PR's severity split depends on.

    The sibling test above only regexes proprioception.py's SOURCE TEXT for
    `verdict_key`/`ok_values`. That proves the declaration is present, not that
    it does anything — and the refuter found the mutation that exploits the
    difference: flipping `not in` to `in` in run_wrap's findings_list branch
    inverts the whole mechanism (warnings become the DIVERGED ones; stale,
    dead_channel, corrupt and unhealthy silently RECONCILE — real P1s suppressed
    on the organism's own heartbeat guardian). Every test in the repo stayed
    green, because nothing anywhere called that branch.

    This calls it, through the REAL DEFAULT_REGISTRY entry — only its `target` is
    swapped for a stub that prints the findings — so the assertion is against the
    verdict_key/ok_values that actually ship, not a copy.
    """
    import importlib.util
    import json as _json

    spec = importlib.util.spec_from_file_location(
        "proprioception_under_test",
        os.path.join(os.path.dirname(__file__), "..", "proprioception.py"),
    )
    prop = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prop)

    entry = next(e for e in prop.DEFAULT_REGISTRY if e["id"] == "organs_heartbeat")

    def verdict_for(findings):
        stub = tmp_path / "stub_findings.py"
        stub.write_text(f"print({_json.dumps(_json.dumps(findings))})\n")
        probe = dict(entry, target=["python3", str(stub)])
        return prop.run_wrap(tmp_path, probe, 30)

    warn_only = [{"organ_id": "o", "kind": "warning", "age_days": 0.0,
                  "status": "warning", "detail": "d"}]
    status, count, _ = verdict_for(warn_only)
    assert status == prop.RECONCILED and count == 0, (
        f"a warning-only report must not be a P1 divergence, got {status}/{count}"
    )

    for bad_kind in ("stale", "dead_channel", "corrupt", "unhealthy"):
        payload = [{"organ_id": "o", "kind": bad_kind, "age_days": 9.0,
                    "status": "?", "detail": "d"}]
        status, count, _ = verdict_for(payload)
        assert status == prop.DIVERGED and count == 1, (
            f"kind={bad_kind} must still DIVERGE — suppressing it is a real P1 "
            f"going silent; got {status}/{count}"
        )

    mixed = warn_only + [{"organ_id": "p", "kind": "stale", "age_days": 9.0,
                          "status": "ok", "detail": "d"}]
    status, count, _ = verdict_for(mixed)
    assert status == prop.DIVERGED and count == 1, (
        f"a warning must not inflate the divergence count beside a real one, got {count}"
    )


# ---------------------------------------------------------------------------
# 2026-08-22, round 3 — a SECOND independent seat chose the mutations, told only
# which ones were already dead. It tried 13 and 13 survived; after round 2's
# cures 7 of those still stood. The lesson is not "add more tests": it is that
# two independent choosers found two disjoint gap sets, and the author found
# neither. The fields below are the ones that ship in to_dict() -> --json ->
# proprioception, and the report a human actually reads.
# ---------------------------------------------------------------------------


def test_short_form_statuses_are_recognised(tmp_path):
    """GUILT: `fail` (like `warn`) is in the vocabulary and no fixture used it.

    Dropping either short form passed every test. They are in the set precisely
    because shell writers shorten them, which makes them the likeliest way for a
    real organ to go unheard — the exact bug class this file's history is about.
    """
    from organism_stale_detector import scan_sidecars_status

    d = str(tmp_path)
    _write(d, "short_fail", {"ts": time.time(), "status": "fail", "note": "why-fail"})
    _write(d, "short_warn", {"ts": time.time(), "status": "warn", "note": "why-warn"})
    got = {f.organ_id: f for f in scan_sidecars_status(d, now=time.time(), host="air-m5")}
    assert got["short_fail"].kind == "unhealthy", "bare 'fail' went unheard"
    assert got["short_warn"].kind == "warning", "bare 'warn' went unheard"
    assert "why-fail" in got["short_fail"].detail
    assert "why-warn" in got["short_warn"].detail


def test_finding_carries_the_real_status_and_age(tmp_path):
    """GUILT: `.status` and `.age_days` are shipped fields, not decoration.

    Both survive into `to_dict()`, which is what `--json` prints (read by
    proprioception) and what `--emit` writes to the alerts file. Nothing asserted
    either on an unhealthy/warning finding, so `status="unknown"` and
    `age_days=99.0` both passed — a breathing organ reported as 99 days old to
    every machine reader.
    """
    from organism_stale_detector import scan_sidecars_status

    d = str(tmp_path)
    _write(d, "sick", {"ts": time.time(), "status": "failed"})
    _write(d, "blind", {"ts": time.time(), "status": "warning"})
    got = {f.organ_id: f for f in scan_sidecars_status(d, now=time.time(), host="air-m5")}
    assert got["sick"].status == "failed" and got["blind"].status == "warning"
    assert got["sick"].age_days == 0.0 and got["blind"].age_days == 0.0, (
        "a fresh organ is 0 days old — a non-zero age here is a lie told to "
        "every consumer of to_dict()"
    )
    assert got["sick"].to_dict()["status"] == "failed"
    assert got["blind"].to_dict()["age_days"] == 0.0


def test_note_is_truncated_from_the_front_and_actually_capped(tmp_path):
    """GUILT: the 120-char cap is what keeps a stack trace out of the alert file.

    Nothing asserted it, so removing the cap entirely OR truncating from the
    wrong end both passed. A `last_error` carrying a traceback would then be
    injected whole into every SessionStart context.
    """
    from organism_stale_detector import scan_sidecars_status

    d = str(tmp_path)
    note = "HEAD-" + ("x" * 400) + "-TAIL"
    _write(d, "chatty", {"ts": time.time(), "status": "failed", "note": note})
    (finding,) = scan_sidecars_status(d, now=time.time(), host="air-m5")
    assert "HEAD-" in finding.detail, (
        "truncated from the wrong end — the front is what identifies the error"
    )
    assert "-TAIL" not in finding.detail, "the cap is not capping"
    assert len(finding.detail) < len(note), "the whole note reached the detail"


def test_human_report_renders_every_kind_once_with_truthful_counts():
    """GUILT: three of the five kinds were never rendered by any test.

    `dead_channel` and `corrupt` have their own branches in `_human_report` and
    no test constructed either, so both were print-only dead code as far as this
    corpus was concerned. The group counts were unasserted too — hardcoding the
    unhealthy count to 0 passed, i.e. a header that lies about how many organs
    are sick, on the one surface a human actually reads.

    Deliberately asserts STRUCTURE, not prose: organ ids, counts, group headings
    and ordering. The glyphs and exact wording are left free — pinning those
    would make the corpus fight legitimate rewording, which is its own defect.
    """
    from organism_stale_detector import StaleFinding, _human_report

    findings = [
        StaleFinding(organ_id="z.warn", kind="warning", age_days=0.0,
                     status="warning", detail="d1"),
        StaleFinding(organ_id="a.warn", kind="warning", age_days=0.0,
                     status="warning", detail="d2"),
        StaleFinding(organ_id="sick.one", kind="unhealthy", age_days=0.0,
                     status="failed", detail="d3"),
        StaleFinding(organ_id="sick.two", kind="unhealthy", age_days=0.0,
                     status="error", detail="d4"),
        StaleFinding(organ_id="gone.organ", kind="dead_channel", detail="no sidecar"),
        StaleFinding(organ_id="broken.organ", kind="corrupt", detail="unparseable"),
        StaleFinding(organ_id="frozen.organ", kind="stale", age_days=9.0,
                     status="ok", detail="d5"),
    ]
    report = _human_report(findings)

    for organ in ("z.warn", "a.warn", "sick.one", "sick.two",
                  "gone.organ", "broken.organ", "frozen.organ"):
        assert report.count(organ) == 1, f"{organ} rendered {report.count(organ)} times:\n{report}"

    assert "7 organ finding(s)" in report, report
    assert "unhealthy (2)" in report, "the unhealthy group count must be real, not a constant"
    assert "this tick (2)" in report, "the warning group count must be real, not a constant"
    assert "(3)" in report, "the not-breathing group holds stale + dead_channel + corrupt"

    # Deterministic ordering inside the warning group — an unsorted group makes
    # two identical fleets print two different reports.
    assert report.index("a.warn") < report.index("z.warn"), report


# ---------------------------------------------------------------------------
# scan_stale_coverage_branches — R7 proprioception (2026-08-27).
#
# Born from the measured root cause of the R7 mandate: a pipefail bug in
# scripts/codex/codex-nightly-coverage-improver.sh silently killed 9 of the
# last 10 nightly runs one line after "Codex completed" — real commits
# landed on a real codex/coverage-* branch and nothing ever surfaced it for
# 10 days. This check is the structural antidote so a future regression (in
# either the generator or scripts/army/spark_coverage_harvester.py) cannot
# go silent again.
#
# Contract:
#   - GUILT: a branch older than stale_hours, with commits ahead of the
#     base, and NO pr anywhere -> flagged kind="stale_branch".
#   - INNOCENCE: a fresh branch (younger than stale_hours) is NOT flagged,
#     regardless of PR status.
#   - INNOCENCE: an old branch that already HAS a pr (any state) is NOT
#     flagged — the harvester did its job.
# ---------------------------------------------------------------------------

import stat as _stat  # noqa: E402


def _git_ok(repo, *args, env=None):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True,
                           text=True, check=True, env=env)


def _make_fake_gh(bin_dir):
    """A `gh` stand-in that answers `gh pr list --head <b> ...` from the
    JSON dict in $FAKE_GH_PRS_BY_BRANCH — never touches the network, so this
    test suite stays offline-safe (SYMBIOSIS Law 6) and deterministic.
    """
    gh_path = os.path.join(bin_dir, "gh")
    with open(gh_path, "w", encoding="utf-8") as fh:
        fh.write(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "args = sys.argv[1:]\n"
            "head = None\n"
            "for i, a in enumerate(args):\n"
            "    if a == '--head' and i + 1 < len(args):\n"
            "        head = args[i + 1]\n"
            "prs = json.loads(os.environ.get('FAKE_GH_PRS_BY_BRANCH', '{}'))\n"
            "print(json.dumps(prs.get(head, [])))\n"
        )
    os.chmod(gh_path, os.stat(gh_path).st_mode | _stat.S_IEXEC | _stat.S_IXGRP | _stat.S_IXOTH)


def _make_repo_with_coverage_branch(tmp_path, branch, age_hours, n_commits=1):
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    _git_ok(repo, "init", "-q")
    _git_ok(repo, "config", "user.email", "t@example.com")
    _git_ok(repo, "config", "user.name", "t")
    _git_ok(repo, "commit", "-q", "--allow-empty", "-m", "init")
    _git_ok(repo, "branch", "-M", "main")
    bare = str(tmp_path / "bare.git")
    subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
    _git_ok(repo, "remote", "add", "origin", bare)
    _git_ok(repo, "push", "-q", "-u", "origin", "main")

    _git_ok(repo, "checkout", "-q", "-b", branch)
    commit_epoch = time.time() - age_hours * 3600
    commit_iso = time.strftime("%Y-%m-%dT%H:%M:%S+0000", time.gmtime(commit_epoch))
    env = dict(os.environ, GIT_AUTHOR_DATE=commit_iso, GIT_COMMITTER_DATE=commit_iso)
    for i in range(n_commits):
        with open(os.path.join(repo, f"f{i}.py"), "w", encoding="utf-8") as fh:
            fh.write("x = 1\n")
        _git_ok(repo, "add", f"f{i}.py")
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", f"c{i}"],
                        check=True, env=env)
    return repo


def _fake_gh_path_env(tmp_path, monkeypatch, prs_by_branch=None):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir(exist_ok=True)
    _make_fake_gh(str(bin_dir))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_GH_PRS_BY_BRANCH", json.dumps(prs_by_branch or {}))


def test_scan_stale_coverage_branches_guilt_old_branch_no_pr_is_flagged(tmp_path, monkeypatch):
    from organism_stale_detector import scan_stale_coverage_branches

    branch = "codex/coverage-foo_bar-20260825_030000"
    repo = _make_repo_with_coverage_branch(tmp_path, branch, age_hours=48)
    _fake_gh_path_env(tmp_path, monkeypatch, prs_by_branch={})

    findings = scan_stale_coverage_branches(repo=repo, stale_hours=24.0)
    assert len(findings) == 1, findings
    f = findings[0]
    assert f.kind == "stale_branch", f
    assert f.organ_id == "codex.coverage_branch.foo_bar", f
    assert f.status == "no PR", f
    assert "1 commit" in f.detail and branch in f.detail, f.detail


def test_scan_stale_coverage_branches_innocence_fresh_branch_not_flagged(tmp_path, monkeypatch):
    from organism_stale_detector import scan_stale_coverage_branches

    branch = "codex/coverage-foo_bar-20260827_030000"
    repo = _make_repo_with_coverage_branch(tmp_path, branch, age_hours=1)
    _fake_gh_path_env(tmp_path, monkeypatch, prs_by_branch={})

    findings = scan_stale_coverage_branches(repo=repo, stale_hours=24.0)
    assert findings == [], f"a 1h-old branch must not be flagged yet (threshold 24h): {findings}"


def test_scan_stale_coverage_branches_innocence_existing_pr_not_flagged(tmp_path, monkeypatch):
    from organism_stale_detector import scan_stale_coverage_branches

    branch = "codex/coverage-foo_bar-20260825_030000"
    repo = _make_repo_with_coverage_branch(tmp_path, branch, age_hours=48)
    _fake_gh_path_env(tmp_path, monkeypatch, prs_by_branch={branch: [4242]})

    findings = scan_stale_coverage_branches(repo=repo, stale_hours=24.0)
    assert findings == [], f"a branch with an existing PR must not be flagged: {findings}"


def _make_fake_gh_failing(bin_dir):
    """A `gh` stand-in that always fails, like an offline or unauthenticated
    machine (gh installed, but `gh pr list` errors) — SYMBIOSIS Law 6:
    disconnection is not evidence of a stuck branch.
    """
    gh_path = os.path.join(bin_dir, "gh")
    with open(gh_path, "w", encoding="utf-8") as fh:
        fh.write(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "sys.stderr.write('gh: not logged in to any GitHub hosts\\n')\n"
            "sys.exit(1)\n"
        )
    os.chmod(gh_path, os.stat(gh_path).st_mode | _stat.S_IEXEC | _stat.S_IXGRP | _stat.S_IXOTH)


def test_scan_stale_coverage_branches_innocence_gh_error_fails_open(tmp_path, monkeypatch):
    # 2026-08-27 refuter finding: `gh` installed but failing (offline/
    # unauthenticated/rate-limited — pr.returncode != 0) fell through to a
    # false RED finding, directly contradicting this function's own
    # docstring ("fails OPEN ... on any git/gh error") and the inverse of
    # what has_any_pr() in spark_coverage_harvester.py already does
    # correctly for the identical gh-error case. This test would have
    # failed against the pre-fix code.
    from organism_stale_detector import scan_stale_coverage_branches

    branch = "codex/coverage-foo_bar-20260825_030000"
    repo = _make_repo_with_coverage_branch(tmp_path, branch, age_hours=48)
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir(exist_ok=True)
    _make_fake_gh_failing(str(bin_dir))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    findings = scan_stale_coverage_branches(repo=repo, stale_hours=24.0)
    assert findings == [], (
        f"gh failing (offline/unauthenticated) must fail OPEN per this "
        f"function's own docstring, never a false RED finding: {findings}"
    )


def test_scan_stale_coverage_branches_fails_open_on_unreadable_repo(tmp_path, monkeypatch):
    from organism_stale_detector import scan_stale_coverage_branches

    _fake_gh_path_env(tmp_path, monkeypatch)
    findings = scan_stale_coverage_branches(repo=str(tmp_path / "does-not-exist"))
    assert findings == [], (
        f"a repo path that is not a git repo must fail OPEN (no finding, no "
        f"crash) — SYMBIOSIS Law 6, offline/misconfigured is not evidence of "
        f"a stuck branch: {findings}"
    )


def test_scan_stale_coverage_branches_exit_code_is_red(tmp_path, monkeypatch):
    # The R7 mandate asks for this to surface as "red", not merely advisory —
    # confirm main()'s exit-code contract treats stale_branch like dead_channel.
    branch = "codex/coverage-foo_bar-20260825_030000"
    repo = _make_repo_with_coverage_branch(tmp_path, branch, age_hours=48)
    _fake_gh_path_env(tmp_path, monkeypatch, prs_by_branch={})

    from organism_stale_detector import main as detector_main

    empty_sidecars = str(tmp_path / "sidecars")
    os.makedirs(empty_sidecars, exist_ok=True)
    rc = detector_main([
        "--dir", empty_sidecars,
        "--no-cross-host-sync",
        "--repo", repo,
        "--coverage-branch-stale-hours", "24",
        "--json",
    ])
    assert rc == 1, f"a stale, PR-less coverage branch must exit non-zero: rc={rc}"


def test_the_all_clear_sentence_is_the_hooks_only_branch_and_is_a_contract():
    """CROSS-ARTIFACT PIN: this one string IS an interface, not prose.

    The distinction matters, because the sibling test above deliberately does
    NOT pin the report's glyphs or wording — pinning prose makes a corpus fight
    legitimate rewording (W112). The exception is prose a consumer PARSES, and a
    second seat's grep found exactly one: `scripts/hooks/organism_alert_sessionstart.sh`
    captures the whole report and branches on a single literal —

        case "$REPORT" in ""|*"all organs breathing"*) exit 0 ;;

    — then passes everything else through verbatim into every session's context.
    No glyph is parsed anywhere; this sentence is the entire decision.

    Unpinned it failed in BOTH directions, and both mutations survived all 53
    tests:

      - reword the all-clear, and the hook stops matching it: an ORGANISM block
        is injected into every session on every machine forever, saying that
        everything is fine. Alert fatigue by construction — the failure this
        detector exists to end.

      - worse, and this is why the assertion is two-sided: the hook's match is a
        SUBSTRING. Make the findings header read "not all organs breathing" —
        an entirely natural rewording — and it CONTAINS the all-clear literal, so
        the hook exits 0 and goes silent on real findings. Simulated against the
        hook's own case-statement: 5 findings, hook exits 0. Classic over-match
        (cicatrix family #3), pointing the wrong way.
    """
    import re

    from organism_stale_detector import StaleFinding, _human_report

    here = os.path.dirname(__file__)
    hook = os.path.join(here, "..", "hooks", "organism_alert_sessionstart.sh")
    assert os.path.exists(hook), hook
    hook_src = open(hook, encoding="utf-8").read()

    # Read the sentinel out of the CONSUMER, so this test cannot drift from the
    # thing it protects: if the hook starts branching on different words, this
    # asserts against those words, not against a copy frozen here.
    m = re.search(r'\*"([^"]+)"\*\)\s*exit 0', hook_src)
    assert m, f"the hook no longer branches on a quoted literal:\n{hook_src[-400:]}"
    sentinel = m.group(1)

    # GUILT direction 1 — the all-clear must carry it, or the hook alarms forever.
    clear = _human_report([])
    assert sentinel in clear, (
        f"the all-clear report no longer contains {sentinel!r}, which is the only "
        f"thing the SessionStart hook matches — it would inject an ORGANISM block "
        f"into every session on every machine, forever. Got: {clear!r}"
    )

    # GUILT direction 2 — no report WITH findings may contain it, or the hook
    # goes silent on them. The match is a substring, so this is not paranoia.
    for kind in ("stale", "dead_channel", "corrupt", "unhealthy", "warning"):
        noisy = _human_report(
            [StaleFinding(organ_id="o", kind=kind, age_days=9.0, status="failed", detail="d")]
        )
        assert sentinel not in noisy, (
            f"a report carrying a {kind} finding contains {sentinel!r} — the hook "
            f"matches it as a substring and exits 0, going SILENT on a real "
            f"finding. Got: {noisy!r}"
        )
