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
    apology is claimed durably (AFTER a successful send, 2026-08-27 finding
    minore) AND actually sent."""
    thread = _open_window_thread()
    conn = ScriptedConn(
        # human_handling_now, apology_sent_at read (None = not yet), latest inbound
        fetchval_results=[False, None, _NON_TRIVIAL_TEXT],
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
    conn = ScriptedConn(fetchval_results=[False, None, _BAHASA_TEXT])
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_apology(conn, 1, thread, svc)

    assert svc.send_message.await_args.kwargs["text"] == wa_outbox_worker._apology_text("id")


@pytest.mark.asyncio
async def test_apology_never_leaks_internal_error_text() -> None:
    """The apology text is a fixed neutral string — assert it never echoes
    exception content (the caller passes gen_exc/exc only to the internal
    ledger error column, never anywhere near this function)."""
    thread = _open_window_thread()
    conn = ScriptedConn(fetchval_results=[False, None, _NON_TRIVIAL_TEXT])
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
async def test_apology_skipped_when_window_closed_but_a_human_is_still_told(
    monkeypatch,
) -> None:
    """GUILT (2026-08-27 Kimi K3 adversarial finding, MAGGIORE): the Meta
    24h window gates the CLIENT-facing send only. A row that sat unanswered
    long enough to exhaust retries AND close the window is exactly the case
    a human is needed most — the previous ordering put `_tell_a_human`
    AFTER the window check, so this exact case got no client apology
    (unavoidable) AND no human alert (avoidable). `_tell_a_human` must
    still fire even though nothing can be sent to the client."""
    notify_spy = AsyncMock(return_value=True)
    monkeypatch.setattr(_wa_inbox_bot_module, "notify_human_telegram", notify_spy)
    thread = _closed_window_thread()
    conn = ScriptedConn(fetchval_results=[False])  # human_handling_now only
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_apology(conn, 1, thread, svc)

    svc.send_message.assert_not_awaited()  # window closed — nothing sendable
    notify_spy.assert_awaited_once()  # but a human WAS told, unconditionally
    assert not conn.sql_contains("apology_sent_at")


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
    conn = ScriptedConn(fetchval_results=[False, None, _NON_TRIVIAL_TEXT])
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
    # fetchval_results is never consumed: the flag check is the function's
    # FIRST statement, before any conn call.
    conn = ScriptedConn(fetchval_results=[False, None, _NON_TRIVIAL_TEXT])
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
    conn = ScriptedConn(fetchval_results=[False, None, _NON_TRIVIAL_TEXT])
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_apology(
        conn, 1, thread, svc, reason="bot_generation_exhausted"
    )

    notify_spy.assert_awaited_once()
    kwargs = notify_spy.await_args.kwargs
    assert kwargs["phone"] == "628111"
    assert kwargs["thread_ref"] == "7"
    assert "bot_generation_exhausted" in kwargs["reason"]


# Real per-language timed-reply promise words/phrases — the actual
# regression surface (2026-08-27 Kimi K3 adversarial review, coordinator-
# weighted MAGGIORE): the first correction only REWORDED the promise
# ("someone will get back to you as soon as they can" / "akan segera
# ditindaklanjuti" / "che ti risponderà appena possibile" / "как только
# смогут" / "щойно зможуть") while a same-day test only ever checked the
# English word "shortly" — a check that could never fail against the other
# four languages no matter what they said.
_APOLOGY_PROMISE_WORDS: dict[str, tuple[str, ...]] = {
    "en": ("shortly", "soon", "as soon as"),
    "id": ("segera", "secepatnya", "sesegera mungkin"),
    "it": ("appena possibile", "presto", "a breve", "quanto prima"),
    "ru": ("как только смогут", "скоро", "в ближайшее время"),
    "uk": ("щойно зможуть", "скоро", "найближчим часом"),
}


@pytest.mark.asyncio
async def test_apology_texts_never_promise_a_timed_reply() -> None:
    """The apology's copy must say the conversation was flagged, and must
    NOT promise a timed reply in ANY of the 5 languages (per
    human_escalation_notifier's own docstring: Telegram acceptance proves
    nothing about a person acting on it, let alone on a timescale nobody
    can guarantee). Derived from a real per-language promise-word list —
    see `test_apology_promise_word_regex_catches_a_reinserted_promise` for
    the mutation proof that this actually fails when it should."""
    for lang, promise_words in _APOLOGY_PROMISE_WORDS.items():
        text = wa_outbox_worker._apology_text(lang).lower()
        for word in promise_words:
            assert word not in text, (
                f"{lang!r} apology text still promises a timed reply via {word!r}: {text!r}"
            )


@pytest.mark.asyncio
async def test_apology_not_resent_when_already_claimed() -> None:
    """Idempotency: never two apologies for one row — a non-NULL
    ``apology_sent_at`` read (a prior attempt already succeeded) skips the
    send entirely, before any further conn calls."""
    thread = _open_window_thread()
    conn = ScriptedConn(
        # human_handling_now, apology_sent_at (non-None = already sent)
        fetchval_results=[False, "2026-08-20T10:00:00+00:00"],
    )
    svc = _wa_service()

    await wa_outbox_worker._maybe_send_apology(conn, 1, thread, svc)

    svc.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_apology_send_failure_never_raises_and_never_masks_original() -> None:
    """GUILT (2026-08-27 Kimi K3 adversarial finding, minore): the durable
    claim happens AFTER a successful send, never before — a failed send
    must leave the row eligible for a future apology attempt, not
    permanently suppressed by a flag that was set before the send even ran."""
    thread = _open_window_thread()
    conn = ScriptedConn(fetchval_results=[False, None, _NON_TRIVIAL_TEXT])
    svc = _wa_service(raise_exc=RuntimeError("graph down"))

    # Must not raise — the caller has already recorded the real failure by
    # the time this is invoked.
    await wa_outbox_worker._maybe_send_apology(conn, 1, thread, svc)

    svc.send_message.assert_awaited_once()
    # The durable claim must NEVER have been written on a failed send.
    assert not conn.sql_contains("apology_sent_at = NOW()")


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
    """End-to-end: WA_GENERATION_PROVIDER is NOT armed codex in this test
    (``_arm_codex`` deliberately not called) → generation raises a plain
    ``BotStandingCondition`` (``provider_not_codex``), not a
    ``SilentStandingCondition`` — per the 2026-08-27 finding (BLOCCANTE)
    this ONE standing-condition reason DOES deserve the apology, unlike
    ``autoreply_disabled``/``no_customer_message`` (see
    ``test_wa_outbox_worker.py``'s silence tests for those). ``_bot_raises``
    is passed only for the (unused, back-compat-only) ``bot_generate_fn``
    signature slot — it is never actually invoked post-Gemini-cut. The
    ledger records the standing condition AND a best-effort apology goes
    out — never a real reply."""
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
        ],
        fetchval_results=[
            True,  # advisory lock
            "hi",  # _latest_inbound_text for the ack → trivial, ack skipped
            False,  # human_handling_now (apology takeover check)
            None,  # apology_sent_at read (not yet sent)
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


def _terminal_conn_open_window(outbox_id: int) -> ScriptedConn:
    """Same shape as ``test_wa_outbox_worker._terminal_conn`` (needs_generation
    row already at MAX_ATTEMPTS-1, terminal this attempt) but with an OPEN
    Meta window and an inbound message present — deliberately NOT the
    closed-window default: a closed window makes ``_maybe_send_apology``
    return before ever reaching the client-send or (pre-2026-08-27-finding-2)
    even the Telegram call, which would make a silence assertion pass
    whether or not the silence GUARD itself works. This fixture supplies
    every fetchval slot the WORST case (guard removed, apology runs to
    completion) would consume, so a mutation that removes the guard is
    actually caught rather than masked by an unrelated early-return."""
    candidate = _candidate(
        outbox_id,
        thread_id=7,
        message_id=outbox_id * 100,
        needs_generation=True,
        attempts=wa_outbox_worker.MAX_ATTEMPTS - 1,
    )
    open_thread = _open_window_thread(thread_id=7)
    return ScriptedConn(
        fetchrow_results=[
            open_thread,  # thread load
            {"id": outbox_id},  # generating-transition fenced RETURNING
            {"id": outbox_id},  # terminal-failure fenced RETURNING
        ],
        fetchval_results=[
            True,  # advisory lock
            "hi",  # _latest_inbound_text for the ack → trivial, ack skipped
            # The next 3 are consumed ONLY if the silence guard is broken
            # and _maybe_send_apology runs to completion:
            False,  # human_handling_now (apology takeover check)
            None,  # apology_sent_at read (not yet sent)
            _NON_TRIVIAL_TEXT,  # _latest_inbound_text for the apology
        ],
        fetch_results=[[candidate], []],
    )


@pytest.mark.asyncio
async def test_silent_standing_conditions_get_no_apology_and_no_telegram(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GUILT (2026-08-27 Kimi K3 adversarial review, coordinator-weighted
    BLOCCANTE): switch off (``autoreply_disabled``) or no customer message
    in the loaded window (``no_customer_message``), WITH an inbound message
    present on the thread AND an open Meta window (so a broken guard would
    have every opportunity to actually fire) — the row still exhausts
    retries, but NEITHER the client apology NOR the Telegram human alert may
    fire for either reason. These two mirror ``generate_bot_reply``'s own
    two silent exits, which by pre-existing, documented contract
    (``_tell_a_human``'s own docstring) notify nobody — the first draft of
    the Gemini-cut PR inverted that contract by firing the apology for
    EVERY standing condition, including these two."""
    notify_spy = AsyncMock(return_value=True)
    monkeypatch.setattr(_wa_inbox_bot_module, "notify_human_telegram", notify_spy)

    for reason in ("autoreply_disabled", "no_customer_message"):
        monkeypatch.setenv("WA_GENERATION_PROVIDER", "codex")
        monkeypatch.setattr(
            wa_outbox_worker.wa_codex_leg,
            "attempt",
            AsyncMock(
                return_value=wa_outbox_worker.wa_codex_leg.CodexLegResult(
                    reason=reason
                )
            ),
        )
        gemini_spy = AsyncMock(return_value="gemini reply")
        conn = _terminal_conn_open_window(84 if reason == "autoreply_disabled" else 85)
        pool = _make_pool(conn)
        svc = _wa_service()

        result = await wa_outbox_worker.process_outbox_once(pool, svc, gemini_spy)

        assert result == "failed", reason
        errors = [str(a) for _, a in conn.executed]
        assert any("bot_standing_condition_after_" in e for e in errors), reason
        svc.send_message.assert_not_awaited()
        notify_spy.assert_not_awaited()
        notify_spy.reset_mock()
