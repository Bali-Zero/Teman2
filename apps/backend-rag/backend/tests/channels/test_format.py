"""Tests for backend.channels.format — channel-aware message formatting.

Client-voice hardening (2026-07-25): the WhatsApp Meta-inbox bot
(`wa_inbox_bot.py`) ships `format_rich_text(answer, "whatsapp")` on the
answer text it sends to real clients. This suite proves the formatter is
correct for WhatsApp's actual rendering rules (*bold*, _italic_,
```monospace``` — no headings, no **bold**, no markdown bullets/links) and
that the new bare-citation-marker strip is narrow enough to leave
legitimate bracketed content (named regulations, KBLI codes) untouched.

Each behavior gets a GUILT case (the defect is fixed) AND an INNOCENCE
case (a legitimate neighboring pattern is not mangled) per
`.claude/rules/cicatrix-superscar.md` family #3 discipline.
"""

from __future__ import annotations

from backend.channels.format import format_rich_text

# ── WhatsApp: headings / bold ────────────────────────────────────────────


def test_whatsapp_converts_heading_to_bold():
    assert format_rich_text("### Key Features", "whatsapp") == "*Key Features*"


def test_whatsapp_converts_double_asterisk_bold_to_single():
    assert format_rich_text("**Initial Validity**: 1 year", "whatsapp") == (
        "*Initial Validity*: 1 year"
    )


def test_whatsapp_does_not_treat_bold_opener_as_a_bullet():
    """Innocence: a line that STARTS with **bold** (no space after the
    first '*') must not be mistaken for a bullet marker — only an actual
    '* '/'- ' bullet prefix (asterisk/hyphen + whitespace) qualifies."""
    result = format_rich_text("**Important**: read this carefully", "whatsapp")
    assert result == "*Important*: read this carefully"
    assert "•" not in result


# ── WhatsApp: bullet lists ───────────────────────────────────────────────


def test_whatsapp_converts_asterisk_bullets_to_unicode_bullet():
    result = format_rich_text("* Item one\n* Item two", "whatsapp")
    assert result == "• Item one\n• Item two"


def test_whatsapp_converts_hyphen_bullets_to_unicode_bullet():
    result = format_rich_text("- Passport valid 6+ months\n- 2 photos", "whatsapp")
    assert result == "• Passport valid 6+ months\n• 2 photos"


def test_whatsapp_bullet_with_inline_bold_resolves_cleanly():
    """Guilt: the exact shape from the production evidence — a bullet whose
    body is itself **bold**, e.g. '*   **Initial Validity & Stay:** 1 year'.
    Order matters: bullet-normalize before bold-convert."""
    result = format_rich_text("*   **Initial Validity & Stay:** 1 year (365 days)", "whatsapp")
    assert result == "• *Initial Validity & Stay:* 1 year (365 days)"
    # No dangling double-asterisk or malformed adjacent-asterisk noise.
    assert "**" not in result


def test_whatsapp_preserves_mid_sentence_hyphen():
    """Innocence: a hyphen NOT at line-start (prose, not a bullet) is left
    alone — only a line-leading '- ' is treated as a bullet marker."""
    result = format_rich_text("Jakarta - Bali direct route", "whatsapp")
    assert result == "Jakarta - Bali direct route"


# ── WhatsApp: markdown links ─────────────────────────────────────────────


def test_whatsapp_converts_markdown_link_to_text_with_url():
    result = format_rich_text("[Apply here](https://forms.balizero.com/x)", "whatsapp")
    assert result == "Apply here (https://forms.balizero.com/x)"


def test_whatsapp_preserves_bracket_space_paren_as_not_a_link():
    """Innocence: '[NPWP] (mandatory)' has a SPACE between ']' and '(' —
    genuine markdown link syntax requires them adjacent, so this must not
    be treated as a link and mangled."""
    result = format_rich_text("[NPWP] (mandatory for all)", "whatsapp")
    assert result == "[NPWP] (mandatory for all)"


# ── WhatsApp: code / horizontal rules ────────────────────────────────────


def test_whatsapp_strips_code_fence_markers():
    result = format_rich_text("```\nplain block\n```", "whatsapp")
    assert "```" not in result
    assert "plain block" in result


def test_whatsapp_strips_inline_code_backticks():
    assert format_rich_text("Use `get_pricing` tool", "whatsapp") == "Use get_pricing tool"


def test_whatsapp_strips_horizontal_rule():
    result = format_rich_text("Before\n---\nAfter", "whatsapp")
    assert "---" not in result
    assert "Before" in result and "After" in result


# ── WhatsApp: bare numeric citation markers ──────────────────────────────


def test_whatsapp_strips_single_bare_citation_marker():
    result = format_rich_text("Initial validity is 1 year (365 days) [5].", "whatsapp")
    assert result == "Initial validity is 1 year (365 days)."


def test_whatsapp_strips_multi_bare_citation_marker():
    result = format_rich_text("As stated [1, 5] in the regulation.", "whatsapp")
    assert result == "As stated in the regulation."


def test_whatsapp_preserves_named_regulation_citation():
    """Innocence: a real, letter-bearing regulation/entity reference must
    survive — only a DIGITS-ONLY bracket group is a citation-index match."""
    for legit in ("[PP 48/2021]", "[Art. 26]", "[KBLI 70100]", "[E33G]"):
        result = format_rich_text(f"See {legit} for details.", "whatsapp")
        assert legit in result, f"{legit!r} was incorrectly stripped: {result!r}"


# ── WhatsApp: full production-shaped regression ──────────────────────────


def test_whatsapp_full_evidence_snippet_is_clean():
    """Regression pinned to the exact defect reported against production:
    a real client-bound answer with heading, bold, bullet, and a bare
    citation marker must come out WhatsApp-clean (no literal markdown
    syntax noise) end to end."""
    raw = (
        "Hey! Here is the official breakdown for the remote worker visa path.\n"
        "### Key Features\n"
        "*   **Initial Validity & Stay:** 1 year (365 days) ... [5]"
    )
    result = format_rich_text(raw, "whatsapp")
    for forbidden in ("###", "**", "[5]"):
        assert forbidden not in result, f"{forbidden!r} leaked into: {result!r}"
    assert "*Key Features*" in result
    assert "• *Initial Validity & Stay:*" in result


# ── WhatsApp: plain text passthrough (no false positives) ────────────────


def test_whatsapp_plain_text_is_unchanged():
    plain = "Il KITAS investitore parte da 17.000.000 IDR per un anno."
    assert format_rich_text(plain, "whatsapp") == plain


# ── Instagram/Twitter: bare citation markers also stripped ──────────────


def test_instagram_strips_bare_citation_marker():
    result = format_rich_text("Valid for 1 year [5].", "instagram")
    assert result == "Valid for 1 year."


def test_instagram_preserves_named_regulation_citation():
    result = format_rich_text("See [PP 48/2021] for details.", "instagram")
    assert "[PP 48/2021]" in result


# ── Telegram / Web: unaffected passthrough (out of scope for this fix) ──


def test_telegram_passthrough_keeps_bare_citation_marker():
    """Telegram/web are explicitly out of scope — they pass markdown
    through untouched, citations included. Only WhatsApp/Instagram/Twitter
    (channels with no footnote-rendering surface) get the new strip."""
    text = "See details [1, 5] here."
    assert format_rich_text(text, "telegram") == text
    assert format_rich_text(text, "web") == text
