"""Unit tests for the internal Visa Oracle evaluate probe wrapper.

The wrapper is deliberately tested through its mocked HTTP seam.  These tests
must never call the deployed endpoint: a real call would write a shadow-ledger
row and could corrupt activation-gate evidence.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
import pytest

from backend.scripts.visa_engine import probe_evaluate


class _Response:
    def __init__(self, body: dict[str, Any], *, status_code: int = 200) -> None:
        self._body = body
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._body


def _write_token(path: Path, token: str = "test-driver-token-never-log") -> str:
    path.write_text(f"{token}\n", encoding="utf-8")
    path.chmod(0o600)
    return token


def _write_payload(path: Path) -> None:
    path.write_text('{"facts": {}}', encoding="utf-8")


def test_parse_args_defaults_to_synthetic_driver() -> None:
    args = probe_evaluate._parse_args(["--payload", "facts.json"])

    assert args.traffic_source is None
    assert args.as_real_i_know_what_i_am_doing is False
    assert probe_evaluate.resolve_traffic_source(args) == "synthetic_driver"


def test_real_traffic_source_requires_the_loud_opt_out() -> None:
    args = probe_evaluate._parse_args(["--payload", "facts.json", "--traffic-source", "real"])

    with pytest.raises(probe_evaluate.ProbeEvaluateError, match="as-real-i-know-what-i-am-doing"):
        probe_evaluate.resolve_traffic_source(args)

    opted_out = probe_evaluate._parse_args(
        [
            "--payload",
            "facts.json",
            "--as-real-i-know-what-i-am-doing",
        ]
    )
    assert probe_evaluate.resolve_traffic_source(opted_out) == "real"


def test_absent_token_file_fails_closed_without_network_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = tmp_path / "facts.json"
    _write_payload(payload)
    absent_token = tmp_path / "missing-driver-token"
    called = False

    async def no_network(**_kwargs: object) -> _Response:
        nonlocal called
        called = True
        raise AssertionError("network must not be called when token custody fails")

    monkeypatch.setattr(probe_evaluate, "_post_evaluate", no_network)
    args = probe_evaluate._parse_args(
        ["--payload", str(payload), "--driver-token-file", str(absent_token)]
    )

    with caplog.at_level(logging.ERROR, logger="visa_engine.probe_evaluate"):
        assert probe_evaluate.run(args) == 2

    assert called is False
    assert "refusing to fall back to traffic_source=real" in caplog.text


def test_synthetic_probe_constructs_authenticated_request_and_reports_pack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = _write_token(tmp_path / "driver-token")
    payload_path = tmp_path / "facts.json"
    _write_payload(payload_path)
    captured: dict[str, object] = {}

    async def fake_post(**kwargs: object) -> _Response:
        captured.update(kwargs)
        return _Response(
            {
                "mode": "CURATED",
                "decision": {
                    "state": "SUPPORTED_CANDIDATES",
                    "rule_pack": {
                        "rule_pack_id": "00000000-0000-0000-0000-000000000007",
                        "sequence": 7,
                        "version": "2026.8.11",
                    },
                },
            }
        )

    monkeypatch.setattr(probe_evaluate, "_post_evaluate", fake_post)
    argv = [
        "--url",
        "https://probe.example.test/api/visa-oracle/evaluate",
        "--payload",
        str(payload_path),
        "--driver-token-file",
        str(tmp_path / "driver-token"),
        "--request-category",
        "tourism",
    ]
    args = probe_evaluate._parse_args(argv)

    with caplog.at_level(logging.INFO, logger="visa_engine.probe_evaluate"):
        assert probe_evaluate.run(args) == 0

    assert captured == {
        "url": "https://probe.example.test/api/visa-oracle/evaluate",
        "params": {"traffic_source": "synthetic_driver", "request_category": "tourism"},
        "headers": {
            "Content-Type": "application/json",
            "X-Visa-Driver-Token": token,
        },
        "payload": {"facts": {}},
        "timeout": 30.0,
    }
    output = capsys.readouterr().out
    assert "state='SUPPORTED_CANDIDATES'" in output
    assert "sequence=7" in output
    assert "version='2026.8.11'" in output
    assert token not in argv
    assert token not in output
    assert token not in caplog.text


def test_full_body_prints_candidate_detail_the_small_summary_cannot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--full-body`` must print detail the default summary structurally
    cannot -- assert on a candidate/reason field, never on ``mode``/``state``
    which both paths print (a test that passes either way proves nothing).
    """

    token = _write_token(tmp_path / "driver-token")
    payload_path = tmp_path / "facts.json"
    _write_payload(payload_path)

    async def fake_post(**_kwargs: object) -> _Response:
        return _Response(
            {
                "mode": "CURATED",
                "decision": {
                    "state": "SUPPORTED_CANDIDATES",
                    "candidates": [
                        {
                            "product_code": "C1-VISIT-SINGLE",
                            "reason_codes": ["ELIGIBLE_STANDARD_PATH"],
                        }
                    ],
                    "rule_pack": {
                        "rule_pack_id": "00000000-0000-0000-0000-000000000007",
                        "sequence": 7,
                        "version": "2026.8.11",
                    },
                },
            }
        )

    monkeypatch.setattr(probe_evaluate, "_post_evaluate", fake_post)
    args = probe_evaluate._parse_args(
        [
            "--payload",
            str(payload_path),
            "--driver-token-file",
            str(tmp_path / "driver-token"),
            "--full-body",
        ]
    )

    assert probe_evaluate.run(args) == 0

    output = capsys.readouterr().out
    assert "C1-VISIT-SINGLE" in output
    assert "ELIGIBLE_STANDARD_PATH" in output
    assert token not in output


def test_full_body_redacts_driver_token_reflected_in_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The defense-in-depth redaction (misbehaving proxy reflects the
    driver-token header back in the response) must survive ``--full-body``
    exactly as it does for the small summary -- this is the test that
    matters most for this flag: it FAILS if a future change moves the
    redaction to only run on ``_summarize_response``'s output.
    """

    token = _write_token(tmp_path / "driver-token")
    payload_path = tmp_path / "facts.json"
    _write_payload(payload_path)

    async def reflecting_proxy(**_kwargs: object) -> _Response:
        return _Response(
            {
                "mode": "CURATED",
                "decision": {"state": "SUPPORTED_CANDIDATES", "rule_pack": None},
                # A misbehaving proxy reflecting the request headers back
                # into the body -- exactly the shape the module docstring's
                # "defense in depth" comment guards against.
                "echoed_headers": {"X-Visa-Driver-Token": token},
            }
        )

    monkeypatch.setattr(probe_evaluate, "_post_evaluate", reflecting_proxy)
    args = probe_evaluate._parse_args(
        [
            "--payload",
            str(payload_path),
            "--driver-token-file",
            str(tmp_path / "driver-token"),
            "--full-body",
        ]
    )

    assert probe_evaluate.run(args) == 0

    output = capsys.readouterr().out
    assert token not in output
    assert "[REDACTED]" in output


def test_default_behaviour_unchanged_without_the_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No ``--full-body`` (and no env override): output stays the small
    summary -- the candidate/reason detail from the full body must NOT
    appear.
    """

    monkeypatch.delenv(probe_evaluate.FULL_BODY_ENV, raising=False)
    token = _write_token(tmp_path / "driver-token")
    payload_path = tmp_path / "facts.json"
    _write_payload(payload_path)

    async def fake_post(**_kwargs: object) -> _Response:
        return _Response(
            {
                "mode": "CURATED",
                "decision": {
                    "state": "SUPPORTED_CANDIDATES",
                    "candidates": [{"product_code": "C1-VISIT-SINGLE"}],
                    "rule_pack": {
                        "rule_pack_id": "00000000-0000-0000-0000-000000000007",
                        "sequence": 7,
                        "version": "2026.8.11",
                    },
                },
            }
        )

    monkeypatch.setattr(probe_evaluate, "_post_evaluate", fake_post)
    args = probe_evaluate._parse_args(
        [
            "--payload",
            str(payload_path),
            "--driver-token-file",
            str(tmp_path / "driver-token"),
        ]
    )
    assert args.full_body is False

    assert probe_evaluate.run(args) == 0

    output = capsys.readouterr().out
    assert "state='SUPPORTED_CANDIDATES'" in output
    assert "sequence=7" in output
    assert "C1-VISIT-SINGLE" not in output
    assert token not in output


def test_transport_error_never_logs_driver_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = _write_token(tmp_path / "driver-token")
    payload = tmp_path / "facts.json"
    _write_payload(payload)

    async def token_reflecting_transport_error(**_kwargs: object) -> _Response:
        raise httpx.ConnectError(f"proxy reflected secret {token}")

    monkeypatch.setattr(probe_evaluate, "_post_evaluate", token_reflecting_transport_error)
    args = probe_evaluate._parse_args(
        ["--payload", str(payload), "--driver-token-file", str(tmp_path / "driver-token")]
    )

    with caplog.at_level(logging.ERROR, logger="visa_engine.probe_evaluate"):
        assert probe_evaluate.run(args) == 3

    assert token not in caplog.text
