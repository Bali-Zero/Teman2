#!/usr/bin/env python3
"""seat_mix_report.py -- A7/R12 daily seat-mix telemetry, joined to PRs.

The fleet dispatches subagents (Agent tool: model + subagent_type) and shells
out to a whole cross-family arsenal (codex/kimi/agy/ollama/nlm/seat_build/...)
from inside Claude Code sessions, but until this script existed nobody had
ever counted the mix -- a one-off hand parse on 2026-08-26 found 882 Agent
dispatches fleet-wide in 48h (sonnet 86%, haiku 0.9%, opus the rest) and
~512 non-Anthropic shell calls, never published or repeatable.

This script stream-parses Claude Code's own project transcripts
(``~/.claude/projects/**/*.jsonl``) inside a time window and counts, purely
structurally:

  - ``Agent`` tool_use blocks, by ``input.model`` (missing -> "inherit") and
    by ``input.subagent_type``.
  - ``Bash`` tool_use blocks, by classifying ``input.command`` against a small
    fixed SEAT VOCABULARY (codex/kimi/agy/seat_build/ollama/nlm/jules/tp1).
    The matched LABEL is kept; the raw command text is discarded immediately
    -- classification never copies free text into the report.
  - ``Workflow`` tool_use blocks (a bare count).

Session -> PR join is best-effort: the JSONL ``gitBranch`` field (when
present) is looked up via ``gh pr list --search "head:<branch>"``; failures
(no gh, no network, no match) just leave that session unmapped.

PII BOUNDARY (SYMBIOSIS Law 2): transcripts carry client PII inside
``tool_result`` blocks and free-text ``text`` blocks. This module NEVER reads
either -- it only ever looks at ``message.content[].type == "tool_use"``
blocks' ``name`` field and a handful of specific, narrow-charset regex
captures out of ``input.command`` / ``input.model`` / ``input.subagent_type``.
Every string that reaches the report is additionally passed through
``sanitize_str`` (truncate + strip to a fixed safe charset) at the point of
extraction, and ``assert_all_strings_safe`` re-walks the whole report as a
hard defense-in-depth gate right before anything is written or printed.

Usage:
  python3 scripts/seat_mix_report.py --since 48
  python3 scripts/seat_mix_report.py --since 24 --json /tmp/x.json --md /tmp/x.md
  python3 scripts/seat_mix_report.py --since 24 --no-map-prs   # skip gh entirely
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

WITA = timezone(timedelta(hours=8))

# Organism genes (organ-conformance G2/G5, born 2026-08-27): this organ must
# prove its own liveness every run (heartbeat on BOTH success and failure —
# superscar #2, esiste != armato) and honor an operator kill switch that
# leaves a "disabled" heartbeat behind so the healer never resurrects an
# intentionally-stopped organ (genes.json G5's own stated reason). Same
# convention as scripts/queue_shepherd.py's SEAT_MIX_REPORT_ENABLED /
# ORGAN_ID / _write_heartbeat shape.
SEAT_MIX_REPORT_ENABLED = os.environ.get("SEAT_MIX_REPORT_ENABLED", "true")
ORGANISM_DIR = Path(os.path.expanduser("~/.organism/last_seen"))
ORGAN_ID = "pro.seat_mix_report"


def _enabled() -> bool:
    return SEAT_MIX_REPORT_ENABLED.strip().lower() not in ("false", "0", "no", "off")


def _write_heartbeat(status: str, metadata: dict) -> None:
    """Unconditional organism heartbeat sidecar — never raises (a heartbeat
    write must never break the run it is reporting on). Atomic tmp+replace."""
    try:
        ORGANISM_DIR.mkdir(parents=True, exist_ok=True)
        organ_path = ORGANISM_DIR / f"{ORGAN_ID}.json"
        organ_tmp = organ_path.with_suffix(f".json.tmp.{os.getpid()}")
        organ_tmp.write_text(
            json.dumps({"ts": time.time(), "status": status, "organ_id": ORGAN_ID, "metadata": metadata})
        )
        organ_tmp.replace(organ_path)
    except Exception as exc:  # noqa: BLE001 — heartbeat must never break the run
        print(f"[seat-mix] organ heartbeat emit failed: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# PII / output guard
# ---------------------------------------------------------------------------

# Deliberately narrow: letters, digits, space, and a small punctuation set
# that covers paths, ratios, percentages, dates and branch/seat labels. No
# '@', no '+', no backslash, no quotes -- a FULL email or a phone number
# written with its '+' cannot survive this charset intact.
#
# This charset alone is NOT sufficient PII/secret protection by itself, and
# is not claimed to be: it is a superset of common secret/token shapes
# (sk-/ghp_-style keys and bare-digit phone numbers are all
# letters/digits/hyphens, which this class allows). classify_bash_seat's
# free-form flag captures (--model/--seat/--tier/ollama's model argument)
# additionally run through _redact_if_sensitive() BEFORE reaching this
# charset check, specifically because the charset does not catch them (found
# live by the Kimi K3 refuter on this PR's own diff). The real PII boundary
# is architectural, not this regex: the scanner never reads tool_result or
# free-text `text` blocks at all, and codex/kimi tier labels come from a
# fixed enumeration that can never contain arbitrary captured text.
SAFE_STRING_RE = re.compile(r"^[A-Za-z0-9 _./:%()\-=,]+$")
MAX_STRING_LEN = 120


def sanitize_str(value, maxlen: int = MAX_STRING_LEN) -> str:
    """Coerce ``value`` to a string that is guaranteed to satisfy the guard.

    Never raises. Unknown/empty input becomes ``"unknown"``. Any character
    outside SAFE_STRING_RE's class is replaced with ``_`` rather than
    dropped, so the length of the informative part is still legible.
    """
    if value is None:
        return "unknown"
    s = str(value)[:maxlen]
    s = re.sub(r"[^A-Za-z0-9 _./:%()\-=,]", "_", s)
    return s if s else "unknown"


def assert_all_strings_safe(obj, path: str = "$") -> None:
    """Recursively assert every string leaf in ``obj`` satisfies the guard.

    Defense-in-depth: everything that reaches the report is already built
    via ``sanitize_str`` or a narrow-charset regex capture, so this should
    never fire. It is not wrapped in try/except anywhere -- a violation here
    means the extraction logic regressed, and the report must not ship
    silently corrupted (superscar #2: a swallowed exception here would be
    exactly the "green but wrong" failure mode this script exists to avoid
    in others).
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert_all_strings_safe(k, f"{path}.{k}")
            assert_all_strings_safe(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            assert_all_strings_safe(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        if len(obj) > MAX_STRING_LEN or not SAFE_STRING_RE.match(obj):
            raise ValueError(
                f"seat_mix_report guard violation at {path}: string of len "
                f"{len(obj)} fails the output-safety charset"
            )


# ---------------------------------------------------------------------------
# Bash seat-vocabulary classifier
# ---------------------------------------------------------------------------

_CODEX_INVOKE_RE = re.compile(r"\bcodex\s+exec\b")
_CODEX_TIER_RE = re.compile(r"-m\s+[\"']?gpt-5\.6-(sol|terra|luna)\b")

_KIMI_INVOKE_RE = re.compile(r"(?:^|[\s;&|])kimi\s")
# Longest alternative first (W-class gotcha): "kimi-for-coding" is a strict
# prefix of "kimi-for-coding-highspeed" -- if the short form were tried
# first, re.search would stop there and every highspeed call would be
# misclassified as the plain coding tier.
_KIMI_MODEL_RE = re.compile(
    r"-m\s+kimi-code/(kimi-for-coding-highspeed|kimi-for-coding|k3)\b"
)

_AGY_INVOKE_RE = re.compile(r"(?:^|[\s;&|])agy\s")
_AGY_MODEL_RE = re.compile(r"--model[= ]([A-Za-z0-9_./\-]+)")

_SEATBUILD_INVOKE_RE = re.compile(r"\bseat_build\.sh\b")
_SEATBUILD_SEAT_RE = re.compile(r"--seat[= ]([A-Za-z0-9_./\-]+)")
_SEATBUILD_TIER_RE = re.compile(r"--tier[= ]([A-Za-z0-9_./\-]+)")

_OLLAMA_RUN_RE = re.compile(r"\bollama\s+run\s+([A-Za-z0-9_./:\-]+)")

# "nlm" is a short token and needs both boundaries (avoid matching inside an
# unrelated longer word). "notebooklm" is almost always a PREFIX of a real
# script/module name in this repo (notebooklm_bridge.py, notebooklm-mcp, ...)
# so it only needs a leading boundary -- requiring a trailing one too would
# systematically under-match the real usage (family #3's UNDER-match twin).
_NLM_RE = re.compile(r"\bnlm\b|\bnotebooklm")
_JULES_RE = re.compile(r"\bjules_dispatch\.py\b")
_TP1_RE = re.compile(r"\b(?:tp1_call|review_routes)\b")

# A command segment whose own first word is a read/inspect/edit verb is never
# an INVOCATION of anything named later in that segment -- "cat seat_build.sh"
# and "grep review_routes -r ." must not count as seat calls just because a
# vocabulary token appears as an argument (found live by the Kimi K3 refuter
# on this PR's own diff: this repo's whole job is editing these very scripts,
# so this over-match would have been a systematic, not theoretical, inflation
# source). Interpreters that legitimately RUN a vocabulary script
# (python3/bash/sh/./) are deliberately NOT on this list.
_NON_INVOCATION_VERBS = frozenset(
    {
        "cat", "grep", "rg", "less", "more", "head", "tail", "vim", "vi",
        "nano", "code", "open", "git", "find", "wc", "diff", "sed", "awk",
        "ls", "stat", "file", "cp", "mv", "rm",
    }
)
_SEGMENT_SPLIT_RE = re.compile(r"[;&|]+")
_FIRST_TOKEN_RE = re.compile(r"^\s*(\S+)")

# Sub-values captured from a free-form flag (--model/--seat/--tier/ollama's
# model argument) come from ARBITRARY command text, not a fixed enumeration
# like the codex/kimi tiers above -- so, unlike those, they must be screened
# for secret/PII shape before they reach the report. A value matching either
# check is replaced with the fixed literal "redacted" rather than propagated
# even in sanitized form (found live by the Kimi K3 refuter: the sanitizer's
# safe charset is a SUPERSET of common secret shapes -- sk-/ghp_-style keys
# and phone numbers made of digits/hyphens pass the charset check untouched,
# so the charset guard alone does not close this gap).
_SECRET_PREFIX_RE = re.compile(
    r"^(?:sk-|sk_|ghp_|gho_|ghs_|ghr_|github_pat_|akia|xox[a-z]-|eyj)",
    re.IGNORECASE,
)


def _redact_if_sensitive(raw: str, maxlen: int) -> str:
    if _SECRET_PREFIX_RE.match(raw) or sum(ch.isdigit() for ch in raw) >= 7:
        return "redacted"
    return sanitize_str(raw, maxlen)


def classify_bash_seat(command) -> Optional[str]:
    """Classify a Bash ``input.command`` string into a seat-vocabulary label.

    Returns ``None`` for anything outside the fixed vocabulary (most Bash
    calls -- ``ls``, ``git``, ``pytest``, ...) -- those are not "seats" and
    are not counted. Entity/intent boundaries throughout (``\\b`` anchors,
    a required invocation token before any flag is inspected, a first-token
    invocation-verb check per ``;``/``&&``/``|``-separated segment) rather
    than bare substring matching, per cicatrix family #3: "the codex
    executable", "kimi-something-else.py", and "cat seat_build.sh" must NOT
    match.
    """
    if not command or not isinstance(command, str):
        return None

    for segment in _SEGMENT_SPLIT_RE.split(command):
        tok = _FIRST_TOKEN_RE.match(segment)
        if tok:
            first = tok.group(1).rsplit("/", 1)[-1]
            if first in _NON_INVOCATION_VERBS:
                continue  # this segment only READS/EDITS a name, never runs it

        if _CODEX_INVOKE_RE.search(segment):
            m = _CODEX_TIER_RE.search(segment)
            return f"codex:{m.group(1)}" if m else "codex:default"

        if _KIMI_INVOKE_RE.search(segment):
            m = _KIMI_MODEL_RE.search(segment)
            return f"kimi:{m.group(1)}" if m else "kimi:default"

        if _AGY_INVOKE_RE.search(segment):
            m = _AGY_MODEL_RE.search(segment)
            return f"agy:{_redact_if_sensitive(m.group(1), 40)}" if m else "agy:default"

        if _SEATBUILD_INVOKE_RE.search(segment):
            seat = _SEATBUILD_SEAT_RE.search(segment)
            tier = _SEATBUILD_TIER_RE.search(segment)
            if seat or tier:
                seat_v = _redact_if_sensitive(seat.group(1), 30) if seat else "unset"
                tier_v = _redact_if_sensitive(tier.group(1), 30) if tier else "unset"
                return f"seat_build:{seat_v}/{tier_v}"
            return "seat_build:default"

        m = _OLLAMA_RUN_RE.search(segment)
        if m:
            return f"ollama:{_redact_if_sensitive(m.group(1), 40)}"

        if _NLM_RE.search(segment):
            return "nlm"

        if _JULES_RE.search(segment):
            return "jules_dispatch"

        if _TP1_RE.search(segment):
            return "tp1"

    return None


# ---------------------------------------------------------------------------
# PR join (best-effort, injectable for tests)
# ---------------------------------------------------------------------------

PrLookup = Callable[[str], Optional[str]]


def gh_pr_lookup(branch: str) -> Optional[str]:
    """Best-effort ``gh pr list --search "head:<branch>"`` -> PR number.

    Never raises -- any failure (no gh, no network, no auth, bad JSON, no
    match) returns None and the caller treats the session as unmapped.
    """
    try:
        proc = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--search",
                f"head:{branch}",
                "--state",
                "all",  # most branches have already merged & closed by report time
                "--json",
                "number",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout or "[]")
        if isinstance(data, list) and data:
            n = data[0].get("number")
            if isinstance(n, int):
                return str(n)
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# Core scan
# ---------------------------------------------------------------------------

DEFAULT_MAX_FILE_BYTES = 200 * 1024 * 1024  # 200 MB


def build_report(
    root: Path,
    *,
    since_epoch: float,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    pr_lookup: Optional[PrLookup] = None,
) -> dict:
    """Scan every ``*.jsonl`` under ``root`` touched since ``since_epoch``.

    Pure function of (filesystem, clock) -- no argparse, no printing, so it
    is directly unit-testable against a fixture tree.
    """
    files = sorted(root.glob("**/*.jsonl")) if root.is_dir() else []

    sessions_scanned = 0
    files_skipped = 0

    agent_total = 0
    agent_by_model: Counter = Counter()
    agent_by_subagent: Counter = Counter()

    seat_calls: Counter = Counter()
    workflow_runs = 0

    per_pr: dict = defaultdict(lambda: {"agent_dispatches": 0, "seat_calls": 0, "sessions": 0})
    unmapped_sessions = 0
    pr_cache: dict = {}

    for fp in files:
        try:
            st = fp.stat()
        except OSError:
            continue

        if st.st_mtime < since_epoch:
            continue  # out of window -- not scanned, not "skipped"

        if st.st_size > max_file_bytes:
            files_skipped += 1
            continue

        sessions_scanned += 1

        branch = None
        session_agent_total = 0
        session_seat_total = 0

        try:
            with fp.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue

                    if branch is None:
                        b = rec.get("gitBranch")
                        if isinstance(b, str) and b:
                            branch = b

                    msg = rec.get("message")
                    if not isinstance(msg, dict):
                        continue
                    content = msg.get("content")
                    if not isinstance(content, list):
                        continue

                    for block in content:
                        if not isinstance(block, dict) or block.get("type") != "tool_use":
                            continue
                        name = block.get("name")
                        inp = block.get("input")
                        if not isinstance(inp, dict):
                            inp = {}

                        if name == "Agent":
                            agent_total += 1
                            session_agent_total += 1
                            model = inp.get("model") or "inherit"
                            agent_by_model[sanitize_str(model, 40)] += 1
                            subagent = inp.get("subagent_type") or "unspecified"
                            agent_by_subagent[sanitize_str(subagent, 60)] += 1

                        elif name == "Bash":
                            label = classify_bash_seat(inp.get("command"))
                            if label:
                                seat_calls[label] += 1
                                session_seat_total += 1
                            # raw command text is never retained past this point

                        elif name == "Workflow":
                            workflow_runs += 1
        except OSError:
            continue

        if session_agent_total or session_seat_total:
            pr_number = None
            if pr_lookup and branch:
                if branch not in pr_cache:
                    pr_cache[branch] = pr_lookup(branch)
                pr_number = pr_cache[branch]
            if pr_number:
                bucket = per_pr[sanitize_str(pr_number, 20)]
                bucket["agent_dispatches"] += session_agent_total
                bucket["seat_calls"] += session_seat_total
                bucket["sessions"] += 1
            else:
                unmapped_sessions += 1

    cheap_dispatches = sum(v for k, v in agent_by_model.items() if "haiku" in k.lower())
    non_anthropic_total = sum(seat_calls.values())

    by_model_pct = {}
    if agent_total:
        for k, v in agent_by_model.items():
            by_model_pct[k] = round(v * 100.0 / agent_total, 1)

    report = {
        "generated_at": datetime.now(WITA).strftime("%Y-%m-%d %H:%M:%S WITA"),
        "window_hours": None,  # filled in by main() -- build_report doesn't know it
        "sessions_scanned": sessions_scanned,
        "files_skipped": files_skipped,
        "agent_dispatches": {
            "total": agent_total,
            "by_model": dict(agent_by_model),
            "by_model_pct": by_model_pct,
            "by_subagent_type": dict(agent_by_subagent),
            "cheap_seat_share_pct": (
                round(cheap_dispatches * 100.0 / agent_total, 1) if agent_total else None
            ),
        },
        "non_anthropic_seat_calls": {
            "total": non_anthropic_total,
            "per_anthropic_dispatch": (
                round(non_anthropic_total / agent_total, 2) if agent_total else None
            ),
            "by_seat": dict(seat_calls),
        },
        "workflow_runs": workflow_runs,
        "per_pr": dict(per_pr),
        "unmapped_sessions_with_activity": unmapped_sessions,
    }
    return report


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_markdown(report: dict) -> str:
    lines = []
    lines.append("# Seat-mix daily report")
    lines.append("")
    lines.append(f"- generated_at: {report['generated_at']}")
    lines.append(f"- window_hours: {report.get('window_hours')}")
    lines.append(f"- sessions_scanned: {report['sessions_scanned']}")
    lines.append(f"- files_skipped (over size cap): {report['files_skipped']}")
    lines.append("")

    ad = report["agent_dispatches"]
    lines.append("## Agent dispatch mix")
    lines.append("")
    lines.append(f"Total Agent dispatches: {ad['total']}")
    lines.append("")
    if ad["by_model"]:
        lines.append("| model | count | pct |")
        lines.append("|---|---|---|")
        for k in sorted(ad["by_model"], key=lambda x: -ad["by_model"][x]):
            pct = ad["by_model_pct"].get(k, 0)
            lines.append(f"| {k} | {ad['by_model'][k]} | {pct}% |")
        lines.append("")
    cheap = ad.get("cheap_seat_share_pct")
    lines.append(f"cheap_seat_share_pct (haiku share): {cheap if cheap is not None else 'n/a'}%")
    lines.append("")
    if ad["by_subagent_type"]:
        lines.append("| subagent_type | count |")
        lines.append("|---|---|")
        for k in sorted(ad["by_subagent_type"], key=lambda x: -ad["by_subagent_type"][x]):
            lines.append(f"| {k} | {ad['by_subagent_type'][k]} |")
        lines.append("")

    nac = report["non_anthropic_seat_calls"]
    lines.append("## Non-Anthropic seat calls (Bash)")
    lines.append("")
    lines.append(f"Total: {nac['total']}")
    ratio = nac.get("per_anthropic_dispatch")
    lines.append(f"Per Anthropic dispatch: {ratio if ratio is not None else 'n/a'}")
    lines.append("")
    if nac["by_seat"]:
        lines.append("| seat | count |")
        lines.append("|---|---|")
        for k in sorted(nac["by_seat"], key=lambda x: -nac["by_seat"][x]):
            lines.append(f"| {k} | {nac['by_seat'][k]} |")
        lines.append("")

    lines.append("## Workflow tool")
    lines.append("")
    lines.append(f"workflow_runs: {report['workflow_runs']}")
    lines.append("")

    lines.append("## Per-PR seat counts (best-effort branch join)")
    lines.append("")
    lines.append(f"unmapped_sessions_with_activity: {report['unmapped_sessions_with_activity']}")
    lines.append("")
    if report["per_pr"]:
        lines.append("| PR | agent_dispatches | seat_calls | sessions |")
        lines.append("|---|---|---|---|")
        for pr, v in sorted(report["per_pr"].items(), key=lambda kv: -kv[1]["agent_dispatches"]):
            lines.append(f"| {pr} | {v['agent_dispatches']} | {v['seat_calls']} | {v['sessions']} |")
        lines.append("")
    else:
        lines.append("(no session mapped to a PR in this window)")
        lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=float, default=24.0, help="lookback window in hours (default 24)")
    ap.add_argument(
        "--projects-root",
        default=str(Path.home() / ".claude" / "projects"),
        help="root to scan recursively for *.jsonl (default ~/.claude/projects)",
    )
    ap.add_argument("--json", dest="json_out", default=None, help="output JSON path")
    ap.add_argument("--md", dest="md_out", default=None, help="output Markdown path")
    ap.add_argument(
        "--max-file-mb",
        type=float,
        default=200.0,
        help="skip (and count) any transcript file larger than this, in MB (default 200)",
    )
    ap.add_argument("--map-prs", dest="map_prs", action="store_true", default=True)
    ap.add_argument(
        "--no-map-prs",
        dest="map_prs",
        action="store_false",
        help="skip the gh pr list branch->PR join entirely",
    )
    args = ap.parse_args(argv)

    if not _enabled():
        # G5 kill switch: leave a "disabled" heartbeat so the healer never
        # tries to resurrect an intentionally-stopped organ, and still print
        # a receipt line (superscar #2: a mute cron reads as a dead cron).
        _write_heartbeat("disabled", {"reason": "SEAT_MIX_REPORT_ENABLED=false"})
        print("[seat-mix] SEAT_MIX_REPORT_ENABLED=false -- no-op run (receipt line, superscar #2)", file=sys.stderr)
        return 0

    try:
        since_epoch = time.time() - args.since * 3600.0
        max_file_bytes = int(args.max_file_mb * 1024 * 1024)

        pr_lookup: Optional[PrLookup] = None
        if args.map_prs and shutil.which("gh"):
            pr_lookup = gh_pr_lookup

        report = build_report(
            Path(os.path.expanduser(args.projects_root)),
            since_epoch=since_epoch,
            max_file_bytes=max_file_bytes,
            pr_lookup=pr_lookup,
        )
        report["window_hours"] = args.since

        assert_all_strings_safe(report)

        date_str = datetime.now(WITA).strftime("%Y-%m-%d")
        default_dir = Path.home() / "logs" / "seat-mix"

        json_path = (
            Path(os.path.expanduser(args.json_out)) if args.json_out else default_dir / f"{date_str}.json"
        )
        md_path = Path(os.path.expanduser(args.md_out)) if args.md_out else default_dir / f"{date_str}.md"

        json_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.parent.mkdir(parents=True, exist_ok=True)

        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        md_text = render_markdown(report)
        md_path.write_text(md_text, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 — G2: heartbeat the failure path too, then re-raise
        _write_heartbeat("error", {"error": str(exc)})
        raise

    print(md_text)
    print(f"[seat-mix] json -> {json_path}", file=sys.stderr)
    print(f"[seat-mix] md   -> {md_path}", file=sys.stderr)
    _write_heartbeat("ok", {"json_path": str(json_path), "md_path": str(md_path)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
