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
directory's ``conftest.py`` — ``visa_schema`` now applies migration 250
THEN migration 251 forward (see that fixture's updated docstring), so every
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
        rule_pack_id=pack_id, activated_by="ops.alice", activation_reason="bootstrap activation"
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
        rule_pack_id=pack_2, activated_by="ops.bob", activation_reason="supersede with pack-2"
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
            rule_pack_id=pack_2, activated_by="ops", activation_reason="partial overlap attempt"
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
# 5. F6(a) guilt+innocence: blank/oversized activated_by/activation_reason
#    are rejected up front by the function itself.
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
    with pytest.raises(asyncpg.exceptions.RaiseError, match="activated_by must be non-blank"):
        await repo.activate_rule_pack(rule_pack_id=pack_id, activated_by="   ", activation_reason="ok reason")


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
    with pytest.raises(asyncpg.exceptions.RaiseError, match="activated_by must be non-blank"):
        await repo.activate_rule_pack(
            rule_pack_id=pack_id, activated_by="x" * 201, activation_reason="ok reason"
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
    with pytest.raises(asyncpg.exceptions.RaiseError, match="activation_reason must be non-blank"):
        await repo.activate_rule_pack(rule_pack_id=pack_id, activated_by="ops.alice", activation_reason="")


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
    with pytest.raises(asyncpg.exceptions.RaiseError, match="activation_reason must be non-blank"):
        await repo.activate_rule_pack(
            rule_pack_id=pack_id, activated_by="ops.alice", activation_reason="y" * 1001
        )


@pytest.mark.asyncio
async def test_activate_accepts_boundary_length_actor_and_reason(repo: VisaEngineRepository) -> None:
    """Innocence: exactly 200/1000 chars (the boundary itself, not one-over)
    must NOT raise."""
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
        rule_pack_id=pack_id, activated_by="a" * 200, activation_reason="b" * 1000
    )
    assert isinstance(activation_id, uuid.UUID)


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
        rule_pack_id=pack_a, activated_by="claimed-human-name", activation_reason="via function"
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
            "raw spoof attempt",
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
            rule_pack_id=uuid.uuid4(), activated_by="ops.alice", activation_reason="ghost pack"
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
            rule_pack_id=pack_1, activated_by="ops", activation_reason="illegal re-activation"
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
            rule_pack_id=pack_2_wrong, activated_by="ops", activation_reason="broken chain"
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
#    this migration; see its header).
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
    assert has_select
    assert has_insert
    assert has_execute


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
