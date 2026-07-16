"""Unit tests for the external-post write-path in scripts/wr2_queue_writer.py:
`add_external` (§B propagation landing point) and `backfill_media_id` (§C
reconciliation). Loaded via importlib, same convention as the other wr2 test
modules in this directory.

Covers Codex red-team findings D, E, F, G (2026-07-17):
  D — add_external dedup must compare by shortcode FIRST, exact-string only
      as a fallback (a `?utm_...` variant of the same post must not double-enqueue).
  E — same item_id but a genuinely DIFFERENT post (different URL/shortcode)
      must return status="conflict", ok=False — never "already_present"/ok=True,
      which the wrapper reads as "safe to mark synced" and would silently lose
      the distinct post.
  F — backfill_media_id must compare-and-set under its OWN lock: an
      `expected_shortcode` mismatch (the entry's URL moved between discovery's
      snapshot and this write) must refuse (conflict), never attach a possibly
      stale media id.
  G — validate_external_payload must type-check optional `slide_count` (int
      >= 0) and `published_at` (ISO-parseable) when present.
"""
from __future__ import annotations

import importlib.util
import json
import sys
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


qw = _load("wr2_queue_writer")


def _external_payload(**overrides) -> dict:
    payload = {
        "item_id": "external_2026-07-17T090000_my-manual-post",
        "state": "published",
        "instagram_post_url": "https://www.instagram.com/p/ManualPost1/",
        "source": qw.EXTERNAL_MANUAL_SOURCE,
        "topic_slug": "my-manual-post",
        "published_at": "2026-07-17T09:00:00+00:00",
        "slide_count": 6,
    }
    payload.update(overrides)
    return payload


# ── finding D — shortcode-first dedup compare ────────────────────────────────


def test_add_external_dedup_by_shortcode_ignores_query_string_variant(tmp_path):
    """GUILT: an existing entry's URL carries a stray ?utm_... query string but
    is the SAME post (same shortcode) as the incoming payload — must be
    refused as already_present, not double-enqueued as a byte-for-byte
    different string."""
    qpath = tmp_path / "q.json"
    existing = _external_payload(
        item_id="external_2026-07-17T080000_earlier-write",
        instagram_post_url="https://www.instagram.com/p/ManualPost1/?utm_source=ig",
    )
    qw.write_queue_atomic(qpath, [existing])

    incoming = _external_payload(
        item_id="external_2026-07-17T090000_my-manual-post",
        instagram_post_url="https://www.instagram.com/p/ManualPost1/",
    )
    res = qw.add_external(qpath, incoming)
    assert res.status == "already_present"
    assert res.ok is True
    assert len(qw.load_queue(qpath)) == 1


def test_add_external_innocence_different_shortcode_is_added(tmp_path):
    """INNOCENCE: a genuinely different post (different shortcode) must still
    be added normally, even though the URLs share the same domain/prefix."""
    qpath = tmp_path / "q.json"
    existing = _external_payload(
        item_id="external_2026-07-17T080000_earlier-write",
        instagram_post_url="https://www.instagram.com/p/DifferentPost/",
    )
    qw.write_queue_atomic(qpath, [existing])

    incoming = _external_payload()
    res = qw.add_external(qpath, incoming)
    assert res.status == "added"
    assert res.ok is True
    assert len(qw.load_queue(qpath)) == 2


# ── finding E — same item_id, different post -> conflict, not already_present ─


def test_add_external_same_item_id_different_url_is_conflict_not_already_present(tmp_path):
    """GUILT (finding E): the SAME item_id already exists but with a
    DIFFERENT URL/shortcode — this must be a distinct `conflict` status with
    ok=False, never collapsed into `already_present`/ok=True (which the
    wrapper reads as "safe to mark synced", silently losing the genuinely
    distinct post with no record it was ever dropped)."""
    qpath = tmp_path / "q.json"
    existing = _external_payload(instagram_post_url="https://www.instagram.com/p/OriginalPost/")
    qw.write_queue_atomic(qpath, [existing])

    incoming = _external_payload(instagram_post_url="https://www.instagram.com/p/ADifferentPostEntirely/")
    res = qw.add_external(qpath, incoming)
    assert res.status == "conflict"
    assert res.ok is False
    # no write — queue untouched
    assert qw.load_queue(qpath) == [existing]


def test_add_external_same_item_id_same_url_is_already_present_ok_true(tmp_path):
    """INNOCENCE: a genuine retry (same item_id, same post) is the normal
    idempotent no-op path — already_present, ok=True, safe to mark synced."""
    qpath = tmp_path / "q.json"
    existing = _external_payload()
    qw.write_queue_atomic(qpath, [existing])

    res = qw.add_external(qpath, _external_payload())
    assert res.status == "already_present"
    assert res.ok is True


def test_cmd_add_external_exit_code_reflects_conflict(tmp_path, capsys):
    """Verifies finding E needs no wrapper-side change: _cmd_add_external's
    exit code already propagates ok=False as a nonzero return, which is what
    the wrapper's existing `if ssh ...; then mark-synced; else WARN; fi` gate
    keys off of."""
    qpath = tmp_path / "q.json"
    existing = _external_payload(instagram_post_url="https://www.instagram.com/p/OriginalPost/")
    qw.write_queue_atomic(qpath, [existing])

    import argparse
    args = argparse.Namespace(
        queue=str(qpath),
        payload=json.dumps(_external_payload(instagram_post_url="https://www.instagram.com/p/ADifferentPostEntirely/")),
    )
    rc = qw._cmd_add_external(args)
    assert rc == 1


# ── finding F — backfill_media_id compare-and-set under lock ────────────────


def test_backfill_media_id_expected_shortcode_mismatch_is_conflict(tmp_path):
    """GUILT (finding F): the entry's URL changed since discovery's snapshot
    matched it on shortcode ABC123 — backfill must recompute the CURRENT
    shortcode under its own lock and refuse (conflict, no write) rather than
    attach media_id for the OLD post onto whatever now sits at this item_id."""
    qpath = tmp_path / "q.json"
    item = {"item_id": "carousel_1", "instagram_post_url": "https://www.instagram.com/p/NEWCODE/"}
    qw.write_queue_atomic(qpath, [item])

    res = qw.backfill_media_id(qpath, "carousel_1", "17895695668004550", expected_shortcode="ABC123")
    assert res.status == "conflict"
    assert res.ok is False
    after = qw.load_queue(qpath)
    assert "ig_media_id" not in after[0]


def test_backfill_media_id_expected_shortcode_matches_writes_normally(tmp_path):
    """INNOCENCE: the entry's current shortcode matches what discovery
    snapshotted -> the write proceeds exactly as before finding F."""
    qpath = tmp_path / "q.json"
    item = {"item_id": "carousel_1", "instagram_post_url": "https://www.instagram.com/p/ABC123/"}
    qw.write_queue_atomic(qpath, [item])

    res = qw.backfill_media_id(qpath, "carousel_1", "17895695668004550", expected_shortcode="ABC123")
    assert res.status == "backfilled"
    assert res.ok is True
    after = qw.load_queue(qpath)
    assert after[0]["ig_media_id"] == "17895695668004550"


def test_backfill_media_id_no_expected_shortcode_skips_the_check(tmp_path):
    """Backward compatibility: callers that never snapshotted a shortcode
    (expected_shortcode=None, the default) get the pre-finding-F behavior —
    no compare-and-set, write proceeds."""
    qpath = tmp_path / "q.json"
    item = {"item_id": "carousel_1", "instagram_post_url": "https://www.instagram.com/p/Whatever/"}
    qw.write_queue_atomic(qpath, [item])

    res = qw.backfill_media_id(qpath, "carousel_1", "17895695668004550")
    assert res.status == "backfilled"


def test_backfill_media_id_still_conflicts_on_different_existing_media_id(tmp_path):
    """Regression guard: the pre-existing "different ig_media_id already
    present" conflict path must still work when expected_shortcode matches
    (or is omitted) — finding F's new check is additive, not a replacement."""
    qpath = tmp_path / "q.json"
    item = {"item_id": "carousel_1", "instagram_post_url": "https://www.instagram.com/p/ABC123/",
            "ig_media_id": "11111111111111111"}
    qw.write_queue_atomic(qpath, [item])

    res = qw.backfill_media_id(qpath, "carousel_1", "22222222222222222", expected_shortcode="ABC123")
    assert res.status == "conflict"
    after = qw.load_queue(qpath)
    assert after[0]["ig_media_id"] == "11111111111111111"


# ── finding G — validate_external_payload type-checks optional fields ──────


def test_validate_external_payload_rejects_negative_slide_count():
    err = qw.validate_external_payload(_external_payload(slide_count=-1))
    assert err is not None and "slide_count" in err


def test_validate_external_payload_rejects_non_int_slide_count():
    err = qw.validate_external_payload(_external_payload(slide_count="six"))
    assert err is not None and "slide_count" in err


def test_validate_external_payload_rejects_bool_slide_count():
    # bool is a subclass of int in Python — must be explicitly excluded.
    err = qw.validate_external_payload(_external_payload(slide_count=True))
    assert err is not None and "slide_count" in err


def test_validate_external_payload_accepts_zero_slide_count():
    # INNOCENCE: 0 is a valid slide_count (>= 0), must not be rejected.
    err = qw.validate_external_payload(_external_payload(slide_count=0))
    assert err is None


def test_validate_external_payload_accepts_missing_slide_count():
    # INNOCENCE: slide_count is optional — absence is fine.
    payload = _external_payload()
    del payload["slide_count"]
    assert qw.validate_external_payload(payload) is None


def test_validate_external_payload_rejects_unparseable_published_at():
    err = qw.validate_external_payload(_external_payload(published_at="not-a-date"))
    assert err is not None and "published_at" in err


def test_validate_external_payload_accepts_iso_published_at_with_z_suffix():
    # INNOCENCE: a trailing "Z" (not directly fromisoformat-parseable pre-3.11)
    # must still be accepted via the Z->+00:00 normalization.
    err = qw.validate_external_payload(_external_payload(published_at="2026-07-17T09:00:00Z"))
    assert err is None


def test_validate_external_payload_accepts_missing_published_at():
    payload = _external_payload()
    del payload["published_at"]
    assert qw.validate_external_payload(payload) is None
