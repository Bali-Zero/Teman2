"""Unit tests for scripts/wr2_ig_metrics_scraper.py — media_id_of / is_stale.

Loaded via importlib (the module lives in repo-root scripts/, same convention
as test_wr2_queue_pull_merge.py). Covers the §C verification finding
(2026-07-17, external-post feature spec): the scraper's candidate SELECTION
already works for any queue entry with instagram_post_url + state=="published"
regardless of pipeline origin, but the actual Graph FETCH needs a resolvable
media id, and that id must now be found on EITHER historical id key ("id" or
"item_id") — the fix under test here.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    assert spec and spec.loader, f"cannot load {name}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


scraper = _load("wr2_ig_metrics_scraper")


# ── media_id_of — dual-schema id key (§C fix) ──────────────────────────────


def test_media_id_of_legacy_id_key():
    assert scraper.media_id_of({"id": "ig-1234567890"}) == "1234567890"


def test_media_id_of_item_id_key_now_resolves():
    # GUILT (pre-fix behavior): an entry carrying ONLY "item_id" (the newer FSM/
    # app schema) used to be silently invisible to the scraper because
    # media_id_of checked "id" alone. Now it resolves too.
    assert scraper.media_id_of({"item_id": "ig-9876543210"}) == "9876543210"


def test_media_id_of_prefers_id_over_item_id_when_both_present():
    assert scraper.media_id_of({"id": "ig-AAA", "item_id": "ig-BBB"}) == "AAA"


def test_media_id_of_none_without_ig_prefix_on_either_key():
    # INNOCENCE: this feature's own external_manual ids ("external_<date>_<slug>")
    # and ingest_external_post's "ig-<shortcode>" ids that happen to collide with
    # a non-numeric shape are NOT silently treated as Graph media ids — the
    # documented limitation (see media_id_of docstring) is a real "cannot fetch",
    # never a wrong fetch.
    assert scraper.media_id_of({"item_id": "external_2026-07-17T090000_my-post"}) is None
    assert scraper.media_id_of({}) is None


def test_media_id_of_empty_string_ids_return_none():
    assert scraper.media_id_of({"id": "", "item_id": ""}) is None


# ── is_stale ────────────────────────────────────────────────────────────────


def test_is_stale_missing_metrics():
    assert scraper.is_stale(None, 7) is True
    assert scraper.is_stale({}, 7) is True


def test_is_stale_no_timestamp():
    assert scraper.is_stale({"likes": 10}, 7) is True


def test_is_stale_fresh_metrics_not_stale():
    now_iso = datetime.now(timezone.utc).isoformat()
    assert scraper.is_stale({"scraped_at": now_iso}, 7) is False


def test_is_stale_old_metrics_are_stale():
    old_iso = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    assert scraper.is_stale({"scraped_at": old_iso}, 7) is True
