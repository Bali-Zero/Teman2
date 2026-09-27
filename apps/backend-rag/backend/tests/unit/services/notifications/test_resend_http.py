"""Unit tests for ``services.notifications.resend_http``.

Resend is the secondary delivery path when Brevo fails (NB-E 2026-04-29).
Contract under test:

- Returns ``True`` only on HTTP 200/201/202.
- Returns ``False`` on missing ``RESEND_API_KEY`` (no exception, no log spam).
- Returns ``False`` on non-2xx response (logs the body excerpt).
- Returns ``False`` on httpx exception (degrade-gracefully, no raise).
- Default ``from`` is the ``send.balizero.com`` subdomain so Brevo apex DNS
  issues do not cascade into the fallback path.
- ``cc`` / ``bcc`` / attachments are forwarded to the Resend payload shape.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.notifications.resend_http import send_via_resend


def _mk_response(status: int = 202, body: str = '{"id":"resend_xxx"}') -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = body
    return resp


@pytest.mark.asyncio
async def test_returns_false_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    with patch(
        "backend.services.notifications.resend_http.get_email_client",
        new=AsyncMock(),
    ) as mocked:
        result = await send_via_resend(
            to_email="alice@example.com",
            subject="hello",
            body="<p>hi</p>",
        )
    assert result is False
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_returns_true_on_2xx(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key_xxxxxx")
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=_mk_response(202))
    with patch(
        "backend.services.notifications.resend_http.get_email_client",
        new=AsyncMock(return_value=fake_client),
    ):
        result = await send_via_resend(
            to_email="alice@example.com",
            subject="hello",
            body="<p>hi</p>",
        )
    assert result is True
    fake_client.post.assert_called_once()
    args, kwargs = fake_client.post.call_args
    assert args[0] == "https://api.resend.com/emails"
    assert kwargs["headers"]["Authorization"].startswith("Bearer re_")
    payload = kwargs["json"]
    # Default from is send.balizero.com — the verified subdomain.
    assert "send.balizero.com" in payload["from"]
    assert payload["to"] == ["alice@example.com"]
    assert payload["subject"] == "hello"
    assert payload["html"] == "<p>hi</p>"


@pytest.mark.asyncio
async def test_default_from_uses_send_subdomain(monkeypatch):
    """Apex balizero.com is Brevo's domain. Resend MUST default to the
    separate subdomain so a Brevo apex DKIM/MX failure does not also
    take down the fallback. This test pins the default."""
    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    monkeypatch.delenv("RESEND_FROM_EMAIL", raising=False)
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=_mk_response(200))
    with patch(
        "backend.services.notifications.resend_http.get_email_client",
        new=AsyncMock(return_value=fake_client),
    ):
        await send_via_resend(to_email="x@y.com", subject="s", body="b")
    payload = fake_client.post.call_args.kwargs["json"]
    assert payload["from"] == "Zantara <zantara@send.balizero.com>"


@pytest.mark.asyncio
async def test_returns_false_on_4xx(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=_mk_response(422, '{"error":"bad"}'))
    with patch(
        "backend.services.notifications.resend_http.get_email_client",
        new=AsyncMock(return_value=fake_client),
    ):
        result = await send_via_resend(to_email="x@y.com", subject="s", body="b")
    assert result is False


@pytest.mark.asyncio
async def test_returns_false_on_exception(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    fake_client = MagicMock()
    fake_client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
    with patch(
        "backend.services.notifications.resend_http.get_email_client",
        new=AsyncMock(return_value=fake_client),
    ):
        result = await send_via_resend(to_email="x@y.com", subject="s", body="b")
    assert result is False


@pytest.mark.asyncio
async def test_cc_bcc_attachments_forwarded(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=_mk_response(202))
    with patch(
        "backend.services.notifications.resend_http.get_email_client",
        new=AsyncMock(return_value=fake_client),
    ):
        await send_via_resend(
            to_email="x@y.com",
            subject="s",
            body="b",
            cc=["c@x.com"],
            bcc=["b@x.com"],
            attachments=[{"name": "doc.pdf", "content": "BASE64=="}],
        )
    payload = fake_client.post.call_args.kwargs["json"]
    assert payload["cc"] == ["c@x.com"]
    assert payload["bcc"] == ["b@x.com"]
    assert payload["attachments"] == [{"filename": "doc.pdf", "content": "BASE64=="}]


@pytest.mark.asyncio
async def test_from_override_via_env(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "ops@send.balizero.com")
    monkeypatch.setenv("RESEND_FROM_NAME", "Ops")
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=_mk_response(202))
    with patch(
        "backend.services.notifications.resend_http.get_email_client",
        new=AsyncMock(return_value=fake_client),
    ):
        await send_via_resend(to_email="x@y.com", subject="s", body="b")
    payload = fake_client.post.call_args.kwargs["json"]
    assert payload["from"] == "Ops <ops@send.balizero.com>"


# ---------------------------------------------------------------------------
# C3 (fresh gate on #7449, follow-up mandate): none of the three log call
# sites in send_via_resend() may carry the raw recipient address or an
# unscrubbed provider body/exception. Guilt+innocence per site.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_log_does_not_leak_the_recipient_and_carries_the_digest(
    monkeypatch, caplog
):
    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=_mk_response(202))
    with (
        patch(
            "backend.services.notifications.resend_http.get_email_client",
            new=AsyncMock(return_value=fake_client),
        ),
        caplog.at_level(logging.INFO, logger="backend.services.notifications.resend_http"),
    ):
        await send_via_resend(to_email="alice@example.com", subject="hello", body="<p>hi</p>")
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "alice@example.com" not in joined
    assert "id:" in joined


@pytest.mark.asyncio
async def test_success_log_escapes_a_newline_in_the_subject(monkeypatch, caplog):
    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=_mk_response(202))
    with (
        patch(
            "backend.services.notifications.resend_http.get_email_client",
            new=AsyncMock(return_value=fake_client),
        ),
        caplog.at_level(logging.INFO, logger="backend.services.notifications.resend_http"),
    ):
        await send_via_resend(
            to_email="x@y.com", subject="Invoice ready\nX-Injected: evil", body="b"
        )
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "\nX-Injected" not in joined
    assert "\\nX-Injected" in joined


@pytest.mark.asyncio
async def test_success_log_scrubs_an_address_embedded_in_the_subject(monkeypatch, caplog):
    """GUILT (R2, fresh gate on #7488 — this was mutant O6, previously
    untested): the newline-escaping test above only proves `repr()` runs; it
    never puts an address IN the subject, so a mutant that drops
    `_bounded_scrub(subject, 120)` and keeps only `repr(subject)` survived
    every existing test. A personalized subject line (e.g. `Re: invoice for
    <name> <addr>`) is exactly the caller-supplied-text case the module
    comment on `notify_email_failure_critical` already warns about."""
    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    addr = "subject.leak@example.com"
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=_mk_response(202))
    with (
        patch(
            "backend.services.notifications.resend_http.get_email_client",
            new=AsyncMock(return_value=fake_client),
        ),
        caplog.at_level(logging.INFO, logger="backend.services.notifications.resend_http"),
    ):
        await send_via_resend(
            to_email="other@example.com", subject=f"Re: invoice for {addr}", body="b"
        )
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert addr not in joined
    assert "subject.leak" not in joined
    assert "Re: invoice for" in joined  # non-PII prose survives


@pytest.mark.asyncio
async def test_error_log_does_not_leak_the_recipient_or_the_raw_response_body(
    monkeypatch, caplog
):
    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    fake_client = MagicMock()
    fake_client.post = AsyncMock(
        return_value=_mk_response(422, '{"error":"unknown address bob@example.com"}')
    )
    with (
        patch(
            "backend.services.notifications.resend_http.get_email_client",
            new=AsyncMock(return_value=fake_client),
        ),
        caplog.at_level(logging.ERROR, logger="backend.services.notifications.resend_http"),
    ):
        result = await send_via_resend(to_email="bob@example.com", subject="s", body="b")
    assert result is False
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "bob@example.com" not in joined
    assert "id:" in joined
    assert "unknown address" in joined  # non-PII diagnostic text survives


@pytest.mark.asyncio
async def test_error_log_innocence_keeps_a_non_pii_status_code_readable(monkeypatch, caplog):
    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=_mk_response(429, "rate limited"))
    with (
        patch(
            "backend.services.notifications.resend_http.get_email_client",
            new=AsyncMock(return_value=fake_client),
        ),
        caplog.at_level(logging.ERROR, logger="backend.services.notifications.resend_http"),
    ):
        await send_via_resend(to_email="x@y.com", subject="s", body="b")
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "429" in joined
    assert "rate limited" in joined


@pytest.mark.asyncio
async def test_exception_log_does_not_leak_the_recipient_or_exception_text(monkeypatch, caplog):
    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    fake_client = MagicMock()
    fake_client.post = AsyncMock(
        side_effect=httpx.ConnectError("connect failed for carol@example.com")
    )
    with (
        patch(
            "backend.services.notifications.resend_http.get_email_client",
            new=AsyncMock(return_value=fake_client),
        ),
        caplog.at_level(logging.ERROR, logger="backend.services.notifications.resend_http"),
    ):
        result = await send_via_resend(to_email="carol@example.com", subject="s", body="b")
    assert result is False
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "carol@example.com" not in joined
    assert "id:" in joined
