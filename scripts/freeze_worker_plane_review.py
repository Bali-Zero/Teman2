#!/usr/bin/env python3
"""Freeze and verify an immutable, Git-object-backed worker-plane review packet.

The packet binds exactly ten covered design documents and one instruction
brief.  Review identity is the SHA-256 of the canonical input manifest; commit,
generator, route, and filesystem evidence belongs only in the external freeze
receipt.  Length framing makes every input byte unambiguous, including NULs and
text that resembles packet markers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


PACKET_MAGIC = b"NUZANTARA-REVIEW-PACKET-V1\n"
PACKET_END = b"END\n"
GENERATOR_VERSION = "3.0.0"
DEFAULT_GENERATOR_PATH = "scripts/freeze_worker_plane_review.py"
DEFAULT_LAUNCHER_PATH = "scripts/launch_worker_plane_review_panel.py"
DEFAULT_VALIDATOR_PATH = "scripts/check_worker_plane_review.py"
DEFAULT_ROUTE_CONFIG_PATH = "scripts/review_routes/worker-plane-council-v3.json"
LEGACY_ROUTE_CONFIG_PATH = "scripts/review_routes/glm-5.2-v1.json"
EXPECTED_GLM_ROUTE_CONFIG = (
    b'{"api_timeout_ms":"3000000","base_url":"https://api.z.ai/api/anthropic",'
    b'"model_map":{"haiku":"glm-4.7","opus":"glm-5.2","sonnet":"glm-5.2"},'
    b'"schema_version":1}\n'
)
EXPECTED_COUNCIL_ROUTE_CONFIG = (
    b'{"final_gate":{"client":"claude","input_transport":"stdin",'
    b'"model":"claude-fable-5","phase":"sequential-after-disposition",'
    b'"role":"final-gate","seat":"fable"},'
    b'"parallel_reviewers":[{"client":"agy","input_transport":"stdin",'
    b'"model":"Gemini 3.1 Pro (High)","role":"constructive","seat":"gemini"},'
    b'{"client":"codex","input_transport":"stdin","model":"account-default",'
    b'"role":"red-team","seat":"codex"},{"client":"kimi",'
    b'"input_transport":"file","model":"kimi-code/k3","role":"refuter",'
    b'"seat":"kimi"}],"retired_routes":["deepseek","glm"],"schema_version":3}\n'
)
COVERED_SET_PRESETS: dict[str, tuple[str, ...]] = {
    "implementation-plan": (
        "docs/superpowers/specs/2026-07-17-backend-modular-kernel-worker-plane-design.md",
        "docs/superpowers/plans/2026-07-17-modular-kernel-worker-plane-implementation.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-0.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-1.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-2.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-3.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-4.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-5.md",
        "docs/superpowers/plans/2026-07-17-modular-worker-plane-production-rollout.md",
        (
            "docs/superpowers/reviews/"
            "2026-07-17-modular-worker-plane-implementation-plan/"
            "2026-07-23-current-system-refresh.md"
        ),
    ),
}
PRESET_INSTRUCTION_PATHS: dict[str, str] = {
    "implementation-plan": (
        "docs/superpowers/reviews/"
        "2026-07-17-modular-worker-plane-implementation-plan/00-review-brief.md"
    ),
}


class PacketError(RuntimeError):
    """Raised when a packet cannot be built, installed, or verified safely."""


@dataclass(frozen=True)
class InputSpec:
    role: str
    path: str


@dataclass(frozen=True)
class ReviewDocument:
    ordinal: int
    role: str
    path: str
    mode: str
    git_blob_oid: str
    content: bytes
    sha256: str


@dataclass(frozen=True)
class BuiltPacket:
    repo_root: Path
    source_head: str
    source_tree: str
    base_commit: str
    upstream_commit: str
    projection_sha256: str
    manifest: dict[str, Any]
    manifest_bytes: bytes
    manifest_sha256: str
    packet_bytes: bytes
    packet_sha256: str
    documents: tuple[ReviewDocument, ...]
    generator: ReviewDocument
    launcher: ReviewDocument
    validator: ReviewDocument
    route_config: ReviewDocument
    clean_status_sha256: str


@dataclass(frozen=True)
class ParsedPacket:
    manifest: dict[str, Any]
    manifest_sha256: str
    packet_sha256: str
    documents: tuple[ReviewDocument, ...]


@dataclass(frozen=True)
class ArtifactPaths:
    review_dir: Path
    packet_path: Path
    manifest_path: Path
    route_config_path: Path
    receipt_path: Path


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git_blob_oid(content: bytes, oid_length: int) -> str:
    framed = f"blob {len(content)}\0".encode("ascii") + content
    if oid_length == 40:
        return hashlib.sha1(framed, usedforsecurity=False).hexdigest()
    if oid_length == 64:
        return hashlib.sha256(framed).hexdigest()
    raise PacketError("unsupported Git blob OID length")


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical UTF-8 JSON without an implicit trailing newline."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _git(
    repo_root: Path,
    *args: str,
    text: bool = False,
    stdin: bytes | None = None,
) -> bytes | str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        input=None if text else stdin,
        text=text,
    )
    if result.returncode != 0:
        stderr = (
            result.stderr if text else result.stderr.decode("utf-8", errors="replace")
        )
        raise PacketError(f"git {' '.join(args)} failed: {stderr.strip()}")
    return result.stdout


def _resolve_commit(repo_root: Path, ref: str) -> str:
    resolved = _git(repo_root, "rev-parse", "--verify", f"{ref}^{{commit}}", text=True)
    assert isinstance(resolved, str)
    return resolved.strip()


def _tree_oid(repo_root: Path, commit: str) -> str:
    resolved = _git(repo_root, "rev-parse", "--verify", f"{commit}^{{tree}}", text=True)
    assert isinstance(resolved, str)
    return resolved.strip()


def _tracked_status(repo_root: Path) -> bytes:
    status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=no")
    assert isinstance(status, bytes)
    return status


def _validate_repo_path(path: str) -> None:
    pure = PurePosixPath(path)
    if (
        not path
        or pure.is_absolute()
        or ".." in pure.parts
        or "\n" in path
        or "\r" in path
        or "\x00" in path
        or str(pure) != path
    ):
        raise PacketError(f"invalid repository-relative path: {path!r}")


def _read_git_blob(repo_root: Path, commit: str, path: str) -> tuple[str, str, bytes]:
    _validate_repo_path(path)
    raw_tree = _git(repo_root, "ls-tree", "-z", commit, "--", path)
    assert isinstance(raw_tree, bytes)
    records = [record for record in raw_tree.split(b"\0") if record]
    if len(records) != 1:
        raise PacketError(
            f"expected one tracked Git object for {path}, found {len(records)}"
        )
    try:
        metadata, recorded_path = records[0].split(b"\t", 1)
        mode, object_type, oid = metadata.decode("ascii").split(" ", 2)
        decoded_path = recorded_path.decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise PacketError(f"malformed git ls-tree record for {path}") from exc
    if decoded_path != path or object_type != "blob":
        raise PacketError(f"review input is not a regular Git blob: {path}")
    content = _git(repo_root, "cat-file", "blob", oid)
    assert isinstance(content, bytes)
    calculated_oid = _git(repo_root, "hash-object", "--stdin", stdin=content)
    assert isinstance(calculated_oid, bytes)
    if calculated_oid.decode("ascii").strip() != oid:
        raise PacketError(f"Git object validation failed for {path}")
    return mode, oid, content


def _validate_roles(inputs: Sequence[InputSpec]) -> tuple[InputSpec, ...]:
    covered_count = sum(spec.role == "covered" for spec in inputs)
    instructions_count = sum(spec.role == "instructions" for spec in inputs)
    if covered_count < 1 or instructions_count != 1 or len(inputs) != covered_count + 1:
        raise PacketError(
            "packet requires one or more covered inputs and exactly one instructions input"
        )
    if len({spec.path for spec in inputs}) != len(inputs):
        raise PacketError("review input paths must be unique")
    unexpected = {spec.role for spec in inputs} - {"covered", "instructions"}
    if unexpected:
        raise PacketError(f"unsupported review input roles: {sorted(unexpected)}")
    for spec in inputs:
        _validate_repo_path(spec.path)
    return tuple(
        sorted(
            inputs,
            key=lambda spec: (spec.role.encode("utf-8"), spec.path.encode("utf-8")),
        )
    )


def _document(
    repo_root: Path,
    source_head: str,
    *,
    ordinal: int,
    role: str,
    path: str,
) -> ReviewDocument:
    mode, oid, content = _read_git_blob(repo_root, source_head, path)
    return ReviewDocument(
        ordinal=ordinal,
        role=role,
        path=path,
        mode=mode,
        git_blob_oid=oid,
        content=content,
        sha256=sha256_bytes(content),
    )


def _entry(document: ReviewDocument) -> dict[str, Any]:
    return {
        "git_blob_oid": document.git_blob_oid,
        "path": document.path,
        "role": document.role,
        "sha256": document.sha256,
        "size": len(document.content),
    }


def _render_packet(manifest_bytes: bytes, documents: Sequence[ReviewDocument]) -> bytes:
    chunks = [
        PACKET_MAGIC,
        f"MANIFEST {len(manifest_bytes)}\n".encode("ascii"),
        manifest_bytes,
    ]
    for document in documents:
        role_bytes = document.role.encode("utf-8")
        path_bytes = document.path.encode("utf-8")
        chunks.extend(
            [
                (
                    f"ENTRY {len(role_bytes)} {len(path_bytes)} "
                    f"{len(document.content)}\n"
                ).encode("ascii"),
                role_bytes,
                path_bytes,
                document.content,
            ]
        )
    chunks.append(PACKET_END)
    return b"".join(chunks)


def _merge_base(repo_root: Path, source_head: str, upstream_commit: str) -> str:
    resolved = _git(
        repo_root,
        "merge-base",
        source_head,
        upstream_commit,
        text=True,
    )
    assert isinstance(resolved, str)
    commits = resolved.splitlines()
    if len(commits) != 1 or not commits[0]:
        raise PacketError("source and upstream do not have one merge-base")
    return commits[0]


def _build_from_git_objects(
    *,
    repo_root: Path,
    source_ref: str,
    base_ref: str,
    upstream_ref: str,
    inputs: Sequence[InputSpec],
    generator_path: str = DEFAULT_GENERATOR_PATH,
    launcher_path: str = DEFAULT_LAUNCHER_PATH,
    validator_path: str = DEFAULT_VALIDATOR_PATH,
    route_config_path: str = DEFAULT_ROUTE_CONFIG_PATH,
    require_clean_tracked_status: bool = True,
    require_source_is_head: bool = True,
) -> BuiltPacket:
    repo_root = repo_root.resolve()
    sorted_inputs = _validate_roles(inputs)
    source_head = _resolve_commit(repo_root, source_ref)
    source_tree = _tree_oid(repo_root, source_head)
    base_commit = _resolve_commit(repo_root, base_ref)
    upstream_commit = _resolve_commit(repo_root, upstream_ref)
    if require_source_is_head and source_head != _resolve_commit(repo_root, "HEAD"):
        raise PacketError("source commit must equal current HEAD")
    expected_base = _merge_base(repo_root, source_head, upstream_commit)
    if base_commit != expected_base:
        raise PacketError("base commit must equal merge-base(source, upstream)")

    documents = tuple(
        _document(
            repo_root,
            source_head,
            ordinal=ordinal,
            role=spec.role,
            path=spec.path,
        )
        for ordinal, spec in enumerate(sorted_inputs, start=1)
    )
    generator = _document(
        repo_root,
        source_head,
        ordinal=0,
        role="generator",
        path=generator_path,
    )
    try:
        executing_freezer = Path(__file__).resolve().read_bytes()
    except OSError as exc:
        raise PacketError("cannot read executing freezer bytes") from exc
    if generator.content != executing_freezer:
        raise PacketError("executing freezer bytes do not match recorded Git blob")
    launcher = _document(
        repo_root,
        source_head,
        ordinal=0,
        role="launcher",
        path=launcher_path,
    )
    validator = _document(
        repo_root,
        source_head,
        ordinal=0,
        role="validator",
        path=validator_path,
    )
    route_config = _document(
        repo_root,
        source_head,
        ordinal=0,
        role="route-config",
        path=route_config_path,
    )
    expected_route_config = {
        DEFAULT_ROUTE_CONFIG_PATH: EXPECTED_COUNCIL_ROUTE_CONFIG,
        LEGACY_ROUTE_CONFIG_PATH: EXPECTED_GLM_ROUTE_CONFIG,
    }.get(route_config_path)
    if expected_route_config is None:
        raise PacketError("review route config path is not supported")
    if route_config.content != expected_route_config:
        route_label = (
            "council"
            if route_config_path == DEFAULT_ROUTE_CONFIG_PATH
            else "GLM"
        )
        raise PacketError(f"{route_label} route config bytes are not canonical")

    status = _tracked_status(repo_root)
    if require_clean_tracked_status and status:
        raise PacketError("tracked worktree is not clean")

    manifest: dict[str, Any] = {"entries": [_entry(document) for document in documents]}
    manifest_bytes = canonical_json_bytes(manifest)
    manifest_sha256 = sha256_bytes(manifest_bytes)
    packet_bytes = _render_packet(manifest_bytes, documents)
    parsed = parse_packet(packet_bytes)
    if (
        parsed.manifest != manifest
        or parsed.manifest_sha256 != manifest_sha256
        or parsed.packet_sha256 != sha256_bytes(packet_bytes)
        or _render_packet(canonical_json_bytes(parsed.manifest), parsed.documents)
        != packet_bytes
    ):
        raise PacketError("completed packet failed strict round-trip validation")
    return BuiltPacket(
        repo_root=repo_root,
        source_head=source_head,
        source_tree=source_tree,
        base_commit=base_commit,
        upstream_commit=upstream_commit,
        projection_sha256=manifest_sha256,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        manifest_sha256=manifest_sha256,
        packet_bytes=packet_bytes,
        packet_sha256=sha256_bytes(packet_bytes),
        documents=documents,
        generator=generator,
        launcher=launcher,
        validator=validator,
        route_config=route_config,
        clean_status_sha256=sha256_bytes(status),
    )


def build_from_git(
    *,
    repo_root: Path,
    source_ref: str,
    base_ref: str,
    inputs: Sequence[InputSpec],
    upstream_ref: str | None = None,
    generator_path: str = DEFAULT_GENERATOR_PATH,
    launcher_path: str = DEFAULT_LAUNCHER_PATH,
    validator_path: str = DEFAULT_VALIDATOR_PATH,
    route_config_path: str = DEFAULT_ROUTE_CONFIG_PATH,
    require_clean_tracked_status: bool = True,
) -> BuiltPacket:
    """Build a provenance-checked packet from the current committed ``HEAD``."""
    return _build_from_git_objects(
        repo_root=repo_root,
        source_ref=source_ref,
        base_ref=base_ref,
        upstream_ref=upstream_ref or base_ref,
        inputs=inputs,
        generator_path=generator_path,
        launcher_path=launcher_path,
        validator_path=validator_path,
        route_config_path=route_config_path,
        require_clean_tracked_status=require_clean_tracked_status,
        require_source_is_head=True,
    )


def build_projection_from_git(
    *,
    repo_root: Path,
    source_ref: str,
    inputs: Sequence[InputSpec],
    route_config_path: str = DEFAULT_ROUTE_CONFIG_PATH,
) -> BuiltPacket:
    """Build a historical projection for comparison, without claiming a freeze."""
    return _build_from_git_objects(
        repo_root=repo_root,
        source_ref=source_ref,
        base_ref=source_ref,
        upstream_ref=source_ref,
        inputs=inputs,
        route_config_path=route_config_path,
        require_clean_tracked_status=False,
        require_source_is_head=False,
    )


class _PacketReader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.offset = 0

    def exact(self, expected: bytes) -> None:
        actual = self.take(len(expected))
        if actual != expected:
            raise PacketError(f"expected packet marker {expected!r}, got {actual!r}")

    def take(self, length: int) -> bytes:
        if length < 0 or self.offset + length > len(self.payload):
            raise PacketError("packet ended before declared byte length")
        chunk = self.payload[self.offset : self.offset + length]
        self.offset += length
        return chunk

    def line(self, label: str) -> bytes:
        end = self.payload.find(b"\n", self.offset)
        if end < 0:
            raise PacketError(f"missing newline after {label}")
        raw = self.payload[self.offset : end]
        self.offset = end + 1
        return raw


def _parse_nonnegative_int(value: bytes, label: str) -> int:
    try:
        text = value.decode("ascii")
        canonical = value == b"0" or (
            bool(value)
            and value[0] in b"123456789"
            and all(character in b"0123456789" for character in value[1:])
        )
        if not canonical:
            raise ValueError
        parsed = int(text)
    except (UnicodeDecodeError, ValueError) as exc:
        raise PacketError(f"invalid integer for {label}") from exc
    if parsed < 0:
        raise PacketError(f"negative byte length for {label}")
    return parsed


def _load_manifest(manifest_bytes: bytes) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PacketError("manifest is not valid UTF-8 JSON") from exc
    if (
        not isinstance(manifest, dict)
        or canonical_json_bytes(manifest) != manifest_bytes
    ):
        raise PacketError("manifest is not canonical JSON")
    if set(manifest) != {"entries"} or not isinstance(manifest["entries"], list):
        raise PacketError("manifest must contain only an entries array")
    entries = manifest["entries"]
    if len(entries) < 2:
        raise PacketError("manifest must contain at least two entries")
    if not all(isinstance(entry, dict) for entry in entries):
        raise PacketError("manifest entry shape is invalid")
    if entries != sorted(
        entries,
        key=lambda entry: (
            str(entry.get("role")).encode("utf-8"),
            str(entry.get("path")).encode("utf-8"),
        ),
    ):
        raise PacketError("manifest entries are not canonically ordered")
    paths: set[str] = set()
    roles: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "git_blob_oid",
            "path",
            "role",
            "sha256",
            "size",
        }:
            raise PacketError("manifest entry shape is invalid")
        if not isinstance(entry["path"], str) or not isinstance(entry["role"], str):
            raise PacketError("manifest entry identity is invalid")
        _validate_repo_path(entry["path"])
        if entry["path"] in paths:
            raise PacketError("manifest paths must be unique")
        paths.add(entry["path"])
        roles.append(entry["role"])
        if (
            isinstance(entry["size"], bool)
            or not isinstance(entry["size"], int)
            or entry["size"] < 0
        ):
            raise PacketError("manifest entry size is invalid")
        for key in ("git_blob_oid", "sha256"):
            value = entry[key]
            if (
                not isinstance(value, str)
                or not value
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise PacketError(f"manifest entry {key} is invalid")
        if len(entry["sha256"]) != 64 or len(entry["git_blob_oid"]) not in {40, 64}:
            raise PacketError("manifest entry digest length is invalid")
    if (
        roles.count("covered") < 1
        or roles.count("instructions") != 1
        or len(roles) != roles.count("covered") + 1
    ):
        raise PacketError("manifest role cardinality is invalid")
    return manifest


def parse_packet(payload: bytes) -> ParsedPacket:
    """Strictly parse and verify a complete packet, including exact EOF."""
    reader = _PacketReader(payload)
    reader.exact(PACKET_MAGIC)
    manifest_header = reader.line("manifest")
    manifest_parts = manifest_header.split(b" ")
    if len(manifest_parts) != 2 or manifest_parts[0] != b"MANIFEST":
        raise PacketError("expected MANIFEST header")
    manifest_length = _parse_nonnegative_int(manifest_parts[1], "manifest")
    manifest_bytes = reader.take(manifest_length)
    manifest = _load_manifest(manifest_bytes)

    documents: list[ReviewDocument] = []
    for ordinal, entry in enumerate(manifest["entries"], start=1):
        entry_header = reader.line("entry")
        fields = entry_header.split(b" ")
        if len(fields) != 4 or fields[0] != b"ENTRY":
            raise PacketError("expected ENTRY header")
        role_length = _parse_nonnegative_int(fields[1], "entry role")
        path_length = _parse_nonnegative_int(fields[2], "entry path")
        content_length = _parse_nonnegative_int(fields[3], "entry content")
        role_bytes = reader.take(role_length)
        path_bytes = reader.take(path_length)
        content = reader.take(content_length)
        try:
            role = role_bytes.decode("utf-8")
            path = path_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PacketError("entry role or path is not valid UTF-8") from exc
        if role != entry["role"] or path != entry["path"]:
            raise PacketError("document identity does not match manifest")
        if content_length != entry["size"]:
            raise PacketError("content byte length does not match manifest")
        actual_sha256 = sha256_bytes(content)
        if actual_sha256 != entry["sha256"]:
            raise PacketError("content SHA-256 mismatch")
        if _git_blob_oid(content, len(entry["git_blob_oid"])) != entry["git_blob_oid"]:
            raise PacketError("Git blob OID mismatch")
        documents.append(
            ReviewDocument(
                ordinal=ordinal,
                role=role,
                path=path,
                mode="",
                git_blob_oid=entry["git_blob_oid"],
                content=content,
                sha256=actual_sha256,
            )
        )

    reader.exact(PACKET_END)
    if reader.offset != len(payload):
        raise PacketError("trailing bytes after END")
    manifest_sha256 = sha256_bytes(manifest_bytes)
    return ParsedPacket(
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        packet_sha256=sha256_bytes(payload),
        documents=tuple(documents),
    )


def _write_new_file(path: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise PacketError(f"short write while creating {path}")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _artifact_paths(review_dir: Path) -> ArtifactPaths:
    return ArtifactPaths(
        review_dir=review_dir,
        packet_path=review_dir / "packet.bin",
        manifest_path=review_dir / "input-manifest.json",
        route_config_path=review_dir / Path(DEFAULT_ROUTE_CONFIG_PATH).name,
        receipt_path=review_dir / "freeze-receipt.json",
    )


def _read_read_only_regular(path: Path, label: str) -> tuple[bytes, os.stat_result]:
    try:
        before = path.lstat()
    except OSError as exc:
        raise PacketError(f"cannot stat {label}: {path}") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise PacketError(f"{label} must be a regular non-symlink file")
    if stat.S_IMODE(before.st_mode) != 0o444:
        raise PacketError(f"{label} must have exact read-only mode 0444")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise PacketError(f"cannot open {label}: {path}") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or stat.S_IMODE(opened.st_mode) != 0o444
        ):
            raise PacketError(f"{label} changed while being opened")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (
            after.st_dev != opened.st_dev
            or after.st_ino != opened.st_ino
            or after.st_size != opened.st_size
            or stat.S_IMODE(after.st_mode) != 0o444
        ):
            raise PacketError(f"{label} changed while being read")
        return b"".join(chunks), after
    finally:
        os.close(descriptor)


def _freeze_receipt(
    built: BuiltPacket,
    packet_stat: os.stat_result,
    built_at_utc: str,
) -> dict[str, Any]:
    return {
        "base_commit": built.base_commit,
        "built_at_utc": built_at_utc,
        "generator_git_blob_oid": built.generator.git_blob_oid,
        "generator_path": built.generator.path,
        "generator_sha256": built.generator.sha256,
        "generator_version": GENERATOR_VERSION,
        "git_object_validation": "pass",
        "input_manifest_sha256": built.manifest_sha256,
        "launcher_git_blob_oid": built.launcher.git_blob_oid,
        "launcher_path": built.launcher.path,
        "launcher_sha256": built.launcher.sha256,
        "packet_bytes": len(built.packet_bytes),
        "packet_device": packet_stat.st_dev,
        "packet_inode": packet_stat.st_ino,
        "packet_sha256": built.packet_sha256,
        "route_config_git_blob_oid": built.route_config.git_blob_oid,
        "route_config_path": built.route_config.path,
        "route_config_sha256": built.route_config.sha256,
        "schema": "nuzantara.worker-plane-review-freeze-receipt/v1",
        "source_head": built.source_head,
        "source_tree": built.source_tree,
        "tracked_status_sha256": built.clean_status_sha256,
        "upstream_commit": built.upstream_commit,
        "validator_git_blob_oid": built.validator.git_blob_oid,
        "validator_path": built.validator.path,
        "validator_sha256": built.validator.sha256,
    }


def _validate_built_at_utc(value: Any) -> str:
    if not isinstance(value, str):
        raise PacketError("freeze receipt built_at_utc is invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PacketError("freeze receipt built_at_utc is invalid") from exc
    offset = parsed.utcoffset()
    if parsed.tzinfo is None or offset is None or offset.total_seconds() != 0:
        raise PacketError("freeze receipt built_at_utc is not UTC")
    return value


def _validate_existing_artifacts(paths: ArtifactPaths, built: BuiltPacket) -> None:
    try:
        directory_stat = paths.review_dir.lstat()
    except OSError as exc:
        raise PacketError(
            f"incomplete content-addressed artifact at {paths.review_dir}"
        ) from exc
    if stat.S_ISLNK(directory_stat.st_mode) or not stat.S_ISDIR(directory_stat.st_mode):
        raise PacketError("frozen review must be a regular non-symlink directory")
    if stat.S_IMODE(directory_stat.st_mode) != 0o555:
        raise PacketError("frozen review directory must have exact mode 0555")
    expected_names = {
        "packet.bin",
        "input-manifest.json",
        "freeze-receipt.json",
        Path(DEFAULT_ROUTE_CONFIG_PATH).name,
    }
    try:
        actual_names = {child.name for child in paths.review_dir.iterdir()}
    except OSError as exc:
        raise PacketError(
            f"cannot enumerate frozen review: {paths.review_dir}"
        ) from exc
    if actual_names != expected_names:
        raise PacketError("frozen review must contain exactly four files")

    expected = {
        paths.packet_path: built.packet_bytes,
        paths.manifest_path: built.manifest_bytes,
        paths.route_config_path: built.route_config.content,
    }
    for path, content in expected.items():
        existing, _ = _read_read_only_regular(path, path.name)
        if existing != content:
            raise PacketError(f"content-addressed artifact collision at {path}")

    parsed = parse_packet(expected[paths.packet_path])
    if (
        parsed.manifest != built.manifest
        or parsed.manifest_sha256 != built.manifest_sha256
        or parsed.packet_sha256 != built.packet_sha256
    ):
        raise PacketError("installed packet failed strict projection validation")

    receipt_bytes, _ = _read_read_only_regular(paths.receipt_path, "freeze receipt")
    try:
        receipt = json.loads(receipt_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PacketError(f"invalid freeze receipt at {paths.receipt_path}") from exc
    if not isinstance(receipt, dict):
        raise PacketError("freeze receipt must be a JSON object")
    built_at_utc = _validate_built_at_utc(receipt.get("built_at_utc"))
    _, packet_stat = _read_read_only_regular(paths.packet_path, "packet")
    expected_receipt = _freeze_receipt(built, packet_stat, built_at_utc)
    expected_receipt_bytes = canonical_json_bytes(expected_receipt) + b"\n"
    if receipt_bytes != expected_receipt_bytes:
        canonical_received = canonical_json_bytes(receipt) + b"\n"
        if receipt_bytes != canonical_received:
            raise PacketError("freeze receipt is not canonical newline-terminated JSON")
        raise PacketError("freeze receipt does not fully match installed packet")


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_artifacts(built: BuiltPacket, output_dir: Path) -> ArtifactPaths:
    """Atomically install a read-only content-addressed review directory."""
    resolved_output = output_dir.expanduser().resolve()
    if resolved_output == built.repo_root or resolved_output.is_relative_to(
        built.repo_root
    ):
        raise PacketError("external review store must be outside repository")
    sha_root = resolved_output / "sha256"
    sha_root.mkdir(parents=True, exist_ok=True, mode=0o755)
    sha_root_stat = sha_root.lstat()
    if stat.S_ISLNK(sha_root_stat.st_mode) or not stat.S_ISDIR(sha_root_stat.st_mode):
        raise PacketError(
            "content-addressed store root must be a non-symlink directory"
        )
    review_dir = sha_root / built.packet_sha256
    paths = _artifact_paths(review_dir)
    if os.path.lexists(review_dir):
        _validate_existing_artifacts(paths, built)
        return paths

    temporary = Path(tempfile.mkdtemp(prefix=f".{built.packet_sha256}.", dir=sha_root))
    temporary_paths = _artifact_paths(temporary)
    installed = False
    try:
        _write_new_file(temporary_paths.packet_path, built.packet_bytes)
        _write_new_file(temporary_paths.manifest_path, built.manifest_bytes)
        _write_new_file(temporary_paths.route_config_path, built.route_config.content)
        packet_stat = temporary_paths.packet_path.lstat()
        receipt = _freeze_receipt(
            built,
            packet_stat,
            datetime.now(timezone.utc).isoformat(),
        )
        _write_new_file(
            temporary_paths.receipt_path,
            canonical_json_bytes(receipt) + b"\n",
        )
        _fsync_directory(temporary)
        for child in temporary.iterdir():
            os.chmod(child, 0o444)
        os.chmod(temporary, 0o555)
        try:
            os.replace(temporary, review_dir)
            installed = True
            _fsync_directory(sha_root)
        except OSError:
            if not os.path.lexists(review_dir):
                raise
            _validate_existing_artifacts(paths, built)
        _validate_existing_artifacts(paths, built)
        return paths
    finally:
        if not installed and temporary.exists():
            os.chmod(temporary, 0o700)
            for child in temporary.iterdir():
                os.chmod(child, 0o600)
            shutil.rmtree(temporary)


def _parse_input(value: str) -> InputSpec:
    try:
        role, path = value.split(":", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("input must be ROLE:PATH") from exc
    return InputSpec(role=role, path=path)


def _covered_paths_for_name(
    repo_root: Path, source_ref: str, name: str
) -> tuple[str, ...]:
    preset = COVERED_SET_PRESETS.get(name)
    if preset is not None:
        return preset
    set_path = f"scripts/review_sets/{name}.json"
    _, _, content = _read_git_blob(
        repo_root.resolve(), _resolve_commit(repo_root, source_ref), set_path
    )
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PacketError(f"covered set is not valid UTF-8 JSON: {set_path}") from exc
    if canonical_json_bytes(value) + b"\n" != content:
        raise PacketError(
            f"covered set is not canonical newline-terminated JSON: {set_path}"
        )
    if not isinstance(value, dict) or set(value) != {"covered"}:
        raise PacketError(f"covered set has invalid shape: {set_path}")
    covered = value["covered"]
    if (
        not isinstance(covered, list)
        or not covered
        or not all(isinstance(path, str) for path in covered)
    ):
        raise PacketError(f"covered set must contain one or more paths: {set_path}")
    for path in covered:
        _validate_repo_path(path)
    if len(set(covered)) != len(covered):
        raise PacketError(f"covered set contains duplicate paths: {set_path}")
    if covered != sorted(covered, key=lambda path: path.encode("utf-8")):
        raise PacketError(f"covered set paths are not canonically sorted: {set_path}")
    return tuple(covered)


def _inputs_from_args(
    *,
    repo_root: Path,
    source_ref: str,
    covered: Sequence[str] | None,
    covered_set: str | None,
    instructions: str,
) -> tuple[InputSpec, ...]:
    if covered_set is not None:
        pinned_instructions = PRESET_INSTRUCTION_PATHS.get(covered_set)
        if pinned_instructions is not None and instructions != pinned_instructions:
            raise PacketError(
                f"covered set {covered_set!r} pins instruction brief "
                f"{pinned_instructions!r}"
            )
        paths = _covered_paths_for_name(repo_root, source_ref, covered_set)
    else:
        paths = tuple(covered or ())
    return tuple(InputSpec(role="covered", path=path) for path in paths) + (
        InputSpec(role="instructions", path=instructions),
    )


def _freeze_command(args: argparse.Namespace) -> int:
    inputs = _inputs_from_args(
        repo_root=args.repo,
        source_ref=args.source,
        covered=args.covered,
        covered_set=args.covered_set,
        instructions=args.instructions,
    )
    built = build_from_git(
        repo_root=args.repo,
        source_ref=args.source,
        base_ref=args.base,
        upstream_ref=args.upstream,
        inputs=inputs,
    )
    artifacts = write_artifacts(built, args.output_store)
    result = {
        "input_manifest_sha256": built.manifest_sha256,
        "packet_path": str(artifacts.packet_path),
        "packet_sha256": built.packet_sha256,
        "receipt_path": str(artifacts.receipt_path),
        "source_head": built.source_head,
    }
    sys.stdout.buffer.write(canonical_json_bytes(result) + b"\n")
    return 0


def _compare_projection_command(args: argparse.Namespace) -> int:
    left_inputs = _inputs_from_args(
        repo_root=args.repo,
        source_ref=args.left,
        covered=args.covered,
        covered_set=args.covered_set,
        instructions=args.instructions,
    )
    right_inputs = _inputs_from_args(
        repo_root=args.repo,
        source_ref=args.right,
        covered=args.covered,
        covered_set=args.covered_set,
        instructions=args.instructions,
    )
    left = build_projection_from_git(
        repo_root=args.repo,
        source_ref=args.left,
        inputs=left_inputs,
    )
    right = build_projection_from_git(
        repo_root=args.repo,
        source_ref=args.right,
        inputs=right_inputs,
    )
    equal = left.projection_sha256 == right.projection_sha256
    result = {
        "equal": equal,
        "left_input_manifest_sha256": left.projection_sha256,
        "right_input_manifest_sha256": right.projection_sha256,
    }
    sys.stdout.buffer.write(canonical_json_bytes(result) + b"\n")
    return 0 if equal else 1


def _verify_command(args: argparse.Namespace) -> int:
    payload = args.packet.read_bytes()
    parsed = parse_packet(payload)
    result = {
        "document_count": len(parsed.documents),
        "input_manifest_sha256": parsed.manifest_sha256,
        "packet_sha256": parsed.packet_sha256,
        "valid": True,
    }
    sys.stdout.buffer.write(canonical_json_bytes(result) + b"\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze = subparsers.add_parser(
        "freeze", help="freeze a packet from committed Git objects"
    )
    freeze.add_argument("--repo", type=Path, required=True)
    freeze.add_argument("--source", required=True)
    freeze.add_argument("--base", required=True)
    freeze.add_argument("--upstream", default="origin/main")
    freeze_inputs = freeze.add_mutually_exclusive_group(required=True)
    freeze_inputs.add_argument("--covered", action="append")
    freeze_inputs.add_argument("--covered-set")
    freeze.add_argument("--instructions", required=True)
    freeze.add_argument("--output-store", type=Path, required=True)
    freeze.set_defaults(handler=_freeze_command)

    compare = subparsers.add_parser(
        "compare-projection",
        help="compare covered/instructions projections at two commits",
    )
    compare.add_argument("--repo", type=Path, required=True)
    compare.add_argument("--left", required=True)
    compare.add_argument("--right", required=True)
    compare_inputs = compare.add_mutually_exclusive_group(required=True)
    compare_inputs.add_argument("--covered", action="append")
    compare_inputs.add_argument("--covered-set")
    compare.add_argument("--instructions", required=True)
    compare.set_defaults(handler=_compare_projection_command)

    verify = subparsers.add_parser("verify", help="strictly verify a packet")
    verify.add_argument("--packet", type=Path, required=True)
    verify.set_defaults(handler=_verify_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, PacketError) as exc:
        print(f"packet error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
