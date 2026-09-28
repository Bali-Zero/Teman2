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

import io
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
    assert judgment.http_status is None
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
        ({"input_tokens": 10.9}, None),
        ({"weird": 3}, None),
        ({"input_tokens": 10}, {"input_tokens": 10}),
    ],
    ids=["absent", "empty", "bool", "negative", "float", "unknown-key", "partial"],
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
    "model,expected",
    [
        (tc.MODEL, tc.MODEL),
        ("jev-9.9.9", tc.UNEXPECTED_MODEL),  # a plausible OTHER pinned version
        ("KEYMARKER123", tc.UNEXPECTED_MODEL),  # short, alnum, looks harmless
        ("x" * 64, tc.UNEXPECTED_MODEL),
        (123, None),
        (None, None),
    ],
    ids=["pinned", "other-version", "key-shaped", "64-char-alnum", "not-a-string-int", "not-a-string-none"],
)
def test_model_extraction_is_an_allowlist(monkeypatch, authorized, model, expected):
    """An allowlist, not a shape check: the field exists to reveal a vendor
    serving a version other than the calibrated pin, never to echo the
    vendor's own string — a regex bound on length/alphabet would still let a
    compromised endpoint smuggle a key or state marker into CI logs."""
    body = json.dumps({"model": model, "answers": {}}).encode()
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))

    assert tc.ask_detailed({}, {}).model == expected


def test_an_unexpected_model_string_never_reaches_telemetry_repr_or_the_lint_summary(
    monkeypatch, authorized, tmp_path, capsys
):
    """Proves the LEAK is closed, not just that the field says "unexpected":
    the marker itself must not survive into `telemetry()`, `repr()`, or the
    lint's own printed summary line."""
    marker = "KEYMARKER123"
    body = json.dumps({"model": marker, "answers": _all_routes_answer(0.0)}).encode()
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))

    judgment = tc.ask_detailed({}, {})
    assert judgment.model == tc.UNEXPECTED_MODEL
    assert marker not in json.dumps(judgment.telemetry())
    assert marker not in repr(judgment)

    monkeypatch.setattr(lint, "in_scope", lambda path: True)
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))
    target = tmp_path / "changed.py"
    target.write_text("resp = requests.post(url, json={'x': 1})\n")
    lint.main([str(target)])
    assert marker not in capsys.readouterr().out


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
    assert sleeps == [tc.BACKOFF_BASE_S, tc.BACKOFF_BASE_S * 2], (
        "exhausting retries on a broad Exception must still back off between attempts"
    )


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
    assert sleeps == [tc.BACKOFF_BASE_S, tc.BACKOFF_BASE_S * 2], (
        "exhausting retries on a broad Exception must still back off between attempts"
    )


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


def test_an_unmapped_unavailable_reason_never_raises(monkeypatch):
    """`ask()` promises it never raises. `REASON_CODES[reason_text]` would
    break that the day `unavailable_reason()` returns a THIRD sentence
    neither NO_KEY nor NOT_AUTHORIZED — the fallback (`UNAVAILABLE`) is what
    keeps that promise. Found in cross-family review of the first round."""
    monkeypatch.setattr(tc, "unavailable_reason", lambda: "a brand new silence")

    def _explode(*_a, **_k):
        raise AssertionError("must not reach the transport while unavailable")

    monkeypatch.setattr(tc.json, "dumps", _explode)

    judgment = tc.ask_detailed({}, {})

    assert tc.ask({}, {}) is None
    assert judgment.mode == "local"
    assert judgment.reason == tc.UNAVAILABLE
    assert judgment.attempts == 0


# ───────────────────────────────────────────────────── 5 — transient/transport


def _http(status: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(tc.ENDPOINT, status, "msg", None, None)


_BACKOFF_2X = [tc.BACKOFF_BASE_S, tc.BACKOFF_BASE_S * 2]

_TRANSIENT_CASES = [
    ([_http(429), None], 2, "jev", None, None, [tc.BACKOFF_BASE_S]),
    ([_http(429)] * tc.MAX_ATTEMPTS, tc.MAX_ATTEMPTS, "degraded", tc.RATE_LIMITED, 429, _BACKOFF_2X),
    # 529 is the OTHER member of RETRY_STATUS — nothing exercised it before,
    # so a mutant narrowing RETRY_STATUS to {429} survived.
    ([_http(529), None], 2, "jev", None, None, [tc.BACKOFF_BASE_S]),
    ([_http(529)] * tc.MAX_ATTEMPTS, tc.MAX_ATTEMPTS, "degraded", tc.RATE_LIMITED, 529, _BACKOFF_2X),
    ([_http(500)], 1, "degraded", tc.HTTP_ERROR, 500, []),
    ([urllib.error.URLError("x")] * tc.MAX_ATTEMPTS, tc.MAX_ATTEMPTS, "degraded", tc.TRANSPORT_ERROR, None, _BACKOFF_2X),
    ([TimeoutError("t")] * tc.MAX_ATTEMPTS, tc.MAX_ATTEMPTS, "degraded", tc.TRANSPORT_ERROR, None, None),
]
_TRANSIENT_IDS = [
    "429-then-success",
    "429-exhausts",
    "529-then-success",
    "529-exhausts",
    "500-no-retry",
    "urlerror-exhausts",
    "timeout-exhausts",
]


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

    # 100.0 -> 100.2506 is 250.6ms: ROUNDS to 251, a truncating `int()` alone
    # would give 250 — the gap that distinguishes the two implementations.
    values = iter([100.0, 100.2506])
    monkeypatch.setattr(tc.time, "monotonic", lambda: next(values))
    monkeypatch.setattr(
        tc.time, "time", lambda: (_ for _ in ()).throw(AssertionError("time.time read"))
    )

    judgment = tc.ask_detailed({}, {})

    assert judgment.elapsed_ms == 251
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


def test_nothing_sensitive_reaches_telemetry_or_repr_on_success(monkeypatch, authorized):
    state = {"content": "STATE_MARKER_never_leaks"}
    questions = {"QUESTIONS_MARKER_never_leaks": {}}
    key_marker = "KEY_MARKER_never_leaks"
    body_marker = "BODY_MARKER_never_leaks"
    monkeypatch.setenv(tc.ENV_VAR, key_marker)

    body = json.dumps({"model": tc.MODEL, "answers": {}, "note": body_marker}).encode()
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))

    judgment = tc.ask_detailed(state, questions)
    dumped = json.dumps(judgment.telemetry())

    for marker in ("STATE_MARKER_never_leaks", "QUESTIONS_MARKER_never_leaks", key_marker, body_marker):
        assert marker not in dumped
        assert marker not in repr(judgment)


def test_nothing_leaks_on_a_final_transport_failure(monkeypatch, authorized, sleeps):
    """The marker rides EVERY attempt, so it is present on the attempt that
    actually gives up — not just a retried one a mutant could leak from
    while still passing a test whose marker sat on an intermediate attempt
    that then succeeded."""
    exc_marker = "EXC_MARKER_final_transport_failure_never_leaks"
    monkeypatch.setattr(
        tc, "_OPENER", _Opener([urllib.error.URLError(exc_marker)] * tc.MAX_ATTEMPTS)
    )

    judgment = tc.ask_detailed({}, {})
    dumped = json.dumps(judgment.telemetry())

    assert judgment.reason == tc.TRANSPORT_ERROR
    assert exc_marker not in dumped
    assert exc_marker not in repr(judgment)


def test_nothing_leaks_on_a_final_http_error_with_a_body(monkeypatch, authorized):
    """`HTTPError.msg` and its `fp` body both carry a marker on the FINAL
    (non-retried) attempt — the shape a mutant storing `str(exc)` on the
    give-up path, rather than an intermediate retry, would be caught by."""
    msg_marker = "MSG_MARKER_final_http_error_never_leaks"
    body_marker = "BODY_MARKER_final_http_error_never_leaks"
    exc = urllib.error.HTTPError(
        tc.ENDPOINT, 500, msg_marker, None, io.BytesIO(body_marker.encode())
    )
    monkeypatch.setattr(tc, "_OPENER", _Opener([exc]))

    judgment = tc.ask_detailed({}, {})
    dumped = json.dumps(judgment.telemetry())

    assert judgment.reason == tc.HTTP_ERROR
    for marker in (msg_marker, body_marker):
        assert marker not in dumped
        assert marker not in repr(judgment)


@pytest.mark.parametrize(
    "value,should_fire",
    [(0.80, True), (0.7999, False)],
    ids=["at-threshold-fires", "just-below-does-not-fire"],
)
def test_fire_threshold_boundary_through_judge_file(monkeypatch, authorized, value, should_fire):
    """FIRE_THRESHOLD itself is unchanged (0.80) — pins the `>=` boundary
    through the real `judge_file` path rather than trusting it by reading."""
    body = json.dumps(
        {"model": tc.MODEL, "answers": {"wrapper_library": {"type": "noul", "noul": value}}}
    ).encode()
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))

    result = lint.judge_file("x.py", "resp = requests.post(url, json={'x': 1})\n")

    assert ("wrapper_library" in result["fired_routes"]) is should_fire


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

    # `Judgment.telemetry()`'s OWN key set, pinned so a mutant adding a field
    # (e.g. a raw "path") goes red here rather than silently widening what
    # ends up printed.
    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))
    telemetry_keys = set(tc.ask_detailed({}, {}).telemetry().keys())
    assert telemetry_keys == {
        "mode", "reason", "model", "usage", "elapsed_ms", "attempts", "http_status",
    }

    monkeypatch.setattr(tc, "_OPENER", _Opener([_Resp(body)]))
    rc = lint.main(["--json", str(target)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["results"][0]["jev"]["mode"] == "jev"
    assert set(payload["results"][0]["jev"].keys()) == telemetry_keys | {
        "routes_asked",
        "routes_answered",
    }
    assert "jev_telemetry" in payload


def test_lint_summary_tracks_elapsed_max_and_usage_unknown_across_files(
    monkeypatch, authorized, tmp_path, capsys
):
    monkeypatch.setattr(lint, "in_scope", lambda path: True)
    target_a = tmp_path / "a.py"
    target_a.write_text("resp = requests.post(url, json={'x': 1})\n")
    target_b = tmp_path / "b.py"
    target_b.write_text("resp = requests.post(url, json={'y': 2})\n")

    body_with_usage = json.dumps(
        {"model": tc.MODEL, "answers": _all_routes_answer(0.0), "usage": {"input_tokens": 5}}
    ).encode("utf-8")
    body_without_usage = json.dumps(
        {"model": tc.MODEL, "answers": _all_routes_answer(0.0)}
    ).encode("utf-8")
    monkeypatch.setattr(
        tc, "_OPENER", _Opener([_Resp(body_with_usage), _Resp(body_without_usage)])
    )

    # File A: start=0.0, elapsed sampled at 0.010 -> 10ms. File B: start=0.010
    # (the third scripted value), elapsed sampled at 0.035 -> 25ms. Two
    # distinct elapsed values so `elapsed_ms_max` (25) is provably the MAX,
    # not just the last or the sum.
    values = iter([0.0, 0.010, 0.010, 0.035])
    monkeypatch.setattr(tc.time, "monotonic", lambda: next(values))

    rc = lint.main([str(target_a), str(target_b)])
    out = capsys.readouterr().out
    line = next(l for l in out.splitlines() if l.startswith("lint_paid_llm_entity: jev-telemetry "))
    payload = json.loads(line.removeprefix("lint_paid_llm_entity: jev-telemetry "))

    assert rc == 0
    assert payload["elapsed_ms_max"] == 25
    assert payload["usage_unknown"] == 1
    assert payload["input_tokens"] == 5


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
