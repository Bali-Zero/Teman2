"""liveness-detector-arm-0717: OURS_RE coverage gap on `com.matagaruda.*`.

Wiring this detector to a daily cron (the whole point of this change-set) is
hollow if the scope regex is blind to a third of the machine's own job family.
Live audit 2026-07-17 on Pro: `launchctl list` + `~/Library/LaunchAgents`
confirmed `com.matagaruda.redis-split-brain.check`,
`com.matagaruda.pipeline-health.hourly`, and `com.matagaruda.kg-query-api` are
all real, loaded, `infra/launchagents/`-tracked LaunchAgents — but `audit()`
silently skipped all three because `OURS_RE` only matched `nuzantara`/`balizero`.
One of the three (`kg-query-api`) turned out to be a genuine, currently-active
crash loop (`OSError: [Errno 49] Can't assign requested address`, ~73k
occurrences) that this detector would never have surfaced.

Contract under test (OURS_RE):
  - guilt: a `com.matagaruda.*` label now matches (the gap this fix closes)
  - innocence: unrelated third-party/system labels (Apple, Homebrew, Google)
    still do NOT match — the fix must not turn OURS_RE into a match-everything
    regex (that would defeat the "avoid noise from Apple/homebrew agents"
    comment right above it)
  - innocence: a label merely *containing* "matagaruda" as a substring of a
    longer unrelated word must not match — this stays a word-boundary match,
    not a bare substring (guard-over-match family, cicatrix superscar #3)
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "launchd_liveness_detector.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("launchd_liveness_detector", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_matagaruda_labels_now_match():
    mod = _load_module()
    live_labels = [
        "com.matagaruda.redis-split-brain.check",
        "com.matagaruda.pipeline-health.hourly",
        "com.matagaruda.kg-query-api",
    ]
    for label in live_labels:
        assert mod.OURS_RE.search(label), f"{label} should be in-scope (matagaruda is ours)"


def test_existing_families_still_match():
    """Innocence in the other direction: the fix must not have broken the
    two families the regex already covered."""
    mod = _load_module()
    assert mod.OURS_RE.search("com.nuzantara.verify-the-verifiers")
    assert mod.OURS_RE.search("com.balizero.wr2.image-generator")


def test_unrelated_system_labels_still_excluded():
    mod = _load_module()
    noise = [
        "com.apple.suggestd",
        "com.google.keystone.agent",
        "homebrew.mxcl.redis",
        "ai.openclaw.gateway",
        "com.osint-nexus.h24",
    ]
    for label in noise:
        assert not mod.OURS_RE.search(label), f"{label} should stay out of scope"


def test_word_boundary_not_bare_substring():
    """A label where 'matagaruda' is glued to other word characters (not a
    dot/hyphen-delimited component) must not match — OURS_RE uses \\b, it does
    not do a bare `"matagaruda" in label` check."""
    mod = _load_module()
    assert not mod.OURS_RE.search("com.notmatagarudareal.foo")
