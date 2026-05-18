"""Tests for manifest idempotence + sha256 consistency.

Symbiosis Law 8 — manifest sha256 anchors must be deterministic across runs
on the same input. Re-running the manifest builder on the same artifacts must
produce identical asset_hashes.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wr3_episode_manifest import (  # noqa: E402
    MANDATORY_FIELDS,
    ManifestBuilder,
    ManifestValidationError,
    load_manifest,
    validate_manifest,
)


@pytest.fixture
def fake_episode(tmp_path: Path) -> Path:
    ep = tmp_path / "ep-test"
    (ep / "clips").mkdir(parents=True)
    (ep / "audio").mkdir()
    (ep / "master.mp4").write_bytes(b"master_bytes_deterministic_for_tests")
    (ep / "audio" / "vo.wav").write_bytes(b"vo_bytes")
    for i in range(1, 4):
        (ep / "clips" / f"{i:02d}.mp4").write_bytes(f"clip_{i}_bytes".encode())
    return ep


def _build(ep_id: str, ep_dir: Path) -> dict:
    b = ManifestBuilder(
        episode_id=ep_id,
        topic="t",
        audience_segment="seg",
    )
    b.add_claim("c1")
    b.record_agent("wr3-brief-interpreter", "1.0.0", cost_usd=0.1)
    b.hash_asset("master.mp4", ep_dir / "master.mp4")
    b.hash_asset("vo.wav", ep_dir / "audio" / "vo.wav")
    b.variants_delivered = ["tiktok", "ig-reels", "yt-shorts", "fb"]
    b.identity_overall_cosine_avg = 0.7
    b.lufs_measured = -14.0
    b.duration_master_ms = 60_000
    b.critic_verdict = "PASS"
    return b.finalize()


def test_sha256_deterministic(fake_episode: Path) -> None:
    m1 = _build("ep1", fake_episode)
    m2 = _build("ep1", fake_episode)
    assert m1["asset_hashes"] == m2["asset_hashes"]


def test_sha256_changes_on_content_change(fake_episode: Path) -> None:
    m1 = _build("ep1", fake_episode)
    (fake_episode / "master.mp4").write_bytes(b"different_content")
    m2 = _build("ep1", fake_episode)
    assert m1["asset_hashes"]["master.mp4"] != m2["asset_hashes"]["master.mp4"]


def test_validate_manifest_rejects_missing_field(fake_episode: Path) -> None:
    m = _build("ep1", fake_episode)
    del m["claim_ids"]
    with pytest.raises(ManifestValidationError, match="claim_ids"):
        validate_manifest(m)


def test_validate_manifest_rejects_empty_claim_ids(fake_episode: Path) -> None:
    m = _build("ep1", fake_episode)
    m["claim_ids"] = []
    with pytest.raises(ManifestValidationError, match="empty"):
        validate_manifest(m)


def test_validate_manifest_rejects_invalid_verdict(fake_episode: Path) -> None:
    m = _build("ep1", fake_episode)
    m["critic_verdict"] = "MAYBE"
    with pytest.raises(ManifestValidationError, match="critic_verdict"):
        validate_manifest(m)


def test_load_manifest_roundtrip(fake_episode: Path, tmp_path: Path) -> None:
    m1 = _build("ep1", fake_episode)
    out = tmp_path / "episode_manifest.json"
    out.write_text(json.dumps(m1))
    m2 = load_manifest(out)
    assert m1 == m2


def test_eighteen_mandatory_fields(fake_episode: Path) -> None:
    m = _build("ep1", fake_episode)
    for field in MANDATORY_FIELDS:
        assert field in m, f"missing mandatory field {field!r}"


def test_record_agent_accumulates_cost(fake_episode: Path) -> None:
    b = ManifestBuilder(episode_id="x", topic="t", audience_segment="s")
    b.record_agent("wr3-brief-interpreter", "1.0.0", cost_usd=0.10)
    b.record_agent("wr3-script-editor", "1.0.0", cost_usd=0.05)
    b.record_agent("wr3-critic", "1.0.0", cost_usd=0.50)
    b.add_claim("c")
    b.variants_delivered = ["tiktok", "ig-reels", "yt-shorts", "fb"]
    b.identity_overall_cosine_avg = 0.7
    b.lufs_measured = -14.0
    b.critic_verdict = "PASS"
    m = b.finalize()
    assert m["total_cost_usd"] == 0.65


def test_hash_asset_missing_returns_marker(fake_episode: Path) -> None:
    b = ManifestBuilder(episode_id="x", topic="t", audience_segment="s")
    digest = b.hash_asset("nonexistent", fake_episode / "missing.mp4")
    assert digest == "MISSING"
    assert b.asset_hashes["nonexistent"] == "MISSING"
