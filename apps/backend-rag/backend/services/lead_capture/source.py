"""LeadSource enum — the 6 homepage apps that can emit a lead intent.

Kept in a dedicated module so pydantic models, repository, routers,
and the matcher cron all import from one place and stay in sync.
"""

from __future__ import annotations

from enum import Enum


class LeadSource(str, Enum):
    VISA_CLOCK = "visa_clock"
    VISA_MATCH = "visa_match"
    KBLI_DECODER = "kbli_decoder"
    KBLI_BUILDER = "kbli_builder"
    TAX_GAP = "tax_gap"
    ZONING_CHECK = "zoning_check"
    # Content-funnel sources (2026-06): blog articles + KBLI Navigator pages.
    ARTICLE = "article"
    KBLI_NAVIGATOR = "kbli_navigator"
    # Conversational handoff (2026-06): the Zantara chat widget, after the
    # visitor sends 3+ messages (high-intent signal). No result page.
    ZANTARA_WIDGET_HANDOFF = "zantara_widget_handoff"

    @property
    def human_name(self) -> str:
        """Human-friendly name for the WhatsApp deeplink template."""
        return {
            LeadSource.VISA_CLOCK: "Visa Clock",
            LeadSource.VISA_MATCH: "Visa Match",
            LeadSource.KBLI_DECODER: "KBLI Decoder",
            LeadSource.KBLI_BUILDER: "KBLI Builder",
            LeadSource.TAX_GAP: "Tax Gap",
            LeadSource.ZONING_CHECK: "Zoning Check",
            LeadSource.ARTICLE: "the Insights blog",
            LeadSource.KBLI_NAVIGATOR: "the KBLI Navigator",
            LeadSource.ZANTARA_WIDGET_HANDOFF: "the Zantara chat",
        }[self]

    @property
    def result_url_path(self) -> str:
        """The public result URL path for a given source (without host)."""
        return {
            LeadSource.VISA_CLOCK: "/visa/clock",
            LeadSource.VISA_MATCH: "/visa/match",
            LeadSource.KBLI_DECODER: "/kbli/decoder",
            LeadSource.KBLI_BUILDER: "/kbli/builder",
            LeadSource.TAX_GAP: "/tax/gap",
            LeadSource.ZONING_CHECK: "/zoning",
            # Articles carry their own URL in context; no hash-based result page.
            LeadSource.ARTICLE: "/",
            # KBLI Navigator: result_hash = the KBLI code → /kbli/<code>.
            LeadSource.KBLI_NAVIGATOR: "/kbli",
            # Chat widget: no result page; the visitor carries the conversation
            # context in the WA message body, not a hash-addressed page.
            LeadSource.ZANTARA_WIDGET_HANDOFF: "/",
        }[self]
