#!/usr/bin/env python3
"""Fail-closed ArcFace identity gate for one WR3 scene-start still.

This verifier is intentionally narrower than ``wr3_arcface_verify.py``: it
accepts one raster image, requires exactly one detected face, and has no mock
mode.  It is suitable for checking a generated portrait start frame before a
Flow video submission is allowed to spend credits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence


ANCHOR_EMBEDDING_PATH = Path(
    os.environ.get(
        "WR3_ARCFACE_ANCHOR",
        str(
            Path.home()
            / "nuzantara/research/marketing/zantara-visual-dataset/v1/ingredients/"
            "zantara-anchor-A007.embedding.npy"
        ),
    )
)
PASS_COSINE = 0.600
HARD_FAIL_COSINE = 0.550

IdentityStatus = Literal["PASS", "REJECT", "HARD_FAIL"]


@dataclass
class SceneStartIdentityReport:
    """Machine-readable result for the single-still identity gate."""

    image_path: str
    embedding_path: str
    image_sha256: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    embedding_sha256: str | None = None
    face_count: int | None = None
    detector_confidences: list[float | None] = field(default_factory=list)
    cosine: float | None = None
    status: IdentityStatus = "HARD_FAIL"
    reason: str = "verification did not complete"

    def to_dict(self) -> dict[str, object]:
        """Return the stable JSON representation consumed by the gate."""

        return {
            "schema_version": "1.0",
            "image": {
                "path": self.image_path,
                "sha256": self.image_sha256,
                "width": self.image_width,
                "height": self.image_height,
            },
            "embedding": {
                "path": self.embedding_path,
                "sha256": self.embedding_sha256,
            },
            "model": {
                "name": "buffalo_l",
                "det_size": [640, 640],
            },
            "face_count": self.face_count,
            "detector_confidences": self.detector_confidences,
            "cosine": self.cosine,
            "thresholds": {
                "pass": PASS_COSINE,
                "hard_fail": HARD_FAIL_COSINE,
            },
            "status": self.status,
            "reason": self.reason,
            "mock": False,
        }


def _try_import_insightface() -> tuple[Any | None, Any | None, Any | None]:
    """Import the real ArcFace runtime, returning sentinels on any miss."""

    try:
        import cv2  # type: ignore
        import insightface  # type: ignore
        import numpy as np  # type: ignore
    except (ImportError, OSError):
        return None, None, None
    return insightface, cv2, np


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hard_fail(
    report: SceneStartIdentityReport,
    reason: str,
) -> SceneStartIdentityReport:
    report.status = "HARD_FAIL"
    report.reason = reason
    return report


def _confidence(face: object, np: Any) -> float | None:
    raw = getattr(face, "det_score", None)
    if raw is None:
        return None
    try:
        score = float(raw)
    except (TypeError, ValueError):
        return None
    return score if bool(np.isfinite(score)) else None


def verify_scene_start_identity(
    image_path: Path,
    embedding_path: Path = ANCHOR_EMBEDDING_PATH,
) -> SceneStartIdentityReport:
    """Verify exactly one face in ``image_path`` against the A007 embedding.

    Expected identity mismatches are returned as ``REJECT``/``HARD_FAIL``.
    Runtime, I/O, image-decoding, face-count, and embedding failures also return
    ``HARD_FAIL`` so callers cannot accidentally interpret an incomplete check
    as permission to continue.
    """

    image = image_path.expanduser().resolve()
    embedding = embedding_path.expanduser().resolve()
    report = SceneStartIdentityReport(
        image_path=str(image),
        embedding_path=str(embedding),
    )

    if not image.is_file():
        return _hard_fail(report, f"image file not found: {image}")
    try:
        report.image_sha256 = _sha256_file(image)
    except OSError as exc:
        return _hard_fail(report, f"image file unreadable: {exc}")

    if not embedding.is_file():
        return _hard_fail(report, f"anchor embedding not found: {embedding}")
    try:
        report.embedding_sha256 = _sha256_file(embedding)
    except OSError as exc:
        return _hard_fail(report, f"anchor embedding unreadable: {exc}")

    insightface, cv2, np = _try_import_insightface()
    if insightface is None or cv2 is None or np is None:
        return _hard_fail(
            report,
            "ArcFace runtime unavailable: insightface, opencv-python, numpy, "
            "and onnxruntime are required",
        )

    try:
        raster = cv2.imread(str(image), getattr(cv2, "IMREAD_COLOR", 1))
    except Exception as exc:  # runtime adapters can raise non-OSError errors
        return _hard_fail(report, f"image decode failed: {exc}")
    if raster is None:
        return _hard_fail(report, "image decode failed: raster is empty")
    shape = getattr(raster, "shape", None)
    if shape is None or len(shape) < 2 or int(shape[0]) <= 0 or int(shape[1]) <= 0:
        return _hard_fail(report, "image decode failed: invalid raster dimensions")
    report.image_height = int(shape[0])
    report.image_width = int(shape[1])

    try:
        anchor = np.asarray(np.load(embedding, allow_pickle=False))
    except Exception as exc:
        return _hard_fail(report, f"anchor embedding load failed: {exc}")
    if anchor.ndim != 1 or anchor.size == 0:
        return _hard_fail(report, "anchor embedding must be a non-empty vector")
    if not bool(np.all(np.isfinite(anchor))):
        return _hard_fail(report, "anchor embedding contains non-finite values")
    try:
        anchor_norm = float(np.linalg.norm(anchor))
    except Exception as exc:
        return _hard_fail(report, f"anchor embedding norm failed: {exc}")
    if not math.isfinite(anchor_norm) or anchor_norm <= 0.0:
        return _hard_fail(report, "anchor embedding norm is missing or zero")

    try:
        app = insightface.app.FaceAnalysis(name="buffalo_l")
        app.prepare(ctx_id=0, det_size=(640, 640))
        detected = app.get(raster)
        faces: list[object] = [] if detected is None else list(detected)
    except Exception as exc:
        return _hard_fail(report, f"ArcFace detection failed: {exc}")

    report.face_count = len(faces)
    report.detector_confidences = [_confidence(face, np) for face in faces]
    if report.face_count == 0:
        return _hard_fail(report, "no face detected; exactly one face is required")
    if report.face_count != 1:
        return _hard_fail(
            report,
            f"multiple faces detected ({report.face_count}); refusing arbitrary selection",
        )
    if report.detector_confidences[0] is None:
        return _hard_fail(report, "detector confidence is missing or non-finite")

    raw_face_embedding = getattr(faces[0], "normed_embedding", None)
    if raw_face_embedding is None:
        return _hard_fail(report, "detected face has no ArcFace embedding")
    try:
        face_embedding = np.asarray(raw_face_embedding)
    except Exception as exc:
        return _hard_fail(report, f"face embedding conversion failed: {exc}")
    if face_embedding.ndim != 1 or face_embedding.size == 0:
        return _hard_fail(report, "face embedding must be a non-empty vector")
    if face_embedding.shape != anchor.shape:
        return _hard_fail(
            report,
            "face and anchor embedding dimensions do not match: "
            f"{face_embedding.shape} != {anchor.shape}",
        )
    if not bool(np.all(np.isfinite(face_embedding))):
        return _hard_fail(report, "face embedding contains non-finite values")
    try:
        face_norm = float(np.linalg.norm(face_embedding))
    except Exception as exc:
        return _hard_fail(report, f"face embedding norm failed: {exc}")
    if not math.isfinite(face_norm) or face_norm <= 0.0:
        return _hard_fail(report, "face embedding norm is missing or zero")

    cosine = float(np.dot(anchor / anchor_norm, face_embedding / face_norm))
    if not math.isfinite(cosine):
        return _hard_fail(report, "cosine similarity is non-finite")
    report.cosine = max(-1.0, min(1.0, cosine))

    if report.cosine >= PASS_COSINE:
        report.status = "PASS"
        report.reason = "identity cosine meets the pass threshold"
    elif report.cosine >= HARD_FAIL_COSINE:
        report.status = "REJECT"
        report.reason = "identity cosine is below pass threshold"
    else:
        report.status = "HARD_FAIL"
        report.reason = "identity cosine is below the hard-fail threshold"
    return report


def write_report_atomic(
    report: SceneStartIdentityReport,
    report_path: Path,
) -> None:
    """Atomically replace ``report_path`` with a complete JSON report."""

    destination = report_path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify A007 identity in one generated scene-start still."
    )
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--embedding",
        type=Path,
        default=ANCHOR_EMBEDDING_PATH,
        help="A007 ArcFace embedding (.npy)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = verify_scene_start_identity(args.image, args.embedding)
    try:
        write_report_atomic(report, args.report)
    except OSError as exc:
        print(
            f"[wr3-scene-start-identity] report write failed: {exc}", file=os.sys.stderr
        )
        return 2
    print(
        f"[wr3-scene-start-identity] {report.status}: {report.reason}",
        file=os.sys.stderr,
    )
    if report.status == "PASS":
        return 0
    return 1 if report.status == "REJECT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
