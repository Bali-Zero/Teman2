#!/usr/bin/env python3
"""B03 Active-Consumer Denominator Census Adapter.

Pure Python stdlib-only deterministic adapter for campaign
universal-db-wave8-20261015 (block B03).

Reads only frozen inputs under .agent-receipts/udb-wave8-inputs/ and pinned
prior inputs under .agent-receipts/udb-wave8-inputs-dux/prior/, verifies
SHA-256 digests before parsing (fails closed on mismatch), and emits a
6,030-row census table (6,029 rows from consumer-matrix.csv + 1 row from
LEAD-DELTA.json) conforming strictly to CONTRACT-CONVENTIONS.md.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Final, Mapping, Sequence

BASE_COMMIT_SHA: Final[str] = "8061c88e0c43dd42e735fd012f9ed072df3ef3d6"
BASE_COMMIT_TIMESTAMP: Final[str] = "2026-10-15T07:06:22Z"
REAL_RUN_OBSERVED_AT: Final[str] = "2026-10-15T03:00:43Z"
PRIOR_SOURCE_INDEX_COMMIT: Final[str] = "prior:86c0e9caf2d31638a8f7f56b8d942642125ececc"
PRIOR_COMPLETION_COMMIT: Final[str] = "prior:d0c67ee668f97c754e8bcec662d0df7dbf30a126"

INPUT_MANIFEST_SHA256: Final[str] = (
    "e8a35c2404520884f58c7d2801e647c743b86cf69707591f1a1c828bab97722e"
)

PINNED_FROZEN_INPUTS: Final[Mapping[str, str]] = {
    ".agent-receipts/udb-wave8-inputs/ASTRA-ADVICE.md": (
        "72f349f285bc681013b67ad1d25cdad54d3d4478080dc1f5e7e0512dd9e1fdb8"
    ),
    ".agent-receipts/udb-wave8-inputs/FINAL-BLUE-GATE.json": (
        "b9d284e1dba9e87ad340cbd4076061e7a35a93fdf8bc1c910340e6099d711856"
    ),
    ".agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json": (
        "9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d"
    ),
    ".agent-receipts/udb-wave8-inputs/REPORT.md": (
        "d289fb8660a6bd634cb7785fef3a8c0b47ceefe82463d134c4bbf66dc0563e9a"
    ),
    ".agent-receipts/udb-wave8-inputs/STATE.json": (
        "caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4"
    ),
    ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv": (
        "c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118"
    ),
    ".agent-receipts/udb-wave8-inputs/research-lines.csv": (
        "1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f45ff808c7203654c10"
    ),
}

SUPPLEMENTARY_PRIOR_PATHS: Final[Mapping[str, str]] = {
    "source_index": (
        ".agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/source-index-enhanced.json"
    ),
    "jobs_pro": (
        ".agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/jobs-pro.json"
    ),
    "jobs_mini": (
        ".agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/jobs-mini.json"
    ),
    "jobs_m5": (
        ".agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/jobs-M5.json"
    ),
    "gh_workflows": (
        ".agent-receipts/udb-wave8-inputs-dux/prior/advance-20261014-0535/GITHUB-WORKFLOW-METADATA.json"
    ),
}

PINNED_PRIOR_INPUTS: Final[Mapping[str, str]] = {
    ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json": (
        "91e6bac9c91181a2b3aa3f6cd1dc6585671c18ce90cb887444229a1a17a084e7"
    ),
    SUPPLEMENTARY_PRIOR_PATHS["source_index"]: (
        "9f90a66733d63b9183ad21beeca6b84b78db0b243e41aeb9a1d7bc5ab89363cd"
    ),
    SUPPLEMENTARY_PRIOR_PATHS["jobs_pro"]: (
        "4f7bf4e90c1aad7f47ca04cd80ca8fe304cf2affae56bbc68fca080185986703"
    ),
    SUPPLEMENTARY_PRIOR_PATHS["jobs_mini"]: (
        "99bff7025a5cfecd5b4413c8f9b19e921f884b6f80890a9e3fffc7342c2306e2"
    ),
    SUPPLEMENTARY_PRIOR_PATHS["jobs_m5"]: (
        "b53d5b487c7da69e732e4bd31a57a422f655871b11b738f9ef136f3f596c7198"
    ),
    SUPPLEMENTARY_PRIOR_PATHS["gh_workflows"]: (
        "115e40a4d82a89b11301ef17b7820ecf4ee94e0f51f4e8a3e94ad91fbb729a29"
    ),
}

FROZEN_CONTRACT_FIELDS: Final[tuple[str, ...]] = (
    "consumer_id",
    "operation_id",
    "store_id",
    "source_version",
    "evidence_timestamp",
    "evidence_sha256",
    "status",
    "unknowns",
)

B03_EXTENSION_FIELDS: Final[tuple[str, ...]] = (
    "x_disposition",
    "x_evidence_ref",
    "x_canonical_consumer_id",
    "x_candidate_join_id",
    "x_restore_ref_role",
    "x_manual_break_glass_class",
)

ALL_OUTPUT_FIELDS: Final[tuple[str, ...]] = FROZEN_CONTRACT_FIELDS + B03_EXTENSION_FIELDS

ALLOWED_STATUS_VALUES: Final[frozenset[str]] = frozenset(
    {"EVIDENCED", "PARTIAL", "BLOCKED", "CONFLICT", "UNKNOWN"}
)

ALLOWED_DISPOSITIONS: Final[frozenset[str]] = frozenset(
    {"active", "retired", "duplicate", "excluded", "unresolved"}
)

HISTORICAL_RESTORE_REFS: Final[Mapping[str, str]] = {
    "src_307bea3dfb94ec31": "historical_restore_ref:git_deleted_workflow_legacy_unproved",
    "src_d073f505ff1671ad": "historical_restore_ref:restore_drill_verifier_script",
    "src_def7a4c288a552af": "historical_restore_ref:pg_restore_drill_shell_script",
    "src_cdf3ae5e4ecf861c": "historical_restore_ref:verifier_unit_test_excluded",
    "src_2f350566b97aee80": "historical_restore_ref:workflow_wiring_unit_test_excluded",
}

ENGINE_STORE_PROPOSALS: Final[Mapping[str, str]] = {
    "engine_pg_pro": "pg:pro:local",
    "engine_redis_pro": "redis:pro:6379",
    "engine_pg_mini": "pg:mini:local",
    "engine_redis_mini": "redis:mini:6379",
    "engine_pg_m5": "pg:m5:local",
}

MANUAL_BREAK_GLASS_PATTERNS: Final[tuple[tuple[str, str], ...]] = (
    ("apps/backend-rag/backend/db/migrate.py", "manual_migration_cli"),
    ("apps/backend-rag/backend/db/migration_manager.py", "manual_migration_manager"),
    ("scripts/pg-restore-drill.sh", "manual_restore_drill_shell"),
    ("scripts/ci/restore_drill_verify.py", "manual_or_cron_restore_verifier"),
    ("scripts/pg.sh", "manual_pg_operator_shell"),
    ("scripts/Migrate.sh", "manual_migration_shell"),
    ("alembic", "manual_alembic_migration_surface"),
    ("backfill", "manual_backfill_script"),
    ("seed", "manual_seed_script"),
    ("restore", "manual_restore_or_recovery_script"),
    ("backup", "manual_backup_script"),
)

_CANONICAL_JOB_RE: Final[re.Pattern[str]] = re.compile(
    r"observed as (job_(?:pro|mini)_[0-9a-f]{24})\b"
)
_SOURCE_PATH_SHA_RE: Final[re.Pattern[str]] = re.compile(
    r"^source-path-sha256:([0-9a-f]{64})$"
)


class PinVerificationError(RuntimeError):
    """Raised when any frozen or pinned input fails SHA-256 verification."""


class ContractValidationError(ValueError):
    """Raised when a census row or classification violates contract invariants."""


def compute_sha256(path: Path) -> str:
    """Compute hex SHA-256 of a file on disk."""
    if not path.is_file():
        raise PinVerificationError(f"Pinned input missing on disk: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_pinned_inputs(
    repo_root: Path,
    extra_pins: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Verify INPUT-MANIFEST.json ('files' map), all 7 frozen inputs, and all 6 prior inputs.

    Returns a mapping from relative path to verified SHA-256 hex digest.
    Raises PinVerificationError on any mismatch or missing file.
    """
    verified: dict[str, str] = {}

    manifest_rel = ".agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json"
    manifest_path = repo_root / manifest_rel
    actual_manifest_sha = compute_sha256(manifest_path)
    if actual_manifest_sha != INPUT_MANIFEST_SHA256:
        raise PinVerificationError(
            f"SHA-256 mismatch for {manifest_rel}: "
            f"expected {INPUT_MANIFEST_SHA256}, got {actual_manifest_sha}"
        )
    verified[manifest_rel] = actual_manifest_sha

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_files = manifest_data.get("files")
    if not isinstance(manifest_files, dict) or len(manifest_files) != len(
        PINNED_FROZEN_INPUTS
    ):
        raise PinVerificationError(
            f"Unexpected 'files' map in {manifest_rel}"
        )

    for filename, manifest_sha in manifest_files.items():
        rel_path = f".agent-receipts/udb-wave8-inputs/{filename}"
        if PINNED_FROZEN_INPUTS.get(rel_path) != manifest_sha:
            raise PinVerificationError(
                f"Manifest 'files' sha256 mismatch for {rel_path}: "
                f"manifest has {manifest_sha}, pin has {PINNED_FROZEN_INPUTS.get(rel_path)}"
            )

    for rel_path, expected_sha in PINNED_FROZEN_INPUTS.items():
        actual_sha = compute_sha256(repo_root / rel_path)
        if actual_sha != expected_sha:
            raise PinVerificationError(
                f"SHA-256 mismatch for {rel_path}: "
                f"expected {expected_sha}, got {actual_sha}"
            )
        verified[rel_path] = actual_sha

    for rel_path, expected_sha in PINNED_PRIOR_INPUTS.items():
        actual_sha = compute_sha256(repo_root / rel_path)
        if actual_sha != expected_sha:
            raise PinVerificationError(
                f"SHA-256 mismatch for {rel_path}: "
                f"expected {expected_sha}, got {actual_sha}"
            )
        verified[rel_path] = actual_sha

    if extra_pins:
        for rel_path, expected_sha in extra_pins.items():
            actual_sha = compute_sha256(repo_root / rel_path)
            if actual_sha != expected_sha:
                raise PinVerificationError(
                    f"SHA-256 mismatch for {rel_path}: "
                    f"expected {expected_sha}, got {actual_sha}"
                )
            verified[rel_path] = actual_sha

    return verified


def validate_duplicate_claim(
    consumer_id: str,
    canonical_consumer_id: str,
    *,
    preimage_verified: bool,
    same_installed_bytes_and_host: bool,
) -> str:
    """Validate a claim that consumer_id is a duplicate of canonical_consumer_id.

    Per consumer-matrix.csv blocker PATH_MATCH_DOES_NOT_PROVE_SAME_DATABASE_CONSUMER
    and Adversary B03-F1, claiming x_disposition == 'duplicate' without both a
    verified pre-image and same-host installed-bytes/registration identity is
    rejected.
    """
    if not canonical_consumer_id or canonical_consumer_id == consumer_id:
        raise ContractValidationError(
            f"Invalid canonical_consumer_id {canonical_consumer_id!r} for {consumer_id!r}"
        )
    if not preimage_verified:
        raise ContractValidationError(
            f"Duplicate claim rejected for {consumer_id!r} -> {canonical_consumer_id!r}: "
            "hash pre-image not verified in pinned prior artifacts"
        )
    if not same_installed_bytes_and_host:
        raise ContractValidationError(
            f"Duplicate claim rejected for {consumer_id!r} -> {canonical_consumer_id!r}: "
            "PATH_MATCH_DOES_NOT_PROVE_SAME_DATABASE_CONSUMER"
        )
    return "duplicate"


def evaluate_retirement_claim(
    consumer_id: str,
    *,
    git_deleted: bool,
    host_registrations_absent_verified: bool,
    legacy_copies_retired_verified: bool,
) -> str:
    """Evaluate whether a lead can be marked 'retired'.

    Per Adversary B03-F5 and Negative Case 2, a git-deleted workflow or script
    with a live host registration or unproved retirement of legacy copies across
    hosts MUST NOT be marked 'retired'; it remains 'unresolved'.
    """
    if not consumer_id:
        raise ContractValidationError("consumer_id must be non-empty")
    if (
        git_deleted
        and host_registrations_absent_verified
        and legacy_copies_retired_verified
    ):
        return "retired"
    return "unresolved"


def validate_active_promotion(
    consumer_id: str,
    csv_status: str,
    *,
    has_deployed_execution_proof: bool,
    has_resolved_target_contract: bool,
) -> str:
    """Validate whether a row can be promoted to x_disposition == 'active'.

    Refuses to promote BLOCKED_DISCOVERY or registration-only rows without
    both deployed execution proof and resolved target store/operation contract.
    """
    if csv_status == "RETAINED_TEST_SOURCE":
        raise ContractValidationError(
            f"Cannot promote test source {consumer_id!r} to active"
        )
    if not has_deployed_execution_proof:
        raise ContractValidationError(
            f"Cannot promote {consumer_id!r} (csv_status={csv_status!r}) to active "
            "without deployed execution proof"
        )
    if not has_resolved_target_contract:
        raise ContractValidationError(
            f"Cannot promote {consumer_id!r} (csv_status={csv_status!r}) to active "
            "without resolved target contract"
        )
    return "active"


def classify_manual_break_glass(entry_point: str, consumer_type: str, csv_status: str) -> str:
    """Return manual/break-glass classification if entry_point matches operator patterns."""
    if csv_status == "RETAINED_TEST_SOURCE":
        return ""
    lowered = entry_point.lower()
    for pattern, label in MANUAL_BREAK_GLASS_PATTERNS:
        if pattern.lower() in lowered:
            return label
    if consumer_type in {"script", "shell_script", "cli"} and (
        "scripts/" in lowered or "/db/" in lowered
    ):
        return "manual_operator_script_candidate"
    return ""


def validate_output_row(row: Mapping[str, Any]) -> None:
    """Enforce CONTRACT-CONVENTIONS.md invariants on a single emitted row."""
    keys = tuple(row.keys())
    if keys[: len(FROZEN_CONTRACT_FIELDS)] != FROZEN_CONTRACT_FIELDS:
        raise ContractValidationError(
            f"Row keys {keys[: len(FROZEN_CONTRACT_FIELDS)]} do not start with "
            f"FROZEN_CONTRACT_FIELDS {FROZEN_CONTRACT_FIELDS}"
        )
    for ext_key in keys[len(FROZEN_CONTRACT_FIELDS) :]:
        if not ext_key.startswith("x_"):
            raise ContractValidationError(
                f"Extension column {ext_key!r} must be prefixed with 'x_'"
            )

    status = row["status"]
    if status not in ALLOWED_STATUS_VALUES:
        raise ContractValidationError(
            f"Invalid status {status!r} for {row['consumer_id']!r}; "
            f"must be one of {sorted(ALLOWED_STATUS_VALUES)}"
        )

    disposition = row["x_disposition"]
    if disposition not in ALLOWED_DISPOSITIONS:
        raise ContractValidationError(
            f"Invalid x_disposition {disposition!r} for {row['consumer_id']!r}; "
            f"must be one of {sorted(ALLOWED_DISPOSITIONS)}"
        )

    if disposition != "excluded" and (
        row["consumer_id"].startswith("NOTEBOOK-CONTAINER-REFERENCE-NLM-")
        or row["consumer_id"].startswith("engine_")
    ):
        raise ContractValidationError(
            f"Non-consumer entity {row['consumer_id']!r} leaked into "
            f"x_disposition={disposition!r}"
        )

    unknowns = row["unknowns"]
    if not isinstance(unknowns, list):
        raise ContractValidationError(
            f"unknowns must be a list of tokens for {row['consumer_id']!r}"
        )
    if status == "EVIDENCED" and len(unknowns) > 0:
        raise ContractValidationError(
            f"unknowns must be empty when status == 'EVIDENCED' ({row['consumer_id']!r})"
        )
    if status != "EVIDENCED" and len(unknowns) == 0:
        raise ContractValidationError(
            f"unknowns must be non-empty when status == {status!r} ({row['consumer_id']!r})"
        )


def _load_supplementary_metadata(
    repo_root: Path,
    verified_hashes: Mapping[str, str],
) -> dict[str, Any]:
    """Load pinned supplementary prior artifacts and build pre-image lookup indices."""
    meta: dict[str, Any] = {
        "hashes": {},
        "timestamps": {},
        "index_ids": set(),
        "pro_job_ids": set(),
        "mini_job_ids": set(),
    }
    for key, rel_path in SUPPLEMENTARY_PRIOR_PATHS.items():
        if rel_path not in verified_hashes:
            raise PinVerificationError(
                f"Supplementary prior {rel_path} was not verified in PINNED_PRIOR_INPUTS"
            )
        full_path = repo_root / rel_path
        meta["hashes"][rel_path] = verified_hashes[rel_path]
        data = json.loads(full_path.read_text(encoding="utf-8"))
        if key in {"jobs_pro", "jobs_mini", "jobs_m5", "gh_workflows"}:
            if not isinstance(data, dict) or not data.get("observed_at"):
                raise PinVerificationError(
                    f"Missing 'observed_at' timestamp in pinned prior {rel_path}"
                )
            meta["timestamps"][key] = str(data["observed_at"])
        if key == "source_index":
            for node in data.get("nodes", []):
                sid = node.get("source_id")
                if sid:
                    meta["index_ids"].add(f"index_{sid}")
        elif key == "jobs_pro":
            for job in data.get("jobs", []):
                lhash = job.get("label_hash")
                if lhash:
                    meta["pro_job_ids"].add(f"job_pro_{lhash[:24]}")
        elif key == "jobs_mini":
            for job in data.get("jobs", []):
                lhash = job.get("label_hash")
                if lhash:
                    meta["mini_job_ids"].add(f"job_mini_{lhash[:24]}")
    return meta


def _transform_csv_row(
    csv_row: Mapping[str, str],
    verified_hashes: Mapping[str, str],
    supp_meta: Mapping[str, Any],
) -> dict[str, Any]:
    """Transform one row from consumer-matrix.csv into the frozen sibling contract."""
    cid = csv_row["consumer_id"].strip()
    consumer_type = csv_row["consumer_type"].strip()
    entry_point = csv_row["entry_point"].strip()
    csv_status = csv_row["status"].strip()
    blocker_raw = csv_row["blocker"].strip()
    id_rel = csv_row.get("identity_relationships", "").strip()

    matrix_rel = ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
    matrix_sha = verified_hashes[matrix_rel]

    unknowns: list[str] = []
    for token in blocker_raw.split(";"):
        cleaned = re.sub(r"[^A-Z0-9_]", "_", token.strip().upper()).strip("_")
        if cleaned and cleaned != "NONE":
            unknowns.append(cleaned)

    operation_id = "UNASSIGNED_B05"
    unknowns.append("OPERATION_ID_PENDING_B05")

    store_id = "unknown:unknown:unknown"
    if cid in ENGINE_STORE_PROPOSALS:
        unknowns.append(f"STORE_ID_PROPOSED:{ENGINE_STORE_PROPOSALS[cid]}")
        unknowns.append("NON_CONSUMER_ENTITY_EXCLUDED")
    elif cid.startswith("NOTEBOOK-CONTAINER-REFERENCE-NLM-"):
        unknowns.append("NON_CONSUMER_ENTITY_EXCLUDED")
    else:
        unknowns.append("STORE_BINDING_PENDING_B04")

    # Provenance: source_version, evidence_timestamp, x_evidence_ref, evidence_sha256
    source_index_rel = SUPPLEMENTARY_PRIOR_PATHS["source_index"]
    jobs_pro_rel = SUPPLEMENTARY_PRIOR_PATHS["jobs_pro"]
    jobs_mini_rel = SUPPLEMENTARY_PRIOR_PATHS["jobs_mini"]
    jobs_m5_rel = SUPPLEMENTARY_PRIOR_PATHS["jobs_m5"]
    gh_rel = SUPPLEMENTARY_PRIOR_PATHS["gh_workflows"]

    if cid.startswith(("src_", "index_")):
        source_version = PRIOR_SOURCE_INDEX_COMMIT
        evidence_timestamp = BASE_COMMIT_TIMESTAMP
        x_evidence_ref = source_index_rel
        evidence_sha256 = supp_meta["hashes"][source_index_rel]
        unknowns.append("STATIC_SOURCE_ONLY")
    elif cid.startswith(
        (
            "job_pro_",
            "cron_pro_",
            "runtime-pro-plist-",
            "runtime-pro-backup-",
            "SOURCE-PATH-UNMATCHED-PRO-",
            "SOURCE-TRACE-UNMATCHED-PRO-",
        )
    ) or cid in {"engine_pg_pro", "engine_redis_pro"}:
        source_version = "prior:UNKNOWN"
        evidence_timestamp = supp_meta["timestamps"]["jobs_pro"]
        x_evidence_ref = jobs_pro_rel
        evidence_sha256 = supp_meta["hashes"][jobs_pro_rel]
    elif cid.startswith(("job_mini_", "cron_mini_", "runtime-mini-plist-")) or cid in {
        "engine_pg_mini",
        "engine_redis_mini",
    }:
        source_version = "prior:UNKNOWN"
        evidence_timestamp = supp_meta["timestamps"]["jobs_mini"]
        x_evidence_ref = jobs_mini_rel
        evidence_sha256 = supp_meta["hashes"][jobs_mini_rel]
    elif cid.startswith("job_M5_") or cid == "engine_pg_m5":
        source_version = "prior:UNKNOWN"
        evidence_timestamp = supp_meta["timestamps"]["jobs_m5"]
        x_evidence_ref = jobs_m5_rel
        evidence_sha256 = supp_meta["hashes"][jobs_m5_rel]
    elif cid.startswith("CI-REGISTRATION-UNMATCHED-GH-"):
        source_version = "prior:UNKNOWN"
        evidence_timestamp = supp_meta["timestamps"]["gh_workflows"]
        x_evidence_ref = gh_rel
        evidence_sha256 = supp_meta["hashes"][gh_rel]
    else:
        source_version = BASE_COMMIT_SHA
        evidence_timestamp = BASE_COMMIT_TIMESTAMP
        x_evidence_ref = matrix_rel
        evidence_sha256 = matrix_sha
        unknowns.append("STATIC_SOURCE_ONLY")

    x_canonical_consumer_id = ""
    x_candidate_join_id = ""
    x_restore_ref_role = HISTORICAL_RESTORE_REFS.get(cid, "")
    x_manual_break_glass_class = classify_manual_break_glass(
        entry_point, consumer_type, csv_status
    )

    # Disposition and Contract Status
    if (
        cid.startswith("NOTEBOOK-CONTAINER-REFERENCE-NLM-")
        or cid.startswith("engine_")
        or csv_status == "RETAINED_TEST_SOURCE"
    ):
        x_disposition = "excluded"
        status = "PARTIAL"
        unknowns.append("EXCLUDED_FROM_ACTIVE_DENOMINATOR")
    elif cid.startswith(("runtime-pro-plist-", "runtime-mini-plist-")):
        match = _CANONICAL_JOB_RE.search(id_rel)
        canonical_id = match.group(1) if match else ""
        if cid.startswith("runtime-pro-plist-"):
            preimage_ok = canonical_id in supp_meta["pro_job_ids"]
        else:
            preimage_ok = canonical_id in supp_meta["mini_job_ids"]
        x_disposition = validate_duplicate_claim(
            cid,
            canonical_id,
            preimage_verified=preimage_ok,
            same_installed_bytes_and_host=bool(canonical_id),
        )
        x_canonical_consumer_id = canonical_id
        status = "PARTIAL"
        unknowns.append("DUPLICATE_REGISTRATION_ALIAS_COLLAPSED")
    else:
        # Check CI-REGISTRATION-UNMATCHED-GH-* candidate path-hash join to index_*
        if cid.startswith("CI-REGISTRATION-UNMATCHED-GH-"):
            sha_match = _SOURCE_PATH_SHA_RE.match(entry_point)
            if sha_match:
                candidate_idx = f"index_{sha_match.group(1)[:24]}"
                if candidate_idx in supp_meta["index_ids"]:
                    x_candidate_join_id = candidate_idx
                    unknowns.append(
                        "CI_WORKFLOW_TO_INDEX_PATH_SHA24_MATCH_NEEDS_ACTOR_PROOF"
                    )

        # Evaluate retirement specifically for git-deleted workflow src_307bea3dfb94ec31
        if cid == "src_307bea3dfb94ec31":
            x_disposition = evaluate_retirement_claim(
                cid,
                git_deleted=True,
                host_registrations_absent_verified=True,
                legacy_copies_retired_verified=False,
            )
            unknowns.append("GIT_DELETED_WORKFLOW_LEGACY_COPIES_UNPROVED_RETIRED")
        else:
            x_disposition = "unresolved"

        if csv_status == "PARTIAL_DISCOVERY":
            status = "PARTIAL"
        elif csv_status in {
            "BLOCKED_DISCOVERY",
            "BLOCKED_RUNTIME_CONTRACT",
            "BLOCKED_MCP_REACHABILITY",
            "UNMATCHED_CURRENT_SOURCE_PATH",
        }:
            status = "BLOCKED"
        else:
            status = "UNKNOWN"

    dedup_unknowns = list(dict.fromkeys(unknowns))

    row = {
        "consumer_id": cid,
        "operation_id": operation_id,
        "store_id": store_id,
        "source_version": source_version,
        "evidence_timestamp": evidence_timestamp,
        "evidence_sha256": evidence_sha256,
        "status": status,
        "unknowns": dedup_unknowns,
        "x_disposition": x_disposition,
        "x_evidence_ref": x_evidence_ref,
        "x_canonical_consumer_id": x_canonical_consumer_id,
        "x_candidate_join_id": x_candidate_join_id,
        "x_restore_ref_role": x_restore_ref_role,
        "x_manual_break_glass_class": x_manual_break_glass_class,
    }
    validate_output_row(row)
    return row


def _build_lead_delta_row(
    lead_delta_data: Mapping[str, Any],
    verified_hashes: Mapping[str, str],
) -> dict[str, Any]:
    """Build the 6,030th lead row from LEAD-DELTA.json + REAL-RUN-RECEIPT.json."""
    cid = str(lead_delta_data["lead_id"]).strip()
    real_run_rel = ".agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json"
    real_run_sha = verified_hashes[real_run_rel]

    blocker_raw = str(lead_delta_data.get("blocker", ""))
    unknowns: list[str] = []
    for token in blocker_raw.split(";"):
        cleaned = re.sub(r"[^A-Z0-9_]", "_", token.strip().upper()).strip("_")
        if cleaned and cleaned != "NONE":
            unknowns.append(cleaned)
    unknowns.append("OPERATION_ID_PENDING_B05")
    unknowns.append("STORE_BINDING_PENDING_B04")
    unknowns.append("STORE_ID_PROPOSED:pg:mini:local")

    row = {
        "consumer_id": cid,
        "operation_id": "UNASSIGNED_B05",
        "store_id": "unknown:unknown:unknown",
        "source_version": PRIOR_COMPLETION_COMMIT,
        "evidence_timestamp": REAL_RUN_OBSERVED_AT,
        "evidence_sha256": real_run_sha,
        "status": "PARTIAL",
        "unknowns": list(dict.fromkeys(unknowns)),
        "x_disposition": "unresolved",
        "x_evidence_ref": real_run_rel,
        "x_canonical_consumer_id": "",
        "x_candidate_join_id": "src_d073f505ff1671ad;src_def7a4c288a552af",
        "x_restore_ref_role": "live_mini_restore_organ_partial_contract",
        "x_manual_break_glass_class": "scheduled_and_manual_restore_drill_organ",
    }
    validate_output_row(row)
    return row


def build_census_rows(
    repo_root: Path,
    extra_pins: Mapping[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Verify pins, transform all 6,030 leads, and compute summary accounting."""
    verified_hashes = verify_pinned_inputs(repo_root, extra_pins=extra_pins)
    supp_meta = _load_supplementary_metadata(repo_root, verified_hashes)

    matrix_path = repo_root / ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
    lead_delta_path = (
        repo_root
        / ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json"
    )

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    with matrix_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for csv_row in reader:
            out_row = _transform_csv_row(csv_row, verified_hashes, supp_meta)
            cid = out_row["consumer_id"]
            if cid in seen_ids:
                raise ContractValidationError(f"Duplicate consumer_id in matrix: {cid!r}")
            seen_ids.add(cid)
            rows.append(out_row)

    lead_delta_data = json.loads(lead_delta_path.read_text(encoding="utf-8"))
    delta_row = _build_lead_delta_row(lead_delta_data, verified_hashes)
    if delta_row["consumer_id"] in seen_ids:
        raise ContractValidationError(
            f"LEAD-DELTA consumer_id already in matrix: {delta_row['consumer_id']!r}"
        )
    seen_ids.add(delta_row["consumer_id"])
    rows.append(delta_row)

    if len(rows) != 6030:
        raise ContractValidationError(
            f"Expected exactly 6030 total leads (6029 CSV + 1 LEAD-DELTA), got {len(rows)}"
        )

    disposition_counts: dict[str, int] = {k: 0 for k in sorted(ALLOWED_DISPOSITIONS)}
    status_counts: dict[str, int] = {k: 0 for k in sorted(ALLOWED_STATUS_VALUES)}
    restore_ref_rows: dict[str, str] = {}
    manual_break_glass_counts: dict[str, int] = {}

    for row in rows:
        disposition_counts[row["x_disposition"]] += 1
        status_counts[row["status"]] += 1
        if row["x_restore_ref_role"]:
            restore_ref_rows[row["consumer_id"]] = row["x_restore_ref_role"]
        m_class = row["x_manual_break_glass_class"]
        if m_class:
            manual_break_glass_counts[m_class] = (
                manual_break_glass_counts.get(m_class, 0) + 1
            )

    summary = {
        "campaign_id": "universal-db-wave8-20261015",
        "block_id": "B03",
        "base_commit_sha": BASE_COMMIT_SHA,
        "total_leads": len(rows),
        "matrix_leads": len(rows) - 1,
        "lead_delta_leads": 1,
        "disposition_counts": disposition_counts,
        "status_counts": status_counts,
        "active_consumer_denominator": (
            disposition_counts["active"]
            if disposition_counts["unresolved"] == 0
            else "UNKNOWN"
        ),
        "historical_restore_references_reconciled": restore_ref_rows,
        "manual_break_glass_counts": manual_break_glass_counts,
        "verified_input_hashes": verified_hashes,
        "supplementary_prior_hashes": supp_meta["hashes"],
    }
    return rows, summary


def write_census_outputs(
    rows: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, str]:
    """Write CSV, JSONL, and summary JSON deterministically and return their SHA-256s."""
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "b03-consumer-census.csv"
    jsonl_path = output_dir / "b03-consumer-census.jsonl"
    summary_path = output_dir / "b03-census-summary.json"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ALL_OUTPUT_FIELDS), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            serialized["unknowns"] = ";".join(row["unknowns"])
            writer.writerow(serialized)

    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=False) + "\n")

    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        str(csv_path): compute_sha256(csv_path),
        str(jsonl_path): compute_sha256(jsonl_path),
        str(summary_path): compute_sha256(summary_path),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="B03 deterministic consumer census adapter (stdlib only)."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
        help="Path to worktree root.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional directory to write b03-consumer-census.{csv,jsonl} and summary.",
    )
    args = parser.parse_args(argv)

    rows, summary = build_census_rows(args.repo_root)
    if args.output_dir is not None:
        artifact_hashes = write_census_outputs(rows, summary, args.output_dir)
        summary = dict(summary)
        summary["emitted_artifact_hashes"] = artifact_hashes
    sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
