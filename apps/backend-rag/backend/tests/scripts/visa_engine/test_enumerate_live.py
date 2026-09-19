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
from pathlib import Path
from typing import Any

import httpx
import pytest

from backend.scripts.visa_engine import enumerate_live


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
        "assessment_id": "x",
        "collected_at": "2026-01-01T00:00:00Z",
        "facts": {"some_question": "yes"},
    }
    assert saved["manifest_sha256"] == enumerate_live.manifest_digest(json.loads(manifest.read_text()))
    assert saved["stopped_reason"] == "completed"
    assert saved["requests_used_this_run"] == 1
    assert saved["requests_used_total"] == 1
    assert saved["health"]["probes_outside_budget"] == 2


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
    lock_path.write_text(json.dumps({"pid": os.getpid(), "started_at": "now"}), encoding="utf-8")

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("must not call the network while the lock is held by a live pid")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        exit_code = enumerate_live.run(args)

    assert exit_code == 2
    assert "another enumerate_live run owns" in caplog.text
    assert not report.exists()  # no write ever happened
    assert lock_path.exists()  # the live lock is untouched, not stolen


def test_stale_lock_is_refused_without_break_stale_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")

    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    dead_pid = dead.pid

    lock_path = report.with_name(report.name + ".lock")
    lock_path.write_text(json.dumps({"pid": dead_pid, "started_at": "then"}), encoding="utf-8")

    async def no_network(*_a: object, **_k: object) -> _Response:
        raise AssertionError("must not call the network on a stale lock without --break-stale-lock")

    monkeypatch.setattr(enumerate_live, "_post_evaluate", no_network)
    args = enumerate_live._parse_args(_args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25))

    with caplog.at_level(logging.ERROR, logger="visa_engine.enumerate_live"):
        assert enumerate_live.run(args) == 2
    assert "stale lock" in caplog.text
    assert "--break-stale-lock" in caplog.text


def test_break_stale_lock_removes_it_and_proceeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_walk("a")])
    report = tmp_path / "report.json"
    _write_token(tmp_path / "driver-token")

    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    lock_path = report.with_name(report.name + ".lock")
    lock_path.write_text(json.dumps({"pid": dead.pid, "started_at": "then"}), encoding="utf-8")

    async def fake_post(*_a: object, **_k: object) -> _Response:
        return _engine_response()

    monkeypatch.setattr(enumerate_live, "_post_evaluate", fake_post)
    args = enumerate_live._parse_args(
        _args(tmp_path, manifest, report, max_requests=10, rate_per_minute=25) + ["--break-stale-lock"]
    )

    assert enumerate_live.run(args) == 0
    assert not lock_path.exists()  # released in `finally` after the run completed
    saved = json.loads(report.read_text())
    assert saved["walks"][0]["classification"] == "engine_verdict"


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
    assert not lock_path.exists()
    assert enumerate_live.run(args) == 0  # second, sequential run: nothing pending, still clean
    assert not lock_path.exists()


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
