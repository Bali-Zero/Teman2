#!/usr/bin/env python3
"""Run the immutable worker-plane council v3 in two fail-closed phases.

Phase one launches Gemini, Codex, and Kimi concurrently as independent
constructive, red-team, and refuter reviewers.  Phase two is a separate command:
it binds those reviews and the completed finding disposition, then invokes
Fable 5 as the only sequential final gate.  GLM and DeepSeek are not routes in
this protocol and can never substitute for an unavailable seat.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
import hashlib
import json
import os
import re
import signal
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

try:
    from freeze_worker_plane_review import (
        EXPECTED_COUNCIL_ROUTE_CONFIG,
        canonical_json_bytes,
        parse_packet,
    )
except ModuleNotFoundError:  # pragma: no cover - import path used by repository tests
    from scripts.freeze_worker_plane_review import (
        EXPECTED_COUNCIL_ROUTE_CONFIG,
        canonical_json_bytes,
        parse_packet,
    )


LAUNCHER_SCHEMA = "nuzantara.worker-plane-review-launcher-receipt/v3"
REVIEW_INPUT_SCHEMA = "nuzantara.worker-plane-review-input/v1"
REVIEW_INPUT_MAGIC = b"NUZANTARA-REVIEW-INPUT-V1\n"
FINAL_GATE_INPUT_SCHEMA = "nuzantara.worker-plane-final-gate-input/v1"
FINAL_GATE_INPUT_MAGIC = b"NUZANTARA-WORKER-PLANE-FINAL-GATE-V1\n"
REVIEWERS_MARKER_SCHEMA = "nuzantara.worker-plane-reviewers-publication/v1"
REVIEWERS_MARKER_NAME = "reviewers-complete.json"
FINAL_GATE_MARKER_SCHEMA = "nuzantara.worker-plane-final-gate-publication/v1"
FINAL_GATE_MARKER_NAME = "final-gate-complete.json"
IDENTITY_POLICY_REVISION = "worker-plane-council-2026-07-23-v3"
DEFAULT_WALL_TIMEOUT_SECONDS = 30 * 60.0
DEFAULT_TERMINATION_GRACE_SECONDS = 5.0
DEFAULT_MAX_OUTPUT_BYTES = 16 * 1024 * 1024
KIMI_TRANSPORT_SCHEMA = "NUZANTARA-KIMI-LOSSLESS-TRANSPORT-V1"
KIMI_TRANSPORT_MAX_LINE_BYTES = 1_800
KIMI_TRANSPORT_SEGMENT_BYTES = 1_500
KIMI_READ_MAX_LINES = 1_000
KIMI_READ_MAX_PAGES = 256
KIMI_READ_PAGE_MAX_UTF16_UNITS = 40_000
KIMI_READ_PAGE_MAX_UTF8_BYTES = 80 * 1024
OUTPUT_SPOOL_MEMORY_BYTES = 1024 * 1024
PHASE1_REVIEW_MAX_WORDS = 1_800
MINIMUM_GEMINI_VERSION = (1, 1, 2)
REQUIRED_KIMI_VERSION = (0, 29, 0)
REQUIRED_CODEX_VERSION = (0, 145, 0)
MCP_CONFIG = '{"mcpServers":{}}'
LAUNCHER_REPOSITORY_PATH = "scripts/launch_worker_plane_review_panel.py"
VALIDATOR_INPUT_NAMES = (
    "00-review-packet.bin",
    "input-manifest.json",
    "freeze-receipt.json",
)
PHASE1_REVIEW_HEADINGS = (
    "# Verdict",
    "# Blocking findings",
    "# Important findings",
    "# What survives review",
    "# Required amendments",
    "# Falsification test",
)
PHASE1_VERDICT = re.compile(
    r"^(GO|GO-WITH-CHANGES|NO-GO) — confidence (100|[0-9]{1,2})$"
)
PHASE1_FINDING_ID = re.compile(r"\[([A-Z0-9][A-Z0-9._-]{2,63})\]")
PHASE1_FINDING_PREFIX = {
    "gemini": "GEMINI-PLAN-",
    "codex": "CODEX-PLAN-",
    "kimi": "KIMI-PLAN-",
}
PHASE1_PLACEHOLDERS = frozenset(
    {
        "",
        "...",
        "none",
        "tbd",
        "todo",
        "n/a",
        "na",
        "placeholder",
        "coming soon",
    }
)

FABLE_GATE_ARGV_SUFFIX = (
    "--print",
    "--model",
    "claude-fable-5",
    "--effort",
    "xhigh",
    "--output-format",
    "json",
    "--no-session-persistence",
    "--safe-mode",
    "--permission-mode",
    "plan",
    "--tools",
    "",
    "--disable-slash-commands",
    "--strict-mcp-config",
    "--mcp-config",
    MCP_CONFIG,
)
GEMINI_ARGV_SUFFIX = (
    "--mode",
    "plan",
    "--sandbox",
    "--print-timeout",
    "30m",
    "--model",
    "Gemini 3.1 Pro (High)",
)
CODEX_ARGV_SUFFIX = (
    "exec",
    "-",
    "--sandbox",
    "read-only",
    "--ephemeral",
    "--ignore-rules",
    "--skip-git-repo-check",
    "--color",
    "never",
    "--json",
)
KIMI_ARGV_SUFFIX = (
    "--model",
    "kimi-code/k3",
    "--output-format",
    "stream-json",
)


class LauncherError(RuntimeError):
    """Raised when immutable launch guarantees cannot be established."""


@dataclass(frozen=True)
class ClientPaths:
    fable: Path
    gemini: Path
    codex_node: Path
    codex_wrapper: Path
    codex_package: Path
    codex_native: Path
    kimi: Path
    sandbox_exec: Path


PRODUCTION_CLIENTS = ClientPaths(
    fable=Path("/Users/nuzantara/.local/share/claude/versions/2.1.216"),
    gemini=Path("/Users/nuzantara/.local/bin/agy"),
    codex_node=Path("/opt/homebrew/Cellar/node/26.5.0/bin/node"),
    codex_wrapper=Path(
        "/opt/homebrew/lib/node_modules/@openai/codex/bin/codex.js"
    ),
    codex_package=Path(
        "/opt/homebrew/lib/node_modules/@openai/codex/package.json"
    ),
    codex_native=Path(
        "/opt/homebrew/lib/node_modules/@openai/codex/node_modules/@openai/"
        "codex-darwin-arm64/vendor/aarch64-apple-darwin/bin/codex"
    ),
    kimi=Path("/Users/nuzantara/.kimi-code/bin/kimi"),
    sandbox_exec=Path("/usr/bin/sandbox-exec"),
)


@dataclass(frozen=True)
class ExecutableIdentity:
    """Reviewable identity pin for one production executable revision."""

    path: Path
    sha256: str
    cdhash: str
    team_identifier: str
    designated_requirement: str
    darwin_spawn_canonical: bool = False


PRODUCTION_IDENTITIES = {
    "fable": ExecutableIdentity(
        path=PRODUCTION_CLIENTS.fable,
        sha256="d01b49210d72ecbe277a2665d104bacccddf2d22185be99446d2929e0edfc48d",
        cdhash="e5b714a6575d1d1945c73745c9506bb37b760969",
        team_identifier="Q6L2SF6YDW",
        designated_requirement=(
            'identifier "com.anthropic.claude-code" and anchor apple generic and '
            "certificate 1[field.1.2.840.113635.100.6.2.6] /* exists */ and "
            "certificate leaf[field.1.2.840.113635.100.6.1.13] /* exists */ and "
            "certificate leaf[subject.OU] = Q6L2SF6YDW"
        ),
    ),
    "gemini": ExecutableIdentity(
        path=PRODUCTION_CLIENTS.gemini,
        sha256="6509d6ca54a66e3eaf61dfe35308ba1dfa1e6b552ef5c4f5f861562c6811ecaf",
        cdhash="d1ab6b43250ebdf79a8836804197495d39b9a5c1",
        team_identifier="EQHXZ8M8AV",
        designated_requirement=(
            "identifier cli and anchor apple generic and certificate "
            "1[field.1.2.840.113635.100.6.2.6] /* exists */ and certificate "
            "leaf[field.1.2.840.113635.100.6.1.13] /* exists */ and "
            "certificate leaf[subject.OU] = EQHXZ8M8AV"
        ),
        # AgY locates signed companion resources relative to its installed
        # image. A byte-for-byte private copy hangs while bootstrapping those
        # resources, so bind the installed vnode and attest the loaded CDHash.
        darwin_spawn_canonical=True,
    ),
    "codex_node": ExecutableIdentity(
        path=PRODUCTION_CLIENTS.codex_node,
        sha256="70851490e028b3d699a8d6d4e1de909af2a989359ae807974c92af9c6580a8e8",
        cdhash="e31a6a98489a6d1c0afeaec28a86c70c9f8d3644",
        team_identifier="not set",
        designated_requirement=(
            'cdhash H"e31a6a98489a6d1c0afeaec28a86c70c9f8d3644"'
        ),
        darwin_spawn_canonical=True,
    ),
    "codex_native": ExecutableIdentity(
        path=PRODUCTION_CLIENTS.codex_native,
        sha256="1da3f4e0e96028b8a771814293c3033dafd1971f943f6c7e79b0897fe705f590",
        cdhash="c9da028e2080a684d2c355e6f40ffc53c21ff7ee",
        team_identifier="2DC432GLL2",
        designated_requirement=(
            "identifier codex and anchor apple generic and certificate "
            "1[field.1.2.840.113635.100.6.2.6] /* exists */ and certificate "
            "leaf[field.1.2.840.113635.100.6.1.13] /* exists */ and "
            'certificate leaf[subject.OU] = "2DC432GLL2"'
        ),
    ),
    "kimi": ExecutableIdentity(
        path=PRODUCTION_CLIENTS.kimi,
        sha256="5cccf53604f20c5499ea10c3094298f49a1ad59fa90cddd9fd7e0ba44815fdd3",
        cdhash="160e1dd4f3a46bc6f5179f58785f53e20ad9f4ea",
        team_identifier="2J9472RW75",
        designated_requirement=(
            "identifier kimi and anchor apple generic and certificate "
            "1[field.1.2.840.113635.100.6.2.6] /* exists */ and certificate "
            "leaf[field.1.2.840.113635.100.6.1.13] /* exists */ and "
            'certificate leaf[subject.OU] = "2J9472RW75"'
        ),
        darwin_spawn_canonical=True,
    ),
    "sandbox_exec": ExecutableIdentity(
        path=PRODUCTION_CLIENTS.sandbox_exec,
        sha256="4b65c7cbdfb11fd6199b8587d6f0334fe9277958be55d0168e29836d867b4866",
        cdhash="806d8a604377ca1f238165d0d342a50d73e7c20a",
        team_identifier="not set",
        designated_requirement=(
            'identifier "com.apple.sandbox-exec" and anchor apple'
        ),
        darwin_spawn_canonical=True,
    ),
}

PRODUCTION_ARTIFACT_SHA256 = {
    "codex_wrapper": "134063e133f0b4244fa3b251acf973d4fe4b4aeeacbdc135211bf480f59f1477",
    "codex_package": "ff896fd5e5444cfc645890b21273ad1c6b3e26e4e4ab0934de597a0f8db5aafb",
}


@dataclass(frozen=True)
class Seat:
    name: str
    requested_route: str
    client: str
    argv_suffix: tuple[str, ...]
    raw_name: str
    stderr_name: str
    receipt_name: str
    review_name: str
    role: str
    input_transport: str


SEATS = (
    Seat(
        name="gemini",
        requested_route="Gemini 3.1 Pro (High)",
        client="gemini",
        argv_suffix=GEMINI_ARGV_SUFFIX,
        raw_name="01-gemini-3.1-pro-high.raw.txt",
        stderr_name="01-gemini-3.1-pro-high.stderr.bin",
        receipt_name="01-gemini-3.1-pro-high.invocation.json",
        review_name="01-gemini-3.1-pro-high.md",
        role="constructive",
        input_transport="file",
    ),
    Seat(
        name="codex",
        requested_route="account-default",
        client="codex",
        argv_suffix=CODEX_ARGV_SUFFIX,
        raw_name="02-codex-gpt-5.6-red-team.raw.jsonl",
        stderr_name="02-codex-gpt-5.6-red-team.stderr.bin",
        receipt_name="02-codex-gpt-5.6-red-team.invocation.json",
        review_name="02-codex-gpt-5.6-red-team.md",
        role="red-team",
        input_transport="stdin",
    ),
    Seat(
        name="kimi",
        requested_route="kimi-code/k3",
        client="kimi",
        argv_suffix=KIMI_ARGV_SUFFIX,
        raw_name="03-kimi-k3-refuter.raw.jsonl",
        stderr_name="03-kimi-k3-refuter.stderr.bin",
        receipt_name="03-kimi-k3-refuter.invocation.json",
        review_name="03-kimi-k3-refuter.md",
        role="refuter",
        input_transport="file",
    ),
)

FABLE_GATE = Seat(
    name="fable",
    requested_route="claude-fable-5",
    client="fable",
    argv_suffix=FABLE_GATE_ARGV_SUFFIX,
    raw_name="04-fable-5-final-gate.raw.json",
    stderr_name="04-fable-5-final-gate.stderr.bin",
    receipt_name="04-fable-5-final-gate.invocation.json",
    review_name="04-fable-5-final-gate.md",
    role="final-gate",
    input_transport="stdin",
)


@dataclass(frozen=True)
class FileProof:
    device: int
    inode: int
    mode: int
    size: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True)
class FrozenReview:
    packet_bytes: bytes
    review_input_bytes: bytes
    manifest_bytes: bytes
    receipt_bytes: bytes
    route_config_bytes: bytes
    packet_sha256: str
    input_manifest_sha256: str
    packet_path: Path
    route_config_path: Path
    packet_proof: FileProof
    launcher_path: str
    launcher_sha256: str
    launcher_git_blob_oid: str


@dataclass(frozen=True)
class AuthenticatedFile:
    path: Path
    sha256: str
    proof: FileProof


@dataclass(frozen=True)
class PreparedExecutable:
    canonical: AuthenticatedFile
    private_copy: AuthenticatedFile
    identity: ExecutableIdentity | None


class CommandRunner(Protocol):
    def __call__(
        self,
        *,
        executable: PreparedExecutable,
        argv: Sequence[str],
        input_bytes: bytes,
        cwd: Path,
        environment: Mapping[str, str],
        label: str,
        wall_timeout_seconds: float,
        termination_grace_seconds: float,
        max_output_bytes: int,
    ) -> subprocess.CompletedProcess[bytes]: ...


@dataclass(frozen=True)
class PublishedFile:
    path: Path
    device: int
    inode: int
    sha256: str


@dataclass(frozen=True)
class SandboxProof:
    path: Path
    mode: int
    device: int
    inode: int
    initial_entries: tuple[str, ...]


@dataclass(frozen=True)
class SeatRun:
    seat: Seat
    launcher_invocation_uuid: str
    executable: Path
    executable_copy: Path
    executable_sha256: str
    executable_identity: ExecutableIdentity | None
    execution_wrapper: Path | None
    execution_wrapper_sha256: str | None
    execution_wrapper_identity: ExecutableIdentity | None
    client_artifact_sha256: tuple[tuple[str, str], ...]
    client_version: str
    argv: tuple[str, ...]
    started_at_utc: str
    ended_at_utc: str
    returncode: int
    stdout: bytes
    stderr: bytes
    wall_timeout_seconds: float
    max_output_bytes: int
    sandbox_enforced: bool
    sandbox_profile_sha256: str | None
    canary_sha256_before: str | None
    canary_sha256_after: str | None
    canary_write_denied: bool | None
    pre_run_input_sha256: str
    post_run_input_sha256: str
    input_bytes: bytes
    home_path: Path


@dataclass(frozen=True)
class PanelResult:
    packet_sha256: str
    input_manifest_sha256: str
    output_dir: Path
    receipt_paths: tuple[Path, ...]


@dataclass(frozen=True)
class FinalGateResult:
    packet_sha256: str
    input_manifest_sha256: str
    output_dir: Path
    receipt_path: Path


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _review_input_bytes(
    *,
    packet_bytes: bytes,
    input_manifest_sha256: str,
) -> bytes:
    if re.fullmatch(r"[0-9a-f]{64}", input_manifest_sha256) is None:
        raise LauncherError("review input manifest SHA-256 is invalid")
    return b"".join(
        (
            REVIEW_INPUT_MAGIC,
            f"schema: {REVIEW_INPUT_SCHEMA}\n".encode("ascii"),
            f"input_manifest_sha256: {input_manifest_sha256}\n".encode("ascii"),
            f"packet_bytes: {len(packet_bytes)}\n".encode("ascii"),
            b"\n",
            packet_bytes,
        )
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _proof(metadata: os.stat_result) -> FileProof:
    return FileProof(
        device=metadata.st_dev,
        inode=metadata.st_ino,
        mode=stat.S_IMODE(metadata.st_mode),
        size=metadata.st_size,
        mtime_ns=metadata.st_mtime_ns,
        ctime_ns=metadata.st_ctime_ns,
    )


def _read_regular_file(
    path: Path,
    label: str,
    *,
    require_executable: bool = False,
) -> tuple[bytes, FileProof]:
    """Read one non-symlink regular file through a stable descriptor."""
    if not path.is_absolute():
        raise LauncherError(f"{label} path must be absolute")
    try:
        path_metadata = path.lstat()
    except OSError as exc:
        raise LauncherError(f"{label} is unavailable: {path}") from exc
    if stat.S_ISLNK(path_metadata.st_mode):
        raise LauncherError(f"{label} must not be a symlink")
    if not stat.S_ISREG(path_metadata.st_mode):
        raise LauncherError(f"{label} must be a regular file")

    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise LauncherError(f"cannot open {label}: {path}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise LauncherError(f"{label} must be a regular file")
        if require_executable and not stat.S_IMODE(before.st_mode) & 0o111:
            raise LauncherError(f"{label} is not executable")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        descriptor_proof = _proof(after)
        if _proof(before) != descriptor_proof:
            raise LauncherError(f"{label} changed while it was read")
    finally:
        os.close(descriptor)

    try:
        final_path_metadata = path.lstat()
    except OSError as exc:
        raise LauncherError(f"{label} disappeared while it was read") from exc
    if (
        stat.S_ISLNK(final_path_metadata.st_mode)
        or not stat.S_ISREG(final_path_metadata.st_mode)
        or _proof(final_path_metadata) != descriptor_proof
    ):
        raise LauncherError(f"{label} path changed while it was read")
    return b"".join(chunks), descriptor_proof


def _authenticate_file(
    path: Path,
    label: str,
    *,
    require_executable: bool = False,
) -> AuthenticatedFile:
    payload, proof = _read_regular_file(
        path,
        label,
        require_executable=require_executable,
    )
    return AuthenticatedFile(path=path, sha256=_sha256(payload), proof=proof)


def _validate_artifact(
    path: Path,
    label: str,
    *,
    expected_sha256: str | None,
) -> AuthenticatedFile:
    artifact = _authenticate_file(path, label)
    if expected_sha256 is not None and artifact.sha256 != expected_sha256:
        raise LauncherError(f"{label} SHA-256 differs from identity policy")
    return artifact


def _assert_authenticated_file_unchanged(
    authenticated: AuthenticatedFile,
    label: str,
    *,
    require_executable: bool = False,
) -> None:
    try:
        current = _authenticate_file(
            authenticated.path,
            label,
            require_executable=require_executable,
        )
    except LauncherError as exc:
        raise LauncherError(f"{label} changed during panel execution") from exc
    if current.proof != authenticated.proof or current.sha256 != authenticated.sha256:
        raise LauncherError(f"{label} changed during panel execution")


def _git_blob_oid(payload: bytes, expected_oid: str) -> str:
    framed = f"blob {len(payload)}\0".encode("ascii") + payload
    if len(expected_oid) == 40:
        return hashlib.sha1(framed, usedforsecurity=False).hexdigest()
    if len(expected_oid) == 64:
        return hashlib.sha256(framed).hexdigest()
    raise LauncherError("launcher Git blob OID has an unsupported length")


def _read_packet_once(path: Path) -> tuple[bytes, FileProof]:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise LauncherError(f"cannot open frozen packet: {path}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or stat.S_IMODE(before.st_mode) & 0o222:
            raise LauncherError("frozen packet must be a read-only regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if _proof(before) != _proof(after):
            raise LauncherError("frozen packet changed while it was read")
        return b"".join(chunks), _proof(after)
    finally:
        os.close(descriptor)


def _read_read_only(path: Path, label: str) -> bytes:
    try:
        metadata = path.lstat()
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            raise LauncherError(f"{label} must be a regular file")
        if stat.S_IMODE(metadata.st_mode) & 0o222:
            raise LauncherError(f"{label} must be read-only")
        return path.read_bytes()
    except OSError as exc:
        raise LauncherError(f"cannot read {label}: {path}") from exc


def _required_receipt_hex(
    receipt: Mapping[str, Any],
    field: str,
    lengths: tuple[int, ...],
) -> str:
    value = receipt.get(field)
    if (
        not isinstance(value, str)
        or len(value) not in lengths
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise LauncherError(f"freeze receipt has invalid {field}")
    return value


def _validate_freeze_provenance(receipt: Mapping[str, Any]) -> tuple[str, str, str]:
    if receipt.get("schema") != "nuzantara.worker-plane-review-freeze-receipt/v1":
        raise LauncherError("freeze receipt schema is not supported")
    for field in ("base_commit", "source_head", "source_tree", "upstream_commit"):
        _required_receipt_hex(receipt, field, (40, 64))
    for field in (
        "generator_sha256",
        "launcher_sha256",
        "route_config_sha256",
        "tracked_status_sha256",
        "validator_sha256",
    ):
        _required_receipt_hex(receipt, field, (64,))
    for field in (
        "generator_git_blob_oid",
        "launcher_git_blob_oid",
        "route_config_git_blob_oid",
        "validator_git_blob_oid",
    ):
        _required_receipt_hex(receipt, field, (40, 64))
    required_text = (
        "built_at_utc",
        "generator_path",
        "generator_version",
        "launcher_path",
        "route_config_path",
        "validator_path",
    )
    for field in required_text:
        if not isinstance(receipt.get(field), str) or not receipt[field]:
            raise LauncherError(f"freeze receipt lacks {field}")
    if receipt["launcher_path"] != LAUNCHER_REPOSITORY_PATH:
        raise LauncherError("freeze receipt launcher path is not canonical")
    return (
        receipt["launcher_path"],
        receipt["launcher_sha256"],
        receipt["launcher_git_blob_oid"],
    )


def _load_frozen_review(review_dir: Path) -> FrozenReview:
    review_dir = review_dir.resolve()
    try:
        directory_stat = review_dir.stat()
    except OSError as exc:
        raise LauncherError(
            f"frozen review directory is unavailable: {review_dir}"
        ) from exc
    if (
        not stat.S_ISDIR(directory_stat.st_mode)
        or stat.S_IMODE(directory_stat.st_mode) & 0o222
    ):
        raise LauncherError("frozen review directory must be read-only")
    if review_dir.parent.name != "sha256":
        raise LauncherError(
            "frozen review is not under a sha256 content-addressed store"
        )

    packet_path = review_dir / "packet.bin"
    manifest_path = review_dir / "input-manifest.json"
    receipt_path = review_dir / "freeze-receipt.json"
    route_config_path = review_dir / "worker-plane-council-v3.json"
    packet_bytes, packet_proof = _read_packet_once(packet_path)
    manifest_bytes = _read_read_only(manifest_path, "input manifest")
    receipt_bytes = _read_read_only(receipt_path, "freeze receipt")
    route_config_bytes = _read_read_only(route_config_path, "council route config")

    try:
        parsed = parse_packet(packet_bytes)
        receipt = json.loads(receipt_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise LauncherError(
            "frozen review failed packet or receipt validation"
        ) from exc
    if canonical_json_bytes(parsed.manifest) != manifest_bytes:
        raise LauncherError("input manifest does not match packet bytes")
    if canonical_json_bytes(receipt) + b"\n" != receipt_bytes:
        raise LauncherError("freeze receipt is not canonical newline-terminated JSON")
    launcher_path, launcher_sha256, launcher_git_blob_oid = _validate_freeze_provenance(
        receipt
    )
    if route_config_bytes != EXPECTED_COUNCIL_ROUTE_CONFIG:
        raise LauncherError("council route config bytes are not canonical")
    route_config_sha256 = _sha256(route_config_bytes)
    if (
        review_dir.name != parsed.packet_sha256
        or receipt.get("packet_sha256") != parsed.packet_sha256
        or receipt.get("input_manifest_sha256") != parsed.manifest_sha256
        or receipt.get("packet_device") != packet_proof.device
        or receipt.get("packet_inode") != packet_proof.inode
        or receipt.get("route_config_sha256") != route_config_sha256
        or receipt.get("packet_bytes") != len(packet_bytes)
        or receipt.get("git_object_validation") != "pass"
    ):
        raise LauncherError("freeze receipt does not prove the frozen review")
    review_input_bytes = _review_input_bytes(
        packet_bytes=packet_bytes,
        input_manifest_sha256=parsed.manifest_sha256,
    )
    return FrozenReview(
        packet_bytes=packet_bytes,
        review_input_bytes=review_input_bytes,
        manifest_bytes=manifest_bytes,
        receipt_bytes=receipt_bytes,
        route_config_bytes=route_config_bytes,
        packet_sha256=parsed.packet_sha256,
        input_manifest_sha256=parsed.manifest_sha256,
        packet_path=packet_path,
        route_config_path=route_config_path,
        packet_proof=packet_proof,
        launcher_path=launcher_path,
        launcher_sha256=launcher_sha256,
        launcher_git_blob_oid=launcher_git_blob_oid,
    )


def _authenticate_launcher(frozen: FrozenReview) -> AuthenticatedFile:
    launcher_path = Path(__file__).absolute()
    repository_root = launcher_path.parent.parent
    expected_path = (repository_root / frozen.launcher_path).absolute()
    if launcher_path != expected_path:
        raise LauncherError("executing launcher path differs from freeze receipt")
    payload, proof = _read_regular_file(launcher_path, "launcher")
    digest = _sha256(payload)
    if digest != frozen.launcher_sha256:
        raise LauncherError("launcher SHA-256 differs from freeze receipt")
    if (
        _git_blob_oid(payload, frozen.launcher_git_blob_oid)
        != frozen.launcher_git_blob_oid
    ):
        raise LauncherError("launcher Git blob differs from freeze receipt")
    return AuthenticatedFile(path=launcher_path, sha256=digest, proof=proof)


def _assert_packet_unchanged(frozen: FrozenReview) -> None:
    try:
        metadata = frozen.packet_path.lstat()
    except OSError as exc:
        raise LauncherError("frozen packet changed after verification") from exc
    if frozen.packet_path.is_symlink() or _proof(metadata) != frozen.packet_proof:
        raise LauncherError("frozen packet changed after verification")


def _write_staged_file(directory: Path, name: str, payload: bytes) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{name}.", dir=directory)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o444)
        if _sha256(temporary.read_bytes()) != _sha256(payload):
            raise LauncherError(f"post-copy hash verification failed for {name}")
        return temporary
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _cleanup_published_files(files: Sequence[PublishedFile]) -> None:
    failures: list[Path] = []
    for published in reversed(files):
        try:
            metadata = published.path.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            failures.append(published.path)
            continue
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_dev != published.device
            or metadata.st_ino != published.inode
        ):
            failures.append(published.path)
            continue
        try:
            published.path.unlink()
        except OSError:
            failures.append(published.path)
    if failures:
        names = ", ".join(path.name for path in failures)
        raise LauncherError(f"refusing to remove replaced launch outputs: {names}")


def _publish_new_files(
    output_dir: Path,
    files: Mapping[str, bytes],
) -> tuple[PublishedFile, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, Path, bytes]] = []
    published: list[PublishedFile] = []
    try:
        for name, payload in files.items():
            target = output_dir / name
            if target.exists() or target.is_symlink():
                raise LauncherError(f"refusing to replace existing output: {target}")
            staged.append(
                (_write_staged_file(output_dir, name, payload), target, payload)
            )
        for temporary, target, payload in staged:
            os.link(temporary, target)
            if _sha256(target.read_bytes()) != _sha256(payload):
                raise LauncherError(
                    f"published output hash verification failed for {target.name}"
                )
            metadata = target.lstat()
            published.append(
                PublishedFile(
                    path=target,
                    device=metadata.st_dev,
                    inode=metadata.st_ino,
                    sha256=_sha256(payload),
                )
            )
        directory_descriptor = os.open(output_dir, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        return tuple(published)
    except (OSError, LauncherError) as exc:
        try:
            _cleanup_published_files(published)
        except LauncherError as cleanup_exc:
            raise cleanup_exc from exc
        if isinstance(exc, LauncherError):
            raise
        raise LauncherError("atomic output publication failed") from exc
    finally:
        for temporary, _, _ in staged:
            temporary.unlink(missing_ok=True)


def _materialize_validator_inputs(
    frozen: FrozenReview,
    output_dir: Path,
) -> tuple[PublishedFile, ...]:
    return _publish_new_files(
        output_dir,
        {
            "00-review-packet.bin": frozen.packet_bytes,
            "input-manifest.json": frozen.manifest_bytes,
            "freeze-receipt.json": frozen.receipt_bytes,
        },
    )


def _canonical_output_names() -> tuple[str, ...]:
    seat_names = tuple(
        name
        for seat in SEATS
        for name in (
            seat.raw_name,
            seat.stderr_name,
            seat.receipt_name,
            seat.review_name,
        )
    )
    return (*VALIDATOR_INPUT_NAMES, *seat_names, REVIEWERS_MARKER_NAME)


def _completion_marker_bytes(
    *,
    frozen: FrozenReview,
    files: Mapping[str, bytes],
) -> bytes:
    expected_names = set(_canonical_output_names()) - {REVIEWERS_MARKER_NAME}
    if set(files) != expected_names:
        raise LauncherError("publication marker file set is incomplete")
    entries = [
        {
            "bytes": len(files[name]),
            "path": name,
            "sha256": _sha256(files[name]),
        }
        for name in sorted(files)
    ]
    marker = {
        "complete": True,
        "files": entries,
        "input_manifest_sha256": frozen.input_manifest_sha256,
        "packet_sha256": frozen.packet_sha256,
        "phase": "parallel-reviewers",
        "schema": REVIEWERS_MARKER_SCHEMA,
        "seat_receipts": [seat.receipt_name for seat in SEATS],
    }
    return canonical_json_bytes(marker) + b"\n"


def _publish_complete_panel(
    output_dir: Path,
    *,
    frozen: FrozenReview,
    validator_payloads: Mapping[str, bytes],
    output_files: Mapping[str, bytes],
) -> tuple[PublishedFile, ...]:
    all_files = {**validator_payloads, **output_files}
    marker_bytes = _completion_marker_bytes(frozen=frozen, files=all_files)
    return _publish_new_files(
        output_dir,
        {**output_files, REVIEWERS_MARKER_NAME: marker_bytes},
    )


def _preflight_output_targets(output_dir: Path) -> None:
    if output_dir.exists() or output_dir.is_symlink():
        metadata = output_dir.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise LauncherError("review output path must be a non-symlink directory")
    else:
        output_dir.mkdir(parents=True)
    names = _canonical_output_names()
    if len(names) != len(set(names)):
        raise LauncherError("canonical review output names are not unique")
    for name in names:
        target = output_dir / name
        if target.exists() or target.is_symlink():
            raise LauncherError(f"refusing to replace existing output: {target}")


def _write_private_executable(
    directory: Path,
    name: str,
    payload: bytes,
) -> AuthenticatedFile:
    path = directory / name
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o500)
    except OSError as exc:
        raise LauncherError(f"cannot create private executable copy: {name}") from exc
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fchmod(handle.fileno(), 0o500)
            os.fsync(handle.fileno())
        private_copy = _authenticate_file(
            path,
            f"private {name}",
            require_executable=True,
        )
        if private_copy.sha256 != _sha256(payload) or private_copy.proof.mode != 0o500:
            raise LauncherError(f"private executable copy failed verification: {name}")
        return private_copy
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _codesign_identity(path: Path, label: str) -> tuple[str, str, str]:
    """Read the system verifier's signing identity for one stable pathname."""
    try:
        verification = subprocess.run(
            ["/usr/bin/codesign", "--verify", "--strict", str(path)],
            shell=False,
            capture_output=True,
            check=False,
            timeout=10.0,
        )
        description = subprocess.run(
            [
                "/usr/bin/codesign",
                "-dvvv",
                "--requirements",
                "-",
                str(path),
            ],
            shell=False,
            capture_output=True,
            check=False,
            timeout=10.0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LauncherError(f"cannot attest {label} code signature") from exc
    if verification.returncode != 0 or description.returncode != 0:
        raise LauncherError(f"{label} code signature verification failed")
    output = (bytes(description.stdout) + bytes(description.stderr)).decode(
        "utf-8", errors="strict"
    )
    values: dict[str, str] = {}
    for line in output.splitlines():
        # Ad-hoc signed Mach-O images prefix the designated requirement with
        # "# "; platform-signed binaries do not. Both forms come from the
        # system verifier and bind the same requirement.
        normalized_line = line.removeprefix("# ")
        if normalized_line.startswith("CDHash="):
            values["cdhash"] = normalized_line.removeprefix("CDHash=")
        elif normalized_line.startswith("TeamIdentifier="):
            values["team_identifier"] = normalized_line.removeprefix(
                "TeamIdentifier="
            )
        elif normalized_line.startswith("designated => "):
            values["designated_requirement"] = normalized_line.removeprefix(
                "designated => "
            )
    if set(values) != {"cdhash", "team_identifier", "designated_requirement"}:
        raise LauncherError(f"{label} code signature identity is incomplete")
    if not re.fullmatch(r"[0-9a-f]{40}", values["cdhash"]):
        raise LauncherError(f"{label} code signature CDHash is invalid")
    return (
        values["cdhash"],
        values["team_identifier"],
        values["designated_requirement"],
    )


def _attest_executable_identity(
    authenticated: AuthenticatedFile,
    expected: ExecutableIdentity,
    label: str,
) -> None:
    if authenticated.path != expected.path:
        raise LauncherError(f"{label} executable path differs from identity policy")
    if authenticated.sha256 != expected.sha256:
        raise LauncherError(f"{label} executable SHA-256 differs from identity policy")
    before = authenticated.proof
    cdhash, team_identifier, designated_requirement = _codesign_identity(
        authenticated.path,
        label,
    )
    _assert_authenticated_file_unchanged(
        authenticated,
        f"{label} executable",
        require_executable=True,
    )
    if authenticated.proof != before:
        raise LauncherError(f"{label} executable changed during identity attestation")
    if (
        cdhash != expected.cdhash
        or team_identifier != expected.team_identifier
        or designated_requirement != expected.designated_requirement
    ):
        raise LauncherError(f"{label} executable signing identity differs from policy")


def _validate_executable(
    path: Path,
    label: str,
    private_directory: Path,
    *,
    allow_read_only_canonical: bool = False,
    expected_identity: ExecutableIdentity | None = None,
) -> PreparedExecutable:
    payload, proof = _read_regular_file(
        path,
        f"{label} executable",
        require_executable=True,
    )
    canonical = AuthenticatedFile(path=path, sha256=_sha256(payload), proof=proof)
    if expected_identity is not None:
        _attest_executable_identity(canonical, expected_identity, label)
    if allow_read_only_canonical:
        if path != PRODUCTION_CLIENTS.sandbox_exec:
            raise LauncherError(
                "read-only canonical execution is reserved for /usr/bin/sandbox-exec"
            )
        try:
            filesystem = os.statvfs(path)
        except OSError as exc:
            raise LauncherError(
                "cannot prove sandbox-exec executable filesystem"
            ) from exc
        if not hasattr(os, "ST_RDONLY") or not filesystem.f_flag & os.ST_RDONLY:
            raise LauncherError("sandbox-exec filesystem is not read-only")
        # macOS kills byte-copied platform binaries; the sealed read-only system
        # volume already makes this canonical path immutable after authentication.
        return PreparedExecutable(
            canonical=canonical,
            private_copy=canonical,
            identity=expected_identity,
        )
    private_copy = _write_private_executable(
        private_directory,
        f"{label.lower()}-client",
        payload,
    )
    if expected_identity is not None:
        try:
            private_cdhash = _macho_cdhash(payload).hex()
        except LauncherError as exc:
            raise LauncherError(
                f"{label} private copy lacks the pinned signed Mach-O identity"
            ) from exc
        if private_cdhash != expected_identity.cdhash:
            raise LauncherError(f"{label} private copy CDHash differs from policy")
    return PreparedExecutable(
        canonical=canonical,
        private_copy=private_copy,
        identity=expected_identity,
    )


def _assert_prepared_executable_unchanged(
    executable: PreparedExecutable,
    label: str,
) -> None:
    _assert_authenticated_file_unchanged(
        executable.canonical,
        f"{label} executable",
        require_executable=True,
    )
    if executable.private_copy.path != executable.canonical.path:
        _assert_authenticated_file_unchanged(
            executable.private_copy,
            f"private {label} executable",
            require_executable=True,
        )


def _assert_executable_sandbox_sealed(
    path: Path,
    executables: Sequence[PreparedExecutable],
) -> None:
    try:
        metadata = path.lstat()
        entries = tuple(sorted(child.name for child in path.iterdir()))
    except OSError as exc:
        raise LauncherError("cannot verify private executable sandbox") from exc
    expected_entries = tuple(
        sorted(
            executable.private_copy.path.name
            for executable in executables
            if executable.private_copy.path.parent == path
        )
    )
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o500
        or entries != expected_entries
    ):
        raise LauncherError("private executable sandbox is not sealed")


def _seal_executable_sandbox(
    path: Path,
    executables: Sequence[PreparedExecutable],
) -> None:
    try:
        os.chmod(path, 0o500)
    except OSError as exc:
        raise LauncherError("cannot seal private executable sandbox") from exc
    _assert_executable_sandbox_sealed(path, executables)


def _open_authenticated_executable_descriptor(
    executable: AuthenticatedFile,
    label: str,
) -> tuple[int, bytes]:
    """Open, re-hash, and retain the exact executable vnode for one spawn."""
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(executable.path, flags)
    except OSError as exc:
        raise LauncherError(f"cannot bind {label} executable descriptor") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or not stat.S_IMODE(before.st_mode) & 0o111
            or _proof(before) != executable.proof
        ):
            raise LauncherError(f"{label} executable changed before descriptor bind")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        payload = b"".join(chunks)
        if (
            _proof(after) != executable.proof
            or _sha256(payload) != executable.sha256
        ):
            raise LauncherError(f"{label} executable changed during descriptor bind")
        os.lseek(descriptor, 0, os.SEEK_SET)
        return descriptor, payload
    except BaseException:
        os.close(descriptor)
        raise


def _macho_cdhash(payload: bytes) -> bytes:
    """Derive the kernel CDHash from authenticated thin Mach-O bytes."""
    if len(payload) < 28:
        raise LauncherError("private executable is not a signed Mach-O image")
    magic = payload[:4]
    if magic == b"\xcf\xfa\xed\xfe":
        endian, header_size = "<", 32
    elif magic == b"\xfe\xed\xfa\xcf":
        endian, header_size = ">", 32
    elif magic == b"\xce\xfa\xed\xfe":
        endian, header_size = "<", 28
    elif magic == b"\xfe\xed\xfa\xce":
        endian, header_size = ">", 28
    else:
        raise LauncherError("private executable is not a thin Mach-O image")
    if len(payload) < header_size:
        raise LauncherError("private Mach-O header is truncated")
    command_count = struct.unpack_from(f"{endian}I", payload, 16)[0]
    command_offset = header_size
    signature: bytes | None = None
    for _ in range(command_count):
        if command_offset + 8 > len(payload):
            raise LauncherError("private Mach-O load commands are truncated")
        command, command_size = struct.unpack_from(
            f"{endian}II", payload, command_offset
        )
        if command_size < 8 or command_offset + command_size > len(payload):
            raise LauncherError("private Mach-O load command is invalid")
        if command == 0x1D:
            if command_size < 16:
                raise LauncherError("private Mach-O code signature command is invalid")
            data_offset, data_size = struct.unpack_from(
                f"{endian}II", payload, command_offset + 8
            )
            if data_offset + data_size > len(payload):
                raise LauncherError("private Mach-O code signature is truncated")
            signature = payload[data_offset : data_offset + data_size]
        command_offset += command_size
    if signature is None or len(signature) < 12:
        raise LauncherError("private Mach-O image has no embedded code signature")
    magic_value, signature_length, count = struct.unpack_from(">III", signature, 0)
    if (
        magic_value != 0xFADE0CC0
        or signature_length > len(signature)
        or 12 + count * 8 > signature_length
    ):
        raise LauncherError("private Mach-O embedded signature is invalid")
    hash_functions = {
        1: hashlib.sha1,
        2: hashlib.sha256,
        3: hashlib.sha256,
        4: hashlib.sha384,
    }
    hash_rank = {1: 1, 3: 2, 2: 3, 4: 4}
    candidates: list[tuple[int, int, bytes]] = []
    for index in range(count):
        slot, blob_offset = struct.unpack_from(">II", signature, 12 + index * 8)
        if blob_offset + 8 > signature_length:
            raise LauncherError("private Mach-O signature index is invalid")
        blob_magic, blob_length = struct.unpack_from(">II", signature, blob_offset)
        if blob_length < 8 or blob_offset + blob_length > signature_length:
            raise LauncherError("private Mach-O signature blob is invalid")
        if blob_magic != 0xFADE0C02:
            continue
        # CS_CodeDirectory's fixed header ends after the 32-bit spare2 field.
        # Forty bytes exposes hashType but is still a structurally truncated
        # CodeDirectory; the minimum complete fixed header is 44 bytes.
        if blob_length < 44:
            raise LauncherError("private Mach-O signature blob is invalid")
        hash_type = signature[blob_offset + 37]
        hash_function = hash_functions.get(hash_type)
        if hash_function is None:
            continue
        code_directory = signature[blob_offset : blob_offset + blob_length]
        candidates.append(
            (
                hash_rank[hash_type],
                -slot,
                hash_function(code_directory).digest()[:20],
            )
        )
    if not candidates:
        raise LauncherError("private Mach-O image has no supported CodeDirectory")
    candidates.sort(reverse=True)
    return candidates[0][2]


def _close_descriptor(descriptor: int) -> None:
    try:
        os.close(descriptor)
    except OSError:
        pass


def _read_pipe(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    try:
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    finally:
        _close_descriptor(descriptor)


def _write_pipe(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    try:
        while view:
            try:
                written = os.write(descriptor, view)
            except BrokenPipeError:
                return
            view = view[written:]
    finally:
        _close_descriptor(descriptor)


def _capture_descriptor(
    descriptor: int,
    spool: Any,
    *,
    max_output_bytes: int,
    overflow: threading.Event,
) -> None:
    total = 0
    try:
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                return
            total += len(chunk)
            remaining = max_output_bytes - spool.tell()
            if remaining > 0:
                spool.write(chunk[:remaining])
            if total > max_output_bytes:
                overflow.set()
    finally:
        _close_descriptor(descriptor)


def _process_group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # EPERM still proves that the process group exists.  Sandboxed provider
        # helpers can briefly become unsignalable while they are exiting, so
        # keep polling until the group disappears instead of aborting cleanup.
        return True
    return True


def _terminate_process_group(
    process_group: int,
    *,
    grace_seconds: float,
    leader_process: subprocess.Popen[bytes] | None = None,
    leader_poll: Callable[[], int | None] | None = None,
) -> None:
    """Terminate the whole isolated group and prove that no member remains."""
    if leader_process is not None and leader_poll is not None:
        raise LauncherError("process-group cleanup received two leader pollers")
    if leader_poll is None and leader_process is not None:
        leader_poll = leader_process.poll
    if leader_poll is not None:
        # Reap a leader that is already a zombie before the first group probe.
        # Otherwise killpg(..., 0) can report a group that has no live member.
        leader_poll()
    if not _process_group_exists(process_group):
        return
    try:
        os.killpg(process_group, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError:
        # The group may be in a transient sandbox teardown state.  We still
        # require it to disappear within the bounded grace period below.
        pass
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if leader_poll is not None:
            leader_poll()
        if not _process_group_exists(process_group):
            return
        time.sleep(0.02)
    try:
        os.killpg(process_group, signal.SIGKILL)
    except ProcessLookupError:
        return
    except PermissionError:
        pass
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if leader_poll is not None:
            leader_poll()
        if not _process_group_exists(process_group):
            return
        time.sleep(0.02)
    if leader_poll is not None:
        leader_poll()
    if not _process_group_exists(process_group):
        return
    raise LauncherError(
        f"process group {process_group} still exists after TERM/KILL"
    )


def _wait_for_process_group_completion(
    process_group: int,
    *,
    leader_poll: Callable[[], int | None],
    overflow: threading.Event,
    deadline: float,
    termination_grace_seconds: float,
    label: str,
    wall_timeout_seconds: float,
    max_output_bytes: int,
) -> int:
    """Wait for the leader, drain final output, and contain leaked helpers.

    Some provider launchers exit before a worker descendant emits the final
    response.  Keep capture active for one bounded grace period after a
    successful leader exit.  Provider-owned MCP servers may instead remain
    alive indefinitely; once the drain expires, terminate only the isolated
    provider group and require it to disappear.  A failed leader has no useful
    drain period and its descendants are contained immediately.
    """
    leader_exit_deadline: float | None = None
    while True:
        leader_status = leader_poll()
        group_exists = _process_group_exists(process_group)
        if overflow.is_set():
            raise LauncherError(
                f"{label} exceeded the {max_output_bytes}-byte output limit"
            )
        if leader_status is not None and not group_exists:
            return leader_status
        if leader_status is None and not group_exists:
            raise LauncherError(
                f"{label} process group disappeared before its leader was reaped"
            )
        now = time.monotonic()
        if leader_status is not None:
            if leader_status != 0:
                _terminate_process_group(
                    process_group,
                    grace_seconds=termination_grace_seconds,
                    leader_poll=leader_poll,
                )
                return leader_status
            if leader_exit_deadline is None:
                leader_exit_deadline = min(
                    deadline,
                    now + termination_grace_seconds,
                )
            if now >= leader_exit_deadline:
                _terminate_process_group(
                    process_group,
                    grace_seconds=termination_grace_seconds,
                    leader_poll=leader_poll,
                )
                return leader_status
        elif now >= deadline:
            raise LauncherError(
                f"{label} exceeded the {wall_timeout_seconds:g}s wall timeout"
            )
        time.sleep(0.02)


def _join_provider_threads(
    threads: Sequence[threading.Thread],
    *,
    grace_seconds: float,
    label: str,
) -> None:
    deadline = time.monotonic() + grace_seconds
    for thread in threads:
        thread.join(timeout=max(0.0, deadline - time.monotonic()))
    if any(thread.is_alive() for thread in threads):
        raise LauncherError(f"{label} stream cleanup did not finish")


def _cleanup_failed_provider_run(
    *,
    process_group: int,
    leader_poll: Callable[[], int | None],
    threads: Sequence[threading.Thread],
    grace_seconds: float,
    label: str,
    failure: LauncherError,
) -> None:
    """Contain a failed provider and retain the primary failure in the error."""
    cleanup_errors: list[str] = []
    try:
        _terminate_process_group(
            process_group,
            grace_seconds=grace_seconds,
            leader_poll=leader_poll,
        )
    except LauncherError as exc:
        cleanup_errors.append(str(exc))
    try:
        leader_poll()
    except (ChildProcessError, OSError) as exc:
        cleanup_errors.append(f"leader reap failed: {exc}")
    try:
        _join_provider_threads(
            threads,
            grace_seconds=grace_seconds,
            label=label,
        )
    except LauncherError as exc:
        cleanup_errors.append(str(exc))
    if _process_group_exists(process_group):
        cleanup_errors.append(f"process group {process_group} still exists")
    if cleanup_errors:
        raise LauncherError(
            f"{failure}; cleanup incomplete: {'; '.join(cleanup_errors)}"
        ) from failure
    raise failure


def _capture_stream(
    stream: Any,
    spool: Any,
    *,
    max_output_bytes: int,
    overflow: threading.Event,
) -> None:
    total = 0
    try:
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk:
                return
            total += len(chunk)
            remaining = max_output_bytes - spool.tell()
            if remaining > 0:
                spool.write(chunk[:remaining])
            if total > max_output_bytes:
                overflow.set()
    finally:
        stream.close()


def _write_process_input(stream: Any, payload: bytes) -> None:
    try:
        stream.write(payload)
        stream.flush()
    except (BrokenPipeError, OSError):
        pass
    finally:
        stream.close()


def _run_popen_command(
    *,
    argv: Sequence[str],
    executable_path: Path,
    pass_fds: Sequence[int] = (),
    input_bytes: bytes,
    cwd: Path,
    environment: Mapping[str, str],
    label: str,
    wall_timeout_seconds: float,
    termination_grace_seconds: float,
    max_output_bytes: int,
) -> subprocess.CompletedProcess[bytes]:
    """Run one command in a new process group with bounded, spooled output."""
    if wall_timeout_seconds <= 0 or termination_grace_seconds <= 0:
        raise LauncherError("wall timeout and termination grace must be positive")
    if max_output_bytes <= 0:
        raise LauncherError("maximum provider output must be positive")
    try:
        process = subprocess.Popen(
            list(argv),
            executable=str(executable_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            cwd=str(cwd),
            env=dict(environment),
            pass_fds=tuple(pass_fds),
            start_new_session=True,
        )
    except OSError as exc:
        raise LauncherError(f"cannot spawn {label}") from exc
    if process.stdin is None or process.stdout is None or process.stderr is None:
        raise LauncherError(f"cannot bind {label} standard streams")

    overflow = threading.Event()
    with (
        tempfile.SpooledTemporaryFile(max_size=OUTPUT_SPOOL_MEMORY_BYTES) as stdout_spool,
        tempfile.SpooledTemporaryFile(max_size=OUTPUT_SPOOL_MEMORY_BYTES) as stderr_spool,
    ):
        threads = (
            threading.Thread(
                target=_capture_stream,
                args=(process.stdout, stdout_spool),
                kwargs={
                    "max_output_bytes": max_output_bytes,
                    "overflow": overflow,
                },
                daemon=True,
            ),
            threading.Thread(
                target=_capture_stream,
                args=(process.stderr, stderr_spool),
                kwargs={
                    "max_output_bytes": max_output_bytes,
                    "overflow": overflow,
                },
                daemon=True,
            ),
            threading.Thread(
                target=_write_process_input,
                args=(process.stdin, input_bytes),
                daemon=True,
            ),
        )
        for thread in threads:
            thread.start()

        deadline = time.monotonic() + wall_timeout_seconds
        try:
            returncode = _wait_for_process_group_completion(
                process.pid,
                leader_poll=process.poll,
                overflow=overflow,
                deadline=deadline,
                termination_grace_seconds=termination_grace_seconds,
                label=label,
                wall_timeout_seconds=wall_timeout_seconds,
                max_output_bytes=max_output_bytes,
            )
        except LauncherError as exc:
            _cleanup_failed_provider_run(
                process_group=process.pid,
                leader_poll=process.poll,
                threads=threads,
                grace_seconds=termination_grace_seconds,
                label=label,
                failure=exc,
            )
            raise AssertionError("unreachable")

        _join_provider_threads(
            threads,
            grace_seconds=termination_grace_seconds,
            label=label,
        )
        if overflow.is_set():
            raise LauncherError(
                f"{label} exceeded the {max_output_bytes}-byte output limit"
            )
        stdout_spool.seek(0)
        stderr_spool.seek(0)
        return subprocess.CompletedProcess(
            args=list(argv),
            returncode=returncode,
            stdout=stdout_spool.read(),
            stderr=stderr_spool.read(),
        )


def _darwin_spawn_suspended(
    *,
    executable_path: Path,
    expected_cdhash: bytes,
    argv: Sequence[str],
    input_bytes: bytes,
    cwd: Path,
    environment: Mapping[str, str],
    label: str,
    wall_timeout_seconds: float,
    termination_grace_seconds: float,
    max_output_bytes: int,
) -> subprocess.CompletedProcess[bytes]:
    """Spawn suspended, attest the loaded vnode's CDHash, then allow execution."""
    libc = ctypes.CDLL(None, use_errno=True)
    attribute_type = ctypes.c_void_p
    actions_type = ctypes.c_void_p
    signatures = {
        "posix_spawnattr_init": ([ctypes.POINTER(attribute_type)], ctypes.c_int),
        "posix_spawnattr_setflags": (
            [ctypes.POINTER(attribute_type), ctypes.c_short],
            ctypes.c_int,
        ),
        "posix_spawnattr_setpgroup": (
            [ctypes.POINTER(attribute_type), ctypes.c_int],
            ctypes.c_int,
        ),
        "posix_spawnattr_destroy": ([ctypes.POINTER(attribute_type)], ctypes.c_int),
        "posix_spawn_file_actions_init": (
            [ctypes.POINTER(actions_type)],
            ctypes.c_int,
        ),
        "posix_spawn_file_actions_adddup2": (
            [ctypes.POINTER(actions_type), ctypes.c_int, ctypes.c_int],
            ctypes.c_int,
        ),
        "posix_spawn_file_actions_addclose": (
            [ctypes.POINTER(actions_type), ctypes.c_int],
            ctypes.c_int,
        ),
        "posix_spawn_file_actions_addchdir_np": (
            [ctypes.POINTER(actions_type), ctypes.c_char_p],
            ctypes.c_int,
        ),
        "posix_spawn_file_actions_destroy": (
            [ctypes.POINTER(actions_type)],
            ctypes.c_int,
        ),
        "posix_spawn": (
            [
                ctypes.POINTER(ctypes.c_int),
                ctypes.c_char_p,
                ctypes.POINTER(actions_type),
                ctypes.POINTER(attribute_type),
                ctypes.POINTER(ctypes.c_char_p),
                ctypes.POINTER(ctypes.c_char_p),
            ],
            ctypes.c_int,
        ),
        "csops": (
            [ctypes.c_int, ctypes.c_uint, ctypes.c_void_p, ctypes.c_size_t],
            ctypes.c_int,
        ),
    }
    for name, (argument_types, result_type) in signatures.items():
        try:
            function = getattr(libc, name)
        except AttributeError as exc:
            raise LauncherError(f"Darwin lacks required bound-spawn primitive: {name}") from exc
        function.argtypes = argument_types
        function.restype = result_type

    stdin_read, stdin_write = os.pipe()
    stdout_read, stdout_write = os.pipe()
    stderr_read, stderr_write = os.pipe()
    parent_descriptors = [stdin_write, stdout_read, stderr_read]
    child_descriptors = [stdin_read, stdout_write, stderr_write]
    actions = actions_type()
    attributes = attribute_type()
    actions_initialized = False
    attributes_initialized = False
    child_pid: int | None = None

    def require_zero(result: int, operation: str) -> None:
        if result != 0:
            raise LauncherError(f"Darwin {operation} failed with status {result}")

    try:
        require_zero(
            libc.posix_spawn_file_actions_init(ctypes.byref(actions)),
            "file-actions initialization",
        )
        actions_initialized = True
        require_zero(
            libc.posix_spawnattr_init(ctypes.byref(attributes)),
            "spawn-attribute initialization",
        )
        attributes_initialized = True
        for source, target in ((stdin_read, 0), (stdout_write, 1), (stderr_write, 2)):
            require_zero(
                libc.posix_spawn_file_actions_adddup2(
                    ctypes.byref(actions), source, target
                ),
                "descriptor duplication",
            )
        for descriptor in (*parent_descriptors, *child_descriptors):
            if descriptor not in (0, 1, 2):
                require_zero(
                    libc.posix_spawn_file_actions_addclose(
                        ctypes.byref(actions), descriptor
                    ),
                    "descriptor closure",
                )
        require_zero(
            libc.posix_spawn_file_actions_addchdir_np(
                ctypes.byref(actions), os.fsencode(cwd)
            ),
            "working-directory binding",
        )
        require_zero(
            libc.posix_spawnattr_setpgroup(ctypes.byref(attributes), 0),
            "process-group binding",
        )
        require_zero(
            libc.posix_spawnattr_setflags(
                ctypes.byref(attributes),
                0x0080 | 0x0002,
            ),
            "suspended-spawn and process-group flags",
        )
        argv_bytes = [os.fsencode(argument) for argument in argv]
        environment_bytes = [
            os.fsencode(f"{name}={value}") for name, value in environment.items()
        ]
        argv_array = (ctypes.c_char_p * (len(argv_bytes) + 1))(
            *argv_bytes, None
        )
        environment_array = (ctypes.c_char_p * (len(environment_bytes) + 1))(
            *environment_bytes, None
        )
        pid = ctypes.c_int()
        require_zero(
            libc.posix_spawn(
                ctypes.byref(pid),
                os.fsencode(executable_path),
                ctypes.byref(actions),
                ctypes.byref(attributes),
                argv_array,
                environment_array,
            ),
            f"{label} suspended spawn",
        )
        child_pid = pid.value
        for descriptor in child_descriptors:
            _close_descriptor(descriptor)
        child_descriptors.clear()

        actual_cdhash_buffer = (ctypes.c_ubyte * 20)()
        if (
            libc.csops(
                child_pid,
                5,
                ctypes.byref(actual_cdhash_buffer),
                len(actual_cdhash_buffer),
            )
            != 0
        ):
            error_number = ctypes.get_errno()
            raise LauncherError(
                f"cannot attest {label} suspended image CDHash: errno {error_number}"
            )
        actual_cdhash = bytes(actual_cdhash_buffer)
        if actual_cdhash != expected_cdhash:
            raise LauncherError(
                f"{label} executable changed at the Darwin spawn boundary"
            )

        overflow = threading.Event()
        with (
            tempfile.SpooledTemporaryFile(
                max_size=OUTPUT_SPOOL_MEMORY_BYTES
            ) as stdout_spool,
            tempfile.SpooledTemporaryFile(
                max_size=OUTPUT_SPOOL_MEMORY_BYTES
            ) as stderr_spool,
        ):
            threads = (
                threading.Thread(
                    target=_capture_descriptor,
                    args=(stdout_read, stdout_spool),
                    kwargs={
                        "max_output_bytes": max_output_bytes,
                        "overflow": overflow,
                    },
                    daemon=True,
                ),
                threading.Thread(
                    target=_capture_descriptor,
                    args=(stderr_read, stderr_spool),
                    kwargs={
                        "max_output_bytes": max_output_bytes,
                        "overflow": overflow,
                    },
                    daemon=True,
                ),
                threading.Thread(
                    target=_write_pipe,
                    args=(stdin_write, input_bytes),
                    daemon=True,
                ),
            )
            for thread in threads:
                thread.start()
            parent_descriptors.clear()
            os.kill(child_pid, signal.SIGCONT)
            deadline = time.monotonic() + wall_timeout_seconds
            status: int | None = None
            process_group = child_pid

            def poll_leader() -> int | None:
                nonlocal status
                if status is not None:
                    return status
                waited_pid, waited_status = os.waitpid(process_group, os.WNOHANG)
                if waited_pid == process_group:
                    status = waited_status
                return status

            try:
                status = _wait_for_process_group_completion(
                    process_group,
                    leader_poll=poll_leader,
                    overflow=overflow,
                    deadline=deadline,
                    termination_grace_seconds=termination_grace_seconds,
                    label=label,
                    wall_timeout_seconds=wall_timeout_seconds,
                    max_output_bytes=max_output_bytes,
                )
            except LauncherError as exc:
                try:
                    _cleanup_failed_provider_run(
                        process_group=process_group,
                        leader_poll=poll_leader,
                        threads=threads,
                        grace_seconds=termination_grace_seconds,
                        label=label,
                        failure=exc,
                    )
                finally:
                    child_pid = None
                raise AssertionError("unreachable")

            child_pid = None
            _join_provider_threads(
                threads,
                grace_seconds=termination_grace_seconds,
                label=label,
            )
            if overflow.is_set():
                raise LauncherError(
                    f"{label} exceeded the {max_output_bytes}-byte output limit"
                )
            stdout_spool.seek(0)
            stderr_spool.seek(0)
            stdout = stdout_spool.read()
            stderr = stderr_spool.read()
        return subprocess.CompletedProcess(
            args=list(argv),
            returncode=os.waitstatus_to_exitcode(status),
            stdout=stdout,
            stderr=stderr,
        )
    finally:
        if child_pid is not None:
            try:
                os.killpg(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(child_pid, 0)
            except ChildProcessError:
                pass
        for descriptor in (*parent_descriptors, *child_descriptors):
            _close_descriptor(descriptor)
        if actions_initialized:
            libc.posix_spawn_file_actions_destroy(ctypes.byref(actions))
        if attributes_initialized:
            libc.posix_spawnattr_destroy(ctypes.byref(attributes))


def _run_test_path_command(
    *,
    executable: PreparedExecutable,
    argv: Sequence[str],
    input_bytes: bytes,
    cwd: Path,
    environment: Mapping[str, str],
    label: str,
    wall_timeout_seconds: float,
    termination_grace_seconds: float,
    max_output_bytes: int,
) -> subprocess.CompletedProcess[bytes]:
    """Explicit test seam for script fixtures; production never selects it."""
    _assert_prepared_executable_unchanged(executable, label)
    return _run_popen_command(
        argv=argv,
        executable_path=executable.private_copy.path,
        input_bytes=input_bytes,
        cwd=cwd,
        environment=environment,
        label=label,
        wall_timeout_seconds=wall_timeout_seconds,
        termination_grace_seconds=termination_grace_seconds,
        max_output_bytes=max_output_bytes,
    )


def _run_bound_command(
    *,
    executable: PreparedExecutable,
    argv: Sequence[str],
    input_bytes: bytes,
    cwd: Path,
    environment: Mapping[str, str],
    label: str,
    wall_timeout_seconds: float,
    termination_grace_seconds: float,
    max_output_bytes: int,
) -> subprocess.CompletedProcess[bytes]:
    """Execute only the authenticated bytes, never a re-resolved mutable pathname."""
    if executable.private_copy.path == executable.canonical.path:
        if executable.canonical.path != PRODUCTION_CLIENTS.sandbox_exec:
            raise LauncherError(
                "canonical execution is reserved for /usr/bin/sandbox-exec"
            )
        _assert_prepared_executable_unchanged(executable, label)
        return _run_popen_command(
            argv=argv,
            executable_path=executable.canonical.path,
            input_bytes=input_bytes,
            cwd=cwd,
            environment=environment,
            label=label,
            wall_timeout_seconds=wall_timeout_seconds,
            termination_grace_seconds=termination_grace_seconds,
            max_output_bytes=max_output_bytes,
        )

    identity = executable.identity
    if (
        sys.platform == "darwin"
        and identity is not None
        and identity.darwin_spawn_canonical
    ):
        _attest_executable_identity(executable.canonical, identity, label)
        result = _darwin_spawn_suspended(
            executable_path=executable.canonical.path,
            expected_cdhash=bytes.fromhex(identity.cdhash),
            argv=argv,
            input_bytes=input_bytes,
            cwd=cwd,
            environment=environment,
            label=label,
            wall_timeout_seconds=wall_timeout_seconds,
            termination_grace_seconds=termination_grace_seconds,
            max_output_bytes=max_output_bytes,
        )
        _assert_prepared_executable_unchanged(executable, label)
        return result

    descriptor, payload = _open_authenticated_executable_descriptor(
        executable.private_copy,
        label,
    )
    try:
        if sys.platform == "darwin":
            return _darwin_spawn_suspended(
                executable_path=executable.private_copy.path,
                expected_cdhash=_macho_cdhash(payload),
                argv=argv,
                input_bytes=input_bytes,
                cwd=cwd,
                environment=environment,
                label=label,
                wall_timeout_seconds=wall_timeout_seconds,
                termination_grace_seconds=termination_grace_seconds,
                max_output_bytes=max_output_bytes,
            )
        if sys.platform.startswith("linux"):
            descriptor_path = Path(f"/proc/self/fd/{descriptor}")
            if not descriptor_path.exists():
                descriptor_path = Path(f"/dev/fd/{descriptor}")
            if not descriptor_path.exists():
                raise LauncherError("Linux lacks an executable descriptor filesystem")
            return _run_popen_command(
                argv=argv,
                executable_path=descriptor_path,
                pass_fds=(descriptor,),
                input_bytes=input_bytes,
                cwd=cwd,
                environment=environment,
                label=label,
                wall_timeout_seconds=wall_timeout_seconds,
                termination_grace_seconds=termination_grace_seconds,
                max_output_bytes=max_output_bytes,
            )
        raise LauncherError(f"bound executable dispatch is unsupported on {sys.platform}")
    finally:
        os.close(descriptor)


_VERSION_PATTERN = re.compile(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)")


def _client_version(
    executable: PreparedExecutable,
    environment: Mapping[str, str],
    command_runner: CommandRunner,
    *,
    cwd: Path,
    wall_timeout_seconds: float,
    termination_grace_seconds: float,
    max_output_bytes: int,
    argv: Sequence[str] | None = None,
) -> tuple[str, tuple[int, int, int]]:
    version_argv = (
        tuple(argv)
        if argv is not None
        else (str(executable.canonical.path), "--version")
    )
    result = command_runner(
        executable=executable,
        argv=version_argv,
        input_bytes=b"",
        cwd=cwd,
        environment=environment,
        label="client version",
        wall_timeout_seconds=wall_timeout_seconds,
        termination_grace_seconds=termination_grace_seconds,
        max_output_bytes=max_output_bytes,
    )
    if result.returncode != 0:
        raise LauncherError(
            f"client version command failed for {executable.canonical.path}"
        )
    output = bytes(result.stdout).decode("utf-8", errors="replace").strip()
    match = _VERSION_PATTERN.search(output)
    if match is None:
        raise LauncherError(
            f"client version is not parseable for {executable.canonical.path}"
        )
    return output, tuple(int(component) for component in match.groups())


_SAFE_ENVIRONMENT_NAMES = {
    "LANG",
    "LC_ALL",
    "NODE_EXTRA_CA_CERTS",
    "PATH",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "TZ",
    "USER",
}


def _base_environment(source: Mapping[str, str]) -> dict[str, str]:
    return {name: source[name] for name in _SAFE_ENVIRONMENT_NAMES if name in source}


def _route_environment(
    seat: Seat,
    *,
    source: Mapping[str, str],
    sandbox: Path,
) -> dict[str, str]:
    environment = _base_environment(source)
    environment.pop("ANTHROPIC_API_KEY", None)
    environment["HOME"] = str(sandbox)
    environment["TMPDIR"] = str(sandbox)
    environment["XDG_CACHE_HOME"] = str(sandbox)
    environment["XDG_CONFIG_HOME"] = str(sandbox)
    environment["XDG_DATA_HOME"] = str(sandbox)
    environment["XDG_STATE_HOME"] = str(sandbox)
    if seat.name == "fable":
        for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN"):
            if name in source:
                environment[name] = source[name]
    return environment


def _sandbox(
    *,
    prefix: str = "worker-plane-review-cwd.",
) -> tuple[Path, SandboxProof]:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    os.chmod(path, 0o700)
    metadata = path.stat()
    entries = tuple(sorted(child.name for child in path.iterdir()))
    proof = SandboxProof(
        path=path.resolve(),
        mode=stat.S_IMODE(metadata.st_mode),
        device=metadata.st_dev,
        inode=metadata.st_ino,
        initial_entries=entries,
    )
    if proof.mode != 0o700 or proof.initial_entries:
        try:
            shutil.rmtree(path)
        except OSError as exc:
            raise LauncherError("review cwd cleanup failed") from exc
        raise LauncherError("review cwd is not newly created, empty, and mode 0700")
    return path, proof


def _remove_sandbox(path: Path) -> None:
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise LauncherError("review cwd cleanup path is not a directory")
        os.chmod(path, 0o700)
        shutil.rmtree(path)
    except LauncherError:
        raise
    except OSError as exc:
        raise LauncherError("review cwd cleanup failed") from exc
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise LauncherError("review cwd cleanup could not be verified") from exc
    raise LauncherError("review cwd cleanup left residue")


def _write_private_data(path: Path, payload: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fchmod(handle.fileno(), mode)
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _copy_private_data(source: Path, target: Path, label: str) -> None:
    payload, _ = _read_regular_file(source, label)
    _write_private_data(target, payload)


def _seed_kimi_home(home: Path, *, production: bool) -> None:
    config_root = home / ".kimi-code"
    (config_root / "credentials").mkdir(parents=True, mode=0o700)
    if not production:
        return
    source_root = Path("/Users/nuzantara/.kimi-code")
    for relative in (
        Path("config.toml"),
        Path("device_id"),
        Path("credentials/kimi-code.json"),
    ):
        _copy_private_data(
            source_root / relative,
            config_root / relative,
            f"Kimi credential material {relative}",
        )


def _seed_codex_home(home: Path, *, production: bool) -> tuple[AuthenticatedFile, ...]:
    config_root = home / ".codex"
    config_root.mkdir(parents=True, mode=0o700)
    if not production:
        return ()
    source_root = Path("/Users/nuzantara/.codex")
    seeded: list[AuthenticatedFile] = []
    for relative in (Path("auth.json"), Path("config.toml")):
        target = config_root / relative
        _copy_private_data(
            source_root / relative,
            target,
            f"Codex credential material {relative}",
        )
        seeded.append(_authenticate_file(target, f"seeded Codex {relative}"))
    return tuple(seeded)


def _split_utf8_text(value: str, *, max_bytes: int) -> tuple[str, ...]:
    if max_bytes <= 0:
        raise LauncherError("Kimi transport segment limit must be positive")
    segments: list[str] = []
    characters: list[str] = []
    byte_count = 0
    for character in value:
        encoded = character.encode("utf-8")
        if len(encoded) > max_bytes:
            raise LauncherError("Kimi transport cannot represent one UTF-8 character")
        if characters and byte_count + len(encoded) > max_bytes:
            segments.append("".join(characters))
            characters = []
            byte_count = 0
        characters.append(character)
        byte_count += len(encoded)
    if characters or not segments:
        segments.append("".join(characters))
    return tuple(segments)


def _kimi_review_transport_bytes(review_input_bytes: bytes) -> bytes:
    """Render one lossless, Read-safe view of the immutable review input.

    Kimi Code 0.29 caps each ``Read`` result at 1,000 lines / 100 KiB and
    truncates individual lines after 2,000 characters.  The source packet is
    therefore wrapped only where needed, with an explicit reconstruction rule;
    the parser later proves that every rendered transport line was returned by
    the local Read tool with exact content.
    """
    try:
        source = review_input_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LauncherError("Kimi review input is not UTF-8") from exc
    if "\x00" in source or "\r" in source or not source.endswith("\n"):
        raise LauncherError("Kimi review input must use canonical LF termination")

    source_lines = source[:-1].split("\n")
    source_sha256 = _sha256(review_input_bytes)
    marker = f"NUZANTARA-KIMI-CONTINUATION-{source_sha256[:16]}"
    begin_marker = f"{marker}-BEGIN-SOURCE-REVIEW-INPUT"
    end_marker = f"{marker}-END-SOURCE-REVIEW-INPUT"
    if any(line.startswith(marker) for line in source_lines):
        raise LauncherError("Kimi transport continuation marker collides with input")

    transport_lines = [
        KIMI_TRANSPORT_SCHEMA,
        f"SOURCE_REVIEW_INPUT_SHA256 {source_sha256}",
        f"SOURCE_REVIEW_INPUT_BYTES {len(review_input_bytes)}",
        f"SOURCE_REVIEW_INPUT_LINES {len(source_lines)}",
        (
            f"RECONSTRUCTION_RULE After {begin_marker}, ordinary lines are "
            "source lines. For continuation records, concatenate the text "
            "after the first TAB in ascending part order with no separator "
            "to recover that one source line."
        ),
        f"CONTINUATION_MARKER {marker}",
        f"BEGIN_MARKER {begin_marker}",
        f"END_MARKER {end_marker}",
        begin_marker,
    ]
    reconstructed_lines: list[str] = []
    for line_number, line in enumerate(source_lines, start=1):
        if len(line.encode("utf-8")) <= KIMI_TRANSPORT_SEGMENT_BYTES:
            transport_lines.append(line)
            reconstructed_lines.append(line)
            continue
        segments = _split_utf8_text(
            line,
            max_bytes=KIMI_TRANSPORT_SEGMENT_BYTES,
        )
        for part_number, segment in enumerate(segments, start=1):
            transport_lines.append(
                f"{marker} line={line_number} "
                f"part={part_number}/{len(segments)}\t{segment}"
            )
        reconstructed_lines.append("".join(segments))
    transport_lines.append(end_marker)

    reconstructed = ("\n".join(reconstructed_lines) + "\n").encode("utf-8")
    if reconstructed != review_input_bytes:
        raise LauncherError("Kimi lossless transport failed reconstruction")
    if any(
        len(line.encode("utf-8")) > KIMI_TRANSPORT_MAX_LINE_BYTES
        for line in transport_lines
    ):
        raise LauncherError("Kimi transport contains an over-limit line")
    return ("\n".join(transport_lines) + "\n").encode("utf-8")


def _utf16_code_units(value: str) -> int:
    """Return JavaScript ``String.length`` for canonical Unicode text."""
    return len(value.encode("utf-16-le")) // 2


def _kimi_read_page_plan(
    transport_bytes: bytes,
) -> tuple[tuple[int, int], ...]:
    """Partition one transport into exact Read results below Kimi's caps.

    Kimi Code 0.29 persists and replaces tool results above 50,000 JavaScript
    string units with a short preview.  Every declared page therefore remains
    comfortably below that framework threshold and the Read tool's own
    1,000-line / 100-KiB limits.  The accounting includes the decimal line
    number, TAB separator, and inter-line newlines emitted by Read.
    """
    try:
        text = transport_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LauncherError("Kimi review transport is not UTF-8") from exc
    if "\r" in text or not text.endswith("\n"):
        raise LauncherError("Kimi review transport is not canonical LF text")
    transport_lines = tuple(text[:-1].split("\n"))
    if not transport_lines:
        raise LauncherError("Kimi review transport is empty")

    pages: list[tuple[int, int]] = []
    next_index = 0
    while next_index < len(transport_lines):
        page_offset = next_index + 1
        page_lines = 0
        page_utf16_units = 0
        page_utf8_bytes = 0
        while (
            next_index + page_lines < len(transport_lines)
            and page_lines < KIMI_READ_MAX_LINES
        ):
            line_number = next_index + page_lines + 1
            separator = "" if page_lines == 0 else "\n"
            rendered = f"{separator}{line_number}\t{transport_lines[line_number - 1]}"
            rendered_utf16_units = _utf16_code_units(rendered)
            rendered_utf8_bytes = len(rendered.encode("utf-8"))
            if page_lines and (
                page_utf16_units + rendered_utf16_units > KIMI_READ_PAGE_MAX_UTF16_UNITS
                or page_utf8_bytes + rendered_utf8_bytes > KIMI_READ_PAGE_MAX_UTF8_BYTES
            ):
                break
            if (
                rendered_utf16_units > KIMI_READ_PAGE_MAX_UTF16_UNITS
                or rendered_utf8_bytes > KIMI_READ_PAGE_MAX_UTF8_BYTES
            ):
                raise LauncherError("one Kimi transport line exceeds a Read page")
            page_utf16_units += rendered_utf16_units
            page_utf8_bytes += rendered_utf8_bytes
            page_lines += 1
        if page_lines == 0:
            raise LauncherError("Kimi Read page planner made no progress")
        pages.append((page_offset, page_lines))
        if len(pages) > KIMI_READ_MAX_PAGES:
            raise LauncherError("Kimi review transport exceeds the page-count limit")
        next_index += page_lines
    return tuple(pages)


def _kimi_review_prompt(input_path: Path, transport_bytes: bytes) -> str:
    page_plan = json.dumps(
        _kimi_read_page_plan(transport_bytes),
        separators=(",", ":"),
    )
    return (
        "Read every line of the lossless immutable review transport at:\n"
        f"@{input_path}\n"
        "Use Read exactly once for each canonical page below, in the listed "
        "order. Every call must explicitly provide this exact path plus the "
        "listed line_offset and n_lines. Do not read any other path or range.\n"
        f"NUZANTARA_KIMI_READ_PAGE_PLAN {page_plan}\n"
        "The transport header explains how to reconstruct continued source "
        "lines. Complete every declared Read page before answering. "
        "Follow its instruction brief exactly. "
        "Do not modify any file. Return only the required review."
    )


def _gemini_review_prompt(input_path: Path, review_input_bytes: bytes) -> str:
    return (
        "Read every byte of the sole immutable review input file at this exact "
        f"path: {input_path}\n"
        f"NUZANTARA_GEMINI_REVIEW_INPUT_BYTES {len(review_input_bytes)}\n"
        f"NUZANTARA_GEMINI_REVIEW_INPUT_SHA256 {_sha256(review_input_bytes)}\n"
        "Use read-only terminal/file tools and bounded sequential chunks until "
        "you have consumed the complete file. Do not inspect any other path. "
        "Follow the sole role=instructions document inside that input exactly. "
        "In # Blocking findings and # Important findings, start every "
        "unindented paragraph or list item with [GEMINI-PLAN-NNN]. Indent any "
        "supporting Evidence, Impact, Amendment, or Test bullet by at least two "
        "spaces beneath that finding ID; never emit an unindented support "
        "bullet without its own finding ID. "
        "Do not modify any file. Return only the required Markdown review, "
        "starting with # Verdict and with no preamble."
    )


def _prepare_gemini_read_only_input(
    *,
    cwd: Path,
    review_input_bytes: bytes,
) -> Path:
    input_path = cwd / "00-review-input.bin"
    _write_private_data(input_path, review_input_bytes, 0o400)
    return input_path


def _sandbox_profile_bytes(writable_home: Path) -> bytes:
    rendered_home = json.dumps(str(writable_home.resolve()))
    profile = (
        "(version 1)\n"
        "(deny default)\n"
        "(allow process*)\n"
        "(allow network*)\n"
        "(allow file-read*)\n"
        "(allow mach-lookup)\n"
        "(allow sysctl-read)\n"
        "(allow ipc-posix*)\n"
        f"(allow file-write* (subpath {rendered_home}))\n"
    )
    return profile.encode("utf-8")


def _prepare_kimi_read_only_inputs(
    *,
    cwd: Path,
    home: Path,
    review_input_bytes: bytes,
    production: bool,
) -> tuple[Path, Path, Path, str, str]:
    _seed_kimi_home(home, production=production)
    input_path = cwd / "00-review-input.transport.txt"
    profile_path = cwd / "kimi-read-only.sb"
    canary_path = cwd / "write-denied.canary"
    _write_private_data(
        input_path,
        _kimi_review_transport_bytes(review_input_bytes),
        0o400,
    )
    profile_bytes = _sandbox_profile_bytes(home)
    _write_private_data(profile_path, profile_bytes, 0o400)
    canary_bytes = b"nuzantara-worker-plane-read-only-canary-v1\n"
    _write_private_data(canary_path, canary_bytes, 0o400)
    return (
        input_path,
        profile_path,
        canary_path,
        _sha256(profile_bytes),
        _sha256(canary_bytes),
    )


def _prove_canary_write_denied(
    *,
    sandbox_exec: PreparedExecutable,
    profile_path: Path,
    canary_path: Path,
    cwd: Path,
    environment: Mapping[str, str],
    command_runner: CommandRunner,
    wall_timeout_seconds: float,
    termination_grace_seconds: float,
    max_output_bytes: int,
) -> tuple[str, str]:
    before_bytes, before_proof = _read_regular_file(canary_path, "Kimi canary")
    before_sha256 = _sha256(before_bytes)
    result = command_runner(
        executable=sandbox_exec,
        argv=(
            str(sandbox_exec.canonical.path),
            "-f",
            str(profile_path),
            "/usr/bin/touch",
            str(canary_path),
        ),
        input_bytes=b"",
        cwd=cwd,
        environment=environment,
        label="kimi-canary-write-probe",
        wall_timeout_seconds=min(wall_timeout_seconds, 10.0),
        termination_grace_seconds=termination_grace_seconds,
        max_output_bytes=min(max_output_bytes, 64 * 1024),
    )
    after_bytes, after_proof = _read_regular_file(canary_path, "Kimi canary")
    after_sha256 = _sha256(after_bytes)
    if result.returncode == 0:
        raise LauncherError("Kimi OS sandbox allowed the canary write")
    if before_sha256 != after_sha256 or before_proof != after_proof:
        raise LauncherError("Kimi canary changed during denied write probe")
    return before_sha256, after_sha256


def _run_seat(
    *,
    seat: Seat,
    executable: PreparedExecutable,
    runner_executable: PreparedExecutable | None,
    execution_prefix: Sequence[str],
    client_artifacts: Sequence[AuthenticatedFile],
    client_version: str,
    review_input_bytes: bytes,
    input_path: Path | None,
    cwd: Path,
    home: Path,
    environment: Mapping[str, str],
    invocation_uuid: str,
    command_runner: CommandRunner,
    wall_timeout_seconds: float,
    termination_grace_seconds: float,
    max_output_bytes: int,
    sandbox_profile_sha256: str | None = None,
    canary_sha256_before: str | None = None,
    canary_sha256_after: str | None = None,
) -> SeatRun:
    if seat.input_transport == "file":
        if input_path is None:
            raise LauncherError(f"{seat.name} requires file-based review input")
        attested_input_bytes = _read_regular_file(
            input_path,
            f"{seat.name} review input",
        )[0]
        if seat.client == "kimi":
            prompt = _kimi_review_prompt(input_path, attested_input_bytes)
            provider_args = (*seat.argv_suffix, "--prompt", prompt)
        elif seat.client == "gemini":
            prompt = _gemini_review_prompt(input_path, attested_input_bytes)
            provider_args = (*seat.argv_suffix, "--print", prompt)
        else:
            raise LauncherError(
                f"{seat.name} has no canonical file-input invocation"
            )
        stdin_bytes = b""
        pre_run_input_sha256 = _sha256(attested_input_bytes)
    else:
        if input_path is not None:
            raise LauncherError(f"{seat.name} must consume review input on stdin")
        provider_args = seat.argv_suffix
        stdin_bytes = review_input_bytes
        attested_input_bytes = review_input_bytes
        pre_run_input_sha256 = _sha256(review_input_bytes)
    actual_runner = runner_executable or executable
    if runner_executable is None:
        argv = (
            str(executable.canonical.path),
            *execution_prefix,
            *provider_args,
        )
    else:
        argv = (
            str(actual_runner.canonical.path),
            *execution_prefix,
            str(executable.canonical.path),
            *provider_args,
        )
    started_at_utc = _utc_now()
    result = command_runner(
        executable=actual_runner,
        argv=argv,
        input_bytes=stdin_bytes,
        cwd=cwd,
        environment=environment,
        label=seat.name,
        wall_timeout_seconds=wall_timeout_seconds,
        termination_grace_seconds=termination_grace_seconds,
        max_output_bytes=max_output_bytes,
    )
    ended_at_utc = _utc_now()
    post_run_input_sha256 = (
        _sha256(_read_regular_file(input_path, f"{seat.name} review input")[0])
        if input_path is not None
        else _sha256(review_input_bytes)
    )
    if pre_run_input_sha256 != post_run_input_sha256:
        raise LauncherError(f"{seat.name} review input changed during invocation")
    wrapper_identity = (
        runner_executable.identity if runner_executable is not None else None
    )
    return SeatRun(
        seat=seat,
        launcher_invocation_uuid=invocation_uuid,
        executable=executable.canonical.path,
        executable_copy=executable.private_copy.path,
        executable_sha256=executable.canonical.sha256,
        executable_identity=executable.identity,
        execution_wrapper=(
            runner_executable.canonical.path
            if runner_executable is not None
            else None
        ),
        execution_wrapper_sha256=(
            runner_executable.canonical.sha256
            if runner_executable is not None
            else None
        ),
        execution_wrapper_identity=wrapper_identity,
        client_artifact_sha256=tuple(
            (artifact.path.name, artifact.sha256) for artifact in client_artifacts
        ),
        client_version=client_version,
        argv=argv,
        started_at_utc=started_at_utc,
        ended_at_utc=ended_at_utc,
        returncode=result.returncode,
        stdout=bytes(result.stdout),
        stderr=bytes(result.stderr),
        wall_timeout_seconds=wall_timeout_seconds,
        max_output_bytes=max_output_bytes,
        sandbox_enforced=runner_executable is not None,
        sandbox_profile_sha256=sandbox_profile_sha256,
        canary_sha256_before=canary_sha256_before,
        canary_sha256_after=canary_sha256_after,
        canary_write_denied=(
            True if canary_sha256_before is not None else None
        ),
        pre_run_input_sha256=pre_run_input_sha256,
        post_run_input_sha256=post_run_input_sha256,
        input_bytes=attested_input_bytes,
        home_path=home,
    )


def _safe_provider_string(value: Any) -> str | None:
    if (
        isinstance(value, str)
        and value
        and not any(character in value for character in ("\x00", "\n", "\r"))
    ):
        return value
    return None


def _provider_metadata(run: SeatRun) -> tuple[str | None, str | None]:
    if run.seat.client in {"kimi", "codex"}:
        # Neither stream format emits a provider-attested model identity.
        # ``requested_route`` records what the launcher asked for; do not
        # present that request as a provider report.
        return None, None
    if run.seat.client != "fable":
        return None, None
    try:
        envelope = json.loads(run.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, None
    if not isinstance(envelope, dict):
        return None, None
    provider_session_id = _safe_provider_string(envelope.get("session_id"))
    if envelope.get("session_id") is not None and provider_session_id is None:
        raise LauncherError(f"{run.seat.name} emitted an invalid session_id")
    direct_model = _safe_provider_string(envelope.get("model"))
    if envelope.get("model") is not None and direct_model is None:
        raise LauncherError(f"{run.seat.name} emitted an invalid model")

    usage_model: str | None = None
    if "modelUsage" in envelope:
        model_usage = envelope["modelUsage"]
        if not isinstance(model_usage, dict) or not all(
            _safe_provider_string(model) is not None and isinstance(usage, dict)
            for model, usage in model_usage.items()
        ):
            raise LauncherError(f"{run.seat.name} emitted invalid modelUsage")
        if run.seat.requested_route in model_usage:
            usage_model = run.seat.requested_route
        elif len(model_usage) == 1:
            usage_model = next(iter(model_usage))
        elif model_usage:
            raise LauncherError(f"{run.seat.name} emitted ambiguous modelUsage")
    if (
        direct_model is not None
        and usage_model is not None
        and direct_model != usage_model
    ):
        raise LauncherError(f"{run.seat.name} emitted disagreeing model fields")
    reported_model = direct_model or usage_model
    return provider_session_id, reported_model


def _jsonl_objects(payload: bytes, label: str) -> tuple[dict[str, Any], ...]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LauncherError(f"{label} stream is not UTF-8") from exc
    objects: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LauncherError(
                f"{label} stream has invalid JSON at line {line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise LauncherError(
                f"{label} stream line {line_number} is not an object"
            )
        objects.append(value)
    if not objects:
        raise LauncherError(f"{label} stream is empty")
    return tuple(objects)


def _expected_kimi_input_path(run: SeatRun) -> str:
    prompt_indexes = [
        index for index, argument in enumerate(run.argv) if argument == "--prompt"
    ]
    if len(prompt_indexes) != 1:
        raise LauncherError("Kimi invocation lacks one exact prompt argument")
    prompt_index = prompt_indexes[0]
    if prompt_index + 1 >= len(run.argv):
        raise LauncherError("Kimi invocation lacks prompt content")
    prompt = run.argv[prompt_index + 1]
    prefix = "Read every line of the lossless immutable review transport at:\n@"
    if not prompt.startswith(prefix):
        raise LauncherError("Kimi invocation prompt differs from the canonical form")
    input_path, separator, _ = prompt[len(prefix) :].partition("\n")
    if not input_path or "\n" in input_path or "\r" in input_path:
        raise LauncherError("Kimi invocation contains an invalid input path")
    if separator != "\n" or prompt != _kimi_review_prompt(
        Path(input_path),
        run.input_bytes,
    ):
        raise LauncherError("Kimi invocation prompt differs from the canonical form")
    return input_path


def _expected_kimi_transport_lines(run: SeatRun) -> tuple[str, ...]:
    payload = run.input_bytes
    if _sha256(payload) != run.pre_run_input_sha256:
        raise LauncherError("Kimi review transport differs from its attested input")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LauncherError("Kimi review transport is not UTF-8") from exc
    if "\r" in text or not text.endswith("\n"):
        raise LauncherError("Kimi review transport is not canonical LF text")
    lines = tuple(text[:-1].split("\n"))
    if not lines or lines[0] != KIMI_TRANSPORT_SCHEMA:
        raise LauncherError("Kimi review transport schema is not supported")
    return lines


def _register_kimi_read_calls(
    value: Mapping[str, Any],
    *,
    expected_input_path: str,
    planned_read_pages: tuple[tuple[int, int], ...],
    pending_tool_reads: dict[str, tuple[int, int]],
    seen_read_pages: list[tuple[int, int]],
    seen_tool_ids: set[str],
) -> None:
    tool_calls = value.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls or pending_tool_reads:
        raise LauncherError(
            "Kimi must issue canonical Read pages only with no result pending"
        )
    staged_reads: list[tuple[str, tuple[int, int]]] = []
    staged_tool_ids: set[str] = set()
    staged_read_pages: set[tuple[int, int]] = set()
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict) or tool_call.get("type") != "function":
            raise LauncherError("Kimi emitted an invalid tool call")
        tool_call_id = tool_call.get("id")
        function = tool_call.get("function")
        if (
            not isinstance(tool_call_id, str)
            or not tool_call_id
            or tool_call_id in seen_tool_ids
            or tool_call_id in staged_tool_ids
            or not isinstance(function, dict)
            or function.get("name") != "Read"
            or not isinstance(function.get("arguments"), str)
        ):
            raise LauncherError("Kimi emitted an invalid Read call")
        try:
            arguments = json.loads(function["arguments"])
        except json.JSONDecodeError as exc:
            raise LauncherError("Kimi Read call arguments are invalid JSON") from exc
        if (
            not isinstance(arguments, dict)
            or arguments.get("path") != expected_input_path
            or set(arguments) != {"path", "line_offset", "n_lines"}
        ):
            raise LauncherError("Kimi attempted to read outside its review input")
        line_offset = arguments["line_offset"]
        n_lines = arguments["n_lines"]
        if (
            isinstance(line_offset, bool)
            or not isinstance(line_offset, int)
            or line_offset < 1
            or isinstance(n_lines, bool)
            or not isinstance(n_lines, int)
            or not 1 <= n_lines <= KIMI_READ_MAX_LINES
        ):
            raise LauncherError("Kimi emitted an invalid Read range")
        read_page = (line_offset, n_lines)
        next_page_index = len(seen_read_pages) + len(staged_reads)
        if (
            read_page in seen_read_pages
            or read_page in staged_read_pages
            or next_page_index >= len(planned_read_pages)
            or read_page != planned_read_pages[next_page_index]
        ):
            raise LauncherError("Kimi Read call differs from the canonical page plan")
        staged_tool_ids.add(tool_call_id)
        staged_read_pages.add(read_page)
        staged_reads.append((tool_call_id, read_page))
    seen_tool_ids.update(staged_tool_ids)
    seen_read_pages.extend(read_page for _, read_page in staged_reads)
    pending_tool_reads.update(staged_reads)


def _consume_kimi_read_result(
    value: Mapping[str, Any],
    *,
    pending_tool_reads: dict[str, tuple[int, int]],
    transport_lines: tuple[str, ...],
    covered_lines: set[int],
) -> None:
    tool_call_id = value.get("tool_call_id")
    content = value.get("content")
    if (
        not isinstance(tool_call_id, str)
        or tool_call_id not in pending_tool_reads
        or not isinstance(content, str)
        or not content
        or "\r" in content
    ):
        raise LauncherError("Kimi emitted an invalid Read result")
    expected_tool_call_id = next(iter(pending_tool_reads))
    if tool_call_id != expected_tool_call_id:
        raise LauncherError("Kimi Read results are out of canonical order")
    line_offset, n_lines = pending_tool_reads[tool_call_id]
    rendered_lines = content.split("\n")
    if len(rendered_lines) != n_lines or len(rendered_lines) > KIMI_READ_MAX_LINES:
        raise LauncherError("Kimi Read result lacks its exact requested range")
    validated_line_numbers: list[int] = []
    for index, rendered_line in enumerate(rendered_lines):
        prefix, separator, actual = rendered_line.partition("\t")
        expected_line_number = line_offset + index
        if (
            separator != "\t"
            or prefix != str(expected_line_number)
            or expected_line_number > len(transport_lines)
            or actual != transport_lines[expected_line_number - 1]
        ):
            raise LauncherError("Kimi Read result differs from the review transport")
        validated_line_numbers.append(expected_line_number)
    pending_tool_reads.pop(tool_call_id)
    covered_lines.update(validated_line_numbers)


def _extract_review_body(run: SeatRun) -> bytes:
    if run.seat.client == "gemini":
        try:
            run.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LauncherError("Gemini raw response is not UTF-8") from exc
        return run.stdout
    if run.seat.client == "kimi":
        assistant_message: str | None = None
        pending_tool_reads: dict[str, tuple[int, int]] = {}
        seen_tool_ids: set[str] = set()
        seen_read_pages: list[tuple[int, int]] = []
        covered_lines: set[int] = set()
        expected_input_path = _expected_kimi_input_path(run)
        transport_lines = _expected_kimi_transport_lines(run)
        planned_read_pages = _kimi_read_page_plan(run.input_bytes)
        events = _jsonl_objects(run.stdout, "Kimi")
        for event_index, value in enumerate(events):
            if value.get("role") == "assistant":
                content = value.get("content")
                if "tool_calls" in value:
                    if assistant_message is not None or (
                        content is not None and not isinstance(content, str)
                    ):
                        raise LauncherError(
                            "Kimi emitted an invalid assistant tool event"
                        )
                    _register_kimi_read_calls(
                        value,
                        expected_input_path=expected_input_path,
                        planned_read_pages=planned_read_pages,
                        pending_tool_reads=pending_tool_reads,
                        seen_read_pages=seen_read_pages,
                        seen_tool_ids=seen_tool_ids,
                    )
                    continue
                if isinstance(content, str) and content:
                    if assistant_message is not None:
                        raise LauncherError("Kimi emitted multiple review responses")
                    if pending_tool_reads:
                        raise LauncherError(
                            "Kimi emitted review text before its Read call completed"
                        )
                    if len(covered_lines) != len(transport_lines):
                        raise LauncherError(
                            "Kimi emitted review text before reading the full transport"
                        )
                    assistant_message = content
                    continue
                if content is not None or assistant_message is not None:
                    raise LauncherError("Kimi emitted an invalid assistant event")
                raise LauncherError("Kimi assistant event lacks content or tool calls")
            if value.get("role") == "tool":
                if assistant_message is not None:
                    raise LauncherError("Kimi emitted a tool result after its review")
                _consume_kimi_read_result(
                    value,
                    pending_tool_reads=pending_tool_reads,
                    transport_lines=transport_lines,
                    covered_lines=covered_lines,
                )
                continue
            if (
                value.get("role") == "meta"
                and value.get("type") == "session.resume_hint"
            ):
                if event_index != len(events) - 1:
                    raise LauncherError("Kimi resume hint is not the final event")
                if pending_tool_reads:
                    raise LauncherError("Kimi stream ended with an incomplete Read call")
                continue
            raise LauncherError("Kimi stream contains an unexpected event")
        if pending_tool_reads:
            raise LauncherError("Kimi stream ended with an incomplete Read call")
        if (
            not events
            or events[-1].get("role") != "meta"
            or events[-1].get("type") != "session.resume_hint"
        ):
            raise LauncherError("Kimi stream lacks a terminal resume hint")
        if len(covered_lines) != len(transport_lines):
            raise LauncherError("Kimi stream did not read the full review transport")
        if tuple(seen_read_pages) != planned_read_pages:
            raise LauncherError("Kimi stream did not complete its canonical page plan")
        if assistant_message is None:
            raise LauncherError("Kimi stream lacks an assistant event")
        return assistant_message.encode("utf-8")
    if run.seat.client == "codex":
        assistant_messages: list[str] = []
        for value in _jsonl_objects(run.stdout, "Codex"):
            if value.get("type") != "item.completed":
                continue
            item = value.get("item")
            if (
                isinstance(item, dict)
                and item.get("type") == "agent_message"
                and isinstance(item.get("text"), str)
                and item["text"]
            ):
                assistant_messages.append(item["text"])
        if not assistant_messages:
            raise LauncherError("Codex stream lacks a completed agent message")
        return assistant_messages[-1].encode("utf-8")
    if run.seat.client != "fable":
        raise LauncherError(f"unsupported review client: {run.seat.client}")
    try:
        envelope = json.loads(run.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LauncherError(f"{run.seat.name} raw JSON response is invalid") from exc
    if not isinstance(envelope, dict) or not isinstance(envelope.get("result"), str):
        raise LauncherError(f"{run.seat.name} raw JSON lacks a string result")
    try:
        return envelope["result"].encode("utf-8")
    except UnicodeEncodeError as exc:
        raise LauncherError(f"{run.seat.name} result is not canonical UTF-8") from exc


def _validate_phase1_review_body(
    *,
    seat: Seat,
    body: bytes,
    input_manifest_sha256: str,
) -> None:
    """Enforce the complete Phase-1 Markdown contract before publication."""
    if seat.name not in PHASE1_FINDING_PREFIX:
        raise LauncherError(f"{seat.name} is not a Phase-1 review seat")
    if re.fullmatch(r"[0-9a-f]{64}", input_manifest_sha256) is None:
        raise LauncherError("Phase-1 review manifest SHA-256 is invalid")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LauncherError(f"{seat.name} review body is not UTF-8") from exc
    if len(re.findall(r"\S+", text)) > PHASE1_REVIEW_MAX_WORDS:
        raise LauncherError(
            f"{seat.name} review exceeds the {PHASE1_REVIEW_MAX_WORDS}-word limit"
        )

    matches = list(re.finditer(r"^# [^\n]+$", text, flags=re.MULTILINE))
    headings = tuple(match.group(0) for match in matches)
    if headings != PHASE1_REVIEW_HEADINGS:
        raise LauncherError(
            f"{seat.name} review headings are missing, extra, or out of order"
        )
    if not matches or text[: matches[0].start()].strip():
        raise LauncherError(f"{seat.name} review contains text before # Verdict")

    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(0)] = text[start:end].strip()
    for heading, section in sections.items():
        if (
            heading in ("# Blocking findings", "# Important findings")
            and section == "None"
        ):
            continue
        normalized = section.lower().rstrip(".")
        if normalized in PHASE1_PLACEHOLDERS or "<placeholder" in normalized:
            raise LauncherError(
                f"{seat.name} review has placeholder content under {heading}"
            )

    verdict_lines = [
        line.strip()
        for line in sections["# Verdict"].splitlines()
        if line.strip()
    ]
    if len(verdict_lines) < 2 or PHASE1_VERDICT.fullmatch(verdict_lines[0]) is None:
        raise LauncherError(f"{seat.name} review verdict line is invalid")
    expected_manifest_line = (
        f"input_manifest_sha256: {input_manifest_sha256}"
    )
    if verdict_lines[1] != expected_manifest_line:
        raise LauncherError(
            f"{seat.name} review verdict does not bind the attested manifest"
        )
    if (
        sum(line == expected_manifest_line for line in verdict_lines) != 1
        or "packet_sha256" in sections["# Verdict"]
    ):
        raise LauncherError(
            f"{seat.name} review verdict contains forbidden or duplicate hashes"
        )

    finding_ids: list[str] = []
    expected_prefix = PHASE1_FINDING_PREFIX[seat.name]
    for heading in ("# Blocking findings", "# Important findings"):
        section = sections[heading]
        if section == "None":
            continue
        identifiers = PHASE1_FINDING_ID.findall(section)
        if not identifiers:
            raise LauncherError(
                f"{seat.name} review has a non-None finding without an ID"
            )
        blocks = tuple(
            block.strip()
            for block in re.split(r"\n[ \t]*\n", section)
            if block.strip()
        )
        for block in blocks:
            first_line = block.splitlines()[0].strip()
            first_identifier = re.match(
                r"^(?:[-*+]\s+|\d+[.)]\s+)?"
                r"\[([A-Z0-9][A-Z0-9._-]{2,63})\]",
                first_line,
            )
            if first_identifier is None:
                raise LauncherError(
                    f"{seat.name} review has a finding block without an ID prefix"
                )
            for continuation_line in block.splitlines()[1:]:
                if re.match(
                    r"^(?:[-*+]\s+|\d+[.)]\s+)",
                    continuation_line,
                ) and (
                    PHASE1_FINDING_ID.match(
                        re.sub(
                            r"^(?:[-*+]\s+|\d+[.)]\s+)",
                            "",
                            continuation_line,
                        )
                    )
                    is None
                ):
                    raise LauncherError(
                        f"{seat.name} review has a finding bullet without an ID prefix"
                    )
        if any(not identifier.startswith(expected_prefix) for identifier in identifiers):
            raise LauncherError(
                f"{seat.name} review uses a finding ID from another seat"
            )
        finding_ids.extend(identifiers)
    if len(finding_ids) != len(set(finding_ids)):
        raise LauncherError(f"{seat.name} review repeats a finding ID")


def _assert_successful_reviewer_run(
    run: SeatRun,
    *,
    input_manifest_sha256: str,
) -> None:
    """Accept one reviewer only when its route completed and output parses."""
    if run.returncode == 124 and run.seat.name == "kimi":
        raise LauncherError("Kimi seat unavailable (timeout exit 124)")
    if run.returncode != 0:
        raise LauncherError(f"{run.seat.name} exited with status {run.returncode}")
    _validate_phase1_review_body(
        seat=run.seat,
        body=_extract_review_body(run),
        input_manifest_sha256=input_manifest_sha256,
    )


def _normalized_review_bytes(
    run: SeatRun,
    *,
    receipt: Mapping[str, Any],
    receipt_bytes: bytes,
) -> bytes:
    body = _extract_review_body(run)
    _validate_phase1_review_body(
        seat=run.seat,
        body=body,
        input_manifest_sha256=str(receipt["input_manifest_sha256"]),
    )
    ordered_values = (
        ("requested_route", receipt["requested_route"]),
        ("launcher_invocation_uuid", receipt["launcher_invocation_uuid"]),
        ("provider_session_id", receipt["provider_session_id"]),
        ("reported_model", receipt["reported_model"]),
        ("input_manifest_sha256", receipt["input_manifest_sha256"]),
        ("packet_sha256", receipt["packet_sha256"]),
        ("launcher_proof_sha256", _sha256(receipt_bytes)),
        ("raw_response_sha256", _sha256(run.stdout)),
    )
    lines = ["---"]
    for key, value in ordered_values:
        rendered = "null" if value is None else str(value)
        if any(character in rendered for character in ("\x00", "\n", "\r")):
            raise LauncherError(f"unsafe normalized review metadata: {key}")
        lines.append(f"{key}: {rendered}")
    lines.append("---")
    return ("\n".join(lines) + "\n").encode("utf-8") + body


def _receipt(
    run: SeatRun,
    *,
    frozen: FrozenReview,
    sandbox: SandboxProof,
    launcher_path: Path,
    launcher_sha256: str,
) -> dict[str, Any]:
    provider_session_id, reported_model = _provider_metadata(run)
    identity = run.executable_identity
    cwd_proof = {
        "device": sandbox.device,
        "initial_entries": list(sandbox.initial_entries),
        "inode": sandbox.inode,
        "mode": f"{sandbox.mode:04o}",
        "path": str(sandbox.path),
    }
    return {
        "argv": list(run.argv),
        "argv_sha256": _sha256(canonical_json_bytes(list(run.argv))),
        "client_version": run.client_version,
        "cwd_device": sandbox.device,
        "cwd_initial_entries": list(sandbox.initial_entries),
        "cwd_inode": sandbox.inode,
        "cwd_mode": f"{sandbox.mode:04o}",
        "cwd_path": str(sandbox.path),
        "cwd_proof_sha256": _sha256(canonical_json_bytes(cwd_proof)),
        "cwd_removed_after_run": True,
        "ended_at_utc": run.ended_at_utc,
        "descendants_absent_after_run": True,
        "executable_cdhash": identity.cdhash if identity is not None else None,
        "executable_designated_requirement": (
            identity.designated_requirement if identity is not None else None
        ),
        "executable_identity_policy_revision": (
            IDENTITY_POLICY_REVISION if identity is not None else None
        ),
        "executable_path": str(run.executable),
        "executable_sha256": run.executable_sha256,
        "executable_team_identifier": (
            identity.team_identifier if identity is not None else None
        ),
        "exit_status": run.returncode,
        "input_manifest_sha256": frozen.input_manifest_sha256,
        "launcher_invocation_uuid": run.launcher_invocation_uuid,
        "launcher_path": str(launcher_path),
        "launcher_sha256": launcher_sha256,
        "max_output_bytes": run.max_output_bytes,
        "output_spooled": True,
        "packet_sha256": frozen.packet_sha256,
        "review_input_bytes": len(frozen.review_input_bytes),
        "review_input_schema": REVIEW_INPUT_SCHEMA,
        "review_input_sha256": _sha256(frozen.review_input_bytes),
        "process_group_isolated": True,
        "provider_session_id": provider_session_id,
        "raw_output_path": run.seat.raw_name,
        "reported_model": reported_model,
        "requested_route": run.seat.requested_route,
        "route_config_path": str(frozen.route_config_path),
        "route_config_sha256": _sha256(frozen.route_config_bytes),
        "review_role": run.seat.role,
        "input_transport": run.seat.input_transport,
        "execution_wrapper_path": (
            str(run.execution_wrapper)
            if run.execution_wrapper is not None
            else None
        ),
        "execution_wrapper_sha256": run.execution_wrapper_sha256,
        "execution_wrapper_cdhash": (
            run.execution_wrapper_identity.cdhash
            if run.execution_wrapper_identity is not None
            else None
        ),
        "execution_wrapper_team_identifier": (
            run.execution_wrapper_identity.team_identifier
            if run.execution_wrapper_identity is not None
            else None
        ),
        "client_artifact_sha256": dict(run.client_artifact_sha256),
        "sandbox_enforced": run.sandbox_enforced,
        "sandbox_profile_sha256": run.sandbox_profile_sha256,
        "canary_sha256_before": run.canary_sha256_before,
        "canary_sha256_after": run.canary_sha256_after,
        "canary_write_denied": run.canary_write_denied,
        "pre_run_input_sha256": run.pre_run_input_sha256,
        "post_run_input_sha256": run.post_run_input_sha256,
        "schema": LAUNCHER_SCHEMA,
        "seat": run.seat.name,
        "shell": False,
        "started_at_utc": run.started_at_utc,
        "stderr_bytes": len(run.stderr),
        "stderr_output_path": run.seat.stderr_name,
        "stderr_sha256": _sha256(run.stderr),
        "stdout_bytes": len(run.stdout),
        "stdout_sha256": _sha256(run.stdout),
        # The launcher constrains each client through its attested argv,
        # isolated cwd/home, and (for Kimi) an OS write-denial profile.  It does
        # not prove that every provider-side read/search capability is absent,
        # so the receipt must not overclaim complete tool denial.
        "tools_denied": False,
        "wall_timeout_seconds": run.wall_timeout_seconds,
        "home_path": str(run.home_path),
        "xdg_cache_home": str(run.home_path),
        "xdg_config_home": str(run.home_path),
        "xdg_data_home": str(run.home_path),
        "xdg_state_home": str(run.home_path),
    }


def launch_panel(
    *,
    frozen_review: Path,
    output_dir: Path,
    clients: ClientPaths = PRODUCTION_CLIENTS,
    command_runner: CommandRunner = _run_bound_command,
    wall_timeout_seconds: float = DEFAULT_WALL_TIMEOUT_SECONDS,
    termination_grace_seconds: float = DEFAULT_TERMINATION_GRACE_SECONDS,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> PanelResult:
    """Launch only the three parallel v3 reviewers and publish their evidence.

    Fable is deliberately absent here.  The final-gate phase must consume these
    immutable outputs plus a completed disposition; until that separate phase
    succeeds, ``reviewers-complete.json`` is not an approval marker.
    """
    if wall_timeout_seconds <= 0 or termination_grace_seconds <= 0:
        raise LauncherError("wall timeout and termination grace must be positive")
    if max_output_bytes <= 0:
        raise LauncherError("maximum provider output must be positive")

    frozen = _load_frozen_review(frozen_review)
    authenticated_launcher = _authenticate_launcher(frozen)
    output_dir = output_dir.absolute()
    _preflight_output_targets(output_dir)
    validator_files: tuple[PublishedFile, ...] = ()
    executable_sandbox_path: Path | None = None
    temporary_sandboxes: dict[str, Path] = {}
    try:
        validator_files = _materialize_validator_inputs(frozen, output_dir)
        validator_payloads = {
            "00-review-packet.bin": frozen.packet_bytes,
            "input-manifest.json": frozen.manifest_bytes,
            "freeze-receipt.json": frozen.receipt_bytes,
        }
        executable_sandbox_path, _ = _sandbox(
            prefix="worker-plane-review-executables."
        )
        production = clients == PRODUCTION_CLIENTS
        identities = PRODUCTION_IDENTITIES if production else {}
        gemini = _validate_executable(
            clients.gemini,
            "Gemini",
            executable_sandbox_path,
            expected_identity=identities.get("gemini"),
        )
        codex_node = _validate_executable(
            clients.codex_node,
            "Codex Node",
            executable_sandbox_path,
            expected_identity=identities.get("codex_node"),
        )
        kimi = _validate_executable(
            clients.kimi,
            "Kimi",
            executable_sandbox_path,
            expected_identity=identities.get("kimi"),
        )
        sandbox_exec = _validate_executable(
            clients.sandbox_exec,
            "sandbox-exec",
            executable_sandbox_path,
            allow_read_only_canonical=production,
            expected_identity=identities.get("sandbox_exec"),
        )
        codex_wrapper = _validate_artifact(
            clients.codex_wrapper,
            "Codex wrapper",
            expected_sha256=(
                PRODUCTION_ARTIFACT_SHA256["codex_wrapper"]
                if production
                else None
            ),
        )
        codex_package = _validate_artifact(
            clients.codex_package,
            "Codex package",
            expected_sha256=(
                PRODUCTION_ARTIFACT_SHA256["codex_package"]
                if production
                else None
            ),
        )
        codex_native = _authenticate_file(
            clients.codex_native,
            "Codex native executable",
            require_executable=True,
        )
        if production:
            _attest_executable_identity(
                codex_native,
                identities["codex_native"],
                "Codex native",
            )
        prepared_executables = (gemini, codex_node, kimi, sandbox_exec)
        _seal_executable_sandbox(
            executable_sandbox_path,
            prepared_executables,
        )

        version_by_client: dict[str, str] = {}
        for client_name, executable, version_argv in (
            ("gemini", gemini, None),
            (
                "codex",
                codex_node,
                (
                    str(codex_node.canonical.path),
                    str(codex_wrapper.path),
                    "--version",
                ),
            ),
            ("kimi", kimi, None),
        ):
            version_cwd, _ = _sandbox(
                prefix=f"worker-plane-review-version-{client_name}."
            )
            temporary_sandboxes[f"version-{client_name}"] = version_cwd
            version_environment = _route_environment(
                next(seat for seat in SEATS if seat.client == client_name),
                source=os.environ,
                sandbox=version_cwd,
            )
            if client_name == "gemini" and production:
                version_environment["HOME"] = os.environ.get(
                    "HOME", version_environment["HOME"]
                )
                for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
                    version_environment.pop(name, None)
            version, parsed_version = _client_version(
                executable,
                version_environment,
                command_runner,
                cwd=version_cwd,
                wall_timeout_seconds=min(wall_timeout_seconds, 30.0),
                termination_grace_seconds=termination_grace_seconds,
                max_output_bytes=min(max_output_bytes, 64 * 1024),
                argv=version_argv,
            )
            if client_name == "gemini" and parsed_version < MINIMUM_GEMINI_VERSION:
                raise LauncherError(
                    "Gemini client 1.1.2 or newer is required for stdin headless mode"
                )
            if client_name == "codex" and parsed_version != REQUIRED_CODEX_VERSION:
                raise LauncherError("Codex client 0.145.0 is required")
            if client_name == "kimi" and parsed_version != REQUIRED_KIMI_VERSION:
                raise LauncherError("Kimi client 0.29.0 is required")
            version_by_client[client_name] = version

        for name, path in tuple(temporary_sandboxes.items()):
            _remove_sandbox(path)
            del temporary_sandboxes[name]

        sandbox_proofs: dict[str, SandboxProof] = {}
        seat_cwds: dict[str, Path] = {}
        seat_homes: dict[str, Path] = {}
        environments: dict[str, dict[str, str]] = {}
        input_paths: dict[str, Path | None] = {seat.name: None for seat in SEATS}
        execution_prefixes: dict[str, tuple[str, ...]] = {
            "gemini": (),
            "codex": (str(codex_wrapper.path),),
            "kimi": (),
        }
        runner_by_seat: dict[str, PreparedExecutable | None] = {
            "gemini": None,
            "codex": None,
            "kimi": sandbox_exec,
        }
        artifact_by_seat: dict[str, tuple[AuthenticatedFile, ...]] = {
            "gemini": (),
            "codex": (codex_wrapper, codex_package, codex_native),
            "kimi": (),
        }
        profile_sha256: dict[str, str | None] = {
            seat.name: None for seat in SEATS
        }
        canary_before: dict[str, str | None] = {seat.name: None for seat in SEATS}
        canary_after: dict[str, str | None] = {seat.name: None for seat in SEATS}
        kimi_canary_path: Path | None = None

        for seat in SEATS:
            cwd, proof = _sandbox(prefix=f"worker-plane-review-cwd-{seat.name}.")
            home, _ = _sandbox(prefix=f"worker-plane-review-home-{seat.name}.")
            temporary_sandboxes[f"cwd-{seat.name}"] = cwd
            temporary_sandboxes[f"home-{seat.name}"] = home
            seat_cwds[seat.name] = cwd
            seat_homes[seat.name] = home
            sandbox_proofs[seat.name] = proof
            environments[seat.name] = _route_environment(
                seat,
                source=os.environ,
                sandbox=home,
            )

        if production:
            environments["gemini"]["HOME"] = os.environ.get(
                "HOME", environments["gemini"]["HOME"]
            )
            for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
                environments["gemini"].pop(name, None)
        _seed_codex_home(seat_homes["codex"], production=production)
        environments["codex"]["CODEX_HOME"] = str(
            seat_homes["codex"] / ".codex"
        )
        input_paths["gemini"] = _prepare_gemini_read_only_input(
            cwd=seat_cwds["gemini"],
            review_input_bytes=frozen.review_input_bytes,
        )
        (
            kimi_input_path,
            kimi_profile_path,
            kimi_canary_path,
            kimi_profile_sha256,
            expected_canary_sha256,
        ) = _prepare_kimi_read_only_inputs(
            cwd=seat_cwds["kimi"],
            home=seat_homes["kimi"],
            review_input_bytes=frozen.review_input_bytes,
            production=production,
        )
        input_paths["kimi"] = kimi_input_path
        profile_sha256["kimi"] = kimi_profile_sha256
        execution_prefixes["kimi"] = ("-f", str(kimi_profile_path))
        denied_before, denied_after = _prove_canary_write_denied(
            sandbox_exec=sandbox_exec,
            profile_path=kimi_profile_path,
            canary_path=kimi_canary_path,
            cwd=seat_cwds["kimi"],
            environment=environments["kimi"],
            command_runner=command_runner,
            wall_timeout_seconds=wall_timeout_seconds,
            termination_grace_seconds=termination_grace_seconds,
            max_output_bytes=max_output_bytes,
        )
        if (
            denied_before != expected_canary_sha256
            or denied_after != expected_canary_sha256
        ):
            raise LauncherError("Kimi canary proof differs from canonical bytes")
        canary_before["kimi"] = denied_before
        canary_after["kimi"] = denied_after

        _assert_packet_unchanged(frozen)
        _assert_executable_sandbox_sealed(
            executable_sandbox_path,
            prepared_executables,
        )
        executable_by_seat = {
            "gemini": gemini,
            "codex": codex_node,
            "kimi": kimi,
        }
        invocation_uuids = {seat.name: str(uuid.uuid4()) for seat in SEATS}
        runs: list[SeatRun] = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(SEATS)
        ) as executor:
            futures = {
                seat.name: executor.submit(
                    _run_seat,
                    seat=seat,
                    executable=executable_by_seat[seat.name],
                    runner_executable=runner_by_seat[seat.name],
                    execution_prefix=execution_prefixes[seat.name],
                    client_artifacts=artifact_by_seat[seat.name],
                    client_version=version_by_client[seat.client],
                    review_input_bytes=frozen.review_input_bytes,
                    input_path=input_paths[seat.name],
                    cwd=seat_cwds[seat.name],
                    home=Path(environments[seat.name]["HOME"]),
                    environment=environments[seat.name],
                    invocation_uuid=invocation_uuids[seat.name],
                    command_runner=command_runner,
                    wall_timeout_seconds=wall_timeout_seconds,
                    termination_grace_seconds=termination_grace_seconds,
                    max_output_bytes=max_output_bytes,
                    sandbox_profile_sha256=profile_sha256[seat.name],
                    canary_sha256_before=canary_before[seat.name],
                    canary_sha256_after=canary_after[seat.name],
                )
                for seat in SEATS
            }
            for seat in SEATS:
                try:
                    runs.append(futures[seat.name].result())
                except OSError as exc:
                    raise LauncherError(f"{seat.name} invocation failed") from exc

        _assert_packet_unchanged(frozen)
        _assert_authenticated_file_unchanged(authenticated_launcher, "launcher")
        for executable, label in (
            (gemini, "Gemini"),
            (codex_node, "Codex Node"),
            (kimi, "Kimi"),
            (sandbox_exec, "sandbox-exec"),
        ):
            _assert_prepared_executable_unchanged(executable, label)
        for artifact, label in (
            (codex_wrapper, "Codex wrapper"),
            (codex_package, "Codex package"),
            (codex_native, "Codex native executable"),
        ):
            _assert_authenticated_file_unchanged(
                artifact,
                label,
                require_executable=artifact is codex_native,
            )
        current_route_config = _read_read_only(
            frozen.route_config_path,
            "council route config",
        )
        if current_route_config != frozen.route_config_bytes:
            raise LauncherError("council route config changed during panel execution")
        if kimi_canary_path is None:
            raise LauncherError("Kimi canary was not established")
        current_canary = _read_regular_file(kimi_canary_path, "Kimi canary")[0]
        if _sha256(current_canary) != expected_canary_sha256:
            raise LauncherError("Kimi canary changed during reviewer execution")
        for run in runs:
            _assert_successful_reviewer_run(
                run,
                input_manifest_sha256=frozen.input_manifest_sha256,
            )

        cleanup_errors: list[LauncherError] = []
        for name, path in tuple(temporary_sandboxes.items()):
            temporary_sandboxes.pop(name, None)
            try:
                _remove_sandbox(path)
            except LauncherError as exc:
                cleanup_errors.append(exc)
        if cleanup_errors:
            raise cleanup_errors[0]
        _remove_sandbox(executable_sandbox_path)
        executable_sandbox_path = None

        output_files: dict[str, bytes] = {}
        receipt_names: list[str] = []
        for run in runs:
            output_files[run.seat.raw_name] = run.stdout
            output_files[run.seat.stderr_name] = run.stderr
            receipt = _receipt(
                run,
                frozen=frozen,
                sandbox=sandbox_proofs[run.seat.name],
                launcher_path=authenticated_launcher.path,
                launcher_sha256=authenticated_launcher.sha256,
            )
            receipt_bytes = canonical_json_bytes(receipt) + b"\n"
            output_files[run.seat.receipt_name] = receipt_bytes
            output_files[run.seat.review_name] = _normalized_review_bytes(
                run,
                receipt=receipt,
                receipt_bytes=receipt_bytes,
            )
            receipt_names.append(run.seat.receipt_name)
        _publish_complete_panel(
            output_dir,
            frozen=frozen,
            validator_payloads=validator_payloads,
            output_files=output_files,
        )
        return PanelResult(
            packet_sha256=frozen.packet_sha256,
            input_manifest_sha256=frozen.input_manifest_sha256,
            output_dir=output_dir,
            receipt_paths=tuple(output_dir / name for name in receipt_names),
        )
    except BaseException as exc:
        executable_cleanup_error: LauncherError | None = None
        for path in set(temporary_sandboxes.values()):
            try:
                _remove_sandbox(path)
            except LauncherError as cleanup_exc:
                executable_cleanup_error = cleanup_exc
        temporary_sandboxes.clear()
        if executable_sandbox_path is not None:
            try:
                _remove_sandbox(executable_sandbox_path)
            except LauncherError as cleanup_exc:
                executable_cleanup_error = cleanup_exc
        try:
            _cleanup_published_files(validator_files)
        except LauncherError as cleanup_exc:
            raise cleanup_exc from exc
        if executable_cleanup_error is not None:
            raise executable_cleanup_error from exc
        raise


def launch_final_gate(*, reviewer_output_dir: Path, disposition_path: Path) -> None:
    """Fail closed until the hash-bound sequential Fable gate is implemented."""
    del reviewer_output_dir, disposition_path
    raise LauncherError(
        "sequential Fable final gate is not implemented; reviewer evidence "
        "cannot authorize execution"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-review", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.set_defaults(clients=PRODUCTION_CLIENTS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = launch_panel(
            frozen_review=args.frozen_review,
            output_dir=args.output_dir,
            clients=args.clients,
        )
    except LauncherError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(
        canonical_json_bytes(
            {
                "input_manifest_sha256": result.input_manifest_sha256,
                "output_dir": str(result.output_dir),
                "packet_sha256": result.packet_sha256,
                "receipt_paths": [str(path) for path in result.receipt_paths],
            }
        )
        + b"\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
