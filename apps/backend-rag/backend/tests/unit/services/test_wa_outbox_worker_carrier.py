"""Isolated-DB tests for the B2.3b carrier + fenced terminal write.

research/operations/2026-09-11-bot-staff-room/B2-engine.md §4 PR B2.3b and
~/.organism/b2-3b-design.md: ``CodexLegResult`` carries the sealed evidence
label, its normalised score and the opaque package reference from
``wa_codex_leg.py``'s parsed sealed wire into ``wa_outbox_worker.py``'s
terminal ``done`` write (``abstained_at``/``evidence_score``, migration 314).
``served_by`` (migration 322) rides the SAME fenced write — it is the
`CodexLegResult.served_by` value verbatim, the durable answer to "which
route served this row" (`docs/zantara-loop-state.md`'s support_abstain
rate gap).

Deliberately a SEPARATE module from ``test_wa_outbox_worker.py`` (which uses
a fully mocked ``ScriptedConn`` and asserts on SQL text) — these tests need
the fenced UPDATE to actually run against real Postgres so a claim-token
mismatch, a NUMERIC cast or a boolean CASE really proves what it claims to.
Fixture pattern copied from ``backend/tests/app/routers/conftest.py``
(``db_pool``): ``TEST_DATABASE_URL`` env var, default
``postgresql://nuzantara@localhost:5432/nuzantara_test`` — same DSN shape
CI's ``postgres:15`` service uses (``.github/workflows/tests.yml``). Skips
cleanly (does not fail) when the DB is unreachable or lacks
``wa_outbox``/``meta_inbox_threads``/``meta_inbox_messages`` or migration
314's two columns or migration 322's ``served_by``, matching that same
conftest's documented convention.

``wa_codex_leg.attempt`` is stubbed per case (never the real broker/RAG
call — no network, no generation, no send beyond the stubbed
``whatsapp_service``). All phone numbers and message bodies are synthetic.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from backend.services.integrations import wa_codex_leg, wa_outbox_worker
from backend.services.integrations.wa_outbox_worker import process_outbox_once

_DEFAULT_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
)

_REQUIRED_TABLES = ("wa_outbox", "meta_inbox_threads", "meta_inbox_messages")
_REQUIRED_COLUMNS = (
    ("wa_outbox", "abstained_at"),
    ("wa_outbox", "evidence_score"),
    ("wa_outbox", "served_by"),
)


@pytest_asyncio.fixture(scope="function")
async def db_pool() -> asyncpg.Pool:
    try:
        pool = await asyncpg.create_pool(_DEFAULT_DB_URL, min_size=1, max_size=5)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"wa_outbox_worker carrier tests: DB unreachable ({exc})")
        return  # help static analyzers see pool is unbound on this path

    skip_reason: str | None = None
    try:
        async with pool.acquire() as conn:
            for table in _REQUIRED_TABLES:
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=$1)",
                    table,
                )
                if not exists:
                    skip_reason = (
                        f"wa_outbox_worker carrier tests: required table "
                        f"'{table}' missing (run migrations against the test "
                        "DB to enable)"
                    )
                    break
            if skip_reason is None:
                for table, column in _REQUIRED_COLUMNS:
                    exists = await conn.fetchval(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name=$1 "
                        "AND column_name=$2)",
                        table,
                        column,
                    )
                    if not exists:
                        skip_reason = (
                            f"wa_outbox_worker carrier tests: {table}.{column} "
                            "missing (migration 314 or 322 not applied to the test DB)"
                        )
                        break
        if skip_reason is None:
            yield pool
    finally:
        await pool.close()
    if skip_reason:
        pytest.skip(skip_reason)


@pytest_asyncio.fixture(autouse=True)
async def _clean_slate(db_pool: asyncpg.Pool) -> None:
    """Truncate before every test in this module.

    ``process_outbox_once`` claims WHICHEVER due row sorts first
    system-wide (``ORDER BY next_retry_at, id ... FOR UPDATE SKIP LOCKED``)
    — a leftover 'pending' row from an EARLIER test in this same module
    (e.g. the retry case's requeued row, due again once its 30s backoff
    has actually elapsed in wall-clock time between runs) can otherwise
    get claimed instead of the row the CURRENT test just seeded, which
    reads as a flaky, unrelated-looking assertion failure two tests later.

    Safe against ``nuzantara_test`` (the dedicated disposable test DB —
    see this repo's root ``backend/tests/conftest.py``, which refuses to
    run at all against the real ``nuzantara_dev``): under pytest-xdist
    each worker clones its OWN database (``backend/tests/conftest.py``'s
    per-worker template mechanism), so this never touches another
    worker's rows; without xdist, pytest runs one file to completion
    before starting the next, so this never runs interleaved with another
    module's real-DB tests either. CASCADE also clears ``broker_jobs``
    (FK to ``wa_outbox``) and ``wa_status_pending`` — neither is written
    by any test here.
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE TABLE wa_outbox, meta_inbox_messages, meta_inbox_threads "
            "RESTART IDENTITY CASCADE"
        )


@pytest.fixture(autouse=True)
def _no_terminal_apology(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never let a terminal-failure case reach ``_tell_a_human`` (Telegram —
    a real network call). Default-ON in prod; every test here is about the
    carrier write, not the apology feature."""
    monkeypatch.setenv("WA_OUTBOX_TERMINAL_APOLOGY_ENABLED", "false")


@pytest.fixture(autouse=True)
def _codex_provider_armed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass the ``WA_GENERATION_PROVIDER`` env gate so every case reaches
    the (stubbed) codex leg instead of the ``provider_not_codex`` standing
    condition."""
    monkeypatch.setattr(wa_codex_leg, "provider_is_codex", lambda: True)


async def _never_bot_gen(_thread: Any) -> str:
    raise AssertionError(
        "bot_generate_fn (Gemini back-compat shape) must never be invoked "
        "post Gemini-cut — the codex leg is the only generation path"
    )


class _StubWhatsApp:
    """Stub ``whatsapp_service`` — records every call, and can raise or run
    an async side effect (to model a race landing during the Graph call)
    before answering."""

    def __init__(
        self,
        *,
        raises: Exception | None = None,
        side_effect: Callable[[], Any] | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._raises = raises
        self._side_effect = side_effect

    async def send_message(
        self, *, phone: str, text: str, reply_to_message_id: str | None = None
    ) -> dict[str, Any]:
        self.calls.append({"phone": phone, "text": text})
        if self._side_effect is not None:
            await self._side_effect()
        if self._raises is not None:
            raise self._raises
        return {"messages": [{"id": f"wamid.synthetic.{uuid.uuid4().hex[:8]}"}]}


def _codex_leg_stub(
    results: list[wa_codex_leg.CodexLegResult],
    *,
    side_effect: Callable[..., Any] | None = None,
):
    """Replaces ``wa_codex_leg.attempt``. Returns ``results`` in call order
    (the last entry repeats past the end); ``side_effect(thread_id=...)`` —
    if given — runs BEFORE the result is returned, e.g. to flip
    ``human_handling`` mid-"generation" (the takeover case)."""

    call_count = {"n": 0}

    async def _stub(
        pool: asyncpg.Pool,
        *,
        outbox_id: int,
        thread_id: int,
        message_id: int,
        claim_token: uuid.UUID,
        outbox_expected_status: str,
        thread: Any,
    ) -> wa_codex_leg.CodexLegResult:
        idx = min(call_count["n"], len(results) - 1)
        call_count["n"] += 1
        if side_effect is not None:
            await side_effect(pool=pool, thread_id=thread_id, outbox_id=outbox_id)
        return results[idx]

    return _stub


async def _seed_row(
    pool: asyncpg.Pool,
    *,
    human_handling: bool = False,
    attempts: int = 0,
    body: str = "synthetic inbound test message",
) -> dict[str, Any]:
    """Insert one fresh thread + inbound message + pending bot-reply
    ``wa_outbox`` row. Synthetic phone (unique per row — ``counterpart_phone``
    is UNIQUE), no real client data."""
    phone = f"+000000{uuid.uuid4().int % 10**7:07d}"
    async with pool.acquire() as conn:
        thread_id = await conn.fetchval(
            """
            INSERT INTO meta_inbox_threads
                (counterpart_phone, human_handling, handling_version,
                 last_customer_at, last_message_at)
            VALUES ($1, $2, 0, NOW(), NOW())
            RETURNING thread_id
            """,
            phone,
            human_handling,
        )
        message_id = await conn.fetchval(
            """
            INSERT INTO meta_inbox_messages
                (thread_id, direction, sender_role, body, status)
            VALUES ($1, 'inbound', 'customer', $2, 'received')
            RETURNING id
            """,
            thread_id,
            body,
        )
        outbox_id = await conn.fetchval(
            """
            INSERT INTO wa_outbox
                (thread_id, message_id, needs_generation, status, attempts,
                 next_retry_at)
            VALUES ($1, $2, true, 'pending', $3, NOW() - INTERVAL '1 second')
            RETURNING id
            """,
            thread_id,
            message_id,
            attempts,
        )
    return {"thread_id": thread_id, "message_id": message_id, "outbox_id": outbox_id}


async def _fetch_carrier(pool: asyncpg.Pool, outbox_id: int) -> asyncpg.Record:
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT status, abstained_at, evidence_score, served_by "
            "FROM wa_outbox WHERE id = $1",
            outbox_id,
        )


async def _fetch_sent_at(pool: asyncpg.Pool, message_id: int) -> Any:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT sent_at FROM meta_inbox_messages WHERE id = $1", message_id
        )


async def _fetch_evidence_score_text(pool: asyncpg.Pool, outbox_id: int) -> str | None:
    """I83 (F2): the exact NUMERIC column text, not a float round-trip —
    proves the worker bound ``decimal.Decimal(repr(score))`` rather than
    the raw float (asyncpg would otherwise hand ``$5::numeric`` a binary
    float artifact that can print with trailing digits the sealed JSON
    text never had)."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT evidence_score::text FROM wa_outbox WHERE id = $1", outbox_id
        )


# ── 1. generated-supported ──────────────────────────────────────────────────


async def test_generated_supported_label_false_sets_score_only(
    db_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _seed_row(db_pool)
    monkeypatch.setattr(
        wa_codex_leg,
        "attempt",
        _codex_leg_stub(
            [
                wa_codex_leg.CodexLegResult(
                    text="Risposta sintetica supportata.",
                    reason="completed",
                    served_by="codex",
                    evidence_abstain_label=False,
                    evidence_score=0.42,
                    package_ref="pkg-hash-supported",
                )
            ]
        ),
    )
    whatsapp = _StubWhatsApp()
    outcome = await process_outbox_once(db_pool, whatsapp, _never_bot_gen)
    assert outcome == "sent"
    assert len(whatsapp.calls) == 1
    carrier = await _fetch_carrier(db_pool, row["outbox_id"])
    assert carrier["abstained_at"] is None
    assert float(carrier["evidence_score"]) == 0.42
    # I83: exact NUMERIC text, not just the float-equal check above.
    assert await _fetch_evidence_score_text(db_pool, row["outbox_id"]) == "0.42"
    assert carrier["served_by"] == "codex"


# ── 2. generated-abstain-label ──────────────────────────────────────────────


async def test_generated_abstain_label_true_sets_abstained_at_eq_sent_at(
    db_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _seed_row(db_pool)
    monkeypatch.setattr(
        wa_codex_leg,
        "attempt",
        _codex_leg_stub(
            [
                wa_codex_leg.CodexLegResult(
                    text="Risposta cautelata con abstain sigillato true.",
                    reason="completed",
                    served_by="codex",
                    evidence_abstain_label=True,
                    evidence_score=0.08,
                    package_ref="pkg-hash-abstain-true",
                )
            ]
        ),
    )
    whatsapp = _StubWhatsApp()
    outcome = await process_outbox_once(db_pool, whatsapp, _never_bot_gen)
    assert outcome == "sent"
    carrier = await _fetch_carrier(db_pool, row["outbox_id"])
    assert carrier["abstained_at"] is not None
    assert float(carrier["evidence_score"]) == 0.08
    sent_at = await _fetch_sent_at(db_pool, row["message_id"])
    assert carrier["abstained_at"] == sent_at
    # I83: exact NUMERIC text, not just the float-equal check above.
    assert await _fetch_evidence_score_text(db_pool, row["outbox_id"]) == "0.08"


# ── 3. retry, then the later successful attempt persists its own carrier ───


async def test_retry_then_later_attempt_persists_its_own_carrier(
    db_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _seed_row(db_pool)
    monkeypatch.setattr(
        wa_codex_leg,
        "attempt",
        _codex_leg_stub(
            [
                wa_codex_leg.CodexLegResult(reason="package_build_error"),  # fall-off
                wa_codex_leg.CodexLegResult(
                    text="Seconda chiamata riuscita.",
                    reason="completed",
                    served_by="codex",
                    evidence_abstain_label=False,
                    evidence_score=0.55,
                    package_ref="pkg-hash-retry-2",
                ),
            ]
        ),
    )
    whatsapp = _StubWhatsApp()

    first = await process_outbox_once(db_pool, whatsapp, _never_bot_gen)
    assert first == "retry"
    assert whatsapp.calls == []
    carrier_after_first = await _fetch_carrier(db_pool, row["outbox_id"])
    assert carrier_after_first["abstained_at"] is None
    assert carrier_after_first["evidence_score"] is None
    # The first attempt's own fall-off never reached the codex leg's
    # served completion branch, so it never had a served_by to carry —
    # this is the "NULL on a failed generation" case.
    assert carrier_after_first["served_by"] is None

    # Fast-forward past the backoff window (test setup only — the worker
    # itself decides the real backoff; this just makes the row due again
    # without sleeping 30s).
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE wa_outbox SET next_retry_at = NOW() - INTERVAL '1 second' "
            "WHERE id = $1",
            row["outbox_id"],
        )

    second = await process_outbox_once(db_pool, whatsapp, _never_bot_gen)
    assert second == "sent"
    assert len(whatsapp.calls) == 1
    carrier_after_second = await _fetch_carrier(db_pool, row["outbox_id"])
    assert carrier_after_second["abstained_at"] is None
    assert float(carrier_after_second["evidence_score"]) == 0.55
    assert carrier_after_second["served_by"] == "codex"


# ── 4. stale claim — commit_fenced None → both stay NULL ───────────────────


async def test_stale_claim_at_terminal_commit_persists_nothing(
    db_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _seed_row(db_pool)

    async def _steal_claim_token(*, pool: asyncpg.Pool, thread_id: int, outbox_id: int) -> None:
        return  # the leg itself is not where the race lands for this case

    monkeypatch.setattr(
        wa_codex_leg,
        "attempt",
        _codex_leg_stub(
            [
                wa_codex_leg.CodexLegResult(
                    text="Testo generato prima della race sul claim.",
                    reason="completed",
                    served_by="codex",
                    evidence_abstain_label=False,
                    evidence_score=0.60,
                    package_ref="pkg-hash-stale-claim",
                )
            ],
            side_effect=_steal_claim_token,
        ),
    )

    async def _steal_claim_during_send() -> None:
        # Simulates a reclaimer grabbing the row (fresh claim_token) in the
        # tiny window between the pre-send fence and the terminal commit —
        # after the pre-send fence already passed, so the Graph send below
        # still goes ahead (this is the documented residual double-send
        # window, spec P5) but the terminal UPDATE's fence now matches
        # nothing.
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE wa_outbox SET claim_token = $1 WHERE id = $2",
                uuid.uuid4(),
                row["outbox_id"],
            )

    whatsapp = _StubWhatsApp(side_effect=_steal_claim_during_send)
    outcome = await process_outbox_once(db_pool, whatsapp, _never_bot_gen)
    # The send itself succeeded (Graph API doesn't know about our claim
    # fence), so the worker still reports "sent" — see the residual-window
    # branch's own comment at the terminal commit.
    assert outcome == "sent"
    assert len(whatsapp.calls) == 1
    carrier = await _fetch_carrier(db_pool, row["outbox_id"])
    assert carrier["abstained_at"] is None
    assert carrier["evidence_score"] is None


# ── 5. takeover mid-generation — pre-send fence catches it, no send ────────


async def test_takeover_mid_generation_aborts_before_send(
    db_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _seed_row(db_pool, human_handling=False)

    async def _flip_human_handling(*, pool: asyncpg.Pool, thread_id: int, outbox_id: int) -> None:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE meta_inbox_threads SET human_handling = true WHERE thread_id = $1",
                thread_id,
            )

    monkeypatch.setattr(
        wa_codex_leg,
        "attempt",
        _codex_leg_stub(
            [
                wa_codex_leg.CodexLegResult(
                    text="Non dovrebbe mai essere inviato.",
                    reason="completed",
                    served_by="codex",
                    evidence_abstain_label=False,
                    evidence_score=0.70,
                    package_ref="pkg-hash-takeover",
                )
            ],
            side_effect=_flip_human_handling,
        ),
    )
    whatsapp = _StubWhatsApp()
    outcome = await process_outbox_once(db_pool, whatsapp, _never_bot_gen)
    assert outcome == "aborted_human"
    assert whatsapp.calls == []
    carrier = await _fetch_carrier(db_pool, row["outbox_id"])
    assert carrier["abstained_at"] is None
    assert carrier["evidence_score"] is None


# ── 6. failed send at MAX_ATTEMPTS — nothing persisted as a send ───────────


async def test_failed_send_at_max_attempts_persists_nothing(
    db_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _seed_row(db_pool, attempts=wa_outbox_worker.MAX_ATTEMPTS - 1)
    monkeypatch.setattr(
        wa_codex_leg,
        "attempt",
        _codex_leg_stub(
            [
                wa_codex_leg.CodexLegResult(
                    text="Generato ma non spedibile.",
                    reason="completed",
                    served_by="codex",
                    evidence_abstain_label=True,
                    evidence_score=0.33,
                    package_ref="pkg-hash-failed-send",
                )
            ]
        ),
    )
    whatsapp = _StubWhatsApp(raises=RuntimeError("synthetic graph send error"))
    outcome = await process_outbox_once(db_pool, whatsapp, _never_bot_gen)
    assert outcome == "failed"
    carrier = await _fetch_carrier(db_pool, row["outbox_id"])
    assert carrier["status"] == "failed"
    assert carrier["abstained_at"] is None
    assert carrier["evidence_score"] is None
    # The send never reached the terminal 'done' commit, so served_by was
    # never written either — same "nothing persisted as a send" rule.
    assert carrier["served_by"] is None


# ── 7. discarded completion (stand_down) — nothing persisted ───────────────


async def test_discarded_stand_down_persists_nothing(
    db_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _seed_row(db_pool)
    monkeypatch.setattr(
        wa_codex_leg,
        "attempt",
        _codex_leg_stub(
            [wa_codex_leg.CodexLegResult(stand_down=True, reason="stand_down_drift")]
        ),
    )
    whatsapp = _StubWhatsApp()
    outcome = await process_outbox_once(db_pool, whatsapp, _never_bot_gen)
    assert outcome == "aborted_human"
    assert whatsapp.calls == []
    carrier = await _fetch_carrier(db_pool, row["outbox_id"])
    assert carrier["abstained_at"] is None
    assert carrier["evidence_score"] is None


# ── 8. scripted greeting — served_by != "codex", both NULL ─────────────────


async def test_scripted_greeting_persists_nothing(
    db_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _seed_row(db_pool)
    monkeypatch.setattr(
        wa_codex_leg,
        "attempt",
        _codex_leg_stub(
            [
                wa_codex_leg.CodexLegResult(
                    text="Ciao! Come posso aiutarti oggi?",
                    reason="scripted_greeting_served",
                    served_by="scripted_greeting",
                )
            ]
        ),
    )
    whatsapp = _StubWhatsApp()
    outcome = await process_outbox_once(db_pool, whatsapp, _never_bot_gen)
    assert outcome == "sent"
    carrier = await _fetch_carrier(db_pool, row["outbox_id"])
    assert carrier["abstained_at"] is None
    assert carrier["evidence_score"] is None
    # served_by is NOT gated on evidence_abstain_label/evidence_score being
    # set — it is written unconditionally from the served completion.
    assert carrier["served_by"] == "scripted_greeting"


# ── 9. support-negative — served_by="support_abstain", never "codex" ───────


@pytest.mark.parametrize("sealed_label", [True, False])
async def test_support_negative_never_sets_abstained_at(
    db_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch, sealed_label: bool
) -> None:
    row = await _seed_row(db_pool)
    monkeypatch.setattr(
        wa_codex_leg,
        "attempt",
        _codex_leg_stub(
            [
                wa_codex_leg.CodexLegResult(
                    text="Mi scuso, ti metto in contatto con un umano.",
                    reason="support_unsupported",
                    served_by="support_abstain",
                    evidence_abstain_label=sealed_label,
                    evidence_score=0.15,
                    package_ref="pkg-hash-support-negative",
                )
            ]
        ),
    )
    whatsapp = _StubWhatsApp()
    outcome = await process_outbox_once(db_pool, whatsapp, _never_bot_gen)
    assert outcome == "sent"
    carrier = await _fetch_carrier(db_pool, row["outbox_id"])
    # D6: only a "codex"-served completion with a True sealed label sets
    # abstained_at — the support-negative stub never qualifies, even when
    # its own sealed label happens to be True (it generated nothing to
    # abstain FROM).
    assert carrier["abstained_at"] is None
    assert float(carrier["evidence_score"]) == 0.15
    # I83: exact NUMERIC text equals repr() of the stubbed score, proving
    # the fenced write binds decimal.Decimal(repr(score)) on this branch
    # too, not just the OFFERED-completed branch above.
    assert await _fetch_evidence_score_text(db_pool, row["outbox_id"]) == repr(0.15)


async def test_served_by_persists_support_abstain(
    db_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dedicated guilt proof for the gap this migration closes
    (docs/zantara-loop-state.md, Iteration 2): before migration 322 +
    the worker carrier change, ``served_by`` did not exist on ``wa_outbox``
    at all and the support-negative stub route was invisible in SQL —
    only `logger.info("wa_outbox: %s served ...")` said so. This test must
    FAIL against origin/main's worker (no ``served_by`` column, no bind
    param), proving the fix is actually in force, not just plausible."""
    row = await _seed_row(db_pool)
    monkeypatch.setattr(
        wa_codex_leg,
        "attempt",
        _codex_leg_stub(
            [
                wa_codex_leg.CodexLegResult(
                    text="Mi scuso, ti metto in contatto con un umano.",
                    reason="support_unsupported",
                    served_by="support_abstain",
                    evidence_abstain_label=True,
                    evidence_score=0.10,
                    package_ref="pkg-hash-served-by-support-abstain",
                )
            ]
        ),
    )
    whatsapp = _StubWhatsApp()
    outcome = await process_outbox_once(db_pool, whatsapp, _never_bot_gen)
    assert outcome == "sent"
    carrier = await _fetch_carrier(db_pool, row["outbox_id"])
    # D6 (unchanged by this PR): the stub never sets abstained_at, even
    # though it now has its OWN durable marker in served_by.
    assert carrier["abstained_at"] is None
    assert carrier["served_by"] == "support_abstain"
    assert carrier["served_by"] != "codex"


async def test_served_by_column_missing_mid_deploy_still_finalizes(
    db_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guilt+innocence for the deploy-window gap the Gear-3 council raised
    (see wa_outbox_worker.py's `_finalize` docstring): fly-deploy.yml's
    pre-deploy `run-migrations` job applies pending SQL against the
    PREVIOUS image, before `deploy` rolls this worker's new served_by
    write onto live traffic — migration 322 itself only lands afterwards,
    in `run-sql-v2-migrations-post-deploy`. Simulates that exact window by
    dropping the column mid-test: the worker must still finalize the row
    to 'done' (no residual double-send) with served_by simply unset,
    never crash the whole tick."""
    row = await _seed_row(db_pool)
    monkeypatch.setattr(
        wa_codex_leg,
        "attempt",
        _codex_leg_stub(
            [
                wa_codex_leg.CodexLegResult(
                    text="Generato durante la finestra di deploy.",
                    reason="completed",
                    served_by="codex",
                    evidence_abstain_label=False,
                    evidence_score=0.44,
                    package_ref="pkg-hash-deploy-window",
                )
            ]
        ),
    )
    async with db_pool.acquire() as conn:
        await conn.execute("ALTER TABLE wa_outbox DROP COLUMN served_by")
    try:
        whatsapp = _StubWhatsApp()
        outcome = await process_outbox_once(db_pool, whatsapp, _never_bot_gen)
        assert outcome == "sent"
        # Guilt: exactly ONE send — the fallback must not re-invoke the
        # Graph API (the send already happened irreversibly before the
        # column-missing terminal write is even attempted).
        assert len(whatsapp.calls) == 1
        async with db_pool.acquire() as conn:
            carrier = await conn.fetchrow(
                "SELECT status, abstained_at, evidence_score FROM wa_outbox WHERE id = $1",
                row["outbox_id"],
            )
        assert carrier["status"] == "done"
        assert carrier["abstained_at"] is None
        assert float(carrier["evidence_score"]) == 0.44
    finally:
        async with db_pool.acquire() as conn:
            await conn.execute("ALTER TABLE wa_outbox ADD COLUMN served_by TEXT NULL")


# ── 10. reattached completion — served_by="codex", all three carrier
#        fields None (F1/I83: a REATTACHED completion's rebuilt sealed wire
#        does not describe the package that generated the text) ───────────


async def test_reattached_completion_persists_nothing(
    db_pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _seed_row(db_pool)
    monkeypatch.setattr(
        wa_codex_leg,
        "attempt",
        _codex_leg_stub(
            [
                wa_codex_leg.CodexLegResult(
                    text="Testo da un job riagganciato da una claim precedente.",
                    reason="completed",
                    served_by="codex",
                    evidence_abstain_label=None,
                    evidence_score=None,
                    package_ref=None,
                )
            ]
        ),
    )
    whatsapp = _StubWhatsApp()
    outcome = await process_outbox_once(db_pool, whatsapp, _never_bot_gen)
    assert outcome == "sent"
    assert len(whatsapp.calls) == 1
    carrier = await _fetch_carrier(db_pool, row["outbox_id"])
    assert carrier["status"] == "done"
    assert carrier["abstained_at"] is None
    # served_by is written unconditionally from leg.served_by, unlike the
    # other two carrier fields which the REATTACHED leg zeroes out here.
    assert carrier["served_by"] == "codex"
    assert carrier["evidence_score"] is None
