"""Plan A Task 4 — lead_source inference helper for SEO attribution.

Tests pure helper ``_infer_lead_source`` only. Full INSERT path covered by
integration tests (require TEST_DATABASE_URL).

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2
Plan: docs/superpowers/plans/2026-04-19-seo-cell-A-prenatal-foundation.md Task 4
"""

from __future__ import annotations

import pytest

from backend.db.repositories.client_repository import _infer_lead_source


def test_explicit_lead_source_wins() -> None:
    payload = {"lead_source": "referral", "landing_page": "/visa"}
    assert _infer_lead_source(payload) == "referral"


def test_utm_medium_whatsapp_cta_infers_inbound() -> None:
    payload = {
        "landing_page": "/visa?utm_source=balizero_web&utm_medium=whatsapp_cta&utm_campaign=visa",
    }
    assert _infer_lead_source(payload) == "whatsapp_inbound"


def test_utm_source_whatsapp_infers_inbound() -> None:
    payload = {"landing_page": "/visa?utm_source=whatsapp&utm_campaign=foo"}
    assert _infer_lead_source(payload) == "whatsapp_inbound"


def test_landing_page_without_utm_defaults_to_organic() -> None:
    payload = {"landing_page": "/blog/e33g-cost-2026"}
    assert _infer_lead_source(payload) == "website_organic"


def test_no_lead_source_no_landing_returns_none() -> None:
    payload: dict = {"full_name": "Direct Contact"}
    assert _infer_lead_source(payload) is None


def test_empty_lead_source_treated_as_missing() -> None:
    payload = {"lead_source": "", "landing_page": "/visa"}
    # Empty string is falsy → fall through to landing_page heuristic
    assert _infer_lead_source(payload) == "website_organic"


def test_explicit_overrides_utm_inference() -> None:
    payload = {
        "lead_source": "manual_correction",
        "landing_page": "/?utm_medium=whatsapp_cta",
    }
    assert _infer_lead_source(payload) == "manual_correction"


@pytest.mark.parametrize(
    "landing,expected",
    [
        ("/visa?utm_medium=whatsapp_cta", "whatsapp_inbound"),
        ("/?utm_source=whatsapp", "whatsapp_inbound"),
        ("/blog/anything", "website_organic"),
        ("", None),
    ],
)
def test_landing_page_variants(landing: str, expected: str | None) -> None:
    assert _infer_lead_source({"landing_page": landing}) == expected
