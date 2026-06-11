"""Unit tests for scripts/wr2_queue_writer.py — the WR2 IG-feedback queue writer.

Loaded via importlib (the module lives in repo-root scripts/, not an importable
package). Covers the pure matching/normalization logic and the atomic
mark_published orchestration, including the scraper-compatibility contract and
every refuse-to-write branch (the anti-fragility guarantees for the WhatsApp
channel: never write on an ambiguous/absent/conflicting match).
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ── Load the module from repo-root scripts/ ────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[6]
_MODULE_PATH = _REPO_ROOT / "scripts" / "wr2_queue_writer.py"
_spec = importlib.util.spec_from_file_location("wr2_queue_writer", _MODULE_PATH)
qw = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = qw
_spec.loader.exec_module(qw)


# ── Fixtures: the two historical queue schemas ─────────────────────────────


def _old_schema_item(item_id="kep71-spt-extension-test6-FIRSTPROD"):
    """43-item 'first-prod' schema: item_id/topic, em as truthy dict, no ig_url key."""
    return {
        "item_id": item_id,
        "topic": "KEP-71/PJ/2026 SPT Tahunan Badan extension",
        "state": "applied_ready_for_damar",
        "engagement_metrics": {"likes": None, "saves": None, "reach": None, "comments": None},
        "domain": "tax",
    }


def _new_schema_item(item_id="some-draft-slug"):
    """Newer drafts schema: id/topic_slug, ig_url key present (null), em None."""
    return {
        "id": item_id,
        "topic_slug": item_id,
        "state": "drafted",
        "instagram_post_url": None,
        "instagram_published_at": None,
        "engagement_metrics": None,
        "state_history": [{"state": "drafted", "at": "2026-05-01T00:00:00+00:00"}],
    }


@pytest.fixture
def queue_file(tmp_path):
    """Write a small heterogeneous queue to a temp file, return its Path."""
    items = [
        _old_schema_item("alpha-FIRSTPROD"),
        _old_schema_item("beta-FIRSTPROD"),
        _new_schema_item("gamma-draft"),
    ]
    p = tmp_path / "human-review-queue.json"
    p.write_text(json.dumps(items, indent=2))
    return p


VALID_URL = "https://www.instagram.com/p/Cabc123_-/"


# ── compute_ref_code / normalize ───────────────────────────────────────────


def test_compute_ref_code_deterministic_and_format():
    a = qw.compute_ref_code("alpha-FIRSTPROD")
    b = qw.compute_ref_code("alpha-FIRSTPROD")
    assert a == b
    assert a.startswith("WR2-")
    assert len(a) == len("WR2-") + 6
    assert a[4:].isalnum() and a[4:].isupper()
    # different ids -> different codes
    assert qw.compute_ref_code("beta-FIRSTPROD") != a


def test_normalize_ref_code_tolerates_missing_prefix_and_case():
    code = qw.compute_ref_code("alpha-FIRSTPROD")  # e.g. WR2-AB12CD
    hex_only = code[len("WR2-"):]
    assert qw.normalize_ref_code(hex_only.lower()) == code
    assert qw.normalize_ref_code(f"  {code.lower()} ") == code


# ── item_id_of / topic_of across schemas ───────────────────────────────────


def test_item_id_of_handles_both_schemas():
    assert qw.item_id_of(_old_schema_item("x")) == "x"
    assert qw.item_id_of(_new_schema_item("y")) == "y"
    assert qw.item_id_of({}) is None


def test_topic_of_handles_both_schemas():
    assert qw.topic_of(_old_schema_item()) .startswith("KEP-71")
    assert qw.topic_of(_new_schema_item("gamma-draft")) == "gamma-draft"


# ── validate_ig_url ────────────────────────────────────────────────────────


@pytest.mark.parametrize("url", [
    "https://www.instagram.com/p/Cabc123_-/",
    "https://instagram.com/reel/Xyz789/",
    "http://instagram.com/tv/Abc/",
    "https://www.instagram.com/p/Cabc123/?igshid=foo",
])
def test_validate_ig_url_accepts_real_permalinks(url):
    assert qw.validate_ig_url(url) is True


@pytest.mark.parametrize("url", [
    "https://instagram.com/balizero0",          # profile, not a post
    "https://example.com/p/abc/",               # wrong host
    "not a url",
    "",
    "https://www.instagram.com/",
])
def test_validate_ig_url_rejects_non_permalinks(url):
    assert qw.validate_ig_url(url) is False


# ── find_by_ref_code ───────────────────────────────────────────────────────


def test_find_by_ref_code_exact_match():
    items = [_old_schema_item("alpha-FIRSTPROD"), _old_schema_item("beta-FIRSTPROD")]
    ref = qw.compute_ref_code("beta-FIRSTPROD")
    idx, item = qw.find_by_ref_code(items, ref)
    assert idx == 1
    assert qw.item_id_of(item) == "beta-FIRSTPROD"


def test_find_by_ref_code_miss_returns_none():
    items = [_old_schema_item("alpha-FIRSTPROD")]
    idx, item = qw.find_by_ref_code(items, "WR2-000000")
    assert idx is None and item is None


# ── apply_publish — the scraper-compatibility contract ─────────────────────


def test_apply_publish_normalizes_to_scraper_shape():
    item = _old_schema_item()
    out = qw.apply_publish(item, VALID_URL, "2026-06-12T10:00:00+00:00")
    # scraper requires: state published, em FALSY, ig_url + published_at set
    assert out["state"] == "published"
    assert out["instagram_post_url"] == VALID_URL
    assert out["instagram_published_at"] == "2026-06-12T10:00:00+00:00"
    assert not out["engagement_metrics"]  # the truthy-dict bug is cleared to None
    assert out["damar_action"] == "published"
    # input not mutated (pure)
    assert item["state"] == "applied_ready_for_damar"
    assert item["engagement_metrics"] == {"likes": None, "saves": None, "reach": None, "comments": None}


def test_apply_publish_appends_state_history_when_present():
    item = _new_schema_item()
    out = qw.apply_publish(item, VALID_URL, "2026-06-12T10:00:00+00:00")
    assert out["state_history"][-1]["state"] == "published"
    assert len(out["state_history"]) == len(item["state_history"]) + 1


# ── mark_published — end to end + every refuse-to-write branch ─────────────


def test_mark_published_happy_path_writes_atomically(queue_file):
    ref = qw.compute_ref_code("alpha-FIRSTPROD")
    res = qw.mark_published(queue_file, ref, VALID_URL, published_at="2026-06-12T10:00:00+00:00")
    assert res.status == "published" and res.ok is True
    assert res.item_id == "alpha-FIRSTPROD"
    # persisted + scraper-compatible
    items = json.loads(queue_file.read_text())
    alpha = next(i for i in items if qw.item_id_of(i) == "alpha-FIRSTPROD")
    assert alpha["state"] == "published"
    assert alpha["instagram_post_url"] == VALID_URL
    assert not alpha["engagement_metrics"]
    # OTHER items untouched
    beta = next(i for i in items if qw.item_id_of(i) == "beta-FIRSTPROD")
    assert beta["state"] == "applied_ready_for_damar"


def test_mark_published_idempotent_same_url(queue_file):
    ref = qw.compute_ref_code("alpha-FIRSTPROD")
    qw.mark_published(queue_file, ref, VALID_URL, published_at="2026-06-12T10:00:00+00:00")
    res2 = qw.mark_published(queue_file, ref, VALID_URL)
    assert res2.status == "already_published" and res2.ok is True


def test_mark_published_conflict_different_url_refuses(queue_file):
    ref = qw.compute_ref_code("alpha-FIRSTPROD")
    qw.mark_published(queue_file, ref, VALID_URL, published_at="2026-06-12T10:00:00+00:00")
    other = "https://www.instagram.com/p/DIFFERENT99/"
    res = qw.mark_published(queue_file, ref, other)
    assert res.status == "conflict" and res.ok is False
    # original url preserved, not overwritten
    items = json.loads(queue_file.read_text())
    alpha = next(i for i in items if qw.item_id_of(i) == "alpha-FIRSTPROD")
    assert alpha["instagram_post_url"] == VALID_URL


def test_mark_published_not_found_no_write(queue_file):
    before = queue_file.read_text()
    res = qw.mark_published(queue_file, "WR2-000000", VALID_URL)
    assert res.status == "not_found" and res.ok is False
    assert queue_file.read_text() == before  # untouched


def test_mark_published_invalid_url_no_write(queue_file):
    before = queue_file.read_text()
    ref = qw.compute_ref_code("alpha-FIRSTPROD")
    res = qw.mark_published(queue_file, ref, "https://example.com/not-ig")
    assert res.status == "invalid_url" and res.ok is False
    assert queue_file.read_text() == before


def test_mark_published_wrong_state_no_write(queue_file):
    before = queue_file.read_text()
    ref = qw.compute_ref_code("gamma-draft")  # state=drafted, not publishable
    res = qw.mark_published(queue_file, ref, VALID_URL)
    assert res.status == "wrong_state" and res.ok is False
    assert queue_file.read_text() == before


# ── write_queue_atomic preserves structure ────────────────────────────────


def test_write_queue_atomic_roundtrip(tmp_path):
    items = [_old_schema_item("a"), _new_schema_item("b")]
    p = tmp_path / "q.json"
    qw.write_queue_atomic(p, items)
    assert json.loads(p.read_text()) == items


def test_load_queue_tolerates_items_wrapper(tmp_path):
    p = tmp_path / "q.json"
    p.write_text(json.dumps({"items": [_old_schema_item("a")]}))
    loaded = qw.load_queue(p)
    assert isinstance(loaded, list) and qw.item_id_of(loaded[0]) == "a"
