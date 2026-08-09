"""Tests for the synthetic portal support-mail adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.portal.qa_support_mail_sink import QASupportMailSinkClient

_KEY = "synthetic_portal_sink_key_00000001"
_RECIPIENT = "portal-support@example.com"
_URL = "http://127.0.0.1:18181/api/notifications/send-email"


def _environment() -> dict[str, str]:
    return {
        "MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT": _RECIPIENT,
        "INTERNAL_EMAIL_API_URL": _URL,
        "NUZANTARA_API_KEY": _KEY,
    }


def test_support_mail_adapter_is_disabled_without_explicit_recipient() -> None:
    assert QASupportMailSinkClient.from_environment({}) is None


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT", "support@balizero.com"),
        (
            "INTERNAL_EMAIL_API_URL",
            "https://nuzantara-rag.fly.dev/api/notifications/send-email",
        ),
        ("INTERNAL_EMAIL_API_URL", "http://127.0.0.1:18181/other"),
        ("NUZANTARA_API_KEY", "weak"),
    ],
)
def test_support_mail_adapter_rejects_unsafe_configuration(name: str, value: str) -> None:
    environment = _environment()
    environment[name] = value

    with pytest.raises(RuntimeError, match=name):
        QASupportMailSinkClient.from_environment(environment)


def test_support_mail_adapter_requires_complete_configuration() -> None:
    environment = _environment()
    del environment["INTERNAL_EMAIL_API_URL"]

    with pytest.raises(RuntimeError, match="configuration is incomplete"):
        QASupportMailSinkClient.from_environment(environment)


@pytest.mark.asyncio
async def test_support_mail_adapter_posts_only_to_configured_recipient() -> None:
    client = QASupportMailSinkClient.from_environment(_environment())
    assert client is not None
    response = MagicMock(status_code=200)
    http_client = MagicMock()
    http_client.post = AsyncMock(return_value=response)

    with patch("httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=http_client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await client.send_document_notification(
            recipient=_RECIPIENT,
            subject="Synthetic subject",
            html_body="Synthetic body",
        )

    http_client.post.assert_awaited_once_with(
        _URL,
        headers={"X-API-Key": _KEY},
        json={
            "to": _RECIPIENT,
            "subject": "Synthetic subject",
            "body": "Synthetic body",
        },
    )

    with pytest.raises(RuntimeError, match="assigned recipient"):
        await client.send_document_notification(
            recipient="another@example.com",
            subject="Synthetic subject",
            html_body="Synthetic body",
        )
