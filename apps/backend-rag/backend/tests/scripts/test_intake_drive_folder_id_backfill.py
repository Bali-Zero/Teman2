"""Unit tests for scripts/intake_drive_folder_id_backfill.py (pure parts only).

No Postgres, no Drive, no HTTP: covers the load-bearing invariants of the
session-as-reviewer backfill — the never-overwrite live guard, bijectivity
enforcement, PII-free audit rows, SELECT-only evidence SQL, and the Tier-A
constants. The network phases run on the Pro at rollout (dry-run first).
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

# test file: apps/backend-rag/backend/tests/scripts/<this>
# parents: [0]=scripts [1]=tests [2]=backend [3]=backend-rag [4]=apps [5]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "intake_drive_folder_id_backfill.py"


def _load():
    spec = importlib.util.spec_from_file_location("gdfb_under_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    # dataclass field-type resolution needs the module registered in
    # sys.modules BEFORE exec (dataclasses._is_type does sys.modules.get).
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_script_help_runs_and_defaults_to_dry_run() -> None:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(_REPO_ROOT / "apps" / "backend-rag"),
    }
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "--apply" in result.stdout  # writes are opt-in, dry-run is the default


def test_evidence_sql_is_select_only() -> None:
    mod = _load()
    for sql in (mod.CANDIDATE_SQL, mod.EXISTING_MAPPING_SQL):
        upper = sql.upper()
        # word-boundary match, not substring: "deleted_at" must not trip DELETE
        # (guard-over-match, cicatrix family #3)
        for verb in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "ALTER"):
            assert not re.search(
                rf"\b{verb}\b", upper
            ), f"evidence SQL must be read-only, found {verb}"


def test_tier_a_constants_tripwire() -> None:
    """Loosening the review bar must be a deliberate, reviewed change."""
    mod = _load()
    assert mod.PIPELINE_VERSION == "v2.2-m227-folder"
    assert mod.SIM_THRESHOLD == 0.85
    assert mod.SAMPLE_FILES_PER_CLIENT >= 2


def test_live_guard_never_overwrites() -> None:
    mod = _load()
    assert mod._live_guard_decision("existing-folder", "new-folder") == (
        "skip",
        "already_set_live",
    )
    assert mod._live_guard_decision("same-id", "same-id") == ("skip", "already_correct")
    assert mod._live_guard_decision(None, "new-folder") is None
    assert mod._live_guard_decision("", "new-folder") is None


def _plan(mod, client_id: int, folder_id: str | None):
    plan = mod.ClientPlan(
        client_id=client_id,
        mv_norm="in memory only",
        max_sim=0.99,
        has_exact=True,
        n_docs=3,
        sample_file_ids=["f1", "f2"],
        raw_variants=["RAW NAME (KITAS)"],
    )
    plan.folder_id = folder_id
    return plan


def test_bijectivity_multi_claimant_conflict() -> None:
    mod = _load()
    a = _plan(mod, 1, "folder-X")
    b = _plan(mod, 2, "folder-X")
    mod._enforce_bijectivity([a, b], {})
    assert a.decision == "skip" and a.detail == "folder_conflict_multi_client"
    assert b.decision == "skip" and b.detail == "folder_conflict_multi_client"


def test_bijectivity_snapshot_owner_conflict() -> None:
    mod = _load()
    stolen = _plan(mod, 1, "folder-X")
    legit = _plan(mod, 2, "folder-Y")
    mod._enforce_bijectivity([stolen, legit], {"folder-X": 99, "folder-Y": 2})
    assert stolen.decision == "skip" and stolen.detail == "folder_taken_by_99"
    assert legit.decision == "pending"  # snapshot owner == claimant: fine


def test_audit_row_is_pii_free() -> None:
    """Law 2: names live in memory only — the audit log gets ids and numbers."""
    mod = _load()
    plan = _plan(mod, 7, "folder-Z")
    row = plan.audit_row()
    assert "mv_norm" not in row and "raw_variants" not in row
    serialized = str(row).lower()
    assert "in memory only" not in serialized
    assert "raw name" not in serialized
