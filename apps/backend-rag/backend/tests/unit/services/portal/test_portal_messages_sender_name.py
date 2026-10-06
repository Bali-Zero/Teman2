"""Portal chat shows the staff member's name, never their email address.

Antonello, 30 Sep 2026 (F2): team messages store the staff email in
``portal_messages.sent_by`` (``crm_portal_integration.py`` writes
``current_user["email"]``), and the client portal chat rendered that value
as the sender line, so clients saw internal staff addresses. Not intended.
Decision: show the staff name (``team_members``), fall back to "Bali Zero";
the stored ``sent_by`` stays as it is.

Client-to-team messages keep their own ``sent_by`` (the portal does not
render a sender line for them).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.portal._rbac import ClientContext

_NOW = datetime(2026, 10, 6, 3, 0, tzinfo=timezone.utc)


def _row(direction: str, sent_by: str, sender_name: str | None) -> dict:
    return {
        "id": 1,
        "subject": None,
        "content": "x",
        "direction": direction,
        "sent_by": sent_by,
        "sender_name": sender_name,
        "read_at": None,
        "created_at": _NOW,
        "practice_id": None,
        "practice_name": None,
    }


def _service(rows: list[dict]) -> tuple[object, AsyncMock]:
    from backend.services.portal.portal_service import PortalService

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": 1})
    conn.fetch = AsyncMock(return_value=rows)
    conn.fetchval = AsyncMock(side_effect=[len(rows), 0])
    pool = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=cm)
    return PortalService(pool), conn


_CTX = ClientContext(client_id=1, email="client@example.com")


async def _messages(rows: list[dict]) -> tuple[list[dict], AsyncMock]:
    svc, conn = _service(rows)
    out = await svc.get_messages(client_id=1, current_user=_CTX)
    return out["messages"], conn


@pytest.mark.asyncio
async def test_guilt_team_message_shows_staff_name_not_email() -> None:
    msgs, _ = await _messages([_row("team_to_client", "staff.one@balizero.com", "Staff One")])
    assert msgs[0]["sent_by"] == "Staff One"
    assert "@" not in msgs[0]["sent_by"]


@pytest.mark.asyncio
async def test_guilt_unknown_team_sender_falls_back_to_bali_zero() -> None:
    msgs, _ = await _messages([_row("team_to_client", "gone@balizero.com", None)])
    assert msgs[0]["sent_by"] == "Bali Zero"


@pytest.mark.asyncio
async def test_guilt_blank_staff_name_falls_back_to_bali_zero() -> None:
    msgs, _ = await _messages([_row("team_to_client", "x@balizero.com", "   ")])
    assert msgs[0]["sent_by"] == "Bali Zero"


@pytest.mark.asyncio
async def test_innocence_client_message_keeps_its_sender() -> None:
    msgs, _ = await _messages([_row("client_to_team", "client@example.com", None)])
    assert msgs[0]["sent_by"] == "client@example.com"
    assert msgs[0]["from_team"] is False


@pytest.mark.asyncio
async def test_reader_sql_looks_up_team_members_once_per_message() -> None:
    _, conn = await _messages([])
    sql = conn.fetch.await_args.args[0]
    assert "team_members" in sql
    # LATERAL ... LIMIT 1: duplicate team_members rows for one email must
    # never duplicate a message in the thread.
    assert "LATERAL" in sql
    assert "LIMIT 1" in sql
