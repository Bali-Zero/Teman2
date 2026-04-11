"""Tests for backend.services.compliance.visa_expiry_team_notifier"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.compliance.visa_expiry_team_notifier import (
    ADMIN_EMAIL,
    ALERT_THRESHOLDS,
    VisaExpiryTeamNotifier,
    _build_client_row,
    _fmt_date,
    _LABEL_COLOURS,
    _ROW_COLOURS,
)


# ---------------------------------------------------------------------------
# _fmt_date
# ---------------------------------------------------------------------------

class TestFmtDate:
    def test_none(self) -> None:
        assert _fmt_date(None) == "\u2014"

    def test_date_object(self) -> None:
        assert _fmt_date(date(2026, 4, 15)) == "15/04/2026"

    def test_datetime_object(self) -> None:
        assert _fmt_date(datetime(2026, 12, 1)) == "01/12/2026"

    def test_string_fallback(self) -> None:
        assert _fmt_date("2026-01-01") == "2026-01-01"

    def test_non_date_type(self) -> None:
        assert _fmt_date(12345) == "12345"


# ---------------------------------------------------------------------------
# _build_client_row
# ---------------------------------------------------------------------------

class TestBuildClientRow:
    def _base_client(self, days: int = 15) -> dict[str, Any]:
        return {
            "client_name": "John Doe",
            "client_phone": "+6281234567890",
            "document_type": "visa",
            "expiry_date": date(2026, 5, 1),
            "days_until_expiry": days,
            "current_visa_type": None,
            "current_visa_sponsor": None,
            "passport_expiry": None,
        }

    def test_7_day_urgency_color(self) -> None:
        client = self._base_client(days=5)
        html = _build_client_row(client)
        assert _ROW_COLOURS[7] in html
        assert _LABEL_COLOURS[7] in html
        assert "5 giorni" in html

    def test_30_day_urgency_color(self) -> None:
        client = self._base_client(days=20)
        html = _build_client_row(client)
        assert _ROW_COLOURS[30] in html

    def test_60_day_urgency_color(self) -> None:
        client = self._base_client(days=45)
        html = _build_client_row(client)
        assert _ROW_COLOURS[60] in html

    def test_visa_type_shown_for_visa(self) -> None:
        client = self._base_client()
        client["current_visa_type"] = "B211"
        html = _build_client_row(client)
        assert "VISA (B211)" in html

    def test_visa_type_shown_for_kitas(self) -> None:
        client = self._base_client()
        client["document_type"] = "kitas"
        client["current_visa_type"] = "Work Permit"
        html = _build_client_row(client)
        assert "KITAS (Work Permit)" in html

    def test_visa_type_not_shown_for_passport(self) -> None:
        client = self._base_client()
        client["document_type"] = "passport"
        client["current_visa_type"] = "Something"
        html = _build_client_row(client)
        assert "PASSPORT" in html
        assert "(Something)" not in html

    def test_sponsor_shown(self) -> None:
        client = self._base_client()
        client["current_visa_sponsor"] = "PT Bali Zero"
        html = _build_client_row(client)
        assert "Sponsor: PT Bali Zero" in html

    def test_no_sponsor_no_html(self) -> None:
        client = self._base_client()
        client["current_visa_sponsor"] = ""
        html = _build_client_row(client)
        assert "Sponsor:" not in html

    def test_passport_warning_shown(self) -> None:
        client = self._base_client(days=30)
        client["expiry_date"] = date(2027, 6, 1)
        client["passport_expiry"] = date(2027, 3, 1)  # Passport expires BEFORE visa
        html = _build_client_row(client)
        assert "Passaporto scade PRIMA" in html
        assert "01/03/2027" in html

    def test_no_passport_warning_when_after(self) -> None:
        client = self._base_client(days=30)
        client["expiry_date"] = date(2027, 3, 1)
        client["passport_expiry"] = date(2027, 6, 1)  # Passport expires AFTER visa
        html = _build_client_row(client)
        assert "Passaporto scade PRIMA" not in html

    def test_missing_name_shows_dash(self) -> None:
        client = self._base_client()
        client["client_name"] = None
        html = _build_client_row(client)
        assert "\u2014" in html  # em dash fallback

    def test_missing_phone_shows_dash(self) -> None:
        client = self._base_client()
        client["client_phone"] = None
        html = _build_client_row(client)
        assert "\u2014" in html

    def test_days_zero(self) -> None:
        client = self._base_client(days=0)
        html = _build_client_row(client)
        assert _ROW_COLOURS[7] in html
        assert "0 giorni" in html


# ---------------------------------------------------------------------------
# VisaExpiryTeamNotifier — mock DB pool
# ---------------------------------------------------------------------------

def _make_pool(
    rows: list[dict[str, Any]] | None = None,
    raise_on_fetch: Exception | None = None,
) -> MagicMock:
    conn = AsyncMock()
    if raise_on_fetch:
        conn.fetch = AsyncMock(side_effect=raise_on_fetch)
    else:
        conn.fetch = AsyncMock(return_value=rows or [])

    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


# ---------------------------------------------------------------------------
# _get_expiring_documents
# ---------------------------------------------------------------------------

class TestGetExpiringDocuments:
    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        pool = _make_pool(rows=[])
        notifier = VisaExpiryTeamNotifier(pool)
        results = await notifier._get_expiring_documents()
        assert results == []

    @pytest.mark.asyncio
    async def test_results_sorted_by_days(self) -> None:
        rows = [
            {"client_id": 1, "days_until_expiry": 30, "assigned_to": "a@b.com"},
            {"client_id": 2, "days_until_expiry": 7, "assigned_to": "a@b.com"},
            {"client_id": 3, "days_until_expiry": 60, "assigned_to": "a@b.com"},
        ]
        pool = _make_pool(rows=rows)
        notifier = VisaExpiryTeamNotifier(pool)
        results = await notifier._get_expiring_documents()
        days_list = [r["days_until_expiry"] for r in results]
        assert days_list == sorted(days_list)


# ---------------------------------------------------------------------------
# check_and_notify
# ---------------------------------------------------------------------------

class TestCheckAndNotify:
    @pytest.mark.asyncio
    async def test_no_expiring_returns_zero(self) -> None:
        pool = _make_pool(rows=[])
        notifier = VisaExpiryTeamNotifier(pool)
        result = await notifier.check_and_notify()
        assert result["total_alerts"] == 0

    @pytest.mark.asyncio
    @patch("backend.services.compliance.visa_expiry_team_notifier.httpx.AsyncClient")
    async def test_sends_alerts_and_summary(self, mock_client_cls: MagicMock) -> None:
        rows = [
            {
                "client_id": 1,
                "client_name": "Alice",
                "client_email": "alice@test.com",
                "client_phone": "+62123",
                "nationality": "US",
                "assigned_to": "leader@balizero.com",
                "document_type": "visa",
                "expiry_date": date(2026, 5, 1),
                "days_until_expiry": 21,
                "current_visa_type": "B211",
                "current_visa_sponsor": "PT BZ",
                "passport_expiry": date(2027, 1, 1),
            },
        ]

        pool = _make_pool(rows=rows)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_http

        notifier = VisaExpiryTeamNotifier(pool)
        result = await notifier.check_and_notify()

        # 3 document types queried (visa, kitas, passport) × same row = 3 alerts
        assert result["total_alerts"] == 3
        # post called at least twice: once for leader, once for admin summary
        assert mock_http.post.await_count >= 2


# ---------------------------------------------------------------------------
# _send_team_leader_alert
# ---------------------------------------------------------------------------

class TestSendTeamLeaderAlert:
    @pytest.mark.asyncio
    async def test_builds_and_sends_email(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        pool = _make_pool()
        notifier = VisaExpiryTeamNotifier(pool)
        notifier._client = mock_client

        clients = [
            {
                "client_name": "Bob",
                "client_phone": "+62999",
                "document_type": "kitas",
                "expiry_date": date(2026, 5, 15),
                "days_until_expiry": 35,
                "current_visa_type": None,
                "current_visa_sponsor": None,
                "passport_expiry": None,
            },
        ]
        await notifier._send_team_leader_alert("leader@bz.com", clients)
        mock_client.post.assert_awaited_once()
        payload = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args[1].get("json")
        assert "leader@bz.com" in payload["to"]
        assert "SCADENZE" in payload["subject"]


# ---------------------------------------------------------------------------
# _send_zero_summary
# ---------------------------------------------------------------------------

class TestSendZeroSummary:
    @pytest.mark.asyncio
    async def test_groups_by_leader(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        pool = _make_pool()
        notifier = VisaExpiryTeamNotifier(pool)
        notifier._client = mock_client

        clients = [
            {
                "client_name": "C1",
                "client_phone": "+62",
                "document_type": "visa",
                "expiry_date": date(2026, 5, 1),
                "days_until_expiry": 10,
                "assigned_to": "leader_a@bz.com",
                "current_visa_type": None,
                "current_visa_sponsor": None,
                "passport_expiry": None,
            },
            {
                "client_name": "C2",
                "client_phone": "+62",
                "document_type": "passport",
                "expiry_date": date(2026, 6, 1),
                "days_until_expiry": 40,
                "assigned_to": "leader_b@bz.com",
                "current_visa_type": None,
                "current_visa_sponsor": None,
                "passport_expiry": None,
            },
        ]
        await notifier._send_zero_summary(clients)
        mock_client.post.assert_awaited_once()
        payload = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args[1].get("json")
        assert ADMIN_EMAIL in payload["to"]
        # Body should contain both leaders
        assert "leader_a@bz.com" in payload["body"]
        assert "leader_b@bz.com" in payload["body"]

    @pytest.mark.asyncio
    async def test_singular_document(self) -> None:
        """Subject uses 'documento' (singular) when n==1."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        pool = _make_pool()
        notifier = VisaExpiryTeamNotifier(pool)
        notifier._client = mock_client

        clients = [
            {
                "client_name": "C1",
                "client_phone": "+62",
                "document_type": "visa",
                "expiry_date": date(2026, 5, 1),
                "days_until_expiry": 10,
                "assigned_to": "leader@bz.com",
                "current_visa_type": None,
                "current_visa_sponsor": None,
                "passport_expiry": None,
            },
        ]
        await notifier._send_zero_summary(clients)
        payload = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args[1].get("json")
        assert "documento" in payload["subject"]


# ---------------------------------------------------------------------------
# _post_email
# ---------------------------------------------------------------------------

class TestPostEmail:
    @pytest.mark.asyncio
    async def test_raises_without_client(self) -> None:
        pool = _make_pool()
        notifier = VisaExpiryTeamNotifier(pool)
        notifier._client = None
        with pytest.raises(RuntimeError, match="outside of an active HTTP client context"):
            await notifier._post_email(to="a@b.com", subject="s", html_body="<p>x</p>")

    @pytest.mark.asyncio
    async def test_sends_correct_payload(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        pool = _make_pool()
        notifier = VisaExpiryTeamNotifier(pool)
        notifier._client = mock_client

        await notifier._post_email(to="user@bz.com", subject="Test", html_body="<p>body</p>")
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["to"] == "user@bz.com"
        assert payload["subject"] == "Test"
        assert payload["body"] == "<p>body</p>"


# ---------------------------------------------------------------------------
# _get_http_client (static)
# ---------------------------------------------------------------------------

class TestGetHttpClient:
    def test_returns_client(self) -> None:
        import httpx
        client = VisaExpiryTeamNotifier._get_http_client()
        assert isinstance(client, httpx.AsyncClient)


# ---------------------------------------------------------------------------
# ALERT_THRESHOLDS config
# ---------------------------------------------------------------------------

class TestConfig:
    def test_thresholds_tuple(self) -> None:
        assert ALERT_THRESHOLDS == (7, 30, 60)

    def test_row_colours_keys(self) -> None:
        assert set(_ROW_COLOURS.keys()) == {7, 30, 60}

    def test_label_colours_keys(self) -> None:
        assert set(_LABEL_COLOURS.keys()) == {7, 30, 60}
