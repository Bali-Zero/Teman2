#!/usr/bin/env python3
"""Project the canonical PROD company graph into local ``nuzantara_dev``.

The command is deliberately narrow:

* PROD is read once through ``scripts/pg.sh`` in one read-only,
  repeatable-read snapshot.  Rows travel as an in-memory JSON-lines stream and
  are never printed or logged.
* The target is exactly the loopback ``nuzantara_dev`` database.  Dry-run is
  the default.  Writes require both ``--apply`` and
  ``INTAKE_COMPANY_PROJECTION_WRITE_ENABLED=true``.
* Apply uses one local transaction in companies -> eligible links -> sequence
  order.  Links whose client does not already exist locally are counted and
  skipped; clients are never synthesized.
* No delete, truncate, intake mutation, reroute, or service restart exists in
  this script.  User-visible output is aggregate JSON plus type-only digests.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol, TypeAlias, cast
from urllib.parse import urlparse
from uuid import UUID

import asyncpg

PG_SH = Path(__file__).resolve().with_name("pg.sh")

EXPECTED_SOURCE_DATABASE = "nuzantara_rag"
EXPECTED_SOURCE_ROLE = "nuzantara_readonly"
EXPECTED_TARGET_DATABASE = "nuzantara_dev"
EXPECTED_TARGET_ROLE = "nuzantara"

DEFAULT_TARGET_DSN = (
    "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
)
TARGET_DSN_ENV = "INTAKE_COMPANY_PROJECTION_DATABASE_URL"
WRITE_ENABLE_ENV = "INTAKE_COMPANY_PROJECTION_WRITE_ENABLED"
CONTENT_DIGEST_DOMAIN = "nuzantara:intake-company-source-snapshot"
CONTENT_DIGEST_VERSION = "1"
PROJECTION_DIGEST_DOMAIN = "nuzantara:intake-company-projection"
PROJECTION_DIGEST_VERSION = "1"

COMPANY_COLUMNS = (
    "id",
    "uuid",
    "company_name",
    "company_type",
    "brand_name",
    "kbli_code",
    "kbli_description",
    "nib",
    "npwp_company",
    "akta_pendirian_no",
    "akta_pendirian_date",
    "akta_perubahan_no",
    "akta_perubahan_date",
    "sk_menhumkam_no",
    "sk_menhumkam_date",
    "registered_address",
    "office_address",
    "city",
    "province",
    "postal_code",
    "company_phone",
    "company_email",
    "status",
    "setup_progress",
    "google_drive_folder_id",
    "custom_fields",
    "created_at",
    "updated_at",
    "created_by",
    "updated_by",
)

SOURCE_ONLY_COMPANY_COLUMNS = (
    "geo_point",
    "rdtr_zone_code",
    "geocoded_at",
    "geocode_source",
    "tax_dept_folder_id",
)

LINK_COLUMNS = (
    "id",
    "client_id",
    "company_id",
    "role",
    "is_primary",
    "ownership_percentage",
    "shares_count",
    "share_nominal_value",
    "start_date",
    "end_date",
    "status",
    "notes",
    "created_at",
    "updated_at",
)

PROTECTED_TABLES = (
    "clients",
    "intake_queue",
    "document_instances",
    "document_routing_proposal",
    "intake_commit_audit",
)


class ProjectionError(RuntimeError):
    """Base class for deliberately sanitized projection failures."""


class SourceSnapshotError(ProjectionError):
    """The PROD snapshot failed transport, attestation, or validation."""


class ApplyGateError(ProjectionError):
    """A target or operator write gate was not satisfied."""


class TargetContractError(ProjectionError):
    """The local database does not expose the expected schema/FK contract."""


class ProjectionInvariantError(ProjectionError):
    """A protected local table changed during the projection transaction."""


@dataclass(frozen=True)
class SourceMetadata:
    snapshot_at: str
    companies_count: int
    links_count: int
    companies_max_updated_at: str | None
    links_max_updated_at: str | None


JsonRow: TypeAlias = Mapping[str, Any]


@dataclass(frozen=True)
class SourceSnapshot:
    metadata: SourceMetadata
    companies: tuple[JsonRow, ...]
    links: tuple[JsonRow, ...]
    canonical_row_bytes: bytes
    content_digest: str


@dataclass(frozen=True)
class ProjectionPlan:
    companies: tuple[JsonRow, ...]
    eligible_links: tuple[JsonRow, ...]
    rejected_missing_local_client: int
    projection_digest: str


@dataclass(frozen=True)
class TargetProjection:
    """Canonical, local target rows acquired through the narrow allowlists."""

    companies: tuple[JsonRow, ...]
    links: tuple[JsonRow, ...]
    digest: str


@dataclass(frozen=True)
class InvariantState:
    row_count: int
    schema_digest: str
    row_digest: str


@dataclass(frozen=True)
class ApplyResult:
    accepted_source: SourceSnapshot
    accepted_plan: ProjectionPlan
    source_content_digest: str
    target_before_counts: Mapping[str, int]
    target_after_counts: Mapping[str, int]
    sequence_status: Mapping[str, Mapping[str, int | bool]]
    protected_before: Mapping[str, InvariantState]
    protected_after: Mapping[str, InvariantState]
    companies_inserted: int
    links_inserted: int
    invariant_digest: str
    projection_digest: str
    no_op: bool


def _immutable_value_copy(value: Any) -> Any:
    """Recursively detach and freeze a value accepted from a source row."""

    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("accepted mapping keys must be strings")
            frozen[key] = _immutable_value_copy(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_immutable_value_copy(item) for item in value)
    if value is None or isinstance(
        value, (str, int, Decimal, UUID, datetime, date, bytes)
    ):
        return value
    raise TypeError("unsupported accepted value type")


def _immutable_rows_copy(rows: Sequence[Mapping[str, Any]]) -> tuple[JsonRow, ...]:
    return tuple(cast(JsonRow, _immutable_value_copy(row)) for row in rows)


def _immutable_source_copy(snapshot: SourceSnapshot) -> SourceSnapshot:
    metadata = snapshot.metadata
    return SourceSnapshot(
        metadata=SourceMetadata(
            snapshot_at=metadata.snapshot_at,
            companies_count=metadata.companies_count,
            links_count=metadata.links_count,
            companies_max_updated_at=metadata.companies_max_updated_at,
            links_max_updated_at=metadata.links_max_updated_at,
        ),
        companies=_immutable_rows_copy(snapshot.companies),
        links=_immutable_rows_copy(snapshot.links),
        canonical_row_bytes=bytes(snapshot.canonical_row_bytes),
        content_digest=snapshot.content_digest,
    )


def _immutable_plan_copy(plan: ProjectionPlan) -> ProjectionPlan:
    return ProjectionPlan(
        companies=_immutable_rows_copy(plan.companies),
        eligible_links=_immutable_rows_copy(plan.eligible_links),
        rejected_missing_local_client=plan.rejected_missing_local_client,
        projection_digest=plan.projection_digest,
    )


def _immutable_counts_copy(counts: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(counts))


def _immutable_sequence_status_copy(
    status: Mapping[str, Mapping[str, int | bool]],
) -> Mapping[str, Mapping[str, int | bool]]:
    return MappingProxyType(
        {
            sequence: MappingProxyType(dict(details))
            for sequence, details in status.items()
        }
    )


def _immutable_invariants_copy(
    states: Mapping[str, InvariantState],
) -> Mapping[str, InvariantState]:
    return MappingProxyType(
        {
            table: InvariantState(
                row_count=state.row_count,
                schema_digest=state.schema_digest,
                row_digest=state.row_digest,
            )
            for table, state in states.items()
        }
    )


class _Transaction(Protocol):
    async def __aenter__(self) -> Any: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> bool | None: ...


class ConnectionLike(Protocol):
    def transaction(self, **kwargs: Any) -> _Transaction: ...

    async def fetch(self, query: str, *args: Any) -> Sequence[Mapping[str, Any]]: ...

    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None: ...

    async def execute(self, query: str, *args: Any) -> str: ...

    async def executemany(
        self, query: str, args: Sequence[Sequence[Any]]
    ) -> None: ...

    async def close(self) -> None: ...


RunCallable: TypeAlias = Callable[..., subprocess.CompletedProcess[bytes]]
ConnectCallable: TypeAlias = Callable[..., Awaitable[ConnectionLike]]


def _quoted_columns(columns: Sequence[str]) -> str:
    """Return a comma-separated identifier list from a module-owned allowlist."""

    for column in columns:
        if re.fullmatch(r"[a-z_][a-z0-9_]*", column) is None:
            raise ValueError("invalid allowlisted SQL identifier")
    return ", ".join(columns)


_COMPANY_COLUMN_SQL = _quoted_columns(COMPANY_COLUMNS)
_LINK_COLUMN_SQL = _quoted_columns(LINK_COLUMNS)

SOURCE_SNAPSHOT_SQL = f"""
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;

SELECT json_build_object(
    'kind', 'meta',
    'database', current_database(),
    'role', current_user,
    'transaction_read_only', current_setting('transaction_read_only'),
    'snapshot_at', statement_timestamp(),
    'companies_count', (SELECT count(*) FROM public.companies),
    'links_count', (SELECT count(*) FROM public.client_company_links),
    'companies_max_updated_at', (SELECT max(updated_at) FROM public.companies),
    'links_max_updated_at', (SELECT max(updated_at) FROM public.client_company_links)
)::text;

SELECT json_build_object('kind', 'company', 'row', to_jsonb(projected))::text
FROM (
    SELECT {_COMPANY_COLUMN_SQL}
    FROM public.companies
    ORDER BY id
) AS projected;

SELECT json_build_object('kind', 'link', 'row', to_jsonb(projected))::text
FROM (
    SELECT {_LINK_COLUMN_SQL}
    FROM public.client_company_links
    ORDER BY id
) AS projected;

COMMIT;
""".strip()

TARGET_ATTEST_SQL = """
SELECT
    current_database() AS database,
    current_user AS role,
    inet_server_addr()::text AS server_address,
    inet_server_port() AS server_port,
    current_setting('transaction_read_only') AS transaction_read_only,
    current_setting('search_path') AS search_path,
    to_regnamespace('public')::oid AS public_schema_oid,
    to_regclass('public.companies')::text AS companies_relation,
    company_relation.oid AS companies_relation_oid,
    to_regclass('public.companies')::oid AS companies_regclass_oid,
    company_namespace.oid AS companies_namespace_oid,
    company_namespace.nspname AS companies_namespace,
    company_relation.relname AS companies_relname,
    company_relation.relkind AS companies_relkind,
    to_regclass('public.client_company_links')::text AS links_relation,
    link_relation.oid AS links_relation_oid,
    to_regclass('public.client_company_links')::oid AS links_regclass_oid,
    link_namespace.oid AS links_namespace_oid,
    link_namespace.nspname AS links_namespace,
    link_relation.relname AS links_relname,
    link_relation.relkind AS links_relkind
FROM pg_catalog.pg_class AS company_relation
JOIN pg_catalog.pg_namespace AS company_namespace
  ON company_namespace.oid = company_relation.relnamespace
JOIN pg_catalog.pg_class AS link_relation
  ON link_relation.oid = to_regclass('public.client_company_links')
JOIN pg_catalog.pg_namespace AS link_namespace
  ON link_namespace.oid = link_relation.relnamespace
WHERE company_relation.oid = to_regclass('public.companies')
  AND company_namespace.oid = to_regnamespace('public')
  AND link_namespace.oid = to_regnamespace('public')
""".strip()

TARGET_COLUMNS_SQL = """
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('companies', 'client_company_links')
ORDER BY table_name, ordinal_position
""".strip()

TARGET_CONSTRAINTS_SQL = """
SELECT
    relation.relname AS table_name,
    pg_get_constraintdef(constraint_row.oid) AS definition,
    constraint_row.convalidated AS convalidated
FROM pg_constraint AS constraint_row
JOIN pg_class AS relation ON relation.oid = constraint_row.conrelid
JOIN pg_namespace AS namespace_row ON namespace_row.oid = relation.relnamespace
WHERE namespace_row.nspname = 'public'
  AND relation.relname IN ('companies', 'client_company_links')
ORDER BY relation.relname, constraint_row.conname
""".strip()

LOCAL_CLIENT_IDS_SQL = "SELECT id FROM public.clients ORDER BY id"

TARGET_COUNTS_SQL = """
SELECT
    (SELECT count(*) FROM public.companies)::bigint AS companies,
    (SELECT count(*) FROM public.client_company_links)::bigint AS client_company_links
""".strip()

TARGET_COMPANIES_SQL = f"""
SELECT {_COMPANY_COLUMN_SQL}
FROM public.companies
ORDER BY id
""".strip()

TARGET_LINKS_SQL = f"""
SELECT {_LINK_COLUMN_SQL}
FROM public.client_company_links
ORDER BY id
""".strip()

COMPANY_INSERT_SQL = f"""
WITH projected AS (
    SELECT *
    FROM jsonb_populate_record(NULL::public.companies, $1::jsonb)
)
INSERT INTO public.companies ({_COMPANY_COLUMN_SQL})
SELECT {_COMPANY_COLUMN_SQL}
FROM projected
""".strip()

LINK_INSERT_SQL = f"""
WITH projected AS (
    SELECT *
    FROM jsonb_populate_record(NULL::public.client_company_links, $1::jsonb)
)
INSERT INTO public.client_company_links ({_LINK_COLUMN_SQL})
SELECT {_LINK_COLUMN_SQL}
FROM projected
""".strip()

SET_LOCAL_SEARCH_PATH_SQL = "SET LOCAL search_path = public"
SET_LOCAL_LOCK_TIMEOUT_SQL = "SET LOCAL lock_timeout = '5000ms'"
SET_LOCAL_STATEMENT_TIMEOUT_SQL = "SET LOCAL statement_timeout = '30000ms'"
CLIENTS_SHARE_LOCK_SQL = "LOCK TABLE public.clients IN SHARE MODE"
ADVISORY_XACT_LOCK_SQL = (
    "SELECT pg_advisory_xact_lock(4815162342)"
)
TARGET_TABLE_LOCK_SQL = (
    "LOCK TABLE public.companies, public.client_company_links "
    "IN SHARE ROW EXCLUSIVE MODE"
)

SEQUENCE_ATTEST_SQL = """
WITH ownership AS (
    SELECT
        sequence_namespace.nspname || '.' || sequence_relation.relname AS sequence_name,
        table_namespace.nspname || '.' || table_relation.relname || '.' || attribute.attname AS owned_by,
        sequence_definition.seqincrement AS increment_by,
        sequence_definition.seqcycle AS cycle
    FROM pg_catalog.pg_depend
    JOIN pg_catalog.pg_class AS sequence_relation
      ON sequence_relation.oid = pg_depend.objid
    JOIN pg_catalog.pg_namespace AS sequence_namespace
      ON sequence_namespace.oid = sequence_relation.relnamespace
    JOIN pg_catalog.pg_sequence AS sequence_definition
      ON sequence_definition.seqrelid = sequence_relation.oid
    JOIN pg_catalog.pg_class AS table_relation
      ON table_relation.oid = pg_depend.refobjid
    JOIN pg_catalog.pg_namespace AS table_namespace
      ON table_namespace.oid = table_relation.relnamespace
    JOIN pg_catalog.pg_attribute AS attribute
      ON attribute.attrelid = table_relation.oid
     AND attribute.attnum = pg_depend.refobjsubid
    WHERE sequence_relation.relkind = 'S'
      AND sequence_namespace.nspname = 'public'
)
SELECT
    'public.companies_id_seq' AS companies_sequence,
    (SELECT owned_by FROM ownership WHERE sequence_name = 'public.companies_id_seq') AS companies_owned_by,
    (SELECT last_value FROM public.companies_id_seq) AS companies_last_value,
    (SELECT is_called FROM public.companies_id_seq) AS companies_is_called,
    (SELECT increment_by FROM ownership WHERE sequence_name = 'public.companies_id_seq') AS companies_increment_by,
    (SELECT cycle FROM ownership WHERE sequence_name = 'public.companies_id_seq') AS companies_cycle,
    'public.client_company_links_id_seq' AS links_sequence,
    (SELECT owned_by FROM ownership WHERE sequence_name = 'public.client_company_links_id_seq') AS links_owned_by,
    (SELECT last_value FROM public.client_company_links_id_seq) AS links_last_value,
    (SELECT is_called FROM public.client_company_links_id_seq) AS links_is_called,
    (SELECT increment_by FROM ownership WHERE sequence_name = 'public.client_company_links_id_seq') AS links_increment_by,
    (SELECT cycle FROM ownership WHERE sequence_name = 'public.client_company_links_id_seq') AS links_cycle
""".strip()

def _protected_invariant_sql(table: str) -> str:
    if table not in PROTECTED_TABLES:
        raise ValueError("protected invariant table is not allowlisted")
    return f"""
WITH column_shape AS (
    SELECT md5(string_agg(
        column_name || ':' || data_type || ':' || is_nullable,
        ',' ORDER BY ordinal_position
    )) AS schema_digest
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = '{table}'
), row_hashes AS (
    SELECT md5(to_jsonb(protected_row)::text) AS row_hash
    FROM public.{table} AS protected_row
), ordered_rows AS (
    SELECT row_hash FROM row_hashes ORDER BY row_hash
)
SELECT
    (SELECT count(*) FROM ordered_rows)::bigint AS row_count,
    (SELECT schema_digest FROM column_shape) AS schema_digest,
    md5(COALESCE((SELECT string_agg(row_hash, ',' ORDER BY row_hash) FROM ordered_rows), '')) AS row_digest
""".strip()


PROTECTED_INVARIANT_SQL = tuple(
    _protected_invariant_sql(table) for table in PROTECTED_TABLES
)

ALL_LOCAL_SQL = (
    SET_LOCAL_SEARCH_PATH_SQL,
    SET_LOCAL_LOCK_TIMEOUT_SQL,
    SET_LOCAL_STATEMENT_TIMEOUT_SQL,
    CLIENTS_SHARE_LOCK_SQL,
    TARGET_TABLE_LOCK_SQL,
    ADVISORY_XACT_LOCK_SQL,
    TARGET_ATTEST_SQL,
    TARGET_COLUMNS_SQL,
    TARGET_CONSTRAINTS_SQL,
    SEQUENCE_ATTEST_SQL,
    LOCAL_CLIENT_IDS_SQL,
    TARGET_COUNTS_SQL,
    TARGET_COMPANIES_SQL,
    TARGET_LINKS_SQL,
    COMPANY_INSERT_SQL,
    LINK_INSERT_SQL,
    *PROTECTED_INVARIANT_SQL,
)


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SourceSnapshotError(f"{label} must be a positive integer")
    return value


def _count_value(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SourceSnapshotError(f"{label} must be a non-negative integer")
    return value


def _project_row(
    row: Mapping[str, Any], columns: Sequence[str], *, row_kind: str
) -> JsonRow:
    missing = [column for column in columns if column not in row]
    if missing:
        raise SourceSnapshotError(
            f"source {row_kind} row is missing allowlisted columns"
        )
    projected = {column: row[column] for column in columns}
    _positive_int(projected["id"], label=f"source {row_kind} id")
    return projected


def compute_content_digest(
    *,
    canonical_row_bytes: bytes,
    domain: str,
    version: str,
    company_columns: Sequence[str],
    link_columns: Sequence[str],
) -> str:
    """Bind raw source row bytes to an explicit versioned column contract."""

    if not isinstance(canonical_row_bytes, bytes):
        raise TypeError("canonical source rows must be bytes")
    header = json.dumps(
        ["header", domain, version, list(company_columns), list(link_columns)],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(header + b"\n" + canonical_row_bytes).hexdigest()


def _digest_value(value: Any) -> Any:
    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, Decimal):
        return ["decimal", str(value)]
    if isinstance(value, UUID):
        return ["string", str(value)]
    if isinstance(value, datetime):
        return ["string", value.isoformat()]
    if isinstance(value, date):
        return ["string", value.isoformat()]
    if isinstance(value, float):
        raise TypeError("float is not lossless")
    if isinstance(value, str):
        return ["string", value]
    if isinstance(value, Mapping):
        return [
            "object",
            [[key, _digest_value(value[key])] for key in sorted(value)],
        ]
    if isinstance(value, (list, tuple)):
        return ["array", [_digest_value(item) for item in value]]
    raise TypeError("unsupported canonical value type")


def _projection_canonical_bytes(
    *,
    companies: Sequence[Mapping[str, Any]],
    eligible_links: Sequence[Mapping[str, Any]],
) -> bytes:
    records: list[Any] = [
        [
            "header",
            PROJECTION_DIGEST_DOMAIN,
            PROJECTION_DIGEST_VERSION,
            list(COMPANY_COLUMNS),
            list(LINK_COLUMNS),
        ]
    ]
    records.extend(
        [
            "company",
            [
                _digest_value(
                    json.loads(row[column], parse_float=Decimal)
                    if column == "custom_fields" and isinstance(row[column], str)
                    else row[column]
                )
                for column in COMPANY_COLUMNS
            ],
        ]
        for row in sorted(companies, key=lambda row: int(row["id"]))
    )
    records.extend(
        ["link", [_digest_value(row[column]) for column in LINK_COLUMNS]]
        for row in sorted(eligible_links, key=lambda row: int(row["id"]))
    )
    return b"\n".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode()
        for record in records
    ) + b"\n"


def compute_projection_digest(
    *,
    companies: Sequence[Mapping[str, Any]],
    eligible_links: Sequence[Mapping[str, Any]],
) -> str:
    return hashlib.sha256(
        _projection_canonical_bytes(
            companies=companies, eligible_links=eligible_links
        )
    ).hexdigest()


EMPTY_TARGET_DIGEST = compute_projection_digest(companies=(), eligible_links=())


def _target_project_row(
    row: Mapping[str, Any], columns: Sequence[str], *, row_kind: str
) -> JsonRow:
    missing = [column for column in columns if column not in row]
    if missing:
        raise TargetContractError(
            f"target {row_kind} row is missing allowlisted columns"
        )
    projected = {column: row[column] for column in columns}
    _positive_int(projected["id"], label=f"target {row_kind} id")
    return projected


async def read_target_projection(conn: ConnectionLike) -> TargetProjection:
    """Acquire exact target rows and derive the canonical digest in Python."""

    company_rows = await conn.fetch(TARGET_COMPANIES_SQL)
    link_rows = await conn.fetch(TARGET_LINKS_SQL)
    companies = tuple(
        _target_project_row(row, COMPANY_COLUMNS, row_kind="company")
        for row in company_rows
    )
    links = tuple(
        _target_project_row(row, LINK_COLUMNS, row_kind="link")
        for row in link_rows
    )
    return TargetProjection(
        companies=companies,
        links=links,
        digest=compute_projection_digest(
            companies=companies, eligible_links=links
        ),
    )


def _source_metadata(record: Mapping[str, Any]) -> SourceMetadata:
    database = record.get("database")
    if database != EXPECTED_SOURCE_DATABASE:
        raise SourceSnapshotError("source database attestation failed")
    role = record.get("role")
    if role != EXPECTED_SOURCE_ROLE:
        raise SourceSnapshotError("source role attestation failed")
    if record.get("transaction_read_only") != "on":
        raise SourceSnapshotError("source read-only attestation failed")

    snapshot_at = record.get("snapshot_at")
    if not isinstance(snapshot_at, str) or not snapshot_at:
        raise SourceSnapshotError("source snapshot timestamp is missing")

    companies_max_updated_at = record.get("companies_max_updated_at")
    links_max_updated_at = record.get("links_max_updated_at")
    if companies_max_updated_at is not None and not isinstance(
        companies_max_updated_at, str
    ):
        raise SourceSnapshotError("source company freshness metadata is invalid")
    if links_max_updated_at is not None and not isinstance(
        links_max_updated_at, str
    ):
        raise SourceSnapshotError("source link freshness metadata is invalid")

    return SourceMetadata(
        snapshot_at=snapshot_at,
        companies_count=_count_value(
            record.get("companies_count"), label="source companies_count"
        ),
        links_count=_count_value(
            record.get("links_count"), label="source links_count"
        ),
        companies_max_updated_at=companies_max_updated_at,
        links_max_updated_at=links_max_updated_at,
    )


def _validate_snapshot_graph(snapshot: SourceSnapshot) -> None:
    if not snapshot.companies:
        raise SourceSnapshotError("source company snapshot is empty")

    company_ids: set[int] = set()
    for company in snapshot.companies:
        company_id = _positive_int(company["id"], label="source company id")
        if company_id in company_ids:
            raise SourceSnapshotError("source company ids are not unique")
        company_ids.add(company_id)

    link_ids: set[int] = set()
    link_pairs: set[tuple[int, int]] = set()
    for link in snapshot.links:
        link_id = _positive_int(link["id"], label="source link id")
        client_id = _positive_int(link["client_id"], label="source link client_id")
        company_id = _positive_int(
            link["company_id"], label="source link company_id"
        )
        if link_id in link_ids:
            raise SourceSnapshotError("source link ids are not unique")
        if company_id not in company_ids:
            raise SourceSnapshotError("source link references an absent company")
        pair = (client_id, company_id)
        if pair in link_pairs:
            raise SourceSnapshotError("source client/company link pairs are not unique")
        link_ids.add(link_id)
        link_pairs.add(pair)


def parse_source_snapshot(stdout: bytes) -> SourceSnapshot:
    """Parse and validate an in-memory JSON-lines snapshot without echoing rows."""

    metadata: SourceMetadata | None = None
    companies: list[JsonRow] = []
    links: list[JsonRow] = []

    if not isinstance(stdout, bytes):
        raise SourceSnapshotError("source snapshot transport must be binary")
    canonical_rows = bytearray()
    for line_number, raw_line in enumerate(stdout.splitlines(keepends=True), start=1):
        line = raw_line.rstrip(b"\r\n")
        if not line.strip():
            continue
        try:
            record = json.loads(line, parse_float=Decimal)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SourceSnapshotError(
                f"invalid JSON at source output line {line_number}"
            ) from exc
        if not isinstance(record, dict):
            raise SourceSnapshotError(
                f"invalid record type at source output line {line_number}"
            )

        kind = record.get("kind")
        if kind == "meta":
            if metadata is not None:
                raise SourceSnapshotError("source emitted more than one metadata record")
            metadata = _source_metadata(record)
            continue
        if kind not in {"company", "link"}:
            raise SourceSnapshotError(
                f"invalid record kind at source output line {line_number}"
            )
        row = record.get("row")
        if not isinstance(row, dict):
            raise SourceSnapshotError(
                f"invalid {kind} row at source output line {line_number}"
            )
        if kind == "company":
            companies.append(_project_row(row, COMPANY_COLUMNS, row_kind="company"))
        else:
            projected_link = _project_row(row, LINK_COLUMNS, row_kind="link")
            _positive_int(
                projected_link["client_id"], label="source link client_id"
            )
            _positive_int(
                projected_link["company_id"], label="source link company_id"
            )
            links.append(projected_link)
        canonical_rows.extend(raw_line)

    if metadata is None:
        raise SourceSnapshotError("source metadata record is missing")
    if metadata.companies_count != len(companies):
        raise SourceSnapshotError("source company count mismatch")
    if metadata.links_count != len(links):
        raise SourceSnapshotError("source link count mismatch")

    snapshot = SourceSnapshot(
        metadata=metadata,
        companies=tuple(companies),
        links=tuple(links),
        canonical_row_bytes=bytes(canonical_rows),
        content_digest=compute_content_digest(
            canonical_row_bytes=bytes(canonical_rows),
            domain=CONTENT_DIGEST_DOMAIN,
            version=CONTENT_DIGEST_VERSION,
            company_columns=COMPANY_COLUMNS,
            link_columns=LINK_COLUMNS,
        ),
    )
    _validate_snapshot_graph(snapshot)
    return snapshot


def fetch_source_snapshot(
    *,
    run: RunCallable = subprocess.run,
    timeout_seconds: int = 180,
) -> SourceSnapshot:
    """Read one canonical PROD snapshot through the existing ``pg.sh`` authority."""

    command = [
        "bash",
        str(PG_SH),
        "-X",
        "-q",
        "-tA",
        "-v",
        "ON_ERROR_STOP=1",
    ]
    try:
        result = run(
            command,
            input=SOURCE_SNAPSHOT_SQL.encode(),
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SourceSnapshotError("source snapshot command could not complete") from exc
    if result.returncode != 0:
        raise SourceSnapshotError(
            f"source snapshot command failed with exit {result.returncode}"
        )
    return parse_source_snapshot(result.stdout)


def source_shape_digest(snapshot: SourceSnapshot) -> str:
    """Hash only entity/link types and integer identities, never row content."""

    digest = hashlib.sha256()
    for company in snapshot.companies:
        digest.update(f"company:{company['id']}\n".encode())
    for link in snapshot.links:
        digest.update(
            (
                f"link:{link['id']}:{link['client_id']}:{link['company_id']}\n"
            ).encode()
        )
    return digest.hexdigest()


def build_projection_plan(
    snapshot: SourceSnapshot, *, local_client_ids: set[int]
) -> ProjectionPlan:
    """Keep every company and only links whose client already exists locally."""

    if any(
        isinstance(client_id, bool) or not isinstance(client_id, int)
        for client_id in local_client_ids
    ):
        raise TargetContractError("local client id set contains an invalid value")
    eligible = tuple(
        link for link in snapshot.links if link["client_id"] in local_client_ids
    )
    return ProjectionPlan(
        companies=snapshot.companies,
        eligible_links=eligible,
        rejected_missing_local_client=len(snapshot.links) - len(eligible),
        projection_digest=compute_projection_digest(
            companies=snapshot.companies, eligible_links=eligible
        ),
    )


def validate_target_dsn(dsn: str) -> None:
    """Fail closed unless the DSN points exactly at loopback ``nuzantara_dev``."""

    try:
        parsed = urlparse(dsn)
        port = parsed.port
    except ValueError as exc:
        raise ApplyGateError("target DSN is malformed") from exc
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ApplyGateError("target DSN must use PostgreSQL")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ApplyGateError("target DSN must use a loopback host")
    if port not in {None, 5432}:
        raise ApplyGateError("target DSN must use the local PostgreSQL port")
    if parsed.username != EXPECTED_TARGET_ROLE:
        raise ApplyGateError("target DSN must use the local nuzantara role")
    if parsed.path != f"/{EXPECTED_TARGET_DATABASE}":
        raise ApplyGateError("target DSN must name nuzantara_dev")
    if parsed.query or parsed.fragment or parsed.params:
        raise ApplyGateError("target DSN options are not allowed")


def validate_apply_request(
    *,
    apply: bool,
    dsn: str,
    environ: Mapping[str, str],
    expected_content_digest: str | None,
    actual_content_digest: str,
) -> None:
    """Require the explicit CLI flag, environment gate, and exact dev target."""

    if not apply:
        raise ApplyGateError("write requires the explicit --apply flag")
    if environ.get(WRITE_ENABLE_ENV) != "true":
        raise ApplyGateError(f"write requires {WRITE_ENABLE_ENV}=true")
    if expected_content_digest is None or not re.fullmatch(
        r"[0-9a-f]{64}", expected_content_digest
    ):
        raise ApplyGateError("write requires an expected content digest")
    if expected_content_digest != actual_content_digest:
        raise ApplyGateError("source content digest mismatch")
    validate_target_dsn(dsn)


def _normalized_constraint(definition: str) -> str:
    return re.sub(r"\s+", " ", definition.upper().replace('"', "")).strip()


def _has_constraint(definitions: Sequence[str], pattern: str) -> bool:
    return any(re.search(pattern, _normalized_constraint(item)) for item in definitions)


def validate_target_contract(
    columns: Mapping[str, set[str]],
    constraints: Mapping[str, Sequence[str]],
) -> None:
    """Validate required columns, keys, uniqueness, and link foreign keys."""

    required_columns = {
        "companies": set(COMPANY_COLUMNS),
        "client_company_links": set(LINK_COLUMNS),
    }
    for table, required in required_columns.items():
        if not required.issubset(columns.get(table, set())):
            raise TargetContractError(f"target {table} column allowlist is incomplete")

    company_constraints = constraints.get("companies", ())
    link_constraints = constraints.get("client_company_links", ())
    if not _has_constraint(company_constraints, r"PRIMARY KEY \(ID\)"):
        raise TargetContractError("target companies primary key is missing")
    if not _has_constraint(link_constraints, r"PRIMARY KEY \(ID\)"):
        raise TargetContractError("target link primary key is missing")
    if not _has_constraint(
        link_constraints, r"UNIQUE \(CLIENT_ID, COMPANY_ID\)"
    ):
        raise TargetContractError("target client/company uniqueness is missing")
    if not _has_constraint(
        link_constraints,
        r"FOREIGN KEY \(CLIENT_ID\) REFERENCES (?:PUBLIC\.)?CLIENTS\(ID\)",
    ):
        raise TargetContractError("target client_id foreign key is missing")
    if not _has_constraint(
        link_constraints,
        r"FOREIGN KEY \(COMPANY_ID\) REFERENCES (?:PUBLIC\.)?COMPANIES\(ID\)",
    ):
        raise TargetContractError("target company_id foreign key is missing")


def _has_validated_exact_foreign_key(
    rows: Sequence[Mapping[str, Any]], *, column: str, target_table: str
) -> bool:
    """Require the one FK needed by the projection, not a look-alike constraint."""

    pattern = (
        rf"^FOREIGN KEY \({column.upper()}\) REFERENCES "
        rf"(?:PUBLIC\.)?{target_table.upper()}\(ID\)(?: |$)"
    )
    return any(
        isinstance(row.get("definition"), str)
        and row.get("convalidated") is True
        and re.search(pattern, _normalized_constraint(row["definition"]))
        for row in rows
    )


def _attest_relation_identity(
    record: Mapping[str, Any],
    *,
    prefix: str,
    expected_relname: str,
    public_schema_oid: int,
) -> int:
    """Validate one public table through mutually consistent catalog facts."""

    relation_oid = record.get(f"{prefix}_relation_oid")
    regclass_oid = record.get(f"{prefix}_regclass_oid")
    namespace_oid = record.get(f"{prefix}_namespace_oid")
    for value in (relation_oid, regclass_oid, namespace_oid):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise TargetContractError(
                f"target {prefix} catalog OID attestation failed"
            )
    if relation_oid != regclass_oid or namespace_oid != public_schema_oid:
        raise TargetContractError(f"target {prefix} catalog identity failed")

    relation_text = record.get(f"{prefix}_relation")
    if relation_text not in {expected_relname, f"public.{expected_relname}"}:
        raise TargetContractError(f"target {prefix} relation attestation failed")
    if (
        record.get(f"{prefix}_namespace") != "public"
        or record.get(f"{prefix}_relname") != expected_relname
        or record.get(f"{prefix}_relkind") != "r"
    ):
        raise TargetContractError(f"target {prefix} catalog attestation failed")
    return cast(int, relation_oid)


async def attest_target(
    conn: ConnectionLike, *, expect_read_only: bool
) -> None:
    """Independently attest database, role, loopback server, port, and mode."""

    record = await conn.fetchrow(TARGET_ATTEST_SQL)
    if record is None:
        raise TargetContractError("target attestation returned no row")
    if record.get("database") != EXPECTED_TARGET_DATABASE:
        raise TargetContractError("target database attestation failed")
    if record.get("role") != EXPECTED_TARGET_ROLE:
        raise TargetContractError("target role attestation failed")
    if record.get("server_address") not in {"127.0.0.1", "::1"}:
        raise TargetContractError("target server is not loopback")
    if record.get("server_port") != 5432:
        raise TargetContractError("target server port attestation failed")
    expected_mode = "on" if expect_read_only else "off"
    if record.get("transaction_read_only") != expected_mode:
        raise TargetContractError("target transaction mode attestation failed")
    if record.get("search_path") != "public":
        raise TargetContractError("target search path attestation failed")
    schema_oid = record.get("public_schema_oid")
    if isinstance(schema_oid, bool) or not isinstance(schema_oid, int) or schema_oid <= 0:
        raise TargetContractError("target public schema attestation failed")
    companies_oid = _attest_relation_identity(
        record,
        prefix="companies",
        expected_relname="companies",
        public_schema_oid=schema_oid,
    )
    links_oid = _attest_relation_identity(
        record,
        prefix="links",
        expected_relname="client_company_links",
        public_schema_oid=schema_oid,
    )
    if companies_oid == links_oid:
        raise TargetContractError("target relation identities are not distinct")


async def assert_target_contract(conn: ConnectionLike) -> None:
    column_rows = await conn.fetch(TARGET_COLUMNS_SQL)
    constraint_rows = await conn.fetch(TARGET_CONSTRAINTS_SQL)
    columns: dict[str, set[str]] = {
        "companies": set(),
        "client_company_links": set(),
    }
    constraints: dict[str, list[str]] = {
        "companies": [],
        "client_company_links": [],
    }
    for row in column_rows:
        table = row.get("table_name")
        column = row.get("column_name")
        if table in columns and isinstance(column, str):
            columns[table].add(column)
    link_constraint_rows: list[Mapping[str, Any]] = []
    for row in constraint_rows:
        table = row.get("table_name")
        definition = row.get("definition")
        if table in constraints and isinstance(definition, str):
            constraints[table].append(definition)
    validate_target_contract(columns, constraints)
    for row in constraint_rows:
        if row.get("table_name") == "client_company_links":
            link_constraint_rows.append(row)
    if not _has_validated_exact_foreign_key(
        link_constraint_rows, column="client_id", target_table="clients"
    ):
        raise TargetContractError("target client_id foreign key is not exact and validated")
    if not _has_validated_exact_foreign_key(
        link_constraint_rows, column="company_id", target_table="companies"
    ):
        raise TargetContractError("target company_id foreign key is not exact and validated")


async def read_local_client_ids(conn: ConnectionLike) -> set[int]:
    rows = await conn.fetch(LOCAL_CLIENT_IDS_SQL)
    client_ids: set[int] = set()
    for row in rows:
        client_ids.add(_positive_int(row.get("id"), label="local client id"))
    return client_ids


async def read_target_counts(conn: ConnectionLike) -> dict[str, int]:
    row = await conn.fetchrow(TARGET_COUNTS_SQL)
    if row is None:
        raise TargetContractError("target count query returned no row")
    counts: dict[str, int] = {}
    for key in ("companies", "client_company_links"):
        value = row.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise TargetContractError("target count query returned an invalid value")
        counts[key] = value
    return counts


async def read_protected_invariants(
    conn: ConnectionLike,
) -> dict[str, InvariantState]:
    states: dict[str, InvariantState] = {}
    for table, sql in zip(PROTECTED_TABLES, PROTECTED_INVARIANT_SQL, strict=True):
        row = await conn.fetchrow(sql)
        if row is None:
            raise ProjectionInvariantError("protected table digest returned no row")
        count = row.get("row_count")
        schema_digest = row.get("schema_digest")
        digest = row.get("row_digest")
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or not isinstance(schema_digest, str)
            or not isinstance(digest, str)
        ):
            raise ProjectionInvariantError("protected table digest is invalid")
        states[table] = InvariantState(
            row_count=count, schema_digest=schema_digest, row_digest=digest
        )
    return states


def protected_shape_digest(states: Mapping[str, InvariantState]) -> str:
    digest = hashlib.sha256()
    for table in PROTECTED_TABLES:
        state = states.get(table)
        if state is None:
            raise ProjectionInvariantError("protected table digest set is incomplete")
        digest.update(
            f"{table}:{state.row_count}:{state.schema_digest}:{state.row_digest}\n".encode()
        )
    return digest.hexdigest()


def _plain_json(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, float):
        raise TypeError("float is not lossless")
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, Mapping):
        return "{" + ",".join(
            f"{json.dumps(str(key), ensure_ascii=False)}:{_plain_json(value[key])}"
            for key in sorted(value)
        ) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_plain_json(item) for item in value) + "]"
    raise TypeError("unsupported JSON value type")


def _json_payload(row: Mapping[str, Any], columns: Sequence[str]) -> tuple[str]:
    projected = {column: row[column] for column in columns}
    return (_plain_json(projected),)


def sequence_restart_value(
    *, last_value: int, is_called: bool, source_max_id: int
) -> int:
    for value, label, allow_zero in (
        (last_value, "sequence last value", False),
        (source_max_id, "source maximum id", True),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < (0 if allow_zero else 1)
            or value > 9223372036854775807
        ):
            raise TargetContractError(f"{label} is invalid")
    if not isinstance(is_called, bool):
        raise TargetContractError("sequence called state is invalid")
    effective_next = last_value + 1 if is_called else last_value
    restart = max(effective_next, source_max_id + 1)
    if restart > 9223372036854775807:
        raise TargetContractError("sequence restart exceeds bigint")
    return restart


_SEQUENCE_NAMES = {
    "public.companies_id_seq",
    "public.client_company_links_id_seq",
}


def sequence_restart_sql(sequence_name: str, restart: Any) -> str:
    if sequence_name not in _SEQUENCE_NAMES:
        raise TargetContractError("sequence name is not allowlisted")
    if (
        isinstance(restart, bool)
        or not isinstance(restart, int)
        or restart <= 0
        or restart > 9223372036854775807
    ):
        raise TargetContractError("sequence restart value is invalid")
    return f"ALTER SEQUENCE {sequence_name} RESTART WITH {restart}"


def classify_target_state(
    *,
    companies_count: int,
    links_count: int,
    actual_digest: str,
    desired_digest: str,
) -> str:
    if companies_count == 0 and links_count == 0:
        return "empty"
    if actual_digest == desired_digest:
        return "exact-noop"
    raise TargetContractError("target is neither empty nor the exact desired projection")


def _sequence_state(record: Mapping[str, Any] | None) -> tuple[int, bool, int, bool]:
    if record is None:
        raise TargetContractError("sequence attestation returned no row")
    exact = {
        "companies_sequence": "public.companies_id_seq",
        "companies_owned_by": "public.companies.id",
        "links_sequence": "public.client_company_links_id_seq",
        "links_owned_by": "public.client_company_links.id",
    }
    if any(record.get(key) != value for key, value in exact.items()):
        raise TargetContractError("sequence identity or ownership attestation failed")
    company_last = record.get("companies_last_value")
    company_called = record.get("companies_is_called")
    link_last = record.get("links_last_value")
    link_called = record.get("links_is_called")
    company_increment = record.get("companies_increment_by")
    company_cycle = record.get("companies_cycle")
    link_increment = record.get("links_increment_by")
    link_cycle = record.get("links_cycle")
    if (
        isinstance(company_increment, bool)
        or not isinstance(company_increment, int)
        or company_increment != 1
        or company_cycle is not False
        or isinstance(link_increment, bool)
        or not isinstance(link_increment, int)
        or link_increment != 1
        or link_cycle is not False
    ):
        raise TargetContractError("sequence definition attestation failed")
    if not isinstance(company_called, bool) or not isinstance(link_called, bool):
        raise TargetContractError("sequence called state attestation failed")
    if (
        isinstance(company_last, bool)
        or not isinstance(company_last, int)
        or company_last <= 0
    ):
        raise TargetContractError("sequence value attestation failed")
    if (
        isinstance(link_last, bool)
        or not isinstance(link_last, int)
        or link_last <= 0
    ):
        raise TargetContractError("sequence value attestation failed")
    return company_last, company_called, link_last, link_called


def _target_counts(target: TargetProjection) -> dict[str, int]:
    return {
        "companies": len(target.companies),
        "client_company_links": len(target.links),
    }


def _sequence_status(
    sequence_state: tuple[int, bool, int, bool], *, plan: ProjectionPlan
) -> dict[str, dict[str, int | bool]]:
    company_last, company_called, link_last, link_called = sequence_state
    company_next = company_last + 1 if company_called else company_last
    link_next = link_last + 1 if link_called else link_last
    company_source_max = max(row["id"] for row in plan.companies)
    link_source_max = max((row["id"] for row in plan.eligible_links), default=0)
    return {
        "companies": {
            "last_value": company_last,
            "is_called": company_called,
            "next_value": company_next,
            "source_max_id": company_source_max,
            "safe": company_next > company_source_max,
        },
        "client_company_links": {
            "last_value": link_last,
            "is_called": link_called,
            "next_value": link_next,
            "source_max_id": link_source_max,
            "safe": link_next > link_source_max,
        },
    }


def _assert_exact_target_projection(
    target: TargetProjection, *, plan: ProjectionPlan
) -> None:
    target_kind = classify_target_state(
        companies_count=len(target.companies),
        links_count=len(target.links),
        actual_digest=target.digest,
        desired_digest=plan.projection_digest,
    )
    if target_kind != "exact-noop":
        raise TargetContractError("target projection does not match the desired rows")


def _detached_apply_result(
    *,
    snapshot: SourceSnapshot,
    plan: ProjectionPlan,
    target_before_counts: Mapping[str, int],
    target_after_counts: Mapping[str, int],
    sequence_status: Mapping[str, Mapping[str, int | bool]],
    protected_before: Mapping[str, InvariantState],
    protected_after: Mapping[str, InvariantState],
    companies_inserted: int,
    links_inserted: int,
    invariant_digest: str,
    projection_digest: str,
    no_op: bool,
) -> ApplyResult:
    """Detach every transaction-accepted fact behind immutable containers."""

    return ApplyResult(
        accepted_source=_immutable_source_copy(snapshot),
        accepted_plan=_immutable_plan_copy(plan),
        source_content_digest=snapshot.content_digest,
        target_before_counts=_immutable_counts_copy(target_before_counts),
        target_after_counts=_immutable_counts_copy(target_after_counts),
        sequence_status=_immutable_sequence_status_copy(sequence_status),
        protected_before=_immutable_invariants_copy(protected_before),
        protected_after=_immutable_invariants_copy(protected_after),
        companies_inserted=companies_inserted,
        links_inserted=links_inserted,
        invariant_digest=invariant_digest,
        projection_digest=projection_digest,
        no_op=no_op,
    )


async def apply_projection(
    conn: ConnectionLike,
    snapshot: SourceSnapshot,
    *,
    expected_content_digest: str,
) -> ApplyResult:
    """Apply one attested projection in one serializable target transaction."""

    if (
        re.fullmatch(r"[0-9a-f]{64}", expected_content_digest) is None
        or expected_content_digest != snapshot.content_digest
    ):
        raise ApplyGateError("source content digest mismatch")

    async with conn.transaction(isolation="serializable", readonly=False):
        await conn.execute(SET_LOCAL_SEARCH_PATH_SQL)
        await conn.execute(SET_LOCAL_LOCK_TIMEOUT_SQL)
        await conn.execute(SET_LOCAL_STATEMENT_TIMEOUT_SQL)
        await conn.execute(CLIENTS_SHARE_LOCK_SQL)
        await conn.execute(TARGET_TABLE_LOCK_SQL)
        await conn.execute(ADVISORY_XACT_LOCK_SQL)

        await attest_target(conn, expect_read_only=False)
        await assert_target_contract(conn)
        sequence_state = _sequence_state(await conn.fetchrow(SEQUENCE_ATTEST_SQL))
        protected_before = await read_protected_invariants(conn)
        local_client_ids = await read_local_client_ids(conn)
        plan = build_projection_plan(
            snapshot, local_client_ids=local_client_ids
        )
        accepted_sequence_status = _sequence_status(sequence_state, plan=plan)

        target_before = await read_target_projection(conn)
        target_before_counts = _target_counts(target_before)
        target_kind = classify_target_state(
            companies_count=len(target_before.companies),
            links_count=len(target_before.links),
            actual_digest=target_before.digest,
            desired_digest=plan.projection_digest,
        )
        if target_kind == "exact-noop":
            company_last, company_called, link_last, link_called = sequence_state
            company_next = company_last + 1 if company_called else company_last
            link_next = link_last + 1 if link_called else link_last
            company_target_max = max(
                (row["id"] for row in target_before.companies), default=0
            )
            link_target_max = max(
                (row["id"] for row in target_before.links), default=0
            )
            if company_next <= company_target_max or link_next <= link_target_max:
                raise TargetContractError(
                    "exact-noop target sequence is not safely ahead of projected ids"
                )
            target_final = await read_target_projection(conn)
            _assert_exact_target_projection(target_final, plan=plan)
            await assert_target_contract(conn)
            protected_after = await read_protected_invariants(conn)
            if protected_before != protected_after:
                raise ProjectionInvariantError(
                    "a protected table changed during company projection"
                )
            return _detached_apply_result(
                snapshot=snapshot,
                plan=plan,
                target_before_counts=target_before_counts,
                target_after_counts=_target_counts(target_final),
                sequence_status=accepted_sequence_status,
                protected_before=protected_before,
                protected_after=protected_after,
                companies_inserted=0,
                links_inserted=0,
                invariant_digest=protected_shape_digest(protected_after),
                projection_digest=target_final.digest,
                no_op=True,
            )

        company_payloads = [
            _json_payload(row, COMPANY_COLUMNS) for row in plan.companies
        ]
        link_payloads = [
            _json_payload(row, LINK_COLUMNS) for row in plan.eligible_links
        ]
        await conn.executemany(COMPANY_INSERT_SQL, company_payloads)
        if link_payloads:
            await conn.executemany(LINK_INSERT_SQL, link_payloads)

        company_last, company_called, link_last, link_called = sequence_state
        company_source_max = max(row["id"] for row in plan.companies)
        link_source_max = max(
            (row["id"] for row in plan.eligible_links), default=0
        )
        company_restart = sequence_restart_value(
            last_value=company_last,
            is_called=company_called,
            source_max_id=company_source_max,
        )
        link_restart = sequence_restart_value(
            last_value=link_last,
            is_called=link_called,
            source_max_id=link_source_max,
        )
        await conn.execute(
            sequence_restart_sql("public.companies_id_seq", company_restart)
        )
        await conn.execute(
            sequence_restart_sql(
                "public.client_company_links_id_seq", link_restart
            )
        )

        protected_after = await read_protected_invariants(conn)
        if protected_before != protected_after:
            raise ProjectionInvariantError(
                "a protected table changed during company projection"
            )
        target_final = await read_target_projection(conn)
        _assert_exact_target_projection(target_final, plan=plan)
        await assert_target_contract(conn)

        return _detached_apply_result(
            snapshot=snapshot,
            plan=plan,
            target_before_counts=target_before_counts,
            target_after_counts=_target_counts(target_final),
            sequence_status=accepted_sequence_status,
            protected_before=protected_before,
            protected_after=protected_after,
            companies_inserted=len(company_payloads),
            links_inserted=len(link_payloads),
            invariant_digest=protected_shape_digest(protected_after),
            projection_digest=target_final.digest,
            no_op=False,
        )


def build_report(
    *,
    snapshot: SourceSnapshot,
    plan: ProjectionPlan,
    mode: str,
    target_before: Mapping[str, int] | None,
    target_after: Mapping[str, int] | None,
    invariant_digest: str,
    sequence_status: Mapping[str, Any],
    target_eligibility: str | None = None,
) -> dict[str, Any]:
    """Build a PII-free aggregate report; row content has no output path."""

    if mode not in {"dry-run", "apply"}:
        raise ValueError("invalid report mode")
    if target_eligibility not in {None, "not_evaluated"}:
        raise ValueError("invalid target eligibility state")

    count_keys = {"companies", "client_company_links"}

    def validated_counts(
        value: Mapping[str, int] | None, *, allow_none: bool
    ) -> dict[str, int] | None:
        if value is None:
            if allow_none:
                return None
            raise TargetContractError("report target counts are missing")
        if set(value) != count_keys:
            raise TargetContractError("report target counts are not allowlisted")
        result: dict[str, int] = {}
        for key in ("companies", "client_company_links"):
            count = value[key]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise TargetContractError("report target counts are invalid")
            result[key] = count
        return result

    allowed_sequences = {"companies", "client_company_links"}
    allowed_sequence_fields = {
        "last_value",
        "is_called",
        "next_value",
        "source_max_id",
        "safe",
    }
    if not set(sequence_status).issubset(allowed_sequences):
        raise TargetContractError("report sequence status is not allowlisted")
    safe_sequence_status: dict[str, dict[str, int | bool]] = {}
    for sequence, raw_status in sequence_status.items():
        if not isinstance(raw_status, Mapping) or set(raw_status) != allowed_sequence_fields:
            raise TargetContractError("report sequence details are not allowlisted")
        for key in ("last_value", "next_value", "source_max_id"):
            value = raw_status[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise TargetContractError("report sequence details are invalid")
        for key in ("is_called", "safe"):
            if not isinstance(raw_status[key], bool):
                raise TargetContractError("report sequence details are invalid")
        safe_sequence_status[sequence] = {
            key: raw_status[key] for key in allowed_sequence_fields
        }

    projection: dict[str, Any] = {
        "companies": len(plan.companies),
        "eligible_links": len(plan.eligible_links),
        "rejected_links_missing_local_client": plan.rejected_missing_local_client,
        "projection_digest": plan.projection_digest,
    }
    if target_eligibility == "not_evaluated":
        projection["target_eligibility"] = "not_evaluated"
        projection["eligible_links"] = "unknown"
        projection["rejected_links_missing_local_client"] = "unknown"
        projection["projection_digest"] = "unknown"

    report: dict[str, Any] = {
        "status": "ok",
        "mode": mode,
        "write_attempted": mode == "apply",
        "source": {
            "authority": "scripts/pg.sh:nuzantara_readonly",
            "snapshot_at": snapshot.metadata.snapshot_at,
            "companies_max_updated_at": (
                snapshot.metadata.companies_max_updated_at
            ),
            "links_max_updated_at": snapshot.metadata.links_max_updated_at,
            "companies": len(snapshot.companies),
            "links": len(snapshot.links),
            "content_digest": snapshot.content_digest,
            "type_identity_digest": source_shape_digest(snapshot),
        },
        "projection": projection,
        "target_before": validated_counts(
            target_before, allow_none=target_eligibility == "not_evaluated"
        ),
        "target_after": validated_counts(target_after, allow_none=True),
        "sequence_preflight": (
            None if target_eligibility == "not_evaluated" else safe_sequence_status
        ),
        "protected_type_digest": invariant_digest,
    }
    return report


async def _connect_target(
    dsn: str, *, read_only: bool
) -> ConnectionLike:
    server_settings = {
        "application_name": "intake_company_projection_dry_run"
        if read_only
        else "intake_company_projection_apply",
    }
    if read_only:
        server_settings["default_transaction_read_only"] = "on"
    connection = await asyncpg.connect(dsn, server_settings=server_settings)
    return cast(ConnectionLike, connection)


async def run_projection(
    *,
    apply: bool,
    dsn: str,
    environ: Mapping[str, str],
    run_subprocess: RunCallable = subprocess.run,
    connect: Callable[..., Awaitable[ConnectionLike]] = _connect_target,
    expected_content_digest: str | None = None,
) -> dict[str, Any]:
    """Orchestrate the bounded source snapshot and local projection."""

    snapshot = fetch_source_snapshot(run=run_subprocess)
    if not apply:
        plan = build_projection_plan(snapshot, local_client_ids=set())
        return build_report(
            snapshot=snapshot,
            plan=plan,
            mode="dry-run",
            target_before=None,
            target_after=None,
            invariant_digest="unknown",
            sequence_status={},
            target_eligibility="not_evaluated",
        )

    validate_apply_request(
        apply=True,
        dsn=dsn,
        environ=environ,
        expected_content_digest=expected_content_digest,
        actual_content_digest=snapshot.content_digest,
    )
    assert expected_content_digest is not None
    conn = await connect(dsn, read_only=False)
    try:
        apply_result = await apply_projection(
            conn,
            snapshot,
            expected_content_digest=expected_content_digest,
        )
        if apply_result.source_content_digest != snapshot.content_digest:
            raise ProjectionInvariantError(
                "accepted source content digest changed before reporting"
            )
        return build_report(
            snapshot=apply_result.accepted_source,
            plan=apply_result.accepted_plan,
            mode="apply",
            target_before=apply_result.target_before_counts,
            target_after=apply_result.target_after_counts,
            invariant_digest=apply_result.invariant_digest,
            sequence_status=apply_result.sequence_status,
        )
    finally:
        await conn.close()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run the canonical PROD company/link projection into local "
            "nuzantara_dev. Output is aggregate JSON only."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "apply the local projection (default: dry-run; also requires "
            f"{WRITE_ENABLE_ENV}=true)"
        ),
    )
    parser.add_argument(
        "--expected-content-digest",
        help="required exact source content SHA-256 when --apply is used",
    )
    return parser


def _safe_error(exc: BaseException) -> dict[str, str]:
    return {
        "status": "error",
        "error_type": type(exc).__name__,
        "reason": "projection failed; row payloads are suppressed",
    }


def _run_cli_projection(**kwargs: Any) -> dict[str, Any]:
    """Run the CLI coroutine even when an embedding host owns an event loop."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_projection(**kwargs))

    result: dict[str, dict[str, Any]] = {}
    failure: list[BaseException] = []

    def runner() -> None:
        try:
            result["report"] = asyncio.run(run_projection(**kwargs))
        except BaseException as exc:  # surfaced at the sanitized CLI boundary
            failure.append(exc)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if failure:
        raise failure[0]
    return result["report"]


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    dsn = os.environ.get(TARGET_DSN_ENV, DEFAULT_TARGET_DSN)
    started = time.monotonic()
    try:
        report = _run_cli_projection(
            apply=args.apply,
            dsn=dsn,
            environ=os.environ,
            expected_content_digest=args.expected_content_digest,
        )
    except Exception as exc:  # sanitized CLI boundary; never echo row-bearing errors
        sys.stderr.write(json.dumps(_safe_error(exc), sort_keys=True) + "\n")
        return 2
    report["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    sys.stdout.write(json.dumps(report, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
