"""Guilt+innocence tests for the 2026-08-25 double-reply fix.

A "Ciaooo" inbound got two replies because the webhook router separated the
meta-inbox pipeline from a legacy inline branch on a single equality check
(``phone_number_id == META_INBOX_PHONE_NUMBER_ID``). A Meta webhook
re-registration armed a second subscription for the SAME visible business
number, delivered with a DIFFERENT phone_number_id — that id was not
recognised, so its messages fell through into the legacy branch, which
answered a message the meta-inbox pipeline (wa_outbox_worker) had already
answered.

Four independent defenses, each tested here:

1. ``META_INBOX_PHONE_NUMBER_IDS`` is a SET, not a single id — a second id
   can be listed via env without a code change.
2. ``_change_belongs_to_meta_inbox`` also matches on ``display_phone_number``
   — a same-number resubscribe is caught even if its id was never listed.
   The comparator normalizes BOTH sides to digits-only, so "+62 821 3465
   159" (config default), "628213465159" (Meta's typical wire format) and
   "62 821-3465-159" all compare equal.
3. Cross-path ATOMIC CLAIM (hardened 2026-08-25, migration 281): the original
   fix was a read-only SELECT against ``meta_inbox_messages``, which is racy
   — it can run before the meta-inbox pipeline's own write commits, so both
   paths can win the read and both reply. Replaced with a write-before-send
   UPSERT into a dedicated ``wa_reply_claims`` table, called from BOTH
   ``process_whatsapp_message`` (legacy) and ``_handle_meta_inbox_message``
   (meta-inbox): whichever path's INSERT lands first for a wamid wins and
   answers; the loser discards.
4. ``_claim_wamid_reply`` itself: a genuine two-writer race (simulated with a
   real in-memory dedup dict standing in for the DB's UNIQUE constraint) must
   resolve to exactly one winner, and a same-path retry (Meta re-delivering
   its own webhook) must re-affirm its own prior win rather than being read
   as a loss.
"""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.routers import whatsapp_chat
from backend.services.integrations import wa_outbox_worker

CANONICAL_ID = wa_outbox_worker.META_INBOX_PHONE_NUMBER_ID
SECOND_SUBSCRIPTION_ID = "2000000000000000"
UNRELATED_ID = "9999999999999"


def _change(phone_number_id: str | None, display_phone_number: str | None = None) -> Any:
    metadata: dict[str, Any] = {}
    if phone_number_id is not None:
        metadata["phone_number_id"] = phone_number_id
    if display_phone_number is not None:
        metadata["display_phone_number"] = display_phone_number
    return MagicMock(field="messages", value={"metadata": metadata})


# ---------------------------------------------------------------------------
# Defense 1: META_INBOX_PHONE_NUMBER_IDS is env-configurable
# ---------------------------------------------------------------------------


def test_default_set_contains_only_the_canonical_id() -> None:
    assert wa_outbox_worker.META_INBOX_PHONE_NUMBER_IDS == frozenset({CANONICAL_ID})


def test_env_var_adds_a_second_recognised_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "META_INBOX_PHONE_NUMBER_IDS", f"{SECOND_SUBSCRIPTION_ID}, {UNRELATED_ID}"
    )
    reloaded = importlib.reload(wa_outbox_worker)
    try:
        assert reloaded.META_INBOX_PHONE_NUMBER_IDS == frozenset(
            {CANONICAL_ID, SECOND_SUBSCRIPTION_ID, UNRELATED_ID}
        )
    finally:
        monkeypatch.delenv("META_INBOX_PHONE_NUMBER_IDS", raising=False)
        importlib.reload(wa_outbox_worker)


def test_env_var_unset_or_empty_still_yields_canonical_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("META_INBOX_PHONE_NUMBER_IDS", raising=False)
    reloaded = importlib.reload(wa_outbox_worker)
    assert reloaded.META_INBOX_PHONE_NUMBER_IDS == frozenset({CANONICAL_ID})

    monkeypatch.setenv("META_INBOX_PHONE_NUMBER_IDS", "  , ,")
    reloaded = importlib.reload(wa_outbox_worker)
    assert reloaded.META_INBOX_PHONE_NUMBER_IDS == frozenset({CANONICAL_ID})
    monkeypatch.delenv("META_INBOX_PHONE_NUMBER_IDS", raising=False)
    importlib.reload(wa_outbox_worker)


# ---------------------------------------------------------------------------
# Defense 2: _change_belongs_to_meta_inbox — id OR display_phone_number
# ---------------------------------------------------------------------------


def test_canonical_id_routes_to_meta_inbox_regression() -> None:
    """Guilt/innocence regression: the id that has always worked still works."""
    assert whatsapp_chat._change_belongs_to_meta_inbox(_change(CANONICAL_ID)) is True


def test_unrelated_id_and_unrelated_display_number_stays_legacy() -> None:
    """Innocence: a genuinely different number must NOT be swept into meta-inbox."""
    assert (
        whatsapp_chat._change_belongs_to_meta_inbox(
            _change(UNRELATED_ID, display_phone_number="15550001111")
        )
        is False
    )


def test_second_subscription_same_number_caught_via_display_phone_number() -> None:
    """Guilt: a NEW subscription id, same visible number, must not reach legacy.

    This is the exact defect: a phone_number_id that META_INBOX_PHONE_NUMBER_IDS
    does not (yet) list, but whose display_phone_number is the bot's public
    WhatsApp number ("+62 821 3465 159" in various Meta-delivered formats).
    """
    for formatted in ("628213465159", "+62 821-3465-159", "62 821 3465 159"):
        change = _change(SECOND_SUBSCRIPTION_ID, display_phone_number=formatted)
        assert whatsapp_chat._change_belongs_to_meta_inbox(change) is True, formatted


def test_missing_display_phone_number_does_not_crash_and_is_innocent() -> None:
    assert whatsapp_chat._is_meta_inbox_public_number(None) is False
    assert whatsapp_chat._is_meta_inbox_public_number("") is False


def test_second_subscription_id_added_via_env_also_recognised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        whatsapp_chat,
        "META_INBOX_PHONE_NUMBER_IDS",
        frozenset({CANONICAL_ID, SECOND_SUBSCRIPTION_ID}),
    )
    change = _change(SECOND_SUBSCRIPTION_ID)
    assert whatsapp_chat._change_belongs_to_meta_inbox(change) is True


# ---------------------------------------------------------------------------
# Defense 3: cross-path ATOMIC CLAIM at the top of process_whatsapp_message
# and _handle_meta_inbox_message
# ---------------------------------------------------------------------------


class _AcquireCM:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def __aenter__(self) -> Any:
        return self._conn

    async def __aexit__(self, *exc: Any) -> bool:
        return False


@pytest.mark.asyncio
async def test_wamid_already_claimed_by_meta_inbox_skips_legacy_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guilt: the exact double-reply shape — meta-inbox already claimed it."""
    conn = MagicMock()
    # The claim UPSERT returns the EXISTING owner on conflict: "meta_inbox"
    # (not "legacy"), so process_whatsapp_message's own claim call loses.
    conn.fetchval = AsyncMock(return_value=whatsapp_chat.WAMID_CLAIMANT_META_INBOX)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))

    request = MagicMock()
    monkeypatch.setattr(whatsapp_chat, "_get_db_pool", lambda r: pool)
    monkeypatch.setattr(
        whatsapp_chat.whatsapp_service, "mark_message_read", AsyncMock(return_value=None)
    )

    # The claim gate runs AFTER the allowlist check (self-review finding,
    # cured in this PR — claiming before the allowlist let a
    # will-be-ignored number still poison the wamid for a legitimate
    # later meta-inbox delivery), so is_allowed must return True to reach
    # it; the guard is on the NEXT stage (triage), which must never run.
    monkeypatch.setattr(whatsapp_chat.whatsapp_triage_service, "is_allowed", lambda *a, **k: True)
    monkeypatch.setattr(
        whatsapp_chat.whatsapp_triage_service,
        "should_escalate",
        AsyncMock(
            side_effect=AssertionError(
                "legacy triage must not run — the claim should have returned early"
            )
        ),
    )

    result = await whatsapp_chat.process_whatsapp_message(
        phone="628111",
        message_text="Ciaooo",
        sender_name="Mario",
        message_id="wamid.DOUBLE",
        request=request,
    )

    assert result is None
    assert conn.fetchval.await_args[0][1] == "wamid.DOUBLE"
    assert conn.fetchval.await_args[0][2] == whatsapp_chat.WAMID_CLAIMANT_LEGACY


@pytest.mark.asyncio
async def test_wamid_claimed_by_legacy_proceeds_to_legacy_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Innocence: a genuinely new legacy-only wamid must still be processed."""
    conn = MagicMock()
    # The UPSERT inserted a fresh row with claimed_by="legacy" — no conflict,
    # so the returned owner equals the caller's own claimant name.
    conn.fetchval = AsyncMock(return_value=whatsapp_chat.WAMID_CLAIMANT_LEGACY)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))

    request = MagicMock()
    monkeypatch.setattr(whatsapp_chat, "_get_db_pool", lambda r: pool)
    monkeypatch.setattr(
        whatsapp_chat.whatsapp_service, "mark_message_read", AsyncMock(return_value=None)
    )
    is_allowed_calls: list[str] = []
    monkeypatch.setattr(
        whatsapp_chat.whatsapp_triage_service,
        "is_allowed",
        # Must return True: the claim gate runs AFTER the allowlist check, so
        # this test needs to actually reach it, not stop here.
        lambda phone, *a, **k: is_allowed_calls.append(phone) or True,
    )
    # Stop the flow right after the claim gate — should_escalate is real
    # triage logic this test has no business exercising. The outer
    # try/except in process_whatsapp_message swallows this and returns
    # None, which is exactly the assertion below.
    should_escalate_mock = AsyncMock(
        side_effect=RuntimeError("stop here — claim gate already proven passed")
    )
    monkeypatch.setattr(
        whatsapp_chat.whatsapp_triage_service, "should_escalate", should_escalate_mock
    )

    result = await whatsapp_chat.process_whatsapp_message(
        phone="628111",
        message_text="hello",
        sender_name="Mario",
        message_id="wamid.LEGACY-ONLY",
        request=request,
    )

    # Reached the allowlist stage (which runs BEFORE the claim) and then
    # won the claim itself — proof neither gate early-returned.
    assert is_allowed_calls == ["628111"]
    assert conn.fetchval.await_args[0][1] == "wamid.LEGACY-ONLY"
    # The outer try/except returns None on ANY unhandled exception past this
    # point, so `result is None` alone does not prove the flow reached the
    # claim gate — a mutant that early-returns right after the allowlist
    # check (never touching should_escalate) also yields None here
    # (adversarial-review finding: mutation testing survived on this
    # assertion gap). Assert the sentinel was actually awaited so a mutant
    # that short-circuits before it goes red.
    should_escalate_mock.assert_awaited_once()
    assert result is None


@pytest.mark.asyncio
async def test_dedup_db_error_is_non_blocking(monkeypatch: pytest.MonkeyPatch) -> None:
    """A DB hiccup on the claim must never block a legitimate legacy reply."""
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=RuntimeError("db down"))

    request = MagicMock()
    monkeypatch.setattr(whatsapp_chat, "_get_db_pool", lambda r: pool)
    monkeypatch.setattr(
        whatsapp_chat.whatsapp_service, "mark_message_read", AsyncMock(return_value=None)
    )
    is_allowed_calls: list[str] = []
    monkeypatch.setattr(
        whatsapp_chat.whatsapp_triage_service,
        "is_allowed",
        # Must return True: the claim gate runs AFTER the allowlist check
        # (self-review finding, cured in this PR), so this test needs to
        # actually reach the claim's DB call — not stop at the allowlist,
        # which would make this "DB error is non-blocking" test pass
        # vacuously without ever touching pool.acquire.
        lambda phone, *a, **k: is_allowed_calls.append(phone) or True,
    )
    # Stop the flow right after the (failed) claim attempt — should_escalate
    # is real triage logic this test has no business exercising. The outer
    # try/except in process_whatsapp_message swallows this and returns None,
    # which is exactly the assertion below.
    should_escalate_mock = AsyncMock(
        side_effect=RuntimeError("stop here — claim gate already proven passed")
    )
    monkeypatch.setattr(
        whatsapp_chat.whatsapp_triage_service, "should_escalate", should_escalate_mock
    )

    # Must not raise despite the claim's DB call failing.
    result = await whatsapp_chat.process_whatsapp_message(
        phone="628111",
        message_text="hello",
        sender_name="Mario",
        message_id="wamid.DB-DOWN",
        request=request,
    )
    assert is_allowed_calls == ["628111"]
    assert pool.acquire.called
    # `result is None` alone is also produced by the swallowed RuntimeError
    # from pool.acquire itself (caught by the claim's own try/except) OR by
    # the outer try/except catching anything else — neither proves the flow
    # actually continued PAST the failed claim into triage, which is the
    # whole point of "non-blocking" (adversarial-review finding: mutation
    # testing survived here too, same gap as the sibling test above).
    # Assert the sentinel was awaited so a mutant that re-raises inside the
    # claim's except (muting instead of continuing) goes red.
    should_escalate_mock.assert_awaited_once()
    assert result is None


# ---------------------------------------------------------------------------
# Defense 3b: _handle_meta_inbox_message's own claim call (the other side of
# the race)
# ---------------------------------------------------------------------------


def _meta_inbox_msg(wamid: str = "wamid.RACE", phone: str = "628111") -> dict[str, Any]:
    return {
        "id": wamid,
        "from": phone,
        "type": "text",
        "text": {"body": "hello"},
        "timestamp": "1735689600",
    }


@pytest.mark.asyncio
async def test_meta_inbox_path_skips_when_legacy_already_claimed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guilt (the mirror case): legacy claimed first, meta-inbox must discard."""
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value=whatsapp_chat.WAMID_CLAIMANT_LEGACY)
    conn.fetchrow = AsyncMock(
        side_effect=AssertionError(
            "meta-inbox ledger writes must not run once the claim is lost"
        )
    )

    await whatsapp_chat._handle_meta_inbox_message(
        conn, _meta_inbox_msg(), sender_name="Mario", webhook_id=1
    )

    conn.fetchrow.assert_not_called()
    assert conn.fetchval.await_args[0][1] == "wamid.RACE"
    assert conn.fetchval.await_args[0][2] == whatsapp_chat.WAMID_CLAIMANT_META_INBOX


@pytest.mark.asyncio
async def test_meta_inbox_path_proceeds_when_it_wins_the_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Innocence: meta-inbox winning its own claim must proceed into the ledger."""
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value=whatsapp_chat.WAMID_CLAIMANT_META_INBOX)
    conn.transaction = MagicMock(return_value=_AcquireCM(None))
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"thread_id": 42, "human_handling": True},  # thread upsert
            None,  # inbound insert: ON CONFLICT DO NOTHING -> duplicate, no-op
        ]
    )

    await whatsapp_chat._handle_meta_inbox_message(
        conn, _meta_inbox_msg(wamid="wamid.WON"), sender_name="Mario", webhook_id=1
    )

    assert conn.fetchrow.await_count == 2  # let through past the claim gate


# ---------------------------------------------------------------------------
# Defense 4: _claim_wamid_reply — simulated two-writer race + same-path retry
# ---------------------------------------------------------------------------


class _FakeClaimTable:
    """Stands in for the DB's ``wa_reply_claims`` UNIQUE constraint on wamid.

    Mirrors the real UPSERT's semantics exactly: first writer for a wamid
    wins, its ``claimed_by`` is permanent, every later call (any claimant)
    reads that same value back — never its own new value.
    """

    def __init__(self) -> None:
        self._owners: dict[str, str] = {}

    async def fetchval(self, _sql: str, wamid: str, claimant: str) -> str:
        return self._owners.setdefault(wamid, claimant)


@pytest.mark.asyncio
async def test_claim_race_exactly_one_winner() -> None:
    """Two concurrent claimants on the SAME wamid: one wins, one loses."""
    table = _FakeClaimTable()

    meta_won = await whatsapp_chat._claim_wamid_reply(
        table, "wamid.RACE", whatsapp_chat.WAMID_CLAIMANT_META_INBOX
    )
    legacy_won = await whatsapp_chat._claim_wamid_reply(
        table, "wamid.RACE", whatsapp_chat.WAMID_CLAIMANT_LEGACY
    )

    assert meta_won is True
    assert legacy_won is False


@pytest.mark.asyncio
async def test_claim_same_path_retry_reaffirms_its_own_win() -> None:
    """A same-path retry (e.g. Meta re-delivering) must not read as a loss."""
    table = _FakeClaimTable()

    first = await whatsapp_chat._claim_wamid_reply(
        table, "wamid.RETRY", whatsapp_chat.WAMID_CLAIMANT_META_INBOX
    )
    retry = await whatsapp_chat._claim_wamid_reply(
        table, "wamid.RETRY", whatsapp_chat.WAMID_CLAIMANT_META_INBOX
    )

    assert first is True
    assert retry is True


# ---------------------------------------------------------------------------
# 3rd-pipeline scar (2026-08-25): the 30s recovery net re-routed meta-inbox
# messages through the retired ChannelRouter pipeline because
# process_meta_inbox_payload never marked the inbound_webhooks row
# processed. Two prongs tested below: (A) process_meta_inbox_payload now
# marks the row on success and NOT on handler failure, and (B) the
# WebhookProcessor's recovery dispatch keeps meta-inbox payloads off
# ChannelRouter entirely, as a second, independent line of defense.
#
# Round 2 (adversarial gate on PR #4894) found two defects in the recovery
# path itself, fixed and tested here too:
#   - process_meta_inbox_payload(mark_row=True) marking the SAME row that
#     WebhookProcessor._process_one already holds FOR UPDATE SKIP LOCKED in
#     an open transaction self-blocks against that transaction until
#     statement_timeout. route_whatsapp_recovery now passes mark_row=False.
#   - process_meta_inbox_payload previously swallowed every handler
#     exception unconditionally, so the WebhookProcessor's retry ladder
#     (backoff/MAX_ATTEMPTS/GIVING UP) never fired for meta-inbox rows — a
#     handler crash during recovery was silent, permanent message loss.
#     process_meta_inbox_payload now returns False on failure and
#     route_whatsapp_recovery re-raises so the processor's own retry
#     semantics apply.
# ---------------------------------------------------------------------------


def _webhook_payload(phone_number_id: str, wamid: str = "wamid.RECOVERY") -> dict[str, Any]:
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
                            "contacts": [{"profile": {"name": "Mario"}}],
                            "messages": [
                                {
                                    "id": wamid,
                                    "from": "628111",
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
async def test_meta_inbox_payload_marks_row_processed_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prong 1, innocence: a handled message closes its inbound_webhooks row."""
    conn = MagicMock()
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))

    handle_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(whatsapp_chat, "_handle_meta_inbox_message", handle_mock)
    monkeypatch.setattr(whatsapp_chat, "_resolve_webhook_id", AsyncMock(return_value=None))
    mark_processed_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "backend.services.channels.inbound_webhook_repo.mark_processed",
        mark_processed_mock,
    )

    result = await whatsapp_chat.process_meta_inbox_payload(
        _webhook_payload(CANONICAL_ID, wamid="wamid.MARKED"),
        request=None,
        db_pool=pool,
    )

    handle_mock.assert_awaited_once()
    mark_processed_mock.assert_awaited_once_with(
        pool, channel="whatsapp", dedup_key="wamid.MARKED"
    )
    assert result is True


@pytest.mark.asyncio
async def test_meta_inbox_payload_does_not_mark_row_on_handler_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prong 1, guilt: a handler crash must leave the row open for retry."""
    conn = MagicMock()
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))

    monkeypatch.setattr(
        whatsapp_chat,
        "_handle_meta_inbox_message",
        AsyncMock(side_effect=RuntimeError("handler exploded")),
    )
    monkeypatch.setattr(whatsapp_chat, "_resolve_webhook_id", AsyncMock(return_value=None))
    mark_processed_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "backend.services.channels.inbound_webhook_repo.mark_processed",
        mark_processed_mock,
    )

    # process_meta_inbox_payload swallows the handler exception internally
    # (existing "processing failed" catch-all) — must not raise here itself,
    # but must SIGNAL the failure via its return value (round-2 fix) so a
    # mark_row=False caller (route_whatsapp_recovery) can re-raise.
    result = await whatsapp_chat.process_meta_inbox_payload(
        _webhook_payload(CANONICAL_ID, wamid="wamid.UNMARKED"),
        request=None,
        db_pool=pool,
    )

    mark_processed_mock.assert_not_awaited()
    assert result is False


@pytest.mark.asyncio
async def test_recovery_net_routes_meta_inbox_payload_away_from_channel_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prong 2, guilt case avoided: meta-inbox payload never reaches ChannelRouter."""
    pool = MagicMock()
    process_meta_inbox_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(whatsapp_chat, "process_meta_inbox_payload", process_meta_inbox_mock)
    legacy_route_mock = AsyncMock(
        side_effect=AssertionError("ChannelRouter must not run for a meta-inbox payload")
    )

    payload = _webhook_payload(CANONICAL_ID, wamid="wamid.NET")
    await whatsapp_chat.route_whatsapp_recovery(
        payload, db_pool=pool, legacy_route=legacy_route_mock
    )

    # mark_row=False is load-bearing (round-2 finding): the WebhookProcessor
    # already holds this row FOR UPDATE SKIP LOCKED and marks it itself —
    # a mutant that drops mark_row=False (or flips it True) must go red here.
    process_meta_inbox_mock.assert_awaited_once_with(
        raw_payload=payload, request=None, db_pool=pool, mark_row=False
    )
    legacy_route_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_net_still_routes_non_meta_inbox_payload_through_channel_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prong 2, innocence (regression guard): unrelated numbers keep the old path."""
    pool = MagicMock()
    process_meta_inbox_mock = AsyncMock(
        side_effect=AssertionError("non-meta-inbox payload must not use process_meta_inbox_payload")
    )
    monkeypatch.setattr(whatsapp_chat, "process_meta_inbox_payload", process_meta_inbox_mock)
    legacy_route_mock = AsyncMock(return_value=None)

    payload = _webhook_payload(UNRELATED_ID, wamid="wamid.LEGACY-NET")
    await whatsapp_chat.route_whatsapp_recovery(
        payload, db_pool=pool, legacy_route=legacy_route_mock
    )

    legacy_route_mock.assert_awaited_once_with(payload)
    process_meta_inbox_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_entry_point_never_calls_mark_processed_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Round-2 finding 1, guilt case avoided: recovery never self-blocks on

    WebhookProcessor's own FOR UPDATE SKIP LOCKED transaction. Drives the
    REAL process_meta_inbox_payload (not mocked) through route_whatsapp_recovery
    end-to-end and proves inbound_webhook_repo.mark_processed is never
    awaited from that path — a mutant that reverts mark_row=False (or drops
    the mark_row guard inside process_meta_inbox_payload) must go red here.
    """
    conn = MagicMock()
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))

    monkeypatch.setattr(
        whatsapp_chat, "_handle_meta_inbox_message", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(whatsapp_chat, "_resolve_webhook_id", AsyncMock(return_value=None))
    mark_processed_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "backend.services.channels.inbound_webhook_repo.mark_processed",
        mark_processed_mock,
    )
    legacy_route_mock = AsyncMock(
        side_effect=AssertionError("ChannelRouter must not run for a meta-inbox payload")
    )

    payload = _webhook_payload(CANONICAL_ID, wamid="wamid.NO-SELF-MARK")
    await whatsapp_chat.route_whatsapp_recovery(
        payload, db_pool=pool, legacy_route=legacy_route_mock
    )

    mark_processed_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_reraises_on_handler_failure_so_processor_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Round-2 finding 2, guilt case avoided: a handler crash during recovery

    must propagate out of route_whatsapp_recovery (not be silently
    swallowed) so WebhookProcessor._process_one's retry ladder (backoff,
    MAX_ATTEMPTS, GIVING UP) applies — and the row must NOT be marked
    processed either, by the processor OR by this function.
    """
    conn = MagicMock()
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))

    monkeypatch.setattr(
        whatsapp_chat,
        "_handle_meta_inbox_message",
        AsyncMock(side_effect=RuntimeError("handler exploded during recovery")),
    )
    monkeypatch.setattr(whatsapp_chat, "_resolve_webhook_id", AsyncMock(return_value=None))
    mark_processed_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "backend.services.channels.inbound_webhook_repo.mark_processed",
        mark_processed_mock,
    )
    legacy_route_mock = AsyncMock(
        side_effect=AssertionError("ChannelRouter must not run for a meta-inbox payload")
    )

    payload = _webhook_payload(CANONICAL_ID, wamid="wamid.RETRY-ME")

    with pytest.raises(RuntimeError, match="process_meta_inbox_payload reported a"):
        await whatsapp_chat.route_whatsapp_recovery(
            payload, db_pool=pool, legacy_route=legacy_route_mock
        )

    mark_processed_mock.assert_not_awaited()
    legacy_route_mock.assert_not_awaited()
