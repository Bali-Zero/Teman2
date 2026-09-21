"""`intel_evidence_bridge`'s `--apply` write path -- against a real, disposable Postgres.

Never PROD. This suite creates and migrates its OWN throwaway database (`_ensure_database`),
distinct from `nuzantara_test`/whatever `test_naga_backfill_pg.py`'s own `TEST_DATABASE_URL`
points at, so it cannot collide with a sibling agent's concurrent run of that suite on the same
shared local Postgres (`intel_items` is this suite's own table; `research_os_objects` /
`research_os_naga_admission` are migrated fresh, same migrations 279/280/312
`test_naga_backfill_pg.py` applies, guarded by this suite's OWN advisory lock name).

LOCAL RUN:
    TEST_DATABASE_URL=postgresql://test:test@127.0.0.1:5432/intel_evidence_bridge_apply_test \\
        PYTHONPATH=.:../.. pytest backend/tests/services/research_os/naga/test_intel_evidence_bridge_apply_pg.py -q

Six tests, each with its own guilt control (per the mandate: a test that goes green without
ever going red first proves nothing):

1. idempotency -- a second `--apply` of the same manifest writes 0 new rows in either table.
   One admitted item now writes TWO `research_os_objects` rows (`evidence` + `claim`).
2. manifest drift -- mutating a seeded row AFTER the dry-run and BEFORE `--apply` must flip the
   recomputed manifest and trigger `SourceSnapshotDrifted`, zero writes.
3. the cap -- a synthetic 67-candidate cohort (`ADMITTED_ROW_CAP + 1`) must refuse by name,
   never truncate to the first 66; the row count is asserted, not just the exception.
4. atomicity -- a hand-built `AdmissionRow` that violates `research_os_naga_admission`'s own
   CHECK constraint must roll back the `research_os_objects` insert `_execute_apply` already
   performed inside the same transaction.
5. `--dry-run` never writes.
6. canonical schema gate -- a `claim` payload missing a REQUIRED `Claim` field (`confidence`)
   must be refused by `CanonicalSchemaInvalid`, naming the field, before any write -- proving
   `run_apply` never writes an object whose `object_kind` lies about what it is.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from research_os.hashing import object_hash as _real_object_hash
from research_os.version import CONTRACT_VERSION

from backend.db.migration_base import split_migration_sql
from backend.services.research_os import intel_evidence_bridge as ieb
from backend.services.research_os.naga_persistence import AdmissionRow, ObjectWrite

pytestmark = pytest.mark.integration

MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "db" / "migrations_v2"

#: A minimal, hand-written `intel_items` shape -- the four columns `intel_evidence_bridge`
#: reads plus the NOT NULL columns migration 168's real table requires, WITHOUT its
#: `events_outbox`-dependent notify trigger (migration 146, irrelevant to this write path and
#: not worth pulling in as a dependency -- same simplification `test_naga_backfill_pg.py`'s own
#: hand-written `naga_claims` table makes for its legacy shape).
_INTEL_ITEMS_TABLE_SQL = """
CREATE TABLE intel_items (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_url     TEXT UNIQUE NOT NULL,
    content_hash      TEXT NOT NULL,
    title             TEXT NOT NULL,
    summary           TEXT,
    source_domain     TEXT NOT NULL,
    language          TEXT,
    jurisdiction      TEXT,
    topic_tags        TEXT[] NOT NULL DEFAULT '{}',
    routing_status    TEXT NOT NULL DEFAULT 'unrouted',
    routing_targets   JSONB NOT NULL DEFAULT '{}',
    confidence_score  REAL,
    first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at      TIMESTAMPTZ,
    expires_at        TIMESTAMPTZ,
    raw_payload       JSONB NOT NULL DEFAULT '{}'
);
"""

#: This suite's own advisory-lock name -- distinct from `r2-naga-backfill-pg-test` /
#: `r2-lane-c-naga-persistence-pg` / `r2-lane-c-naga-reader-pg`, since this suite touches its own
#: dedicated database, not a table set shared with those suites.
_LOCK_NAME = "r2-intel-evidence-bridge-apply-pg-test"


def _dsn() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://test:test@127.0.0.1:5432/intel_evidence_bridge_apply_test",
    )


def _forward(name: str) -> str:
    forward, _ = split_migration_sql((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))
    return forward


async def _ensure_database(dsn: str) -> None:
    """`CREATE DATABASE` cannot run inside a transaction or against the database it targets --
    connect to `postgres` (same host/creds) and create this suite's own database if missing."""

    parts = urlsplit(dsn)
    db_name = parts.path.lstrip("/")
    admin_dsn = urlunsplit((parts.scheme, parts.netloc, "/postgres", parts.query, parts.fragment))
    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


@pytest.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    dsn = _dsn()
    await _ensure_database(dsn)
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(f"SELECT pg_advisory_lock(hashtext('{_LOCK_NAME}'))")
        await conn.execute(
            """
            DROP TABLE IF EXISTS research_os_naga_admission, research_os_objects, intel_items
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
            await conn.execute(_INTEL_ITEMS_TABLE_SQL)
        yield conn
    finally:
        await conn.execute(f"SELECT pg_advisory_unlock(hashtext('{_LOCK_NAME}'))")
        await conn.close()


async def _seed_intel_item(
    conn: asyncpg.Connection,
    *,
    canonical_url: str,
    citation: str,
    verbatim_excerpt: str,
    published_at: datetime,
) -> str:
    """A row shaped exactly like a fully-sourced `regulatory_watcher` item -- all four fields
    `bridge()` needs, citation a delimited literal token of its own excerpt, so `admit()` has no
    reason to exclude it (mirrors the real 8-admitted cohort's own shape, synthetically)."""

    row_id = await conn.fetchval(
        """
        INSERT INTO intel_items
            (canonical_url, content_hash, title, source_domain, published_at, raw_payload)
        VALUES ($1, $2, $3, 'example.invalid', $4, $5::text::jsonb)
        RETURNING id
        """,
        canonical_url,
        hashlib.sha256(canonical_url.encode("utf-8")).hexdigest(),
        f"synthetic regulatory item for {canonical_url}",
        published_at,
        json.dumps({"verbatim_excerpt": verbatim_excerpt, "citation": citation}),
    )
    return str(row_id)


async def _counts(conn: asyncpg.Connection) -> dict[str, int]:
    return {
        "intel_items": await conn.fetchval("SELECT count(*) FROM intel_items"),
        "research_os_objects": await conn.fetchval("SELECT count(*) FROM research_os_objects"),
        "research_os_naga_admission": await conn.fetchval(
            "SELECT count(*) FROM research_os_naga_admission"
        ),
    }


# --------------------------------------------------------------------------------------------
# 1. Idempotency.
# --------------------------------------------------------------------------------------------


async def test_apply_twice_on_the_same_manifest_writes_zero_the_second_time(
    db: asyncpg.Connection,
) -> None:
    await _seed_intel_item(
        db,
        canonical_url="https://example.invalid/reg-idempotent",
        citation="PMK 1/2026",
        verbatim_excerpt="Sesuai dengan PMK 1/2026, ketentuan berlaku efektif mulai Januari.",
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    dry = await ieb.run_dry_run(db)
    assert dry.admitted == 1, dry.excluded_by_reason

    before = await _counts(db)
    report1 = await ieb.run_apply(db, manifest=dry.manifest_hash)
    # One admitted item -> one `evidence` object + one `claim` object that cites it.
    assert report1.objects_inserted == 2
    assert report1.objects_already_present == 0
    assert report1.admissions_inserted == 1
    assert {kind for kind, _, _ in report1.written} == {"evidence", "claim"}
    mid = await _counts(db)
    assert mid["research_os_objects"] == before["research_os_objects"] + 2
    assert mid["research_os_naga_admission"] == before["research_os_naga_admission"] + 1

    report2 = await ieb.run_apply(db, manifest=dry.manifest_hash)
    assert report2.objects_inserted == 0
    assert report2.objects_already_present == 2
    assert report2.admissions_inserted == 0
    assert report2.written == ()

    after = await _counts(db)
    assert after == mid


# --------------------------------------------------------------------------------------------
# 2. Manifest drift -- a row mutated after the dry-run must be caught, not silently written.
# --------------------------------------------------------------------------------------------


async def test_apply_after_mutating_a_row_refuses_the_stale_manifest(
    db: asyncpg.Connection,
) -> None:
    item_id = await _seed_intel_item(
        db,
        canonical_url="https://example.invalid/reg-drift",
        citation="PMK 2/2026",
        verbatim_excerpt="Sesuai dengan PMK 2/2026, ketentuan berlaku efektif mulai Februari.",
        published_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    stale = await ieb.run_dry_run(db)
    assert stale.admitted == 1

    # RED control: mutate the very field the manifest binds (the citation, inside raw_payload)
    # after the dry-run was signed. A bridge/manifest pair that ignored this would let `--apply`
    # write against data the caller never actually reviewed.
    await db.execute(
        "UPDATE intel_items SET raw_payload = raw_payload || '{\"citation\": \"PMK 999/2026\"}'::jsonb "
        "WHERE id = $1::uuid",
        item_id,
    )
    before = await _counts(db)

    with pytest.raises(ieb.SourceSnapshotDrifted) as excinfo:
        await ieb.run_apply(db, manifest=stale.manifest_hash)

    assert excinfo.value.given == stale.manifest_hash
    assert excinfo.value.computed != stale.manifest_hash
    assert await _counts(db) == before
    assert (await _counts(db))["research_os_objects"] == 0


# --------------------------------------------------------------------------------------------
# 3. The cap is a refusal, never a truncation.
# --------------------------------------------------------------------------------------------


async def test_apply_refuses_a_cohort_past_the_admitted_row_cap_and_writes_nothing(
    db: asyncpg.Connection,
) -> None:
    candidate_count = ieb.ADMITTED_ROW_CAP + 1  # 67
    for i in range(candidate_count):
        await _seed_intel_item(
            db,
            canonical_url=f"https://example.invalid/reg-cap-{i}",
            citation=f"PMK {i}/2026",
            verbatim_excerpt=f"Sesuai dengan PMK {i}/2026, ketentuan berlaku efektif segera.",
            published_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    dry = await ieb.run_dry_run(db)
    assert dry.admitted == candidate_count, dry.excluded_by_reason

    before = await _counts(db)
    with pytest.raises(ieb.AdmittedCohortExceedsCap) as excinfo:
        await ieb.run_apply(db, manifest=dry.manifest_hash)

    assert excinfo.value.admitted == candidate_count
    assert excinfo.value.cap == ieb.ADMITTED_ROW_CAP
    after = await _counts(db)
    assert after == before
    assert after["research_os_objects"] == 0
    assert after["research_os_naga_admission"] == 0


# --------------------------------------------------------------------------------------------
# 4. Atomicity -- a failure recording the SECOND table rolls back the FIRST table's insert.
# --------------------------------------------------------------------------------------------


async def test_a_failed_admission_row_rolls_back_the_object_it_was_paired_with(
    db: asyncpg.Connection,
) -> None:
    claim_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "document_id": "https://example.invalid/reg-atomic",
        "contract_version": CONTRACT_VERSION,
        "tenant": "bali-zero",
        "claim_id": claim_id,
    }
    payload["object_hash"] = _real_object_hash(payload)
    write = ObjectWrite(object_kind="claim", object_id=claim_id, payload=payload)

    # RED control: `claim_object_id`/`claim_object_hash` are `None` on a `decision="admitted"`
    # row, which violates `research_os_naga_admission_admitted_has_identity_no_reason` (migration
    # 312) -- a real CHECK, not a fabricated one, so this proves the SAME constraint production
    # traffic would hit, not a test-only trap.
    bad_admission_row = AdmissionRow(
        run_id="1" * 64,
        legacy_claim_id="fake-intel-item-1",
        family_id="fam-x",
        claim_object_id=None,
        claim_object_hash=None,
        evidence_object_ids=(),
        evidence_object_hashes=(),
        source_snapshot_hash="2" * 64,
        decision="admitted",
        reason=None,
    )

    before = await _counts(db)
    with pytest.raises(asyncpg.CheckViolationError):
        await ieb._execute_apply(db, writes=[write], admission_rows=[bad_admission_row])

    after = await _counts(db)
    assert after == before
    assert after["research_os_objects"] == 0
    assert after["research_os_naga_admission"] == 0


# --------------------------------------------------------------------------------------------
# 5. `--dry-run` never writes.
# --------------------------------------------------------------------------------------------


async def test_dry_run_never_writes(db: asyncpg.Connection) -> None:
    await _seed_intel_item(
        db,
        canonical_url="https://example.invalid/reg-readonly",
        citation="PMK 3/2026",
        verbatim_excerpt="Sesuai dengan PMK 3/2026, ketentuan berlaku efektif mulai Maret.",
        published_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    before = await _counts(db)

    report = await ieb.run_dry_run(db)

    assert report.admitted == 1
    assert await _counts(db) == before


# --------------------------------------------------------------------------------------------
# 6. Canonical schema gate -- a `claim` payload that is not a `Claim` is refused, by name, before
#    any write. `run_apply`'s own real `_build_claim_write` runs first here -- the mutation
#    drops one field AFTER that real construction, so everything else in the payload is genuine.
# --------------------------------------------------------------------------------------------


async def test_a_claim_missing_a_required_field_is_refused_by_name_and_writes_nothing(
    db: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_intel_item(
        db,
        canonical_url="https://example.invalid/reg-schema-gate",
        citation="PMK 4/2026",
        verbatim_excerpt="Sesuai dengan PMK 4/2026, ketentuan berlaku efektif mulai April.",
        published_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    dry = await ieb.run_dry_run(db)
    assert dry.admitted == 1, dry.excluded_by_reason

    real_build_claim_write = ieb._build_claim_write

    def _claim_write_missing_confidence(mapped, *, item, evidence_write, manifest):
        write = real_build_claim_write(
            mapped, item=item, evidence_write=evidence_write, manifest=manifest
        )
        # RED control: drop a REQUIRED `Claim` field after the real builder already produced a
        # genuine payload -- only `confidence` is missing, nothing else is fabricated.
        broken_payload = dict(write.payload)
        del broken_payload["confidence"]
        broken_payload["object_hash"] = "0" * 64
        broken_payload["object_hash"] = _real_object_hash(broken_payload)
        return ObjectWrite(
            object_kind=write.object_kind, object_id=write.object_id, payload=broken_payload
        )

    monkeypatch.setattr(ieb, "_build_claim_write", _claim_write_missing_confidence)

    before = await _counts(db)
    with pytest.raises(ieb.CanonicalSchemaInvalid) as excinfo:
        await ieb.run_apply(db, manifest=dry.manifest_hash)

    assert excinfo.value.object_kind == "claim"
    assert "confidence" in excinfo.value.errors
    after = await _counts(db)
    assert after == before
    assert after["research_os_objects"] == 0
    assert after["research_os_naga_admission"] == 0
