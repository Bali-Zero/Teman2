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
from types import SimpleNamespace

import numpy as np
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


def _install_real_verify_fakes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    total_frames: int,
    read_ok: bool,
) -> tuple[Path, dict[str, int]]:
    """Install a deterministic ArcFace/OpenCV harness for one fake clip."""
    anchor_path = tmp_path / "anchor.npy"
    np.save(anchor_path, np.array([1.0, 0.0], dtype=np.float32))
    clip = tmp_path / "01.mp4"
    clip.write_bytes(b"fake-video")
    calls = {"read": 0, "face_get": 0}

    class FakeCapture:
        def get(self, _property):
            return total_frames

        def set(self, _property, _value):
            return True

        def read(self):
            calls["read"] += 1
            return read_ok, object()

        def release(self):
            return None

    fake_cv2 = SimpleNamespace(
        CAP_PROP_FRAME_COUNT=1,
        CAP_PROP_POS_FRAMES=2,
        VideoCapture=lambda _path: FakeCapture(),
    )

    class FakeFaceAnalysis:
        def __init__(self, **_kwargs):
            pass

        def prepare(self, **_kwargs):
            return None

        def get(self, _frame):
            calls["face_get"] += 1
            return [
                SimpleNamespace(normed_embedding=np.array([0.8, 0.6], dtype=np.float32))
            ]

    fake_insightface = SimpleNamespace(
        app=SimpleNamespace(FaceAnalysis=FakeFaceAnalysis)
    )
    monkeypatch.setattr(af, "ANCHOR_EMBEDDING_PATH", anchor_path)
    monkeypatch.setattr(
        af,
        "_try_import_insightface",
        lambda: (fake_insightface, fake_cv2, np),
    )
    return clip, calls


def test_select_identity_clips_keeps_only_a007(tmp_path: Path) -> None:
    ep = _episode(
        tmp_path,
        [
            {"shot_id": "s001", "identity_tokens": ["A007", "calm"]},  # Zantara
            {"shot_id": "s002", "identity_tokens": ["broll-abstract"]},  # b-roll
            {"shot_id": "s003", "identity_tokens": ["A007"]},  # Zantara
            {"shot_id": "s004", "identity_tokens": []},  # b-roll
        ],
    )
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
    ep = _episode(
        tmp_path,
        [
            {"shot_id": "s001", "identity_tokens": ["broll-abstract"]},
            {"shot_id": "s002", "identity_tokens": []},
        ],
    )
    identity, broll = af.select_identity_clips(ep / "clips", ep)
    assert identity == [] and sorted(p.name for p in broll) == ["01.mp4", "02.mp4"]


def test_verify_clips_dir_skips_broll_no_hardfail(tmp_path: Path, monkeypatch) -> None:
    """Gate runs ArcFace only on A007 clips; faceless b-roll never hard-fails."""
    ep = _episode(
        tmp_path,
        [
            {"shot_id": "s001", "identity_tokens": ["A007"]},
            {
                "shot_id": "s002",
                "identity_tokens": ["broll-abstract"],
            },  # would be cosine 0
        ],
    )

    # Force real path off; stub _real_verify to assert it receives ONLY the A007 clip.
    captured = {}

    def fake_real_verify(clips):
        captured["clips"] = [p.name for p in clips]
        return af.IdentityReport(
            overall_cosine_avg=0.9,
            overall_cosine_min=0.88,
            clips_passed=len(clips),
            clips_failed=0,
            hard_fail_triggered=False,
            per_clip=[af.ClipIdentity(c, 0.9, 0.88, 5, True) for c in clips],
            mock_mode=False,
        )

    monkeypatch.setattr(af, "_real_verify", fake_real_verify)
    monkeypatch.setattr(af, "MOCK_MODE", False)

    report = af.verify_clips_dir(ep / "clips", ep)
    assert captured["clips"] == ["01.mp4"]  # b-roll 02.mp4 excluded
    assert not report.hard_fail_triggered
    # report on disk records the b-roll as skipped
    disk = json.loads((ep / "identity-report.json").read_text())
    assert disk.get("skipped_broll") == ["02.mp4"]


def test_verify_clips_dir_all_broll_passes_vacuously(
    tmp_path: Path, monkeypatch
) -> None:
    """An episode with zero A007 shots has no identity to verify → no hard-fail."""
    ep = _episode(
        tmp_path,
        [
            {"shot_id": "s001", "identity_tokens": ["broll"]},
            {"shot_id": "s002", "identity_tokens": []},
        ],
    )
    monkeypatch.setattr(af, "MOCK_MODE", False)

    # _real_verify must NOT be called when there are no identity clips
    def boom(clips):
        raise AssertionError("_real_verify should not run with zero A007 clips")

    monkeypatch.setattr(af, "_real_verify", boom)

    report = af.verify_clips_dir(ep / "clips", ep)
    assert not report.hard_fail_triggered
    assert report.clips_passed == 0 and report.clips_failed == 0


def test_real_verify_reports_the_actual_minimum_for_passing_faces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid clip must not inherit a synthetic zero overall minimum."""
    clip, calls = _install_real_verify_fakes(
        tmp_path,
        monkeypatch,
        total_frames=5,
        read_ok=True,
    )

    report = af._real_verify([clip])

    assert report.hard_fail_triggered is False
    assert report.overall_cosine_min == pytest.approx(0.8)
    assert report.per_clip[0].cosine_min == pytest.approx(0.8)
    assert calls == {
        "read": af.SAMPLE_FRAMES_PER_CLIP,
        "face_get": af.SAMPLE_FRAMES_PER_CLIP,
    }


def test_real_verify_zero_frame_clip_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unreadable MP4 must be represented as a failed clip, never omitted."""
    clip, calls = _install_real_verify_fakes(
        tmp_path,
        monkeypatch,
        total_frames=0,
        read_ok=False,
    )

    report = af._real_verify([clip])

    assert calls == {"read": 0, "face_get": 0}
    assert report.overall_cosine_avg == 0.0
    assert report.overall_cosine_min == 0.0
    assert report.clips_passed == 0
    assert report.clips_failed == 1
    assert report.hard_fail_triggered is True
    assert report.per_clip == [af.ClipIdentity(clip, 0.0, 0.0, 0, False)]


def test_real_verify_all_frame_reads_failed_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A declared frame count is insufficient when every sampled read fails."""
    clip, calls = _install_real_verify_fakes(
        tmp_path,
        monkeypatch,
        total_frames=5,
        read_ok=False,
    )

    report = af._real_verify([clip])

    assert calls == {"read": af.SAMPLE_FRAMES_PER_CLIP, "face_get": 0}
    assert report.overall_cosine_avg == 0.0
    assert report.overall_cosine_min == 0.0
    assert report.clips_passed == 0
    assert report.clips_failed == 1
    assert report.hard_fail_triggered is True
    assert report.per_clip == [af.ClipIdentity(clip, 0.0, 0.0, 0, False)]
