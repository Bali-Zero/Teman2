"""Tests for mata_garuda_invalidation_sweep.py — argparse + dry-run paths.

DB-touching test (real PG connection + INSERT/UPDATE round-trip) lives in
the integration test layer when a Pro-local Postgres is available. This
file covers the pure-Python argparse + logging surface so it runs in
<50ms on every PR (no Docker, no DB required).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the script importable as a module
_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(_SCRIPT_PATH))

import mata_garuda_invalidation_sweep as sweep  # noqa: E402


def test_parse_args_default_batch_size():
    args = sweep._parse_args(["--database-url", "postgres://x"])
    assert args.batch_size == 1000


def test_parse_args_custom_batch_size():
    args = sweep._parse_args([
        "--database-url", "postgres://x",
        "--batch-size", "250",
    ])
    assert args.batch_size == 250


def test_parse_args_dry_run_default_false():
    args = sweep._parse_args(["--database-url", "postgres://x"])
    assert args.dry_run is False


def test_parse_args_dry_run_flag():
    args = sweep._parse_args([
        "--database-url", "postgres://x",
        "--dry-run",
    ])
    assert args.dry_run is True


def test_parse_args_verbose_flag():
    args = sweep._parse_args([
        "--database-url", "postgres://x",
        "--verbose",
    ])
    assert args.verbose is True


def test_parse_args_database_url_required(monkeypatch):
    """Without env DATABASE_URL and without --database-url, the entry
    point must error out cleanly (exit 2), not crash with a stack trace."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    args = sweep._parse_args([])
    assert args.database_url is None


def test_main_returns_2_when_database_url_missing(monkeypatch, caplog):
    """_main_async must early-return exit 2 when no DATABASE_URL is set."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    caplog.set_level("ERROR")
    rc = sweep.main([])
    assert rc == 2
    assert any("DATABASE_URL" in record.message for record in caplog.records)
