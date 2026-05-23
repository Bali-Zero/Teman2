"""Unit tests for scripts/wr2_canva_reconcile.py.

The reconciler exists for late Canva Desktop completions: the skill can write
carousel_canva.json after the Python worker timed out. It must therefore match
the same pre-render statuses that canva-apply consumes, including the
fact-checked state `drafts_imaged_checked`.
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
RECONCILE_PATH = SCRIPTS_DIR / "wr2_canva_reconcile.py"


@pytest.fixture
def reconcile_mod():
    """Load wr2_canva_reconcile fresh from scripts/."""
    sys.modules.pop("wr2_canva_reconcile", None)
    spec = importlib.util.spec_from_file_location("wr2_canva_reconcile", RECONCILE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_canva_reconcile"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_fetch_unfinished_includes_fact_checked_status(reconcile_mod):
    """Late Canva output for `drafts_imaged_checked` must be discoverable."""
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])

    asyncio.run(reconcile_mod._fetch_unfinished(conn))

    sql = conn.fetch.call_args[0][0]
    assert "drafts_imaged" in sql
    assert "drafts" in sql
    assert "drafts_imaged_facted" in sql
    assert "drafts_imaged_checked" in sql


def test_apply_update_allows_fact_checked_status(reconcile_mod):
    """The UPDATE guard must allow the same statuses as the SELECT."""
    conn = MagicMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")

    asyncio.run(
        reconcile_mod._apply_update(
            conn,
            uuid.uuid4(),
            "DAHITEST123",
            "https://www.canva.com/design/DAHITEST123/edit",
            "https://www.canva.com/design/DAHITEST123/view",
        )
    )

    sql = conn.execute.call_args[0][0]
    assert "drafts_imaged" in sql
    assert "drafts" in sql
    assert "drafts_imaged_facted" in sql
    assert "drafts_imaged_checked" in sql
