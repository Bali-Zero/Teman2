"""Unit tests for the B2' live enumeration runner.

Every test drives the module through its mocked HTTP seam
(``enumerate_live._post_evaluate`` / ``_get_health``) and a fake, non-sleeping
``_sleep`` -- NONE of these tests may call the deployed endpoint: a real call
would land in the shadow ledger and could burn the live rate budget these
tests exist to protect.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from backend.scripts.visa_engine import enumerate_live
from backend.scripts.visa_engine.report_lock import ReportLock


class _Response:
    def __init__(
        self, body: dict[str, Any] | None = None, *, status_code: int = 200, headers: dict[str, str] | None = None
    ) -> None:
        self._body = body if body is not None else {}
        self.status_code = status_code
        self.headers = headers or {}

    def json(self) -> dict[str, Any]:
        return self._body


def _write_token(path: Path, token: str = "test-driver-token-never-log") -> str:
    path.write_text(f"{token}\n", encoding="utf-8")
    path.chmod(0o600)
    return token


#: B2''-c: a fixed, obviously-synthetic UUID -- valid shape, no realistic
#: identity is ever emitted. Used as every test walk's default assessment_id
#: so the pre-flight (uuid.UUID(str(value))) passes for every EXISTING test;
#: individual guilt tests below override it with an invalid value.
_VALID_ASSESSMENT_ID = "11111111-1111-4111-8111-111111111111"


def _walk(label: str, value: str = "yes", assessment_id: str = _VALID_ASSESSMENT_ID) -> dict[str, Any]:
    return {
        "label": label,
        "asked": ["some_question"],
        "schema_version": "1.0.0",
        "assessment_id": assessment_id,
        "collected_at": "2026-01-01T00:00:00Z",
        "facts": {"some_question": value},
    }


def _write_manifest(path: Path, walks: list[dict[str, Any]]) -> None:
    manifest = {"coveringSubset": {"walks": walks}}
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _engine_response(state: str = "SUPPORTED_CANDIDATES", *, outage: dict[str, Any] | None = None) -> _Response:
    return _Response(
        {
            "mode": "CURATED",
            "decision": {
                "state": state,
                "review_reasons": [],
                "no_path_reasons": [],
                "notices": [{"code": "DISCLOSED_HEALTH_CONCERN_CONDITION"}],
                "rule_pack": {"rule_pack_id": "x", "sequence": 22, "version": "2026.9.1"},
                "outage": outage,
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


# ---------------------------------------------------------------------------
# Budget / validation (unchanged mechanics, updated signature)
# ---------------------------------------------------------------------------


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
    with pytest.raises(enumerate_live.EnumerateLiveError, match="dedicated"):
        enumerate_live.validate_budget(10, 30, enumerate_live.DEFAULT_MAX_CONSECUTIVE_HARNESS_REDS)


def test_max_consecutive_harness_reds_must_be_at_least_one() -> None:
    with pytest.raises(enumerate_live.EnumerateLiveError, match="must be >= 1"):
        enumerate_live.validate_budget(10, 25, 0)


def test_max_consecutive_harness_reds_cannot_exceed_max_requests() -> None:
    with pytest.raises(enumerate_live.EnumerateLiveError, match="must be <="):
        enumerate_live.validate_budget(5, 25, 6)


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


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
    assert "never_attempted=2" in out
    assert "retryable_harness_reds=0" in out
    assert "health_probes_outside_budget=2" in out
    assert "max_consecutive_harness_reds=3" in out
    assert not report.exists()


def test_dry_run_reads_a_v2_report_without_rewriting_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("recorded")])
    report = tmp_path / "b4-2-report.json"
    old_report = {
        "report_version": 2,
        "manifest_sha256": enumerate_live.manifest_digest(enumerate_live.load_manifest(manifest)),
        "walks": [{"walk_id": "recorded", "classification": "engine_verdict"}],
    }
    original = json.dumps(old_report)
    report.write_text(original, encoding="utf-8")
    _write_token(tmp_path / "driver-token")

    args = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25) + ["--dry-run"]
    )

    assert enumerate_live.run(args) == 0
    out = capsys.readouterr().out
    assert "pending=0" in out
    assert "already_recorded=1" in out
    assert report.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# Successful walk / report shape
# ---------------------------------------------------------------------------


def test_successful_walk_is_recorded_as_engine_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("baseline/all-default")])
    report = tmp_path / "report.json"
    token = _write_token(tmp_path / "driver-token")
    captured: dict[str, Any] = {}

    async def fake_post(
        client: httpx.AsyncClient, *, url: str, headers: dict[str, str], json_body: dict, timeout: float
    ) -> _Response:
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
    assert row["attempts"] == 1
    assert len(row["attempts_history"]) == 1
    assert row["attempts_history"][0]["classification"] == "engine_verdict"
    assert "facts" not in row and "label" not in row  # no request facts beyond the walk id
    assert captured["headers"][enumerate_live.DRIVER_TOKEN_HEADER] == token
    assert captured["json_body"] == {
        "schema_version": "1.0.0",
        "assessment_id": _VALID_ASSESSMENT_ID,
        "collected_at": "2026-01-01T00:00:00Z",
        "facts": {"some_question": "yes"},
    }
    assert saved["manifest_sha256"] == enumerate_live.manifest_digest(json.loads(manifest.read_text()))
    assert saved["stopped_reason"] == "completed"
    assert saved["requests_used_this_run"] == 1
    assert saved["requests_used_total"] == 1
    assert saved["health"]["probes_outside_budget"] == 2


def test_temp_unavailable_outage_is_preserved_verbatim_in_the_report_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("temporarily-unavailable")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")
    outage = {"code": "UPSTREAM_MAINTENANCE", "retryable": True, "window": "short"}

    async def fake_post(*_a: object, **_k: object) -> _Response:
        return _engine_response("TEMPORARILY_UNAVAILABLE", outage=outage)

    monkeypatch.setattr(enumerate_live, "_post_evaluate", fake_post)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    assert enumerate_live.run(args) == 0
    row = json.loads(report.read_text(encoding="utf-8"))["walks"][0]
    assert row["engine_state"] == "TEMPORARILY_UNAVAILABLE"
    assert row["outage"]["code"] == "UPSTREAM_MAINTENANCE"
    assert row["outage"] == outage


# ---------------------------------------------------------------------------
# W1 -- circuit breakers
# ---------------------------------------------------------------------------


def test_401_circuit_breaker_stops_after_exactly_one_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a"), _walk("b"), _walk("c")])
    report = tmp_path / "report.json"
    token = _write_token(tmp_path / "driver-token")
    calls = 0

    async def always_401(*_a: object, **_k: object) -> _Response:
        nonlocal calls
        calls += 1
        return _Response(status_code=401)

    monkeypatch.setattr(enumerate_live, "_post_evaluate", always_401)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=60, rate_per_minute=25))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 1

    assert calls == 1  # exactly one evaluate request -- no retry, no further walks
    saved = json.loads(report.read_text())
    assert len(saved["walks"]) == 1
    row = saved["walks"][0]
    assert row["classification"] == "harness_red"
    assert row["harness_detail"] == "http_401"
    assert row["http_status"] == 401
    assert row["attempts"] == 1
    assert saved["stopped_reason"] == "auth_error_circuit_breaker"
    assert saved["requests_used_this_run"] == 1
    assert "the token FILE is the likely cause" in caplog.text
    assert token not in caplog.text


def test_403_circuit_breaker_also_stops_after_one_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a"), _walk("b")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")
    calls = 0

    async def always_403(*_a: object, **_k: object) -> _Response:
        nonlocal calls
        calls += 1
        return _Response(status_code=403)

    monkeypatch.setattr(enumerate_live, "_post_evaluate", always_403)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=60, rate_per_minute=25))

    assert enumerate_live.run(args) == 1
    assert calls == 1
    saved = json.loads(report.read_text())
    assert saved["stopped_reason"] == "auth_error_circuit_breaker"
    assert saved["walks"][0]["harness_detail"] == "http_403"


def test_consecutive_harness_reds_trip_the_breaker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk(f"walk-{i}") for i in range(5)])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")
    calls = 0

    async def blanket_400(*_a: object, **_k: object) -> _Response:
        nonlocal calls
        calls += 1
        return _Response(status_code=400)

    monkeypatch.setattr(enumerate_live, "_post_evaluate", blanket_400)
    args = enumerate_live._parse_args(
        _args(
            tmp_path, manifest, report, max_requests=60, rate_per_minute=25, max_consecutive_harness_reds=2
        )
    )

    assert enumerate_live.run(args) == 1
    assert calls == 2  # breaker trips after exactly 2 consecutive harness reds
    saved = json.loads(report.read_text())
    assert len(saved["walks"]) == 2
    assert all(w["harness_detail"] == "http_400" for w in saved["walks"])
    assert saved["stopped_reason"] == "consecutive_harness_reds_circuit_breaker"


def test_engine_verdict_resets_the_consecutive_counter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk(f"walk-{i}") for i in range(5)])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")
    # 500, 500, 200 (resets), 500, 500 -- breaker set to 3 never trips because
    # the 200 resets the streak before it reaches 3 either time.
    sequence = [
        _Response(status_code=500),
        _Response(status_code=500),
        _engine_response(),
        _Response(status_code=500),
        _Response(status_code=500),
    ]

    async def scripted(*_a: object, **_k: object) -> _Response:
        return sequence.pop(0)

    monkeypatch.setattr(enumerate_live, "_post_evaluate", scripted)
    args = enumerate_live._parse_args(
        _args(
            tmp_path,
            manifest,
            report,
            max_requests=60,
            rate_per_minute=25,
            max_retries=0,
            max_consecutive_harness_reds=3,
        )
    )

    # exit is still non-zero (the pre-existing rule: 0 requires ZERO harness
    # reds too, unchanged from #6861) -- what this test proves is the BREAKER
    # never trips and every walk gets attempted, which stopped_reason pins.
    assert enumerate_live.run(args) == 1
    saved = json.loads(report.read_text())
    assert len(saved["walks"]) == 5
    assert saved["stopped_reason"] == "completed"
    assert saved["summary"]["engine_verdicts"] == {"SUPPORTED_CANDIDATES": 1}
    assert saved["summary"]["harness_reds"] == {"http_5xx": 4}


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
    assert saved["requests_used_this_run"] == 3
    # 2 backoff sleeps + 2 rate-limiter spacing sleeps (the very first attempt never waits).
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
    assert saved["requests_used_this_run"] == 3
    assert len(_no_real_sleeping) == 4


# ---------------------------------------------------------------------------
# W2 -- harness reds are re-attemptable on resume
# ---------------------------------------------------------------------------


def test_harness_red_is_reattempted_on_resume_and_history_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk(f"walk-{i}") for i in range(3)])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")

    async def all_500(*_a: object, **_k: object) -> _Response:
        return _Response(status_code=500)

    monkeypatch.setattr(enumerate_live, "_post_evaluate", all_500)
    args1 = enumerate_live._parse_args(
        _args(
            tmp_path,
            manifest,
            report,
            max_requests=60,
            rate_per_minute=25,
            max_retries=0,
            max_consecutive_harness_reds=3,
        )
    )
    assert enumerate_live.run(args1) == 1  # breaker trips after all 3
    run1 = json.loads(report.read_text())
    assert len(run1["walks"]) == 3
    assert all(w["classification"] == "harness_red" for w in run1["walks"])
    assert all(w["attempts"] == 1 for w in run1["walks"])

    async def healthy(*_a: object, **_k: object) -> _Response:
        return _engine_response()

    monkeypatch.setattr(enumerate_live, "_post_evaluate", healthy)
    args2 = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=60, rate_per_minute=25)
    )
    assert enumerate_live.run(args2) == 0

    run2 = json.loads(report.read_text())
    assert len(run2["walks"]) == 3
    for row in run2["walks"]:
        assert row["classification"] == "engine_verdict"
        assert row["attempts"] == 2
        assert [a["classification"] for a in row["attempts_history"]] == ["harness_red", "engine_verdict"]
        assert row["attempts_history"][0]["harness_detail"] == "http_5xx"
    assert [w["walk_id"] for w in run2["walks"]] == ["walk-0", "walk-1", "walk-2"]  # deterministic order
    assert run2["requests_used_total"] == 6  # 3 from run 1 + 3 from run 2


def test_manifest_report_hash_mismatch_refuses_to_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a")])
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "report_version": enumerate_live.REPORT_VERSION,
                "manifest_sha256": "not-the-real-hash",
                "walks": [],
            }
        ),
        encoding="utf-8",
    )
    _write_token(tmp_path / "driver-token")

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("must not call the network on a hash mismatch")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2
    assert "refusing to resume against a mismatched walk set" in caplog.text


def test_report_version_mismatch_refuses_before_any_network_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a")])
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps({"manifest_sha256": enumerate_live.manifest_digest(enumerate_live.load_manifest(manifest)), "walks": []}),
        encoding="utf-8",
    )
    _write_token(tmp_path / "driver-token")

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("version mismatch must not call evaluate or health")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    monkeypatch.setattr(enumerate_live, "_get_health", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2
    assert str(report) in caplog.text
    assert "report_version='missing'" in caplog.text
    assert f"REPORT_VERSION={enumerate_live.REPORT_VERSION}" in caplog.text


def test_report_version_stale_integer_refuses_before_any_network_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Council LOW finding (kimi, on B2''-b): the sibling test above only
    proves the "missing" branch of V2's refusal; an explicit STALE integer
    (not just an absent key) is a separate code path through the same
    ``!=`` comparison and was untested.
    """

    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a")])
    report = tmp_path / "report.json"
    stale_version = 1
    report.write_text(
        json.dumps(
            {
                "report_version": stale_version,
                "manifest_sha256": enumerate_live.manifest_digest(enumerate_live.load_manifest(manifest)),
                "walks": [],
            }
        ),
        encoding="utf-8",
    )
    _write_token(tmp_path / "driver-token")

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("version mismatch must not call evaluate or health")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    monkeypatch.setattr(enumerate_live, "_get_health", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2
    assert str(report) in caplog.text
    assert f"report_version={stale_version!r}" in caplog.text
    assert f"REPORT_VERSION={enumerate_live.REPORT_VERSION}" in caplog.text


def test_duplicate_walk_labels_refuse_before_any_network_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Council finding, independently corroborated (codex MEDIUM + kimi LOW
    on B2''-b): ``walks_by_id`` is keyed on label, so two walks sharing one
    label would collapse into a single report row while BOTH still get
    POSTed to production. Fail closed before any token load or network call.
    """

    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("dup", "a"), _walk("dup", "b")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("duplicate labels must not call evaluate or health")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    monkeypatch.setattr(enumerate_live, "_get_health", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2
    assert "duplicate walk label" in caplog.text
    assert "'dup'" in caplog.text
    assert not report.exists()


# ---------------------------------------------------------------------------
# B2''-c -- wire-shape pre-flight: the engine would 422 on these, so the
# runner refuses them itself, before the token and before any request
# (evaluate OR health), in --dry-run and live alike.
# ---------------------------------------------------------------------------


def test_wire_shape_bad_assessment_id_refuses_before_token_and_network_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """GUILT (a): the exact manifest that tripped the production breaker at
    request 3 -- assessment_id="x" is the mouth emitter's hardcoded
    placeholder, not a UUID. No driver-token file is written at all: if the
    pre-flight ran after the token load, this would surface "driver token
    file not found" instead of the walk-shape refusal.
    """

    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("baseline/all-default", assessment_id="x")])
    report = tmp_path / "report.json"

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("a rejected wire shape must not call evaluate or health")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    monkeypatch.setattr(enumerate_live, "_get_health", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2
    assert "baseline/all-default" in caplog.text
    assert "assessment_id" in caplog.text
    assert "driver token file not found" not in caplog.text
    assert not report.exists()


def test_wire_shape_bad_assessment_id_refuses_before_token_and_network_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """GUILT (b): the SAME manifest as the live test above, under --dry-run.
    On the merge-base this printed `pending=1` (the cause this PR closes --
    see the merge-base proof pasted in the PR body); the pre-flight now runs
    in --dry-run too, so it refuses identically to the live path.
    """

    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("baseline/all-default", assessment_id="x")])
    report = tmp_path / "report.json"

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("--dry-run must never call evaluate or health either")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    monkeypatch.setattr(enumerate_live, "_get_health", no_network)
    args = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25) + ["--dry-run"]
    )

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2
    assert "baseline/all-default" in caplog.text
    assert "assessment_id" in caplog.text
    assert "driver token file not found" not in caplog.text
    assert not report.exists()


def test_wire_shape_collected_at_without_offset_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """GUILT (c): a naive datetime string (no 'Z', no '+00:00') mirrors
    exactly what models.py's _validate_utc rejects."""

    manifest = tmp_path / "manifest.json"
    walk = _walk("a")
    walk["collected_at"] = "2026-09-06T00:00:00"
    _write_manifest(manifest, [walk])
    report = tmp_path / "report.json"

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("a rejected wire shape must not call evaluate or health")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    monkeypatch.setattr(enumerate_live, "_get_health", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2
    assert "collected_at" in caplog.text
    assert "'a'" in caplog.text
    assert not report.exists()


def test_wire_shape_wrong_schema_version_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """GUILT (d): a manifest built against a future/other schema version."""

    manifest = tmp_path / "manifest.json"
    walk = _walk("a")
    walk["schema_version"] = "2.0.0"
    _write_manifest(manifest, [walk])
    report = tmp_path / "report.json"

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("a rejected wire shape must not call evaluate or health")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    monkeypatch.setattr(enumerate_live, "_get_health", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2
    assert "schema_version" in caplog.text
    assert "2.0.0" in caplog.text
    assert not report.exists()


def test_wire_shape_empty_facts_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """GUILT (e): an empty facts object -- the refusal names the walk and
    the field, never a facts VALUE (there is none to echo here, but the
    message never interpolates walk["facts"] at all)."""

    manifest = tmp_path / "manifest.json"
    walk = _walk("a")
    walk["facts"] = {}
    _write_manifest(manifest, [walk])
    report = tmp_path / "report.json"

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("a rejected wire shape must not call evaluate or health")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    monkeypatch.setattr(enumerate_live, "_get_health", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2
    assert "facts" in caplog.text
    assert "'a'" in caplog.text
    assert not report.exists()


def test_wire_shape_non_list_disclosed_review_flags_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Extra coverage beyond the five named guilt cases: the optional
    disclosed_review_flags field, when present, must be a list of strings."""

    manifest = tmp_path / "manifest.json"
    walk = _walk("a")
    walk["disclosed_review_flags"] = "not-a-list"
    _write_manifest(manifest, [walk])
    report = tmp_path / "report.json"

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("a rejected wire shape must not call evaluate or health")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    monkeypatch.setattr(enumerate_live, "_get_health", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2
    assert "disclosed_review_flags" in caplog.text
    assert not report.exists()


def test_wire_shape_valid_uuid4_and_flags_pass_preflight_and_dry_run_still_prints_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """INNOCENCE: a well-formed walk (uuid4 id, 'Z' timestamp, non-empty
    facts, a list-of-strings disclosed_review_flags) passes extract_walks
    unchanged and --dry-run still prints its plan -- this PR narrows what a
    malformed manifest can do, not what a well-formed one can.
    """

    import uuid as _uuid

    manifest = tmp_path / "manifest.json"
    walk = _walk("a", assessment_id=str(_uuid.uuid4()))
    walk["disclosed_review_flags"] = ["DISCLOSED_HEALTH_CONCERN_CONDITION"]
    _write_manifest(manifest, [walk])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("--dry-run must never call the network")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    args = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=60, rate_per_minute=25) + ["--dry-run"]
    )

    assert enumerate_live.run(args) == 0
    assert "pending=1" in capsys.readouterr().out


def test_dry_run_reports_version_mismatch_before_a_bad_token_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Council MEDIUM finding (codex, on B2''-b): the dry-run branch
    previously loaded the driver token BEFORE checking report_version/digest,
    so a version-mismatched report combined with an invalid token file
    surfaced the unrelated token error instead of V2's own refusal line --
    masking the more informative error. Precedence now matches the live
    path: version/digest first, token second.
    """

    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a")])
    report = tmp_path / "report.json"
    stale_version = 1
    report.write_text(
        json.dumps(
            {
                "report_version": stale_version,
                "manifest_sha256": enumerate_live.manifest_digest(enumerate_live.load_manifest(manifest)),
                "walks": [],
            }
        ),
        encoding="utf-8",
    )
    # No driver-token file written at all -- load_driver_token would raise
    # EnumerateLiveError("driver token file not found: ...") if it ran first.

    args = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25) + ["--dry-run"]
    )

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2
    assert f"report_version={stale_version!r}" in caplog.text
    assert "driver token file not found" not in caplog.text


# ---------------------------------------------------------------------------
# W3 -- exclusive one-runner-per-report lock
# ---------------------------------------------------------------------------


def test_second_runner_on_a_live_locked_report_refuses_with_one_line_never_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")

    lock_path = report.with_name(report.name + ".lock")
    lock = ReportLock(report)
    lock.acquire()

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("must not call the network while the lock is held by a live pid")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    try:
        with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
            exit_code = enumerate_live.run(args)
    finally:
        lock.release()

    assert exit_code == 2
    assert "another run owns" in caplog.text
    assert not report.exists()  # no write ever happened
    assert lock_path.exists()  # the live lock is untouched, not stolen


def test_report_lock_error_is_caught_before_evaluate_or_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")
    lock = ReportLock(report)
    lock.acquire()

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("lock refusal must precede evaluate and health")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    monkeypatch.setattr(enumerate_live, "_get_health", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))
    try:
        with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
            assert enumerate_live.run(args) == 2
    finally:
        lock.release()
    assert "report.json.lock" in caplog.text
    assert "Traceback" not in caplog.text
    assert not report.exists()


def test_lock_is_released_after_a_run_so_a_second_run_can_proceed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")
    lock_path = report.with_name(report.name + ".lock")

    async def fake_post(*_a: object, **_k: object) -> _Response:
        return _engine_response()

    monkeypatch.setattr(enumerate_live, "_post_evaluate", fake_post)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    assert enumerate_live.run(args) == 0
    assert lock_path.exists()
    assert enumerate_live.run(args) == 0  # second, sequential run: nothing pending, still clean
    assert lock_path.exists()


def test_v1_counters_are_flushed_before_sigkill_and_accumulate_on_resume(tmp_path: Path) -> None:
    """A SIGKILL may race one in-flight request, so one request of tolerance is allowed."""

    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk(str(i)) for i in range(4)])
    report = tmp_path / "report.json"
    token = tmp_path / "driver-token"
    count = tmp_path / "evaluate-count"
    _write_token(token)
    child_script = tmp_path / "runner.py"
    child_script.write_text(
        "import asyncio, json, pathlib, sys\n"
        "from backend.scripts.visa_engine import enumerate_live as m\n"
        "class R:\n"
        "  status_code = 200\n"
        "  headers = {}\n"
        "  def json(self): return {'mode':'CURATED','decision':{'state':'SUPPORTED_CANDIDATES','review_reasons':[],'no_path_reasons':[],'notices':[],'rule_pack':{}}}\n"
        "async def post(*a, **k):\n"
        f"  p = pathlib.Path({str(count)!r}); p.write_text(str(int(p.read_text() or '0') + 1) if p.exists() else '1')\n"
        "  await asyncio.sleep(0.2); return R()\n"
        "async def health(*a, **k): return R()\n"
        "m._post_evaluate = post; m._get_health = health\n"
        "raise SystemExit(m.main(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    base = [
        sys.executable,
        str(child_script),
        "--manifest",
        str(manifest),
        "--report",
        str(report),
        "--driver-token-file",
        str(token),
        "--max-requests",
        "10",
        "--rate-per-minute",
        "29",
    ]
    backend_root = Path(__file__).parents[4]
    env = dict(os.environ, PYTHONPATH=str(backend_root))
    child = subprocess.Popen(base, cwd=backend_root, env=env)
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if report.exists() and len(json.loads(report.read_text())["walks"]) >= 2:
                break
            time.sleep(0.05)
        else:
            raise AssertionError("subprocess did not flush two walks before the deadline")
        child.kill()
        child.wait(timeout=10)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)

    first = json.loads(report.read_text())
    counted_at_kill = int(count.read_text())
    assert first["requests_used_this_run"] > 0
    assert abs(first["requests_used_this_run"] - counted_at_kill) <= 1

    resumed = subprocess.run(base, cwd=backend_root, env=env, check=False)
    assert resumed.returncode == 0
    final = json.loads(report.read_text())
    assert final["requests_used_total"] == int(count.read_text())


def test_v1_counters_track_a_retry_still_inside_one_unresolved_walk(tmp_path: Path) -> None:
    """Council guilt test (codex HIGH finding on B2''-b): the original
    per-walk-only flush left the report at 0 for a walk that burned a failed
    attempt and was then killed DURING the backoff sleep before its retry --
    the failed attempt was real (the server saw it) but never resolved to a
    terminal WalkResult, so the per-walk ``_flush()`` never ran. The cure
    flushes counters at every retry's ``continue`` point (run_walk's
    ``on_reserve`` hook), not just once per resolved walk. This test proves
    the on-disk count reflects the ONE failed-but-settled attempt, not 0,
    while the process is parked in the backoff sleep after it and before the
    retry -- the exact window codex named as untested by the SIGKILL test
    above (which only waits for two COMPLETED walks).
    """

    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("only-walk")])
    report = tmp_path / "report.json"
    token = tmp_path / "driver-token"
    count = tmp_path / "evaluate-count"
    backoff_started = tmp_path / "backoff-started"
    _write_token(token)
    child_script = tmp_path / "runner.py"
    child_script.write_text(
        "import asyncio, json, pathlib, sys\n"
        "from backend.scripts.visa_engine import enumerate_live as m\n"
        "class R:\n"
        "  def __init__(self, status): self.status_code = status; self.headers = {}\n"
        "  def json(self): return {'mode':'CURATED','decision':{'state':'SUPPORTED_CANDIDATES','review_reasons':[],'no_path_reasons':[],'notices':[],'rule_pack':{}}}\n"
        "async def post(*a, **k):\n"
        f"  p = pathlib.Path({str(count)!r}); n = int(p.read_text() or '0') + 1 if p.exists() else 1; p.write_text(str(n))\n"
        "  return R(500 if n == 1 else 200)\n"
        "async def health(*a, **k): return R(200)\n"
        "async def marked_sleep(seconds):\n"
        f"  pathlib.Path({str(backoff_started)!r}).write_text('1')\n"
        "  await asyncio.sleep(seconds)\n"
        "m._post_evaluate = post; m._get_health = health; m._sleep = marked_sleep\n"
        "raise SystemExit(m.main(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    base = [
        sys.executable,
        str(child_script),
        "--manifest",
        str(manifest),
        "--report",
        str(report),
        "--driver-token-file",
        str(token),
        "--max-requests",
        "10",
        "--rate-per-minute",
        "29",
        "--max-retries",
        "1",
        "--backoff-seconds",
        "20",
    ]
    backend_root = Path(__file__).parents[4]
    env = dict(os.environ, PYTHONPATH=str(backend_root))
    child = subprocess.Popen(base, cwd=backend_root, env=env)
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if backoff_started.exists():
                break
            time.sleep(0.02)
        else:
            raise AssertionError("subprocess never entered the post-failure backoff sleep before the deadline")
        # The failed attempt's on_reserve flush runs BEFORE _sleep is awaited
        # (see run_walk), so by the time marked_sleep's marker file exists,
        # the flush for attempt 1 has already landed on disk.
        child.kill()
        child.wait(timeout=10)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)

    assert count.read_text() == "1"  # server saw exactly the one failed attempt
    saved = json.loads(report.read_text())
    assert saved["requests_used_this_run"] == 1  # NOT 0 -- the pre-cure bug this test pins
    assert saved["requests_used_total"] == 1
    assert saved["walks"] == []  # the walk itself never resolved -- only the counters are ahead of it


# ---------------------------------------------------------------------------
# W4 -- cumulative requests_used, health probes declared outside the budget
# ---------------------------------------------------------------------------


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
    args = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=2, rate_per_minute=25, max_consecutive_harness_reds=2)
    )

    assert enumerate_live.run(args) == 1
    saved = json.loads(report.read_text())
    assert len(saved["walks"]) == 2
    assert saved["stopped_reason"] == "max_requests_exhausted"
    assert saved["requests_used_this_run"] == 2
    assert saved["requests_used_total"] == 2


def test_requests_used_total_accumulates_across_resumes_while_this_run_is_per_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a"), _walk("b")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")

    async def fake_post(*_a: object, **_k: object) -> _Response:
        return _engine_response()

    monkeypatch.setattr(enumerate_live, "_post_evaluate", fake_post)

    args1 = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=1, rate_per_minute=25, max_consecutive_harness_reds=1)
    )
    assert enumerate_live.run(args1) == 1
    first = json.loads(report.read_text())
    assert first["requests_used_this_run"] == 1
    assert first["requests_used_total"] == 1

    args2 = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))
    assert enumerate_live.run(args2) == 0
    second = json.loads(report.read_text())
    assert second["requests_used_this_run"] == 1  # only walk "b" was pending this run
    assert second["requests_used_total"] == 2  # cumulative across both runs


def test_health_probes_declared_outside_budget_everywhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")

    async def fake_post(*_a: object, **_k: object) -> _Response:
        return _engine_response()

    monkeypatch.setattr(enumerate_live, "_post_evaluate", fake_post)
    args = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=1, rate_per_minute=25, max_consecutive_harness_reds=1)
    )

    assert enumerate_live.run(args) == 0
    saved = json.loads(report.read_text())
    assert saved["health"]["probes_outside_budget"] == 2
    assert saved["requests_used_this_run"] == 1  # the 2 health GETs are not in this count


# ---------------------------------------------------------------------------
# Cross-cutting: PII / secrecy / summary shape
# ---------------------------------------------------------------------------


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
