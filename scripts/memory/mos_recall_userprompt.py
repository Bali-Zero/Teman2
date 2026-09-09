#!/usr/bin/env python3
"""LAYER 2b — mos_recall_userprompt.py (UserPromptSubmit recall hook).

Companion to mos_recall_sessionstart.py's Layer-2 recall (SessionStart-only,
top-6, <=1500B): this fires on EVERY prompt, so a pertinent memory/scar
surfaces mid-session too (cicatrix family #2, exists != armed — the 441KB
MEMORY_INDEX.md catalog is armed by nothing mid-session; Zero's order
2026-09-04). Reuses the sibling's index build/BM25/scar-index/redaction via
direct Python import (not subprocess — the query is arbitrary user text and
would be a quoting hazard as a CLI argv) with a STRICTER budget: top-3,
<=600B, 0.45 relevance floor (vs top-6/1500B/0.35), plus prompt-shape gates
(too short, too few informative terms, slash/bang) with no SessionStart
analogue.

Kill switch: CLAUDE_RECALL_PROMPT_DISABLED=1. Tunables (env):
RECALL_PROMPT_MAX_BYTES, RECALL_PROMPT_MIN_RELEVANCE, RECALL_PROMPT_TOPK,
RECALL_PROMPT_MIN_OVERLAP.

2026-09-04 follow-up (live observation, minutes after the first merge): the
hook fired on a harness-generated turn, not a human one — a `"prompt"` that
was itself a `[SYSTEM NOTIFICATION - NOT USER INPUT] …` envelope — and a
long machine-generated block can clear the relevance floor on a single rare
token's IDF alone. Three cures, all quiet-by-default: (1) an envelope-shape
gate (`is_harness_envelope()`) recognizes the harness's own wrapper tags and
never scores them; (2) the query text is capped at MAX_QUERY_CHARS before
scoring, so a pasted log does not become a 400-term query; (3) `recall()`
(in the sibling module) now also requires the WINNING candidate to share at
least `min_overlap` distinct query terms, not just clear the score floor.

Fail-open, same as the sibling: any error/malformed stdin -> silent exit 0;
nothing on stderr ever (would surface as hook noise).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mos_recall_sessionstart as mos  # noqa: E402

DEFAULT_MAX_BYTES = 600
DEFAULT_MIN_RELEVANCE = 0.45  # higher than SessionStart's 0.35 — a per-turn hit must be more certain
DEFAULT_TOPK = 3
DEFAULT_CLAIM_MAX_CHARS = 110
DEFAULT_MIN_OVERLAP = 2  # >=2 distinct query terms must land in the winning candidate
MIN_PROMPT_CHARS = 12
MIN_INFORMATIVE_TERMS = 2
MIN_TERM_CHARS = 4
# 1,200 chars is ~2 paragraphs / a long paste's opening — long enough that a genuine
# question always fits inside it, short enough that a multi-KB pasted log or stack
# trace does not turn into a 400-term query that can match anything by sheer volume.
MAX_QUERY_CHARS = 1200
NOT_USER_INPUT_MARKER = "NOT USER INPUT"
NOT_USER_INPUT_SCAN_CHARS = 200  # harness envelopes carry this marker near the very top
HARNESS_ENVELOPE_PREFIXES = (
    "[SYSTEM NOTIFICATION",
    "<task-notification",
    "<teammate-message",
    "<cross-session-message",
    "<system-reminder",
)
HEADER = "🧠 recall:"
KILL_SWITCH_ENV = "CLAUDE_RECALL_PROMPT_DISABLED"
MAX_BYTES_ENV = "RECALL_PROMPT_MAX_BYTES"
MIN_RELEVANCE_ENV = "RECALL_PROMPT_MIN_RELEVANCE"
TOPK_ENV = "RECALL_PROMPT_TOPK"
MIN_OVERLAP_ENV = "RECALL_PROMPT_MIN_OVERLAP"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def is_slash_or_bang(prompt: str) -> bool:
    """A slash command (`/context`) or a shell escape (`!ls`) is not a
    natural-language question a memory/scar recall could ever answer."""
    stripped = prompt.lstrip()
    return stripped.startswith("/") or stripped.startswith("!")


def is_harness_envelope(prompt: str) -> bool:
    """A harness-generated turn (background-task notification, teammate
    relay, cross-session message, an injected system-reminder) is never a
    human question — and its own machinery text ("staff activity log",
    "keychain", scar numbers quoted verbatim in status text) makes it
    lexically dense enough to clear the relevance floor by accident."""
    stripped = prompt.lstrip()
    if stripped.startswith(HARNESS_ENVELOPE_PREFIXES):
        return True
    return NOT_USER_INPUT_MARKER in prompt[:NOT_USER_INPUT_SCAN_CHARS]


def has_enough_informative_terms(prompt: str, min_terms: int = MIN_INFORMATIVE_TERMS,
                                  min_chars: int = MIN_TERM_CHARS) -> bool:
    """Reuses mos.tokenize() (EN+IT stopwords, len>=2 already stripped) and
    adds a >=4-char floor on top — "ok can you check" has plenty of len>=2
    tokens after stopword removal but nothing worth searching on."""
    terms = {t for t in mos.tokenize(prompt) if len(t) >= min_chars}
    return len(terms) >= min_terms


def should_run(prompt: str) -> bool:
    if not prompt or len(prompt) < MIN_PROMPT_CHARS:
        return False
    if is_slash_or_bang(prompt):
        return False
    if is_harness_envelope(prompt):
        return False
    if not has_enough_informative_terms(prompt):
        return False
    return True


def build_recall_output(prompt: str, cwd: str, max_bytes: int = DEFAULT_MAX_BYTES,
                         min_relevance: float = DEFAULT_MIN_RELEVANCE, topk: int = DEFAULT_TOPK,
                         claim_max_chars: int = DEFAULT_CLAIM_MAX_CHARS,
                         min_overlap: int = DEFAULT_MIN_OVERLAP) -> str:
    memdir = mos.resolve_memdir(cwd=cwd)
    if not memdir or not os.path.isdir(memdir):
        return ""  # not wired on this machine — same silent contract as the sibling
    cache_path = os.path.join(memdir, mos.CACHE_FILENAME)
    scars_dir = mos.resolve_scars_dir(cwd)
    query = prompt[:MAX_QUERY_CHARS]
    results, _stats = mos.recall(memdir, cache_path, query, topk=topk, threshold=min_relevance,
                                  scars_dir=scars_dir, min_overlap=min_overlap)
    if not results:
        return ""
    return mos.format_output(results, cap_bytes=max_bytes, header=HEADER, claim_max_chars=claim_max_chars)


def main() -> int:
    try:
        if os.environ.get(KILL_SWITCH_ENV) == "1":
            return 0
        raw = sys.stdin.read()
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return 0
        if not isinstance(payload, dict):
            return 0
        prompt = (payload.get("prompt") or "").strip()
        if not should_run(prompt):
            return 0
        cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        out = build_recall_output(
            prompt, cwd,
            max_bytes=_env_int(MAX_BYTES_ENV, DEFAULT_MAX_BYTES),
            min_relevance=_env_float(MIN_RELEVANCE_ENV, DEFAULT_MIN_RELEVANCE),
            topk=_env_int(TOPK_ENV, DEFAULT_TOPK),
            min_overlap=_env_int(MIN_OVERLAP_ENV, DEFAULT_MIN_OVERLAP),
        )
        if out:
            print(out)
        return 0
    except Exception:
        return 0  # fail-open: a receptor must never break a turn


if __name__ == "__main__":
    raise SystemExit(main())
