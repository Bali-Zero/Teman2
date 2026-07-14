"""Tests for scripts/wr2_carousel_import.py — pure helpers only.

Scar W96 discipline: every fixture below uses tmp_path, never the real
`human-review-queue.json` or `apps/war-room/output/carousel/`. No sips
invocation, no network. `process_import` (the I/O orchestrator that shells
out to sips/pdftoppm) is exercised separately by the one live smoke-test run
in the PR description, not here.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_MODULE_PATH = _THIS_DIR / "wr2_carousel_import.py"
_spec = importlib.util.spec_from_file_location("wr2_carousel_import", _MODULE_PATH)
wci = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = wci
_spec.loader.exec_module(wci)


# ── natural_sort_key ────────────────────────────────────────────────────────


def test_natural_sort_key_numeric_ordering():
    names = ["10.png", "2.png", "1.png"]
    assert sorted(names, key=wci.natural_sort_key) == ["1.png", "2.png", "10.png"]


def test_natural_sort_key_mixed_prefix():
    names = ["slide9.png", "slide10.png", "slide2.png"]
    assert sorted(names, key=wci.natural_sort_key) == [
        "slide2.png", "slide9.png", "slide10.png"
    ]


# ── slugify / derive_slug / humanize_slug ──────────────────────────────────


def test_slugify_basic():
    assert wci.slugify("Coretax Went Dark!") == "coretax-went-dark"


def test_slugify_never_empty():
    assert wci.slugify("!!!") == "imported"


def test_derive_slug_explicit_slug_wins():
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    assert wci.derive_slug("My Slug", "some topic", now) == "my-slug"


def test_derive_slug_from_topic_when_no_slug():
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    assert wci.derive_slug(None, "Visa Rules Changed", now) == "visa-rules-changed"


def test_derive_slug_timestamp_fallback():
    now = datetime(2026, 7, 14, 15, 30, 0, tzinfo=timezone.utc)
    assert wci.derive_slug(None, None, now) == "imported-20260714-153000"


def test_humanize_slug():
    assert wci.humanize_slug("visa-rules-changed") == "Visa Rules Changed"


def test_iso_z_format():
    dt = datetime(2026, 7, 14, 5, 16, 22, tzinfo=timezone.utc)
    assert wci.iso_z(dt) == "2026-07-14T05:16:22Z"


# ── to_tilde_path ───────────────────────────────────────────────────────────


def test_to_tilde_path_under_home(tmp_path):
    home = tmp_path / "home" / "someuser"
    home.mkdir(parents=True)
    target = home / "Desktop/nuzantara/apps/war-room/output/carousel/my-slug"
    assert wci.to_tilde_path(target, home=home) == "~/Desktop/nuzantara/apps/war-room/output/carousel/my-slug"


def test_to_tilde_path_outside_home_unchanged(tmp_path):
    home = tmp_path / "home" / "someuser"
    home.mkdir(parents=True)
    outside = tmp_path / "elsewhere" / "carousel"
    assert wci.to_tilde_path(outside, home=home) == str(outside)


# ── classify_inputs ─────────────────────────────────────────────────────────


def test_classify_inputs_single_pdf(tmp_path):
    pdf = tmp_path / "deck.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    kind, sources = wci.classify_inputs([str(pdf)])
    assert kind == "pdf"
    assert sources == [pdf]


def test_classify_inputs_directory_natural_sorted(tmp_path):
    d = tmp_path / "slides"
    d.mkdir()
    for name in ["2.png", "10.jpg", "1.webp", "notes.txt"]:
        (d / name).write_bytes(b"x")
    kind, sources = wci.classify_inputs([str(d)])
    assert kind == "dir"
    assert [p.name for p in sources] == ["1.webp", "2.png", "10.jpg"]


def test_classify_inputs_empty_directory_raises(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    try:
        wci.classify_inputs([str(d)])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "no supported images" in str(e)


def test_classify_inputs_individual_files_natural_sorted(tmp_path):
    files = []
    for name in ["slide10.png", "slide2.jpg", "slide1.heic"]:
        p = tmp_path / name
        p.write_bytes(b"x")
        files.append(str(p))
    kind, sources = wci.classify_inputs(files)
    assert kind == "images"
    assert [p.name for p in sources] == ["slide1.heic", "slide2.jpg", "slide10.png"]


def test_classify_inputs_missing_file_raises(tmp_path):
    missing = tmp_path / "nope.png"
    try:
        wci.classify_inputs([str(missing)])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "not found" in str(e)


def test_classify_inputs_unsupported_extension_raises(tmp_path):
    bad = tmp_path / "notes.txt"
    bad.write_text("hello")
    try:
        wci.classify_inputs([str(bad)])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "unsupported file type" in str(e)


def test_classify_inputs_no_args_raises():
    try:
        wci.classify_inputs([])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "no input" in str(e)


# ── build_manifest ───────────────────────────────────────────────────────────


def test_build_manifest_shape():
    manifest = wci.build_manifest(
        topic="Test Topic",
        png_paths=["/a/01.png", "/a/02.png"],
        fit_mode="contain",
        import_source="deck.pdf",
        pdf_path="/a/deck.pdf",
    )
    assert manifest == {
        "topic": "Test Topic",
        "total_slides": 2,
        "families": ["external-import"],
        "heroes_expected": 0,
        "heroes_placed": 0,
        "slides_rendered": 2,
        "ok": True,
        "failures": [],
        "png_paths": ["/a/01.png", "/a/02.png"],
        "pdf_path": "/a/deck.pdf",
        "imported": True,
        "import_source": "deck.pdf",
        "fit_mode": "contain",
    }
    # Must be JSON-serializable as-is (this is what gets written to disk).
    json.dumps(manifest)


def test_import_source_label_joins_basenames():
    assert wci.import_source_label(["/x/a.png", "/y/b.jpg"]) == "a.png,b.jpg"


# ── build_queue_item ─────────────────────────────────────────────────────────


def test_build_queue_item_shape_and_state(tmp_path):
    home = tmp_path / "home" / "someuser"
    home.mkdir(parents=True)
    carousel_dir = home / "Desktop/nuzantara/apps/war-room/output/carousel/my-slug"
    now = datetime(2026, 7, 14, 5, 16, 22, tzinfo=timezone.utc)

    item = wci.build_queue_item(
        slug="my-slug", topic="My Topic", slide_count=5,
        carousel_dir=carousel_dir, now=now, home=home,
    )

    assert item["id"] == "carousel_2026-07-14T05:16:22Z_my-slug"
    assert item["topic_slug"] == "my-slug"
    assert item["topic"] == "My Topic"
    assert item["drafted_at"] == "2026-07-14T05:16:22Z"
    assert item["carousel_path"] == "~/Desktop/nuzantara/apps/war-room/output/carousel/my-slug/"
    assert item["slides_dir"] == "~/Desktop/nuzantara/apps/war-room/output/carousel/my-slug/slides/"
    assert item["drive_url"] is None
    assert item["media_type"] == "carousel"
    assert item["slide_count"] == 5
    assert item["critic_overall_verdict"] == "external"
    assert item["critic_summary"] == "imported — not critic-gated"
    assert item["fact_check_status"] == "external"
    assert item["state"] == "drafted"
    assert item["state_history"] == [
        {"state": "drafted", "at": "2026-07-14T05:16:22Z", "by": "wr2-carousel-import"}
    ]
    assert item["instagram_post_url"] is None
    assert item["instagram_published_at"] is None
    assert item["engagement_metrics"] is None
    assert item["source"] == "external-import"
    # draft_id must be a well-formed uuid4 string.
    import uuid
    uuid.UUID(item["draft_id"], version=4)
    # Must be JSON-serializable as-is (this is what gets appended to the queue).
    json.dumps(item, ensure_ascii=False)


# ── resolve_output_root / resolve_queue_path env overrides ─────────────────


def test_resolve_output_root_env_override(tmp_path, monkeypatch):
    override = tmp_path / "custom-output"
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(override))
    assert wci.resolve_output_root() == override


def test_resolve_output_root_default_no_env(monkeypatch):
    monkeypatch.delenv("WR2_OUTPUT_ROOT", raising=False)
    assert wci.resolve_output_root() == wci.DEFAULT_OUTPUT_ROOT


def test_resolve_queue_path_arg_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("WR2_QUEUE_PATH", str(tmp_path / "env-queue.json"))
    explicit = tmp_path / "explicit-queue.json"
    assert wci.resolve_queue_path(str(explicit)) == explicit


def test_resolve_queue_path_env_fallback(tmp_path, monkeypatch):
    env_path = tmp_path / "env-queue.json"
    monkeypatch.setenv("WR2_QUEUE_PATH", str(env_path))
    assert wci.resolve_queue_path(None) == env_path
