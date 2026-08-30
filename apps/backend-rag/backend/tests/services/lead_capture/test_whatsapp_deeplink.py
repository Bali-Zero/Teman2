"""Unit tests for the WhatsApp deeplink builder."""

from __future__ import annotations

import logging
from urllib.parse import parse_qs, urlparse

from backend.app.routers.lead_capture import LeadCaptureRequest
from backend.services.lead_capture.source import LeadSource, PublicLeadSource
from backend.services.lead_capture.whatsapp_deeplink import build_whatsapp_url


def _body_from(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    return qs["text"][0]


class TestDeeplinkBuilder:
    def test_basic_structure(self):
        url = build_whatsapp_url(
            source=LeadSource.VISA_CLOCK,
            context_lines=[("Visa", "E33G"), ("Expiry", "1 Dec 2026")],
            result_hash="abcdef",
            lead_intent_id="li_xyz",
            wa_number="628213454721",
            public_host="https://balizero.com",
        )
        assert url.startswith("https://wa.me/628213454721?text=")

    def test_body_contains_app_name(self):
        url = build_whatsapp_url(
            source=LeadSource.VISA_MATCH,
            context_lines=[],
            result_hash=None,
            lead_intent_id="li_xyz",
        )
        body = _body_from(url)
        assert "Visa Match" in body

    def test_body_includes_context_bullets(self):
        url = build_whatsapp_url(
            source=LeadSource.VISA_CLOCK,
            context_lines=[("Visa", "E33G"), ("Entry", "2025-01-01")],
            result_hash="abcdef0123456789",
            lead_intent_id="li_xyz",
        )
        body = _body_from(url)
        assert "• Visa: E33G" in body
        assert "• Entry: 2025-01-01" in body

    def test_body_includes_reference_and_lead_id(self):
        url = build_whatsapp_url(
            source=LeadSource.VISA_MATCH,
            context_lines=[("Visa", "E33G")],
            result_hash="abcdef0123456789",
            lead_intent_id="li_xyz",
            public_host="https://balizero.com",
        )
        body = _body_from(url)
        assert "Reference: https://balizero.com/visa/match/abcdef0123456789" in body
        assert "Lead ID: li_xyz" in body

    def test_skips_reference_when_no_hash(self):
        url = build_whatsapp_url(
            source=LeadSource.ZONING_CHECK,
            context_lines=[],
            result_hash=None,
            lead_intent_id="li_xyz",
        )
        body = _body_from(url)
        assert "Reference:" not in body

    def test_retired_garuda_source_never_emits_public_result_path(self):
        url = build_whatsapp_url(
            source=LeadSource.GARUDA_VOA,
            context_lines=[("Case", "internal")],
            result_hash="legacyhash",
            lead_intent_id="li_legacy",
            public_host="https://balizero.com",
        )
        body = _body_from(url)
        assert "/visa/voa" not in body
        assert "Reference:" not in body

    def test_debug_log_never_contains_raw_message_body(self, caplog):
        private_value = "visitor-private-context"
        with caplog.at_level(
            logging.DEBUG,
            logger="backend.services.lead_capture.whatsapp_deeplink",
        ):
            build_whatsapp_url(
                source=LeadSource.VISA_CLOCK,
                context_lines=[("Case", private_value)],
                result_hash="abc123",
                lead_intent_id="li_private",
            )
        assert private_value not in caplog.text
        assert "Hi Bali Zero" not in caplog.text

    def test_ignores_empty_context_values(self):
        url = build_whatsapp_url(
            source=LeadSource.TAX_GAP,
            context_lines=[("Visa", ""), ("Entry", "2025-01-01")],
            result_hash=None,
            lead_intent_id="li_xyz",
        )
        body = _body_from(url)
        assert "Visa:" not in body  # empty value should be dropped
        assert "Entry: 2025-01-01" in body

    def test_cleans_phone_number_with_plus_and_spaces(self):
        url = build_whatsapp_url(
            source=LeadSource.VISA_CLOCK,
            context_lines=[],
            result_hash=None,
            lead_intent_id="li_xyz",
            wa_number="+62 821 3454 721",
        )
        assert url.startswith("https://wa.me/628213454721?")


class TestContentFunnelSources:
    """ARTICLE + KBLI_NAVIGATOR — the content-funnel sources (2026-06)."""

    def test_kbli_navigator_reference_points_to_code_page(self):
        url = build_whatsapp_url(
            source=LeadSource.KBLI_NAVIGATOR,
            context_lines=[("KBLI", "56303"), ("Business", "Bar")],
            result_hash="56303",
            lead_intent_id="li_kbli1",
            public_host="https://balizero.com",
        )
        body = _body_from(url)
        assert "the KBLI Navigator" in body
        assert "Reference: https://balizero.com/kbli/56303" in body
        assert "Lead ID: li_kbli1" in body

    def test_article_source_has_no_reference_line(self):
        url = build_whatsapp_url(
            source=LeadSource.ARTICLE,
            context_lines=[("Article", "Indonesia UMKM tax reforms")],
            result_hash=None,
            lead_intent_id="li_art1",
        )
        body = _body_from(url)
        assert "the Insights blog" in body
        assert "Reference:" not in body
        assert "• Article: Indonesia UMKM tax reforms" in body


class TestPricingModalSource:
    """PRICING_MODAL — ServicePricing.tsx modal CTA (2026-06-29)."""

    def test_pricing_modal_has_no_reference_line(self):
        url = build_whatsapp_url(
            source=LeadSource.PRICING_MODAL,
            context_lines=[("Package", "Single Entry Visa")],
            result_hash=None,
            lead_intent_id="li_price1",
        )
        body = _body_from(url)
        assert "the pricing page" in body
        assert "Reference:" not in body
        assert "• Package: Single Entry Visa" in body


class TestSourceEnum:
    def test_all_sources_have_names(self):
        for s in LeadSource:
            assert s.human_name
            if s is LeadSource.GARUDA_VOA:
                assert s.result_url_path is None
            else:
                assert s.result_url_path is not None
                assert s.result_url_path.startswith("/")

    def test_public_capture_accepts_garuda_but_never_resurrects_its_url(self):
        """The RETIRED half of #4344 is the URL, not the capture.

        Until 2026-08-28 this asserted the opposite — that the public capture
        API REJECTS `garuda_voa` — which was correct when #4344 (2026-08-21)
        retired the then-public GARUDA routes. Four days later #4960 relaunched
        the funnel dark-by-flag, and its result page captures under exactly this
        source (`apps/mouth/src/app/visa/voa/[hash]/page.tsx`, the ACCEPT branch:
        "prefer a human to walk you through it", offered right after the price
        stamp). Two encoded intents in direct conflict; the newer one is the
        ratified product (owner decision 5, "Concept A — The Stamp").

        So the assertion is inverted, NOT deleted, and #4344's other half is
        pinned here in the same breath: `result_url_path` stays None, so no new
        public deeplink can resurrect the retired URL. The lead is captured; the
        WA body simply carries no "Reference:" line.

        Flipping this does NOT make anything public: `/visa/voa/*` is gated
        server-side in `layout.tsx` on `GARUDA_PUBLIC_ENABLED`, which is off on
        Vercel (product.yaml: `status: build-dark`, `owner_signed_at: null`,
        go_live `state: blocked-...`). It only means that WHEN the owner flips
        that flag, the funnel's highest-intent handoff writes a lead row instead
        of 422'ing into the bare wa.me link.
        """
        req = LeadCaptureRequest.model_validate({"source": "garuda_voa"})
        assert req.source is PublicLeadSource.GARUDA_VOA
        assert req.source.to_persisted() is LeadSource.GARUDA_VOA
        assert LeadSource.GARUDA_VOA.result_url_path is None

    def test_historical_garuda_value_still_decodes(self):
        assert LeadSource("garuda_voa") is LeadSource.GARUDA_VOA
        assert "garuda_voa" in {source.value for source in PublicLeadSource}

    def test_content_funnel_values_are_stable(self):
        # Wire-format values: the mouth frontend sends these literal strings.
        assert LeadSource.ARTICLE.value == "article"
        assert LeadSource.KBLI_NAVIGATOR.value == "kbli_navigator"
        # HeroCTA.tsx posts source="homepage_hero". It shipped 2026-07-06
        # against an enum that did not carry the value: the router's
        # `source: LeadSource` rejected every homepage hero click with 422
        # until 2026-07-16, so the site's single primary CTA wrote no
        # lead_intents row for 10 days. Pinning the wire value here.
        assert LeadSource("homepage_hero") is LeadSource.HOMEPAGE_HERO
