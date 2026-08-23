"""Flag-off no-op is the acceptance criterion itself (packet's "Shadow and
rollback" section): with the flag off, no existing runtime behaviour
changes at all. Enforced here at the code level -- the adapters must never
even be CALLED, not merely "called but their result discarded".
"""

from __future__ import annotations

import backend.services.research_os.shadow as shadow_module
from backend.services.research_os.shadow import (
    SHADOW_FLAG_ENV_VAR,
    shadow_adapt_magazine_action_chain,
    shadow_dual_write_enabled,
)


def test_flag_defaults_off_with_no_env_var_set(monkeypatch):
    monkeypatch.delenv(SHADOW_FLAG_ENV_VAR, raising=False)
    assert shadow_dual_write_enabled() is False


def test_flag_off_never_calls_any_adapter(monkeypatch, ops_intent_row, ops_receipt_row):
    monkeypatch.delenv(SHADOW_FLAG_ENV_VAR, raising=False)
    calls: list[str] = []
    monkeypatch.setattr(
        shadow_module, "adapt_ops_intent_to_action_item", lambda row: calls.append("item")
    )
    monkeypatch.setattr(
        shadow_module, "adapt_ops_intent_to_action_intent", lambda row: calls.append("intent")
    )
    monkeypatch.setattr(
        shadow_module,
        "adapt_ops_receipt_to_operational_receipt",
        lambda receipt_row, intent_row: calls.append("receipt"),
    )

    result = shadow_adapt_magazine_action_chain(ops_intent_row, ops_receipt_row)

    assert result.enabled is False
    assert result.action_item is None
    assert result.action_intent is None
    assert result.operational_receipt is None
    assert calls == [], "flag off must be a genuine no-op: zero adapter calls"


def test_flag_on_runs_all_three_adapters(monkeypatch, ops_intent_row, ops_receipt_row):
    monkeypatch.setenv(SHADOW_FLAG_ENV_VAR, "true")

    result = shadow_adapt_magazine_action_chain(ops_intent_row, ops_receipt_row)

    assert result.enabled is True
    assert result.error is None
    assert result.action_item is not None and result.action_item.accepted
    assert result.action_intent is not None and result.action_intent.accepted
    assert result.operational_receipt is not None and result.operational_receipt.accepted


def test_flag_on_without_a_receipt_row_still_adapts_the_intent_half(monkeypatch, ops_intent_row):
    monkeypatch.setenv(SHADOW_FLAG_ENV_VAR, "true")

    result = shadow_adapt_magazine_action_chain(ops_intent_row, None)

    assert result.enabled is True
    assert result.action_item is not None
    assert result.operational_receipt is None


def test_flag_on_isolates_an_adapter_failure_never_raises(monkeypatch, ops_intent_row, caplog):
    monkeypatch.setenv(SHADOW_FLAG_ENV_VAR, "true")

    def _boom(row):
        raise RuntimeError("simulated canonical-side failure")

    monkeypatch.setattr(shadow_module, "adapt_ops_intent_to_action_item", _boom)

    result = shadow_adapt_magazine_action_chain(ops_intent_row, None)

    assert result.enabled is True
    assert result.error is not None and "simulated canonical-side failure" in result.error
    assert result.action_item is None
    assert result.action_intent is None
    assert result.operational_receipt is None
