"""Unit tests for scripts/wr2_ig_profile_harvester.py — STRATO 4 (pure helpers).

The browser I/O (login/collect) is not unit-tested (needs a live Instagram
session); the load-bearing pure logic is `normalize_post_urls`, which turns the
raw grid hrefs into unique canonical permalinks — tested here.
"""

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[6]
_MODULE_PATH = _REPO_ROOT / "scripts" / "wr2_ig_profile_harvester.py"
_spec = importlib.util.spec_from_file_location("wr2_ig_profile_harvester", _MODULE_PATH)
hv = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = hv
_spec.loader.exec_module(hv)


def test_normalize_keeps_only_posts_and_reels():
    hrefs = [
        "https://www.instagram.com/p/ABC123/",
        "https://www.instagram.com/reel/DEF456/",
        "https://www.instagram.com/balizero0/",          # profile -> dropped
        "https://www.instagram.com/explore/tags/bali/",  # explore -> dropped
        "https://www.instagram.com/p/ABC123/liked_by/",  # same post, sub-route -> dedup
    ]
    out = hv.normalize_post_urls(hrefs)
    assert out == [
        "https://www.instagram.com/p/ABC123/",
        "https://www.instagram.com/reel/DEF456/",
    ]


def test_normalize_dedups_by_shortcode_preserving_order():
    hrefs = [
        "https://www.instagram.com/p/AAA/",
        "https://www.instagram.com/p/BBB/",
        "https://www.instagram.com/p/AAA/",  # dup
        "https://www.instagram.com/p/CCC/",
    ]
    out = hv.normalize_post_urls(hrefs)
    assert out == [
        "https://www.instagram.com/p/AAA/",
        "https://www.instagram.com/p/BBB/",
        "https://www.instagram.com/p/CCC/",
    ]


def test_normalize_canonicalizes_messy_urls():
    hrefs = [
        "https://instagram.com/p/XYZ?igshid=foo",   # no www, query -> canonical
        "http://www.instagram.com/reel/QQQ/",        # http -> https
    ]
    out = hv.normalize_post_urls(hrefs)
    assert out == [
        "https://www.instagram.com/p/XYZ/",
        "https://www.instagram.com/reel/QQQ/",
    ]


def test_normalize_empty_and_garbage():
    assert hv.normalize_post_urls([]) == []
    assert hv.normalize_post_urls(["", None, "https://example.com/p/x/"]) == []


def test_normalized_urls_pass_writer_validation():
    # every URL the harvester emits must be accepted by STRATO 1's validator,
    # else ingest-external would reject them.
    out = hv.normalize_post_urls([
        "https://www.instagram.com/p/ABC123/",
        "https://instagram.com/reel/DEF456?x=1",
    ])
    assert out and all(hv._qw.validate_ig_url(u) for u in out)
