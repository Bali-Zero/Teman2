"""Deterministic detector + notifier for "I want to talk to a human" (B2.5-2).

WHY THIS EXISTS
----------------
A client who asks to speak to a person is the highest-intent message the bot
ever receives — it is a lead. Today nothing on the Meta Inbox channel detects
it: the message falls through to retrieval, abstains, and reaches nobody.

CONTRACT — Half A, ``match_human_request`` (identical shape to ``wa_greeting``
/ ``wa_identity``): pure, no I/O, no LLM, never raises. Whole-TOKEN phrase
matching over an NFKC/casefolded/punctuation-stripped normalization, same
discipline as the two siblings. Five languages: id, en, it, ru, uk.

**THE VETO IS INVERTED HERE.** ``wa_identity`` vetoes any message naming a
case topic, because a question about a case is not a question about the
assistant. For THIS guard the opposite is true: "voglio parlare con una
persona riguardo alla mia PT PMA" is exactly the message that must match — a
client naming their case while asking for a human is the most valuable lead
of all. There is deliberately no ``_DOMAIN_VETO_TOKENS`` here.

Deliberately NOT matched (innocence, judged not vetoed): a third-person
question about staff ("chi è il notaio che usate?", "siapa konsultan yang
menangani kasus saya?" — asking WHO, not asking FOR one) and a question about
the bot's own nature ("sei un umano?", "are you human?" — ``wa_identity``'s
vocabulary, not this module's). Neither is in the phrase table, so both
return ``None`` without needing an explicit veto.

Two authorities can both claim one message ("are you human or can I talk to a
person" matches both this module and ``wa_identity``). The call site decides
the order and a test pins it — see ``wa_codex_leg.py``.

CONTRACT — Half B, ``notify_human_handoff``: async, does I/O (DB read +
email), never raises (the caller still wraps it — see the call site comment
for why a defensive belt-and-suspenders layer lives there too). Resolves the
consultant via ``meta_inbox_threads.counterpart_phone`` -> ``clients.phone``/
``clients.whatsapp`` -> ``clients.assigned_to`` (``meta_inbox_threads`` has no
assignee column of its own), falls back to ``zero@balizero.com``. Dedup reuses
``human_escalation_notifier``'s per-thread 30-minute TTL map rather than a
second one, under a namespaced key so this channel's window never
cross-suppresses an unrelated Telegram escalation on the same thread.

PII: the phone number is used ONLY to resolve the consultant, in-process. It
never appears in the email subject/body/log. The email body is a fixed
Bahasa Indonesia sentence — never the client's verbatim text — precisely
because a robust "free of identifiers" classifier is out of scope for this
slice's size budget; when in doubt, the mandate says omit, so this omits
always.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.app.services.internal_email import send_internal_email
from backend.services.integrations.human_escalation_notifier import (
    _already_escalated,
    _recent_escalations,
)
from backend.services.whatsapp_identity import normalize_phone

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger("zantara.backend")

# ── Half A: the pure detector ───────────────────────────────────────────────

# Core phrases only ("parlare con una persona", not every modal-verb prefix
# of it) — the whole-window scan below finds a core phrase anywhere inside a
# longer sentence, so "voglio PARLARE CON UNA PERSONA riguardo alla mia PT
# PMA" and the bare core phrase match identically.
_HUMAN_REQUEST_PHRASES: dict[str, str] = {
    # Italian
    "parlare con una persona": "it",
    "parlare con un umano": "it",
    "parlare con un operatore": "it",
    "parlare con un consulente": "it",
    "parlare con qualcuno": "it",
    # English
    "talk to a human": "en",
    "talk to a person": "en",
    "speak to a human": "en",
    "speak to a person": "en",
    "talk to an agent": "en",
    "speak to someone": "en",
    "talk to a consultant": "en",
    # Indonesian
    "bicara dengan manusia": "id",
    "bicara dengan orang": "id",
    "bicara dengan konsultan": "id",
    "bicara dengan admin": "id",
    "ngobrol dengan orang": "id",
    # Russian
    "поговорить с человеком": "ru",
    "поговорить с консультантом": "ru",
    "поговорить с оператором": "ru",
    # Ukrainian
    "поговорити з людиною": "uk",
    "поговорити з консультантом": "uk",
    "поговорити з оператором": "uk",
}

_MAX_PHRASE_TOKENS = max(len(p.split()) for p in _HUMAN_REQUEST_PHRASES)

# A human request may carry a whole case description — a looser brake than
# the greeting/identity modules', but still a bound: whatever slips past the
# phrase rules, a very long message is never matched from a canned string.
_MAX_HUMAN_TOKENS = 60
_MAX_HUMAN_CHARS = 400

_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+", flags=re.UNICODE)

_HUMAN_REQUEST_CONFIRMATIONS: dict[str, str] = {
    "id": "Baik, saya sampaikan ke kolega kami — mereka akan segera menghubungi Anda.",
    "en": "Sure — I'm flagging this for a colleague, who will reach out to you shortly.",
    "it": "Certo, lo segnalo a un collega: ti contatterà a breve.",
    "ru": "Хорошо, я передаю это коллеге — он свяжется с вами в ближайшее время.",
    "uk": "Добре, я передаю це колезі — він зв'яжеться з вами найближчим часом.",
}

_FALLBACK_LANG = "en"


@dataclass(frozen=True)
class HumanRequestTurn:
    """A matched human-handoff request and the confirmation to send back."""

    language: str
    text: str


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation/emoji, collapse whitespace. NFKC first."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    stripped = _PUNCT_RE.sub(" ", folded)
    return _WS_RE.sub(" ", stripped).strip()


def match_human_request(text: str | None) -> HumanRequestTurn | None:
    """Return the confirmation turn when `text` asks to reach a human.

    Never raises, never performs I/O. `None` means "not my business" — the
    normal route (or another authority) still runs.
    """
    if not text:
        return None

    if len(text) > _MAX_HUMAN_CHARS:
        return None

    normalized = _normalize(text)
    if not normalized:
        return None

    tokens = normalized.split()
    if not tokens or len(tokens) > _MAX_HUMAN_TOKENS:
        return None

    for start in range(len(tokens)):
        for span in range(min(_MAX_PHRASE_TOKENS, len(tokens) - start), 0, -1):
            phrase = " ".join(tokens[start : start + span])
            language = _HUMAN_REQUEST_PHRASES.get(phrase)
            if language is not None:
                reply = (
                    _HUMAN_REQUEST_CONFIRMATIONS.get(language)
                    or _HUMAN_REQUEST_CONFIRMATIONS[_FALLBACK_LANG]
                )
                return HumanRequestTurn(language=language, text=reply)

    return None


# ── Half B: the notification (I/O — NOT pure, unlike match_human_request) ──

_ASSIGNEE_LOOKUP_SQL = """
SELECT id, assigned_to
  FROM clients
 WHERE NULLIF(regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g'), '')
       IN ($1, '62' || $1, '0' || $1)
    OR NULLIF(regexp_replace(COALESCE(whatsapp, ''), '[^0-9]', '', 'g'), '')
       IN ($1, '62' || $1, '0' || $1)
 ORDER BY id
 LIMIT 1
"""

_FALLBACK_RECIPIENT = "zero@balizero.com"
_EMAIL_TYPE = "wa_human_handoff"


async def _resolve_assignee(
    pool: asyncpg.Pool, counterpart_phone: str | None
) -> tuple[int | None, str | None]:
    """thread's phone -> clients row -> (client_id, assigned_to email).

    Best-effort: any DB error resolves to (None, None) so the caller falls
    back to the fixed recipient rather than losing the notification.
    """
    normalized = normalize_phone(counterpart_phone)
    if not normalized:
        return None, None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(_ASSIGNEE_LOOKUP_SQL, normalized)
    except Exception as exc:
        logger.warning("wa_human_handoff: assignee lookup failed: %s", type(exc).__name__)
        return None, None
    if row is None:
        return None, None
    assigned_to = (row["assigned_to"] or "").strip() or None
    return row["id"], assigned_to


async def notify_human_handoff(
    pool: asyncpg.Pool,
    *,
    thread_id: int,
    counterpart_phone: str | None,
    language: str,
) -> bool:
    """Tell a human this thread's client asked for one. Never raises.

    Dedup: per-thread 30-minute window, reusing
    ``human_escalation_notifier``'s TTL map under a namespaced key (this
    channel is email, not Telegram — only the mechanism is shared).
    Returns True only on an actually-sent email; False on dedup suppression.
    """
    dedup_key = f"human_handoff:{thread_id}"
    if _already_escalated(dedup_key):
        logger.info("wa_human_handoff: suppressed thread=%s (dedup window)", thread_id)
        return False

    client_id, assignee = await _resolve_assignee(pool, counterpart_phone)
    to_email = assignee or _FALLBACK_RECIPIENT

    body_lines = [
        "Klien meminta untuk berbicara dengan kolega manusia melalui WhatsApp.",
        "",
        f"Thread: {thread_id}",
    ]
    if client_id is not None:
        body_lines.append(f"Client ID: {client_id}")
    body_lines.append(f"Bahasa klien: {language}")
    body_lines.append("")
    body_lines.append("Silakan buka thread di konsol operator untuk membaca detailnya.")

    await send_internal_email(
        to=to_email,
        subject=f"[WA] Klien minta bicara dengan manusia — thread {thread_id}",
        body="\n".join(body_lines),
        email_type=_EMAIL_TYPE,
        pool=pool,
        client_id=client_id,
    )
    _recent_escalations[dedup_key] = time.monotonic()
    return True
