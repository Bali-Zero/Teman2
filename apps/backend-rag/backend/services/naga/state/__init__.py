"""Naga state management — lightweight data for the research loop."""

from backend.services.naga.state.budget_tracker import BudgetTracker
from backend.services.naga.state.url_history import URLHistory

__all__ = ["BudgetTracker", "URLHistory"]
