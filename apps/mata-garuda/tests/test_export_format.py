"""Tests for slugify + export markdown shape."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _import_apo():
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import execute_apoptosis  # type: ignore[import-not-found]
    return execute_apoptosis


def test_slugify_strips_non_ascii():
    apo = _import_apo()
    assert apo.slugify("Café Núzantará") == "cafe-nuzantara"


def test_slugify_handles_empty_input_with_fallback_untitled():
    apo = _import_apo()
    assert apo.slugify("") == "untitled"
    assert apo.slugify("   ") == "untitled"


def test_slugify_truncates_at_80():
    apo = _import_apo()
    assert len(apo.slugify("a" * 200)) == 80


def test_export_filename_format():
    apo = _import_apo()
    fn = apo.export_filename(uuid="dc5d01cd-e99f-4c8f-aae4-75060b43d0de", title="My NB")
    # <uuid_short>-<slug>-2026-05-07.md
    assert fn.endswith("-2026-05-07.md")
    assert "dc5d01cd" in fn


def test_export_frontmatter_fields_complete(tmp_path):
    apo = _import_apo()
    out = apo.render_export(
        uuid="dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
        title="My NB",
        sources=[{"type": "url", "url": "https://example.com", "snippet": "x"}],
        summary="x" * 600,
    )
    assert "---" in out
    assert "uuid: dc5d01cd-e99f-4c8f-aae4-75060b43d0de" in out
    assert "exported_at:" in out


def test_export_includes_summary_500w():
    apo = _import_apo()
    out = apo.render_export(
        uuid="dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
        title="My NB",
        sources=[],
        summary="word " * 500,
    )
    assert "## Summary" in out


def test_export_includes_reimport_command_for_url_sources():
    apo = _import_apo()
    out = apo.render_export(
        uuid="dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
        title="My NB",
        sources=[{"type": "url", "url": "https://example.com/a"}],
        summary="x",
    )
    assert "reimport_command:" in out
    assert "https://example.com/a" in out


def test_export_omits_reimport_for_text_sources():
    apo = _import_apo()
    out = apo.render_export(
        uuid="dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
        title="My NB",
        sources=[{"type": "text", "snippet": "raw text"}],
        summary="x",
    )
    assert "reimport_command:" not in out


def test_kill_uses_archived_prefix(monkeypatch, tmp_path):
    """KILL_PENDING items get ARCHIVED prefix (legacy/test path: flat list)."""
    apo = _import_apo()
    monkeypatch.setattr(apo, "PREVIEW_PATH", tmp_path / "preview.md")
    apo.run_apoptosis(pending=["uuid-kill-1"], dry_run=True)
    content = (tmp_path / "preview.md").read_text()
    assert "[ARCHIVED-2026-05-07]" in content


def test_export_uses_exported_prefix(monkeypatch, tmp_path):
    """EXPORT_PENDING items get EXPORTED prefix (per-tuple prefix path)."""
    apo = _import_apo()
    monkeypatch.setattr(apo, "PREVIEW_PATH", tmp_path / "preview.md")
    apo.run_apoptosis(
        pending=[("uuid-exp-1", apo.EXPORTED_PREFIX)],
        dry_run=True,
    )
    content = (tmp_path / "preview.md").read_text()
    assert "[EXPORTED-2026-05-07]" in content


def test_render_preview_separates_archived_from_exported(monkeypatch, tmp_path):
    """The preview's count breakdown shows archived vs exported."""
    apo = _import_apo()
    monkeypatch.setattr(apo, "PREVIEW_PATH", tmp_path / "preview.md")
    apo.run_apoptosis(
        pending=[
            ("uuid-1", apo.ARCHIVED_PREFIX),
            ("uuid-2", apo.EXPORTED_PREFIX),
            ("uuid-3", apo.EXPORTED_PREFIX),
        ],
        dry_run=True,
    )
    content = (tmp_path / "preview.md").read_text()
    assert "1 → ARCHIVED prefix" in content
    assert "2 → EXPORTED prefix" in content
