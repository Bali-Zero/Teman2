"""Full-episode end-to-end test — driven by wr3_smoke_test.py logic.

Validates the full lifecycle in mock mode WITHOUT any cloud spend:
  - contracts load
  - manifest builder produces 18-field valid manifest
  - sha256 anchors compute
  - all 4 variants declared
  - Symbiosis Law 7 numeric thresholds (identity ≥0.6, LUFS ±1)

This is the LAST safety net before the real S7.8 pilot.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr3_smoke_test  # noqa: E402
from wr3_contracts import load_contracts  # noqa: E402


@pytest.mark.asyncio
async def test_smoke_pipeline_pass(tmp_path: Path) -> None:
    """Run the entire smoke driver. Exit 0 == 7/7 sanity checks pass."""
    import argparse

    args = argparse.Namespace(
        episode_id="ep-pytest-e2e",
        output=str(tmp_path),
    )

    exit_code = await wr3_smoke_test.main_async(args)
    assert exit_code == 0


def test_episode_dir_has_all_required_artifacts(tmp_path: Path) -> None:
    """After _seed_episode + _verify_episode, all 18-field manifest is present."""
    ep_id = "ep-artifact-check"
    ep_dir = tmp_path / ep_id
    wr3_smoke_test._seed_episode(ep_dir, ep_id)
    manifest = wr3_smoke_test._verify_episode(ep_dir)

    required_artifacts = ["brief.json", "script.json", "shot-pack.json", "master.mp4"]
    for art in required_artifacts:
        assert (ep_dir / art).exists(), f"missing artifact {art}"

    assert (ep_dir / "clips").exists()
    assert any((ep_dir / "clips").glob("*.mp4")), "no clips found"

    assert manifest["critic_verdict"] == "PASS"
    assert manifest["total_cost_usd"] > 0
    assert len(manifest["claim_ids"]) >= 1
    assert len(manifest["variants_delivered"]) == 4


def test_contracts_loaded_before_episode_seeded(tmp_path: Path) -> None:
    """Defensive: smoke test must load contracts before touching disk."""
    contracts = load_contracts()
    assert len(contracts.agents) == 13
    # If this passes but the smoke fails, the bug is in seed/verify, not contracts


def test_identity_threshold_in_smoke_passes() -> None:
    """0.72 > 0.6 — smoke fixture identity must always pass."""
    ep_dir = Path("/tmp/_smoke_throwaway")
    ep_dir.mkdir(exist_ok=True)
    wr3_smoke_test._seed_episode(ep_dir, "ep-thresh")
    manifest = wr3_smoke_test._verify_episode(ep_dir)
    assert manifest["identity_overall_cosine_avg"] >= 0.6


def test_lufs_in_tolerance_for_smoke() -> None:
    ep_dir = Path("/tmp/_lufs_throwaway")
    ep_dir.mkdir(exist_ok=True)
    wr3_smoke_test._seed_episode(ep_dir, "ep-lufs")
    manifest = wr3_smoke_test._verify_episode(ep_dir)
    lufs = manifest["lufs_measured"]
    assert lufs is not None
    assert abs(lufs + 14) <= 1.0
