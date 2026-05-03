"""
Exa API Budget Guard — prevents overspending on daily Exa calls.
File-based tracker at /tmp/exa_daily_budget.json.

Usage:
    from exa_budget_guard import can_spend, log_spend, get_daily_spend

    if not can_spend(0.007):  # cost of one search
        print("Daily budget exceeded")
        return

    # ... make the API call ...
    log_spend(0.007, "search", query="KITAS Indonesia")
"""
import json
import os
from datetime import datetime, date
from pathlib import Path

BUDGET_FILE = Path("/tmp/exa_daily_budget.json")
DAILY_LIMIT = float(os.environ.get("EXA_DAILY_BUDGET", "0.50"))  # $0.50 default

# Cost per call (Exa pricing April 2026)
COST_SEARCH = 0.007        # $7/1K searches
COST_CONTENT = 0.001       # $1/1K content pages
COST_EXTRA_RESULT = 0.001  # $1/1K extra results beyond 10


def _load() -> dict:
    """Load today's budget state."""
    if BUDGET_FILE.exists():
        try:
            data = json.loads(BUDGET_FILE.read_text())
            if data.get("date") == str(date.today()):
                return data
        except (json.JSONDecodeError, KeyError):
            pass
    return {"date": str(date.today()), "total_spent": 0.0, "calls": []}


def _save(data: dict):
    """Save budget state atomically."""
    tmp = BUDGET_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(BUDGET_FILE)


def get_daily_spend() -> float:
    """Get total spent today."""
    return _load()["total_spent"]


def get_remaining() -> float:
    """Get remaining budget for today."""
    return max(0.0, DAILY_LIMIT - get_daily_spend())


def can_spend(cost: float) -> bool:
    """Check if we can afford this call."""
    return get_daily_spend() + cost <= DAILY_LIMIT


def log_spend(cost: float, call_type: str = "search", **meta):
    """Log a spend event."""
    data = _load()
    data["total_spent"] = round(data["total_spent"] + cost, 6)
    data["calls"].append({
        "time": datetime.now().isoformat(),
        "type": call_type,
        "cost": cost,
        **meta,
    })
    _save(data)


def budget_status() -> str:
    """Human-readable budget status."""
    spent = get_daily_spend()
    remaining = get_remaining()
    return f"Exa budget: ${spent:.3f}/${DAILY_LIMIT:.2f} spent, ${remaining:.3f} remaining"
