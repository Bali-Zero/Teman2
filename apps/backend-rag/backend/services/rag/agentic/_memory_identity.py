"""
Single source of truth for "is this user_id a non-personal/shared memory identity?".

WHY (P0-MEM, 2026-07-24)
------------------------
Path B (WhatsApp) authenticates every sender with a SHARED internal key.
``hybrid_auth.py`` resolves that shared key to ONE fixed pseudo-identity —
``user_id="wa-mirror-internal"``, ``email="wa-mirror-internal@balizero.com"`` —
for EVERY WhatsApp sender (there is no per-phone identity resolution yet;
that is a later W-1 item). ``agentic_rag.py`` substitutes this fixed
pseudo-identity as the long-term memory ``user_id``.

Long-term memory was keying on this ONE shared id at two chokepoints:

  * WRITE — ``memory_handler.save_conversation_memory`` only skipped the
    literal string ``"anonymous"``, so every WhatsApp client's facts were
    saved under the shared bucket.
  * READ  — ``context_manager.get_user_context`` fetched facts keyed on
    ``user_id``, so the shared bucket was read back into ANY client's
    context.

Net effect: cross-client memory bleed (UU PDP violation) — client A's
facts could surface in client B's WhatsApp conversation.

This module makes "which identities are non-personal / shared-service,
and therefore must never anchor long-term memory" EXPLICIT, NAMED, and
TESTABLE, and is imported by both chokepoints so they can never drift
out of sync again.

Scope note: this is CONTAINMENT, not the full fix. It does not touch
in-thread ``conversation_history`` (API-supplied per request, not keyed
on this user_id — unaffected) and does not delete any existing shared
facts already persisted under the shared id; it only stops them being
read back, and stops new ones being written. The real fix — resolving
each WhatsApp sender to a stable per-phone pseudonymous subject — is a
later, separate W-1 item.
"""

from __future__ import annotations

# Identities that must NEVER anchor long-term (cross-session) memory —
# they represent either "no authenticated subject" (anonymous) or a
# SHARED service/internal identity backing multiple real end-users
# (wa-mirror-internal, in either bare or email form).
NON_PERSONAL_MEMORY_IDS: frozenset[str] = frozenset(
    {
        "anonymous",
        "wa-mirror-internal",
        "wa-mirror-internal@balizero.com",
    },
)


def is_non_personal_memory_identity(user_id: str | None) -> bool:
    """
    True if ``user_id`` must NOT be used to save or read long-term memory.

    Covers:
      - ``None`` or empty/whitespace-only strings (no real subject).
      - Any identity in :data:`NON_PERSONAL_MEMORY_IDS`, matched
        case-insensitively after stripping surrounding whitespace (e.g.
        ``"WA-Mirror-Internal@BaliZero.com"`` still matches).

    Does NOT do substring/prefix matching (guard-over-match family,
    cicatrix #3) — ``"wa-mirror-internal2"`` or
    ``"somewa-mirror-internal@balizero.com"`` are real, distinct
    identifiers and correctly return ``False``.

    Args:
        user_id: User identifier (email, UUID, or shared-service id).
            ``None``-safe.

    Returns:
        ``True`` if this identity must be excluded from long-term memory
        save/read (anonymous or shared/service identity); ``False`` for a
        real per-user identity.
    """
    if not user_id:
        return True
    normalized = user_id.strip().lower()
    if not normalized:
        return True
    return normalized in NON_PERSONAL_MEMORY_IDS
