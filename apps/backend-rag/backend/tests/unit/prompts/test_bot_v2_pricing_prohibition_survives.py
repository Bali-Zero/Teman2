"""BOT-V2 gate (task #14) — PricingTool-only invariant, real gap fill.

Per the invariant walkthrough in `research/operations/2026-08-15-bot-openai-
provider-threat-model.md` §(b) ("PricingTool-only pricing"): a model swap
changes nothing about this invariant IN PRINCIPLE, but a different model's
function-calling reliability can silently make it invent a price MORE often
than the current provider did on the same prompt — the invariant that must
survive any provider change is not "the words get_pricing appear somewhere"
but the actual PROHIBITION sentence that stops a model from guessing.

`apps/backend-rag/backend/tests/unit/prompts/
test_whatsapp_persona_no_hardcoded_pricing.py` already pins that
`"get_pricing" in prompt` (its `test_get_pricing_tool_instruction_still_
reaches_the_prompt`) — but that alone would still pass if a refactor kept
the bare word "get_pricing" somewhere while dropping the actual "NEVER
invent/estimate/guess ANY price" prohibition. This file pins the stronger,
previously-unpinned claim: the prohibition SENTENCE itself, verbatim,
in `backend/prompts/zantara_core.py::ZANTARA_MASTER_TEMPLATE` (the v1
template `prompt_manager.get_master_template()` currently serves —
verified this session by direct execution).

Guilt/innocence per cicatrix-superscar.md family #3: the guilt case is a
pure helper tested in isolation (so this test corpus is not vacuous even
before touching the real template), then the SAME helper is run as a
contract test against the real, live template.
"""

from __future__ import annotations

from backend.prompts.zantara_core import ZANTARA_MASTER_TEMPLATE

_REQUIRED_PROHIBITION_PHRASES = (
    "ONLY USE PRICES FROM get_pricing TOOL",
    "NEVER invent, estimate, or guess ANY price",
)


def _forbids_price_invention(text: str) -> bool:
    """True only when EVERY required prohibition phrase is present verbatim.

    Deliberately a real (if small) function under test, not just a bare
    `in` check inline in the assertion — so the guilt/innocence pair below
    exercises actual logic, matching this repo's scar-#3 guard discipline
    rather than a one-line tautology."""
    return all(phrase in text for phrase in _REQUIRED_PROHIBITION_PHRASES)


# ── Guilt: a template missing the prohibition must be caught ────────────────


def test_guilt_template_without_pricing_rule_fails() -> None:
    fake_template = "You are a helpful assistant. Answer questions about visas."
    assert _forbids_price_invention(fake_template) is False


def test_guilt_template_with_only_partial_phrase_fails() -> None:
    """A refactor that keeps 'get_pricing' mentioned but drops the actual
    anti-invention prohibition — the exact silent-regression shape the
    threat model's PricingTool row warns about — must still be caught."""
    fake_template = "Use the get_pricing tool when relevant."
    assert _forbids_price_invention(fake_template) is False


# ── Innocence: a template carrying the full prohibition passes ──────────────


def test_innocence_template_with_full_rule_passes() -> None:
    fake_template = (
        "**RULE 1: ONLY USE PRICES FROM get_pricing TOOL**\n"
        "- **NEVER invent, estimate, or guess ANY price** (not ranges)\n"
    )
    assert _forbids_price_invention(fake_template) is True


# ── Contract test on the real hook: the live template actually serves this ──


def test_live_master_template_still_forbids_price_invention() -> None:
    """The regression floor: whatever provider answers, the served system
    prompt must still carry this exact prohibition. Fails loud if a future
    prompt-version bump (v1→v5, or a provider-swap refactor) drops it."""
    assert _forbids_price_invention(ZANTARA_MASTER_TEMPLATE) is True
