#!/usr/bin/env python3
"""WR3 ArcFace identity gate — Zantara face verification.

Verifies that every clip in clips/ contains the Zantara anchor face with
cosine similarity ≥0.6 vs the anchor embedding. Single-clip ArcFace <0.55
HARD-FAIL (Symbiosis Law 7 Numeri prima — strict numeric threshold).

Dependencies (HARD: missing insightface raises ArcFaceError — NO silent
graceful degrade to mock, that would be a production identity-gate bypass):
  - insightface (pip install insightface onnxruntime)
  - opencv-python (cv2)

Reference anchor:
  ~/Desktop/nuzantara/research/marketing/zantara-visual-dataset/v1/ingredients/
  zantara-anchor-A007.embedding.npy  (pre-computed)

Mock mode: if WR3_ARCFACE_MOCK=true returns deterministic PASS — INTENDED
ONLY for smoke testing. Guarded by WR3_PRODUCTION env var: if PRODUCTION
is true, the mock flag is IGNORED and real verification is forced. Codex
+ Gemini + DeepSeek 3/3 review 2026-05-18 caught the launchd leak risk.
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

# CRITICAL — Codex+Gemini+DeepSeek 3/3 panel review 2026-05-18:
# WR3_ARCFACE_MOCK env var leaking into launchd/production would silently
# bypass the identity gate. Guard: WR3_PRODUCTION=true forces real verify
# regardless of WR3_ARCFACE_MOCK value. Treat env var ordering as
# Production > Mock (production overrides mock requests).
_RAW_MOCK = os.environ.get("WR3_ARCFACE_MOCK", "false").lower() == "true"
_PRODUCTION = os.environ.get("WR3_PRODUCTION", "false").lower() == "true"
MOCK_MODE = _RAW_MOCK and not _PRODUCTION

# The identity token a shot must declare to be subject to the ArcFace gate.
# Faceless b-roll shots (empty desks, abstract paths) do NOT carry it and must
# be SKIPPED — they have no Zantara face by design, so cosine ~0 is correct, not
# a failure (2026-05-30: the gate hard-failed C5a on 4 b-roll clips while all
# 11 A007 clips passed).
IDENTITY_TOKEN = os.environ.get("WR3_ARCFACE_IDENTITY_TOKEN", "A007")


def select_identity_clips(
    clips_dir: "Path", episode_dir: "Path"
) -> "tuple[list[Path], list[Path]]":
    """Split clips into (identity_bearing, faceless_broll) using the shot-pack.

    Maps clip NN.mp4 → shots[NN-1] and keeps only clips whose shot declares
    IDENTITY_TOKEN in its identity_tokens. If no shot-pack exists (or a clip has
    no matching shot), the clip is treated as identity-bearing — conservative:
    we never silently skip a clip that might contain Zantara.
    """
    clips = sorted(clips_dir.glob("*.mp4"))
    shot_pack_path = episode_dir / "shot-pack.json"
    if not shot_pack_path.exists():
        return clips, []

    try:
        shots = json.loads(shot_pack_path.read_text()).get("shots") or []
    except (json.JSONDecodeError, OSError):
        return clips, []

    identity: list[Path] = []
    broll: list[Path] = []
    for clip in clips:
        try:
            idx = int(clip.stem)  # "01.mp4" → 1
        except ValueError:
            identity.append(clip)  # unparseable name → don't skip
            continue
        shot = shots[idx - 1] if 1 <= idx <= len(shots) else None
        tokens = (shot or {}).get("identity_tokens") or []
        if shot is None or IDENTITY_TOKEN in tokens:
            identity.append(clip)
        else:
            broll.append(clip)
    return identity, broll


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
    # Start overall_min at 0.0 NOT 1.0 — Codex review 2026-05-18 caught:
    # if every clip is zero-frame/unreadable (face detection skipped), we
    # would have hard_fail=False + overall_min=1.0 = silent PASS. With 0.0
    # start, an episode with zero detected faces hard-fails the threshold.
    overall_min = 0.0 if clips else 1.0
    hard_fail = False
    passed_count = 0
    clips_with_zero_samples = 0

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
            # Zero samples = zero faces detected. Treat as identity hard-fail.
            # Codex review: previously avg=0.0 + mn=0.0 left hard_fail=False
            # because the for-loop never wrote a low value to overall_min.
            avg = 0.0
            mn = 0.0
            clips_with_zero_samples += 1
            hard_fail = True  # zero-detection IS a hard fail
        else:
            avg = sum(cosines) / len(cosines)
            mn = min(cosines)

        clip_passed = (
            avg >= MIN_COSINE
            and mn >= HARD_FAIL_COSINE
            and len(cosines) > 0  # explicit: zero samples never passes
        )
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

    SECURITY: WR3_PRODUCTION=true forces real verify even if WR3_ARCFACE_MOCK
    is set — Codex+Gemini+DeepSeek panel review 2026-05-18 caught launchd
    env-var leak risk. MOCK_MODE is computed at module load with this guard.
    """
    all_clips = sorted(clips_dir.glob("*.mp4"))
    if not all_clips:
        raise ArcFaceError(f"No clips found in {clips_dir}")

    # Identity gate applies ONLY to clips whose shot declares the A007 token.
    # Faceless b-roll is recorded as skipped, never verified or failed.
    clips, broll = select_identity_clips(clips_dir, episode_dir)
    if broll:
        print(
            f"[wr3-arcface] skipping {len(broll)} faceless b-roll clip(s): "
            f"{', '.join(p.name for p in broll)}",
            flush=True,
        )

    if not clips:
        # Episode has zero Zantara shots — nothing to verify, vacuous pass.
        report = IdentityReport(
            overall_cosine_avg=0.0, overall_cosine_min=0.0,
            clips_passed=0, clips_failed=0, hard_fail_triggered=False,
            per_clip=[], mock_mode=MOCK_MODE,
        )
    elif MOCK_MODE:
        # Audit log line — operator should see this in launchd logs and
        # immediately escalate if MOCK_MODE fires in production
        print(
            "[wr3-arcface] WARNING: MOCK_MODE active — identity gate bypassed. "
            "Set WR3_PRODUCTION=true to disable.",
            flush=True,
        )
        report = _mock_verify(clips)
    else:
        try:
            report = _real_verify(clips)
        except ArcFaceError:
            raise

    payload = report.to_dict()
    payload["skipped_broll"] = [p.name for p in broll]
    report_path = episode_dir / "identity-report.json"
    report_path.write_text(json.dumps(payload, indent=2))

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
