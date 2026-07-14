#!/usr/bin/env python3
"""Falsifiable tests for scripts/deepseek_client.py — the smart-spend consumer.

Run:
    apps/backend-rag/.venv/bin/python -m pytest scripts/test_deepseek_client.py -q

Guilt tests (the guard MUST fire):
  - STOP verdict -> complete() raises WITHOUT any network call.
  - DEGRADE verdict -> raises by default; allow_degrade=True proceeds.
  - Legacy alias models (deepseek-chat/-reasoner) refused (silent-downgrade trap).
Innocence tests (the guard MUST NOT fire on legitimate work):
  - ALLOW verdict -> the call proceeds and the ledger gets a row the real
    cost_breaker can sum (round-trip through sum_rows_in_window).
  - Fresh machine (no ledger at all) -> ensure_ledger bootstraps KNOWN-zero,
    verdict is ALLOW, not the fail-closed DEGRADE deadlock.
Plus: flash-first default, cache-hit-aware pricing math, ledger schema.

No test touches the network or the user's home dir (W96): every root is
tmp_path, urlopen is always monkeypatched.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cost_breaker as cb  # noqa: E402
import deepseek_client as dc  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decision(verdict: cb.Verdict, spend: str = "1.00") -> cb.BreakerDecision:
    return cb.BreakerDecision(
        provider="deepseek",
        spend_usd=Decimal(spend),
        verdict=verdict,
        next_tier="ollama",
    )


class _NetworkTouched(AssertionError):
    """Raised by the tripwire urlopen — a guilt test hit the network."""


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Every test: fresh verdict cache, tmp ledger root, no real key needed."""
    monkeypatch.setattr(dc, "_verdict_cache", {"ts": 0.0, "decision": None})
    monkeypatch.setenv("LLM_COST_JSONL_ROOT", str(tmp_path / "ledger"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-real")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)


def _fake_response(model: str = "deepseek-v4-flash", *, prompt=1000, completion=500, cache_hit=0):
    body = {
        "model": model,
        "choices": [{"message": {"content": "pong"}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "prompt_cache_hit_tokens": cache_hit,
            "total_tokens": prompt + completion,
        },
    }

    class _Resp:
        def read(self):
            return json.dumps(body).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return _Resp()


# ---------------------------------------------------------------------------
# Guilt: the guard fires
# ---------------------------------------------------------------------------


def test_stop_verdict_refuses_without_network(monkeypatch):
    monkeypatch.setattr(dc, "budget_verdict", lambda **_: _decision(cb.Verdict.STOP, "6.00"))

    def _tripwire(*a, **k):
        raise _NetworkTouched("STOP verdict must never reach the API")

    monkeypatch.setattr(dc.urllib.request, "urlopen", _tripwire)
    with pytest.raises(dc.DeepSeekBudgetExceeded):
        dc.complete("ping")


def test_degrade_refuses_by_default_allows_when_opted_in(monkeypatch):
    monkeypatch.setattr(dc, "budget_verdict", lambda **_: _decision(cb.Verdict.DEGRADE, "4.50"))
    calls = {"n": 0}

    def _fake_urlopen(*a, **k):
        calls["n"] += 1
        return _fake_response()

    monkeypatch.setattr(dc.urllib.request, "urlopen", _fake_urlopen)

    with pytest.raises(dc.DeepSeekBudgetExceeded):
        dc.complete("ping")
    assert calls["n"] == 0, "DEGRADE default must not spend"

    result = dc.complete("ping", allow_degrade=True)
    assert result.text == "pong"
    assert calls["n"] == 1


def test_legacy_aliases_refused():
    for alias in ("deepseek-chat", "deepseek-reasoner"):
        with pytest.raises(dc.DeepSeekError, match="legacy alias"):
            dc.resolve_model(alias)


def test_breaker_false_still_writes_ledger(monkeypatch, tmp_path):
    """The escape hatch bypasses the guard but NEVER the visibility."""
    monkeypatch.setattr(
        dc, "budget_verdict",
        lambda **_: (_ for _ in ()).throw(AssertionError("breaker=False must not consult")),
    )
    monkeypatch.setattr(dc.urllib.request, "urlopen", lambda *a, **k: _fake_response())
    root = tmp_path / "ledger"
    monkeypatch.setenv("LLM_COST_JSONL_ROOT", str(root))

    result = dc.complete("ping", breaker=False)
    assert result.cost_usd > 0
    rows = _ledger_rows(root)
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Innocence: legitimate work proceeds and is ledgered
# ---------------------------------------------------------------------------


def _ledger_rows(root: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(root.glob("llm_cost_log.*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def test_allow_proceeds_and_breaker_can_sum_the_row(monkeypatch, tmp_path):
    monkeypatch.setattr(dc, "budget_verdict", lambda **_: _decision(cb.Verdict.ALLOW, "0.10"))
    monkeypatch.setattr(dc.urllib.request, "urlopen", lambda *a, **k: _fake_response())
    root = tmp_path / "ledger"
    monkeypatch.setenv("LLM_COST_JSONL_ROOT", str(root))

    result = dc.complete("ping", purpose="unit-test")
    rows = _ledger_rows(root)
    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "deepseek"
    assert row["purpose"] == "unit-test"
    assert row["cost_usd"] == pytest.approx(result.cost_usd)

    # Round-trip: the REAL breaker sums this exact row.
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    total = cb.sum_rows_in_window(rows, "deepseek", start, now)
    assert total == Decimal(str(row["cost_usd"]))


def test_fresh_machine_bootstraps_known_zero_not_degrade(tmp_path):
    """No ledger at all would be spend-UNKNOWN -> fail-closed DEGRADE deadlock.

    ensure_ledger creates today's empty file first, so the real breaker reads
    KNOWN-zero and ALLOWs. Uses the REAL budget_verdict (no mocks) against an
    empty tmp root.
    """
    root = tmp_path / "fresh"
    assert not root.exists()
    decision = dc.budget_verdict(root=root)
    assert decision.verdict is cb.Verdict.ALLOW
    assert decision.spend_usd == Decimal("0")


def test_default_model_is_flash_env_overridable(monkeypatch):
    assert dc.resolve_model() == "deepseek-v4-flash"
    assert dc.resolve_model("deepseek-v4-pro") == "deepseek-v4-pro"
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    assert dc.resolve_model() == "deepseek-v4-pro"
    # explicit arg still wins over env
    assert dc.resolve_model("deepseek-v4-flash") == "deepseek-v4-flash"


def test_pricing_math_cache_hit_aware():
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 0, "prompt_cache_hit_tokens": 0}
    assert dc.estimate_cost_usd("deepseek-v4-pro", usage) == pytest.approx(0.435)
    assert dc.estimate_cost_usd("deepseek-v4-flash", usage) == pytest.approx(0.14)
    # full cache hit on flash is ~50x cheaper than miss
    hit = {"prompt_tokens": 1_000_000, "completion_tokens": 0, "prompt_cache_hit_tokens": 1_000_000}
    assert dc.estimate_cost_usd("deepseek-v4-flash", hit) == pytest.approx(0.0028)
    out = {"prompt_tokens": 0, "completion_tokens": 1_000_000, "prompt_cache_hit_tokens": 0}
    assert dc.estimate_cost_usd("deepseek-v4-pro", out) == pytest.approx(0.87)


def test_402_maps_to_balance_dead(monkeypatch):
    import io
    import urllib.error

    monkeypatch.setattr(dc, "budget_verdict", lambda **_: _decision(cb.Verdict.ALLOW, "0.00"))

    def _raise_402(*a, **k):
        raise urllib.error.HTTPError(dc.API_URL, 402, "Payment Required", {}, io.BytesIO(b"{}"))

    monkeypatch.setattr(dc.urllib.request, "urlopen", _raise_402)
    with pytest.raises(dc.DeepSeekBalanceDead):
        dc.complete("ping")


def test_verdict_cache_ttl(monkeypatch):
    """Bulk loops consult the breaker at most once per TTL, not per call."""
    consults = {"n": 0}

    def _counting_verdict(**_):
        consults["n"] += 1
        return _decision(cb.Verdict.ALLOW, "0.00")

    monkeypatch.setattr(dc, "budget_verdict", _counting_verdict)
    monkeypatch.setattr(dc.urllib.request, "urlopen", lambda *a, **k: _fake_response())
    monkeypatch.setenv("DEEPSEEK_BREAKER_TTL_S", "3600")

    for _ in range(5):
        dc.complete("ping")
    assert consults["n"] == 1
