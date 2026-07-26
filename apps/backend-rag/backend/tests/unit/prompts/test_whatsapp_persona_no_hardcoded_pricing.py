"""W0 safety pre-arm — item 3: whatsapp_persona.py must never hardcode prices.

CLAUDE.md Golden Rule 11: "All prices from PricingTool. Never hardcode."
`backend/prompts/whatsapp_persona.py` previously loaded
`backend/data/bali_zero_official_prices_2026.json` at import time and baked
a full, language-localized price table directly into the WA system prompt
string returned by `build_system_prompt()`. That table goes stale the
moment prices change without a matching prompt-module edit, and it
duplicates (redundantly, and via a second unmanaged code path) the pricing
policy already carried by the shared `ZANTARA_MASTER_TEMPLATE` base prompt
("CALL get_pricing tool, NEVER invent/estimate/guess ANY price" —
zantara_core.py). The landmine: this file is reachable today from
`backend/app/routers/whatsapp_chat.py`'s in-process DIRECT RAG fallback
branch (a `_BOTH`-registered, live-mounted router per
`router_manifest.py:374`) — the hardcoded table would silently start lying
about prices, or leak stale numbers to a NEW `phone_number_id` onboarding
through that path, without anyone touching this file.

Guilt/innocence:
- GUILT: the built system prompt must never contain the old hardcoded price
  table's header strings or any concrete "Rp <digits>" price figure.
- INNOCENCE: everything else `build_system_prompt()` renders (client
  context, greeting logic, the CRITICAL expert-consultant rule, response
  language instruction, and the base template's own get_pricing-tool
  policy) must be completely unaffected by the removal.
"""

from __future__ import annotations

import re

import pytest

from backend.prompts import whatsapp_persona

_LANGS = ["en", "it", "id", "de"]

# The 3 removed localized headers — must never appear again.
_REMOVED_PRICE_HEADERS = [
    "OFFICIAL BALI ZERO 2026 PRICE LIST",
    "LISTINO PREZZI UFFICIALE BALI ZERO 2026",
    "DAFTAR HARGA RESMI BALI ZERO 2026",
    "OFFIZIELLE BALI ZERO 2026 PREISLISTE",
]

_PRICE_FIGURE_RE = re.compile(r"Rp\s?[\d.,]{4,}")


class TestNoHardcodedPriceLoadingMachinery:
    def test_price_loader_function_removed(self):
        assert not hasattr(whatsapp_persona, "_load_full_pricing")

    def test_pricing_tables_dict_removed(self):
        assert not hasattr(whatsapp_persona, "_PRICING_TABLES")

    def test_pricing_table_alias_removed(self):
        assert not hasattr(whatsapp_persona, "_PRICING_TABLE")

    def test_format_2026_entry_helper_removed(self):
        assert not hasattr(whatsapp_persona, "_format_2026_entry")


class TestBuildSystemPromptNoHardcodedPricing:
    @pytest.mark.parametrize("lang", _LANGS)
    def test_no_price_list_header(self, lang):
        prompt = whatsapp_persona.build_system_prompt(detected_language=lang)
        for header in _REMOVED_PRICE_HEADERS:
            assert header not in prompt

    @pytest.mark.parametrize("lang", _LANGS)
    def test_no_new_concrete_price_figures_beyond_the_base_template(self, lang):
        """ZANTARA_MASTER_TEMPLATE (zantara_core.py — hard off-limits, not
        touched by this fix) carries its OWN 2 'Rp <digits>' occurrences as
        a worked example of correctly citing a get_pricing-tool result, not
        a static table. This asserts whatsapp_persona.py's own additions
        contribute ZERO price figures on top of that baseline — not that
        the fully-assembled prompt has none at all, which would incorrectly
        require editing the off-limits base template."""
        from backend.prompts.zantara_core import ZANTARA_MASTER_TEMPLATE

        baseline_count = len(_PRICE_FIGURE_RE.findall(ZANTARA_MASTER_TEMPLATE))
        prompt = whatsapp_persona.build_system_prompt(detected_language=lang)
        prompt_count = len(_PRICE_FIGURE_RE.findall(prompt))
        assert prompt_count == baseline_count

    @pytest.mark.parametrize("lang", _LANGS)
    def test_no_exchange_rate_line(self, lang):
        prompt = whatsapp_persona.build_system_prompt(detected_language=lang)
        assert "15.385 IDR" not in prompt
        assert "15,385 IDR" not in prompt


class TestBuildSystemPromptInnocence:
    """Everything NOT related to pricing must survive unchanged."""

    def test_client_name_still_injected(self):
        prompt = whatsapp_persona.build_system_prompt(
            client_name="Test Client", detected_language="en"
        )
        assert "Test Client" in prompt

    def test_first_message_greeting_note_present(self):
        prompt = whatsapp_persona.build_system_prompt(
            is_first_message=True, detected_language="en"
        )
        assert "greet once" in prompt.lower()

    def test_non_first_message_no_greeting_note_present(self):
        prompt = whatsapp_persona.build_system_prompt(
            is_first_message=False, detected_language="en"
        )
        assert "no greeting" in prompt.lower()

    @pytest.mark.parametrize("lang", _LANGS)
    def test_expert_consultant_rule_still_present(self, lang):
        prompt = whatsapp_persona.build_system_prompt(detected_language=lang)
        # Each language's expert_rule uses its own word: en "expert",
        # it "esperto", id "ahli", de "Experte".
        lowered = prompt.lower()
        assert (
            "expert" in lowered
            or "esperto" in lowered
            or "ahli" in lowered
            or "experte" in lowered
        )

    @pytest.mark.parametrize("lang", _LANGS)
    def test_get_pricing_tool_instruction_still_reaches_the_prompt(self, lang):
        """This comes from the shared ZANTARA_MASTER_TEMPLATE base prompt
        (zantara_core.py), untouched by this fix — asserts the removal of
        the hardcoded table did not also remove the real policy."""
        prompt = whatsapp_persona.build_system_prompt(detected_language=lang)
        assert "get_pricing" in prompt

    def test_few_shot_examples_untouched(self):
        assert len(whatsapp_persona.FEW_SHOT_EXAMPLES) == 18

    def test_system_instruction_module_constant_still_builds(self):
        """SYSTEM_INSTRUCTION = build_system_prompt() at import time must
        not raise and must still be a non-empty string."""
        assert isinstance(whatsapp_persona.SYSTEM_INSTRUCTION, str)
        assert len(whatsapp_persona.SYSTEM_INSTRUCTION) > 0
