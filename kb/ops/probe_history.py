#!/usr/bin/env python3
"""Turn one probe run into HISTORY, and answer the one question MANDATE §8 asks.

MANDATE §8: "A topic is current when ... the probe suite for that topic is green
against production **and has stayed green for 48h under the scheduled job**. Point
four is the only one that proves the other three." Until this file existed there
was no scheduled job and nothing recorded a run's outcome anywhere — so "stayed
green for 48h" was unmeasurable by construction, no matter how many times a lane
ran `probe_retrieval.py` by hand. This file is the ledger and the question-answerer.

TWO SUBCOMMANDS

  record   Runs `probe_retrieval.py --json` for every `kb/journeys/*.yaml` found on
           disk right now, and appends ONE line per topic to the history file
           (default `kb/ops/probe_history.jsonl`, gitignored — this is per-machine
           runtime state, the same class as the DLQ/heartbeat files this repo
           already keeps out of git).

  status   Reads the history file and answers, per topic, exactly the question
           §8 asks: has this topic been continuously at target for 48 hours? Never
           invents an answer from a single record — the answer is a computed
           streak with the evidence printed alongside it, never asserted alone.

FOUR WAYS THIS COULD LIE, AND HOW EACH IS CLOSED (read this before touching the
streak logic — the guilt/innocence matrix in the test file exists to keep these
four true, not merely once, forever):

(a) THE STREAK MUST NOT SURVIVE AN EDIT TO THE JOURNEYS. Every record carries the
    sha256 of the journeys file's bytes AT THE TIME OF THAT RUN. `status` computes
    the CURRENT file's sha256 and only counts records whose sha256 matches it
    towards the live streak. Rewrite a journey to something easier — or merely
    reorder two lines — and the sha changes, every prior record stops counting,
    and the 48h clock restarts at zero. Without this, "make the suite pass" and
    "make the suite easier" are indistinguishable to this file, and the second is
    a straight reward-hacking path to a green ledger with no work behind it. This
    is the single most important rule here.

(b) AN EMPTY RUN MUST NOT READ AS SUCCESS. Zero `kb/journeys/*.yaml` files, or a
    file that declares zero journeys inside it (which `probe_retrieval.py` itself
    reports as its own `broken`/`no_journeys` case), is recorded as the verdict
    `nothing_measured` — a member of this file's OWN closed vocabulary, never
    `at_target`, and `record` does not exit 0 when EVERY topic it looked at ended
    up `nothing_measured`. As of 2026-08-25 `kb/journeys/` holds only `.gitkeep`,
    so this is not a hypothetical: it is the exact state this file ships in, and
    `record`/`status` are exercised against it below (see module-level smoke
    invocation note in the test file).

(c) BROKEN MUST NOT COUNT AS ANYTHING. A run where `probe_retrieval.py`'s own
    control query failed graded nothing about the topic — it is an absence of
    evidence about the corpus, not evidence of anything. `broken` records are
    therefore dropped OUT of the streak timeline entirely before the streak is
    walked: they neither extend a run of `at_target` records (they prove nothing
    good happened) nor break one (they prove nothing bad happened either) DECIDED
    HERE, not left implicit — see `_streak` and the deliberate `verdict != "broken"`
    filter at its top. What they DO affect is visibility: `status` reports how many
    broken runs sit inside the window, because a topic whose "streak" is propped up
    by three broken runs in a row is not the same claim as one with 20 clean
    at_target runs, even if both currently answer "yes, 48h".

(d) A GAP IN THE RECORD MUST BREAK THE STREAK. If the scheduled job did not run for
    longer than `MAX_GAP_HOURS`, the evidence has a hole, whatever the two records
    on either side say. The threshold is `24` — not invented for this file, but
    reused from MANDATE §7's own dead-man-switch declaration for this exact probe
    ("Dead-man switch: probe silent 24h → alert"). A gap check also applies between
    the most recent gradable record and NOW: a topic whose last real measurement
    is 30 hours old is not "currently" anything, it is stale, and `status` says so
    explicitly rather than reporting a stopped clock as if it were still ticking.

Nothing here writes to Qdrant or touches `probe_retrieval.py`'s grading — this
file only runs that script as a subprocess and interprets its `--json` output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# MANDATE §7's own dead-man-switch threshold for this exact probe ("probe silent
# 24h -> alert"), reused rather than invented: a gap this file tolerates is a gap
# the mandate has already declared acceptable for the SAME job, and a gap it does
# not tolerate is one the mandate already calls an incident.
MAX_GAP_HOURS = 24

# This file's own closed vocabulary for a per-topic RECORD's verdict. The first
# four are probe_retrieval.py's own (imported by name below, never restated as
# literals — a restated copy is exactly the kind of tripwire that goes blind the
# day the two drift, per the "compares two outputs of one generator" lesson).
# `nothing_measured` is added HERE because it is a fact about the campaign's
# current state (no journeys exist to run), not about any single probe run.
NOTHING_MEASURED = "nothing_measured"


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in here.parents:
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise SystemExit("repo root not found")


def _probe_retrieval_module():
    """Import probe_retrieval.py by path (it lives outside any package) so this
    file reads its VERDICT_BY_EXIT vocabulary from the source of truth instead of
    retyping it — the exact discipline `test_kb_topic_contract.py` already applies
    to `kb_inventory_probe.py`'s PAYLOAD_SHAPES, for the same reason."""
    import importlib.util

    cached = sys.modules.get("kb_probe_retrieval")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "kb_probe_retrieval", Path(__file__).with_name("probe_retrieval.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["kb_probe_retrieval"] = module
    spec.loader.exec_module(module)
    return module


VERDICTS = frozenset(_probe_retrieval_module().VERDICT_BY_EXIT.values()) | {NOTHING_MEASURED}


def default_history_path(root: Path) -> Path:
    return root / "kb" / "ops" / "probe_history.jsonl"


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ── record ─────────────────────────────────────────────────────────────────


def run_probe_json(journeys_path: Path, collection: str, timeout_s: int = 300) -> dict:
    """Run probe_retrieval.py --json as a subprocess and return its parsed object.

    A crash or unparseable stdout is reported as this file's own `broken` shape
    (rule c: broken counts as nothing either way) rather than raised — a history
    recorder that dies because one topic's probe crashed would fail to record
    every OTHER topic in the same run, which is a worse silence than the one it
    would be reporting.
    """
    script = Path(__file__).with_name("probe_retrieval.py")
    try:
        proc = subprocess.run(
            [sys.executable, str(script), str(journeys_path),
             "--collection", collection, "--json"],
            capture_output=True, text=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {
            "journeys_file": str(journeys_path), "collection": collection,
            "verdict": "broken", "reason": "control_failed",
            "detail": "probe_retrieval.py timed out after %ds" % timeout_s,
            "exit_code": None, "degraded_path": False, "journeys": [],
        }
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except (ValueError, IndexError):
        return {
            "journeys_file": str(journeys_path), "collection": collection,
            "verdict": "broken", "reason": "control_failed",
            "detail": "probe_retrieval.py produced no parseable JSON "
                      "(rc=%s, stderr=%r)" % (proc.returncode, proc.stderr[-500:]),
            "exit_code": proc.returncode, "degraded_path": False, "journeys": [],
        }


def build_record(topic: str, journeys_path: Path, sha256: str, probe_result: dict) -> dict:
    verdict = probe_result.get("verdict") or "broken"
    if verdict not in VERDICTS:
        # Defensive, not reachable via the real subprocess today: an unrecognized
        # verdict is closer to broken (evidence about the probe itself, not the
        # topic) than to any real grading outcome.
        verdict = "broken"
    return {
        "ts": now_utc().isoformat(),
        "topic": topic,
        "journeys_path": str(journeys_path),
        "sha256": sha256,
        "verdict": verdict,
        "exit_code": probe_result.get("exit_code"),
        "degraded_path": bool(probe_result.get("degraded_path")),
        "journeys": probe_result.get("journeys") or [],
        "detail": probe_result.get("detail"),
    }


def cmd_record(args, root: Path) -> int:
    history_path = Path(args.history) if args.history else default_history_path(root)
    journeys_dir = root / "kb" / "journeys"
    files = sorted(journeys_dir.glob("*.yaml")) if journeys_dir.is_dir() else []

    records: list[dict] = []
    if not files:
        # Rule (b): zero journey files is a FACT about today's campaign state, and
        # it must be written down, not silently skipped. topic/journeys_path/sha256
        # are null because there is nothing to name.
        records.append({
            "ts": now_utc().isoformat(), "topic": None, "journeys_path": None,
            "sha256": None, "verdict": NOTHING_MEASURED, "exit_code": None,
            "degraded_path": False, "journeys": [],
            "detail": "0 kb/journeys/*.yaml files found on disk",
        })
    else:
        for path in files:
            topic = path.stem
            sha = sha256_bytes(path)
            result = run_probe_json(path, args.collection)
            if result.get("reason") == "no_journeys":
                # Rule (b) again, at the per-file granularity: this specific file
                # exists but declares nothing to run.
                rec = build_record(topic, path, sha, result)
                rec["verdict"] = NOTHING_MEASURED
                rec["detail"] = result.get("detail") or "%s declares no journeys" % path.name
            else:
                rec = build_record(topic, path, sha, result)
            records.append(rec)

    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    measured_something = any(r["verdict"] != NOTHING_MEASURED for r in records)
    for rec in records:
        label = rec["topic"] or "(no topic)"
        print("[record] %-24s verdict=%-16s sha=%s"
              % (label, rec["verdict"], (rec["sha256"] or "-")[:12]))

    if not measured_something:
        print()
        print("nothing_measured — every topic this run produced no journeys to grade "
              "(%d topic file(s) found). This is NOT success: record() intentionally "
              "does not exit 0 here." % len(files))
        return 1
    return 0


# ── status ─────────────────────────────────────────────────────────────────


def load_history(history_path: Path) -> list[dict]:
    if not history_path.is_file():
        return []
    records = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            continue  # a corrupt line is not this file's job to repair
    return records


def _streak(records_same_sha: list[dict], reference: datetime) -> dict:
    """Walk the most-recent-first, same-sha history and answer §8's question.

    `records_same_sha` must already be filtered to ONE topic and ONE sha256 (the
    CURRENT file's), and sorted ascending by timestamp — the caller's job, so this
    function has no way to silently mix two journeys versions together.
    """
    gradable = [r for r in records_same_sha if r["verdict"] != "broken"]  # rule (c)
    broken_count = sum(1 for r in records_same_sha if r["verdict"] == "broken")

    if not gradable:
        return {
            "at_target_48h": False, "currently_at_target": False, "stale": None,
            "first_green": None, "elapsed_hours": 0.0, "runs_in_window": 0,
            "broken_runs_in_window": broken_count,
            "reason": "no gradable (non-broken) runs at the current journeys sha",
        }

    latest = gradable[-1]
    latest_ts = parse_ts(latest["ts"])
    gap_to_now = (reference - latest_ts).total_seconds() / 3600
    stale = gap_to_now > MAX_GAP_HOURS  # rule (d), applied to the "now" edge too

    if latest["verdict"] != "at_target":
        return {
            "at_target_48h": False, "currently_at_target": False, "stale": stale,
            "first_green": None, "elapsed_hours": 0.0, "runs_in_window": 0,
            "broken_runs_in_window": broken_count,
            "reason": "latest run at current sha is %r, not at_target" % latest["verdict"],
        }

    first_green_ts = latest_ts
    prev_ts = latest_ts
    runs_in_window = 1
    for rec in reversed(gradable[:-1]):
        if rec["verdict"] != "at_target":
            break  # a non-at_target run inside the window ends the streak here
        ts = parse_ts(rec["ts"])
        gap_hours = (prev_ts - ts).total_seconds() / 3600
        if gap_hours > MAX_GAP_HOURS:
            break  # rule (d): a hole in the record, not evidence of 48h
        first_green_ts = ts
        prev_ts = ts
        runs_in_window += 1

    if stale:
        # rule (d): the streak that WAS built is real evidence up to latest_ts,
        # but it is not evidence that the topic is at target RIGHT NOW.
        elapsed = (latest_ts - first_green_ts).total_seconds() / 3600
        return {
            "at_target_48h": False, "currently_at_target": False, "stale": True,
            "first_green": first_green_ts.isoformat(), "elapsed_hours": round(elapsed, 1),
            "runs_in_window": runs_in_window, "broken_runs_in_window": broken_count,
            "reason": "last gradable run was %.1fh ago (> %dh) — no recent evidence"
                      % (gap_to_now, MAX_GAP_HOURS),
        }

    elapsed = (reference - first_green_ts).total_seconds() / 3600
    return {
        "at_target_48h": elapsed >= 48.0, "currently_at_target": True, "stale": False,
        "first_green": first_green_ts.isoformat(), "elapsed_hours": round(elapsed, 1),
        "runs_in_window": runs_in_window, "broken_runs_in_window": broken_count,
        "reason": "continuously at_target since first_green" if elapsed >= 48.0
                  else "at_target now, but only %.1fh of the 48h window covered" % elapsed,
    }


def cmd_status(args, root: Path) -> int:
    history_path = Path(args.history) if args.history else default_history_path(root)
    records = load_history(history_path)
    journeys_dir = root / "kb" / "journeys"

    topics = sorted({r["topic"] for r in records if r.get("topic")})
    if not records or not topics:
        print("nothing_measured — no history recorded (%s: %d record(s), %d topic(s))"
              % (history_path, len(records), len(topics)))
        return 1

    reference = now_utc()
    any_current = False
    edited_since_last_record = 0
    for topic in topics:
        topic_records = [r for r in records if r.get("topic") == topic]
        journeys_path = journeys_dir / ("%s.yaml" % topic)
        if not journeys_path.is_file():
            print("[status] %-24s MISSING — kb/journeys/%s.yaml no longer on disk, "
                  "%d historical record(s) orphaned" % (topic, journeys_path.name,
                                                          len(topic_records)))
            continue
        current_sha = sha256_bytes(journeys_path)
        same_sha = sorted(
            (r for r in topic_records if r.get("sha256") == current_sha),
            key=lambda r: r["ts"],
        )
        if topic_records and not same_sha:
            # Rule (a): every record on file predates the current bytes — the
            # journeys changed since the last recorded run, so there is zero
            # continuing evidence, not "unknown" evidence.
            edited_since_last_record += 1
        result = _streak(same_sha, reference)
        any_current = any_current or result["at_target_48h"]
        verdict = "AT-TARGET-48H" if result["at_target_48h"] else (
            "STALE" if result["stale"] else "NOT-YET")
        print(
            "[status] %-24s %-14s first_green=%s elapsed=%.1fh runs=%d broken=%d — %s"
            % (topic, verdict, result["first_green"] or "-", result["elapsed_hours"],
               result["runs_in_window"], result["broken_runs_in_window"], result["reason"])
        )

    if edited_since_last_record:
        print()
        print("(%d topic(s) have history but every recorded sha256 predates the "
              "current file — the journeys changed since the last recorded run; "
              "the 48h clock for those restarted at zero per rule (a))"
              % edited_since_last_record)

    return 0 if any_current else 1


# ── CLI ────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_record = sub.add_parser("record", help="run every kb/journeys/*.yaml and append history")
    p_record.add_argument("--collection", default="legal_unified")
    p_record.add_argument("--history", default=None,
                           help="override the history file path (default kb/ops/probe_history.jsonl)")

    p_status = sub.add_parser("status", help="answer MANDATE §8's 48h-continuous question per topic")
    p_status.add_argument("--history", default=None)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    root = repo_root()
    if args.command == "record":
        return cmd_record(args, root)
    if args.command == "status":
        return cmd_status(args, root)
    raise AssertionError("unreachable: argparse enforces the subcommand vocabulary")


if __name__ == "__main__":
    raise SystemExit(main())
