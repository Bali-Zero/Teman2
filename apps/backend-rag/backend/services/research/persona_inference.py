"""Persona inference — builds 6 personas from source signals + LLM synthesis.

Pipeline (Fase 0 days 4-5):
  Day 4 (wave 1): 3 expat personas
      - expat_boomer_retiree (EU/NA retirees, 55-70)
      - expat_techie_pma (founders/developers, 30-45)
      - expat_italian_aire (Italian nationals registered AIRE)
  Day 5 (wave 2): 3 ID domestic personas
      - id_konsultan_kadin (senior KADIN advisors, 40-60)
      - id_founder_pma (Indonesian startup founders, 28-45)
      - id_umkm_digital (UMKM digital-first practitioners, 25-40)

For each persona:
  1. NotebookLM / Gemini reads the source signals listed in
     EXPAT_SOURCES / ID_SOURCES and synthesizes a structured profile
  2. DeepSeek (if budget allows) or a second LLM falsifies weak claims
  3. Output merged into `04_personas.json`

Gate 4 invariant (EOD day 5): 6 personas, each with ≥15 populated
attribute fields + ≥3 verbatim quotes from real comments.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger(__name__)


class PersonaValidationError(ValueError):
    """Raised when a persona fails Gate 4 invariants."""


@dataclass
class Persona:
    # Identity fields — not counted in populated_attrs
    slug: str
    market_segment: str  # expat | id_domestic

    # 16 countable attribute fields (Gate 4 min: ≥15 populated)
    age_range: str = ""
    geo_origin: str = ""
    gender_split: str = ""
    profession_past: str = ""
    wealth_level: str = ""
    primary_goal: str = ""
    pain_points: list[str] = field(default_factory=list)
    platforms_used: list[str] = field(default_factory=list)
    content_preferences: list[str] = field(default_factory=list)
    language_primary: str = ""
    language_secondary: list[str] = field(default_factory=list)
    decision_journey_stages: list[str] = field(default_factory=list)
    tone_resonance: dict[str, float] = field(default_factory=dict)
    hook_patterns_that_work: list[str] = field(default_factory=list)
    verbatim_quotes: list[str] = field(default_factory=list)
    trust_signals: list[str] = field(default_factory=list)

    # Identity field names (not counted in populated_attrs)
    _IDENTITY_FIELDS = frozenset({"slug", "market_segment"})

    def count_populated_attrs(self) -> int:
        """Count non-empty attribute fields.

        Empty string / empty list / empty dict all count as unpopulated.
        Identity fields (slug, market_segment) are excluded.
        """
        data = asdict(self)
        count = 0
        for key, value in data.items():
            if key in self._IDENTITY_FIELDS:
                continue
            if isinstance(value, str) and value:
                count += 1
            elif isinstance(value, (list, dict)) and len(value) > 0:
                count += 1
        return count

    def validate(self) -> None:
        """Gate 4 invariants: ≥15 populated attrs, ≥3 verbatim quotes."""
        attrs = self.count_populated_attrs()
        if attrs < 15:
            raise PersonaValidationError(
                f"persona {self.slug!r} needs at least 15 attribute "
                f"fields populated, got {attrs}"
            )
        if len(self.verbatim_quotes) < 3:
            raise PersonaValidationError(
                f"persona {self.slug!r} needs at least 3 verbatim quotes, "
                f"got {len(self.verbatim_quotes)}"
            )


class PersonaInferenceAgent:
    """Declares source-signal mappings per persona slug.

    Actual LLM synthesis runs in `scripts/sota_infer_personas.py` (Task 15)
    which shells out to gemini CLI per slug with the relevant source list
    and the output schema derived from the Persona dataclass.
    """

    # Per-slug source signals. Each entry is a human-readable identifier
    # (Instagram handle, Facebook group name, LinkedIn community, etc.).
    # NotebookLM/Gemini interprets these as research pointers.
    EXPAT_SOURCES: dict[str, list[str]] = {
        "expat_boomer_retiree": [
            "@balibuddha",
            "@nomadgate",
            "@reneesylvestre",
            "Facebook group: Bali Expats",
            "r/bali (reddit, retiree threads 2024-26)",
        ],
        "expat_techie_pma": [
            "@solopreneur_bali",
            "@digitalnomadworld",
            "@nomadsembassy",
            "LinkedIn: founders relocated to Bali 2024-26",
            "IndoHackers / PT PMA founder Slack communities",
        ],
        "expat_italian_aire": [
            "Italian-language expat FB groups Bali",
            "LinkedIn Italian PMA founders Indonesia",
            "@balibuddha (Italian commenters)",
            "Bali Zero client base with AIRE registration",
        ],
    }

    ID_SOURCES: dict[str, list[str]] = {
        "id_konsultan_kadin": [
            "LinkedIn KADIN senior members",
            "IG @kadin_indonesia + @bkpm_id followers",
            "Indonesian legal forums (hukum online) 2024-26",
        ],
        "id_founder_pma": [
            "LinkedIn Indonesian startup founders 2023-26",
            "IG @startupindonesia community",
            "Tech in Asia Indonesia founder interviews",
        ],
        "id_umkm_digital": [
            "LinkedIn UMKM digital practitioners",
            "TikTok Indonesian small business content",
            "Instagram @tokopedia / @shopeeindonesia creator posts",
        ],
    }
