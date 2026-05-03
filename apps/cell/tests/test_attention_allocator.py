# apps/cell/tests/test_attention_allocator.py
"""Tests for AttentionAllocator."""
import pytest
from cell.metabolism.attention_allocator import AttentionAllocator, AttentionCost


class TestAttentionBudget:
    def test_full_budget_at_start(self):
        a = AttentionAllocator(daily_units=100)
        assert a.available() == 100

    def test_spend_reduces_available(self):
        a = AttentionAllocator(daily_units=100)
        a.spend(AttentionCost.DEEP_REASONING)
        assert a.available() == 95

    def test_spend_dreaming(self):
        a = AttentionAllocator(daily_units=100)
        a.spend(AttentionCost.DREAMING)
        assert a.available() == 97

    def test_can_afford_true_when_enough(self):
        a = AttentionAllocator(daily_units=100)
        assert a.can_afford(AttentionCost.DEEP_REASONING) is True

    def test_can_afford_false_when_depleted(self):
        a = AttentionAllocator(daily_units=10)
        a.spend(AttentionCost.DEEP_REASONING)
        a.spend(AttentionCost.DEEP_REASONING)  # spent 10
        assert a.can_afford(AttentionCost.DEEP_REASONING) is False

    def test_cannot_go_below_zero(self):
        a = AttentionAllocator(daily_units=3)
        a.spend(AttentionCost.DEEP_REASONING)  # costs 5, only 3 available
        assert a.available() == 0  # clamped at 0, not negative

    def test_reset_restores_full_budget(self):
        a = AttentionAllocator(daily_units=100)
        a.spend(AttentionCost.DEEP_REASONING)
        a.reset()
        assert a.available() == 100

    def test_daily_spend_tracking(self):
        a = AttentionAllocator(daily_units=100)
        a.spend(AttentionCost.DEEP_REASONING)
        a.spend(AttentionCost.DREAMING)
        assert a.daily_spent == 8

    def test_to_dict(self):
        a = AttentionAllocator(daily_units=100)
        a.spend(AttentionCost.DEEP_REASONING)
        d = a.to_dict()
        assert d["available"] == 95
        assert d["spent"] == 5
        assert d["daily_units"] == 100
