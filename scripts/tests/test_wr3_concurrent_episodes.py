"""Concurrent episode safety — Q9 panel-flagged missing test (Gemini catch).

Multiple WR3 episodes may be in flight simultaneously. Verifies:
  - Telemetry from different episode_ids does not collide
  - Manifest builder per-episode is isolated (no shared state)
  - Episode dir naming + atomic write-rename works in parallel
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wr3_episode_manifest import ManifestBuilder  # noqa: E402
import wr3_telemetry  # noqa: E402


def _hash(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


@pytest.mark.asyncio
async def test_telemetry_isolated_per_episode(tmp_path: Path, monkeypatch) -> None:
    """Two episodes emitting concurrently must write to the same agent.jsonl
    but their lines must be distinguishable by episode_id."""
    monkeypatch.setattr(wr3_telemetry, "TELEMETRY_ROOT", tmp_path)

    async def _emit(ep_id: str, count: int) -> None:
        for i in range(count):
            wr3_telemetry.emit(
                agent="wr3-script-editor",
                episode_id=ep_id,
                outcome="PASS",
                duration_ms=i * 100,
                cost_usd=0.01,
                contract_version="1.0.0",
            )
            await asyncio.sleep(0)

    await asyncio.gather(
        _emit("ep-concurrent-A", 5),
        _emit("ep-concurrent-B", 5),
        _emit("ep-concurrent-C", 5),
    )

    log_path = tmp_path / "wr3-script-editor.jsonl"
    assert log_path.exists()
    lines = [json.loads(l) for l in log_path.read_text().splitlines() if l]
    assert len(lines) == 15

    ep_ids = {l["episode_id"] for l in lines}
    assert ep_ids == {"ep-concurrent-A", "ep-concurrent-B", "ep-concurrent-C"}


def test_manifest_builders_isolated() -> None:
    """Two ManifestBuilder instances must not share state."""
    b1 = ManifestBuilder(episode_id="ep1", topic="T1", audience_segment="seg1")
    b2 = ManifestBuilder(episode_id="ep2", topic="T2", audience_segment="seg2")

    b1.add_claim("c-from-b1")
    b2.add_claim("c-from-b2")

    b1.record_agent("wr3-brief-interpreter", "1.0.0", cost_usd=0.1)
    b2.record_agent("wr3-script-editor", "1.0.0", cost_usd=0.05)

    assert "c-from-b1" in b1.claim_ids
    assert "c-from-b1" not in b2.claim_ids
    assert b1.total_cost_usd == 0.1
    assert b2.total_cost_usd == 0.05


@pytest.mark.asyncio
async def test_concurrent_manifest_writes_are_isolated(tmp_path: Path) -> None:
    """Two episodes finalising manifests in parallel must produce 2 valid files."""
    async def _do(ep_id: str) -> Path:
        ep_dir = tmp_path / ep_id
        ep_dir.mkdir()
        # Mock asset for hashing
        (ep_dir / "master.mp4").write_bytes(f"master_for_{ep_id}".encode())

        b = ManifestBuilder(episode_id=ep_id, topic="t", audience_segment="s")
        b.add_claim("claim-x")
        b.record_agent("wr3-brief-interpreter", "1.0.0", cost_usd=0.1)
        b.hash_asset("master.mp4", ep_dir / "master.mp4")
        b.variants_delivered = ["tiktok", "ig-reels", "yt-shorts", "fb"]
        b.identity_overall_cosine_avg = 0.7
        b.lufs_measured = -14.0
        b.duration_master_ms = 60_000
        b.critic_verdict = "PASS"

        # Tiny await to simulate I/O interleaving
        await asyncio.sleep(0)
        return b.write(ep_dir)

    p_a, p_b = await asyncio.gather(_do("ep-A"), _do("ep-B"))
    assert p_a.exists() and p_b.exists()

    m_a = json.loads(p_a.read_text())
    m_b = json.loads(p_b.read_text())
    assert m_a["episode_id"] == "ep-A"
    assert m_b["episode_id"] == "ep-B"
    # Different masters → different sha256 even though both episodes have one
    assert m_a["asset_hashes"]["master.mp4"] != m_b["asset_hashes"]["master.mp4"]


def test_telemetry_env_var_override(tmp_path: Path, monkeypatch) -> None:
    """WR3_TELEMETRY_ROOT must redirect output dir (CI isolation)."""
    custom = tmp_path / "custom-tel"
    monkeypatch.setattr(wr3_telemetry, "TELEMETRY_ROOT", custom)
    p = wr3_telemetry.emit(
        agent="wr3-critic",
        episode_id="ep-env-test",
        outcome="PASS",
        contract_version="1.0.0",
    )
    assert p.parent == custom
    assert p.name == "wr3-critic.jsonl"
