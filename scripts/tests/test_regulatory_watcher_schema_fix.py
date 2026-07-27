"""Regression pins for task #95 (2026-07-27, defects 3+4 authorized by Zero).

Defect 3 — stale source path: `~/.claude/agents/regulatory-watcher.md`'s IKPI entry
pointed at `https://ikpi.or.id/news/`, which 404s on every run (19/19 occurrences
measured across the delta archive on disk). Live-verified with the watcher's own
User-Agent 2026-07-27: `/news/` -> HTTP 404, `/berita/` -> HTTP 200 with dated
articles. Fixed to the current path.

Defect 4 — labeling bug: `unreachable_sources` mixed genuine fetch failures with
successful checks that found nothing new (e.g. `www.imigrasi.go.id` filed there on
6/6 occurrences, every time annotated "200, checked, no new items" — a working
source misfiled as broken). Fixed by pinning a closed reason-vocabulary and splitting
successes into a separate `sources_checked_no_delta` array, in both the Tier-1 agent
spec (the dominant path — PROMPT_GENERIC never even named these fields) and the
cross-provider fallback prompt.

These are plain string/content pins, not behavioral tests — the "logic" under fix is
a Markdown spec + a shell-embedded prompt string that an LLM reads, so there is no
Python function to unit-test. The value here is regression protection: if a future
edit reverts the path or drops the vocabulary pinning, this fails loudly instead of
silently re-introducing either defect.
"""
from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AGENT_SPEC = _REPO_ROOT / ".claude" / "agents" / "regulatory-watcher.md"
_WRAPPER = _REPO_ROOT / "infra" / "launchagents" / "wrappers" / "regulatory-watcher-run.sh"

_CLOSED_VOCAB_UNREACHABLE = ("http_403", "http_404", "timeout", "ssl_error", "empty_shell")
_CLOSED_VOCAB_CHECKED = ("checked_no_new", "outside_window")


def test_agent_spec_exists_as_repo_canon() -> None:
    """The Tier-1 workflow's PROMPT_CLAUDE literally instructs 'Read
    ~/.claude/agents/regulatory-watcher.md for full spec' — if this repo canon
    disappears, defects 3+4 have no source of truth to arm from (superscar #1)."""
    assert _AGENT_SPEC.is_file(), (
        f"{_AGENT_SPEC} missing — regulatory-watcher's Tier-1 spec must be repo-tracked, "
        "declared in infra/home-fork/declared-pairs.json"
    )


def test_defect3_ikpi_path_fixed_in_agent_spec() -> None:
    text = _AGENT_SPEC.read_text(encoding="utf-8")
    assert "5. `https://ikpi.or.id/berita/`" in text, (
        "IKPI source entry must point at /berita/ (the live path) — /news/ 404s "
        "on every run (measured 19/19 in the delta archive, 2026-07-27)"
    )


def test_defect4_closed_vocabulary_present_in_agent_spec() -> None:
    text = _AGENT_SPEC.read_text(encoding="utf-8")
    assert "sources_checked_no_delta" in text, (
        "successes-with-no-new-content must have their own field, separate from "
        "unreachable_sources (defect 4: a true negative filed as unreachable)"
    )
    for token in _CLOSED_VOCAB_UNREACHABLE:
        assert f"`{token}`" in text, f"unreachable_sources reason '{token}' missing from spec"
    for token in _CLOSED_VOCAB_CHECKED:
        assert f"`{token}`" in text, f"sources_checked_no_delta reason '{token}' missing from spec"


def test_defect4_nb_query_errors_always_present_rule_documented() -> None:
    text = _AGENT_SPEC.read_text(encoding="utf-8")
    assert "MUST always be present" in text and "nb_query_errors" in text, (
        "the absent-vs-empty ambiguity on nb_query_errors (13/36 files omitted the key "
        "entirely) needs an explicit always-emit-the-key rule, not just a schema example"
    )


def test_defect4_schema_pinned_in_cross_provider_prompt_too() -> None:
    """PROMPT_GENERIC (tiers 2-4 fallback) never named unreachable_sources or
    nb_query_errors at all before this fix — team-lead's own citation of
    'not in the wrapper's documented output schema' pointed at this exact string.
    Tier 1 dominates in practice, but the fallback prompt should not re-teach the
    same labeling bug if it ever fires."""
    text = _WRAPPER.read_text(encoding="utf-8")
    assert 'PROMPT_GENERIC="' in text, "PROMPT_GENERIC definition not found — anchor drifted"
    assert "sources_checked_no_delta" in text
    assert "unreachable_sources" in text
    assert "nb_query_errors" in text
    for token in _CLOSED_VOCAB_UNREACHABLE:
        assert token in text, f"PROMPT_GENERIC missing closed-vocab reason '{token}'"
    for token in _CLOSED_VOCAB_CHECKED:
        assert token in text, f"PROMPT_GENERIC missing closed-vocab reason '{token}'"


def test_declared_home_fork_pair_registered() -> None:
    """Without this, the fix can merge to main and never reach the live cron —
    the agent spec lives only at ~/.claude/agents/, outside git, unless declared
    and synced (superscar #1: constructed != armed)."""
    import json

    pairs_path = _REPO_ROOT / "infra" / "home-fork" / "declared-pairs.json"
    config = json.loads(pairs_path.read_text(encoding="utf-8"))
    matches = [
        p
        for p in config["pairs"]
        if p.get("repo") == ".claude/agents/regulatory-watcher.md"
        and p.get("live") == "~/.claude/agents/regulatory-watcher.md"
    ]
    assert len(matches) == 1, (
        "expected exactly one declared pair for the regulatory-watcher agent spec"
    )
    assert set(matches[0].get("machines", [])) == {"pro", "m5"}, (
        "must match the wrapper .sh pair's machine scope (pro=active cron, "
        "m5=dormant aligned copy, no Mini — active-active split-brain risk)"
    )
