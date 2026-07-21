"""Integration tests for ``VisaEngineRepository`` (PR4) — real Postgres.

Every test uses the ``repo``/``visa_schema``/``db_pool`` fixtures from this
directory's ``conftest.py``: a fresh, freshly-migration-250-applied
``visa_rule_packs``/``visa_ruleset_activations`` schema per test (DROP +
recreate — see that fixture's docstring for why per-test DELETE-based
cleanup is impossible against an append-only table).

These tests build minimal, DB-shape-valid rows directly (random 32/64-byte
placeholder digests via ``uuid4().bytes``, real ``tstzrange`` values) — they
do NOT sign or JSON-Schema-validate ``protected_header``/``payload``
content, because to the repository (and to Postgres) those columns are
opaque JSONB; signing/verification is ``bundle.py``'s job (PR2b), not
tested here.

PR4 SCOPE (2026-07-19): ``VisaEngineRepository`` ships no activation WRITER
— the bitemporal supersession (closing a prior activation and inserting the
new one atomically) is deferred to STEP 6's ``SECURITY DEFINER`` DB
function ``visa_activate_rule_pack(...)`` (see ``repository.py``'s module
docstring, "PR4 SCOPE — no activation WRITER"). Every test below that needs
an activation row builds it via a RAW INSERT (the ``_insert_activation_raw``
helper below) instead of calling a repository method — this exercises
exactly the RETAINED ledger structural triggers
(``reject_visa_activation_insert``/``reject_visa_activation_mutation``),
which are unchanged by the PR4 split and are exactly what STEP-6's
``SECURITY DEFINER`` function will itself run under. Full supersession
(automatic close-of-prior), legal-period adjacency, and partial-legal-
overlap rejection are STEP-6 BEHAVIORS — they depend on the writer's
close-then-insert transaction, which this module does not have — and are
tested there, not here (this file previously carried
``test_supersession_closes_prior``, ``test_disjoint_legal_periods_coexist``,
``test_activation_periods_adjacent``, and
``test_partial_legal_overlap_rejected`` for exactly that logic; they moved
out with the writer).

Run manually (see the conftest module docstring for the DB-safety
rationale — never point this at ``nuzantara_test``/``nuzantara_dev``):

    TEST_DATABASE_URL=postgresql://nuzantara@localhost:5432/<throwaway_db> \\
    PYTHONPATH=. pytest backend/tests/services/visa_engine/test_repository.py -v
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    TrustedSigningKey,
    VerifiedRulePack,
    _decode_base64url_no_padding,
    _parse_utc_datetime,
    verify_rule_pack,
)
from backend.services.visa_engine.repository import VisaEngineRepository

from ._builders import (
    ephemeral_ed25519_keypair,
    minimal_valid_envelope,
    sign_rule_pack_envelope,
)

_ENV = "TEST"


def _trust_store_for(*, kid: str, public_key, environment: str) -> StaticTrustStore:
    """Minimal single-key trust store for the P0-1/P1-8 end-to-end proof
    below — always-valid (no expiry/revocation), scoped to ``environment``
    (see ``bundle.TrustedSigningKey``'s docstring for why the scope matters)."""

    return StaticTrustStore(
        [
            TrustedSigningKey(
                key_id=kid,
                public_key=public_key,
                valid_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
                valid_to=None,
                revoked_at=None,
                environment=environment,
            )
        ]
    )


def _open_range(lower: datetime) -> asyncpg.Range:
    """``[lower, infinity)`` — matches migration 250's ``'[)'`` CHECK shape."""
    return asyncpg.Range(lower, None, lower_inc=True, upper_inc=False)


def _bounded_range(lower: datetime, upper: datetime) -> asyncpg.Range:
    """``[lower, upper)`` — matches migration 250's ``'[)'`` CHECK shape."""
    return asyncpg.Range(lower, upper, lower_inc=True, upper_inc=False)


def _protected_header(*, kid: str, signed_at: datetime, environment: str = _ENV) -> dict:
    """A ``ProtectedHeader``-shaped dict. Opaque to the repository/DB — only
    the wire *shape* (JSON object) matters for these tests, not schema
    validity (that's ``bundle.py``'s concern)."""
    return {
        "domain": "balizero.visa-rulepack.v1",
        "alg": "Ed25519",
        "kid": kid,
        "signed_at": signed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema_version": "1.0.0",
        "environment": environment,
    }


def _pack_hash(n: int) -> bytes:
    """Deterministic, distinct 32-byte placeholder "hash" for chain-position
    ``n`` (a small positive int). NOT a real SHA-256 digest — these tests
    never hash real bytes, only prove the DB's stored-BYTES hash-chain
    trigger compares exactly what it is given — but each ``n`` yields a
    value distinct from every other ``n``, so the table's
    ``UNIQUE(payload_sha256)`` constraint never collides across packs
    inserted within the same test.
    """
    return bytes([n]) * 32


def _valid_period_for(legal_period: asyncpg.Range) -> dict:
    """Build a payload ``valid_period`` dict that round-trips to EXACTLY the
    given ``legal_period`` under migration 250's pack-payload-binding
    trigger's ``tstzrange((from)::timestamptz, (to)::timestamptz, '[)')``
    comparison (PR4 FIX-FIRST round 3, finding 1 — the row's legal_period is
    now bound to the signed payload's valid_period). ``.isoformat()`` on a
    tz-aware UTC datetime round-trips to the identical instant when cast back
    via ``::timestamptz``; a ``None`` upper (unbounded/open-ended range)
    becomes JSON ``null``, matching ``tstzrange(lower, NULL, '[)')``'s
    unbounded-upper shape.
    """
    return {
        "from": legal_period.lower.isoformat(),
        "to": legal_period.upper.isoformat() if legal_period.upper is not None else None,
    }


async def _insert_pack(
    repo: VisaEngineRepository,
    *,
    pack_id: uuid.UUID,
    sequence: int,
    legal_period: asyncpg.Range,
    kid: str,
    signed_at: datetime,
    note: str,
    payload_sha256: bytes,
    environment: str = _ENV,
    previous_payload_sha256: bytes | None = None,
) -> None:
    """Insert one minimal, DB-shape-valid ``visa_rule_packs`` row.

    PR4 FIX-FIRST round 2: the NEW pack-binding trigger
    (``reject_visa_pack_payload_mismatch``) requires the payload JSONB's
    ``rule_pack_id``/``environment``/``sequence``/``previous_payload_sha256``
    to EXACTLY match this row's own columns — so this helper now builds the
    payload dict FROM the same arguments it passes as row columns, instead
    of an unrelated ``{"note": note}`` blob. ``payload_sha256`` is now a
    REQUIRED, caller-chosen 32-byte value (never random — see ``_pack_hash``
    above): the NEW hash-chain trigger (``reject_visa_activation_insert``)
    compares a superseding pack's ``previous_payload_sha256`` against the
    CURRENT head activation's own pack's ``payload_sha256`` at activation
    time, so a test that activates a chain of packs must thread the real
    prior pack's hash into the next pack's ``previous_payload_sha256`` (both
    the row column AND the payload dict's hex string, kept in lockstep
    here) — ``None`` is only correct for a genuine sequence-1/bootstrap
    pack (or a pack that is never activated at all).

    PR4 FIX-FIRST round 3, finding 1 (P0): the trigger ALSO now binds this
    row's ``legal_period`` to the payload's ``valid_period`` — so the
    payload dict's ``valid_period`` is built via ``_valid_period_for``
    directly FROM the same ``legal_period`` this helper passes as the row
    column, keeping the two in lockstep for every call site in this suite.
    """
    await repo.insert_rule_pack(
        id=pack_id,
        environment=environment,
        sequence=sequence,
        pack_version="1.0.0",
        engine_contract_version="1.0.0",
        engine_min_version="1.0.0",
        engine_max_version="1.0.0",
        legal_period=legal_period,
        protected_header=_protected_header(kid=kid, signed_at=signed_at, environment=environment),
        payload={
            "note": note,
            "rule_pack_id": str(pack_id),
            "environment": environment,
            "sequence": sequence,
            "previous_payload_sha256": (
                previous_payload_sha256.hex() if previous_payload_sha256 is not None else None
            ),
            "valid_period": _valid_period_for(legal_period),
        },
        payload_sha256=payload_sha256,
        previous_payload_sha256=previous_payload_sha256,
        signature=uuid.uuid4().bytes * 4,
        signing_key_id=kid,
        signed_at=signed_at,
    )


async def _insert_activation_raw(
    repo: VisaEngineRepository,
    *,
    rule_pack_id: uuid.UUID,
    environment: str,
    jurisdiction: str = "ID",
    decision_domain: str = "IMMIGRATION_VISA",
    legal_period: asyncpg.Range,
    system_period: asyncpg.Range | None = None,
) -> None:
    """Raw INSERT into ``visa_ruleset_activations`` — PR4 ships no
    ``activate_rule_pack`` writer (that atomic close-prior/insert-new
    supersession is STEP 6's ``SECURITY DEFINER`` DB function; see
    ``repository.py``'s module docstring, "PR4 SCOPE — no activation
    WRITER"). Every test that needs an activation row builds it directly
    with this helper, exercising exactly the RETAINED ``visa_ruleset_
    activations`` structural triggers (``reject_visa_activation_insert`` —
    scope/hash-chain/sequence-monotonicity binding — and
    ``reject_visa_activation_mutation`` — append-only-with-close) rather
    than a Python method that no longer exists.

    ``system_period=None`` leaves the column DEFAULT
    (``tstzrange(now(), NULL, '[)')`` — open at insert time), which is
    correct for a test that only ever needs ONE open activation for a given
    ``(environment, jurisdiction, decision_domain)`` triple. A test that
    needs MULTIPLE activations for the SAME triple (e.g. proving
    sequence-monotonicity or the hash-chain across more than one pack) must
    pass explicit, non-overlapping ``system_period`` ranges — without the
    writer's automatic close-prior step, two open (unbounded-upper) rows for
    the same triple would collide on the GiST ``EXCLUDE`` constraint, same
    as any other raw INSERT would.
    """
    async with repo.db_pool.acquire() as conn:
        if system_period is None:
            await conn.execute(
                """
                INSERT INTO visa_ruleset_activations
                    (rule_pack_id, environment, jurisdiction, decision_domain,
                     legal_period, activated_by, activation_reason)
                VALUES ($1, $2, $3, $4, $5, 'tester', 'raw-activation-for-test')
                """,
                rule_pack_id,
                environment,
                jurisdiction,
                decision_domain,
                legal_period,
            )
        else:
            await conn.execute(
                """
                INSERT INTO visa_ruleset_activations
                    (rule_pack_id, environment, jurisdiction, decision_domain,
                     legal_period, system_period, activated_by, activation_reason)
                VALUES ($1, $2, $3, $4, $5, $6, 'tester', 'raw-activation-for-test')
                """,
                rule_pack_id,
                environment,
                jurisdiction,
                decision_domain,
                legal_period,
                system_period,
            )


async def _close_activation_raw(
    repo: VisaEngineRepository, *, rule_pack_id: uuid.UUID, closed_at: datetime
) -> None:
    """Raw UPDATE closing an open activation's ``system_period`` upper bound
    — the one legal mutation ``reject_visa_activation_mutation`` carves out
    (append-only-WITH-close). Stands in for the writer's automatic
    close-prior step (deferred to STEP 6) wherever a test needs a SECOND
    activation for the same ``(environment, jurisdiction, decision_domain)``
    triple without colliding on the GiST ``EXCLUDE`` constraint.
    """
    async with repo.db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE visa_ruleset_activations
            SET system_period = tstzrange(lower(system_period), $2, '[)')
            WHERE rule_pack_id = $1
            """,
            rule_pack_id,
            closed_at,
        )


# --------------------------------------------------------------------------
# 1. Bitemporal selection: both clocks must independently contain the query
#    point, or the read misses.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bitemporal_selection(repo: VisaEngineRepository) -> None:
    pack_id = uuid.uuid4()
    legal = _bounded_range(
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-A",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-A",
        payload_sha256=_pack_hash(1),
    )
    await _insert_activation_raw(
        repo, rule_pack_id=pack_id, environment=_ENV, legal_period=legal
    )
    # The raw insert's system_period lower bound is the DB's own column
    # DEFAULT now() — capture a safely-inside-and-a-safely-outside instant
    # relative to real wall-clock execution rather than a fixed calendar
    # date (the DB's "now" and the test's "today" must not be assumed to
    # coincide).
    inside_system = datetime.now(timezone.utc) + timedelta(milliseconds=5)
    outside_system_before = datetime.now(timezone.utc) - timedelta(days=1)
    inside_legal = datetime(2026, 6, 15, tzinfo=timezone.utc)
    outside_legal = datetime(2027, 6, 1, tzinfo=timezone.utc)

    found = await repo.load_active_rule_pack(
        environment=_ENV, effective_at=inside_legal, observed_at=inside_system
    )
    assert found is not None
    assert found["canonicalization"] == "RFC8785"
    assert found["protected"]["kid"] == "key-A"
    assert found["payload"]["note"] == "pack-A"
    # payload_sha256: 64 lowercase hex chars (Sha256Hex); signature: 86-char
    # unpadded base64url (Ed25519Signature) — the exact wire shapes
    # bundle.verify_rule_pack's schema validation requires.
    assert isinstance(found["payload_sha256"], str)
    assert len(found["payload_sha256"]) == 64
    int(found["payload_sha256"], 16)  # must be valid hex
    assert isinstance(found["signature"], str)
    assert len(found["signature"]) == 86
    assert "=" not in found["signature"]

    # effective_at OUTSIDE legal_period -> None (system clock still satisfied)
    assert (
        await repo.load_active_rule_pack(
            environment=_ENV, effective_at=outside_legal, observed_at=inside_system
        )
        is None
    )

    # observed_at BEFORE system_period start -> None (legal clock still satisfied)
    assert (
        await repo.load_active_rule_pack(
            environment=_ENV, effective_at=inside_legal, observed_at=outside_system_before
        )
        is None
    )


# --------------------------------------------------------------------------
# (test_supersession_closes_prior removed — full supersession, closing a
# prior activation and inserting the new one atomically, is the activation
# WRITER's job. That writer is deferred to STEP 6 (see this file's module
# docstring, "PR4 SCOPE"); the behavior is tested there, not here.)
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 3. GiST EXCLUDE: two activations whose legal_period AND system_period both
#    overlap for the same (environment, jurisdiction, decision_domain) must
#    raise — the DB-level guarantee ``load_active_rule_pack`` depends on for
#    "at most one active row" to be true.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_overlap_exclusion(repo: VisaEngineRepository) -> None:
    legal = _bounded_range(
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    pack_a = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_a,
        sequence=1,
        legal_period=legal,
        kid="key-A",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-A",
        payload_sha256=_pack_hash(1),
    )
    await _insert_activation_raw(
        repo, rule_pack_id=pack_a, environment=_ENV, legal_period=legal
    )

    pack_b = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_b,
        sequence=2,
        legal_period=legal,
        kid="key-B",
        signed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        note="pack-B",
        payload_sha256=_pack_hash(2),
        # Matches A's current head hash so this pack's own activation would
        # pass the hash-chain trigger too — this test's raw INSERT below
        # must fail on the EXCLUDE constraint specifically, not be masked by
        # an unrelated hash-chain rejection from the round-2 trigger.
        previous_payload_sha256=_pack_hash(1),
    )

    # A raw INSERT of a second activation with the SAME (still-open)
    # system_period AND an overlapping legal_period — this is what the
    # EXCLUDE constraint itself must reject, independent of any close-prior
    # step (which PR4 does not have — that supersession logic is STEP-6's
    # writer).
    with pytest.raises(asyncpg.exceptions.ExclusionViolationError):
        async with repo.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO visa_ruleset_activations
                    (rule_pack_id, environment, legal_period, activated_by, activation_reason)
                VALUES ($1, $2, $3, $4, $5)
                """,
                pack_b,
                _ENV,
                legal,
                "tester",
                "overlapping-activation-must-raise",
            )


# --------------------------------------------------------------------------
# 4. Append-only: a raw UPDATE/DELETE against visa_rule_packs must raise —
#    the only legitimate mutation path is INSERT (higher sequence).
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_append_only_pack(repo: VisaEngineRepository) -> None:
    pack_id = uuid.uuid4()
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-A",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-A",
        payload_sha256=_pack_hash(1),
    )

    async with repo.db_pool.acquire() as conn:
        with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
            await conn.execute(
                "UPDATE visa_rule_packs SET pack_version = 'tampered' WHERE id = $1",
                pack_id,
            )
        with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
            await conn.execute("DELETE FROM visa_rule_packs WHERE id = $1", pack_id)


# --------------------------------------------------------------------------
# 5. Empty table -> None, no exception.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_returns_none_when_empty(repo: VisaEngineRepository) -> None:
    result = await repo.load_active_rule_pack(
        environment=_ENV,
        effective_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        observed_at=datetime.now(timezone.utc),
    )
    assert result is None


# ==========================================================================
# PR4 FIX-FIRST (2026-07-19): guilt + innocence tests for the 6 P0 + 3 P1
# fixes — every test below MUST fail if the corresponding fix were reverted.
# ==========================================================================


# --------------------------------------------------------------------------
# 6. P0-1 + P1-8: insert_rule_pack must persist a genuine JSONB *object*
#    (never a double-encoded string) under EITHER pool shape, and the
#    persisted bytes must be real-world consumable by the actual trust
#    boundary (bundle.verify_rule_pack), not merely DB-shape-valid.
# --------------------------------------------------------------------------


async def _insert_activate_load_verify(repo: VisaEngineRepository) -> None:
    """Shared body for the codec-pool and codec-less-pool variants below:
    build a REAL Ed25519-signed pack, insert it via ``repo``, assert the DB
    itself sees a JSONB *object* (P0-1's structural proof), activate it,
    load it back, and feed the loaded envelope straight into
    ``bundle.verify_rule_pack`` — proving the round-trip is not just
    DB-shape-valid but actually verifies (P1-8)."""

    private_key, public_key = ephemeral_ed25519_keypair()
    payload = minimal_valid_envelope()["payload"]
    kid = "pr4-key-1"
    signed_at = "2026-07-01T00:00:00Z"
    envelope = sign_rule_pack_envelope(payload, private_key=private_key, kid=kid, signed_at=signed_at)

    valid_period = payload["valid_period"]
    legal_lower = _parse_utc_datetime(valid_period["from"])
    legal_upper = _parse_utc_datetime(valid_period["to"]) if valid_period["to"] is not None else None
    legal = asyncpg.Range(legal_lower, legal_upper, lower_inc=True, upper_inc=False)

    rule_pack_id = uuid.UUID(payload["rule_pack_id"])
    previous_sha = payload["previous_payload_sha256"]

    await repo.insert_rule_pack(
        id=rule_pack_id,
        environment=payload["environment"],
        sequence=payload["sequence"],
        pack_version=payload["version"],
        engine_contract_version=payload["engine_contract_version"],
        engine_min_version=payload["engine_min_version"],
        engine_max_version=payload["engine_max_version"],
        legal_period=legal,
        protected_header=envelope["protected"],
        payload=envelope["payload"],
        payload_sha256=bytes.fromhex(envelope["payload_sha256"]),
        previous_payload_sha256=bytes.fromhex(previous_sha) if previous_sha is not None else None,
        signature=_decode_base64url_no_padding(envelope["signature"]),
        signing_key_id=envelope["protected"]["kid"],
        signed_at=_parse_utc_datetime(envelope["protected"]["signed_at"]),
    )

    # Structural proof (P0-1): the DB itself must see JSONB *objects*, never
    # a double-encoded string — this is exactly what the bare `::jsonb` cast
    # would have gotten wrong under a codec-registered pool.
    async with repo.db_pool.acquire() as conn:
        payload_type = await conn.fetchval(
            "SELECT jsonb_typeof(payload) FROM visa_rule_packs WHERE id = $1", rule_pack_id
        )
        header_type = await conn.fetchval(
            "SELECT jsonb_typeof(protected_header) FROM visa_rule_packs WHERE id = $1", rule_pack_id
        )
    assert payload_type == "object"
    assert header_type == "object"

    await _insert_activation_raw(
        repo, rule_pack_id=rule_pack_id, environment=payload["environment"], legal_period=legal
    )

    observed_at = datetime.now(timezone.utc) + timedelta(milliseconds=5)
    loaded = await repo.load_active_rule_pack(
        environment=payload["environment"],
        effective_at=legal_lower + timedelta(days=1),
        observed_at=observed_at,
    )
    assert loaded is not None
    assert loaded["payload"]["rule_pack_id"] == payload["rule_pack_id"]

    trust_store = _trust_store_for(kid=kid, public_key=public_key, environment=payload["environment"])
    verified = verify_rule_pack(loaded, trust_store=trust_store, observed_at=observed_at)

    assert isinstance(verified, VerifiedRulePack)
    assert verified.unsigned_dev is False
    assert str(verified.pack.payload.rule_pack_id) == payload["rule_pack_id"]


@pytest.mark.asyncio
async def test_insert_stores_jsonb_object_and_verifies_production_codec_pool(
    repo_codec: VisaEngineRepository,
) -> None:
    """P0-1's actual regression surface: the PRODUCTION pool shape (jsonb
    type codec registered — mirrors ``backend/app/core/database.py``'s
    ``init_db_connection``). A bare ``$N::jsonb`` cast double-encodes here."""

    await _insert_activate_load_verify(repo_codec)


@pytest.mark.asyncio
async def test_insert_stores_jsonb_object_and_verifies_codec_less_pool(
    repo: VisaEngineRepository,
) -> None:
    """Same proof against the codec-less pool shape (this suite's own
    throwaway pool) — the fix must not regress the shape that was already
    correct before PR4."""

    await _insert_activate_load_verify(repo)


# --------------------------------------------------------------------------
# 7. P0-2: an activation's scope must be bound to its referenced pack's own
#    (environment, jurisdiction, decision_domain, legal_period) — a TEST
#    pack can never be activated as if it were PRODUCTION.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activation_env_bound_to_pack(repo: VisaEngineRepository) -> None:
    pack_id = uuid.uuid4()
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-A",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-A",
        payload_sha256=_pack_hash(1),
    )
    assert _ENV != "PRODUCTION"

    # Guilt: a raw activation whose environment does NOT match the
    # referenced pack's own environment ('TEST') must raise.
    with pytest.raises(asyncpg.exceptions.RaiseError, match="scope/legal_period must equal"):
        async with repo.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO visa_ruleset_activations
                    (rule_pack_id, environment, legal_period, activated_by, activation_reason)
                VALUES ($1, $2, $3, $4, $5)
                """,
                pack_id,
                "PRODUCTION",
                legal,
                "tester",
                "mismatched-environment-must-raise",
            )

    # Innocence: activating with the MATCHING scope succeeds — this raw
    # INSERT supplies environment=_ENV itself (PR4 ships no writer that
    # derives it from the pack; see this file's module docstring, "PR4
    # SCOPE"), but the trigger's own P0-2 binding still requires it match
    # the referenced pack's own environment regardless of what the caller
    # supplies.
    await _insert_activation_raw(
        repo, rule_pack_id=pack_id, environment=_ENV, legal_period=legal
    )


@pytest.mark.asyncio
async def test_ledger_rejects_wrong_jurisdiction(repo: VisaEngineRepository) -> None:
    """P0-2 CHECK (mirrors ``visa_rule_packs``'s own): a raw activation row
    with ``jurisdiction='US'`` must be rejected — in practice this is caught
    by the NEW scope-binding trigger before the CHECK constraint is even
    reached (a real pack's own jurisdiction is constitutionally 'ID', so any
    mismatching activation trips the trigger first), so either error class
    is an acceptable guilty verdict."""

    pack_id = uuid.uuid4()
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="key-A",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-A",
        payload_sha256=_pack_hash(1),
    )

    with pytest.raises((asyncpg.exceptions.CheckViolationError, asyncpg.exceptions.RaiseError)):
        async with repo.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO visa_ruleset_activations
                    (rule_pack_id, environment, jurisdiction, legal_period, activated_by, activation_reason)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                pack_id,
                _ENV,
                "US",
                legal,
                "tester",
                "wrong-jurisdiction-must-raise",
            )


# --------------------------------------------------------------------------
# 8. P0-3: sequence-monotonicity anti-rollback across ALL prior activations
#    for the same (environment, jurisdiction, decision_domain) triple.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activation_sequence_monotonic(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_1, pack_2, pack_3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_1,
        sequence=1,
        legal_period=legal,
        kid="key-1",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="p1",
        payload_sha256=_pack_hash(1),
    )
    await _insert_pack(
        repo,
        pack_id=pack_2,
        sequence=2,
        legal_period=legal,
        kid="key-2",
        signed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        note="p2",
        payload_sha256=_pack_hash(2),
        previous_payload_sha256=_pack_hash(1),
    )
    await _insert_pack(
        repo,
        pack_id=pack_3,
        sequence=3,
        legal_period=legal,
        kid="key-3",
        signed_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        note="p3",
        payload_sha256=_pack_hash(3),
        previous_payload_sha256=_pack_hash(2),
    )

    # Without the (deferred-to-STEP-6) writer's automatic close-prior step,
    # two OPEN (unbounded-upper) activations for the same triple would
    # collide on the GiST EXCLUDE constraint — so seq1 and seq2 are raw-
    # inserted with explicit, adjacent, non-overlapping system_period
    # ranges (mimicking what the writer would otherwise do atomically).
    t0 = datetime.now(timezone.utc)
    sp_1 = asyncpg.Range(t0, t0 + timedelta(seconds=1), lower_inc=True, upper_inc=False)
    sp_2 = asyncpg.Range(t0 + timedelta(seconds=1), None, lower_inc=True, upper_inc=False)
    await _insert_activation_raw(
        repo, rule_pack_id=pack_1, environment=_ENV, legal_period=legal, system_period=sp_1
    )
    await _insert_activation_raw(
        repo, rule_pack_id=pack_2, environment=_ENV, legal_period=legal, system_period=sp_2
    )

    # Guilt: raw-inserting pack_1 again (sequence 1, already superseded by
    # sequence 2's activation) must be rejected as a rollback attempt — the
    # sequence-monotonicity check (reject_visa_activation_insert) compares
    # against the highest-sequence pack among ALL prior activations for the
    # triple, open or closed, so it fires regardless of system_period.
    with pytest.raises(asyncpg.exceptions.RaiseError, match="rollback rejected"):
        await _insert_activation_raw(
            repo,
            rule_pack_id=pack_1,
            environment=_ENV,
            legal_period=legal,
            system_period=asyncpg.Range(
                t0 + timedelta(seconds=2), None, lower_inc=True, upper_inc=False
            ),
        )

    # The rejected attempt raised BEFORE the INSERT could ever land — pack_2's
    # activation is untouched (still open, exactly as sp_2 left it).
    async with repo.db_pool.acquire() as conn:
        pack_2_upper_before_seq3 = await conn.fetchval(
            "SELECT upper(system_period) FROM visa_ruleset_activations WHERE rule_pack_id = $1", pack_2
        )
    assert pack_2_upper_before_seq3 is None

    # Innocence: a strictly-higher-sequence pack still activates cleanly —
    # close pack_2 first (the one legal raw UPDATE the append-only-with-
    # close trigger permits), then raw-insert pack_3 into the now-vacated
    # system_period.
    close_at = t0 + timedelta(seconds=3)
    await _close_activation_raw(repo, rule_pack_id=pack_2, closed_at=close_at)
    await _insert_activation_raw(
        repo,
        rule_pack_id=pack_3,
        environment=_ENV,
        legal_period=legal,
        system_period=asyncpg.Range(close_at, None, lower_inc=True, upper_inc=False),
    )

    async with repo.db_pool.acquire() as conn:
        pack_2_upper = await conn.fetchval(
            "SELECT upper(system_period) FROM visa_ruleset_activations WHERE rule_pack_id = $1", pack_2
        )
    assert pack_2_upper is not None


# --------------------------------------------------------------------------
# (test_disjoint_legal_periods_coexist removed — the writer's decision to
# NOT close a legally-disjoint prior activation when superseding is the
# activation WRITER's job, deferred to STEP 6; see this file's module
# docstring, "PR4 SCOPE". Tested there, not here.)
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 10. P0-5: the activation ledger is append-only-with-close — DELETE always
#     rejected, UPDATE only legal as an open->closed system_period edit,
#     re-closing an already-closed row rejected.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ledger_append_only(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    pack_a, pack_b = uuid.uuid4(), uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_a,
        sequence=1,
        legal_period=legal,
        kid="key-A",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-A",
        payload_sha256=_pack_hash(1),
    )
    await _insert_pack(
        repo,
        pack_id=pack_b,
        sequence=2,
        legal_period=legal,
        kid="key-B",
        signed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        note="pack-B",
        payload_sha256=_pack_hash(2),
        previous_payload_sha256=_pack_hash(1),
    )
    t0 = datetime.now(timezone.utc)
    sp_a = asyncpg.Range(t0, None, lower_inc=True, upper_inc=False)
    await _insert_activation_raw(
        repo, rule_pack_id=pack_a, environment=_ENV, legal_period=legal, system_period=sp_a
    )

    async with repo.db_pool.acquire() as conn:
        activation_id = await conn.fetchval(
            "SELECT id FROM visa_ruleset_activations WHERE rule_pack_id = $1", pack_a
        )

        # Guilt: mutating anything other than the close carve-out must raise.
        with pytest.raises(asyncpg.exceptions.RaiseError, match="only closing an open system_period"):
            await conn.execute(
                "UPDATE visa_ruleset_activations SET rule_pack_id = $1 WHERE id = $2",
                pack_b,
                activation_id,
            )

        # Guilt (PR4 FIX-FIRST round 2, finding 5): swapping the primary key
        # ITSELF while otherwise shaping the UPDATE like a legitimate close
        # (system_period upper bound set to a finite value, nothing else
        # touched) must still raise — the round-1 OR-chain did not enumerate
        # ``id`` at all.
        with pytest.raises(asyncpg.exceptions.RaiseError, match="only closing an open system_period"):
            await conn.execute(
                """
                UPDATE visa_ruleset_activations
                SET id = gen_random_uuid(),
                    system_period = tstzrange(lower(system_period), now(), '[)')
                WHERE id = $1
                """,
                activation_id,
            )

        # Guilt: DELETE must always raise.
        with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
            await conn.execute("DELETE FROM visa_ruleset_activations WHERE id = $1", activation_id)

    # Innocence: a legitimate close (raw UPDATE narrowing the open upper
    # bound to a finite value, nothing else touched) succeeds — this is
    # exactly the one carve-out reject_visa_activation_mutation permits, and
    # exactly what STEP-6's writer will perform automatically as its
    # close-prior step. Followed by inserting pack_b's activation into the
    # now-vacated system_period, so the ledger's own head moves to pack_b.
    close_at = datetime.now(timezone.utc) + timedelta(milliseconds=5)
    await _close_activation_raw(repo, rule_pack_id=pack_a, closed_at=close_at)
    await _insert_activation_raw(
        repo,
        rule_pack_id=pack_b,
        environment=_ENV,
        legal_period=legal,
        system_period=asyncpg.Range(close_at, None, lower_inc=True, upper_inc=False),
    )

    async with repo.db_pool.acquire() as conn:
        closed_upper = await conn.fetchval(
            "SELECT upper(system_period) FROM visa_ruleset_activations WHERE id = $1", activation_id
        )
        assert closed_upper is not None

        # Guilt: re-closing an already-closed row must raise.
        with pytest.raises(asyncpg.exceptions.RaiseError, match="already closed"):
            await conn.execute(
                """
                UPDATE visa_ruleset_activations
                SET system_period = tstzrange(lower(system_period), now(), '[)')
                WHERE id = $1
                """,
                activation_id,
            )


# --------------------------------------------------------------------------
# (test_activation_periods_adjacent removed — proving the closed prior
# activation's system_period upper bound and the new activation's lower
# bound are exactly adjacent depends on the writer's single shared
# clock_timestamp() read across its close-then-insert pair, which is the
# activation WRITER's job, deferred to STEP 6; see this file's module
# docstring, "PR4 SCOPE". Tested there, not here.)
# --------------------------------------------------------------------------


# ==========================================================================
# PR4 FIX-FIRST round 2 (2026-07-19): a second cross-family adversarial gate
# found the write path still open on 5 more findings after round 1's 6 P0 +
# 3 P1. Every test below MUST fail if its corresponding round-2 fix were
# reverted. (Finding 3 — the advisory lock moved INTO the trigger itself —
# is structural/concurrency-shaped and is not independently re-asserted by
# a dedicated test here: every test above that activates more than one pack
# already exercises the trigger path the lock now guards, and a deterministic
# 2-connection race test would be flaky/slow for the marginal coverage it
# adds over the existing sequence-monotonicity and hash-chain tests below.)
# ==========================================================================


# --------------------------------------------------------------------------
# 12. Finding 1: a ``visa_rule_packs`` row's relational columns must equal
#     what its OWN signed payload declares — a row can never claim a
#     scope/sequence/identity its signed payload does not.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pack_columns_bound_to_payload(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))

    async def _insert_raw(
        pack_id: uuid.UUID,
        *,
        row_environment: str,
        row_sequence: int,
        payload_environment: str,
        payload_sequence: int,
    ) -> None:
        payload = {
            "rule_pack_id": str(pack_id),
            "environment": payload_environment,
            "sequence": payload_sequence,
            "previous_payload_sha256": None,
            "valid_period": _valid_period_for(legal),
            "note": "payload-binding-probe",
        }
        await repo.insert_rule_pack(
            id=pack_id,
            environment=row_environment,
            sequence=row_sequence,
            pack_version="1.0.0",
            engine_contract_version="1.0.0",
            engine_min_version="1.0.0",
            engine_max_version="1.0.0",
            legal_period=legal,
            protected_header=_protected_header(
                kid="key-mismatch", signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), environment=row_environment
            ),
            payload=payload,
            payload_sha256=uuid.uuid4().bytes + uuid.uuid4().bytes,
            previous_payload_sha256=None,
            signature=uuid.uuid4().bytes * 4,
            signing_key_id="key-mismatch",
            signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    async def _insert_raw_custom(pack_id: uuid.UUID, *, row_sequence: int, payload: dict) -> None:
        """Same wiring as ``_insert_raw`` above, but takes a caller-built
        ``payload`` dict verbatim — for the round-3 NULL-slip/type cases
        below, which need to OMIT a key entirely or use a non-int JSON type,
        neither of which ``_insert_raw``'s fixed argument shape can express.
        """
        await repo.insert_rule_pack(
            id=pack_id,
            environment=_ENV,
            sequence=row_sequence,
            pack_version="1.0.0",
            engine_contract_version="1.0.0",
            engine_min_version="1.0.0",
            engine_max_version="1.0.0",
            legal_period=legal,
            protected_header=_protected_header(
                kid="key-mismatch", signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), environment=_ENV
            ),
            payload=payload,
            payload_sha256=uuid.uuid4().bytes + uuid.uuid4().bytes,
            previous_payload_sha256=None,
            signature=uuid.uuid4().bytes * 4,
            signing_key_id="key-mismatch",
            signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    # Guilt: row environment='PRODUCTION' but the signed payload declares
    # environment='TEST' — the row must never be allowed to claim a scope
    # its own payload does not.
    with pytest.raises(asyncpg.exceptions.RaiseError, match="does not match signed payload environment"):
        await _insert_raw(
            uuid.uuid4(),
            row_environment="PRODUCTION",
            row_sequence=1,
            payload_environment="TEST",
            payload_sequence=1,
        )

    # Guilt: row sequence=2 but the signed payload declares sequence=1.
    with pytest.raises(asyncpg.exceptions.RaiseError, match="does not match signed payload sequence"):
        await _insert_raw(
            uuid.uuid4(),
            row_environment="TEST",
            row_sequence=2,
            payload_environment="TEST",
            payload_sequence=1,
        )

    # Innocence: row and payload agreeing on both fields inserts cleanly.
    await _insert_raw(
        uuid.uuid4(),
        row_environment="TEST",
        row_sequence=1,
        payload_environment="TEST",
        payload_sequence=1,
    )

    # --- PR4 FIX-FIRST round 3, finding 2 (P1, NULL-slip + type) ------------
    # The round-2 comparisons used bare `<>`, which is NULL for a MISSING
    # payload key (`x <> NULL` is NULL, never TRUE) — the IF never fired and
    # the mismatch silently passed. `IS DISTINCT FROM` must reject a missing
    # key exactly like an explicit mismatch.

    # Guilt: payload is MISSING the 'environment' key entirely.
    pack_missing_env = uuid.uuid4()
    payload_missing_env = {
        "rule_pack_id": str(pack_missing_env),
        "sequence": 5,
        "previous_payload_sha256": None,
        "valid_period": _valid_period_for(legal),
        "note": "missing-environment",
    }
    with pytest.raises(asyncpg.exceptions.RaiseError, match="does not match signed payload environment"):
        await _insert_raw_custom(pack_missing_env, row_sequence=5, payload=payload_missing_env)

    # Guilt: payload is MISSING the 'sequence' key entirely — a bare `<>`
    # would have returned NULL and let this through.
    pack_missing_seq = uuid.uuid4()
    payload_missing_seq = {
        "rule_pack_id": str(pack_missing_seq),
        "environment": _ENV,
        "previous_payload_sha256": None,
        "valid_period": _valid_period_for(legal),
        "note": "missing-sequence",
    }
    with pytest.raises(asyncpg.exceptions.RaiseError, match="does not match signed payload sequence"):
        await _insert_raw_custom(pack_missing_seq, row_sequence=6, payload=payload_missing_seq)

    # Guilt: payload sequence is the JSON STRING "11" while the row's own
    # sequence is the matching int 11 — a bare `("11")::bigint = 11` cast
    # would have silently accepted this; the trigger must require
    # jsonb_typeof = 'number', not merely a castable value.
    pack_string_seq = uuid.uuid4()
    payload_string_seq = {
        "rule_pack_id": str(pack_string_seq),
        "environment": _ENV,
        "sequence": "11",
        "previous_payload_sha256": None,
        "valid_period": _valid_period_for(legal),
        "note": "string-sequence",
    }
    with pytest.raises(asyncpg.exceptions.RaiseError, match="does not match signed payload sequence"):
        await _insert_raw_custom(pack_string_seq, row_sequence=11, payload=payload_string_seq)

    # --- PR4 FIX-FIRST round 4, finding 2 (P1, key-presence) ----------------
    # Round-3's IS DISTINCT FROM fix still could not tell a MISSING payload
    # key apart from an explicit JSON null (`NEW.payload->>'x'` reads back
    # NULL either way) — the contract mandates the KEY exists, so a payload
    # that OMITS it entirely must be rejected too, even for a field whose
    # legitimate VALUE is null (previous_payload_sha256's bootstrap case).

    # Guilt: payload is MISSING the 'previous_payload_sha256' key entirely
    # (not merely holding an explicit null).
    pack_missing_prev_hash = uuid.uuid4()
    payload_missing_prev_hash = {
        "rule_pack_id": str(pack_missing_prev_hash),
        "environment": _ENV,
        "sequence": 12,
        "valid_period": _valid_period_for(legal),
        "note": "missing-previous-payload-sha256-key",
    }
    with pytest.raises(
        asyncpg.exceptions.RaiseError,
        match="previous_payload_sha256 does not match signed payload",
    ):
        await _insert_raw_custom(pack_missing_prev_hash, row_sequence=12, payload=payload_missing_prev_hash)

    # Innocence: the KEY present with an explicit JSON null (the normal
    # bootstrap shape every other insert in this suite already uses) still
    # inserts cleanly — proving the fix rejects a MISSING key without also
    # rejecting the legitimate null-valued key.
    pack_bootstrap_null = uuid.uuid4()
    payload_bootstrap_null = {
        "rule_pack_id": str(pack_bootstrap_null),
        "environment": _ENV,
        "sequence": 13,
        "previous_payload_sha256": None,
        "valid_period": _valid_period_for(legal),
        "note": "bootstrap-explicit-null-previous-payload-sha256",
    }
    await _insert_raw_custom(pack_bootstrap_null, row_sequence=13, payload=payload_bootstrap_null)


# --------------------------------------------------------------------------
# 13. Finding 2: DB-level hash-chain enforcement — an activating pack's
#     ``previous_payload_sha256`` must equal the CURRENT head activation's
#     own pack's ``payload_sha256`` for the same triple (stored-bytes
#     comparison, not cryptography — this is why it belongs in the trigger).
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activation_hash_chain_enforced(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    hash_a, hash_b = _pack_hash(1), _pack_hash(2)

    pack_a = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_a,
        sequence=1,
        legal_period=legal,
        kid="key-A",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-A",
        payload_sha256=hash_a,
    )
    # Explicit, adjacent, non-overlapping system_period ranges — without the
    # (deferred-to-STEP-6) writer's automatic close-prior step, two OPEN
    # activations for the same triple would collide on the GiST EXCLUDE
    # constraint.
    t0 = datetime.now(timezone.utc)
    sp_a = asyncpg.Range(t0, t0 + timedelta(seconds=1), lower_inc=True, upper_inc=False)
    await _insert_activation_raw(
        repo, rule_pack_id=pack_a, environment=_ENV, legal_period=legal, system_period=sp_a
    )

    pack_b = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_b,
        sequence=2,
        legal_period=legal,
        kid="key-B",
        signed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        note="pack-B",
        payload_sha256=hash_b,
        previous_payload_sha256=hash_a,
    )
    sp_b = asyncpg.Range(t0 + timedelta(seconds=1), None, lower_inc=True, upper_inc=False)
    await _insert_activation_raw(
        repo, rule_pack_id=pack_b, environment=_ENV, legal_period=legal, system_period=sp_b
    )

    # Guilt: pack_c's previous_payload_sha256 points at hash_a (A) instead of
    # the CURRENT head's hash (B's hash_b) — the chain skips a link.
    # (sequence=3, distinct from pack_b's sequence=2, to satisfy the pack
    # table's own UNIQUE(environment, jurisdiction, decision_domain,
    # sequence) constraint at INSERT time — the pack row itself inserts
    # fine regardless of chain correctness; only its ACTIVATION is chain-
    # checked.)
    pack_c_wrong = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_c_wrong,
        sequence=3,
        legal_period=legal,
        kid="key-C-wrong",
        signed_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        note="pack-C-wrong",
        payload_sha256=_pack_hash(3),
        previous_payload_sha256=hash_a,
    )
    with pytest.raises(asyncpg.exceptions.RaiseError, match="hash chain broken"):
        await _insert_activation_raw(
            repo, rule_pack_id=pack_c_wrong, environment=_ENV, legal_period=legal
        )

    # Innocence: a pack whose previous_payload_sha256 correctly points at the
    # CURRENT head (hash_b — pack_c_wrong's activation above raised before
    # ever landing, so B is still head) activates cleanly. sequence=4
    # (not 3) because pack_c_wrong already claimed sequence=3 in this
    # environment/jurisdiction/domain triple. B's activation (sp_b) is still
    # OPEN, so pack_c_ok's raw insert must close it first (the one legal
    # UPDATE the append-only-with-close trigger permits).
    pack_c_ok = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_c_ok,
        sequence=4,
        legal_period=legal,
        kid="key-C-ok",
        signed_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        note="pack-C-ok",
        payload_sha256=_pack_hash(4),
        previous_payload_sha256=hash_b,
    )
    close_at = t0 + timedelta(seconds=2)
    await _close_activation_raw(repo, rule_pack_id=pack_b, closed_at=close_at)
    await _insert_activation_raw(
        repo,
        rule_pack_id=pack_c_ok,
        environment=_ENV,
        legal_period=legal,
        system_period=asyncpg.Range(close_at, None, lower_inc=True, upper_inc=False),
    )


# --------------------------------------------------------------------------
# (test_partial_legal_overlap_rejected removed — deciding whether a
# candidate's legal_period partially overlaps an open prior activation
# (and refusing to close it if so) is the activation WRITER's job, deferred
# to STEP 6; see this file's module docstring, "PR4 SCOPE". Tested there,
# not here.)
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 15. Finding 6a: an explicit '-infinity' legal_period LOWER bound is
#     rejected by CHECK on BOTH tables (P1-9, already in migration 250's
#     round-1 amendments — this test proves it, which round 1 had not).
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_infinity_legal_lower_rejected(repo: VisaEngineRepository) -> None:
    # (a) visa_rule_packs: an explicit '-infinity' legal_period lower bound,
    # via a raw INSERT (repo.insert_rule_pack takes an asyncpg.Range, which
    # has no clean way to express the Postgres '-infinity' *value* as
    # distinct from an unbounded/NULL endpoint — NULL is NOT '-infinity' to
    # this CHECK, see (b)'s comment below).
    pack_id = uuid.uuid4()
    # valid_period matches the row's own tstzrange('-infinity', 2027-01-01, '[)')
    # below EXACTLY (round 3, finding 1 binds legal_period to valid_period too) —
    # Postgres' timestamptz cast accepts the literal string '-infinity', so this
    # is the one case where the payload's "from" is not a normal ISO instant.
    # Without this match, the round-3 trigger's own RaiseError would fire before
    # the CHECK constraint is ever reached, and this test would see the WRONG
    # exception type.
    payload_json = json.dumps(
        {
            "rule_pack_id": str(pack_id),
            "environment": _ENV,
            "sequence": 1,
            "previous_payload_sha256": None,
            "valid_period": {
                "from": "-infinity",
                "to": datetime(2027, 1, 1, tzinfo=timezone.utc).isoformat(),
            },
            "note": "pack-infinity",
        }
    )
    protected_json = json.dumps(
        _protected_header(kid="key-inf", signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    )
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        async with repo.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO visa_rule_packs (
                    id, environment, sequence, pack_version, engine_contract_version,
                    engine_min_version, engine_max_version, legal_period, protected_header,
                    payload, payload_sha256, previous_payload_sha256, signature,
                    signing_key_id, signed_at
                ) VALUES (
                    $1, $2, 1, '1.0.0', '1.0.0', '1.0.0', '1.0.0',
                    tstzrange('-infinity', $3, '[)'),
                    $4::text::jsonb, $5::text::jsonb, $6, NULL, $7, $8, $9
                )
                """,
                pack_id,
                _ENV,
                datetime(2027, 1, 1, tzinfo=timezone.utc),
                protected_json,
                payload_json,
                uuid.uuid4().bytes + uuid.uuid4().bytes,
                uuid.uuid4().bytes * 4,
                "key-inf",
                datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

    # (b) visa_ruleset_activations: the table's OWN CHECK, exercised with
    # the round-2 scope-binding/hash-chain trigger temporarily disabled.
    # This is necessary, not a workaround-of-convenience: (a) already proves
    # NO pack can ever hold an infinite legal_period, and the trigger binds
    # every activation's legal_period to EXACTLY equal its referenced pack's
    # (own, already-non-infinite) legal_period BEFORE the CHECK constraint
    # is even evaluated (BEFORE ROW triggers run before CHECK, verified
    # empirically against live Postgres) — so through the normal trigger
    # path this CHECK could never fire at all. Disabling the trigger for
    # this one raw INSERT proves the table's CHECK constraint itself still
    # stands on its own, independent of the trigger.
    pack_id_valid = uuid.uuid4()
    legal_valid = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    await _insert_pack(
        repo,
        pack_id=pack_id_valid,
        sequence=1,
        legal_period=legal_valid,
        kid="key-valid",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="pack-valid",
        payload_sha256=_pack_hash(1),
    )
    async with repo.db_pool.acquire() as conn:
        await conn.execute("ALTER TABLE visa_ruleset_activations DISABLE TRIGGER visa_activation_insert_guard")
        try:
            # migration 251: activated_by_principal is NOT NULL and is
            # normally stamped by the (here, deliberately disabled) insert-
            # guard trigger itself — with the trigger off, this raw INSERT
            # must supply it explicitly so the statement reaches the
            # table's own legal_period CHECK (what this test proves) rather
            # than failing earlier on the unrelated NOT NULL constraint.
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                await conn.execute(
                    """
                    INSERT INTO visa_ruleset_activations
                        (rule_pack_id, environment, legal_period, activated_by, activation_reason,
                         activated_by_principal)
                    VALUES ($1, $2, tstzrange('-infinity', $3, '[)'), $4, $5, $6)
                    """,
                    pack_id_valid,
                    _ENV,
                    datetime(2027, 1, 1, tzinfo=timezone.utc),
                    "tester",
                    "infinite-legal-lower-must-raise",
                    "tester-principal-trigger-disabled",
                )
        finally:
            await conn.execute(
                "ALTER TABLE visa_ruleset_activations ENABLE TRIGGER visa_activation_insert_guard"
            )


# ==========================================================================
# PR4 FIX-FIRST round 3 (2026-07-19): a third cross-family adversarial gate
# closed 5 of 6 round-2 findings; the pack-payload-binding trigger itself
# still had two: the row's legal_period was NOT bound to the signed
# payload's valid_period (P0 — a validly-signed BOUNDED pack could be
# inserted as an OPEN-ENDED row, and load_active_rule_pack would then serve
# its rules forever past what was actually signed), and the id/environment/
# sequence comparisons used bare `<>`/`=`, which a MISSING payload key or a
# JSON-STRING sequence silently slipped through (P1). The test below MUST
# fail if the legal_period binding were reverted; the NULL-slip/type cases
# live as extensions of test_pack_columns_bound_to_payload above.
# ==========================================================================


# --------------------------------------------------------------------------
# 16. Round-3 finding 1 (P0): a visa_rule_packs row's legal_period must equal
#     the tstzrange its OWN signed payload's valid_period declares — a row
#     can never claim a legally-in-force window WIDER than what was signed.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pack_legal_period_bound_to_payload(repo: VisaEngineRepository) -> None:
    async def _insert_raw(
        *,
        pack_id: uuid.UUID,
        legal_period: asyncpg.Range,
        valid_period: dict,
    ) -> None:
        payload = {
            "rule_pack_id": str(pack_id),
            "environment": _ENV,
            "sequence": 1,
            "previous_payload_sha256": None,
            "valid_period": valid_period,
            "note": "legal-period-binding-probe",
        }
        await repo.insert_rule_pack(
            id=pack_id,
            environment=_ENV,
            sequence=1,
            pack_version="1.0.0",
            engine_contract_version="1.0.0",
            engine_min_version="1.0.0",
            engine_max_version="1.0.0",
            legal_period=legal_period,
            protected_header=_protected_header(
                kid="key-legal", signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), environment=_ENV
            ),
            payload=payload,
            payload_sha256=uuid.uuid4().bytes + uuid.uuid4().bytes,
            previous_payload_sha256=None,
            signature=uuid.uuid4().bytes * 4,
            signing_key_id="key-legal",
            signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    # Guilt: the row claims an OPEN-ENDED legal_period [2026, infinity) while
    # its own signed payload's valid_period declares a BOUNDED [2026, 2027) —
    # letting this through would let load_active_rule_pack serve this pack's
    # rules forever, long past what was actually signed (Codex proved this
    # concretely: compile_ok=True, rules still active at effective_at=2029).
    with pytest.raises(
        asyncpg.exceptions.RaiseError, match="does not match signed payload valid_period"
    ):
        await _insert_raw(
            pack_id=uuid.uuid4(),
            legal_period=_open_range(datetime(2026, 1, 1, tzinfo=timezone.utc)),
            valid_period={"from": "2026-01-01T00:00:00Z", "to": "2027-01-01T00:00:00Z"},
        )

    # Innocence: row legal_period EXACTLY equal to the payload's valid_period
    # (both open-ended here) inserts cleanly — this is already the norm
    # elsewhere in this suite (every _insert_pack call derives valid_period
    # FROM legal_period via _valid_period_for), asserted directly here too.
    await _insert_raw(
        pack_id=uuid.uuid4(),
        legal_period=_open_range(datetime(2026, 1, 1, tzinfo=timezone.utc)),
        valid_period={"from": "2026-01-01T00:00:00Z", "to": None},
    )

    # --- PR4 FIX-FIRST round 4, finding 2 (P1, key-presence) ----------------
    # Guilt: valid_period is MISSING the 'to' key entirely (not merely
    # holding an explicit null) — the contract mandates BOTH 'from' and 'to'
    # keys are present even when "to" is open-ended. Deliberately pairs this
    # payload with an OPEN-ENDED legal_period (matching what an implicit
    # null "to" would otherwise produce): without the round-4 key-presence
    # check, the round-3 tstzrange-equality comparison alone would treat a
    # missing "to" the same as an explicit null and let this through —
    # only the explicit `? 'to'` check catches it.
    with pytest.raises(
        asyncpg.exceptions.RaiseError, match="does not match signed payload valid_period"
    ):
        await _insert_raw(
            pack_id=uuid.uuid4(),
            legal_period=_open_range(datetime(2026, 1, 1, tzinfo=timezone.utc)),
            valid_period={"from": "2026-01-01T00:00:00Z"},  # 'to' key omitted entirely
        )
