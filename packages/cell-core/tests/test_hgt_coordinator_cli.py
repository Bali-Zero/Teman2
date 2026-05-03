"""CLI tests for the HGT coordinator (Sprint 1 W2)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cell_core.hgt_coordinator import cli as cli_mod
from cell_core.hgt_coordinator.audit_log import init_db, list_pending, record_proposal
from cell_core.hgt_coordinator.proposal import Proposal


@pytest.fixture(autouse=True)
def isolate_audit_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Force every CLI test to use a per-test SQLite path so they don't
    pollute ./data/hgt_coordinator/proposals.db (which would also fail
    on CI runners without write access there)."""
    db = tmp_path / "proposals.db"
    monkeypatch.setenv("HGT_COORDINATOR_AUDIT_LOG", str(db))
    # The audit_log module reads env at import time, but we re-init via
    # path= override; ensure the module-level DEFAULT is recomputed for
    # tests that don't pass an explicit path.
    import importlib

    from cell_core.hgt_coordinator import audit_log

    importlib.reload(audit_log)
    init_db(db)
    return db


def _connect_redis_returns_none(*_args: Any, **_kw: Any):
    """Replacement for ``cli._connect_redis`` to bypass network in tests."""

    async def _coro() -> None:
        return None

    return _coro()


def test_observe_empty_stream_emits_zero_proposals(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``observe`` with no Redis connection produces empty bucket JSON."""
    monkeypatch.setattr(cli_mod, "_connect_redis", _connect_redis_returns_none)
    rc = cli_mod.main(["observe", "--window-days", "7"])
    captured = capsys.readouterr()
    assert rc == 0, f"stderr={captured.err}"
    payload = json.loads(captured.out.strip().splitlines()[-1])
    assert payload["proposals"] == []
    assert payload["deferred"] == []
    assert payload["rejected"] == []
    assert "summary" in payload
    assert payload["window_days"] == 7


def test_list_pending_returns_inserted_row(
    isolate_audit_log: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A proposal manually inserted via record_proposal shows up via the CLI."""
    p = Proposal(
        skill_name="manual_skill",
        source_cells=("cell-X",),
        target_cell_candidates=("cell-Y",),
        domain="kbli",
        total_uses=11,
        avg_confidence=0.82,
        std_confidence=0.05,
        confidence=0.82,
        transfer_rationale="manual test",
        recommended_action="propose",
        observation_window_days=7,
    )
    inserted_id = record_proposal(p, path=isolate_audit_log)
    rc = cli_mod.main(["list-pending", "--limit", "10"])
    captured = capsys.readouterr()
    assert rc == 0, f"stderr={captured.err}"
    payload = json.loads(captured.out.strip().splitlines()[-1])
    assert payload["count"] == 1
    assert payload["pending"][0]["skill_name"] == "manual_skill"
    assert payload["pending"][0]["id"] == inserted_id
    # Sanity: list_pending returns same row independently.
    rows = list_pending(isolate_audit_log)
    assert len(rows) == 1


def test_bad_args_returns_usage_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Invalid subcommand yields a non-zero exit (usage = 1)."""
    rc = cli_mod.main(["definitely-not-a-cmd"])
    assert rc != 0
    # argparse normalises to our EXIT_USAGE (1).
    assert rc == cli_mod.EXIT_USAGE


def test_resolve_marks_row_approved(
    isolate_audit_log: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``resolve --status accepted`` flips status → approved."""
    p = Proposal(
        skill_name="resolvable_skill",
        source_cells=("cell-A",),
        target_cell_candidates=(),
        domain="rag",
        total_uses=12,
        avg_confidence=0.81,
        std_confidence=0.04,
        confidence=0.81,
        transfer_rationale="resolve me",
        recommended_action="propose",
        observation_window_days=7,
    )
    row_id = record_proposal(p, path=isolate_audit_log)
    rc = cli_mod.main(
        [
            "resolve",
            "--id",
            str(row_id),
            "--status",
            "accepted",
            "--by",
            "human:test",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0, f"stderr={captured.err}"
    payload = json.loads(captured.out.strip().splitlines()[-1])
    assert payload["updated"] is True
    assert payload["new_status"] == "approved"
    # And the row is no longer pending.
    rows = list_pending(isolate_audit_log)
    assert all(r["id"] != row_id for r in rows)
