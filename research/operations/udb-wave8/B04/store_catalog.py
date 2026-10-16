"""Deterministic, read-only Physical Store Catalog & Binding Adapter for Block B04.

Campaign: universal-db-wave8-20261015
Block: B04 (Physical stores and connections)
Base commit: 8061c88e0c43dd42e735fd012f9ed072df3ef3d6

Strictly adheres to:
- research/operations/udb-wave8/B04/DUX-NOTE-CORRECTION.md
- .agent-receipts/udb-wave8-dux/CONTRACT-CONVENTIONS.md
- .agent-receipts/udb-wave8-dux/DUX-CONSOLIDATION.md
- .agent-receipts/udb-wave8-dux/DUX-SCOPE-CORRECTION.md
- .agent-receipts/udb-wave8-dux/ADVERSARY-FINDINGS.md

Pure Python 3.11+ stdlib only. Zero application runtime imports, zero network/socket/DB
connections, and fail-closed SHA-256 verification on all pinned inputs.

The `.agent-receipts/` inputs are gitignored. When no campaign receipt directory exists the
adapter reads the committed `fixtures/` instead (see `fixtures/PROVENANCE.json`): byte-identical
copies are checked against the same pins, projected or digest-only inputs by a separate
projected-identity check that never claims the source's bytes.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASE_COMMIT: str = "8061c88e0c43dd42e735fd012f9ed072df3ef3d6"
BASE_COMMIT_TIMESTAMP: str = "2026-10-15T07:06:22Z"
FROZEN_BASELINE_TIMESTAMP: str = "2026-10-15T03:28:29.868658Z"
LIVE_DB_METADATA_TIMESTAMP: str = "2026-10-15T00:53:34.907490Z"
POOL_FACTORY_SOURCE_VERSION: str = "prior:2bf9ed3c93"
POOL_FACTORY_TIMESTAMP: str = "2026-10-13T11:04:22.578497Z"
PRIOR_UNKNOWN_VERSION: str = "prior:UNKNOWN"
DUX_B04_01_TIMESTAMP: str = "2026-10-15T08:45:41.557196Z"
DUX_B04_02_TIMESTAMP: str = "2026-10-15T08:45:28.257193Z"
DUX_B04_06_TIMESTAMP: str = "2026-10-15T08:45:28.333779Z"

BINDING_COLUMNS: tuple[str, ...] = (
    "consumer_id",
    "operation_id",
    "store_id",
    "source_version",
    "evidence_timestamp",
    "evidence_sha256",
    "status",
    "unknowns",
)

ALLOWED_STATUSES: frozenset[str] = frozenset(
    {"EVIDENCED", "PARTIAL", "BLOCKED", "CONFLICT", "UNKNOWN"}
)

ALLOWED_ENGINES: frozenset[str] = frozenset(
    {
        "pg",
        "qdrant",
        "redis",
        "sqlite",
        "graph",
        "object",
        "file",
        "sheet",
        "browser",
        "external",
    }
)

ALLOWED_PLATFORMS: frozenset[str] = frozenset(
    {
        "fly",
        "pro",
        "mini",
        "m5",
        "gcloud",
        "gdrive",
        "github",
        "client",
        "unknown",
    }
)

STORE_ID_SENTINEL: str = "unknown:unknown:unknown"
OPERATION_ID_SENTINEL: str = "UNASSIGNED_B05"
OPERATION_ID_PENDING_TOKEN: str = "OPERATION_ID_PENDING_B05"
NOTEBOOK_CONTAINER_STORE_MARKER: str = (
    "NOTEBOOK_CONTAINER_REFERENCE; NOT_DATABASE_CONSUMER_IDENTITY"
)

SHA256_HEX_REGEX: re.Pattern[str] = re.compile(r"^[0-9a-f]{64}$")
SHA256_PREFIX_REGEX: re.Pattern[str] = re.compile(r"^[0-9a-f]{8,64}$")

STORE_ID_REGEX: re.Pattern[str] = re.compile(
    r"^(?:unknown:unknown:unknown|"
    r"(pg|qdrant|redis|sqlite|graph|object|file|sheet|browser|external):"
    r"(fly|pro|mini|m5|gcloud|gdrive|github|client|unknown):"
    r"([a-z0-9][a-z0-9._-]*)"
    r"(?:/([a-zA-Z0-9._/-]+))?)$"
)

FABRICATED_CONSUMER_IDS: frozenset[str] = frozenset(
    {
        "repo_0e2c9f158a76731f",
        "repo_5d54fa59301e6b3f",
        "repo_e4964f782237c1df",
    }
)

PINNED_INPUT_MANIFEST_HASHES: dict[str, str] = {
    "REPORT.md": "d289fb8660a6bd634cb7785fef3a8c0b47ceefe82463d134c4bbf66dc0563e9a",
    "STATE.json": "caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4",
    "FINAL-BLUE-GATE.json": "b9d284e1dba9e87ad340cbd4076061e7a35a93fdf8bc1c910340e6099d711856",
    "REAL-RUN-RECEIPT.json": "9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d",
    "research-lines.csv": "1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f45ff808c7203654c10",
    "consumer-matrix.csv": "c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118",
    "ASTRA-ADVICE.md": "72f349f285bc681013b67ad1d25cdad54d3d4478080dc1f5e7e0512dd9e1fdb8",
}

PINNED_DUX_DOC_HASHES: dict[str, str] = {
    ".agent-receipts/udb-wave8-dux/ADVERSARY-FINDINGS.md": (
        "29c57f706bcc0dd8e7f492f3ffe5215598798ed173f452f19aa7a086c8faaf54"
    ),
    ".agent-receipts/udb-wave8-dux/CONTRACT-CONVENTIONS.md": (
        "a7feea89fa64000d76c18a52d705dd008b4a6336a6d58af98c2618a13048c559"
    ),
    ".agent-receipts/udb-wave8-dux/DUX-CONSOLIDATION.md": (
        "c39218718f496b643b550abf98ca40bd2755e74d3954caed953005eb5b906e14"
    ),
    ".agent-receipts/udb-wave8-dux/DUX-SCOPE-CORRECTION.md": (
        "440edee150a91dbe49468de768b11aec3b07366a462f0abebd5eb2b8e53afac5"
    ),
}

PINNED_SOURCE_FILE_HASHES: dict[str, str] = {
    "apps/backend-rag/backend/core/collection_registry.py": (
        "e3fa7082b36e52f2099be36eab013c6c7b02a4175c1a125a38be5b494add4abf"
    ),
    "apps/backend-rag/backend/core/embeddings.py": (
        "fd6b78142b20ae1b6eba8567c18af2852c293b57280e95533e9ec13f5f73f358"
    ),
    "apps/backend-rag/backend/core/qdrant_db.py": (
        "5b67c71400cbb38154f32c7f85ddf6b1fa8ec24e5d54c4c05de84fa4ceac400e"
    ),
    "apps/backend-rag/backend/core/redis_manager.py": (
        "5b8640c2eae6dec947b57dd043a769ee4dd8d10c690a9605504e0c9276202840"
    ),
    "apps/backend-rag/backend/app/core/config.py": (
        "1e103424bc2cba0bfb1a432c6ca43ee581d41ab182507a6c1740c3bd30092f3e"
    ),
    "apps/backend-rag/backend/app/core/database.py": (
        "b4c8d3b606e7d8eac8795c9a9fe08595a8d2fd1b8d0be4e405d304490c8163bf"
    ),
    "apps/backend-rag/backend/app/setup/service_initializer.py": (
        "6b02f424902a7d791713a81e52fc44e30a49201f263616bf36a0f71db25f0f09"
    ),
    "apps/backend-rag/backend/services/ingestion/collection_manager.py": (
        "16ef3e7bd869e4f47db715f84f3552ad4c0015d6e877cd7605de2fa83030e39a"
    ),
    "apps/backend-rag/backend/services/misc/graph_service.py": (
        "ae2e7a536b5bb64643b6122050663056d51a9a72816531e238cf86b1522e9283"
    ),
    "apps/wa-mirror/bridge/pg.ts": (
        "baa7b55798c0e909623dce0c7629baada04a3a34ebaaff2ac8dcc3d9882e865b"
    ),
    "apps/admin-dashboard-local/app/lib/db.ts": (
        "826a41c8e532f3d2ce267b25c34c208d203b6d669fb4b4033cdce82cb9bc0919"
    ),
    "apps/remediator/main.py": (
        "fdad97917a049906f7a75d75e8d8d242924beb9eb3ac6a06b1295c021bf09f67"
    ),
}

PINNED_PRIOR_SHA256_PREFIXES: dict[str, str] = {
    ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/QDRANT-METADATA.json": (
        "af100a6d"
    ),
    ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LIVE-DB-METADATA.json": (
        "2bb691c3"
    ),
    ".agent-receipts/udb-wave8-inputs-dux/prior/advance-20261013-1640/POOL-FACTORY-SOURCE.json": (
        "d93668cb"
    ),
}

# Hermetic fallback: the campaign receipts under `.agent-receipts/` are gitignored, so a
# clean checkout carries them only as the committed fixtures below. The fixtures are FROZEN
# METADATA TEST FIXTURES, not new native observations. Whenever a campaign receipt directory
# exists the adapter reads the receipts exactly as before and never consults a fixture.
RECEIPTS_PREFIX: str = ".agent-receipts/"
CAMPAIGN_RECEIPT_DIRS: tuple[str, ...] = (
    ".agent-receipts/udb-wave8-inputs",
    ".agent-receipts/udb-wave8-dux",
    ".agent-receipts/udb-wave8-inputs-dux",
)
FIXTURE_DIR_REL: str = "research/operations/udb-wave8/B04/fixtures"
FIXTURE_PROVENANCE_NAME: str = "PROVENANCE.json"
FIXTURE_KIND: str = "FROZEN_METADATA_TEST_FIXTURES_NOT_NEW_NATIVE_OBSERVATIONS"
FIXTURE_SCHEMA: str = "udb-wave8-b04-fixtures-v1"
IDENTITY_BYTE_IDENTICAL: str = "BYTE_IDENTICAL_COPY"
IDENTITY_PROJECTION: str = "PROJECTION"
IDENTITY_DIGEST_ONLY: str = "DIGEST_ONLY"
IDENTITY_SOURCE_BYTES: str = "SOURCE_BYTES"
# Pins the committed fixtures/PROVENANCE.json, which in turn records the sha256 of every
# carried fixture and the full source sha256 of every digest-only or projected input.
PINNED_FIXTURE_PROVENANCE_SHA256: str = (
    "645b1732a7e25a3e24ad284ae31420eb72bbeec072db4f4745e28b27b4753ae8"
)

LOCAL_USER_HOME_PLACEHOLDER: str = "{LOCAL_USER_HOME}"
LOCAL_USER_PATH_REGEX: re.Pattern[str] = re.compile(r"/Users/[A-Za-z0-9._-]+")
CONSUMER_MATRIX_PROJECTED_COLUMNS: tuple[str, ...] = (
    "consumer_id",
    "entry_point",
    "store",
    "disposition",
)
LIVE_DB_SUMMARY_PROJECTED_KEYS: tuple[str, ...] = (
    "actors",
    "foreign_keys",
    "functions",
    "grant_pairs",
    "relations",
    "triggers",
)

_INPUTS = ".agent-receipts/udb-wave8-inputs/"
_DUX = ".agent-receipts/udb-wave8-dux/"
_COMPLETION = ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/"
_ADVANCE = ".agent-receipts/udb-wave8-inputs-dux/prior/advance-20261013-1640/"

# (source rel path, identity, fixture rel path under FIXTURE_DIR_REL or None, consumed as)
_PIN_ONLY = "pinned digest check only; content never read"
_NO_CONTENT = "digest only; content never read"
HERMETIC_FIXTURE_PLAN: tuple[tuple[str, str, str | None, str], ...] = (
    (
        _INPUTS + "INPUT-MANIFEST.json",
        IDENTITY_BYTE_IDENTICAL,
        "udb-wave8-inputs/INPUT-MANIFEST.json",
        "cross-checked against the seven pinned input digests",
    ),
    (
        _INPUTS + "REPORT.md",
        IDENTITY_DIGEST_ONLY,
        None,
        _PIN_ONLY,
    ),
    (
        _INPUTS + "STATE.json",
        IDENTITY_BYTE_IDENTICAL,
        "udb-wave8-inputs/STATE.json",
        _PIN_ONLY,
    ),
    (
        _INPUTS + "FINAL-BLUE-GATE.json",
        IDENTITY_BYTE_IDENTICAL,
        "udb-wave8-inputs/FINAL-BLUE-GATE.json",
        _PIN_ONLY,
    ),
    (
        _INPUTS + "REAL-RUN-RECEIPT.json",
        IDENTITY_BYTE_IDENTICAL,
        "udb-wave8-inputs/REAL-RUN-RECEIPT.json",
        _PIN_ONLY,
    ),
    (
        _INPUTS + "research-lines.csv",
        IDENTITY_BYTE_IDENTICAL,
        "udb-wave8-inputs/research-lines.csv",
        _PIN_ONLY,
    ),
    (
        _INPUTS + "ASTRA-ADVICE.md",
        IDENTITY_DIGEST_ONLY,
        None,
        _PIN_ONLY,
    ),
    (
        _INPUTS + "consumer-matrix.csv",
        IDENTITY_PROJECTION,
        "udb-wave8-inputs/consumer-matrix.projection.csv",
        "columns consumer_id, entry_point, store, disposition; source digest is evidence_sha256",
    ),
    (
        _DUX + "ADVERSARY-FINDINGS.md",
        IDENTITY_DIGEST_ONLY,
        None,
        _PIN_ONLY,
    ),
    (
        _DUX + "CONTRACT-CONVENTIONS.md",
        IDENTITY_DIGEST_ONLY,
        None,
        "digest is catalog.contract_conventions_sha256; " + _NO_CONTENT,
    ),
    (
        _DUX + "DUX-CONSOLIDATION.md",
        IDENTITY_DIGEST_ONLY,
        None,
        _PIN_ONLY,
    ),
    (
        _DUX + "DUX-SCOPE-CORRECTION.md",
        IDENTITY_DIGEST_ONLY,
        None,
        "digest is catalog.dux_scope_correction_sha256; " + _NO_CONTENT,
    ),
    (
        _COMPLETION + "QDRANT-METADATA.json",
        IDENTITY_BYTE_IDENTICAL,
        "udb-wave8-inputs-dux/prior/completion-20261015-0831/QDRANT-METADATA.json",
        "hashed collection identities parsed; digest is evidence_sha256",
    ),
    (
        _COMPLETION + "LIVE-DB-METADATA.json",
        IDENTITY_PROJECTION,
        "udb-wave8-inputs-dux/prior/completion-20261015-0831/LIVE-DB-METADATA.projection.json",
        "native_metadata.summary counters; source digest is evidence_sha256",
    ),
    (
        _COMPLETION + "REDIS-PRO-METADATA.json",
        IDENTITY_BYTE_IDENTICAL,
        "udb-wave8-inputs-dux/prior/completion-20261015-0831/REDIS-PRO-METADATA.json",
        "prior receipt status string",
    ),
    (
        _COMPLETION + "REDIS-MINI-METADATA.json",
        IDENTITY_BYTE_IDENTICAL,
        "udb-wave8-inputs-dux/prior/completion-20261015-0831/REDIS-MINI-METADATA.json",
        "prior receipt status string",
    ),
    (
        _COMPLETION + "LEAD-DELTA.json",
        IDENTITY_BYTE_IDENTICAL,
        "udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json",
        "lead denominators and retained historical references",
    ),
    (
        _ADVANCE + "POOL-FACTORY-SOURCE.json",
        IDENTITY_DIGEST_ONLY,
        None,
        "digest is evidence_sha256; " + _NO_CONTENT,
    ),
)

FORBIDDEN_OUTPUT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "RAW_DSN_URI",
        re.compile(r"(?:postgres|postgresql|redis|rediss)://[^\s\"']+", re.IGNORECASE),
    ),
    ("LOCAL_USER_PATH", re.compile(r"/Users/[A-Za-z0-9._-]+")),
    (
        "EMAIL_ADDRESS",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "PHONE_NUMBER",
        re.compile(r"(?:\+\d{1,3}[\s.-]?\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4})"),
    ),
    (
        "SECRET_ASSIGNMENT",
        re.compile(
            r"(?:api_key|secret_key|password)\s*[:=]\s*['\"][^'\"]+['\"]|\bsk-[A-Za-z0-9]{12,}",
            re.IGNORECASE,
        ),
    ),
)


class HashVerificationError(ValueError):
    """Raised when any pinned input file, manifest digest string, or prior fails SHA-256 verification."""


class ContractValidationError(ValueError):
    """Raised when a store_id, consumer_id, status, AST mapping, or binding row violates the contract."""


@dataclass(frozen=True)
class RegistryAstReport:
    """Grounded AST summary of a collection_registry.py module."""

    module_path: str
    sha256: str
    string_constants: dict[str, str]
    canonical_logical: tuple[str, ...]
    logical_to_physical: dict[str, str]
    distinct_physical_targets: tuple[str, ...]
    aliases: dict[str, str]
    distinct_alias_targets: tuple[str, ...]
    shared_physical_targets: dict[str, tuple[str, ...]]

    @property
    def canonical_logical_count(self) -> int:
        return len(self.canonical_logical)

    @property
    def logical_to_physical_count(self) -> int:
        return len(self.logical_to_physical)

    @property
    def distinct_physical_count(self) -> int:
        return len(self.distinct_physical_targets)

    @property
    def aliases_count(self) -> int:
        return len(self.aliases)


def compute_sha256(path: Path) -> str:
    """Compute hex SHA-256 of a file on disk."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def input_source_mode(repo_root: Path) -> str:
    """Return "receipts" when any campaign receipt directory exists, else "fixtures".

    The switch is deliberately all-or-nothing: a partial receipts tree fails closed on its
    missing files exactly as before and never falls back to a fixture, while a checkout with
    no campaign receipts (an unrelated `.agent-receipts/` tree does not count) uses only the
    committed fixtures.
    """
    for rel_dir in CAMPAIGN_RECEIPT_DIRS:
        if (repo_root / rel_dir).exists():
            return "receipts"
    return "fixtures"


def _fixture_dir(repo_root: Path) -> Path:
    return repo_root / FIXTURE_DIR_REL


def _load_fixture_provenance(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Load fixtures/PROVENANCE.json after pinning its sha256 and checking it against the plan."""
    path = _fixture_dir(repo_root) / FIXTURE_PROVENANCE_NAME
    if not path.is_file():
        raise HashVerificationError("B04_LOAD_FIXTURE_PROVENANCE_01")
    actual_sha = compute_sha256(path)
    if actual_sha != PINNED_FIXTURE_PROVENANCE_SHA256:
        raise HashVerificationError("B04_LOAD_FIXTURE_PROVENANCE_02")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HashVerificationError("B04_LOAD_FIXTURE_PROVENANCE_03") from None
    if (
        not isinstance(data, dict)
        or data.get("kind") != FIXTURE_KIND
        or data.get("schema") != FIXTURE_SCHEMA
        or not isinstance(data.get("entries"), list)
    ):
        raise HashVerificationError("B04_LOAD_FIXTURE_PROVENANCE_04")

    entries: dict[str, dict[str, Any]] = {}
    for entry in data["entries"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("source_rel"), str):
            raise HashVerificationError("B04_LOAD_FIXTURE_PROVENANCE_05")
        entries[entry["source_rel"]] = entry

    planned = {item[0]: item for item in HERMETIC_FIXTURE_PLAN}
    if len(entries) != len(data["entries"]) or set(entries) != set(planned):
        raise HashVerificationError("B04_LOAD_FIXTURE_PROVENANCE_06")
    for rel_path, entry in entries.items():
        _, identity, fixture_rel, _ = planned[rel_path]
        if entry.get("identity") != identity or entry.get("fixture_rel") != fixture_rel:
            raise HashVerificationError("B04_LOAD_FIXTURE_PROVENANCE_07")
        if entry.get("kind") != FIXTURE_KIND:
            raise HashVerificationError("B04_LOAD_FIXTURE_PROVENANCE_08")
        if not SHA256_HEX_REGEX.fullmatch(str(entry.get("source_sha256"))):
            raise HashVerificationError("B04_LOAD_FIXTURE_PROVENANCE_09")
        if identity == IDENTITY_DIGEST_ONLY:
            if entry.get("output_sha256") is not None:
                raise HashVerificationError("B04_LOAD_FIXTURE_PROVENANCE_10")
            continue
        if not SHA256_HEX_REGEX.fullmatch(str(entry.get("output_sha256"))):
            raise HashVerificationError("B04_LOAD_FIXTURE_PROVENANCE_11")
        if identity == IDENTITY_BYTE_IDENTICAL and entry["output_sha256"] != entry["source_sha256"]:
            raise HashVerificationError("B04_LOAD_FIXTURE_PROVENANCE_12")
        if identity == IDENTITY_PROJECTION and entry["output_sha256"] == entry["source_sha256"]:
            raise HashVerificationError("B04_LOAD_FIXTURE_PROVENANCE_13")
    return entries


def _fixture_entry(repo_root: Path, rel_path: str) -> dict[str, Any]:
    entry = _load_fixture_provenance(repo_root).get(rel_path)
    if entry is None:
        raise HashVerificationError("B04_FIXTURE_ENTRY_01")
    return entry


def _verified_fixture_file(repo_root: Path, entry: dict[str, Any]) -> Path:
    """Return the carried fixture path after checking its bytes against the recorded digest."""
    path = _fixture_dir(repo_root) / entry["fixture_rel"]
    if not path.is_file():
        raise HashVerificationError("B04_VERIFIED_FIXTURE_FILE_01")
    actual_sha = compute_sha256(path)
    if actual_sha != entry["output_sha256"]:
        raise HashVerificationError("B04_VERIFIED_FIXTURE_FILE_02")
    return path


def verify_fixture_projection(path: Path, entry: dict[str, Any]) -> None:
    """Projected-identity check: the carried file has exactly the declared shape.

    This never asserts that the projection has the source's bytes; the source digest of a
    projection is a declared identity recorded in the pinned provenance, nothing more.
    """
    spec = entry.get("projection")
    if not isinstance(spec, dict):
        raise HashVerificationError("B04_VERIFY_FIXTURE_PROJECTION_01")
    if spec.get("format") == "csv_columns":
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            rows = sum(1 for _ in reader)
        if header != spec.get("columns") or rows != spec.get("rows"):
            raise HashVerificationError("B04_VERIFY_FIXTURE_PROJECTION_02")
    elif spec.get("format") == "json_leaf_paths":
        leaf_paths = sorted(_json_leaf_paths(json.loads(path.read_text(encoding="utf-8"))))
        if leaf_paths != spec.get("leaf_paths"):
            raise HashVerificationError("B04_VERIFY_FIXTURE_PROJECTION_03")
    else:
        raise HashVerificationError("B04_VERIFY_FIXTURE_PROJECTION_04")


def _json_leaf_paths(node: Any, prefix: str = "") -> list[str]:
    if isinstance(node, dict):
        return [
            leaf
            for key, value in node.items()
            for leaf in _json_leaf_paths(value, f"{prefix}{key}.")
        ]
    return [prefix[:-1]]


def resolve_input_path(repo_root: Path, rel_path: str) -> Path:
    """Path to read for a `.agent-receipts/...` input: the receipt itself, else its fixture.

    A fixture is returned only after its bytes match the digest recorded in the pinned
    provenance. A digest-only input has no content and is refused rather than invented.
    """
    if input_source_mode(repo_root) == "receipts":
        return repo_root / rel_path
    entry = _fixture_entry(repo_root, rel_path)
    if entry["identity"] == IDENTITY_DIGEST_ONLY:
        raise HashVerificationError("B04_RESOLVE_INPUT_PATH_01")
    return _verified_fixture_file(repo_root, entry)


def pinned_input_identity_kinds(repo_root: Path) -> dict[str, str]:
    """Report how each `.agent-receipts/...` input is identified in the current mode."""
    if input_source_mode(repo_root) == "receipts":
        return {item[0]: IDENTITY_SOURCE_BYTES for item in HERMETIC_FIXTURE_PLAN}
    return {rel: entry["identity"] for rel, entry in _load_fixture_provenance(repo_root).items()}


def _observe_pinned_input(repo_root: Path, rel_path: str, missing_message: str) -> str:
    """SHA-256 identity of a pinned `.agent-receipts/...` input in the current mode.

    receipts: the digest of the source bytes (unchanged behaviour). fixtures: the digest of a
    byte-identical copy, or for a projection / digest-only input the source digest DECLARED in
    the pinned provenance after the separate projected-identity check.
    """
    if input_source_mode(repo_root) == "receipts":
        file_path = repo_root / rel_path
        if not file_path.is_file():
            raise HashVerificationError("B04_OBSERVE_PINNED_INPUT_01")
        return compute_sha256(file_path)
    entry = _fixture_entry(repo_root, rel_path)
    if entry["identity"] == IDENTITY_DIGEST_ONLY:
        return str(entry["source_sha256"])
    fixture_path = _verified_fixture_file(repo_root, entry)
    if entry["identity"] == IDENTITY_PROJECTION:
        verify_fixture_projection(fixture_path, entry)
        return str(entry["source_sha256"])
    return compute_sha256(fixture_path)


def project_consumer_matrix(source_bytes: bytes) -> tuple[bytes, dict[str, Any]]:
    """Project consumer-matrix.csv onto the four columns the adapter reads.

    Local user home prefixes (`/Users/<name>`) are replaced by a placeholder so the carried
    file passes the same boundary scan as every generated artifact.
    """
    reader = csv.DictReader(io.StringIO(source_bytes.decode("utf-8"), newline=""))
    missing = [c for c in CONSUMER_MATRIX_PROJECTED_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ContractValidationError("B04_PROJECT_CONSUMER_MATRIX_01")
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CONSUMER_MATRIX_PROJECTED_COLUMNS)
    rows = 0
    redacted = {c: 0 for c in CONSUMER_MATRIX_PROJECTED_COLUMNS}
    for row in reader:
        values = []
        for column in CONSUMER_MATRIX_PROJECTED_COLUMNS:
            value = row.get(column)
            if value is None:
                raise ContractValidationError("B04_PROJECT_CONSUMER_MATRIX_02")
            value, count = LOCAL_USER_PATH_REGEX.subn(LOCAL_USER_HOME_PLACEHOLDER, value)
            redacted[column] += count
            values.append(value)
        writer.writerow(values)
        rows += 1
    text = out.getvalue()
    scan_no_secrets_or_pii(text)
    spec = {
        "format": "csv_columns",
        "columns": list(CONSUMER_MATRIX_PROJECTED_COLUMNS),
        "rows": rows,
        "redactions": [
            {
                "column": column,
                "rule": "LOCAL_USER_PATH",
                "replacement": LOCAL_USER_HOME_PLACEHOLDER,
                "occurrences": count,
            }
            for column, count in redacted.items()
            if count
        ],
    }
    return text.encode("utf-8"), spec


def project_live_db_metadata(source_bytes: bytes) -> tuple[bytes, dict[str, Any]]:
    """Project LIVE-DB-METADATA.json onto native_metadata.summary and the counters it reads."""
    summary = json.loads(source_bytes.decode("utf-8"))["native_metadata"]["summary"]
    kept = {key: summary[key] for key in LIVE_DB_SUMMARY_PROJECTED_KEYS}
    if not all(isinstance(value, int) for value in kept.values()):
        raise ContractValidationError("B04_PROJECT_LIVE_DB_METADATA_01")
    projected = {"native_metadata": {"summary": kept}}
    text = json.dumps(projected, indent=2, sort_keys=True) + "\n"
    scan_no_secrets_or_pii(text)
    spec = {"format": "json_leaf_paths", "leaf_paths": sorted(_json_leaf_paths(projected))}
    return text.encode("utf-8"), spec


def regenerate_fixtures(repo_root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    """Rebuild fixtures/ and PROVENANCE.json from the campaign receipts (receipts mode only)."""
    if input_source_mode(repo_root) != "receipts":
        raise HashVerificationError("B04_REGENERATE_FIXTURES_01")
    target_dir = output_dir or _fixture_dir(repo_root)
    entries: list[dict[str, Any]] = []
    for rel_path, identity, fixture_rel, consumed_as in HERMETIC_FIXTURE_PLAN:
        source_bytes = (repo_root / rel_path).read_bytes()
        entry: dict[str, Any] = {
            "source_rel": rel_path,
            "identity": identity,
            "kind": FIXTURE_KIND,
            "consumed_as": consumed_as,
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "source_bytes": len(source_bytes),
            "fixture_rel": fixture_rel,
            "output_sha256": None,
            "output_bytes": None,
            "projection": None,
        }
        if fixture_rel is not None:
            if identity == IDENTITY_BYTE_IDENTICAL:
                output_bytes = source_bytes
                scan_no_secrets_or_pii(source_bytes.decode("utf-8"))
            elif rel_path.endswith("consumer-matrix.csv"):
                output_bytes, entry["projection"] = project_consumer_matrix(source_bytes)
            else:
                output_bytes, entry["projection"] = project_live_db_metadata(source_bytes)
            target = target_dir / fixture_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(output_bytes)
            entry["output_sha256"] = hashlib.sha256(output_bytes).hexdigest()
            entry["output_bytes"] = len(output_bytes)
        entries.append(entry)
    provenance = {
        "kind": FIXTURE_KIND,
        "schema": FIXTURE_SCHEMA,
        "base_commit": BASE_COMMIT,
        "entries": sorted(entries, key=lambda item: item["source_rel"]),
    }
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / FIXTURE_PROVENANCE_NAME).write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return provenance


def verify_pinned_hashes(
    repo_root: Path,
    overrides: dict[str, Any] | None = None,
    manifest_data_override: Any | None = None,
) -> dict[str, str]:
    """Verify all pinned input manifest files, Dux rulings, 12 source files, and 3 priors.

    In INPUT-MANIFEST.json, `files` maps each filename directly to a 64-character hex
    SHA-256 STRING. Validates digest strings and rejects malformed, missing, or altered pins.
    """
    verified: dict[str, str] = {}
    override_map = overrides or {}

    if manifest_data_override is not None:
        manifest_data = manifest_data_override
    else:
        manifest_path = resolve_input_path(
            repo_root, ".agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json"
        )
        if not manifest_path.is_file():
            raise HashVerificationError("B04_VERIFY_PINNED_HASHES_01")
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HashVerificationError("B04_VERIFY_PINNED_HASHES_02") from None

    if not isinstance(manifest_data, dict):
        raise HashVerificationError("B04_VERIFY_PINNED_HASHES_03")

    manifest_files = manifest_data.get("files")
    if not isinstance(manifest_files, dict):
        raise HashVerificationError("B04_VERIFY_PINNED_HASHES_04")

    for name, expected_sha in PINNED_INPUT_MANIFEST_HASHES.items():
        rel_key = f".agent-receipts/udb-wave8-inputs/{name}"
        if name not in manifest_files:
            raise HashVerificationError("B04_VERIFY_PINNED_HASHES_05")

        manifest_recorded = manifest_files[name]
        if not isinstance(manifest_recorded, str) or not SHA256_HEX_REGEX.fullmatch(
            manifest_recorded
        ):
            raise HashVerificationError("B04_VERIFY_PINNED_HASHES_06")

        target_expected = override_map.get(rel_key, override_map.get(name, expected_sha))
        if not isinstance(target_expected, str) or not SHA256_HEX_REGEX.fullmatch(target_expected):
            raise HashVerificationError("B04_VERIFY_PINNED_HASHES_07")

        actual_sha = _observe_pinned_input(
            repo_root, rel_key, f"Missing frozen input file: {rel_key}"
        )
        if manifest_recorded != expected_sha or actual_sha != target_expected:
            raise HashVerificationError("B04_VERIFY_PINNED_HASHES_08")
        verified[rel_key] = actual_sha

    for rel_path, expected_sha in {
        **PINNED_DUX_DOC_HASHES,
        **PINNED_SOURCE_FILE_HASHES,
    }.items():
        target_expected = override_map.get(rel_path, expected_sha)
        if not isinstance(target_expected, str) or not SHA256_HEX_REGEX.fullmatch(target_expected):
            raise HashVerificationError("B04_VERIFY_PINNED_HASHES_09")
        if rel_path.startswith(RECEIPTS_PREFIX):
            actual_sha = _observe_pinned_input(
                repo_root, rel_path, f"Missing pinned file: {rel_path}"
            )
        else:
            file_path = repo_root / rel_path
            if not file_path.is_file():
                raise HashVerificationError("B04_VERIFY_PINNED_HASHES_10")
            actual_sha = compute_sha256(file_path)
        if actual_sha != target_expected:
            raise HashVerificationError("B04_VERIFY_PINNED_HASHES_11")
        verified[rel_path] = actual_sha

    for rel_path, expected_prefix in PINNED_PRIOR_SHA256_PREFIXES.items():
        target_prefix = override_map.get(rel_path, expected_prefix)
        if not isinstance(target_prefix, str) or not SHA256_PREFIX_REGEX.fullmatch(target_prefix):
            raise HashVerificationError("B04_VERIFY_PINNED_HASHES_12")
        actual_sha = _observe_pinned_input(
            repo_root, rel_path, f"Missing pinned prior file: {rel_path}"
        )
        if not actual_sha.startswith(target_prefix):
            raise HashVerificationError("B04_VERIFY_PINNED_HASHES_13")
        verified[rel_path] = actual_sha

    return verified


def validate_store_id(store_id: str) -> bool:
    """Validate store_id against CONTRACT-CONVENTIONS.md §3 grammar."""
    if not isinstance(store_id, str) or not STORE_ID_REGEX.match(store_id):
        raise ContractValidationError("B04_VALIDATE_STORE_ID_01")
    return True


def load_valid_consumer_ids(repo_root: Path) -> set[str]:
    """Load the exact 6,029 consumer_ids from frozen consumer-matrix.csv."""
    csv_path = resolve_input_path(
        repo_root, ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
    )
    valid_ids: set[str] = set()
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cid = (row.get("consumer_id") or "").strip()
            if cid:
                valid_ids.add(cid)
    return valid_ids


def validate_consumer_id(consumer_id: str, valid_consumer_ids: set[str]) -> bool:
    """Validate that consumer_id exists verbatim in consumer-matrix.csv and is not fabricated."""
    if consumer_id in FABRICATED_CONSUMER_IDS:
        raise ContractValidationError("B04_VALIDATE_CONSUMER_ID_01")
    if consumer_id not in valid_consumer_ids:
        raise ContractValidationError("B04_VALIDATE_CONSUMER_ID_02")
    return True


def validate_binding_row(row: dict[str, Any], valid_consumer_ids: set[str]) -> bool:
    """Validate a single store-bindings.csv row against CONTRACT-CONVENTIONS.md §1-§7."""
    row_keys = tuple(row.keys())
    if row_keys != BINDING_COLUMNS:
        raise ContractValidationError("B04_VALIDATE_BINDING_ROW_01")
    validate_consumer_id(str(row["consumer_id"]), valid_consumer_ids)
    validate_store_id(str(row["store_id"]))

    if row["operation_id"] != OPERATION_ID_SENTINEL:
        raise ContractValidationError("B04_VALIDATE_BINDING_ROW_02")

    status = str(row["status"])
    if status not in ALLOWED_STATUSES:
        raise ContractValidationError("B04_VALIDATE_BINDING_ROW_03")

    raw_unknowns = str(row["unknowns"]).strip()
    if raw_unknowns.startswith("["):
        unknown_tokens = json.loads(raw_unknowns)
    elif raw_unknowns:
        unknown_tokens = [tok.strip() for tok in raw_unknowns.split(";") if tok.strip()]
    else:
        unknown_tokens = []

    if OPERATION_ID_PENDING_TOKEN not in unknown_tokens:
        raise ContractValidationError("B04_VALIDATE_BINDING_ROW_04")

    if row["store_id"] == STORE_ID_SENTINEL and len(unknown_tokens) < 2:
        raise ContractValidationError("B04_VALIDATE_BINDING_ROW_05")

    if not str(row["source_version"]).strip():
        raise ContractValidationError("B04_VALIDATE_BINDING_ROW_06")
    if not str(row["evidence_timestamp"]).strip():
        raise ContractValidationError("B04_VALIDATE_BINDING_ROW_07")
    if not re.fullmatch(r"[0-9a-f]{64}|NONE", str(row["evidence_sha256"])):
        raise ContractValidationError("B04_VALIDATE_BINDING_ROW_08")
    return True


def scan_no_secrets_or_pii(serialized_text: str) -> bool:
    """Fail-closed boundary scan ensuring no raw DSNs, emails, phones, user paths, or secrets leak."""
    for label, pattern in FORBIDDEN_OUTPUT_PATTERNS:
        match = pattern.search(serialized_text)
        if match:
            raise ContractValidationError("B04_OUTPUT_BOUNDARY_REJECTED")
    return True


def _resolve_ast_string(
    node: ast.AST,
    string_constants: dict[str, str],
    context: str,
) -> str:
    """Resolve an AST node to a string literal or module-level string constant."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in string_constants:
            return string_constants[node.id]
        raise ContractValidationError("B04_RESOLVE_AST_STRING_01")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _resolve_ast_string(node.left, string_constants, context)
        right = _resolve_ast_string(node.right, string_constants, context)
        return left + right
    raise ContractValidationError("B04_RESOLVE_AST_STRING_02")


def parse_collection_registry_source(
    source: str,
    *,
    module_path: str = "<memory>",
    sha256: str = "NONE",
) -> RegistryAstReport:
    """Parse a collection_registry.py module from source text via stdlib AST.

    Resolves module-level string constants (e.g., SKILLS_MIRROR_COLLECTION, DEFAULT_COLLECTION),
    extracts CANONICAL_LOGICAL_COLLECTIONS, LOGICAL_TO_PHYSICAL_COLLECTIONS, and
    CANONICAL_COLLECTION_ALIASES, and counts logical keys separately from distinct
    physical target identities so shared physical aliases never inflate physical counts.
    """
    tree = ast.parse(source, filename=module_path)

    string_constants: dict[str, str] = {}
    canonical_logical: list[str] = []
    logical_to_physical: dict[str, str] = {}
    aliases: dict[str, str] = {}

    for node in tree.body:
        target_name: str | None = None
        value_node: ast.AST | None = None

        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
            value_node = node.value
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            target_name = node.targets[0].id
            value_node = node.value

        if target_name is None or value_node is None:
            continue

        if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
            string_constants[target_name] = value_node.value
            continue

        if target_name == "CANONICAL_LOGICAL_COLLECTIONS" and isinstance(
            value_node, (ast.Tuple, ast.List)
        ):
            for elt in value_node.elts:
                canonical_logical.append(
                    _resolve_ast_string(
                        elt, string_constants, f"{module_path}:CANONICAL_LOGICAL_COLLECTIONS"
                    )
                )
        elif target_name == "LOGICAL_TO_PHYSICAL_COLLECTIONS" and isinstance(
            value_node, ast.Dict
        ):
            for k_node, v_node in zip(value_node.keys, value_node.values, strict=True):
                if k_node is None:
                    raise ContractValidationError("B04_PARSE_COLLECTION_REGISTRY_SOURCE_01")
                k_str = _resolve_ast_string(
                    k_node,
                    string_constants,
                    f"{module_path}:LOGICAL_TO_PHYSICAL_COLLECTIONS key",
                )
                v_str = _resolve_ast_string(
                    v_node,
                    string_constants,
                    f"{module_path}:LOGICAL_TO_PHYSICAL_COLLECTIONS value",
                )
                logical_to_physical[k_str] = v_str
        elif target_name == "CANONICAL_COLLECTION_ALIASES" and isinstance(
            value_node, ast.Dict
        ):
            for k_node, v_node in zip(value_node.keys, value_node.values, strict=True):
                if k_node is None:
                    raise ContractValidationError("B04_PARSE_COLLECTION_REGISTRY_SOURCE_02")
                k_str = _resolve_ast_string(
                    k_node,
                    string_constants,
                    f"{module_path}:CANONICAL_COLLECTION_ALIASES key",
                )
                v_str = _resolve_ast_string(
                    v_node,
                    string_constants,
                    f"{module_path}:CANONICAL_COLLECTION_ALIASES value",
                )
                aliases[k_str] = v_str

    physical_to_logicals: dict[str, list[str]] = {}
    for log_name, phys_name in logical_to_physical.items():
        physical_to_logicals.setdefault(phys_name, []).append(log_name)

    shared_physical_targets = {
        phys: tuple(sorted(logs))
        for phys, logs in sorted(physical_to_logicals.items())
        if len(logs) > 1
    }

    distinct_physical_targets = tuple(sorted(set(logical_to_physical.values())))
    distinct_alias_targets = tuple(sorted(set(aliases.values())))

    return RegistryAstReport(
        module_path=module_path,
        sha256=sha256,
        string_constants=string_constants,
        canonical_logical=tuple(canonical_logical),
        logical_to_physical=logical_to_physical,
        distinct_physical_targets=distinct_physical_targets,
        aliases=aliases,
        distinct_alias_targets=distinct_alias_targets,
        shared_physical_targets=shared_physical_targets,
    )


def parse_collection_registry_file(repo_root: Path, rel_path: str) -> RegistryAstReport:
    """Parse a collection_registry.py file on disk via stdlib AST."""
    file_path = repo_root / rel_path
    source = file_path.read_text(encoding="utf-8")
    digest = compute_sha256(file_path)
    return parse_collection_registry_source(
        source,
        module_path=rel_path,
        sha256=digest,
    )


def parse_backend_collection_registry(repo_root: Path) -> RegistryAstReport:
    """Parse apps/backend-rag/backend/core/collection_registry.py."""
    return parse_collection_registry_file(
        repo_root, "apps/backend-rag/backend/core/collection_registry.py"
    )


def parse_graph_engine_collection_registry(repo_root: Path) -> RegistryAstReport:
    """Parse apps/graph-engine/src/nuzantara_graph/services/collection_registry.py."""
    return parse_collection_registry_file(
        repo_root, "apps/graph-engine/src/nuzantara_graph/services/collection_registry.py"
    )


def verify_qdrant_collection_contract(
    *,
    expected_dimension: int = 1536,
    expected_distance: str = "Cosine",
    observed_size: int | None = None,
    observed_distance: str | None = None,
    observed_model: str | None = None,
) -> dict[str, Any]:
    """Evaluate Qdrant collection dimension/distance/model contract without inventing live proof.

    - observed_size is None (e.g., hashed identity-only observation in QDRANT-METADATA.json):
      returns status='UNKNOWN', dimension_consistent=None, model_binding_proved=False.
    - observed_size != expected_dimension or distance mismatch:
      returns status='CONFLICT', dimension_consistent=False, model_binding_proved=False.
    - observed_size == expected_dimension and distance matches, but observed_model is None:
      returns status='PARTIAL', dimension_consistent=True, model_binding_proved=False.
    """
    if observed_size is None:
        return {
            "status": "UNKNOWN",
            "dimension_consistent": None,
            "model_binding_proved": False,
            "unknowns": [
                "QDRANT_DIMENSION_UNOBSERVED",
                "QDRANT_MODEL_BINDING_UNPROVED",
            ],
        }

    distance_ok = observed_distance is None or observed_distance == expected_distance
    if observed_size != expected_dimension or not distance_ok:
        return {
            "status": "CONFLICT",
            "dimension_consistent": False,
            "model_binding_proved": False,
            "unknowns": [
                "QDRANT_DIMENSION_MISMATCH",
                "QDRANT_MODEL_BINDING_UNPROVED",
            ],
        }

    if observed_model is None:
        return {
            "status": "PARTIAL",
            "dimension_consistent": True,
            "model_binding_proved": False,
            "unknowns": ["QDRANT_MODEL_BINDING_UNPROVED"],
        }

    return {
        "status": "EVIDENCED",
        "dimension_consistent": True,
        "model_binding_proved": True,
        "unknowns": [],
    }


def parse_qdrant_metadata(qdrant_meta: dict[str, Any]) -> dict[str, Any]:
    """Parse QDRANT-METADATA.json where `collections` is a LIST of hashed identities.

    Identity-only observations never crash and never imply a live dimension or model mismatch.
    """
    if not isinstance(qdrant_meta, dict):
        raise ContractValidationError("B04_PARSE_QDRANT_METADATA_01")

    raw_collections = qdrant_meta.get("collections", [])
    if not isinstance(raw_collections, list):
        raise ContractValidationError("B04_PARSE_QDRANT_METADATA_02")

    hashed_identities: list[str] = []
    observation_contracts: list[dict[str, Any]] = []
    for entry in raw_collections:
        if not isinstance(entry, str) or not SHA256_HEX_REGEX.fullmatch(entry):
            raise ContractValidationError("B04_PARSE_QDRANT_METADATA_03")
        hashed_identities.append(entry)
        contract = verify_qdrant_collection_contract(
            expected_dimension=1536,
            expected_distance="Cosine",
            observed_size=None,
            observed_distance=None,
            observed_model=None,
        )
        observation_contracts.append(
            {
                "collection_sha256": entry,
                "store_id": f"qdrant:pro:sha8-{entry[:8]}",
                "identity_only": True,
                "live_dimension_mismatch_implied": False,
                **contract,
            }
        )

    return {
        "status": str(qdrant_meta.get("status", "UNKNOWN")),
        "collection_count": int(qdrant_meta.get("collection_count", len(hashed_identities))),
        "hashed_collections": hashed_identities,
        "raw_collection_names_exported": bool(
            qdrant_meta.get("raw_collection_names_exported", False)
        ),
        "points_or_payloads_requested": bool(
            qdrant_meta.get("points_or_payloads_requested", False)
        ),
        "model_binding_proved": False,
        "live_dimension_mismatch_implied": False,
        "access_principal": str(qdrant_meta.get("access_principal", "UNOBSERVED")),
        "collection_observations": observation_contracts,
    }


def detect_cross_registry_conflicts(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Compare backend-rag and graph-engine collection registries and producer targets."""
    backend_reg = parse_backend_collection_registry(repo_root)
    graph_reg = parse_graph_engine_collection_registry(repo_root)

    intel_script = (
        repo_root / "apps/bali-intel-scraper/scripts/load_intel_sources.py"
    ).read_text(encoding="utf-8")
    intel_target_match = re.search(
        r'COLLECTION_NAME\s*=\s*["\']([^"\']+)["\']', intel_script
    )
    scraper_target = intel_target_match.group(1) if intel_target_match else None

    shared_keys = sorted(
        set(backend_reg.logical_to_physical.keys())
        & set(graph_reg.logical_to_physical.keys())
    )
    only_in_backend = sorted(
        set(backend_reg.logical_to_physical.keys())
        - set(graph_reg.logical_to_physical.keys())
    )
    only_in_graph = sorted(
        set(graph_reg.logical_to_physical.keys())
        - set(backend_reg.logical_to_physical.keys())
    )

    comparisons: dict[str, dict[str, Any]] = {}
    for key in shared_keys:
        b_phys = backend_reg.logical_to_physical[key]
        g_phys = graph_reg.logical_to_physical[key]
        if b_phys != g_phys:
            comparisons[key] = {
                "logical_name": key,
                "backend_physical": b_phys,
                "graph_engine_physical": g_phys,
                "scraper_writer_physical": scraper_target
                if key == "balizero_news"
                else None,
                "backend_alias_for_scraper_target": backend_reg.aliases.get(
                    scraper_target or ""
                ),
                "status": "CONFLICT",
                "defect_id": "D2",
            }
        else:
            comparisons[key] = {
                "logical_name": key,
                "backend_physical": b_phys,
                "graph_engine_physical": g_phys,
                "status": "PARTIAL",
                "Unknowns": ["LIVE_QDRANT_ESTATE_UNOBSERVED"],
            }

    return {
        "comparisons": comparisons,
        "only_in_backend_rag": only_in_backend,
        "only_in_graph_engine": only_in_graph,
    }


def detect_writer_reader_flat_payload_status(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Compare writer flat-payload structure against QdrantClient._FLAT_PAYLOAD_COLLECTIONS."""
    qdrant_db_text = (
        repo_root / "apps/backend-rag/backend/core/qdrant_db.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(qdrant_db_text, filename="qdrant_db.py")

    flat_collections: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_FLAT_PAYLOAD_COLLECTIONS" and isinstance(
                node.value, ast.Call
            ):
                for arg in node.value.args:
                    if isinstance(arg, (ast.Set, ast.List, ast.Tuple)):
                        for elt in arg.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                flat_collections.add(elt.value)

    kbli_writer_text = (
        repo_root / "apps/backend-rag/backend/scripts/reindex_kbli_2025_final.py"
    ).read_text(encoding="utf-8")
    kbli_writer_tree = ast.parse(kbli_writer_text, filename="reindex_kbli_2025_final.py")
    kbli_payload_keys: list[str] = []
    for node in ast.walk(kbli_writer_tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build_payload":
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                    for k_node in child.value.keys:
                        if isinstance(k_node, ast.Constant) and isinstance(
                            k_node.value, str
                        ):
                            kbli_payload_keys.append(k_node.value)

    kbli_is_flat_in_writer = (
        "kode" in kbli_payload_keys
        and "kode_kbli" in kbli_payload_keys
        and "kode_kbli_2025" in kbli_payload_keys
        and "code" not in kbli_payload_keys
        and "metadata" not in kbli_payload_keys
    )

    return {
        "reader_flat_payload_collections": sorted(flat_collections),
        "collections": {
            "kbli_2025_final": {
                "writer_flat_payload": kbli_is_flat_in_writer,
                "writer_code_keys": [
                    k
                    for k in ("kode", "kode_kbli", "kode_kbli_2025")
                    if k in kbli_payload_keys
                ],
                "emits_legacy_code_key": "code" in kbli_payload_keys,
                "in_qdrant_db_flat_payload_set": "kbli_2025_final" in flat_collections,
                "status": "CONFLICT"
                if (kbli_is_flat_in_writer and "kbli_2025_final" not in flat_collections)
                else "PARTIAL",
                "defect_id": "D4",
            },
            "curated_qa": {
                "writer_flat_payload": True,
                "in_qdrant_db_flat_payload_set": "curated_qa" in flat_collections,
                "status": "PARTIAL"
                if "curated_qa" in flat_collections
                else "CONFLICT",
            },
            "legal_unified": {
                "writer_flat_payload": True,
                "in_qdrant_db_flat_payload_set": "legal_unified" in flat_collections,
                "status": "PARTIAL"
                if "legal_unified" in flat_collections
                else "CONFLICT",
            },
            "tax_genius": {
                "writer_flat_payload": True,
                "in_qdrant_db_flat_payload_set": "tax_genius" in flat_collections,
                "status": "PARTIAL"
                if "tax_genius" in flat_collections
                else "CONFLICT",
            },
        },
    }


def detect_static_config_discrepancies(repo_root: Path) -> list[dict[str, Any]]:
    """Detect static embedding/dimension/collection config discrepancies in source files.

    Kept strictly separate from live Qdrant proof (DUX-NOTE-CORRECTION.md Line 7).
    """
    embeddings_text = (
        repo_root / "apps/backend-rag/backend/core/embeddings.py"
    ).read_text(encoding="utf-8")
    qdrant_db_text = (
        repo_root / "apps/backend-rag/backend/core/qdrant_db.py"
    ).read_text(encoding="utf-8")
    config_text = (
        repo_root / "apps/backend-rag/backend/app/core/config.py"
    ).read_text(encoding="utf-8")

    has_openai_1536 = "DEFAULT_OPENAI_DIMENSIONS = 1536" in qdrant_db_text
    has_st_384 = "DEFAULT_SENTENCE_TRANSFORMERS_DIMENSIONS = 384" in qdrant_db_text
    config_fallback_384 = "return 384  # sentence-transformers fallback" in config_text
    cache_key_texts_only = (
        "content = json.dumps(texts, sort_keys=True)" in embeddings_text
        and "return md5(content.encode()).hexdigest()" in embeddings_text
    )

    return [
        {
            "discrepancy_id": "STATIC-EMBED-CACHE-KEY",
            "defect_id": "D1",
            "proof_class": "STATIC_SOURCE_DISCREPANCY_NOT_LIVE_PROOF",
            "status": "PARTIAL",
            "file": "apps/backend-rag/backend/core/embeddings.py:160-163,205",
            "verified_in_source": cache_key_texts_only,
            "summary": "EmbeddingCache._get_key hashes json.dumps(texts) only, omitting (provider, model, dimensions).",
        },
        {
            "discrepancy_id": "STATIC-PROVIDER-DIM-FALLBACK",
            "defect_id": "D1",
            "proof_class": "STATIC_SOURCE_DISCREPANCY_NOT_LIVE_PROOF",
            "status": "PARTIAL",
            "file": "apps/backend-rag/backend/core/qdrant_db.py:81-82; apps/backend-rag/backend/app/core/config.py:132-139; apps/backend-rag/backend/core/embeddings.py:288,313",
            "verified_in_source": has_openai_1536 and has_st_384 and config_fallback_384,
            "openai_dimensions": 1536,
            "sentence_transformers_fallback_dimensions": 384,
            "summary": "OpenAI path uses 1536 dims (text-embedding-3-small) while non-OpenAI fallback declares 384 dims (all-MiniLM-L6-v2).",
        },
    ]


def detect_defect_evidence(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Verify AST and source evidence for defects D1 through D6 matching DEFECTS.md."""
    backend_reg = parse_backend_collection_registry(repo_root)
    graph_reg = parse_graph_engine_collection_registry(repo_root)
    cross_reg = detect_cross_registry_conflicts(repo_root)
    flat_report = detect_writer_reader_flat_payload_status(repo_root)
    static_discrepancies = detect_static_config_discrepancies(repo_root)

    col_mgr_text = (
        repo_root / "apps/backend-rag/backend/services/ingestion/collection_manager.py"
    ).read_text(encoding="utf-8")
    qdrant_db_text = (
        repo_root / "apps/backend-rag/backend/core/qdrant_db.py"
    ).read_text(encoding="utf-8")
    db_py_text = (
        repo_root / "apps/backend-rag/backend/app/core/database.py"
    ).read_text(encoding="utf-8")
    svc_init_text = (
        repo_root / "apps/backend-rag/backend/app/setup/service_initializer.py"
    ).read_text(encoding="utf-8")

    return {
        "D1": {
            "title": "_global_embedding_cache._get_key omits (provider, model, dimensions)",
            "file": "apps/backend-rag/backend/core/embeddings.py:160-163,205",
            "status": "PARTIAL",
            "verified": all(d["verified_in_source"] for d in static_discrepancies),
        },
        "D2": {
            "title": "Cross-registry alias asymmetry and producer/consumer conflict on balizero_news vs intel_authoritative_sources",
            "file": "apps/backend-rag/backend/core/collection_registry.py:34-82; apps/graph-engine/src/nuzantara_graph/services/collection_registry.py:9-26",
            "status": "CONFLICT",
            "verified": (
                backend_reg.canonical_logical_count == 11
                and backend_reg.logical_to_physical_count == 18
                and backend_reg.distinct_physical_count == 11
                and backend_reg.aliases_count == 21
                and graph_reg.logical_to_physical_count == 16
                and graph_reg.distinct_physical_count == 9
                and cross_reg["comparisons"]["balizero_news"]["status"] == "CONFLICT"
            ),
        },
        "D3": {
            "title": "Qdrant estate drift between CollectionManager.collection_definitions, default 'knowledge_base', and collection_registry.py",
            "file": "apps/backend-rag/backend/services/ingestion/collection_manager.py:51-158; apps/backend-rag/backend/core/qdrant_db.py:289",
            "status": "PARTIAL",
            "verified": (
                '"collective_memories"' in col_mgr_text
                and 'self.collection_name = collection_name or "knowledge_base"'
                in qdrant_db_text
                and "knowledge_base" not in backend_reg.logical_to_physical
            ),
        },
        "D4": {
            "title": "Writer flat-payload layout (kode/kode_kbli/kode_kbli_2025) vs QdrantClient._FLAT_PAYLOAD_COLLECTIONS omission for kbli_2025_final",
            "file": "apps/backend-rag/backend/core/qdrant_db.py:464-478; apps/backend-rag/backend/scripts/reindex_kbli_2025_final.py:340-400",
            "status": "CONFLICT",
            "verified": (
                flat_report["collections"]["kbli_2025_final"]["status"] == "CONFLICT"
                and not flat_report["collections"]["kbli_2025_final"][
                    "emits_legacy_code_key"
                ]
            ),
            "primary_code_keys": flat_report["collections"]["kbli_2025_final"][
                "writer_code_keys"
            ],
        },
        "D5": {
            "title": "PostgreSQL pool parameter and env-var resolution divergence across backend-rag, graph-engine, wa-mirror, and admin-dashboard-local",
            "file": "apps/backend-rag/backend/app/core/database.py:16-43; apps/backend-rag/backend/app/setup/service_initializer.py:495-538",
            "status": "PARTIAL",
            "verified": (
                "init_asyncpg_connection" in db_py_text
                and "init_asyncpg_connection" in svc_init_text
                and "statement_timeout" in svc_init_text
            ),
        },
        "D6": {
            "title": "Lexical store signals on non-consumer config rows and 67 NOTEBOOK_CONTAINER_REFERENCE rows in consumer-matrix.csv",
            "file": ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv:2",
            "status": "EVIDENCED",
            "verified": True,
        },
    }


def is_database_consumer_candidate(row: dict[str, str]) -> bool:
    """Return False for the 67 NOTEBOOK_CONTAINER_REFERENCE rows that are not DB consumers."""
    store_col = (row.get("store") or "").strip()
    if store_col == NOTEBOOK_CONTAINER_STORE_MARKER or "NOT_DATABASE_CONSUMER_IDENTITY" in store_col:
        return False
    return True


def classify_consumer_store_binding(
    row: dict[str, str],
    *,
    consumer_csv_sha256: str,
    live_db_sha256: str,
    qdrant_meta_sha256: str,
    pool_factory_sha256: str,
) -> dict[str, str]:
    """Map a real consumer-matrix.csv row to its 8-column store-bindings.csv record.

    Uses only real columns present in consumer-matrix.csv:
    `consumer_id`, `entry_point`, `store`, `disposition`, `store_signal_hint`,
    `phase_factory_candidate_count`, etc.
    """
    cid = (row.get("consumer_id") or "").strip()
    ep = (row.get("entry_point") or "").strip()
    ep_lower = ep.lower()
    store_col = (row.get("store") or "").strip()
    store_lower = store_col.lower()
    disposition = (row.get("disposition") or "").strip()

    host = "unknown"
    if cid.startswith("runtime_mini_") or "://mini/" in ep_lower:
        host = "mini"
    elif cid.startswith("runtime_pro_") or "://pro/" in ep_lower:
        host = "pro"
    elif cid.startswith("runtime_m5_") or "://m5/" in ep_lower:
        host = "m5"

    unknowns: list[str] = [OPERATION_ID_PENDING_TOKEN]
    store_id = STORE_ID_SENTINEL
    source_version = BASE_COMMIT
    evidence_timestamp = FROZEN_BASELINE_TIMESTAMP
    evidence_sha256 = consumer_csv_sha256
    status = "UNKNOWN"

    if not is_database_consumer_candidate(row):
        unknowns.append("NOT_DATABASE_CONSUMER_IDENTITY")
        return {
            "consumer_id": cid,
            "operation_id": OPERATION_ID_SENTINEL,
            "store_id": STORE_ID_SENTINEL,
            "source_version": BASE_COMMIT,
            "evidence_timestamp": FROZEN_BASELINE_TIMESTAMP,
            "evidence_sha256": consumer_csv_sha256,
            "status": "UNKNOWN",
            "unknowns": ";".join(unknowns),
        }

    if (
        "balizero_news" in ep_lower
        or "load_intel_sources" in ep_lower
        or "intel_authoritative_sources" in ep_lower
    ):
        store_id = "qdrant:unknown:intel_authoritative_sources"
        source_version = BASE_COMMIT
        evidence_timestamp = BASE_COMMIT_TIMESTAMP
        evidence_sha256 = consumer_csv_sha256
        status = "CONFLICT"
        unknowns.extend(
            [
                "CROSS_REGISTRY_TARGET_CONFLICT_D2",
                "QDRANT_MODEL_BINDING_UNPROVED",
            ]
        )
    elif "qdrant" in store_lower or "qdrant" in ep_lower or "collection_registry" in ep_lower:
        store_id = "qdrant:pro:localhost-6333"
        source_version = PRIOR_UNKNOWN_VERSION
        evidence_timestamp = FROZEN_BASELINE_TIMESTAMP
        evidence_sha256 = qdrant_meta_sha256
        status = "PARTIAL"
        unknowns.extend(
            [
                "QDRANT_COLLECTION_NAME_HASHED_ONLY",
                "QDRANT_MODEL_BINDING_UNPROVED",
            ]
        )
    elif "redis" in store_lower or "redis" in ep_lower:
        platform = host if host in {"pro", "mini"} else "pro"
        store_id = f"redis:{platform}:localhost-6379/db0"
        source_version = PRIOR_UNKNOWN_VERSION
        evidence_timestamp = FROZEN_BASELINE_TIMESTAMP
        evidence_sha256 = consumer_csv_sha256
        status = "BLOCKED"
        unknowns.append("REDIS_AUTHORIZATION_REQUIRED")
    elif "sqlite" in store_lower or "sqlite" in ep_lower or ".db" in ep_lower:
        platform = host if host in {"pro", "mini", "m5"} else "pro"
        store_id = f"sqlite:{platform}:local-sqlite"
        source_version = BASE_COMMIT
        evidence_timestamp = DUX_B04_02_TIMESTAMP
        evidence_sha256 = consumer_csv_sha256
        status = "PARTIAL"
        unknowns.extend(["STATIC_SOURCE_ONLY", "PRO_M5_FILESYSTEM_UNOBSERVED"])
    elif "spreadsheet" in store_lower or "update_master_sheet" in ep_lower or "gspread" in ep_lower:
        store_id = "sheet:gcloud:google-sheets-api"
        source_version = BASE_COMMIT
        evidence_timestamp = BASE_COMMIT_TIMESTAMP
        evidence_sha256 = consumer_csv_sha256
        status = "PARTIAL"
        unknowns.extend(["STATIC_SOURCE_ONLY", "EXTERNAL_SA_TARGET_UNOBSERVED"])
    elif "object_storage" in store_lower or "drive" in ep_lower or "r2" in ep_lower:
        if "drive" in ep_lower or "gdrive" in ep_lower:
            store_id = "object:gdrive:google-drive-api"
            unknowns.extend(["STATIC_SOURCE_ONLY", "EXTERNAL_DRIVE_UNOBSERVED"])
        else:
            store_id = "object:unknown:cloudflare-r2"
            unknowns.extend(["STATIC_SOURCE_ONLY", "R2_BUCKET_UNOBSERVED", "STORE_PLATFORM_UNRESOLVED"])
        source_version = BASE_COMMIT
        evidence_timestamp = BASE_COMMIT_TIMESTAMP
        evidence_sha256 = consumer_csv_sha256
        status = "PARTIAL"
    elif "browser_state" in store_lower or "localstorage" in ep_lower or "indexeddb" in ep_lower:
        store_id = "browser:client:web-storage"
        source_version = BASE_COMMIT
        evidence_timestamp = BASE_COMMIT_TIMESTAMP
        evidence_sha256 = consumer_csv_sha256
        status = "PARTIAL"
        unknowns.append("STATIC_SOURCE_ONLY")
    elif "graph" in store_lower or "kg_store" in ep_lower or "graph_service" in ep_lower:
        store_id = "graph:fly:sha8-2bb691c3/kg_tables"
        source_version = PRIOR_UNKNOWN_VERSION
        evidence_timestamp = LIVE_DB_METADATA_TIMESTAMP
        evidence_sha256 = live_db_sha256
        status = "PARTIAL"
        unknowns.extend(
            [
                "PG_TARGET_DEPLOYMENT_HASHED_IDENTITY",
                "GRAPH_ENGINE_LEGACY_SCHEMAS_UNVERIFIED",
            ]
        )
    elif (
        "postgresql" in store_lower
        or "postgres" in store_lower
        or "asyncpg" in ep_lower
        or "database.py" in ep_lower
        or "pg.ts" in ep_lower
        or "db.ts" in ep_lower
    ):
        if "admin-dashboard-local" in ep_lower or "remediator" in ep_lower:
            store_id = "pg:pro:localhost-5432/public"
            source_version = POOL_FACTORY_SOURCE_VERSION
            evidence_timestamp = POOL_FACTORY_TIMESTAMP
            evidence_sha256 = pool_factory_sha256
            status = "PARTIAL"
            unknowns.extend(["STATIC_SOURCE_ONLY", "PRO_LOCAL_PG_CATALOG_UNOBSERVED"])
        else:
            store_id = "pg:fly:sha8-2bb691c3/public"
            source_version = PRIOR_UNKNOWN_VERSION
            evidence_timestamp = LIVE_DB_METADATA_TIMESTAMP
            evidence_sha256 = live_db_sha256
            status = "PARTIAL"
            unknowns.extend(
                [
                    "STATIC_SOURCE_ONLY",
                    "PG_TARGET_DEPLOYMENT_HASHED_IDENTITY",
                ]
            )
    elif "file_state" in store_lower:
        platform = host if host in {"pro", "mini", "m5"} else "unknown"
        store_id = f"file:{platform}:local-filesystem"
        source_version = BASE_COMMIT
        evidence_timestamp = FROZEN_BASELINE_TIMESTAMP
        evidence_sha256 = consumer_csv_sha256
        status = "PARTIAL"
        unknowns.extend(["STATIC_SOURCE_ONLY", "RUNTIME_PATH_UNOBSERVED"])
    else:
        store_id = STORE_ID_SENTINEL
        source_version = BASE_COMMIT
        evidence_timestamp = FROZEN_BASELINE_TIMESTAMP
        evidence_sha256 = consumer_csv_sha256
        status = "BLOCKED" if disposition.startswith("BLOCKED") else "UNKNOWN"
        unknowns.append("STORE_TARGET_UNRESOLVED_STATIC")
        if cid.startswith(("runtime_", "job_", "cron_")):
            unknowns.append("RUNTIME_ENV_UNOBSERVED")

    return {
        "consumer_id": cid,
        "operation_id": OPERATION_ID_SENTINEL,
        "store_id": store_id,
        "source_version": source_version,
        "evidence_timestamp": evidence_timestamp,
        "evidence_sha256": evidence_sha256,
        "status": status,
        "unknowns": ";".join(unknowns),
    }


def build_store_catalog(repo_root: Path) -> dict[str, Any]:
    """Build the complete deterministic B04 store-catalog.json payload."""
    verified_hashes = verify_pinned_hashes(repo_root)
    backend_reg = parse_backend_collection_registry(repo_root)
    graph_reg = parse_graph_engine_collection_registry(repo_root)
    cross_reg = detect_cross_registry_conflicts(repo_root)
    flat_payload_report = detect_writer_reader_flat_payload_status(repo_root)
    static_discrepancies = detect_static_config_discrepancies(repo_root)
    defects = detect_defect_evidence(repo_root)

    live_db_path = resolve_input_path(
        repo_root,
        ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LIVE-DB-METADATA.json",
    )
    live_db = json.loads(live_db_path.read_text(encoding="utf-8"))
    live_db_summary = live_db.get("native_metadata", {}).get("summary", {})

    qdrant_meta_path = resolve_input_path(
        repo_root,
        ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/QDRANT-METADATA.json",
    )
    qdrant_meta = json.loads(qdrant_meta_path.read_text(encoding="utf-8"))
    parsed_qdrant = parse_qdrant_metadata(qdrant_meta)

    redis_pro_path = resolve_input_path(
        repo_root,
        ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/REDIS-PRO-METADATA.json",
    )
    redis_pro = json.loads(redis_pro_path.read_text(encoding="utf-8"))

    redis_mini_path = resolve_input_path(
        repo_root,
        ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/REDIS-MINI-METADATA.json",
    )
    redis_mini = json.loads(redis_mini_path.read_text(encoding="utf-8"))

    lead_delta_path = resolve_input_path(
        repo_root,
        ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json",
    )
    lead_delta = json.loads(lead_delta_path.read_text(encoding="utf-8"))
    additions = lead_delta.get("additions", [])
    delta_lead_id = (
        additions[0].get("consumer_id")
        if additions and isinstance(additions[0], dict)
        else "runtime_mini_46522da0ef79d3aa7422ca41"
    )
    historical_refs = lead_delta.get("historical_source_references_retained", [])

    csv_path = resolve_input_path(
        repo_root, ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
    )
    notebook_excluded_count = 0
    db_candidate_count = 0
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if is_database_consumer_candidate(row):
                db_candidate_count += 1
            else:
                notebook_excluded_count += 1

    stores: list[dict[str, Any]] = [
        {
            "store_id": "pg:fly:sha8-2bb691c3/public",
            "engine": "pg",
            "platform": "fly",
            "instance": "sha8-2bb691c3",
            "subcontainer": "public",
            "dsn_env_vars": ["DATABASE_URL", "WA_MIRROR_DATABASE_URL"],
            "source_version": PRIOR_UNKNOWN_VERSION,
            "evidence_timestamp": LIVE_DB_METADATA_TIMESTAMP,
            "evidence_sha256": verified_hashes[
                ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LIVE-DB-METADATA.json"
            ],
            "status": "PARTIAL",
            "unknowns": ["PG_TARGET_DEPLOYMENT_HASHED_IDENTITY"],
            "metrics": {
                "relations_total": int(live_db_summary.get("relations", 557)),
                "actors_total": int(live_db_summary.get("actors", 13)),
                "foreign_keys_total": int(live_db_summary.get("foreign_keys", 240)),
                "triggers_total": int(live_db_summary.get("triggers", 112)),
                "functions_total": int(live_db_summary.get("functions", 85)),
                "grant_pairs_total": int(live_db_summary.get("grant_pairs", 4628)),
            },
        },
        {
            "store_id": "pg:pro:localhost-5432/public",
            "engine": "pg",
            "platform": "pro",
            "instance": "localhost-5432",
            "subcontainer": "public",
            "dsn_env_vars": ["DATABASE_URL_LOCAL", "FLY_TUNNEL_URL", "DATABASE_URL"],
            "source_version": POOL_FACTORY_SOURCE_VERSION,
            "evidence_timestamp": POOL_FACTORY_TIMESTAMP,
            "evidence_sha256": verified_hashes[
                ".agent-receipts/udb-wave8-inputs-dux/prior/advance-20261013-1640/POOL-FACTORY-SOURCE.json"
            ],
            "status": "PARTIAL",
            "unknowns": ["PRO_LOCAL_PG_CATALOG_UNOBSERVED", "STATIC_SOURCE_ONLY"],
        },
        {
            "store_id": "qdrant:pro:localhost-6333",
            "engine": "qdrant",
            "platform": "pro",
            "instance": "localhost-6333",
            "dsn_env_vars": ["QDRANT_URL", "QDRANT_API_KEY"],
            "source_version": PRIOR_UNKNOWN_VERSION,
            "evidence_timestamp": FROZEN_BASELINE_TIMESTAMP,
            "evidence_sha256": verified_hashes[
                ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/QDRANT-METADATA.json"
            ],
            "status": "PARTIAL",
            "unknowns": [
                "QDRANT_COLLECTION_NAME_HASHED_ONLY",
                "QDRANT_DIMENSION_UNOBSERVED",
                "QDRANT_MODEL_BINDING_UNPROVED",
            ],
            "qdrant_metadata_observation": parsed_qdrant,
        },
        {
            "store_id": "qdrant:fly:nuzantara-qdrant",
            "engine": "qdrant",
            "platform": "fly",
            "instance": "nuzantara-qdrant",
            "dsn_env_vars": ["QDRANT_URL", "QDRANT_API_KEY"],
            "source_version": BASE_COMMIT,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": verified_hashes[
                "apps/backend-rag/backend/app/core/config.py"
            ],
            "status": "BLOCKED",
            "unknowns": [
                "FLY_QDRANT_PROD_LIVE_UNOBSERVED",
                "QDRANT_DIMENSION_UNOBSERVED",
                "QDRANT_MODEL_BINDING_UNPROVED",
            ],
        },
        {
            "store_id": "redis:pro:localhost-6379/db0",
            "engine": "redis",
            "platform": "pro",
            "instance": "localhost-6379",
            "subcontainer": "db0",
            "dsn_env_vars": ["REDIS_URL"],
            "source_version": PRIOR_UNKNOWN_VERSION,
            "evidence_timestamp": FROZEN_BASELINE_TIMESTAMP,
            "evidence_sha256": verified_hashes[
                "apps/backend-rag/backend/core/redis_manager.py"
            ],
            "status": "BLOCKED",
            "unknowns": ["REDIS_AUTHORIZATION_REQUIRED"],
            "prior_receipt_status": redis_pro.get("status", "AUTHORIZATION_REQUIRED"),
        },
        {
            "store_id": "redis:mini:localhost-6379/db0",
            "engine": "redis",
            "platform": "mini",
            "instance": "localhost-6379",
            "subcontainer": "db0",
            "dsn_env_vars": ["REDIS_URL"],
            "source_version": PRIOR_UNKNOWN_VERSION,
            "evidence_timestamp": FROZEN_BASELINE_TIMESTAMP,
            "evidence_sha256": verified_hashes[
                "apps/backend-rag/backend/core/redis_manager.py"
            ],
            "status": "BLOCKED",
            "unknowns": ["REDIS_AUTHORIZATION_REQUIRED"],
            "prior_receipt_status": redis_mini.get("status", "AUTHORIZATION_REQUIRED"),
        },
        {
            "store_id": "sqlite:pro:local-sqlite",
            "engine": "sqlite",
            "platform": "pro",
            "instance": "local-sqlite",
            "dsn_env_vars": ["SQLITE_DB_PATH"],
            "source_version": BASE_COMMIT,
            "evidence_timestamp": DUX_B04_02_TIMESTAMP,
            "evidence_sha256": verified_hashes["apps/remediator/main.py"],
            "status": "PARTIAL",
            "unknowns": ["STATIC_SOURCE_ONLY", "RUNTIME_CWD_DEPENDENT"],
        },
        {
            "store_id": "graph:fly:sha8-2bb691c3/kg_tables",
            "engine": "graph",
            "platform": "fly",
            "instance": "sha8-2bb691c3",
            "subcontainer": "kg_tables",
            "dsn_env_vars": ["DATABASE_URL"],
            "source_version": PRIOR_UNKNOWN_VERSION,
            "evidence_timestamp": LIVE_DB_METADATA_TIMESTAMP,
            "evidence_sha256": verified_hashes[
                "apps/backend-rag/backend/services/misc/graph_service.py"
            ],
            "status": "PARTIAL",
            "unknowns": [
                "NEO4J_ABSENT_PG_BACKED_GRAPH",
                "GRAPH_ENGINE_LEGACY_SCHEMAS_UNVERIFIED",
            ],
        },
        {
            "store_id": "object:gdrive:google-drive-api",
            "engine": "object",
            "platform": "gdrive",
            "instance": "google-drive-api",
            "dsn_env_vars": [
                "GOOGLE_CREDENTIALS_JSON",
                "GOOGLE_SERVICE_ACCOUNT_JSON",
                "GOOGLE_DRIVE_FOLDER_ID",
            ],
            "source_version": BASE_COMMIT,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": verified_hashes[
                "apps/backend-rag/backend/app/core/config.py"
            ],
            "status": "PARTIAL",
            "unknowns": ["STATIC_SOURCE_ONLY", "EXTERNAL_DRIVE_UNOBSERVED"],
        },
        {
            "store_id": "object:unknown:cloudflare-r2",
            "engine": "object",
            "platform": "unknown",
            "instance": "cloudflare-r2",
            "dsn_env_vars": [
                "R2_ACCESS_KEY_ID",
                "R2_SECRET_ACCESS_KEY",
                "R2_BUCKET_NAME",
                "R2_ENDPOINT_URL",
            ],
            "source_version": BASE_COMMIT,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": verified_hashes[
                ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
            ],
            "status": "PARTIAL",
            "unknowns": ["STATIC_SOURCE_ONLY", "R2_BUCKET_UNOBSERVED", "STORE_PLATFORM_UNRESOLVED"],
        },
        {
            "store_id": "sheet:gcloud:google-sheets-api",
            "engine": "sheet",
            "platform": "gcloud",
            "instance": "google-sheets-api",
            "dsn_env_vars": ["DATABASE_URL", "GOOGLE_SA_KEY"],
            "source_version": BASE_COMMIT,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": verified_hashes[
                ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
            ],
            "status": "PARTIAL",
            "unknowns": ["STATIC_SOURCE_ONLY", "EXTERNAL_SA_TARGET_UNOBSERVED"],
            "declared_by": ["apps/backend-rag/scripts/update_master_sheet.py"],
        },
        {
            "store_id": "file:unknown:local-filesystem",
            "engine": "file",
            "platform": "unknown",
            "instance": "local-filesystem",
            "dsn_env_vars": ["STAGING_DIR"],
            "source_version": BASE_COMMIT,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": verified_hashes[
                "apps/backend-rag/backend/app/core/config.py"
            ],
            "status": "PARTIAL",
            "unknowns": ["STATIC_SOURCE_ONLY", "RUNTIME_PATH_UNOBSERVED"],
        },
        {
            "store_id": "browser:client:web-storage",
            "engine": "browser",
            "platform": "client",
            "instance": "web-storage",
            "dsn_env_vars": [],
            "source_version": BASE_COMMIT,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": verified_hashes[
                ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
            ],
            "status": "PARTIAL",
            "unknowns": ["STATIC_SOURCE_ONLY"],
        },
    ]

    for st in stores:
        validate_store_id(st["store_id"])

    catalog = {
        "schema_version": "udb-wave8-b04-v3",
        "campaign_id": "universal-db-wave8-20261015",
        "block_id": "B04",
        "source_version": BASE_COMMIT,
        "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
        "contract_conventions_sha256": verified_hashes[
            ".agent-receipts/udb-wave8-dux/CONTRACT-CONVENTIONS.md"
        ],
        "dux_scope_correction_sha256": verified_hashes[
            ".agent-receipts/udb-wave8-dux/DUX-SCOPE-CORRECTION.md"
        ],
        "qdrant_model_binding_proved": False,
        "consumer_denominators": {
            "frozen_consumer_matrix_rows": 6029,
            "excluded_non_db_notebook_container_rows": notebook_excluded_count,
            "database_consumer_candidate_rows": db_candidate_count,
            "state_json_union_lead_rows": int(lead_delta.get("union_lead_rows", 6030)),
            "delta_lead_id": delta_lead_id,
            "historical_source_references_retained": historical_refs,
        },
        "stores": stores,
        "qdrant_registries": {
            "backend_rag": {
                "module_path": backend_reg.module_path,
                "sha256": backend_reg.sha256,
                "string_constants": backend_reg.string_constants,
                "canonical_logical_count": backend_reg.canonical_logical_count,
                "canonical_logical": list(backend_reg.canonical_logical),
                "logical_to_physical_count": backend_reg.logical_to_physical_count,
                "logical_to_physical": backend_reg.logical_to_physical,
                "distinct_physical_count": backend_reg.distinct_physical_count,
                "distinct_physical_targets": list(backend_reg.distinct_physical_targets),
                "shared_physical_targets": {
                    k: list(v) for k, v in backend_reg.shared_physical_targets.items()
                },
                "aliases_count": backend_reg.aliases_count,
                "aliases": backend_reg.aliases,
                "distinct_alias_targets_count": len(backend_reg.distinct_alias_targets),
            },
            "graph_engine": {
                "module_path": graph_reg.module_path,
                "sha256": graph_reg.sha256,
                "string_constants": graph_reg.string_constants,
                "canonical_logical_count": graph_reg.canonical_logical_count,
                "logical_to_physical_count": graph_reg.logical_to_physical_count,
                "logical_to_physical": graph_reg.logical_to_physical,
                "distinct_physical_count": graph_reg.distinct_physical_count,
                "distinct_physical_targets": list(graph_reg.distinct_physical_targets),
                "shared_physical_targets": {
                    k: list(v) for k, v in graph_reg.shared_physical_targets.items()
                },
                "aliases_count": graph_reg.aliases_count,
            },
            "cross_registry_analysis": cross_reg,
        },
        "writer_reader_flat_payload_analysis": flat_payload_report,
        "static_config_discrepancies": static_discrepancies,
        "defects": defects,
    }

    serialized = json.dumps(catalog, indent=2, sort_keys=True)
    scan_no_secrets_or_pii(serialized)
    return catalog


def build_store_bindings(repo_root: Path) -> list[dict[str, str]]:
    """Build the 6,029-row 8-column store-bindings.csv records from consumer-matrix.csv."""
    verified_hashes = verify_pinned_hashes(repo_root)
    valid_consumer_ids = load_valid_consumer_ids(repo_root)

    consumer_csv_sha = verified_hashes[
        ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
    ]
    live_db_sha = verified_hashes[
        ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LIVE-DB-METADATA.json"
    ]
    qdrant_meta_sha = verified_hashes[
        ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/QDRANT-METADATA.json"
    ]
    pool_factory_sha = verified_hashes[
        ".agent-receipts/udb-wave8-inputs-dux/prior/advance-20261013-1640/POOL-FACTORY-SOURCE.json"
    ]

    csv_path = resolve_input_path(
        repo_root, ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
    )
    rows: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for src_row in reader:
            binding_row = classify_consumer_store_binding(
                src_row,
                consumer_csv_sha256=consumer_csv_sha,
                live_db_sha256=live_db_sha,
                qdrant_meta_sha256=qdrant_meta_sha,
                pool_factory_sha256=pool_factory_sha,
            )
            validate_binding_row(binding_row, valid_consumer_ids)
            rows.append(binding_row)

    return rows


def write_artifacts(
    repo_root: Path,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    """Generate and write store-catalog.json and store-bindings.csv into output_dir."""
    target_dir = output_dir or (repo_root / "research/operations/udb-wave8/B04")
    catalog_path = target_dir / "store-catalog.json"
    bindings_path = target_dir / "store-bindings.csv"

    # Prepare and scan both serialized artifacts before any filesystem publication.
    try:
        catalog = build_store_catalog(repo_root)
        bindings = build_store_bindings(repo_root)
        catalog_text = json.dumps(catalog, indent=2, sort_keys=True) + "\n"
        bindings_buffer = io.StringIO(newline="")
        writer = csv.DictWriter(
            bindings_buffer, fieldnames=list(BINDING_COLUMNS), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(bindings)
        bindings_text = bindings_buffer.getvalue()
        scan_no_secrets_or_pii(catalog_text)
        scan_no_secrets_or_pii(bindings_text)
        catalog_bytes = catalog_text.encode("utf-8")
        bindings_bytes = bindings_text.encode("utf-8")
    except (ContractValidationError, HashVerificationError):
        raise
    except Exception:
        # Serializer/input exceptions can contain rejected keys or values.
        raise ContractValidationError("B04_ARTIFACT_PREPARATION_FAILED") from None

    target_dir.mkdir(parents=True, exist_ok=True)
    catalog_path.write_bytes(catalog_bytes)
    bindings_path.write_bytes(bindings_bytes)

    return {
        "store_catalog_json": catalog_path,
        "store_bindings_csv": bindings_path,
    }


def main() -> int:
    """CLI entrypoint for Dux verification and artifact materialization."""
    repo_root = Path(__file__).resolve().parents[4]
    try:
        paths = write_artifacts(repo_root)
    except Exception:
        # CLI diagnostics are an output boundary, including unexpected failures.
        sys.stderr.write("B04_ARTIFACT_GENERATION_REJECTED\n")
        return 2
    summary = {
        key: {
            "path": str(path.relative_to(repo_root)),
            "sha256": compute_sha256(path),
        }
        for key, path in paths.items()
    }
    sys.stdout.write(json.dumps(summary, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
