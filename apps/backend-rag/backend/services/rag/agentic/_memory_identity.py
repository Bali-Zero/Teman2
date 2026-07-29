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

THE W-1 ITEM, 2026-07-27 (``derive_wa_memory_subject`` below)
-------------------------------------------------------------
Containment left every WhatsApp client with no memory at all, which is the
safe state but not the right one. This function mints the per-sender
pseudonymous subject the note above promised, under four rules — each one
closing a hole that the P0s of the preceding week actually opened:

1. **Trust comes from the dedicated bot key, never from the request body.**
   The subject is derived only when the caller proved it is
   ``wa_inbox_bot`` (``X-WA-Bot-Profile-Key``). Deriving it from a
   body-supplied ``user_id`` alone would rebuild P0-ID as a memory bug:
   any holder of the widely-shared ``X-Internal-Key`` could send
   ``user_id="whatsapp_<someone else's number>"`` and READ that person's
   memory. Same shape, worse blast radius.

2. **HMAC, not a bare hash.** A phone number has almost no entropy — the
   Indonesian mobile space is enumerable in minutes, so ``sha256(phone)``
   is reversible by brute force and is therefore not a pseudonym, just the
   phone number wearing a hat. Keying the digest with a server-side secret
   makes the mapping computable only by us. UU PDP Art. 67-68.

3. **Fail-closed on every input.** No salt, no bot key, no phone → ``None``
   → the caller keeps today's containment behaviour. The feature cannot
   arm itself by accident; provisioning the secret is the deliberate act
   that turns it on.

4. **Rotating the salt is a memory wipe, not a key rotation.** Every subject
   changes, so every client silently starts from zero. That is a product
   decision, not an ops chore — which is why this secret is its own, and
   not borrowed from ``wa_inbox_bot_profile_key`` (whose rotation must stay
   a routine, consequence-free act).
"""

from __future__ import annotations

import hmac
import re
from hashlib import sha256

#: Everything that is not a digit is noise in a phone number: "+62 821-3465-159",
#: "62821-3465159" and "+628213465159" must map to ONE subject, or the same
#: client gets a fresh memory every time the formatting shifts upstream.
_NON_DIGITS = re.compile(r"\D+")

#: Namespace prefix. Keeps a WA subject from ever colliding with the other
#: things that anchor memory here (emails, UUIDs) and makes the origin of a
#: row in the memory store readable at a glance.
WA_MEMORY_SUBJECT_PREFIX = "wa:"

#: Hex chars kept from the digest. 32 hex = 128 bits: collision-free for any
#: plausible client book, and short enough to stay legible in logs.
_SUBJECT_HEX_LEN = 32

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


def derive_wa_memory_subject(
    *,
    is_trusted_wa_bot: bool,
    phone: str | None,
    salt: str | None,
) -> str | None:
    """Stable per-sender pseudonymous memory subject for a WhatsApp client.

    See the module docstring for the four rules this obeys and why each
    exists. All three arguments are keyword-only and each is a gate: the
    function returns ``None`` — meaning "keep the P0-MEM containment
    behaviour, no long-term memory" — unless every one of them is satisfied.

    Args:
        is_trusted_wa_bot: The request carried ``wa_inbox_bot``'s OWN
            dedicated secret (``_verify_wa_inbox_bot_profile_key``). A
            generic internal-key holder must NOT reach a subject, or reading
            someone else's memory becomes a matter of typing their number.
        phone: The sender's number, already extracted from the WA-shaped
            ``user_id`` by the caller that owns that regex. Any formatting
            accepted; normalised to digits here.
        salt: Server-side secret (``settings.wa_memory_subject_salt``).
            Absent → the feature is off.

    Returns:
        ``"wa:<32 hex>"``, or ``None`` if any gate fails.
    """
    if not is_trusted_wa_bot or not phone or not salt:
        return None

    digits = _NON_DIGITS.sub("", phone)
    if not digits:
        return None

    digest = hmac.new(salt.encode("utf-8"), digits.encode("utf-8"), sha256).hexdigest()
    return f"{WA_MEMORY_SUBJECT_PREFIX}{digest[:_SUBJECT_HEX_LEN]}"
