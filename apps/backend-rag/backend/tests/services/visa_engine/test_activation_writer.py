"""Integration tests for the STEP-6a activation WRITER — real Postgres.

``VisaEngineRepository.activate_rule_pack`` (repository.py) is a thin,
one-statement wrapper around migration 251's ``SECURITY DEFINER`` function
``public.visa_activate_rule_pack(rule_pack_id, activated_by,
activation_reason)`` — ALL the bitemporal supersession logic (partial-
overlap reject, close-covered-priors, single-clock insert) lives in that
SQL function, not in Python. These tests exercise the function through the
repository method exclusively (never a raw INSERT for the activation under
test — ``test_repository.py`` already covers the raw-insert path against
the retained structural triggers).

Every test uses the ``repo``/``visa_schema``/``db_pool`` fixtures from this
directory's ``conftest.py`` — ``visa_schema`` now applies migration 250,
THEN 251, THEN 253 forward (see that fixture's updated docstring — 253 is
the STEP-6a FIX-ROUND roll-forward correction against 251, which merged and
applied to prod in flawed form before the fix-round landed; see 253's own
header), so every
test starts from a schema that includes ``activated_by_principal``, the
hardened (schema-qualified, ``search_path``-pinned) trigger functions, and
the writer function itself.

Reuses ``test_repository.py``'s pure builder/insert helpers
(``_insert_pack``, ``_pack_hash``, ``_open_range``, ``_bounded_range``,
``_ENV``) rather than duplicating them — these are plain functions, not
fixtures, and importing them from a sibling test module (mirroring how
``_builders.py`` is shared) keeps the two files' pack-insertion shape in
lockstep instead of two independently-drifting copies.

Run manually (see conftest.py's module docstring for the DB-safety
rationale — never point this at ``nuzantara_test``/``nuzantara_dev``):

    TEST_DATABASE_URL=postgresql://nuzantara@localhost:5432/<throwaway_db> \\
    PYTHONPATH=. pytest backend/tests/services/visa_engine/test_activation_writer.py -v
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from backend.services.visa_engine.repository import VisaEngineRepository

from .test_repository import _ENV, _bounded_range, _insert_pack, _open_range, _pack_hash

# --------------------------------------------------------------------------
# 1. Bootstrap: the first-ever activation for a triple (no prior head)
#    succeeds and stamps activated_by_principal.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_bootstrap_succeeds(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-boot",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-boot",
        payload_sha256=_pack_hash(1),
    )

    activation_id = await repo.activate_rule_pack(
        rule_pack_id=pack_id, activated_by="ops.alice", activation_reason="bootstrap-activation"
    )
    assert isinstance(activation_id, uuid.UUID)

    async with repo.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT rule_pack_id, activated_by, upper(system_period) AS upper_sp "
            "FROM visa_ruleset_activations WHERE id = $1",
            activation_id,
        )
    assert row is not None
    assert row["rule_pack_id"] == pack_id
    assert row["activated_by"] == "ops.alice"
    assert row["upper_sp"] is None  # open

    loaded = await repo.load_active_rule_pack(
        environment=_ENV,
        effective_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        observed_at=datetime.now(timezone.utc) + timedelta(milliseconds=5),
    )
    assert loaded is not None
    assert loaded["payload"]["note"] == "pack-boot"


# --------------------------------------------------------------------------
# 2. Supersession: activating a second pack that fully covers the first's
#    legal_period closes the prior activation and opens the new one, at the
#    SAME shared clock_timestamp() instant (adjacency).
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_supersession_closes_prior(repo: VisaEngineRepository) -> None:
    legal = _bounded_range(
        datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc)
    )
    pack_1, pack_2 = uuid.uuid4(), uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_1,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=_pack_hash(1),
    )
    await _insert_pack(
        repo,
        pack_id=pack_2,
        sequence=2,
        legal_period=legal,
        kid="key-2",
        signed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        note="pack-2",
        payload_sha256=_pack_hash(2),
        previous_payload_sha256=_pack_hash(1),
    )

    activation_1 = await repo.activate_rule_pack(
        rule_pack_id=pack_1, activated_by="ops.alice", activation_reason="bootstrap"
    )
    activation_2 = await repo.activate_rule_pack(
        rule_pack_id=pack_2, activated_by="ops.bob", activation_reason="supersede-with-pack-2"
    )
    assert activation_1 != activation_2

    async with repo.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, rule_pack_id, lower(system_period) AS lo, upper(system_period) AS hi "
            "FROM visa_ruleset_activations ORDER BY created_at"
        )
    assert len(rows) == 2
    prior, new = rows[0], rows[1]
    assert prior["id"] == activation_1
    assert prior["hi"] is not None  # closed
    assert new["id"] == activation_2
    assert new["hi"] is None  # still open

    # exactly one open activation for the triple
    async with repo.db_pool.acquire() as conn:
        open_count = await conn.fetchval(
            "SELECT count(*) FROM visa_ruleset_activations WHERE upper(system_period) IS NULL"
        )
    assert open_count == 1

    loaded = await repo.load_active_rule_pack(
        environment=_ENV,
        effective_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        observed_at=datetime.now(timezone.utc) + timedelta(milliseconds=5),
    )
    assert loaded is not None
    assert loaded["payload"]["note"] == "pack-2"


@pytest.mark.asyncio
async def test_activation_periods_adjacent(repo: VisaEngineRepository) -> None:
    """Closed prior's system_period upper bound == new activation's system_period
    lower bound EXACTLY — proof that both the close-step UPDATE and the new
    INSERT share the SAME ``clock_timestamp()`` read (design Q3)."""
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_1, pack_2 = uuid.uuid4(), uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_1,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=_pack_hash(1),
    )
    await _insert_pack(
        repo,
        pack_id=pack_2,
        sequence=2,
        legal_period=legal,
        kid="key-2",
        signed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        note="pack-2",
        payload_sha256=_pack_hash(2),
        previous_payload_sha256=_pack_hash(1),
    )

    await repo.activate_rule_pack(rule_pack_id=pack_1, activated_by="ops", activation_reason="r1")
    await repo.activate_rule_pack(rule_pack_id=pack_2, activated_by="ops", activation_reason="r2")

    async with repo.db_pool.acquire() as conn:
        closed_upper = await conn.fetchval(
            "SELECT upper(system_period) FROM visa_ruleset_activations WHERE rule_pack_id = $1", pack_1
        )
        new_lower = await conn.fetchval(
            "SELECT lower(system_period) FROM visa_ruleset_activations WHERE rule_pack_id = $1", pack_2
        )
    assert closed_upper is not None
    assert closed_upper == new_lower


# --------------------------------------------------------------------------
# 3. Disjoint legal periods: activating a second pack whose legal_period is
#    DISJOINT from a still-open prior's does NOT close the prior — both
#    remain open (different legal-validity windows, both "current" system-
#    wise; the GiST EXCLUDE constraint permits this precisely because
#    legal_period doesn't overlap).
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disjoint_legal_periods_coexist(repo: VisaEngineRepository) -> None:
    legal_a = _bounded_range(
        datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc)
    )
    legal_b = _bounded_range(
        datetime(2027, 1, 1, tzinfo=timezone.utc), datetime(2028, 1, 1, tzinfo=timezone.utc)
    )
    pack_a, pack_b = uuid.uuid4(), uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_a,
        sequence=1,
        legal_period=legal_a,
        kid="key-a",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-a",
        payload_sha256=_pack_hash(1),
    )
    await _insert_pack(
        repo,
        pack_id=pack_b,
        sequence=2,
        legal_period=legal_b,
        kid="key-b",
        signed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        note="pack-b",
        payload_sha256=_pack_hash(2),
        previous_payload_sha256=_pack_hash(1),
    )

    await repo.activate_rule_pack(rule_pack_id=pack_a, activated_by="ops", activation_reason="r-a")
    await repo.activate_rule_pack(rule_pack_id=pack_b, activated_by="ops", activation_reason="r-b")

    async with repo.db_pool.acquire() as conn:
        open_count = await conn.fetchval(
            "SELECT count(*) FROM visa_ruleset_activations WHERE upper(system_period) IS NULL"
        )
    assert open_count == 2  # BOTH stay open — disjoint legal_period, no close


# --------------------------------------------------------------------------
# 4. Partial legal-period overlap must be rejected (the finding-1 orphan
#    case) — and the rejected attempt must leave the prior activation
#    completely untouched (the whole function call is one transaction).
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_legal_overlap_rejected(repo: VisaEngineRepository) -> None:
    legal_1 = _bounded_range(
        datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc)
    )
    legal_2_partial = _bounded_range(
        datetime(2026, 6, 1, tzinfo=timezone.utc), datetime(2027, 6, 1, tzinfo=timezone.utc)
    )
    pack_1, pack_2 = uuid.uuid4(), uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_1,
        sequence=1,
        legal_period=legal_1,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=_pack_hash(1),
    )
    await _insert_pack(
        repo,
        pack_id=pack_2,
        sequence=2,
        legal_period=legal_2_partial,
        kid="key-2",
        signed_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        note="pack-2",
        payload_sha256=_pack_hash(2),
        previous_payload_sha256=_pack_hash(1),
    )

    await repo.activate_rule_pack(rule_pack_id=pack_1, activated_by="ops", activation_reason="r1")

    with pytest.raises(asyncpg.exceptions.RaiseError, match="partial legal-period overlap"):
        await repo.activate_rule_pack(
            rule_pack_id=pack_2, activated_by="ops", activation_reason="partial-overlap-attempt"
        )

    # innocence-of-side-effect: the rejected call must not have touched
    # pack_1's still-open activation (statement-level atomicity — the
    # trigger's RAISE unwinds the close-step UPDATE too).
    async with repo.db_pool.acquire() as conn:
        still_open = await conn.fetchval(
            "SELECT upper(system_period) FROM visa_ruleset_activations WHERE rule_pack_id = $1", pack_1
        )
    assert still_open is None


# --------------------------------------------------------------------------
# 5. F6(a) + P2 (verify round-1) guilt+innocence: activated_by/
#    activation_reason must be an OPAQUE TOKEN (^[A-Za-z0-9._:-]{1,120}$) —
#    blank, free-sentence (spaces), and oversized (>120 chars) values are all
#    rejected up front by the function itself.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_rejects_blank_activated_by(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=_pack_hash(1),
    )
    with pytest.raises(asyncpg.exceptions.RaiseError, match="activated_by must be an opaque token"):
        await repo.activate_rule_pack(rule_pack_id=pack_id, activated_by="   ", activation_reason="ok-reason")


@pytest.mark.asyncio
async def test_activate_rejects_free_sentence_activated_by(repo: VisaEngineRepository) -> None:
    """P2 (verify round-1): a human-readable free sentence (spaces) is no
    longer accepted — only an opaque reason-code/ticket-id/handle token."""
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=_pack_hash(1),
    )
    with pytest.raises(asyncpg.exceptions.RaiseError, match="activated_by must be an opaque token"):
        await repo.activate_rule_pack(
            rule_pack_id=pack_id, activated_by="ops alice smith", activation_reason="ok-reason"
        )


@pytest.mark.asyncio
async def test_activate_rejects_oversized_activated_by(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=_pack_hash(1),
    )
    with pytest.raises(asyncpg.exceptions.RaiseError, match="activated_by must be an opaque token"):
        await repo.activate_rule_pack(
            rule_pack_id=pack_id, activated_by="x" * 121, activation_reason="ok-reason"
        )


@pytest.mark.asyncio
async def test_activate_rejects_blank_activation_reason(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=_pack_hash(1),
    )
    with pytest.raises(
        asyncpg.exceptions.RaiseError, match="activation_reason must be an opaque reason-code"
    ):
        await repo.activate_rule_pack(rule_pack_id=pack_id, activated_by="ops.alice", activation_reason="")


@pytest.mark.asyncio
async def test_activate_rejects_free_sentence_activation_reason(repo: VisaEngineRepository) -> None:
    """P2 (verify round-1): the exact PII-forgery scenario this fix closes —
    a caller can no longer write a client's name/passport into this
    immutable, append-only, DELETE-rejecting audit column."""
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=_pack_hash(1),
    )
    with pytest.raises(
        asyncpg.exceptions.RaiseError, match="activation_reason must be an opaque reason-code"
    ):
        await repo.activate_rule_pack(
            rule_pack_id=pack_id,
            activated_by="ops.alice",
            activation_reason="activated per client X passport 123456 request",
        )


@pytest.mark.asyncio
async def test_activate_rejects_oversized_activation_reason(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=_pack_hash(1),
    )
    with pytest.raises(
        asyncpg.exceptions.RaiseError, match="activation_reason must be an opaque reason-code"
    ):
        await repo.activate_rule_pack(
            rule_pack_id=pack_id, activated_by="ops.alice", activation_reason="y" * 121
        )


@pytest.mark.asyncio
async def test_activate_accepts_boundary_length_actor_and_reason(repo: VisaEngineRepository) -> None:
    """Innocence: exactly 120 chars (the token-format boundary itself, not
    one-over) must NOT raise, for either column."""
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=_pack_hash(1),
    )
    activation_id = await repo.activate_rule_pack(
        rule_pack_id=pack_id, activated_by="a" * 120, activation_reason="b" * 120
    )
    assert isinstance(activation_id, uuid.UUID)


@pytest.mark.asyncio
async def test_activate_accepts_token_with_allowed_punctuation(repo: VisaEngineRepository) -> None:
    """Innocence: `.`/`_`/`:`/`-` are all allowed inside the opaque token
    shape (ticket-ID / reason-code conventions commonly use all four)."""
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=_pack_hash(1),
    )
    activation_id = await repo.activate_rule_pack(
        rule_pack_id=pack_id,
        activated_by="ops.alice_bot:2026-07-19",
        activation_reason="TICKET-2026.07.19_reg:update",
    )
    assert isinstance(activation_id, uuid.UUID)


@pytest.mark.asyncio
async def test_activate_rejects_null_activated_by(repo: VisaEngineRepository) -> None:
    """F3 (cross-family fix-round): before this fix, ``NULL ~ regex`` is SQL
    NULL, ``NOT NULL`` is still NULL, and ``IF NULL THEN ...`` never enters
    the branch — a NULL ``activated_by`` silently skipped the function's own
    validation entirely and fell through to the INSERT, where it surfaced as
    a raw, low-level ``NOT NULL`` table-constraint violation instead of this
    function's typed, friendly error. The explicit ``IS NULL OR`` guard
    closes that gap."""
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-null-activated-by",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-null-activated-by",
        payload_sha256=_pack_hash(1),
    )
    with pytest.raises(asyncpg.exceptions.RaiseError, match="activated_by must be an opaque token"):
        await repo.activate_rule_pack(
            rule_pack_id=pack_id, activated_by=None, activation_reason="ok-reason"  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_activate_rejects_null_activation_reason(repo: VisaEngineRepository) -> None:
    """F3 (cross-family fix-round): same NULL-slips-past-regex gap as above,
    for ``activation_reason`` (also ``TEXT NOT NULL`` at the table level)."""
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-null-activation-reason",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-null-activation-reason",
        payload_sha256=_pack_hash(1),
    )
    with pytest.raises(
        asyncpg.exceptions.RaiseError, match="activation_reason must be an opaque reason-code"
    ):
        await repo.activate_rule_pack(
            rule_pack_id=pack_id, activated_by="ops.alice", activation_reason=None  # type: ignore[arg-type]
        )


# --------------------------------------------------------------------------
# 6. F6(b): activated_by_principal is stamped with session_user
#    UNCONDITIONALLY — a caller-supplied value (even via a raw INSERT that
#    explicitly names the column) is always overwritten.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activated_by_principal_stamped_and_unspoofable(repo: VisaEngineRepository) -> None:
    legal_a = _bounded_range(
        datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc)
    )
    legal_b = _bounded_range(
        datetime(2027, 1, 1, tzinfo=timezone.utc), datetime(2028, 1, 1, tzinfo=timezone.utc)
    )
    pack_a, pack_b = uuid.uuid4(), uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_a,
        sequence=1,
        legal_period=legal_a,
        kid="key-a",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-a",
        payload_sha256=_pack_hash(1),
    )
    await _insert_pack(
        repo,
        pack_id=pack_b,
        sequence=2,
        legal_period=legal_b,
        kid="key-b",
        signed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        note="pack-b",
        payload_sha256=_pack_hash(2),
        previous_payload_sha256=_pack_hash(1),
    )

    async with repo.db_pool.acquire() as conn:
        session_user = await conn.fetchval("SELECT session_user")

    # Via the writer function: activated_by is preserved as narrative;
    # activated_by_principal is the REAL session_user, never the caller's
    # claimed identity.
    activation_a = await repo.activate_rule_pack(
        rule_pack_id=pack_a, activated_by="claimed-human-name", activation_reason="via-function"
    )
    async with repo.db_pool.acquire() as conn:
        row_a = await conn.fetchrow(
            "SELECT activated_by, activated_by_principal FROM visa_ruleset_activations WHERE id = $1",
            activation_a,
        )
    assert row_a["activated_by"] == "claimed-human-name"
    assert row_a["activated_by_principal"] == session_user

    # Via a raw INSERT that explicitly tries to SPOOF activated_by_principal
    # in the column list itself — the trigger overwrites it regardless.
    async with repo.db_pool.acquire() as conn:
        activation_b = await conn.fetchval(
            """
            INSERT INTO visa_ruleset_activations
                (rule_pack_id, environment, legal_period, activated_by, activation_reason,
                 activated_by_principal)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            pack_b,
            _ENV,
            legal_b,
            "tester",
            "raw-spoof-attempt",
            "someone-else-entirely",
        )
        row_b = await conn.fetchrow(
            "SELECT activated_by_principal FROM visa_ruleset_activations WHERE id = $1", activation_b
        )
    assert row_b["activated_by_principal"] == session_user
    assert row_b["activated_by_principal"] != "someone-else-entirely"


@pytest.mark.asyncio
async def test_activated_by_principal_immutable_on_update(repo: VisaEngineRepository) -> None:
    """Implementer-added closure (migration 251 header): a raw UPDATE that
    tries to change ONLY activated_by_principal (while otherwise shaping the
    UPDATE like a legitimate close) must still raise — the mutation-guard
    trigger's OR-chain enumerates this column too, not just system_period.
    """
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=_pack_hash(1),
    )
    activation_id = await repo.activate_rule_pack(
        rule_pack_id=pack_id, activated_by="ops.alice", activation_reason="r1"
    )

    async with repo.db_pool.acquire() as conn:
        with pytest.raises(
            asyncpg.exceptions.RaiseError, match="only closing an open system_period"
        ):
            await conn.execute(
                "UPDATE visa_ruleset_activations SET activated_by_principal = 'spoofed' WHERE id = $1",
                activation_id,
            )


# --------------------------------------------------------------------------
# 7. Function guilt: unknown pack_id, sequence-rollback (trigger), hash-
#    chain break (trigger) — all raise from WITHIN the function call, and
#    each rejected attempt leaves prior state untouched (one transaction).
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_unknown_pack_id_raises(repo: VisaEngineRepository) -> None:
    with pytest.raises(asyncpg.exceptions.RaiseError, match="unknown rule_pack_id"):
        await repo.activate_rule_pack(
            rule_pack_id=uuid.uuid4(), activated_by="ops.alice", activation_reason="ghost-pack"
        )


@pytest.mark.asyncio
async def test_activate_sequence_rollback_via_function_raises(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_1, pack_2 = uuid.uuid4(), uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_1,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=_pack_hash(1),
    )
    await _insert_pack(
        repo,
        pack_id=pack_2,
        sequence=2,
        legal_period=legal,
        kid="key-2",
        signed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        note="pack-2",
        payload_sha256=_pack_hash(2),
        previous_payload_sha256=_pack_hash(1),
    )

    await repo.activate_rule_pack(rule_pack_id=pack_1, activated_by="ops", activation_reason="r1")
    await repo.activate_rule_pack(rule_pack_id=pack_2, activated_by="ops", activation_reason="r2")

    # pack_1 (sequence 1) is now superseded by pack_2 (sequence 2) — trying
    # to activate pack_1 again must be rejected by the insert-guard
    # trigger's sequence-monotonicity check, even though it is reached only
    # after the writer function's OWN close-step ran (same legal_period, so
    # the close-step closes pack_2's activation before the INSERT trigger
    # rejects it) — the whole call rolls back atomically.
    with pytest.raises(asyncpg.exceptions.RaiseError, match="rollback rejected"):
        await repo.activate_rule_pack(
            rule_pack_id=pack_1, activated_by="ops", activation_reason="illegal-re-activation"
        )

    # pack_2's activation must be untouched (still open) — the close-step's
    # UPDATE inside the failed call was rolled back with everything else.
    async with repo.db_pool.acquire() as conn:
        pack_2_upper = await conn.fetchval(
            "SELECT upper(system_period) FROM visa_ruleset_activations WHERE rule_pack_id = $1", pack_2
        )
    assert pack_2_upper is None


@pytest.mark.asyncio
async def test_activate_hash_chain_break_via_function_raises(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    hash_a = _pack_hash(1)
    pack_1 = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_1,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-1",
        payload_sha256=hash_a,
    )
    await repo.activate_rule_pack(rule_pack_id=pack_1, activated_by="ops", activation_reason="r1")

    # pack_2_wrong claims a HIGHER sequence (passes sequence-monotonicity)
    # but its previous_payload_sha256 points at the WRONG hash (not pack_1's
    # actual payload_sha256) — the hash-chain check must reject it.
    pack_2_wrong = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_2_wrong,
        sequence=2,
        legal_period=legal,
        kid="key-2-wrong",
        signed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        note="pack-2-wrong",
        payload_sha256=_pack_hash(2),
        previous_payload_sha256=_pack_hash(99),  # wrong — not hash_a
    )
    with pytest.raises(asyncpg.exceptions.RaiseError, match="hash chain broken"):
        await repo.activate_rule_pack(
            rule_pack_id=pack_2_wrong, activated_by="ops", activation_reason="broken-chain"
        )

    async with repo.db_pool.acquire() as conn:
        pack_1_upper = await conn.fetchval(
            "SELECT upper(system_period) FROM visa_ruleset_activations WHERE rule_pack_id = $1", pack_1
        )
    assert pack_1_upper is None  # untouched — rejected call rolled back atomically


# --------------------------------------------------------------------------
# 8. F1+F2 grant scaffold: role-guarded, no-op today (CI clone has no
#    visa_activation_executor role) — proves the scaffold WOULD arm
#    correctly once the operator provisioning creates that role, without
#    asserting anything about backend_rag_v2 (deliberately untouched by
#    this migration; see its header). VERIFY ROUND-1 (P0-1): the executor
#    gets EXECUTE-only — this test now also proves the INNOCENCE half of
#    that fix (no SELECT/INSERT leak onto the signed-pack table), not just
#    the guilt half (EXECUTE present).
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grant_scaffold_role_aware(repo: VisaEngineRepository) -> None:
    async with repo.db_pool.acquire() as conn:
        role_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'visa_activation_executor')"
        )
    if not role_exists:
        pytest.skip(
            "visa_activation_executor role absent — operator provisioning not yet run "
            "(F1+F2 Option-1 scaffold, migration 251 header)"
        )
    async with repo.db_pool.acquire() as conn:
        has_select = await conn.fetchval(
            "SELECT has_table_privilege('visa_activation_executor', 'public.visa_rule_packs', 'SELECT')"
        )
        has_insert = await conn.fetchval(
            "SELECT has_table_privilege('visa_activation_executor', 'public.visa_rule_packs', 'INSERT')"
        )
        has_execute = await conn.fetchval(
            "SELECT has_function_privilege("
            "'visa_activation_executor', 'public.visa_activate_rule_pack(uuid,text,text)', 'EXECUTE')"
        )
    assert has_execute
    # P0-1 innocence: NEVER direct table access on the signed-pack table —
    # an executor with SELECT+INSERT there could insert a structurally-
    # valid but Ed25519-forged pack and activate it via EXECUTE, defeating
    # the "only signed packs become active" invariant (see this migration's
    # header, F1+F2(b)).
    assert not has_select
    assert not has_insert


@pytest.mark.asyncio
async def test_function_not_executable_by_unprivileged_role(repo: VisaEngineRepository) -> None:
    """REVOKE ALL ON FUNCTION ... FROM PUBLIC (F1+F2(c)) holds unconditionally
    — independent of the role-provisioning state. Postgres grants EXECUTE to
    PUBLIC by default at CREATE FUNCTION time; migration 251 explicitly
    revokes it. Proven by creating a throwaway, privilege-free role and
    confirming it (and therefore PUBLIC) has no EXECUTE grant."""
    probe_role = "visa_test_probe_norights"
    async with repo.db_pool.acquire() as conn:
        try:
            await conn.execute(f"CREATE ROLE {probe_role} NOLOGIN")
        except asyncpg.exceptions.InsufficientPrivilegeError:
            pytest.skip("test DB role lacks CREATE ROLE — cannot probe PUBLIC-execute directly")
        try:
            has_exec = await conn.fetchval(
                "SELECT has_function_privilege("
                "$1, 'public.visa_activate_rule_pack(uuid,text,text)', 'EXECUTE')",
                probe_role,
            )
            assert has_exec is False
        finally:
            await conn.execute(f"DROP ROLE {probe_role}")


# --------------------------------------------------------------------------
# 9. P1-3 (verify round-1): every migration-250 trigger's `tgfoid` resolves
#    to the expected `public.*` HARDENED function, and that function's
#    `proconfig` has `search_path` pinned — the regression the unqualified
#    `CREATE OR REPLACE FUNCTION reject_visa_*` targets (fixed by this
#    round) would otherwise let a hijacked migration-session search_path
#    silently create/replace a DECOY function elsewhere, leaving the real
#    triggers bound to migration 250's un-hardened bodies with zero error.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("trigger_name", "table_name", "expected_function"),
    [
        ("visa_rule_packs_immutable", "visa_rule_packs", "reject_visa_immutable_mutation"),
        (
            "visa_rule_packs_payload_binding",
            "visa_rule_packs",
            "reject_visa_pack_payload_mismatch",
        ),
        (
            "visa_activation_insert_guard",
            "visa_ruleset_activations",
            "reject_visa_activation_insert",
        ),
        (
            "visa_ruleset_activations_append_only",
            "visa_ruleset_activations",
            "reject_visa_activation_mutation",
        ),
    ],
)
async def test_trigger_resolves_to_hardened_public_function(
    repo: VisaEngineRepository, trigger_name: str, table_name: str, expected_function: str
) -> None:
    async with repo.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT n.nspname, p.proname, p.proconfig
            FROM pg_trigger t
            JOIN pg_proc p ON p.oid = t.tgfoid
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE t.tgrelid = $1::regclass AND t.tgname = $2 AND NOT t.tgisinternal
            """,
            f"public.{table_name}",
            trigger_name,
        )
    assert row is not None, f"trigger {trigger_name} not found on {table_name}"
    # tgfoid resolves to public.<expected_function> — not some other schema's
    # same-named (or differently-named) decoy.
    assert row["nspname"] == "public"
    assert row["proname"] == expected_function
    # search_path is pinned on the resolved function (F3 hardening) — never
    # inherits the caller/migration-session's search_path.
    proconfig = row["proconfig"] or []
    assert "search_path=pg_catalog, pg_temp" in proconfig, (
        f"{expected_function} proconfig={proconfig!r} does not pin search_path"
    )


# --------------------------------------------------------------------------
# 10. F9 (verify round-1 addendum) guilt+innocence: row-level triggers never
#     fire on a statement-level table-wipe — the new statement-level guards
#     must reject it on BOTH tables, while normal INSERT still works.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_truncate_rejected_on_visa_rule_packs(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    await _insert_pack(
        repo,
        pack_id=uuid.uuid4(),
        sequence=1,
        legal_period=legal,
        kid="key-truncate-guard",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-truncate-guard",
        payload_sha256=_pack_hash(1),
    )
    async with repo.db_pool.acquire() as conn:
        # CASCADE is required here purely because `visa_ruleset_activations`
        # FK-references this table (Postgres refuses a bare TRUNCATE on a
        # referenced table) — the statement-level guard trigger still fires
        # BEFORE either table is actually emptied, so CASCADE never gets a
        # chance to take effect.
        with pytest.raises(asyncpg.exceptions.RaiseError, match="is append-only"):
            await conn.execute("TRUNCATE TABLE public.visa_rule_packs CASCADE")
        # innocence: the table (and the row just inserted) is untouched —
        # the rejected TRUNCATE must not have wiped anything.
        count = await conn.fetchval("SELECT count(*) FROM public.visa_rule_packs")
    assert count == 1


@pytest.mark.asyncio
async def test_truncate_rejected_on_visa_ruleset_activations(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-truncate-guard-2",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-truncate-guard-2",
        payload_sha256=_pack_hash(1),
    )
    await repo.activate_rule_pack(
        rule_pack_id=pack_id, activated_by="ops.alice", activation_reason="truncate-guard-setup"
    )
    async with repo.db_pool.acquire() as conn:
        with pytest.raises(asyncpg.exceptions.RaiseError, match="is append-only"):
            await conn.execute("TRUNCATE TABLE public.visa_ruleset_activations")
        count = await conn.fetchval("SELECT count(*) FROM public.visa_ruleset_activations")
    assert count == 1


@pytest.mark.asyncio
async def test_insert_still_works_after_truncate_guard_installed(repo: VisaEngineRepository) -> None:
    """Innocence at the writer level: adding the two statement-level guards
    must not perturb the normal INSERT path the writer function relies on."""
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-truncate-guard-3",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-truncate-guard-3",
        payload_sha256=_pack_hash(1),
    )
    activation_id = await repo.activate_rule_pack(
        rule_pack_id=pack_id, activated_by="ops.alice", activation_reason="truncate-guard-innocence"
    )
    assert isinstance(activation_id, uuid.UUID)


# --------------------------------------------------------------------------
# 11. P1-5 + P1-6 (verify round-1): the REAL boundary, not a proxy. Creates
#     REAL, randomly-suffixed roles (Postgres roles are CLUSTER-wide — a
#     fixed name would collide with a sibling suite's concurrent run) that
#     mirror the operator provisioning script byte-for-byte: transfer BOTH
#     tables' AND all 5 functions' ownership to a stand-in ledger-owner
#     role, REVOKE direct DML from a stand-in serving role (which starts
#     out AS the table owner, mirroring `backend_rag_v2`'s documented
#     "prod today" state), GRANT EXECUTE-only to a stand-in executor role.
#     Then proves, by MACHINE ASSERTION: (i) the serving role has zero
#     direct INSERT after the transfer; (ii) the writer succeeds connected
#     AS the executor; (iii) it fails permission-denied for the (now
#     unprivileged) serving role; (iv) migration 251's OWN rollback SQL
#     executes cleanly when run AS the ledger-owner role post-transfer
#     (P1-6 — the documented answer to "who runs rollbacks post-hardening").
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ownership_and_grant_boundary_real_roles(repo: VisaEngineRepository) -> None:
    from .conftest import _read_migration_251

    suffix = uuid.uuid4().hex[:10]
    owner_role = f"visa_test_owner_{suffix}"
    serving_role = f"visa_test_serving_{suffix}"
    executor_role = f"visa_test_executor_{suffix}"

    trigger_functions = [
        "reject_visa_immutable_mutation",
        "reject_visa_pack_payload_mismatch",
        "reject_visa_activation_insert",
        "reject_visa_activation_mutation",
    ]

    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_id = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-real-boundary",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-real-boundary",
        payload_sha256=_pack_hash(1),
    )

    async with repo.db_pool.acquire() as conn:
        try:
            # The whole provisioning phase below (CREATE ROLE through the
            # final schema GRANT) requires the SAME elevated privilege the
            # test's own finally-block comment assumes ("the connecting
            # (superuser) role"): CREATE ROLE alone isn't sufficient — a
            # non-superuser with CREATEROLE can create a role without
            # thereby gaining membership in it, so the very next step
            # (ALTER TABLE ... OWNER TO <role just created>) fails with the
            # identical InsufficientPrivilegeError on a test-runner role
            # that merely has CREATEROLE but not superuser (observed on a
            # local dev Postgres, 2026-07-20). One try/except for the whole
            # phase, not just the CREATE ROLE calls — a role created but
            # never successfully owned/granted anything is equally unable
            # to "mirror the real boundary" this test exists to assert.
            try:
                await conn.execute(f"CREATE ROLE {owner_role} NOLOGIN")
                await conn.execute(f"CREATE ROLE {serving_role} NOLOGIN")
                await conn.execute(f"CREATE ROLE {executor_role} NOLOGIN")

                # 1. Simulate TODAY's prod state: the serving role owns both
                #    tables (mirrors `backend_rag_v2` being both table owner
                #    AND serving role — F1+F2's own documented starting point).
                await conn.execute(f"ALTER TABLE public.visa_rule_packs OWNER TO {serving_role}")
                await conn.execute(
                    f"ALTER TABLE public.visa_ruleset_activations OWNER TO {serving_role}"
                )

                # 2. The operator provisioning script's REQUIRED steps
                #    (migration header, F1+F2 / P0-2): move BOTH tables' AND
                #    all 5 functions' ownership to the ledger-owner role,
                #    THEN revoke direct DML from the now-non-owning serving
                #    role, THEN grant EXECUTE-only to the executor role.
                await conn.execute(f"ALTER TABLE public.visa_rule_packs OWNER TO {owner_role}")
                await conn.execute(
                    f"ALTER TABLE public.visa_ruleset_activations OWNER TO {owner_role}"
                )
                await conn.execute(
                    f"ALTER FUNCTION public.visa_activate_rule_pack(uuid, text, text) OWNER TO {owner_role}"
                )
                for fn in trigger_functions:
                    await conn.execute(f"ALTER FUNCTION public.{fn}() OWNER TO {owner_role}")
                await conn.execute(
                    f"REVOKE INSERT, UPDATE, DELETE ON public.visa_rule_packs, "
                    f"public.visa_ruleset_activations FROM {serving_role}"
                )
                await conn.execute(
                    f"GRANT EXECUTE ON FUNCTION public.visa_activate_rule_pack(uuid, text, text) "
                    f"TO {executor_role}"
                )
                # DISCOVERED WHILE WRITING THIS TEST (P1-6): `CREATE OR
                # REPLACE FUNCTION` checks schema-level CREATE privilege
                # independent of function ownership (Postgres does not
                # exempt "replace" from the schema ACL check even though it
                # exempts it from needing to already own the target).
                # Migration 251's rollback runs `CREATE OR REPLACE FUNCTION
                # public.reject_visa_*` — so `visa_ledger_owner` needs
                # `CREATE ON SCHEMA public` too, not just object ownership,
                # or a post-hardening rollback fails with "permission
                # denied for schema public". Folded into the migration
                # header's provisioning steps + PENDING-ARMS.md.
                await conn.execute(f"GRANT CREATE ON SCHEMA public TO {owner_role}")
            except asyncpg.exceptions.InsufficientPrivilegeError:
                pytest.skip(
                    "test DB role lacks privilege to create/own throwaway "
                    "roles — cannot mirror the real boundary"
                )

            # --- P0-2 machine assertion: every one of the 5 functions is
            #     now owned by the ledger-owner role, never the serving
            #     role — the exact `pg_proc.proowner` check this migration's
            #     header documents as the required proof-of-armed.
            owners = await conn.fetch(
                """
                SELECT p.proname, p.proowner::regrole::text AS owner
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proname = ANY($1::text[])
                """,
                ["visa_activate_rule_pack", *trigger_functions],
            )
            assert len(owners) == 5
            for row in owners:
                assert row["owner"] == owner_role, (
                    f"{row['proname']} owned by {row['owner']!r}, expected {owner_role!r}"
                )

            # --- P1-5 (i): the serving role — post-transfer, post-revoke —
            #     has NO direct INSERT on the ledger table.
            has_insert = await conn.fetchval(
                "SELECT has_table_privilege($1, 'public.visa_ruleset_activations', 'INSERT')",
                serving_role,
            )
            assert has_insert is False

            # --- P1-5 (ii): the writer succeeds when called AS the
            #     executor (SET LOCAL ROLE scopes the identity change to
            #     this one transaction on the pooled connection).
            async with conn.transaction():
                await conn.execute(f"SET LOCAL ROLE {executor_role}")
                activation_id = await conn.fetchval(
                    "SELECT public.visa_activate_rule_pack($1, $2, $3)",
                    pack_id,
                    "ops.alice",
                    "boundary-test",
                )
            assert isinstance(activation_id, uuid.UUID)

            # --- P1-5 (iii): the writer FAILS permission-denied for the
            #     (now-unprivileged) serving role — proves the boundary
            #     against the REAL serving-role identity, not a throwaway
            #     unrelated probe role.
            with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.execute(f"SET LOCAL ROLE {serving_role}")
                    await conn.fetchval(
                        "SELECT public.visa_activate_rule_pack($1, $2, $3)",
                        pack_id,
                        "ops.alice",
                        "boundary-test-2",
                    )

            # --- P1-6: migration 251's OWN rollback SQL executes cleanly
            #     when run AS the ledger-owner role, post-transfer — the
            #     documented answer to "who runs rollbacks post-hardening".
            _, rollback_251 = _read_migration_251()
            async with conn.transaction():
                await conn.execute(f"SET LOCAL ROLE {owner_role}")
                await conn.execute(rollback_251)
        finally:
            # Defensive teardown regardless of assertion outcome above:
            # reassign anything the throwaway roles still own back to the
            # connecting (superuser) role, drop residual grants, then drop
            # the roles themselves — never leave CLUSTER-wide role debris
            # for a sibling suite to collide with.
            await conn.execute("RESET ROLE")
            for role in (executor_role, serving_role, owner_role):
                for stmt in (
                    f"REASSIGN OWNED BY {role} TO CURRENT_USER",
                    f"DROP OWNED BY {role}",
                    f"DROP ROLE IF EXISTS {role}",
                ):
                    try:
                        await conn.execute(stmt)
                    except asyncpg.exceptions.PostgresError:
                        pass
