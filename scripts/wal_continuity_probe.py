#!/usr/bin/env python3
"""wal_continuity_probe.py — is the WAL chain CONTINUOUS, and is archiving succeeding NOW?

WHY THIS EXISTS
---------------
On 2026-08-09 WAL archiving on `nuzantara-postgres` was found DISABLED by a legacy
override. Nothing was red. The nightly backup reported DONE every single night and the
monthly restore drill passed — because both of them measure a *logical dump*, and a
logical dump neither needs nor observes the WAL chain. So the fleet held snapshots and
believed it held point-in-time recovery. The distance between those two is the entire
reason for this file.

WHAT THE EXISTING TOOLING ACTUALLY ASSERTS (measured on origin/main, 2026-08-29):

  scripts/fly-pg-backup.sh          a `pg_dump | gzip` landed an object in Tigris.
  .github/workflows/restore-drill   the newest `.sql.gz` restores into a CI Postgres
                                    and has >= 50 tables. Touches no WAL.
  apps/cell/.../backup_sensor.py    the off-site receipt is younger than N hours.

Three healthy proofs that a SNAPSHOT exists and restores. Zero proofs that the WAL
between snapshots is being shipped, or that it has no holes. `pg_stat_archiver` had
ZERO occurrences in the tree before this file.

WHAT THIS PROBE READS
---------------------
Archiver state itself — never a proxy for it. A backup object's timestamp is a proxy.
An exit code is a proxy. `pg_stat_archiver` is the thing:

    archived_count, last_archived_wal, last_archived_time,
    failed_count,   last_failed_wal,   last_failed_time,  stats_reset

plus `archive_mode`, whether `archive_command` is set at all, the current WAL insert
position, `wal_segment_size`, and `pg_is_in_recovery()`.

WHAT MAKES IT RED  (this list is the contract; see `classify`)
--------------------------------------------------------------
  ARCHIVING_DISABLED     archive_mode is off (or unreadable — fail closed), or NEITHER
                         archive_command NOR archive_library (PG15+) is set.
                         THE 2026-08-09 SCAR. Absolute — fires on the first run,
                         with no previous observation to compare against.
  ARCHIVER_FAILING       the most recent archive attempt FAILED and nothing has
                         succeeded since (last_failed_time > last_archived_time, or
                         a failure exists and nothing was ever archived). Absolute.
  FAILURES_ACCUMULATING  failed_count rose since the previous observation AND the
                         archiver has not succeeded since. A rise that RECOVERED is a
                         note, not a page: the archiver retries the same segment until
                         it succeeds, so a transient error is not a break in the chain.
  ARCHIVING_STALLED      archived_count did NOT move since the previous observation
                         while the database wrote >= STALL_SEGMENTS worth of WAL.
                         The write-pressure half is load-bearing: a quiet database
                         legitimately archives nothing, because archiving happens on
                         segment switch. "archived_count is 5000" means nothing;
                         "5000 and unmoved while 2 segments of WAL were written"
                         is the signal.
  ARCHIVING_LAGGING      the current WAL segment is more than MAX_LAG_SEGMENTS ahead
                         of the last archived one. Absolute, so a FIRST run on an
                         already-broken server is red instead of politely baselining.
  SEQUENCE_GAP           the archived WAL filename advanced by MORE segments than
                         archived_count advanced: segments were skipped. This is the
                         hole that makes a restore stop mid-recovery.

NOT red, but NEVER SILENT. Each of these means a check DID NOT RUN, and a skipped check
is not a passed check — so they raise a digest-tier alert rather than exiting 0 in quiet:
  TIMELINE_CHANGED            a failover/PITR happened; sequence arithmetic is void.
  STATS_RESET                 the counters restarted; deltas are void.
  COUNTERS_WENT_BACKWARDS     archived_count fell with stats_reset UNCHANGED — the stats
                              were lost (a crash), not reset; deltas are void.
  NON_SEGMENT_LAST_ARCHIVED   last_archived_wal is a `.backup`/`.history` file; the lag
                              and sequence checks cannot run against it.
  CHECKS_UNRUNNABLE           an input one of the delta checks needs was missing on one
                              side (no WAL position, or a non-segment on the older side).
  FAILURES_RECOVERED          failures rose but the archiver succeeded afterwards.
  FIRST_RUN                   no baseline yet — the absolute checks still applied.

CANNOT_VERIFY (exit 4) is its own verdict and is NEVER green: the reader failed, the
server answered from recovery (we asked for the primary), or a required field is
missing. W106b's rule — "I could not check" must never be reported as "there is no
problem". It escalates to p0 after CANNOT_VERIFY_P0_STREAK consecutive runs, so a
permanently blind probe cannot sit quietly at digest tier forever.

WHAT THIS PROBE CANNOT SEE — stated up front, because a guard whose limits are unwritten
gets trusted past them (all three raised by a cross-family refuter before this shipped)
-----------------------------------------------------------------------------------------
1. **A LYING archive_command.** `archive_command = '/bin/true'`, or a script that exits 0
   before the upload is durable, makes Postgres increment `archived_count` and advance
   `last_archived_wal` with nothing recoverable anywhere. Every check here would be green
   and every one of them would be right about what it measured. `pg_stat_archiver` records
   what Postgres BELIEVES it shipped; it is not evidence the object exists. Closing this
   needs a bucket-side listing that diffs the archived WAL sequence against what is really
   in Tigris — a separate probe, tracked in the ledger, NOT silently assumed here.
2. **SEQUENCE_GAP is one-directional and bounded.** It fires when the archived filename
   ran further than the counter did. Because `.backup` and `.history` files also increment
   `archived_count`, a hole SMALLER than the number of non-segment archives in the same
   window hides inside that slack. It catches the large, obvious gap; it does not prove
   the set is complete. Only the bucket-side listing in (1) can do that.
3. **Primary-only, by contract.** An answer from a server in recovery is CANNOT_VERIFY,
   which is correct for this cluster (we ask the primary) but would be wrong for a standby
   legitimately running `archive_mode = always`. If such a standby is ever archived from,
   this probe needs a second mode, not a loosened check.

EXIT CODES
    0  clean (or first-run baseline written, with no absolute finding)
    1  RED   — at least one continuity finding above
    2  blind-guard / usage — the observation carried no archiver fields at all.
       A probe that read nothing must not report clean (W84 green-but-dead).
    4  CANNOT_VERIFY

SECURITY
    `archive_command` frequently embeds credentials (an S3 URL, a wal-g env line).
    Its VALUE is never persisted, never printed, never sent to Telegram — only the
    boolean "is it set". Superscar #4.

ALERTING
    Routed through scripts/tg_notify.py by NAME (TELEGRAM_BOT_TOKEN /
    TELEGRAM_OWNER_CHAT_ID are read by the gateway from the environment). No token
    and no chat id appears in this file — this repo already carries 119 hardcoded
    fallbacks pointing at a mailbox nobody can open.

USAGE
    python3 scripts/wal_continuity_probe.py                  # query + classify + alert
    python3 scripts/wal_continuity_probe.py --dry-run        # no Telegram, no state write
    python3 scripts/wal_continuity_probe.py --from-json obs.json   # classify a captured read
    python3 scripts/wal_continuity_probe.py --json           # machine-readable verdict
    python3 scripts/wal_continuity_probe.py --selftest       # guilt + innocence, in-process
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tg_gateway_verdict import (  # noqa: E402
    extract_gateway_verdict,
    gateway_delivered,
)

FLY_APP = os.environ.get("WAL_PROBE_FLY_APP", "nuzantara-postgres")

# ---------------------------------------------------------------- exit codes
EXIT_OK = 0
EXIT_RED = 1
EXIT_BLIND = 2
EXIT_CANNOT_VERIFY = 4

# ---------------------------------------------------------------- thresholds
# Every one of these is a segment COUNT, never a byte count, because archiving is
# per-segment: expressing the thresholds in the unit the mechanism actually works in
# is what keeps them meaningful when wal_segment_size changes.
#
# STALL_SEGMENTS = 2 — one full segment of write pressure can straddle a run boundary
# with the switch not yet due, so 1 would flap on a healthy server. 2 cannot: by the
# time a second segment is filled the first has certainly been switched away from.
STALL_SEGMENTS = int(os.environ.get("WAL_PROBE_STALL_SEGMENTS", "2"))
# MAX_LAG_SEGMENTS = 8 — 128 MiB of unarchived WAL at the default 16 MiB segment size.
# The current segment is ALWAYS unarchived (it is still being written), and a slow
# uploader legitimately trails by a few, so this is deliberately not tight. It exists
# to make a FIRST run on an already-broken server red rather than politely baselining.
MAX_LAG_SEGMENTS = int(os.environ.get("WAL_PROBE_MAX_LAG_SEGMENTS", "8"))
# After this many consecutive CANNOT_VERIFY runs, escalate digest -> p0. A probe that
# cannot see must get LOUDER, never quieter (superscar #2).
CANNOT_VERIFY_P0_STREAK = int(os.environ.get("WAL_PROBE_CANNOT_VERIFY_P0_STREAK", "3"))

# ---------------------------------------------------------------- verdicts
V_OK = "OK"
V_FIRST_RUN = "FIRST_RUN"
V_ARCHIVING_DISABLED = "ARCHIVING_DISABLED"
V_ARCHIVER_FAILING = "ARCHIVER_FAILING"
V_FAILURES_ACCUMULATING = "FAILURES_ACCUMULATING"
V_ARCHIVING_STALLED = "ARCHIVING_STALLED"
V_ARCHIVING_LAGGING = "ARCHIVING_LAGGING"
V_SEQUENCE_GAP = "SEQUENCE_GAP"
V_TIMELINE_CHANGED = "TIMELINE_CHANGED"
V_STATS_RESET = "STATS_RESET"
V_CANNOT_VERIFY = "CANNOT_VERIFY"

V_NON_SEGMENT_LAST_ARCHIVED = "NON_SEGMENT_LAST_ARCHIVED"
V_FAILURES_RECOVERED = "FAILURES_RECOVERED"
V_COUNTERS_WENT_BACKWARDS = "COUNTERS_WENT_BACKWARDS"
V_CHECKS_UNRUNNABLE = "CHECKS_UNRUNNABLE"

# Notes that mean "a check did not run this time". Each of them is legitimate, and each
# of them leaves a window nothing looked at — so they alert (digest), never in silence.
VOIDING_NOTES = frozenset({
    V_TIMELINE_CHANGED, V_STATS_RESET, V_NON_SEGMENT_LAST_ARCHIVED, V_FAILURES_RECOVERED,
    V_COUNTERS_WENT_BACKWARDS, V_CHECKS_UNRUNNABLE,
})

RED_FINDINGS = frozenset({
    V_ARCHIVING_DISABLED,
    V_ARCHIVER_FAILING,
    V_FAILURES_ACCUMULATING,
    V_ARCHIVING_STALLED,
    V_ARCHIVING_LAGGING,
    V_SEQUENCE_GAP,
})

# Fields that must be present for the observation to count as a real read. If NONE of
# them arrived we did not read archiver state — we read something else, or nothing.
ARCHIVER_FIELDS = ("archive_mode", "archived_count", "last_archived_wal", "failed_count")

VERBOSE = False


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}Z] {msg}")


def vlog(msg: str) -> None:
    if VERBOSE:
        log(msg)


# ===========================================================================
# Pure parsing helpers — no I/O, trivially testable
# ===========================================================================

def parse_lsn(lsn: str) -> int | None:
    """`X/YYYYYYYY` (hex/hex) -> absolute byte offset. None if unparseable."""
    if not isinstance(lsn, str) or "/" not in lsn:
        return None
    hi, _, lo = lsn.partition("/")
    try:
        return (int(hi, 16) << 32) | int(lo, 16)
    except ValueError:
        return None


def parse_wal_filename(name: str) -> tuple[int, int, int] | None:
    """`000000010000000000000023` -> (timeline, logid, segno). None if not a WAL name.

    Strictly 24 hex chars. A shorter/longer string is not a WAL segment name and must
    not be silently coerced: a probe that guesses at its own input is how a sequence
    check goes green on nonsense.
    """
    if not isinstance(name, str) or len(name) != 24:
        return None
    try:
        int(name, 16)
    except ValueError:
        return None
    return int(name[0:8], 16), int(name[8:16], 16), int(name[16:24], 16)


def segments_per_logid(wal_segment_size: int) -> int:
    """How many segments fill one 4 GiB logid window. 256 at the 16 MiB default."""
    if not wal_segment_size or wal_segment_size <= 0:
        return 0
    return (1 << 32) // wal_segment_size


def wal_segment_index(name: str, wal_segment_size: int) -> int | None:
    """Absolute, monotonically-increasing segment number for a WAL filename.

    Timeline is deliberately EXCLUDED from the index: a timeline bump restarts nothing
    in the segment numbering, and folding it in would make every failover look like a
    astronomically large jump. The timeline is compared separately.
    """
    parsed = parse_wal_filename(name)
    per = segments_per_logid(wal_segment_size)
    if parsed is None or per == 0:
        return None
    _tli, logid, segno = parsed
    return logid * per + segno


def lsn_segment_index(lsn: str, wal_segment_size: int) -> int | None:
    """Which segment the given LSN falls in."""
    off = parse_lsn(lsn)
    if off is None or not wal_segment_size or wal_segment_size <= 0:
        return None
    return off // wal_segment_size


def _parse_ts(value: Any) -> datetime | None:
    """Postgres timestamptz text -> aware datetime. None on anything unparseable."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip().replace(" ", "T", 1)
    # Postgres renders `+00` / `+07`; fromisoformat wants `+00:00`.
    if len(text) >= 3 and (text[-3] in "+-") and text[-3:].lstrip("+-").isdigit():
        text = text + ":00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ===========================================================================
# Observation + verdict
# ===========================================================================

@dataclass
class Finding:
    code: str
    detail: str


@dataclass
class Verdict:
    verdict: str                      # the single worst code, for the dedup key
    findings: list[Finding] = field(default_factory=list)
    notes: list[Finding] = field(default_factory=list)
    exit_code: int = EXIT_OK

    @property
    def is_red(self) -> bool:
        return any(f.code in RED_FINDINGS for f in self.findings)

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "exit_code": self.exit_code,
            "findings": [{"code": f.code, "detail": f.detail} for f in self.findings],
            "notes": [{"code": n.code, "detail": n.detail} for n in self.notes],
        }


def sanitize_observation(raw: dict) -> dict:
    """Keep exactly the fields we reason about; drop `archive_command`'s VALUE.

    The value routinely carries credentials (an S3 URL, a wal-g line). We persist and
    report only whether it is set — superscar #4, secrets-in-the-clear.
    """
    cmd = raw.get("archive_command")
    lib = raw.get("archive_library")
    obs = {
        "observed_at": raw.get("observed_at") or datetime.now(timezone.utc).isoformat(),
        "archive_mode": raw.get("archive_mode"),
        "archive_command_set": bool(cmd) if cmd is not None else raw.get("archive_command_set"),
        "archive_library_set": bool(lib) if lib is not None else raw.get("archive_library_set"),
        "archived_count": raw.get("archived_count"),
        "last_archived_wal": raw.get("last_archived_wal") or "",
        "last_archived_time": raw.get("last_archived_time"),
        "failed_count": raw.get("failed_count"),
        "last_failed_wal": raw.get("last_failed_wal") or "",
        "last_failed_time": raw.get("last_failed_time"),
        "stats_reset": raw.get("stats_reset"),
        "current_wal_lsn": raw.get("current_wal_lsn") or "",
        "wal_segment_size": raw.get("wal_segment_size"),
        "in_recovery": raw.get("in_recovery"),
    }
    return obs


def observation_is_blind(obs: dict) -> bool:
    """True when NONE of the archiver fields arrived — we read nothing real."""
    return all(obs.get(k) in (None, "") for k in ARCHIVER_FIELDS)


def classify(previous: dict | None, current: dict, now: datetime | None = None) -> Verdict:
    """The whole judgment, as a pure function. Every RED path is reachable from here.

    Order matters only for which code names the dedup key; ALL findings are collected
    so an alert never hides a second fault behind the first.
    """
    now = now or datetime.now(timezone.utc)
    findings: list[Finding] = []
    notes: list[Finding] = []

    seg_size = current.get("wal_segment_size") or 0

    # ---- absolute checks: valid with no baseline at all --------------------
    raw_mode = current.get("archive_mode")
    mode = (raw_mode or "").strip().lower()
    cmd_set = current.get("archive_command_set")
    lib_set = current.get("archive_library_set")
    if mode in ("off", ""):
        # Fail CLOSED, and say WHICH of the two it is. `off` is the 2026-08-09 world.
        # NULL/empty means `current_setting('archive_mode')` itself came back empty — a
        # read failure, not a measurement — and on a recoverability probe an unreadable
        # answer must be treated as the bad answer, never as the good one. The detail
        # exists so whoever reads the page can tell the two apart in one glance instead
        # of going to look for a setting that was never off.
        how = ("the setting is OFF" if mode == "off"
               else "archive_mode could not be READ (empty/NULL) — treated as off, "
                    "fail-closed; check the connection's ability to read GUCs")
        findings.append(Finding(
            V_ARCHIVING_DISABLED,
            f"archive_mode={raw_mode!r}: {how}. WAL is not being shipped. Every backup is a "
            "snapshot; point-in-time recovery is not available.",
        ))
    elif cmd_set is False and lib_set is False:
        # BOTH, never just the command. Since PG 15 an archive MODULE
        # (`archive_library = 'basic_archive'`, or a vendor's) replaces `archive_command`
        # entirely, and a perfectly healthy server then reports an EMPTY archive_command.
        # Demanding the command alone declares that server disabled — a false RED on the
        # exact configuration Fly's postgres-flex 17.x can be running. Caught by a
        # cross-family refuter (codex gpt-5.6-sol) before this ever shipped.
        findings.append(Finding(
            V_ARCHIVING_DISABLED,
            f"archive_mode={mode!r} but NEITHER archive_command NOR archive_library is set "
            "— archiving is nominally on and ships nothing.",
        ))

    last_ok = _parse_ts(current.get("last_archived_time"))
    last_fail = _parse_ts(current.get("last_failed_time"))
    if last_fail is not None and (last_ok is None or last_fail > last_ok):
        findings.append(Finding(
            V_ARCHIVER_FAILING,
            f"the most recent archive attempt FAILED ({current.get('last_failed_wal') or '?'} "
            f"at {current.get('last_failed_time')}) and nothing has succeeded since "
            f"(last success: {current.get('last_archived_time') or 'never'}).",
        ))

    cur_seg = lsn_segment_index(current.get("current_wal_lsn", ""), seg_size)
    arch_seg = wal_segment_index(current.get("last_archived_wal", ""), seg_size)
    # `last_archived_wal` is not always a segment: a base backup leaves
    # `<seg>.<offset>.backup` and a timeline switch leaves `<tli>.history`, and both
    # legitimately land there and bump archived_count. Neither parses as a 24-hex segment,
    # so the lag and sequence checks cannot run against them. That skip must be VISIBLE —
    # a check that quietly stops checking is how this organism goes blind (superscar #2).
    last_wal = current.get("last_archived_wal") or ""
    if last_wal and arch_seg is None:
        notes.append(Finding(
            V_NON_SEGMENT_LAST_ARCHIVED,
            f"last_archived_wal={last_wal!r} is not a plain WAL segment (a .backup or "
            ".history file). Lag and sequence-gap checks are SKIPPED this run; the "
            "disabled/failing/stall checks still applied.",
        ))
    if cur_seg is not None and arch_seg is not None:
        lag = cur_seg - arch_seg
        if lag > MAX_LAG_SEGMENTS:
            findings.append(Finding(
                V_ARCHIVING_LAGGING,
                f"{lag} WAL segments written but not archived (limit {MAX_LAG_SEGMENTS}). "
                f"current LSN {current.get('current_wal_lsn')}, "
                f"last archived {current.get('last_archived_wal')}.",
            ))

    # ---- delta checks: need a baseline -------------------------------------
    if previous is None:
        notes.append(Finding(V_FIRST_RUN, "no previous observation — baseline written; "
                                          "delta checks start on the next run."))
    else:
        prev_reset = current.get("stats_reset")
        if prev_reset != previous.get("stats_reset"):
            notes.append(Finding(
                V_STATS_RESET,
                f"pg_stat_archiver counters were reset ({previous.get('stats_reset')} -> "
                f"{prev_reset}); count deltas are void this run and are re-baselined.",
            ))
        else:
            p_arch = previous.get("archived_count")
            c_arch = current.get("archived_count")
            p_fail = previous.get("failed_count")
            c_fail = current.get("failed_count")

            if isinstance(p_fail, int) and isinstance(c_fail, int) and c_fail > p_fail:
                # RECOVERED failures are a note, not a page. The archiver retries the same
                # segment until it succeeds, so a transient error followed by a success is
                # not a break in continuity — and paging p0 on it is how a probe teaches
                # people to ignore it. `last_ok > last_fail` is the recovery proof, and it
                # is the same pair ARCHIVER_FAILING uses in the other direction.
                recovered = last_ok is not None and (last_fail is None or last_ok > last_fail)
                blurb = (f"failed_count rose {p_fail} -> {c_fail} (+{c_fail - p_fail}) since "
                         f"{previous.get('observed_at')}; last failure "
                         f"{current.get('last_failed_wal') or '?'}")
                if recovered:
                    notes.append(Finding(
                        V_FAILURES_RECOVERED,
                        f"{blurb} — but the archiver SUCCEEDED afterwards "
                        f"({current.get('last_archived_time')}), so the chain is not broken. "
                        "Worth knowing, not worth paging.",
                    ))
                else:
                    findings.append(Finding(V_FAILURES_ACCUMULATING, blurb + "."))

            if isinstance(p_arch, int) and isinstance(c_arch, int):
                count_delta = c_arch - p_arch
                if count_delta < 0:
                    # Counters fell without a stats_reset — a crash can lose the stats
                    # file while `stats_reset` stays put. Both delta checks then skip on
                    # their own sign guards and the run reports clean, having compared
                    # nothing. Raised by the Kimi K3 refuter; this is the note that keeps
                    # it from being silent.
                    notes.append(Finding(
                        V_COUNTERS_WENT_BACKWARDS,
                        f"archived_count fell {p_arch} -> {c_arch} with stats_reset "
                        "UNCHANGED — the counters were lost, not reset. Delta checks are "
                        "void this run; the absolute checks still applied.",
                    ))
                # STALLED: nothing archived while the database kept writing.
                prev_cur_seg = lsn_segment_index(previous.get("current_wal_lsn", ""), seg_size)
                if count_delta == 0 and (cur_seg is None or prev_cur_seg is None):
                    # No write-pressure reading, so "archived nothing" cannot be judged.
                    # Skipping is right; skipping QUIETLY is the disease.
                    notes.append(Finding(
                        V_CHECKS_UNRUNNABLE,
                        "archived_count did not move, but the WAL position could not be "
                        f"read on one side (now={current.get('current_wal_lsn') or 'missing'!r}, "
                        f"then={previous.get('current_wal_lsn') or 'missing'!r}) — the stall "
                        "check could not run.",
                    ))
                if count_delta == 0 and cur_seg is not None and prev_cur_seg is not None:
                    written = cur_seg - prev_cur_seg
                    if written >= STALL_SEGMENTS:
                        findings.append(Finding(
                            V_ARCHIVING_STALLED,
                            f"archived_count has not moved ({c_arch}) since "
                            f"{previous.get('observed_at')} while the database wrote "
                            f"{written} WAL segments. Archiving is not keeping up, or has "
                            "stopped.",
                        ))

                # SEQUENCE GAP: the archived filename ran further than the counter did.
                prev_parsed = parse_wal_filename(previous.get("last_archived_wal", ""))
                cur_parsed = parse_wal_filename(current.get("last_archived_wal", ""))
                if not (prev_parsed and cur_parsed):
                    # The PREVIOUS side can be the non-segment one, and that case had no
                    # note: only the current side did. Same silence, one run earlier.
                    notes.append(Finding(
                        V_CHECKS_UNRUNNABLE,
                        "the sequence-gap check could not run: last_archived_wal is not a "
                        f"plain segment on one side (then="
                        f"{previous.get('last_archived_wal') or 'missing'!r}, now="
                        f"{current.get('last_archived_wal') or 'missing'!r}).",
                    ))
                if prev_parsed and cur_parsed:
                    if prev_parsed[0] != cur_parsed[0]:
                        notes.append(Finding(
                            V_TIMELINE_CHANGED,
                            f"WAL timeline changed {prev_parsed[0]} -> {cur_parsed[0]} "
                            "(failover or PITR); sequence arithmetic is void this run.",
                        ))
                    else:
                        prev_seg = wal_segment_index(previous.get("last_archived_wal", ""), seg_size)
                        this_seg = wal_segment_index(current.get("last_archived_wal", ""), seg_size)
                        if prev_seg is not None and this_seg is not None:
                            seg_delta = this_seg - prev_seg
                            if count_delta >= 0 and seg_delta > count_delta:
                                findings.append(Finding(
                                    V_SEQUENCE_GAP,
                                    f"the archived WAL sequence advanced {seg_delta} segments "
                                    f"({previous.get('last_archived_wal')} -> "
                                    f"{current.get('last_archived_wal')}) but archived_count "
                                    f"advanced only {count_delta}: "
                                    f"{seg_delta - count_delta} segment(s) were SKIPPED. "
                                    "A restore replaying this chain stops at the hole.",
                                ))

    if findings:
        # Name the worst by the declared order, so the dedup key is stable per condition.
        order = [V_ARCHIVING_DISABLED, V_SEQUENCE_GAP, V_ARCHIVER_FAILING,
                 V_ARCHIVING_STALLED, V_FAILURES_ACCUMULATING, V_ARCHIVING_LAGGING]
        worst = next(c for c in order if any(f.code == c for f in findings))
        return Verdict(verdict=worst, findings=findings, notes=notes, exit_code=EXIT_RED)

    top = notes[0].code if notes else V_OK
    return Verdict(verdict=top if top == V_FIRST_RUN else V_OK,
                   findings=[], notes=notes, exit_code=EXIT_OK)


# ===========================================================================
# State — the previous observation has to survive between runs
# ===========================================================================

def state_path() -> Path:
    """Read the env at CALL time, never at import: tests must be able to redirect it.

    W96: a test that writes the real `~/.agent/decisions/state` is a test that mutates
    production. The default is the real path; every test passes its own.
    """
    override = os.environ.get("WAL_PROBE_STATE_FILE")
    if override:
        return Path(override)
    return Path(os.path.expanduser("~/.agent/decisions/state")) / "wal_continuity_probe.state.json"


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(path)


# ===========================================================================
# Reader — the only part that talks to the world
# ===========================================================================

_FLY_CANDIDATES = (
    "/opt/homebrew/bin/flyctl",
    "/opt/homebrew/bin/fly",
    "/usr/local/bin/flyctl",
    "/usr/local/bin/fly",
    str(Path.home() / ".fly" / "bin" / "flyctl"),
    str(Path.home() / ".fly" / "bin" / "fly"),
)

# One query, one JSON row. `pg_settings` rather than SHOW so the three settings and the
# archiver counters come back in a single round trip and cannot describe two moments.
ARCHIVER_QUERY = """
SELECT json_build_object(
  'archive_mode',       current_setting('archive_mode', true),
  'archive_command_set', COALESCE(current_setting('archive_command', true), '') <> '',
  -- PG15+ archive MODULE: a healthy server using one has an EMPTY archive_command.
  -- `missing_ok = true` keeps this working against a pre-15 server, where the GUC does
  -- not exist and the expression is simply false.
  'archive_library_set',  COALESCE(current_setting('archive_library', true), '') <> '',
  'archived_count',     a.archived_count,
  'last_archived_wal',  COALESCE(a.last_archived_wal, ''),
  'last_archived_time', a.last_archived_time,
  'failed_count',       a.failed_count,
  'last_failed_wal',    COALESCE(a.last_failed_wal, ''),
  'last_failed_time',   a.last_failed_time,
  'stats_reset',        a.stats_reset,
  'in_recovery',        pg_is_in_recovery(),
  'current_wal_lsn',    CASE WHEN pg_is_in_recovery()
                             THEN pg_last_wal_replay_lsn()::text
                             ELSE pg_current_wal_lsn()::text END,
  'wal_segment_size',   (SELECT setting::bigint FROM pg_settings WHERE name='wal_segment_size')
)::text FROM pg_stat_archiver a
""".strip()


def _resolve_fly() -> str | None:
    import shutil

    found = shutil.which("fly") or shutil.which("flyctl")
    if found:
        return found
    for cand in _FLY_CANDIDATES:
        if os.access(cand, os.X_OK):
            return cand
    return None


def read_archiver_state_via_fly(timeout: int = 90) -> tuple[dict | None, str | None]:
    """Query the primary. Returns `(observation, failure_reason)` — exactly one is None.

    TWO credentials exist and only one of them works, and WHICH one has already inverted
    once (W106: a cure pinned to today's world becomes tomorrow's bug). So we probe both
    in the order the environment offers them and LOG which was accepted — never hardcode
    that the env token is the stale one, in either direction.

    NOT EXERCISED against production from the lane that wrote it: this function is the
    one part of the probe that mutates nothing but does reach out, and the mandate that
    commissioned it forbade touching prod. Its contract is pinned by the fixtures the
    tests feed to `classify`; the live path is proven by the first scheduled run.
    """
    fly = _resolve_fly()
    if fly is None:
        return None, (
            "the `fly` binary is not on this process's PATH "
            f"(PATH={os.environ.get('PATH', '')[:120]})"
        )

    cmd = [fly, "ssh", "console", "--app", FLY_APP,
           "--command", f"psql -U postgres -d postgres -Atc {json.dumps(ARCHIVER_QUERY)}"]

    attempts: list[tuple[str, dict]] = [("env/inherited", dict(os.environ))]
    if os.environ.get("FLY_API_TOKEN"):
        fallback = dict(os.environ)
        fallback.pop("FLY_API_TOKEN", None)
        attempts.append(("~/.fly/config.yml", fallback))

    failures: list[str] = []
    for source, env in attempts:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            failures.append(f"{source}: timed out after {timeout}s")
            continue
        except OSError as exc:
            failures.append(f"{source}: {exc}")
            continue
        for line in reversed(proc.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    vlog(f"credential accepted: {source}")
                    return json.loads(line), None
                except ValueError:
                    break
        # stderr can echo the command, which embeds nothing secret here, but keep it short.
        failures.append(f"{source}: rc={proc.returncode} {proc.stderr.strip()[:160]}")

    return None, "; ".join(failures) or "no credential produced a parseable row"


# ===========================================================================
# Alerting — through the gateway, by NAME, never a hardcoded destination
# ===========================================================================

def _gateway() -> Path:
    local = PROJECT_ROOT / "scripts" / "tg_notify.py"
    if local.is_file():
        return local
    return Path(os.path.expanduser("~/nuzantara/scripts/tg_notify.py"))


def send_alert(text: str, condition: str, tier: str, dry_run: bool = False) -> bool:
    """Route via scripts/tg_notify.py.

    The gateway owns the destination: it reads TELEGRAM_BOT_TOKEN and
    TELEGRAM_OWNER_CHAT_ID from the environment. Nothing here names a bot or a chat.

    The dedup key names the CONDITION and the host, never a MEASUREMENT — a segment
    count in the key mints a fresh key every run and dedup stops working; a key shared
    across conditions lets the loud one swallow the quiet one (#3677 / 2026-08-06).
    """
    if dry_run:
        log(f"[DRY RUN] telegram({tier}): {text[:160]}")
        return True
    host = socket.gethostname().split(".")[0]
    dedup_key = f"wal-continuity:{condition}:{host}"
    try:
        proc = subprocess.run(
            [sys.executable, str(_gateway()), "--tier", tier,
             "--source", "wal-continuity-probe", "--dedup-key", dedup_key, "--", text],
            capture_output=True, text=True, timeout=30,
        )
        # THE EXIT CODE IS NOT THE ANSWER. `tg_notify.py` deliberately never fails its
        # caller: it exits 0 on six outcomes, and three of them mean "not sent to
        # Telegram now" (deduped / p0_overflow_spooled / p0_unsent_spooled). Reading
        # `returncode == 0` therefore reports a REFUSAL as a delivery — which for a
        # probe whose entire job is "the alarm actually reached someone" is the same
        # disease it was built to catch, one level up. Caught by the repo's own
        # `test_gateway_callers_read_the_verdict.py` gate before this shipped; seven
        # live callers were blind this way when that census ran on 2026-08-10.
        verdict = extract_gateway_verdict(proc.stderr)
        log(f"tg_notify: {verdict or f'NO VERDICT rc={proc.returncode}'}")
        if proc.returncode != 0:
            return False
        # A digest is accepted once the gateway durably queues it (or recognises an
        # already-queued duplicate). A p0 is accepted ONLY when Telegram received it.
        if tier == "digest":
            return verdict in {"spooled", "deduped"}
        return gateway_delivered(verdict)
    except Exception as exc:  # never let the alerter kill the probe's exit code
        log(f"telegram failed: {exc}")
        return False


def format_message(verdict: Verdict, obs: dict) -> str:
    if verdict.verdict == V_CANNOT_VERIFY:
        head = "⚠️ WAL continuity: CANNOT VERIFY"
    elif verdict.is_red:
        head = "🔴 WAL continuity BROKEN"
    else:
        head = "✅ WAL continuity OK"
    lines = [f"{head} — {FLY_APP} @ {socket.gethostname().split('.')[0]}"]
    for f in verdict.findings:
        lines.append(f"• {f.code}: {f.detail}")
    for n in verdict.notes:
        lines.append(f"· {n.code}: {n.detail}")
    if obs:
        lines.append(
            f"archived_count={obs.get('archived_count')} "
            f"last_archived_wal={obs.get('last_archived_wal') or '—'} "
            f"failed_count={obs.get('failed_count')} "
            f"archive_mode={obs.get('archive_mode')}"
        )
    return "\n".join(lines)


# ===========================================================================
# Run
# ===========================================================================

def run(args: argparse.Namespace) -> int:
    path = Path(args.state_file) if args.state_file else state_path()
    state = load_state(path)
    previous = state.get("previous")

    raw: dict | None
    reason: str | None
    if args.from_json:
        try:
            text = sys.stdin.read() if args.from_json == "-" else Path(args.from_json).read_text()
            raw, reason = json.loads(text), None
        except (OSError, ValueError) as exc:
            raw, reason = None, f"--from-json unreadable: {exc}"
    else:
        raw, reason = read_archiver_state_via_fly()

    # ---- CANNOT_VERIFY: read failed, or answered from recovery -------------
    cannot_verify_reason = reason
    obs: dict = {}
    if raw is not None:
        obs = sanitize_observation(raw)
        if observation_is_blind(obs):
            # Read *something*, but not archiver state. Never clean (W84).
            log("BLIND: the observation carried no pg_stat_archiver fields at all.")
            verdict = Verdict(verdict=V_CANNOT_VERIFY, exit_code=EXIT_BLIND,
                              findings=[Finding(V_CANNOT_VERIFY,
                                                "the read returned no archiver fields — "
                                                "the probe looked at the wrong thing.")])
            if not args.dry_run:
                send_alert(format_message(verdict, obs), "blind", "p0")
            if args.json:
                print(json.dumps(verdict.as_dict(), indent=2))
            return EXIT_BLIND
        if obs.get("in_recovery") is True or \
                str(obs.get("in_recovery")).strip().lower() in ("true", "t"):
            cannot_verify_reason = (
                "the server answered from RECOVERY (pg_is_in_recovery() = true). We asked "
                "for the primary; pg_stat_archiver on a standby does not describe the "
                "primary's archiving. Check which machine the proxy routed to."
            )

    if cannot_verify_reason:
        streak = int(state.get("cannot_verify_streak", 0)) + 1
        tier = "p0" if streak >= CANNOT_VERIFY_P0_STREAK else "digest"
        verdict = Verdict(
            verdict=V_CANNOT_VERIFY, exit_code=EXIT_CANNOT_VERIFY,
            findings=[Finding(V_CANNOT_VERIFY,
                              f"{cannot_verify_reason} (consecutive: {streak})")],
        )
        log(f"CANNOT_VERIFY (streak {streak}): {cannot_verify_reason}")
        if not args.dry_run:
            send_alert(format_message(verdict, obs), "cannot-verify", tier)
            state["cannot_verify_streak"] = streak
            state["last_verdict"] = V_CANNOT_VERIFY
            save_state(path, state)
        if args.json:
            print(json.dumps(verdict.as_dict(), indent=2))
        return EXIT_CANNOT_VERIFY

    verdict = classify(previous, obs)
    log(f"verdict={verdict.verdict} exit={verdict.exit_code}")
    for f in verdict.findings:
        log(f"  RED  {f.code}: {f.detail}")
    for n in verdict.notes:
        log(f"  note {n.code}: {n.detail}")

    if not args.dry_run:
        if verdict.is_red:
            send_alert(format_message(verdict, obs), verdict.verdict.lower(), "p0")
        elif any(n.code in VOIDING_NOTES for n in verdict.notes):
            # A run where a check was SKIPPED is not the same as a run where it passed,
            # and the difference must leave the machine. A timeline switch, a stats reset
            # or a `.backup`/`.history` in last_archived_wal each void real arithmetic;
            # exiting 0 and saying nothing is precisely how this organism goes blind while
            # looking healthy. Digest tier, not p0 — visible, not paging.
            send_alert(format_message(verdict, obs), "checks-voided", "digest")
        elif state.get("last_verdict") in (V_CANNOT_VERIFY, *RED_FINDINGS):
            # Recovery is news too — a silent return to green leaves whoever read the
            # p0 believing it is still broken.
            send_alert(format_message(verdict, obs), "recovered", "digest")
        # The baseline advances on EVERY successful read, red included: the next run
        # must measure against what is true now, or a stall reports itself forever.
        state["previous"] = obs
        state["cannot_verify_streak"] = 0
        state["last_verdict"] = verdict.verdict
        save_state(path, state)

    if args.json:
        print(json.dumps(verdict.as_dict(), indent=2))
    return verdict.exit_code


def main(argv: list[str] | None = None) -> int:
    global VERBOSE
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="classify and print; no Telegram, no state write")
    ap.add_argument("--from-json", metavar="PATH",
                    help="classify a captured observation instead of querying ('-' = stdin)")
    ap.add_argument("--state-file", metavar="PATH", help="override the state file location")
    ap.add_argument("--json", action="store_true", help="print the verdict as JSON")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--selftest", action="store_true",
                    help="run the in-process guilt+innocence fixtures")
    args = ap.parse_args(argv)
    VERBOSE = args.verbose

    if args.selftest:
        return selftest()
    return run(args)


# ===========================================================================
# Selftest — guilt AND innocence, in-process, no network, no state
# ===========================================================================

def _obs(**over) -> dict:
    base = {
        "observed_at": "2026-08-29T00:00:00+00:00",
        "archive_mode": "on",
        "archive_command": "wal-g wal-push %p",
        "archive_library": "",
        "archived_count": 1000,
        "last_archived_wal": "000000010000000000000064",   # logid 0, seg 100
        "last_archived_time": "2026-08-29 00:00:00+00",
        "failed_count": 0,
        "last_failed_wal": "",
        "last_failed_time": None,
        "stats_reset": "2026-01-01 00:00:00+00",
        "current_wal_lsn": "0/65000000",                    # segment 101
        "wal_segment_size": 16777216,
        "in_recovery": False,
    }
    base.update(over)
    return sanitize_observation(base)


def selftest() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool) -> None:
        if not ok:
            failures.append(name)
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")

    prev = _obs()

    # --- innocence -------------------------------------------------------
    healthy = _obs(observed_at="2026-08-29T06:00:00+00:00", archived_count=1010,
                   last_archived_wal="00000001000000000000006E",  # seg 110
                   current_wal_lsn="0/6F000000")                   # seg 111
    check("innocence: healthy advance is OK", classify(prev, healthy).exit_code == EXIT_OK)
    check("innocence: quiet database (no writes, nothing archived) is OK",
          classify(prev, _obs(observed_at="2026-08-29T06:00:00+00:00")).exit_code == EXIT_OK)
    check("innocence: first run on a healthy server is OK, not red",
          classify(None, _obs()).exit_code == EXIT_OK)
    check("innocence: one segment of write pressure does not cry stall",
          classify(prev, _obs(observed_at="2026-08-29T06:00:00+00:00",
                              current_wal_lsn="0/66000000")).exit_code == EXIT_OK)
    check("innocence: a timeline bump is a note, not a gap",
          classify(prev, _obs(last_archived_wal="00000002000000000000006E",
                              archived_count=1010,
                              current_wal_lsn="0/6F000000")).exit_code == EXIT_OK)

    # --- guilt: every RED path ------------------------------------------
    check("guilt: archive_mode=off is RED",
          classify(prev, _obs(archive_mode="off")).verdict == V_ARCHIVING_DISABLED)
    check("guilt: archive_mode=off is RED on the FIRST run too",
          classify(None, _obs(archive_mode="off")).exit_code == EXIT_RED)
    check("guilt: neither command nor library set is RED",
          classify(prev, _obs(archive_command="", archive_library="")).verdict
          == V_ARCHIVING_DISABLED)
    check("innocence: an archive MODULE with an empty command is healthy (PG15+)",
          classify(prev, _obs(archive_command="", archive_library="basic_archive")
                   ).exit_code == EXIT_OK)
    check("guilt: a failure newer than the last success is RED",
          classify(prev, _obs(last_failed_time="2026-08-29 05:00:00+00",
                              last_failed_wal="000000010000000000000065")
                   ).verdict == V_ARCHIVER_FAILING)
    check("guilt: rising failed_count with no recovery is RED",
          any(f.code == V_FAILURES_ACCUMULATING for f in classify(
              prev, _obs(failed_count=4,
                         last_failed_time="2026-08-29 05:00:00+00")).findings))
    check("innocence: failures that RECOVERED are a note, not a page",
          classify(prev, _obs(failed_count=4,
                              last_failed_time="2026-08-28 00:00:00+00")).exit_code == EXIT_OK)
    check("guilt: stalled archiver under write pressure is RED",
          classify(prev, _obs(observed_at="2026-08-29T06:00:00+00:00",
                              current_wal_lsn="0/67000000")   # +2 segments, count unmoved
                   ).verdict == V_ARCHIVING_STALLED)
    check("guilt: a skipped segment is RED",
          classify(prev, _obs(archived_count=1002,            # +2 archived
                              last_archived_wal="00000001000000000000006E",  # +10 segments
                              current_wal_lsn="0/6F000000")
                   ).verdict == V_SEQUENCE_GAP)
    check("guilt: a far-behind archiver is RED with no baseline",
          classify(None, _obs(current_wal_lsn="0/80000000")   # seg 128 vs archived 100
                   ).verdict == V_ARCHIVING_LAGGING)

    # --- the blind guard -------------------------------------------------
    check("blind: an observation with no archiver fields is not clean",
          observation_is_blind(sanitize_observation({"observed_at": "x"})))
    check("blind: a real observation is not blind", not observation_is_blind(_obs()))

    # --- the secret must not survive sanitisation ------------------------
    sanitized = sanitize_observation({"archive_command": "s3://key:secret@bucket/%f"})
    check("secret: archive_command's VALUE is dropped, only the boolean kept",
          "archive_command" not in sanitized and sanitized["archive_command_set"] is True)

    print("SELFTEST", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
