from __future__ import annotations

import importlib.util
import json
import os
import plistlib
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PREFLIGHT_PATH = _REPO_ROOT / "scripts" / "visa_oracle_analytics_retention_preflight.py"
_PLIST_PATH = (
    _REPO_ROOT
    / "infra"
    / "launchagents"
    / "com.nuzantara.visa-oracle-retention.15min.plist.example"
)
_WRAPPER_PATH = (
    _REPO_ROOT / "infra" / "launchagents" / "wrappers" / "visa-oracle-retention-run.sh"
)
_ATTESTATION_EXAMPLE_PATH = (
    _REPO_ROOT
    / "infra"
    / "launchagents"
    / "visa-oracle-analytics-retention-attestation.example.json"
)


def _load_preflight() -> ModuleType:
    spec = importlib.util.spec_from_file_location("visa_retention_preflight", _PREFLIGHT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _valid_attestation(now: datetime) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "ATTESTED",
        "destination": {
            "provider": "provider-export",
            "destination_id_sha256": "a" * 64,
            "event_scope": "visa_oracle_v2_*",
        },
        "retention": {"ttl_days": 365, "mode": "AUTOMATIC_TTL"},
        "verification": {
            "method": "PROVIDER_READ_ONLY_EXPORT_AND_SYNTHETIC_PROBE",
            "observed_at": now.isoformat(),
            "synthetic_expired_event_was_present": True,
            "synthetic_expired_ingestion_receipt_sha256": "c" * 64,
            "synthetic_expired_event_absent": True,
            "synthetic_control_event_present": True,
            "production_rows_deleted": False,
            "provider_export_sha256": "b" * 64,
        },
    }


def test_valid_pii_free_12_month_attestation_passes(tmp_path: Path) -> None:
    """Guilt+innocence pair, innocence half (DPIA V2 §A ruling: 12 months = 365 days).

    A fresh, correctly-shaped attestation carrying the ruled 365-day TTL must be
    accepted by the real `load_attestation` function — not a mocked constant.
    """
    preflight = _load_preflight()
    assert preflight.EXPECTED_TTL_DAYS == 365
    now = datetime(2026, 8, 7, 3, 0, tzinfo=timezone.utc)
    path = tmp_path / "attestation.json"
    path.write_text(json.dumps(_valid_attestation(now)), encoding="utf-8")

    evidence = preflight.load_attestation(path, now=now + timedelta(hours=1))

    assert evidence.provider == "provider-export"
    assert evidence.destination_id_sha256 == "a" * 64


def test_ninety_day_attestation_is_rejected_after_ttl_ruling(tmp_path: Path) -> None:
    """Guilt+innocence pair, guilt half.

    The old provisional 90-day TTL (pre DPIA V2 §A) must now be REJECTED by the
    real preflight function — the constant moved to 365, and an attestation stuck
    on the superseded 90-day value cannot pass the gate.
    """
    preflight = _load_preflight()
    now = datetime(2026, 8, 7, 3, 0, tzinfo=timezone.utc)
    document = _valid_attestation(now)
    document["retention"]["ttl_days"] = 90
    path = tmp_path / "ninety-day-attestation.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(preflight.PreflightError, match="365 days"):
        preflight.load_attestation(path, now=now)


@pytest.mark.parametrize(
    ("field_path", "value", "message"),
    [
        (("retention", "ttl_days"), 366, "365 days"),
        (("retention", "mode"), "MANUAL", "automatic TTL"),
        (("verification", "production_rows_deleted"), True, "must not delete production"),
        (("verification", "synthetic_expired_event_was_present"), False, "prior ingestion"),
        (("verification", "synthetic_expired_event_absent"), False, "not proven"),
    ],
)
def test_attestation_fails_closed_on_policy_drift(
    tmp_path: Path,
    field_path: tuple[str, str],
    value: object,
    message: str,
) -> None:
    preflight = _load_preflight()
    now = datetime(2026, 8, 7, 3, 0, tzinfo=timezone.utc)
    document = _valid_attestation(now)
    section = document[field_path[0]]
    assert isinstance(section, dict)
    section[field_path[1]] = value
    path = tmp_path / "attestation.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(preflight.PreflightError, match=message):
        preflight.load_attestation(path, now=now)


def test_unconfigured_repository_example_blocks_enforce() -> None:
    preflight = _load_preflight()

    with pytest.raises(preflight.PreflightError, match="not ATTESTED"):
        preflight.load_attestation(_ATTESTATION_EXAMPLE_PATH)


def test_stale_or_future_dated_attestation_blocks_enforce(tmp_path: Path) -> None:
    preflight = _load_preflight()
    now = datetime(2026, 8, 7, 3, 0, tzinfo=timezone.utc)
    path = tmp_path / "attestation.json"
    path.write_text(
        json.dumps(_valid_attestation(now - timedelta(days=8))),
        encoding="utf-8",
    )
    with pytest.raises(preflight.PreflightError, match="older than 7 days"):
        preflight.load_attestation(path, now=now)

    path.write_text(
        json.dumps(_valid_attestation(now + timedelta(minutes=1))),
        encoding="utf-8",
    )
    with pytest.raises(preflight.PreflightError, match="future-dated"):
        preflight.load_attestation(path, now=now)


def test_duplicate_keys_and_raw_payload_keys_are_rejected(tmp_path: Path) -> None:
    preflight = _load_preflight()
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    with pytest.raises(preflight.PreflightError, match="duplicate JSON key"):
        preflight.load_attestation(duplicate)

    now = datetime(2026, 8, 7, 3, 0, tzinfo=timezone.utc)
    document = _valid_attestation(now)
    document["payload"] = "must-never-be-present"
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(preflight.PreflightError, match="unexpected=.*payload"):
        preflight.load_attestation(raw, now=now)


def test_oversized_attestation_is_rejected_before_json_parse(tmp_path: Path) -> None:
    preflight = _load_preflight()
    path = tmp_path / "oversized.json"
    path.write_text(" " * 16_385, encoding="utf-8")

    with pytest.raises(preflight.PreflightError, match="exceeds 16384 bytes"):
        preflight.load_attestation(path)


def test_unknown_extra_key_is_rejected_without_a_blocklist_match(tmp_path: Path) -> None:
    preflight = _load_preflight()
    now = datetime(2026, 8, 7, 3, 0, tzinfo=timezone.utc)
    document = _valid_attestation(now)
    destination = document["destination"]
    assert isinstance(destination, dict)
    destination["opaque_metadata"] = "not-on-any-pii-blocklist"
    path = tmp_path / "extra.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(preflight.PreflightError, match="unexpected=.*opaque_metadata"):
        preflight.load_attestation(path, now=now)


def test_absent_expired_probe_without_prior_presence_is_blocked(tmp_path: Path) -> None:
    preflight = _load_preflight()
    now = datetime(2026, 8, 7, 3, 0, tzinfo=timezone.utc)
    document = _valid_attestation(now)
    verification = document["verification"]
    assert isinstance(verification, dict)
    assert verification["synthetic_expired_event_absent"] is True
    verification["synthetic_expired_event_was_present"] = False
    path = tmp_path / "never-ingested.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(preflight.PreflightError, match="prior ingestion"):
        preflight.load_attestation(path, now=now)


def test_launchagent_is_one_shot_dry_run_and_uses_existing_cron_wrapper() -> None:
    with _PLIST_PATH.open("rb") as handle:
        manifest = plistlib.load(handle)

    assert manifest["KeepAlive"] is False
    assert manifest["RunAtLoad"] is False
    assert manifest["StartInterval"] == 900
    # Backlog/lag exits with 2 and must page immediately. Retrying the same
    # cycle could clear the backlog and hide the required alert.
    assert manifest["EnvironmentVariables"]["CRON_MAX_RETRIES"] == "0"
    assert manifest["EnvironmentVariables"]["VISA_ORACLE_RETENTION_APPLY"] == "false"
    arguments = manifest["ProgramArguments"]
    assert "/Users/nuzantara/nuzantara/scripts/cron-wrapper.sh" in arguments
    assert "visa-oracle-retention" in arguments


def test_payload_wrapper_is_syntax_valid_and_never_hardcodes_apply() -> None:
    result = subprocess.run(
        ["bash", "-n", str(_WRAPPER_PATH)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    source = _WRAPPER_PATH.read_text(encoding="utf-8")
    assert 'APPLY_MODE="${VISA_ORACLE_RETENTION_APPLY:-false}"' in source
    assert "retention_worker --apply" in source
    assert 'exec env PYTHONPATH=. "$PYTHON_BIN"' in source
    assert "visa_oracle_analytics_retention_preflight.py" not in source


@pytest.mark.parametrize(("apply", "expected_apply"), [("false", False), ("true", True)])
def test_payload_wrapper_apply_mode_is_explicit_and_analytics_independent(
    tmp_path: Path,
    apply: str,
    expected_apply: bool,
) -> None:
    fake_repo = tmp_path / "repo"
    backend_root = fake_repo / "apps" / "backend-rag"
    backend_root.mkdir(parents=True)
    captured = tmp_path / "arguments.txt"
    fake_python = tmp_path / "python"
    fake_python.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$@" > "$CAPTURED_ARGUMENTS"\n',
        encoding="utf-8",
    )
    fake_python.chmod(0o700)
    environment = os.environ.copy()
    environment.update(
        {
            "CAPTURED_ARGUMENTS": str(captured),
            "NUZANTARA_REPO_ROOT": str(fake_repo),
            "VISA_ORACLE_PYTHON_BIN": str(fake_python),
            "VISA_ORACLE_RETENTION_APPLY": apply,
        }
    )

    result = subprocess.run(
        ["bash", str(_WRAPPER_PATH)],
        cwd=_REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    arguments = captured.read_text(encoding="utf-8").splitlines()
    expected = ["-m", "backend.scripts.visa_engine.retention_worker"]
    if expected_apply:
        expected.append("--apply")
    assert arguments == expected
