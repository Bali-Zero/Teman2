"""Tests for the loopback-only client-portal QA mail sink."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.scripts.portal_qa_mail_sink import QAMailSinkSettings, create_app

_KEY = "synthetic_portal_sink_key_00000001"
_RECIPIENT = "portal-active@example.com"
_SUPPORT_RECIPIENT = "portal-support@example.com"
_ORIGIN = "http://127.0.0.1:3101"
_TOKEN = "synthetic_magic_token_00000000000000000001"


def _settings() -> QAMailSinkSettings:
    return QAMailSinkSettings.from_environment(
        {
            "MY_PORTAL_QA_MAIL_SINK_KEY": _KEY,
            "MY_PORTAL_QA_MAIL_SINK_RECIPIENT": _RECIPIENT,
            "MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT": _SUPPORT_RECIPIENT,
            "MY_PORTAL_QA_FRONTEND_ORIGIN": _ORIGIN,
        }
    )


def _payload(link: str) -> dict[str, str]:
    return {
        "to": _RECIPIENT,
        "subject": "Your Bali Zero portal sign-in link",
        "body": f'<p>Synthetic QA</p><a href="{link}">Sign in</a>',
    }


def test_settings_fail_closed_without_echoing_values() -> None:
    with pytest.raises(RuntimeError, match="MY_PORTAL_QA_MAIL_SINK_KEY") as error:
        QAMailSinkSettings.from_environment(
            {
                "MY_PORTAL_QA_MAIL_SINK_RECIPIENT": _RECIPIENT,
                "MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT": _SUPPORT_RECIPIENT,
                "MY_PORTAL_QA_FRONTEND_ORIGIN": _ORIGIN,
            }
        )
    assert _RECIPIENT not in str(error.value)

    with pytest.raises(RuntimeError, match="MY_PORTAL_QA_FRONTEND_ORIGIN"):
        QAMailSinkSettings.from_environment(
            {
                "MY_PORTAL_QA_MAIL_SINK_KEY": _KEY,
                "MY_PORTAL_QA_MAIL_SINK_RECIPIENT": _RECIPIENT,
                "MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT": _SUPPORT_RECIPIENT,
                "MY_PORTAL_QA_FRONTEND_ORIGIN": "https://my.balizero.com",
            }
        )


def test_sink_rejects_wrong_keys_recipient_and_external_link() -> None:
    client = TestClient(create_app(_settings()))
    local_link = f"{_ORIGIN}/portal/magic?token={_TOKEN}"

    assert (
        client.post(
            "/api/notifications/send-email",
            headers={"X-API-Key": "wrong"},
            json=_payload(local_link),
        ).status_code
        == 401
    )

    wrong_recipient = _payload(local_link)
    wrong_recipient["to"] = "another@example.com"
    assert (
        client.post(
            "/api/notifications/send-email",
            headers={"X-API-Key": _KEY},
            json=wrong_recipient,
        ).status_code
        == 422
    )

    wrong_subject = _payload(local_link)
    wrong_subject["subject"] = "Support request"
    assert (
        client.post(
            "/api/notifications/send-email",
            headers={"X-API-Key": _KEY},
            json=wrong_subject,
        ).status_code
        == 422
    )

    assert (
        client.post(
            "/api/notifications/send-email",
            headers={"X-API-Key": _KEY},
            json=_payload(f"https://my.balizero.com/portal/magic?token={_TOKEN}"),
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/qa/latest-magic-link",
            headers={"X-QA-Sink-Key": _KEY},
        ).status_code
        == 404
    )


def test_sink_captures_one_valid_link_in_memory() -> None:
    client = TestClient(create_app(_settings()))
    link = f"{_ORIGIN}/portal/magic?token={_TOKEN}"

    captured = client.post(
        "/api/notifications/send-email",
        headers={"X-API-Key": _KEY},
        json=_payload(link),
    )
    assert captured.status_code == 200
    assert captured.json() == {"success": True}

    assert client.get("/qa/latest-magic-link").status_code == 401
    latest = client.get(
        "/qa/latest-magic-link",
        headers={"X-QA-Sink-Key": _KEY},
    )
    assert latest.status_code == 200
    assert latest.json() == {"magic_link": link}
    assert (
        client.get(
            "/qa/latest-magic-link",
            headers={"X-QA-Sink-Key": _KEY},
        ).status_code
        == 404
    )

    fresh_process = TestClient(create_app(_settings()))
    assert (
        fresh_process.get(
            "/qa/latest-magic-link",
            headers={"X-QA-Sink-Key": _KEY},
        ).status_code
        == 404
    )


def _support_payload(
    file_name: str = "synthetic-portal-upload-chromium-prodlike.pdf",
) -> dict[str, str]:
    body = f"""Hello,

Client Synthetic Active Portal Client has uploaded a new document to the portal.

Details:
• File: {file_name}
• Type: Other
• Client: Synthetic Active Portal Client

Open the workspace to review and verify the document:
https://kita.balizero.com/clients/101

---
This is an automated notification from Bali Zero CRM.
"""
    return {
        "to": _SUPPORT_RECIPIENT,
        "subject": "📄 New Document Uploaded - Synthetic Active Portal Client",
        "body": body.replace("\n", "<br>"),
    }


def test_sink_captures_only_strict_synthetic_support_notification_count() -> None:
    client = TestClient(create_app(_settings()))

    assert client.get("/qa/support-mail-receipt").status_code == 401
    initial = client.get(
        "/qa/support-mail-receipt",
        headers={"X-QA-Sink-Key": _KEY},
    )
    assert initial.status_code == 200
    assert initial.json() == {"document_upload_notifications": 0}

    captured = client.post(
        "/api/notifications/send-email",
        headers={"X-API-Key": _KEY},
        json=_support_payload(),
    )
    assert captured.status_code == 200
    assert captured.json() == {"success": True}
    receipt = client.get(
        "/qa/support-mail-receipt",
        headers={"X-QA-Sink-Key": _KEY},
    )
    assert receipt.json() == {"document_upload_notifications": 1}

    wrong_name = _support_payload("passport.pdf")
    assert (
        client.post(
            "/api/notifications/send-email",
            headers={"X-API-Key": _KEY},
            json=wrong_name,
        ).status_code
        == 422
    )
    wrong_recipient = _support_payload()
    wrong_recipient["to"] = _RECIPIENT
    assert (
        client.post(
            "/api/notifications/send-email",
            headers={"X-API-Key": _KEY},
            json=wrong_recipient,
        ).status_code
        == 422
    )
    assert client.get(
        "/qa/support-mail-receipt",
        headers={"X-QA-Sink-Key": _KEY},
    ).json() == {"document_upload_notifications": 1}
