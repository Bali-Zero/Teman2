"""Tests for scripts/intake_ocr_provider_capture.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[5]
_APP_ROOT = _REPO_ROOT / "apps" / "backend-rag"
_SCRIPT_PATH = _APP_ROOT / "scripts" / "intake_ocr_provider_capture.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("intake_ocr_provider_capture", _SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


async def _fake_ocr_pages(_pages):
    return [
        {
            "page": 0,
            "text": "PASSPORT\nPassport No X1234567",
            "confidence": 0.9,
            "model": "fake-vlm",
            "via": "response",
        }
    ]


async def test_capture_manifest_writes_quality_jsonl(tmp_path: Path) -> None:
    module = _load_script_module()
    image_path = tmp_path / "passport.png"
    image_path.write_bytes(b"not-a-real-png")
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        json.dumps(
            {
                "id": "passport",
                "image_path": "passport.png",
                "expected_doc_type": "passport",
                "expected_fields": {"passport_no": "X1234567"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "provider.jsonl"

    samples = module.load_manifest(manifest_path)
    results = await module.capture_samples(
        samples,
        provider="ollama",
        output_path=output_path,
        ocr_pages_fn=_fake_ocr_pages,
    )

    assert results == [
        {
            "id": "passport",
            "provider": "ollama",
            "ocr_text": "PASSPORT\nPassport No X1234567",
            "expected_doc_type": "passport",
            "expected_fields": {"passport_no": "X1234567"},
            "chars": 29,
            "page_count": 1,
            "models": ["fake-vlm"],
            "vias": ["response"],
            "error": None,
        }
    ]
    [row] = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert row["provider"] == "ollama"
    assert row["ocr_text"] == "PASSPORT\nPassport No X1234567"
    assert row["seconds"] >= 0.0


def test_cli_requires_explicit_cloud_flag_for_gemini(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.jsonl"
    output_path = tmp_path / "provider.jsonl"

    completed = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT_PATH),
            "--manifest",
            str(manifest_path),
            "--output",
            str(output_path),
            "--provider",
            "gemini",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "--allow-cloud-vision" in completed.stderr
    assert not output_path.exists()
