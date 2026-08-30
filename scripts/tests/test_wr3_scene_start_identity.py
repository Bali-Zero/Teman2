from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr3_scene_start_identity as gate  # noqa: E402


def _runtime(
    monkeypatch: pytest.MonkeyPatch,
    faces: list[object],
) -> dict[str, object]:
    calls: dict[str, object] = {}

    class FakeFaceAnalysis:
        def __init__(self, *, name: str) -> None:
            calls["name"] = name

        def prepare(self, *, ctx_id: int, det_size: tuple[int, int]) -> None:
            calls["prepare"] = {"ctx_id": ctx_id, "det_size": det_size}

        def get(self, raster: np.ndarray) -> list[object]:
            calls["raster_shape"] = raster.shape
            return faces

    fake_insightface = SimpleNamespace(
        app=SimpleNamespace(FaceAnalysis=FakeFaceAnalysis)
    )
    fake_cv2 = SimpleNamespace(
        IMREAD_COLOR=1,
        imread=lambda _path, _mode: np.zeros((1280, 720, 3), dtype=np.uint8),
    )
    monkeypatch.setattr(
        gate,
        "_try_import_insightface",
        lambda: (fake_insightface, fake_cv2, np),
    )
    return calls


def _inputs(tmp_path: Path) -> tuple[Path, Path]:
    image = tmp_path / "scene-start.png"
    image.write_bytes(b"deterministic-raster-fixture")
    embedding = tmp_path / "A007.embedding.npy"
    np.save(embedding, np.array([1.0, 0.0], dtype=np.float32))
    return image, embedding


def _face(cosine: float, confidence: float = 0.99) -> object:
    return SimpleNamespace(
        det_score=confidence,
        normed_embedding=np.array(
            [cosine, math.sqrt(1.0 - cosine**2)], dtype=np.float32
        ),
    )


def test_exactly_one_face_passes_with_real_buffalo_l_pattern(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, embedding = _inputs(tmp_path)
    calls = _runtime(monkeypatch, [_face(0.80)])

    report = gate.verify_scene_start_identity(image, embedding)
    payload = report.to_dict()

    assert report.status == "PASS"
    assert report.face_count == 1
    assert report.detector_confidences == [pytest.approx(0.99)]
    assert report.cosine == pytest.approx(0.80)
    assert calls == {
        "name": "buffalo_l",
        "prepare": {"ctx_id": 0, "det_size": (640, 640)},
        "raster_shape": (1280, 720, 3),
    }
    assert payload["mock"] is False
    assert payload["image"]["width"] == 720
    assert payload["image"]["height"] == 1280
    assert len(payload["image"]["sha256"]) == 64
    assert payload["embedding"]["path"] == str(embedding.resolve())
    assert len(payload["embedding"]["sha256"]) == 64


def test_borderline_identity_is_rejected_not_hard_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, embedding = _inputs(tmp_path)
    _runtime(monkeypatch, [_face(0.575)])

    report = gate.verify_scene_start_identity(image, embedding)

    assert report.status == "REJECT"
    assert report.cosine == pytest.approx(0.575)
    assert report.to_dict()["thresholds"] == {"pass": 0.6, "hard_fail": 0.55}


def test_low_identity_is_hard_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, embedding = _inputs(tmp_path)
    _runtime(monkeypatch, [_face(0.54)])

    report = gate.verify_scene_start_identity(image, embedding)

    assert report.status == "HARD_FAIL"
    assert report.cosine == pytest.approx(0.54)


@pytest.mark.parametrize("faces", [[], [_face(0.80), _face(0.82)]])
def test_zero_or_multiple_faces_hard_fail_without_arbitrary_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    faces: list[object],
) -> None:
    image, embedding = _inputs(tmp_path)
    _runtime(monkeypatch, faces)

    report = gate.verify_scene_start_identity(image, embedding)

    assert report.status == "HARD_FAIL"
    assert report.face_count == len(faces)
    assert report.cosine is None


def test_atomic_report_preserves_existing_file_if_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "qa" / "identity.json"
    destination.parent.mkdir()
    destination.write_text("old-complete-report\n")
    report = gate.SceneStartIdentityReport(
        image_path="/tmp/image.png",
        embedding_path="/tmp/anchor.npy",
        status="PASS",
        reason="fixture",
    )

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("simulated interruption before atomic rename")

    monkeypatch.setattr(gate.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated interruption"):
        gate.write_report_atomic(report, destination)

    assert destination.read_text() == "old-complete-report\n"
    assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []


def test_atomic_report_and_cli_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, embedding = _inputs(tmp_path)
    _runtime(monkeypatch, [_face(0.80)])
    destination = tmp_path / "reports" / "identity.json"

    assert (
        gate.main(
            [
                "--image",
                str(image),
                "--embedding",
                str(embedding),
                "--report",
                str(destination),
            ]
        )
        == 0
    )

    payload = json.loads(destination.read_text())
    assert payload["status"] == "PASS"
    assert payload["mock"] is False
    assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []
