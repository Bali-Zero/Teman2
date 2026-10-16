#!/usr/bin/env python3
"""B01 recovery adapter and throwaway PG17 guilt/innocence harness.

Conforms strictly to:
- `.agent-receipts/udb-wave8-dux/CONTRACT-CONVENTIONS.md`
  (sha256: a7feea89fa64000d76c18a52d705dd008b4a6336a6d58af98c2618a13048c559)
- `.agent-receipts/udb-wave8-dux/DUX-CONSOLIDATION.md`
  (sha256: c39218718f496b643b550abf98ca40bd2755e74d3954caed953005eb5b906e14)
- `.agent-receipts/udb-wave8-dux/ADVERSARY-FINDINGS.md`
  (sha256: 29c57f706bcc0dd8e7f492f3ffe5215598798ed173f452f19aa7a086c8faaf54)

Stdlib only. No network access, no live production store connections, no PII.

Input resolution: when the gitignored `.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json`
is present every pinned input is read from `.agent-receipts/` exactly as before. Otherwise (a
clean checkout) the inputs the records consume are read from the committed
`fixtures/` directory next to this file: byte-identical copies are checked against the SOURCE
sha256, and the consumer-matrix projection is checked against its own OUTPUT sha256 only (it is
never reported as the source's bytes). See `fixtures/PROVENANCE.json`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[4]
BASE_COMMIT = "8061c88e0c43dd42e735fd012f9ed072df3ef3d6"
BASE_COMMIT_TIMESTAMP = "2026-10-15T07:06:22Z"

FIXTURES_REL = "research/operations/udb-wave8/B01/fixtures"
FIXTURE_KIND = "FROZEN_METADATA_TEST_FIXTURES_NOT_NEW_NATIVE_OBSERVATIONS"
FIXTURE_COPY = "BYTE_IDENTICAL_COPY"
FIXTURE_PROJECTION = "PROJECTION_NOT_SOURCE_BYTES"

# Pins for the committed fixtures. A copy is pinned to the SOURCE sha256 recorded in the
# `.agent-receipts` manifests (the fixture bytes are the source bytes). The projection is pinned
# to its own OUTPUT sha256; its `source_sha256` only says what it was derived from.
FIXTURE_PINS: dict[str, dict[str, str]] = {
    "REAL-RUN-RECEIPT.json": {
        "identity": FIXTURE_COPY,
        "source_rel": ".agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json",
        "sha256": "9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d",
    },
    "STATE.json": {
        "identity": FIXTURE_COPY,
        "source_rel": ".agent-receipts/udb-wave8-inputs/STATE.json",
        "sha256": "caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4",
    },
    "LEAD-DELTA.json": {
        "identity": FIXTURE_COPY,
        "source_rel": (
            ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json"
        ),
        "sha256": "91e6bac9c91181a2b3aa3f6cd1dc6585671c18ce90cb887444229a1a17a084e7",
    },
    "consumer-matrix.projection.csv": {
        "identity": FIXTURE_PROJECTION,
        "source_rel": ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv",
        "source_sha256": "c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118",
        "sha256": "d743bfb90c0ece5c40288bac0bb041c1842db8cf1088255b38f8462061b6d70f",
    },
}

FROZEN_KEYS: tuple[str, ...] = (
    "consumer_id",
    "operation_id",
    "store_id",
    "source_version",
    "evidence_timestamp",
    "evidence_sha256",
    "status",
    "unknowns",
)

INSTANCE_KEYS: tuple[str, ...] = (
    "principal",
    "role",
    "tenant",
    "authorization",
    "transaction",
    "effects",
    "retries",
    "idempotency",
    "failure",
    "retention",
    "recovery",
)

ALLOWED_STATUSES: frozenset[str] = frozenset(
    {"EVIDENCED", "PARTIAL", "BLOCKED", "CONFLICT", "UNKNOWN"}
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _use_fixtures(repo_root: Path) -> bool:
    """True on a clean checkout, i.e. when the gitignored receipts pins are absent."""
    return not (repo_root / ".agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json").is_file()


def _input_path(repo_root: Path, source_rel: str) -> Path:
    """Where `source_rel` is read from: the receipt itself, else its committed fixture."""
    if not _use_fixtures(repo_root):
        return repo_root / source_rel
    for name, pin in FIXTURE_PINS.items():
        if pin["source_rel"] == source_rel:
            return repo_root / FIXTURES_REL / name
    raise ValueError(f"No committed fixture for {source_rel}")


def _verify_fixture_inputs(repo_root: Path) -> dict[str, str]:
    """Verify the committed fixtures: copies against SOURCE sha256, projection against OUTPUT."""
    fixtures_dir = repo_root / FIXTURES_REL
    provenance_path = fixtures_dir / "PROVENANCE.json"
    if not provenance_path.is_file():
        raise FileNotFoundError(
            f"Neither .agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json nor {FIXTURES_REL}/"
            f"PROVENANCE.json exists under {repo_root}"
        )
    with open(provenance_path, encoding="utf-8") as fh:
        provenance = json.load(fh).get("fixtures", {})
    if set(provenance) != set(FIXTURE_PINS):
        raise ValueError("PROVENANCE.json fixture set differs from the adapter pins")

    verified: dict[str, str] = {}
    for name, pin in FIXTURE_PINS.items():
        is_copy = pin["identity"] == FIXTURE_COPY
        expected = pin["sha256"]
        entry = provenance[name]
        claimed = {
            key: entry.get(key)
            for key in ("kind", "identity", "source_rel", "source_sha256", "output_sha256")
        }
        pinned = {
            "kind": FIXTURE_KIND,
            "identity": pin["identity"],
            "source_rel": pin["source_rel"],
            "source_sha256": pin.get("source_sha256", expected),
            "output_sha256": expected,
        }
        if claimed != pinned:
            raise ValueError(f"PROVENANCE.json disagrees with the adapter pin for fixture {name}")
        actual = sha256_file(fixtures_dir / name)
        if actual != expected:
            what = "source" if is_copy else "projection output"
            raise ValueError(
                f"SHA-256 mismatch for fixture {name} ({what}): "
                f"expected {expected}, got {actual}"
            )
        # A copy IS the source bytes, so it is reported under the source path. A projection is
        # reported under its own path and never under the source's.
        verified[pin["source_rel"] if is_copy else f"{FIXTURES_REL}/{name}"] = actual
    return verified


def verify_pinned_inputs(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """Verify SHA-256 digests of all scoped frozen inputs before reading."""
    if _use_fixtures(repo_root):
        return _verify_fixture_inputs(repo_root)
    manifest_path = repo_root / ".agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json"
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)

    verified: dict[str, str] = {}
    for rel_name, expected_sha in manifest["files"].items():
        fpath = repo_root / ".agent-receipts/udb-wave8-inputs" / rel_name
        actual_sha = sha256_file(fpath)
        if actual_sha != expected_sha:
            raise ValueError(
                f"SHA-256 mismatch for {rel_name}: expected {expected_sha}, got {actual_sha}"
            )
        verified[f".agent-receipts/udb-wave8-inputs/{rel_name}"] = actual_sha

    prior_manifest_path = (
        repo_root / ".agent-receipts/udb-wave8-inputs-dux/prior/PINNED-MANIFEST.json"
    )
    if prior_manifest_path.is_file():
        with open(prior_manifest_path, encoding="utf-8") as fh:
            prior_manifest = json.load(fh)
        for rel_name in (
            "completion-20261015-0831/LEAD-DELTA.json",
            "completion-20261015-0831/SYNTHETIC-PG-RESULT.json",
        ):
            expected_sha = prior_manifest["files"][rel_name]
            fpath = repo_root / ".agent-receipts/udb-wave8-inputs-dux/prior" / rel_name
            actual_sha = sha256_file(fpath)
            if actual_sha != expected_sha:
                raise ValueError(
                    f"SHA-256 mismatch for prior/{rel_name}: expected {expected_sha}, got {actual_sha}"
                )
            verified[f".agent-receipts/udb-wave8-inputs-dux/prior/{rel_name}"] = actual_sha

    return verified


def load_valid_consumer_ids(
    repo_root: Path = REPO_ROOT,
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    """Load the 6,029 CSV rows + the 6,030th LEAD-DELTA runtime addition."""
    csv_path = _input_path(repo_root, ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv")
    lead_delta_path = _input_path(
        repo_root,
        ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json",
    )

    by_id: dict[str, dict[str, str]] = {}
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            cid = row["consumer_id"]
            by_id[cid] = row

    with open(lead_delta_path, encoding="utf-8") as fh:
        lead_delta = json.load(fh)

    for addition in lead_delta.get("additions", []):
        cid = addition["consumer_id"]
        by_id[cid] = addition

    return by_id, lead_delta


def _field(value: Any, status: str, evidence_ref: str | None) -> dict[str, Any]:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid field status: {status!r}")
    return {"value": value, "status": status, "evidence_ref": evidence_ref}


def validate_contract_instance_record(
    record: Mapping[str, Any], valid_consumer_ids: frozenset[str]
) -> None:
    """Enforce CONTRACT-CONVENTIONS.md 19-key + x_ extension schema."""
    keys = list(record.keys())
    required_19 = list(FROZEN_KEYS) + list(INSTANCE_KEYS)
    if keys[:19] != required_19:
        raise ValueError(
            f"Record keys[:19] must be exactly {required_19}, got {keys[:19]}"
        )
    for extra_key in keys[19:]:
        if not extra_key.startswith("x_"):
            raise ValueError(f"Extra key {extra_key!r} must start with 'x_'")

    cid = record["consumer_id"]
    if cid not in valid_consumer_ids:
        raise ValueError(f"consumer_id {cid!r} not in pinned 6,030-lead universe")

    status = record["status"]
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid row status: {status!r}")

    unknowns = record["unknowns"]
    if not isinstance(unknowns, list):
        raise ValueError("unknowns must be a list")
    if status == "EVIDENCED" and unknowns:
        raise ValueError("unknowns must be empty when status is EVIDENCED")
    if status != "EVIDENCED" and not unknowns:
        raise ValueError("unknowns must be non-empty when status is not EVIDENCED")

    for ikey in INSTANCE_KEYS:
        obj = record[ikey]
        if not isinstance(obj, Mapping) or set(obj.keys()) != {
            "value",
            "status",
            "evidence_ref",
        }:
            raise ValueError(
                f"Instance field {ikey!r} must be {{'value', 'status', 'evidence_ref'}}"
            )
        if obj["status"] not in ALLOWED_STATUSES:
            raise ValueError(f"Instance field {ikey!r} has invalid status {obj['status']!r}")


def build_b01_records(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build B01 contract rows and summary strictly from verified pinned inputs."""
    verified_hashes = verify_pinned_inputs(repo_root)
    by_id, lead_delta = load_valid_consumer_ids(repo_root)
    valid_ids = frozenset(by_id.keys())

    receipt_rel = ".agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json"
    state_rel = ".agent-receipts/udb-wave8-inputs/STATE.json"
    lead_delta_rel = (
        ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json"
    )

    with open(_input_path(repo_root, receipt_rel), encoding="utf-8") as fh:
        real_receipt = json.load(fh)
    with open(_input_path(repo_root, state_rel), encoding="utf-8") as fh:
        state_doc = json.load(fh)

    terminal_events = [
        ev for ev in real_receipt.get("events", []) if ev.get("event") == "TERMINAL"
    ]
    if len(terminal_events) != 1:
        raise ValueError("Expected exactly one TERMINAL event in REAL-RUN-RECEIPT.json")
    terminal = terminal_events[0]
    started_events = [
        ev for ev in real_receipt.get("events", []) if ev.get("event") == "REQUEST_ACCEPTED"
    ]
    started_at = started_events[0]["started_at"] if started_events else None
    terminal_ts = terminal["sidecar"]["timestamp"]
    verifier_summary = terminal["verifier_summary"]

    mini_cid = "runtime_mini_46522da0ef79d3aa7422ca41"
    if mini_cid not in valid_ids:
        raise ValueError(f"Missing expected Mini restore consumer_id {mini_cid}")

    primary_record: dict[str, Any] = {
        "consumer_id": mini_cid,
        "operation_id": "UNASSIGNED_B05",
        "store_id": "unknown:unknown:unknown",
        "source_version": BASE_COMMIT,
        "evidence_timestamp": terminal_ts,
        "evidence_sha256": verified_hashes[receipt_rel],
        "status": "BLOCKED",
        "unknowns": [
            "OPERATION_ID_PENDING_B05",
            "STORE_ID_PROPOSED:pg:mini:nuzantara-pg-drill/public",
            "CONVERSATIONS_UNMEASURED_CHECK_CAUSE_UNOBSERVED_ON_BACKUP",
            "CLIENTS_VIOLATION_SUBCHECK_UNOBSERVED_ON_BACKUP",
            "MINI_CANDIDATE_INSTALLATION_NOT_ADMITTED",
            "OWNER_CONSENT_EXHAUSTED_FOR_NEW_REAL_BACKUP_RUN",
            "DATA_OWNER_RULING_REQUIRED_ON_CLIENTS_VIOLATION",
        ],
        "principal": _field(
            "launchd://mini/46522da0ef79d3aa7422ca41b5a1650560afb1b1579ff36db0ea38a1f8d9e2e5",
            "PARTIAL",
            lead_delta_rel,
        ),
        "role": _field(
            {
                "drill_user_default": "drill",
                "derived_nologin_roles_via": "scripts/restore_drill/role_scanner.py",
                "effective_job_role_overrides": "UNOBSERVED",
            },
            "PARTIAL",
            "scripts/restore_drill/run_drill.sh",
        ),
        "tenant": _field(
            "system_wide_full_backup_restore_drill",
            "EVIDENCED",
            "scripts/restore_drill/run_drill.sh",
        ),
        "authorization": _field(
            {
                "prior_authorization": state_doc.get("real_backup_owner_authorization"),
                "real_backup_run_triggered": state_doc.get("real_backup_run_triggered"),
                "further_runs": "OWNER_CONSENT_REQUIRED",
            },
            "BLOCKED",
            state_rel,
        ),
        "transaction": _field(
            {
                "restore_stream": "gunzip -c dump | psql dsn -v ON_ERROR_STOP=1",
                "verifier_queries": "per_query_autocommit_psql_ON_ERROR_STOP_1",
            },
            "EVIDENCED",
            "scripts/restore_drill/run_drill.sh",
        ),
        "effects": _field(
            {
                "reads": "s3://nuzantara-backups/postgres/nuzantara-fly-*.sql.gz",
                "writes_disposable": "docker container nuzantara-pg-drill (127.0.0.1:15499) + /tmp/nuzantara-restore-drill.*",
                "sidecar": "~/.organism/last_seen/mini.restore_drill.json",
            },
            "EVIDENCED",
            "scripts/restore_drill/run_drill.sh",
        ),
        "retries": _field(
            {
                "postgres_health_poll_attempts": 60,
                "watchdog_timeout_seconds": 1800,
                "organ_recovery_action": "human_only",
            },
            "EVIDENCED",
            "scripts/restore_drill/run_drill.sh",
        ),
        "idempotency": _field(
            {
                "stale_workdir_reap_minutes": 60,
                "active_workdir_refusal_exit": 75,
                "container_label_cleanup": "com.nuzantara.restore-drill.run",
            },
            "EVIDENCED",
            "scripts/restore_drill/run_drill.sh",
        ),
        "failure": _field(
            {
                "verifier_exit_codes": {"PASS": 0, "FAIL": 1, "USAGE": 2, "CANNOT-VERIFY": 3},
                "drill_exit_codes": {
                    "PASS": 0,
                    "CANNOT-VERIFY": 2,
                    "PSQL_RESTORE_ABORT": 3,
                    "GUNZIP_ABORT": 4,
                    "VERIFIER_FAIL": 5,
                    "CONCURRENT_RUN": 75,
                    "WATCHDOG_TIMEOUT": 124,
                },
            },
            "EVIDENCED",
            "scripts/restore_drill/run_drill.sh",
        ),
        "retention": _field(
            {
                "max_dump_age_hours": 72,
                "scratch_workdir_and_container": "deleted_on_exit_trap",
            },
            "EVIDENCED",
            "scripts/restore_drill/run_drill.sh",
        ),
        "recovery": _field(
            {
                "real_backup_run_started_at": started_at,
                "real_backup_run_terminal_at": terminal_ts,
                "real_backup_elapsed_seconds": real_receipt.get("elapsed_seconds"),
                "verifier_aggregate": verifier_summary.get("aggregate"),
                "invariants": verifier_summary.get("invariants"),
                "raw_report_sha256": verifier_summary.get("raw_report_sha256"),
                "real_backup_restore_success_proved": state_doc.get(
                    "real_backup_restore_success_proved"
                ),
            },
            "BLOCKED",
            receipt_rel,
        ),
        "x_evidence_ref": receipt_rel,
        "x_block_id": "B01",
        "x_verifier_aggregate": verifier_summary.get("aggregate"),
        "x_invariant_verdicts": {
            item["relation"]: {
                "status": item["status"],
                "reason_classes": item["reason_classes"],
            }
            for item in verifier_summary.get("invariants", [])
        },
        "x_mini_install_required": True,
    }
    validate_contract_instance_record(primary_record, valid_ids)

    historical_refs: list[dict[str, Any]] = []
    for ref_id in lead_delta.get("historical_source_references_retained", []):
        if ref_id not in valid_ids:
            raise ValueError(f"Historical restore reference {ref_id!r} missing from CSV")
        csv_row = by_id[ref_id]
        historical_refs.append(
            {
                "consumer_id": ref_id,
                "entry_point": csv_row.get("entry_point"),
                "store": csv_row.get("store"),
                "disposition": csv_row.get("disposition"),
                "evidence": csv_row.get("evidence"),
            }
        )

    owned_files = (
        "scripts/ci/restore_drill_verify.py",
        "scripts/tests/test_restore_drill_verify.py",
        "scripts/restore_drill/run_drill.sh",
        "scripts/restore_drill/role_scanner.py",
        "scripts/restore_drill/Dockerfile",
    )
    candidate_pins = {
        rel: sha256_file(repo_root / rel)
        for rel in owned_files
        if (repo_root / rel).is_file()
    }

    bundle: dict[str, Any] = {
        "campaign_id": "universal-db-wave8-20261015",
        "block_id": "B01",
        "source_version": BASE_COMMIT,
        "base_commit_timestamp": BASE_COMMIT_TIMESTAMP,
        "verified_input_hashes": verified_hashes,
        "candidate_file_hashes": candidate_pins,
        "real_run_observation": {
            "started_at": started_at,
            "terminal_timestamp": terminal_ts,
            "elapsed_seconds": real_receipt.get("elapsed_seconds"),
            "terminal_elapsed_seconds": terminal.get("elapsed_seconds"),
            "source_pin_matches": started_events[0].get("source_pin_matches")
            if started_events
            else None,
            "sidecar_status": terminal["sidecar"]["status"],
            "verifier_aggregate": verifier_summary["aggregate"],
            "relation_count": len(verifier_summary["invariants"]),
            "invariants": verifier_summary["invariants"],
            "raw_report_sha256": verifier_summary["raw_report_sha256"],
            "rows_counts_and_raw_errors_exported": verifier_summary[
                "rows_counts_and_raw_errors_exported"
            ],
        },
        "historical_restore_references": historical_refs,
        "records": [primary_record],
    }
    if _use_fixtures(repo_root):
        bundle["input_resolution"] = {
            "mode": "COMMITTED_FIXTURES",
            "kind": FIXTURE_KIND,
            "fixtures_dir": FIXTURES_REL,
            "byte_identical_copies_verified_against_source_sha256": sorted(
                pin["source_rel"]
                for pin in FIXTURE_PINS.values()
                if pin["identity"] == FIXTURE_COPY
            ),
            "projections_verified_against_output_sha256_only": {
                f"{FIXTURES_REL}/{name}": {
                    "derived_from": pin["source_rel"],
                    "derived_from_sha256_per_provenance_not_reverified": pin["source_sha256"],
                    "output_sha256": pin["sha256"],
                }
                for name, pin in FIXTURE_PINS.items()
                if pin["identity"] == FIXTURE_PROJECTION
            },
            "other_pinned_inputs": "NOT_VERIFIED_IN_THIS_MODE (not consumed by the records)",
        }
    return bundle


def _find_pg_bin(binary_name: str) -> str | None:
    found = shutil.which(binary_name)
    if found:
        return found
    for prefix in (
        "/opt/homebrew/opt/postgresql@17/bin",
        "/usr/local/opt/postgresql@17/bin",
        "/usr/lib/postgresql/17/bin",
        "/opt/homebrew/bin",
    ):
        candidate = Path(prefix) / binary_name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _load_verifier_module(repo_root: Path = REPO_ROOT):
    target = repo_root / "scripts/ci/restore_drill_verify.py"
    spec = importlib.util.spec_from_file_location("restore_drill_verify_b01", target)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _base_synthetic_ddl(messages_col_ddl: str) -> str:
    """Create the 5 golden relations with synthetic-only non-PII rows."""
    return f"""
    DROP TABLE IF EXISTS conversations, clients, visa_decisions, events_outbox, visa_decision_retention_policies CASCADE;

    CREATE TABLE conversations (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(255) NOT NULL,
        messages {messages_col_ddl},
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE clients (
        id SERIAL PRIMARY KEY,
        full_name VARCHAR(255) NOT NULL,
        client_type VARCHAR(50) NOT NULL DEFAULT 'individual',
        google_drive_folder_id VARCHAR(255),
        lead_metadata JSONB DEFAULT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE visa_decisions (
        id SERIAL PRIMARY KEY,
        decision_id VARCHAR(64) NOT NULL,
        environment VARCHAR(32) NOT NULL,
        verdict VARCHAR(64) NOT NULL,
        citations JSONB NOT NULL DEFAULT '[]'::jsonb,
        rule_pack_id VARCHAR(64),
        evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE events_outbox (
        id SERIAL PRIMARY KEY,
        channel VARCHAR(64) NOT NULL,
        payload JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        consumed_at TIMESTAMPTZ,
        consumer_id VARCHAR(128)
    );

    CREATE TABLE visa_decision_retention_policies (
        id SERIAL PRIMARY KEY,
        environment VARCHAR(32) NOT NULL,
        policy_version INTEGER NOT NULL,
        retention_interval INTERVAL NOT NULL,
        idempotency_retention_interval INTERVAL NOT NULL,
        legal_hold_review_interval INTERVAL NOT NULL,
        retention_anchor VARCHAR(32) NOT NULL,
        effective_period TSTZRANGE NOT NULL,
        approved_by VARCHAR(128) NOT NULL,
        approval_reference VARCHAR(128) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    INSERT INTO conversations (user_id, messages) VALUES ('synthetic_u1', '[]');
    INSERT INTO clients (full_name, client_type, lead_metadata)
    VALUES ('SYNTHETIC_CLIENT_01', 'individual', '{{"source": "synthetic"}}'::jsonb);
    """


def run_synthetic_pg17_suite(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Run the 4 adversary guilt cases + innocence proofs on a throwaway PG17 cluster.

    Uses a private Unix-domain socket (`listen_addresses=''`), zero TCP listeners,
    zero production data, and deterministic cleanup in `finally:`.
    """
    initdb_bin = _find_pg_bin("initdb")
    postgres_bin = _find_pg_bin("postgres")
    psql_bin = _find_pg_bin("psql")
    pg_isready_bin = _find_pg_bin("pg_isready")
    if not (initdb_bin and postgres_bin and psql_bin):
        return {
            "synthetic_only": True,
            "status": "SKIPPED_PG17_BINARIES_NOT_FOUND",
            "binaries_found": {
                "initdb": initdb_bin,
                "postgres": postgres_bin,
                "psql": psql_bin,
            },
        }

    rdv = _load_verifier_module(repo_root)
    base_dir = Path(tempfile.mkdtemp(prefix="b01-synth-pg17-"))
    data_dir = base_dir / "data"
    sock_dir = base_dir / "sock"
    sock_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    proc: subprocess.Popen[str] | None = None

    def exec_sql(dsn: str, sql: str) -> None:
        res = subprocess.run(
            [psql_bin, dsn, "-Atq", "-v", "ON_ERROR_STOP=1"],
            input=sql,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"psql failed (rc={res.returncode}): {res.stderr.strip()}")

    try:
        subprocess.run(
            [
                initdb_bin,
                "-D",
                str(data_dir),
                "-U",
                "postgres",
                "--auth=trust",
                "--no-instructions",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )

        proc = subprocess.Popen(
            [
                postgres_bin,
                "-D",
                str(data_dir),
                "-k",
                str(sock_dir),
                "-c",
                "listen_addresses=",
                "-c",
                "fsync=on",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        dsn = f"postgresql://postgres@/postgres?host={sock_dir}"
        ready = False
        for _ in range(50):
            if proc.poll() is not None:
                raise RuntimeError("Throwaway postgres exited prematurely")
            probe = subprocess.run(
                [psql_bin, dsn, "-Atqc", "SELECT 1;"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if probe.returncode == 0 and probe.stdout.strip() == "1":
                ready = True
                break
            time.sleep(0.2)
        if not ready:
            raise RuntimeError("Throwaway postgres did not become ready on private socket")

        # 1. Innocence: conversations.messages as JSONB (production type)
        exec_sql(dsn, _base_synthetic_ddl("JSONB NOT NULL DEFAULT '[]'::jsonb"))
        res_innocence_jsonb = rdv.evaluate(rdv.fetch_live(dsn, psql_bin=psql_bin))

        # 2. Innocence: conversations.messages as TEXT (Migration 143 type)
        exec_sql(dsn, _base_synthetic_ddl("TEXT NOT NULL DEFAULT '[]'"))
        res_innocence_text = rdv.evaluate(rdv.fetch_live(dsn, psql_bin=psql_bin))

        # 3. Guilt Case 1a: JSONB non-array values (object + string scalar) are counted
        exec_sql(dsn, _base_synthetic_ddl("JSONB NOT NULL DEFAULT '[]'::jsonb"))
        exec_sql(
            dsn,
            """
            INSERT INTO conversations (user_id, messages)
            VALUES ('synthetic_u2', '{"not": "array"}'::jsonb),
                   ('synthetic_u3', '"scalar_string"'::jsonb);
            """,
        )
        m_guilt1_jsonb = rdv.fetch_live(dsn, psql_bin=psql_bin)
        res_guilt1_jsonb = rdv.evaluate(m_guilt1_jsonb)
        conv_m1_jsonb = next(
            m for m in m_guilt1_jsonb if m["relation"] == "conversations"
        )

        # 4. Guilt Case 1b: TEXT malformed JSON and non-array JSON are counted
        exec_sql(dsn, _base_synthetic_ddl("TEXT NOT NULL DEFAULT '[]'"))
        exec_sql(
            dsn,
            """
            INSERT INTO conversations (user_id, messages)
            VALUES ('synthetic_u2', 'malformed-json{'),
                   ('synthetic_u3', '{"not": "array"}');
            """,
        )
        m_guilt1_text = rdv.fetch_live(dsn, psql_bin=psql_bin)
        res_guilt1_text = rdv.evaluate(m_guilt1_text)
        conv_m1_text = next(m for m in m_guilt1_text if m["relation"] == "conversations")

        # 5. Guilt Case 2: NULL behaviour is unchanged on both JSONB and TEXT (B01-F4)
        exec_sql(dsn, _base_synthetic_ddl("JSONB DEFAULT NULL"))
        exec_sql(
            dsn,
            "INSERT INTO conversations (user_id, messages) VALUES ('synthetic_null', NULL);",
        )
        m_null_jsonb = rdv.fetch_live(dsn, psql_bin=psql_bin)
        res_null_jsonb = rdv.evaluate(m_null_jsonb)

        exec_sql(dsn, _base_synthetic_ddl("TEXT DEFAULT NULL"))
        exec_sql(
            dsn,
            "INSERT INTO conversations (user_id, messages) VALUES ('synthetic_null', NULL);",
        )
        m_null_text = rdv.fetch_live(dsn, psql_bin=psql_bin)
        res_null_text = rdv.evaluate(m_null_text)

        # 6. Guilt Case 3: String-scalar lead_metadata still FAILs (B01-F3)
        exec_sql(dsn, _base_synthetic_ddl("JSONB NOT NULL DEFAULT '[]'::jsonb"))
        exec_sql(
            dsn,
            """
            INSERT INTO clients (full_name, client_type, lead_metadata)
            VALUES ('SYNTHETIC_CLIENT_02', 'individual', to_jsonb('{"double":"encoded"}'::text));
            """,
        )
        m_guilt3 = rdv.fetch_live(dsn, psql_bin=psql_bin)
        res_guilt3 = rdv.evaluate(m_guilt3)
        clients_m3 = next(m for m in m_guilt3 if m["relation"] == "clients")
        clients_v3 = next(
            v for v in res_guilt3["invariants"] if v["relation"] == "clients"
        )

        # 7. Guilt Case 4: FAIL on clients + unmeasured check on conversations -> CANNOT-VERIFY
        exec_sql(dsn, "ALTER TABLE conversations DROP COLUMN messages;")
        m_guilt4 = rdv.fetch_live(dsn, psql_bin=psql_bin)
        res_guilt4 = rdv.evaluate(m_guilt4)
        by_rel_g4 = {v["relation"]: v for v in res_guilt4["invariants"]}

        # 8. Schema guard check: clients missing lead_metadata -> CANNOT-VERIFY naming lead_metadata
        exec_sql(dsn, _base_synthetic_ddl("JSONB NOT NULL DEFAULT '[]'::jsonb"))
        exec_sql(dsn, "ALTER TABLE clients DROP COLUMN lead_metadata;")
        m_guard = rdv.fetch_live(dsn, psql_bin=psql_bin)
        res_guard = rdv.evaluate(m_guard)
        clients_v_guard = next(
            v for v in res_guard["invariants"] if v["relation"] == "clients"
        )

        checks = {
            "innocence_jsonb_pass": res_innocence_jsonb["aggregate"] == "PASS",
            "innocence_text_pass": res_innocence_text["aggregate"] == "PASS",
            "guilt_1_jsonb_non_array_counted": (
                conv_m1_jsonb.get("violations", {}).get("messages_not_json_array") == 2
                and res_guilt1_jsonb["aggregate"] == "FAIL"
            ),
            "guilt_1_text_malformed_and_non_array_counted": (
                conv_m1_text.get("violations", {}).get("messages_not_json_array") == 2
                and res_guilt1_text["aggregate"] == "FAIL"
            ),
            "guilt_2_null_jsonb_unchanged_pass": res_null_jsonb["aggregate"] == "PASS",
            "guilt_2_null_text_unchanged_pass": res_null_text["aggregate"] == "PASS",
            "guilt_3_string_scalar_lead_metadata_fails": (
                clients_m3.get("violations", {}).get("lead_metadata_not_object") == 1
                and clients_v3["status"] == "FAIL"
                and res_guilt3["aggregate"] == "FAIL"
            ),
            "guilt_4_fail_plus_unmeasured_gives_cannot_verify": (
                by_rel_g4["clients"]["status"] == "FAIL"
                and by_rel_g4["conversations"]["status"] == "CANNOT-VERIFY"
                and res_guilt4["aggregate"] == "CANNOT-VERIFY"
            ),
            "schema_guard_missing_lead_metadata_named": (
                clients_v_guard["status"] == "CANNOT-VERIFY"
                and any(
                    "missing required column(s): lead_metadata" in r
                    for r in clients_v_guard["reasons"]
                )
            ),
        }

        return {
            "synthetic_only": True,
            "production_connections_requested": False,
            "tcp_listener_requested": False,
            "native_binary_sha256": {
                "initdb": sha256_file(Path(initdb_bin)),
                "postgres": sha256_file(Path(postgres_bin)),
                "psql": sha256_file(Path(psql_bin)),
                **(
                    {"pg_isready": sha256_file(Path(pg_isready_bin))}
                    if pg_isready_bin
                    else {}
                ),
            },
            "all_passed": all(checks.values()),
            "checks": checks,
        }
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        shutil.rmtree(base_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory to write b01-recovery-instances.json and b01-recovery-summary.json",
    )
    parser.add_argument(
        "--synthetic-pg-out",
        type=Path,
        default=None,
        help="Optional path to run throwaway PG17 suite and write its JSON receipt",
    )
    args = parser.parse_args(argv)

    bundle = build_b01_records(REPO_ROOT)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    instances_path = args.out_dir / "b01-recovery-instances.json"
    summary_path = args.out_dir / "b01-recovery-summary.json"

    with open(instances_path, "w", encoding="utf-8") as fh:
        json.dump(bundle["records"], fh, indent=2)
        fh.write("\n")

    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, indent=2)
        fh.write("\n")

    if args.synthetic_pg_out is not None:
        pg_res = run_synthetic_pg17_suite(REPO_ROOT)
        args.synthetic_pg_out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.synthetic_pg_out, "w", encoding="utf-8") as fh:
            json.dump(pg_res, fh, indent=2)
            fh.write("\n")
        if not pg_res.get("all_passed", False):
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
