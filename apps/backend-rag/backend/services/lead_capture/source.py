"""LeadSource enum — the 6 homepage apps that can emit a lead intent.

Kept in a dedicated module so pydantic models, repository, routers,
and the matcher cron all import from one place and stay in sync.
"""

from __future__ import annotations

from enum import Enum


class LeadSource(str, Enum):
    VISA_CLOCK = "visa_clock"
    VISA_MATCH = "visa_match"
    GARUDA_VOA = "garuda_voa"
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
    # Property funnel sources (2026-08-07): Ask Zantara chat on
    # /property/eligibility and article-page CTAs on property articles.
    # Enum lands first; call-sites follow in a separate frontend PR once
    # CI parity is confirmed (WIRE/RETIRE audit pending).
    PROPERTY_CHAT_QUESTION = "property_chat_question"
    PROPERTY_ARTICLE_CTA = "property_article_cta"

    @property
    def human_name(self) -> str:
        """Human-friendly name for the WhatsApp deeplink template."""
        return {
            LeadSource.VISA_CLOCK: "Visa Clock",
            LeadSource.VISA_MATCH: "Visa Match",
            LeadSource.GARUDA_VOA: "the VOA request check",
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
            LeadSource.PROPERTY_CHAT_QUESTION: "the Property Eligibility chat",
            LeadSource.PROPERTY_ARTICLE_CTA: "the Property article",
        }[self]

    @property
    def result_url_path(self) -> str | None:
        """The live public result URL path, or ``None`` when retired/absent."""
        return {
            LeadSource.VISA_CLOCK: "/visa/clock",
            LeadSource.VISA_MATCH: "/visa/match",
            # GARUDA is an owner-only archive plus stateless internal preview.
            # Historical rows still decode, but no new public deeplink may
            # resurrect its retired URL.
            LeadSource.GARUDA_VOA: None,
            LeadSource.KBLI_DECODER: "/kbli/decoder",
            LeadSource.KBLI_BUILDER: "/kbli/builder",
            LeadSource.TAX_GAP: "/taxes/gap",  # live page moved PR #3629 Aug 2026
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
            LeadSource.PROPERTY_CHAT_QUESTION: "/property/eligibility",
            LeadSource.PROPERTY_ARTICLE_CTA: "/property/eligibility",
        }[self]


class PublicLeadSource(str, Enum):
    """Lead sources accepted by the public capture API.

    ``LeadSource.GARUDA_VOA`` intentionally remains in the persistence enum so
    historical rows continue to decode. It is absent here because the public
    GARUDA funnel is retired.
    """

    VISA_CLOCK = LeadSource.VISA_CLOCK.value
    VISA_MATCH = LeadSource.VISA_MATCH.value
    KBLI_DECODER = LeadSource.KBLI_DECODER.value
    KBLI_BUILDER = LeadSource.KBLI_BUILDER.value
    TAX_GAP = LeadSource.TAX_GAP.value
    ZONING_CHECK = LeadSource.ZONING_CHECK.value
    ARTICLE = LeadSource.ARTICLE.value
    KBLI_NAVIGATOR = LeadSource.KBLI_NAVIGATOR.value
    ZANTARA_WIDGET_HANDOFF = LeadSource.ZANTARA_WIDGET_HANDOFF.value
    CTA_HANDOFF = LeadSource.CTA_HANDOFF.value
    PRICING_MODAL = LeadSource.PRICING_MODAL.value
    HOMEPAGE_HERO = LeadSource.HOMEPAGE_HERO.value
    PROPERTY_CHAT_QUESTION = LeadSource.PROPERTY_CHAT_QUESTION.value
    PROPERTY_ARTICLE_CTA = LeadSource.PROPERTY_ARTICLE_CTA.value

    def to_persisted(self) -> LeadSource:
        """Return the storage enum after public-input validation."""
        return LeadSource(self.value)
