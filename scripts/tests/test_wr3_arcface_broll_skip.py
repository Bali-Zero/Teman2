"""Identity gate must skip faceless b-roll clips (2026-05-30).

C5a re-render: 11/11 Zantara (A007) shots passed ArcFace, but the gate also ran
on 4 faceless b-roll shots (empty checkpoint desk, empty studio, abstract paths)
whose shots have NO A007 in identity_tokens — those have no Zantara face by design,
so ArcFace cosine is ~0 and the gate hard-failed the whole episode.

The gate must verify identity ONLY on clips whose shot declares the A007 token;
b-roll clips are recorded as skipped, never as failures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr3_arcface_verify as af  # noqa: E402


def _episode(tmp_path: Path, shots: list[dict]) -> Path:
    """Build an episode dir with a shot-pack and matching empty clip files."""
    ep = tmp_path / "ep"
    clips = ep / "clips"
    clips.mkdir(parents=True)
    ep.joinpath("shot-pack.json").write_text(json.dumps({"shots": shots}))
    for i in range(1, len(shots) + 1):
        (clips / f"{i:02d}.mp4").write_bytes(b"\x00\x00\x00\x20ftypisom")
    return ep


def test_select_identity_clips_keeps_only_a007(tmp_path: Path) -> None:
    ep = _episode(tmp_path, [
        {"shot_id": "s001", "identity_tokens": ["A007", "calm"]},      # Zantara
        {"shot_id": "s002", "identity_tokens": ["broll-abstract"]},    # b-roll
        {"shot_id": "s003", "identity_tokens": ["A007"]},              # Zantara
        {"shot_id": "s004", "identity_tokens": []},                    # b-roll
    ])
    identity, broll = af.select_identity_clips(ep / "clips", ep)
    assert sorted(p.name for p in identity) == ["01.mp4", "03.mp4"]
    assert sorted(p.name for p in broll) == ["02.mp4", "04.mp4"]


def test_select_identity_clips_no_shotpack_keeps_all(tmp_path: Path) -> None:
    """No shot-pack → conservative: every clip is treated as identity-bearing."""
    ep = tmp_path / "ep"
    clips = ep / "clips"
    clips.mkdir(parents=True)
    for i in (1, 2):
        (clips / f"{i:02d}.mp4").write_bytes(b"x")
    identity, broll = af.select_identity_clips(clips, ep)
    assert len(identity) == 2 and broll == []


def test_select_identity_clips_all_broll(tmp_path: Path) -> None:
    ep = _episode(tmp_path, [
        {"shot_id": "s001", "identity_tokens": ["broll-abstract"]},
        {"shot_id": "s002", "identity_tokens": []},
    ])
    identity, broll = af.select_identity_clips(ep / "clips", ep)
    assert identity == [] and sorted(p.name for p in broll) == ["01.mp4", "02.mp4"]


def test_verify_clips_dir_skips_broll_no_hardfail(tmp_path: Path, monkeypatch) -> None:
    """Gate runs ArcFace only on A007 clips; faceless b-roll never hard-fails."""
    ep = _episode(tmp_path, [
        {"shot_id": "s001", "identity_tokens": ["A007"]},
        {"shot_id": "s002", "identity_tokens": ["broll-abstract"]},  # would be cosine 0
    ])

    # Force real path off; stub _real_verify to assert it receives ONLY the A007 clip.
    captured = {}

    def fake_real_verify(clips):
        captured["clips"] = [p.name for p in clips]
        return af.IdentityReport(
            overall_cosine_avg=0.9, overall_cosine_min=0.88,
            clips_passed=len(clips), clips_failed=0,
            hard_fail_triggered=False,
            per_clip=[af.ClipIdentity(c, 0.9, 0.88, 5, True) for c in clips],
            mock_mode=False,
        )

    monkeypatch.setattr(af, "_real_verify", fake_real_verify)
    monkeypatch.setattr(af, "MOCK_MODE", False)

    report = af.verify_clips_dir(ep / "clips", ep)
    assert captured["clips"] == ["01.mp4"]          # b-roll 02.mp4 excluded
    assert not report.hard_fail_triggered
    # report on disk records the b-roll as skipped
    disk = json.loads((ep / "identity-report.json").read_text())
    assert disk.get("skipped_broll") == ["02.mp4"]


def test_verify_clips_dir_all_broll_passes_vacuously(tmp_path: Path, monkeypatch) -> None:
    """An episode with zero A007 shots has no identity to verify → no hard-fail."""
    ep = _episode(tmp_path, [
        {"shot_id": "s001", "identity_tokens": ["broll"]},
        {"shot_id": "s002", "identity_tokens": []},
    ])
    monkeypatch.setattr(af, "MOCK_MODE", False)
    # _real_verify must NOT be called when there are no identity clips
    def boom(clips):
        raise AssertionError("_real_verify should not run with zero A007 clips")
    monkeypatch.setattr(af, "_real_verify", boom)

    report = af.verify_clips_dir(ep / "clips", ep)
    assert not report.hard_fail_triggered
    assert report.clips_passed == 0 and report.clips_failed == 0
