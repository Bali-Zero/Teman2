#!/usr/bin/env python3
"""WR3 ArcFace identity gate — Zantara face verification.

Verifies that every clip in clips/ contains the Zantara anchor face with
cosine similarity ≥0.6 vs the anchor embedding. Single-clip ArcFace <0.55
HARD-FAIL (Symbiosis Law 7 Numeri prima — strict numeric threshold).

Dependencies (lazy import — stub returns simulated PASS if unavailable):
  - insightface (pip install insightface onnxruntime)
  - opencv-python (cv2)

Reference anchor:
  ~/Desktop/nuzantara/research/marketing/zantara-visual-dataset/v1/ingredients/
  zantara-anchor-A007.embedding.npy  (pre-computed)

Mock mode: if WR3_ARCFACE_MOCK=true OR insightface unavailable, returns
deterministic PASS for smoke testing.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

ANCHOR_EMBEDDING_PATH = Path(os.environ.get(
    "WR3_ARCFACE_ANCHOR",
    str(Path.home() / "Desktop/nuzantara/research/marketing/zantara-visual-dataset/v1/ingredients/zantara-anchor-A007.embedding.npy"),
))
MIN_COSINE = float(os.environ.get("WR3_ARCFACE_MIN_COSINE", "0.6"))
HARD_FAIL_COSINE = float(os.environ.get("WR3_ARCFACE_HARD_FAIL", "0.55"))
SAMPLE_FRAMES_PER_CLIP = int(os.environ.get("WR3_ARCFACE_SAMPLES", "5"))
MOCK_MODE = os.environ.get("WR3_ARCFACE_MOCK", "false").lower() == "true"


class ArcFaceError(Exception):
    """Base for ArcFace-layer errors."""


class IdentityHardFailError(ArcFaceError):
    """At least one clip below HARD_FAIL_COSINE (<0.55). Episode HALTS."""


@dataclass(frozen=True)
class ClipIdentity:
    clip_path: Path
    cosine_avg: float
    cosine_min: float
    sample_count: int
    passed: bool


@dataclass(frozen=True)
class IdentityReport:
    overall_cosine_avg: float
    overall_cosine_min: float
    clips_passed: int
    clips_failed: int
    hard_fail_triggered: bool
    per_clip: list[ClipIdentity]
    mock_mode: bool

    def to_dict(self) -> dict:
        return {
            "overall_cosine_avg": self.overall_cosine_avg,
            "overall_cosine_min": self.overall_cosine_min,
            "clips_passed": self.clips_passed,
            "clips_failed": self.clips_failed,
            "hard_fail_triggered": self.hard_fail_triggered,
            "min_cosine_threshold": MIN_COSINE,
            "hard_fail_threshold": HARD_FAIL_COSINE,
            "samples_per_clip": SAMPLE_FRAMES_PER_CLIP,
            "mock_mode": self.mock_mode,
            "per_clip": [
                {
                    "clip": str(c.clip_path.name),
                    "cosine_avg": c.cosine_avg,
                    "cosine_min": c.cosine_min,
                    "samples": c.sample_count,
                    "passed": c.passed,
                }
                for c in self.per_clip
            ],
        }


def _try_import_insightface():
    try:
        import insightface  # type: ignore
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        return insightface, cv2, np
    except ImportError:
        return None, None, None


def _mock_verify(clips: list[Path]) -> IdentityReport:
    per_clip = [
        ClipIdentity(
            clip_path=c,
            cosine_avg=0.72,
            cosine_min=0.65,
            sample_count=SAMPLE_FRAMES_PER_CLIP,
            passed=True,
        )
        for c in clips
    ]
    return IdentityReport(
        overall_cosine_avg=0.72,
        overall_cosine_min=0.65,
        clips_passed=len(clips),
        clips_failed=0,
        hard_fail_triggered=False,
        per_clip=per_clip,
        mock_mode=True,
    )


def _real_verify(clips: list[Path]) -> IdentityReport:
    insightface, cv2, np = _try_import_insightface()
    if insightface is None:
        raise ArcFaceError(
            "insightface not installed. pip install insightface onnxruntime opencv-python. "
            "Or set WR3_ARCFACE_MOCK=true for smoke testing."
        )

    if not ANCHOR_EMBEDDING_PATH.exists():
        raise ArcFaceError(
            f"Anchor embedding not found at {ANCHOR_EMBEDDING_PATH}. "
            "Build via tools/build-zantara-anchor.py (S7.5 follow-up)."
        )

    anchor = np.load(ANCHOR_EMBEDDING_PATH)
    app = insightface.app.FaceAnalysis(name="buffalo_l")
    app.prepare(ctx_id=0, det_size=(640, 640))

    per_clip: list[ClipIdentity] = []
    overall_sum = 0.0
    overall_min = 1.0
    hard_fail = False
    passed_count = 0

    for clip_path in clips:
        cap = cv2.VideoCapture(str(clip_path))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            cap.release()
            continue
        step = max(1, total // SAMPLE_FRAMES_PER_CLIP)
        cosines: list[float] = []

        for i in range(SAMPLE_FRAMES_PER_CLIP):
            frame_idx = min(i * step, total - 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = cap.read()
            if not ok:
                continue
            faces = app.get(frame)
            if not faces:
                continue
            emb = faces[0].normed_embedding
            cos = float(np.dot(anchor / np.linalg.norm(anchor), emb))
            cosines.append(cos)
        cap.release()

        if not cosines:
            avg = 0.0
            mn = 0.0
        else:
            avg = sum(cosines) / len(cosines)
            mn = min(cosines)

        clip_passed = avg >= MIN_COSINE and mn >= HARD_FAIL_COSINE
        if mn < HARD_FAIL_COSINE:
            hard_fail = True

        per_clip.append(ClipIdentity(
            clip_path=clip_path,
            cosine_avg=avg,
            cosine_min=mn,
            sample_count=len(cosines),
            passed=clip_passed,
        ))
        overall_sum += avg
        overall_min = min(overall_min, mn)
        if clip_passed:
            passed_count += 1

    overall_avg = overall_sum / max(1, len(per_clip))

    return IdentityReport(
        overall_cosine_avg=overall_avg,
        overall_cosine_min=overall_min,
        clips_passed=passed_count,
        clips_failed=len(per_clip) - passed_count,
        hard_fail_triggered=hard_fail,
        per_clip=per_clip,
        mock_mode=False,
    )


def verify_clips_dir(clips_dir: Path, episode_dir: Path) -> IdentityReport:
    """Verify all clips and write identity-report.json.

    Raises IdentityHardFailError if any clip cosine_min < HARD_FAIL_COSINE.
    """
    clips = sorted(clips_dir.glob("*.mp4"))
    if not clips:
        raise ArcFaceError(f"No clips found in {clips_dir}")

    if MOCK_MODE:
        report = _mock_verify(clips)
    else:
        try:
            report = _real_verify(clips)
        except ArcFaceError:
            raise

    report_path = episode_dir / "identity-report.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2))

    if report.hard_fail_triggered:
        raise IdentityHardFailError(
            f"identity hard-fail: overall_min={report.overall_cosine_min:.3f} "
            f"< threshold {HARD_FAIL_COSINE} — episode HALTED"
        )

    return report


if __name__ == "__main__":
    import sys
    print(f"min_cosine={MIN_COSINE} hard_fail={HARD_FAIL_COSINE} samples={SAMPLE_FRAMES_PER_CLIP}", file=sys.stderr)
    print(f"anchor={ANCHOR_EMBEDDING_PATH} mock={MOCK_MODE}", file=sys.stderr)
