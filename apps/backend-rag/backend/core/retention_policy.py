"""
Conversation retention policy — single source of truth.

Decided by Zero on 2026-08-08, two answers:

  (a) "5 anni"        — we must be able to reconstruct *what we told this
                        client* for five years. That is the horizon of
                        Indonesian tax/legal exposure, not of a chat log.
  (b) "non cancellare" — nothing leaves on a clock.

This module exists because the rule has more than one enforcement point and a
rule written twice is a rule that will diverge. Both clock-driven doors onto
`conversations` import from here:

  * `backend/app/routers/admin_conversation_cleanup.py` (HTTP, admin-keyed)
  * `backend/db/repositories/conversation_repository.py` (used by
    `backend/jobs/conversation_cleanup.py`, whose own defaults were 30d/7d)

WHAT THIS DOES **NOT** COVER, deliberately — do not "consistently" extend it:

  * `DELETE /api/conversations/clear` and the single-conversation delete in
    `conversations.py` are **per-subject erasure**, authenticated by JWT and
    requested by the data subject. UU PDP Art. 43 gives that right, and a
    retention floor must never stand in front of it. The floor governs
    *clock-driven bulk* deletion only — time is not a request.
  * Test fixtures that clean up their own rows.

Why a floor rather than a doc: the previous arrangement WAS a doc, and it lost.
The nightly cron asked for `delete_after_days=30 anonymize_after_days=7` while
the router's own defaults said 90/30; the drift was written down on 2026-07-14
("docs dicono 7d/30d, endpoint live fa 30d/90d — rilevante per review UU PDP")
and never acted on. Anonymising at 7 days would have destroyed the five-year
requirement within a week. The only reason it did not is that `backend_rag_v2`
holds no DELETE grant on `conversations`, so the destructive path failed every
night while the dry run returned 200. An accident is not a control.

Measured 2026-08-08: the oldest row in the conversation stack is 2025-12-31, so
no row is due for any retention action before 2030-12-31. Nothing here is
racing a deadline.
"""

import os

# 5 years, leap-inclusive.
RETENTION_MIN_DAYS = 1826

# Answer (b). The switch exists so the capability is recoverable without a code
# change if the policy ever changes, and is named so that enabling it is a
# deliberate, visible act rather than a default someone inherits.
ALLOW_CLOCK_DELETE_ENV = "CONVERSATION_RETENTION_ALLOW_CLOCK_DELETE"


class RetentionPolicyViolation(ValueError):
    """Raised when a caller asks for a retention window the policy forbids.

    A ValueError subclass so that callers which already narrow on ValueError
    keep working; distinct so the HTTP layer can map it to a 400 that names the
    policy instead of a generic 500.
    """


def enforce_retention_floor(label: str, days: int) -> None:
    """Reject any retention window shorter than the five-year floor.

    Call this ABOVE any `try:` that swallows exceptions — several of the call
    sites return 0 on error, which would turn a refused policy violation into a
    silent "0 rows affected" success.
    """
    if days < RETENTION_MIN_DAYS:
        raise RetentionPolicyViolation(
            f"{label}={days} is below the {RETENTION_MIN_DAYS}-day (5-year) retention floor. "
            "Policy 2026-08-08: conversations must stay reconstructable for five years. "
            "Erasure on a data-subject request is a separate, per-subject path."
        )


def clock_delete_allowed() -> bool:
    """True only when the operator has deliberately re-enabled timed deletion.

    Read at call time, never cached: the point of the switch is that flipping it
    takes effect on the next call, and a module-level snapshot would make the
    env var a lie for the lifetime of the process.
    """
    return os.getenv(ALLOW_CLOCK_DELETE_ENV, "").strip().lower() in ("1", "true")
