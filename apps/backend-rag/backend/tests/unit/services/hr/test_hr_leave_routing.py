"""Tests for HR leave routing logic (pure functions, no I/O)."""

import pytest

from backend.app.services.hr.hr_leave_routing import (
    ASYA_EMAIL,
    ZERO_EMAIL,
    build_notification_recipients,
    build_review_recipients,
    resolve_approver,
)


class TestResolveApprover:
    @pytest.mark.parametrize("requester,expected", [
        ("kadek.tax@balizero.com",    "tax@balizero.com"),
        ("angel.tax@balizero.com",    "tax@balizero.com"),
        ("dewa.ayu.tax@balizero.com", "tax@balizero.com"),
        ("faysha.tax@balizero.com",   "tax@balizero.com"),
        ("dea@balizero.com",          "ruslana@balizero.com"),
        ("rina@balizero.com",         "ruslana@balizero.com"),
        ("tax@balizero.com",          ZERO_EMAIL),   # Veronika → Zero
        ("asya@balizero.com",         ZERO_EMAIL),
        ("ruslana@balizero.com",      ZERO_EMAIL),
        ("zero@balizero.com",         ZERO_EMAIL),
        ("random@balizero.com",       ZERO_EMAIL),   # unknown → Zero
    ])
    def test_routing_rules(self, requester: str, expected: str) -> None:
        assert resolve_approver(requester) == expected

    def test_case_insensitive(self) -> None:
        assert resolve_approver("KADEK.TAX@BALIZERO.COM") == "tax@balizero.com"

    def test_whitespace_stripped(self) -> None:
        assert resolve_approver("  kadek.tax@balizero.com  ") == "tax@balizero.com"


class TestBuildNotificationRecipients:
    def test_tax_team_kadek(self) -> None:
        result = build_notification_recipients("kadek.tax@balizero.com")
        assert result == {"to": "tax@balizero.com", "cc": [ZERO_EMAIL, ASYA_EMAIL]}

    def test_dea_routes_to_ruslana(self) -> None:
        result = build_notification_recipients("dea@balizero.com")
        assert result == {"to": "ruslana@balizero.com", "cc": [ZERO_EMAIL, ASYA_EMAIL]}

    def test_zero_is_own_approver_no_duplicate_cc(self) -> None:
        result = build_notification_recipients("zero@balizero.com")
        assert result == {"to": ZERO_EMAIL, "cc": [ASYA_EMAIL]}

    def test_asya_as_requester_not_in_cc(self) -> None:
        result = build_notification_recipients("asya@balizero.com")
        assert result == {"to": ZERO_EMAIL, "cc": []}

    def test_veronika_as_requester(self) -> None:
        result = build_notification_recipients("tax@balizero.com")
        assert result == {"to": ZERO_EMAIL, "cc": [ASYA_EMAIL]}

    def test_ruslana_as_requester(self) -> None:
        result = build_notification_recipients("ruslana@balizero.com")
        assert result == {"to": ZERO_EMAIL, "cc": [ASYA_EMAIL]}

    def test_unknown_user_fallback(self) -> None:
        result = build_notification_recipients("newhire@balizero.com")
        assert result == {"to": ZERO_EMAIL, "cc": [ASYA_EMAIL]}


class TestBuildReviewRecipients:
    """Recipients for the email sent to the requester after approve/reject.

    TO is always the requester. Asya and Zero are CC'd unless they are
    either the reviewer or the requester themselves (no self-CC).
    """

    def test_kadek_request_reviewed_by_veronika(self) -> None:
        result = build_review_recipients(
            requester_email="kadek.tax@balizero.com",
            reviewer_email="tax@balizero.com",
        )
        assert result == {
            "to": "kadek.tax@balizero.com",
            "cc": [ZERO_EMAIL, ASYA_EMAIL],
        }

    def test_dea_request_reviewed_by_ruslana(self) -> None:
        result = build_review_recipients(
            requester_email="dea@balizero.com",
            reviewer_email="ruslana@balizero.com",
        )
        assert result == {
            "to": "dea@balizero.com",
            "cc": [ZERO_EMAIL, ASYA_EMAIL],
        }

    def test_kadek_request_reviewed_by_zero_excludes_zero_from_cc(self) -> None:
        result = build_review_recipients(
            requester_email="kadek.tax@balizero.com",
            reviewer_email="zero@balizero.com",
        )
        assert result == {"to": "kadek.tax@balizero.com", "cc": [ASYA_EMAIL]}

    def test_kadek_request_reviewed_by_asya_excludes_asya_from_cc(self) -> None:
        result = build_review_recipients(
            requester_email="kadek.tax@balizero.com",
            reviewer_email="asya@balizero.com",
        )
        assert result == {"to": "kadek.tax@balizero.com", "cc": [ZERO_EMAIL]}

    def test_asya_request_reviewed_by_zero_no_self_cc(self) -> None:
        # Asya requested → Asya is the TO. Zero is the reviewer → Zero
        # not in CC. Asya not in CC because she is the requester. Empty cc.
        result = build_review_recipients(
            requester_email="asya@balizero.com",
            reviewer_email="zero@balizero.com",
        )
        assert result == {"to": "asya@balizero.com", "cc": []}

    def test_zero_request_reviewed_by_asya_no_self_cc(self) -> None:
        # Mirror of the above: Zero is requester → no Zero in CC. Asya is
        # reviewer → no Asya in CC. Empty cc.
        result = build_review_recipients(
            requester_email="zero@balizero.com",
            reviewer_email="asya@balizero.com",
        )
        assert result == {"to": "zero@balizero.com", "cc": []}

    def test_case_insensitive(self) -> None:
        result = build_review_recipients(
            requester_email="  KADEK.TAX@BALIZERO.COM  ",
            reviewer_email="  TAX@BALIZERO.COM  ",
        )
        assert result == {
            "to": "kadek.tax@balizero.com",
            "cc": [ZERO_EMAIL, ASYA_EMAIL],
        }
