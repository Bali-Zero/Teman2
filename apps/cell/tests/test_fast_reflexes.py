"""Tests for FAST reflex layer — pure rules, no LLM."""
from cell.fast.health_triage import HealthStatus, triage
from cell.fast.cost_guard import BudgetDecision, check_budget


def test_triage_green():
    result = triage(cpu_percent=30.0, memory_percent=50.0, disk_io_wait=10.0)
    assert result == HealthStatus.GREEN


def test_triage_yellow_cpu():
    result = triage(cpu_percent=80.0, memory_percent=50.0, disk_io_wait=10.0)
    assert result == HealthStatus.YELLOW


def test_triage_yellow_memory():
    result = triage(cpu_percent=30.0, memory_percent=85.0, disk_io_wait=10.0)
    assert result == HealthStatus.YELLOW


def test_triage_red_cpu():
    result = triage(cpu_percent=95.0, memory_percent=50.0, disk_io_wait=10.0)
    assert result == HealthStatus.RED


def test_triage_red_memory():
    result = triage(cpu_percent=30.0, memory_percent=95.0, disk_io_wait=10.0)
    assert result == HealthStatus.RED


def test_budget_allow():
    result = check_budget(current_daily_spend=2.0, estimated_action_cost=0.50, daily_limit=10.0)
    assert result == BudgetDecision.ALLOW


def test_budget_deny_over_threshold():
    result = check_budget(current_daily_spend=8.5, estimated_action_cost=0.60, daily_limit=10.0)
    assert result == BudgetDecision.DENY


def test_budget_allow_just_under():
    result = check_budget(current_daily_spend=8.0, estimated_action_cost=0.90, daily_limit=10.0)
    assert result == BudgetDecision.ALLOW
