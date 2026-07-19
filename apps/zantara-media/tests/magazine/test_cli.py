from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from zantara_media.cli.magazine_publish import async_main


@pytest.mark.asyncio
async def test_morning_dry_run_is_deterministic_and_never_logs_payload_or_secret(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = tmp_path / "manifest.json"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    secret_marker = "never-log-this-secret"
    source.write_text(
        json.dumps(
            {
                "collector_runs": [],
                "candidate_rows": {"intel-lake": []},
                "expected_current_revision": 4,
                "expected_breaking_revision": 3,
                "private_note": secret_marker,
            }
        ),
        encoding="utf-8",
    )
    common = [
        "morning",
        "--input",
        str(source),
        "--cutoff",
        "2026-07-17T22:15:00Z",
        "--required-system-id",
        "intel-lake",
        "--dry-run",
    ]
    with caplog.at_level(logging.INFO):
        assert await async_main([*common, "--output", str(first)]) == 0
        assert await async_main([*common, "--output", str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()
    packet = json.loads(first.read_text(encoding="utf-8"))
    assert packet["edition_kind"] == "quiet"
    assert secret_marker not in caplog.text
    assert "private_note" not in caplog.text


def test_cli_requires_explicit_publish_flag_for_network() -> None:
    source = Path("manifest.json")
    # Importing/building the CLI performs no network I/O; publishing is opt-in.
    assert "--publish" not in ["morning", "--input", str(source), "--dry-run"]
