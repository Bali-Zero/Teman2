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


# ── extract_ig_shortcode / build_external_item ─────────────────────────────


@pytest.mark.parametrize("url,code", [
    ("https://www.instagram.com/p/Cabc123_-/", "Cabc123_-"),
    ("https://instagram.com/reel/Xyz789/", "Xyz789"),
    ("http://instagram.com/tv/Abc/?igshid=x", "Abc"),
])
def test_extract_ig_shortcode(url, code):
    assert qw.extract_ig_shortcode(url) == code


def test_extract_ig_shortcode_none_on_profile():
    assert qw.extract_ig_shortcode("https://instagram.com/balizero0") is None


def test_build_external_item_scraper_shape():
    it = qw.build_external_item(VALID_URL, "2026-06-10T00:00:00+00:00", topic="My post")
    assert it["item_id"] == "ig-Cabc123_-"
    assert it["state"] == "published"
    assert it["instagram_post_url"] == VALID_URL
    assert it["instagram_published_at"] == "2026-06-10T00:00:00+00:00"
    assert not it["engagement_metrics"]
    assert it["external"] is True and it["source"] == "manual_external"
    assert it["topic"] == "My post"


def test_build_external_item_auto_topic():
    it = qw.build_external_item(VALID_URL, "2026-06-10T00:00:00+00:00")
    assert "Cabc123_-" in it["topic"]


# ── ingest_external_post — orchestration ───────────────────────────────────


def test_ingest_external_mints_published_item(queue_file):
    before = len(json.loads(queue_file.read_text()))
    res = qw.ingest_external_post(queue_file, VALID_URL, topic="Zero's post")
    assert res.status == "ingested" and res.ok is True
    items = json.loads(queue_file.read_text())
    assert len(items) == before + 1
    new = next(i for i in items if qw.item_id_of(i) == "ig-Cabc123_-")
    assert new["state"] == "published" and new["instagram_post_url"] == VALID_URL
    assert new["topic"] == "Zero's post"


def test_ingest_external_default_published_at_is_scraper_eligible(queue_file):
    # Default published_at must be >24h in the past so the scraper picks it up now.
    from datetime import datetime, timezone
    qw.ingest_external_post(queue_file, VALID_URL)
    items = json.loads(queue_file.read_text())
    new = next(i for i in items if qw.item_id_of(i) == "ig-Cabc123_-")
    pub = datetime.fromisoformat(new["instagram_published_at"])
    age_hours = (datetime.now(timezone.utc) - pub).total_seconds() / 3600
    assert age_hours >= 24


def test_ingest_external_idempotent_same_url(queue_file):
    qw.ingest_external_post(queue_file, VALID_URL)
    n_after_first = len(json.loads(queue_file.read_text()))
    res = qw.ingest_external_post(queue_file, VALID_URL)
    assert res.status == "already_present" and res.ok is True
    assert len(json.loads(queue_file.read_text())) == n_after_first  # no duplicate


def test_ingest_external_invalid_url_no_write(queue_file):
    before = queue_file.read_text()
    res = qw.ingest_external_post(queue_file, "https://example.com/p/x")
    assert res.status == "invalid_url" and res.ok is False
    assert queue_file.read_text() == before


def test_ingest_external_explicit_date(queue_file):
    res = qw.ingest_external_post(queue_file, VALID_URL, published_at="2026-05-01T12:00:00+00:00")
    assert res.ok
    items = json.loads(queue_file.read_text())
    new = next(i for i in items if qw.item_id_of(i) == "ig-Cabc123_-")
    assert new["instagram_published_at"] == "2026-05-01T12:00:00+00:00"


# ── build_external_item / ingest_external_post — ig_media_id (§C, 2026-07-17) ─
#
# The scraper diagnosis (team-lead, live Pro-side) found `build_external_item`
# derives its pseudo-id from the URL SHORTCODE and DISCARDS the real numeric
# Graph media id even when the caller (wr2_ig_discovery.py) already fetched it.
# This threads an OPTIONAL `ig_media_id` through, stored as its own field —
# never folded into item_id's ig-<shortcode> derivation.


def test_build_external_item_omits_ig_media_id_when_not_passed():
    # GUILT/regression guard: no Graph fetch happened -> no fabricated field.
    it = qw.build_external_item(VALID_URL, "2026-06-10T00:00:00+00:00", topic="My post")
    assert "ig_media_id" not in it


def test_build_external_item_stores_ig_media_id_when_passed():
    # INNOCENCE: caller already has the real numeric Graph id -> persisted verbatim,
    # as a STRING, and separate from item_id (which stays shortcode-derived).
    it = qw.build_external_item(
        VALID_URL, "2026-06-10T00:00:00+00:00", topic="My post", ig_media_id=17895695668004550,
    )
    assert it["ig_media_id"] == "17895695668004550"
    assert it["item_id"] == "ig-Cabc123_-"  # unchanged — never derived from ig_media_id


def test_build_external_item_omits_ig_media_id_when_falsy():
    # empty string / 0 must not produce a bogus ig_media_id="" or "0" field.
    it = qw.build_external_item(VALID_URL, "2026-06-10T00:00:00+00:00", ig_media_id="")
    assert "ig_media_id" not in it


def test_ingest_external_without_ig_media_id_omits_field(queue_file):
    # Regression: the WR2 Control app's manual §A entry point never has a Graph
    # fetch — the minted item must degrade gracefully (no field), not crash.
    res = qw.ingest_external_post(queue_file, VALID_URL)
    assert res.ok
    items = json.loads(queue_file.read_text())
    new = next(i for i in items if qw.item_id_of(i) == "ig-Cabc123_-")
    assert "ig_media_id" not in new


def test_ingest_external_with_ig_media_id_persists_it(queue_file):
    res = qw.ingest_external_post(
        queue_file, VALID_URL, ig_media_id="17895695668004550",
    )
    assert res.ok
    items = json.loads(queue_file.read_text())
    new = next(i for i in items if qw.item_id_of(i) == "ig-Cabc123_-")
    assert new["ig_media_id"] == "17895695668004550"


# ── backfill_media_id — reconciliation for already-known posts (§C point 3) ──
#
# WR2-native carousels are published via the app's own publish gate, which
# records the permalink but NEVER a Graph media id. wr2_ig_discovery.py's
# reconciliation pass (find_media_id_backfills) calls this to attach the real
# id back onto a native entry once discovery matches it by shortcode.


def _native_published_item(item_id="bali-pma-rental-crackdown", ig_url=VALID_URL):
    """A WR2-native carousel entry: published via the app's own gate — has a
    permalink but no ig_media_id (the exact shape backfill_media_id targets)."""
    return {
        "id": item_id,
        "topic_slug": item_id,
        "state": "published",
        "instagram_post_url": ig_url,
        "instagram_published_at": "2026-07-10T00:00:00+00:00",
        "engagement_metrics": None,
    }


@pytest.fixture
def native_queue_file(tmp_path):
    items = [_native_published_item()]
    p = tmp_path / "native-queue.json"
    p.write_text(json.dumps(items))
    return p


def test_backfill_media_id_not_found_no_write(native_queue_file):
    before = native_queue_file.read_text()
    res = qw.backfill_media_id(native_queue_file, "does-not-exist", "17895695668004550")
    assert res.status == "not_found" and res.ok is False
    assert native_queue_file.read_text() == before


def test_backfill_media_id_backfills_native_entry(native_queue_file):
    res = qw.backfill_media_id(
        native_queue_file, "bali-pma-rental-crackdown", "17895695668004550",
    )
    assert res.status == "backfilled" and res.ok is True
    items = json.loads(native_queue_file.read_text())
    updated = next(i for i in items if qw.item_id_of(i) == "bali-pma-rental-crackdown")
    assert updated["ig_media_id"] == "17895695668004550"
    # everything else on the item survives untouched
    assert updated["instagram_post_url"] == VALID_URL
    assert updated["state"] == "published"


def test_backfill_media_id_idempotent_replay_is_noop(native_queue_file):
    qw.backfill_media_id(native_queue_file, "bali-pma-rental-crackdown", "17895695668004550")
    after_first = native_queue_file.read_text()
    res = qw.backfill_media_id(native_queue_file, "bali-pma-rental-crackdown", "17895695668004550")
    assert res.status == "already_backfilled" and res.ok is True
    assert native_queue_file.read_text() == after_first  # no duplicate write


def test_backfill_media_id_conflict_refuses_overwrite(native_queue_file):
    qw.backfill_media_id(native_queue_file, "bali-pma-rental-crackdown", "17895695668004550")
    after_first = native_queue_file.read_text()
    res = qw.backfill_media_id(native_queue_file, "bali-pma-rental-crackdown", "99999999999999999")
    assert res.status == "conflict" and res.ok is False
    assert native_queue_file.read_text() == after_first  # refused — no overwrite


# ── add_external / validate_external_payload — M5->Pro propagation (§B) ────


def _external_payload(**overrides):
    payload = {
        "item_id": "external_2026-07-17T090000_my-manual-post",
        "state": "published",
        "instagram_post_url": VALID_URL,
        "source": "external_manual",
        "published_at": "2026-07-17T09:00:00+00:00",
        "instagram_published_at": "2026-07-17T09:00:00+00:00",
        "topic": "My manual post",
        "topic_slug": "my-manual-post",
        "slide_count": 0,
        "created_at": "2026-07-17T09:00:00+00:00",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("field", list(qw.REQUIRED_EXTERNAL_PAYLOAD_FIELDS))
def test_validate_external_payload_rejects_missing_required_field(field):
    payload = _external_payload()
    del payload[field]
    err = qw.validate_external_payload(payload)
    assert err is not None and field in err


def test_validate_external_payload_rejects_wrong_state():
    err = qw.validate_external_payload(_external_payload(state="drafted"))
    assert err is not None and "state" in err


def test_validate_external_payload_rejects_wrong_source():
    err = qw.validate_external_payload(_external_payload(source="manual_external"))
    assert err is not None and "source" in err


def test_validate_external_payload_rejects_bad_url():
    err = qw.validate_external_payload(_external_payload(instagram_post_url="https://example.com/not-ig"))
    assert err is not None and "instagram_post_url" in err


def test_validate_external_payload_accepts_well_formed_payload():
    assert qw.validate_external_payload(_external_payload()) is None


def test_add_external_happy_path_appends_verbatim(queue_file):
    before = len(json.loads(queue_file.read_text()))
    payload = _external_payload()
    res = qw.add_external(queue_file, payload)
    assert res.status == "added" and res.ok is True
    items = json.loads(queue_file.read_text())
    assert len(items) == before + 1
    new = next(i for i in items if qw.item_id_of(i) == payload["item_id"])
    assert new["state"] == "published"
    assert new["instagram_post_url"] == VALID_URL
    assert new["source"] == "external_manual"
    assert new["topic_slug"] == "my-manual-post"
    assert new["slide_count"] == 0
    # OTHER items untouched
    alpha = next(i for i in items if qw.item_id_of(i) == "alpha-FIRSTPROD")
    assert alpha["state"] == "applied_ready_for_damar"


def test_add_external_invalid_payload_no_write(queue_file):
    before = queue_file.read_text()
    res = qw.add_external(queue_file, _external_payload(state="drafted"))
    assert res.status == "invalid_payload" and res.ok is False
    assert queue_file.read_text() == before


def test_add_external_same_item_id_different_post_is_conflict(queue_file):
    """GUILT (Codex red-team, 2026-07-17, finding E): the SAME item_id but a
    DIFFERENT post (different URL/shortcode) must be a distinct `conflict`
    status with ok=False — NOT `already_present`/ok=True, which the wrapper
    reads as "safe to mark synced" and would silently lose the genuinely
    distinct post with no record it was ever dropped. Was previously
    asserting the pre-finding-E (buggy) already_present/ok=True behavior."""
    payload = _external_payload()
    qw.add_external(queue_file, payload)
    n_after_first = len(json.loads(queue_file.read_text()))
    # same item_id, DIFFERENT URL — a genuinely different post, must conflict
    dup = _external_payload(instagram_post_url="https://www.instagram.com/p/DIFFERENT99/")
    res = qw.add_external(queue_file, dup)
    assert res.status == "conflict" and res.ok is False
    items = json.loads(queue_file.read_text())
    assert len(items) == n_after_first  # no duplicate appended, no write at all
    kept = next(i for i in items if qw.item_id_of(i) == payload["item_id"])
    assert kept["instagram_post_url"] == VALID_URL  # original untouched


def test_add_external_duplicate_url_different_item_id_refused(queue_file):
    payload = _external_payload()
    qw.add_external(queue_file, payload)
    n_after_first = len(json.loads(queue_file.read_text()))
    # different item_id, SAME url — must still be refused as a duplicate
    dup = _external_payload(item_id="external_2026-07-17T091500_retry-post", topic_slug="retry-post")
    res = qw.add_external(queue_file, dup)
    assert res.status == "already_present" and res.ok is True
    assert len(json.loads(queue_file.read_text())) == n_after_first


def test_add_external_idempotent_replay_safe(queue_file):
    """The M5->Pro push-back loop may retry the SAME payload after a flaky ssh —
    replaying the identical payload twice must be a no-op, not an error."""
    payload = _external_payload()
    res1 = qw.add_external(queue_file, payload)
    assert res1.status == "added"
    res2 = qw.add_external(queue_file, payload)
    assert res2.status == "already_present" and res2.ok is True
