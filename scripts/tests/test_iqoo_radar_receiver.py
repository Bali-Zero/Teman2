"""Black-box tests for the Termux forced-command receiver."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RECEIVER = REPO_ROOT / "infra" / "radar" / "iqoo" / "nuzantara-radar-receive"


def _capsule(**overrides: Any) -> dict[str, Any]:
    capsule: dict[str, Any] = {
        "schema_version": 1,
        "incident_id": "a" * 32,
        "condition_id": "b" * 16,
        "observed_at": "2026-08-25T01:02:03Z",
        "severity": "critical",
        "stage": "detected",
        "source_node": "pro",
        "source_class": "backup",
        "category": "data_integrity",
        "delivery_state": "sent",
        "repeat_count": 1,
        "details": "kept_on_source",
        "pii_policy": "no_raw_logs_no_free_text",
        "route": {
            "repairer": "bounded_sonnet5_healer",
            "reviewer": "independent_medium",
            "supervisor": "opus5_for_high_risk",
            "owner_gate": "irreversible_only",
        },
    }
    capsule.update(overrides)
    return capsule


def _run(
    home: Path, capsule: dict[str, Any], *, original_command: str = ""
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HOME": str(home),
        "SSH_ORIGINAL_COMMAND": original_command,
        "PATH": os.environ["PATH"],
    }
    return subprocess.run(
        ["bash", str(RECEIVER)],
        input=json.dumps(capsule) + "\n",
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
        check=False,
    )


def test_valid_capsule_is_stored_and_duplicate_is_idempotent(tmp_path: Path) -> None:
    first = _run(tmp_path, _capsule())
    assert first.returncode == 0
    assert first.stdout.strip() == f"RADAR_OK {'a' * 32}"

    stored = tmp_path / ".local/state/nuzantara-radar/incidents" / f"{'a' * 32}.json"
    latest = tmp_path / ".local/state/nuzantara-radar/latest.json"
    assert stored.is_file()
    assert latest.is_file()
    assert stored.stat().st_mode & 0o777 == 0o600

    second = _run(tmp_path, _capsule())
    assert second.returncode == 0
    assert second.stdout.strip() == f"RADAR_DUPLICATE {'a' * 32}"


def test_extra_free_text_field_is_rejected(tmp_path: Path) -> None:
    result = _run(tmp_path, _capsule(raw_log="PRIVATE_FREE_TEXT_TOKEN"))
    assert result.returncode == 64
    assert result.stdout.strip() == "RADAR_REJECTED"
    assert not list(
        (tmp_path / ".local/state/nuzantara-radar/incidents").glob("*.json")
    )


def test_remote_command_is_rejected_even_with_valid_capsule(tmp_path: Path) -> None:
    result = _run(tmp_path, _capsule(), original_command="uname -a")
    assert result.returncode == 64
    assert result.stdout.strip() == "RADAR_REJECTED"


def test_invalid_enum_and_oversized_payload_are_rejected(tmp_path: Path) -> None:
    invalid = _run(tmp_path, _capsule(category="PRIVATE_CATEGORY_TOKEN"))
    assert invalid.returncode == 64

    oversized = _run(tmp_path, _capsule(extra="x" * 9_000))
    assert oversized.returncode == 64
