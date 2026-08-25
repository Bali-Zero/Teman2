"""``META_WEBHOOK_REQUIRE_SIGNATURE`` — the shared WhatsApp+Instagram fail-closed knob.

WHY THIS FILE EXISTS
--------------------
The knob shipped on 2026-08-25 (#4885, Instagram) and until this file landed it
had **no test of any kind on either surface** — ``grep -rn
meta_webhook_require_signature backend/tests`` returned a single passing mention
inside another test's docstring. Instagram's signature verification, added by
that same PR, had no test at all: the existing ``test_instagram_ack_first.py``
POSTs unsigned and asserts 200, which passes only because the fail-OPEN branch
is taken — so it cannot tell a working verifier from an absent one.

That matters because this knob is the one lever that makes the production
posture non-silently-reversible, and arming an untested switch on a live client
channel is the named scar: *"arming this wrong silently deafens the channel a
second time, in the opposite direction"*
(``.claude/skills/modus/PENDING-ARMS.md``, the WhatsApp fail-open row).

So every case below is written as a GUILT/INNOCENCE pair, per surface:

  GUILT     — with the knob True and no app secret, the webhook REJECTS.
              That is the whole point: an operator who unsets or blanks the
              secret can no longer land production in fail-open without
              anything going red.
  INNOCENCE — with the knob True and the secret present, a correctly signed
              payload is STILL ACCEPTED. This half is not optional. A knob
              that rejected everything would take the channel off the air
              exactly as effectively as the fail-open it replaces, and the
              throughput sentinel would be the only organ that noticed.

The default posture (knob False, no secret -> fail-open) is pinned here too, on
purpose: it is documented behaviour that local dev depends on, and a future
change to ``Settings.meta_webhook_require_signature``'s default should have to
edit a test that says so out loud rather than silently altering every
developer's machine.

Live posture at the time of writing (measured 2026-08-25, not inferred):
``WHATSAPP_APP_SECRET`` and ``INSTAGRAM_APP_SECRET`` are both present on
``nuzantara-rag``, and an unsigned POST to the production WhatsApp webhook
already answers 401 ``Invalid signature``. The knob is what keeps that true.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.config import settings as real_settings

_TEST_APP_SECRET = "test_secret_key_for_hmac"


def _seeded_settings_mock() -> MagicMock:
    """A settings double pre-seeded with the REAL field defaults.

    Same rationale as ``test_whatsapp_chat_coverage._seeded_settings_mock``: a
    bare ``MagicMock`` answers truthily to every attribute, so
    ``not settings.meta_webhook_require_signature`` would read ``False`` and
    silently flip the fail-open branch — turning a test about the DEFAULT
    posture into a test about the armed one, and passing either way.
    """
    mock = MagicMock()
    for field_name, value in real_settings.model_dump().items():
        setattr(mock, field_name, value)
    return mock


def _sign(body: bytes, secret: str = _TEST_APP_SECRET) -> str:
    return f"sha256={hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()}"


# --------------------------------------------------------------------------
# WhatsApp
# --------------------------------------------------------------------------


def _wa_payload() -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "62821",
                                "phone_number_id": "pnid_1",
                            },
                            "messages": [
                                {
                                    "from": "6281234567890",
                                    "id": "wamid.TEST",
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": "Halo"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


@pytest.fixture
def wa_client() -> TestClient:
    from backend.app.routers.whatsapp_chat import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def test_wa_knob_true_without_secret_rejects(wa_client):
    """GUILT — the knob's whole purpose: no secret must mean no service, loudly."""
    with patch(
        "backend.app.routers.whatsapp_chat.settings", new_callable=_seeded_settings_mock
    ) as mock_settings:
        mock_settings.whatsapp_app_secret = None
        mock_settings.meta_webhook_require_signature = True
        resp = wa_client.post(
            "/webhook/whatsapp",
            content=json.dumps(_wa_payload()),
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 401


def test_wa_knob_true_still_accepts_a_valid_signature(wa_client):
    """INNOCENCE — arming the knob must not take the channel off the air."""
    body = json.dumps(_wa_payload()).encode("utf-8")
    with (
        patch(
            "backend.app.routers.whatsapp_chat.settings", new_callable=_seeded_settings_mock
        ) as mock_settings,
        patch("backend.app.routers.whatsapp_chat.process_whatsapp_message", new=AsyncMock()),
    ):
        mock_settings.whatsapp_app_secret = _TEST_APP_SECRET
        mock_settings.meta_webhook_require_signature = True
        resp = wa_client.post(
            "/webhook/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body),
            },
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_wa_knob_true_rejects_an_unsigned_post_when_the_secret_is_present(wa_client):
    """The armed posture must not depend on WHICH of the two conditions is missing."""
    with patch(
        "backend.app.routers.whatsapp_chat.settings", new_callable=_seeded_settings_mock
    ) as mock_settings:
        mock_settings.whatsapp_app_secret = _TEST_APP_SECRET
        mock_settings.meta_webhook_require_signature = True
        resp = wa_client.post(
            "/webhook/whatsapp",
            content=json.dumps(_wa_payload()),
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 401


def test_wa_default_posture_without_secret_is_still_fail_open(wa_client):
    """Pins the documented dev-mode default so a change to it has to say so."""
    with (
        patch(
            "backend.app.routers.whatsapp_chat.settings", new_callable=_seeded_settings_mock
        ) as mock_settings,
        patch("backend.app.routers.whatsapp_chat.process_whatsapp_message", new=AsyncMock()),
    ):
        mock_settings.whatsapp_app_secret = None
        mock_settings.meta_webhook_require_signature = False
        resp = wa_client.post("/webhook/whatsapp", json=_wa_payload())
    assert resp.status_code == 200


# --------------------------------------------------------------------------
# Instagram — the surface #4885 gave a verifier and no test
# --------------------------------------------------------------------------


def _ig_payload() -> dict:
    return {
        "object": "instagram",
        "entry": [
            {
                "id": "ig_entry_1",
                "time": 1700000000,
                "messaging": [
                    {
                        "sender": {"id": "user_1"},
                        "recipient": {"id": "page_1"},
                        "timestamp": 1700000000,
                        "message": {"mid": "ig_msg_xyz", "text": "Hello", "is_echo": False},
                    }
                ],
            }
        ],
    }


@pytest.fixture
def ig_client() -> TestClient:
    from backend.app.routers import instagram_chat

    app = FastAPI()
    app.include_router(instagram_chat.webhook_router)
    # No db_pool and no channel router on purpose: persistence and routing are
    # best-effort and deliberately never block the ack, so the 200 asserted
    # below is the SIGNATURE verdict, not a claim about downstream delivery.
    app.state.db_pool = None
    return TestClient(app, raise_server_exceptions=False)


def test_ig_knob_true_without_secret_rejects(ig_client):
    """GUILT, Instagram side — the knob is shared, so its guarantee must be too."""
    with patch(
        "backend.app.routers.instagram_chat.settings", new_callable=_seeded_settings_mock
    ) as mock_settings:
        mock_settings.instagram_app_secret = None
        mock_settings.meta_webhook_require_signature = True
        resp = ig_client.post(
            "/webhook/instagram",
            content=json.dumps(_ig_payload()),
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 401


def test_ig_knob_true_still_accepts_a_valid_signature(ig_client):
    """INNOCENCE, Instagram side."""
    body = json.dumps(_ig_payload()).encode("utf-8")
    with patch(
        "backend.app.routers.instagram_chat.settings", new_callable=_seeded_settings_mock
    ) as mock_settings:
        mock_settings.instagram_app_secret = _TEST_APP_SECRET
        mock_settings.meta_webhook_require_signature = True
        resp = ig_client.post(
            "/webhook/instagram",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body),
            },
        )
    assert resp.status_code == 200


def test_ig_wrong_signature_is_rejected(ig_client):
    """The first test anywhere that proves Instagram's verifier actually verifies.

    Without this, ``test_instagram_ack_first``'s unsigned-POST-returns-200 reads
    identically whether the verifier works or does not exist at all.
    """
    body = json.dumps(_ig_payload()).encode("utf-8")
    with patch(
        "backend.app.routers.instagram_chat.settings", new_callable=_seeded_settings_mock
    ) as mock_settings:
        mock_settings.instagram_app_secret = _TEST_APP_SECRET
        mock_settings.meta_webhook_require_signature = False
        resp = ig_client.post(
            "/webhook/instagram",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body, "a_different_secret"),
            },
        )
    assert resp.status_code == 401


def test_ig_default_posture_without_secret_is_still_fail_open(ig_client):
    """Pins the default for the surface whose only other test relies on it."""
    with patch(
        "backend.app.routers.instagram_chat.settings", new_callable=_seeded_settings_mock
    ) as mock_settings:
        mock_settings.instagram_app_secret = None
        mock_settings.meta_webhook_require_signature = False
        resp = ig_client.post("/webhook/instagram", json=_ig_payload())
    assert resp.status_code == 200
