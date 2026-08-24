"""Proves the webhook replay harness (``replay.WebhookReplayer`` +
``conftest.duebot``) drives the REAL WhatsApp/Instagram routers correctly:
a good signature is accepted end-to-end, a tampered/missing/wrong-secret
signature is rejected end-to-end, and a duplicate ``wamid``/``mid`` replay
is idempotent — the exact contract the research capture §5.2 asks this
harness to prove.

Every test here exercises the production routers through an in-process
FastAPI ``TestClient`` (no socket ever opens) with only the heavy
downstream side effects mocked — see ``conftest.duebot``'s docstring for
exactly what is and is not mocked.
"""

from __future__ import annotations

import pytest

from backend.app.core.config import settings
from backend.tests.duebot.conftest import DuebotHarness
from backend.tests.duebot.fake_meta_sender import (
    instagram_dm_payload,
    load_static_payload,
    to_raw_body,
    whatsapp_image_payload,
    whatsapp_status_payload,
    whatsapp_text_payload,
)
from backend.tests.duebot.replay import instagram_replayer, whatsapp_replayer
from backend.tests.duebot.webhook_signer import sign_payload, tamper

APP_SECRET = "harness-test-app-secret-do-not-use-in-prod"


@pytest.fixture(autouse=True)
def _configured_app_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same rationale as ``test_webhook_signer.py`` — arm the real
    signature check for every test in this file instead of running against
    the "no secret configured" dev-mode bypass.
    """
    monkeypatch.setattr(settings, "whatsapp_app_secret", APP_SECRET)


# ---------------------------------------------------------------------------
# WhatsApp
# ---------------------------------------------------------------------------


def test_valid_signed_text_message_is_acked_persisted_and_scheduled(
    duebot: DuebotHarness,
) -> None:
    raw_body = to_raw_body(whatsapp_text_payload(message_id="wamid.REPLAY_001"))
    replayer = whatsapp_replayer(duebot.client)

    result = replayer.send_signed(raw_body, APP_SECRET)

    assert result.status_code == 200
    assert ("whatsapp", "wamid.REPLAY_001") in duebot.seen_dedup_keys
    duebot.process_whatsapp_mock.assert_awaited_once()
    assert duebot.process_whatsapp_mock.call_args.kwargs["message_id"] == "wamid.REPLAY_001"


def test_tampered_body_is_rejected_with_401_and_never_persisted(
    duebot: DuebotHarness,
) -> None:
    """The end-to-end RED case: the same tamper-by-one-byte proof from
    ``test_webhook_signer.py``, now run through the actual HTTP path —
    401, no DB write, no background task.
    """
    raw_body = to_raw_body(whatsapp_text_payload(message_id="wamid.REPLAY_TAMPER"))
    valid_signature = sign_payload(raw_body, APP_SECRET)
    tampered_body = tamper(raw_body)
    replayer = whatsapp_replayer(duebot.client)

    result = replayer.send_raw(tampered_body, signature=valid_signature)

    assert result.status_code == 401
    assert ("whatsapp", "wamid.REPLAY_TAMPER") not in duebot.seen_dedup_keys
    duebot.process_whatsapp_mock.assert_not_awaited()


def test_missing_signature_header_is_rejected(duebot: DuebotHarness) -> None:
    raw_body = to_raw_body(whatsapp_text_payload(message_id="wamid.REPLAY_NOSIG"))
    replayer = whatsapp_replayer(duebot.client)

    result = replayer.send_raw(raw_body, signature=None)

    assert result.status_code == 401
    duebot.process_whatsapp_mock.assert_not_awaited()


def test_wrong_secret_signature_is_rejected(duebot: DuebotHarness) -> None:
    raw_body = to_raw_body(whatsapp_text_payload(message_id="wamid.REPLAY_WRONGSECRET"))
    replayer = whatsapp_replayer(duebot.client)

    result = replayer.send_signed(raw_body, "not-the-configured-secret")

    assert result.status_code == 401
    duebot.process_whatsapp_mock.assert_not_awaited()


def test_malformed_json_body_with_valid_signature_returns_400(duebot: DuebotHarness) -> None:
    """A valid signature over garbage bytes: signature check passes (it
    only cares about bytes), JSON parse fails afterward — 400, not a
    crash, and no persist (parse happens before the persist loop).
    """
    raw_body = b"{not-valid-json"
    replayer = whatsapp_replayer(duebot.client)

    result = replayer.send_signed(raw_body, APP_SECRET)

    assert result.status_code == 400
    duebot.process_whatsapp_mock.assert_not_awaited()


@pytest.mark.parametrize("times", [2, 10, 100])
def test_duplicate_wamid_replayed_n_times_is_idempotent(
    duebot: DuebotHarness, times: int
) -> None:
    """Research capture §5.2: "same event replayed concurrently 2, 10, and
    100 times". ``TestClient`` runs each POST to completion sequentially
    (no real concurrency), which is sufficient here — the property under
    test is idempotency of the STORED outcome, not a race in the DB layer
    (there is no DB layer; ``fake_inbound_store`` IS the linearizable
    source of truth by construction).
    """
    raw_body = to_raw_body(whatsapp_text_payload(message_id=f"wamid.REPLAY_DUP_{times}"))
    replayer = whatsapp_replayer(duebot.client)

    results = replayer.replay(raw_body, APP_SECRET, times=times)

    assert all(r.status_code == 200 for r in results), "every replay must still ack 200"
    assert duebot.process_whatsapp_mock.await_count == 1, (
        "exactly one background-task schedule despite N redeliveries"
    )


def test_image_message_is_persisted_but_not_scheduled_for_text_processing(
    duebot: DuebotHarness,
) -> None:
    """Attachment-only message (research capture §5.1
    ``client.attachment-only-message``): the router persists every message
    in a "messages" change regardless of type, but only schedules the
    inline text-triage background task for ``type == "text"``.
    """
    raw_body = to_raw_body(whatsapp_image_payload(message_id="wamid.REPLAY_IMAGE"))
    replayer = whatsapp_replayer(duebot.client)

    result = replayer.send_signed(raw_body, APP_SECRET)

    assert result.status_code == 200
    assert ("whatsapp", "wamid.REPLAY_IMAGE") in duebot.seen_dedup_keys
    duebot.process_whatsapp_mock.assert_not_awaited()


def test_status_update_is_not_persisted(duebot: DuebotHarness) -> None:
    """A delivery-receipt change (``field="statuses"``) is filtered before
    the persist loop — it is not a message, must not create a row.
    """
    raw_body = to_raw_body(whatsapp_status_payload(message_id="wamid.REPLAY_STATUS"))
    replayer = whatsapp_replayer(duebot.client)

    result = replayer.send_signed(raw_body, APP_SECRET)

    assert result.status_code == 200
    assert ("whatsapp", "wamid.REPLAY_STATUS") not in duebot.seen_dedup_keys
    duebot.process_whatsapp_mock.assert_not_awaited()


@pytest.mark.parametrize(
    "fixture_name",
    ["whatsapp_text.json", "whatsapp_image.json", "whatsapp_status.json"],
)
def test_static_fixtures_replay_successfully(duebot: DuebotHarness, fixture_name: str) -> None:
    """The checked-in payloads/*.json fixtures drive the real router
    end-to-end, not just the freshly-built payloads.
    """
    raw_body = load_static_payload(fixture_name)
    replayer = whatsapp_replayer(duebot.client)

    result = replayer.send_signed(raw_body, APP_SECRET)

    assert result.status_code == 200


# ---------------------------------------------------------------------------
# Instagram
# ---------------------------------------------------------------------------


def test_instagram_dm_is_acked_persisted_and_routed(duebot: DuebotHarness) -> None:
    raw_body = to_raw_body(instagram_dm_payload(mid="ig_mid_REPLAY_001"))
    replayer = instagram_replayer(duebot.client)

    result = replayer.send_raw(raw_body)  # IG router does not verify a signature today

    assert result.status_code == 200
    assert ("instagram", "ig_mid_REPLAY_001") in duebot.seen_dedup_keys
    duebot.channel_router_mock.route_message.assert_awaited_once()
    assert duebot.channel_router_mock.route_message.await_args.args[0] == "instagram"


def test_instagram_duplicate_mid_dedupes_the_persisted_row(duebot: DuebotHarness) -> None:
    """Known, deliberately-not-fixed-here gap (out of scope for B6a):
    unlike the WhatsApp router, the Instagram router does not check
    ``persist()``'s ``inserted`` flag before routing — so the STORED row
    is deduplicated (this assertion), but ``channel_router.route_message``
    is still invoked on every redelivery (asserted explicitly below, so a
    future fix that adds the guard is visible as an intentional test
    change, not a silent behavior flip).
    """
    raw_body = to_raw_body(instagram_dm_payload(mid="ig_mid_REPLAY_DUP"))
    replayer = instagram_replayer(duebot.client)

    results = [replayer.send_raw(raw_body) for _ in range(3)]

    assert all(r.status_code == 200 for r in results)
    assert ("instagram", "ig_mid_REPLAY_DUP") in duebot.seen_dedup_keys
    assert len({k for k in duebot.seen_dedup_keys if k[1] == "ig_mid_REPLAY_DUP"}) == 1
    assert duebot.channel_router_mock.route_message.await_count == 3


def test_instagram_static_fixture_replays_successfully(duebot: DuebotHarness) -> None:
    raw_body = load_static_payload("instagram_dm.json")
    replayer = instagram_replayer(duebot.client)

    result = replayer.send_raw(raw_body)

    assert result.status_code == 200
