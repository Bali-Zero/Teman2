"""Shared late-incident state-transition logic (anti-drift).

Both the unauthenticated email-token form (`hr_late_reply.py`) and the
authenticated gate endpoint (`POST /api/hr/my-late-incident/resolve`) must apply
the SAME state transition when a worker explains a late arrival. Per spec §4.2
("do NOT duplicate the logic, extract it to a shared helper") this module is the
single source of truth for that transition.

Transition (mirrors the original inline map in hr_late_reply.py):
    AWAITING_REPLY → RESOLVED        (replied on time, before reminder)
    REMINDER_SENT  → RESOLVED_LATE   (replied after a reminder)
    ESCALATED      → ESCALATED        (stays escalated; a reply is recorded but a
                                       manager already owns it — not auto-cleared)

PII / Law 2: operates on the LOCAL Postgres only; `reason` is free text the
worker typed about their own lateness (not third-party PII).
"""

from __future__ import annotations

from backend.services.analytics.attendance_monitor import (
    STATE_AWAITING_REPLY,
    STATE_REMINDER_SENT,
    STATE_RESOLVED,
    STATE_RESOLVED_LATE,
)

# The canonical transition map. ESCALATED (and any unknown) is preserved.
_NEXT_STATE: dict[str, str] = {
    STATE_AWAITING_REPLY: STATE_RESOLVED,
    STATE_REMINDER_SENT: STATE_RESOLVED_LATE,
}


def next_state_for(current_state: str) -> str:
    """Return the state a late incident moves to once a reason is submitted.

    AWAITING_REPLY→RESOLVED, REMINDER_SENT→RESOLVED_LATE, else unchanged
    (ESCALATED stays ESCALATED — a manager already owns it).
    """
    return _NEXT_STATE.get(current_state, current_state)
