"""Contract tests for the bounded PROD -> dev company projection.

All rows are synthetic and every database/subprocess boundary is faked.  These
tests must never contact Postgres, start the Fly proxy, or mutate an intake
table.
"""

from __future__ import annotations

import asyncio
import copy
import decimal
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "intake_company_projection.py"

EXPECTED_COMPANY_COLUMNS = (
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

EXPECTED_LINK_COLUMNS = (
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

_PROJECTION_DIGEST_DOMAIN = "nuzantara:intake-company-projection"
_PROJECTION_DIGEST_VERSION = "1"
EXPECTED_PROTECTED_TABLES = (
    "clients",
    "intake_queue",
    "document_instances",
    "document_routing_proposal",
    "intake_commit_audit",
)


def _independent_digest_value(value: Any) -> Any:
    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, decimal.Decimal):
        return ["decimal", str(value)]
    if isinstance(value, float):
        raise TypeError("float is not lossless")
    if isinstance(value, str):
        return ["string", value]
    if isinstance(value, Mapping):
        return [
            "object",
            [
                [key, _independent_digest_value(value[key])]
                for key in sorted(value)
            ],
        ]
    if isinstance(value, (list, tuple)):
        return ["array", [_independent_digest_value(item) for item in value]]
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def _independent_projection_bytes(
    *,
    companies: tuple[Mapping[str, Any], ...],
    eligible_links: tuple[Mapping[str, Any], ...],
    company_columns: tuple[str, ...] = EXPECTED_COMPANY_COLUMNS,
    link_columns: tuple[str, ...] = EXPECTED_LINK_COLUMNS,
) -> bytes:
    records: list[Any] = [
        [
            "header",
            _PROJECTION_DIGEST_DOMAIN,
            _PROJECTION_DIGEST_VERSION,
            list(company_columns),
            list(link_columns),
        ]
    ]
    records.extend(
        ["company", [_independent_digest_value(row[column]) for column in company_columns]]
        for row in sorted(companies, key=lambda row: int(row["id"]))
    )
    records.extend(
        ["link", [_independent_digest_value(row[column]) for column in link_columns]]
        for row in sorted(eligible_links, key=lambda row: int(row["id"]))
    )
    return b"\n".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode()
        for record in records
    ) + b"\n"


def _independent_projection_digest(
    *,
    companies: tuple[Mapping[str, Any], ...],
    eligible_links: tuple[Mapping[str, Any], ...],
    company_columns: tuple[str, ...] = EXPECTED_COMPANY_COLUMNS,
    link_columns: tuple[str, ...] = EXPECTED_LINK_COLUMNS,
) -> str:
    return hashlib.sha256(
        _independent_projection_bytes(
            companies=companies,
            eligible_links=eligible_links,
            company_columns=company_columns,
            link_columns=link_columns,
        )
    ).hexdigest()


def _load() -> Any:
    spec = importlib.util.spec_from_file_location(
        "intake_company_projection_under_test", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _company(company_id: int, *, marker: str = "SYNTHETIC COMPANY") -> dict[str, Any]:
    row = dict.fromkeys(EXPECTED_COMPANY_COLUMNS)
    row.update(
        {
            "id": company_id,
            "uuid": f"00000000-0000-4000-8000-{company_id:012d}",
            "company_name": marker,
            "company_type": "PT PMA",
            "status": "active",
            "setup_progress": 0,
            "custom_fields": {},
            "created_at": "2026-08-01T00:00:00+00:00",
            "updated_at": "2026-08-02T00:00:00+00:00",
        }
    )
    return row


def _link(link_id: int, client_id: int, company_id: int) -> dict[str, Any]:
    row = dict.fromkeys(EXPECTED_LINK_COLUMNS)
    row.update(
        {
            "id": link_id,
            "client_id": client_id,
            "company_id": company_id,
            "role": "shareholder",
            "is_primary": True,
            "status": "active",
            "created_at": "2026-08-01T00:00:00+00:00",
            "updated_at": "2026-08-02T00:00:00+00:00",
        }
    )
    return row


def _snapshot_stdout(
    companies: list[dict[str, Any]],
    links: list[dict[str, Any]],
    *,
    meta_overrides: Mapping[str, Any] | None = None,
) -> bytes:
    meta: dict[str, Any] = {
        "kind": "meta",
        "database": "nuzantara_rag",
        "role": "nuzantara_readonly",
        "transaction_read_only": "on",
        "snapshot_at": "2026-08-19T01:02:03+00:00",
        "companies_count": len(companies),
        "links_count": len(links),
        "companies_max_updated_at": "2026-08-02T00:00:00+00:00",
        "links_max_updated_at": "2026-08-02T00:00:00+00:00",
    }
    meta.update(meta_overrides or {})
    records = [meta]
    records.extend({"kind": "company", "row": row} for row in companies)
    records.extend({"kind": "link", "row": row} for row in links)
    return ("\n".join(json.dumps(record) for record in records) + "\n").encode()


class _Runner:
    def __init__(self, stdout: bytes, *, returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = b"SYNTHETIC STDERR MUST NOT BE ECHOED"
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        self.calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=self.returncode,
            stdout=self.stdout,
            stderr=self.stderr,
        )


def test_schema_allowlists_are_exact_and_source_only_columns_are_excluded() -> None:
    mod = _load()
    assert mod.COMPANY_COLUMNS == EXPECTED_COMPANY_COLUMNS
    assert mod.LINK_COLUMNS == EXPECTED_LINK_COLUMNS
    assert set(mod.SOURCE_ONLY_COMPANY_COLUMNS) == {
        "geo_point",
        "rdtr_zone_code",
        "geocoded_at",
        "geocode_source",
        "tax_dept_folder_id",
    }
    assert set(mod.COMPANY_COLUMNS).isdisjoint(mod.SOURCE_ONLY_COMPANY_COLUMNS)


def test_script_help_runs_and_defaults_to_dry_run() -> None:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(_REPO_ROOT / "apps" / "backend-rag"),
    }
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "--apply" in result.stdout
    assert "--expected-content-digest" in result.stdout
    assert "dry-run" in result.stdout.lower()


def test_actual_main_default_dry_run_never_connects_to_target_or_writes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(_snapshot_stdout([_company(101)], []))
    target_connects = 0
    writes = 0

    async def forbidden_target_connect(*args: Any, **kwargs: Any) -> Any:
        nonlocal target_connects
        target_connects += 1
        raise AssertionError("default dry-run connected to target")

    async def forbidden_apply(*args: Any, **kwargs: Any) -> Any:
        nonlocal writes
        writes += 1
        raise AssertionError("default dry-run attempted a write")

    monkeypatch.setattr(mod, "fetch_source_snapshot", lambda **kwargs: snapshot)
    monkeypatch.setattr(mod.asyncpg, "connect", forbidden_target_connect)
    monkeypatch.setattr(mod, "apply_projection", forbidden_apply)

    assert mod.main([]) == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert captured.err == ""
    assert report["mode"] == "dry-run"
    assert report["write_attempted"] is False
    assert target_connects == 0
    assert writes == 0


def test_prod_snapshot_uses_one_pg_sh_read_only_json_stream() -> None:
    mod = _load()
    company = _company(101)
    company["geo_point"] = "SOURCE_ONLY"
    company["unexpected_source_field"] = "DROP_ME"
    runner = _Runner(_snapshot_stdout([company], [_link(201, 301, 101)]))

    snapshot = mod.fetch_source_snapshot(run=runner)

    assert len(runner.calls) == 1
    positional, kwargs = runner.calls[0]
    command = positional[0]
    assert command[:2] == ["bash", str(_REPO_ROOT / "scripts" / "pg.sh")]
    assert "-q" in command and "-tA" in command and "ON_ERROR_STOP=1" in command
    sql = kwargs["input"]
    assert isinstance(sql, bytes)
    decoded_sql = sql.decode()
    assert "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY" in decoded_sql
    assert decoded_sql.count("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY") == 1
    assert decoded_sql.count("COMMIT") == 1
    assert "current_database()" in decoded_sql
    assert "current_user" in decoded_sql
    assert "current_setting('transaction_read_only')" in decoded_sql
    assert "FROM public.companies" in decoded_sql
    assert "FROM public.client_company_links" in decoded_sql
    assert decoded_sql.count("ORDER BY id") == 2
    for verb in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "ALTER"):
        assert not re.search(rf"\b{verb}\b", decoded_sql.upper())
    assert snapshot.companies[0]["company_name"] == "SYNTHETIC COMPANY"
    assert set(snapshot.companies[0]) == set(EXPECTED_COMPANY_COLUMNS)
    assert "geo_point" not in snapshot.companies[0]
    assert "unexpected_source_field" not in snapshot.companies[0]
    exact_row_bytes = b"\n".join(runner.stdout.splitlines()[1:]) + b"\n"
    assert snapshot.canonical_row_bytes == exact_row_bytes


def test_content_digest_binds_domain_version_ordered_columns_and_exact_row_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load()
    raw = _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    baseline = mod.parse_source_snapshot(raw)
    original_domain = mod.CONTENT_DIGEST_DOMAIN
    original_version = mod.CONTENT_DIGEST_VERSION
    assert isinstance(mod.CONTENT_DIGEST_DOMAIN, str) and mod.CONTENT_DIGEST_DOMAIN
    assert isinstance(mod.CONTENT_DIGEST_VERSION, str) and mod.CONTENT_DIGEST_VERSION
    assert baseline.content_digest == mod.compute_content_digest(
        canonical_row_bytes=baseline.canonical_row_bytes,
        domain=mod.CONTENT_DIGEST_DOMAIN,
        version=mod.CONTENT_DIGEST_VERSION,
        company_columns=EXPECTED_COMPANY_COLUMNS,
        link_columns=EXPECTED_LINK_COLUMNS,
    )

    monkeypatch.setattr(mod, "CONTENT_DIGEST_DOMAIN", "mutated-domain")
    assert mod.parse_source_snapshot(raw).content_digest != baseline.content_digest
    monkeypatch.setattr(mod, "CONTENT_DIGEST_DOMAIN", original_domain)
    monkeypatch.setattr(mod, "CONTENT_DIGEST_VERSION", "mutated-version")
    assert mod.parse_source_snapshot(raw).content_digest != baseline.content_digest
    monkeypatch.setattr(mod, "CONTENT_DIGEST_VERSION", original_version)

    reordered = (EXPECTED_COMPANY_COLUMNS[1], EXPECTED_COMPANY_COLUMNS[0], *EXPECTED_COMPANY_COLUMNS[2:])
    assert mod.compute_content_digest(
        canonical_row_bytes=baseline.canonical_row_bytes,
        domain="contract-domain",
        version="contract-version",
        company_columns=reordered,
        link_columns=EXPECTED_LINK_COLUMNS,
    ) != mod.compute_content_digest(
        canonical_row_bytes=baseline.canonical_row_bytes,
        domain="contract-domain",
        version="contract-version",
        company_columns=EXPECTED_COMPANY_COLUMNS,
        link_columns=EXPECTED_LINK_COLUMNS,
    )

    reordered_links = (EXPECTED_LINK_COLUMNS[1], EXPECTED_LINK_COLUMNS[0], *EXPECTED_LINK_COLUMNS[2:])
    assert mod.compute_content_digest(
        canonical_row_bytes=baseline.canonical_row_bytes,
        domain="contract-domain",
        version="contract-version",
        company_columns=EXPECTED_COMPANY_COLUMNS,
        link_columns=reordered_links,
    ) != mod.compute_content_digest(
        canonical_row_bytes=baseline.canonical_row_bytes,
        domain="contract-domain",
        version="contract-version",
        company_columns=EXPECTED_COMPANY_COLUMNS,
        link_columns=EXPECTED_LINK_COLUMNS,
    )


def test_numeric_values_are_lossless_and_never_roundtrip_through_float() -> None:
    mod = _load()
    company = _company(101)
    company["setup_progress"] = decimal.Decimal("0.123456789012345678901234567890")
    base = _snapshot_stdout([_company(101)], [])
    line = base.splitlines()[1].decode()
    line = line.replace('"setup_progress": 0', '"setup_progress": 0.123456789012345678901234567890')
    raw = base.splitlines()[0] + b"\n" + line.encode() + b"\n"

    snapshot = mod.parse_source_snapshot(raw)

    value = snapshot.companies[0]["setup_progress"]
    assert not isinstance(value, float)
    assert decimal.Decimal(str(value)) == company["setup_progress"]
    assert b"0.123456789012345678901234567890" in snapshot.canonical_row_bytes


@pytest.mark.parametrize(
    ("overrides", "expected_fragment"),
    [
        ({"database": "not_prod"}, "source database attestation failed"),
        ({"role": "write_role"}, "source role attestation failed"),
        ({"transaction_read_only": "off"}, "source read-only attestation failed"),
        ({"companies_count": 99}, "source company count mismatch"),
    ],
)
def test_prod_snapshot_attestation_fails_closed(
    overrides: Mapping[str, Any], expected_fragment: str
) -> None:
    mod = _load()
    stdout = _snapshot_stdout([_company(101)], [], meta_overrides=overrides)
    with pytest.raises(mod.SourceSnapshotError, match=expected_fragment):
        mod.parse_source_snapshot(stdout)


def test_malformed_source_json_error_never_echoes_payload_or_stderr() -> None:
    mod = _load()
    private_marker = "SYNTHETIC_PRIVATE_MARKER"
    malformed = _snapshot_stdout([_company(101)], []) + f'{{"{private_marker}":'.encode()
    runner = _Runner(malformed)

    with pytest.raises(mod.SourceSnapshotError) as exc_info:
        mod.fetch_source_snapshot(run=runner)

    message = str(exc_info.value)
    assert "output line" in message
    assert private_marker not in message
    assert "SYNTHETIC STDERR" not in message


@pytest.mark.parametrize(
    "mutate",
    [
        lambda records: [records[0], records[0], *records[1:]],
        lambda records: [*records, {"kind": "unknown", "row": {}}],
        lambda records: [*records, records[1]],
        lambda records: [*records, records[2]],
    ],
    ids=("duplicate-meta", "unknown-record", "duplicate-company", "duplicate-link"),
)
def test_source_stream_rejects_duplicate_unknown_or_trailing_records(mutate) -> None:
    mod = _load()
    original = _snapshot_stdout(
        [_company(101)], [_link(201, 301, 101)]
    ).decode().splitlines()
    records = [json.loads(line) for line in original]
    poisoned = ("\n".join(json.dumps(record) for record in mutate(records)) + "\n").encode()

    with pytest.raises(mod.SourceSnapshotError):
        mod.parse_source_snapshot(poisoned)


def test_source_stream_rejects_trailing_non_json_bytes_without_echoing_them() -> None:
    mod = _load()
    poison = b"SYNTHETIC_TRAILING_PRIVATE_BYTES"
    raw = _snapshot_stdout([_company(101)], []) + poison
    with pytest.raises(mod.SourceSnapshotError) as exc_info:
        mod.parse_source_snapshot(raw)
    assert poison.decode() not in str(exc_info.value)


def test_projection_keeps_all_companies_and_only_links_with_local_clients() -> None:
    mod = _load()
    stdout = _snapshot_stdout(
        [_company(101), _company(102)],
        [_link(201, 301, 101), _link(202, 999, 102)],
    )
    snapshot = mod.parse_source_snapshot(stdout)

    plan = mod.build_projection_plan(snapshot, local_client_ids={301})

    assert len(plan.companies) == 2
    assert [row["id"] for row in plan.eligible_links] == [201]
    assert plan.rejected_missing_local_client == 1
    assert not hasattr(plan, "synthesized_clients")


def test_projection_digest_is_lossless_and_excludes_rejected_links() -> None:
    mod = _load()
    eligible = _link(201, 301, 101)
    rejected_a = _link(202, 999, 101)
    rejected_b = dict(rejected_a, notes="SYNTHETIC REJECTED CONTENT MUTANT")
    first = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [eligible, rejected_a])
    )
    second = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [eligible, rejected_b])
    )
    first_plan = mod.build_projection_plan(first, local_client_ids={301})
    second_plan = mod.build_projection_plan(second, local_client_ids={301})
    assert first.content_digest != second.content_digest
    assert first_plan.projection_digest == second_plan.projection_digest

    eligible_mutant = dict(eligible, ownership_percentage="0.12345678901234567890")
    third = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [eligible_mutant, rejected_a])
    )
    third_plan = mod.build_projection_plan(third, local_client_ids={301})
    assert third_plan.projection_digest != first_plan.projection_digest
    assert third_plan.projection_digest == _independent_projection_digest(
        companies=third_plan.companies,
        eligible_links=third_plan.eligible_links,
    )


def test_projection_digest_independent_oracle_covers_every_ordered_column() -> None:
    mod = _load()
    assert mod.PROJECTION_DIGEST_DOMAIN == _PROJECTION_DIGEST_DOMAIN
    assert mod.PROJECTION_DIGEST_VERSION == _PROJECTION_DIGEST_VERSION
    assert mod.COMPANY_COLUMNS == EXPECTED_COMPANY_COLUMNS
    assert mod.LINK_COLUMNS == EXPECTED_LINK_COLUMNS

    company = _company(101)
    company["setup_progress"] = decimal.Decimal(
        "0.123456789012345678901234567890"
    )
    company["custom_fields"] = {"nested": ["SYNTHETIC", decimal.Decimal("1.01")]}
    link = _link(201, 301, 101)
    link["ownership_percentage"] = decimal.Decimal("99.999999999999999999")
    link["share_nominal_value"] = decimal.Decimal("1000000.000000000001")
    companies = (company,)
    links = (link,)
    expected = _independent_projection_digest(
        companies=companies, eligible_links=links
    )
    assert mod.compute_projection_digest(
        companies=companies, eligible_links=links
    ) == expected
    canonical_bytes = _independent_projection_bytes(
        companies=companies, eligible_links=links
    )
    assert b"0.123456789012345678901234567890" in canonical_bytes
    assert b"99.999999999999999999" in canonical_bytes
    assert b"1000000.000000000001" in canonical_bytes

    for index, column in enumerate(EXPECTED_COMPANY_COLUMNS, start=1):
        mutant = copy.deepcopy(company)
        if column == "id":
            mutant[column] = 1000 + index
        elif column == "setup_progress":
            mutant[column] = decimal.Decimal(f"0.{index:030d}")
        elif column == "custom_fields":
            mutant[column] = {"poison": f"SYNTHETIC_COMPANY_COLUMN_{index}"}
        else:
            mutant[column] = f"SYNTHETIC_COMPANY_COLUMN_{index}_{column}"
        oracle = _independent_projection_digest(
            companies=(mutant,), eligible_links=links
        )
        assert oracle != expected, column
        assert mod.compute_projection_digest(
            companies=(mutant,), eligible_links=links
        ) == oracle

    for index, column in enumerate(EXPECTED_LINK_COLUMNS, start=1):
        mutant = copy.deepcopy(link)
        if column in {"id", "client_id", "company_id", "shares_count"}:
            mutant[column] = 2000 + index
        elif column == "is_primary":
            mutant[column] = not link[column]
        elif column in {"ownership_percentage", "share_nominal_value"}:
            mutant[column] = decimal.Decimal(f"{index}.{'7' * 30}")
        else:
            mutant[column] = f"SYNTHETIC_LINK_COLUMN_{index}_{column}"
        oracle = _independent_projection_digest(
            companies=companies, eligible_links=(mutant,)
        )
        assert oracle != expected, column
        assert mod.compute_projection_digest(
            companies=companies, eligible_links=(mutant,)
        ) == oracle

    reordered = _independent_projection_digest(
        companies=companies,
        eligible_links=links,
        company_columns=(EXPECTED_COMPANY_COLUMNS[1], EXPECTED_COMPANY_COLUMNS[0], *EXPECTED_COMPANY_COLUMNS[2:]),
    )
    assert reordered != expected
    float_company = copy.deepcopy(company)
    float_company["setup_progress"] = 0.1
    with pytest.raises(TypeError, match="float"):
        mod.compute_projection_digest(
            companies=(float_company,), eligible_links=links
        )


def test_shape_digest_excludes_company_content() -> None:
    mod = _load()
    first = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101, marker="SYNTHETIC A")], [_link(201, 301, 101)])
    )
    second = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101, marker="SYNTHETIC B")], [_link(201, 301, 101)])
    )
    assert mod.source_shape_digest(first) == mod.source_shape_digest(second)


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://nuzantara@db.internal:5432/nuzantara_dev",
        "postgresql://nuzantara@127.0.0.1:5432/nuzantara_rag",
        "postgresql://nuzantara@127.0.0.1:5432/postgres",
    ],
)
def test_target_dsn_rejects_remote_or_non_dev_database(dsn: str) -> None:
    mod = _load()
    with pytest.raises(mod.ApplyGateError):
        mod.validate_target_dsn(dsn)


def test_apply_requires_flag_environment_gate_and_exact_local_target() -> None:
    mod = _load()
    dsn = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
    digest = "a" * 64
    mod.validate_target_dsn(dsn)

    with pytest.raises(mod.ApplyGateError, match="--apply"):
        mod.validate_apply_request(
            apply=False,
            dsn=dsn,
            environ={},
            expected_content_digest=None,
            actual_content_digest=digest,
        )
    with pytest.raises(mod.ApplyGateError, match=mod.WRITE_ENABLE_ENV):
        mod.validate_apply_request(
            apply=True,
            dsn=dsn,
            environ={},
            expected_content_digest=digest,
            actual_content_digest=digest,
        )
    with pytest.raises(mod.ApplyGateError, match="expected content digest"):
        mod.validate_apply_request(
            apply=True,
            dsn=dsn,
            environ={mod.WRITE_ENABLE_ENV: "true"},
            expected_content_digest=None,
            actual_content_digest=digest,
        )
    with pytest.raises(mod.ApplyGateError, match="content digest mismatch"):
        mod.validate_apply_request(
            apply=True,
            dsn=dsn,
            environ={mod.WRITE_ENABLE_ENV: "true"},
            expected_content_digest="b" * 64,
            actual_content_digest=digest,
        )
    mod.validate_apply_request(
        apply=True,
        dsn=dsn,
        environ={mod.WRITE_ENABLE_ENV: "true"},
        expected_content_digest=digest,
        actual_content_digest=digest,
    )


def test_target_contract_requires_allowlisted_columns_and_both_link_fks() -> None:
    mod = _load()
    columns = {
        "companies": {*EXPECTED_COMPANY_COLUMNS, "future_target_only_column"},
        "client_company_links": {*EXPECTED_LINK_COLUMNS, "future_link_only_column"},
    }
    constraints = {
        "companies": ("PRIMARY KEY (id)",),
        "client_company_links": (
            "PRIMARY KEY (id)",
            "UNIQUE (client_id, company_id)",
            "FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE",
            "FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE",
        ),
    }
    mod.validate_target_contract(columns, constraints)

    missing_fk = dict(constraints)
    missing_fk["client_company_links"] = constraints["client_company_links"][:-1]
    with pytest.raises(mod.TargetContractError, match="company_id foreign key"):
        mod.validate_target_contract(columns, missing_fk)


def test_target_attestation_contract_is_exact_and_rejects_socket_fallback() -> None:
    mod = _load()
    required_aliases = {
        "database",
        "role",
        "server_address",
        "server_port",
        "transaction_read_only",
        "search_path",
        "public_schema_oid",
        "companies_relation",
        "companies_relation_oid",
        "companies_regclass_oid",
        "companies_namespace_oid",
        "companies_namespace",
        "companies_relname",
        "companies_relkind",
        "links_relation",
        "links_relation_oid",
        "links_regclass_oid",
        "links_namespace_oid",
        "links_namespace",
        "links_relname",
        "links_relkind",
    }
    for alias in required_aliases:
        assert re.search(rf"\bAS\s+{alias}\b", mod.TARGET_ATTEST_SQL, re.IGNORECASE)
    assert "current_setting('search_path')" in mod.TARGET_ATTEST_SQL
    assert "to_regnamespace('public')" in mod.TARGET_ATTEST_SQL
    assert "to_regclass('public.companies')" in mod.TARGET_ATTEST_SQL
    assert "to_regclass('public.client_company_links')" in mod.TARGET_ATTEST_SQL
    assert re.search(
        r"company_relation\.oid\s+AS\s+companies_relation_oid",
        mod.TARGET_ATTEST_SQL,
        re.IGNORECASE,
    )
    assert re.search(
        r"to_regclass\('public\.companies'\)::oid\s+AS\s+companies_regclass_oid",
        mod.TARGET_ATTEST_SQL,
        re.IGNORECASE,
    )
    assert re.search(
        r"company_namespace\.oid\s+AS\s+companies_namespace_oid",
        mod.TARGET_ATTEST_SQL,
        re.IGNORECASE,
    )
    assert re.search(
        r"link_relation\.oid\s+AS\s+links_relation_oid",
        mod.TARGET_ATTEST_SQL,
        re.IGNORECASE,
    )
    assert re.search(
        r"to_regclass\('public\.client_company_links'\)::oid\s+AS\s+links_regclass_oid",
        mod.TARGET_ATTEST_SQL,
        re.IGNORECASE,
    )
    assert re.search(
        r"link_namespace\.oid\s+AS\s+links_namespace_oid",
        mod.TARGET_ATTEST_SQL,
        re.IGNORECASE,
    )


class _AttestConnection:
    def __init__(self, mod: Any, values: Mapping[str, Any]) -> None:
        self.mod = mod
        self.values = dict(values)

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any]:
        assert sql == self.mod.TARGET_ATTEST_SQL
        return dict(self.values)


def _valid_target_attestation() -> dict[str, Any]:
    return {
        "database": "nuzantara_dev",
        "role": "nuzantara",
        "server_address": "127.0.0.1",
        "server_port": 5432,
        "transaction_read_only": "off",
        "search_path": "public",
        "public_schema_oid": 2200,
        # PostgreSQL renders visible regclass values without schema qualification
        # when search_path is exactly public.  Identity comes from the catalog OIDs,
        # namespace, relation name, and relkind below, not this display string.
        "companies_relation": "companies",
        "companies_relation_oid": 41001,
        "companies_regclass_oid": 41001,
        "companies_namespace_oid": 2200,
        "companies_namespace": "public",
        "companies_relname": "companies",
        "companies_relkind": "r",
        "links_relation": "client_company_links",
        "links_relation_oid": 41002,
        "links_regclass_oid": 41002,
        "links_namespace_oid": 2200,
        "links_namespace": "public",
        "links_relname": "client_company_links",
        "links_relkind": "r",
    }


async def test_target_attestation_accepts_pg_visible_unqualified_regclass_text() -> None:
    """A real search_path=public regclass rendering must not fail attestation."""
    mod = _load()

    await mod.attest_target(
        _AttestConnection(mod, _valid_target_attestation()),
        expect_read_only=False,
    )


@pytest.mark.parametrize(
    ("field", "mutant"),
    [
        ("database", "postgres"),
        ("role", "write_role"),
        ("server_address", None),
        ("server_address", "10.0.0.9"),
        ("server_port", 15432),
        ("transaction_read_only", "on"),
        ("search_path", '"$user", public'),
        ("public_schema_oid", None),
        ("companies_relation", "shadow.companies"),
        ("links_relation", "shadow.client_company_links"),
    ],
)
async def test_target_attestation_rejects_every_value_mutant(
    field: str, mutant: Any
) -> None:
    mod = _load()
    values = _valid_target_attestation()
    values[field] = mutant
    with pytest.raises(mod.TargetContractError):
        await mod.attest_target(
            _AttestConnection(mod, values), expect_read_only=False
        )


@pytest.mark.parametrize(
    ("field", "mutant"),
    [
        ("companies_relation_oid", 41999),
        ("companies_regclass_oid", 41999),
        ("companies_namespace_oid", 2299),
        ("links_relation_oid", 42999),
        ("links_regclass_oid", 42999),
        ("links_namespace_oid", 2299),
    ],
)
async def test_target_attestation_rejects_catalog_oid_identity_mismatch(
    field: str, mutant: int
) -> None:
    """Catalog identity remains causal even if legacy display text looks valid."""
    mod = _load()
    values = _valid_target_attestation()
    values.update(
        {
            "companies_relation": "public.companies",
            "links_relation": "public.client_company_links",
            field: mutant,
        }
    )

    with pytest.raises(mod.TargetContractError):
        await mod.attest_target(
            _AttestConnection(mod, values), expect_read_only=False
        )


def test_target_contract_queries_fk_validation_and_exact_sequence_ownership() -> None:
    mod = _load()
    constraint_sql = mod.TARGET_CONSTRAINTS_SQL.lower()
    assert "convalidated" in constraint_sql
    assert "public" in constraint_sql
    sequence_sql = mod.SEQUENCE_ATTEST_SQL.lower()
    for exact_name in (
        "public.companies_id_seq",
        "public.client_company_links_id_seq",
        "public.companies",
        "public.client_company_links",
    ):
        assert exact_name in sequence_sql
    assert "pg_depend" in sequence_sql
    assert "attnum" in sequence_sql or "pg_attribute" in sequence_sql


def test_protected_table_set_and_digest_sql_cover_actual_rows_and_columns() -> None:
    mod = _load()
    assert mod.PROTECTED_TABLES == (
        "clients",
        "intake_queue",
        "document_instances",
        "document_routing_proposal",
        "intake_commit_audit",
    )
    assert len(mod.PROTECTED_INVARIANT_SQL) == len(mod.PROTECTED_TABLES)
    for table, sql in zip(
        mod.PROTECTED_TABLES, mod.PROTECTED_INVARIANT_SQL, strict=True
    ):
        assert f"public.{table}" in sql
        assert "information_schema.columns" in sql
        assert "ordinal_position" in sql
        assert "to_jsonb" in sql
        assert "ORDER BY row_hash" in sql
        assert "schema_digest" in sql and "row_digest" in sql


class _SharedProjectionState:
    def __init__(self) -> None:
        self.companies: dict[int, dict[str, Any]] = {}
        self.links: dict[int, dict[str, Any]] = {}
        self.sequences: dict[str, tuple[int, bool]] = {
            "public.companies_id_seq": (1000, True),
            "public.client_company_links_id_seq": (2000, True),
        }
        self.advisory_lock = asyncio.Lock()
        self.second_lock_waiting = asyncio.Event()
        self.first_writer_entered = asyncio.Event()
        self.release_first_writer = asyncio.Event()
        self.active_writers = 0
        self.max_active_writers = 0


class _FakeTransaction:
    def __init__(self, conn: _StatefulConnection, options: dict[str, Any]) -> None:
        self.conn = conn
        self.options = options
        self.saved_companies: dict[int, dict[str, Any]] = {}
        self.saved_links: dict[int, dict[str, Any]] = {}
        self.saved_sequences: dict[str, tuple[int, bool]] = {}

    async def __aenter__(self) -> _FakeTransaction:
        assert not self.conn.in_transaction
        self.conn.in_transaction = True
        self.conn.transaction_options.append(self.options)
        self.saved_companies = copy.deepcopy(self.conn.state.companies)
        self.saved_links = copy.deepcopy(self.conn.state.links)
        self.saved_sequences = copy.deepcopy(self.conn.state.sequences)
        self.conn.events.append("begin")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> bool:
        if exc_type is not None:
            self.conn.state.companies = self.saved_companies
            self.conn.state.links = self.saved_links
            self.conn.state.sequences = self.saved_sequences
            self.conn.events.append("rollback")
        else:
            self.conn.events.append("commit")
        if self.conn.holds_advisory_lock:
            self.conn.state.active_writers -= 1
            self.conn.state.advisory_lock.release()
            self.conn.holds_advisory_lock = False
        self.conn.in_transaction = False
        return False


class _StatefulConnection:
    def __init__(
        self,
        mod: Any,
        *,
        state: _SharedProjectionState | None = None,
        fail_links: bool = False,
        drift_invariants: bool = False,
        hold_first_writer: bool = False,
        fail_after_alter: int | None = None,
        sequence_attest_mutant: Mapping[str, Any] | None = None,
        constraint_mutant: Mapping[str, Any] | None = None,
        drift_schema: bool = False,
    ) -> None:
        self.mod = mod
        self.state = state or _SharedProjectionState()
        self.fail_links = fail_links
        self.drift_invariants = drift_invariants
        self.hold_first_writer = hold_first_writer
        self.fail_after_alter = fail_after_alter
        self.sequence_attest_mutant = dict(sequence_attest_mutant or {})
        self.constraint_mutant = dict(constraint_mutant or {})
        self.drift_schema = drift_schema
        self.events: list[str] = []
        self.transaction_options: list[dict[str, Any]] = []
        self.in_transaction = False
        self.holds_advisory_lock = False
        self.invariant_reads = 0
        self.company_payloads: list[tuple[str]] = []
        self.link_payloads: list[tuple[str]] = []
        self.alter_count = 0

    def transaction(self, **kwargs: Any) -> _FakeTransaction:
        return _FakeTransaction(self, kwargs)

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        assert self.in_transaction
        if sql == self.mod.TARGET_COLUMNS_SQL:
            self.events.append("schema_columns")
            return [
                {"table_name": "companies", "column_name": column}
                for column in EXPECTED_COMPANY_COLUMNS
            ] + [
                {"table_name": "client_company_links", "column_name": column}
                for column in EXPECTED_LINK_COLUMNS
            ]
        if sql == self.mod.TARGET_CONSTRAINTS_SQL:
            self.events.append("schema_constraints")
            rows = [
                {"table_name": "companies", "definition": "PRIMARY KEY (id)"},
                {
                    "table_name": "client_company_links",
                    "definition": "PRIMARY KEY (id)",
                    "convalidated": True,
                },
                {
                    "table_name": "client_company_links",
                    "definition": "UNIQUE (client_id, company_id)",
                    "convalidated": True,
                },
                {
                    "table_name": "client_company_links",
                    "definition": (
                        "FOREIGN KEY (client_id) REFERENCES clients(id) "
                        "ON DELETE CASCADE"
                    ),
                    "convalidated": True,
                },
                {
                    "table_name": "client_company_links",
                    "definition": (
                        "FOREIGN KEY (company_id) REFERENCES companies(id) "
                        "ON DELETE CASCADE"
                    ),
                    "convalidated": True,
                },
            ]
            if self.constraint_mutant:
                fragment = self.constraint_mutant["definition_contains"]
                row = next(item for item in rows if fragment in item["definition"])
                row.update(self.constraint_mutant["values"])
            return rows
        if sql == self.mod.TARGET_COMPANIES_SQL:
            self.events.append("target_companies")
            return [
                self.state.companies[key] for key in sorted(self.state.companies)
            ]
        if sql == self.mod.TARGET_LINKS_SQL:
            self.events.append("target_links")
            return [self.state.links[key] for key in sorted(self.state.links)]
        assert sql == self.mod.LOCAL_CLIENT_IDS_SQL
        self.events.append("local_clients")
        return [{"id": 301}]

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any]:
        assert self.in_transaction
        if sql == self.mod.TARGET_ATTEST_SQL:
            self.events.append("attest")
            return _valid_target_attestation()
        if sql == self.mod.SEQUENCE_ATTEST_SQL:
            self.events.append("sequence_preflight")
            company_sequence = self.state.sequences["public.companies_id_seq"]
            link_sequence = self.state.sequences[
                "public.client_company_links_id_seq"
            ]
            row = {
                "companies_sequence": "public.companies_id_seq",
                "companies_owned_by": "public.companies.id",
                "companies_last_value": company_sequence[0],
                "companies_is_called": company_sequence[1],
                "companies_increment_by": 1,
                "companies_cycle": False,
                "links_sequence": "public.client_company_links_id_seq",
                "links_owned_by": "public.client_company_links.id",
                "links_last_value": link_sequence[0],
                "links_is_called": link_sequence[1],
                "links_increment_by": 1,
                "links_cycle": False,
            }
            row.update(self.sequence_attest_mutant)
            return row
        if sql == self.mod.TARGET_COUNTS_SQL:
            self.events.append("counts")
            return {
                "companies": len(self.state.companies),
                "client_company_links": len(self.state.links),
            }
        assert "information_schema.columns" in sql
        assert "to_jsonb" in sql and "ORDER BY row_hash" in sql
        self.invariant_reads += 1
        phase = "after" if self.invariant_reads % 10 > 5 or self.invariant_reads % 10 == 0 else "before"
        self.events.append(f"invariant:{phase}")
        digest = "changed" if self.drift_invariants and phase == "after" else "stable"
        schema_digest = (
            "schema-changed"
            if self.drift_schema and phase == "after"
            else "schema-stable"
        )
        return {
            "row_count": 7,
            "schema_digest": schema_digest,
            "row_digest": digest,
        }

    async def execute(self, sql: str, *args: Any) -> str:
        assert self.in_transaction
        fixed_events = {
            self.mod.SET_LOCAL_SEARCH_PATH_SQL: "set_search_path",
            self.mod.SET_LOCAL_LOCK_TIMEOUT_SQL: "set_lock_timeout",
            self.mod.SET_LOCAL_STATEMENT_TIMEOUT_SQL: "set_statement_timeout",
            _CLIENTS_SHARE_LOCK_SQL: "clients_share_lock",
            self.mod.TARGET_TABLE_LOCK_SQL: "target_table_lock",
        }
        if sql in fixed_events:
            self.events.append(fixed_events[sql])
            return "OK"
        if sql == self.mod.ADVISORY_XACT_LOCK_SQL:
            self.events.append("advisory_lock_attempt")
            if self.state.advisory_lock.locked():
                self.state.second_lock_waiting.set()
            await self.state.advisory_lock.acquire()
            self.holds_advisory_lock = True
            self.state.active_writers += 1
            self.state.max_active_writers = max(
                self.state.max_active_writers, self.state.active_writers
            )
            self.events.append("advisory_lock_acquired")
            return "SELECT 1"
        match = re.fullmatch(
            r"ALTER SEQUENCE (public\.(?:companies_id_seq|client_company_links_id_seq)) "
            r"RESTART WITH ([1-9][0-9]*)",
            sql,
        )
        assert match is not None, f"unapproved SQL: {sql}"
        sequence_name, raw_value = match.groups()
        self.state.sequences[sequence_name] = (int(raw_value), False)
        self.alter_count += 1
        self.events.append(f"alter:{sequence_name}")
        if self.fail_after_alter == self.alter_count:
            raise RuntimeError(f"synthetic failure after alter {self.alter_count}")
        return "ALTER SEQUENCE"

    async def executemany(self, sql: str, args: list[tuple[str]]) -> None:
        assert self.in_transaction and self.holds_advisory_lock
        if sql == self.mod.COMPANY_INSERT_SQL:
            self.events.append("companies")
            self.company_payloads = args
            for payload, in args:
                row = json.loads(payload, parse_float=decimal.Decimal)
                if row["id"] in self.state.companies:
                    raise RuntimeError("synthetic duplicate company id")
                self.state.companies[row["id"]] = row
            if self.hold_first_writer:
                self.state.first_writer_entered.set()
                await self.state.release_first_writer.wait()
            return
        assert sql == self.mod.LINK_INSERT_SQL
        self.events.append("links")
        if self.fail_links:
            raise RuntimeError("synthetic link failure")
        self.link_payloads = args
        for payload, in args:
            row = json.loads(payload, parse_float=decimal.Decimal)
            if row["id"] in self.state.links:
                raise RuntimeError("synthetic duplicate link id")
            if row["client_id"] != 301 or row["company_id"] not in self.state.companies:
                raise RuntimeError("synthetic foreign key failure")
            self.state.links[row["id"]] = row


async def test_apply_attests_and_reads_clients_inside_one_locked_transaction() -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    conn = _StatefulConnection(mod)

    result = await mod.apply_projection(
        conn,
        snapshot,
        expected_content_digest=snapshot.content_digest,
    )

    assert conn.transaction_options == [
        {"isolation": "serializable", "readonly": False}
    ]
    assert conn.events[0:9] == [
        "begin",
        "set_search_path",
        "set_lock_timeout",
        "set_statement_timeout",
        "clients_share_lock",
        "target_table_lock",
        "advisory_lock_attempt",
        "advisory_lock_acquired",
        "attest",
    ]
    assert conn.events.index("local_clients") < conn.events.index("companies")
    assert conn.events.index("sequence_preflight") < conn.events.index("companies")
    assert conn.events.index("companies") < conn.events.index("links")
    assert conn.events.index("links") < conn.events.index("alter:public.companies_id_seq")
    assert conn.events.index("alter:public.companies_id_seq") < conn.events.index(
        "alter:public.client_company_links_id_seq"
    )
    assert conn.events.index("alter:public.client_company_links_id_seq") < max(
        index
        for index, event in enumerate(conn.events)
        if event == "target_companies"
    )
    assert conn.events.count("target_companies") == 2
    assert conn.events.count("target_links") == 2
    assert [event for event in conn.events if event.startswith("alter:")] == [
        "alter:public.companies_id_seq",
        "alter:public.client_company_links_id_seq",
    ]
    assert conn.events[-1] == "commit"
    assert result.companies_inserted == 1
    assert result.links_inserted == 1
    assert result.no_op is False
    assert set(json.loads(conn.company_payloads[0][0])) == set(EXPECTED_COMPANY_COLUMNS)
    assert set(json.loads(conn.link_payloads[0][0])) == set(EXPECTED_LINK_COLUMNS)


async def test_apply_twice_is_idempotent_in_stateful_transaction_harness() -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    state = _SharedProjectionState()
    conn = _StatefulConnection(mod, state=state)

    first = await mod.apply_projection(
        conn, snapshot, expected_content_digest=snapshot.content_digest
    )
    first_state = (copy.deepcopy(state.companies), copy.deepcopy(state.links))
    first_sequences = copy.deepcopy(state.sequences)
    second_event_start = len(conn.events)
    second = await mod.apply_projection(
        conn, snapshot, expected_content_digest=snapshot.content_digest
    )

    assert (state.companies, state.links) == first_state
    assert state.sequences == first_sequences
    assert len(state.companies) == 1 and len(state.links) == 1
    assert first.companies_inserted == first.links_inserted == 1
    assert first.no_op is False
    assert second.companies_inserted == second.links_inserted == 0
    assert second.no_op is True
    second_events = conn.events[second_event_start:]
    assert "companies" not in second_events and "links" not in second_events
    assert not any(event.startswith("alter:") for event in second_events)
    assert second_events[-1] == "commit"


@pytest.mark.parametrize("target_kind", ["partial", "mismatch"])
async def test_apply_refuses_nonempty_nonmatching_target_without_writes(
    target_kind: str,
) -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    state = _SharedProjectionState()
    state.companies[101] = copy.deepcopy(_company(101))
    if target_kind == "mismatch":
        state.companies[101]["company_name"] = "SYNTHETIC DIFFERENT COMPANY"
        state.links[201] = copy.deepcopy(_link(201, 301, 101))
    before = copy.deepcopy((state.companies, state.links, state.sequences))
    conn = _StatefulConnection(mod, state=state)

    with pytest.raises(mod.TargetContractError):
        await mod.apply_projection(
            conn, snapshot, expected_content_digest=snapshot.content_digest
        )

    assert (state.companies, state.links, state.sequences) == before
    assert "companies" not in conn.events and "links" not in conn.events
    assert not any(event.startswith("alter:") for event in conn.events)
    assert conn.events[-1] == "rollback"


async def test_apply_rolls_back_on_link_foreign_key_failure() -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    conn = _StatefulConnection(mod, fail_links=True)

    with pytest.raises(RuntimeError, match="synthetic link failure"):
        await mod.apply_projection(
            conn, snapshot, expected_content_digest=snapshot.content_digest
        )

    assert conn.events[-1] == "rollback"
    assert conn.state.companies == {} and conn.state.links == {}


async def test_apply_rolls_back_if_protected_rows_or_columns_digest_changes() -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    conn = _StatefulConnection(mod, drift_invariants=True)

    with pytest.raises(mod.ProjectionInvariantError, match="protected table"):
        await mod.apply_projection(
            conn, snapshot, expected_content_digest=snapshot.content_digest
        )

    assert conn.events[-1] == "rollback"
    assert conn.state.companies == {} and conn.state.links == {}


async def test_apply_rolls_back_on_protected_schema_digest_only_drift() -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    conn = _StatefulConnection(mod, drift_schema=True)

    with pytest.raises(mod.ProjectionInvariantError, match="protected table"):
        await mod.apply_projection(
            conn, snapshot, expected_content_digest=snapshot.content_digest
        )

    assert conn.events[-1] == "rollback"
    assert conn.state.companies == {} and conn.state.links == {}


@pytest.mark.parametrize(
    "sequence_attest_mutant",
    [
        {"companies_owned_by": "public.other_table.id"},
        {"links_owned_by": "public.other_table.id"},
        {"companies_sequence": "shadow.companies_id_seq"},
        {"links_sequence": "public.wrong_links_id_seq"},
    ],
    ids=(
        "company-sequence-owner",
        "link-sequence-owner",
        "company-sequence-name",
        "link-sequence-name",
    ),
)
async def test_returned_sequence_identity_mutants_refuse_without_writes(
    sequence_attest_mutant: Mapping[str, Any],
) -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    conn = _StatefulConnection(
        mod, sequence_attest_mutant=sequence_attest_mutant
    )

    with pytest.raises(mod.TargetContractError):
        await mod.apply_projection(
            conn, snapshot, expected_content_digest=snapshot.content_digest
        )

    assert "companies" not in conn.events and "links" not in conn.events
    assert not any(event.startswith("alter:") for event in conn.events)
    assert conn.events[-1] == "rollback"


@pytest.mark.parametrize(
    "definition_contains",
    ["FOREIGN KEY (client_id)", "FOREIGN KEY (company_id)"],
    ids=("client-fk", "company-fk"),
)
async def test_returned_unvalidated_fk_mutants_refuse_without_writes(
    definition_contains: str,
) -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    conn = _StatefulConnection(
        mod,
        constraint_mutant={
            "definition_contains": definition_contains,
            "values": {"convalidated": False},
        },
    )

    with pytest.raises(mod.TargetContractError):
        await mod.apply_projection(
            conn, snapshot, expected_content_digest=snapshot.content_digest
        )

    assert "companies" not in conn.events and "links" not in conn.events
    assert not any(event.startswith("alter:") for event in conn.events)
    assert conn.events[-1] == "rollback"


@pytest.mark.parametrize("fail_after_alter", [1, 2])
async def test_apply_rolls_back_rows_and_sequence_state_after_each_alter_failure(
    fail_after_alter: int,
) -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    conn = _StatefulConnection(mod, fail_after_alter=fail_after_alter)
    before = copy.deepcopy(
        (conn.state.companies, conn.state.links, conn.state.sequences)
    )

    with pytest.raises(RuntimeError, match="synthetic failure after alter"):
        await mod.apply_projection(
            conn, snapshot, expected_content_digest=snapshot.content_digest
        )

    assert (conn.state.companies, conn.state.links, conn.state.sequences) == before
    assert conn.alter_count == fail_after_alter
    assert conn.events[-1] == "rollback"


@pytest.mark.parametrize(
    "sequence_name",
    ["public.companies_id_seq", "public.client_company_links_id_seq"],
)
@pytest.mark.parametrize(
    ("last_value", "is_called", "source_max_id", "expected_restart"),
    [
        (500, False, 100, 500),  # uncalled: last_value is already the effective next
        (500, True, 100, 501),  # called: effective next is last_value + 1
        (101, False, 100, 101),  # equality boundary, uncalled
        (100, True, 100, 101),  # equality boundary, called
        (50, False, 100, 101),  # source max + 1 is higher, uncalled
        (50, True, 100, 101),  # source max + 1 is higher, called
    ],
)
def test_sequence_restart_boundaries_are_lossless_and_hardcoded(
    sequence_name: str,
    last_value: int,
    is_called: bool,
    source_max_id: int,
    expected_restart: int,
) -> None:
    mod = _load()
    restart = mod.sequence_restart_value(
        last_value=last_value,
        is_called=is_called,
        source_max_id=source_max_id,
    )
    assert restart == expected_restart
    assert mod.sequence_restart_sql(sequence_name, restart) == (
        f"ALTER SEQUENCE {sequence_name} RESTART WITH {expected_restart}"
    )


@pytest.mark.parametrize(
    "sequence_name",
    [
        "public.unapproved_id_seq",
        "shadow.companies_id_seq",
        "public.companies_id_seq; DROP TABLE public.clients",
        'public."companies_id_seq"',
    ],
)
def test_sequence_restart_rejects_every_nonexact_or_injected_name(
    sequence_name: str,
) -> None:
    mod = _load()
    with pytest.raises((mod.TargetContractError, ValueError)):
        mod.sequence_restart_sql(sequence_name, 101)


@pytest.mark.parametrize("restart", [0, -1, True, 1.5, "101", 9223372036854775808])
def test_sequence_restart_rejects_non_positive_non_integer_or_out_of_range_value(
    restart: Any,
) -> None:
    mod = _load()
    with pytest.raises((mod.TargetContractError, ValueError, TypeError)):
        mod.sequence_restart_sql("public.companies_id_seq", restart)


def test_target_initial_state_is_empty_or_exact_digest_noop_only() -> None:
    mod = _load()
    desired = "a" * 64
    assert mod.classify_target_state(
        companies_count=0,
        links_count=0,
        actual_digest=mod.EMPTY_TARGET_DIGEST,
        desired_digest=desired,
    ) == "empty"
    assert mod.classify_target_state(
        companies_count=2,
        links_count=1,
        actual_digest=desired,
        desired_digest=desired,
    ) == "exact-noop"
    for counts, digest in [((2, 1), "b" * 64)]:
        with pytest.raises(mod.TargetContractError):
            mod.classify_target_state(
                companies_count=counts[0],
                links_count=counts[1],
                actual_digest=digest,
                desired_digest=desired,
            )


async def test_advisory_transaction_lock_serializes_concurrent_applies() -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    state = _SharedProjectionState()
    first_conn = _StatefulConnection(mod, state=state, hold_first_writer=True)
    second_conn = _StatefulConnection(mod, state=state)

    first_task = asyncio.create_task(
        mod.apply_projection(
            first_conn, snapshot, expected_content_digest=snapshot.content_digest
        )
    )
    await asyncio.wait_for(state.first_writer_entered.wait(), timeout=1.0)
    second_task = asyncio.create_task(
        mod.apply_projection(
            second_conn, snapshot, expected_content_digest=snapshot.content_digest
        )
    )
    await asyncio.wait_for(state.second_lock_waiting.wait(), timeout=1.0)
    assert state.max_active_writers == 1
    state.release_first_writer.set()
    await asyncio.wait_for(asyncio.gather(first_task, second_task), timeout=1.0)

    assert state.max_active_writers == 1


def test_sql_surface_is_insert_only_except_two_exact_sequence_restarts() -> None:
    mod = _load()
    sql_surface = "\n".join(mod.ALL_LOCAL_SQL).upper()
    for verb in ("DELETE", "TRUNCATE", "DROP", "UPDATE"):
        assert not re.search(rf"\b{verb}\b", sql_surface)
    assert "SETVAL" not in sql_surface
    assert "NEXTVAL" not in sql_surface
    assert "PG_ADVISORY_XACT_LOCK" in mod.ADVISORY_XACT_LOCK_SQL.upper()
    assert "LAST_VALUE" in mod.SEQUENCE_ATTEST_SQL.upper()
    assert "IS_CALLED" in mod.SEQUENCE_ATTEST_SQL.upper()
    assert "ON CONFLICT" not in sql_surface
    assert re.search(r"\bINSERT\s+INTO\s+PUBLIC\.COMPANIES\s*\(", mod.COMPANY_INSERT_SQL.upper())
    assert re.search(
        r"\bINSERT\s+INTO\s+PUBLIC\.CLIENT_COMPANY_LINKS\s*\(",
        mod.LINK_INSERT_SQL.upper(),
    )
    assert "ON CONFLICT" not in mod.COMPANY_INSERT_SQL.upper()
    assert "ON CONFLICT" not in mod.LINK_INSERT_SQL.upper()
    assert not re.search(r"\bINSERT\s+INTO\s+CLIENTS\b", sql_surface)
    assert not re.search(r"\bUPDATE\s+CLIENTS\b", sql_surface)
    for table in mod.PROTECTED_TABLES:
        assert not re.search(
            rf"\b(?:INSERT\s+INTO|UPDATE)\s+{re.escape(table.upper())}\b",
            sql_surface,
        )


def test_apply_transaction_setup_and_target_acquisition_are_fixed() -> None:
    mod = _load()
    assert mod.SET_LOCAL_SEARCH_PATH_SQL == "SET LOCAL search_path = public"
    assert re.fullmatch(
        r"SET LOCAL lock_timeout = '[1-9][0-9]*ms'",
        mod.SET_LOCAL_LOCK_TIMEOUT_SQL,
    )
    assert re.fullmatch(
        r"SET LOCAL statement_timeout = '[1-9][0-9]*ms'",
        mod.SET_LOCAL_STATEMENT_TIMEOUT_SQL,
    )
    assert mod.TARGET_TABLE_LOCK_SQL == (
        "LOCK TABLE public.companies, public.client_company_links "
        "IN SHARE ROW EXCLUSIVE MODE"
    )
    assert _CLIENTS_SHARE_LOCK_SQL in mod.ALL_LOCAL_SQL
    assert "pg_advisory_xact_lock" in mod.ADVISORY_XACT_LOCK_SQL
    assert "from public.companies" in mod.TARGET_COMPANIES_SQL.lower()
    assert "from public.client_company_links" in mod.TARGET_LINKS_SQL.lower()


def test_report_is_aggregate_only_and_never_contains_row_payloads() -> None:
    mod = _load()
    private_markers = {
        column: f"SYNTHETIC_PRIVATE_{column.upper()}"
        for column in (
            "company_name",
            "brand_name",
            "nib",
            "npwp_company",
            "registered_address",
            "office_address",
            "company_phone",
            "company_email",
            "google_drive_folder_id",
            "created_by",
            "updated_by",
        )
    }
    company = _company(101, marker=private_markers["company_name"])
    company.update(private_markers)
    link = _link(201, 301, 101)
    link["notes"] = "SYNTHETIC_PRIVATE_LINK_NOTES"
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([company], [link])
    )
    plan = mod.build_projection_plan(snapshot, local_client_ids={301})

    report = mod.build_report(
        snapshot=snapshot,
        plan=plan,
        mode="dry-run",
        target_before={"companies": 0, "client_company_links": 0},
        target_after=None,
        invariant_digest="shape-only-digest",
        sequence_status={
            "companies": {
                "last_value": 1000,
                "is_called": True,
                "next_value": 1001,
                "source_max_id": 101,
                "safe": True,
            },
            "client_company_links": {
                "last_value": 2000,
                "is_called": True,
                "next_value": 2001,
                "source_max_id": 201,
                "safe": True,
            },
        },
    )

    serialized = json.dumps(report, sort_keys=True)
    for private_marker in (*private_markers.values(), link["notes"]):
        assert private_marker not in serialized
    assert "company_name" not in serialized
    assert "row" not in report
    assert set(report) == {
        "status",
        "mode",
        "write_attempted",
        "source",
        "projection",
        "target_before",
        "target_after",
        "sequence_preflight",
        "protected_type_digest",
    }
    assert set(report["source"]) == {
        "authority",
        "snapshot_at",
        "companies_max_updated_at",
        "links_max_updated_at",
        "companies",
        "links",
        "content_digest",
        "type_identity_digest",
    }
    assert set(report["target_before"]) == {
        "companies",
        "client_company_links",
    }
    assert report["write_attempted"] is False
    assert report["projection"]["companies"] == 1
    assert report["projection"]["eligible_links"] == 1


def test_report_rejects_unallowlisted_recursive_keys() -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(_snapshot_stdout([_company(101)], []))
    plan = mod.build_projection_plan(snapshot, local_client_ids=set())
    with pytest.raises(mod.TargetContractError, match="report target counts"):
        mod.build_report(
            snapshot=snapshot,
            plan=plan,
            mode="dry-run",
            target_before={
                "companies": 0,
                "client_company_links": 0,
                "private_unallowlisted_key": 1,
            },
            target_after=None,
            invariant_digest="shape-only-digest",
            sequence_status={},
        )


@pytest.mark.parametrize(
    "sequence_status",
    [
        {"private_unallowlisted_key": "SYNTHETIC_PRIVATE_REPORT_POISON"},
        {
            "companies": {
                "last_value": 1000,
                "is_called": True,
                "next_value": 1001,
                "source_max_id": 101,
                "safe": True,
                "private_nested_key": "SYNTHETIC_PRIVATE_REPORT_POISON",
            }
        },
        {
            "companies": {
                "last_value": 1000,
                "is_called": True,
                "next_value": 1001,
                "source_max_id": 101,
                "safe": True,
                "failures": ["SYNTHETIC_PRIVATE_REPORT_POISON"],
            }
        },
    ],
    ids=("sequence-top-level", "sequence-nested", "sequence-failures"),
)
def test_report_rejects_recursive_sequence_status_pii(
    sequence_status: Mapping[str, Any],
) -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(_snapshot_stdout([_company(101)], []))
    plan = mod.build_projection_plan(snapshot, local_client_ids=set())
    poison = "SYNTHETIC_PRIVATE_REPORT_POISON"

    with pytest.raises(mod.TargetContractError) as exc_info:
        mod.build_report(
            snapshot=snapshot,
            plan=plan,
            mode="dry-run",
            target_before={"companies": 0, "client_company_links": 0},
            target_after=None,
            invariant_digest="shape-only-digest",
            sequence_status=sequence_status,
        )

    assert poison not in str(exc_info.value)


def test_every_cli_failure_path_suppresses_poisoned_exception_content() -> None:
    mod = _load()
    poison = "SYNTHETIC_PRIVATE_FAILURE_PAYLOAD"
    error_types = (
        RuntimeError,
        mod.ProjectionError,
        mod.SourceSnapshotError,
        mod.ApplyGateError,
        mod.TargetContractError,
        mod.ProjectionInvariantError,
    )
    for error_type in error_types:
        exc = error_type(poison)
        serialized = json.dumps(mod._safe_error(exc), sort_keys=True)
        assert poison not in serialized

    runner = _Runner(poison.encode(), returncode=9)
    runner.stderr = poison.encode()
    with pytest.raises(mod.SourceSnapshotError) as exc_info:
        mod.fetch_source_snapshot(run=runner)
    assert poison not in str(exc_info.value)


def test_main_suppresses_every_projection_failure_from_stdout_and_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod = _load()
    poison = "SYNTHETIC_PRIVATE_CLI_FAILURE"
    error_types = (
        mod.ProjectionError,
        mod.SourceSnapshotError,
        mod.ApplyGateError,
        mod.TargetContractError,
        mod.ProjectionInvariantError,
    )

    for error_type in error_types:
        async def fail_projection(
            *, _error_type: type[BaseException] = error_type, **kwargs: Any
        ) -> dict[str, Any]:
            raise _error_type(poison)

        monkeypatch.setattr(mod, "run_projection", fail_projection)
        assert mod.main([]) == 2
        captured = capsys.readouterr()
        assert poison not in captured.out
        assert poison not in captured.err
        failure = json.loads(captured.err)
        assert set(failure) == {"status", "error_type", "reason"}


class _AcquiredTargetConnection:
    """Target double which returns rows only through production acquisition SQL."""

    def __init__(
        self,
        mod: Any,
        *,
        companies: tuple[Mapping[str, Any], ...],
        links: tuple[Mapping[str, Any], ...],
    ) -> None:
        self.mod = mod
        self.companies = tuple(copy.deepcopy(row) for row in companies)
        self.links = tuple(copy.deepcopy(row) for row in links)
        self.fetch_calls: list[str] = []

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_calls.append(sql)
        if sql == self.mod.TARGET_COMPANIES_SQL:
            return [copy.deepcopy(row) for row in self.companies]
        if sql == self.mod.TARGET_LINKS_SQL:
            return [copy.deepcopy(row) for row in self.links]
        raise AssertionError(f"unexpected target acquisition SQL: {sql}")


def _require_target_acquisition_contract(mod: Any) -> None:
    assert hasattr(mod, "TARGET_COMPANIES_SQL")
    assert hasattr(mod, "TARGET_LINKS_SQL")
    assert hasattr(mod, "read_target_projection")


def _assert_exact_target_acquisition_sql(sql: str, columns: tuple[str, ...], table: str) -> None:
    normalized = " ".join(sql.lower().split())
    assert re.search(rf"\bfrom\s+public\.{table}\b", normalized)
    assert re.search(r"\border\s+by\s+id\b", normalized)
    selected = re.search(r"\bselect\s+(.+?)\s+\bfrom\b", normalized)
    assert selected is not None
    assert tuple(part.strip() for part in selected.group(1).split(",")) == columns


@pytest.mark.parametrize(
    ("companies", "links", "desired_digest", "expected_state"),
    [
        ((), (), None, "empty"),
        (( _company(101),), (_link(201, 301, 101),), "oracle", "exact-noop"),
        (
            (_company(101, marker="SYNTHETIC CONTENT MUTANT"),),
            (_link(201, 301, 101),),
            "different",
            "refuse",
        ),
        (( _company(101), _company(102)), (_link(201, 301, 101),), "oracle", "post-insert"),
    ],
    ids=("empty", "exact-noop", "same-count-content-mutant", "post-insert"),
)
async def test_target_projection_is_acquired_from_exact_rows_and_python_digest(
    companies: tuple[Mapping[str, Any], ...],
    links: tuple[Mapping[str, Any], ...],
    desired_digest: str | None,
    expected_state: str,
) -> None:
    mod = _load()
    _require_target_acquisition_contract(mod)
    _assert_exact_target_acquisition_sql(
        mod.TARGET_COMPANIES_SQL, EXPECTED_COMPANY_COLUMNS, "companies"
    )
    _assert_exact_target_acquisition_sql(
        mod.TARGET_LINKS_SQL, EXPECTED_LINK_COLUMNS, "client_company_links"
    )
    conn = _AcquiredTargetConnection(mod, companies=companies, links=links)
    target = await mod.read_target_projection(conn)
    oracle = _independent_projection_digest(
        companies=companies, eligible_links=links
    )

    assert conn.fetch_calls == [mod.TARGET_COMPANIES_SQL, mod.TARGET_LINKS_SQL]
    assert target.companies == companies
    assert target.links == links
    assert target.digest == oracle
    if expected_state == "empty":
        assert mod.classify_target_state(
            companies_count=len(companies),
            links_count=len(links),
            actual_digest=target.digest,
            desired_digest="a" * 64,
        ) == "empty"
    elif expected_state == "exact-noop":
        assert mod.classify_target_state(
            companies_count=len(companies),
            links_count=len(links),
            actual_digest=target.digest,
            desired_digest=oracle,
        ) == "exact-noop"
    elif expected_state == "post-insert":
        assert target.digest == _independent_projection_digest(
            companies=companies, eligible_links=links
        )
    else:
        with pytest.raises(mod.TargetContractError):
            mod.classify_target_state(
                companies_count=len(companies),
                links_count=len(links),
                actual_digest=target.digest,
                desired_digest=("b" * 64 if desired_digest == "different" else oracle),
            )


def test_legacy_target_digest_queries_are_absent() -> None:
    mod = _load()
    assert not hasattr(mod, "TARGET_STATE_SQL")
    assert not hasattr(mod, "FINAL_ACCEPTANCE_SQL")


class _ExclusiveTargetAcquisitionConnection(_StatefulConnection):
    """Apply double: target rows are available only through the new SQL pair."""

    def __init__(self, mod: Any, *, state: _SharedProjectionState) -> None:
        super().__init__(mod, state=state)
        self.acquisition_fetches: list[str] = []

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        if sql == self.mod.TARGET_COMPANIES_SQL:
            self.acquisition_fetches.append(sql)
            return [
                copy.deepcopy(self.state.companies[company_id])
                for company_id in sorted(self.state.companies)
            ]
        if sql == self.mod.TARGET_LINKS_SQL:
            self.acquisition_fetches.append(sql)
            return [
                copy.deepcopy(self.state.links[link_id])
                for link_id in sorted(self.state.links)
            ]
        return await super().fetch(sql, *args)

async def test_apply_exclusively_acquires_target_rows_prewrite_and_precommit(
) -> None:
    mod = _load()
    _require_target_acquisition_contract(mod)
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    state = _SharedProjectionState()
    conn = _ExclusiveTargetAcquisitionConnection(mod, state=state)

    first = await mod.apply_projection(
        conn, snapshot, expected_content_digest=snapshot.content_digest
    )

    assert first.no_op is False
    assert conn.acquisition_fetches == [
        mod.TARGET_COMPANIES_SQL,
        mod.TARGET_LINKS_SQL,
        mod.TARGET_COMPANIES_SQL,
        mod.TARGET_LINKS_SQL,
    ]
    exact_event_start = len(conn.events)
    exact = await mod.apply_projection(
        conn, snapshot, expected_content_digest=snapshot.content_digest
    )
    assert exact.no_op is True
    assert "companies" not in conn.events[exact_event_start:]
    assert "links" not in conn.events[exact_event_start:]

    state.companies[101]["company_name"] = "SYNTHETIC SAME-COUNT MUTANT"
    before = copy.deepcopy((state.companies, state.links, state.sequences))
    mutant_conn = _ExclusiveTargetAcquisitionConnection(mod, state=state)
    with pytest.raises(mod.TargetContractError):
        await mod.apply_projection(
            mutant_conn, snapshot, expected_content_digest=snapshot.content_digest
        )
    assert mutant_conn.acquisition_fetches == [
        mod.TARGET_COMPANIES_SQL,
        mod.TARGET_LINKS_SQL,
    ]
    assert "companies" not in mutant_conn.events and "links" not in mutant_conn.events
    assert (state.companies, state.links, state.sequences) == before


class _ConstraintPhaseMutantConnection(_StatefulConnection):
    def __init__(
        self,
        mod: Any,
        *,
        constraint_mutator: Callable[[list[dict[str, Any]]], None],
        mutate_on_constraint_read: int,
    ) -> None:
        super().__init__(mod)
        self.constraint_mutator = constraint_mutator
        self.mutate_on_constraint_read = mutate_on_constraint_read
        self.constraint_reads = 0

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        rows = await super().fetch(sql, *args)
        if sql == self.mod.TARGET_CONSTRAINTS_SQL:
            self.constraint_reads += 1
            if self.constraint_reads >= self.mutate_on_constraint_read:
                self.constraint_mutator(rows)
        return rows


def _mutate_fk_row(
    rows: list[dict[str, Any]], *, fk_column: str, kind: str
) -> None:
    fk_index = next(
        index
        for index, row in enumerate(rows)
        if row["definition"].startswith(f"FOREIGN KEY ({fk_column})")
    )
    if kind == "missing":
        rows.pop(fk_index)
    elif kind == "wrong-target":
        target_table = "shadow_clients" if fk_column == "client_id" else "shadow_companies"
        rows[fk_index]["definition"] = (
            f"FOREIGN KEY ({fk_column}) REFERENCES public.{target_table}(id)"
        )
    elif kind == "wrong-source":
        target_table = "clients" if fk_column == "client_id" else "companies"
        rows[fk_index]["definition"] = (
            f"FOREIGN KEY (other_{fk_column}) REFERENCES public.{target_table}(id)"
        )
    elif kind == "unrelated-validated":
        rows[fk_index]["definition"] = (
            "FOREIGN KEY (unrelated_id) REFERENCES public.unrelated(id)"
        )
        rows[fk_index]["convalidated"] = True
    elif kind == "unvalidated":
        rows[fk_index]["convalidated"] = False
    else:
        raise AssertionError(f"unknown FK mutation: {kind}")


@pytest.mark.parametrize(
    "mutation_kind",
    ("missing", "wrong-target", "wrong-source", "unrelated-validated", "unvalidated"),
)
@pytest.mark.parametrize("fk_column", ("client_id", "company_id"))
@pytest.mark.parametrize(
    ("phase", "constraint_read"),
    (("prewrite", 1), ("final", 2)),
)
async def test_exact_validated_link_fks_are_rechecked_prewrite_and_before_commit(
    mutation_kind: str,
    fk_column: str,
    phase: str,
    constraint_read: int,
) -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    conn = _ConstraintPhaseMutantConnection(
        mod,
        constraint_mutator=lambda rows: _mutate_fk_row(
            rows, fk_column=fk_column, kind=mutation_kind
        ),
        mutate_on_constraint_read=constraint_read,
    )

    with pytest.raises(mod.TargetContractError):
        await mod.apply_projection(
            conn, snapshot, expected_content_digest=snapshot.content_digest
        )

    assert conn.events[-1] == "rollback"
    if phase == "prewrite":
        assert "companies" not in conn.events and "links" not in conn.events
    else:
        assert "companies" in conn.events
        assert conn.constraint_reads >= 2
    assert conn.state.companies == {} and conn.state.links == {}


class _ProtectedDigestDriftConnection(_StatefulConnection):
    def __init__(self, mod: Any, *, drift_table: str, drift_field: str) -> None:
        super().__init__(mod)
        self.drift_table = drift_table
        self.drift_field = drift_field
        self.invariant_reads_by_table: dict[str, int] = {}

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any]:
        if sql in self.mod.PROTECTED_INVARIANT_SQL:
            table = self.mod.PROTECTED_TABLES[
                self.mod.PROTECTED_INVARIANT_SQL.index(sql)
            ]
            count = self.invariant_reads_by_table.get(table, 0) + 1
            self.invariant_reads_by_table[table] = count
            row = await super().fetchrow(sql, *args)
            if table == self.drift_table and count == 2:
                row[self.drift_field] = f"synthetic-{self.drift_field}-drift"
            return row
        return await super().fetchrow(sql, *args)


@pytest.mark.parametrize("protected_table", EXPECTED_PROTECTED_TABLES)
@pytest.mark.parametrize("drift_field", ("row_digest", "schema_digest"))
async def test_each_protected_table_digest_drift_rolls_back(
    protected_table: str,
    drift_field: str,
) -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    conn = _ProtectedDigestDriftConnection(
        mod, drift_table=protected_table, drift_field=drift_field
    )

    with pytest.raises(mod.ProjectionInvariantError, match="protected table"):
        await mod.apply_projection(
            conn, snapshot, expected_content_digest=snapshot.content_digest
        )

    assert conn.invariant_reads_by_table == dict.fromkeys(mod.PROTECTED_TABLES, 2)
    assert conn.events[-1] == "rollback"
    assert conn.state.companies == {} and conn.state.links == {}


def test_target_state_classifier_handles_empty_and_zero_link_noops_exactly() -> None:
    mod = _load()
    desired = "a" * 64
    assert mod.classify_target_state(
        companies_count=0,
        links_count=0,
        actual_digest="f" * 64,
        desired_digest=desired,
    ) == "empty"
    assert mod.classify_target_state(
        companies_count=2,
        links_count=0,
        actual_digest=desired,
        desired_digest=desired,
    ) == "exact-noop"


async def test_company_only_projection_applies_once_then_is_exact_noop() -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(_snapshot_stdout([_company(101)], []))
    conn = _StatefulConnection(mod)

    first = await mod.apply_projection(
        conn, snapshot, expected_content_digest=snapshot.content_digest
    )
    second_event_start = len(conn.events)
    second = await mod.apply_projection(
        conn, snapshot, expected_content_digest=snapshot.content_digest
    )

    assert first.companies_inserted == 1 and first.links_inserted == 0
    assert second.companies_inserted == second.links_inserted == 0
    assert second.no_op is True
    second_events = conn.events[second_event_start:]
    assert "companies" not in second_events and "links" not in second_events
    assert not any(event.startswith("alter:") for event in second_events)


async def test_dry_run_never_connects_or_writes_and_reports_unknown_eligibility(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod = _load()
    connect_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    write_attempts: list[bool] = []

    async def forbidden_connect(*args: Any, **kwargs: Any) -> Any:
        connect_calls.append((args, kwargs))
        raise AssertionError("dry-run must not connect to the target")

    async def forbidden_apply(*args: Any, **kwargs: Any) -> Any:
        write_attempts.append(True)
        raise AssertionError("dry-run must not write to the target")

    monkeypatch.setattr(mod, "apply_projection", forbidden_apply)

    runner = _Runner(_snapshot_stdout([_company(101)], [_link(201, 301, 101)]))
    report = await mod.run_projection(
        apply=False,
        dsn=mod.DEFAULT_TARGET_DSN,
        environ={},
        run_subprocess=runner,
        connect=forbidden_connect,
    )
    assert connect_calls == []
    assert report["projection"]["target_eligibility"] == "not_evaluated"
    assert report["projection"]["eligible_links"] == "unknown"
    assert report["projection"]["rejected_links_missing_local_client"] == "unknown"
    assert report["source"]["companies"] == 1
    assert report["source"]["links"] == 1
    assert report["target_before"] is None
    assert report["target_after"] is None
    assert report["projection"].get("projection_digest") in (None, "unknown")
    assert report.get("protected_type_digest") in (None, "unknown")
    assert report.get("sequence_preflight") in (None, "unknown")
    assert write_attempts == []

    actual_run_projection = mod.run_projection

    async def main_run_projection(**kwargs: Any) -> dict[str, Any]:
        return await actual_run_projection(
            **kwargs,
            run_subprocess=runner,
            connect=forbidden_connect,
        )

    monkeypatch.setattr(mod, "run_projection", main_run_projection)
    assert mod.main([]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "dry-run"
    assert output["write_attempted"] is False
    assert output["projection"]["target_eligibility"] == "not_evaluated"
    assert output["projection"]["eligible_links"] == "unknown"
    assert output["projection"]["rejected_links_missing_local_client"] == "unknown"
    assert connect_calls == []
    assert write_attempts == []


def _asyncpg_shaped_target_row(
    row: Mapping[str, Any], *, table: str
) -> dict[str, Any]:
    """Model asyncpg typed scalars and JSONB text at the target boundary."""
    shaped = copy.deepcopy(dict(row))
    if table == "companies":
        shaped["uuid"] = uuid.UUID(str(shaped["uuid"]))
        date_columns = (
            "akta_pendirian_date",
            "akta_perubahan_date",
            "sk_menhumkam_date",
        )
        shaped["custom_fields"] = json.dumps(
            shaped["custom_fields"], ensure_ascii=False, separators=(",", ":")
        )
    else:
        date_columns = ("start_date", "end_date")
    for column in date_columns:
        if shaped[column] is not None:
            shaped[column] = date.fromisoformat(str(shaped[column]))
    for column in ("created_at", "updated_at"):
        if shaped[column] is not None:
            shaped[column] = datetime.fromisoformat(str(shaped[column]))
    return shaped


def _independent_source_shape(row: Mapping[str, Any], *, table: str) -> dict[str, Any]:
    """Independent logical representation for a source JSON versus target row check."""
    normalized = dict(row)
    if table == "companies":
        normalized["uuid"] = str(normalized["uuid"])
        normalized["custom_fields"] = json.loads(str(normalized["custom_fields"]))
        date_columns = (
            "akta_pendirian_date",
            "akta_perubahan_date",
            "sk_menhumkam_date",
        )
    else:
        date_columns = ("start_date", "end_date")
    for column in date_columns:
        if normalized[column] is not None:
            normalized[column] = normalized[column].isoformat()
    for column in ("created_at", "updated_at"):
        if normalized[column] is not None:
            normalized[column] = normalized[column].isoformat()
    return normalized


class _AsyncpgProjectionConnection(_StatefulConnection):
    def __init__(
        self,
        mod: Any,
        *,
        target_mutation: tuple[str, str, Any] | None = None,
    ) -> None:
        super().__init__(mod)
        self.target_mutation = target_mutation

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        rows = await super().fetch(sql, *args)
        if sql not in (self.mod.TARGET_COMPANIES_SQL, self.mod.TARGET_LINKS_SQL):
            return rows
        table = "companies" if sql == self.mod.TARGET_COMPANIES_SQL else "links"
        shaped = [_asyncpg_shaped_target_row(row, table=table) for row in rows]
        if shaped and self.target_mutation is not None:
            mutation_table, column, value = self.target_mutation
            if mutation_table == table:
                shaped[0][column] = value
        return shaped


def _typed_source_snapshot(mod: Any) -> Any:
    company = _company(101)
    company.update(
        {
            "uuid": "00000000-0000-4000-8000-000000000101",
            "akta_pendirian_date": "2024-02-29",
            "akta_perubahan_date": "2025-01-02",
            "created_at": "2026-08-01T00:00:00",
            "updated_at": "2026-08-02T00:00:00+00:00",
            "custom_fields": {"sensitive": {"tier": 3}, "registered": True},
        }
    )
    link = _link(201, 301, 101)
    link.update(
        {
            "ownership_percentage": 12.5,
            "share_nominal_value": 123.45,
            "start_date": "2024-02-29",
            "end_date": "2026-08-01",
            "created_at": "2026-08-01T00:00:00+00:00",
            "updated_at": "2026-08-02T00:00:00",
        }
    )
    return mod.parse_source_snapshot(_snapshot_stdout([company], [link]))


async def test_asyncpg_target_scalars_match_source_json_in_final_acceptance() -> None:
    mod = _load()
    snapshot = _typed_source_snapshot(mod)
    expected = _independent_projection_digest(
        companies=snapshot.companies, eligible_links=snapshot.links
    )
    typed_companies = tuple(
        _independent_source_shape(
            _asyncpg_shaped_target_row(row, table="companies"), table="companies"
        )
        for row in snapshot.companies
    )
    typed_links = tuple(
        _independent_source_shape(
            _asyncpg_shaped_target_row(row, table="links"), table="links"
        )
        for row in snapshot.links
    )
    assert _independent_projection_digest(
        companies=typed_companies, eligible_links=typed_links
    ) == expected

    conn = _AsyncpgProjectionConnection(mod)
    result = await mod.apply_projection(
        conn, snapshot, expected_content_digest=snapshot.content_digest
    )
    assert result.projection_digest == expected
    assert conn.events[-1] == "commit"


@pytest.mark.parametrize(
    ("table", "column", "mutant"),
    [
        ("companies", "uuid", uuid.UUID("00000000-0000-4000-8000-000000000999")),
        ("companies", "akta_pendirian_date", date(2030, 1, 1)),
        ("companies", "created_at", datetime(2030, 1, 1, 0, 0)),
        ("companies", "updated_at", datetime(2030, 1, 1, tzinfo=timezone.utc)),
        ("links", "ownership_percentage", decimal.Decimal("12.6")),
        ("companies", "custom_fields", '{"sensitive":"mutant"}'),
    ],
    ids=("uuid", "date", "naive-datetime", "aware-datetime", "decimal", "jsonb"),
)
async def test_asyncpg_sensitive_target_mutants_fail_final_acceptance(
    table: str, column: str, mutant: Any
) -> None:
    mod = _load()
    snapshot = _typed_source_snapshot(mod)
    conn = _AsyncpgProjectionConnection(
        mod, target_mutation=(table, column, mutant)
    )

    with pytest.raises(mod.TargetContractError):
        await mod.apply_projection(
            conn, snapshot, expected_content_digest=snapshot.content_digest
        )

    assert conn.events[-1] == "rollback"
    assert conn.state.companies == {} and conn.state.links == {}


def _noop_sequence_state(
    *, source_max_id: int, is_called: bool, safe: bool
) -> tuple[int, bool]:
    if safe:
        return (source_max_id if is_called else source_max_id + 1, is_called)
    return (source_max_id - 1 if is_called else source_max_id, is_called)


@pytest.mark.parametrize(
    ("sequence_name", "source_max_id"),
    [
        ("public.companies_id_seq", 101),
        ("public.client_company_links_id_seq", 201),
    ],
)
@pytest.mark.parametrize("is_called", (False, True))
@pytest.mark.parametrize("safe", (False, True))
async def test_exact_noop_requires_safe_sequence_preflight(
    sequence_name: str, source_max_id: int, is_called: bool, safe: bool
) -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    state = _SharedProjectionState()
    state.companies = {101: copy.deepcopy(snapshot.companies[0])}
    state.links = {201: copy.deepcopy(snapshot.links[0])}
    state.sequences[sequence_name] = _noop_sequence_state(
        source_max_id=source_max_id, is_called=is_called, safe=safe
    )
    conn = _StatefulConnection(mod, state=state)

    if safe:
        result = await mod.apply_projection(
            conn, snapshot, expected_content_digest=snapshot.content_digest
        )
        assert result.no_op is True
        assert conn.events[-1] == "commit"
    else:
        with pytest.raises(mod.TargetContractError):
            await mod.apply_projection(
                conn, snapshot, expected_content_digest=snapshot.content_digest
            )
        assert conn.events[-1] == "rollback"

    assert "companies" not in conn.events and "links" not in conn.events
    assert not any(event.startswith("alter:") for event in conn.events)


class _CatalogAttestationConnection(_StatefulConnection):
    def __init__(
        self, mod: Any, *, relation_mutation: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(mod)
        self.relation_mutation = dict(relation_mutation or {})

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any]:
        row = await super().fetchrow(sql, *args)
        if sql == self.mod.TARGET_ATTEST_SQL:
            row.update(self.relation_mutation)
        return row


def test_target_attestation_uses_real_public_pg_catalog_relations() -> None:
    mod = _load()
    sql = mod.TARGET_ATTEST_SQL
    assert "pg_catalog.pg_class" in sql
    assert "pg_catalog.pg_namespace" in sql
    assert "companies_namespace" in sql and "links_namespace" in sql
    assert "companies_relname" in sql and "links_relname" in sql
    assert "companies_relkind" in sql and "links_relkind" in sql


@pytest.mark.parametrize(
    "relation_mutation",
    [
        {"companies_namespace": "shadow"},
        {"companies_relname": "companies_shadow"},
        {"companies_relkind": "v"},
        {"links_namespace": "shadow"},
        {"links_relname": "client_company_links_shadow"},
        {"links_relkind": "m"},
    ],
    ids=(
        "companies-namespace",
        "companies-name",
        "companies-kind",
        "links-namespace",
        "links-name",
        "links-kind",
    ),
)
async def test_catalog_relation_attestation_mutants_rollback_before_writes(
    relation_mutation: Mapping[str, Any],
) -> None:
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    conn = _CatalogAttestationConnection(mod, relation_mutation=relation_mutation)

    with pytest.raises(mod.TargetContractError):
        await mod.apply_projection(
            conn, snapshot, expected_content_digest=snapshot.content_digest
        )

    assert conn.events[-1] == "rollback"
    assert "companies" not in conn.events and "links" not in conn.events
    assert not any(event.startswith("alter:") for event in conn.events)


def _nested_fractional_snapshot(mod: Any) -> Any:
    company = _company(101)
    company["custom_fields"] = {
        "nested": {"fraction": 12.5},
        "array": [0.125, {"fraction": 7.25}],
    }
    return mod.parse_source_snapshot(_snapshot_stdout([company], []))


def _nested_fractional_target(
    source_row: Mapping[str, Any],
    *,
    fraction: float = 12.5,
    array_fraction: float = 0.125,
) -> dict[str, Any]:
    target = copy.deepcopy(dict(source_row))
    target["custom_fields"] = json.dumps(
        {
            "nested": {"fraction": fraction},
            "array": [array_fraction, {"fraction": 7.25}],
        },
        separators=(",", ":"),
    )
    return target


def test_jsonb_text_nested_fractionals_match_independent_decimal_oracle() -> None:
    mod = _load()
    snapshot = _nested_fractional_snapshot(mod)
    target = _nested_fractional_target(snapshot.companies[0], fraction=12.5)
    oracle_target = dict(target)
    oracle_target["custom_fields"] = json.loads(
        target["custom_fields"], parse_float=decimal.Decimal
    )
    expected = _independent_projection_digest(
        companies=snapshot.companies, eligible_links=()
    )

    assert _independent_projection_digest(
        companies=(oracle_target,), eligible_links=()
    ) == expected
    assert mod.compute_projection_digest(
        companies=(target,), eligible_links=()
    ) == expected


@pytest.mark.parametrize("fraction", (12.25, 12.75))
def test_jsonb_text_nested_fractional_mutants_change_projection_digest(
    fraction: float,
) -> None:
    mod = _load()
    snapshot = _nested_fractional_snapshot(mod)
    target = _nested_fractional_target(snapshot.companies[0], fraction=fraction)
    expected = mod.compute_projection_digest(
        companies=snapshot.companies, eligible_links=()
    )

    assert mod.compute_projection_digest(
        companies=(target,), eligible_links=()
    ) != expected


@pytest.mark.parametrize(
    ("array_fraction", "matches_source"),
    ((0.125, True), (0.0625, False), (0.375, False)),
)
def test_jsonb_text_fractional_array_matches_independent_oracle_and_detects_mutation(
    array_fraction: float,
    matches_source: bool,
) -> None:
    mod = _load()
    snapshot = _nested_fractional_snapshot(mod)
    target = _nested_fractional_target(
        snapshot.companies[0], array_fraction=array_fraction
    )
    oracle_target = dict(target)
    oracle_target["custom_fields"] = json.loads(
        target["custom_fields"], parse_float=decimal.Decimal
    )
    expected = _independent_projection_digest(
        companies=snapshot.companies, eligible_links=()
    )
    mutant_oracle = _independent_projection_digest(
        companies=(oracle_target,), eligible_links=()
    )

    assert (mutant_oracle == expected) is matches_source
    assert mod.compute_projection_digest(
        companies=(target,), eligible_links=()
    ) == mutant_oracle


class _SequenceDefinitionConnection(_StatefulConnection):
    def __init__(
        self, mod: Any, *, sequence_mutation: Mapping[str, Any]
    ) -> None:
        super().__init__(mod)
        self.sequence_mutation = dict(sequence_mutation)

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any]:
        row = await super().fetchrow(sql, *args)
        if sql == self.mod.SEQUENCE_ATTEST_SQL:
            row.update(self.sequence_mutation)
        return row


def test_sequence_attestation_requires_increment_one_and_cycle_false() -> None:
    mod = _load()
    sql = mod.SEQUENCE_ATTEST_SQL
    for field in (
        "companies_increment_by",
        "companies_cycle",
        "links_increment_by",
        "links_cycle",
    ):
        assert field in sql


@pytest.mark.parametrize("phase", ("initial-empty", "exact-noop"))
@pytest.mark.parametrize(
    ("sequence_mutation", "label"),
    [
        ({"companies_increment_by": -1}, "companies-increment-negative"),
        ({"companies_increment_by": 2}, "companies-increment-two"),
        ({"companies_cycle": True}, "companies-cycle"),
        ({"links_increment_by": -1}, "links-increment-negative"),
        ({"links_increment_by": 2}, "links-increment-two"),
        ({"links_cycle": True}, "links-cycle"),
    ],
)
async def test_sequence_definition_mutants_refuse_before_write_or_alter(
    phase: str,
    sequence_mutation: Mapping[str, Any],
    label: str,
) -> None:
    del label
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    conn = _SequenceDefinitionConnection(
        mod, sequence_mutation=sequence_mutation
    )
    if phase == "exact-noop":
        conn.state.companies = {101: copy.deepcopy(snapshot.companies[0])}
        conn.state.links = {201: copy.deepcopy(snapshot.links[0])}

    with pytest.raises(mod.TargetContractError):
        await mod.apply_projection(
            conn, snapshot, expected_content_digest=snapshot.content_digest
        )

    assert conn.events[-1] == "rollback"
    assert "companies" not in conn.events and "links" not in conn.events
    assert not any(event.startswith("alter:") for event in conn.events)


_CLIENTS_SHARE_LOCK_SQL = "LOCK TABLE public.clients IN SHARE MODE"
_TARGET_WRITE_LOCK_SQL = (
    "LOCK TABLE public.companies, public.client_company_links "
    "IN SHARE ROW EXCLUSIVE MODE"
)


class _ClientLockOrderState(_SharedProjectionState):
    def __init__(self) -> None:
        super().__init__()
        self.clients_write_lock = asyncio.Lock()
        self.client_writer_waiting = asyncio.Event()
        self.client_writer_acquired = asyncio.Event()


class _ClientLockOrderTransaction(_FakeTransaction):
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> bool:
        result = await super().__aexit__(exc_type, exc, traceback)
        if self.conn.holds_clients_share_lock:
            self.conn.state.clients_write_lock.release()
            self.conn.holds_clients_share_lock = False
        return result


class _ClientLockOrderConnection(_StatefulConnection):
    state: _ClientLockOrderState

    def __init__(
        self, mod: Any, *, state: _ClientLockOrderState, hold_first_writer: bool
    ) -> None:
        super().__init__(mod, state=state, hold_first_writer=hold_first_writer)
        self.holds_clients_share_lock = False
        self.holds_target_write_lock = False

    def transaction(self, **kwargs: Any) -> _ClientLockOrderTransaction:
        return _ClientLockOrderTransaction(self, kwargs)

    async def execute(self, sql: str, *args: Any) -> str:
        if sql == _CLIENTS_SHARE_LOCK_SQL:
            assert self.events[-1] == "set_statement_timeout"
            await self.state.clients_write_lock.acquire()
            self.holds_clients_share_lock = True
            self.events.append("clients_share_lock")
            return "LOCK TABLE"
        if sql == _TARGET_WRITE_LOCK_SQL:
            assert self.holds_clients_share_lock
            self.holds_target_write_lock = True
            self.events.append("target_table_lock")
            return "LOCK TABLE"
        if sql == self.mod.ADVISORY_XACT_LOCK_SQL:
            assert self.holds_clients_share_lock and self.holds_target_write_lock
        return await super().execute(sql, *args)

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        assert self.holds_clients_share_lock and self.holds_target_write_lock
        return await super().fetch(sql, *args)

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any]:
        assert self.holds_clients_share_lock and self.holds_target_write_lock
        return await super().fetchrow(sql, *args)

    async def write_client_row(self) -> None:
        self.state.client_writer_waiting.set()
        await self.state.clients_write_lock.acquire()
        self.state.client_writer_acquired.set()
        self.state.clients_write_lock.release()


async def test_client_lock_order_precedes_advisory_and_blocks_client_writer() -> None:
    """The clients SHARE lock is a transaction-wide barrier for client writers."""
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    state = _ClientLockOrderState()
    apply_conn = _ClientLockOrderConnection(
        mod, state=state, hold_first_writer=True
    )
    writer_conn = _ClientLockOrderConnection(
        mod, state=state, hold_first_writer=False
    )

    apply_task = asyncio.create_task(
        mod.apply_projection(
            apply_conn,
            snapshot,
            expected_content_digest=snapshot.content_digest,
        )
    )
    try:
        await asyncio.wait_for(state.first_writer_entered.wait(), timeout=1.0)
    except TimeoutError:
        await asyncio.gather(apply_task, return_exceptions=True)
        raise

    writer_task = asyncio.create_task(writer_conn.write_client_row())
    await asyncio.wait_for(state.client_writer_waiting.wait(), timeout=1.0)
    await asyncio.sleep(0)
    assert not state.client_writer_acquired.is_set()

    state.release_first_writer.set()
    await asyncio.wait_for(asyncio.gather(apply_task, writer_task), timeout=1.0)

    assert state.client_writer_acquired.is_set()
    assert apply_conn.events[0:7] == [
        "begin",
        "set_search_path",
        "set_lock_timeout",
        "set_statement_timeout",
        "clients_share_lock",
        "target_table_lock",
        "advisory_lock_attempt",
    ]


class _QualifiedRegclassCompatibilityConnection(_StatefulConnection):
    """Isolate result immutability from the legacy regclass-rendering failure."""

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any]:
        row = await super().fetchrow(sql, *args)
        if sql == self.mod.TARGET_ATTEST_SQL:
            row.update(
                {
                    "companies_relation": "public.companies",
                    "links_relation": "public.client_company_links",
                }
            )
        return row


def _expected_sequence_status() -> dict[str, dict[str, int | bool]]:
    return {
        "companies": {
            "last_value": 1000,
            "is_called": True,
            "next_value": 1001,
            "source_max_id": 101,
            "safe": True,
        },
        "client_company_links": {
            "last_value": 2000,
            "is_called": True,
            "next_value": 2001,
            "source_max_id": 201,
            "safe": True,
        },
    }


def _expected_protected_facts(mod: Any) -> dict[str, Any]:
    return {
        table: mod.InvariantState(
            row_count=7,
            schema_digest="schema-stable",
            row_digest="stable",
        )
        for table in mod.PROTECTED_TABLES
    }


def _detached_result_value(value: Any) -> Any:
    """Snapshot returned API values without retaining any mutable reference."""
    if isinstance(value, Mapping):
        return {
            key: _detached_result_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return tuple(_detached_result_value(item) for item in value)
    if all(
        hasattr(value, attribute)
        for attribute in ("row_count", "schema_digest", "row_digest")
    ):
        return (
            value.row_count,
            value.schema_digest,
            value.row_digest,
        )
    return value


def _observe_apply_result(result: Any) -> dict[str, Any]:
    """Read every fact carried by ApplyResult through its public attributes."""
    return {
        "accepted_plan": {
            "companies": _detached_result_value(result.accepted_plan.companies),
            "eligible_links": _detached_result_value(
                result.accepted_plan.eligible_links
            ),
            "rejected_missing_local_client": (
                result.accepted_plan.rejected_missing_local_client
            ),
            "projection_digest": result.accepted_plan.projection_digest,
        },
        "source_content_digest": result.source_content_digest,
        "target_before_counts": _detached_result_value(
            result.target_before_counts
        ),
        "target_after_counts": _detached_result_value(result.target_after_counts),
        "sequence_status": _detached_result_value(result.sequence_status),
        "protected_before": _detached_result_value(result.protected_before),
        "protected_after": _detached_result_value(result.protected_after),
        "companies_inserted": result.companies_inserted,
        "links_inserted": result.links_inserted,
        "invariant_digest": result.invariant_digest,
        "projection_digest": result.projection_digest,
        "no_op": result.no_op,
    }


def _assign_item(container: Any, key: Any, value: Any) -> None:
    container[key] = value


def _append_item(container: Any, value: Any) -> None:
    container.append(value)


def _assign_attribute(instance: Any, name: str, value: Any) -> None:
    setattr(instance, name, value)


async def _returned_apply_result_with_aliases(
    mod: Any, *, phase: str
) -> tuple[Any, dict[str, Any]]:
    company = _company(101)
    company["custom_fields"] = {
        "nested": {"fraction": 12.5, "label": "original"},
        "array": [0.125, {"fraction": 7.25}],
    }
    link = _link(201, 301, 101)
    link["notes"] = "ORIGINAL LINK"
    snapshot = mod.parse_source_snapshot(_snapshot_stdout([company], [link]))
    state = _SharedProjectionState()
    if phase == "exact-noop":
        state.companies = {101: copy.deepcopy(snapshot.companies[0])}
        state.links = {201: copy.deepcopy(snapshot.links[0])}
    conn = _QualifiedRegclassCompatibilityConnection(mod, state=state)
    result = await mod.apply_projection(
        conn, snapshot, expected_content_digest=snapshot.content_digest
    )
    source_company = snapshot.companies[0]
    source_link = snapshot.links[0]
    state_company = state.companies[101]
    state_link = state.links[201]
    aliases = {
        "snapshot": snapshot,
        "source_company": source_company,
        "source_link": source_link,
        "source_custom_fields": source_company["custom_fields"],
        "source_nested_object": source_company["custom_fields"]["nested"],
        "source_array": source_company["custom_fields"]["array"],
        "source_array_object": source_company["custom_fields"]["array"][1],
        "state_companies": state.companies,
        "state_links": state.links,
        "state_sequences": state.sequences,
        "state_company": state_company,
        "state_link": state_link,
        "state_custom_fields": state_company["custom_fields"],
        "state_nested_object": state_company["custom_fields"]["nested"],
        "state_array": state_company["custom_fields"]["array"],
        "state_array_object": state_company["custom_fields"]["array"][1],
    }
    return result, aliases


async def _returned_apply_result(mod: Any, *, phase: str) -> Any:
    result, _aliases = await _returned_apply_result_with_aliases(
        mod, phase=phase
    )
    return result


def _apply_result_mutations() -> tuple[tuple[str, Callable[[Any], None]], ...]:
    return (
        (
            "accepted company row",
            lambda result: _assign_item(
                result.accepted_plan.companies[0], "company_name", "MUTATED"
            ),
        ),
        (
            "accepted company custom_fields",
            lambda result: _assign_item(
                result.accepted_plan.companies[0]["custom_fields"],
                "extra",
                "MUTATED",
            ),
        ),
        (
            "accepted company nested object",
            lambda result: _assign_item(
                result.accepted_plan.companies[0]["custom_fields"]["nested"],
                "label",
                "MUTATED",
            ),
        ),
        (
            "accepted company nested array item",
            lambda result: _assign_item(
                result.accepted_plan.companies[0]["custom_fields"]["array"],
                0,
                decimal.Decimal("9.875"),
            ),
        ),
        (
            "accepted company nested array append",
            lambda result: _append_item(
                result.accepted_plan.companies[0]["custom_fields"]["array"],
                {"mutant": True},
            ),
        ),
        (
            "accepted link row",
            lambda result: _assign_item(
                result.accepted_plan.eligible_links[0], "notes", "MUTATED"
            ),
        ),
        (
            "accepted companies tuple",
            lambda result: _assign_item(result.accepted_plan.companies, 0, {}),
        ),
        (
            "accepted plan attribute",
            lambda result: _assign_attribute(
                result.accepted_plan, "rejected_missing_local_client", 99
            ),
        ),
        (
            "target before counts",
            lambda result: _assign_item(
                result.target_before_counts, "companies", 999
            ),
        ),
        (
            "target after counts",
            lambda result: _assign_item(
                result.target_after_counts, "client_company_links", 999
            ),
        ),
        (
            "sequence status outer map",
            lambda result: _assign_item(result.sequence_status, "mutant", {}),
        ),
        (
            "sequence status nested map",
            lambda result: _assign_item(
                result.sequence_status["companies"], "last_value", 999
            ),
        ),
        (
            "protected before map",
            lambda result: _assign_item(result.protected_before, "clients", None),
        ),
        (
            "protected before value",
            lambda result: _assign_attribute(
                result.protected_before["clients"], "row_count", 999
            ),
        ),
        (
            "protected after map",
            lambda result: _assign_item(
                result.protected_after, "intake_queue", None
            ),
        ),
        (
            "apply result attribute",
            lambda result: _assign_attribute(result, "source_content_digest", "x"),
        ),
    )


def _clear_mapping(mapping: Any) -> None:
    mapping.clear()


def _apply_result_backing_alias_mutations() -> tuple[
    tuple[str, Callable[[Mapping[str, Any]], None]], ...
]:
    return (
        (
            "source company row alias",
            lambda aliases: _assign_item(
                aliases["source_company"], "company_name", "MUTATED SOURCE"
            ),
        ),
        (
            "source link row alias",
            lambda aliases: _assign_item(
                aliases["source_link"], "notes", "MUTATED SOURCE LINK"
            ),
        ),
        (
            "source custom_fields alias",
            lambda aliases: _assign_item(
                aliases["source_custom_fields"], "extra", "MUTATED SOURCE"
            ),
        ),
        (
            "source nested object alias",
            lambda aliases: _assign_item(
                aliases["source_nested_object"], "label", "MUTATED SOURCE"
            ),
        ),
        (
            "source array item alias",
            lambda aliases: _assign_item(
                aliases["source_array"], 0, decimal.Decimal("6.875")
            ),
        ),
        (
            "source array append alias",
            lambda aliases: _append_item(
                aliases["source_array"], {"source_mutant": True}
            ),
        ),
        (
            "source array object alias",
            lambda aliases: _assign_item(
                aliases["source_array_object"],
                "fraction",
                decimal.Decimal("8.75"),
            ),
        ),
        (
            "state companies backing map",
            lambda aliases: _clear_mapping(aliases["state_companies"]),
        ),
        (
            "state links backing map",
            lambda aliases: _clear_mapping(aliases["state_links"]),
        ),
        (
            "state company row alias",
            lambda aliases: _assign_item(
                aliases["state_company"], "company_name", "MUTATED STATE"
            ),
        ),
        (
            "state link row alias",
            lambda aliases: _assign_item(
                aliases["state_link"], "notes", "MUTATED STATE LINK"
            ),
        ),
        (
            "state custom_fields alias",
            lambda aliases: _assign_item(
                aliases["state_custom_fields"], "extra", "MUTATED STATE"
            ),
        ),
        (
            "state nested object alias",
            lambda aliases: _assign_item(
                aliases["state_nested_object"], "label", "MUTATED STATE"
            ),
        ),
        (
            "state array item alias",
            lambda aliases: _assign_item(
                aliases["state_array"], 0, decimal.Decimal("6.875")
            ),
        ),
        (
            "state array append alias",
            lambda aliases: _append_item(
                aliases["state_array"], {"state_mutant": True}
            ),
        ),
        (
            "state array object alias",
            lambda aliases: _assign_item(
                aliases["state_array_object"],
                "fraction",
                decimal.Decimal("8.75"),
            ),
        ),
        (
            "state sequence backing map",
            lambda aliases: _clear_mapping(aliases["state_sequences"]),
        ),
    )


@pytest.mark.parametrize("phase", ("apply", "exact-noop"))
async def test_apply_result_is_deeply_immutable_for_every_carried_fact(
    phase: str,
) -> None:
    """Every returned mapping and nested source row rejects mutation."""
    mod = _load()
    baseline_result = await _returned_apply_result(mod, phase=phase)
    baseline = _observe_apply_result(baseline_result)
    assert baseline["accepted_plan"]["companies"][0]["custom_fields"] == {
        "array": (decimal.Decimal("0.125"), {"fraction": decimal.Decimal("7.25")}),
        "nested": {
            "fraction": decimal.Decimal("12.5"),
            "label": "original",
        },
    }
    assert baseline["accepted_plan"]["eligible_links"][0]["notes"] == (
        "ORIGINAL LINK"
    )

    violations: list[str] = []
    for label, mutate in _apply_result_mutations():
        result = await _returned_apply_result(mod, phase=phase)
        if _observe_apply_result(result) != baseline:
            violations.append(f"{label}: pre-mutation facts differ")
            continue
        try:
            mutate(result)
        except (TypeError, AttributeError):
            pass
        except Exception as exc:  # pragma: no cover - diagnostic contract
            violations.append(f"{label}: raised {type(exc).__name__}")
        else:
            violations.append(f"{label}: mutation succeeded")
        if _observe_apply_result(result) != baseline:
            violations.append(f"{label}: original facts changed")

    assert violations == []


@pytest.mark.parametrize("phase", ("apply", "exact-noop"))
async def test_apply_result_is_detached_from_every_mutable_input_alias(
    phase: str,
) -> None:
    """A read-only proxy over caller-owned backing dictionaries is insufficient."""
    mod = _load()
    baseline_result, baseline_aliases = await _returned_apply_result_with_aliases(
        mod, phase=phase
    )
    baseline = _observe_apply_result(baseline_result)
    assert baseline_aliases["snapshot"].companies[0] is (
        baseline_aliases["source_company"]
    )
    assert baseline_aliases["snapshot"].links[0] is baseline_aliases["source_link"]
    assert baseline_aliases["source_company"]["custom_fields"] is (
        baseline_aliases["source_custom_fields"]
    )
    assert baseline_aliases["source_custom_fields"]["nested"] is (
        baseline_aliases["source_nested_object"]
    )
    assert baseline_aliases["source_custom_fields"]["array"] is (
        baseline_aliases["source_array"]
    )
    assert baseline_aliases["source_array"][1] is (
        baseline_aliases["source_array_object"]
    )
    assert baseline_aliases["state_companies"][101] is (
        baseline_aliases["state_company"]
    )
    assert baseline_aliases["state_links"][201] is baseline_aliases["state_link"]
    assert baseline_aliases["state_company"]["custom_fields"] is (
        baseline_aliases["state_custom_fields"]
    )
    assert baseline_aliases["state_custom_fields"]["nested"] is (
        baseline_aliases["state_nested_object"]
    )
    assert baseline_aliases["state_custom_fields"]["array"] is (
        baseline_aliases["state_array"]
    )
    assert baseline_aliases["state_array"][1] is (
        baseline_aliases["state_array_object"]
    )

    violations: list[str] = []
    for label, mutate_alias in _apply_result_backing_alias_mutations():
        result, aliases = await _returned_apply_result_with_aliases(
            mod, phase=phase
        )
        if _observe_apply_result(result) != baseline:
            violations.append(f"{label}: pre-mutation facts differ")
            continue
        mutate_alias(aliases)
        if _observe_apply_result(result) != baseline:
            violations.append(f"{label}: accepted facts followed mutable alias")

    assert violations == []


@pytest.mark.parametrize("phase", ("apply", "exact-noop"))
async def test_apply_result_carries_all_transaction_accepted_report_facts(
    phase: str,
) -> None:
    """The report must be derived from immutable facts accepted before commit."""
    mod = _load()
    snapshot = mod.parse_source_snapshot(
        _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    )
    state = _SharedProjectionState()
    if phase == "exact-noop":
        state.companies = {101: copy.deepcopy(snapshot.companies[0])}
        state.links = {201: copy.deepcopy(snapshot.links[0])}
    conn = _StatefulConnection(mod, state=state)

    result = await mod.apply_projection(
        conn, snapshot, expected_content_digest=snapshot.content_digest
    )

    assert result.accepted_plan == mod.build_projection_plan(
        snapshot, local_client_ids={301}
    )
    assert result.source_content_digest == snapshot.content_digest
    assert result.target_before_counts == {
        "companies": 1 if phase == "exact-noop" else 0,
        "client_company_links": 1 if phase == "exact-noop" else 0,
    }
    assert result.target_after_counts == {
        "companies": 1,
        "client_company_links": 1,
    }
    assert result.sequence_status == _expected_sequence_status()
    expected_protected = _expected_protected_facts(mod)
    assert result.protected_before == expected_protected
    assert result.protected_after == expected_protected
    assert result.invariant_digest == mod.protected_shape_digest(expected_protected)
    assert result.projection_digest == result.accepted_plan.projection_digest
    assert result.companies_inserted == (0 if phase == "exact-noop" else 1)
    assert result.links_inserted == (0 if phase == "exact-noop" else 1)
    assert result.no_op is (phase == "exact-noop")


class _PostCommitMutationTransaction(_FakeTransaction):
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> bool:
        result = await super().__aexit__(exc_type, exc, traceback)
        if exc_type is None:
            self.conn.post_commit_mutated = True
            self.conn.state.companies.clear()
            self.conn.state.links.clear()
            self.conn.state.sequences["public.companies_id_seq"] = (1, False)
            self.conn.state.sequences["public.client_company_links_id_seq"] = (
                1,
                False,
            )
        return result


class _PostCommitMutationConnection(_StatefulConnection):
    def __init__(
        self, mod: Any, *, state: _SharedProjectionState | None = None
    ) -> None:
        super().__init__(mod, state=state)
        self.post_commit_mutated = False
        self.post_transaction_reads: list[str] = []
        self.closed = False

    def transaction(self, **kwargs: Any) -> _PostCommitMutationTransaction:
        return _PostCommitMutationTransaction(self, kwargs)

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        if not self.in_transaction:
            self.post_transaction_reads.append(sql)
            raise AssertionError("report must not fetch after the transaction")
        return await super().fetch(sql, *args)

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any]:
        if not self.in_transaction:
            self.post_transaction_reads.append(sql)
            raise AssertionError("report must not fetch after the transaction")
        return await super().fetchrow(sql, *args)

    async def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("phase", ("apply", "exact-noop"))
async def test_run_projection_reports_only_transaction_accepted_facts(
    phase: str,
) -> None:
    mod = _load()
    snapshot_stdout = _snapshot_stdout([_company(101)], [_link(201, 301, 101)])
    snapshot = mod.parse_source_snapshot(snapshot_stdout)
    state = _SharedProjectionState()
    if phase == "exact-noop":
        state.companies = {101: copy.deepcopy(snapshot.companies[0])}
        state.links = {201: copy.deepcopy(snapshot.links[0])}
    conn = _PostCommitMutationConnection(mod, state=state)

    async def connect(*args: Any, **kwargs: Any) -> _PostCommitMutationConnection:
        del args, kwargs
        return conn

    report = await mod.run_projection(
        apply=True,
        dsn=mod.DEFAULT_TARGET_DSN,
        environ={mod.WRITE_ENABLE_ENV: "true"},
        run_subprocess=_Runner(snapshot_stdout),
        connect=connect,
        expected_content_digest=snapshot.content_digest,
    )

    assert conn.post_commit_mutated and conn.closed
    assert conn.post_transaction_reads == []
    assert conn.state.companies == {} and conn.state.links == {}
    assert report["target_before"] == {
        "companies": 1 if phase == "exact-noop" else 0,
        "client_company_links": 1 if phase == "exact-noop" else 0,
    }
    assert report["target_after"] == {
        "companies": 1,
        "client_company_links": 1,
    }
    assert report["projection"] == {
        "companies": 1,
        "eligible_links": 1,
        "rejected_links_missing_local_client": 0,
        "projection_digest": mod.compute_projection_digest(
            companies=snapshot.companies, eligible_links=snapshot.links
        ),
    }
    assert report["sequence_preflight"] == _expected_sequence_status()
    assert report["protected_type_digest"] == mod.protected_shape_digest(
        _expected_protected_facts(mod)
    )
