"""Naga Action Engine — deterministic trigger detection from research claims."""

from backend.services.naga.actions.action_engine import (
    ActionItem,
    detect_actions,
)

__all__ = ["ActionItem", "detect_actions"]
