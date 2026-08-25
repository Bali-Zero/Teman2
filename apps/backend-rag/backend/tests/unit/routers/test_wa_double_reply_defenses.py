"""Guilt+innocence tests for the 2026-08-25 double-reply fix.

A "Ciaooo" inbound got two replies because the webhook router separated the
meta-inbox pipeline from a legacy inline branch on a single equality check
(``phone_number_id == META_INBOX_PHONE_NUMBER_ID``). A Meta webhook
re-registration armed a second subscription for the SAME visible business
number, delivered with a DIFFERENT phone_number_id — that id was not
recognised, so its messages fell through into the legacy branch, which
answered a message the meta-inbox pipeline (wa_outbox_worker) had already
answered.

Three independent defenses, each tested here:

1. ``META_INBOX_PHONE_NUMBER_IDS`` is a SET, not a single id — a second id
   can be listed via env without a code change.
2. ``_change_belongs_to_meta_inbox`` also matches on ``display_phone_number``
   — a same-number resubscribe is caught even if its id was never listed.
3. Cross-path dedup in ``process_whatsapp_message``: a wamid already present
   in ``meta_inbox_messages`` (the meta-inbox pipeline's own ledger) must
   never be answered a second time by the legacy path.
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
# Defense 3: cross-path dedup at the top of process_whatsapp_message
# ---------------------------------------------------------------------------


class _AcquireCM:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def __aenter__(self) -> Any:
        return self._conn

    async def __aexit__(self, *exc: Any) -> bool:
        return False


@pytest.mark.asyncio
async def test_wamid_already_owned_by_meta_inbox_skips_legacy_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guilt: the exact double-reply shape — meta-inbox already answered."""
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value=1)  # row exists in meta_inbox_messages
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))

    request = MagicMock()
    monkeypatch.setattr(whatsapp_chat, "_get_db_pool", lambda r: pool)
    monkeypatch.setattr(
        whatsapp_chat.whatsapp_service, "mark_message_read", AsyncMock(return_value=None)
    )

    monkeypatch.setattr(
        whatsapp_chat.whatsapp_triage_service,
        "is_allowed",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("legacy triage must not run — dedup should have returned early")
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


@pytest.mark.asyncio
async def test_wamid_not_in_meta_inbox_ledger_proceeds_to_legacy_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Innocence: a genuinely new legacy-only wamid must still be processed."""
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value=None)  # no row — not owned by meta-inbox
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
        lambda phone, *a, **k: is_allowed_calls.append(phone) or False,
    )

    result = await whatsapp_chat.process_whatsapp_message(
        phone="628111",
        message_text="hello",
        sender_name="Mario",
        message_id="wamid.LEGACY-ONLY",
        request=request,
    )

    # The dedup check let it through to the allowlist stage — proof it did
    # not early-return at the dedup gate.
    assert is_allowed_calls == ["628111"]
    assert conn.fetchval.await_args[0][1] == "wamid.LEGACY-ONLY"
    assert result is None


@pytest.mark.asyncio
async def test_dedup_db_error_is_non_blocking(monkeypatch: pytest.MonkeyPatch) -> None:
    """A DB hiccup on the dedup check must never block a legitimate legacy reply."""
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
        lambda phone, *a, **k: is_allowed_calls.append(phone) or False,
    )

    # Must not raise despite the dedup check's DB call failing.
    result = await whatsapp_chat.process_whatsapp_message(
        phone="628111",
        message_text="hello",
        sender_name="Mario",
        message_id="wamid.DB-DOWN",
        request=request,
    )
    assert is_allowed_calls == ["628111"]
    assert result is None
