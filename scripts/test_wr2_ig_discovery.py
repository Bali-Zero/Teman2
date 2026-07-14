from __future__ import annotations

from datetime import datetime, timedelta, timezone

import wr2_ig_discovery as discovery

# scar W96: tests never touch the real queue path — every fixture below is a
# plain in-memory list/dict, no disk I/O beyond what pytest's tmp_path gives us
# (and this module doesn't even need tmp_path since the tested helpers are pure).


# ── word_tokens ──────────────────────────────────────────────────────────


def test_word_tokens_drops_short_words() -> None:
    assert discovery.word_tokens("a to KBLI visa update now") == {"kbli", "visa", "update"}


def test_word_tokens_empty_string() -> None:
    assert discovery.word_tokens("") == set()
    assert discovery.word_tokens(None) == set()  # type: ignore[arg-type]


def test_word_tokens_lowercases() -> None:
    assert discovery.word_tokens("KITAS Rules Update") == {"kitas", "rules", "update"}


# ── jaccard_similarity ──────────────────────────────────────────────────


def test_jaccard_identical_sets_is_one() -> None:
    s = {"visa", "kitas", "rules"}
    assert discovery.jaccard_similarity(s, s) == 1.0


def test_jaccard_disjoint_sets_is_zero() -> None:
    assert discovery.jaccard_similarity({"visa"}, {"tax"}) == 0.0


def test_jaccard_both_empty_is_zero_not_matched() -> None:
    assert discovery.jaccard_similarity(set(), set()) == 0.0


def test_jaccard_partial_overlap() -> None:
    a = {"visa", "kitas", "rules", "update"}
    b = {"visa", "kitas", "guide", "price"}
    # intersection = {visa, kitas} = 2, union = 6
    assert discovery.jaccard_similarity(a, b) == 2 / 6


# ── caption_first_line ──────────────────────────────────────────────────


def test_caption_first_line_splits_on_blank_line() -> None:
    caption = "New KITAS rules 2026\n\nRead the full breakdown in our bio link."
    assert discovery.caption_first_line(caption) == "New KITAS rules 2026"


def test_caption_first_line_none_is_empty() -> None:
    assert discovery.caption_first_line(None) == ""


def test_caption_first_line_blank_is_empty() -> None:
    assert discovery.caption_first_line("   \n\n  ") == ""


# ── build_known_shortcodes ───────────────────────────────────────────────


def test_build_known_shortcodes_extracts_from_urls() -> None:
    items = [
        {"instagram_post_url": "https://www.instagram.com/p/ABC123/"},
        {"instagram_post_url": "https://www.instagram.com/reel/XYZ789/"},
        {"topic": "no url here"},
    ]
    assert discovery.build_known_shortcodes(items) == {"ABC123", "XYZ789"}


def test_build_known_shortcodes_empty_queue() -> None:
    assert discovery.build_known_shortcodes([]) == set()


def test_build_known_shortcodes_ignores_malformed_url() -> None:
    items = [{"instagram_post_url": "not-a-url"}]
    assert discovery.build_known_shortcodes(items) == set()


# ── parse_ig_timestamp / is_recent ───────────────────────────────────────


def test_parse_ig_timestamp_offset_no_colon() -> None:
    dt = discovery.parse_ig_timestamp("2026-06-01T12:00:00+0000")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 6 and dt.day == 1


def test_parse_ig_timestamp_none_input() -> None:
    assert discovery.parse_ig_timestamp(None) is None


def test_parse_ig_timestamp_garbage_input() -> None:
    assert discovery.parse_ig_timestamp("not-a-date") is None


def test_is_recent_within_window() -> None:
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    ts = (now - timedelta(days=10)).isoformat()
    assert discovery.is_recent(ts, max_age_days=90, now=now) is True


def test_is_recent_outside_window() -> None:
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    ts = (now - timedelta(days=200)).isoformat()
    assert discovery.is_recent(ts, max_age_days=90, now=now) is False


def test_is_recent_unparseable_is_false() -> None:
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    assert discovery.is_recent("garbage", max_age_days=90, now=now) is False


# ── filter_new_media ─────────────────────────────────────────────────────


def test_filter_new_media_excludes_known_shortcode() -> None:
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    media = [
        {
            "permalink": "https://www.instagram.com/p/KNOWN1/",
            "timestamp": (now - timedelta(days=1)).isoformat(),
        }
    ]
    out = discovery.filter_new_media(media, known_shortcodes={"KNOWN1"}, max_age_days=90, now=now)
    assert out == []


def test_filter_new_media_excludes_stale_media() -> None:
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    media = [
        {
            "permalink": "https://www.instagram.com/p/NEW1/",
            "timestamp": (now - timedelta(days=365)).isoformat(),
        }
    ]
    out = discovery.filter_new_media(media, known_shortcodes=set(), max_age_days=90, now=now)
    assert out == []


def test_filter_new_media_keeps_fresh_unknown_media() -> None:
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    media = [
        {
            "permalink": "https://www.instagram.com/p/NEW2/",
            "timestamp": (now - timedelta(days=5)).isoformat(),
        }
    ]
    out = discovery.filter_new_media(media, known_shortcodes=set(), max_age_days=90, now=now)
    assert len(out) == 1
    assert out[0]["permalink"].endswith("/p/NEW2/")


def test_filter_new_media_skips_media_without_permalink() -> None:
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    media = [{"timestamp": now.isoformat()}]
    out = discovery.filter_new_media(media, known_shortcodes=set(), max_age_days=90, now=now)
    assert out == []


# ── find_fuzzy_match ─────────────────────────────────────────────────────


def test_find_fuzzy_match_hits_above_threshold() -> None:
    queue = [
        {"item_id": "wr2-1", "topic": "KBLI 2025 conversion rules for PT PMA", "state": "drafted"},
        {"item_id": "wr2-2", "topic": "Tax deadline reminder Q2", "state": "reviewed"},
    ]
    match = discovery.find_fuzzy_match("KBLI 2025 conversion rules explained", queue)
    assert match is not None
    assert match["item_id"] == "wr2-1"


def test_find_fuzzy_match_no_hit_below_threshold() -> None:
    queue = [{"item_id": "wr2-1", "topic": "Completely unrelated subject matter", "state": "drafted"}]
    match = discovery.find_fuzzy_match("KBLI 2025 conversion rules", queue)
    assert match is None


def test_find_fuzzy_match_ignores_out_of_flight_states() -> None:
    queue = [
        {"item_id": "wr2-1", "topic": "KBLI 2025 conversion rules for PT PMA", "state": "published"},
    ]
    match = discovery.find_fuzzy_match("KBLI 2025 conversion rules explained", queue)
    assert match is None


def test_find_fuzzy_match_empty_caption_line_no_match() -> None:
    queue = [{"item_id": "wr2-1", "topic": "KBLI 2025 conversion rules", "state": "drafted"}]
    assert discovery.find_fuzzy_match("", queue) is None


def test_find_fuzzy_match_empty_queue_no_match() -> None:
    assert discovery.find_fuzzy_match("KBLI 2025 conversion rules", []) is None
