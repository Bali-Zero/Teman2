"""Confirm-code extraction — the ONLY thing pulled out of inbound text/button
payloads before F6's CAS transitions ever see it.

F6 verbatim: "Meta interactive buttons (opaque payloads `confirm:<code>`)
preferred; numbered/code fallback (`CONFERMA 7F3K`) where buttons
unavailable." and, immediately before that: "the executor calls the CRM
with the STORED payload — post-confirmation text never touches the
arguments."

These two clauses coexist because they are about DIFFERENT things: the
short_code is a ROUTING KEY (which PendingAction is this about), never one
of the mutation's ARGUMENTS. Both parsers below extract ONLY the code and
discard everything else in the message — "CONFERMA 7F3K per giovedì" yields
the code "7F3K" and nothing else; "per giovedì" is never read, never
stored, never merged into any args. That is what makes the two clauses
consistent rather than contradictory.

MANDATE F6's own text requires the CODE even in the text-fallback path —
this is STRICTER than Kimi's original proposal (LENS 6 §2), whose bare-word
matcher (``sì|si|ok|confermo|yes``, no code) is sufficient only under
Kimi's own reasoning that "one pending mutation per actor" already
disambiguates. A bare "sì" is far likelier to fire by accident in an async
WhatsApp thread than a random alnum code is, so this module implements the
FROZEN, stricter requirement: a bare "sì"/"ok"/"yes" with no code is never
treated as a confirmation, and — for the same reason — the keyword
("conferma"/"confirm"/"konfirmasi") is REQUIRED, not optional: a bare code
floating anywhere in an ordinary message is not distinguishable from
incidental text (see below), so this parser only extracts a code that
IMMEDIATELY follows the keyword.

REAL COLLISION FOUND WHILE BUILDING THIS (documented, not hidden): a naive
"any 4-12 char alnum token anywhere in the message" scan matches the
NUMERIC TAIL of a practice/client ID — "PR-3090" contains "3090", a valid
4-digit token. Two independent fixes close this: (1) ``SHORT_CODE_PATTERN``
(models.py) requires at least one LETTER, which "3090" fails and every
GENERATED code (store.py) always satisfies; (2) this module's text pattern
requires the code to appear immediately after the keyword, not anywhere in
the message, so an unrelated ID mentioned elsewhere in the same reply is
never a candidate at all.

Author: Claude Sonnet 5 (lane B3 — team-bot confirmation state machine)
"""

from __future__ import annotations

import re

from .models import is_valid_short_code

__all__ = ["parse_confirmation_button_payload", "parse_confirmation_text"]

_BUTTON_PREFIX = "confirm:"

# Keyword MANDATORY, code must immediately follow (only whitespace/colon in
# between) — never a scan of the rest of the message.
_TEXT_PATTERN = re.compile(
    r"\b(?:conferma|confirm|konfirmasi)\b\s*:?\s*([A-Za-z0-9]{4,12})\b",
    re.IGNORECASE,
)


def parse_confirmation_button_payload(payload: str) -> str | None:
    """Meta interactive button postback, e.g. ``confirm:7F3K``. Returns the
    upper-cased code, or ``None`` if the payload is not a confirm postback
    or the code shape is invalid (including a pure-digit token — see
    module docstring). Uses ``is_valid_short_code`` (models.py), the single
    source of truth for shape-AND-letter-requirement — never a local copy."""
    if not payload.startswith(_BUTTON_PREFIX):
        return None
    code = payload[len(_BUTTON_PREFIX) :].strip().upper()
    return code if is_valid_short_code(code) else None


def parse_confirmation_text(text: str) -> str | None:
    """Fallback path for surfaces without interactive buttons. Requires the
    literal keyword ("conferma"/"confirm"/"konfirmasi") IMMEDIATELY
    followed by an alnum code containing at least one letter — a bare
    "sì"/"ok"/"yes" never matches, and a code-shaped ID fragment elsewhere
    in the message (a practice/client ID) never matches either, since it
    is not adjacent to the keyword. Case-insensitive; the matched code is
    normalized to upper-case to match how short_codes are generated
    (``store.py``).
    """
    match = _TEXT_PATTERN.search(text)
    if match is None:
        return None
    code = match.group(1).upper()
    return code if is_valid_short_code(code) else None
