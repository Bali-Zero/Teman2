#!/usr/bin/env python3
"""Tests for `typesafe_client.ask_detailed()` and the lint's telemetry line.

`ask()` has always answered a question and thrown away everything else that
happened while answering it. `ask_detailed()` keeps the rest — mode, closed
reason, model identity, usage-or-unknown, attempts, elapsed time — WITHOUT
changing `ask()`'s observable behaviour. This file proves both halves: the
client's new path in isolation, and that `lint_paid_llm_entity.py` prints
exactly one compact telemetry line built from it without moving any verdict,
exit code or threshold.

Stubbing style follows `test_vendor_authorization_fence.py`: an authorized
listing on disk, a key via `monkeypatch.setenv`, and `tc._OPENER` replaced
with a scripted stub — never a real key, never network.
"""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lint_paid_llm_entity as lint  # noqa: E402
import typesafe_client as tc  # noqa: E402

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "paid_llm_entity" / "bench_cases.json").read_text()
)


class _Resp:
    """A stubbed HTTP response context manager whose `read()` returns fixed
    bytes."""

    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def read(self) -> bytes:
        return self._body


class _Opener:
    """Scripted transport: each `open()` pops the next outcome — a response
    to return, or an exception to raise."""

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)

    def open(self, *_a, **_k):
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _all_routes_answer(value: float) -> dict:
    return {route: {"type": "noul", "noul": value} for route in lint.ROUTE_QUESTIONS}


@pytest.fixture
def authorized(tmp_path, monkeypatch):
    """Key set AND endpoint listed on disk — the only state that lets
    `ask_detailed` reach the transport at all (successor to PR #6989)."""
    listing = tmp_path / "authorized_endpoints.json"
    listing.write_text(
        json.dumps(
            {
                "endpoints": [
                    {
                        "endpoint": tc.ENDPOINT,
                        "ruling": "test fixture",
                        "use": "test",
                        "paths": ["**"],
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(tc, "AUTHORIZATION", listing)
    monkeypatch.setenv(tc.ENV_VAR, "x")
    return listing


@pytest.fixture
def sleeps(monkeypatch):
    calls: list[float] = []
    monkeypatch.setattr(tc.time, "sleep", lambda s: calls.append(s))
    return calls


# ───────────────────────────────────────────────────────────── 1/2 — success


def test_success_reports_model_usage_and_attempts(monkeypatch, authorized, sleeps):
    body = json.dumps(
        {
            "model": tc.MODEL,
            "answers": {"route": {"type": "noul", "noul": 0.4}},
            "usage": {"input_tokens": 427, "output_tokens": 0},
        }
    ).encode("utf-8")
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))

    judgment = tc.ask_detailed({}, {})

    assert judgment.mode == "jev"
    assert judgment.reason is None
    assert judgment.attempts == 1
    assert judgment.model == tc.MODEL
    assert judgment.usage == {"input_tokens": 427, "output_tokens": 0}
    assert judgment.answers == {"route": {"type": "noul", "noul": 0.4}}

    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))
    assert tc.ask({}, {}) == judgment.answers


@pytest.mark.parametrize(
    "usage,expected",
    [
        (None, None),
        ({}, None),
        ({"input_tokens": True}, None),
        ({"input_tokens": -1}, None),
        ({"weird": 3}, None),
        ({"input_tokens": 10}, {"input_tokens": 10}),
    ],
    ids=["absent", "empty", "bool", "negative", "unknown-key", "partial"],
)
def test_usage_extraction_is_strict(monkeypatch, authorized, usage, expected):
    payload = {"model": tc.MODEL, "answers": {}}
    if usage is not None:
        payload["usage"] = usage
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(json.dumps(payload).encode())]))

    judgment = tc.ask_detailed({}, {})

    assert judgment.usage == expected
    if expected is None:
        assert judgment.usage is None, "absent usage must be None, never falsy 0 or {}"


@pytest.mark.parametrize(
    "model",
    ["with\nnewline", "x" * 200, "", 123, None],
    ids=["newline", "too-long", "empty", "not-a-string-int", "not-a-string-none"],
)
def test_unsafe_model_strings_become_none(monkeypatch, authorized, model):
    body = json.dumps({"model": model, "answers": {}}).encode()
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))

    assert tc.ask_detailed({}, {}).model is None


# ─────────────────────────────────────────────────────────────── 3 — malformed


def test_non_utf8_body_is_malformed_after_full_retry(monkeypatch, authorized, sleeps):
    class _BadResp(_Resp):
        def read(self) -> bytes:
            return b"\xff\xfe not utf-8"

    monkeypatch.setattr(tc, "_OPENER", _Opener([_BadResp(b"")] * tc.MAX_ATTEMPTS))

    judgment = tc.ask_detailed({}, {})

    assert judgment.mode == "degraded"
    assert judgment.reason == tc.MALFORMED
    assert judgment.attempts == tc.MAX_ATTEMPTS
    assert judgment.answers is None


def test_answers_not_a_dict_is_malformed_with_no_retry(monkeypatch, authorized, sleeps):
    body = json.dumps({"model": tc.MODEL, "answers": [1, 2]}).encode()
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))

    judgment = tc.ask_detailed({}, {})

    assert judgment.mode == "degraded"
    assert judgment.reason == tc.MALFORMED
    assert judgment.attempts == 1
    assert sleeps == [], "a body that parsed is not a transport failure worth retrying"


def test_json_list_body_is_malformed_after_full_retry(monkeypatch, authorized, sleeps):
    body = json.dumps([1, 2, 3]).encode()
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)] * tc.MAX_ATTEMPTS))

    judgment = tc.ask_detailed({}, {})

    assert judgment.mode == "degraded"
    assert judgment.reason == tc.MALFORMED
    assert judgment.attempts == tc.MAX_ATTEMPTS


def test_empty_answers_dict_is_jev_not_none(monkeypatch, authorized):
    body = json.dumps({"model": tc.MODEL, "answers": {}}).encode()
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))

    judgment = tc.ask_detailed({}, {})
    assert judgment.mode == "jev"
    assert judgment.answers == {}

    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))
    assert tc.ask({}, {}) == {}, "an empty answers map is a real answer, not silence"


# ──────────────────────────────────────── 4 — denied before serialization


@pytest.mark.parametrize(
    "authorize,set_key,expected_reason",
    [(False, True, "not_authorized"), (True, False, "no_key")],
    ids=["not-authorized", "no-key"],
)
def test_denied_never_serializes(monkeypatch, tmp_path, authorize, set_key, expected_reason):
    if authorize:
        listing = tmp_path / "authorized_endpoints.json"
        listing.write_text(
            json.dumps(
                {"endpoints": [{"endpoint": tc.ENDPOINT, "ruling": "t", "use": "t", "paths": ["**"]}]}
            )
        )
        monkeypatch.setattr(tc, "AUTHORIZATION", listing)
    else:
        monkeypatch.setattr(tc, "AUTHORIZATION", tmp_path / "does-not-exist.json")
    if set_key:
        monkeypatch.setenv(tc.ENV_VAR, "x")
    else:
        monkeypatch.delenv(tc.ENV_VAR, raising=False)

    def _explode(*_a, **_k):
        raise AssertionError("must not reach the transport while denied")

    monkeypatch.setattr(tc.json, "dumps", _explode)
    monkeypatch.setattr(tc._OPENER, "open", _explode)

    judgment = tc.ask_detailed({"file": {"content": "secret source"}}, {})

    assert judgment.mode == "local"
    assert judgment.reason == expected_reason
    assert judgment.attempts == 0
    assert judgment.usage is None


# ───────────────────────────────────────────────────── 5 — transient/transport


def _http(status: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(tc.ENDPOINT, status, "msg", None, None)


_BACKOFF_2X = [tc.BACKOFF_BASE_S, tc.BACKOFF_BASE_S * 2]

_TRANSIENT_CASES = [
    ([_http(429), None], 2, "jev", None, None, [tc.BACKOFF_BASE_S]),
    ([_http(429)] * tc.MAX_ATTEMPTS, tc.MAX_ATTEMPTS, "degraded", tc.RATE_LIMITED, 429, _BACKOFF_2X),
    ([_http(500)], 1, "degraded", tc.HTTP_ERROR, 500, []),
    ([urllib.error.URLError("x")] * tc.MAX_ATTEMPTS, tc.MAX_ATTEMPTS, "degraded", tc.TRANSPORT_ERROR, None, None),
    ([TimeoutError("t")] * tc.MAX_ATTEMPTS, tc.MAX_ATTEMPTS, "degraded", tc.TRANSPORT_ERROR, None, None),
]
_TRANSIENT_IDS = ["429-then-success", "429-exhausts", "500-no-retry", "urlerror-exhausts", "timeout-exhausts"]


@pytest.mark.parametrize(
    "outcomes,exp_attempts,exp_mode,exp_reason,exp_status,exp_sleeps", _TRANSIENT_CASES, ids=_TRANSIENT_IDS
)
def test_transient_and_transport_failures(
    monkeypatch, authorized, sleeps, outcomes, exp_attempts, exp_mode, exp_reason, exp_status, exp_sleeps
):
    """429 retries and eventually succeeds or exhausts; 500 never retries;
    a transport-level OSError (URLError, TimeoutError) retries like 429 but
    is a different reason code when it never recovers."""
    body = json.dumps({"model": tc.MODEL, "answers": {}}).encode()
    resolved = [_Resp(body) if o is None else o for o in outcomes]
    monkeypatch.setattr(tc, "_OPENER", _Opener(resolved))

    judgment = tc.ask_detailed({}, {})

    assert judgment.attempts == exp_attempts
    assert judgment.mode == exp_mode
    assert judgment.reason == exp_reason
    assert judgment.http_status == exp_status
    if exp_sleeps is not None:
        assert sleeps == exp_sleeps


# ───────────────────────────────────────────────────────────── 6 — monotonic


def test_elapsed_ms_uses_monotonic_only(monkeypatch, tmp_path):
    monkeypatch.setattr(tc, "AUTHORIZATION", tmp_path / "does-not-exist.json")
    monkeypatch.delenv(tc.ENV_VAR, raising=False)

    values = iter([100.0, 100.25])
    monkeypatch.setattr(tc.time, "monotonic", lambda: next(values))
    monkeypatch.setattr(
        tc.time, "time", lambda: (_ for _ in ()).throw(AssertionError("time.time read"))
    )

    judgment = tc.ask_detailed({}, {})

    assert judgment.elapsed_ms == 250
    assert judgment.mode == "local"


# ──────────────────────────────────────────────────────────────────── 7/8


_SCENARIOS = {
    "success": lambda: _Opener([_Resp(json.dumps({"model": tc.MODEL, "answers": {}}).encode())]),
    "malformed": lambda: _Opener([_Resp(json.dumps({"model": tc.MODEL, "answers": []}).encode())]),
    "transport-error": lambda: _Opener([urllib.error.URLError("x")] * tc.MAX_ATTEMPTS),
}


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_ask_matches_ask_detailed_and_elapsed_is_sane(monkeypatch, authorized, sleeps, name):
    """No leak (7) is its own test below; this covers elapsed_ms's basic
    shape and ask()/ask_detailed() parity (8) across every failure family."""
    monkeypatch.setattr(tc, "_OPENER", _SCENARIOS[name]())
    judgment = tc.ask_detailed({}, {})
    assert isinstance(judgment.elapsed_ms, int)
    assert judgment.elapsed_ms >= 0
    monkeypatch.setattr(tc, "_OPENER", _SCENARIOS[name]())
    assert tc.ask({}, {}) == judgment.answers


def test_nothing_sensitive_reaches_telemetry_or_repr(monkeypatch, authorized, sleeps):
    state = {"content": "STATE_MARKER_never_leaks"}
    questions = {"QUESTIONS_MARKER_never_leaks": {}}
    key_marker = "KEY_MARKER_never_leaks"
    body_marker = "BODY_MARKER_never_leaks"
    exc_marker = "EXC_MARKER_never_leaks"
    monkeypatch.setenv(tc.ENV_VAR, key_marker)

    body = json.dumps({"model": tc.MODEL, "answers": {}, "note": body_marker}).encode()
    monkeypatch.setattr(tc, "_OPENER", _Opener([urllib.error.URLError(exc_marker), _Resp(body)]))

    judgment = tc.ask_detailed(state, questions)
    dumped = json.dumps(judgment.telemetry())

    for marker in (
        "STATE_MARKER_never_leaks",
        "QUESTIONS_MARKER_never_leaks",
        key_marker,
        body_marker,
        exc_marker,
    ):
        assert marker not in dumped
        assert marker not in repr(judgment)


# ───────────────────────────────────────────────── 9 — the stubbed CI path


def test_lint_main_reports_telemetry_for_an_innocent_file(
    monkeypatch, authorized, sleeps, tmp_path, capsys
):
    monkeypatch.setattr(lint, "in_scope", lambda path: True)
    marker = "UNIQUE_FILE_CONTENT_MARKER_9f2a"
    target = tmp_path / "changed.py"
    target.write_text(f"resp = requests.post(url, json={{'x': 1}})  # {marker}\n")

    body = json.dumps(
        {"model": tc.MODEL, "answers": _all_routes_answer(0.0), "usage": {"input_tokens": 11}}
    ).encode("utf-8")
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))

    rc = lint.main([str(target)])
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.startswith("lint_paid_llm_entity: jev-telemetry ")]
    assert len(lines) == 1
    payload = json.loads(lines[0].removeprefix("lint_paid_llm_entity: jev-telemetry "))

    assert rc == 0
    assert payload["service"] == "available"
    assert payload["asked"] == 1
    assert payload["answered"] == 1
    assert payload["unavailable"] == 0
    assert payload["attempts"] == 1
    assert payload["input_tokens"] == 11
    assert isinstance(payload["elapsed_ms"], int)
    assert marker not in lines[0]


def test_lint_main_reports_telemetry_when_transport_fails(
    monkeypatch, authorized, sleeps, tmp_path, capsys
):
    monkeypatch.setattr(lint, "in_scope", lambda path: True)
    target = tmp_path / "changed.py"
    target.write_text("resp = requests.post(url, json={'x': 1})\n")
    monkeypatch.setattr(tc, "_OPENER", _Opener([urllib.error.URLError("boom")] * tc.MAX_ATTEMPTS))

    rc = lint.main([str(target)])
    out = capsys.readouterr().out
    line = next(l for l in out.splitlines() if l.startswith("lint_paid_llm_entity: jev-telemetry "))
    payload = json.loads(line.removeprefix("lint_paid_llm_entity: jev-telemetry "))

    assert rc == 0, "silence is no opinion, never a violation on its own"
    assert payload["unavailable"] == 1
    assert payload["reasons"] == {"transport_error": 1}
    assert payload["input_tokens"] is None
    assert payload["attempts"] == tc.MAX_ATTEMPTS


def test_lint_main_keeps_grep_verdict_when_service_is_silent(
    monkeypatch, authorized, sleeps, tmp_path
):
    monkeypatch.setattr(lint, "in_scope", lambda path: True)
    case = next(c for c in CASES["guilt"] if c["name"].startswith("canonical_constructor"))
    target = tmp_path / "changed.py"
    target.write_text(case["content"])
    monkeypatch.setattr(tc, "_OPENER", _Opener([urllib.error.URLError("boom")] * tc.MAX_ATTEMPTS))

    rc = lint.main([str(target)])

    assert rc == 1, "the grep verdict must never be cleared by a silent model"


def test_lint_main_json_mode_carries_per_file_and_summary_telemetry(
    monkeypatch, authorized, sleeps, tmp_path, capsys
):
    monkeypatch.setattr(lint, "in_scope", lambda path: True)
    target = tmp_path / "changed.py"
    target.write_text("resp = requests.post(url, json={'x': 1})\n")
    body = json.dumps(
        {"model": tc.MODEL, "answers": _all_routes_answer(0.0), "usage": {"input_tokens": 3}}
    ).encode("utf-8")
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))

    rc = lint.main(["--json", str(target)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["results"][0]["jev"]["mode"] == "jev"
    assert "jev_telemetry" in payload


def test_lint_main_telemetry_service_is_no_key_when_key_absent(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(tc.ENV_VAR, raising=False)
    monkeypatch.setattr(lint, "in_scope", lambda path: True)
    target = tmp_path / "changed.py"
    target.write_text("x = 1\n")

    rc = lint.main([str(target)])
    out = capsys.readouterr().out
    line = next(l for l in out.splitlines() if l.startswith("lint_paid_llm_entity: jev-telemetry "))
    payload = json.loads(line.removeprefix("lint_paid_llm_entity: jev-telemetry "))

    assert rc == 0
    assert payload["service"] == "no_key"
    assert payload["asked"] == 0
