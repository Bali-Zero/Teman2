"""Read pre-issued grants; a caller-supplied hash is never authority.

The installed helper fixes these paths and checks its kernel service identity.
Directory/file ownership is the trust input. PostgreSQL, not these immutable
files, owns admission, expiry, revocation, attempts, and outcomes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from typing import Any
from uuid import UUID

CONFIG_PATH = Path("/var/db/nuzantara-consul/config.json")
GRANTS_DIR = Path("/var/db/nuzantara-consul/grants")
SERVICE_USER = "_nuz_consul"
MAX_GRANT_BYTES = 262144
MAX_REQUEST_BYTES = 65536


def strict_json(raw: bytes) -> dict[str, Any]:
    """Reject duplicate keys and non-JSON numeric constants at the boundary."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise ValueError("invalid_number")

    obj = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    if not isinstance(obj, dict):
        raise ValueError("object_required")
    return obj


def grant_name(grant_id: object) -> str:
    if not isinstance(grant_id, str) or str(UUID(grant_id)) != grant_id:
        raise ValueError("canonical_grant_id_required")
    return grant_id + ".json"


def _trusted_directory(path: Path, owner_uid: int) -> None:
    """Require a non-replaceable ancestor chain, including the named directory."""
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise PermissionError("grant_directory_not_regular")
    for ancestor in (path.resolve(strict=True), *path.resolve(strict=True).parents):
        info = ancestor.stat()
        if info.st_uid not in {0, owner_uid}:
            raise PermissionError("untrusted_directory_owner")
        # A root-owned sticky /tmp protects the next component's trusted owner.
        sticky_root = info.st_uid == 0 and bool(info.st_mode & stat.S_ISVTX)
        if info.st_mode & 0o022 and not sticky_root:
            raise PermissionError("writable_directory")


def protected_document(
    directory: Path,
    filename: str,
    *,
    file_uid: int,
    directory_uid: int = 0,
    private: bool = False,
    max_bytes: int = MAX_GRANT_BYTES,
) -> dict[str, Any]:
    """Use directory descriptors/O_NOFOLLOW; reject writable or linked files."""
    if Path(filename).name != filename or filename in {".", ".."}:
        raise ValueError("filename_required")
    _trusted_directory(directory, directory_uid)
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open(
            filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd
        )
        try:
            info = os.fstat(fd)
            forbidden = 0o077 if private else 0o022
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != file_uid
                or info.st_mode & forbidden
                or info.st_nlink != 1
                or not 0 < info.st_size <= max_bytes
            ):
                raise PermissionError("untrusted_document")
            raw = bytearray()
            while len(raw) <= max_bytes:
                chunk = os.read(fd, min(65536, max_bytes + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
            if len(raw) > max_bytes:
                raise ValueError("document_too_large")
            return strict_json(bytes(raw))
        finally:
            os.close(fd)
    finally:
        os.close(directory_fd)


def load_grant(grant_id: str) -> dict[str, Any]:
    return protected_document(GRANTS_DIR, grant_name(grant_id), file_uid=0)


def load_config(service_uid: int) -> dict[str, Any]:
    config = protected_document(
        CONFIG_PATH.parent,
        CONFIG_PATH.name,
        file_uid=service_uid,
        private=True,
        max_bytes=8192,
    )
    if set(config) != {"database_dsn", "grants_dir"} or config["grants_dir"] != str(
        GRANTS_DIR
    ):
        raise PermissionError("fixed_configuration_required")
    dsn = config["database_dsn"]
    if not isinstance(dsn, str) or not dsn.startswith("postgresql://"):
        raise PermissionError("database_configuration_required")
    return config


def parse_request(raw: bytes) -> dict[str, Any]:
    if not 0 < len(raw) <= MAX_REQUEST_BYTES:
        raise ValueError("request_size")
    request = strict_json(raw)
    if type(request.get("version")) is not int or request["version"] != 1:
        raise ValueError("protocol_version")
    grant_name(request.get("grant_id"))
    fields = {
        "admit": {"binding"},
        "check": {"lease", "binding", "phase"},
        "cancel": set(),
        "checkpoint": {"lease", "binding", "result"},
    }
    verb = request.get("verb")
    if not isinstance(verb, str) or verb not in fields:
        raise ValueError("closed_verb_required")
    required = {"version", "verb", "grant_id"} | fields[verb]
    allowed = required | ({"lease"} if verb == "cancel" else set())
    if not required <= request.keys() or request.keys() - allowed:
        raise ValueError("closed_request_fields")
    if "phase" in request and request["phase"] not in {
        "start",
        "resume",
        "turn",
        "complete",
    }:
        raise ValueError("closed_phase_required")
    return request
