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
from backend.services.visa_engine.enums import SourceStatus
from backend.services.visa_engine.models import RulePack, SourceRecord
from backend.services.visa_engine.shadow_evidence import (
    REQUIRED_INTERVIEW_CATEGORIES,
    collect_shadow_evidence,
    evaluate_shadow_evidence,
)
from backend.tests.services.visa_engine.gold_harness import loader as gold_loader

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_MIGRATION_252_PATH = _BACKEND_DIR / "db" / "migrations_v2" / "252_visa_engine_write_substrate.sql"
_MIGRATION_255_PATH = _BACKEND_DIR / "db" / "migrations_v2" / "255_visa_shadow_evidence.sql"


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
    forward_252, rollback_252 = _read_migration(_MIGRATION_252_PATH, 252)
    forward_255, rollback_255 = _read_migration(_MIGRATION_255_PATH, 255)
    async with db_pool.acquire() as conn:
        await conn.execute(rollback_255)
        await conn.execute(rollback_252)
        await conn.execute(forward_252)
        await conn.execute(forward_255)
    yield
    async with db_pool.acquire() as conn:
        await conn.execute(rollback_255)
        await conn.execute(rollback_252)


async def _insert_unavailable_audit_row(
    conn: asyncpg.Connection,
    *,
    environment: str,
    evaluated_at: datetime,
    fingerprint_seed: str,
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
            grounding_summary
        ) VALUES (
            $1, $2, 'MATCH', 'SHADOW', 'TEMPORARILY_UNAVAILABLE',
            '[]'::jsonb, 'visa-engine/test', $3, $3, $3, $4, 'other',
            '[]'::jsonb, '[]'::jsonb
        )
        """,
        uuid.uuid4(),
        environment,
        evaluated_at,
        hashlib.sha256(fingerprint_seed.encode("utf-8")).digest(),
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
    assert gates["G-a"]["green"] is True
    assert gates["G-c"]["green"] is True
    assert gates["G-b"]["status"] == "UNMEASURED"
    assert gates["G-d"]["status"] == "UNMEASURED"
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
    assert gates["G-a"]["green"] is False
    assert gates["G-a"]["distinct_requests"] == 999
    assert gates["G-a"]["invalid_candidate_bindings"] == 1
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

    gate_a = report["gates"]["G-a"]
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

    gate_a = report["gates"]["G-a"]
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

    assert report["gates"]["G-a"]["green"] is False
    assert report["gates"]["G-c"]["green"] is False
    assert report["enforce_ready"] is False


def test_legacy_rows_without_correlators_or_grounding_keep_both_gates_red() -> None:
    rows, pack, db_pack_id = _green_fixture()
    for row in rows:
        row["request_fingerprint"] = None
        row["request_category"] = None
        row["candidate_summary"] = []
        row["grounding_summary"] = []

    report = _evaluate(rows, pack, db_pack_id)

    gate_a = report["gates"]["G-a"]
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
        ("TEST", start - timedelta(microseconds=1), "before-start"),
        ("TEST", start, "at-start"),
        ("TEST", end - timedelta(microseconds=1), "before-end"),
        ("TEST", end, "at-end"),
        ("PRODUCTION", start + timedelta(hours=12), "wrong-environment"),
    ]
    async with db_pool.acquire() as conn:
        for environment, evaluated_at, seed in rows:
            await _insert_unavailable_audit_row(
                conn,
                environment=environment,
                evaluated_at=evaluated_at,
                fingerprint_seed=seed,
            )

    report = await collect_shadow_evidence(
        db_pool,
        window_start=start,
        window_end=end,
        environment="TEST",
    )

    gate_a = report["gates"]["G-a"]
    assert gate_a["total_audit_rows"] == 2
    assert gate_a["distinct_requests"] == 2
    assert gate_a["missing_request_fingerprints"] == 0


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
