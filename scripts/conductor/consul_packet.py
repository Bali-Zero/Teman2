"""Prepare an Astra/medium marker intent; assemble supplied canonical receipts.

No native calls, database access, issuance, installation, or approval creation.
Assembly validates receipt content, NOT issuer authenticity or current revocation.
The protected issuer must verify provenance before installing the resulting grant.
Mission IDs are opaque UUIDs. References must identify existing ROS objects; this
offline tool does not establish their existence. Producers use the native consul
names/version 4.0.0; lineage uses exact hashes and retention is audit/no legal hold,
as in the existing v4 contracts. Output is exclusively a new mode-0600 artifact.

Run: PYTHONPATH=apps/backend-rag:packages/research-os-core:. python -m scripts.conductor.consul_packet
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any
from uuid import UUID, uuid4

from backend.services.autonomous_lab.consul_executor import seal
from backend.services.autonomous_lab.consul_native_broker import (
    AUTHORITY,
    EFFECT,
    NativeGrant,
    _binding,
    _digest,
)
from research_os.models.action_intent import ActionIntent
from research_os.models.action_item import ActionItemRef, RequestedActionSpecRef
from scripts.conductor.codex_shadow_launch import validate_runtime_binding
from scripts.conductor.consul_native import CANARY_TEXT
from scripts.conductor.protected_grants import MAX_GRANT_BYTES, grant_name, strict_json


def _uuid(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError("canonical_uuid_required")
    return value


def _parent(path: Path) -> int:
    """Open every absolute path component without following any symlink."""
    if not path.is_absolute() or ".." in path.parts or not path.name:
        raise ValueError("absolute_artifact_path_required")
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:-1]:
            child = os.open(
                component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_json(path: Path) -> dict[str, Any]:
    directory = _parent(path)
    try:
        fd = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
        )
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or not 0 < info.st_size <= MAX_GRANT_BYTES
            ):
                raise ValueError("input_size_or_type")
            raw = handle.read(MAX_GRANT_BYTES + 1)
            if len(raw) > MAX_GRANT_BYTES:
                raise ValueError("input_size")
            return strict_json(raw)
    finally:
        os.close(directory)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    raw = (json.dumps(payload, allow_nan=False, separators=(",", ":")) + "\n").encode()
    if len(raw) > MAX_GRANT_BYTES:
        raise ValueError("output_size")
    directory = _parent(path)
    try:
        fd = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(directory)


def canary_binding(value: dict[str, Any]) -> dict[str, Any]:
    binding = _binding(value)
    _uuid(binding["mission_id"])
    key = binding["discovery_key"]
    version, separator, digest = key["runtime_version"].rpartition("@")
    if not separator:
        raise ValueError("runtime_binding_required")
    validate_runtime_binding(version, digest)
    if (
        binding["thread_id"] is not None
        or binding["model"] != "gpt-6-astra"
        or binding["effort"] != "medium"
        or binding["input_hash"] != sha256(CANARY_TEXT.encode()).hexdigest()
        or key["host"].lower().removesuffix(".local")
        not in {"air-m5", "nuzantara", "mini-pro2"}
    ):
        raise ValueError("fixed_canary_required")
    return binding


def prepare(
    discovery: dict[str, Any],
    *,
    producer: str,
    action_item_ref: dict[str, str],
    requested_action_spec_ref: dict[str, str],
    now: datetime | None = None,
) -> dict[str, Any]:
    if (
        set(discovery) != {"mode", "binding", "inference_performed"}
        or discovery["mode"] != "discovery"
        or discovery["inference_performed"] is not False
        or producer not in {"astra", "fable"}
    ):
        raise ValueError("discovery_or_producer_invalid")
    binding = canary_binding(discovery["binding"])
    item = ActionItemRef.model_validate(action_item_ref)
    spec = RequestedActionSpecRef.model_validate(requested_action_spec_ref)
    packet_hash, identifier = _digest(binding), str(uuid4())
    intent = seal(
        ActionIntent,
        {
            "action_intent_id": identifier,
            "contract_version": "research-os/v1.0.0",
            "tenant": "bali-zero",
            "action_item_ref": item.model_dump(mode="json"),
            "requested_action_spec_ref": spec.model_dump(mode="json"),
            "action_type": EFFECT,
            "target": {
                "system": "com.balizero.autonomous_lab",
                "object_ref": {
                    "object_kind": "com.balizero.lab_run",
                    "object_id": binding["mission_id"],
                    "object_hash": packet_hash,
                },
            },
            "arguments_ref": "native:" + binding["mission_id"],
            "arguments_hash": _digest(
                {"effect": EFFECT, "max_invocations": 1, "binding": binding}
            ),
            "input_revision_hash": packet_hash,
            "risk_class": "green",
            "sensitivity": "internal",
            "authority_required": {
                "role": AUTHORITY,
                "scope": binding["mission_id"],
                "expires_after_seconds": 3600,
            },
            "idempotency_key": identifier,
            "expected_outcome_types": [EFFECT],
            "created_at": (now or datetime.now(timezone.utc))
            .isoformat()
            .replace("+00:00", "Z"),
            "producer": {"name": "com.balizero.consul." + producer, "version": "4.0.0"},
            "lineage": {
                "input_hashes": [packet_hash, item.object_hash, spec.object_hash]
            },
            "retention": {"retention_class": "audit", "legal_hold": False},
        },
    )
    return {
        "version": 1,
        "binding": binding,
        "intent": intent.model_dump(mode="json", exclude_unset=True),
    }


def assemble(
    prepared: dict[str, Any],
    approval: dict[str, Any],
    review: dict[str, Any],
    *,
    grant_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    if (
        set(prepared) != {"version", "binding", "intent"}
        or type(prepared["version"]) is not int
        or prepared["version"] != 1
    ):
        raise ValueError("prepared_shape")
    grant_name(grant_id)
    payload = {
        "grant_id": grant_id,
        "binding": canary_binding(prepared["binding"]),
        "intent": prepared["intent"],
        "approval": approval,
        "review": review,
    }
    grant = NativeGrant.from_payload(payload)
    grant.validate(now or datetime.now(timezone.utc))
    return payload


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("arguments_invalid")


def main(argv: list[str] | None = None) -> int:
    try:
        parser = Parser(description=__doc__)
        modes = parser.add_subparsers(dest="mode", required=True)
        draft = modes.add_parser("prepare")
        draft.add_argument("--discovery", type=Path, required=True)
        draft.add_argument("--producer", choices=("astra", "fable"), required=True)
        for name in (
            "action-item-id",
            "action-item-hash",
            "requested-action-spec-id",
            "requested-action-spec-hash",
        ):
            draft.add_argument("--" + name, required=True)
        draft.add_argument("--output", type=Path, required=True)
        finish = modes.add_parser("assemble")
        for name in ("prepared", "approval", "review", "output"):
            finish.add_argument("--" + name, type=Path, required=True)
        finish.add_argument("--grant-id", required=True)
        args = parser.parse_args(argv)
        if args.mode == "prepare":
            result = prepare(
                read_json(args.discovery),
                producer=args.producer,
                action_item_ref={
                    "action_item_id": _uuid(args.action_item_id),
                    "object_hash": args.action_item_hash,
                },
                requested_action_spec_ref={
                    "requested_action_spec_id": _uuid(args.requested_action_spec_id),
                    "object_hash": args.requested_action_spec_hash,
                },
            )
        else:
            result = assemble(
                read_json(args.prepared),
                read_json(args.approval),
                read_json(args.review),
                grant_id=args.grant_id,
            )
        write_json(args.output, result)
        return 0
    except Exception:
        sys.stderr.write("consul_packet_refused\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
