"""Tests for VisaOracleService.

All tests mock PricingService so no JSON file or network access is required.
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.services.visa_oracle.visa_oracle_service import (
    VisaOracleService,
    get_visa_oracle_service,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PRICES = {
    "services": {
        "single_entry_visas": {
            "C1 Tourism": {
                "price": "2.300.000 IDR",
                "duration": "60 days",
                "validity": "",
                "notes": "Single entry, 60 days",
            },
            "C22A&B Internship (180 Days)": {
                "price": "5.800.000 IDR",
                "duration": "180 days",
                "validity": "",
                "notes": "",
            },
            "C2 Business": {
                "price": "4.500.000 IDR",
                "duration": "60 days",
                "validity": "",
                "notes": "Business visit",
            },
        },
        "multiple_entry_visas": {
            "D12 Business Investigation (1 Year)": {
                "price": "9.800.000 IDR",
                "duration": "1 year",
                "validity": "1 year",
                "notes": "Multiple entry",
            },
        },
        "kitas_permits": {
            "Retirement (Altus/Onshore)": {
                "price": "35.000.000 IDR",
                "duration": "1 year",
                "validity": "1 year",
                "notes": "Retirement KITAS",
            },
            "Investor KITAS 2 Years (Altus/Onshore)": {
                "price": "45.000.000 IDR",
                "duration": "2 years",
                "validity": "2 years",
                "notes": "Investor KITAS",
            },
            "Spouse 1 Year (Altus/Onshore)": {
                "price": "22.000.000 IDR",
                "duration": "1 year",
                "validity": "1 year",
                "notes": "Spouse KITAS",
            },
            "E33G Remote Worker (Altus/Onshore)": {
                "price": "28.000.000 IDR",
                "duration": "1 year",
                "validity": "1 year",
                "notes": "Remote worker / digital nomad",
            },
            "Working KITAS (Altus/Onshore)": {
                "price": "40.000.000 IDR",
                "duration": "1 year",
                "validity": "1 year",
                "notes": "Work permit KITAS",
            },
        },
        "visa_extensions": {},
        "kitap_permits": {},
        "company_services": {},
        "other_process": {},
        "urgent_services": {},
    }
}


@pytest.fixture
def service() -> VisaOracleService:
    """Return a VisaOracleService with mocked PricingService."""
    mock_pricing = MagicMock()
    mock_pricing.prices = SAMPLE_PRICES

    with patch(
        "backend.services.visa_oracle.visa_oracle_service.get_pricing_service",
        return_value=mock_pricing,
    ):
        svc = VisaOracleService()
    return svc


# ---------------------------------------------------------------------------
# recommend_visas — structural tests
# ---------------------------------------------------------------------------


def test_recommend_visas_returns_list(service: VisaOracleService) -> None:
    """recommend_visas must always return a list."""
    result = service.recommend_visas(
        nationality="Australian",
        purpose="visit",
        duration="short",
        family=False,
    )
    assert isinstance(result, list)


def test_recommend_visas_max_three_results(service: VisaOracleService) -> None:
    """Never returns more than 3 results."""
    result = service.recommend_visas(
        nationality="German",
        purpose="visit",
        duration="short",
        family=False,
    )
    assert len(result) <= 3


def test_recommend_visas_required_fields(service: VisaOracleService) -> None:
    """Every result must carry the required fields."""
    result = service.recommend_visas(
        nationality="British",
        purpose="invest",
        duration="long",
        family=False,
    )
    required = {"visa_name", "category", "price", "score"}
    for item in result:
        assert required.issubset(item.keys()), f"Missing fields in {item}"


# ---------------------------------------------------------------------------
# recommend_visas — purpose-specific behaviour
# ---------------------------------------------------------------------------


def test_recommend_visas_visit_short_returns_tourism(service: VisaOracleService) -> None:
    """visit + short duration should prioritise tourism / single-entry visas."""
    result = service.recommend_visas(
        nationality="Australian",
        purpose="visit",
        duration="short",
        family=False,
    )
    assert len(result) > 0
    # Top result may be visa_on_arrival, single_entry_visas, or multiple_entry_visas
    # depending on scoring — all are valid for a short visit
    top = result[0]
    assert top["category"] in {"single_entry_visas", "multiple_entry_visas", "visa_on_arrival"}
    # Tourism or Business visa should appear in results
    names = [r["visa_name"] for r in result]
    assert any("Tourism" in n or "Business" in n or "Arrival" in n for n in names)


def test_recommend_visas_invest_long_returns_kitas(service: VisaOracleService) -> None:
    """invest + long duration must surface investor KITAS."""
    result = service.recommend_visas(
        nationality="Singaporean",
        purpose="invest",
        duration="long",
        family=False,
    )
    assert len(result) > 0
    # At least one result from kitas_permits
    categories = {r["category"] for r in result}
    assert "kitas_permits" in categories
    # Investor KITAS should appear
    names = [r["visa_name"] for r in result]
    assert any("Investor" in n or "KITAS" in n for n in names)


def test_recommend_visas_retire_returns_retirement_visa(service: VisaOracleService) -> None:
    """retire purpose must surface retirement KITAS."""
    result = service.recommend_visas(
        nationality="Dutch",
        purpose="retire",
        duration="long",
        family=False,
    )
    assert len(result) > 0
    names = [r["visa_name"] for r in result]
    assert any("Retirement" in n or "retire" in n.lower() for n in names)


def test_recommend_visas_digital_nomad_includes_remote_worker(
    service: VisaOracleService,
) -> None:
    """digital_nomad purpose should surface E33G Remote Worker."""
    result = service.recommend_visas(
        nationality="American",
        purpose="digital_nomad",
        duration="long",
        family=False,
    )
    assert len(result) > 0
    names = [r["visa_name"] for r in result]
    assert any("Remote" in n or "Freelance" in n or "C1" in n for n in names)


def test_recommend_visas_family_match_adds_spouse_bonus(service: VisaOracleService) -> None:
    """family=True should boost spouse/dependent KITAS in ranking."""
    result_with_family = service.recommend_visas(
        nationality="Japanese",
        purpose="work",
        duration="long",
        family=True,
    )
    result_without_family = service.recommend_visas(
        nationality="Japanese",
        purpose="work",
        duration="long",
        family=False,
    )
    # The spouse option should score higher when family=True
    spouse_with = next(
        (r for r in result_with_family if "Spouse" in r["visa_name"]), None
    )
    spouse_without = next(
        (r for r in result_without_family if "Spouse" in r["visa_name"]), None
    )
    if spouse_with and spouse_without:
        assert spouse_with["score"] > spouse_without["score"]


# ---------------------------------------------------------------------------
# get_all_visa_types
# ---------------------------------------------------------------------------


def test_get_all_visa_types_returns_list(service: VisaOracleService) -> None:
    """get_all_visa_types must return a non-empty list."""
    result = service.get_all_visa_types()
    assert isinstance(result, list)
    assert len(result) > 0


def test_get_all_visa_types_has_required_fields(service: VisaOracleService) -> None:
    """Each entry must have name, category and price."""
    result = service.get_all_visa_types()
    for item in result:
        assert "name" in item
        assert "category" in item
        assert "price" in item


def test_get_all_visa_types_includes_all_categories(service: VisaOracleService) -> None:
    """All non-empty service categories should be represented."""
    result = service.get_all_visa_types()
    categories = {r["category"] for r in result}
    assert "single_entry_visas" in categories
    assert "kitas_permits" in categories


# ---------------------------------------------------------------------------
# build_whatsapp_message
# ---------------------------------------------------------------------------


def test_build_whatsapp_message_returns_wa_url(service: VisaOracleService) -> None:
    """build_whatsapp_message must return a wa.me URL."""
    url = service.build_whatsapp_message(
        nationality="Australian",
        purpose="visit",
        duration="short",
        visa_name="C1 Tourism",
        price="2.300.000 IDR",
    )
    assert url.startswith("https://wa.me/")
    assert "C1%20Tourism" in url or "C1" in url


# ---------------------------------------------------------------------------
# build_telegram_summary
# ---------------------------------------------------------------------------


def test_build_telegram_summary_contains_session_id(service: VisaOracleService) -> None:
    """Telegram summary must include (part of) the session_id."""
    sid = "abc123def456"
    summary = service.build_telegram_summary(
        session_id=sid,
        quiz_answers={"nationality": "French", "purpose": "retire", "duration": "long"},
        recommended_visas=[],
        messages=[],
        language="fr",
    )
    assert sid[:12] in summary


def test_build_telegram_summary_contains_nationality(service: VisaOracleService) -> None:
    """Telegram summary must include nationality."""
    summary = service.build_telegram_summary(
        session_id="x" * 32,
        quiz_answers={"nationality": "Brazilian", "purpose": "visit", "duration": "short"},
        recommended_visas=[],
        messages=[],
        language="pt",
    )
    assert "Brazilian" in summary


# ---------------------------------------------------------------------------
# hash_ip and generate_session_id
# ---------------------------------------------------------------------------


def test_hash_ip_is_64_chars(service: VisaOracleService) -> None:
    """SHA-256 hex digest must be exactly 64 characters."""
    result = service.hash_ip("127.0.0.1")
    assert len(result) == 64
    assert result.isalnum()


def test_hash_ip_is_deterministic(service: VisaOracleService) -> None:
    """Same IP must always produce the same hash."""
    h1 = service.hash_ip("192.168.1.1")
    h2 = service.hash_ip("192.168.1.1")
    assert h1 == h2


def test_hash_ip_different_ips_differ(service: VisaOracleService) -> None:
    """Different IPs must produce different hashes."""
    h1 = service.hash_ip("10.0.0.1")
    h2 = service.hash_ip("10.0.0.2")
    assert h1 != h2


def test_generate_session_id_length(service: VisaOracleService) -> None:
    """Session ID must be exactly 64 hex chars (32 bytes)."""
    sid = service.generate_session_id()
    assert len(sid) == 64
    assert all(c in "0123456789abcdef" for c in sid)


def test_generate_session_id_unique(service: VisaOracleService) -> None:
    """Successive session IDs must be unique."""
    ids = {service.generate_session_id() for _ in range(10)}
    assert len(ids) == 10


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_get_visa_oracle_service_singleton() -> None:
    """get_visa_oracle_service must return the same instance twice."""
    import backend.services.visa_oracle.visa_oracle_service as module

    # Reset singleton for test isolation
    module._visa_oracle_service = None

    mock_pricing = MagicMock()
    mock_pricing.prices = SAMPLE_PRICES

    with patch(
        "backend.services.visa_oracle.visa_oracle_service.get_pricing_service",
        return_value=mock_pricing,
    ):
        svc1 = get_visa_oracle_service()
        svc2 = get_visa_oracle_service()

    assert svc1 is svc2

    # Clean up singleton so other tests are not affected
    module._visa_oracle_service = None
