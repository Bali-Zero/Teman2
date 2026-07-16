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
    # Sticky "Next actions" handoff bar — shared CTAHandoff component across all funnel pages (2026-06).
    CTA_HANDOFF = "cta_handoff"
    # Pricing page modal CTA (2026-06-29): ServicePricing.tsx package
    # selection modal, /services/[slug] pages. No fixed hash route — the
    # service slug + package name are carried in context, not result_hash.
    PRICING_MODAL = "pricing_modal"
    # Homepage hero primary CTA (2026-07-06 frontend, enum landed 2026-07-16):
    # HeroCTA.tsx, the single red primary action of balizero.com. Shipped
    # against this enum before the value existed, so every hero click 422'd
    # and fell back to the bare wa.me link — clicks tracked, leads unlogged.
    # No result page: the visitor has not run a tool, they came off the hero.
    HOMEPAGE_HERO = "homepage_hero"

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
            LeadSource.CTA_HANDOFF: "Bali Zero",
            LeadSource.PRICING_MODAL: "the pricing page",
            LeadSource.HOMEPAGE_HERO: "the homepage",
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
            # Sticky handoff bar lives on the page already in context; no hash-based result page.
            LeadSource.CTA_HANDOFF: "/",
            # No fixed hash route — service slug varies; carried in context.
            LeadSource.PRICING_MODAL: "/",
            # The hero IS the homepage; no tool result to link back to.
            LeadSource.HOMEPAGE_HERO: "/",
        }[self]
