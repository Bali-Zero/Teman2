"""Unit tests for the WhatsApp deeplink builder."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from backend.services.lead_capture.source import LeadSource
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
            wa_number="628213107363",
            public_host="https://balizero.com",
        )
        assert url.startswith("https://wa.me/628213107363?text=")

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
            wa_number="+62 821 310 7363",
        )
        assert url.startswith("https://wa.me/628213107363?")


class TestSourceEnum:
    def test_all_sources_have_names(self):
        for s in LeadSource:
            assert s.human_name
            assert s.result_url_path.startswith("/")
