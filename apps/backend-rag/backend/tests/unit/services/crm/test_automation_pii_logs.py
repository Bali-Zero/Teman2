"""PII log hygiene for automation.py's module-level
`_send_with_brevo_fallback` — R2 (PR #7451 gate follow-up), sibling of
test_completed_process_service_pii_logs.py / test_waiting_documents_service_pii_logs.py.

Unlike those two class-method copies, this module's `_send_with_brevo_fallback`
kept logging the raw recipient (`to_email`) and the unscrubbed provider error
(`brevo_err_msg`) at the two log lines this PR rewrote — the AST scan in the
fresh gate's REWORK-BUILD verdict found `automation.py` was the one site of
the three that had not been redacted. Fixed by reusing the same
`redact_identifier_for_log` / `_bounded_scrub` helpers the siblings already
use — no new regex.

C-2(b) of #7451's delta gate (PR #7488 follow-up) adds a second class of
sites in the same module: `ProcessAutomationService.trigger_on_process_start`
has its OWN caller-level success/except log lines around each
`_send_with_brevo_fallback` call (one pair for the client email, one pair
for the team-leader email) — these are separate log statements from the
ones inside `_send_with_brevo_fallback` itself, and were still logging the
raw `client_data["email"]` / `team_leader_email` on success and the raw
exception object (`%s`, e) on failure. The exception case matters even with
`exc_info=True`: a caught `ValueError`/`httpx.HTTPError`'s own message can
echo the recipient back (e.g. a provider bounce quoting the address), and
`exc_info=True` only attaches the traceback — it does not re-scrub the `%s`
argument. Fixed with the same two helpers, applied to `str(e)`.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.security.pii_log_identifier import redact_identifier_for_log
from backend.services.crm.automation import ProcessAutomationService, _send_with_brevo_fallback

_LOGGER_NAME = "backend.services.crm.automation"
_ADDR = "automation.probe@example.com"
_TEAM_ADDR = "leader.probe@example.com"


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


def _make_pool():
    pool = MagicMock()
    conn = AsyncMock()

    class _Ctx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *a):
            pass

    pool.acquire = MagicMock(return_value=_Ctx())
    return pool


def _patch_email_infra(http_client: object):
    mock_cls = MagicMock()
    mock_cls.return_value = http_client
    return (
        patch("backend.services.crm.automation.httpx.AsyncClient", mock_cls),
        patch(
            "backend.services.crm.automation.log_email_attempt",
            new=AsyncMock(return_value=1),
        ),
        patch(
            "backend.services.crm.automation.record_email_result",
            new=AsyncMock(),
        ),
        patch(
            "backend.services.crm.automation.notify_email_failure_critical",
            new=MagicMock(),
        ),
    )


# --- GUILT ---


@pytest.mark.asyncio
async def test_brevo_success_log_does_not_leak_the_recipient(caplog):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    client.post = AsyncMock(return_value=_FakeResponse())
    p1, p2, p3, p4 = _patch_email_infra(client)
    with p1, p2, p3, p4, caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        await _send_with_brevo_fallback(
            _make_pool(), _ADDR, "hi", "body", email_type="process_start_client"
        )
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _ADDR not in joined
    assert "automation.probe" not in joined
    assert redact_identifier_for_log(_ADDR) in joined
    assert "Brevo" in joined


@pytest.mark.asyncio
async def test_brevo_failure_never_logs_the_address_or_raw_error(caplog):
    """GUILT: before R2, `logger.error("Brevo failed for %s, no fallback
    provider: %s", to_email, brevo_err_msg)` put the raw recipient AND the
    provider's raw error text (which can itself echo the address back, e.g.
    a bounce message) straight into the log."""
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    client.post = AsyncMock(side_effect=RuntimeError(f"550 mailbox {_ADDR} rejected"))
    p1, p2, p3, p4 = _patch_email_infra(client)
    with (
        p1,
        p2,
        p3,
        p4,
        caplog.at_level(logging.INFO, logger=_LOGGER_NAME),
        pytest.raises(RuntimeError),
    ):
        await _send_with_brevo_fallback(
            _make_pool(), _ADDR, "hi", "body", email_type="process_start_client"
        )
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _ADDR not in joined
    assert "automation.probe" not in joined
    assert redact_identifier_for_log(_ADDR) in joined
    assert "Brevo" in joined
    assert "no fallback provider" in joined


# --- INNOCENCE: non-PII diagnostic content survives ---


@pytest.mark.asyncio
async def test_innocence_brevo_failure_keeps_the_non_pii_diagnostic_text(caplog):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    client.post = AsyncMock(side_effect=RuntimeError("connection reset by peer"))
    p1, p2, p3, p4 = _patch_email_infra(client)
    with (
        p1,
        p2,
        p3,
        p4,
        caplog.at_level(logging.INFO, logger=_LOGGER_NAME),
        pytest.raises(RuntimeError),
    ):
        await _send_with_brevo_fallback(
            _make_pool(), _ADDR, "hi", "body", email_type="process_start_client"
        )
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "connection reset by peer" in joined


# --- trigger_on_process_start's OWN caller-level logs (C-2(b), #7488 follow-up) ---


def _make_practice(team_leader_email: str | None) -> dict:
    return {
        "id": 1,
        "client_id": 10,
        "practice_type_name": "KITAS",
        "assigned_to": team_leader_email,
        "created_by": None,
    }


def _make_service() -> ProcessAutomationService:
    return ProcessAutomationService(MagicMock())


@pytest.mark.asyncio
async def test_trigger_client_success_log_does_not_leak_the_client_address(caplog):
    svc = _make_service()
    practice = _make_practice(team_leader_email=None)
    client = {"id": 10, "full_name": "John", "email": _ADDR}
    with (
        patch(
            "backend.services.crm.automation._fetch_practice_with_client",
            new_callable=AsyncMock,
        ) as m_fetch,
        patch(
            "backend.services.crm.automation._send_with_brevo_fallback",
            new_callable=AsyncMock,
        ),
        patch("backend.services.crm.automation._log_activity", new_callable=AsyncMock),
        caplog.at_level(logging.INFO, logger=_LOGGER_NAME),
    ):
        m_fetch.return_value = (practice, client)
        result = await svc.trigger_on_process_start(1, "user@x.com")
    assert result["client_notified"] is True
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _ADDR not in joined
    assert "automation.probe" not in joined
    assert redact_identifier_for_log(_ADDR) in joined
    assert "Process start email sent to client" in joined


@pytest.mark.asyncio
async def test_trigger_team_leader_success_log_does_not_leak_the_team_leader_address(caplog):
    svc = _make_service()
    practice = _make_practice(team_leader_email=_TEAM_ADDR)
    client = {"id": 10, "full_name": "John", "email": None}
    with (
        patch(
            "backend.services.crm.automation._fetch_practice_with_client",
            new_callable=AsyncMock,
        ) as m_fetch,
        patch(
            "backend.services.crm.automation._send_with_brevo_fallback",
            new_callable=AsyncMock,
        ),
        patch("backend.services.crm.automation._log_activity", new_callable=AsyncMock),
        caplog.at_level(logging.INFO, logger=_LOGGER_NAME),
    ):
        m_fetch.return_value = (practice, client)
        result = await svc.trigger_on_process_start(1, "user@x.com")
    assert result["team_leader_notified"] is True
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _TEAM_ADDR not in joined
    assert "leader.probe" not in joined
    assert redact_identifier_for_log(_TEAM_ADDR) in joined
    assert "Process start notification sent to team leader" in joined


def _rendered(records) -> str:
    """Render each record the way a real handler would, INCLUDING the
    formatted traceback when `exc_info` is set — `record.getMessage()` alone
    only reads the `%s` slot and is blind to `exc_info=True` re-attaching the
    raw exception via the traceback (R1, fresh gate on this PR: prod's
    `StructuredFormatter` puts that same text in `exception.message` /
    `exception.traceback`, and `log_ring_buffer.py` stores it too)."""
    fmt = logging.Formatter()
    return "\n".join(fmt.format(r) for r in records)


def _error_records(records):
    return [r for r in records if r.levelno >= logging.ERROR]


@pytest.mark.asyncio
async def test_trigger_client_send_failure_scrubs_a_bounce_that_echoes_the_address(caplog):
    """GUILT: before this fix, `logger.error(..., e, exc_info=True)` put the
    raw caught exception straight into the `%s` slot (and, even after the
    `%s` slot was scrubbed, `exc_info=True` re-attached the same raw text via
    the traceback — R1) — a bounce-style ValueError quoting the recipient
    back leaked it either way. Covers the `(httpx.HTTPError, ValueError)`
    branch on the CLIENT call site."""
    svc = _make_service()
    practice = _make_practice(team_leader_email=None)
    client = {"id": 10, "full_name": "John", "email": _ADDR}
    with (
        patch(
            "backend.services.crm.automation._fetch_practice_with_client",
            new_callable=AsyncMock,
        ) as m_fetch,
        patch(
            "backend.services.crm.automation._send_with_brevo_fallback",
            new_callable=AsyncMock,
            side_effect=ValueError(f"550 mailbox {_ADDR} rejected"),
        ),
        patch("backend.services.crm.automation._log_activity", new_callable=AsyncMock),
        caplog.at_level(logging.INFO, logger=_LOGGER_NAME),
    ):
        m_fetch.return_value = (practice, client)
        result = await svc.trigger_on_process_start(1, "user@x.com")
    assert result["client_notified"] is False
    rendered = _rendered(caplog.records)
    assert _ADDR not in rendered
    assert "automation.probe" not in rendered
    assert "Failed to send process start email to client" in rendered
    assert "ValueError" in rendered  # exception TYPE still survives
    assert "mailbox" in rendered and "rejected" in rendered
    for rec in _error_records(caplog.records):
        assert rec.exc_info is None


@pytest.mark.asyncio
async def test_trigger_client_send_failure_scrubs_the_unexpected_error(caplog):
    """GUILT (R2, fresh gate — this was mutant O1, previously untested):
    covers the bare `except Exception` (unexpected-error) branch on the
    CLIENT call site, not just the `httpx.HTTPError`/`ValueError` one — a
    RuntimeError hits it."""
    svc = _make_service()
    practice = _make_practice(team_leader_email=None)
    client = {"id": 10, "full_name": "John", "email": _ADDR}
    with (
        patch(
            "backend.services.crm.automation._fetch_practice_with_client",
            new_callable=AsyncMock,
        ) as m_fetch,
        patch(
            "backend.services.crm.automation._send_with_brevo_fallback",
            new_callable=AsyncMock,
            side_effect=RuntimeError(f"provider quoted {_ADDR} as invalid"),
        ),
        patch("backend.services.crm.automation._log_activity", new_callable=AsyncMock),
        caplog.at_level(logging.INFO, logger=_LOGGER_NAME),
    ):
        m_fetch.return_value = (practice, client)
        result = await svc.trigger_on_process_start(1, "user@x.com")
    assert result["client_notified"] is False
    rendered = _rendered(caplog.records)
    assert _ADDR not in rendered
    assert "automation.probe" not in rendered
    assert "Unexpected error sending process start email to client" in rendered
    assert "RuntimeError" in rendered
    assert "invalid" in rendered
    for rec in _error_records(caplog.records):
        assert rec.exc_info is None


@pytest.mark.asyncio
async def test_trigger_team_leader_send_failure_scrubs_a_bounce_that_echoes_the_address(caplog):
    """GUILT (R2, fresh gate — this was mutant O2, previously untested):
    covers the `(httpx.HTTPError, ValueError)` branch on the TEAM-LEADER
    call site — the sibling client-side branch was tested, this one wasn't."""
    svc = _make_service()
    practice = _make_practice(team_leader_email=_TEAM_ADDR)
    client = {"id": 10, "full_name": "John", "email": None}
    with (
        patch(
            "backend.services.crm.automation._fetch_practice_with_client",
            new_callable=AsyncMock,
        ) as m_fetch,
        patch(
            "backend.services.crm.automation._send_with_brevo_fallback",
            new_callable=AsyncMock,
            side_effect=ValueError(f"550 mailbox {_TEAM_ADDR} rejected"),
        ),
        patch("backend.services.crm.automation._log_activity", new_callable=AsyncMock),
        caplog.at_level(logging.INFO, logger=_LOGGER_NAME),
    ):
        m_fetch.return_value = (practice, client)
        result = await svc.trigger_on_process_start(1, "user@x.com")
    assert result["team_leader_notified"] is False
    rendered = _rendered(caplog.records)
    assert _TEAM_ADDR not in rendered
    assert "leader.probe" not in rendered
    assert "Failed to send notification to team leader" in rendered
    assert "ValueError" in rendered
    assert "mailbox" in rendered and "rejected" in rendered
    for rec in _error_records(caplog.records):
        assert rec.exc_info is None


@pytest.mark.asyncio
async def test_trigger_team_leader_send_failure_scrubs_the_unexpected_error(caplog):
    """Covers the `except Exception` (unexpected-error) branch, not just
    the `httpx.HTTPError`/`ValueError` one — a bare RuntimeError hits it."""
    svc = _make_service()
    practice = _make_practice(team_leader_email=_TEAM_ADDR)
    client = {"id": 10, "full_name": "John", "email": None}
    with (
        patch(
            "backend.services.crm.automation._fetch_practice_with_client",
            new_callable=AsyncMock,
        ) as m_fetch,
        patch(
            "backend.services.crm.automation._send_with_brevo_fallback",
            new_callable=AsyncMock,
            side_effect=RuntimeError(f"provider quoted {_TEAM_ADDR} as invalid"),
        ),
        patch("backend.services.crm.automation._log_activity", new_callable=AsyncMock),
        caplog.at_level(logging.INFO, logger=_LOGGER_NAME),
    ):
        m_fetch.return_value = (practice, client)
        result = await svc.trigger_on_process_start(1, "user@x.com")
    assert result["team_leader_notified"] is False
    rendered = _rendered(caplog.records)
    assert _TEAM_ADDR not in rendered
    assert "leader.probe" not in rendered
    assert "Unexpected error notifying team leader" in rendered
    assert "RuntimeError" in rendered
    assert "invalid" in rendered
    for rec in _error_records(caplog.records):
        assert rec.exc_info is None


# --- INNOCENCE: trigger_on_process_start keeps non-PII diagnostic text ---


@pytest.mark.asyncio
async def test_innocence_trigger_client_failure_keeps_the_non_pii_diagnostic_text(caplog):
    svc = _make_service()
    practice = _make_practice(team_leader_email=None)
    client = {"id": 10, "full_name": "John", "email": _ADDR}
    with (
        patch(
            "backend.services.crm.automation._fetch_practice_with_client",
            new_callable=AsyncMock,
        ) as m_fetch,
        patch(
            "backend.services.crm.automation._send_with_brevo_fallback",
            new_callable=AsyncMock,
            side_effect=ValueError("connection timed out"),
        ),
        patch("backend.services.crm.automation._log_activity", new_callable=AsyncMock),
        caplog.at_level(logging.INFO, logger=_LOGGER_NAME),
    ):
        m_fetch.return_value = (practice, client)
        await svc.trigger_on_process_start(1, "user@x.com")
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "connection timed out" in joined
