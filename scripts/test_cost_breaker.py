#!/usr/bin/env python3
"""Falsifiable tests for scripts/cost_breaker.py — mapped to P9 gates.

Run:
    apps/backend-rag/.venv/bin/python -m pytest scripts/test_cost_breaker.py -q

Each test names the gate it falsifies. The gates (from the P9 spec):
  G1  ALLOW state emits ZERO telegram push.
  G2  spend in [threshold, budget) -> DEGRADE returns next tier (not STOP,
      not blind-continue).
  G3  STOP push is a CHOICE ([D]/[P]/[C]), not a bare diagnosis.
  G6  every cascade provider in {claude_oauth, gemini, deepseek} has a
      breaker threshold (no provider unguarded).
Plus: window-sum correctness with injected fake rows (provider isolation),
next_tier cascade order + terminal None, and import-purity.
"""

from __future__ import annotations

import importlib
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

# Make scripts/ importable regardless of pytest invocation cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cost_breaker as cb  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class _SpyPush:
    """Records calls so we can assert 'pushed' vs 'not pushed'."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, text: str, *args: object, **kwargs: object) -> bool:
        self.calls.append(text)
        return True


@pytest.fixture()
def config() -> cb.BreakerConfig:
    # Deterministic config independent of env: budget 10, threshold 85% = 8.5.
    return cb.BreakerConfig(
        budgets_usd={
            "claude_oauth": Decimal("10.00"),
            "gemini": Decimal("10.00"),
            "deepseek": Decimal("10.00"),
        },
        threshold_fraction=Decimal("0.85"),
        window_seconds=24 * 60 * 60,
    )


# ---------------------------------------------------------------------------
# G1 — ALLOW emits ZERO push
# ---------------------------------------------------------------------------


def test_g1_allow_emits_zero_push(config: cb.BreakerConfig) -> None:
    spy = _SpyPush()
    # spend 1.00 << threshold 8.50 -> ALLOW
    decision = cb.decide("claude_oauth", Decimal("1.00"), config, push=spy)
    assert decision.verdict is cb.Verdict.ALLOW
    assert spy.calls == [], "ALLOW state must emit ZERO telegram push (G1)"
    assert decision.next_tier is None


def test_g1_allow_just_below_threshold_still_silent(config: cb.BreakerConfig) -> None:
    spy = _SpyPush()
    # spend 8.49 < threshold 8.50 -> still ALLOW, still silent
    decision = cb.decide("gemini", Decimal("8.49"), config, push=spy)
    assert decision.verdict is cb.Verdict.ALLOW
    assert spy.calls == []


# ---------------------------------------------------------------------------
# G2 — DEGRADE returns next tier (not STOP, not blind-continue)
# ---------------------------------------------------------------------------


def test_g2_degrade_returns_next_tier(config: cb.BreakerConfig) -> None:
    spy = _SpyPush()
    # spend 9.00 in [8.50, 10.00) -> DEGRADE
    decision = cb.decide("claude_oauth", Decimal("9.00"), config, push=spy)
    assert decision.verdict is cb.Verdict.DEGRADE, "must DEGRADE, not STOP (G2)"
    assert decision.next_tier == "gemini", "DEGRADE must hand off to the next tier"
    assert decision.verdict is not cb.Verdict.ALLOW, "must not blind-continue (G2)"


def test_g2_degrade_exactly_at_threshold(config: cb.BreakerConfig) -> None:
    # spend == threshold (8.50) -> DEGRADE (inclusive lower bound)
    verdict = cb.evaluate("deepseek", Decimal("8.50"), config)
    assert verdict is cb.Verdict.DEGRADE


def test_g2_degrade_does_not_push(config: cb.BreakerConfig) -> None:
    # DEGRADE is automatic + silent; the only push is STOP (so DEGRADE keeps G1
    # quiet too — no notification noise on every cascade).
    spy = _SpyPush()
    cb.decide("gemini", Decimal("9.50"), config, push=spy)
    assert spy.calls == []


# ---------------------------------------------------------------------------
# G3 — STOP push is a CHOICE, not a diagnosis
# ---------------------------------------------------------------------------


def test_g3_stop_pushes_a_choice(config: cb.BreakerConfig) -> None:
    spy = _SpyPush()
    # spend 10.00 >= budget 10.00 -> STOP. cooldown_sec=0 keeps the test
    # deterministic + writes no state file (P2-1 cooldown is off here).
    decision = cb.decide("deepseek", Decimal("10.00"), config, push=spy, cooldown_sec=0)
    assert decision.verdict is cb.Verdict.STOP
    assert len(spy.calls) == 1, "STOP must push exactly once"
    msg = spy.calls[0]
    # A CHOICE contains action options; a diagnosis-only message is malformed.
    assert "[D]" in msg and "[P]" in msg and "[C]" in msg, (
        "STOP message must offer action options [D]/[P]/[C], not just diagnose (G3)"
    )


def test_g3_diagnosis_only_message_is_rejected(config: cb.BreakerConfig) -> None:
    # Falsifier: a message with the spend but NO options must fail the G3 check.
    diagnosis_only = "budget deepseek exhausted: spend $10.00 / $10.00 in 24h."
    has_options = all(opt in diagnosis_only for opt in ("[D]", "[P]", "[C]"))
    assert not has_options, "a diagnosis-only message must NOT pass the choice gate"


def test_g3_build_stop_message_directly(config: cb.BreakerConfig) -> None:
    msg = cb.build_stop_message("claude_oauth", Decimal("12.34"), config)
    assert "[D]" in msg and "[P]" in msg and "[C]" in msg
    assert "claude_oauth" in msg
    # the next-tier hint is part of the choice (degrade target)
    assert "gemini" in msg


# ---------------------------------------------------------------------------
# G6 — every cascade provider is guarded (no provider unguarded)
# ---------------------------------------------------------------------------


def test_g6_every_guarded_provider_has_threshold() -> None:
    config = cb.BreakerConfig.from_env(env={})  # pure defaults
    for provider in ("claude_oauth", "gemini", "deepseek"):
        assert config.budget_for(provider) is not None, f"{provider} has no budget (G6)"
        assert config.threshold_for(provider) is not None, f"{provider} has no threshold (G6)"
        assert config.budget_for(provider) > 0


def test_g6_guarded_set_covers_paid_cascade_tiers() -> None:
    # Every cascade tier that costs money must be in the guarded set.
    paid_tiers = [t for t in cb.CASCADE_ORDER if t != "ollama"]
    for tier in paid_tiers:
        assert tier in cb.GUARDED_PROVIDERS, f"paid tier {tier} is unguarded (G6)"


def test_g6_ollama_is_unguarded_and_always_allows() -> None:
    # ollama is local/$0 — intentionally unguarded; it must never break.
    config = cb.BreakerConfig.from_env(env={})
    assert config.budget_for("ollama") is None
    assert cb.evaluate("ollama", Decimal("9999"), config) is cb.Verdict.ALLOW


# ---------------------------------------------------------------------------
# Window-sum correctness with injected fake rows (provider isolation)
# ---------------------------------------------------------------------------


def _row(provider: str, cost: str, ts: datetime) -> dict[str, object]:
    return {"provider": provider, "cost_usd": cost, "ts_utc": ts}


def test_window_sum_isolates_provider() -> None:
    now = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=24)
    rows = [
        _row("claude_oauth", "1.00", now - timedelta(hours=1)),
        _row("claude_oauth", "2.50", now - timedelta(hours=2)),
        _row("gemini", "5.00", now - timedelta(hours=1)),  # different provider
    ]
    a = cb.sum_rows_in_window(rows, "claude_oauth", start)
    b = cb.sum_rows_in_window(rows, "gemini", start)
    assert a == Decimal("3.50"), "provider A spend must exclude provider B"
    assert b == Decimal("5.00")
    # provider isolation: A's spend does not count toward B
    assert a != b


def test_window_sum_excludes_rows_before_window() -> None:
    now = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=24)
    rows = [
        _row("deepseek", "1.00", now - timedelta(hours=1)),  # in window
        _row("deepseek", "9.99", now - timedelta(hours=48)),  # too old
    ]
    total = cb.sum_rows_in_window(rows, "deepseek", start)
    assert total == Decimal("1.00"), "rows older than the window must be excluded"


def test_window_sum_handles_iso_string_ts() -> None:
    now = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=24)
    # JSONL stores ts_utc as an ISO string; the 'Z' suffix form too.
    rows = [
        {"provider": "gemini", "cost_usd": "2.00", "ts_utc": (now - timedelta(hours=1)).isoformat()},
        {"provider": "gemini", "cost_usd": "3.00", "ts_utc": "2026-06-08T11:30:00Z"},
    ]
    total = cb.sum_rows_in_window(rows, "gemini", start)
    assert total == Decimal("5.00")


def test_window_sum_skips_malformed_rows() -> None:
    now = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=24)
    rows = [
        {"provider": "gemini", "cost_usd": "2.00", "ts_utc": now - timedelta(hours=1)},
        {"provider": "gemini", "cost_usd": None, "ts_utc": now},  # bad cost
        {"provider": "gemini", "cost_usd": "1.00", "ts_utc": None},  # bad ts
        {"provider": "gemini", "cost_usd": "not-a-number", "ts_utc": now},  # bad cost
    ]
    total = cb.sum_rows_in_window(rows, "gemini", start)
    assert total == Decimal("2.00"), "malformed rows must be skipped, not crash"


# ---------------------------------------------------------------------------
# next_tier cascade order + terminal None
# ---------------------------------------------------------------------------


def test_next_tier_cascade_order() -> None:
    # openrouter (paid per-token, no flat sub) is the last PAID tier before the
    # free floor (P0-2), so the cascade is now
    # claude_oauth -> gemini -> deepseek -> openrouter -> ollama.
    assert cb.next_tier("claude_oauth") == "gemini"
    assert cb.next_tier("gemini") == "deepseek"
    assert cb.next_tier("deepseek") == "openrouter"
    assert cb.next_tier("openrouter") == "ollama"


def test_next_tier_terminal_none() -> None:
    assert cb.next_tier("ollama") is None, "ollama is the floor — no tier after it"


def test_next_tier_unknown_provider_none() -> None:
    assert cb.next_tier("totally-unknown") is None


def test_stop_at_floor_has_no_next_tier(config: cb.BreakerConfig) -> None:
    # An unguarded provider can't STOP, so to test 'STOP at floor' we add ollama
    # a budget explicitly and exhaust it: next_tier is still None.
    floor_config = cb.BreakerConfig(
        budgets_usd={"ollama": Decimal("1.00")},
        threshold_fraction=Decimal("0.85"),
        window_seconds=3600,
    )
    spy = _SpyPush()
    decision = cb.decide(
        "ollama", Decimal("5.00"), floor_config, push=spy, cooldown_sec=0,
    )
    assert decision.verdict is cb.Verdict.STOP
    assert decision.next_tier is None, "STOP at the cascade floor yields next_tier None"


# ---------------------------------------------------------------------------
# Config env overrides
# ---------------------------------------------------------------------------


def test_config_env_override() -> None:
    config = cb.BreakerConfig.from_env(
        env={
            "COST_BREAKER_BUDGET_CLAUDE_OAUTH_USD": "100",
            "COST_BREAKER_THRESHOLD_FRACTION": "0.5",
        },
    )
    assert config.budget_for("claude_oauth") == Decimal("100")
    assert config.threshold_for("claude_oauth") == Decimal("50.0")


def test_config_env_invalid_falls_back_to_default() -> None:
    config = cb.BreakerConfig.from_env(
        env={"COST_BREAKER_BUDGET_GEMINI_USD": "not-a-number"},
    )
    # falls back to the conservative default, never crashes
    assert config.budget_for("gemini") == cb._DEFAULT_BUDGET_USD["gemini"]


# ---------------------------------------------------------------------------
# Import purity — no network / DB at import time
# ---------------------------------------------------------------------------


def test_module_imports_without_network_or_db() -> None:
    # Re-import in a fresh module object; if import touched the network or a DB
    # it would block/raise here (no creds in the test env).
    mod = importlib.reload(cb)
    assert hasattr(mod, "evaluate")
    assert hasattr(mod, "provider_spend_in_window")


def test_jsonl_fallback_reads_real_file(tmp_path: Path) -> None:
    import asyncio

    now = datetime.now(timezone.utc)
    day = now.date().isoformat()
    f = tmp_path / f"llm_cost_log.{day}.jsonl"
    f.write_text(
        "\n".join(
            [
                f'{{"provider": "deepseek", "cost_usd": 1.5, "ts_utc": "{now.isoformat()}"}}',
                f'{{"provider": "gemini", "cost_usd": 9.0, "ts_utc": "{now.isoformat()}"}}',
                "not json at all",  # malformed line must be skipped
            ],
        ),
    )
    total = asyncio.run(
        cb.provider_spend_in_window(
            "deepseek", 3600, jsonl_root=tmp_path, now=now,
        ),
    )
    assert total == Decimal("1.5")


# ===========================================================================
# Adversarial-review fixes — a money-guard MUST fail CLOSED (verdict DEGRADE
# when spend is UNKNOWN), never fail open to ALLOW.
# ===========================================================================


# ---------------------------------------------------------------------------
# Test doubles for the asyncpg surface (Connection / Pool)
# ---------------------------------------------------------------------------


class _FakeConn:
    """Minimal asyncpg Connection double: returns a fixed fetchval value."""

    def __init__(self, value: object) -> None:
        self._value = value
        self.calls: list[tuple] = []

    async def fetchval(self, sql: str, *args: object) -> object:
        self.calls.append((sql, args))
        return self._value


class _RaisingConn:
    """asyncpg Connection double whose fetchval RAISES (simulated DB error)."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def fetchval(self, sql: str, *args: object) -> object:
        raise self._exc


# ---------------------------------------------------------------------------
# P0-1 — FAIL-CLOSED on every spend-UNKNOWN path
# ---------------------------------------------------------------------------


def test_p0_1_db_read_raises_degrades_not_allow_not_crash(config: cb.BreakerConfig) -> None:
    import asyncio

    # A DB error must surface as spend=None (UNKNOWN), NOT crash, NOT $0.
    conn = _RaisingConn(RuntimeError("connection reset by peer"))
    spend = asyncio.run(
        cb.provider_spend_in_window("claude_oauth", 3600, conn_or_pool=conn),
    )
    assert spend is None, "a DB read error must yield UNKNOWN spend, not 0"
    # ...and a guarded provider with UNKNOWN spend must DEGRADE, never ALLOW.
    verdict = cb.evaluate("claude_oauth", spend, config)
    assert verdict is cb.Verdict.DEGRADE, "UNKNOWN spend must fail-closed DEGRADE (P0-1)"
    assert verdict is not cb.Verdict.ALLOW


def test_p0_1_jsonl_root_missing_for_guarded_degrades(config: cb.BreakerConfig, tmp_path: Path) -> None:
    import asyncio

    # No DB pool AND no JSONL file present in the (empty) root = no source ->
    # UNKNOWN -> fail-closed DEGRADE for a guarded provider.
    empty_root = tmp_path / "nonexistent"
    spend = asyncio.run(
        cb.provider_spend_in_window("gemini", 3600, jsonl_root=empty_root),
    )
    assert spend is None, "no consultable source must yield UNKNOWN, not 0"
    assert cb.evaluate("gemini", spend, config) is cb.Verdict.DEGRADE


def test_p0_1_empty_but_read_source_is_known_zero_allows(config: cb.BreakerConfig, tmp_path: Path) -> None:
    import asyncio

    # A PRESENT JSONL file with no matching rows is KNOWN-zero (Decimal 0),
    # distinct from unread (None). Known-zero ALLOWs.
    now = datetime.now(timezone.utc)
    day = now.date().isoformat()
    f = tmp_path / f"llm_cost_log.{day}.jsonl"
    f.write_text(  # a row for a DIFFERENT provider — gemini has zero, but read
        f'{{"provider": "deepseek", "cost_usd": 1.0, "ts_utc": "{now.isoformat()}"}}\n',
    )
    spend = asyncio.run(
        cb.provider_spend_in_window("gemini", 3600, jsonl_root=tmp_path, now=now),
    )
    assert spend == Decimal("0"), "empty-but-read source is KNOWN zero, not None"
    assert spend is not None
    assert cb.evaluate("gemini", spend, config) is cb.Verdict.ALLOW


def test_p0_1_db_zero_is_known_zero_not_unknown(config: cb.BreakerConfig) -> None:
    import asyncio

    # A successful DB read returning 0 is KNOWN zero -> Decimal(0) -> ALLOW.
    conn = _FakeConn(0)
    spend = asyncio.run(
        cb.provider_spend_in_window("deepseek", 3600, conn_or_pool=conn),
    )
    assert spend == Decimal("0")
    assert spend is not None
    assert cb.evaluate("deepseek", spend, config) is cb.Verdict.ALLOW


def test_p0_1_unguarded_provider_unknown_still_allows(config: cb.BreakerConfig) -> None:
    # ollama is unguarded — even UNKNOWN spend must ALLOW (no money to break).
    assert cb.evaluate("ollama", None, config) is cb.Verdict.ALLOW


def test_p0_1_check_all_degrades_on_unknown_not_zero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    # _check_all must NOT exit 0 (ALLOW-only) when every read is UNKNOWN — a
    # failed/absent ledger is a DEGRADE storm (exit 1), not a clean bill.
    async def _always_unknown(provider: str, window_seconds: int, **kw: object):
        return None

    monkeypatch.setattr(cb, "provider_spend_in_window", _always_unknown)
    cfg = cb.BreakerConfig.from_env(env={})
    code = asyncio.run(cb._check_all(cfg))
    assert code == 1, "all-UNKNOWN must be DEGRADE (exit 1), never ALLOW (exit 0)"


def test_p0_1_decide_unknown_spend_is_degrade_no_push(config: cb.BreakerConfig) -> None:
    spy = _SpyPush()
    decision = cb.decide("claude_oauth", None, config, push=spy, cooldown_sec=0)
    assert decision.verdict is cb.Verdict.DEGRADE
    assert decision.spend_usd is None
    assert decision.next_tier == "gemini"
    assert spy.calls == [], "fail-closed DEGRADE is silent like any DEGRADE (G1)"


# ---------------------------------------------------------------------------
# P0-2 — provider label normalization + openrouter guard
# ---------------------------------------------------------------------------


def test_p0_2_anthropic_row_counts_toward_claude_oauth() -> None:
    now = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=24)
    rows = [
        _row("anthropic", "3.00", now - timedelta(hours=1)),
        _row("claude_oauth", "2.00", now - timedelta(hours=2)),
        _row("claude-oauth", "1.00", now - timedelta(hours=3)),
    ]
    total = cb.sum_rows_in_window(rows, "claude_oauth", start, now)
    assert total == Decimal("6.00"), "anthropic/claude-oauth must fold onto claude_oauth"


def test_p0_2_gemini_flash_counts_toward_gemini() -> None:
    now = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=24)
    rows = [
        _row("gemini-flash", "2.00", now - timedelta(hours=1)),
        _row("gemini-2.0", "3.00", now - timedelta(hours=2)),
        _row("deepseek-v4-pro", "9.00", now - timedelta(hours=1)),  # not gemini
    ]
    total = cb.sum_rows_in_window(rows, "gemini", start, now)
    assert total == Decimal("5.00"), "model-suffixed gemini variants fold onto gemini"


def test_p0_2_deepseek_suffix_folds() -> None:
    assert cb._normalize_provider("deepseek-v4-pro") == "deepseek"
    assert cb._normalize_provider("deepseek-v4-flash") == "deepseek"
    assert cb._normalize_provider("DeepSeek") == "deepseek"


def test_p0_2_openrouter_is_guarded_not_auto_allow() -> None:
    config = cb.BreakerConfig.from_env(env={})
    assert config.budget_for("openrouter") is not None, "openrouter must be guarded (P0-2)"
    assert config.threshold_for("openrouter") is not None
    # at-budget openrouter STOPs (it is NOT ALLOW-forever)
    assert cb.evaluate("openrouter", config.budget_for("openrouter"), config) is cb.Verdict.STOP
    assert "openrouter" in cb.GUARDED_PROVIDERS
    assert "openrouter" in cb.CASCADE_ORDER


def test_p0_2_openrouter_budget_env_override() -> None:
    config = cb.BreakerConfig.from_env(
        env={"COST_BREAKER_BUDGET_OPENROUTER_USD": "12.50"},
    )
    assert config.budget_for("openrouter") == Decimal("12.50")


def test_p0_2_unknown_provider_stays_unknown_not_silent_allow() -> None:
    # An unmapped label is returned unchanged (lower-cased) — it is NOT folded
    # onto a guarded provider, and (being unguarded) ALLOWs, but it is logged-
    # honest: the normalizer does not silently rename it to a known provider.
    assert cb._normalize_provider("some-new-vendor") == "some-new-vendor"
    assert cb._normalize_provider("") == ""
    assert cb._normalize_provider(None) == ""


def test_p0_2_pg_alias_set_includes_anthropic() -> None:
    aliases = cb._pg_alias_set("claude_oauth")
    assert "anthropic" in aliases
    assert "claude_oauth" in aliases
    assert "claude-oauth" in aliases
    # normalizing a raw alias resolves to the canonical key
    assert cb._pg_alias_set("anthropic") == cb._pg_alias_set("claude_oauth")


def test_p0_2_pg_query_uses_alias_set() -> None:
    import asyncio

    conn = _FakeConn(Decimal("4.00"))
    now = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    asyncio.run(
        cb.provider_spend_in_window("anthropic", 3600, conn_or_pool=conn, now=now),
    )
    assert conn.calls, "fetchval must have been called"
    _sql, args = conn.calls[0]
    alias_arg = args[0]
    assert "anthropic" in alias_arg and "claude_oauth" in alias_arg
    assert "= ANY(" in _sql


# ---------------------------------------------------------------------------
# P1-1 / P1-2 — PG honors injected now + upper bound on BOTH paths
# ---------------------------------------------------------------------------


def test_p1_1_pg_window_anchored_on_injected_now() -> None:
    import asyncio

    conn = _FakeConn(Decimal("1.00"))
    now = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    asyncio.run(
        cb.provider_spend_in_window("gemini", 3600, conn_or_pool=conn, now=now),
    )
    _sql, args = conn.calls[0]
    # args: (aliases, window_start, now)
    window_start, upper = args[1], args[2]
    assert upper == now, "PG upper bound must be the injected now (P1-1)"
    assert window_start == now - timedelta(seconds=3600)
    # the SQL must bind both bounds, not derive the window from the DB clock
    assert "ts_utc >= $2" in _sql and "ts_utc <= $3" in _sql
    assert "NOW()" not in _sql, "PG must bind injected now, not re-derive from DB clock"


def test_p1_2_future_dated_row_excluded_jsonl() -> None:
    now = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=24)
    rows = [
        _row("deepseek", "1.00", now - timedelta(hours=1)),  # in window
        _row("deepseek", "99.00", now + timedelta(hours=1)),  # FUTURE — excluded
    ]
    total = cb.sum_rows_in_window(rows, "deepseek", start, now)
    assert total == Decimal("1.00"), "a future-dated row must not inflate spend (P1-2)"


# ---------------------------------------------------------------------------
# P1-3 — NaN / Inf / negative cost cannot poison the sum or flip the verdict
# ---------------------------------------------------------------------------


def test_p1_3_nan_cost_row_is_skipped_rest_sum_correctly() -> None:
    now = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=24)
    rows = [
        _row("gemini", "2.00", now - timedelta(hours=1)),
        _row("gemini", "NaN", now - timedelta(hours=2)),  # poison row
        _row("gemini", "3.00", now - timedelta(hours=3)),
    ]
    total = cb.sum_rows_in_window(rows, "gemini", start, now)
    assert total == Decimal("5.00"), "NaN row must be skipped, not poison the sum"
    assert total.is_finite()


def test_p1_3_inf_and_negative_cost_skipped() -> None:
    now = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=24)
    rows = [
        _row("deepseek", "Infinity", now - timedelta(hours=1)),  # skipped
        _row("deepseek", "-5.00", now - timedelta(hours=2)),  # negative skipped
        _row("deepseek", "4.00", now - timedelta(hours=3)),
    ]
    total = cb.sum_rows_in_window(rows, "deepseek", start, now)
    assert total == Decimal("4.00")


def test_p1_3_safe_decimal_rejects_nan_inf_negative() -> None:
    assert cb._safe_decimal("NaN") is None
    assert cb._safe_decimal("Infinity") is None
    assert cb._safe_decimal("-Infinity") is None
    assert cb._safe_decimal(float("nan")) is None
    assert cb._safe_decimal(float("inf")) is None
    assert cb._safe_decimal("-0.01") is None
    assert cb._safe_decimal("0") == Decimal("0")
    assert cb._safe_decimal("1.50") == Decimal("1.50")


def test_p1_3_nan_does_not_flip_verdict_to_allow(config: cb.BreakerConfig) -> None:
    # A single NaN row used to make the whole provider sum NaN, and
    # NaN >= budget is False -> ALLOW (fail-open). Now the NaN is skipped, the
    # real spend (12.00 >= budget 10.00) STOPs.
    now = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=24)
    rows = [
        _row("deepseek", "12.00", now - timedelta(hours=1)),
        _row("deepseek", "NaN", now - timedelta(hours=2)),
    ]
    total = cb.sum_rows_in_window(rows, "deepseek", start, now)
    assert cb.evaluate("deepseek", total, config) is cb.Verdict.STOP


def test_p1_3_zero_budget_config_is_unguarded_no_stop_spam() -> None:
    # A directly-constructed budget=0 must NOT STOP at every spend (STOP-spam);
    # zero budget = unguarded = ALLOW.
    cfg = cb.BreakerConfig(
        budgets_usd={"deepseek": Decimal("0")},
        threshold_fraction=Decimal("0.85"),
        window_seconds=3600,
    )
    assert cfg.budget_for("deepseek") is None
    assert cb.evaluate("deepseek", Decimal("100"), cfg) is cb.Verdict.ALLOW


# ---------------------------------------------------------------------------
# P2-1 — STOP push cooldown (no per-tick re-spam), G1 still holds
# ---------------------------------------------------------------------------


def test_p2_1_stop_push_suppressed_within_cooldown(config: cb.BreakerConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Redirect the cooldown state dir into tmp so the test is hermetic.
    monkeypatch.setattr(cb, "_COOLDOWN_STATE_DIR", tmp_path)
    spy = _SpyPush()
    # First STOP fires + sets cooldown.
    cb.decide("deepseek", Decimal("10.00"), config, push=spy, cooldown_sec=3600)
    assert len(spy.calls) == 1, "first STOP must push"
    # Second STOP within cooldown is suppressed.
    cb.decide("deepseek", Decimal("10.00"), config, push=spy, cooldown_sec=3600)
    assert len(spy.calls) == 1, "duplicate STOP within cooldown must be suppressed (P2-1)"


def test_p2_1_cooldown_is_per_provider(config: cb.BreakerConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cb, "_COOLDOWN_STATE_DIR", tmp_path)
    spy = _SpyPush()
    cb.decide("deepseek", Decimal("10.00"), config, push=spy, cooldown_sec=3600)
    cb.decide("gemini", Decimal("10.00"), config, push=spy, cooldown_sec=3600)
    assert len(spy.calls) == 2, "a different provider has its own cooldown"


def test_p2_1_cooldown_zero_disables(config: cb.BreakerConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cb, "_COOLDOWN_STATE_DIR", tmp_path)
    spy = _SpyPush()
    cb.decide("deepseek", Decimal("10.00"), config, push=spy, cooldown_sec=0)
    cb.decide("deepseek", Decimal("10.00"), config, push=spy, cooldown_sec=0)
    assert len(spy.calls) == 2, "cooldown_sec=0 must not suppress (every STOP pushes)"


def test_p2_1_allow_and_degrade_never_push_even_with_cooldown(config: cb.BreakerConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # G1 still holds: ALLOW + DEGRADE emit zero push regardless of cooldown.
    monkeypatch.setattr(cb, "_COOLDOWN_STATE_DIR", tmp_path)
    spy = _SpyPush()
    cb.decide("gemini", Decimal("1.00"), config, push=spy, cooldown_sec=3600)  # ALLOW
    cb.decide("gemini", Decimal("9.00"), config, push=spy, cooldown_sec=3600)  # DEGRADE
    cb.decide("gemini", None, config, push=spy, cooldown_sec=3600)  # UNKNOWN->DEGRADE
    assert spy.calls == [], "ALLOW/DEGRADE must never push (G1)"


def test_p2_1_cooldown_seconds_env_override() -> None:
    assert cb._push_cooldown_seconds(env={}) == cb._DEFAULT_PUSH_COOLDOWN_SEC
    assert cb._push_cooldown_seconds(env={"COST_BREAKER_PUSH_COOLDOWN_SEC": "120"}) == 120
    # invalid -> default
    assert cb._push_cooldown_seconds(env={"COST_BREAKER_PUSH_COOLDOWN_SEC": "x"}) == cb._DEFAULT_PUSH_COOLDOWN_SEC
