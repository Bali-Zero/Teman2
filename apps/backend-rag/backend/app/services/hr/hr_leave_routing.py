"""HR leave request routing — hard-coded org chart rules.

Tax team (*.tax@) → Veronika (tax@balizero.com)
Dea, Rina → Ruslana
Everyone else (including Veronika herself) → Zero

When the org chart changes, update SUPERVISOR_MAP and add tests.
No DB column, no migration: 7 employees, rules stable per Zero (2026-04-07).
"""
from __future__ import annotations

SUPERVISOR_MAP: dict[str, str] = {
    "kadek.tax@balizero.com":    "tax@balizero.com",  # Veronika
    "angel.tax@balizero.com":    "tax@balizero.com",
    "dewa.ayu.tax@balizero.com": "tax@balizero.com",
    "faysha.tax@balizero.com":   "tax@balizero.com",
    "dea@balizero.com":          "ruslana@balizero.com",
    "rina@balizero.com":         "ruslana@balizero.com",
}

ZERO_EMAIL = "zero@balizero.com"
ASYA_EMAIL = "asya@balizero.com"


def _normalize(email: str) -> str:
    return email.lower().strip()


def resolve_approver(requester_email: str) -> str:
    """Return the email of the user who should approve this leave request.

    Falls back to Zero when the requester has no specific supervisor
    configured (e.g. Veronika, Asya, Ruslana, and anyone not in the map).
    """
    return SUPERVISOR_MAP.get(_normalize(requester_email), ZERO_EMAIL)


def build_notification_recipients(
    requester_email: str,
) -> dict[str, str | list[str]]:
    """Return {to, cc[]} for the leave-request notification email.

    Rules:
    - TO: the approver from resolve_approver()
    - Zero always in CC unless he is already the TO
    - Asya always in CC unless she is the requester
    """
    requester = _normalize(requester_email)
    approver = resolve_approver(requester)
    cc: list[str] = []
    if approver != ZERO_EMAIL:
        cc.append(ZERO_EMAIL)
    if requester != ASYA_EMAIL:
        cc.append(ASYA_EMAIL)
    return {"to": approver, "cc": cc}
