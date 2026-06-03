"""Read-only access to local Postgres for the corpus-miner.

Functions take an open psycopg2 connection so they are easy to use under a
single transaction and easy to point at a test DB.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


def _digits(phone: str | None) -> str:
    return re.sub(r"[^0-9]", "", phone or "")


# Capitalized tokens that are NOT client names: sentence-initial words (EN/ID),
# common chat words, and Bali Zero brand terms. Keeps count_distinct_names from
# inflating on a normal 1-a-1 chat (e.g. "What/How/Can/Please/Bali/Zero").
_NAME_STOPWORDS = frozenset(
    {
        # EN sentence-initial / common
        "the", "and", "but", "for", "you", "your", "yes", "not", "now", "can",
        "could", "would", "should", "will", "what", "when", "where", "which",
        "who", "why", "how", "this", "that", "these", "those", "here", "there",
        "have", "has", "had", "are", "was", "were", "its", "our", "their", "his",
        "her", "please", "thanks", "thank", "hello", "hai", "hey", "bro", "sir",
        "madam", "ok", "okay", "good", "morning", "afternoon", "evening", "night",
        "nothing", "something", "anything", "last", "next", "first", "today",
        "tomorrow", "yesterday", "with", "from", "about", "still", "just", "only",
        "need", "want", "send", "sent", "let", "got", "get",
        # ID common
        "iya", "tidak", "terima", "kasih", "selamat", "pagi", "siang", "sore",
        "malam", "saya", "kamu", "kita", "ini", "itu", "sudah", "belum", "untuk",
        "dengan", "yang",
        # Brand / org
        "bali", "zero", "balizero", "kitas", "visa", "pma", "indonesia", "denpasar",
        "whatsapp", "email", "gmail", "google",
    }
)


@dataclass(frozen=True)
class Pair:
    team_member_phone: str
    counterpart_phone: str
    n_msgs: int


@dataclass(frozen=True)
class ChatLine:
    direction: str
    message_date: datetime | None
    text: str


def iter_pairs(conn, *, min_msgs: int = 1) -> list[Pair]:
    """All direct (team, counterpart) pairs with >= min_msgs messages."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT team_member_phone, counterpart_phone, COUNT(*) AS n
        FROM whatsapp_message_context
        WHERE chat_type='direct'
          AND counterpart_phone IS NOT NULL
          AND team_member_phone IS NOT NULL
        GROUP BY team_member_phone, counterpart_phone
        HAVING COUNT(*) >= %s
        ORDER BY n DESC
        """,
        (min_msgs,),
    )
    return [Pair(t, c, n) for (t, c, n) in cur.fetchall()]


def fetch_chat(conn, team_phone: str, counterpart_phone: str) -> list[ChatLine]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT direction, message_date,
               COALESCE(NULLIF(body,''), NULLIF(message_text,''), '') AS txt
        FROM whatsapp_message_context
        WHERE chat_type='direct'
          AND team_member_phone=%s AND counterpart_phone=%s
        ORDER BY message_date NULLS LAST, id
        """,
        (team_phone, counterpart_phone),
    )
    return [ChatLine(d, m, t) for (d, m, t) in cur.fetchall()]


def get_contact_type(conn, counterpart_phone: str) -> str | None:
    """contact_type from whatsapp_contacts, matched by normalized digits."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT contact_type FROM whatsapp_contacts
        WHERE regexp_replace(phone_normalized,'[^0-9]','','g') = %s
        LIMIT 1
        """,
        (_digits(counterpart_phone),),
    )
    row = cur.fetchone()
    return row[0] if row else None


def is_team_member(conn, phone: str) -> bool:
    """True if the phone belongs to the Bali Zero team.

    Two independent signals, either suffices (team batte client/prospect):
      1. whatsapp_contacts.contact_type='team' for this number, OR
      2. the number appears as a team_member_phone in mirrored chats (it is one
         of the team's own outbound lines).
    """
    digits = _digits(phone)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM whatsapp_contacts
        WHERE contact_type='team'
          AND regexp_replace(phone_normalized,'[^0-9]','','g') = %s
        LIMIT 1
        """,
        (digits,),
    )
    if cur.fetchone():
        return True
    cur.execute(
        """
        SELECT 1
        FROM whatsapp_message_context
        WHERE regexp_replace(team_member_phone,'[^0-9]','','g') = %s
        LIMIT 1
        """,
        (digits,),
    )
    return cur.fetchone() is not None


def is_in_crm(conn, phone: str) -> bool:
    """True if the phone matches a row in the clients table (already a client).

    Matched against both clients.phone_normalized and clients.whatsapp.
    """
    digits = _digits(phone)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1 FROM clients
        WHERE regexp_replace(COALESCE(phone_normalized,''),'[^0-9]','','g') = %s
           OR regexp_replace(COALESCE(whatsapp,''),'[^0-9]','','g') = %s
        LIMIT 1
        """,
        (digits, digits),
    )
    return cur.fetchone() is not None


def crm_name(conn, phone: str) -> str | None:
    """Return the CRM display name for a phone, or None if not a client.

    Prefers clients.full_name; falls back to company_name. Matched against both
    phone_normalized and whatsapp. Used by the naming rule (Doc title = CRM name
    when the counterpart is already a client, else the phone number).
    """
    digits = _digits(phone)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT NULLIF(TRIM(full_name),''), NULLIF(TRIM(company_name),'')
        FROM clients
        WHERE regexp_replace(COALESCE(phone_normalized,''),'[^0-9]','','g') = %s
           OR regexp_replace(COALESCE(whatsapp,''),'[^0-9]','','g') = %s
        LIMIT 1
        """,
        (digits, digits),
    )
    row = cur.fetchone()
    if not row:
        return None
    full_name, company_name = row
    return full_name or company_name


def count_distinct_names(conn, team_phone: str, counterpart_phone: str) -> int:
    """Rough count of distinct client-like names mentioned in the chat body.

    Heuristic proxy for 'is this one person or a channel'. Counts distinct
    capitalized first-name tokens of length >=3, excluding common sentence-initial
    / chat / brand words (_NAME_STOPWORDS) that would otherwise inflate the count.
    """
    lines = fetch_chat(conn, team_phone, counterpart_phone)
    return _distinct_names_in_texts(ln.text for ln in lines)


def _distinct_names_in_texts(texts) -> int:
    names: set[str] = set()
    for text in texts:
        for tok in re.findall(r"\b[A-Z][a-z]{2,}\b", text):
            if tok.lower() not in _NAME_STOPWORDS:
                names.add(tok)
    return len(names)


def latest_message_at(conn, team_phone: str, counterpart_phone: str) -> datetime | None:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT MAX(message_date) FROM whatsapp_message_context
        WHERE chat_type='direct' AND team_member_phone=%s AND counterpart_phone=%s
        """,
        (team_phone, counterpart_phone),
    )
    return cur.fetchone()[0]
