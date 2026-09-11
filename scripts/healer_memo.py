#!/usr/bin/env python3
"""healer_memo.py — memoize pro-healer's LLM spawn on the organ-state fingerprint.

D-004 (~/.tokenaudit/DECISIONS.md): skip the headless-Claude spawn when nothing
changed and the last verdict was "incurable". Measured in T3
(~/.tokenaudit/reports/04-rightsizing.md): 5/9 pro-healer ticks held an
identical organ-state AND an identical incurable verdict — the healer spawned
a `--max-budget-usd 10` session against the same dead organs, tick after tick,
for zero new information (`shared/escalations_pro.jsonl` carries 8 open HIGH
`healer_pro_tick` entries of the shape "N dead organs ... 0/N curable").

The fingerprint MUST include the heartbeat status (not just the count) of the
dead organs — the revision criterion D-004 names explicitly: two ticks with
the same COUNT of dead organs are not the same state if a different organ
died, or the same organ's status text changed.

Subcommands:
    fingerprint                Read a receptor-state JSON object on stdin,
                                print its deterministic sha256 hex.
    check                      Decide SPAWN (exit 0) vs SKIP (exit 3) against
                                a persisted state file.
    record                     Persist {fingerprint, verdict, spawned_at}.
    verdict-from-escalations   Classify the newest `healer_pro_tick` line in
                                shared/escalations_pro.jsonl since a given
                                time as incurable / cured / unknown.

Kill switch: env PRO_HEALER_MEMO=0 (or false/no/off/disabled) makes `check`
always exit 0 (SPAWN) with reason "memo disabled" — never suppresses a cure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("healer_memo")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s healer_memo: %(message)s"
    )

KILL_SWITCH_ENV = "PRO_HEALER_MEMO"
DEFAULT_MAX_AGE_H = 24.0
DEFAULT_MAX_SKIPS = 3
AGE_BUCKET_CAP_H = 48

EXIT_SPAWN = 0
EXIT_SKIP = 3

VALID_VERDICTS = ("incurable", "cured", "unknown")


def _kill_switch_disabled() -> bool:
    val = os.environ.get(KILL_SWITCH_ENV, "").strip().lower()
    return val in {"0", "false", "no", "off", "disabled"}


# ---------------------------------------------------------------------------
# fingerprint
# ---------------------------------------------------------------------------


def _age_bucket(age_s: Any) -> int:
    """floor(age_s / 3600) capped at AGE_BUCKET_CAP_H.

    A malformed/missing age must never crash the fingerprint (it would take
    down the healer's pre-check with it) — it degrades to bucket 0, which
    only means "this organ's age never distinguishes two states on its own",
    not that the organ is ignored (id/status/recovery_action still count).
    """
    try:
        age = float(age_s)
    except (TypeError, ValueError):
        return 0
    if age < 0:
        return 0
    return min(int(age // 3600), AGE_BUCKET_CAP_H)


def fingerprint(receptor_state: dict) -> str:
    """Deterministic sha256 hex over the organ-state shape D-004 names.

    Every axis is sorted so neither dict/list iteration order nor JSON key
    order can perturb the hash across two runs that observed the same state.
    """
    dead = receptor_state.get("dead_organs") or []
    dead_tuples = sorted(
        (
            str(o.get("id", "")),
            str(o.get("status", "")),
            str(o.get("recovery_action", "")),
            _age_bucket(o.get("age_s")),
        )
        for o in dead
        if isinstance(o, dict)
    )

    diverged = sorted(str(p) for p in (receptor_state.get("diverged_probes") or []))
    drifted = sorted(str(p) for p in (receptor_state.get("drifted_pairs") or []))
    arsenal_new_dead = sorted(
        str(t) for t in (receptor_state.get("arsenal_new_dead") or [])
    )
    reasons_tokens = sorted(
        tok for tok in str(receptor_state.get("reasons", "")).split() if tok
    )

    canonical = {
        "dead_organs": [list(t) for t in dead_tuples],
        "diverged_probes": diverged,
        "drifted_pairs": drifted,
        "arsenal_new_dead": arsenal_new_dead,
        "reasons_tokens": reasons_tokens,
    }
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# state file I/O
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _load_state(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    s = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# escalation-log verdict classification
# ---------------------------------------------------------------------------

_CURABLE_FRACTION_RE = re.compile(r"\b(\d+)/(\d+)\s*curable\b", re.IGNORECASE)
_CURED_WORD_RE = re.compile(r"\b(cured|healed)\b", re.IGNORECASE)


def _classify_summary(text: str) -> str:
    """incurable if the newest tick reads "0/N curable"; cured if it reads
    "N/N curable" with N>0, or names "cured"/"healed"; unknown otherwise
    (including a partial "k/N curable" with 0<k<N — a partial cure is not the
    all-clear that lets the memo skip the NEXT spawn)."""
    m = _CURABLE_FRACTION_RE.search(text)
    if m:
        num, den = int(m.group(1)), int(m.group(2))
        if num == 0:
            return "incurable"
        if num == den:
            return "cured"
    if _CURED_WORD_RE.search(text):
        return "cured"
    return "unknown"


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------


def cmd_fingerprint(args: argparse.Namespace) -> int:
    raw = sys.stdin.read()
    try:
        receptor_state = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON on stdin: {exc}", file=sys.stderr)
        return 1
    if not isinstance(receptor_state, dict):
        print("ERROR: receptor state JSON must be an object", file=sys.stderr)
        return 1
    print(fingerprint(receptor_state))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    if _kill_switch_disabled():
        print("SPAWN: memo disabled (PRO_HEALER_MEMO=0)")
        return EXIT_SPAWN

    state_path = Path(args.state).expanduser()
    state = _load_state(state_path)
    if state is None:
        print("SPAWN: no usable prior state (first run or unreadable state file)")
        return EXIT_SPAWN

    if state.get("fingerprint") != args.fingerprint:
        print("SPAWN: organ-state fingerprint changed since last spawn")
        return EXIT_SPAWN

    if state.get("verdict") != "incurable":
        print(f"SPAWN: last verdict was {state.get('verdict')!r}, not incurable")
        return EXIT_SPAWN

    spawned_at = _parse_iso(str(state.get("spawned_at", "")))
    if spawned_at is None:
        print("SPAWN: last spawn timestamp missing/unparseable")
        return EXIT_SPAWN

    age_h = (datetime.now(timezone.utc) - spawned_at).total_seconds() / 3600.0
    if age_h > args.max_age_h:
        print(f"SPAWN: last spawn {age_h:.1f}h ago exceeds max-age {args.max_age_h}h")
        return EXIT_SPAWN
    if age_h < 0:
        # Clock skew / future timestamp — do not trust it as "fresh", spawn.
        print("SPAWN: last spawn timestamp is in the future — refusing to trust it")
        return EXIT_SPAWN

    try:
        skips = int(state.get("skips", 0) or 0)
    except (TypeError, ValueError):
        skips = 0
    if skips >= args.max_skips:
        print(f"SPAWN: skip streak {skips} reached max-skips {args.max_skips}")
        return EXIT_SPAWN

    # SKIP: identical fingerprint, still-incurable verdict, still fresh, still
    # under the skip budget. Only mutation on the SKIP path — record() owns
    # every other write.
    state["skips"] = skips + 1
    state["recorded_at"] = _utc_now_iso()
    try:
        _atomic_write_json(state_path, state)
    except OSError as exc:
        logger.warning("could not persist skip counter to %s: %s", state_path, exc)
    print(
        "SKIP: memoized (fingerprint unchanged, last verdict incurable, "
        f"age={age_h:.1f}h<{args.max_age_h}h, skip {skips + 1}/{args.max_skips})"
    )
    return EXIT_SKIP


def cmd_record(args: argparse.Namespace) -> int:
    state_path = Path(args.state).expanduser()
    data = {
        "fingerprint": args.fingerprint,
        "verdict": args.verdict,
        "spawned_at": args.spawned_at,
        "skips": 0,
        "recorded_at": _utc_now_iso(),
    }
    _atomic_write_json(state_path, data)
    print(
        f"recorded: fingerprint={args.fingerprint[:12]}... verdict={args.verdict} "
        f"spawned_at={args.spawned_at}"
    )
    return 0


def cmd_verdict_from_escalations(args: argparse.Namespace) -> int:
    path = Path(args.file).expanduser()
    since_dt = _parse_iso(args.since) or datetime.fromtimestamp(0, tz=timezone.utc)
    since_epoch = since_dt.timestamp()

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        print("unknown")
        return 0

    newest_ts: float | None = None
    newest_summary = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict) or obj.get("job") != "healer_pro_tick":
            continue
        try:
            ts = float(obj.get("ts"))
        except (TypeError, ValueError):
            continue
        if ts < since_epoch:
            continue
        if newest_ts is None or ts > newest_ts:
            newest_ts = ts
            newest_summary = str(obj.get("error_summary", ""))

    if newest_ts is None:
        print("unknown")
        return 0
    print(_classify_summary(newest_summary))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_fp = sub.add_parser(
        "fingerprint", help="sha256 hex of a receptor-state JSON object read from stdin"
    )
    p_fp.set_defaults(func=cmd_fingerprint)

    p_check = sub.add_parser(
        "check", help="SPAWN (exit 0) vs SKIP (exit 3) against a persisted state file"
    )
    p_check.add_argument("--state", required=True)
    p_check.add_argument("--fingerprint", required=True)
    p_check.add_argument("--max-age-h", type=float, default=DEFAULT_MAX_AGE_H)
    p_check.add_argument("--max-skips", type=int, default=DEFAULT_MAX_SKIPS)
    p_check.set_defaults(func=cmd_check)

    p_record = sub.add_parser("record", help="persist fingerprint/verdict/spawn time")
    p_record.add_argument("--state", required=True)
    p_record.add_argument("--fingerprint", required=True)
    p_record.add_argument("--verdict", required=True, choices=VALID_VERDICTS)
    p_record.add_argument("--spawned-at", required=True)
    p_record.set_defaults(func=cmd_record)

    p_verdict = sub.add_parser(
        "verdict-from-escalations",
        help="classify the newest healer_pro_tick escalation since a given time",
    )
    p_verdict.add_argument("--file", required=True)
    p_verdict.add_argument("--since", required=True)
    p_verdict.set_defaults(func=cmd_verdict_from_escalations)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
