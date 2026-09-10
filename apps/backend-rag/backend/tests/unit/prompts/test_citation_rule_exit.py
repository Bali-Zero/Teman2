"""The citation rule gets an exit (RULED Zero 2026-09-11: ZERO-DECISIONS §Item 3 ratified).

`CITATION_RULES` in `backend/prompts/zantara_core.py` used to say the model MUST cite the
source law at the end of every regulatory answer, with no licit way to cite nothing.
Measured on WhatsApp thread 30 (cycle 359, 2026-09-01): a bank-transfer question closed
with PP 36/2021 (a wages regulation) and a passport-photo refusal cited immigration law.
The ratified bullet cites a law only when a law is the basis of the answer and names the
cases where no source line is the correct answer.

Text-level only: no LLM is called. Whether a live model obeys the new bullet is measured
by the cycle-360 battery, not by this file.

Guilt: the old mandatory bullet is gone from the SSOT and from every built prompt.
Innocence: every consumer that interpolates CITATION_RULES (the v1-v4 master templates,
the three v5 audience builds and the WhatsApp codex-leg persona digest) carries the new
bullet AND the untouched LEGAL/MONEY and CHAT bullets, and the citation format is still
there for answers that do rest on a law: the cure is a replacement, not a silent removal
of citations.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from backend.prompts import zantara_core as v1
from backend.prompts import zantara_core_v2 as v2
from backend.prompts import zantara_core_v3 as v3
from backend.prompts import zantara_core_v4 as v4
from backend.prompts import zantara_core_v5 as v5
from backend.services.rag.agentic.prompt_builder import _safe_template_fill
from backend.services.rag.agentic.wa_package_builder import _build_persona_digest

NEW_BULLET_HEAD = (
    "  - **LAW CITATION — required when a law is the basis, forbidden when it is not.**"
)
KEY_SENTENCE = "required when a law is the basis, forbidden when it is not"
NO_CITATION_CLAUSE = "**Cite NOTHING — and add no source line at all — when:**"
NO_CITATION_CASES = (
    "(a) the question is operational or commercial rather than legal: our prices, our payment",
    "(b) the answer is a courtesy, a greeting, a clarifying question, or a hand-off to a",
    "(c) the KB context you were given contains no regulation that actually governs the answer.",
)
FORMAT_LINE = (
    'Format: "📜 Sumber: [Nama Peraturan], Pasal [X]" or "📜 Source: [Law Name], Article [X]".'
)
LEGAL_MONEY_BULLET = (
    "  - **LEGAL/MONEY:** Use formal markers with exact values from KB, "
    'e.g., "The price is [AMOUNT FROM KB] [1]."'
)
CHAT_BULLET = '  - **CHAT:** Use natural attribution, e.g., "As your founder mentions..."'
OLD_LABEL = "MANDATORY LAW CITATION"
OLD_OBLIGATION = "you MUST cite the source law"


def _new_bullet() -> str:
    """The ratified bullet as it sits in CITATION_RULES, from its head to the closing tag."""
    rules = v1.CITATION_RULES
    start = rules.index(NEW_BULLET_HEAD)
    end = rules.index("</citation_rules>", start)
    return rules[start:end]


def _v5_build(audience: str) -> Callable[[], str]:
    return lambda: v5.build_master_template(audience)


_BUILT_PROMPTS: dict[str, Callable[[], str]] = {
    "v1_master_template": lambda: v1.ZANTARA_MASTER_TEMPLATE,
    "v2_master_template": lambda: v2.ZANTARA_MASTER_TEMPLATE,
    "v3_master_template": lambda: v3.ZANTARA_MASTER_TEMPLATE,
    "v4_master_template": lambda: v4.ZANTARA_MASTER_TEMPLATE,
    **{f"v5_build_{audience}": _v5_build(audience) for audience in v5.VALID_AUDIENCES},
    "wa_codex_persona_digest": _build_persona_digest,
}


class TestGuilt:
    def test_ssot_no_longer_carries_the_mandatory_bullet(self) -> None:
        assert OLD_LABEL not in v1.CITATION_RULES
        assert OLD_OBLIGATION not in v1.CITATION_RULES

    @pytest.mark.parametrize("name", sorted(_BUILT_PROMPTS))
    def test_no_built_prompt_carries_the_mandatory_bullet(self, name: str) -> None:
        built = _BUILT_PROMPTS[name]()
        assert OLD_LABEL not in built
        assert OLD_OBLIGATION not in built


class TestInnocence:
    def test_ssot_carries_the_ratified_bullet(self) -> None:
        bullet = _new_bullet()
        assert KEY_SENTENCE in bullet
        assert NO_CITATION_CLAUSE in bullet
        for case in NO_CITATION_CASES:
            assert case in bullet
        assert FORMAT_LINE in bullet

    def test_legal_money_and_chat_bullets_are_untouched_and_first(self) -> None:
        assert v1.CITATION_RULES.splitlines()[:3] == [
            "<citation_rules>",
            LEGAL_MONEY_BULLET,
            CHAT_BULLET,
        ]

    def test_every_v5_audience_is_covered(self) -> None:
        assert set(v5.VALID_AUDIENCES) == {"client", "team", "creator"}

    @pytest.mark.parametrize("name", sorted(_BUILT_PROMPTS))
    def test_every_consumer_carries_the_new_bullet_and_the_untouched_ones(self, name: str) -> None:
        built = _BUILT_PROMPTS[name]()
        assert _new_bullet() in built
        assert LEGAL_MONEY_BULLET in built
        assert CHAT_BULLET in built


class TestTemplateFillSafety:
    """The prompt goes through `.format()` (v1) and `_safe_template_fill()` (v2-v5)."""

    def test_new_bullet_has_no_braces(self) -> None:
        bullet = _new_bullet()
        assert "{" not in bullet
        assert "}" not in bullet

    def test_citation_rules_survive_str_format_unchanged(self) -> None:
        assert v1.CITATION_RULES.format() == v1.CITATION_RULES

    def test_safe_template_fill_leaves_the_bullet_intact(self) -> None:
        filled = _safe_template_fill(
            v4.ZANTARA_MASTER_TEMPLATE,
            today_wita="Friday, 11 September 2026",
            user_memory="",
            rag_results="",
            query="posso pagare con bonifico?",
        )
        assert _new_bullet() in filled
        assert LEGAL_MONEY_BULLET in filled
        assert OLD_LABEL not in filled
