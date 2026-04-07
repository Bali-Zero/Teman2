"""Tests for HR leave notifiers — pure formatters delegating to send_internal_email."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.services.hr.hr_leave_notifier import (
    notify_leave_request_pending,
    notify_leave_request_reviewed,
)


@pytest.fixture
def sample_pending_args() -> dict:
    return {
        "request_id": 42,
        "requester_email": "kadek.tax@balizero.com",
        "requester_name": "Kadek",
        "leave_type_name": "Annual Leave",
        "start_date": date(2026, 12, 15),
        "end_date": date(2026, 12, 19),
        "total_days": 5,
        "reason": "Family visit",
    }


@pytest.fixture
def sample_review_args() -> dict:
    return {
        "request_id": 99,
        "requester_email": "kadek.tax@balizero.com",
        "requester_name": "Kadek",
        "reviewer_email": "tax@balizero.com",
        "reviewer_name": "Veronika",
        "leave_type_name": "Annual Leave",
        "start_date": date(2026, 12, 15),
        "end_date": date(2026, 12, 19),
        "total_days": 5,
        "action": "approved",
        "rejection_reason": None,
    }


# ─── notify_leave_request_pending ──────────────────────────────────────────


class TestNotifyLeaveRequestPending:
    @pytest.mark.asyncio
    async def test_happy_path_calls_internal_email_with_correct_recipients(
        self, sample_pending_args: dict,
    ) -> None:
        with patch(
            "backend.app.services.hr.hr_leave_notifier.send_internal_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await notify_leave_request_pending(**sample_pending_args)

        assert mock_send.call_count == 1
        kwargs = mock_send.call_args.kwargs
        assert kwargs["to"] == "tax@balizero.com"
        assert kwargs["cc"] == ["zero@balizero.com", "asya@balizero.com"]
        assert "Kadek" in kwargs["subject"]
        assert "5 days" in kwargs["subject"]
        assert "Annual Leave" in kwargs["body"]
        assert "2026-12-15 → 2026-12-19" in kwargs["body"]
        assert "Family visit" in kwargs["body"]
        assert kwargs["log_context"] == "hr_leave pending req=42"

    @pytest.mark.asyncio
    async def test_single_day_range_uses_singular_day(
        self, sample_pending_args: dict,
    ) -> None:
        sample_pending_args["total_days"] = 1
        sample_pending_args["start_date"] = date(2026, 12, 15)
        sample_pending_args["end_date"] = date(2026, 12, 15)

        with patch(
            "backend.app.services.hr.hr_leave_notifier.send_internal_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await notify_leave_request_pending(**sample_pending_args)

        kwargs = mock_send.call_args.kwargs
        assert "1 day" in kwargs["subject"]
        assert "1 days" not in kwargs["subject"]
        assert "2026-12-15" in kwargs["body"]
        assert "→" not in kwargs["body"]

    @pytest.mark.asyncio
    async def test_reason_none_omits_reason_block(
        self, sample_pending_args: dict,
    ) -> None:
        sample_pending_args["reason"] = None

        with patch(
            "backend.app.services.hr.hr_leave_notifier.send_internal_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await notify_leave_request_pending(**sample_pending_args)

        kwargs = mock_send.call_args.kwargs
        assert "Reason:" not in kwargs["body"]

    @pytest.mark.asyncio
    async def test_html_injection_in_reason_is_escaped(
        self, sample_pending_args: dict,
    ) -> None:
        """Regression: free-text reason must not break HTML structure."""
        sample_pending_args["reason"] = "</p><script>alert(1)</script>"

        with patch(
            "backend.app.services.hr.hr_leave_notifier.send_internal_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await notify_leave_request_pending(**sample_pending_args)

        body = mock_send.call_args.kwargs["body"]
        assert "<script>" not in body
        assert "&lt;script&gt;" in body

    @pytest.mark.asyncio
    async def test_asya_as_requester_omits_asya_from_cc(
        self, sample_pending_args: dict,
    ) -> None:
        sample_pending_args["requester_email"] = "asya@balizero.com"
        sample_pending_args["requester_name"] = "Asya"

        with patch(
            "backend.app.services.hr.hr_leave_notifier.send_internal_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await notify_leave_request_pending(**sample_pending_args)

        kwargs = mock_send.call_args.kwargs
        # Asya is the requester → cc list is empty → cc=None passed to client
        assert kwargs["cc"] is None


# ─── notify_leave_request_reviewed ─────────────────────────────────────────


class TestNotifyLeaveRequestReviewed:
    @pytest.mark.asyncio
    async def test_approved_happy_path(
        self, sample_review_args: dict,
    ) -> None:
        with patch(
            "backend.app.services.hr.hr_leave_notifier.send_internal_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await notify_leave_request_reviewed(**sample_review_args)

        assert mock_send.call_count == 1
        kwargs = mock_send.call_args.kwargs
        # TO is the requester, not the reviewer
        assert kwargs["to"] == "kadek.tax@balizero.com"
        # Veronika reviewed → both Zero and Asya in CC
        assert kwargs["cc"] == ["zero@balizero.com", "asya@balizero.com"]
        assert "Approved" in kwargs["subject"]
        assert "5 days" in kwargs["subject"]
        assert "approved" in kwargs["body"]
        assert "Veronika" in kwargs["body"]
        assert "Annual Leave" in kwargs["body"]
        assert "2026-12-15 → 2026-12-19" in kwargs["body"]
        # No rejection reason on approval
        assert "Reason for rejection" not in kwargs["body"]
        assert "approved" in kwargs["log_context"]

    @pytest.mark.asyncio
    async def test_rejected_with_reason(
        self, sample_review_args: dict,
    ) -> None:
        sample_review_args["action"] = "rejected"
        sample_review_args["rejection_reason"] = "Insufficient balance"

        with patch(
            "backend.app.services.hr.hr_leave_notifier.send_internal_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await notify_leave_request_reviewed(**sample_review_args)

        kwargs = mock_send.call_args.kwargs
        assert "Rejected" in kwargs["subject"]
        assert "rejected" in kwargs["body"]
        assert "Reason for rejection:" in kwargs["body"]
        assert "Insufficient balance" in kwargs["body"]

    @pytest.mark.asyncio
    async def test_rejected_without_reason_omits_block(
        self, sample_review_args: dict,
    ) -> None:
        sample_review_args["action"] = "rejected"
        sample_review_args["rejection_reason"] = None

        with patch(
            "backend.app.services.hr.hr_leave_notifier.send_internal_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await notify_leave_request_reviewed(**sample_review_args)

        body = mock_send.call_args.kwargs["body"]
        assert "Reason for rejection" not in body

    @pytest.mark.asyncio
    async def test_zero_reviewer_excluded_from_cc(
        self, sample_review_args: dict,
    ) -> None:
        sample_review_args["reviewer_email"] = "zero@balizero.com"
        sample_review_args["reviewer_name"] = "Zero"

        with patch(
            "backend.app.services.hr.hr_leave_notifier.send_internal_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await notify_leave_request_reviewed(**sample_review_args)

        kwargs = mock_send.call_args.kwargs
        # Zero is reviewer → no Zero in CC, only Asya
        assert kwargs["cc"] == ["asya@balizero.com"]

    @pytest.mark.asyncio
    async def test_html_injection_in_rejection_reason_is_escaped(
        self, sample_review_args: dict,
    ) -> None:
        sample_review_args["action"] = "rejected"
        sample_review_args["rejection_reason"] = "</p><script>alert(1)</script>"

        with patch(
            "backend.app.services.hr.hr_leave_notifier.send_internal_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await notify_leave_request_reviewed(**sample_review_args)

        body = mock_send.call_args.kwargs["body"]
        assert "<script>" not in body
        assert "&lt;script&gt;" in body

    @pytest.mark.asyncio
    async def test_asya_as_requester_zero_as_reviewer_no_cc(
        self, sample_review_args: dict,
    ) -> None:
        sample_review_args["requester_email"] = "asya@balizero.com"
        sample_review_args["requester_name"] = "Asya"
        sample_review_args["reviewer_email"] = "zero@balizero.com"
        sample_review_args["reviewer_name"] = "Zero"

        with patch(
            "backend.app.services.hr.hr_leave_notifier.send_internal_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await notify_leave_request_reviewed(**sample_review_args)

        kwargs = mock_send.call_args.kwargs
        # Both Zero and Asya excluded → empty cc list → cc=None
        assert kwargs["cc"] is None
