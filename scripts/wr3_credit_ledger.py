#!/usr/bin/env python3
"""WR3 credit ledger — append-only spend truth for Veo/Flow clip generation.

Problem this fixes (verified on disk, 2026-08-23): `wr3_gatekeeper_check.py`
reads `~/.cache/wr3/flow-quota.json` to enforce a cost circuit breaker before
any Veo spend, but nothing in the repo ever WRITES that file — it was
hand-seeded once (`as_of: 2026-05-29`) and never updated, while real clips
kept getting rendered. The budget gate was decorative: it divided against a
static number that never decremented.

This module is the missing machine-readable ledger:

  - `record_spend()` is called from `wr3_flowkit_client.py`'s charging call
    sites, appending one JSONL record per clip/image charge.
  - `backfill` (CLI subcommand) reconstructs what it can of the PRE-ledger
    history from local render artifacts under
    `apps/war-room/output/episode/*/` — no cloud call, no gateway call, ever.
    Backfilled numbers are ESTIMATES (`mode="backfill"`), never presented as
    measurements, and — critically — they are a FLOOR, not a measurement of
    the true spend: the dedupe-by-shot-key counting rule (see
    discover_backfill_records docstring) conservatively collapses retries
    and copies, but a retry/re-render is a REAL Veo charge that looks
    identical, on disk, to a harmless duplicate copy. E.g.
    `clips_lipsync_incoming_2026-06-03/` holds both `01_before_0432.mp4` and
    `01_replaced_0433.mp4` for the same shot — a genuine re-render — which
    this rule (correctly, conservatively) counts once. Nothing on disk can
    settle whether a given duplicate shot key was a retry (extra charge) or
    a mere copy (no extra charge), so every backfilled number is a LOWER
    BOUND on real spend, never the true figure. `estimate_kind="floor"` is
    stamped on every backfill-mode record for exactly this reason, and
    `spend_by_episode()` exposes the aggregate as `credits_is_floor`.
  - `report` (CLI subcommand) is the "one command" that answers "what did we
    actually spend": `python3 scripts/wr3_credit_ledger.py report --days 30`.

Dependency-free by design (stdlib only): `wr3_flowkit_client.py` imports this
module to record real spend, so this module must never import
`wr3_flowkit_client` back (would be circular) and must not require anything
outside the standard library to stay trivially importable from the hot path.

KNOWN FINDING (not fixed here, by instruction — see PR description): this
repo disagrees with itself about the true per-clip Veo cost —
`wr3_flowkit_client.py:49` says `DEFAULT_CLIP_COST_CR = 20`,
`wr3_gatekeeper_check.py` (~line 22) says `CR_PER_CLIP = 10`. The ledger
records the client's actual `clip_cost_cr` on every real-mode record, which
is what makes that disagreement measurable instead of assumed.

HARDENING PASS 2026-08-23 (cross-family refuter, Kimi K3 — 12 confirmed
defects against the packet's central "credits before == credits after"
claim): every fix below closes a specific way the ledger could silently
lie. See individual functions/docstrings for detail; the summary:

  1. `backfill --apply` is now idempotent — `dedupe_against_ledger()` checks
     existing (episode_id, shot_index, source) triples before writing, so a
     re-run reports "N already present, 0 added" instead of doubling.
  2. `report --json` now splits `measured_credits` / `estimated_floor_credits`
     / `total_credits`, plus per-episode `estimate_kind`, so an automated
     before/after check can no longer compare a number that silently blends
     measurements with estimates.
  3+5. `record_spend()` never raises (unchanged contract) but a validation
     rejection or an IO write failure is now recorded to a durable sidecar
     (`<ledger>.failures`) that `report` surfaces as an INTEGRITY line — a
     report that cannot certify completeness now says so out loud, instead
     of a real charge silently becoming invisible.
  4. `report` prints the RESOLVED ABSOLUTE ledger path in its header (table
     and json), so a before/after comparison across two different files
     (e.g. cron vs interactive shell disagreeing on $WR3_CREDIT_LEDGER) is
     visible on its face instead of silently "passing" by comparing nothing
     to nothing.
  6. `mode == "placeholder"` now REQUIRES `credits == 0` and
     `clip_cost_cr == 0` — enforced at write time, so a real charge can
     never be laundered through the zero-spend path, and a zero-spend run
     can never report non-zero credits.
  7. A record with a missing/unparseable `ts` now WARNS regardless of
     whether `--days` is given (previously silent when no window was
     requested), even though it is still included only when there is no
     cutoff to fail.
  8. A non-numeric `credits` value now WARNS instead of silently
     contributing 0 credits while still counting as a clip.
  9. Zero-byte `.mp4` files (failed/incomplete renders) are skipped from
     backfill counting instead of being charged as a full clip.
  10. The canonical `clips/` dir is now walked recursively (was flat,
      inconsistent with the sibling dirs), and any directory that matches
      NEITHER `clips/` nor the sibling allowlist but contains `.mp4` files
      is now reported via `notes`, not silently skipped.
  11. mp4 discovery is case-insensitive (`.MP4` no longer invisible).
  12. Two differently-named files colliding on the same leading-digit shot
      key (e.g. "01.mp4" and "1.mp4") still dedupe to one finding (floor
      semantics, unchanged) but the collision is now recorded in `notes`
      instead of being a silent drop.

NOT a defect (explicitly, per the packet owner): dedupe-by-shot-key
undercounting genuine re-renders is BY DESIGN — that is what makes a
backfilled number a floor rather than a guess. This pass does not try to
distinguish "retry" from "copy"; it only makes every other silent miscount
loud.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LEDGER_ENV_VAR = "WR3_CREDIT_LEDGER"
_DEFAULT_LEDGER_SUBPATH = Path(".cache") / "wr3" / "credit-ledger.jsonl"

# Estimated per-clip cost used ONLY for backfilled (historical, no live
# instrumentation) records — see the KNOWN FINDING in the module docstring.
# Mirrors wr3_flowkit_client.DEFAULT_CLIP_COST_CR (the constant actually used
# at the real spend call site); NOT imported from there to keep this module
# dependency-free / avoid a circular import.
BACKFILL_ESTIMATED_CLIP_COST_CR = 20

VALID_MODES = ("real", "placeholder", "backfill")

# estimate_kind is derived from mode, never caller-supplied: "floor" for
# backfill records, None (a real measurement, not an estimate) otherwise.
ESTIMATE_KIND_FLOOR = "floor"

LEDGER_FIELDS = (
    "ts",
    "episode_id",
    "shot_index",
    "credits",
    "mode",
    "veo_job_id",
    "source",
    "clip_cost_cr",
    "estimate_kind",
)


def _default_ledger_path() -> Path:
    env = os.environ.get(_LEDGER_ENV_VAR)
    if env:
        return Path(env)
    return Path.home() / _DEFAULT_LEDGER_SUBPATH


def _resolve_ledger_path(ledger_path: Path | None) -> Path:
    return ledger_path if ledger_path is not None else _default_ledger_path()


def _resolved_absolute_ledger_path(ledger_path: Path | None) -> Path:
    """The path to DISPLAY to a human/machine — always absolute, symlinks
    resolved — so two different `$WR3_CREDIT_LEDGER`/`--ledger` values that
    LOOK different but resolve to the same file (or vice versa) are visible
    on their face (refuter finding #4). Internal read/write plumbing keeps
    using `_resolve_ledger_path` unresolved; this is display-only.
    """
    return _resolve_ledger_path(ledger_path).resolve()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(ts: Any) -> datetime | None:
    if not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _coerce_credits(value: Any, *, context: str) -> int:
    """Coerce a record's `credits` field to int, WARNING (never raising, never
    silently swallowing — refuter finding #8) when it can't be. A corrupt
    credits value contributes 0 to arithmetic, but the corruption is now
    logged instead of disappearing.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning(
            "wr3_credit_ledger: record has non-numeric credits=%r (%s) — "
            "contributing 0 to totals, but this record is CORRUPT, not zero-cost; "
            "inspect the ledger",
            value,
            context,
        )
        return 0


# ---------------------------------------------------------------------------
# Integrity sidecar — a failed write must become visible, never invisible
# ---------------------------------------------------------------------------


def _failures_path(ledger_path: Path) -> Path:
    return ledger_path.parent / f"{ledger_path.name}.failures"


def _record_failure(*, ledger_path: Path, kind: str, detail: dict[str, Any]) -> None:
    """Best-effort durable marker for a spend event that could NOT be
    recorded in the main ledger (validation rejection or IO write failure).

    This is what makes refuter finding #3 fixable without ever raising out
    of record_spend(): the render still doesn't crash, but the failure is no
    longer purely a log line — `report`'s INTEGRITY check reads this file.
    Never raises further; if even THIS write fails, logs CRITICAL (the
    absolute last resort) rather than propagate.
    """
    fail_path = _failures_path(ledger_path)
    record = {"ts": _now_iso(), "kind": kind, **detail}
    try:
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True) + "\n"
        fd = os.open(str(fail_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:  # noqa: BLE001 — absolute last resort, must not raise
        logger.critical(
            "wr3_credit_ledger: COULD NOT RECORD THE FAILURE MARKER EITHER (%s) — "
            "this failure is now invisible even to the integrity check. "
            "Original failure: %s",
            fail_path,
            detail,
            exc_info=True,
        )


def read_integrity(ledger_path: Path | None = None) -> dict[str, Any]:
    """Summarize the failures sidecar for `report`'s INTEGRITY line.

    Returns {"status": "ok"|"degraded", "failure_count": int, "since": str|None}.
    "degraded" means: at least one spend event since `since` could NOT be
    durably recorded — a report reading this MUST say it cannot certify
    completeness, not silently present a clean-looking total.
    """
    path = _resolve_ledger_path(ledger_path)
    fail_path = _failures_path(path)
    if not fail_path.exists():
        return {"status": "ok", "failure_count": 0, "since": None}

    count = 0
    since: str | None = None
    with fail_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            count += 1
            ts = rec.get("ts")
            if isinstance(ts, str) and (since is None or ts < since):
                since = ts

    if count == 0:
        return {"status": "ok", "failure_count": 0, "since": None}
    return {"status": "degraded", "failure_count": count, "since": since}


# ---------------------------------------------------------------------------
# Core append/read API
# ---------------------------------------------------------------------------


def _write_line(record: dict[str, Any], ledger_path: Path) -> None:
    """Append one JSON line to ledger_path; fsync; mode 0600 on creation.

    Raises on failure — record_spend() is the layer that swallows errors so
    a ledger problem never crashes a render; this helper stays honest.
    """
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not ledger_path.exists()
    line = json.dumps(record, sort_keys=True) + "\n"
    fd = os.open(str(ledger_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    if is_new:
        try:
            os.chmod(ledger_path, 0o600)
        except OSError:
            logger.warning(
                "wr3_credit_ledger: could not chmod 0600 on new ledger %s", ledger_path
            )


class _ValidationError(Exception):
    """Internal only — NEVER escapes record_spend(). Carries the reason a
    spend event was rejected, so it can be logged and durably marked instead
    of silently dropped or (worse) raised into a live render.
    """


def _validate_and_build_record(
    *,
    episode_id: str,
    shot_index: Any,
    credits: Any,
    mode: str,
    veo_job_id: str | None,
    source: str,
    clip_cost_cr: Any,
    ts: str | None,
) -> dict[str, Any]:
    """All coercion/validation in ONE place, ALWAYS inside a guarded caller
    (record_spend) — refuter finding #5: the previous version built the
    record dict (with bare `int(...)` calls) OUTSIDE the try/except, so
    `credits=None` raised TypeError straight into the caller, crashing a
    live render. Every int() call now happens here, where the caller can
    catch _ValidationError and route to the failure marker instead.
    """
    if mode not in VALID_MODES:
        raise _ValidationError(f"unknown mode={mode!r} — valid modes: {VALID_MODES}")

    try:
        shot_index_i = int(shot_index)
    except (TypeError, ValueError) as e:
        raise _ValidationError(f"shot_index={shot_index!r} not coercible to int: {e}") from e
    try:
        credits_i = int(credits)
    except (TypeError, ValueError) as e:
        raise _ValidationError(f"credits={credits!r} not coercible to int: {e}") from e
    try:
        clip_cost_cr_i = int(clip_cost_cr)
    except (TypeError, ValueError) as e:
        raise _ValidationError(f"clip_cost_cr={clip_cost_cr!r} not coercible to int: {e}") from e

    if mode == "placeholder" and (credits_i != 0 or clip_cost_cr_i != 0):
        # Refuter finding #6: nothing previously stopped a real charge from
        # being laundered through the zero-spend path, or a zero-spend run
        # from reporting non-zero credits. A placeholder render MUST carry
        # zero cost basis, full stop.
        raise _ValidationError(
            f"mode='placeholder' requires credits==0 and clip_cost_cr==0 "
            f"(got credits={credits_i}, clip_cost_cr={clip_cost_cr_i}) — a "
            f"placeholder render must never carry a nonzero charge"
        )

    return {
        "ts": ts if ts is not None else _now_iso(),
        "episode_id": episode_id,
        "shot_index": shot_index_i,
        "credits": credits_i,
        "mode": mode,
        "veo_job_id": veo_job_id,
        "source": source,
        "estimate_kind": ESTIMATE_KIND_FLOOR if mode == "backfill" else None,
        "clip_cost_cr": clip_cost_cr_i,
    }


def record_spend(
    *,
    episode_id: str,
    shot_index: int,
    credits: int,
    mode: str,
    veo_job_id: str | None,
    source: str,
    clip_cost_cr: int,
    ts: str | None = None,
    ledger_path: Path | None = None,
) -> None:
    """Append one clip-submission spend record.

    NEVER raises into the caller's render path — a ledger failure must not
    crash a render. Both a validation rejection (bad mode, non-coercible
    field, placeholder-with-nonzero-cost) and an IO write failure are caught,
    logged at ERROR, and durably marked via `_record_failure` so `report`'s
    INTEGRITY check can surface them — a rejected/lost record is now VISIBLE
    downstream instead of silently vanishing (refuter findings #3, #5, #6).

    `ts` defaults to now (the real, live spend path always wants "when this
    actually happened", which IS now). Pass an explicit ISO8601 `ts` only for
    reconstruction — the backfill CLI passes the source mp4's mtime so a
    historical clip is dated to when it was actually rendered, not to when
    it was backfilled.

    `estimate_kind` is NOT a caller-supplied parameter — it is derived from
    `mode` ("floor" for backfill, None otherwise) so it can never be
    forgotten or set inconsistently at a call site.
    """
    path = _resolve_ledger_path(ledger_path)

    try:
        record = _validate_and_build_record(
            episode_id=episode_id,
            shot_index=shot_index,
            credits=credits,
            mode=mode,
            veo_job_id=veo_job_id,
            source=source,
            clip_cost_cr=clip_cost_cr,
            ts=ts,
        )
    except _ValidationError as e:
        logger.error(
            "wr3_credit_ledger: refusing to record spend — %s "
            "(episode_id=%s shot_index=%r)",
            e,
            episode_id,
            shot_index,
        )
        _record_failure(
            ledger_path=path,
            kind="rejected",
            detail={
                "episode_id": str(episode_id),
                "shot_index_raw": repr(shot_index),
                "mode": str(mode),
                "reason": str(e),
            },
        )
        return

    try:
        _write_line(record, path)
    except Exception:  # noqa: BLE001 — a ledger write must never crash the render
        logger.error(
            "wr3_credit_ledger: failed to append spend record "
            "episode_id=%s shot_index=%s ledger=%s",
            episode_id,
            shot_index,
            path,
            exc_info=True,
        )
        _record_failure(
            ledger_path=path,
            kind="write_failure",
            detail={
                "episode_id": str(episode_id),
                "shot_index": record["shot_index"],
                "mode": mode,
            },
        )


def read_records(
    *,
    since_days: int | None = None,
    ledger_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Read all well-formed records, optionally windowed to the last N days.

    Malformed/truncated JSONL lines are skipped (logged at WARNING), never
    fatal — a half-written line from a crash must not kill the report.

    A record with a missing/unparseable `ts` now WARNS regardless of whether
    a window is requested (refuter finding #7 — previously this only warned,
    and only excluded, when `since_days` was given; with no window it was
    silently included with zero indication anything was wrong, so the SAME
    ledger produced two different totals depending on `--days` with no
    signal). It is still excluded only when a cutoff is active (cannot prove
    it's within an unknown-age window) — included, but WARNED, otherwise.
    """
    path = _resolve_ledger_path(ledger_path)
    if not path.exists():
        return []

    cutoff: datetime | None = None
    if since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(
                    "wr3_credit_ledger: skipping malformed JSONL line %d in %s",
                    line_no,
                    path,
                )
                continue
            if not isinstance(rec, dict):
                logger.warning(
                    "wr3_credit_ledger: skipping non-object JSONL line %d in %s",
                    line_no,
                    path,
                )
                continue

            rec_dt = _parse_ts(rec.get("ts"))
            if rec_dt is None:
                logger.warning(
                    "wr3_credit_ledger: record at line %d in %s has a missing/"
                    "unparseable ts=%r — %s",
                    line_no,
                    path,
                    rec.get("ts"),
                    "EXCLUDED (cannot verify it's within the --days window)"
                    if cutoff is not None
                    else "included as-is (no --days window active)",
                )
                if cutoff is not None:
                    continue
                records.append(rec)
                continue

            if cutoff is not None and rec_dt < cutoff:
                continue
            records.append(rec)
    return records


def spend_by_episode(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-episode spend rollup.

    Returns {episode_id: {"credits", "clips", "real_clips",
    "placeholder_clips", "backfill_clips", "credits_is_floor",
    "estimate_kind", "first_ts", "last_ts"}}.

    `credits_is_floor` is True whenever this episode's `credits` total
    includes ANY backfill-mode record — i.e. the number is a LOWER BOUND on
    real spend, not a measurement (retries/re-renders that dedupe-by-shot-key
    cannot distinguish from harmless copies are undercounted; see module
    docstring). `estimate_kind` mirrors the ledger record's own field
    ("floor" or None) so a JSON consumer reading only this rollup sees the
    same vocabulary as one reading raw records. A machine reader must not
    treat `credits` as exact when either flag says otherwise.
    """
    out: dict[str, dict[str, Any]] = {}
    for rec in records:
        eid = str(rec.get("episode_id", "unknown"))
        entry = out.setdefault(
            eid,
            {
                "credits": 0,
                "clips": 0,
                "real_clips": 0,
                "placeholder_clips": 0,
                "backfill_clips": 0,
                "credits_is_floor": False,
                "first_ts": None,
                "last_ts": None,
            },
        )
        entry["credits"] += _coerce_credits(
            rec.get("credits", 0), context=f"episode_id={eid}"
        )
        entry["clips"] += 1
        mode = rec.get("mode")
        if mode == "real":
            entry["real_clips"] += 1
        elif mode == "placeholder":
            entry["placeholder_clips"] += 1
        elif mode == "backfill":
            entry["backfill_clips"] += 1
            entry["credits_is_floor"] = True
        ts = rec.get("ts")
        if isinstance(ts, str):
            if entry["first_ts"] is None or ts < entry["first_ts"]:
                entry["first_ts"] = ts
            if entry["last_ts"] is None or ts > entry["last_ts"]:
                entry["last_ts"] = ts

    for entry in out.values():
        entry["estimate_kind"] = ESTIMATE_KIND_FLOOR if entry["credits_is_floor"] else None
    return out


def total_spend(records: Iterable[dict[str, Any]]) -> int:
    total = 0
    for rec in records:
        total += _coerce_credits(rec.get("credits", 0), context="total_spend")
    return total


def total_spend_by_kind(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Split spend into `measured` (mode real/placeholder — an actual
    instrumented event, even when its credits are 0) vs `estimated_floor`
    (mode=backfill — a reconstruction, never a measurement). Refuter finding
    #2: a bare `total_credits` blends the two with no marker, so an
    automated before/after check cannot tell a June estimate from a today
    measurement. Callers (report --json) must present both, not just the sum.
    """
    measured = 0
    estimated_floor = 0
    for rec in records:
        c = _coerce_credits(rec.get("credits", 0), context="total_spend_by_kind")
        if rec.get("mode") == "backfill":
            estimated_floor += c
        else:
            measured += c
    return {
        "measured": measured,
        "estimated_floor": estimated_floor,
        "total": measured + estimated_floor,
    }


# ---------------------------------------------------------------------------
# Backfill — reconstruct historical spend from local render artifacts ONLY.
# No cloud call, no gateway call, no network of any kind.
# ---------------------------------------------------------------------------

DEFAULT_EPISODE_ROOT = (
    Path(__file__).resolve().parents[1] / "apps" / "war-room" / "output" / "episode"
)

_CANONICAL_CLIP_DIRNAME = "clips"

# Sibling-directory allowlist (regex over the directory's basename). Anything
# NOT matching one of these is out of scope for backfill counting — we do
# NOT walk audio/, variants/, _rebuild_scripts/, or any unrecognized dir
# SILENTLY: if such a directory holds .mp4 files, discover_backfill_records
# now says so via `notes` (refuter finding #10) instead of just not walking
# it. Allowlist, not blocklist: safer to under-count-and-report than to
# hoover up unrelated mp4s as if they were Veo spends.
_SIBLING_CLIP_DIR_RE = re.compile(
    r"^("
    r"clips_lipsync.*"  # clips_lipsync, clips_lipsync_bak_*, clips_lipsync_incoming_*
    r"|clips_old_identity_fail.*"
    r"|clips_original_backup.*"
    r"|_probe_clips.*"
    r"|.*_backup_.*"
    r")$"
)

_LEADING_INT_RE = re.compile(r"^\d+")


def _find_mp4_files(directory: Path, *, recursive: bool) -> list[Path]:
    """Case-insensitive `.mp4` discovery (refuter finding #11 — a bare
    `glob("*.mp4")` is case-SENSITIVE even on a case-insensitive filesystem,
    because Path.glob's pattern matcher is POSIX normcase, not a filesystem
    lookup). `recursive=True` for BOTH the canonical dir and sibling dirs
    (refuter finding #10 — canonical was previously flat while siblings were
    recursive, so a file under `clips/subdir/03.mp4` was silently missed).
    """
    it = directory.rglob("*") if recursive else directory.glob("*")
    return sorted(p for p in it if p.is_file() and p.suffix.lower() == ".mp4")


def _shot_key(stem: str) -> tuple[int | None, str]:
    """Derive a dedup key from an mp4 filename stem.

    Returns (numeric_key, raw_key). numeric_key is the leading run of digits
    interpreted as int (e.g. "01_before_0432" -> 1, "606" -> 606, "00" -> 0),
    or None if the stem does not start with a digit — those never dedup
    against a numeric canonical entry (conservative: better to over-count an
    oddly named file than to silently merge it into an unrelated shot).

    NOTE two structurally different filenames CAN collide on this key (e.g.
    "01.mp4" and "1.mp4" both -> 1) — refuter finding #12. This is left
    unresolved BY DESIGN (dedupe-by-shot-key still applies, consistent with
    floor semantics) but the caller (`_consider_mp4_for_backfill`) now
    records the collision in `notes` instead of a silent drop.
    """
    m = _LEADING_INT_RE.match(stem)
    if not m:
        return None, stem
    return int(m.group(0)), stem


@dataclass(frozen=True)
class BackfillFinding:
    """One reconstructed historical clip.

    `ts` is the source mp4's filesystem mtime (ISO8601 UTC) — the artifact's
    actual render date, NOT the time `backfill --apply` was run. This is
    what record_spend() writes as the ledger record's `ts` when applied, so
    a June render stays dated to June, not to whenever it was backfilled.

    `mp4_path` is informational only — it is NOT part of the ledger schema
    and is never passed to record_spend.
    """

    episode_id: str
    shot_index: int
    credits: int
    mode: str
    veo_job_id: str | None
    source: str
    clip_cost_cr: int
    ts: str
    mp4_path: str


def _mtime_iso(mp4: Path) -> str:
    return datetime.fromtimestamp(mp4.stat().st_mtime, tz=timezone.utc).isoformat()


def _make_finding(*, episode_id: str, shot_key: int | str, mp4: Path, source: str) -> BackfillFinding:
    shot_index = shot_key if isinstance(shot_key, int) else -1
    return BackfillFinding(
        episode_id=episode_id,
        shot_index=shot_index,
        credits=BACKFILL_ESTIMATED_CLIP_COST_CR,
        mode="backfill",
        veo_job_id=None,
        source=source,
        clip_cost_cr=BACKFILL_ESTIMATED_CLIP_COST_CR,
        ts=_mtime_iso(mp4),
        mp4_path=str(mp4),
    )


def _consider_mp4_for_backfill(
    mp4: Path,
    *,
    episode_id: str,
    episode_dir: Path,
    source_label: str,
    seen_numeric: dict[int, Path],
    seen_raw: set[str],
    notes: list[str],
) -> BackfillFinding | None:
    """Shared per-file logic for both the canonical dir and sibling dirs.

    Returns a new BackfillFinding, or None if the file was skipped — a
    0-byte file (refuter #9) or a dedup-collision against an already-seen
    shot key. Both kinds of skip are appended to `notes`: nothing here is a
    SILENT drop, even when the counting decision itself (skip/dedupe) is
    unchanged from before.
    """
    if mp4.stat().st_size == 0:
        notes.append(
            f"{episode_id}: {mp4.relative_to(episode_dir)} is a 0-byte mp4 "
            f"(failed/incomplete render) — SKIPPED, not counted"
        )
        logger.warning("wr3_credit_ledger: skipping 0-byte mp4 %s", mp4)
        return None

    key, raw = _shot_key(mp4.stem)
    if key is not None:
        if key in seen_numeric:
            prior = seen_numeric[key]
            if prior.name != mp4.name:
                notes.append(
                    f"{episode_id}: shot key {key} seen via both "
                    f"{prior.relative_to(episode_dir)} (counted) and "
                    f"{mp4.relative_to(episode_dir)} (skipped as dup — same leading "
                    f"digits, different filename) — floor semantics unchanged, but "
                    f"verify these are really the same shot"
                )
            return None
        seen_numeric[key] = mp4
    else:
        if raw in seen_raw:
            return None
        seen_raw.add(raw)

    rel = mp4.relative_to(episode_dir)
    return _make_finding(
        episode_id=episode_id,
        shot_key=key if key is not None else raw,
        mp4=mp4,
        source=f"backfill:{source_label}:{rel}",
    )


def discover_backfill_records(
    episode_root: Path,
) -> tuple[list[BackfillFinding], list[str], list[str]]:
    """Walk episode_root/*/ and reconstruct one finding per DISTINCT real clip.

    Counting rule (stated once here; every finding's `source` names it too):

      1. `<episode>/clips/**/*.mp4` is the canonical output dir — every file
         there is counted (recursively, case-insensitively — see
         `_find_mp4_files`), keyed by its filename stem's leading digits.
      2. Sibling directories matching `_SIBLING_CLIP_DIR_RE` (clips_lipsync*,
         clips_old_identity_fail*, clips_original_backup*, _probe_clips*,
         *_backup_*) are walked recursively too, in SORTED order for
         determinism. A file there counts as a NEW clip only if its shot key
         has not already been seen — from `clips/` or an earlier-scanned
         sibling in this same pass. This is what stops `clips_lipsync_bak_*`
         / `clips_lipsync_incoming_*` / `clips_original_backup_*` (retries or
         copies, by their own naming) from being double-counted against
         `clips_lipsync/` or `clips/`.
      3. Any OTHER directory (`audio/`, `variants/`, `_rebuild_scripts/`,
         ...) is never walked for counting — but if it contains `.mp4`
         files, that is now reported in `notes`, not silently ignored.
      4. The episode-root-level `master.mp4` (final assembly) is never
         counted — rule 3 already excludes it, since it lives outside every
         clips-shaped directory (and IS itself an "unrecognized" file at
         episode-root, though `notes` only checks directories, not loose
         root-level files, since master.mp4's nature — one file, always
         named the same, always the final assembly — is already understood
         and documented, unlike an unrecognized DIRECTORY of unknown origin).
      5. A 0-byte `.mp4` (failed/incomplete render) is skipped, not counted
         as a full charge — noted, not silently dropped.
      6. Two differently-named files colliding on the same leading-digit
         shot key still dedupe to one finding (floor semantics unchanged)
         but the collision is recorded in `notes`.

    Returns (findings, skipped_episode_ids, notes):
      - `skipped_episode_ids` lists episode dirs where zero clips were
        discoverable under this rule.
      - `notes` collects the two previously-silent anomaly classes above
        (unrecognized directory with mp4s; shot-key collision) so nothing
        that affects count accuracy is invisible.

    FLOOR, not a measurement: rule 2's dedupe-by-shot-key is deliberately
    conservative, and that conservatism cuts only one way — it can only
    UNDERcount, never overcount. A genuine re-render (a real Veo charge)
    looks, on disk, identical to a harmless duplicate copy — e.g.
    `clips_lipsync_incoming_2026-06-03/` holds both `01_before_0432.mp4` and
    `01_replaced_0433.mp4`, i.e. shot 01 was re-rendered at least once, a
    real charge this rule counts as zero additional clips. Nothing in the
    filesystem can distinguish "re-rendered" from "copied" after the fact,
    so every BackfillFinding is tagged mode="backfill" /
    estimate_kind="floor" and callers must present it as a lower bound. This
    is NOT something this hardening pass tries to fix — it is the packet's
    intentional, load-bearing floor semantics.
    """
    findings: list[BackfillFinding] = []
    skipped: list[str] = []
    notes: list[str] = []

    if not episode_root.exists():
        logger.warning(
            "wr3_credit_ledger: episode root does not exist: %s", episode_root
        )
        return findings, [f"<episode root does not exist: {episode_root}>"], notes

    for episode_dir in sorted(p for p in episode_root.iterdir() if p.is_dir()):
        episode_id = episode_dir.name
        seen_numeric: dict[int, Path] = {}
        seen_raw: set[str] = set()
        episode_findings: list[BackfillFinding] = []

        canonical_dir = episode_dir / _CANONICAL_CLIP_DIRNAME
        if canonical_dir.is_dir():
            for mp4 in _find_mp4_files(canonical_dir, recursive=True):
                finding = _consider_mp4_for_backfill(
                    mp4,
                    episode_id=episode_id,
                    episode_dir=episode_dir,
                    source_label="canonical-clips-dir",
                    seen_numeric=seen_numeric,
                    seen_raw=seen_raw,
                    notes=notes,
                )
                if finding is not None:
                    episode_findings.append(finding)

        sibling_dirs: list[Path] = []
        unrecognized_dirs: list[Path] = []
        for p in sorted(q for q in episode_dir.iterdir() if q.is_dir()):
            if p.name == _CANONICAL_CLIP_DIRNAME:
                continue
            if _SIBLING_CLIP_DIR_RE.match(p.name):
                sibling_dirs.append(p)
            else:
                unrecognized_dirs.append(p)

        for sib in sibling_dirs:
            for mp4 in _find_mp4_files(sib, recursive=True):
                finding = _consider_mp4_for_backfill(
                    mp4,
                    episode_id=episode_id,
                    episode_dir=episode_dir,
                    source_label="sibling-dir-new-shot",
                    seen_numeric=seen_numeric,
                    seen_raw=seen_raw,
                    notes=notes,
                )
                if finding is not None:
                    episode_findings.append(finding)

        for other in unrecognized_dirs:
            mp4s = _find_mp4_files(other, recursive=True)
            if mp4s:
                notes.append(
                    f"{episode_id}: {len(mp4s)} mp4 file(s) in unrecognized "
                    f"directory {other.relative_to(episode_dir)} — NOT counted "
                    f"(matches neither clips/ nor the sibling allowlist; add a "
                    f"pattern or investigate)"
                )

        if not episode_findings:
            skipped.append(episode_id)
            continue
        findings.extend(episode_findings)

    return findings, skipped, notes


def dedupe_against_ledger(
    findings: list[BackfillFinding],
    *,
    ledger_path: Path | None = None,
) -> tuple[list[BackfillFinding], int]:
    """Filter out findings already present in the ledger as a mode="backfill"
    record with the same (episode_id, shot_index, source) — refuter finding
    #1: `backfill --apply` had no memory of what it already wrote, so a
    second run silently doubled the historical total. A baseline that can
    silently double is worse than no baseline.

    Returns (new_findings, already_present_count). Calling `--apply` twice
    now reports "N already present, 0 added" on the second run.
    """
    existing = read_records(ledger_path=ledger_path)
    existing_keys = {
        (rec.get("episode_id"), rec.get("shot_index"), rec.get("source"))
        for rec in existing
        if rec.get("mode") == "backfill"
    }
    new_findings: list[BackfillFinding] = []
    already_present = 0
    for f in findings:
        key = (f.episode_id, f.shot_index, f.source)
        if key in existing_keys:
            already_present += 1
            continue
        new_findings.append(f)
        existing_keys.add(key)  # guard duplicate keys within this same findings list
    return new_findings, already_present


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wr3_credit_ledger.py",
        description="WR3 Veo/Flow credit ledger — spend truth CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common_ledger = argparse.ArgumentParser(add_help=False)
    common_ledger.add_argument(
        "--ledger",
        type=str,
        default=None,
        help=(
            "Path to the ledger JSONL file (default: $WR3_CREDIT_LEDGER or "
            "~/.cache/wr3/credit-ledger.jsonl)"
        ),
    )

    p_report = sub.add_parser(
        "report", parents=[common_ledger], help="Print spend-by-episode table."
    )
    p_report.add_argument(
        "--days", type=int, default=None, help="Only include records from the last N days."
    )
    p_report.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON instead of a table."
    )

    p_backfill = sub.add_parser(
        "backfill",
        parents=[common_ledger],
        help="Reconstruct historical spend from local render artifacts (no network).",
    )
    p_backfill.add_argument(
        "--episode-root",
        type=str,
        default=None,
        help=f"Override episode root directory (default: {DEFAULT_EPISODE_ROOT})",
    )
    p_backfill.add_argument(
        "--apply",
        action="store_true",
        help="Write the reconstructed records to the ledger. Default is dry-run (print only).",
    )
    p_backfill.add_argument(
        "--json", action="store_true", help="Also emit the full findings as machine-readable JSON."
    )

    return parser


def _fmt_row(vals: list[Any], widths: list[int]) -> str:
    return "  ".join(str(v).ljust(w) for v, w in zip(vals, widths))


def _integrity_line(integrity: dict[str, Any]) -> str:
    if integrity["status"] == "ok":
        return "ledger integrity: OK"
    return (
        f"ledger integrity: DEGRADED — {integrity['failure_count']} write "
        f"failure(s) since {integrity['since']}; this report CANNOT certify "
        f"completeness"
    )


def _cmd_report(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger) if args.ledger else None
    records = read_records(since_days=args.days, ledger_path=ledger_path)
    by_ep = spend_by_episode(records)
    split = total_spend_by_kind(records)
    integrity = read_integrity(ledger_path)
    resolved_path = _resolved_absolute_ledger_path(ledger_path)

    if args.json:
        print(
            json.dumps(
                {
                    "ledger": str(resolved_path),
                    "days": args.days,
                    "episodes": by_ep,
                    "measured_credits": split["measured"],
                    "estimated_floor_credits": split["estimated_floor"],
                    "total_credits": split["total"],
                    "total_clips": len(records),
                    "integrity": integrity,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    # Header FIRST — refuter finding #4: a resolved, absolute ledger path
    # must be visible up front, or a before/after comparison across two
    # different files is invisible on its face.
    print(f"# ledger: {resolved_path}")
    print(
        f"# window: last {args.days} day(s)"
        if args.days is not None
        else "# window: ALL records (no --days given)"
    )
    print()

    cols = ["episode_id", "clips", "real", "placeholder", "backfill", "credits", "first_ts", "last_ts"]
    widths = [40, 6, 6, 11, 8, 8, 26, 26]
    print(_fmt_row(cols, widths))
    print("-" * (sum(widths) + 2 * (len(widths) - 1)))

    any_backfill = False
    for eid in sorted(by_ep):
        e = by_ep[eid]
        is_floor = e["credits_is_floor"]
        marker = "~" if is_floor else ""
        if is_floor:
            any_backfill = True
        credits_display = f"≥{e['credits']}" if is_floor else str(e["credits"])
        print(
            _fmt_row(
                [
                    f"{marker}{eid}",
                    e["clips"],
                    e["real_clips"],
                    e["placeholder_clips"],
                    e["backfill_clips"],
                    credits_display,
                    e["first_ts"] or "-",
                    e["last_ts"] or "-",
                ],
                widths,
            )
        )

    print("-" * (sum(widths) + 2 * (len(widths) - 1)))
    print(
        _fmt_row(
            [
                "TOTAL",
                len(records),
                sum(e["real_clips"] for e in by_ep.values()),
                sum(e["placeholder_clips"] for e in by_ep.values()),
                sum(e["backfill_clips"] for e in by_ep.values()),
                split["total"],
                "",
                "",
            ],
            widths,
        )
    )
    print(
        f"  measured: {split['measured']} cr  |  estimated floor: "
        f"{split['estimated_floor']} cr"
    )

    print(f"\n{_integrity_line(integrity)}")
    if any_backfill:
        print(
            "\n~ = episode's credits shown as ≥N cr (estimated FLOOR, not a "
            "measurement): retries/re-renders are real charges that "
            "dedupe-by-shot-key cannot see, so the artifacts on disk cannot "
            "settle the true figure — the real spend may be higher."
        )
    return 0


def _cmd_backfill(args: argparse.Namespace) -> int:
    episode_root = Path(args.episode_root) if args.episode_root else DEFAULT_EPISODE_ROOT
    findings, skipped, notes = discover_backfill_records(episode_root)
    ledger_path = Path(args.ledger) if args.ledger else None
    resolved_path = _resolved_absolute_ledger_path(ledger_path)

    print(f"# wr3_credit_ledger backfill — episode_root={episode_root}")
    print(f"# ledger: {resolved_path}")
    print("# Counting rule: clips/**/*.mp4 is canonical (recursive, case-insensitive);")
    print("#   sibling dirs matching clips_lipsync*, clips_old_identity_fail*,")
    print("#   clips_original_backup*, _probe_clips*, *_backup_* are walked ONLY for")
    print("#   shot keys absent from clips/ (or an earlier-scanned sibling) — retries/")
    print("#   copies are never double-counted. Assumed clip_cost_cr = "
          f"{BACKFILL_ESTIMATED_CLIP_COST_CR} (mirrors wr3_flowkit_client."
          "DEFAULT_CLIP_COST_CR; wr3_gatekeeper_check.py's CR_PER_CLIP=10 "
          "disagrees — unresolved, see module docstring).")
    print("# Every row below is an ESTIMATED FLOOR (mode=backfill), never a")
    print("#   measurement: a re-render is a real charge that dedupe-by-shot-key")
    print("#   cannot tell apart from a harmless duplicate copy (e.g. shot 01 has")
    print("#   BOTH 01_before_0432.mp4 and 01_replaced_0433.mp4 on disk — a real")
    print("#   re-render, counted once here). `ts` is the source mp4's mtime (the")
    print("#   artifact's actual render date), not the time this command was run.")
    print("# --apply is IDEMPOTENT: a finding already present in the ledger")
    print("#   (same episode_id/shot_index/source) is never re-written.")
    print()

    by_episode: dict[str, list[BackfillFinding]] = {}
    for f in findings:
        by_episode.setdefault(f.episode_id, []).append(f)

    total_credits = 0
    for eid in sorted(by_episode):
        rows = by_episode[eid]
        credits = sum(r.credits for r in rows)
        total_credits += credits
        print(f"{eid}: {len(rows)} clip(s), ≥{credits} cr (estimated FLOOR)")
        for r in rows:
            shot_label = r.shot_index if r.shot_index >= 0 else "n/a"
            print(f"    shot_key={shot_label}  ts={r.ts}  {r.source}")

    if skipped:
        print()
        print(f"No clips discoverable in: {', '.join(skipped)}")

    if notes:
        print()
        print("NOTES (anomalies — verify these, they affect count accuracy):")
        for n in notes:
            print(f"  - {n}")

    print()
    print(
        f"TOTAL: {len(findings)} clip(s) across {len(by_episode)} episode(s), "
        f"≥{total_credits} cr (estimated FLOOR — retries/re-renders are real "
        f"charges that dedupe by shot key cannot see; the artifacts cannot "
        f"settle the true figure)"
    )

    if args.json:
        print()
        print(
            json.dumps(
                {
                    "ledger": str(resolved_path),
                    "episode_root": str(episode_root),
                    "findings": [f.__dict__ for f in findings],
                    "skipped_episodes_no_clips_found": skipped,
                    "notes": notes,
                },
                indent=2,
                sort_keys=True,
            )
        )

    # Idempotency check runs regardless of --apply, so a DRY RUN preview
    # already tells you what --apply would actually do (refuter finding #1).
    new_findings, already_present = dedupe_against_ledger(findings, ledger_path=ledger_path)

    if not args.apply:
        print()
        print(
            f"DRY RUN — {len(new_findings)} new record(s) would be written, "
            f"{already_present} already present in the ledger (idempotent). "
            f"Re-run with --apply to write them."
        )
        return 0

    for f in new_findings:
        record_spend(
            episode_id=f.episode_id,
            shot_index=f.shot_index,
            credits=f.credits,
            mode=f.mode,
            veo_job_id=f.veo_job_id,
            source=f.source,
            clip_cost_cr=f.clip_cost_cr,
            ts=f.ts,
            ledger_path=ledger_path,
        )

    print()
    print(
        f"Applied {len(new_findings)} new record(s), {already_present} already "
        f"present (skipped, idempotent) to {resolved_path}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    if args.command == "report":
        return _cmd_report(args)
    if args.command == "backfill":
        return _cmd_backfill(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sys.exit(main())
