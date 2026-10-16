"""Guard: portal status messages name the service, not the internal code.

A client saw "Status update: visa_d12_business_1yr" in my.balizero.com
(screenshot client_id 12536, 25 Sep 2026). The practice-update router passed
practice_type_code first and the human name only as a fallback.
"""

from pathlib import Path

from backend.services.portal.portal_notification_service import (
    practice_display_name,
)

ROUTER = Path(__file__).resolve().parents[4] / "app" / "routers" / "crm_practices.py"


def test_name_wins_over_code() -> None:
    practice = {
        "practice_type_name": "D12 Business Visa (1 year)",
        "practice_type_code": "visa_d12_business_1yr",
    }
    assert practice_display_name(practice) == "D12 Business Visa (1 year)"


def test_code_fallback_never_shows_underscores() -> None:
    practice = {"practice_type_name": None, "practice_type_code": "visa_d12_business_1yr"}
    assert practice_display_name(practice) == "visa d12 business 1yr"


def test_blank_name_falls_back_to_code() -> None:
    practice = {"practice_type_name": "   ", "practice_type_code": "kitas_investor"}
    assert practice_display_name(practice) == "kitas investor"


def test_nothing_known_says_practice() -> None:
    assert practice_display_name({}) == "Practice"


def test_router_uses_the_display_name_helper() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    # positive control: the status-change notification is still wired here
    assert "notify_practice_status_changed(" in source
    assert "practice_display_name(response_practice)" in source
    # GUILT case: the code-first lookup that leaked the slug must be gone
    assert 'response_practice.get("practice_type_code")\n' not in source
