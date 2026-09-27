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
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.security.pii_log_identifier import redact_identifier_for_log
from backend.services.crm.automation import _send_with_brevo_fallback

_LOGGER_NAME = "backend.services.crm.automation"
_ADDR = "automation.probe@example.com"


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
