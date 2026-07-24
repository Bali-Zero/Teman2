"""Aggregation and local-DB tests for the Visa Oracle SHADOW evidence gate."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

import asyncpg
import pytest
import pytest_asyncio

from backend.db.migration_base import split_migration_sql
from backend.db.migration_manager import _assert_unique_migration_numbers
from backend.services.visa_engine.enums import SourceStatus
from backend.services.visa_engine.models import RulePack, SourceRecord
from backend.services.visa_engine.shadow_evidence import (
    REAL_TRAFFIC_SOURCE,
    REPORTED_ONLY_INTERVIEW_CATEGORIES,
    REQUIRED_INTERVIEW_CATEGORIES,
    SYNTHETIC_TRAFFIC_SOURCES,
    collect_shadow_evidence,
    evaluate_shadow_evidence,
)
from backend.tests.services.visa_engine.gold_harness import loader as gold_loader

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_MIGRATION_252_PATH = _BACKEND_DIR / "db" / "migrations_v2" / "252_visa_engine_write_substrate.sql"
_MIGRATION_255_PATH = _BACKEND_DIR / "db" / "migrations_v2" / "255_visa_shadow_evidence.sql"
_MIGRATION_256_PATH = _BACKEND_DIR / "db" / "migrations_v2" / "256_visa_traffic_source.sql"
_MIGRATION_257_PATH = (
    _BACKEND_DIR / "db" / "migrations_v2" / "257_visa_request_category_extension.sql"
)


def _green_fixture() -> tuple[list[dict[str, object]], RulePack, uuid.UUID]:
    pack = RulePack.model_validate(gold_loader.load_rule_pack_raw())
    db_pack_id = uuid.uuid5(pack.payload.rule_pack_id, "database-row")
    product_template = pack.payload.products[0]
    products = tuple(
        product_template.model_copy(
            update={
                "product_version_id": uuid.uuid5(pack.payload.rule_pack_id, f"product-{index}"),
                "product_code": f"X{index:02d}",
            }
        )
        for index in range(30)
    )
    pack = pack.model_copy(
        update={"payload": pack.payload.model_copy(update={"products": products})}
    )
    source_id = str(pack.payload.source_records[0].source_record_id)
    categories = sorted(REQUIRED_INTERVIEW_CATEGORIES)
    rows: list[dict[str, object]] = []
    for index in range(1_000):
        evaluated_at = gold_loader.GOLD_EFFECTIVE_AT + timedelta(days=index % 7, seconds=index)
        rows.append(
            {
                "request_fingerprint": index.to_bytes(32, "big"),
                "request_category": categories[index % len(categories)],
                "candidate_summary": [
                    {
                        "product_version_id": str(products[index % 30].product_version_id),
                        "product_code": str(products[index % 30].product_code),
                    }
                ],
                "grounding_summary": [
                    {
                        "claim_kind": "VERDICT",
                        "claim_code": "SUPPORTED_CANDIDATES",
                        "source_record_ids": [source_id],
                    }
                ],
                "citations": [{"source_record_id": source_id}],
                "verdict": "SUPPORTED_CANDIDATES",
                "rule_pack_id": db_pack_id,
                "ruleset_activation_id": uuid.uuid5(pack.payload.rule_pack_id, "shadow-activation"),
                "rule_pack_sha256": bytes.fromhex(pack.payload_sha256),
                "effective_at": evaluated_at,
                "observed_at": evaluated_at,
                "evaluated_at": evaluated_at,
                "traffic_source": REAL_TRAFFIC_SOURCE,
            }
        )
    return rows, pack, db_pack_id


def _evaluate(
    rows: list[dict[str, object]], pack: RulePack, db_pack_id: uuid.UUID
) -> dict[str, object]:
    return evaluate_shadow_evidence(
        rows,
        {db_pack_id: pack.payload},
        window_start=gold_loader.GOLD_EFFECTIVE_AT,
        window_end=gold_loader.GOLD_EFFECTIVE_AT + timedelta(days=8),
    )


def _add_source(pack: RulePack) -> tuple[RulePack, SourceRecord]:
    source = pack.payload.source_records[0].model_copy(
        update={
            "source_record_id": uuid.uuid4(),
            "source_key": "test.additional.source",
        }
    )
    payload = pack.payload.model_copy(
        update={"source_records": (*pack.payload.source_records, source)}
    )
    return pack.model_copy(update={"payload": payload}), source


def _replace_source(pack: RulePack, source: SourceRecord) -> RulePack:
    payload = pack.payload.model_copy(
        update={
            "source_records": tuple(
                source if existing.source_record_id == source.source_record_id else existing
                for existing in pack.payload.source_records
            )
        }
    )
    return pack.model_copy(update={"payload": payload})


def _read_migration(path: Path, number: int) -> tuple[str, str]:
    forward, rollback = split_migration_sql(path.read_text(encoding="utf-8"))
    assert rollback, f"migration {number} must carry a '-- === ROLLBACK ===' section"
    return forward, rollback


@pytest_asyncio.fixture
async def shadow_evidence_schema(db_pool: asyncpg.Pool, visa_schema: None) -> AsyncIterator[None]:
    """Layers migrations 252+255+256+257 on conftest.py's visa_schema.

    Ordering note (deliberate, NOT strict reverse-dependency): 257's rollback
    re-ADDs an 8-value CHECK constraint, which re-VALIDATES every surviving
    ``visa_decisions`` row — so it must run only AFTER 252's rollback has
    dropped the table (making it an ``IF EXISTS`` no-op), never while
    257-era rows ('business'/'diaspora') can still be present. Running it
    last also makes setup crash-robust: a previous run that died mid-test
    can leave new-category rows behind, and the 256/255 column drops +
    252's table drop clear them before 257's rollback is ever attempted.
    """
    forward_252, rollback_252 = _read_migration(_MIGRATION_252_PATH, 252)
    forward_255, rollback_255 = _read_migration(_MIGRATION_255_PATH, 255)
    forward_256, rollback_256 = _read_migration(_MIGRATION_256_PATH, 256)
    forward_257, rollback_257 = _read_migration(_MIGRATION_257_PATH, 257)
    async with db_pool.acquire() as conn:
        await conn.execute(rollback_256)
        await conn.execute(rollback_255)
        await conn.execute(rollback_252)
        await conn.execute(rollback_257)
        await conn.execute(forward_252)
        await conn.execute(forward_255)
        await conn.execute(forward_256)
        await conn.execute(forward_257)
    yield
    async with db_pool.acquire() as conn:
        await conn.execute(rollback_256)
        await conn.execute(rollback_255)
        await conn.execute(rollback_252)
        await conn.execute(rollback_257)


async def _insert_unavailable_audit_row(
    conn: asyncpg.Connection,
    *,
    environment: str,
    evaluated_at: datetime,
    fingerprint_seed: str,
    traffic_source: str | None = None,
    request_category: str = "other",
    engine_surface: str = "MATCH",
) -> None:
    await conn.execute(
        """
        INSERT INTO public.visa_decisions (
            decision_id,
            environment,
            engine_surface,
            engine_mode,
            verdict,
            citations,
            engine_version,
            effective_at,
            observed_at,
            evaluated_at,
            request_fingerprint,
            request_category,
            candidate_summary,
            grounding_summary,
            traffic_source
        ) VALUES (
            $1, $2, $7, 'SHADOW', 'TEMPORARILY_UNAVAILABLE',
            '[]'::jsonb, 'visa-engine/test', $3, $3, $3, $4, $6,
            '[]'::jsonb, '[]'::jsonb, $5
        )
        """,
        uuid.uuid4(),
        environment,
        evaluated_at,
        hashlib.sha256(fingerprint_seed.encode("utf-8")).digest(),
        traffic_source,
        request_category,
        engine_surface,
    )


class _CollectorConnection:
    def __init__(
        self,
        *,
        decision_rows: list[dict[str, object]],
        pack_rows: list[dict[str, object]],
    ) -> None:
        self._decision_rows = decision_rows
        self._pack_rows = pack_rows

    async def fetch(self, query: str, *args: object) -> list[dict[str, object]]:
        if "FROM public.visa_decisions" in query:
            return self._decision_rows
        if "FROM public.visa_rule_packs" in query:
            return self._pack_rows
        raise AssertionError(f"unexpected collector query: {query}")


class _CollectorAcquireContext:
    def __init__(self, connection: _CollectorConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> _CollectorConnection:
        return self._connection

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        return None


class _CollectorPool:
    def __init__(self, connection: _CollectorConnection) -> None:
        self._connection = connection

    def acquire(self) -> _CollectorAcquireContext:
        return _CollectorAcquireContext(self._connection)


def test_green_shadow_projection_still_cannot_arm_enforce() -> None:
    rows, pack, db_pack_id = _green_fixture()
    report = evaluate_shadow_evidence(
        rows,
        {db_pack_id: pack.payload},
        window_start=gold_loader.GOLD_EFFECTIVE_AT,
        window_end=gold_loader.GOLD_EFFECTIVE_AT + timedelta(days=8),
    )

    gates = report["gates"]
    assert gates["G-a-vol"]["green"] is True
    assert gates["G-a-breadth"]["green"] is False
    assert gates["G-a-breadth"]["total_audit_rows"] == 0
    assert gates["G-c"]["green"] is True
    assert gates["G-b"]["status"] == "UNMEASURED"
    assert gates["G-d"]["status"] == "UNMEASURED"
    assert report["traffic_source"] == {
        "real": 1_000,
        "synthetic_gold": 0,
        "synthetic_driver": 0,
        "legacy": 0,
        "total_audit_rows": 1_000,
    }
    assert report["enforce_ready"] is False
    assert report["gate_status"] == "RED"


def test_duplicate_request_and_ungrounded_verdict_fail_closed() -> None:
    rows, pack, db_pack_id = _green_fixture()
    rows[-1]["request_fingerprint"] = rows[0]["request_fingerprint"]
    rows[-1]["candidate_summary"] = [
        {
            "product_version_id": str(uuid.uuid4()),
            "product_code": "X29",
        }
    ]
    rows[-1]["ruleset_activation_id"] = None
    rows[-1]["rule_pack_sha256"] = None
    rows[0]["grounding_summary"] = [
        {
            "claim_kind": "VERDICT",
            "claim_code": "SUPPORTED_CANDIDATES",
            "source_record_ids": [],
        }
    ]
    rows[0]["citations"] = []

    report = evaluate_shadow_evidence(
        rows,
        {db_pack_id: pack.payload},
        window_start=gold_loader.GOLD_EFFECTIVE_AT,
        window_end=gold_loader.GOLD_EFFECTIVE_AT + timedelta(days=8),
    )

    gates = report["gates"]
    assert gates["G-a-vol"]["green"] is False
    assert gates["G-a-vol"]["distinct_requests"] == 999
    assert gates["G-a-vol"]["invalid_candidate_bindings"] == 1
    assert gates["G-c"]["green"] is False
    assert gates["G-c"]["decisions_without_citations"] == 1
    assert gates["G-c"]["missing_ruleset_activations"] == 1
    assert gates["G-c"]["missing_rule_pack_digests"] == 1
    assert gates["G-c"]["ungrounded_claims"] == 1


def test_duplicate_evaluations_ignore_missing_and_malformed_fingerprints() -> None:
    rows, pack, db_pack_id = _green_fixture()
    rows[-1]["request_fingerprint"] = None
    rows[-2]["request_fingerprint"] = b"malformed"
    rows[-3]["request_fingerprint"] = rows[0]["request_fingerprint"]

    report = _evaluate(rows, pack, db_pack_id)

    gate_a = report["gates"]["G-a-vol"]
    assert gate_a["missing_request_fingerprints"] == 2
    assert gate_a["distinct_requests"] == 997
    assert gate_a["duplicate_evaluations"] == 1


def test_citationless_needs_input_abstention_passes_grounding() -> None:
    rows, pack, db_pack_id = _green_fixture()
    rows[0]["verdict"] = "NEEDS_INPUT"
    rows[0]["candidate_summary"] = []
    rows[0]["grounding_summary"] = [
        {
            "claim_kind": "VERDICT",
            "claim_code": "NEEDS_INPUT",
            "source_record_ids": [],
        }
    ]
    rows[0]["citations"] = []

    report = evaluate_shadow_evidence(
        rows,
        {db_pack_id: pack.payload},
        window_start=gold_loader.GOLD_EFFECTIVE_AT,
        window_end=gold_loader.GOLD_EFFECTIVE_AT + timedelta(days=8),
    )

    gates = report["gates"]
    assert gates["G-c"]["green"] is True
    assert gates["G-c"]["decisions_without_citations"] == 0
    assert gates["G-c"]["ungrounded_claims"] == 0


def test_window_shorter_than_seven_full_days_fails_volume() -> None:
    rows, pack, db_pack_id = _green_fixture()
    start = gold_loader.GOLD_EFFECTIVE_AT
    report = evaluate_shadow_evidence(
        rows,
        {db_pack_id: pack.payload},
        window_start=start,
        window_end=start + timedelta(days=6, hours=23),
    )

    gate_a = report["gates"]["G-a-vol"]
    assert gate_a["longest_consecutive_utc_day_streak"] == 7
    assert gate_a["window_duration_hours"] == 167
    assert gate_a["green"] is False


def test_empty_window_is_red_not_vacuously_green() -> None:
    start = gold_loader.GOLD_EFFECTIVE_AT
    report = evaluate_shadow_evidence(
        [],
        {},
        window_start=start,
        window_end=start + timedelta(days=8),
    )

    assert report["gates"]["G-a-vol"]["green"] is False
    assert report["gates"]["G-a-breadth"]["green"] is False
    assert report["gates"]["G-c"]["green"] is False
    assert report["traffic_source"]["total_audit_rows"] == 0
    assert report["enforce_ready"] is False


def test_legacy_rows_without_correlators_or_grounding_keep_both_gates_red() -> None:
    rows, pack, db_pack_id = _green_fixture()
    for row in rows:
        row["request_fingerprint"] = None
        row["request_category"] = None
        row["candidate_summary"] = []
        row["grounding_summary"] = []

    report = _evaluate(rows, pack, db_pack_id)

    gate_a = report["gates"]["G-a-vol"]
    gate_c = report["gates"]["G-c"]
    assert gate_a["green"] is False
    assert gate_a["missing_request_fingerprints"] == 1_000
    assert gate_a["missing_or_invalid_categories"] == 1_000
    assert gate_c["green"] is False
    assert gate_c["malformed_grounding_summaries"] == 1_000
    assert gate_c["ungrounded_claims"] == 1_000


def test_citations_not_claimed_counter_is_directly_exercised() -> None:
    rows, pack, db_pack_id = _green_fixture()
    pack, additional_source = _add_source(pack)
    rows[0]["citations"] = [
        *cast(list[dict[str, object]], rows[0]["citations"]),
        {"source_record_id": str(additional_source.source_record_id)},
    ]

    gate_c = _evaluate(rows, pack, db_pack_id)["gates"]["G-c"]

    assert gate_c["green"] is False
    assert gate_c["citations_not_claimed"] == 1
    assert gate_c["claimed_sources_not_cited"] == 0
    assert gate_c["unresolved_or_invalid_sources"] == 0


def test_claimed_sources_not_cited_counter_is_directly_exercised() -> None:
    rows, pack, db_pack_id = _green_fixture()
    pack, additional_source = _add_source(pack)
    grounding = cast(list[dict[str, object]], rows[0]["grounding_summary"])
    grounding[0]["source_record_ids"] = [
        *cast(list[str], grounding[0]["source_record_ids"]),
        str(additional_source.source_record_id),
    ]

    gate_c = _evaluate(rows, pack, db_pack_id)["gates"]["G-c"]

    assert gate_c["green"] is False
    assert gate_c["citations_not_claimed"] == 0
    assert gate_c["claimed_sources_not_cited"] == 1
    assert gate_c["unresolved_or_invalid_sources"] == 0


@pytest.mark.parametrize(
    "malformed_citations",
    [
        "{not-json",
        [{"source_record_id": "not-a-uuid"}],
        ["not-an-object"],
    ],
)
def test_malformed_citations_counter_is_directly_exercised(
    malformed_citations: object,
) -> None:
    rows, pack, db_pack_id = _green_fixture()
    rows[0]["citations"] = malformed_citations

    gate_c = _evaluate(rows, pack, db_pack_id)["gates"]["G-c"]

    assert gate_c["green"] is False
    assert gate_c["malformed_citations"] == 1


@pytest.mark.parametrize(
    "failure",
    [
        "missing_source",
        "non_verified_status",
        "blank_canonical_url",
        "missing_effective_at",
        "missing_observed_at",
        "outside_legal_period",
        "outside_recorded_period",
    ],
)
def test_unresolved_or_invalid_sources_counts_every_failure_condition(failure: str) -> None:
    rows, pack, db_pack_id = _green_fixture()
    source = pack.payload.source_records[0]
    cited_source_id = source.source_record_id

    if failure == "missing_source":
        cited_source_id = uuid.uuid4()
    elif failure == "non_verified_status":
        pack, source = _add_source(pack)
        source = source.model_copy(update={"status": SourceStatus.SUPERSEDED})
        pack = _replace_source(pack, source)
        cited_source_id = source.source_record_id
    elif failure == "blank_canonical_url":
        pack, source = _add_source(pack)
        source = source.model_copy(update={"canonical_url": "   "})
        pack = _replace_source(pack, source)
        cited_source_id = source.source_record_id
    elif failure == "missing_effective_at":
        rows[0]["effective_at"] = None
    elif failure == "missing_observed_at":
        rows[0]["observed_at"] = None
    elif failure == "outside_legal_period":
        rows[0]["effective_at"] = source.legal_period.from_ - timedelta(microseconds=1)
    elif failure == "outside_recorded_period":
        rows[0]["observed_at"] = source.recorded_period.from_ - timedelta(microseconds=1)
    else:
        raise AssertionError(f"unknown failure case: {failure}")

    rows[0]["citations"] = [{"source_record_id": str(cited_source_id)}]
    rows[0]["grounding_summary"] = [
        {
            "claim_kind": "VERDICT",
            "claim_code": "SUPPORTED_CANDIDATES",
            "source_record_ids": [str(cited_source_id)],
        }
    ]

    gate_c = _evaluate(rows, pack, db_pack_id)["gates"]["G-c"]

    assert gate_c["green"] is False
    assert gate_c["unresolved_or_invalid_sources"] == 1


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.asyncio
async def test_collect_filters_environment_and_uses_half_open_window(
    db_pool: asyncpg.Pool, shadow_evidence_schema: None
) -> None:
    start = datetime(2026, 7, 21, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    rows = [
        ("TEST", start - timedelta(microseconds=1), "before-start", None),
        ("TEST", start, "at-start", REAL_TRAFFIC_SOURCE),
        ("TEST", end - timedelta(microseconds=1), "before-end", REAL_TRAFFIC_SOURCE),
        ("TEST", end, "at-end", None),
        ("PRODUCTION", start + timedelta(hours=12), "wrong-environment", None),
    ]
    async with db_pool.acquire() as conn:
        for environment, evaluated_at, seed, traffic_source in rows:
            await _insert_unavailable_audit_row(
                conn,
                environment=environment,
                evaluated_at=evaluated_at,
                fingerprint_seed=seed,
                traffic_source=traffic_source,
            )

    report = await collect_shadow_evidence(
        db_pool,
        window_start=start,
        window_end=end,
        environment="TEST",
    )

    gate_a = report["gates"]["G-a-vol"]
    assert gate_a["total_audit_rows"] == 2
    assert gate_a["distinct_requests"] == 2
    assert gate_a["missing_request_fingerprints"] == 0
    assert report["traffic_source"] == {
        "real": 2,
        "synthetic_gold": 0,
        "synthetic_driver": 0,
        "legacy": 0,
        "total_audit_rows": 2,
    }


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.asyncio
async def test_collect_splits_traffic_source_end_to_end(
    db_pool: asyncpg.Pool, shadow_evidence_schema: None
) -> None:
    """Migration 256's column round-trips: real -> G-a-vol, synthetic ->
    G-a-breadth, NULL -> legacy (neither), straight from the database."""
    start = datetime(2026, 7, 21, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    rows = [
        ("at-start", REAL_TRAFFIC_SOURCE),
        ("gold-row", "synthetic_gold"),
        ("driver-row", "synthetic_driver"),
        ("legacy-row", None),
    ]
    async with db_pool.acquire() as conn:
        for seed, traffic_source in rows:
            await _insert_unavailable_audit_row(
                conn,
                environment="TEST",
                evaluated_at=start,
                fingerprint_seed=seed,
                traffic_source=traffic_source,
            )

    report = await collect_shadow_evidence(
        db_pool,
        window_start=start,
        window_end=end,
        environment="TEST",
    )

    gates = report["gates"]
    assert gates["G-a-vol"]["total_audit_rows"] == 1
    assert gates["G-a-vol"]["traffic_sources"] == [REAL_TRAFFIC_SOURCE]
    assert gates["G-a-vol"]["traffic_source_counts"] == {REAL_TRAFFIC_SOURCE: 1}
    assert gates["G-a-breadth"]["total_audit_rows"] == 2
    assert gates["G-a-breadth"]["traffic_sources"] == sorted(SYNTHETIC_TRAFFIC_SOURCES)
    assert gates["G-a-breadth"]["traffic_source_counts"] == {
        "synthetic_gold": 1,
        "synthetic_driver": 1,
    }
    assert report["traffic_source"] == {
        "real": 1,
        "synthetic_gold": 1,
        "synthetic_driver": 1,
        "legacy": 1,
        "total_audit_rows": 4,
    }


@pytest.mark.parametrize(
    ("pack_rows_kind", "expected_invalid_count"),
    [
        ("missing", 1),
        ("invalid", 1),
        ("valid", 0),
    ],
)
@pytest.mark.asyncio
async def test_collect_counts_missing_or_invalid_pack_payloads(
    pack_rows_kind: str,
    expected_invalid_count: int,
) -> None:
    rows, pack, _db_pack_id = _green_fixture()
    pack_id = uuid.uuid4()
    decision_row = rows[0]
    decision_row["rule_pack_id"] = pack_id
    decision_row["candidate_summary"] = []
    decision_row["verdict"] = "NEEDS_INPUT"
    decision_row["citations"] = []
    decision_row["grounding_summary"] = [
        {
            "claim_kind": "VERDICT",
            "claim_code": "NEEDS_INPUT",
            "source_record_ids": [],
        }
    ]

    if pack_rows_kind == "missing":
        pack_rows: list[dict[str, object]] = []
    elif pack_rows_kind == "invalid":
        pack_rows = [{"id": pack_id, "payload": {"not": "a-rule-pack"}}]
    elif pack_rows_kind == "valid":
        pack_rows = [
            {
                "id": pack_id,
                "payload": pack.payload.model_dump(mode="json", by_alias=True),
            }
        ]
    else:
        raise AssertionError(f"unknown pack row kind: {pack_rows_kind}")

    connection = _CollectorConnection(decision_rows=[decision_row], pack_rows=pack_rows)
    pool = cast(asyncpg.Pool, _CollectorPool(connection))
    start = gold_loader.GOLD_EFFECTIVE_AT

    report = await collect_shadow_evidence(
        pool,
        window_start=start,
        window_end=start + timedelta(days=1),
        environment="TEST",
    )

    assert report["gates"]["G-c"]["invalid_rule_pack_payloads"] == expected_invalid_count


# ---------------------------------------------------------------------------
# Fable final-gate deltas 1-2 (2026-07-23) — traffic_source split (migration
# 256): real -> G-a-vol, synthetic classes -> G-a-breadth, NULL/unknown ->
# legacy (neither).  Guilt AND innocence for each direction.
# ---------------------------------------------------------------------------


def test_synthetic_gold_rows_feed_breadth_never_vol() -> None:
    rows, pack, db_pack_id = _green_fixture()
    for row in rows:
        row["traffic_source"] = "synthetic_gold"

    report = _evaluate(rows, pack, db_pack_id)

    gates = report["gates"]
    # Innocence: the synthetic corpus DOES prove breadth...
    assert gates["G-a-breadth"]["green"] is True
    assert gates["G-a-breadth"]["total_audit_rows"] == 1_000
    assert gates["G-a-breadth"]["distinct_requests"] == 1_000
    assert gates["G-a-breadth"]["traffic_sources"] == sorted(SYNTHETIC_TRAFFIC_SOURCES)
    assert gates["G-a-breadth"]["traffic_source_counts"] == {
        "synthetic_gold": 1_000,
        "synthetic_driver": 0,
    }
    # Guilt: ...but it can NEVER manufacture production adoption.
    assert gates["G-a-vol"]["green"] is False
    assert gates["G-a-vol"]["total_audit_rows"] == 0
    assert gates["G-a-vol"]["distinct_requests"] == 0
    assert gates["G-a-vol"]["traffic_sources"] == [REAL_TRAFFIC_SOURCE]
    assert "G-a-vol" in report["blockers"]
    assert "G-a-breadth" not in report["blockers"]


def test_both_synthetic_classes_are_labeled_and_summed_in_breadth() -> None:
    rows, pack, db_pack_id = _green_fixture()
    for index, row in enumerate(rows):
        row["traffic_source"] = "synthetic_gold" if index % 2 == 0 else "synthetic_driver"

    report = _evaluate(rows, pack, db_pack_id)

    breadth = report["gates"]["G-a-breadth"]
    assert breadth["traffic_source_counts"] == {
        "synthetic_gold": 500,
        "synthetic_driver": 500,
    }
    assert breadth["total_audit_rows"] == 1_000
    assert report["traffic_source"]["synthetic_gold"] == 500
    assert report["traffic_source"]["synthetic_driver"] == 500
    assert report["gates"]["G-a-vol"]["total_audit_rows"] == 0


def test_null_and_unknown_sources_are_legacy_counted_toward_neither_gate() -> None:
    rows, pack, db_pack_id = _green_fixture()
    for index, row in enumerate(rows):
        if index % 3 == 0:
            row["traffic_source"] = None  # pre-256 legacy row
        elif index % 3 == 1:
            del row["traffic_source"]  # key absent entirely
        else:
            row["traffic_source"] = "not-a-checked-source"  # non-CHECK value

    report = _evaluate(rows, pack, db_pack_id)

    gates = report["gates"]
    assert gates["G-a-vol"]["total_audit_rows"] == 0
    assert gates["G-a-breadth"]["total_audit_rows"] == 0
    assert gates["G-a-vol"]["green"] is False
    assert gates["G-a-breadth"]["green"] is False
    assert report["traffic_source"] == {
        "real": 0,
        "synthetic_gold": 0,
        "synthetic_driver": 0,
        "legacy": 1_000,
        "total_audit_rows": 1_000,
    }


def test_mixed_traffic_split_fields_sum_to_total() -> None:
    rows, pack, db_pack_id = _green_fixture()
    synthetic_rows, _, _ = _green_fixture()
    extra: list[dict[str, object]] = []
    for index, row in enumerate(synthetic_rows[:40]):
        clone = dict(row)
        clone["request_fingerprint"] = (1_000 + index).to_bytes(32, "big")
        clone["traffic_source"] = "synthetic_driver"
        extra.append(clone)
    rows[0]["traffic_source"] = None  # one legacy row
    mixed = rows + extra

    report = _evaluate(mixed, pack, db_pack_id)

    traffic = report["traffic_source"]
    assert traffic == {
        "real": 999,
        "synthetic_gold": 0,
        "synthetic_driver": 40,
        "legacy": 1,
        "total_audit_rows": 1_040,
    }
    gates = report["gates"]
    # Vol counts ONLY real rows: the 40 synthetic rows carry fresh
    # fingerprints and must not leak into vol's distinct_requests.
    assert gates["G-a-vol"]["total_audit_rows"] == 999
    assert gates["G-a-vol"]["distinct_requests"] == 999
    assert gates["G-a-breadth"]["total_audit_rows"] == 40
    assert gates["G-a-breadth"]["distinct_requests"] == 40
    assert (
        gates["G-a-vol"]["total_audit_rows"]
        + gates["G-a-breadth"]["total_audit_rows"]
        + traffic["legacy"]
        == traffic["total_audit_rows"]
    )


def test_grounding_gate_spans_all_traffic_sources() -> None:
    """G-c is intentionally NOT split: a grounding defect in a synthetic row
    is still an engine-output defect and must keep G-c red."""
    rows, pack, db_pack_id = _green_fixture()
    rows[0]["traffic_source"] = "synthetic_gold"
    rows[0]["grounding_summary"] = []

    report = _evaluate(rows, pack, db_pack_id)

    gate_c = report["gates"]["G-c"]
    assert gate_c["green"] is False
    assert gate_c["malformed_grounding_summaries"] == 1
    assert gate_c["ungrounded_claims"] == 1


def test_migration_256_carries_rollback_marker() -> None:
    forward, rollback = _read_migration(_MIGRATION_256_PATH, 256)
    assert "traffic_source" in forward
    assert "traffic_source" in rollback


def test_migration_256_keeps_migrations_v2_prefixes_unique() -> None:
    sql_files = sorted(_MIGRATION_256_PATH.parent.glob("*.sql"))
    _assert_unique_migration_numbers(sql_files)
    prefixes = [path.name.split("_", 1)[0] for path in sql_files]
    assert prefixes.count("256") == 1


# ---------------------------------------------------------------------------
# W1 Fable delta 3 (2026-07-23) — migration 257 request_category extension:
# 'business'/'diaspora' are VALID (counted, honestly labeled) but NOT
# required for G-a gate-green (their behavioral trees are Track B FASE 2).
# Guilt AND innocence for both directions of the rule.
# ---------------------------------------------------------------------------


def test_required_interview_categories_still_the_seven_legacy() -> None:
    assert REQUIRED_INTERVIEW_CATEGORIES == frozenset(
        {
            "work_remote",
            "investor",
            "work_employee",
            "family",
            "long_tourism",
            "retirement",
            "student",
        }
    )
    assert REPORTED_ONLY_INTERVIEW_CATEGORIES == frozenset({"business", "diaspora"})
    assert REQUIRED_INTERVIEW_CATEGORIES.isdisjoint(REPORTED_ONLY_INTERVIEW_CATEGORIES)
    # Migration 257's CHECK admits exactly these ten values — no more.
    assert len(REQUIRED_INTERVIEW_CATEGORIES | REPORTED_ONLY_INTERVIEW_CATEGORIES | {"other"}) == 10


def test_business_and_diaspora_are_reported_not_required() -> None:
    rows, pack, db_pack_id = _green_fixture()
    categories = sorted(REQUIRED_INTERVIEW_CATEGORIES) + ["business", "diaspora"]
    for index, row in enumerate(rows):
        row["request_category"] = categories[index % len(categories)]

    report = _evaluate(rows, pack, db_pack_id)
    gate = report["gates"]["G-a-vol"]

    # Innocence: business/diaspora count as VALID categories (never as
    # missing-or-invalid) and are honestly reported in category_counts...
    assert gate["missing_or_invalid_categories"] == 0
    assert gate["category_counts"]["business"] > 0
    assert gate["category_counts"]["diaspora"] > 0
    # ...but are NOT required for gate-green: only the 7 legacy categories
    # feed missing_required_categories.
    assert gate["missing_required_categories"] == []
    assert gate["required_categories"] == sorted(REQUIRED_INTERVIEW_CATEGORIES)
    assert gate["reported_only_categories"] == ["business", "diaspora"]
    assert gate["green"] is True


def test_a_missing_legacy_category_still_fails_closed_with_ten_value_enum() -> None:
    """Guilt: the widened enum does not dilute the 7-category requirement —
    a window with zero 'student' rows stays RED even with plenty of
    business/diaspora traffic."""
    rows, pack, db_pack_id = _green_fixture()
    categories = [c for c in sorted(REQUIRED_INTERVIEW_CATEGORIES) if c != "student"]
    categories += ["business", "diaspora"]
    for index, row in enumerate(rows):
        row["request_category"] = categories[index % len(categories)]

    report = _evaluate(rows, pack, db_pack_id)
    gate = report["gates"]["G-a-vol"]

    assert gate["missing_required_categories"] == ["student"]
    assert gate["green"] is False


def test_migration_257_carries_rollback_marker_and_correct_value_sets() -> None:
    forward, rollback = _read_migration(_MIGRATION_257_PATH, 257)
    for value in (
        "work_remote",
        "investor",
        "work_employee",
        "family",
        "long_tourism",
        "retirement",
        "student",
        "other",
        "business",
        "diaspora",
    ):
        assert f"'{value}'" in forward
    # The restored CHECK is migration 255's exact 8-value one: the two new
    # values must not appear in it.  (They DO appear earlier in the rollback
    # — the relabel-first UPDATE that downgrades live new-category rows to
    # 'other' before the CHECK is restored, which is what makes the rollback
    # succeed at all — so assert on the ADD CONSTRAINT tail only.)
    restored_check = rollback.rsplit("ADD CONSTRAINT", 1)[-1]
    assert "'business'" not in restored_check
    assert "'diaspora'" not in restored_check
    for value in (
        "work_remote",
        "investor",
        "work_employee",
        "family",
        "long_tourism",
        "retirement",
        "student",
        "other",
    ):
        assert f"'{value}'" in restored_check


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.asyncio
async def test_migration_257_check_admits_new_categories_and_rejects_bogus(
    db_pool: asyncpg.Pool, shadow_evidence_schema: None
) -> None:
    start = datetime(2026, 7, 23, tzinfo=timezone.utc)
    async with db_pool.acquire() as conn:
        # Innocence: the two new categories insert cleanly.
        await _insert_unavailable_audit_row(
            conn,
            environment="TEST",
            evaluated_at=start,
            fingerprint_seed="business-row",
            request_category="business",
        )
        await _insert_unavailable_audit_row(
            conn,
            environment="TEST",
            evaluated_at=start,
            fingerprint_seed="diaspora-row",
            request_category="diaspora",
        )
        # Guilt: a non-CHECK value is still rejected at the storage layer.
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await _insert_unavailable_audit_row(
                conn,
                environment="TEST",
                evaluated_at=start,
                fingerprint_seed="bogus-row",
                request_category="not-a-category",
            )


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.asyncio
async def test_collect_reports_business_diaspora_as_valid_not_required(
    db_pool: asyncpg.Pool, shadow_evidence_schema: None
) -> None:
    """End-to-end through Postgres: rows carrying the new categories survive
    the 257 CHECK, are read back by the collector, and land in
    category_counts without ever feeding missing_required_categories."""
    start = datetime(2026, 7, 23, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    async with db_pool.acquire() as conn:
        for seed, category in (("biz", "business"), ("diaspora", "diaspora")):
            await _insert_unavailable_audit_row(
                conn,
                environment="TEST",
                evaluated_at=start,
                fingerprint_seed=seed,
                traffic_source=REAL_TRAFFIC_SOURCE,
                request_category=category,
            )

    report = await collect_shadow_evidence(
        db_pool,
        window_start=start,
        window_end=end,
        environment="TEST",
    )

    gate = report["gates"]["G-a-vol"]
    assert gate["missing_or_invalid_categories"] == 0
    assert gate["category_counts"] == {"business": 1, "diaspora": 1}
    assert "business" not in gate["missing_required_categories"]
    assert "diaspora" not in gate["missing_required_categories"]
    assert gate["reported_only_categories"] == ["business", "diaspora"]


# ---------------------------------------------------------------------------
# W1 (2026-07-23) — evidence-surface widening: the collector reads SHADOW
# rows for MATCH (STEP-6c) AND RECOMMEND (the W1 evaluate read-path).
# Other surfaces are skipped fail-closed. Guilt AND innocence both ways.
# ---------------------------------------------------------------------------


def test_recommend_surface_rows_count_like_match_rows() -> None:
    rows, pack, db_pack_id = _green_fixture()
    for index, row in enumerate(rows):
        row["engine_surface"] = "RECOMMEND" if index % 2 == 0 else "MATCH"

    report = _evaluate(rows, pack, db_pack_id)

    gate = report["gates"]["G-a-vol"]
    assert gate["total_audit_rows"] == 1_000
    assert gate["green"] is True
    assert report["surfaces"] == {"MATCH": 500, "RECOMMEND": 500}
    assert report["skipped_non_evidence_surfaces"] == 0


def test_non_evidence_surface_rows_are_skipped_fail_closed() -> None:
    """Guilt: a future writer on a non-evidence surface (e.g. CLOCK) must not
    inflate any gate, even if its rows are fully valid and real-labeled."""
    rows, pack, db_pack_id = _green_fixture()
    for row in rows:
        row["engine_surface"] = "CLOCK"

    report = _evaluate(rows, pack, db_pack_id)

    assert report["gates"]["G-a-vol"]["total_audit_rows"] == 0
    assert report["gates"]["G-a-breadth"]["total_audit_rows"] == 0
    assert report["traffic_source"] == {
        "real": 0,
        "synthetic_gold": 0,
        "synthetic_driver": 0,
        "legacy": 0,
        "total_audit_rows": 1_000,
    }
    assert report["surfaces"] == {}
    assert report["skipped_non_evidence_surfaces"] == 1_000
    # Reconciliation: admitted traffic classes + skipped == raw input rows.
    traffic = report["traffic_source"]
    assert (
        traffic["real"]
        + traffic["synthetic_gold"]
        + traffic["synthetic_driver"]
        + traffic["legacy"]
        + report["skipped_non_evidence_surfaces"]
        == traffic["total_audit_rows"]
    )


def test_rows_without_surface_key_stay_admitted_backward_compatible() -> None:
    rows, pack, db_pack_id = _green_fixture()
    for row in rows:
        row.pop("engine_surface", None)

    report = _evaluate(rows, pack, db_pack_id)

    assert report["gates"]["G-a-vol"]["total_audit_rows"] == 1_000
    assert report["skipped_non_evidence_surfaces"] == 0
    assert report["surfaces"] == {}


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.asyncio
async def test_collect_reads_match_and_recommend_surfaces_only(
    db_pool: asyncpg.Pool, shadow_evidence_schema: None
) -> None:
    """End-to-end through Postgres: the SQL filter admits MATCH + RECOMMEND
    SHADOW rows and excludes any other surface."""
    start = datetime(2026, 7, 23, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    async with db_pool.acquire() as conn:
        for seed, surface in (
            ("match-row", "MATCH"),
            ("recommend-row", "RECOMMEND"),
            ("clock-row", "CLOCK"),
            ("catalog-row", "CATALOG"),
        ):
            await _insert_unavailable_audit_row(
                conn,
                environment="TEST",
                evaluated_at=start,
                fingerprint_seed=seed,
                traffic_source=REAL_TRAFFIC_SOURCE,
                engine_surface=surface,
            )

    report = await collect_shadow_evidence(
        db_pool,
        window_start=start,
        window_end=end,
        environment="TEST",
    )

    assert report["gates"]["G-a-vol"]["total_audit_rows"] == 2
    assert report["traffic_source"]["total_audit_rows"] == 2
    assert report["surfaces"] == {"MATCH": 1, "RECOMMEND": 1}
    assert report["skipped_non_evidence_surfaces"] == 0


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.asyncio
async def test_migration_257_rollback_relabels_new_categories_and_restores_check(
    db_pool: asyncpg.Pool, shadow_evidence_schema: None
) -> None:
    """The rollback must SUCCEED even with 'business'/'diaspora' rows live
    (the re-added 8-value CHECK re-validates every row): it relabels those
    rows to 'other' BEFORE restoring the constraint — a lossy but honest
    downgrade — and never touches legacy-category rows."""
    _, rollback_257 = _read_migration(_MIGRATION_257_PATH, 257)
    start = datetime(2026, 7, 23, tzinfo=timezone.utc)
    async with db_pool.acquire() as conn:
        for seed, category in (
            ("biz", "business"),
            ("diaspora", "diaspora"),
            ("legacy", "student"),
        ):
            await _insert_unavailable_audit_row(
                conn,
                environment="TEST",
                evaluated_at=start,
                fingerprint_seed=seed,
                request_category=category,
            )

        # The rollback itself must not fail on the live new-category rows...
        await conn.execute(rollback_257)

        # ...both new-category rows are relabeled to 'other'; the legacy one
        # is untouched.
        rows = await conn.fetch(
            "SELECT request_category, count(*) AS n FROM public.visa_decisions GROUP BY 1"
        )
        counts = {row["request_category"]: row["n"] for row in rows}
        assert counts == {"other": 2, "student": 1}

        # ...and the restored CHECK is the 8-value one again.
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await _insert_unavailable_audit_row(
                conn,
                environment="TEST",
                evaluated_at=start,
                fingerprint_seed="post-rollback-biz",
                request_category="business",
            )

        # ...and migration 252's append-only guard is re-armed: the relabel
        # was a one-shot DDL suspension, never a lasting weakening.
        with pytest.raises(asyncpg.exceptions.RaiseError):
            await conn.execute("UPDATE public.visa_decisions SET engine_version = 'tamper'")
