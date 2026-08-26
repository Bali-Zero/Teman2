"""Guilt+innocence tests for the 2026-08-26 team-bot-ingress routing fix.

Zero confirmed via WhatsApp Manager (2026-08-26) that the team-bot number
(``TEAM_BOT_PHONE_NUMBER_ID``) lives on the SAME WABA and the SAME Meta app
as the public client number: one app, one webhook, two numbers. Before this
fix, the team-bot pnid matched neither ``META_INBOX_PHONE_NUMBER_IDS`` (an
unlisted id) nor the public-number ``display_phone_number`` fallback (a
genuinely different visible number), so it fell all the way through the
webhook router's classification into the legacy inline client-triage flow —
a staff message would have been processed as if it came from a client.

The naive fix (adding the team pnid to ``META_INBOX_PHONE_NUMBER_IDS``)
would have been equally wrong: it removes the fall-through but routes staff
traffic into the CLIENT meta-inbox pipeline instead — a different wrong
destination. This lane adds a THIRD, disjoint branch
(``_change_belongs_to_team_bot_ingress`` / ``_team_bot_ingress_enabled`` /
``_handle_team_bot_ingress_payload``), checked before both existing
branches, so team-bot traffic reaches neither.

Only synthetic sender phone numbers are used below — the business-side
constants (``TEAM_BOT_PHONE_NUMBER_ID``, the canonical meta-inbox id, the
default public display number) are configuration values, not PII, and are
already public in the plan docs this lane implements.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.routers import whatsapp_chat
from backend.services.integrations import wa_outbox_worker

TEAM_ID = whatsapp_chat.TEAM_BOT_PHONE_NUMBER_ID
CLIENT_META_INBOX_ID = wa_outbox_worker.META_INBOX_PHONE_NUMBER_ID
UNRELATED_ID = "5550001112223"
PUBLIC_DISPLAY_NUMBER = "628213465159"  # digits of settings.SUPPORT_WHATSAPP default
SECOND_META_INBOX_SUBSCRIPTION_ID = "2000000000000000"  # unlisted id, same visible number


def _change(phone_number_id: str | None, display_phone_number: str | None = None) -> Any:
    metadata: dict[str, Any] = {}
    if phone_number_id is not None:
        metadata["phone_number_id"] = phone_number_id
    if display_phone_number is not None:
        metadata["display_phone_number"] = display_phone_number
    return MagicMock(field="messages", value={"metadata": metadata})


# ---------------------------------------------------------------------------
# NOTE on scope, so the next reader does not think a test went missing.
# The sibling branch's first test asserted that TEAM_BOT_INGRESS_ENABLED is an
# entry in `backend.services.client_bot.kill_switches` (owning lane B3,
# default_dark=True). That package does not exist on origin/main yet: it lands
# with the client-bot lane, not with this router fix. Carrying the test here
# would have made a 132-line routing cure depend on a module it does not need.
# The behaviour that test protected is NOT lost — `test_ingress_flag_*` below
# pin the same contract (born OFF, only the literal "true" arms it, anything
# else fails closed) against the reader this router actually calls. When the
# registry lands, re-add the registry-shape assertion beside these.
# ---------------------------------------------------------------------------


def test_ingress_flag_defaults_off_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEAM_BOT_INGRESS_ENABLED", raising=False)
    assert whatsapp_chat._team_bot_ingress_enabled() is False


@pytest.mark.parametrize("value", ["true", "True", "TRUE", " true "])
def test_ingress_flag_true_variants_turn_it_on(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("TEAM_BOT_INGRESS_ENABLED", value)
    assert whatsapp_chat._team_bot_ingress_enabled() is True


@pytest.mark.parametrize("value", ["false", "0", "1", "yes", "", "  "])
def test_ingress_flag_anything_else_fails_closed(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Fail-closed means a typo or an unexpected value degrades to OFF, not
    ON — this is the flag's whole safety property, so every non-"true"
    value gets its own case here rather than one representative sample.
    """
    monkeypatch.setenv("TEAM_BOT_INGRESS_ENABLED", value)
    assert whatsapp_chat._team_bot_ingress_enabled() is False


# ---------------------------------------------------------------------------
# _change_belongs_to_team_bot_ingress — guilt + innocence
# ---------------------------------------------------------------------------


def test_team_bot_pnid_is_recognised() -> None:
    """Guilt: the exact defect input — the team-bot pnid — must be caught."""
    assert whatsapp_chat._change_belongs_to_team_bot_ingress(_change(TEAM_ID)) is True


def test_client_meta_inbox_pnid_is_not_team_bot() -> None:
    """Innocence: the client meta-inbox id must never match the team-bot set."""
    assert whatsapp_chat._change_belongs_to_team_bot_ingress(_change(CLIENT_META_INBOX_ID)) is False


def test_unrelated_pnid_is_not_team_bot() -> None:
    """Innocence: a genuinely unrelated id must never match."""
    assert whatsapp_chat._change_belongs_to_team_bot_ingress(_change(UNRELATED_ID)) is False


def test_missing_phone_number_id_is_not_team_bot() -> None:
    assert whatsapp_chat._change_belongs_to_team_bot_ingress(_change(None)) is False


def test_the_two_sets_never_overlap() -> None:
    """The mandate's hardest constraint: TEAM_BOT_PHONE_NUMBER_IDS must
    NEVER be merged into META_INBOX_PHONE_NUMBER_IDS. A regression here
    (e.g. someone "simplifying" by unioning the two sets) would silently
    resurrect the exact defect this lane fixes.
    """
    assert whatsapp_chat.TEAM_BOT_PHONE_NUMBER_IDS.isdisjoint(
        wa_outbox_worker.META_INBOX_PHONE_NUMBER_IDS
    )


def test_env_var_extends_team_bot_ids_without_losing_the_canonical_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mirrors META_INBOX_PHONE_NUMBER_IDS's own env-configurability
    contract (module reload required — the set is computed at import time).
    """
    import importlib

    monkeypatch.setenv("TEAM_BOT_PHONE_NUMBER_IDS", f"{UNRELATED_ID}, {UNRELATED_ID}")
    reloaded = importlib.reload(whatsapp_chat)
    try:
        assert reloaded.TEAM_BOT_PHONE_NUMBER_IDS == frozenset({TEAM_ID, UNRELATED_ID})
    finally:
        monkeypatch.delenv("TEAM_BOT_PHONE_NUMBER_IDS", raising=False)
        importlib.reload(whatsapp_chat)


# ---------------------------------------------------------------------------
# Regression: the 2026-08-25 double-reply defense (meta-inbox display-number
# fallback) is untouched by inserting the team-bot check ahead of it.
# ---------------------------------------------------------------------------


def test_double_reply_defense_still_catches_a_resubscribed_public_number() -> None:
    """Innocence: a second meta-inbox subscription (unlisted id, same
    visible public number) is still recognised as meta-inbox, NOT as
    team-bot — proving the new branch does not shadow or weaken the
    existing 2026-08-25 defense-in-depth.
    """
    change = _change(SECOND_META_INBOX_SUBSCRIPTION_ID, display_phone_number=PUBLIC_DISPLAY_NUMBER)
    assert whatsapp_chat._change_belongs_to_team_bot_ingress(change) is False
    assert whatsapp_chat._change_belongs_to_meta_inbox(change) is True


# ---------------------------------------------------------------------------
# _handle_team_bot_ingress_payload — the stub seam (no real handler yet)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stub_handler_logs_and_returns_without_raising() -> None:
    """B3's real ingress handler does not exist on this branch yet — this
    proves the seam itself is inert (no exception, no return value used
    downstream) so wiring it into the router cannot itself be a new crash
    surface.
    """
    result = await whatsapp_chat._handle_team_bot_ingress_payload(_change(TEAM_ID))
    assert result is None


# ---------------------------------------------------------------------------
# route_whatsapp_recovery — the SECOND call site (recovery net), same
# defect class: a payload that misses the fast path must not resurrect the
# bug via WebhookProcessor's retry/recovery dispatch.
# ---------------------------------------------------------------------------


def _recovery_payload(phone_number_id: str, wamid: str = "wamid.RECOVERY") -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "messages": [
                                {
                                    "id": wamid,
                                    "from": "628190000001",  # synthetic
                                    "type": "text",
                                    "text": {"body": "hello"},
                                    "timestamp": "1735689600",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_recovery_diverts_team_bot_payload_when_switch_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guilt: on recovery, a team-bot payload must reach neither
    legacy_route NOR process_meta_inbox_payload — only the ingress seam.
    """
    monkeypatch.setenv("TEAM_BOT_INGRESS_ENABLED", "true")
    handle_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(whatsapp_chat, "_handle_team_bot_ingress_payload", handle_mock)
    legacy_route = AsyncMock(
        side_effect=AssertionError("legacy_route must not run for team-bot payload")
    )
    process_meta_inbox_mock = AsyncMock(
        side_effect=AssertionError("meta-inbox pipeline must not run for team-bot payload")
    )
    monkeypatch.setattr(whatsapp_chat, "process_meta_inbox_payload", process_meta_inbox_mock)

    await whatsapp_chat.route_whatsapp_recovery(
        _recovery_payload(TEAM_ID), db_pool=MagicMock(), legacy_route=legacy_route
    )

    handle_mock.assert_awaited_once()
    legacy_route.assert_not_awaited()
    process_meta_inbox_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_drops_team_bot_payload_when_switch_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail-closed: switch OFF (the default) means recognised-and-dropped,
    never fallen through to legacy_route.
    """
    monkeypatch.delenv("TEAM_BOT_INGRESS_ENABLED", raising=False)
    handle_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(whatsapp_chat, "_handle_team_bot_ingress_payload", handle_mock)
    legacy_route = AsyncMock(
        side_effect=AssertionError("legacy_route must not run for team-bot payload")
    )

    await whatsapp_chat.route_whatsapp_recovery(
        _recovery_payload(TEAM_ID), db_pool=MagicMock(), legacy_route=legacy_route
    )

    handle_mock.assert_not_awaited()
    legacy_route.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_meta_inbox_payload_is_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Innocence regression: the pre-existing meta-inbox recovery branch
    (2026-08-25 scar) still works exactly as before the team-bot branch
    was added.
    """
    process_meta_inbox_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(whatsapp_chat, "process_meta_inbox_payload", process_meta_inbox_mock)
    legacy_route = AsyncMock(
        side_effect=AssertionError("legacy_route must not run for meta-inbox payload")
    )

    await whatsapp_chat.route_whatsapp_recovery(
        _recovery_payload(CLIENT_META_INBOX_ID), db_pool=MagicMock(), legacy_route=legacy_route
    )

    process_meta_inbox_mock.assert_awaited_once()
    legacy_route.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_unrelated_payload_still_goes_to_legacy_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Innocence regression: genuinely unrelated/public-client traffic is
    completely untouched by this lane, on the recovery path too.
    """
    legacy_route = AsyncMock(return_value=None)
    process_meta_inbox_mock = AsyncMock(
        side_effect=AssertionError("meta-inbox pipeline must not run for unrelated payload")
    )
    monkeypatch.setattr(whatsapp_chat, "process_meta_inbox_payload", process_meta_inbox_mock)

    payload = _recovery_payload(UNRELATED_ID)
    await whatsapp_chat.route_whatsapp_recovery(
        payload, db_pool=MagicMock(), legacy_route=legacy_route
    )

    legacy_route.assert_awaited_once_with(payload)
    process_meta_inbox_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# THE FAST PATH — added 2026-08-27, and it is the branch the defect lives in.
#
# The sibling branch shipped four recovery-path tests and none for
# ``whatsapp_webhook`` itself. But the recovery net only runs when the fast
# path already failed: the defect this lane cures — a staff message to the
# team number falling through into the legacy inline client-triage flow —
# reaches production through ``whatsapp_webhook``, every time, on the happy
# path. A suite that proves only the recovery branch proves the wrong half.
#
# Driven through ``TestClient`` like the router's own coverage suite, so the
# real FastAPI dispatch, the real change loop and the real branch ordering
# all run. The assertion is on the LEGACY SCHEDULER: with the team pnid it
# must never be scheduled; with an unrelated pnid it must be — that pair is
# the guilt/innocence of the divert, not the existence of a constant.
# ---------------------------------------------------------------------------

import json as _json  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.core.config import settings as _real_settings  # noqa: E402


def _webhook_payload(phone_number_id: str, display_phone_number: str = "15556151111") -> dict:
    """Minimal valid text-message webhook payload for ONE business number."""
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
                                "display_phone_number": display_phone_number,
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [
                                {"profile": {"name": "QA Synthetic"}, "wa_id": "620000000001"}
                            ],
                            "messages": [
                                {
                                    "from": "620000000001",
                                    "id": "wamid.QA-TEAM-INGRESS-1",
                                    "timestamp": "1712000000",
                                    "type": "text",
                                    "text": {"body": "[QA] synthetic ingress probe"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


@pytest.fixture
def _webhook_client():
    app = FastAPI()
    app.include_router(whatsapp_chat.router)
    with patch.object(_real_settings, "meta_webhook_require_signature", False):
        yield TestClient(app)


def _post(client: Any, payload: dict) -> Any:
    """POST the payload with the webhook's side effects neutralised.

    The meta-inbox task is stubbed so this test observes ONE thing: whether
    the legacy inline scheduler was reached. Webhook persistence is NOT
    stubbed — it resolves ``inbound_webhook_repo`` by local import inside the
    handler (no module attribute to patch) and already degrades without a
    pool, exactly as the router's own coverage suite relies on.
    """
    with (
        patch.object(whatsapp_chat, "process_meta_inbox_payload", new=AsyncMock(return_value=True)),
        patch.object(
            whatsapp_chat, "process_whatsapp_message_and_mark_processed", new=AsyncMock()
        ) as legacy,
        patch.object(whatsapp_chat, "_handle_team_bot_ingress_payload", new=AsyncMock()) as seam,
    ):
        response = client.post(
            "/webhook/whatsapp",
            content=_json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
    return response, legacy, seam


def test_fast_path_team_bot_message_never_reaches_the_legacy_client_flow(
    _webhook_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE GUILT TEST. On origin/main before this lane, a message to the
    team-bot number fell through both classification branches and was
    scheduled onto ``process_whatsapp_message_and_mark_processed`` — the
    client brain answering on the staff number. It must not.

    Asserted with the kill switch OFF (its born state), because that is the
    configuration production actually runs: the divert must hold even when
    nothing is armed to receive the traffic.
    """
    monkeypatch.delenv("TEAM_BOT_INGRESS_ENABLED", raising=False)
    response, legacy, seam = _post(_webhook_client, _webhook_payload(TEAM_ID))

    assert response.status_code == 200
    legacy.assert_not_called()
    seam.assert_not_called()  # switch off => recognised and dropped, not handed on


def test_fast_path_team_bot_message_reaches_the_seam_when_the_switch_is_on(
    _webhook_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Armed, the SAME payload goes to the ingress seam — and still never to
    the legacy client flow. Both halves matter: an arm that also leaked into
    the client path would be a worse defect than the one being cured.
    """
    monkeypatch.setenv("TEAM_BOT_INGRESS_ENABLED", "true")
    response, legacy, seam = _post(_webhook_client, _webhook_payload(TEAM_ID))

    assert response.status_code == 200
    legacy.assert_not_called()
    assert seam.call_count == 1


def test_fast_path_unrelated_number_still_reaches_the_legacy_flow(
    _webhook_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE INNOCENCE TEST, and the one that would catch an over-match: a
    genuinely unrelated business number must be routed exactly as before.
    Without this, a divert that swallowed everything would look green.
    """
    monkeypatch.delenv("TEAM_BOT_INGRESS_ENABLED", raising=False)
    response, legacy, seam = _post(_webhook_client, _webhook_payload(UNRELATED_ID))

    assert response.status_code == 200
    assert legacy.call_count == 1
    seam.assert_not_called()


def test_fast_path_the_public_client_number_still_goes_to_the_meta_inbox(
    _webhook_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Innocence for the paying surface: the client number keeps its own
    branch — neither diverted to the team seam nor dropped into the legacy
    inline flow (the 2026-08-25 double-reply scar's own invariant).
    """
    monkeypatch.delenv("TEAM_BOT_INGRESS_ENABLED", raising=False)
    response, legacy, seam = _post(
        _webhook_client, _webhook_payload(CLIENT_META_INBOX_ID, PUBLIC_DISPLAY_NUMBER)
    )

    assert response.status_code == 200
    legacy.assert_not_called()
    seam.assert_not_called()
