"""Tests for scripts/intake_ocr_quality_eval.py.

The script consumes OCR text that providers already produced. It must stay
offline by default: no Ollama/Gemini calls during the benchmark harness.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[5]
_APP_ROOT = _REPO_ROOT / "apps" / "backend-rag"
_SCRIPT_PATH = _APP_ROOT / "scripts" / "intake_ocr_quality_eval.py"


def _clean_env() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(_APP_ROOT),
    }


def _app_env() -> dict[str, str]:
    env = _clean_env()
    env.update(
        {
            "JWT_SECRET_KEY": "test-jwt-secret-key-for-ocr-quality-eval",
            "API_KEYS": "test-api-key-for-ocr-quality-eval",
        }
    )
    return env


def test_script_help_does_not_require_model_or_app_settings() -> None:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--help"],
        cwd=_APP_ROOT,
        env=_clean_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "--input" in result.stdout
    assert "--allow-model-calls" in result.stdout
    assert "JWT_SECRET_KEY" not in result.stderr
    assert "API_KEYS" not in result.stderr


def test_script_evaluates_jsonl_and_summarizes_by_provider(tmp_path: Path) -> None:
    sample_path = tmp_path / "ocr_samples.jsonl"
    records = [
        {
            "id": "kitas-ollama",
            "provider": "ollama",
            "ocr_text": (
                "REPUBLIK INDONESIA\n"
                "IZIN TINGGAL TERBATAS\n"
                "Permit No: 2C11AB98765\n"
                "Name: MARIO LUCA ROSSI\n"
                "Valid Until: 2027-06-25\n"
                "Sponsor: PT BALI ZERO TEST"
            ),
            "expected_doc_type": "kitas",
            "expected_fields": {
                "kitas_no": "2C11AB98765",
                "name": "Mario Luca Rossi",
                "expiry": "2027-06-25",
                "sponsor": "PT BALI ZERO TEST",
            },
        },
        {
            "id": "kitas-gemini-missing",
            "provider": "gemini",
            "ocr_text": (
                "REPUBLIK INDONESIA\n"
                "IZIN TINGGAL TERBATAS\n"
                "Name: MARIO LUCA ROSSI\n"
                "Valid Until: 2027-06-25"
            ),
            "expected_doc_type": "kitas",
            "expected_fields": {
                "kitas_no": "2C11AB98765",
                "name": "Mario Luca Rossi",
                "expiry": "2027-06-25",
                "sponsor": "PT BALI ZERO TEST",
            },
        },
    ]
    sample_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--input", str(sample_path)],
        cwd=_APP_ROOT,
        env=_app_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["sample_count"] == 2
    assert payload["provider_summary"]["ollama"]["avg_field_score"] == 1.0
    assert payload["provider_summary"]["gemini"]["avg_field_score"] == 0.5
    assert payload["results"][1]["field_score"]["missing_fields"] == [
        "kitas_no",
        "sponsor",
    ]
