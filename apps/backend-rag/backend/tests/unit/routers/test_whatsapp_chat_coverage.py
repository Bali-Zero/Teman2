"""
Unit tests for whatsapp_chat router.
Coverage target: GET /webhook/whatsapp (verification), POST /webhook/whatsapp (messages),
GET /webhook/whatsapp/status, alias routes GET/POST /api/whatsapp/webhook,
X-Hub-Signature-256 HMAC verification.
"""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.whatsapp_chat import alias_router, router


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.include_router(alias_router)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


# ============================================================
# GET /webhook/whatsapp — Verification
# ============================================================


def test_verify_webhook_success(client):
    """Should return hub.challenge when mode=subscribe and token matches."""
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_verify_token = "test_whatsapp_verify_token"
        response = client.get(
            "/webhook/whatsapp"
            "?hub.mode=subscribe"
            "&hub.verify_token=test_whatsapp_verify_token"
            "&hub.challenge=CHALLENGE_CODE_12345"
        )
    assert response.status_code == 200
    assert response.text == "CHALLENGE_CODE_12345"


def test_verify_webhook_wrong_token(client):
    """Should return 403 when verify token doesn't match."""
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_verify_token = "correct_token"
        response = client.get(
            "/webhook/whatsapp"
            "?hub.mode=subscribe"
            "&hub.verify_token=wrong_token"
            "&hub.challenge=CHALLENGE"
        )
    assert response.status_code == 403


def test_verify_webhook_wrong_mode(client):
    """Should return 403 when mode is not 'subscribe'."""
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_verify_token = "test_token"
        response = client.get(
            "/webhook/whatsapp"
            "?hub.mode=unsubscribe"
            "&hub.verify_token=test_token"
            "&hub.challenge=CHALLENGE"
        )
    assert response.status_code == 403


def test_verify_webhook_missing_params(client):
    """Should return 403 when params are missing."""
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_verify_token = "test_token"
        response = client.get("/webhook/whatsapp")
    assert response.status_code == 403


def test_verify_webhook_empty_challenge(client):
    """Should return empty challenge string when challenge is empty."""
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_verify_token = "test_whatsapp_verify_token"
        response = client.get(
            "/webhook/whatsapp"
            "?hub.mode=subscribe"
            "&hub.verify_token=test_whatsapp_verify_token"
            "&hub.challenge="
        )
    # Challenge is None → returns None as text or 200
    assert response.status_code in (200, 403)


# ============================================================
# POST /webhook/whatsapp — Message handling
# ============================================================


def _make_webhook_payload(
    phone: str = "621234567890",
    text: str = "Hello Zan!",
    message_id: str = "wamid.ABC123",
    sender_name: str = "Test Client",
    message_type: str = "text",
) -> dict:
    """Build a valid WhatsApp webhook payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15556151111",
                                "phone_number_id": "PHONE_NUMBER_ID",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": sender_name},
                                    "wa_id": phone,
                                }
                            ],
                            "messages": [
                                {
                                    "from": phone,
                                    "id": message_id,
                                    "timestamp": "1712000000",
                                    "type": message_type,
                                    "text": {"body": text} if message_type == "text" else None,
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def test_whatsapp_webhook_returns_ok(client):
    """Should return status=ok immediately without processing."""
    with (
        patch("backend.app.routers.whatsapp_chat.settings") as mock_settings,
        patch("backend.app.routers.whatsapp_chat.process_whatsapp_message", new=AsyncMock()),
    ):
        mock_settings.whatsapp_app_secret = None
        response = client.post("/webhook/whatsapp", json=_make_webhook_payload())
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_whatsapp_webhook_non_text_message_ignored(client):
    """Should skip non-text messages and still return ok."""
    payload = _make_webhook_payload(message_type="image")
    # Remove text field from payload since type is image
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"] = None

    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_app_secret = None
        response = client.post("/webhook/whatsapp", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_whatsapp_webhook_non_message_change_ignored(client):
    """Should skip non-messages change events."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "BIZ_ID",
                "changes": [
                    {
                        "field": "statuses",
                        "value": {"statuses": [{"id": "wamid.XYZ", "status": "delivered"}]},
                    }
                ],
            }
        ],
    }
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_app_secret = None
        response = client.post("/webhook/whatsapp", json=payload)
    assert response.status_code == 200


def test_whatsapp_webhook_empty_messages(client):
    """Should handle empty messages array gracefully."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "BIZ_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {"messages": []},
                    }
                ],
            }
        ],
    }
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_app_secret = None
        response = client.post("/webhook/whatsapp", json=payload)
    assert response.status_code == 200


def test_whatsapp_webhook_empty_text_body(client):
    """Should skip messages with empty text body."""
    payload = _make_webhook_payload(text="")
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_app_secret = None
        response = client.post("/webhook/whatsapp", json=payload)
    assert response.status_code == 200


def test_whatsapp_webhook_multiple_messages(client):
    """Should process multiple messages in a single webhook."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "BIZ_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "contacts": [{"profile": {"name": "Client"}, "wa_id": "621234"}],
                            "messages": [
                                {
                                    "from": "621234",
                                    "id": "msg_001",
                                    "timestamp": "1712000000",
                                    "type": "text",
                                    "text": {"body": "First message"},
                                },
                                {
                                    "from": "621234",
                                    "id": "msg_002",
                                    "timestamp": "1712000001",
                                    "type": "text",
                                    "text": {"body": "Second message"},
                                },
                            ],
                        },
                    }
                ],
            }
        ],
    }
    with (
        patch("backend.app.routers.whatsapp_chat.settings") as mock_settings,
        patch("backend.app.routers.whatsapp_chat.process_whatsapp_message", new=AsyncMock()),
    ):
        mock_settings.whatsapp_app_secret = None
        response = client.post("/webhook/whatsapp", json=payload)
    assert response.status_code == 200


def test_whatsapp_webhook_no_contacts(client):
    """Should handle webhook without contacts (sender_name=None)."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "BIZ_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "from": "621234567890",
                                    "id": "msg_001",
                                    "timestamp": "1712000000",
                                    "type": "text",
                                    "text": {"body": "Hello"},
                                }
                            ]
                        },
                    }
                ],
            }
        ],
    }
    with (
        patch("backend.app.routers.whatsapp_chat.settings") as mock_settings,
        patch("backend.app.routers.whatsapp_chat.process_whatsapp_message", new=AsyncMock()),
    ):
        mock_settings.whatsapp_app_secret = None
        response = client.post("/webhook/whatsapp", json=payload)
    assert response.status_code == 200


def test_whatsapp_webhook_invalid_payload(client):
    """Should return 400 for invalid payload structure (now parsed internally)."""
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_app_secret = None
        response = client.post("/webhook/whatsapp", json={"invalid": "payload"})
    assert response.status_code == 400


def test_whatsapp_webhook_missing_object_field(client):
    """Should return 400 when 'object' field is missing."""
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_app_secret = None
        response = client.post("/webhook/whatsapp", json={"entry": []})
    assert response.status_code == 400


# ============================================================
# GET /webhook/whatsapp/status
# ============================================================


def test_whatsapp_status_configured(client):
    """Should return configured=True when tokens are set."""
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_api_token = "test_token"
        mock_settings.whatsapp_phone_number_id = "12345678"
        mock_settings.admin_telegram_chat_id = None

        mock_triage = MagicMock()
        mock_triage.personal_contacts = ["62812345", "62898765"]

        with patch(
            "backend.app.routers.whatsapp_chat.whatsapp_triage_service",
            mock_triage,
        ):
            response = client.get("/webhook/whatsapp/status")

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert "phone_number_id" in data
    assert data["triage_enabled"] is True


def test_whatsapp_status_not_configured(client):
    """Should return configured=False when tokens are missing."""
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_api_token = None
        mock_settings.whatsapp_phone_number_id = None

        mock_triage = MagicMock()
        mock_triage.personal_contacts = []

        with patch(
            "backend.app.routers.whatsapp_chat.whatsapp_triage_service",
            mock_triage,
        ):
            response = client.get("/webhook/whatsapp/status")

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is False
    assert data["phone_number_id"] is None


# ============================================================
# Alias routes: GET/POST /api/whatsapp/webhook
# ============================================================


def test_verify_webhook_alias_success(client):
    """Alias GET /api/whatsapp/webhook should behave like primary."""
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_verify_token = "test_whatsapp_verify_token"
        response = client.get(
            "/api/whatsapp/webhook"
            "?hub.mode=subscribe"
            "&hub.verify_token=test_whatsapp_verify_token"
            "&hub.challenge=ALIAS_CHALLENGE"
        )
    assert response.status_code == 200
    assert response.text == "ALIAS_CHALLENGE"


def test_verify_webhook_alias_wrong_token(client):
    """Alias GET should also return 403 for wrong token."""
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_verify_token = "correct_token"
        response = client.get(
            "/api/whatsapp/webhook"
            "?hub.mode=subscribe"
            "&hub.verify_token=wrong_token"
            "&hub.challenge=CHALLENGE"
        )
    assert response.status_code == 403


def test_webhook_alias_post_returns_ok(client):
    """Alias POST /api/whatsapp/webhook should return ok."""
    with (
        patch("backend.app.routers.whatsapp_chat.settings") as mock_settings,
        patch("backend.app.routers.whatsapp_chat.process_whatsapp_message", new=AsyncMock()),
    ):
        mock_settings.whatsapp_app_secret = None
        response = client.post("/api/whatsapp/webhook", json=_make_webhook_payload())
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ============================================================
# HMAC-SHA256 Signature Verification
# ============================================================

_TEST_APP_SECRET = "test_secret_key_for_hmac"


def _sign_payload(payload: dict, secret: str = _TEST_APP_SECRET) -> str:
    """Generate X-Hub-Signature-256 header value for a payload."""
    body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def test_hmac_unsigned_request_rejected_when_secret_configured(client):
    """POST without signature should return 401 when WHATSAPP_APP_SECRET is set."""
    payload = _make_webhook_payload()
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_app_secret = _TEST_APP_SECRET
        response = client.post(
            "/webhook/whatsapp",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 401


def test_hmac_wrong_signature_rejected(client):
    """POST with wrong signature should return 401."""
    payload = _make_webhook_payload()
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_app_secret = _TEST_APP_SECRET
        response = client.post(
            "/webhook/whatsapp",
            content=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=0000000000000000000000000000000000000000000000000000000000000000",
            },
        )
    assert response.status_code == 401


def test_hmac_valid_signature_accepted(client):
    """POST with valid HMAC signature should pass through and return 200."""
    payload = _make_webhook_payload()
    body = json.dumps(payload)
    signature = _sign_payload(payload)

    with (
        patch("backend.app.routers.whatsapp_chat.settings") as mock_settings,
        patch("backend.app.routers.whatsapp_chat.process_whatsapp_message", new=AsyncMock()),
    ):
        mock_settings.whatsapp_app_secret = _TEST_APP_SECRET
        response = client.post(
            "/webhook/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_hmac_skipped_when_no_secret(client):
    """POST without signature should pass when WHATSAPP_APP_SECRET is not configured."""
    with (
        patch("backend.app.routers.whatsapp_chat.settings") as mock_settings,
        patch("backend.app.routers.whatsapp_chat.process_whatsapp_message", new=AsyncMock()),
    ):
        mock_settings.whatsapp_app_secret = None
        response = client.post("/webhook/whatsapp", json=_make_webhook_payload())
    assert response.status_code == 200


def test_hmac_malformed_signature_rejected(client):
    """POST with malformed signature (no sha256= prefix) should return 401."""
    payload = _make_webhook_payload()
    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.whatsapp_app_secret = _TEST_APP_SECRET
        response = client.post(
            "/webhook/whatsapp",
            content=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "invalid_format_no_prefix",
            },
        )
    assert response.status_code == 401


# ============================================================
# process_whatsapp_message — unit tests (pure function)
# ============================================================


@pytest.mark.asyncio
async def test_process_whatsapp_message_not_allowed():
    """Should return early for non-allowed phone numbers."""
    from backend.app.routers.whatsapp_chat import process_whatsapp_message

    mock_request = MagicMock()
    mock_triage_service = MagicMock()
    mock_triage_service.is_allowed.return_value = False
    mock_wa_service = MagicMock()
    mock_wa_service.mark_message_read = AsyncMock()

    with (
        patch("backend.app.routers.whatsapp_chat.whatsapp_service", mock_wa_service),
        patch("backend.app.routers.whatsapp_chat.whatsapp_triage_service", mock_triage_service),
    ):
        # Should complete without error
        await process_whatsapp_message(
            phone="628999999999",
            message_text="Hello",
            sender_name="Unknown",
            message_id="msg_test",
            request=mock_request,
        )

    mock_triage_service.is_allowed.assert_called_once_with("628999999999")


@pytest.mark.asyncio
async def test_process_whatsapp_message_escalate_to_human():
    """Should escalate to human and send Telegram notification."""
    from backend.app.routers.whatsapp_chat import process_whatsapp_message
    from backend.services.integrations.whatsapp_triage_service import TriageDecision

    mock_request = MagicMock()
    mock_triage_service = MagicMock()
    mock_triage_service.is_allowed.return_value = True
    mock_triage_service.should_escalate = AsyncMock(
        return_value=(TriageDecision.ESCALATE_PERSONAL, "personal_contact")
    )
    mock_triage_service.get_escalation_message.return_value = "Transferring to team..."

    mock_wa_service = MagicMock()
    mock_wa_service.mark_message_read = AsyncMock()
    mock_wa_service.send_message = AsyncMock()

    mock_onboarding = MagicMock()
    mock_onboarding.detect_and_trigger = AsyncMock(return_value=None)

    with (
        patch("backend.app.routers.whatsapp_chat.whatsapp_service", mock_wa_service),
        patch("backend.app.routers.whatsapp_chat.whatsapp_triage_service", mock_triage_service),
        patch("backend.app.routers.whatsapp_chat.get_onboarding_detector", return_value=mock_onboarding),
        patch("backend.app.routers.whatsapp_chat.notify_human_telegram", new=AsyncMock()),
        patch("backend.app.routers.whatsapp_chat._get_db_pool", return_value=None),
        patch("backend.app.routers.whatsapp_chat.settings") as mock_settings,
    ):
        mock_settings.admin_telegram_chat_id = "123456"
        await process_whatsapp_message(
            phone="621234567890",
            message_text="This is personal",
            sender_name="Test Client",
            message_id="msg_001",
            request=mock_request,
        )

    mock_wa_service.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_process_whatsapp_message_offer_choice():
    """Should send welcome message for OFFER_CHOICE decision."""
    from backend.app.routers.whatsapp_chat import process_whatsapp_message
    from backend.services.integrations.whatsapp_triage_service import TriageDecision

    mock_request = MagicMock()
    mock_triage_service = MagicMock()
    mock_triage_service.is_allowed.return_value = True
    mock_triage_service.should_escalate = AsyncMock(
        return_value=(TriageDecision.OFFER_CHOICE, "ambiguous")
    )
    mock_triage_service.get_welcome_message.return_value = "How can I help?"

    mock_wa_service = MagicMock()
    mock_wa_service.mark_message_read = AsyncMock()
    mock_wa_service.send_message = AsyncMock()

    mock_onboarding = MagicMock()
    mock_onboarding.detect_and_trigger = AsyncMock(return_value=None)

    with (
        patch("backend.app.routers.whatsapp_chat.whatsapp_service", mock_wa_service),
        patch("backend.app.routers.whatsapp_chat.whatsapp_triage_service", mock_triage_service),
        patch("backend.app.routers.whatsapp_chat.get_onboarding_detector", return_value=mock_onboarding),
    ):
        await process_whatsapp_message(
            phone="621234567890",
            message_text="hi",
            sender_name=None,
            message_id="msg_002",
            request=mock_request,
        )

    mock_wa_service.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_process_whatsapp_message_onboarding_triggered():
    """Should send onboarding confirmation when detector triggers."""
    from backend.app.routers.whatsapp_chat import process_whatsapp_message
    from backend.services.integrations.whatsapp_triage_service import TriageDecision

    mock_request = MagicMock()
    mock_triage_service = MagicMock()
    mock_triage_service.is_allowed.return_value = True
    mock_triage_service.should_escalate = AsyncMock(
        return_value=(TriageDecision.BOT_CAN_HANDLE, "business_query")
    )

    mock_wa_service = MagicMock()
    mock_wa_service.mark_message_read = AsyncMock()
    mock_wa_service.send_message = AsyncMock()

    mock_onboarding = MagicMock()
    mock_onboarding.detect_and_trigger = AsyncMock(
        return_value={"chain": "new_client_onboarding", "status": "triggered"}
    )

    mock_telegram = MagicMock()
    mock_telegram.send_message = AsyncMock()

    with (
        patch("backend.app.routers.whatsapp_chat.whatsapp_service", mock_wa_service),
        patch("backend.app.routers.whatsapp_chat.whatsapp_triage_service", mock_triage_service),
        patch("backend.app.routers.whatsapp_chat.get_onboarding_detector", return_value=mock_onboarding),
        patch("backend.app.routers.whatsapp_chat.telegram_bot", mock_telegram),
        patch("backend.app.routers.whatsapp_chat.settings") as mock_settings,
    ):
        mock_settings.admin_telegram_chat_id = "8037989885"
        await process_whatsapp_message(
            phone="621234567890",
            message_text="I want to set up a company",
            sender_name="New Client",
            message_id="msg_003",
            request=mock_request,
        )

    # Should send onboarding confirmation to client
    mock_wa_service.send_message.assert_called()


# ============================================================
# notify_zero_conversation_log — unit test
# ============================================================


@pytest.mark.asyncio
async def test_notify_zero_conversation_log_no_chat_id():
    """Should return early when no admin_telegram_chat_id configured."""
    from backend.app.routers.whatsapp_chat import notify_zero_conversation_log

    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.admin_telegram_chat_id = None
        # Should not raise
        await notify_zero_conversation_log(
            phone="621234567890",
            sender_name="Client",
            client_message="Hello",
            bot_response="Hi!",
            language="en",
        )


@pytest.mark.asyncio
async def test_notify_zero_conversation_log_sends_message():
    """Should send Telegram message when chat_id is configured."""
    from backend.app.routers.whatsapp_chat import notify_zero_conversation_log

    mock_telegram = MagicMock()
    mock_telegram.send_message = AsyncMock()

    with (
        patch("backend.app.routers.whatsapp_chat.settings") as mock_settings,
        patch("backend.app.routers.whatsapp_chat.telegram_bot", mock_telegram),
    ):
        mock_settings.admin_telegram_chat_id = "1125336968"
        await notify_zero_conversation_log(
            phone="621234567890",
            sender_name="Test",
            client_message="What is a PT PMA?",
            bot_response="PT PMA is a foreign investment company...",
            language="en",
        )

    mock_telegram.send_message.assert_called_once()


# ============================================================
# notify_human_telegram — unit test
# ============================================================


@pytest.mark.asyncio
async def test_notify_human_telegram_no_chat_id():
    """Should return early when no admin_telegram_chat_id."""
    from backend.app.routers.whatsapp_chat import notify_human_telegram

    with patch("backend.app.routers.whatsapp_chat.settings") as mock_settings:
        mock_settings.admin_telegram_chat_id = None
        await notify_human_telegram(phone="62123", message_text="Help!")


@pytest.mark.asyncio
async def test_notify_human_telegram_with_context():
    """Should format and send message with client profile and history."""
    from backend.app.routers.whatsapp_chat import notify_human_telegram

    mock_telegram = MagicMock()
    mock_telegram.send_message = AsyncMock()

    with (
        patch("backend.app.routers.whatsapp_chat.settings") as mock_settings,
        patch("backend.app.routers.whatsapp_chat.telegram_bot", mock_telegram),
    ):
        mock_settings.admin_telegram_chat_id = "1125336968"
        await notify_human_telegram(
            phone="621234567890",
            message_text="I need help personally",
            sender_name="Marco",
            reason="personal_contact",
            client_profile={
                "detected_language": "it",
                "interests": ["visa", "company"],
                "visa_discussed": ["KITAS"],
                "client_type": "prospect",
                "message_count": 5,
                "first_contact": "2026-04-01",
            },
            conversation_history=[
                {"role": "user", "content": "ciao"},
                {"role": "assistant", "content": "Ciao! Come posso aiutarti?"},
            ],
        )

    mock_telegram.send_message.assert_called_once()
