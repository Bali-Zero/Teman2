"""Tests for the WA outbox worker "manners" additions (spec items C3/C4):

  - C3: a best-effort concierge "checking…" ack fires once a bot reply starts
    generating.
  - C4: a best-effort apology fires once a row is permanently failed after
    exhausting retries.

Direct unit tests exercise ``_maybe_send_ack``/``_maybe_send_apology`` in
isolation (guilt: fires under the right conditions; innocence: skipped on
trivial text / closed window / kill-switch / already-sent / human takeover /
manners-flag-off). Integration tests drive the full ``process_outbox_once``
orchestration to prove the wiring point — that the real worker flow actually
reaches these hooks at the right moment, using the existing ScriptedConn/pool
fixtures from test_wa_outbox_worker.py.

Arming contract (gate review 2026-07-25, apology-side revised 2026-08-27):
``WA_OUTBOX_MANNERS_ENABLED`` gates the ACK ONLY and defaults to OFF in
production (unset today) — every test in this file except the dedicated
``test_ack_disabled_by_default_*`` tests explicitly ARMS it via the autouse
fixture, mirroring how a real canary rollout would set it before anything
in this file's ack "guilt" tests could fire for real. The APOLOGY has its
OWN dedicated flag as of the Gemini-cut PR (``WA_OUTBOX_TERMINAL_APOLOGY_ENABLED``,
DEFAULT **ON**, see ``test_apology_*_terminal_apology_flag_*`` /
``test_apology_still_sent_when_manners_flag_off``) — it no longer reads
``WA_OUTBOX_MANNERS_ENABLED`` at all.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.services import whatsapp_ack
from backend.services.integrations import wa_inbox_bot as _wa_inbox_bot_module
from backend.services.integrations import wa_outbox_worker
from backend.tests.unit.services.test_wa_outbox_worker import (
    ScriptedConn,
    _arm_codex,
    _candidate,
    _make_pool,
    _thread_row,
    _wa_service,
)


@pytest.fixture(autouse=True)
def _clean_ack_state(monkeypatch):
    """Every test gets a fresh should_send_ack throttle state, the
    pre-existing WHATSAPP_ACK_ENABLED kill-switch at ITS default (enabled —
    mirrors test_whatsapp_ack.py, untouched by this PR), and the NEW
    dedicated WA_OUTBOX_MANNERS_ENABLED flag explicitly ARMED — this file is
    specifically about exercising C3/C4 behavior, so tests opt IN to the
    real production default (off) only where that default is itself under
    test (see test_ack_disabled_by_default_flag_off). Also stubs
    ``notify_human_telegram`` (Telegram) to a deterministic AsyncMock — the
    real function raises cleanly with no token configured, but a test must
    never depend on THAT being true in every environment; individual tests
    override/inspect this mock via `monkeypatch` when they need to."""
    whatsapp_ack._reset_for_testing()
    monkeypatch.delenv("WHATSAPP_ACK_ENABLED", raising=False)
    monkeypatch.setenv("WA_OUTBOX_MANNERS_ENABLED", "true")
    monkeypatch.setattr(
        _wa_inbox_bot_module, "notify_human_telegram", AsyncMock(return_value=True)
    )
    yield
    whatsapp_ack._reset_for_testing()


_NON_TRIVIAL_TEXT = "How much does the 2-year investor KITAS cost and what documents do I need?"
_BAHASA_TEXT = "Berapa biaya perpanjangan KITAS investor dan dokumen apa saja yang dibutuhkan?"


def _open_window_thread(**overrides: Any) -> dict[str, Any]:
    thread = _thread_row(last_customer_at=datetime.now(timezone.utc) - timedelta(hours=1))
    thread.update(overrides)
    return thread


def _closed_window_thread(**overrides: Any) -> dict[str, Any]:
    thread = _thread_row(last_customer_at=datetime.now(timezone.utc) - timedelta(hours=25))
    thread.update(overrides)
    return thread


# ── _maybe_send_ack — direct unit tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_ack_sent_on_non_trivial_question_within_window() -> None:
    """Guilt: window open + non-trivial customer text + not-yet-acked row →
    the ack is claimed durably AND actually sent with the right phone/text."""
    thread = _open_window_thread()
    conn = ScriptedConn(
        fetchval_results=[_NON_TRIVIAL_TEXT],  # _latest_inbound_text
        fetchrow_results=[{"id": 1}],  # ack-claim UPDATE ... RETURNING id
    )
    svc = _wa_service()
    claim_token = uuid.uuid4()

    await wa_outbox_worker._maybe_send_ack(conn, 1, claim_token, thread, svc)

    svc.send_message.assert_awaited_once()
    kwargs = svc.send_message.await_args.kwargs
    assert kwargs["phone"] == "628111"
    assert kwargs["text"] == whatsapp_ack.ack_text("en")
    assert any(
        "ack_sent_at = NOW()" in s and a == (1, claim_token) for s, a in conn.executed
    )


@pytest.mark.asyncio
async def test_ack_localized_to_detected_language() -> None:
    thread = _open_window_thread()
    conn = ScriptedConn(
        fetchval_results=[_BAHASA_TEXT],
        fetchrow_results=[{"id": 1}],
    )
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_ack(conn, 1, uuid.uuid4(), thread, svc)

    assert svc.send_message.await_args.kwargs["text"] == whatsapp_ack.ack_text("id")


@pytest.mark.asyncio
async def test_ack_skipped_for_trivial_message() -> None:
    """Innocence: a greeting/short message never warrants a concierge ack —
    should_send_ack's own filter, reused as-is."""
    thread = _open_window_thread()
    conn = ScriptedConn(fetchval_results=["ok thanks!"])
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_ack(conn, 1, uuid.uuid4(), thread, svc)

    svc.send_message.assert_not_awaited()
    assert not conn.sql_contains("ack_sent_at")


@pytest.mark.asyncio
async def test_ack_skipped_when_window_closed() -> None:
    """Innocence: Meta 24h window closed → no ack (nothing sendable anyway).
    Short-circuits before even reading the latest inbound text."""
    thread = _closed_window_thread()
    conn = ScriptedConn()
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_ack(conn, 1, uuid.uuid4(), thread, svc)

    svc.send_message.assert_not_awaited()
    assert conn.executed == []  # never touched the DB at all


@pytest.mark.asyncio
async def test_ack_skipped_when_kill_switch_off(monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_ACK_ENABLED", "false")
    thread = _open_window_thread()
    conn = ScriptedConn()
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_ack(conn, 1, uuid.uuid4(), thread, svc)

    svc.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_ack_disabled_by_default_flag_off(monkeypatch) -> None:
    """Arming contract (gate review 2026-07-25): the dedicated
    WA_OUTBOX_MANNERS_ENABLED flag defaults OFF in production (unset today).
    With it unset — overriding this file's autouse arm-fixture back to the
    real prod default — neither a send NOR any DB write happens: the ack
    must short-circuit before ever touching ack_sent_at (which stays NULL
    because the claim UPDATE is never even issued)."""
    monkeypatch.delenv("WA_OUTBOX_MANNERS_ENABLED", raising=False)
    thread = _open_window_thread()
    conn = ScriptedConn(fetchval_results=[_NON_TRIVIAL_TEXT])
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_ack(conn, 1, uuid.uuid4(), thread, svc)

    svc.send_message.assert_not_awaited()
    assert conn.executed == []  # never touched the DB — not even a read
    assert not conn.sql_contains("ack_sent_at")


@pytest.mark.asyncio
async def test_ack_disabled_by_default_flag_explicit_false(monkeypatch) -> None:
    """Same contract, explicit 'false' value rather than unset — the two
    must behave identically (default-safe, not just absence-safe)."""
    monkeypatch.setenv("WA_OUTBOX_MANNERS_ENABLED", "false")
    thread = _open_window_thread()
    conn = ScriptedConn(fetchval_results=[_NON_TRIVIAL_TEXT])
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_ack(conn, 1, uuid.uuid4(), thread, svc)

    svc.send_message.assert_not_awaited()
    assert conn.executed == []


@pytest.mark.asyncio
async def test_ack_not_resent_when_already_claimed() -> None:
    """Idempotency (retry / crash-and-reclaim): the fenced UPDATE matches
    zero rows (ack_sent_at already set by a prior attempt on this SAME row)
    → must not send a second ack."""
    thread = _open_window_thread()
    conn = ScriptedConn(
        fetchval_results=[_NON_TRIVIAL_TEXT],
        fetchrow_results=[None],  # WHERE ack_sent_at IS NULL matched nothing
    )
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_ack(conn, 1, uuid.uuid4(), thread, svc)

    svc.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_ack_send_failure_never_raises() -> None:
    """A broken Graph call must not propagate — generation must proceed."""
    thread = _open_window_thread()
    conn = ScriptedConn(
        fetchval_results=[_NON_TRIVIAL_TEXT],
        fetchrow_results=[{"id": 1}],
    )
    svc = _wa_service(raise_exc=RuntimeError("graph down"))

    # Must not raise.
    await wa_outbox_worker._maybe_send_ack(conn, 1, uuid.uuid4(), thread, svc)

    svc.send_message.assert_awaited_once()


# ── _maybe_send_apology — direct unit tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_apology_sent_on_terminal_failure() -> None:
    """Guilt: window open, no human takeover, not-yet-apologized row → the
    apology is claimed durably AND actually sent."""
    thread = _open_window_thread()
    conn = ScriptedConn(
        fetchval_results=[False, _NON_TRIVIAL_TEXT],  # human_handling_now, latest inbound
        fetchrow_results=[{"id": 1}],  # apology-claim UPDATE ... RETURNING id
    )
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_apology(conn, 1, thread, svc)

    svc.send_message.assert_awaited_once()
    kwargs = svc.send_message.await_args.kwargs
    assert kwargs["phone"] == "628111"
    assert kwargs["text"] == wa_outbox_worker._apology_text("en")
    assert any("apology_sent_at = NOW()" in s and a == (1,) for s, a in conn.executed)


@pytest.mark.asyncio
async def test_apology_localized_to_detected_language() -> None:
    thread = _open_window_thread()
    conn = ScriptedConn(
        fetchval_results=[False, _BAHASA_TEXT],
        fetchrow_results=[{"id": 1}],
    )
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_apology(conn, 1, thread, svc)

    assert svc.send_message.await_args.kwargs["text"] == wa_outbox_worker._apology_text("id")


@pytest.mark.asyncio
async def test_apology_never_leaks_internal_error_text() -> None:
    """The apology text is a fixed neutral string — assert it never echoes
    exception content (the caller passes gen_exc/exc only to the internal
    ledger error column, never anywhere near this function)."""
    thread = _open_window_thread()
    conn = ScriptedConn(
        fetchval_results=[False, _NON_TRIVIAL_TEXT],
        fetchrow_results=[{"id": 1}],
    )
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_apology(conn, 1, thread, svc)

    sent_text = svc.send_message.await_args.kwargs["text"]
    for leak in ("Traceback", "asyncpg", "RuntimeError", "Exception"):
        assert leak not in sent_text


@pytest.mark.asyncio
async def test_apology_skipped_when_human_took_over() -> None:
    """Innocence, takeover-aware: a FRESH human_handling read (not the
    caller's possibly-stale value) gates the apology — if a human now owns
    the thread, they are already the one following up."""
    thread = _open_window_thread()
    conn = ScriptedConn(fetchval_results=[True])  # human_handling_now = True
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_apology(conn, 1, thread, svc)

    svc.send_message.assert_not_awaited()
    assert not conn.sql_contains("apology_sent_at")


@pytest.mark.asyncio
async def test_apology_skipped_when_window_closed() -> None:
    thread = _closed_window_thread()
    conn = ScriptedConn()
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_apology(conn, 1, thread, svc)

    svc.send_message.assert_not_awaited()
    assert conn.executed == []


@pytest.mark.asyncio
async def test_apology_still_sent_when_manners_flag_off(monkeypatch) -> None:
    """INNOCENCE, contract-reversed 2026-08-27: the apology's OWN flag
    (WA_OUTBOX_TERMINAL_APOLOGY_ENABLED) defaults ON and is fully decoupled
    from the ack's WA_OUTBOX_MANNERS_ENABLED — with the latter unset (the
    real prod default for the ack), the apology must still send. This
    replaces the pre-cut test of the same shape, which asserted the
    opposite under the OLD single-flag contract."""
    monkeypatch.delenv("WA_OUTBOX_MANNERS_ENABLED", raising=False)
    thread = _open_window_thread()
    conn = ScriptedConn(
        fetchval_results=[False, _NON_TRIVIAL_TEXT],
        fetchrow_results=[{"id": 1}],  # apology-claim UPDATE ... RETURNING id
    )
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_apology(conn, 1, thread, svc)

    svc.send_message.assert_awaited_once()
    assert conn.sql_contains("apology_sent_at = NOW()")


@pytest.mark.asyncio
async def test_apology_disabled_when_terminal_apology_flag_off(monkeypatch) -> None:
    """GUILT, the NEW dedicated kill-switch: with
    WA_OUTBOX_TERMINAL_APOLOGY_ENABLED=false, no send and no DB write —
    the one escape hatch this PR leaves for emergencies."""
    monkeypatch.setenv("WA_OUTBOX_TERMINAL_APOLOGY_ENABLED", "false")
    thread = _open_window_thread()
    conn = ScriptedConn(fetchval_results=[False, _NON_TRIVIAL_TEXT])
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_apology(conn, 1, thread, svc)

    svc.send_message.assert_not_awaited()
    assert conn.executed == []
    assert not conn.sql_contains("apology_sent_at")


@pytest.mark.asyncio
async def test_apology_tells_a_human_on_the_way_out(monkeypatch) -> None:
    """GUILT: the apology's promise ("flagged for our team") must be made
    TRUE — `_tell_a_human` (Telegram) fires with the right phone/reason,
    exactly once per row, before the client-facing send."""
    notify_spy = AsyncMock(return_value=True)
    monkeypatch.setattr(_wa_inbox_bot_module, "notify_human_telegram", notify_spy)
    thread = _open_window_thread()
    conn = ScriptedConn(
        fetchval_results=[False, _NON_TRIVIAL_TEXT],
        fetchrow_results=[{"id": 1}],
    )
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_apology(
        conn, 1, thread, svc, reason="bot_generation_exhausted"
    )

    notify_spy.assert_awaited_once()
    kwargs = notify_spy.await_args.kwargs
    assert kwargs["phone"] == "628111"
    assert kwargs["thread_ref"] == "7"
    assert "bot_generation_exhausted" in kwargs["reason"]


@pytest.mark.asyncio
async def test_apology_text_flags_never_promises_a_timed_reply() -> None:
    """The apology's old copy promised "a member of our team will follow up
    ... shortly" while nothing told a human anything — corrected 2026-08-27.
    The new copy must say the conversation was flagged, and must NOT promise
    a timed reply (per human_escalation_notifier's own docstring: Telegram
    acceptance proves nothing about a person acting on it)."""
    for lang in ("en", "id", "it", "ru", "uk"):
        text = wa_outbox_worker._apology_text(lang)
        assert "shortly" not in text.lower()


@pytest.mark.asyncio
async def test_apology_not_resent_when_already_claimed() -> None:
    """Idempotency: never two apologies for one row."""
    thread = _open_window_thread()
    conn = ScriptedConn(
        fetchval_results=[False, _NON_TRIVIAL_TEXT],
        fetchrow_results=[None],  # WHERE apology_sent_at IS NULL matched nothing
    )
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_apology(conn, 1, thread, svc)

    svc.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_apology_send_failure_never_raises_and_never_masks_original() -> None:
    thread = _open_window_thread()
    conn = ScriptedConn(
        fetchval_results=[False, _NON_TRIVIAL_TEXT],
        fetchrow_results=[{"id": 1}],
    )
    svc = _wa_service(raise_exc=RuntimeError("graph down"))

    # Must not raise — the caller has already recorded the real failure by
    # the time this is invoked.
    await wa_outbox_worker._maybe_send_apology(conn, 1, thread, svc)

    svc.send_message.assert_awaited_once()


# ── Wiring: prove process_outbox_once reaches these hooks at the right time ─


@pytest.mark.asyncio
async def test_ack_fires_during_real_generation_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: a bot-reply row that survives claim+coalescing gets an
    ack right as it starts generating, THEN the real reply is sent — TWO
    distinct send_message calls, ack first. Gemini cut: generation runs
    through the codex leg (mocked)."""
    _arm_codex(monkeypatch, text="the real generated reply")
    candidate = _candidate(10, thread_id=7, message_id=1000, needs_generation=True)
    open_thread = _open_window_thread(thread_id=7)
    conn = ScriptedConn(
        fetchrow_results=[
            open_thread,  # thread load
            {"id": 10},  # generating-transition fenced RETURNING
            {"id": 10},  # ack-claim UPDATE RETURNING id
            {"id": 10},  # pre-send fence RETURNING
            {"id": 10},  # final commit RETURNING
            None,  # no staged receipt
        ],
        fetchval_results=[
            True,  # advisory lock
            _NON_TRIVIAL_TEXT,  # _latest_inbound_text for the ack
            False,  # human_handling re-read at pre-send (no takeover)
            True,  # window_open (SQL check, step 6)
        ],
        fetch_results=[
            [candidate],  # candidate scan
            [],  # coalesce sweep — nothing else pending
        ],
    )
    pool = _make_pool(conn)
    svc = _wa_service(send_result={"messages": [{"id": "wamid.REPLY.1"}]})

    async def _bot_gen(_thread: Any) -> str:
        return "the real generated reply"

    result = await wa_outbox_worker.process_outbox_once(pool, svc, _bot_gen)

    assert result == "sent"
    assert svc.send_message.await_count == 2
    first_call, second_call = svc.send_message.await_args_list
    assert first_call.kwargs["text"] == whatsapp_ack.ack_text("en")
    assert second_call.kwargs["text"] == "the real generated reply"
    assert conn.sql_contains("ack_sent_at = NOW()")


@pytest.mark.asyncio
async def test_apology_fires_after_bot_generation_exhausts_retries() -> None:
    """End-to-end: bot generation fails permanently → the ledger records the
    real failure AND a best-effort apology goes out — never a real reply."""
    candidate = _candidate(
        20,
        thread_id=7,
        message_id=2000,
        needs_generation=True,
        attempts=wa_outbox_worker.MAX_ATTEMPTS - 1,
    )
    open_thread = _open_window_thread(thread_id=7)
    conn = ScriptedConn(
        fetchrow_results=[
            open_thread,  # thread load
            {"id": 20},  # generating-transition fenced RETURNING
            # (no entry for the ack-claim UPDATE: should_send_ack("hi", ...)
            # returns False — too short — so _maybe_send_ack short-circuits
            # BEFORE ever calling conn.fetchrow, consuming zero fetchrow slots)
            {"id": 20},  # terminal gen-failure fenced RETURNING
            {"id": 20},  # apology-claim UPDATE RETURNING id
        ],
        fetchval_results=[
            True,  # advisory lock
            "hi",  # _latest_inbound_text for the ack → trivial, ack skipped
            False,  # human_handling_now (apology takeover check)
            _NON_TRIVIAL_TEXT,  # _latest_inbound_text for the apology
        ],
        fetch_results=[[candidate], []],
    )
    pool = _make_pool(conn)
    svc = _wa_service()

    async def _bot_raises(_thread: Any) -> str:
        raise RuntimeError("RAG unreachable")

    result = await wa_outbox_worker.process_outbox_once(pool, svc, _bot_raises)

    assert result == "failed"
    svc.send_message.assert_awaited_once()  # apology only, never a real reply
    assert svc.send_message.await_args.kwargs["text"] == wa_outbox_worker._apology_text("en")
    assert conn.sql_contains("apology_sent_at = NOW()")
