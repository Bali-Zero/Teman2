"""`naga_backfill` against a real `postgres:15` -- dry-run/apply on a legacy-shaped `naga_claims`
table, migrations 279+280+312 applied forward exactly as
`test_migration_312_research_os_naga_claims.py`'s own `db` fixture does, plus a minimal
`naga_claims` table shaped like `services/naga/persist.py`'s own INSERT column list
(migrations 079/081, measured on disk).

LOCAL RUN (this slice's own docker container, `r2-dux-verify-pg`, port 55434):
    TEST_DATABASE_URL=postgresql://test:test@localhost:55434/nuzantara_test \\
        PYTHONPATH=.:../.. pytest backend/tests/services/research_os/naga/test_naga_backfill_pg.py -q
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from research_os.hashing import object_hash as _real_object_hash
from research_os.version import CONTRACT_VERSION

from backend.db.migration_base import split_migration_sql
from backend.services.research_os import naga_backfill as nb

pytestmark = pytest.mark.integration

MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "db" / "migrations_v2"

_LEGACY_TABLE_SQL = """
CREATE TABLE naga_claims (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID,
    claim_text          TEXT NOT NULL,
    claim_key           VARCHAR(255),
    domain              VARCHAR(20),
    verification_level  VARCHAR(20),
    confidence          FLOAT,
    cross_ref_count     INT DEFAULT 0,
    review_status       VARCHAR(20) DEFAULT 'auto_extracted',
    valid_as_of         DATE,
    expires_at          DATE,
    quality_score       FLOAT,
    claim_status        VARCHAR(20) DEFAULT 'active'
);
"""


def _dsn() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL", "postgresql://test:test@localhost:55434/nuzantara_test"
    )


def _forward(name: str) -> str:
    forward, _ = split_migration_sql((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))
    return forward


@pytest.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(_dsn())
    try:
        await conn.execute("SELECT pg_advisory_lock(hashtext('r2-naga-backfill-pg-test'))")
        await conn.execute(
            """
            DROP TABLE IF EXISTS research_os_naga_admission, research_os_objects, naga_claims
                CASCADE;
            DROP FUNCTION IF EXISTS public.research_os_instant_key(text);
            DROP FUNCTION IF EXISTS public.reject_research_os_naga_admission_mutation();
            DROP FUNCTION IF EXISTS public.reject_research_os_objects_mutation();
            """
        )
        async with conn.transaction():
            await conn.execute(_forward("279_research_os_contract_core.sql"))
            await conn.execute(_forward("280_research_os_objects_truncate_guard.sql"))
            await conn.execute(_forward("312_research_os_naga_claims.sql"))
            await conn.execute(_LEGACY_TABLE_SQL)
        yield conn
    finally:
        await conn.execute("SELECT pg_advisory_unlock(hashtext('r2-naga-backfill-pg-test'))")
        await conn.close()


async def _seed_legacy_rows(conn: asyncpg.Connection, count: int) -> list[str]:
    ids: list[str] = []
    for i in range(count):
        row_id = await conn.fetchval(
            """
            INSERT INTO naga_claims
                (claim_text, claim_key, domain, verification_level, confidence,
                 cross_ref_count, review_status, valid_as_of, expires_at,
                 quality_score, claim_status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, CURRENT_DATE, CURRENT_DATE + 30, $8, $9)
            RETURNING id
            """,
            f"legacy claim body #{i}",
            f"claim-key-{i}",
            "tax",
            "unverified",
            0.4,
            0,
            "auto_extracted",
            0.5,
            "active",
        )
        ids.append(str(row_id))
    return ids


async def _counts(conn: asyncpg.Connection) -> dict[str, int]:
    return {
        "naga_claims": await conn.fetchval("SELECT count(*) FROM naga_claims"),
        "research_os_objects": await conn.fetchval("SELECT count(*) FROM research_os_objects"),
        "research_os_naga_admission": await conn.fetchval(
            "SELECT count(*) FROM research_os_naga_admission"
        ),
    }


# --------------------------------------------------------------------------------------------
# Dry-run on 5 legacy-shaped rows -- expected zero admitted (D4, R2-build-spec.md section 6.1).
# --------------------------------------------------------------------------------------------


async def test_dry_run_admits_nothing_and_writes_nothing(db: asyncpg.Connection) -> None:
    await _seed_legacy_rows(db, 5)
    before = await _counts(db)

    report = await nb.run_dry_run(db, cohort=nb.PRODUCTION_COHORT)

    assert report.legacy_rows_read == 5
    assert report.admitted == 0
    assert report.excluded == 5
    assert report.excluded_by_reason == {"statement_not_from_source": 5}
    claim_counts = report.kind_counts["claim"]
    assert claim_counts.eligible == 0
    assert claim_counts.inserted == 0
    assert claim_counts.already_present == 0
    assert claim_counts.excluded == 5
    assert claim_counts.rejected == 0
    for kind in ("evidence", "object_successor_edge", "intel_event"):
        assert report.kind_counts[kind] == nb.KindCounts()

    after = await _counts(db)
    assert after == before
    assert after["research_os_objects"] == 0
    assert after["research_os_naga_admission"] == 0
    assert after["naga_claims"] == 5


async def test_dry_run_twice_yields_identical_manifest_hash(db: asyncpg.Connection) -> None:
    await _seed_legacy_rows(db, 3)
    report1 = await nb.run_dry_run(db, cohort=nb.PRODUCTION_COHORT)
    report2 = await nb.run_dry_run(db, cohort=nb.PRODUCTION_COHORT)
    assert report1.manifest_hash == report2.manifest_hash
    assert report1.source_snapshot_hash == report2.source_snapshot_hash


# --------------------------------------------------------------------------------------------
# Apply refusals -- source snapshot drift, zero writes either way.
# --------------------------------------------------------------------------------------------


async def test_apply_with_wrong_manifest_refuses_and_writes_nothing(
    db: asyncpg.Connection,
) -> None:
    await _seed_legacy_rows(db, 5)
    before = await _counts(db)
    wrong_manifest = "0" * 64

    with pytest.raises(nb.SourceSnapshotDrifted):
        await nb.run_apply(db, cohort=nb.PRODUCTION_COHORT, manifest=wrong_manifest)

    assert await _counts(db) == before


async def test_apply_after_mutating_a_row_refuses_the_stale_manifest(
    db: asyncpg.Connection,
) -> None:
    ids = await _seed_legacy_rows(db, 5)
    stale = await nb.run_dry_run(db, cohort=nb.PRODUCTION_COHORT)

    await db.execute(
        "UPDATE naga_claims SET claim_text = 'mutated body' WHERE id = $1::uuid", ids[0]
    )
    before = await _counts(db)

    with pytest.raises(nb.SourceSnapshotDrifted) as excinfo:
        await nb.run_apply(db, cohort=nb.PRODUCTION_COHORT, manifest=stale.manifest_hash)
    assert excinfo.value.given == stale.manifest_hash
    assert excinfo.value.computed != stale.manifest_hash

    assert await _counts(db) == before


async def test_apply_with_the_recomputed_correct_manifest_on_all_excluded_cohort_writes_zero(
    db: asyncpg.Connection,
) -> None:
    await _seed_legacy_rows(db, 5)
    fresh = await nb.run_dry_run(db, cohort=nb.PRODUCTION_COHORT)
    before = await _counts(db)

    report = await nb.run_apply(db, cohort=nb.PRODUCTION_COHORT, manifest=fresh.manifest_hash)

    assert report.admitted == 0
    assert report.written == ()
    assert report.kind_counts["claim"].inserted == 0
    after = await _counts(db)
    assert after == before
    assert after["research_os_objects"] == 0
    assert after["research_os_naga_admission"] == 0


# --------------------------------------------------------------------------------------------
# An admitted record path, driven at the internal-function level with a fake admission input
# that carries a canonical claim payload (naga_claims itself never has one) -- exercised against
# the real database so the write, the idempotent replay and the row counts are all observed.
# --------------------------------------------------------------------------------------------


def _fake_claim_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "claim_id": str(uuid.uuid4()),
        "claim_family_id": str(uuid.uuid4()),
        "contract_version": CONTRACT_VERSION,
        "tenant": "bali-zero",
        "statement": {
            "subject_ref": {
                "object_kind": "regulation",
                "object_id": "reg-1",
                "object_hash": "a" * 64,
            },
            "predicate": "naga.has-fee",
            "object_ref_or_value": 100.0,
        },
        "scope": {"domain": "tax"},
        "time": {"recorded_at": "2026-01-01T00:00:00Z"},
        "status": "supported",
        "evidence_refs": [],
        "confidence": {"score": 0.9, "method": "manual"},
        "classification": {"risk_class": "green", "sensitivity": "public"},
        "review": {"state": "unreviewed"},
        "lineage": {
            "run_id": str(uuid.uuid4()),
            "extractor": "naga.legacy",
            "input_claim_refs": [],
        },
        "retention": {"retention_class": "operational", "legal_hold": False},
    }
    base.update(overrides)
    base["object_hash"] = _real_object_hash(base)
    return base


async def test_execute_apply_writes_an_admitted_record_once_then_zero_on_replay(
    db: asyncpg.Connection,
) -> None:
    from backend.services.research_os.naga_admission import Admitted

    payload = _fake_claim_payload()
    legacy_row = {"id": "fake-legacy-1", "canonical_claim_payload": payload}
    decision = Admitted(legacy_claim_id="fake-legacy-1", family_id=payload["claim_family_id"])
    manifest_hash = "1" * 64
    source_snapshot_hash = "2" * 64

    before = await _counts(db)

    outcome1 = await nb._execute_apply(
        db,
        manifest_hash=manifest_hash,
        source_snapshot_hash=source_snapshot_hash,
        rows=[legacy_row],
        decisions=[decision],
    )
    assert outcome1.kind_counts["claim"].inserted == 1
    assert outcome1.kind_counts["claim"].already_present == 0
    assert outcome1.written == ((payload["claim_id"], payload["object_hash"]),)

    mid = await _counts(db)
    assert mid["research_os_objects"] == before["research_os_objects"] + 1
    assert mid["research_os_naga_admission"] == before["research_os_naga_admission"] + 1
    assert mid["naga_claims"] == before["naga_claims"]

    outcome2 = await nb._execute_apply(
        db,
        manifest_hash=manifest_hash,
        source_snapshot_hash=source_snapshot_hash,
        rows=[legacy_row],
        decisions=[decision],
    )
    assert outcome2.kind_counts["claim"].inserted == 0
    assert outcome2.kind_counts["claim"].already_present == 1
    assert outcome2.written == ()

    after = await _counts(db)
    assert after == mid

    stored = await db.fetchrow(
        "SELECT object_hash FROM research_os_objects WHERE object_id = $1", payload["claim_id"]
    )
    assert stored["object_hash"] == payload["object_hash"]

    admission_row = await db.fetchrow(
        "SELECT decision, claim_object_id, claim_object_hash, run_id "
        "FROM research_os_naga_admission WHERE legacy_claim_id = 'fake-legacy-1'"
    )
    assert admission_row["decision"] == "admitted"
    assert admission_row["claim_object_id"] == payload["claim_id"]
    assert admission_row["claim_object_hash"] == payload["object_hash"]
    assert admission_row["run_id"] == manifest_hash


async def test_execute_apply_rejects_an_admitted_decision_with_no_canonical_payload(
    db: asyncpg.Connection,
) -> None:
    from backend.services.research_os.naga_admission import Admitted

    legacy_row = {"id": "fake-legacy-no-payload"}  # no canonical_claim_payload key at all
    decision = Admitted(legacy_claim_id="fake-legacy-no-payload", family_id="fam-x")
    before = await _counts(db)

    outcome = await nb._execute_apply(
        db,
        manifest_hash="3" * 64,
        source_snapshot_hash="4" * 64,
        rows=[legacy_row],
        decisions=[decision],
    )

    assert outcome.kind_counts["claim"].rejected == 1
    assert outcome.kind_counts["claim"].inserted == 0
    assert outcome.written == ()
    assert await _counts(db) == before
