"""Hermetic tests for the PII-safe iQOO RADAR relay."""

from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "iqoo_radar_relay.py"
SPEC = importlib.util.spec_from_file_location("iqoo_radar_relay", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
radar = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = radar
SPEC.loader.exec_module(radar)


def _record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "ts": 1_774_915_200.0,
        "tier": "p0",
        "source": "postgres-backup-watchdog",
        "machine": "Nuzantara",
        "key": "cron-fail:backup-PRIVATE_KEY_TOKEN",
        "text": (
            "Backup failed for PRIVATE_NAME_TOKEN, PRIVATE_PHONE_TOKEN, "
            "PRIVATE_EMAIL_TOKEN, PRIVATE_DOCUMENT_TOKEN"
        ),
        "sent": True,
    }
    record.update(overrides)
    return record


def _append(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def test_capsule_contains_no_raw_or_pseudonymized_pii() -> None:
    record = _record()
    capsule = radar.build_capsule(
        record, spool_name="archive-p0.jsonl", byte_offset=123
    )
    encoded = json.dumps(capsule, sort_keys=True)

    for forbidden in (
        record["text"],
        record["key"],
        record["source"],
        "PRIVATE_NAME_TOKEN",
        "PRIVATE_PHONE_TOKEN",
        "PRIVATE_EMAIL_TOKEN",
        "PRIVATE_DOCUMENT_TOKEN",
    ):
        assert forbidden not in encoded
    assert capsule["category"] == "data_integrity"
    assert capsule["source_class"] == "backup"
    assert capsule["route"]["supervisor"] == "opus5_for_high_risk"
    assert capsule["pii_policy"] == "no_raw_logs_no_free_text"


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("credential revoked", "security"),
        ("payment quota exhausted", "billing"),
        ("WhatsApp bridge down", "communications"),
        ("disk inode exhausted", "storage"),
        ("LKPM deadline missed", "compliance"),
        ("service timeout", "availability"),
        ("unexpected generic condition", "system"),
    ],
)
def test_category_vocabulary_is_finite(text: str, category: str) -> None:
    capsule = radar.build_capsule(
        _record(source="generic", key="generic", text=text),
        spool_name="archive-p0.jsonl",
        byte_offset=0,
    )
    assert capsule["category"] == category
    assert capsule["category"] in radar.ALLOWED_CATEGORIES


def test_first_run_bootstraps_at_eof_without_historical_replay(tmp_path: Path) -> None:
    spool = tmp_path / "spool"
    state = tmp_path / "state"
    spool.mkdir()
    archive = spool / "archive-p0.jsonl"
    _append(archive, _record())
    sent: list[dict[str, Any]] = []

    first = radar.relay_once(spool_dir=spool, state_dir=state, sender=sent.append)
    assert first.bootstrapped == 1
    assert sent == []

    _append(archive, _record(ts=1_774_915_201.0))
    second = radar.relay_once(spool_dir=spool, state_dir=state, sender=sent.append)
    assert second.delivered == 1
    assert len(sent) == 1


def test_failed_delivery_retries_same_incident_without_advancing(
    tmp_path: Path,
) -> None:
    spool = tmp_path / "spool"
    state = tmp_path / "state"
    spool.mkdir()
    archive = spool / "archive-p0.jsonl"
    _append(archive, _record())
    attempts: list[str] = []

    def fail(capsule: dict[str, Any]) -> None:
        attempts.append(capsule["incident_id"])
        raise radar.RelayError("synthetic transport failure")

    first = radar.relay_once(
        spool_dir=spool,
        state_dir=state,
        sender=fail,
        replay_existing=True,
    )
    assert first.failed == 1

    delivered: list[dict[str, Any]] = []
    second = radar.relay_once(
        spool_dir=spool,
        state_dir=state,
        sender=delivered.append,
    )
    assert second.delivered == 1
    assert attempts == [delivered[0]["incident_id"]]


def test_pending_relays_only_unsent_or_overflow_p0(tmp_path: Path) -> None:
    spool = tmp_path / "spool"
    state = tmp_path / "state"
    spool.mkdir()
    pending = spool / "pending.jsonl"
    _append(pending, _record(tier="digest"))
    _append(pending, _record(ts=1_774_915_201.0, sent=False))
    _append(pending, _record(ts=1_774_915_202.0, sent=False, p0_unsent=True))
    _append(pending, _record(ts=1_774_915_203.0, sent=False, p0_overflow=True))
    sent: list[dict[str, Any]] = []

    outcome = radar.relay_once(
        spool_dir=spool,
        state_dir=state,
        sender=sent.append,
        replay_existing=True,
    )
    assert outcome.ignored == 2
    assert outcome.delivered == 2
    assert {item["delivery_state"] for item in sent} == {
        "transport_unsent",
        "budget_holdback",
    }


def test_malformed_line_is_skipped_without_leaking_or_blocking(tmp_path: Path) -> None:
    spool = tmp_path / "spool"
    state = tmp_path / "state"
    spool.mkdir()
    archive = spool / "archive-p0.jsonl"
    archive.write_text("not-json-with-PRIVATE_TOKEN\n", encoding="utf-8")
    _append(archive, _record())
    sent: list[dict[str, Any]] = []

    outcome = radar.relay_once(
        spool_dir=spool,
        state_dir=state,
        sender=sent.append,
        replay_existing=True,
    )
    assert outcome.malformed == 1
    assert outcome.delivered == 1
    assert len(sent) == 1


def test_oversized_physical_line_is_drained_as_one_record(tmp_path: Path) -> None:
    spool = tmp_path / "spool"
    state = tmp_path / "state"
    spool.mkdir()
    archive = spool / "archive-p0.jsonl"
    archive.write_bytes(b"x" * (radar.MAX_LINE_BYTES * 3) + b"\n")
    _append(archive, _record())
    sent: list[dict[str, Any]] = []

    outcome = radar.relay_once(
        spool_dir=spool,
        state_dir=state,
        sender=sent.append,
        replay_existing=True,
    )

    assert outcome.malformed == 1
    assert outcome.delivered == 1
    assert len(sent) == 1


def test_unexpected_sender_exception_remains_retry_safe(tmp_path: Path) -> None:
    spool = tmp_path / "spool"
    state = tmp_path / "state"
    spool.mkdir()
    archive = spool / "archive-p0.jsonl"
    _append(archive, _record())

    def fail_unexpected(_capsule: dict[str, Any]) -> None:
        raise ValueError("synthetic failure with sensitive-looking text")

    first = radar.relay_once(
        spool_dir=spool,
        state_dir=state,
        sender=fail_unexpected,
        replay_existing=True,
    )
    assert first.failed == 1

    delivered: list[dict[str, Any]] = []
    second = radar.relay_once(
        spool_dir=spool,
        state_dir=state,
        sender=delivered.append,
    )
    assert second.delivered == 1


def test_incomplete_trailing_line_is_retried_after_producer_finishes(
    tmp_path: Path,
) -> None:
    spool = tmp_path / "spool"
    state = tmp_path / "state"
    spool.mkdir()
    archive = spool / "archive-p0.jsonl"
    archive.write_text(json.dumps(_record()), encoding="utf-8")
    sent: list[dict[str, Any]] = []

    incomplete = radar.relay_once(
        spool_dir=spool,
        state_dir=state,
        sender=sent.append,
        replay_existing=True,
    )
    assert incomplete.delivered == 0
    assert incomplete.malformed == 0
    assert sent == []

    with archive.open("a", encoding="utf-8") as handle:
        handle.write("\n")
    completed = radar.relay_once(
        spool_dir=spool,
        state_dir=state,
        sender=sent.append,
    )
    assert completed.delivered == 1
    assert len(sent) == 1


def test_cursor_state_permissions_are_private(tmp_path: Path) -> None:
    spool = tmp_path / "spool"
    state = tmp_path / "state"
    spool.mkdir()
    _append(spool / "archive-p0.jsonl", _record())

    radar.relay_once(spool_dir=spool, state_dir=state, sender=lambda _item: None)

    assert stat.S_IMODE(state.stat().st_mode) == 0o700
    assert stat.S_IMODE((state / "cursor.json").stat().st_mode) == 0o600


def test_ssh_transport_uses_only_dedicated_pins_and_option_terminator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = tmp_path / "identity"
    known_hosts = tmp_path / "known_hosts"
    identity.touch()
    known_hosts.touch()
    capsule = radar.build_capsule(
        _record(), spool_name="archive-p0.jsonl", byte_offset=0
    )
    captured: list[str] = []

    def fake_run(
        command: list[str], **_kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        captured.extend(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f"RADAR_OK {capsule['incident_id']}\n",
            stderr="",
        )

    monkeypatch.setattr(radar.subprocess, "run", fake_run)
    radar._send_via_ssh(
        capsule,
        target="radar@100.64.134.94",
        port=8022,
        identity=identity,
        known_hosts=known_hosts,
        timeout_seconds=5,
    )

    assert "GlobalKnownHostsFile=/dev/null" in captured
    assert "StrictHostKeyChecking=yes" in captured
    assert captured[-2:] == ["--", "radar@100.64.134.94"]

    with pytest.raises(radar.RelayError, match="option prefix"):
        radar._send_via_ssh(
            capsule,
            target="-malformed",
            port=8022,
            identity=identity,
            known_hosts=known_hosts,
            timeout_seconds=5,
        )


def test_main_distinguishes_retryable_delivery_from_local_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        radar,
        "relay_once",
        lambda **_kwargs: radar.DeliveryResult(failed=1),
    )
    assert radar.main(["--state-dir", str(tmp_path)]) == radar.EXIT_TEMPFAIL

    def local_failure(**_kwargs: Any) -> radar.DeliveryResult:
        raise radar.RelayError("synthetic local failure")

    monkeypatch.setattr(radar, "relay_once", local_failure)
    assert radar.main(["--state-dir", str(tmp_path)]) == radar.EXIT_SOFTWARE


@pytest.mark.parametrize(
    "wrapper_name",
    ["pro-iqoo-radar-relay.sh", "mini-iqoo-radar-relay.sh"],
)
def test_wrapper_marks_mobile_delivery_deferral_as_healthy(wrapper_name: str) -> None:
    wrapper = (
        REPO_ROOT / "infra" / "launchagents" / "wrappers" / wrapper_name
    ).read_text(encoding="utf-8")
    assert "75)\n        # A mobile pager" in wrapper
    assert 'heartbeat "ok" "delivery deferred rc=75"' in wrapper
    assert 'PYTHON="$REPO/apps/backend-rag/.venv/bin/python"' in wrapper
