"""Unit tests for the B2 live enumeration runner.

Every test drives the module through its mocked HTTP seam
(``enumerate_live._post_evaluate`` / ``_get_health``) and a fake, non-sleeping
``_sleep`` -- NONE of these tests may call the deployed endpoint: a real call
would land in the shadow ledger and could burn the live rate budget these
tests exist to protect.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx
import pytest

from backend.scripts.visa_engine import enumerate_live


class _Response:
    def __init__(self, body: dict[str, Any] | None = None, *, status_code: int = 200, headers: dict[str, str] | None = None) -> None:
        self._body = body if body is not None else {}
        self.status_code = status_code
        self.headers = headers or {}

    def json(self) -> dict[str, Any]:
        return self._body


def _write_token(path: Path, token: str = "test-driver-token-never-log") -> str:
    path.write_text(f"{token}\n", encoding="utf-8")
    path.chmod(0o600)
    return token


def _walk(label: str, value: str = "yes") -> dict[str, Any]:
    return {
        "label": label,
        "asked": ["some_question"],
        "schema_version": "1.0.0",
        "assessment_id": "x",
        "collected_at": "2026-01-01T00:00:00Z",
        "facts": {"some_question": value},
    }


def _write_manifest(path: Path, walks: list[dict[str, Any]]) -> None:
    manifest = {"coveringSubset": {"walks": walks}}
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _engine_response(state: str = "SUPPORTED_CANDIDATES") -> _Response:
    return _Response(
        {
            "mode": "CURATED",
            "decision": {
                "state": state,
                "review_reasons": [],
                "no_path_reasons": [],
                "notices": [{"code": "DISCLOSED_HEALTH_CONCERN_CONDITION"}],
                "rule_pack": {"rule_pack_id": "x", "sequence": 22, "version": "2026.9.1"},
            },
        }
    )


@pytest.fixture(autouse=True)
def _no_real_sleeping(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Every backoff/rate-limit sleep is recorded, never actually awaited."""

    calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        calls.append(seconds)

    monkeypatch.setattr(enumerate_live, "_sleep", fake_sleep)

    async def fake_health(client: httpx.AsyncClient, *, url: str, timeout: float) -> _Response:
        return _Response({"build_sha": "deadbeef"}, status_code=200)

    monkeypatch.setattr(enumerate_live, "_get_health", fake_health)
    return calls


def _args(tmp_path: Path, manifest: Path, report: Path, **overrides: Any) -> list[str]:
    argv = [
        "--manifest",
        str(manifest),
        "--report",
        str(report),
        "--driver-token-file",
        str(tmp_path / "driver-token"),
    ]
    for key, value in overrides.items():
        argv.extend([f"--{key.replace('_', '-')}", str(value)])
    return argv


def test_missing_max_requests_refuses_without_network_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("baseline/all-default")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("network must not be called with no budget")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2

    assert not report.exists()
    assert "--max-requests is required" in caplog.text


def test_rate_per_minute_at_ceiling_refuses(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("baseline/all-default")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")

    args = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=10, rate_per_minute=30)
    )
    with pytest.raises(enumerate_live.EnumerateLiveError, match="dedicated"):
        enumerate_live.validate_budget(args.max_requests, args.rate_per_minute)


def test_dry_run_validates_and_prints_plan_without_network_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a"), _walk("b")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("--dry-run must never call the network")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    args = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=60, rate_per_minute=25) + ["--dry-run"]
    )

    assert enumerate_live.run(args) == 0
    out = capsys.readouterr().out
    assert "pending=2" in out
    assert "total=2" in out
    assert not report.exists()


def test_successful_walk_is_recorded_as_engine_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("baseline/all-default")])
    report = tmp_path / "report.json"
    token = _write_token(tmp_path / "driver-token")
    captured: dict[str, Any] = {}

    async def fake_post(client: httpx.AsyncClient, *, url: str, headers: dict[str, str], json_body: dict, timeout: float) -> _Response:
        captured["headers"] = headers
        captured["json_body"] = json_body
        return _engine_response()

    monkeypatch.setattr(enumerate_live, "_post_evaluate", fake_post)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    assert enumerate_live.run(args) == 0
    saved = json.loads(report.read_text())
    assert len(saved["walks"]) == 1
    row = saved["walks"][0]
    assert row["classification"] == "engine_verdict"
    assert row["engine_state"] == "SUPPORTED_CANDIDATES"
    assert row["reason_codes"]["notices"] == ["DISCLOSED_HEALTH_CONCERN_CONDITION"]
    assert row["walk_id"] == "baseline/all-default"
    assert "facts" not in row and "label" not in row  # no request facts beyond the walk id
    assert captured["headers"][enumerate_live.DRIVER_TOKEN_HEADER] == token
    assert captured["json_body"] == {
        "schema_version": "1.0.0",
        "assessment_id": "x",
        "collected_at": "2026-01-01T00:00:00Z",
        "facts": {"some_question": "yes"},
    }
    assert saved["manifest_sha256"] == enumerate_live.manifest_digest(json.loads(manifest.read_text()))
    assert saved["stopped_reason"] == "completed"


def test_429_is_a_harness_red_never_an_engine_verdict_and_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_real_sleeping: list[float]
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a"), _walk("b")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")
    calls = 0

    async def always_429(*_a: object, **_k: object) -> _Response:
        nonlocal calls
        calls += 1
        return _Response(status_code=429, headers={"Retry-After": "0"})

    monkeypatch.setattr(enumerate_live, "_post_evaluate", always_429)
    args = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=60, rate_per_minute=25, max_retries=2)
    )

    assert enumerate_live.run(args) == 1
    saved = json.loads(report.read_text())
    assert len(saved["walks"]) == 1  # walk "b" never attempted -- the run stopped
    row = saved["walks"][0]
    assert row["classification"] == "harness_red"
    assert row["harness_detail"] == "http_429"
    assert row["engine_state"] is None
    assert saved["stopped_reason"] == "rate_limited_harness_red"
    assert calls == 3  # 1 initial + 2 retries, all charged against the budget
    assert saved["requests_used"] == 3
    # 2 backoff sleeps (after attempt 1 and 2) + 2 rate-limiter spacing sleeps
    # (before attempt 2 and 3 -- the very first attempt never waits).
    assert len(_no_real_sleeping) == 4


def test_connection_error_retries_with_backoff_then_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_real_sleeping: list[float]
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("baseline/all-default")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")
    attempts = 0

    async def flaky(*_a: object, **_k: object) -> _Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("network flapped")
        return _engine_response()

    monkeypatch.setattr(enumerate_live, "_post_evaluate", flaky)
    args = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25, max_retries=3)
    )

    assert enumerate_live.run(args) == 0
    saved = json.loads(report.read_text())
    assert saved["walks"][0]["classification"] == "engine_verdict"
    assert saved["walks"][0]["retries"] == 2
    assert saved["requests_used"] == 3
    # 2 backoff sleeps (after the 2 failed attempts) + 2 rate-limiter spacing
    # sleeps (before attempt 2 and 3 -- the very first attempt never waits).
    assert len(_no_real_sleeping) == 4


def test_resume_skips_walks_already_recorded_with_a_terminal_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a"), _walk("b")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")
    calls: list[str] = []

    async def fake_post(client: httpx.AsyncClient, *, url: str, headers: dict, json_body: dict, timeout: float) -> _Response:
        calls.append(json_body["facts"]["some_question"])
        return _engine_response()

    monkeypatch.setattr(enumerate_live, "_post_evaluate", fake_post)

    args1 = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=1, rate_per_minute=25))
    assert enumerate_live.run(args1) == 1  # budget of 1 stops before walk "b"
    assert calls == ["yes"]
    first_saved = json.loads(report.read_text())
    assert len(first_saved["walks"]) == 1

    args2 = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))
    assert enumerate_live.run(args2) == 0
    assert calls == ["yes", "yes"]  # walk "a" was NOT re-sent
    second_saved = json.loads(report.read_text())
    assert [w["walk_id"] for w in second_saved["walks"]] == ["a", "b"]


def test_manifest_report_hash_mismatch_refuses_to_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a")])
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps({"manifest_sha256": "not-the-real-hash", "walks": []}), encoding="utf-8"
    )
    _write_token(tmp_path / "driver-token")

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("must not call the network on a hash mismatch")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2
    assert "refusing to resume against a mismatched walk set" in caplog.text


def test_driver_token_never_appears_in_report_or_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("baseline/all-default")])
    report = tmp_path / "report.json"
    token = _write_token(tmp_path / "driver-token")

    async def fake_post(*_a: object, **_k: object) -> _Response:
        return _engine_response()

    monkeypatch.setattr(enumerate_live, "_post_evaluate", fake_post)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    with caplog.at_level(logging.INFO, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 0

    assert token not in report.read_text()
    assert token not in caplog.text


def test_summary_never_adds_engine_verdicts_and_harness_reds_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a"), _walk("b")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")
    responses = [_engine_response(), _Response(status_code=503)]

    async def fake_post(*_a: object, **_k: object) -> _Response:
        return responses.pop(0)

    monkeypatch.setattr(enumerate_live, "_post_evaluate", fake_post)
    args = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25, max_retries=0)
    )

    assert enumerate_live.run(args) == 1
    saved = json.loads(report.read_text())
    summary = saved["summary"]
    assert set(summary.keys()) == {"total_walks", "recorded", "pending", "engine_verdicts", "harness_reds"}
    assert summary["engine_verdicts"] == {"SUPPORTED_CANDIDATES": 1}
    assert summary["harness_reds"] == {"http_5xx": 1}


def test_max_requests_exhausted_leaves_remaining_walks_unrecorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a"), _walk("b"), _walk("c")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")

    async def fake_post(*_a: object, **_k: object) -> _Response:
        return _engine_response()

    monkeypatch.setattr(enumerate_live, "_post_evaluate", fake_post)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=2, rate_per_minute=25))

    assert enumerate_live.run(args) == 1
    saved = json.loads(report.read_text())
    assert len(saved["walks"]) == 2
    assert saved["stopped_reason"] == "max_requests_exhausted"
    assert saved["requests_used"] == 2
