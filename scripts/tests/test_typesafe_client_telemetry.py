from __future__ import annotations

import json
import time
import urllib.error

import lint_paid_llm_entity as lint
import typesafe_client as tc


class _Response:
    def __init__(self, body: dict | bytes):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self._body


class _Opener:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = 0

    def open(self, *args, **kwargs):
        self.calls += 1
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return _Response(outcome)


class _LateOpener:
    def __init__(self, budget):
        self.budget = budget

    def open(self, *args, **kwargs):
        self.budget.started_at -= self.budget.total_deadline_s + 1
        return _Response({"answers": {"q": {"type": "noul", "noul": 0.9}}})


class _DripOpener:
    def open(self, *args, **kwargs):
        time.sleep(0.2)
        return _Response({"answers": {"q": {"type": "noul", "noul": 0.9}}})


def _authorize(monkeypatch) -> None:
    monkeypatch.setenv(tc.ENV_VAR, "test-only")
    monkeypatch.setattr(tc, "authorized", lambda: True)


def test_unavailable_is_not_an_attempt_or_zero_usage(monkeypatch):
    monkeypatch.delenv(tc.ENV_VAR, raising=False)
    result = tc.ask_detailed({"x": 1}, {"q": {"type": "noul"}})

    assert result.answers is None
    assert result.telemetry == {
        "attempted": False,
        "response_received": False,
        "schema_valid": False,
        "abstained": False,
        "failure": "no_key",
        "requested_model": tc.MODEL,
        "resolved_model": None,
        "usage": {"input_tokens": None, "output_tokens": None},
        "latency_ms": 0.0,
        "http_attempts": 0,
        "fallback": True,
    }


def test_valid_response_reports_model_usage_and_distinct_states(monkeypatch):
    _authorize(monkeypatch)
    opener = _Opener(
        [
            {
                "model": "jev-1.13.0-build.7",
                "answers": {"q": {"type": "noul", "noul": 0.9}},
                "usage": {"input_tokens": 123, "output_tokens": 7},
            }
        ]
    )
    monkeypatch.setattr(tc, "_OPENER", opener)

    result = tc.ask_detailed({"x": 1}, {"q": {"type": "noul"}})

    assert result.answers == {"q": {"type": "noul", "noul": 0.9}}
    assert result.telemetry["attempted"] is True
    assert result.telemetry["response_received"] is True
    assert result.telemetry["schema_valid"] is True
    assert result.telemetry["abstained"] is False
    assert result.telemetry["failure"] is None
    assert result.telemetry["requested_model"] == tc.MODEL
    assert result.telemetry["resolved_model"] == "jev-1.13.0-build.7"
    assert result.telemetry["usage"] == {"input_tokens": 123, "output_tokens": 7}
    assert result.telemetry["http_attempts"] == 1
    assert result.telemetry["fallback"] is False
    assert result.telemetry["latency_ms"] >= 0.0


def test_valid_empty_answers_is_abstention_not_schema_failure(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(tc, "_OPENER", _Opener([{"answers": {}, "usage": {}}]))

    result = tc.ask_detailed({"x": 1}, {"q": {"type": "noul"}})

    assert result.answers == {}
    assert result.telemetry["response_received"] is True
    assert result.telemetry["schema_valid"] is True
    assert result.telemetry["abstained"] is True
    assert result.telemetry["failure"] is None
    assert result.telemetry["fallback"] is True


def test_unusable_requested_answer_is_abstention_not_a_judgment(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(tc, "_OPENER", _Opener([{"answers": {"q": {}}}]))

    result = tc.ask_detailed({"x": 1}, {"q": {"type": "noul"}})

    assert result.answers == {"q": {}}
    assert result.telemetry["response_received"] is True
    assert result.telemetry["schema_valid"] is True
    assert result.telemetry["abstained"] is True
    assert result.telemetry["failure"] is None
    assert result.telemetry["fallback"] is True


def test_malformed_envelope_is_received_but_not_schema_valid(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(tc, "_OPENER", _Opener([{"model": tc.MODEL}]))
    budget = tc.RequestBudget(total_deadline_s=1.0, max_http_attempts=1)

    result = tc.ask_detailed(
        {"x": 1}, {"q": {"type": "noul"}}, budget=budget
    )

    assert result.answers is None
    assert result.telemetry["attempted"] is True
    assert result.telemetry["response_received"] is True
    assert result.telemetry["schema_valid"] is False
    assert result.telemetry["failure"] == "invalid_schema"
    assert result.telemetry["fallback"] is True


def test_malformed_envelope_is_not_retried(monkeypatch):
    _authorize(monkeypatch)
    opener = _Opener([{"model": tc.MODEL}, {"answers": {}}])
    monkeypatch.setattr(tc, "_OPENER", opener)

    result = tc.ask_detailed({"x": 1}, {"q": {"type": "noul"}})

    assert result.telemetry["failure"] == "invalid_schema"
    assert opener.calls == 1


def test_shared_attempt_budget_prevents_a_second_batch(monkeypatch):
    _authorize(monkeypatch)
    err = urllib.error.HTTPError(tc.ENDPOINT, 429, "retry", {}, None)
    opener = _Opener([err])
    monkeypatch.setattr(tc, "_OPENER", opener)
    budget = tc.RequestBudget(total_deadline_s=2.0, max_http_attempts=1)

    first = tc.ask_detailed({"batch": 1}, {"q": {}}, budget=budget)
    second = tc.ask_detailed({"batch": 2}, {"q": {}}, budget=budget)

    assert first.telemetry["http_attempts"] == 1
    assert first.telemetry["failure"] == "retry_budget_exhausted"
    assert second.telemetry["attempted"] is False
    assert second.telemetry["failure"] == "retry_budget_exhausted"
    assert opener.calls == 1


def test_late_response_is_received_but_discarded(monkeypatch):
    _authorize(monkeypatch)
    budget = tc.RequestBudget(total_deadline_s=1.0, max_http_attempts=1)
    monkeypatch.setattr(tc, "_OPENER", _LateOpener(budget))

    result = tc.ask_detailed({"x": 1}, {"q": {"type": "noul"}}, budget=budget)

    assert result.answers is None
    assert result.telemetry["response_received"] is True
    assert result.telemetry["schema_valid"] is False
    assert result.telemetry["failure"] == "deadline_exhausted"


def test_drip_response_cannot_extend_wall_deadline(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(tc, "_OPENER", _DripOpener())
    budget = tc.RequestBudget(total_deadline_s=0.03, max_http_attempts=1)
    started = time.monotonic()

    result = tc.ask_detailed({"x": 1}, {"q": {"type": "noul"}}, budget=budget)

    assert time.monotonic() - started < 0.15
    assert result.answers is None
    assert result.telemetry["failure"] == "deadline_exhausted"


def test_lint_exposes_structured_call_state_not_only_asked(monkeypatch):
    _authorize(monkeypatch)
    telemetry = {
        "attempted": True,
        "response_received": True,
        "schema_valid": True,
        "abstained": False,
        "failure": None,
        "requested_model": tc.MODEL,
        "resolved_model": "jev-1.13.0-build.7",
        "usage": {"input_tokens": 91, "output_tokens": 4},
        "latency_ms": 12.3,
        "http_attempts": 1,
        "fallback": False,
    }
    monkeypatch.setattr(
        lint,
        "ask",
        lambda *args, **kwargs: tc.AskResult(
            {"wrapper_library": {"type": "noul", "noul": 0.91}}, telemetry
        ),
    )

    result = lint.judge_file("x.py", "import litellm\nmodel = 'claude-x'\n")

    assert result["asked"] is True
    assert result["typesafe"] == telemetry
    assert result["fired_routes"] == ["wrapper_library"]
