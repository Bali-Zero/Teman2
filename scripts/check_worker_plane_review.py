#!/usr/bin/env python3
"""Deterministically validate one immutable three-seat worker-plane review.

The validator is deliberately read-only.  It consumes the materialized packet,
its canonical manifest and freeze receipt, three normalized reviews with their
raw/invocation companions, and the final finding disposition.  It regenerates
both projections from committed Git objects; it never invokes a shell or a
provider and never reads a covered input from the mutable worktree.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from freeze_worker_plane_review import (
        DEFAULT_GENERATOR_PATH,
        DEFAULT_LAUNCHER_PATH,
        DEFAULT_ROUTE_CONFIG_PATH,
        DEFAULT_VALIDATOR_PATH,
        InputSpec,
        PacketError,
        _git,
        _inputs_from_args,
        _read_git_blob,
        _resolve_commit,
        _tree_oid,
        _validate_repo_path,
        build_projection_from_git,
        canonical_json_bytes,
        parse_packet,
        sha256_bytes,
    )
except ModuleNotFoundError:  # pragma: no cover - repository import path
    from scripts.freeze_worker_plane_review import (
        DEFAULT_GENERATOR_PATH,
        DEFAULT_LAUNCHER_PATH,
        DEFAULT_ROUTE_CONFIG_PATH,
        DEFAULT_VALIDATOR_PATH,
        InputSpec,
        PacketError,
        _git,
        _inputs_from_args,
        _read_git_blob,
        _resolve_commit,
        _tree_oid,
        _validate_repo_path,
        build_projection_from_git,
        canonical_json_bytes,
        parse_packet,
        sha256_bytes,
    )


EXPECTED_HEADINGS = (
    "# Verdict",
    "# Blocking findings",
    "# Important findings",
    "# What survives review",
    "# Required amendments",
    "# Falsification test",
)
EXPECTED_ROUTES = frozenset({"claude-fable-5", "Gemini 3.1 Pro (High)", "glm-5.2"})
FREEZE_RECEIPT_SCHEMA = "nuzantara.worker-plane-review-freeze-receipt/v1"
INVOCATION_SCHEMA = "nuzantara.worker-plane-review-launcher-receipt/v2"
REVIEW_INPUT_SCHEMA = "nuzantara.worker-plane-review-input/v1"
REVIEW_INPUT_MAGIC = b"NUZANTARA-REVIEW-INPUT-V1\n"
LAUNCHER_REPO_PATH = DEFAULT_LAUNCHER_PATH
VALIDATOR_REPO_PATH = DEFAULT_VALIDATOR_PATH
CLAUDE_EXECUTABLE = "/Users/nuzantara/.local/share/claude/versions/2.1.214"
GEMINI_EXECUTABLE = "/Users/nuzantara/.local/bin/agy"
MCP_CONFIG = '{"mcpServers":{}}'
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
FINDING_ID = re.compile(r"\[([A-Z0-9][A-Z0-9._-]{2,63})\]")
COMMIT_ID = re.compile(r"^[0-9a-f]{7,64}$")
EVIDENCE_REFERENCE = re.compile(
    r"^(?:artifact:(?P<artifact_path>[^@;]+)@(?P<artifact_sha>[0-9a-f]{64})"
    r"|test:(?P<test_path>[^:;]+)::(?P<test_symbol>[A-Za-z_][A-Za-z0-9_.-]*))$"
)
ACCEPTED_EVIDENCE = re.compile(
    r"^evidence=(?P<reference>[^;]+); resolution=(?P<resolution>[^;]+)$"
)
REJECTED_EVIDENCE = re.compile(
    r"^falsification=(?P<reference>[^;]+); rationale=(?P<rationale>[^;]+); "
    r"resolution=(?P<resolution>[^;]+)$"
)
VERDICT = re.compile(
    r"^(GO|GO-WITH-CHANGES|NO-GO)\s*(?:[—-]\s*)?"
    r"confidence\s*(?::|=)?\s*(100|[0-9]{1,2})%?\.?$",
    re.IGNORECASE,
)
VERSION_PATTERN = re.compile(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)")
MINIMUM_GEMINI_VERSION = (1, 1, 2)
IDENTITY_POLICY_REVISION = "pro-clients-2026-07-23-v3"
ROUTE_SEATS = {
    "claude-fable-5": "fable",
    "Gemini 3.1 Pro (High)": "gemini",
    "glm-5.2": "glm",
}
EXPECTED_EXECUTABLE_IDENTITIES = {
    "claude-fable-5": {
        "sha256": "59796dd18e9d77f1256f367db6d28ce4bd9cd5968e402ad3a327aac36abc6dec",
        "cdhash": "57f37e5659c14725f4e11dc77a96b6e7ba3a80ca",
        "team_identifier": "Q6L2SF6YDW",
        "designated_requirement": (
            'identifier "com.anthropic.claude-code" and anchor apple generic and '
            "certificate 1[field.1.2.840.113635.100.6.2.6] /* exists */ and "
            "certificate leaf[field.1.2.840.113635.100.6.1.13] /* exists */ and "
            "certificate leaf[subject.OU] = Q6L2SF6YDW"
        ),
    },
    "Gemini 3.1 Pro (High)": {
        "sha256": "6509d6ca54a66e3eaf61dfe35308ba1dfa1e6b552ef5c4f5f861562c6811ecaf",
        "cdhash": "d1ab6b43250ebdf79a8836804197495d39b9a5c1",
        "team_identifier": "EQHXZ8M8AV",
        "designated_requirement": (
            "identifier cli and anchor apple generic and certificate "
            "1[field.1.2.840.113635.100.6.2.6] /* exists */ and certificate "
            "leaf[field.1.2.840.113635.100.6.1.13] /* exists */ and "
            "certificate leaf[subject.OU] = EQHXZ8M8AV"
        ),
    },
    "glm-5.2": {
        "sha256": "59796dd18e9d77f1256f367db6d28ce4bd9cd5968e402ad3a327aac36abc6dec",
        "cdhash": "57f37e5659c14725f4e11dc77a96b6e7ba3a80ca",
        "team_identifier": "Q6L2SF6YDW",
        "designated_requirement": (
            'identifier "com.anthropic.claude-code" and anchor apple generic and '
            "certificate 1[field.1.2.840.113635.100.6.2.6] /* exists */ and "
            "certificate leaf[field.1.2.840.113635.100.6.1.13] /* exists */ and "
            "certificate leaf[subject.OU] = Q6L2SF6YDW"
        ),
    },
}
INVOCATION_KEYS = frozenset(
    {
        "argv",
        "argv_sha256",
        "client_version",
        "cwd_device",
        "cwd_initial_entries",
        "cwd_inode",
        "cwd_mode",
        "cwd_path",
        "cwd_proof_sha256",
        "cwd_removed_after_run",
        "descendants_absent_after_run",
        "ended_at_utc",
        "executable_cdhash",
        "executable_designated_requirement",
        "executable_identity_policy_revision",
        "executable_path",
        "executable_sha256",
        "executable_team_identifier",
        "exit_status",
        "home_path",
        "input_manifest_sha256",
        "launcher_invocation_uuid",
        "launcher_path",
        "launcher_sha256",
        "max_output_bytes",
        "output_spooled",
        "packet_sha256",
        "process_group_isolated",
        "provider_session_id",
        "raw_output_path",
        "reported_model",
        "requested_route",
        "route_config_path",
        "route_config_sha256",
        "review_input_bytes",
        "review_input_schema",
        "review_input_sha256",
        "schema",
        "seat",
        "shell",
        "started_at_utc",
        "stderr_bytes",
        "stderr_output_path",
        "stderr_sha256",
        "stdout_bytes",
        "stdout_sha256",
        "tools_denied",
        "wall_timeout_seconds",
        "xdg_cache_home",
        "xdg_config_home",
        "xdg_data_home",
        "xdg_state_home",
    }
)
FRONTMATTER_KEYS = frozenset(
    {
        "requested_route",
        "launcher_invocation_uuid",
        "provider_session_id",
        "reported_model",
        "input_manifest_sha256",
        "packet_sha256",
        "launcher_proof_sha256",
        "raw_response_sha256",
    }
)
PLACEHOLDER_VALUES = frozenset(
    {"", "...", "tbd", "todo", "n/a", "na", "placeholder", "coming soon"}
)


class ReviewValidationError(RuntimeError):
    """Raised when immutable review evidence fails closed."""


@dataclass(frozen=True)
class Finding:
    finding_id: str
    severity: str
    review_path: Path


@dataclass(frozen=True)
class ReviewProof:
    path: Path
    route: str
    launcher_uuid: str
    verdict: str
    findings: tuple[Finding, ...]


@dataclass(frozen=True)
class ArtifactBinding:
    path: Path
    label: str


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ReviewValidationError(f"missing or unreadable {label}: {path}") from exc


def _read_utf8(path: Path, label: str) -> str:
    payload = _read_bytes(path, label)
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReviewValidationError(f"{label} is not UTF-8: {path}") from exc


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and HEX_SHA256.fullmatch(value) is not None


def _require_sha256(value: object, label: str) -> str:
    if not _is_sha256(value):
        raise ReviewValidationError(f"invalid {label}")
    assert isinstance(value, str)
    return value


def _load_canonical_json(
    path: Path, label: str, *, newline: bool
) -> tuple[dict[str, Any], bytes]:
    payload = _read_bytes(path, label)
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewValidationError(f"{label} is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ReviewValidationError(f"{label} must be a JSON object: {path}")
    expected = canonical_json_bytes(value) + (b"\n" if newline else b"")
    if payload != expected:
        raise ReviewValidationError(f"{label} is not canonical JSON: {path}")
    return value, payload


def _git_inputs(
    *,
    repo_root: Path,
    source_ref: str,
    covered_paths: Sequence[str] | None,
    covered_set: str | None,
    instructions_path: str,
) -> tuple[InputSpec, ...]:
    try:
        return _inputs_from_args(
            repo_root=repo_root,
            source_ref=source_ref,
            covered=covered_paths,
            covered_set=covered_set,
            instructions=instructions_path,
        )
    except PacketError as exc:
        raise ReviewValidationError(
            f"cannot resolve committed review inputs: {exc}"
        ) from exc


def _committed_blob(
    repo_root: Path, commit: str, path: str, label: str
) -> tuple[str, bytes]:
    try:
        _, oid, content = _read_git_blob(repo_root, commit, path)
    except PacketError as exc:
        raise ReviewValidationError(f"invalid committed {label}: {exc}") from exc
    return oid, content


def _review_artifact_bindings(
    *,
    packet_path: Path,
    input_manifest_path: Path,
    freeze_receipt_path: Path,
    disposition_path: Path,
    review_paths: Sequence[Path],
) -> tuple[ArtifactBinding, ...]:
    bindings = [
        ArtifactBinding(packet_path, "review packet"),
        ArtifactBinding(input_manifest_path, "input manifest"),
        ArtifactBinding(freeze_receipt_path, "freeze receipt"),
        ArtifactBinding(disposition_path, "finding disposition"),
    ]
    for review_path in review_paths:
        bindings.extend(
            (
                ArtifactBinding(review_path, "normalized review"),
                ArtifactBinding(_raw_companion(review_path), "raw response companion"),
                ArtifactBinding(
                    review_path.with_suffix(".stderr.bin"),
                    "raw stderr companion",
                ),
                ArtifactBinding(
                    review_path.with_suffix(".invocation.json"),
                    "invocation companion",
                ),
            )
        )
    return tuple(bindings)


def _validate_h1_artifact_bindings(
    bindings: Sequence[ArtifactBinding],
    *,
    repo_root: Path,
    h1_head: str,
) -> None:
    resolved_repo = repo_root.resolve()
    for binding in bindings:
        try:
            resolved_path = binding.path.resolve(strict=True)
        except OSError as exc:
            raise ReviewValidationError(
                f"missing or unreadable {binding.label}: {binding.path}"
            ) from exc
        try:
            relative_path = resolved_path.relative_to(resolved_repo).as_posix()
        except ValueError as exc:
            raise ReviewValidationError(
                f"{binding.label} must resolve inside --repo: {binding.path}"
            ) from exc
        try:
            _validate_repo_path(relative_path)
        except PacketError as exc:
            raise ReviewValidationError(
                f"{binding.label} has an invalid repository path: {binding.path}"
            ) from exc
        _, committed_bytes = _committed_blob(
            resolved_repo,
            h1_head,
            relative_path,
            f"H1 {binding.label}",
        )
        if _read_bytes(resolved_path, binding.label) != committed_bytes:
            raise ReviewValidationError(
                f"{binding.label} does not match its exact committed H1 Git blob: "
                f"{relative_path}"
            )


def _validate_receipt_blob(
    receipt: Mapping[str, Any],
    *,
    repo_root: Path,
    h0_head: str,
    prefix: str,
    expected_path: str,
) -> bytes:
    path = receipt.get(f"{prefix}_path")
    if path != expected_path:
        raise ReviewValidationError(f"freeze receipt {prefix}_path mismatch")
    oid, content = _committed_blob(repo_root, h0_head, expected_path, prefix)
    if receipt.get(f"{prefix}_git_blob_oid") != oid:
        raise ReviewValidationError(f"freeze receipt {prefix}_git_blob_oid mismatch")
    if receipt.get(f"{prefix}_sha256") != sha256_bytes(content):
        raise ReviewValidationError(f"freeze receipt {prefix}_sha256 mismatch")
    return content


def _validate_freeze_receipt(
    receipt: Mapping[str, Any],
    *,
    repo_root: Path,
    h0_head: str,
    h0_tree: str,
    manifest_sha256: str,
    packet_sha256: str,
    packet_bytes: int,
    executing_validator_path: Path,
) -> None:
    if receipt.get("schema") != FREEZE_RECEIPT_SCHEMA:
        raise ReviewValidationError("freeze receipt schema mismatch")
    if receipt.get("source_head") != h0_head:
        raise ReviewValidationError("freeze receipt source_head mismatch")
    if receipt.get("source_tree") != h0_tree:
        raise ReviewValidationError("freeze receipt source_tree mismatch")
    if receipt.get("git_object_validation") != "pass":
        raise ReviewValidationError(
            "freeze receipt lacks passing Git-object validation"
        )
    if receipt.get("input_manifest_sha256") != manifest_sha256:
        raise ReviewValidationError("freeze receipt input_manifest_sha256 mismatch")
    if receipt.get("packet_sha256") != packet_sha256:
        raise ReviewValidationError("freeze receipt packet_sha256 mismatch")
    if receipt.get("packet_bytes") != packet_bytes:
        raise ReviewValidationError("freeze receipt packet_bytes mismatch")
    for field in ("packet_inode", "packet_device"):
        value = receipt.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ReviewValidationError(f"freeze receipt {field} is invalid")
    built_at = _validate_iso_timestamp(receipt.get("built_at_utc"), "built_at_utc")
    if built_at.utcoffset() is None or built_at.utcoffset().total_seconds() != 0:
        raise ReviewValidationError("freeze receipt built_at_utc must be UTC")
    if receipt.get("tracked_status_sha256") != sha256_bytes(b""):
        raise ReviewValidationError("freeze receipt tracked_status_sha256 is not clean")

    base_commit = receipt.get("base_commit")
    upstream_commit = receipt.get("upstream_commit")
    if not isinstance(base_commit, str):
        raise ReviewValidationError("freeze receipt base_commit is invalid")
    if not isinstance(upstream_commit, str):
        raise ReviewValidationError("freeze receipt upstream_commit is invalid")
    try:
        resolved_base = _resolve_commit(repo_root, base_commit)
        resolved_upstream = _resolve_commit(repo_root, upstream_commit)
        actual_base_output = _git(
            repo_root, "merge-base", h0_head, resolved_upstream, text=True
        )
        assert isinstance(actual_base_output, str)
        actual_base = actual_base_output.strip()
    except PacketError as exc:
        raise ReviewValidationError(
            "freeze receipt base/upstream provenance is invalid"
        ) from exc
    if actual_base != resolved_base:
        raise ReviewValidationError(
            "freeze receipt base_commit is not merge-base(H0, upstream_commit)"
        )

    generator = _validate_receipt_blob(
        receipt,
        repo_root=repo_root,
        h0_head=h0_head,
        prefix="generator",
        expected_path=DEFAULT_GENERATOR_PATH,
    )
    if not isinstance(receipt.get("generator_version"), str) or _is_placeholder(
        str(receipt.get("generator_version"))
    ):
        raise ReviewValidationError("freeze receipt generator_version is invalid")
    if receipt.get("generator_sha256") != sha256_bytes(generator):
        raise ReviewValidationError("freeze receipt generator provenance mismatch")
    _validate_receipt_blob(
        receipt,
        repo_root=repo_root,
        h0_head=h0_head,
        prefix="route_config",
        expected_path=DEFAULT_ROUTE_CONFIG_PATH,
    )
    _validate_receipt_blob(
        receipt,
        repo_root=repo_root,
        h0_head=h0_head,
        prefix="launcher",
        expected_path=LAUNCHER_REPO_PATH,
    )
    validator_bytes = _validate_receipt_blob(
        receipt,
        repo_root=repo_root,
        h0_head=h0_head,
        prefix="validator",
        expected_path=VALIDATOR_REPO_PATH,
    )
    if _read_bytes(executing_validator_path, "executing validator") != validator_bytes:
        raise ReviewValidationError(
            "executing validator does not match freeze receipt validator_sha256"
        )


def _validate_packet_projection(
    *,
    repo_root: Path,
    h0_ref: str,
    h1_ref: str,
    covered_paths: Sequence[str] | None,
    covered_set: str | None,
    instructions_path: str,
    packet_path: Path,
    input_manifest_path: Path,
    freeze_receipt_path: Path,
    executing_validator_path: Path,
) -> tuple[str, str, Mapping[str, Any], str]:
    repo_root = repo_root.resolve()
    packet_bytes = _read_bytes(packet_path, "review packet")
    try:
        parsed = parse_packet(packet_bytes)
    except PacketError as exc:
        raise ReviewValidationError(f"invalid review packet: {exc}") from exc

    manifest, manifest_bytes = _load_canonical_json(
        input_manifest_path,
        "input manifest",
        newline=False,
    )
    copied_projection = sha256_bytes(manifest_bytes)
    if manifest != parsed.manifest or copied_projection != parsed.manifest_sha256:
        raise ReviewValidationError(
            "materialized input manifest differs from the immutable H0 packet"
        )

    receipt, _ = _load_canonical_json(
        freeze_receipt_path,
        "freeze receipt",
        newline=True,
    )
    try:
        h0_head = _resolve_commit(repo_root, h0_ref)
        h1_head = _resolve_commit(repo_root, h1_ref)
        _git(repo_root, "merge-base", "--is-ancestor", h0_head, h1_head)
        h0_inputs = _git_inputs(
            repo_root=repo_root,
            source_ref=h0_head,
            covered_paths=covered_paths,
            covered_set=covered_set,
            instructions_path=instructions_path,
        )
        h1_inputs = _git_inputs(
            repo_root=repo_root,
            source_ref=h1_head,
            covered_paths=covered_paths,
            covered_set=covered_set,
            instructions_path=instructions_path,
        )
        h0_built = build_projection_from_git(
            repo_root=repo_root,
            source_ref=h0_head,
            inputs=h0_inputs,
        )
        h1_built = build_projection_from_git(
            repo_root=repo_root,
            source_ref=h1_head,
            inputs=h1_inputs,
        )
    except PacketError as exc:
        raise ReviewValidationError(
            f"cannot regenerate committed projection: {exc}"
        ) from exc

    if (
        h0_built.manifest_bytes != manifest_bytes
        or h0_built.packet_bytes != packet_bytes
    ):
        raise ReviewValidationError(
            "regenerated projection(H0) differs from the immutable packet"
        )
    if h1_built.manifest_bytes != h0_built.manifest_bytes:
        raise ReviewValidationError(
            "projection(H1) != projection(H0): committed covered bytes differ"
        )
    _validate_freeze_receipt(
        receipt,
        repo_root=repo_root,
        h0_head=h0_head,
        h0_tree=_tree_oid(repo_root, h0_head),
        manifest_sha256=h0_built.manifest_sha256,
        packet_sha256=h0_built.packet_sha256,
        packet_bytes=len(packet_bytes),
        executing_validator_path=executing_validator_path,
    )
    return h0_built.manifest_sha256, h0_built.packet_sha256, receipt, h1_head


def _parse_frontmatter(text: str, path: Path) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        raise ReviewValidationError(
            f"review lacks machine-generated YAML front matter: {path}"
        )
    end = text.find("---\n", 4)
    if end < 0:
        raise ReviewValidationError(f"review front matter is not terminated: {path}")
    raw_frontmatter = text[4:end]
    body = text[end + 4 :]
    values: dict[str, object] = {}
    for line in raw_frontmatter.splitlines():
        if not line or ":" not in line:
            raise ReviewValidationError(f"invalid review front matter line in {path}")
        key, raw_value = line.split(":", 1)
        if key in values or key.strip() != key or not key:
            raise ReviewValidationError(
                f"duplicate or invalid review front matter key in {path}"
            )
        value = raw_value.strip()
        values[key] = None if value == "null" else value
    if set(values) != FRONTMATTER_KEYS:
        raise ReviewValidationError(f"review front matter has the wrong fields: {path}")
    return values, body


def _section_map(body: str, path: Path) -> dict[str, str]:
    matches = list(re.finditer(r"^# [^\n]+$", body, flags=re.MULTILINE))
    headings = tuple(match.group(0) for match in matches)
    if len(headings) != len(EXPECTED_HEADINGS):
        raise ReviewValidationError(
            f"review must contain exactly six level-one headings: {path}"
        )
    if headings != EXPECTED_HEADINGS:
        raise ReviewValidationError(
            f"review heading order or spelling is invalid: {path}"
        )
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[match.group(0)] = body[start:end].strip()
    return sections


def _is_placeholder(text: str) -> bool:
    normalized = text.strip().lower().rstrip(".")
    return normalized in PLACEHOLDER_VALUES or "<placeholder" in normalized


def _validate_verdict(
    verdict_body: str,
    *,
    manifest_sha256: str,
    packet_sha256: str,
    path: Path,
) -> str:
    lines = [line.strip() for line in verdict_body.splitlines() if line.strip()]
    if not lines:
        raise ReviewValidationError(f"empty verdict body: {path}")
    verdict_line = lines[0].replace("**", "").replace("__", "").strip()
    match = VERDICT.fullmatch(verdict_line)
    if match is None:
        raise ReviewValidationError(f"invalid verdict enum or confidence: {path}")
    verdict = match.group(1).upper()
    manifest_lines = [
        line for line in lines if line.startswith("input_manifest_sha256:")
    ]
    expected_line = f"input_manifest_sha256: {manifest_sha256}"
    if manifest_lines != [expected_line]:
        raise ReviewValidationError(
            f"reviewer must repeat only input_manifest_sha256, never packet SHA: {path}"
        )
    if "packet_sha256" in verdict_body or packet_sha256 in verdict_body:
        raise ReviewValidationError(
            f"reviewer must repeat only input_manifest_sha256, never packet SHA: {path}"
        )
    return verdict


def _findings_from_section(
    section: str,
    *,
    severity: str,
    path: Path,
) -> tuple[Finding, ...]:
    if section == "None":
        return ()
    if _is_placeholder(section):
        raise ReviewValidationError(
            f"placeholder content under {severity} findings: {path}"
        )
    identifiers = FINDING_ID.findall(section)
    if not identifiers:
        raise ReviewValidationError(
            f"every non-None {severity} finding needs a stable unique [FINDING-ID]: {path}"
        )
    if len(identifiers) != len(set(identifiers)):
        raise ReviewValidationError(f"duplicate finding ID within review: {path}")
    return tuple(Finding(identifier, severity, path) for identifier in identifiers)


def _raw_companion(review_path: Path) -> Path:
    candidates = (
        review_path.with_suffix(".raw.json"),
        review_path.with_suffix(".raw.txt"),
    )
    existing = tuple(path for path in candidates if path.is_file())
    if len(existing) != 1:
        raise ReviewValidationError(
            f"review needs exactly one raw response companion: {review_path}"
        )
    return existing[0]


def _emitted_string(
    envelope: Mapping[str, Any], field: str, raw_path: Path
) -> str | None:
    if field not in envelope or envelope[field] is None:
        return None
    value = envelope[field]
    if not isinstance(value, str) or _is_placeholder(value):
        raise ReviewValidationError(
            f"raw provider field {field} is invalid: {raw_path}"
        )
    return value


def _extract_raw_proof(
    raw_path: Path, raw_bytes: bytes, requested_route: str
) -> tuple[str, str | None, str | None]:
    if raw_path.suffix == ".txt":
        try:
            return raw_bytes.decode("utf-8"), None, None
        except UnicodeDecodeError as exc:
            raise ReviewValidationError(
                f"raw response is not UTF-8: {raw_path}"
            ) from exc
    try:
        envelope = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewValidationError(
            f"raw JSON response is invalid: {raw_path}"
        ) from exc
    if not isinstance(envelope, dict) or not isinstance(envelope.get("result"), str):
        raise ReviewValidationError(
            f"raw JSON response lacks string result: {raw_path}"
        )
    provider_session_id = _emitted_string(envelope, "session_id", raw_path)
    reported_model = _emitted_string(envelope, "model", raw_path)
    if "modelUsage" in envelope:
        model_usage = envelope["modelUsage"]
        if not isinstance(model_usage, dict) or not all(
            isinstance(model, str) and model and isinstance(usage, dict)
            for model, usage in model_usage.items()
        ):
            raise ReviewValidationError(
                f"raw provider modelUsage is invalid: {raw_path}"
            )
        emitted_model: str | None
        if requested_route in model_usage:
            emitted_model = requested_route
        elif len(model_usage) == 1:
            emitted_model = next(iter(model_usage))
        elif model_usage:
            raise ReviewValidationError(
                f"raw provider modelUsage is ambiguous for requested route: {raw_path}"
            )
        else:
            emitted_model = None
        if (
            reported_model is not None
            and emitted_model is not None
            and reported_model != emitted_model
        ):
            raise ReviewValidationError(
                f"raw provider model fields disagree: {raw_path}"
            )
        reported_model = reported_model or emitted_model
    return envelope["result"], provider_session_id, reported_model


def _expected_argv(route: str) -> list[str]:
    executable = (
        GEMINI_EXECUTABLE if route == "Gemini 3.1 Pro (High)" else CLAUDE_EXECUTABLE
    )
    if route == "Gemini 3.1 Pro (High)":
        return [
            executable,
            "--mode",
            "plan",
            "--sandbox",
            "--print-timeout",
            "15m",
            "--model",
            "Gemini 3.1 Pro (High)",
        ]
    model = "claude-fable-5" if route == "claude-fable-5" else "glm-5.2"
    effort = "xhigh" if route == "claude-fable-5" else "high"
    permission_mode = "plan" if route == "claude-fable-5" else "dontAsk"
    return [
        executable,
        "--print",
        "--model",
        model,
        "--effort",
        effort,
        "--output-format",
        "json",
        "--no-session-persistence",
        "--safe-mode",
        "--permission-mode",
        permission_mode,
        "--tools",
        "",
        "--disable-slash-commands",
        "--strict-mcp-config",
        "--mcp-config",
        MCP_CONFIG,
    ]


def _validate_iso_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ReviewValidationError(f"invalid invocation {label}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ReviewValidationError(f"invalid invocation {label}") from exc
    if parsed.tzinfo is None:
        raise ReviewValidationError(f"invocation {label} must include UTC offset")
    return parsed


def _validate_invocation(
    *,
    repo_root: Path,
    review_path: Path,
    frontmatter: Mapping[str, object],
    raw_path: Path,
    raw_bytes: bytes,
    manifest_sha256: str,
    packet_bytes: bytes,
    packet_sha256: str,
    freeze_receipt: Mapping[str, Any],
    emitted_provider_session_id: str | None,
    emitted_reported_model: str | None,
) -> tuple[str, str]:
    invocation_path = review_path.with_suffix(".invocation.json")
    if not invocation_path.is_file():
        raise ReviewValidationError(f"missing invocation companion: {invocation_path}")
    invocation, invocation_bytes = _load_canonical_json(
        invocation_path,
        "invocation companion",
        newline=True,
    )
    if set(invocation) != INVOCATION_KEYS:
        raise ReviewValidationError(
            f"invocation companion has the wrong exact schema fields: {invocation_path}"
        )
    if invocation.get("schema") != INVOCATION_SCHEMA:
        raise ReviewValidationError(f"invocation schema mismatch: {invocation_path}")
    route = invocation.get("requested_route")
    if not isinstance(route, str) or route not in EXPECTED_ROUTES:
        raise ReviewValidationError(f"invalid requested_route in {invocation_path}")
    if frontmatter.get("requested_route") != route:
        raise ReviewValidationError(
            f"normalized requested_route differs from invocation: {review_path}"
        )

    launcher_uuid = invocation.get("launcher_invocation_uuid")
    if not isinstance(launcher_uuid, str):
        raise ReviewValidationError(
            f"missing launcher_invocation_uuid: {invocation_path}"
        )
    try:
        parsed_uuid = uuid.UUID(launcher_uuid)
    except ValueError as exc:
        raise ReviewValidationError(
            f"invalid launcher_invocation_uuid: {invocation_path}"
        ) from exc
    if str(parsed_uuid) != launcher_uuid:
        raise ReviewValidationError(
            f"launcher_invocation_uuid is not canonical: {invocation_path}"
        )
    if frontmatter.get("launcher_invocation_uuid") != launcher_uuid:
        raise ReviewValidationError(
            f"normalized launcher UUID differs from invocation: {review_path}"
        )

    emitted_values = {
        "provider_session_id": emitted_provider_session_id,
        "reported_model": emitted_reported_model,
    }
    for field, emitted_value in emitted_values.items():
        value = invocation.get(field)
        if value is not None and (not isinstance(value, str) or _is_placeholder(value)):
            raise ReviewValidationError(
                f"invalid nullable invocation field {field}: {invocation_path}"
            )
        if frontmatter.get(field) != value:
            raise ReviewValidationError(
                f"normalized {field} differs from invocation: {review_path}"
            )
        if value != emitted_value:
            raise ReviewValidationError(
                f"invocation {field} does not match provider-emitted raw JSON: {raw_path}"
            )

    if invocation.get("input_manifest_sha256") != manifest_sha256:
        raise ReviewValidationError(
            f"invocation input_manifest_sha256 mismatch: {invocation_path}"
        )
    if invocation.get("packet_sha256") != packet_sha256:
        raise ReviewValidationError(
            f"invocation packet_sha256 mismatch: {invocation_path}"
        )
    expected_review_input = b"".join(
        (
            REVIEW_INPUT_MAGIC,
            f"schema: {REVIEW_INPUT_SCHEMA}\n".encode("ascii"),
            f"input_manifest_sha256: {manifest_sha256}\n".encode("ascii"),
            f"packet_bytes: {len(packet_bytes)}\n".encode("ascii"),
            b"\n",
            packet_bytes,
        )
    )
    if (
        invocation.get("review_input_schema") != REVIEW_INPUT_SCHEMA
        or invocation.get("review_input_bytes") != len(expected_review_input)
        or invocation.get("review_input_sha256")
        != sha256_bytes(expected_review_input)
    ):
        raise ReviewValidationError(
            f"invocation review-input attestation mismatch: {invocation_path}"
        )
    if frontmatter.get("input_manifest_sha256") != manifest_sha256:
        raise ReviewValidationError(
            f"normalized input_manifest_sha256 mismatch: {review_path}"
        )
    if frontmatter.get("packet_sha256") != packet_sha256:
        raise ReviewValidationError(f"normalized packet_sha256 mismatch: {review_path}")
    if frontmatter.get("launcher_proof_sha256") != sha256_bytes(invocation_bytes):
        raise ReviewValidationError(f"launcher proof SHA-256 mismatch: {review_path}")

    expected_launcher_sha = _require_sha256(
        freeze_receipt.get("launcher_sha256"), "freeze receipt launcher_sha256"
    )
    if invocation.get("launcher_sha256") != expected_launcher_sha:
        raise ReviewValidationError(
            f"invocation launcher_sha256 mismatch: {invocation_path}"
        )
    launcher_path = invocation.get("launcher_path")
    expected_launcher_path = (repo_root / LAUNCHER_REPO_PATH).resolve()
    if (
        not isinstance(launcher_path, str)
        or not Path(launcher_path).is_absolute()
        or Path(launcher_path).resolve() != expected_launcher_path
    ):
        raise ReviewValidationError(
            f"invocation launcher_path mismatch: {invocation_path}"
        )

    expected_seat = ROUTE_SEATS[route]
    if invocation.get("seat") != expected_seat:
        raise ReviewValidationError(
            f"invocation seat/name mismatch for {route}: {invocation_path}"
        )

    expected_executable = (
        GEMINI_EXECUTABLE if route == "Gemini 3.1 Pro (High)" else CLAUDE_EXECUTABLE
    )
    if invocation.get("executable_path") != expected_executable:
        raise ReviewValidationError(
            f"invocation executable_path is not canonical: {invocation_path}"
        )
    expected_identity = EXPECTED_EXECUTABLE_IDENTITIES[route]
    identity_fields = {
        "executable_sha256": expected_identity["sha256"],
        "executable_cdhash": expected_identity["cdhash"],
        "executable_team_identifier": expected_identity["team_identifier"],
        "executable_designated_requirement": expected_identity[
            "designated_requirement"
        ],
        "executable_identity_policy_revision": IDENTITY_POLICY_REVISION,
    }
    for field, expected_value in identity_fields.items():
        if invocation.get(field) != expected_value:
            raise ReviewValidationError(
                f"invocation {field} mismatch: {invocation_path}"
            )
    version = invocation.get("client_version")
    if not isinstance(version, str) or _is_placeholder(version):
        raise ReviewValidationError(
            f"invocation client_version is missing: {invocation_path}"
        )
    if route == "Gemini 3.1 Pro (High)":
        version_match = VERSION_PATTERN.search(version)
        if (
            version_match is None
            or tuple(int(component) for component in version_match.groups())
            < MINIMUM_GEMINI_VERSION
        ):
            raise ReviewValidationError(
                f"Gemini client version must be at least 1.1.2: {invocation_path}"
            )

    argv = invocation.get("argv")
    expected_argv = _expected_argv(route)
    if argv != expected_argv:
        raise ReviewValidationError(
            f"invocation argv is not canonical: {invocation_path}"
        )
    if invocation.get("argv_sha256") != sha256_bytes(canonical_json_bytes(argv)):
        raise ReviewValidationError(
            f"invocation argv_sha256 mismatch: {invocation_path}"
        )

    route_config_path = invocation.get("route_config_path")
    route_config_sha = invocation.get("route_config_sha256")
    if route == "glm-5.2":
        if (
            not isinstance(route_config_path, str)
            or Path(route_config_path).name != "glm-5.2-v1.json"
        ):
            raise ReviewValidationError(
                f"GLM route_config_path is not canonical: {invocation_path}"
            )
        if route_config_sha != freeze_receipt.get("route_config_sha256"):
            raise ReviewValidationError(
                f"GLM route_config_sha256 mismatch: {invocation_path}"
            )
    elif route_config_path is not None or route_config_sha is not None:
        raise ReviewValidationError(
            f"non-GLM invocation must not declare route config: {invocation_path}"
        )

    cwd_path = invocation.get("cwd_path")
    if not isinstance(cwd_path, str) or not Path(cwd_path).is_absolute():
        raise ReviewValidationError(
            f"invocation cwd_path must be absolute: {invocation_path}"
        )
    if invocation.get("cwd_initial_entries") != []:
        raise ReviewValidationError(
            f"invocation lacks empty cwd proof: {invocation_path}"
        )
    if invocation.get("cwd_mode") != "0700":
        raise ReviewValidationError(
            f"invocation cwd mode must be 0700: {invocation_path}"
        )
    if (
        not isinstance(invocation.get("cwd_inode"), int)
        or not isinstance(invocation.get("cwd_device"), int)
        or invocation["cwd_inode"] < 0
        or invocation["cwd_device"] < 0
    ):
        raise ReviewValidationError(
            f"invocation cwd inode/device proof is invalid: {invocation_path}"
        )
    if isinstance(invocation.get("cwd_inode"), bool) or isinstance(
        invocation.get("cwd_device"), bool
    ):
        raise ReviewValidationError(
            f"invocation cwd inode/device proof is invalid: {invocation_path}"
        )
    cwd_proof = {
        "device": invocation["cwd_device"],
        "initial_entries": invocation["cwd_initial_entries"],
        "inode": invocation["cwd_inode"],
        "mode": invocation["cwd_mode"],
        "path": invocation["cwd_path"],
    }
    if invocation.get("cwd_proof_sha256") != sha256_bytes(
        canonical_json_bytes(cwd_proof)
    ):
        raise ReviewValidationError(
            f"invocation cwd_proof_sha256 mismatch: {invocation_path}"
        )
    if invocation.get("cwd_removed_after_run") is not True:
        raise ReviewValidationError(
            f"invocation lacks cwd cleanup proof: {invocation_path}"
        )
    for field in (
        "descendants_absent_after_run",
        "output_spooled",
        "process_group_isolated",
    ):
        if invocation.get(field) is not True:
            raise ReviewValidationError(
                f"invocation {field} must be true: {invocation_path}"
            )
    for field in (
        "home_path",
        "xdg_cache_home",
        "xdg_config_home",
        "xdg_data_home",
        "xdg_state_home",
    ):
        if invocation.get(field) != cwd_path:
            raise ReviewValidationError(
                f"invocation {field} must equal cwd_path: {invocation_path}"
            )
    max_output_bytes = invocation.get("max_output_bytes")
    if (
        not isinstance(max_output_bytes, int)
        or isinstance(max_output_bytes, bool)
        or max_output_bytes <= 0
    ):
        raise ReviewValidationError(
            f"invocation max_output_bytes is invalid: {invocation_path}"
        )
    wall_timeout_seconds = invocation.get("wall_timeout_seconds")
    if (
        not isinstance(wall_timeout_seconds, (int, float))
        or isinstance(wall_timeout_seconds, bool)
        or wall_timeout_seconds <= 0
    ):
        raise ReviewValidationError(
            f"invocation wall_timeout_seconds is invalid: {invocation_path}"
        )
    if invocation.get("tools_denied") is not True:
        raise ReviewValidationError(
            f"invocation must prove tools denied: {invocation_path}"
        )
    if invocation.get("shell") is not False:
        raise ReviewValidationError(
            f"invocation must prove shell=false: {invocation_path}"
        )
    if invocation.get("exit_status") != 0:
        raise ReviewValidationError(
            f"invocation exit status is nonzero: {invocation_path}"
        )

    started = _validate_iso_timestamp(
        invocation.get("started_at_utc"), "started_at_utc"
    )
    ended = _validate_iso_timestamp(invocation.get("ended_at_utc"), "ended_at_utc")
    if ended < started:
        raise ReviewValidationError(f"invocation end precedes start: {invocation_path}")
    if (
        started.utcoffset() is None
        or ended.utcoffset() is None
        or started.utcoffset().total_seconds() != 0
        or ended.utcoffset().total_seconds() != 0
    ):
        raise ReviewValidationError(
            f"invocation timestamps must be UTC: {invocation_path}"
        )

    raw_sha = sha256_bytes(raw_bytes)
    if invocation.get("stdout_sha256") != raw_sha:
        raise ReviewValidationError(
            f"raw response SHA-256 differs from stdout receipt: {raw_path}"
        )
    if invocation.get("stdout_bytes") != len(raw_bytes):
        raise ReviewValidationError(
            f"raw response byte count differs from stdout receipt: {raw_path}"
        )
    if frontmatter.get("raw_response_sha256") != raw_sha:
        raise ReviewValidationError(f"raw response SHA-256 mismatch: {review_path}")
    raw_output_path = invocation.get("raw_output_path")
    if (
        not isinstance(raw_output_path, str)
        or Path(raw_output_path).name != raw_path.name
    ):
        raise ReviewValidationError(
            f"invocation raw_output_path mismatch: {invocation_path}"
        )
    stderr_sha256 = _require_sha256(
        invocation.get("stderr_sha256"),
        "invocation stderr_sha256",
    )
    stderr_bytes = invocation.get("stderr_bytes")
    if not isinstance(stderr_bytes, int) or stderr_bytes < 0:
        raise ReviewValidationError(
            f"invocation stderr_bytes is invalid: {invocation_path}"
        )
    stderr_output_path = invocation.get("stderr_output_path")
    expected_stderr_path = review_path.with_suffix(".stderr.bin")
    if (
        not isinstance(stderr_output_path, str)
        or Path(stderr_output_path).name != expected_stderr_path.name
    ):
        raise ReviewValidationError(
            f"invocation stderr_output_path mismatch: {invocation_path}"
        )
    stderr_payload = _read_bytes(expected_stderr_path, "raw stderr companion")
    if len(stderr_payload) != stderr_bytes:
        raise ReviewValidationError(
            f"raw stderr byte count mismatch: {expected_stderr_path}"
        )
    if sha256_bytes(stderr_payload) != stderr_sha256:
        raise ReviewValidationError(
            f"raw stderr SHA-256 mismatch: {expected_stderr_path}"
        )
    return route, launcher_uuid


def _validate_review(
    review_path: Path,
    *,
    repo_root: Path,
    manifest_sha256: str,
    packet_bytes: bytes,
    packet_sha256: str,
    freeze_receipt: Mapping[str, Any],
) -> ReviewProof:
    text = _read_utf8(review_path, "normalized review")
    frontmatter, body = _parse_frontmatter(text, review_path)
    sections = _section_map(body, review_path)
    for heading, section in sections.items():
        if heading not in {
            "# Blocking findings",
            "# Important findings",
        } and _is_placeholder(section):
            raise ReviewValidationError(
                f"placeholder content under {heading}: {review_path}"
            )
    verdict = _validate_verdict(
        sections["# Verdict"],
        manifest_sha256=manifest_sha256,
        packet_sha256=packet_sha256,
        path=review_path,
    )
    findings = _findings_from_section(
        sections["# Blocking findings"],
        severity="Blocking",
        path=review_path,
    ) + _findings_from_section(
        sections["# Important findings"],
        severity="Important",
        path=review_path,
    )

    raw_path = _raw_companion(review_path)
    raw_bytes = _read_bytes(raw_path, "raw response companion")
    frontmatter_route = frontmatter.get("requested_route")
    if (
        not isinstance(frontmatter_route, str)
        or frontmatter_route not in EXPECTED_ROUTES
    ):
        raise ReviewValidationError(
            f"normalized review has invalid requested_route: {review_path}"
        )
    raw_body, emitted_provider_session_id, emitted_reported_model = _extract_raw_proof(
        raw_path, raw_bytes, frontmatter_route
    )
    route, launcher_uuid = _validate_invocation(
        repo_root=repo_root,
        review_path=review_path,
        frontmatter=frontmatter,
        raw_path=raw_path,
        raw_bytes=raw_bytes,
        manifest_sha256=manifest_sha256,
        packet_bytes=packet_bytes,
        packet_sha256=packet_sha256,
        freeze_receipt=freeze_receipt,
        emitted_provider_session_id=emitted_provider_session_id,
        emitted_reported_model=emitted_reported_model,
    )
    if raw_body != body:
        raise ReviewValidationError(
            f"normalized review does not preserve the unedited raw model body: {review_path}"
        )
    return ReviewProof(review_path, route, launcher_uuid, verdict, findings)


def _parse_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _validate_evidence_reference(
    reference: str, *, repo_root: Path, h1_head: str, finding_id: str
) -> None:
    match = EVIDENCE_REFERENCE.fullmatch(reference)
    if match is None:
        raise ReviewValidationError(
            f"disposition finding {finding_id} lacks a concrete evidence reference"
        )
    path = match.group("artifact_path") or match.group("test_path")
    assert path is not None
    try:
        _validate_repo_path(path)
    except PacketError as exc:
        raise ReviewValidationError(
            f"disposition finding {finding_id} has an invalid evidence path"
        ) from exc
    _, content = _committed_blob(repo_root, h1_head, path, "disposition evidence")
    artifact_sha = match.group("artifact_sha")
    if artifact_sha is not None and sha256_bytes(content) != artifact_sha:
        raise ReviewValidationError(
            f"disposition finding {finding_id} artifact evidence SHA-256 mismatch"
        )
    test_symbol = match.group("test_symbol")
    if test_symbol is not None and test_symbol.encode("utf-8") not in content:
        raise ReviewValidationError(
            f"disposition finding {finding_id} test evidence symbol is absent at H1"
        )


def _validate_disposition_evidence(
    *,
    decision: str,
    evidence: str,
    repo_root: Path,
    h1_head: str,
    finding_id: str,
) -> None:
    grammar = ACCEPTED_EVIDENCE if decision == "accepted" else REJECTED_EVIDENCE
    match = grammar.fullmatch(evidence)
    if match is None:
        kind = (
            "evidence and resolution"
            if decision == "accepted"
            else ("falsification evidence, rationale, and resolution")
        )
        raise ReviewValidationError(
            f"disposition finding {finding_id} lacks deterministic {kind}"
        )
    for field in ("resolution", "rationale"):
        value = match.groupdict().get(field)
        if value is not None and (_is_placeholder(value) or len(value.strip()) < 8):
            raise ReviewValidationError(
                f"disposition finding {finding_id} has placeholder {field}"
            )
    _validate_evidence_reference(
        match.group("reference"),
        repo_root=repo_root,
        h1_head=h1_head,
        finding_id=finding_id,
    )


def _validate_owning_commit(
    owning_commit: str, *, repo_root: Path, h1_head: str, finding_id: str
) -> None:
    if COMMIT_ID.fullmatch(owning_commit) is None:
        raise ReviewValidationError(
            f"disposition finding {finding_id} lacks a resolved owning commit"
        )
    try:
        resolved = _resolve_commit(repo_root, owning_commit)
        _git(repo_root, "merge-base", "--is-ancestor", resolved, h1_head)
    except PacketError as exc:
        raise ReviewValidationError(
            f"disposition finding {finding_id} owning commit does not exist or is not an ancestor of H1"
        ) from exc


def _validate_disposition(
    disposition_path: Path,
    findings: Sequence[Finding],
    *,
    repo_root: Path,
    h1_head: str,
) -> None:
    text = _read_utf8(disposition_path, "finding disposition")
    lines = text.splitlines()
    expected_header = [
        "Finding ID",
        "Severity",
        "Decision",
        "Evidence",
        "Owning commit",
        "Rereview status",
    ]
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if _parse_table_row(line) == expected_header
        ),
        None,
    )
    if header_index is None or header_index + 1 >= len(lines):
        raise ReviewValidationError("disposition lacks the canonical finding table")
    separator = _parse_table_row(lines[header_index + 1])
    if len(separator) != len(expected_header) or any(
        re.fullmatch(r":?-{3,}:?", cell) is None for cell in separator
    ):
        raise ReviewValidationError("disposition table separator is invalid")

    expected = {finding.finding_id: finding for finding in findings}
    rows: dict[str, list[str]] = {}
    for line in lines[header_index + 2 :]:
        if not line.strip().startswith("|"):
            continue
        cells = _parse_table_row(line)
        if len(cells) != len(expected_header):
            raise ReviewValidationError("disposition row has the wrong column count")
        finding_id = cells[0].strip("[]")
        if finding_id in rows:
            raise ReviewValidationError(
                f"duplicate disposition finding ID: {finding_id}"
            )
        rows[finding_id] = cells

    actual_ids = set(rows)
    expected_ids = set(expected)
    missing = expected_ids - actual_ids
    extra = actual_ids - expected_ids
    if missing:
        raise ReviewValidationError(
            f"missing disposition finding IDs: {', '.join(sorted(missing))}"
        )
    if extra:
        raise ReviewValidationError(
            f"extra disposition finding IDs: {', '.join(sorted(extra))}"
        )

    for finding_id, cells in rows.items():
        finding = expected[finding_id]
        _, severity, decision, evidence, owning_commit, rereview_status = cells
        if severity != finding.severity:
            raise ReviewValidationError(
                f"disposition severity mismatch for {finding_id}"
            )
        if decision not in {"accepted", "rejected"}:
            raise ReviewValidationError(
                f"disposition finding {finding_id} is not resolved"
            )
        _validate_disposition_evidence(
            decision=decision,
            evidence=evidence,
            repo_root=repo_root,
            h1_head=h1_head,
            finding_id=finding_id,
        )
        _validate_owning_commit(
            owning_commit,
            repo_root=repo_root,
            h1_head=h1_head,
            finding_id=finding_id,
        )
        if rereview_status not in {"resolved", "closed", "rereviewed-pass", "verified"}:
            raise ReviewValidationError(
                f"disposition finding {finding_id} is not resolved"
            )


def validate_review_panel(
    *,
    repo_root: Path,
    h0_ref: str,
    h1_ref: str,
    covered_paths: Sequence[str] | None,
    covered_set: str | None,
    instructions_path: str,
    packet_path: Path,
    input_manifest_path: Path,
    freeze_receipt_path: Path,
    disposition_path: Path,
    review_paths: Sequence[Path],
    executing_validator_path: Path | None = None,
) -> dict[str, Any]:
    """Validate a complete panel and return its canonical summary."""
    if len(review_paths) != 3:
        raise ReviewValidationError("exactly three review files are required")
    if len(set(review_paths)) != 3:
        raise ReviewValidationError("the three review files must be distinct")

    if covered_set is not None and covered_paths:
        raise ReviewValidationError(
            "choose either covered_paths or covered_set, not both"
        )
    resolved_repo = repo_root.resolve()
    try:
        bound_h1_head = _resolve_commit(resolved_repo, h1_ref)
    except PacketError as exc:
        raise ReviewValidationError(f"cannot resolve committed H1: {exc}") from exc
    artifact_bindings = _review_artifact_bindings(
        packet_path=packet_path,
        input_manifest_path=input_manifest_path,
        freeze_receipt_path=freeze_receipt_path,
        disposition_path=disposition_path,
        review_paths=review_paths,
    )
    _validate_h1_artifact_bindings(
        artifact_bindings,
        repo_root=resolved_repo,
        h1_head=bound_h1_head,
    )
    manifest_sha256, packet_sha256, freeze_receipt, h1_head = (
        _validate_packet_projection(
            repo_root=resolved_repo,
            h0_ref=h0_ref,
            h1_ref=bound_h1_head,
            covered_paths=covered_paths,
            covered_set=covered_set,
            instructions_path=instructions_path,
            packet_path=packet_path,
            input_manifest_path=input_manifest_path,
            freeze_receipt_path=freeze_receipt_path,
            executing_validator_path=(
                executing_validator_path or Path(__file__).resolve()
            ),
        )
    )
    packet_bytes = _read_bytes(packet_path, "review packet")
    proofs = tuple(
        _validate_review(
            path,
            repo_root=resolved_repo,
            manifest_sha256=manifest_sha256,
            packet_bytes=packet_bytes,
            packet_sha256=packet_sha256,
            freeze_receipt=freeze_receipt,
        )
        for path in review_paths
    )
    routes = [proof.route for proof in proofs]
    if len(set(routes)) != 3 or set(routes) != EXPECTED_ROUTES:
        raise ReviewValidationError(
            "panel must contain three distinct requested routes"
        )
    launcher_uuids = [proof.launcher_uuid for proof in proofs]
    if len(set(launcher_uuids)) != 3:
        raise ReviewValidationError("panel must contain three unique launcher UUIDs")
    no_go = [proof.path for proof in proofs if proof.verdict == "NO-GO"]
    if no_go:
        raise ReviewValidationError(
            "final panel contains NO-GO verdict: "
            + ", ".join(str(path) for path in no_go)
        )

    findings = tuple(finding for proof in proofs for finding in proof.findings)
    finding_ids = [finding.finding_id for finding in findings]
    if len(finding_ids) != len(set(finding_ids)):
        raise ReviewValidationError("duplicate finding ID across reviews")
    _validate_disposition(
        disposition_path,
        findings,
        repo_root=resolved_repo,
        h1_head=h1_head,
    )
    _validate_h1_artifact_bindings(
        artifact_bindings,
        repo_root=resolved_repo,
        h1_head=h1_head,
    )
    return {
        "finding_count": len(findings),
        "input_manifest_sha256": manifest_sha256,
        "packet_sha256": packet_sha256,
        "review_count": len(proofs),
        "valid": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--h0", required=True)
    parser.add_argument("--h1", required=True)
    review_inputs = parser.add_mutually_exclusive_group(required=True)
    review_inputs.add_argument("--covered", action="append")
    review_inputs.add_argument("--covered-set")
    parser.add_argument("--instructions", required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--freeze-receipt", type=Path, required=True)
    parser.add_argument("--disposition", type=Path, required=True)
    parser.add_argument("--files", type=Path, nargs=3, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = validate_review_panel(
            repo_root=args.repo,
            h0_ref=args.h0,
            h1_ref=args.h1,
            covered_paths=args.covered,
            covered_set=args.covered_set,
            instructions_path=args.instructions,
            packet_path=args.packet,
            input_manifest_path=args.input_manifest,
            freeze_receipt_path=args.freeze_receipt,
            disposition_path=args.disposition,
            review_paths=args.files,
        )
    except ReviewValidationError as exc:
        sys.stderr.write(f"review validation error: {exc}\n")
        return 2
    sys.stdout.buffer.write(canonical_json_bytes(result) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
