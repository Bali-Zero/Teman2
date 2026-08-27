#!/usr/bin/env python3
"""organism_stale_detector — the heartbeat-channel watcher (the RECEPTOR).

Born 2026-06-28 to end a 28-day blindness: five CORE organs (pro.sentinel,
pro.dlq_autopilot, cell.observatory, infra.pg_organism_bridge_watchdog,
pro.federation_alert_dispatcher) ran green (launchd exit 0) while their
heartbeat sidecar (~/.organism/last_seen/<organ>.json) froze for 18-28 days.
Nobody noticed because the bridge-watchdog that should have alarmed was itself
NOT LOADED, and no SessionStart hook read any alert channel.

This module answers ONE question honestly: which organs have stopped breathing?
It does NOT act (restart is the wrong cure for a dead heartbeat channel — that
lesson is why W2 was disarmed). It emits findings to ~/.organism/alerts/open.jsonl
which the SessionStart hook injects into every session's context.

green (launchd exit 0) != working (heartbeat written). This reads the breath,
not the pulse. (cicatrix-superscar #2)

CLI:
    python3 scripts/organism_stale_detector.py            # human report
    python3 scripts/organism_stale_detector.py --emit     # write alerts file
    python3 scripts/organism_stale_detector.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any

# Organs whose absence is itself an alarm (the breath channel must exist).
# Kept deliberately small: only the organism's own core guardians, because a
# MISSING sidecar for a leaf organ is noise, but for a guardian it is the W2 bug.
# All five are Pro-resident (hostname "Nuzantara") — expecting them on M5/Mini
# produced phantom dead_channel findings (proprioception run 2026-07-03), so the
# expectation is gated by machine residency, not applied fleet-wide.
CORE_ORGANS_EXPECTED: tuple[str, ...] = (
    "pro.sentinel",
    "pro.dlq_autopilot",
    "infra.pg_organism_bridge_watchdog",
    "pro.federation_alert_dispatcher",
    "cell.observatory",
)

CORE_ORGANS_RESIDENT_HOST = "nuzantara"  # Pro's hostname, lowercased, first label


def _core_organs_expected_here() -> tuple[str, ...]:
    """Return the core-organ expectation for THIS machine.

    The core guardians live on Pro only; on M5 (Air-M5) and Mini (Mini-Pro2)
    their sidecars legitimately do not exist, so expecting them there turns the
    detector into a noise source. Residency is decided by hostname first-label.
    """
    host = socket.gethostname().split(".")[0].lower()
    return CORE_ORGANS_EXPECTED if host == CORE_ORGANS_RESIDENT_HOST else ()

DEFAULT_SIDECAR_DIR = os.path.expanduser("~/.organism/last_seen")
DEFAULT_ALERTS_FILE = os.path.expanduser("~/.organism/alerts/open.jsonl")
DEFAULT_STALE_DAYS = 7

# arsenal_probe's AUTOMATED recurring heartbeat is a promise only on its primary
# node (docs/runbooks/arsenal-probe.md §How it is armed: "Mini (primary)"). Any
# other node's `<machine>.arsenal_probe.json` is a one-time on-demand stamp from
# a manual `--table`/VCR-triggered run there (infra/vcr/cli.py check) — its
# staleness is expected, not a silent outage. Sibling fix to
# organism_digest.py::stale_heartbeats() (same exemption, same constant name):
# that module got this exemption, this detector reads the same sidecar dir and
# had the identical bug (same class as the .worktrees/ runtime-stamp fix a few
# lines below) — found live 2026-08-21 when a dispatch went out to "revive"
# m5.arsenal_probe as a dead cron when no cron for it has ever existed on M5
# (CLAUDE.md: M5 = no daemon/cron H24; the probe is on-demand only there). This
# detector's blanket 7-day scan flagged the 8.7-day-old on-demand stamp as if
# it were a broken recurring promise.
_ARSENAL_PROBE_STEM_RE = re.compile(r"^(?P<machine>[a-z][a-z0-9]*)\.arsenal_probe$")
ARSENAL_PROBE_PRIMARY_NODE = "mini"

# Cross-host visibility gap (found 2026-07-17, PENDING-ARMS "infra.eventbus_redis_mini
# heartbeat frozen"): a handful of organ_ids are TCP-probed and written by a cron that
# is resident on ANOTHER host, not the machine that owns the organ. The one live case:
# infra.eventbus_redis_mini is Mini's own redis, but the probe that exercises it lives
# in launchagent-state-bridge.py's BRIDGED_TCP_PROBES, which is gated to run ONLY on
# Pro (RESIDENT_HOST) — so the fresh receipt lands in Pro's ~/.organism/last_seen/,
# never Mini's. Mini's local copy of the sidecar can freeze forever with nothing on
# Mini able to refresh it, while the organ itself is perfectly healthy. This maps
# organ_id -> where to read a fresher receipt FROM, keyed by the host that has the
# blind spot (read-only ssh pull, never a write to the remote host).
CROSS_HOST_SIDECAR_SOURCES: dict[str, dict[str, str]] = {
    "infra.eventbus_redis_mini": {
        "blind_host": "mini-pro2",
        "ssh_alias": "pro",
        "remote_path": "~/.organism/last_seen/infra.eventbus_redis_mini.json",
    },
}
# The Pro-side writer refreshes every 300s (launchagent-state-bridge cron cadence) —
# refresh a bit faster than that so we rarely serve a receipt older than one cycle,
# but never so fast that a SessionStart hook invocation pays for an ssh round-trip
# on every single call.
CROSS_HOST_SYNC_MIN_INTERVAL_SEC = 240.0
CROSS_HOST_SYNC_TIMEOUT_SEC = 3.0


def sync_cross_host_sidecars(
    sidecar_dir: str = DEFAULT_SIDECAR_DIR,
    *,
    sources: dict[str, dict[str, str]] = CROSS_HOST_SIDECAR_SOURCES,
    min_interval_sec: float = CROSS_HOST_SYNC_MIN_INTERVAL_SEC,
    timeout_sec: float = CROSS_HOST_SYNC_TIMEOUT_SEC,
    now: float | None = None,
    host: str | None = None,
) -> None:
    """Best-effort refresh of sidecars whose live writer runs on another host.

    Read-only ssh pull, never a write to the remote host (cicatrix-superscar
    perimeter). Silently a no-op on ANY failure — unreachable host, timeout, bad
    JSON, or a local mirror that is already fresh enough — so this never blocks
    or breaks the SessionStart hot path: scan_sidecars() reports the existing
    (however stale) local file honestly, same as before this function existed.
    """
    this_host = (host or socket.gethostname()).split(".")[0].lower()
    now = time.time() if now is None else now
    for organ_id, spec in sources.items():
        if this_host != spec.get("blind_host"):
            continue
        local_path = os.path.join(sidecar_dir, f"{organ_id}.json")
        try:
            if os.path.getmtime(local_path) > now - min_interval_sec:
                continue  # fresh enough — don't hammer ssh every invocation
        except OSError:
            pass  # missing sidecar is worth trying to fetch
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o", "BatchMode=yes",
                    "-o", f"ConnectTimeout={int(timeout_sec)}",
                    spec["ssh_alias"],
                    "cat", spec["remote_path"],
                ],
                capture_output=True,
                text=True,
                timeout=timeout_sec + 2,
            )
        except (subprocess.TimeoutExpired, OSError):
            continue
        if result.returncode != 0 or not result.stdout.strip():
            continue
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue
        try:
            os.makedirs(sidecar_dir, exist_ok=True)
            tmp_path = f"{local_path}.tmp.{os.getpid()}"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, sort_keys=True)
                fh.write("\n")
            os.replace(tmp_path, local_path)
        except OSError:
            continue

# Statuses that mean "the organ is breathing but reporting trouble".
#
# `refused` added 2026-08-22 by the same method that found `warning` below —
# grep the fleet for the vocabulary organs actually WRITE, rather than trusting
# the set. Two registered organs emit it from 8 call sites:
# `wa-codex-broker-wrapper.sh` (:51,:56,:76,:80) and
# `wa-codex-seat-probe-wrapper.sh` (:58,:92,:97,:101). In both it means the organ
# REFUSED TO START — env file missing, env placeholders unfilled, venv python
# missing, cd failed — and each is followed by `exit 78`, launchd's "do not
# restart me". That is the loudest thing an organ can say, and this reader was
# deaf to it. UNHEALTHY and not WARNING deliberately: a refusal to start is not
# "not working this tick", it is not working until a human changes something.
# Blast radius today is zero (neither organ is currently loaded on Pro — no
# plist, no launchctl label, no sidecar), which is exactly why it is cheap to fix
# now instead of the day one of them is armed and says nothing.
UNHEALTHY_STATUSES: frozenset[str] = frozenset(
    {"failed", "fail", "degraded", "error", "refused"}
)

# Statuses that mean "breathing, doing its job's paperwork, but NOT doing its job
# this tick". Added 2026-08-22: three organs write `warning` on every fleet node
# and this reader knew none of them, so the word was a note to nobody.
#
# The one that proves it: mini.vercel_autopromote (born 2026-08-21) writes
# `warning` on all three of its not-working paths — "skipped: previous run still
# alive", "degraded target - git could not be asked", "no READY build to
# promote". Its own source comment reasons the case explicitly: "A skip is not
# health ... the sidecar must not spell them the same way" — and then picks a
# word this receptor does not read. Intent documented in the writer, defeated in
# the reader: superscar #2 one floor up, at the READING (the same floor that let
# frontend-live-sentinel go red 13 times unheard).
#
# Kept SEPARATE from UNHEALTHY_STATUSES rather than merged into it, because
# `warning` carries two populations: an organ that is blind (above) and routine
# advisory traffic (all three *.agent_worktree_cleanup organs say "WIP worktree
# skipped (Nx) - commit/stash to let the reaper through", which is a true and
# entirely ordinary thing to say). Merging would spell those two the same way —
# the exact mistake this constant exists to fix. So: visible in the human report
# a session actually reads, and NOT a P1 boundary divergence in proprioception
# (see its organs_heartbeat entry's verdict_key/ok_values).
WARNING_STATUSES: frozenset[str] = frozenset({"warning", "warn"})

# Organs whose status=failed/degraded is a KNOWN false-positive — do NOT surface
# them (would cause alert-fatigue = the next blindness). Established by the
# 2026-06-28 triage of all 14 fresh-but-failed organs. Each entry is here because
# the failure is benign, with the documented reason:
#   - codex.spark_*        : intentionally disabled by the W81 firebreak (runaway loop)
#   - wr2.telegram_gate    : decommissioned 2026-06-11 (.removed-*), genome not pruned
#   - wr2.carousel_dispatcher: decommissioned 2026-06-11 (.removed-*), genome not pruned
#   - pro.agent_library_evolver_* : intentionally disabled (deploy-drift quarantine)
#   - pro.audit_launchd_daily : exit 1 BY DESIGN = "N unhealthy jobs found" (a true report)
#   - infra.ollama_pro : launchd job exits 1 because the real `ollama serve` already
#       owns :11434 (port collision, two program paths) — the daemon is ALIVE and serving
#       (6 models on :11434). The bridge reads the launchd exit code, not the live socket.
#       (Live triage 2026-06-28. NOTE: pro.curiosity_weekly was triaged the same day as a
#       REAL failure — W84 TCC-dead on ~/Desktop — and is deliberately NOT suppressed here:
#       it must stay visible as an operator-boundary finding, not be hidden.)
# The bridge tags all of these "failed" because it has no `disabled`/`expected_exit`
# concept (HEALTHY_EXIT_CODES={0}). Curing the bridge is a separate hot-zone PR;
# this allow-list is the safe downstream filter. Audit this list when an organ is
# re-enabled — a re-enabled organ that genuinely fails must NOT stay suppressed.
KNOWN_BENIGN_FAILED: frozenset[str] = frozenset({
    "codex.spark_loop",
    "codex.spark_harvester",
    "codex.spark_alarm",
    "wr2.telegram_gate",
    "wr2.carousel_dispatcher",
    # "wr3.reflexion_weekly" was suppressed here as "launchctl-disabled on purpose"
    # — REMOVED 2026-07-03: the organ was re-armed (real synthesis script wired into
    # the plist, label enabled+bootstrapped on Pro). Per the audit rule above, a
    # re-enabled organ that genuinely fails must NOT stay suppressed.
    "pro.agent_library_evolver_daily",
    "pro.agent_library_evolver_weekly",
    "pro.audit_launchd_daily",
    "infra.ollama_pro",
})


@dataclass
class StaleFinding:
    organ_id: str
    kind: str  # "stale" | "dead_channel" | "corrupt" | "unhealthy"
    age_days: float = field(default=-1.0)
    status: str = field(default="?")
    detail: str = field(default="")

    def to_dict(self) -> dict[str, Any]:
        return {
            "organ_id": self.organ_id,
            "kind": self.kind,
            "age_days": round(self.age_days, 1),
            "status": self.status,
            "detail": self.detail,
        }


def _machine_label(host: str | None = None) -> str:
    """Return this machine's short label: m5 / mini / pro / <raw hostname>.

    Self-contained port of proprioception.py::machine_label() (same file's
    probe_guardian_freshness(), 2026-07-17 lesson: "a Pro-only guardian probed
    on M5 is a false DIVERGED — jurisdiction, not divergence"). Duplicated
    rather than imported: this detector is invoked as a standalone,
    bootstrap-safe script (see module docstring: `cat ... | ssh pro python3 -`)
    and must not gain an intra-repo import dependency.

    host is injectable so tests can exercise jurisdiction scoping without
    touching the real hostname (mirrors sync_cross_host_sidecars's own `host`
    param below); defaults to socket.gethostname() in production.
    """
    h = (host or socket.gethostname()).split(".")[0].lower()
    if "air-m5" in h:
        return "m5"
    if "mini" in h:
        return "mini"
    if h == "nuzantara":
        return "pro"
    return h


# organ_id PREFIX -> the host whose jurisdiction the sidecar falls under.
# Ported from proprioception.py::probe_guardian_freshness()'s per-item machine
# scoping (same 2026-07-17 lesson as _machine_label() above). "cell" and
# "infra" both resolve to "pro" because, as of today, EVERY cell.*/infra.*
# sidecar in this organism is written exclusively by
# launchagent-state-bridge.py, which is gated to run ONLY on Pro (see its
# BRIDGED_TCP_PROBES + CORE_ORGANS_EXPECTED's comment above: "All five are
# Pro-resident"). A prefix ABSENT from this map (wr2., codex., mata_garuda., a
# bare "auth-sentinel", ...) is NOT jurisdiction-scoped — today's behaviour
# (report it) is preserved, because an unrecognised prefix is evidence of
# nothing: attribute-or-report, never attribute-or-drop. Audit this map if a
# cell.*/infra.* organ is ever written from a host other than Pro.
ORGAN_PREFIX_HOST: dict[str, str] = {
    "pro": "pro",
    "mini": "mini",
    "m5": "m5",
    "cell": "pro",
    "infra": "pro",
}


def _is_foreign_jurisdiction(
    organ_id: str,
    here: str,
    sources: dict[str, dict[str, str]] = CROSS_HOST_SIDECAR_SOURCES,
) -> bool:
    """True iff this sidecar belongs to another host's organ and is not an
    explicit cross-host mirror (CROSS_HOST_SIDECAR_SOURCES).

    Root cause this closes: a Pro-owned snapshot (e.g. pro.translate_hourly)
    orphaned in a DIFFERENT machine's ~/.organism/last_seen/ — nothing on that
    machine ever refreshes another host's organ, so the stray file freezes
    forever and reads as a dead organ that is, in fact, alive on its own host
    (2026-08-07). infra.eventbus_redis_mini is the deliberate exception: its
    canonical writer also lives on Pro, but CROSS_HOST_SIDECAR_SOURCES exists
    precisely so Mini (and, transitively, any other non-owning host) keeps
    seeing it — silencing that mirror here would be the W94 under-match twin.
    """
    owner = ORGAN_PREFIX_HOST.get(organ_id.split(".", 1)[0])
    if owner is None or owner == here:
        return False
    return organ_id not in sources


def _parse_ts(raw: Any, fallback_mtime: float) -> float:
    """Parse both sidecar schemas (superscar #9 tolerance).

    A) float epoch  (~/scripts/_organism_lib.sh)
    B) ISO8601 'Z'  (scripts/lib/heartbeat.sh)
    Fall back to file mtime if the field is absent but the file parsed.
    """
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str) and raw:
        try:
            from datetime import datetime, timezone

            s = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            pass
    return fallback_mtime


def scan_sidecars(
    sidecar_dir: str = DEFAULT_SIDECAR_DIR,
    stale_days: float = DEFAULT_STALE_DAYS,
    now: float | None = None,
    expect_core: tuple[str, ...] | None = None,
    host: str | None = None,
) -> list[StaleFinding]:
    """Return findings for organs whose heartbeat is stale, missing, or corrupt.

    Pure: takes a directory, returns a list. No side effects (so it is testable
    and the CLI decides whether to emit). now is injectable for determinism.

    expect_core lists organs whose ABSENT sidecar is itself an alarm. It defaults
    to the machine-resident core set (Pro only) when scanning the real organism
    dir; tests pass () so an isolated tmp dir does not spuriously flag the
    production core organs, and M5/Mini scans do not flag Pro-resident organs.

    host is forwarded to _machine_label() for jurisdiction scoping (see
    _is_foreign_jurisdiction): a sidecar owned by another host (by its
    organ_id prefix) is skipped unless it is on the CROSS_HOST_SIDECAR_SOURCES
    allow-list — a stray same-name snapshot orphaned on the wrong machine is
    not evidence that organ is dead, it just isn't this machine's to judge.
    """
    if expect_core is None:
        expect_core = (
            _core_organs_expected_here()
            if os.path.abspath(sidecar_dir) == os.path.abspath(DEFAULT_SIDECAR_DIR)
            else ()
        )
    now = time.time() if now is None else now
    here = _machine_label(host)
    findings: list[StaleFinding] = []

    if not os.path.isdir(sidecar_dir):
        return findings

    seen: set[str] = set()
    for fname in sorted(os.listdir(sidecar_dir)):
        if not fname.endswith(".json"):
            continue
        organ_id = fname[: -len(".json")]
        seen.add(organ_id)
        m = _ARSENAL_PROBE_STEM_RE.match(organ_id)
        if m and m.group("machine") != ARSENAL_PROBE_PRIMARY_NODE:
            continue  # on-demand elsewhere; no recurring promise here, never "silent"
        if _is_foreign_jurisdiction(organ_id, here):
            continue
        path = os.path.join(sidecar_dir, fname)
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            findings.append(
                StaleFinding(
                    organ_id=organ_id,
                    kind="corrupt",
                    detail=f"unparseable sidecar: {type(exc).__name__}",
                )
            )
            continue

        # wr2_runtime_stamp provenance files (ts/pid/host/checkout/head_sha/...,
        # scripts/lib/wr2_runtime_stamp.py) are written per-INVOCATION by one-shot
        # workers, not on a recurring cadence — a `checkout` under .worktrees/ is
        # an ephemeral agent sandbox (superscar #5/#1) reaped after its task ends,
        # so its mtime aging forever is not a broken promise, just an unreaped
        # one-off stamp. Sibling fix to organism_digest.py::stale_heartbeats()
        # (PR #3486, 2026-07-30) — that PR only patched organism_digest.py, not
        # this detector, which reads the same sidecar dir and has the same bug
        # (found live: wr2.html_apply.runtime stale 7.4d here, sourced from a
        # reaped .worktrees/docs-inventory-check-blocker2-surgical-0725 stamp,
        # while the canonical Pro deploy-clone's own stamp was minutes old).
        checkout = payload.get("checkout")
        if isinstance(checkout, str) and "/.worktrees/" in checkout:
            continue

        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = now
        ts = _parse_ts(
            payload.get("ts") or payload.get("timestamp"), fallback_mtime=mtime
        )
        age_days = (now - ts) / 86400.0
        if age_days > stale_days:
            findings.append(
                StaleFinding(
                    organ_id=organ_id,
                    kind="stale",
                    age_days=age_days,
                    status=str(payload.get("status", "?")),
                    detail=f"heartbeat frozen {age_days:.1f}d (threshold {stale_days}d)",
                )
            )

    # A core guardian with NO sidecar at all is the worst case (W2 root): flag it.
    for organ_id in expect_core:
        if organ_id not in seen:
            findings.append(
                StaleFinding(
                    organ_id=organ_id,
                    kind="dead_channel",
                    detail="expected core organ has NO heartbeat sidecar",
                )
            )

    return findings


def _sidecar_note(payload: dict[str, Any]) -> str:
    """The organ's own words about why it is not ok — wherever it put them.

    This reader used to look ONLY inside `metadata.note` / `metadata.last_error`.
    Measured across the live fleet on 2026-08-22: 57 sidecars carry a note at the
    TOP level and exactly 1 nests it under `metadata` — so on 57 of 58 the cause
    the organ carefully wrote was dropped, and the finding degraded to the bare
    "breathing but status=failed", which names the state and not the reason. The
    canonical writer (organ_birth.py's G2_heartbeat gene) emits
    {"ts","status","note"} flat, so flat is the convention and the nested lookup
    was the outlier; both are honoured here rather than picking a winner and
    silently losing the other population.
    """
    for src in (payload.get("metadata"), payload):
        if isinstance(src, dict):
            note = src.get("note") or src.get("last_error")
            if note:
                return str(note)
    return ""


def scan_sidecars_status(
    sidecar_dir: str = DEFAULT_SIDECAR_DIR,
    stale_days: float = DEFAULT_STALE_DAYS,
    now: float | None = None,
    benign: frozenset[str] = KNOWN_BENIGN_FAILED,
    expect_core: tuple[str, ...] | None = None,
    host: str | None = None,
) -> list[StaleFinding]:
    """Full receptor scan: stale/dead/corrupt (via scan_sidecars) PLUS unhealthy.

    An "unhealthy" finding is a FRESH organ (it IS breathing) whose status is in
    UNHEALTHY_STATUSES and which is NOT in the benign allow-list. Stale dominates:
    a stale organ is reported once as stale, never also as unhealthy (the frozen
    channel is the headline, not its last-reported status).

    This is the status-aware extension (2026-06-28): the prior receptor saw the
    mute organs but ignored the ones crying for help.

    host is forwarded to scan_sidecars() AND applied again in this function's
    own unhealthy loop below — without the second application, a foreign-host
    organ that scan_sidecars() correctly skips as out-of-jurisdiction would
    fall through into `already` being empty for it and get reported here
    instead as "unhealthy", turning a jurisdiction skip into a misclassified
    finding rather than a clean skip (2026-08-07).
    """
    now = time.time() if now is None else now
    here = _machine_label(host)
    findings = scan_sidecars(
        sidecar_dir, stale_days=stale_days, now=now, expect_core=expect_core,
        host=host,
    )
    already = {f.organ_id for f in findings}  # don't double-count stale/corrupt

    if not os.path.isdir(sidecar_dir):
        return findings

    for fname in sorted(os.listdir(sidecar_dir)):
        if not fname.endswith(".json"):
            continue
        organ_id = fname[: -len(".json")]
        if organ_id in already or organ_id in benign:
            continue
        if _is_foreign_jurisdiction(organ_id, here):
            continue
        path = os.path.join(sidecar_dir, fname)
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue  # corrupt already handled by scan_sidecars
        status = str(payload.get("status", "")).lower()
        if status in UNHEALTHY_STATUSES or status in WARNING_STATUSES:
            note = _sidecar_note(payload)
            findings.append(
                StaleFinding(
                    organ_id=organ_id,
                    kind="warning" if status in WARNING_STATUSES else "unhealthy",
                    age_days=0.0,
                    status=status,
                    detail=f"breathing but status={status}"
                    + (f" — {note[:120]}" if note else ""),
                )
            )

    return findings


_COVERAGE_BRANCH_RE = re.compile(r"^codex/coverage-(?P<module>.+)-(?P<ts>\d{8}_\d{6})$")


def scan_stale_coverage_branches(
    repo: str = ".",
    remote: str = "origin",
    base: str = "main",
    stale_hours: float = 24.0,
    now: float | None = None,
    repo_slug: str = "Balizero1987/Teman2",
) -> list[StaleFinding]:
    """R7 proprioception (2026-08-27): a `codex/coverage-*` branch older than
    `stale_hours`, with commits ahead of the base and no PR anywhere, is a RED
    finding — scripts/army/spark_coverage_harvester.py runs far more often
    than once a day and should have opened a PR for it well before this.

    Born from the measured 2026-08-27 root cause: a pipefail bug in
    scripts/codex/codex-nightly-coverage-improver.sh silently killed 9 of the
    last 10 nightly runs one line after "Codex completed" was logged — real
    commits landed on a real branch, and nothing ever surfaced it. This check
    is the structural antidote (cicatrix family #2: monitor the real outcome,
    not the exit code) so a FUTURE regression of that class — in either the
    generator or the harvester — cannot go silent again for 10 days unnoticed.

    Best-effort and fails OPEN (returns no finding, never raises) on any
    git/gh error: this machine may legitimately be offline (SYMBIOSIS Law 6 —
    disconnection is not a fault) or `gh` may not be installed here, and
    neither is on its own evidence of a stuck branch.
    """
    now = time.time() if now is None else now
    findings: list[StaleFinding] = []
    try:
        refs = subprocess.run(
            ["git", "-C", repo, "for-each-ref",
             "--format=%(refname:short) %(committerdate:unix)",
             "refs/heads/codex/coverage-*", f"refs/remotes/{remote}/codex/coverage-*"],
            capture_output=True, text=True, timeout=15,
        )
        if refs.returncode != 0:
            return []

        newest_commit_epoch: dict[str, float] = {}
        for line in refs.stdout.splitlines():
            parts = line.strip().rsplit(" ", 1)
            if len(parts) != 2:
                continue
            name, committed_raw = parts
            short = name[len(f"{remote}/"):] if name.startswith(f"{remote}/") else name
            if not _COVERAGE_BRANCH_RE.match(short):
                continue
            try:
                committed = float(committed_raw)
            except ValueError:
                continue
            newest_commit_epoch[short] = max(newest_commit_epoch.get(short, 0.0), committed)

        for short, committed in sorted(newest_commit_epoch.items()):
            age_hours = (now - committed) / 3600.0
            if age_hours < stale_hours:
                continue
            ahead = subprocess.run(
                ["git", "-C", repo, "rev-list", "--count", f"{remote}/{base}..{short}"],
                capture_output=True, text=True, timeout=15,
            )
            try:
                commits_ahead = int(ahead.stdout.strip() or "0")
            except ValueError:
                commits_ahead = 0
            if commits_ahead <= 0:
                continue  # fully merged, or the generator aborted before committing

            pr = subprocess.run(
                ["gh", "pr", "list", "--repo", repo_slug, "--head", short,
                 "--state", "all", "--json", "number"],
                capture_output=True, text=True, timeout=20,
            )
            if pr.returncode != 0:
                # gh installed but failing (offline/unauthenticated/rate-
                # limited) is NOT evidence of "no PR" — this docstring's own
                # fail-OPEN contract requires skipping here, not flagging.
                # (2026-08-27 refuter finding: this branch previously fell
                # through to a false RED finding, the exact inverse of what
                # has_any_pr() in spark_coverage_harvester.py already does
                # correctly for the same gh-error case.)
                continue
            try:
                if json.loads(pr.stdout or "[]"):
                    continue  # a PR already exists — the harvester did its job
            except json.JSONDecodeError:
                pass  # unreadable answer — fall through, treat as "no PR" below

            m = _COVERAGE_BRANCH_RE.match(short)
            module = m.group("module") if m else short
            findings.append(StaleFinding(
                organ_id=f"codex.coverage_branch.{module}",
                kind="stale_branch",
                age_days=age_hours / 24.0,
                status="no PR",
                detail=(
                    f"{commits_ahead} commit(s) ahead of {base}, {age_hours:.1f}h old, "
                    f"no PR for `{short}` — the R7 harvester should have opened one"
                ),
            ))
    except (OSError, subprocess.SubprocessError):
        return []
    return findings


def emit_alerts(findings: list[StaleFinding], alerts_file: str = DEFAULT_ALERTS_FILE) -> str:
    """Overwrite the open-alerts file with current findings (idempotent snapshot).

    The file is a SNAPSHOT of currently-open alerts, not an append log — so a
    cured organ disappears from it on the next run (no stale-alert graveyard,
    the exact failure mode that killed claude_tasks).
    """
    os.makedirs(os.path.dirname(alerts_file), exist_ok=True)
    tmp = f"{alerts_file}.tmp.{os.getpid()}"
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(tmp, "w", encoding="utf-8") as fh:
        for f in findings:
            rec = f.to_dict()
            rec["detected_at"] = stamp
            fh.write(json.dumps(rec) + "\n")
    os.replace(tmp, alerts_file)
    return alerts_file


def _human_report(findings: list[StaleFinding]) -> str:
    if not findings:
        return "✅ organism heartbeat: all organs breathing + healthy (no findings)"
    not_breathing = [f for f in findings if f.kind not in ("unhealthy", "warning")]
    unhealthy = [f for f in findings if f.kind == "unhealthy"]
    warning = [f for f in findings if f.kind == "warning"]
    lines = [f"⚠️ ORGANISM: {len(findings)} organ finding(s):"]
    if not_breathing:
        lines.append(f"  — not breathing ({len(not_breathing)}):")
        for f in sorted(not_breathing, key=lambda x: x.age_days, reverse=True):
            if f.kind == "dead_channel":
                lines.append(f"    💀 {f.organ_id}: NO heartbeat sidecar (core guardian)")
            elif f.kind == "corrupt":
                lines.append(f"    ❓ {f.organ_id}: corrupt sidecar — {f.detail}")
            else:
                lines.append(
                    f"    🫥 {f.organ_id}: stale {f.age_days:.1f}d (status={f.status})"
                )
    if unhealthy:
        lines.append(f"  — breathing but unhealthy ({len(unhealthy)}):")
        for f in sorted(unhealthy, key=lambda x: x.organ_id):
            lines.append(f"    🤒 {f.organ_id}: {f.detail}")
    if warning:
        # Deliberately worded as "not working THIS tick", not as a fault: the
        # population is mixed (a blind organ and a routine advisory both land
        # here) and only the organ's own note tells them apart — which is why
        # the note is now carried through, and why this group is not a P1.
        lines.append(f"  — breathing, not working this tick ({len(warning)}):")
        for f in sorted(warning, key=lambda x: x.organ_id):
            lines.append(f"    ⚠️  {f.organ_id}: {f.detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=DEFAULT_SIDECAR_DIR)
    ap.add_argument("--stale-days", type=float, default=DEFAULT_STALE_DAYS)
    ap.add_argument("--emit", action="store_true", help="write alerts file")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument(
        "--no-cross-host-sync",
        action="store_true",
        help=(
            "skip the best-effort ssh refresh of cross-host organ sidecars "
            "(CROSS_HOST_SIDECAR_SOURCES) — for tests/determinism, or a "
            "network-isolated run"
        ),
    )
    ap.add_argument(
        "--no-coverage-branch-scan",
        action="store_true",
        help=(
            "skip the R7 proprioception check for stale codex/coverage-* "
            "branches (shells out to git + gh) — for tests/determinism, or "
            "a network-isolated run"
        ),
    )
    ap.add_argument("--repo", default=".", help="repo path for the coverage-branch scan")
    ap.add_argument("--repo-slug", default="Balizero1987/Teman2",
                     help="GitHub repo slug for the coverage-branch scan's `gh pr list`")
    ap.add_argument("--coverage-branch-stale-hours", type=float, default=24.0)
    args = ap.parse_args(argv)

    if not args.no_cross_host_sync:
        sync_cross_host_sidecars(args.dir)

    findings = scan_sidecars_status(args.dir, stale_days=args.stale_days)

    if not args.no_coverage_branch_scan:
        findings = findings + scan_stale_coverage_branches(
            repo=args.repo, repo_slug=args.repo_slug,
            stale_hours=args.coverage_branch_stale_hours,
        )

    if args.emit:
        path = emit_alerts(findings)
        if not args.json:
            print(f"alerts written: {path} ({len(findings)} open)")

    if args.json:
        print(json.dumps([f.to_dict() for f in findings]))
    elif not args.emit:
        print(_human_report(findings))

    # exit 1 if any core guardian has a dead channel, or a coverage branch is
    # stuck without a PR — both are actionable now, not just advisory.
    return 1 if any(f.kind in ("dead_channel", "stale_branch") for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
