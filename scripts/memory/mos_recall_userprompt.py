#!/usr/bin/env python3
"""LAYER 2b — mos_recall_userprompt.py (UserPromptSubmit recall hook).

Companion to mos_recall_sessionstart.py's Layer-2 recall (SessionStart-only,
top-6, <=1500B): this fires on EVERY user prompt, not just session start, so
a pertinent memory or scar surfaces mid-session instead of only at the door
(cicatrix family #2, exists != armed — a peer session observed on 2026-09-04
that "the things that bite most are the ones you don't know you should ask
for", and the 441KB MEMORY_INDEX.md catalog it named is armed by nothing
mid-session). Reuses mos_recall_sessionstart's index build, BM25 scoring,
scar index and redaction WHOLESALE (imported, not duplicated) and layers a
separate, STRICTER quiet-gate on top — because a UserPromptSubmit hook's
stdout is appended to context on every single turn, not once per session:
top-3 (not top-6), <=600B (not <=1500B), a relevance floor of 0.45 (not
0.35), plus prompt-shape gates (too short, too few informative terms, a
slash/bang command) that have no SessionStart analogue.

Imported directly rather than shelled out to as a subprocess: the query is
arbitrary user text (may contain quotes/newlines/shell metacharacters), so
passing it as a CLI argv string would be a quoting hazard for no benefit —
mos_recall_sessionstart.py's functions are already a clean Python API
(recall/format_output/resolve_memdir/resolve_scars_dir), and importing them
skips a second process spawn on every turn.

Kill switch: CLAUDE_RECALL_PROMPT_DISABLED=1 (silent, exit 0).
Tunables (env): RECALL_PROMPT_MAX_BYTES, RECALL_PROMPT_MIN_RELEVANCE,
RECALL_PROMPT_TOPK.

Fail-open contract, same as the sibling: any error, any missing engine, any
malformed stdin -> silent exit 0. Nothing on stdout unless a hit clears
every gate; nothing on stderr ever (would surface as hook noise the harness
might act on).
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
MIN_PROMPT_CHARS = 12
MIN_INFORMATIVE_TERMS = 2
MIN_TERM_CHARS = 4
HEADER = "🧠 recall:"
KILL_SWITCH_ENV = "CLAUDE_RECALL_PROMPT_DISABLED"
MAX_BYTES_ENV = "RECALL_PROMPT_MAX_BYTES"
MIN_RELEVANCE_ENV = "RECALL_PROMPT_MIN_RELEVANCE"
TOPK_ENV = "RECALL_PROMPT_TOPK"


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
    if not has_enough_informative_terms(prompt):
        return False
    return True


def build_recall_output(prompt: str, cwd: str, max_bytes: int = DEFAULT_MAX_BYTES,
                         min_relevance: float = DEFAULT_MIN_RELEVANCE, topk: int = DEFAULT_TOPK,
                         claim_max_chars: int = DEFAULT_CLAIM_MAX_CHARS) -> str:
    memdir = mos.resolve_memdir(cwd=cwd)
    if not memdir or not os.path.isdir(memdir):
        return ""  # not wired on this machine — same silent contract as the sibling
    cache_path = os.path.join(memdir, mos.CACHE_FILENAME)
    scars_dir = mos.resolve_scars_dir(cwd)
    results, _stats = mos.recall(memdir, cache_path, prompt, topk=topk, threshold=min_relevance,
                                  scars_dir=scars_dir)
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
        )
        if out:
            print(out)
        return 0
    except Exception:
        return 0  # fail-open: a receptor must never break a turn


if __name__ == "__main__":
    raise SystemExit(main())
