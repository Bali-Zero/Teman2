#!/usr/bin/env python3
"""Deterministic Redis consumer census and CONTRACT-CONVENTIONS.md ledger generator (B02).

Reads pinned Wave-8 inputs and admitted digest-only historical receipt identities.
Enforces membership testing against the 6,030-lead universe (6,029 CSV rows + 1 LEAD-DELTA row).

Inputs come from the gitignored `.agent-receipts/` tree when it is present; otherwise from the
committed, sha256-pinned `fixtures/` (frozen metadata test fixtures, NOT new native observations;
see `fixtures/PROVENANCE.json`). Both sources yield a byte-identical ledger.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any, NamedTuple

BASE_COMMIT_SHA = "8061c88e0c43dd42e735fd012f9ed072df3ef3d6"
BASE_COMMIT_TIMESTAMP = "2026-10-15T07:06:22Z"
PRIOR_BASELINE_TIMESTAMP = "2026-10-15T03:28:29.868658+00:00"
DUX_REQ_03_TIMESTAMP = "2026-10-15T08:54:05.004121+00:00"
DUX_REQ_04_TIMESTAMP = "2026-10-15T08:54:05.387260+00:00"

FROZEN_ROW_KEYS: tuple[str, ...] = (
    "consumer_id",
    "operation_id",
    "store_id",
    "source_version",
    "evidence_timestamp",
    "evidence_sha256",
    "status",
    "unknowns",
)

VALID_STATUSES: frozenset[str] = frozenset(
    {"EVIDENCED", "PARTIAL", "BLOCKED", "CONFLICT", "UNKNOWN"}
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


RECEIPTS_ROOT = ".agent-receipts"
FIXTURES_REL = "research/operations/udb-wave8/B02/fixtures"
INPUT_MODES: tuple[str, ...] = ("auto", "fixtures")

# sha256 of the ORIGINAL campaign inputs, as pinned by INPUT-MANIFEST.json / PINNED-MANIFEST.json.
# This is the identity the ledger reports for them, whichever input mode supplied the data.
SOURCE_CSV_SHA256 = "c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118"
LEAD_DELTA_SHA256 = "91e6bac9c91181a2b3aa3f6cd1dc6585671c18ce90cb887444229a1a17a084e7"
REDIS_PRO_METADATA_SHA256 = "e77cefd1e69ccff94db34292cfecc73e87e1888ad433e3bd0dffb2ff58b3cda0"
REDIS_MINI_METADATA_SHA256 = "6ad6b9b9d4839906061610fa54392880d08699efd66162a7f30e58ff79087e30"

# Committed fixtures. The three small files are byte-identical copies of their sources and hash to
# the SOURCE identities above. The matrix fixture is a PROJECTION: it does NOT hash to
# SOURCE_CSV_SHA256 and is verified against its own sha256 instead.
FIXTURE_PROJECTION_SHA256 = "d3d541a59df30b65bc3d488eee7475be5c12590d622cb959d0a36faacda70b7c"
PROJECTED_COLUMNS: tuple[str, ...] = (
    "consumer_id",
    "entry_point",
    "runtime_registration",
    "store",
    "store_signal_hint",
    "disposition",
    "test_coverage",
    "phase_source_scope_status",
    "phase_ci_actor_identity",
)
# Columns the census reads on EVERY matrix row; any other projected column is read only on
# Redis-tagged rows, so the projection blanks it elsewhere (keeps the fixture small and minimal).
ALL_ROWS_COLUMNS: tuple[str, ...] = ("consumer_id", "store", "store_signal_hint")
USERS_ROOT_LITERAL = "/Users/"
USERS_ROOT_SENTINEL = "<USERS_ROOT>/"


class CensusInputs(NamedTuple):
    source: str  # "agent-receipts" | "committed-fixtures"
    matrix_path: Path
    lead_delta_path: Path
    pro_meta_path: Path
    mini_meta_path: Path
    # Identities REPORTED in the ledger (those of the original inputs).
    matrix_sha256: str
    lead_delta_sha256: str
    pro_meta_sha256: str
    mini_meta_sha256: str
    # sha256 of the projected matrix fixture actually read; None when the original matrix is read.
    matrix_projection_sha256: str | None


def _store_tokens(row: dict[str, str]) -> set[str]:
    stores_combined = f"{row.get('store', '')};{row.get('store_signal_hint', '')}".lower()
    return {tok.strip() for tok in stores_combined.split(";") if tok.strip()}


def project_consumer_matrix(source_bytes: bytes) -> bytes:
    """Project the pinned consumer matrix to the cells the census reads (row order kept).

    Columns outside ALL_ROWS_COLUMNS are kept only on Redis-tagged rows and blank elsewhere, since
    the census never reads them there. The only other cell transformation is the reversible
    USERS_ROOT_LITERAL -> USERS_ROOT_SENTINEL encoding: no absolute home-directory path survives.
    """
    reader = csv.DictReader(io.StringIO(source_bytes.decode("utf-8"), newline=""))
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=list(PROJECTED_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in reader:
        redis_tagged = "redis" in _store_tokens(row)
        cells: dict[str, str] = {}
        for col in PROJECTED_COLUMNS:
            if not (redis_tagged or col in ALL_ROWS_COLUMNS):
                cells[col] = ""
                continue
            value = row[col]
            if value is None or USERS_ROOT_SENTINEL in value:
                raise ValueError(f"cannot project column {col}: missing value or sentinel present")
            cells[col] = value.replace(USERS_ROOT_LITERAL, USERS_ROOT_SENTINEL)
        writer.writerow(cells)
    return out.getvalue().encode("utf-8")


def resolve_inputs(repo_root: Path, mode: str = "auto") -> CensusInputs:
    """Choose the census inputs: `.agent-receipts` when any is present, else committed fixtures."""
    if mode not in INPUT_MODES:
        raise ValueError(f"unknown input mode: {mode}")
    completion = repo_root / RECEIPTS_ROOT / "udb-wave8-inputs-dux/prior/completion-20261015-0831"
    matrix = repo_root / RECEIPTS_ROOT / "udb-wave8-inputs/consumer-matrix.csv"
    lead = completion / "LEAD-DELTA.json"
    pro = completion / "REDIS-PRO-METADATA.json"
    mini = completion / "REDIS-MINI-METADATA.json"
    if mode == "auto" and any(path.exists() for path in (matrix, lead, pro, mini)):
        return CensusInputs(
            "agent-receipts",
            matrix,
            lead,
            pro,
            mini,
            sha256_file(matrix),
            sha256_file(lead),
            sha256_file(pro),
            sha256_file(mini),
            None,
        )

    fixtures = repo_root / FIXTURES_REL
    matrix_fx = fixtures / "consumer-matrix.projection.csv"
    projection_sha = sha256_file(matrix_fx)
    if projection_sha != FIXTURE_PROJECTION_SHA256:
        raise ValueError(
            f"fixture consumer-matrix.projection.csv sha256 mismatch: {projection_sha}"
            f" != {FIXTURE_PROJECTION_SHA256}"
        )
    copies: list[Path] = []
    for name, expected in (
        ("LEAD-DELTA.json", LEAD_DELTA_SHA256),
        ("REDIS-PRO-METADATA.json", REDIS_PRO_METADATA_SHA256),
        ("REDIS-MINI-METADATA.json", REDIS_MINI_METADATA_SHA256),
    ):
        path = fixtures / name
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f"fixture {name} sha256 mismatch: {actual} != {expected}")
        copies.append(path)
    return CensusInputs(
        "committed-fixtures",
        matrix_fx,
        copies[0],
        copies[1],
        copies[2],
        SOURCE_CSV_SHA256,
        LEAD_DELTA_SHA256,
        REDIS_PRO_METADATA_SHA256,
        REDIS_MINI_METADATA_SHA256,
        projection_sha,
    )


def _open_matrix(inputs: CensusInputs) -> Any:
    if inputs.matrix_projection_sha256 is None:
        return inputs.matrix_path.open(newline="", encoding="utf-8")
    text = inputs.matrix_path.read_bytes().decode("utf-8")
    return io.StringIO(text.replace(USERS_ROOT_SENTINEL, USERS_ROOT_LITERAL), newline="")


def resolve_store_id_for_row(row: dict[str, str]) -> tuple[str, list[str]]:
    """Map a Redis-tagged CSV row to its CONTRACT-CONVENTIONS.md store_id and unknowns."""
    cid = row["consumer_id"]
    reg = row.get("runtime_registration", "UNKNOWN")
    entry = row.get("entry_point", "")
    extra_unknowns: list[str] = []

    if cid == "runtime_6e9b0846bcc0bc34" or reg.startswith("Nuzantara:"):
        return "redis:pro:6379/db0", ["STORE_ID_PROPOSED:redis:pro:6379/db0"]
    if reg.startswith("Mini-Pro2:") or "scripts/mini/" in entry:
        return "redis:mini:6379/db0", extra_unknowns
    return "unknown:unknown:unknown", ["REDIS_INSTANCE_HOST_UNRESOLVED_FROM_STATIC_SOURCE"]


DUX_RECEIPT_SHA256 = {'DUX-REQ-B02-03.out': 'b0f510eb06809573b50f75c1155a0a569a0f0237ea4df022d0fe7c66801d416e', 'DUX-REQ-B02-03.pro.out': '4924a388e48af18458127f3d2d9b33a326f6ce416f5e932d27929f34de010301', 'DUX-REQ-B02-04.out': '521658bea8409fc5531a4ff817701c89a98390cf5837cf0f9f5b9ae3894b690a'}


def admitted_dux_receipt_hashes(repo_root: Path) -> dict[str, str]:
    """Frozen receipt identities; raw historical output is not a shipping dependency."""
    root = repo_root / "research/operations/udb-wave8/B02/dux-requests"
    for name, expected in DUX_RECEIPT_SHA256.items():
        candidate = root / name
        if (candidate.exists() or candidate.is_symlink()) and (candidate.is_symlink() or not candidate.is_file() or sha256_file(candidate) != expected):
            raise ValueError("DUX_RECEIPT_PIN_MISMATCH")
    return dict(DUX_RECEIPT_SHA256)


def generate_census(repo_root: Path, inputs: CensusInputs | None = None) -> dict[str, Any]:
    if inputs is None:
        inputs = resolve_inputs(repo_root)
    receipt_pins = admitted_dux_receipt_hashes(repo_root)

    csv_sha = inputs.matrix_sha256
    lead_delta_sha = inputs.lead_delta_sha256
    pro_meta_sha = inputs.pro_meta_sha256
    mini_meta_sha = inputs.mini_meta_sha256
    req03_mini_sha = receipt_pins['DUX-REQ-B02-03.out']
    req03_pro_sha = receipt_pins['DUX-REQ-B02-03.pro.out']
    req04_pro_sha = receipt_pins['DUX-REQ-B02-04.out']

    lead_delta = json.loads(inputs.lead_delta_path.read_text(encoding="utf-8"))
    delta_ids = {item["consumer_id"] for item in lead_delta.get("additions", [])}

    universe_ids: set[str] = set(delta_ids)
    redis_rows_raw: list[dict[str, str]] = []
    event_delivery_only_count = 0

    with _open_matrix(inputs) as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row["consumer_id"]
            universe_ids.add(cid)
            tokens = _store_tokens(row)
            if "redis" in tokens:
                redis_rows_raw.append(row)
            elif "event_delivery" in tokens:
                event_delivery_only_count += 1

    by_disposition: Counter[str] = Counter()
    by_test_coverage: Counter[str] = Counter()
    by_scope_status: Counter[str] = Counter()
    by_ci_actor: Counter[str] = Counter()

    contract_rows: list[dict[str, Any]] = []
    registered_runtime_rows: list[dict[str, Any]] = []

    for row in redis_rows_raw:
        cid = row["consumer_id"]
        if cid not in universe_ids:
            raise ValueError(f"Membership check failed for consumer_id: {cid}")

        disp = row.get("disposition", "") or "EMPTY"
        tcov = row.get("test_coverage", "") or "EMPTY"
        sstat = row.get("phase_source_scope_status", "") or "EMPTY"
        ci_actor = row.get("phase_ci_actor_identity", "") or "EMPTY"

        by_disposition[disp] += 1
        by_test_coverage[tcov] += 1
        by_scope_status[sstat] += 1
        by_ci_actor[ci_actor] += 1

        store_id, store_unknowns = resolve_store_id_for_row(row)
        unknowns: list[str] = [
            "OPERATION_ID_PENDING_B05",
            "OWNER_CONSENT_REQUIRED_REDIS_OBSERVER_ACL",
        ]
        unknowns.extend(store_unknowns)

        if cid == "runtime_6e9b0846bcc0bc34":
            ev_ts = DUX_REQ_04_TIMESTAMP
            ev_sha = req04_pro_sha
            ev_ref = "research/operations/udb-wave8/B02/dux-requests/DUX-REQ-B02-04.out"
            row_status = "PARTIAL"
            unknowns.append(
                "HOME_FORK_SHA256_DRIFTED_FROM_20261012_CENSUS:6adec8ac4f1e7fbc3a46f026e92c178d15643796b270eea969e556f25cf3885d"
            )
            unknowns.append("USES_APPLICATION_REDIS_PASSWORD_DEFAULT_USER")
        else:
            ev_ts = BASE_COMMIT_TIMESTAMP
            ev_sha = csv_sha
            ev_ref = ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
            row_status = "BLOCKED" if "BLOCKED" in disp else "PARTIAL"
            unknowns.append("STATIC_SOURCE_ONLY")

        contract_row: dict[str, Any] = {
            "consumer_id": cid,
            "operation_id": "UNASSIGNED_B05",
            "store_id": store_id,
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": ev_ts,
            "evidence_sha256": ev_sha,
            "status": row_status,
            "unknowns": unknowns,
            "x_entry_point": row.get("entry_point", ""),
            "x_disposition": disp,
            "x_test_coverage": tcov,
            "x_runtime_registration": row.get("runtime_registration", "UNKNOWN"),
            "x_observed_stores": row.get("store", ""),
            "x_evidence_ref": ev_ref,
        }
        contract_rows.append(contract_row)

        if row.get("runtime_registration", "UNKNOWN") != "UNKNOWN":
            registered_runtime_rows.append(
                {
                    "consumer_id": cid,
                    "entry_point": row.get("entry_point", ""),
                    "runtime_registration": row.get("runtime_registration", ""),
                    "disposition": disp,
                    "store_id": store_id,
                }
            )

    return {
        "campaign": "universal-db-wave8-20261015",
        "block_id": "B02",
        "source_version": BASE_COMMIT_SHA,
        "inputs_pinned": {
            "consumer_matrix_csv_sha256": csv_sha,
            "lead_delta_json_sha256": lead_delta_sha,
            "redis_pro_metadata_prior_sha256": pro_meta_sha,
            "redis_mini_metadata_prior_sha256": mini_meta_sha,
            "dux_req_b02_03_mini_sha256": req03_mini_sha,
            "dux_req_b02_03_pro_sha256": req03_pro_sha,
            "dux_req_b02_04_pro_sha256": req04_pro_sha,
        },
        "observed_servers": {
            "mini": {
                "store_id": "redis:mini:6379/db0",
                "redis_version": "8.10.2",
                "redis_cli_version": "8.10.2",
                "version_observed_at": DUX_REQ_03_TIMESTAMP,
                "version_evidence_sha256": req03_mini_sha,
                "prior_unauthenticated_info_status": "AUTHORIZATION_REQUIRED",
                "prior_evidence_timestamp": PRIOR_BASELINE_TIMESTAMP,
                "prior_evidence_sha256": mini_meta_sha,
                "keychain_observer": "UNSET",
                "env_observer": "ABSENT",
                "status": "BLOCKED",
            },
            "pro": {
                "store_id": "redis:pro:6379/db0",
                "redis_version": "8.6.1",
                "redis_cli_version": "8.6.1",
                "version_observed_at": DUX_REQ_03_TIMESTAMP,
                "version_evidence_sha256": req03_pro_sha,
                "prior_unauthenticated_info_status": "AUTHORIZATION_REQUIRED",
                "prior_evidence_timestamp": PRIOR_BASELINE_TIMESTAMP,
                "prior_evidence_sha256": pro_meta_sha,
                "keychain_observer": "UNSET",
                "env_observer": "ABSENT",
                "status": "BLOCKED",
            },
        },
        "summary": {
            "csv_baseline_rows": len(universe_ids) - len(delta_ids),
            "lead_delta_rows": len(delta_ids),
            "union_universe_count": len(universe_ids),
            "total_redis_tagged_rows": len(contract_rows),
            "event_delivery_only_rows_excluded_from_direct_redis": event_delivery_only_count,
            "registered_runtime_rows_count": len(registered_runtime_rows),
            "by_disposition": dict(by_disposition.most_common()),
            "by_test_coverage": dict(by_test_coverage.most_common()),
            "by_phase_source_scope_status": dict(by_scope_status.most_common()),
            "by_phase_ci_actor_identity": dict(by_ci_actor.most_common()),
        },
        "registered_runtime_rows": registered_runtime_rows,
        "rows": contract_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate B02 Redis consumer census ledger")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "redis-consumer-ledger.json",
    )
    parser.add_argument(
        "--inputs",
        choices=INPUT_MODES,
        default="auto",
        help="auto: .agent-receipts when present, else committed fixtures; fixtures: force fixtures",
    )
    args = parser.parse_args(argv)

    inputs = resolve_inputs(args.repo_root, args.inputs)
    ledger = generate_census(args.repo_root, inputs)
    args.output.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "input_source": inputs.source,
                "matrix_projection_sha256": inputs.matrix_projection_sha256,
                "output": str(args.output),
                "output_sha256": sha256_file(args.output),
                "summary": ledger["summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
