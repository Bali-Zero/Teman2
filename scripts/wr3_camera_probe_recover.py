#!/usr/bin/env python3
"""Crash-safe recovery of one already-generated WR3 camera-probe MP4.

This command can only retrieve media for the exact Flow identifiers authorized
by a trusted, pre-recovery receipt SHA-256. It never imports or calls a render
submission primitive.

The recovery protocol is write-ahead: the initial receipt bytes, exact Flow
tuple, and deterministic staging path are durably bound before network; media
is downloaded to staging, validated, SHA-pinned, atomically published, and each
rename is followed by a directory fsync. Restarts reconcile every durable
boundary without repeating a completed download.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import copy
import fcntl
import hashlib
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence
from urllib.parse import urljoin, urlsplit

from wr3_flowkit_client import (
    EpisodeContext,
    _download_video_media,
    _http_get_json,
)


RECOVERY_VERSION = "1.1"
RECOVERY_SCHEMA_VERSION = "wr3-camera-probe-recovery/1.1"
AUTHORIZATION_SCHEMA_VERSION = "wr3-camera-probe-recovery-authorization/1.1"
STAGING_SCHEMA_VERSION = "wr3-camera-probe-recovery-staging/1.0"
SUPPORTED_RECEIPT_SCHEMA = "wr3-camera-probe-run-receipt/1.1"
DEFAULT_TIMEOUT_S = 240
DEFAULT_POLL_INTERVAL_S = 10
FLOWKIT_GATEWAY_PORT = 8100
LIVE_DELTA_SCOPE = "global_account_balance_observation_not_per_workflow"


class ProbeRecoveryError(RuntimeError):
    """Base error for recovery-only probe operations."""


class ReceiptValidationError(ProbeRecoveryError):
    """The durable receipt and local artifact state disagree or are unsafe."""


class ProbeDownloadRecoveryError(ProbeRecoveryError):
    """The single workflow-aware download attempt failed."""


class ProbeCreditReadError(ProbeRecoveryError):
    """The MP4 is durable but the read-only live-credit query failed."""


@dataclass(frozen=True)
class RecoveryConfig:
    receipt: Path
    expected_initial_receipt_sha256: str
    timeout_s: int = DEFAULT_TIMEOUT_S
    poll_interval_s: int = DEFAULT_POLL_INTERVAL_S


@dataclass(frozen=True)
class RecoveryIds:
    project_id: str
    video_id: str
    workflow_id: str
    media_id: str


@dataclass(frozen=True)
class ValidatedRecovery:
    receipt_path: Path
    receipt: dict[str, Any]
    ids: RecoveryIds
    endpoint: str
    paygate: str
    episode_id: str
    mp4_path: Path
    staging_path: Path
    staging_token: str
    initial_receipt_bytes: bytes
    expected_initial_receipt_sha256: str
    authorization_tuple: dict[str, Any]
    mode: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _required_exact_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReceiptValidationError(
            f"{label} must be an exact non-empty string without outer whitespace"
        )
    return value


def _required_non_negative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReceiptValidationError(f"{label} must be a non-negative integer")
    return value


def _required_sha256(value: Any, label: str) -> str:
    raw = _required_exact_string(value, label).lower()
    if len(raw) != 64 or any(char not in "0123456789abcdef" for char in raw):
        raise ReceiptValidationError(f"{label} must be a 64-character SHA-256")
    return raw


def _validate_endpoint(value: Any) -> str:
    endpoint = _required_exact_string(value, "flow.endpoint")
    parsed = urlsplit(endpoint)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ReceiptValidationError(
            f"flow.endpoint has an invalid port: {endpoint}"
        ) from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "::1"}
        or port != FLOWKIT_GATEWAY_PORT
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ReceiptValidationError(
            "flow.endpoint must be the literal loopback FlowKit gateway on "
            f"port {FLOWKIT_GATEWAY_PORT}: {endpoint}"
        )
    return endpoint.rstrip("/")


def _recovery_lock_path(receipt_path: Path) -> Path:
    return receipt_path.with_name(f".{receipt_path.name}.recovery.lock")


@contextmanager
def _exclusive_recovery_lock(receipt_path: Path) -> Iterator[None]:
    """Hold one persistent, non-blocking lock for the whole recovery lifecycle."""
    lock_path = _recovery_lock_path(receipt_path)
    if not lock_path.parent.is_dir():
        raise ReceiptValidationError(
            f"receipt directory does not exist: {lock_path.parent}"
        )
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    except OSError as exc:
        raise ReceiptValidationError(
            f"cannot open recovery lock: {lock_path}: {exc}"
        ) from exc
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ReceiptValidationError(
                f"recovery already in progress for receipt: {receipt_path}"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _parse_json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptValidationError(f"{label} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReceiptValidationError(f"{label} must be a JSON object")
    return payload


def _read_receipt(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ReceiptValidationError(f"receipt is unreadable: {path}: {exc}") from exc
    return data, _parse_json_object(data, "receipt")


def _fsync_directory(path: Path) -> None:
    """Make a rename durable by syncing its containing directory."""
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_file(path: Path) -> None:
    """Make validated staging bytes durable before their receipt metadata."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Durably replace one receipt; never expose partially written JSON."""
    encoded = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _validate_mp4(path: Path) -> tuple[int, str]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ReceiptValidationError(f"MP4 is unreadable: {path}: {exc}") from exc
    if len(data) < 32 or b"ftyp" not in data[:32]:
        raise ReceiptValidationError(
            f"artifact is not a non-empty MP4: path={path} bytes={len(data)}"
        )
    return len(data), _sha256_bytes(data)


def _artifact_path(receipt_path: Path, artifact: dict[str, Any]) -> Path:
    raw = _required_exact_string(artifact.get("mp4_path"), "artifact.mp4_path")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = receipt_path.parent / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(receipt_path.parent)
    except ValueError as exc:
        raise ReceiptValidationError(
            "artifact.mp4_path must stay inside the receipt directory"
        ) from exc
    if resolved.suffix.lower() != ".mp4":
        raise ReceiptValidationError("artifact.mp4_path must end in .mp4")
    return resolved


def _validate_exact_ids(receipt: dict[str, Any]) -> RecoveryIds:
    flow = receipt.get("flow")
    if not isinstance(flow, dict):
        raise ReceiptValidationError("flow must be a JSON object")
    return RecoveryIds(
        project_id=_required_exact_string(flow.get("project_id"), "flow.project_id"),
        video_id=_required_exact_string(flow.get("video_id"), "flow.video_id"),
        workflow_id=_required_exact_string(flow.get("workflow_id"), "flow.workflow_id"),
        media_id=_required_exact_string(flow.get("media_id"), "flow.media_id"),
    )


def _ids_payload(ids: RecoveryIds) -> dict[str, str]:
    return {
        "project_id": ids.project_id,
        "video_id": ids.video_id,
        "workflow_id": ids.workflow_id,
        "media_id": ids.media_id,
    }


def _credit_authorization_tuple(receipt: dict[str, Any]) -> dict[str, Any]:
    """Bind initial credit truth while normalizing older v1.1 receipts.

    The live-after fields are recovery outputs. Everything else supplied by the
    runner, including the account baseline and declared-cost provenance, is
    immutable. Early v1.1 receipts (including the pinned M02 receipt) predate
    the explicit scope and exact-cost boolean, so absence is normalized to the
    only semantics recovery is allowed to publish.
    """
    credits = receipt.get("credits")
    if not isinstance(credits, dict):
        raise ReceiptValidationError("credits must be a JSON object")
    credit_tuple = copy.deepcopy(credits)
    for key in ("live_after", "live_delta", "live_balance_delta_observed"):
        credit_tuple.pop(key, None)
    credit_tuple["live_before"] = _required_non_negative_int(
        credits.get("live_before"),
        "credits.live_before",
    )
    scope = credits.get("live_delta_scope")
    if scope is not None and scope != LIVE_DELTA_SCOPE:
        raise ReceiptValidationError(
            f"credits.live_delta_scope must be {LIVE_DELTA_SCOPE!r}"
        )
    exact_cost = credits.get("live_delta_is_exact_workflow_cost")
    if exact_cost is not None and exact_cost is not False:
        raise ReceiptValidationError(
            "credits.live_delta_is_exact_workflow_cost must be false"
        )
    credit_tuple["live_delta_scope"] = LIVE_DELTA_SCOPE
    credit_tuple["live_delta_is_exact_workflow_cost"] = False
    return credit_tuple


def _authorization_tuple(
    receipt_path: Path,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Extract every immutable field that authorizes media recovery."""
    if receipt.get("schema_version") != SUPPORTED_RECEIPT_SCHEMA:
        raise ReceiptValidationError(
            f"receipt schema must be exactly {SUPPORTED_RECEIPT_SCHEMA!r}"
        )
    if receipt.get("generation_status") != "successful":
        raise ReceiptValidationError(
            "generation_status must be successful; recovery never submits a render"
        )
    ids = _validate_exact_ids(receipt)
    flow = receipt["flow"]
    if flow.get("generate_call_count") != 1:
        raise ReceiptValidationError("flow.generate_call_count must be exactly 1")
    endpoint = _validate_endpoint(flow.get("endpoint"))
    paygate = _required_exact_string(flow.get("paygate"), "flow.paygate")

    source = receipt.get("source")
    if not isinstance(source, dict):
        raise ReceiptValidationError("source must be a JSON object")
    source_tuple = copy.deepcopy(source)
    source_tuple["episode_id"] = _required_exact_string(
        source.get("episode_id"), "source.episode_id"
    )
    source_tuple["family_id"] = _required_exact_string(
        source.get("family_id"), "source.family_id"
    )
    source_tuple["variant_id"] = _required_exact_string(
        source.get("variant_id"), "source.variant_id"
    )
    source_tuple["shot_index"] = _required_non_negative_int(
        source.get("shot_index"), "source.shot_index"
    )

    artifact = receipt.get("artifact")
    if not isinstance(artifact, dict):
        raise ReceiptValidationError("artifact must be a JSON object")
    mp4_path = _artifact_path(receipt_path, artifact)
    # Every Flow field is immutable except the recovery download-call counter.
    # This captures scene/start-media identifiers present in real receipts, not
    # just the four identifiers passed to the download primitive.
    flow_tuple = copy.deepcopy(flow)
    flow_tuple.pop("download_call_count", None)
    flow_tuple["endpoint"] = endpoint
    flow_tuple["paygate"] = paygate
    flow_tuple["project_id"] = ids.project_id
    flow_tuple["video_id"] = ids.video_id
    flow_tuple["workflow_id"] = ids.workflow_id
    flow_tuple["media_id"] = ids.media_id
    flow_tuple["generate_call_count"] = 1
    return {
        "receipt_schema": SUPPORTED_RECEIPT_SCHEMA,
        "runner_version": receipt.get("runner_version"),
        "created_at": receipt.get("created_at"),
        "flow": flow_tuple,
        "source": source_tuple,
        "credits": _credit_authorization_tuple(receipt),
        "artifact_mp4_path": str(mp4_path),
    }


def _staging_token(
    expected_initial_receipt_sha256: str,
    authorization_tuple: dict[str, Any],
) -> str:
    payload = {
        "expected_initial_receipt_sha256": expected_initial_receipt_sha256,
        "authorization_tuple": authorization_tuple,
    }
    return _sha256_bytes(_canonical_json_bytes(payload))


def _staging_path(mp4_path: Path, token: str) -> Path:
    return mp4_path.with_name(f".{mp4_path.name}.{token[:24]}.recovery-stage.mp4")


def _authorization_payload(
    *,
    initial_receipt_bytes: bytes,
    expected_initial_receipt_sha256: str,
    authorization_tuple: dict[str, Any],
    staging_token: str,
) -> dict[str, Any]:
    return {
        "schema_version": AUTHORIZATION_SCHEMA_VERSION,
        "initial_receipt_sha256": expected_initial_receipt_sha256,
        "initial_receipt_bytes_b64": base64.b64encode(initial_receipt_bytes).decode(
            "ascii"
        ),
        "authorization_tuple": copy.deepcopy(authorization_tuple),
        "staging_token": staging_token,
    }


def _validate_authorization(
    *,
    receipt_path: Path,
    current_receipt: dict[str, Any],
    recovery: dict[str, Any],
    expected_initial_receipt_sha256: str,
) -> tuple[bytes, dict[str, Any], str]:
    authorization = recovery.get("authorization")
    if not isinstance(authorization, dict):
        raise ReceiptValidationError(
            "existing recovery state lacks immutable initial-receipt authorization"
        )
    if authorization.get("schema_version") != AUTHORIZATION_SCHEMA_VERSION:
        raise ReceiptValidationError("unsupported recovery authorization schema")
    if (
        _required_sha256(
            authorization.get("initial_receipt_sha256"),
            "recovery.authorization.initial_receipt_sha256",
        )
        != expected_initial_receipt_sha256
    ):
        raise ReceiptValidationError(
            "trusted initial receipt SHA-256 does not match binding"
        )
    encoded = _required_exact_string(
        authorization.get("initial_receipt_bytes_b64"),
        "recovery.authorization.initial_receipt_bytes_b64",
    )
    try:
        initial_receipt_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ReceiptValidationError(
            "recovery authorization contains invalid initial receipt bytes"
        ) from exc
    if _sha256_bytes(initial_receipt_bytes) != expected_initial_receipt_sha256:
        raise ReceiptValidationError(
            "stored initial receipt bytes fail trusted SHA-256"
        )
    initial_receipt = _parse_json_object(
        initial_receipt_bytes,
        "authorized initial receipt",
    )
    if initial_receipt.get("recovery") is not None:
        raise ReceiptValidationError(
            "authorized initial receipt must predate recovery state"
        )
    original_tuple = _authorization_tuple(receipt_path, initial_receipt)
    if authorization.get("authorization_tuple") != original_tuple:
        raise ReceiptValidationError(
            "stored recovery authorization tuple differs from initial receipt"
        )
    if _authorization_tuple(receipt_path, current_receipt) != original_tuple:
        raise ReceiptValidationError(
            "current receipt immutable authorization tuple differs from initial receipt"
        )
    token = _staging_token(expected_initial_receipt_sha256, original_tuple)
    if authorization.get("staging_token") != token:
        raise ReceiptValidationError(
            "recovery staging token differs from authorization"
        )
    return initial_receipt_bytes, original_tuple, token


def _staging_binding_payload(
    *,
    ids: RecoveryIds,
    staging_path: Path,
    final_path: Path,
    token: str,
) -> dict[str, Any]:
    return {
        "schema_version": STAGING_SCHEMA_VERSION,
        "token": token,
        "path": str(staging_path),
        "final_path": str(final_path),
        "ids": _ids_payload(ids),
        "status": "bound",
        "bytes": None,
        "sha256": None,
    }


def _validate_staging_binding(
    recovery: dict[str, Any],
    *,
    ids: RecoveryIds,
    staging_path: Path,
    final_path: Path,
    token: str,
) -> dict[str, Any]:
    staging = recovery.get("staging")
    if not isinstance(staging, dict):
        raise ReceiptValidationError("existing recovery state lacks staging binding")
    expected_fixed = {
        "schema_version": STAGING_SCHEMA_VERSION,
        "token": token,
        "path": str(staging_path),
        "final_path": str(final_path),
        "ids": _ids_payload(ids),
    }
    for key, value in expected_fixed.items():
        if staging.get(key) != value:
            raise ReceiptValidationError(f"recovery staging binding changed: {key}")
    status = staging.get("status")
    if status not in {"bound", "staged", "published"}:
        raise ReceiptValidationError("invalid recovery staging status")
    if status == "bound":
        if staging.get("bytes") is not None or staging.get("sha256") is not None:
            raise ReceiptValidationError("bound staging state cannot contain metadata")
    else:
        _required_non_negative_int(staging.get("bytes"), "recovery.staging.bytes")
        _required_sha256(staging.get("sha256"), "recovery.staging.sha256")
    return staging


def _assert_ids_unchanged(receipt: dict[str, Any], expected: RecoveryIds) -> None:
    if _validate_exact_ids(receipt) != expected:
        raise ReceiptValidationError("charged Flow identifiers changed during recovery")
    if receipt.get("generation_status") != "successful":
        raise ReceiptValidationError("generation_status changed during recovery")


def _validate_recorded_file(
    *,
    path: Path,
    expected_bytes: Any,
    expected_sha256: Any,
    label: str,
) -> tuple[int, str]:
    byte_count = _required_non_negative_int(expected_bytes, f"{label}.bytes")
    sha256 = _required_sha256(expected_sha256, f"{label}.sha256")
    actual_bytes, actual_sha = _validate_mp4(path)
    if actual_bytes != byte_count or actual_sha != sha256:
        raise ReceiptValidationError(f"{label} metadata does not match {path}")
    return actual_bytes, actual_sha


def _validate_recorded_artifact(
    artifact: dict[str, Any],
    mp4_path: Path,
) -> tuple[int, str]:
    return _validate_recorded_file(
        path=mp4_path,
        expected_bytes=artifact.get("bytes"),
        expected_sha256=artifact.get("sha256"),
        label="artifact",
    )


def _validate_recorded_staging(
    staging: dict[str, Any],
    path: Path,
) -> tuple[int, str]:
    return _validate_recorded_file(
        path=path,
        expected_bytes=staging.get("bytes"),
        expected_sha256=staging.get("sha256"),
        label="recovery.staging",
    )


def _validate_recovery_attempts(recovery: dict[str, Any]) -> list[dict[str, Any]]:
    attempts = recovery.get("attempts")
    if not isinstance(attempts, list):
        raise ReceiptValidationError("recovery.attempts must be a list")
    for index, attempt in enumerate(attempts, start=1):
        if not isinstance(attempt, dict) or attempt.get("attempt") != index:
            raise ReceiptValidationError("recovery attempts must be sequential objects")
    return attempts


def _determine_recovery_mode(
    *,
    receipt: dict[str, Any],
    recovery: dict[str, Any] | None,
    staging: dict[str, Any] | None,
    staging_path: Path,
    mp4_path: Path,
) -> str:
    artifact = receipt["artifact"]
    stage_exists = staging_path.exists()
    final_exists = mp4_path.exists()
    if stage_exists and final_exists:
        raise ReceiptValidationError(
            "both bound staging and final MP4 exist; publication state is ambiguous"
        )

    if recovery is None:
        if stage_exists or final_exists:
            raise ReceiptValidationError(
                "existing MP4 has no immutable recovery authorization binding"
            )
        if artifact.get("bytes") is not None or artifact.get("sha256") is not None:
            raise ReceiptValidationError(
                "missing MP4 cannot retain artifact bytes or SHA-256"
            )
        return "download"

    if staging is None:
        raise ReceiptValidationError(
            "recovery state lacks deterministic staging binding"
        )
    stage_status = staging["status"]
    artifact_has_metadata = (
        artifact.get("bytes") is not None or artifact.get("sha256") is not None
    )

    if stage_exists:
        if stage_status == "published":
            raise ReceiptValidationError(
                "published staging state cannot retain a staging MP4"
            )
        if artifact_has_metadata:
            raise ReceiptValidationError(
                "staging MP4 cannot coexist with final artifact metadata"
            )
        if stage_status == "staged":
            _validate_recorded_staging(staging, staging_path)
            return "resume_staged"
        _validate_mp4(staging_path)
        return "resume_unrecorded_staging"

    if final_exists:
        if stage_status not in {"staged", "published"}:
            raise ReceiptValidationError(
                "final MP4 exists without recorded staging metadata"
            )
        staged_metadata = _validate_recorded_file(
            path=mp4_path,
            expected_bytes=staging.get("bytes"),
            expected_sha256=staging.get("sha256"),
            label="recovery.staging",
        )
        if artifact_has_metadata:
            artifact_metadata = _validate_recorded_artifact(artifact, mp4_path)
            if artifact_metadata != staged_metadata:
                raise ReceiptValidationError(
                    "artifact metadata differs from authorized staging metadata"
                )
            return "resume_artifact"
        return "resume_published"

    if stage_status in {"staged", "published"}:
        raise ReceiptValidationError(
            "receipt records recovered bytes but neither staging nor final MP4 exists"
        )
    if artifact_has_metadata:
        raise ReceiptValidationError(
            "missing final MP4 cannot retain artifact metadata"
        )
    return "download"


def validate_recovery(config: RecoveryConfig) -> ValidatedRecovery:
    """Validate all authorization, receipt, and filesystem invariants."""
    if config.timeout_s <= 0:
        raise ReceiptValidationError("timeout_s must be positive")
    if config.poll_interval_s < 0:
        raise ReceiptValidationError("poll_interval_s must be non-negative")
    expected_sha = _required_sha256(
        config.expected_initial_receipt_sha256,
        "expected_initial_receipt_sha256",
    )

    receipt_path = config.receipt.expanduser().resolve()
    if not receipt_path.is_file():
        raise ReceiptValidationError(f"receipt does not exist: {receipt_path}")
    receipt_bytes, receipt = _read_receipt(receipt_path)
    current_tuple = _authorization_tuple(receipt_path, receipt)
    ids = _validate_exact_ids(receipt)
    flow = receipt["flow"]
    _required_non_negative_int(
        flow.get("download_call_count"),
        "flow.download_call_count",
    )

    recovery_raw = receipt.get("recovery")
    recovery: dict[str, Any] | None
    if recovery_raw is None:
        if _sha256_bytes(receipt_bytes) != expected_sha:
            raise ReceiptValidationError(
                "trusted initial receipt SHA-256 does not match receipt bytes"
            )
        initial_receipt_bytes = receipt_bytes
        authorization_tuple = current_tuple
        token = _staging_token(expected_sha, authorization_tuple)
        recovery = None
    elif isinstance(recovery_raw, dict):
        if recovery_raw.get("schema_version") != RECOVERY_SCHEMA_VERSION:
            raise ReceiptValidationError("unsupported existing recovery state schema")
        _validate_recovery_attempts(recovery_raw)
        initial_receipt_bytes, authorization_tuple, token = _validate_authorization(
            receipt_path=receipt_path,
            current_receipt=receipt,
            recovery=recovery_raw,
            expected_initial_receipt_sha256=expected_sha,
        )
        recovery = recovery_raw
    else:
        raise ReceiptValidationError("recovery must be a JSON object when present")

    endpoint = current_tuple["flow"]["endpoint"]
    paygate = current_tuple["flow"]["paygate"]
    episode_id = current_tuple["source"]["episode_id"]
    mp4_path = Path(current_tuple["artifact_mp4_path"])
    staging_path = _staging_path(mp4_path, token)

    staging: dict[str, Any] | None = None
    if recovery is not None:
        staging = _validate_staging_binding(
            recovery,
            ids=ids,
            staging_path=staging_path,
            final_path=mp4_path,
            token=token,
        )

    credits = receipt.get("credits")
    if not isinstance(credits, dict):
        raise ReceiptValidationError("credits must be a JSON object")
    live_before = _required_non_negative_int(
        credits.get("live_before"), "credits.live_before"
    )
    artifact = receipt.get("artifact")
    if not isinstance(artifact, dict):
        raise ReceiptValidationError("artifact must be a JSON object")
    retrieval_status = receipt.get("retrieval_status")

    if retrieval_status == "successful":
        if receipt.get("error") is not None:
            raise ReceiptValidationError(
                "successful retrieval cannot retain a top-level error"
            )
        if staging_path.exists():
            raise ReceiptValidationError(
                "successful retrieval cannot retain a staging MP4"
            )
        _validate_recorded_artifact(artifact, mp4_path)
        live_after = _required_non_negative_int(
            credits.get("live_after"),
            "credits.live_after",
        )
        live_delta = credits.get("live_delta")
        if isinstance(live_delta, bool) or not isinstance(live_delta, int):
            raise ReceiptValidationError("credits.live_delta must be an integer")
        if live_delta != live_before - live_after:
            raise ReceiptValidationError(
                "credits.live_delta disagrees with live credit readings"
            )
        if credits.get("live_balance_delta_observed") != live_delta:
            raise ReceiptValidationError(
                "credits.live_balance_delta_observed must equal credits.live_delta"
            )
        if credits.get("live_delta_scope") != LIVE_DELTA_SCOPE:
            raise ReceiptValidationError(
                f"credits.live_delta_scope must be {LIVE_DELTA_SCOPE!r}"
            )
        if credits.get("live_delta_is_exact_workflow_cost") is not False:
            raise ReceiptValidationError(
                "credits.live_delta_is_exact_workflow_cost must be false"
            )
        mode = "already_successful"
    elif retrieval_status in {"failed", "pending", "not_started"}:
        if (
            credits.get("live_after") is not None
            or credits.get("live_delta") is not None
            or credits.get("live_balance_delta_observed") is not None
        ):
            raise ReceiptValidationError(
                "non-final retrieval cannot contain final live credit values"
            )
        mode = _determine_recovery_mode(
            receipt=receipt,
            recovery=recovery,
            staging=staging,
            staging_path=staging_path,
            mp4_path=mp4_path,
        )
    else:
        raise ReceiptValidationError(
            "retrieval_status must be failed, pending, not_started, or successful"
        )

    return ValidatedRecovery(
        receipt_path=receipt_path,
        receipt=receipt,
        ids=ids,
        endpoint=endpoint,
        paygate=paygate,
        episode_id=episode_id,
        mp4_path=mp4_path,
        staging_path=staging_path,
        staging_token=token,
        initial_receipt_bytes=initial_receipt_bytes,
        expected_initial_receipt_sha256=expected_sha,
        authorization_tuple=authorization_tuple,
        mode=mode,
    )


def _prepare_attempt(
    validated: ValidatedRecovery,
    receipt: dict[str, Any],
) -> int:
    recovery_raw = receipt.get("recovery")
    if recovery_raw is None:
        recovery: dict[str, Any] = {
            "schema_version": RECOVERY_SCHEMA_VERSION,
            "client_version": RECOVERY_VERSION,
            "original_error": copy.deepcopy(receipt.get("error")),
            "authorization": _authorization_payload(
                initial_receipt_bytes=validated.initial_receipt_bytes,
                expected_initial_receipt_sha256=(
                    validated.expected_initial_receipt_sha256
                ),
                authorization_tuple=validated.authorization_tuple,
                staging_token=validated.staging_token,
            ),
            "staging": _staging_binding_payload(
                ids=validated.ids,
                staging_path=validated.staging_path,
                final_path=validated.mp4_path,
                token=validated.staging_token,
            ),
            "attempts": [],
        }
        receipt["recovery"] = recovery
    elif isinstance(recovery_raw, dict):
        recovery = recovery_raw
        recovery["client_version"] = RECOVERY_VERSION
    else:
        raise ReceiptValidationError("recovery must be a JSON object when present")

    attempts = _validate_recovery_attempts(recovery)
    attempt_number = len(attempts) + 1
    initial_status = {
        "download": "downloading",
        "resume_unrecorded_staging": "reconciling_staging",
        "resume_staged": "reconciling_staging",
        "resume_published": "reconciling_published",
        "resume_artifact": "resuming_artifact",
    }[validated.mode]
    attempts.append(
        {
            "attempt": attempt_number,
            "started_at": _utc_now(),
            "completed_at": None,
            "mode": validated.mode,
            "status": initial_status,
            "ids": _ids_payload(validated.ids),
            "staging_token": validated.staging_token,
            "error": None,
        }
    )
    return attempt_number


def _last_attempt(receipt: dict[str, Any], attempt_number: int) -> dict[str, Any]:
    recovery = receipt.get("recovery")
    if not isinstance(recovery, dict):
        raise ReceiptValidationError("recovery state disappeared during recovery")
    attempts = _validate_recovery_attempts(recovery)
    if not attempts or attempts[-1].get("attempt") != attempt_number:
        raise ReceiptValidationError("last recovery attempt number changed")
    return attempts[-1]


def _staging_binding(receipt: dict[str, Any]) -> dict[str, Any]:
    recovery = receipt.get("recovery")
    if not isinstance(recovery, dict) or not isinstance(recovery.get("staging"), dict):
        raise ReceiptValidationError("recovery staging binding disappeared")
    return recovery["staging"]


def _error_payload(exc: BaseException) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def _record_failure(
    validated: ValidatedRecovery,
    receipt: dict[str, Any],
    *,
    attempt_number: int,
    exc: BaseException,
    artifact_recovered: bool,
) -> None:
    _assert_ids_unchanged(receipt, validated.ids)
    error = _error_payload(exc)
    attempt = _last_attempt(receipt, attempt_number)
    attempt["completed_at"] = _utc_now()
    attempt["error"] = error
    attempt["status"] = "artifact_recovered" if artifact_recovered else "failed"
    receipt["generation_status"] = "successful"
    receipt["retrieval_status"] = "failed"
    receipt["error"] = error
    receipt["updated_at"] = _utc_now()
    _write_json_atomic(validated.receipt_path, receipt)


def _extract_live_credits(payload: Any) -> int:
    if not isinstance(payload, dict) or payload.get("detail"):
        raise ProbeCreditReadError(f"live-credit read failed: {payload}")
    candidates = [payload.get("credits")]
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.append(data.get("credits"))
    for value in candidates:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    raise ProbeCreditReadError(
        f"live-credit payload has no non-negative integer: {payload}"
    )


async def _read_live_credits(endpoint: str) -> int:
    url = urljoin(endpoint.rstrip("/") + "/", "api/flow/credits")
    payload = await _http_get_json(url, timeout_s=30)
    return _extract_live_credits(payload)


def _persist_staged(
    validated: ValidatedRecovery,
    receipt: dict[str, Any],
    *,
    attempt_number: int,
    byte_count: int,
    sha256: str,
) -> None:
    # File data must reach stable storage before the receipt claims the staged
    # byte count and digest are durable. The parent fsync is separately needed
    # because the Flow client publishes its temporary file with a rename.
    _fsync_file(validated.staging_path)
    _fsync_directory(validated.staging_path.parent)
    staging = _staging_binding(receipt)
    staging["status"] = "staged"
    staging["bytes"] = byte_count
    staging["sha256"] = sha256
    attempt = _last_attempt(receipt, attempt_number)
    attempt["status"] = "staged"
    receipt["retrieval_status"] = "pending"
    receipt["updated_at"] = _utc_now()
    _assert_ids_unchanged(receipt, validated.ids)
    _write_json_atomic(validated.receipt_path, receipt)


def _publish_staged_artifact(staging_path: Path, mp4_path: Path) -> None:
    """Atomically publish a validated staging artifact and sync the directory.

    Cooperative writers of this probe's final path must hold the persistent
    receipt recovery lock. ``os.replace`` is atomic but is not a no-clobber
    primitive, so the precondition is enforced by the outer lock protocol; the
    immediate existence check additionally refuses any pre-existing artifact.
    """
    if not staging_path.is_file():
        raise ReceiptValidationError(f"bound staging MP4 is missing: {staging_path}")
    if mp4_path.exists():
        raise ReceiptValidationError(
            f"refusing to overwrite an existing final MP4: {mp4_path}"
        )
    os.replace(staging_path, mp4_path)
    _fsync_directory(mp4_path.parent)


def _persist_artifact_recovered(
    validated: ValidatedRecovery,
    receipt: dict[str, Any],
    *,
    attempt_number: int,
    byte_count: int,
    sha256: str,
) -> None:
    staging = _staging_binding(receipt)
    staging["status"] = "published"
    staging["bytes"] = byte_count
    staging["sha256"] = sha256
    receipt["artifact"]["bytes"] = byte_count
    receipt["artifact"]["sha256"] = sha256
    attempt = _last_attempt(receipt, attempt_number)
    attempt["status"] = "artifact_recovered"
    receipt["retrieval_status"] = "pending"
    receipt["updated_at"] = _utc_now()
    _assert_ids_unchanged(receipt, validated.ids)
    _write_json_atomic(validated.receipt_path, receipt)


async def _recover_one_locked(config: RecoveryConfig) -> dict[str, Any]:
    """Recover or finalize one receipt while its exclusive lock is held."""
    validated = validate_recovery(config)
    if validated.mode == "already_successful":
        return validated.receipt

    receipt = copy.deepcopy(validated.receipt)
    _assert_ids_unchanged(receipt, validated.ids)
    attempt_number = _prepare_attempt(validated, receipt)
    if validated.mode == "download":
        flow = receipt["flow"]
        flow["download_call_count"] = (
            _required_non_negative_int(
                flow.get("download_call_count"),
                "flow.download_call_count",
            )
            + 1
        )
    receipt["retrieval_status"] = "pending"
    receipt["updated_at"] = _utc_now()
    _assert_ids_unchanged(receipt, validated.ids)
    # Authorization, exact IDs, and staging are durable before network.
    _write_json_atomic(validated.receipt_path, receipt)

    if validated.mode == "download":
        validated.staging_path.parent.mkdir(parents=True, exist_ok=True)
        if validated.staging_path.exists() or validated.mp4_path.exists():
            raise ReceiptValidationError(
                "artifact appeared after validation but before recovery download"
            )
        context = EpisodeContext(
            project_id=validated.ids.project_id,
            video_id=validated.ids.video_id,
            project_name=validated.episode_id,
            endpoint=validated.endpoint,
            paygate=validated.paygate,
        )
        try:
            await _download_video_media(
                context,
                workflow_id=validated.ids.workflow_id,
                media_id=validated.ids.media_id,
                dest=validated.staging_path,
                timeout_s=config.timeout_s,
                poll_interval_s=config.poll_interval_s,
            )
            byte_count, mp4_sha = _validate_mp4(validated.staging_path)
        except Exception as exc:
            _record_failure(
                validated,
                receipt,
                attempt_number=attempt_number,
                exc=exc,
                artifact_recovered=False,
            )
            raise ProbeDownloadRecoveryError(
                "workflow media recovery failed; charged IDs were preserved and no "
                "render was resubmitted"
            ) from exc
        _persist_staged(
            validated,
            receipt,
            attempt_number=attempt_number,
            byte_count=byte_count,
            sha256=mp4_sha,
        )
        _publish_staged_artifact(validated.staging_path, validated.mp4_path)
        _persist_artifact_recovered(
            validated,
            receipt,
            attempt_number=attempt_number,
            byte_count=byte_count,
            sha256=mp4_sha,
        )
    elif validated.mode == "resume_unrecorded_staging":
        byte_count, mp4_sha = _validate_mp4(validated.staging_path)
        _persist_staged(
            validated,
            receipt,
            attempt_number=attempt_number,
            byte_count=byte_count,
            sha256=mp4_sha,
        )
        _publish_staged_artifact(validated.staging_path, validated.mp4_path)
        _persist_artifact_recovered(
            validated,
            receipt,
            attempt_number=attempt_number,
            byte_count=byte_count,
            sha256=mp4_sha,
        )
    elif validated.mode == "resume_staged":
        staging = _staging_binding(receipt)
        byte_count, mp4_sha = _validate_recorded_staging(
            staging,
            validated.staging_path,
        )
        _publish_staged_artifact(validated.staging_path, validated.mp4_path)
        _persist_artifact_recovered(
            validated,
            receipt,
            attempt_number=attempt_number,
            byte_count=byte_count,
            sha256=mp4_sha,
        )
    elif validated.mode == "resume_published":
        staging = _staging_binding(receipt)
        byte_count, mp4_sha = _validate_recorded_file(
            path=validated.mp4_path,
            expected_bytes=staging.get("bytes"),
            expected_sha256=staging.get("sha256"),
            label="recovery.staging",
        )
        _persist_artifact_recovered(
            validated,
            receipt,
            attempt_number=attempt_number,
            byte_count=byte_count,
            sha256=mp4_sha,
        )
    else:
        byte_count, mp4_sha = _validate_recorded_artifact(
            receipt["artifact"],
            validated.mp4_path,
        )

    try:
        live_after = await _read_live_credits(validated.endpoint)
    except Exception as exc:
        _record_failure(
            validated,
            receipt,
            attempt_number=attempt_number,
            exc=exc,
            artifact_recovered=True,
        )
        raise ProbeCreditReadError(
            "MP4 was recovered and SHA-pinned, but the read-only live-credit query failed"
        ) from exc

    live_before = _required_non_negative_int(
        receipt["credits"].get("live_before"),
        "credits.live_before",
    )
    receipt["credits"]["live_after"] = live_after
    observed_live_delta = live_before - live_after
    receipt["credits"]["live_delta"] = observed_live_delta
    receipt["credits"]["live_balance_delta_observed"] = observed_live_delta
    receipt["credits"]["live_delta_scope"] = LIVE_DELTA_SCOPE
    receipt["credits"]["live_delta_is_exact_workflow_cost"] = False
    receipt["artifact"]["bytes"] = byte_count
    receipt["artifact"]["sha256"] = mp4_sha
    receipt["generation_status"] = "successful"
    receipt["retrieval_status"] = "successful"
    receipt["error"] = None
    attempt = _last_attempt(receipt, attempt_number)
    attempt["status"] = "successful"
    attempt["completed_at"] = _utc_now()
    attempt["error"] = None
    receipt["updated_at"] = _utc_now()
    _assert_ids_unchanged(receipt, validated.ids)
    _write_json_atomic(validated.receipt_path, receipt)
    return receipt


async def recover_one(config: RecoveryConfig) -> dict[str, Any]:
    """Recover one receipt without resubmission or concurrent state races."""
    receipt_path = config.receipt.expanduser().resolve()
    with _exclusive_recovery_lock(receipt_path):
        return await _recover_one_locked(config)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recover one already-generated WR3 camera probe from its receipt",
    )
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument(
        "--expected-initial-receipt-sha256",
        required=True,
        help="Trusted SHA-256 of the exact receipt bytes before any recovery write",
    )
    parser.add_argument("--timeout-s", type=int, default=DEFAULT_TIMEOUT_S)
    parser.add_argument(
        "--poll-interval-s",
        type=int,
        default=DEFAULT_POLL_INTERVAL_S,
    )
    return parser


async def _async_main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = RecoveryConfig(
        receipt=args.receipt,
        expected_initial_receipt_sha256=args.expected_initial_receipt_sha256,
        timeout_s=args.timeout_s,
        poll_interval_s=args.poll_interval_s,
    )
    try:
        receipt = await recover_one(config)
    except ReceiptValidationError as exc:
        print(json.dumps({"ok": False, "stage": "validation", "error": str(exc)}))
        return 2
    except ProbeDownloadRecoveryError as exc:
        print(json.dumps({"ok": False, "stage": "retrieval", "error": str(exc)}))
        return 6
    except ProbeCreditReadError as exc:
        print(json.dumps({"ok": False, "stage": "credits", "error": str(exc)}))
        return 7
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": "recovery",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        )
        return 5

    print(json.dumps({"ok": True, "receipt": receipt}, ensure_ascii=False))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    sys.exit(main())
