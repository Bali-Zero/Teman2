"""Unit tests for scripts/wr2_ig_metrics_scraper.py — media_id_of / is_stale.

Loaded via importlib (the module lives in repo-root scripts/, same convention
as test_wr2_queue_pull_merge.py). Covers the §C fix, CORRECTED per a live
Pro-side diagnosis (2026-07-17) that superseded the first-pass fix: the
scraper's candidate SELECTION already works for any queue entry with
instagram_post_url + state=="published" regardless of pipeline origin, but the
Graph FETCH needs a media id it can TRUST — `ig_media_id` (authoritative,
wired from wr2_ig_discovery.py's real Graph fetch) when present, else a legacy
`"ig-<digits>"` id/item_id whose suffix is ALL-NUMERIC (a real Graph media id
is numeric-only; an IG shortcode is alphanumeric — conflating the two was the
bug the first-pass fix (checking "id" OR "item_id") did not catch, because it
widened which KEY was searched, not which VALUE was trusted).
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


# ── media_id_of — ig_media_id preference + numeric-suffix discrimination ────


def test_media_id_of_prefers_authoritative_ig_media_id_field():
    # the discovery/backfill-wired field wins even when a legacy id is ALSO present.
    assert scraper.media_id_of({"ig_media_id": "17895695668004550",
                                 "id": "ig-11111111111111111"}) == "17895695668004550"


def test_media_id_of_ig_media_id_alone():
    assert scraper.media_id_of({"item_id": "external_2026-07-17T090000_my-post",
                                 "ig_media_id": "17895695668004550"}) == "17895695668004550"


def test_media_id_of_legacy_id_key_numeric_suffix():
    # all 45 real legacy ids on record are 17-digit Graph media ids (finding I floor).
    assert scraper.media_id_of({"id": "ig-12345678901234567"}) == "12345678901234567"


def test_media_id_of_item_id_key_numeric_suffix_now_resolves():
    # the dual-schema-key half of the fix: an entry carrying ONLY "item_id" (the
    # newer FSM/app schema) used to be silently invisible because media_id_of
    # checked "id" alone. Now it resolves too, when the suffix is numeric and long enough.
    assert scraper.media_id_of({"item_id": "ig-98765432109876543"}) == "98765432109876543"


def test_media_id_of_prefers_id_over_item_id_when_both_present():
    assert scraper.media_id_of({"id": "ig-11111111111111111",
                                 "item_id": "ig-22222222222222222"}) == "11111111111111111"


def test_media_id_of_rejects_alphanumeric_shortcode_suffix():
    # GUILT (the corrected bug, 2026-07-17): "ig-DaxDJuYFPi6" is an IG shortcode
    # (ingest_external_post's pre-ig_media_id convention), NOT a Graph media id —
    # feeding it to the Graph endpoint would 400 with a confusing error rather
    # than failing cleanly. The suffix must be ALL-NUMERIC to be trusted.
    assert scraper.media_id_of({"id": "ig-DaxDJuYFPi6"}) is None
    assert scraper.media_id_of({"item_id": "ig-Cabc123_-"}) is None


def test_media_id_of_none_without_ig_prefix_or_media_id_field():
    # INNOCENCE: this feature's own external_manual ids ("external_<date>_<slug>")
    # never even reach the "ig-" branch and never carry ig_media_id (the operator
    # only pasted a URL, no Graph fetch happened) — a real "cannot fetch", never
    # a wrong fetch (documented limitation, see media_id_of docstring).
    assert scraper.media_id_of({"item_id": "external_2026-07-17T090000_my-post"}) is None
    assert scraper.media_id_of({}) is None


def test_media_id_of_empty_string_ids_return_none():
    assert scraper.media_id_of({"id": "", "item_id": "", "ig_media_id": ""}) is None


def test_media_id_of_rejects_short_all_digit_suffix():
    # GUILT (Codex red-team, 2026-07-17, finding I): a short all-digit suffix is
    # exactly the theoretical shortcode-that-happens-to-render-as-digits case
    # `isdigit()` alone would wrongly trust. All 45 real legacy ids are 17
    # digits — the <15-digit floor keeps this fallback scoped to that shape,
    # including the 10-digit shape used (pre-finding-I) as "the legacy example".
    assert scraper.media_id_of({"id": "ig-123"}) is None
    assert scraper.media_id_of({"id": "ig-1234567890"}) is None
    assert scraper.media_id_of({"item_id": "ig-9876543210"}) is None
    # INNOCENCE: a real 17-digit legacy id still resolves.
    assert scraper.media_id_of({"id": "ig-12345678901234567"}) == "12345678901234567"


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
