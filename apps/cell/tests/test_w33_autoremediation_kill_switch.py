"""W33 (2026-05-23) — CELL_AUTOREMEDIATION_ENABLED operator kill switch.

Codex non-negotiable from W27 4-LLM panel: operator must have a fast
off-switch for the auto-heal chain (Cell sustained_red → Organism →
fly_machines_restart) without ssh+grep+kill. The switch lives in Cell
because Cell is the emit source — gating here zeros downstream load.

Default-ON discipline (NOT default-OFF): the chain has been validated
end-to-end (W27+W31). Defaulting OFF would silently disarm auto-heal
for new deployments. Explicit opt-out is safer than default-out.
"""
from __future__ import annotations

import pytest

from cell.core.pulse import _autoremediation_enabled


def test_default_enabled_when_unset(monkeypatch):
    """Empty/unset env var → True (default-on)."""
    monkeypatch.delenv("CELL_AUTOREMEDIATION_ENABLED", raising=False)
    assert _autoremediation_enabled() is True


def test_explicit_true_enabled(monkeypatch):
    monkeypatch.setenv("CELL_AUTOREMEDIATION_ENABLED", "true")
    assert _autoremediation_enabled() is True


def test_empty_string_enabled(monkeypatch):
    """Empty value = default = enabled."""
    monkeypatch.setenv("CELL_AUTOREMEDIATION_ENABLED", "")
    assert _autoremediation_enabled() is True


@pytest.mark.parametrize("disabled_value", [
    "false", "FALSE", "False", "  false  ",
    "0",
    "no", "NO",
    "off", "OFF",
    "disabled", "DISABLED",
])
def test_disabled_values(monkeypatch, disabled_value):
    """Every documented off-switch syntax must work."""
    monkeypatch.setenv("CELL_AUTOREMEDIATION_ENABLED", disabled_value)
    assert _autoremediation_enabled() is False, (
        f"value {disabled_value!r} should disable but didn't"
    )


@pytest.mark.parametrize("active_value", [
    "true", "1", "yes", "on", "enabled",
    "anything-else",  # unknown → default-on (NOT default-off)
    "TRUE", "Yes",
])
def test_active_values(monkeypatch, active_value):
    """Anything not in the explicit disable set should keep auto-heal armed."""
    monkeypatch.setenv("CELL_AUTOREMEDIATION_ENABLED", active_value)
    assert _autoremediation_enabled() is True, (
        f"value {active_value!r} should keep auto-heal armed but disabled it"
    )


def test_no_caching_between_calls(monkeypatch):
    """Operator must be able to flip the env var without restarting Cell —
    next pulse cycle sees new state. Verify no module-level cache."""
    monkeypatch.setenv("CELL_AUTOREMEDIATION_ENABLED", "true")
    assert _autoremediation_enabled() is True
    monkeypatch.setenv("CELL_AUTOREMEDIATION_ENABLED", "false")
    assert _autoremediation_enabled() is False
    monkeypatch.setenv("CELL_AUTOREMEDIATION_ENABLED", "true")
    assert _autoremediation_enabled() is True
