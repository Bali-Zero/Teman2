"""
Self-healing agent subsystem.

The public entrypoint is `BackendSelfHealingAgent` in `backend_agent.py`,
which is a thin façade over the decomposed modules in this package:

- `checks/`       — individual diagnostic checks (cpu, memory, disk, api, db, cache)
- `actions/`      — remediation actions (reconnect cache, gc, etc.)
- `circuit_breaker.py` — per-check consecutive-failure cooldown
- `orchestrator.py` — runs checks, applies actions, coordinates with circuit
                     breakers
- `reporter.py`   — posts events to the central orchestrator HTTP endpoint
- `metrics.py`    — in-memory stats (success/failure/recovery time) exposed
                    via `/api/admin/self-healing/stats`

The autonomous_scheduler registers the active agent via `set_active_agent`
so the admin router can read its stats without needing app.state wiring.
"""

from __future__ import annotations

_active_agent = None  # type: ignore[assignment]


def set_active_agent(agent) -> None:  # noqa: ANN001 — avoid import cycle
    """Register the process-wide self-healing agent (called by the scheduler)."""
    global _active_agent
    _active_agent = agent


def get_active_agent():  # noqa: ANN201
    """Return the registered agent, or None if the scheduler didn't wire one."""
    return _active_agent
