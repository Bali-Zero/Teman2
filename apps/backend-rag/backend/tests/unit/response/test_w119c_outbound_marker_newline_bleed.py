r"""W119c — a marker-stripping rule must never eat the line after its marker.

Three rules on the bot's OUTBOUND path used `\s` as the separator between a
marker and its own text. `\s` matches a newline, so when the marker line was
EMPTY the separator swallowed its own newline and the rule went on to consume
the FOLLOWING line — which is the client's answer.

    THOUGHT:                          ->  (marker line removed, correct)
    Here is the real answer.              Here is the real answer.   <- DELETED

The trigger is narrower than "any leaked scratchpad": it needs the marker line
to be empty. That is stated plainly because the fix should be judged on what it
actually prevents. But the direction is the unsafe one — content the client was
meant to read is deleted silently, on every channel — so it is worth a character.

`[^\S\n]` here, NOT `[ \t]`. These rules run on natural-language text, where a
non-breaking space or other exotic separator is legitimate and matching it is
the CORRECT behaviour; the repo learned that in
`test_redos_anchor_patterns.py`, where a first-draft `[ \t\r]` silently dropped
NBSP and form-feed out of OCR'd legal PDFs. Note the opposite choice is right
for the command guards in `infra/claude-hooks/` (`[ \t]`, W119b/W119c there):
matching LESS is safe when a miss falls through to a block, and matching MORE is
safe when a miss deletes a customer's answer. The direction of the failure picks
the character, not house style.
"""

from __future__ import annotations

import re

import pytest

from backend.channels.format import format_rich_text
from backend.utils.response_sanitizer import sanitize_zantara_response

REAL = "The capital gains rate for a PT PMA depends on your KBLI sector."


# --- guilt: the content loss each rule caused ---------------------------------


@pytest.mark.parametrize("marker", ["THOUGHT", "ACTION", "OBSERVATION"])
def test_w119c_an_empty_agentic_marker_does_not_delete_the_answer(marker):
    out = sanitize_zantara_response(f"{marker}:\n{REAL}\nSecond line.\n")
    assert REAL in out, f"{marker}: ate the answer -> {out!r}"


@pytest.mark.parametrize("marker", ["THOUGHT", "ACTION", "OBSERVATION"])
def test_w119c_a_populated_agentic_marker_line_is_still_removed(marker):
    """Innocence: the rule must keep doing the job it exists for."""
    out = sanitize_zantara_response(f"{marker}: I should look up the KBLI table.\n{REAL}\n")
    assert marker.lower() not in out.lower(), out
    assert REAL in out, out


def test_w119c_an_empty_user_query_marker_does_not_delete_the_answer():
    from backend.services.response.cleaner import _MARKER_PATTERNS

    pat = next(p for p in _MARKER_PATTERNS if "User Query" in getattr(p, "pattern", str(p)))
    rx = pat if isinstance(pat, re.Pattern) else re.compile(pat, re.MULTILINE)
    out = rx.sub("", f"User Query:\n{REAL}\nMore of the real answer.\n")
    assert REAL in out, out


# --- guilt + innocence: the WhatsApp/Telegram heading conversion ---------------


def test_w119c_a_bare_hash_does_not_bold_the_next_paragraph_as_a_heading():
    out = format_rich_text("###\n" + REAL + "\nAnd more.\n", "whatsapp")
    assert f"*{REAL}*" not in out, out


def test_w119c_a_real_heading_is_still_converted():
    out = format_rich_text("## Pajak Penghasilan\nbody text\n", "whatsapp")
    assert "*Pajak Penghasilan*" in out, out


def test_w119c_a_heading_separated_by_a_non_breaking_space_is_still_converted():
    """Why `[^\\S\n]` and not `[ \t]` on this path: NBSP is real text, not an attack."""
    out = format_rich_text("## Pajak Penghasilan\nbody\n", "whatsapp")
    assert "*Pajak Penghasilan*" in out, out


# --- the class ----------------------------------------------------------------


def test_w119c_no_outbound_marker_rule_matches_across_a_newline():
    r"""Behavioural, not a source grep: assert on spans, so reintroducing the
    defect with `[^|]`, `[\s\S]` or `.` under DOTALL is caught too."""
    from backend.services.response.cleaner import _MARKER_PATTERNS

    probe = "THOUGHT:\n" + REAL + "\nUser Query:\nAnother real line.\n"
    for pat in _MARKER_PATTERNS:
        rx = pat if isinstance(pat, re.Pattern) else re.compile(pat, re.MULTILINE)
        for m in rx.finditer(probe):
            span = m.group(0)
            # a rule may legitimately END on its own newline; it may not contain
            # a newline with non-whitespace after it (that is the next line).
            assert not re.search(r"\n\s*\S", span), f"{rx.pattern!r} spanned: {span!r}"
