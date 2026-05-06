"""Tests for --dry-run mode (no MCP calls, preview file)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def _import_apo():
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import execute_apoptosis  # type: ignore[import-not-found]
    return execute_apoptosis


def test_dry_run_makes_no_mcp_calls(monkeypatch, tmp_path):
    apo = _import_apo()
    monkeypatch.setattr(apo, "PREVIEW_PATH", tmp_path / "preview.md")
    rename_calls = []
    monkeypatch.setattr(apo, "nlm_rename", lambda u, n: rename_calls.append(u))
    apo.run_apoptosis(pending=["uuid-1", "uuid-2"], dry_run=True)
    assert rename_calls == []


def test_dry_run_writes_preview_to_tmp(monkeypatch, tmp_path):
    apo = _import_apo()
    preview = tmp_path / "preview.md"
    monkeypatch.setattr(apo, "PREVIEW_PATH", preview)
    apo.run_apoptosis(pending=["uuid-1"], dry_run=True)
    assert preview.exists()


def test_dry_run_preview_lists_all_pending_nb(monkeypatch, tmp_path):
    apo = _import_apo()
    preview = tmp_path / "preview.md"
    monkeypatch.setattr(apo, "PREVIEW_PATH", preview)
    apo.run_apoptosis(pending=["uuid-aaa", "uuid-bbb", "uuid-ccc"], dry_run=True)
    content = preview.read_text()
    assert "uuid-aaa" in content
    assert "uuid-bbb" in content
    assert "uuid-ccc" in content


def test_dry_run_preview_mentions_apply_command(monkeypatch, tmp_path):
    apo = _import_apo()
    preview = tmp_path / "preview.md"
    monkeypatch.setattr(apo, "PREVIEW_PATH", preview)
    apo.run_apoptosis(pending=["uuid-1"], dry_run=True)
    assert "--apply" in preview.read_text()
