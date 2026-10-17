"""Retired Claude seats are never attempted; an unclassified failure on one
seat moves on to the next instead of stopping the chain."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mata_garuda.runtime import cli_runtime as cr

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    import os

    for key in list(os.environ):
        if key.startswith("CLAUDE_CODE_OAUTH_TOKEN"):
            monkeypatch.delenv(key)
    cr.reset_exhausted_tokens()
    yield
    cr.reset_exhausted_tokens()


def _stub(monkeypatch, behaviour):
    calls: list[str] = []

    def fake(self, cmd, label, token="", timeout_override=None):
        calls.append(label)
        stdout, stderr, rc = behaviour(token)
        return cr.CLIResult(stdout, stderr, rc, 0.1, "claude", label)

    monkeypatch.setattr(cr.CLIRuntime, "_invoke_single", fake)
    return calls


def _fallback_stub(monkeypatch):
    seen: list[str] = []
    real = cr.CLIRuntime.invoke

    def spy(self, prompt, system_prompt=None, extra_flags=None):
        if self.model != "claude":
            seen.append(self.model)
            return cr.CLIResult("FALLBACK", "", 0, 0.1, self.model, "agy")
        return real(self, prompt, system_prompt, extra_flags)

    monkeypatch.setattr(cr.CLIRuntime, "invoke", spy)
    return seen


def test_registry_retired_slots_equal_the_runtime_constant():
    slots = json.loads((REPO_ROOT / "FLEET_TOPOLOGY.json").read_text())["accounts"]["anthropic"]["slots"]
    registry = {
        str(seat["oauth_token_slot"]).rsplit("_", 1)[-1]
        for seat in slots.values()
        if seat.get("status") == "retired" and seat.get("oauth_token_slot")
    }
    assert registry == set(cr.RETIRED_OAUTH_SLOTS)


def test_retired_slots_are_not_in_the_chain_even_when_set(monkeypatch):
    for n in "123456":
        monkeypatch.setenv(f"CLAUDE_CODE_OAUTH_TOKEN_{n}", f"fake-{n}")
    labels = [label for label, _ in cr.claude_token_chain()]
    assert labels == [
        "CLAUDE_CODE_OAUTH_TOKEN_1",
        "CLAUDE_CODE_OAUTH_TOKEN_5",
        "CLAUDE_CODE_OAUTH_TOKEN_6",
        "keychain",
    ]


@pytest.mark.parametrize("target", ["CLAUDE_CODE_OAUTH_TOKEN_1", "CLAUDE_CODE_OAUTH_TOKEN_5", "CLAUDE_CODE_OAUTH_TOKEN"])
def test_retired_value_aliased_into_a_live_or_legacy_slot_is_never_used(monkeypatch, target):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_4", "fake-closed4")
    monkeypatch.setenv(target, "fake-closed4")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_6", "fake-live6")
    tokens = [token for _, token in cr.claude_token_chain()]
    assert "fake-closed4" not in tokens
    assert "fake-live6" in tokens


def test_retired_value_with_surrounding_whitespace_still_matches_its_alias(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_3", "  fake-closed3 \n")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "fake-closed3")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "fake-closed3\t")
    tokens = [token for _, token in cr.claude_token_chain()]
    assert tokens == [""]


def test_gate_reproducer_dead_seat_then_closed_seat_reaches_live_seats(monkeypatch):
    for k, v in {
        "CLAUDE_CODE_OAUTH_TOKEN_1": "fake-dead1",
        "CLAUDE_CODE_OAUTH_TOKEN_4": "fake-closed4",
        "CLAUDE_CODE_OAUTH_TOKEN_5": "fake-live5",
        "CLAUDE_CODE_OAUTH_TOKEN_6": "fake-live6",
    }.items():
        monkeypatch.setenv(k, v)

    def behaviour(token):
        if token == "fake-dead1":
            return "", "Claude AI usage limit reached", 1
        if token == "fake-closed4":
            return "", "API Error: 403 forbidden (account closed)", 1
        return "ANSWER", "", 0

    calls = _stub(monkeypatch, behaviour)
    result = cr.CLIRuntime(model="claude", timeout=30).invoke("hi")
    assert calls == ["CLAUDE_CODE_OAUTH_TOKEN_1", "CLAUDE_CODE_OAUTH_TOKEN_5"]
    assert result.success and result.token_used == "CLAUDE_CODE_OAUTH_TOKEN_5"


def test_unclassified_failure_on_seat_1_tries_seat_5_then_6_each_once(monkeypatch):
    for n in "156":
        monkeypatch.setenv(f"CLAUDE_CODE_OAUTH_TOKEN_{n}", f"fake-{n}")
    fallback = _fallback_stub(monkeypatch)
    calls = _stub(monkeypatch, lambda token: ("", "something odd", 2))
    result = cr.CLIRuntime(model="claude", timeout=30).invoke("hi")
    assert calls == [
        "CLAUDE_CODE_OAUTH_TOKEN_1",
        "CLAUDE_CODE_OAUTH_TOKEN_5",
        "CLAUDE_CODE_OAUTH_TOKEN_6",
        "keychain",
    ]
    assert fallback and result.output == "FALLBACK"
    assert cr.get_exhausted_tokens() == set()


def test_retired_slots_never_called_through_invoke(monkeypatch):
    for n in "2346":
        monkeypatch.setenv(f"CLAUDE_CODE_OAUTH_TOKEN_{n}", f"fake-{n}")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_5", "fake-2")
    calls = _stub(monkeypatch, lambda token: ("ANSWER", "", 0))
    cr.CLIRuntime(model="claude", timeout=30).invoke("hi")
    assert calls == ["CLAUDE_CODE_OAUTH_TOKEN_6"]


def test_success_on_seat_1_makes_no_further_calls(monkeypatch):
    for n in "156":
        monkeypatch.setenv(f"CLAUDE_CODE_OAUTH_TOKEN_{n}", f"fake-{n}")
    calls = _stub(monkeypatch, lambda token: ("ANSWER", "", 0))
    result = cr.CLIRuntime(model="claude", timeout=30).invoke("hi")
    assert calls == ["CLAUDE_CODE_OAUTH_TOKEN_1"]
    assert result.success


def test_missing_claude_binary_skips_remaining_seats(monkeypatch):
    for n in "156":
        monkeypatch.setenv(f"CLAUDE_CODE_OAUTH_TOKEN_{n}", f"fake-{n}")
    _fallback_stub(monkeypatch)
    calls = _stub(monkeypatch, lambda token: ("", "Command not found: claude", -2))
    cr.CLIRuntime(model="claude", timeout=30).invoke("hi")
    assert calls == ["CLAUDE_CODE_OAUTH_TOKEN_1"]
