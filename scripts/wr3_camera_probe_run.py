#!/usr/bin/env python3
"""Render exactly one approved WR3 camera-probe variant through FlowKit.

This runner is intentionally smaller and stricter than the episode renderer:

* one derived family pack in, one explicitly selected variant out;
* one scene and one video-generation call in either a fresh A007 context or an
  explicitly supplied, PASS-gated scene-start context;
* no retry, no fallback, no LLM, and no implicit credit allowance;
* a durable receipt is written before retrieval begins; and
* a failed retrieval can never turn into an automatic re-submission.

An existing scene-start run is accepted only when its three Flow IDs are
supplied together and an externally SHA-pinned authorization binds the exact
manifest, identity-gate JSON, raster, decision thresholds, selected variant,
and PASS lineage. Raw A007 is never uploaded or selected as the video start in
that mode.

The existing FlowKit client's private primitives are used on purpose.  The
normal public renderer owns a multi-shot retry loop, which is the wrong
contract for a diagnostic probe whose charged workflow/media IDs must survive
even when the legacy media endpoint cannot retrieve the finished clip.
"""

from __future__ import annotations

import argparse
import asyncio
import errno
import fcntl
import hashlib
import json
import math
import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence
from urllib.parse import urljoin, urlsplit
from uuid import UUID

import wr3_flowkit_client as fk
import wr3_camera_probe_recover as probe_recovery
from wr3_originality_gate import (
    OriginalityGateError,
    description_sha256 as originality_description_sha256,
    normalize_text as originality_normalize_text,
    read_validated_ledger,
    signature_sha256 as originality_signature_sha256,
    validated_ledger_prefix_sha256,
)


RUNNER_VERSION = "1.1"
RECEIPT_SCHEMA_VERSION = "wr3-camera-probe-run-receipt/1.1"
EXPECTED_PACK_SCHEMA = "wr3-camera-probe-runtime/1.0"
EXPECTED_ADAPTER_VERSION = "1.2"
EXPECTED_LINEAGE_SCHEMA = "wr3-camera-probe-lineage/1.0"
EXPECTED_VERDICT_SCHEMA = "wr3-camera-probe-gate/1.0"
SCENE_START_MANIFEST_SCHEMA = "wr3.scene-start-manifest.v1"
SCENE_START_GATE_SCHEMA = "wr3.scene-start-identity-gate.v1"
SCENE_START_AUTHORIZATION_SCHEMA = "wr3.scene-start-video-authorization.v1"
SCENE_START_AUTHORIZATION_SCOPE = "single_video_generation"
MIN_PASS_COSINE_THRESHOLD = 0.6
MAX_POSITIVE_PROMPT_WORDS = 25
DEFAULT_PAYGATE = "PAYGATE_TIER_TIER1P5"
DEFAULT_TIMEOUT_S = 300
RECEIPT_NAME = "probe-run-receipt.json"
CONTEXT_NAME = "_flowkit_context.json"
RUN_LOCK_NAME = ".probe-run.lock"
LIVE_DELTA_SCOPE = "global_account_balance_observation_not_per_workflow"
FLOWKIT_ALLOWED_HOSTS = frozenset({"127.0.0.1", "::1"})
FLOWKIT_ALLOWED_PORT = 8100
REPO_ROOT = Path(__file__).resolve().parents[1]


class ProbeRunError(RuntimeError):
    """Base error for a one-shot probe run."""


class ProbeValidationError(ProbeRunError):
    """Local input or cap violation detected before any network call."""


class ProbePreflightError(ProbeRunError):
    """FlowKit health, extension, or credit preflight failed."""


class ProbeRetrievalError(ProbeRunError):
    """Generation succeeded but the single retrieval attempt failed."""


@dataclass(frozen=True)
class RunConfig:
    shot_pack: Path
    variant_id: str
    episode_dir: Path
    endpoint: str
    paygate: str
    credit_cap: int
    accounted_credits: int
    measured_clip_cost: int
    timeout_s: int = DEFAULT_TIMEOUT_S
    existing_project_id: str | None = None
    existing_video_id: str | None = None
    scene_start_media_id: str | None = None
    scene_start_manifest: Path | None = None
    scene_start_authorization: Path | None = None
    scene_start_authorization_sha256: str | None = None


@dataclass(frozen=True)
class SceneStartEvidence:
    manifest_path: Path
    manifest_sha256: str
    gate_path: Path
    gate_sha256: str
    authorization_path: Path
    authorization_sha256: str
    start_frame_path: Path
    start_frame_sha256: str
    project_id: str
    video_id: str
    media_id: str
    gate_verdict: str
    gate_face_count: int
    gate_cosine: float
    gate_pass_cosine_threshold: float
    gate_hard_fail_cosine_threshold: float
    gate_verifier: str


@dataclass(frozen=True)
class ProbeAuthorizationEvidence:
    """Exact local files that authorize the selected charged probe."""

    bound_files: tuple[tuple[str, Path, str], ...]


@dataclass(frozen=True)
class ValidatedRun:
    config: RunConfig
    pack: dict[str, Any]
    shot: dict[str, Any]
    anchor_path: Path
    pack_sha256: str
    positive_prompt: str
    negative_prompt: str
    flow_prompt: str
    scene_start: SceneStartEvidence | None
    probe_authorization: ProbeAuthorizationEvidence


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_bound_file(path_ref: Any, label: str) -> Path:
    raw = _required_string(path_ref, label)
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ProbeValidationError(f"{label} escapes the repository") from exc
    if not resolved.is_file():
        raise ProbeValidationError(f"{label} does not exist: {resolved}")
    return resolved


def _validate_probe_authorization(
    pack: dict[str, Any],
    *,
    pack_path: Path,
    pack_sha256: str,
) -> ProbeAuthorizationEvidence:
    """Bind originality, lineage, and the current adapter PASS generation."""

    if pack.get("adapter_version") != EXPECTED_ADAPTER_VERSION:
        raise ProbeValidationError(
            "charged camera probes require exact adapter_version "
            f"{EXPECTED_ADAPTER_VERSION!r}; legacy packs are recovery-only"
        )

    evidence = pack.get("originality_gate")
    if not isinstance(evidence, dict):
        raise ProbeValidationError("pack.originality_gate must be a bound PASS object")
    if evidence.get("verdict") != "PASS":
        raise ProbeValidationError("pack.originality_gate verdict must be PASS")

    request_path = _repo_bound_file(
        evidence.get("request_path"),
        "pack.originality_gate.request_path",
    )
    receipt_path = _repo_bound_file(
        evidence.get("receipt_path"),
        "pack.originality_gate.receipt_path",
    )
    ledger_path = _repo_bound_file(
        evidence.get("ledger_path"),
        "pack.originality_gate.ledger_path",
    )
    if _sha256_path(request_path) != evidence.get("request_sha256"):
        raise ProbeValidationError("originality request SHA mismatch")
    if _sha256_path(receipt_path) != evidence.get("receipt_sha256"):
        raise ProbeValidationError("originality receipt SHA mismatch")

    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeValidationError(
            "originality request or receipt is unreadable"
        ) from exc
    if not isinstance(request, dict) or not isinstance(receipt, dict):
        raise ProbeValidationError("originality request and receipt must be objects")
    try:
        signature_digest = originality_signature_sha256(request.get("signature_axes"))
    except OriginalityGateError as exc:
        raise ProbeValidationError(f"originality signature is invalid: {exc}") from exc
    if signature_digest != evidence.get("signature_sha256"):
        raise ProbeValidationError(
            "originality signature does not match runtime binding"
        )

    creative_seed = pack.get("creative_seed_id")
    request_description = _required_string(
        request.get("description"),
        "originality request.description",
    )
    description_normalized = originality_normalize_text(request_description)
    description_digest = originality_description_sha256(description_normalized)
    parent_seed = request.get("parent_seed_id")
    expected_kind = "root" if parent_seed is None else "child"
    expected = {
        "schema_version": "wr3.originality-receipt.v1",
        "verdict": "PASS",
        "seed_id": creative_seed,
        "parent_seed_id": parent_seed,
        "registration_kind": expected_kind,
        "signature_sha256": signature_digest,
        "description_sha256": description_digest,
    }
    if request.get("schema_version") != "wr3.originality-request.v1":
        raise ProbeValidationError("unsupported originality request schema")
    if request.get("seed_id") != creative_seed:
        raise ProbeValidationError(
            "originality request seed does not match runtime pack"
        )
    for key, expected_value in expected.items():
        if receipt.get(key) != expected_value:
            raise ProbeValidationError(f"originality receipt {key} mismatch")
    if receipt.get("status") not in {"RECORDED", "IDEMPOTENT_REPLAY"}:
        raise ProbeValidationError("originality receipt is not durable")
    if evidence.get("registration_kind") != expected_kind:
        raise ProbeValidationError("runtime originality registration kind mismatch")
    if evidence.get("description_sha256") != description_digest:
        raise ProbeValidationError("runtime originality description SHA mismatch")

    try:
        records = read_validated_ledger(ledger_path)
    except OriginalityGateError as exc:
        raise ProbeValidationError(f"originality ledger invalid: {exc}") from exc
    matches = [
        record
        for record in records
        if record["seed_id"] == creative_seed
        and record["parent_seed_id"] == parent_seed
        and record["registration_kind"] == expected_kind
        and record["signature_sha256"] == signature_digest
    ]
    if len(matches) != 1 or matches[0]["sequence"] != receipt.get("sequence"):
        raise ProbeValidationError("originality ledger does not bind this runtime seed")
    if matches[0]["description_normalized"] != description_normalized:
        raise ProbeValidationError("originality ledger description mismatch")
    registration_count = evidence.get("ledger_record_count_at_registration")
    if (
        isinstance(registration_count, bool)
        or not isinstance(registration_count, int)
        or registration_count < matches[0]["sequence"]
        or len(records) < registration_count
    ):
        raise ProbeValidationError("originality ledger record count is inconsistent")
    try:
        prefix_sha = validated_ledger_prefix_sha256(
            ledger_path,
            registration_count,
        )
    except OriginalityGateError as exc:
        raise ProbeValidationError(
            f"originality ledger registration prefix invalid: {exc}"
        ) from exc
    if prefix_sha != evidence.get("ledger_sha256_at_registration"):
        raise ProbeValidationError("originality ledger registration SHA mismatch")

    family_id = _required_string(pack.get("family_id"), "pack.family_id")
    episode_id = _required_string(pack.get("episode_id"), "pack.episode_id")
    lineage_path = pack_path.parent / "lineage-receipt.json"
    verdict_path = pack_path.parent.parent / "probe-gate-verdict.json"
    lineage, lineage_sha256 = _read_json_object_with_sha(
        lineage_path,
        "probe lineage receipt",
    )
    verdict, verdict_sha256 = _read_json_object_with_sha(
        verdict_path,
        "probe gate verdict",
    )

    if lineage.get("schema_version") != EXPECTED_LINEAGE_SCHEMA:
        raise ProbeValidationError(
            f"probe lineage schema must be {EXPECTED_LINEAGE_SCHEMA!r}"
        )
    if lineage.get("adapter_version") != EXPECTED_ADAPTER_VERSION:
        raise ProbeValidationError("probe lineage adapter version mismatch")
    if lineage.get("family_id") != family_id:
        raise ProbeValidationError("probe lineage family_id mismatch")
    if lineage.get("creative_seed_id") != creative_seed:
        raise ProbeValidationError("probe lineage creative seed mismatch")
    if lineage.get("runtime_episode_id") != episode_id:
        raise ProbeValidationError("probe lineage episode mismatch")
    expected_runtime_ref = f"{family_id}/shot-pack.json"
    if lineage.get("runtime_pack") != expected_runtime_ref:
        raise ProbeValidationError("probe lineage runtime-pack path mismatch")
    if lineage.get("runtime_pack_sha256") != pack_sha256:
        raise ProbeValidationError("probe lineage runtime-pack SHA mismatch")
    if lineage.get("originality_gate") != evidence:
        raise ProbeValidationError("probe lineage originality binding mismatch")

    if verdict.get("schema_version") != EXPECTED_VERDICT_SCHEMA:
        raise ProbeValidationError(
            f"probe gate schema must be {EXPECTED_VERDICT_SCHEMA!r}"
        )
    if verdict.get("adapter_version") != EXPECTED_ADAPTER_VERSION:
        raise ProbeValidationError("probe gate adapter version mismatch")
    if verdict.get("verdict") != "PASS":
        raise ProbeValidationError("current probe gate verdict must be exactly PASS")
    checks = verdict.get("checks")
    if not isinstance(checks, dict):
        raise ProbeValidationError("probe gate checks must be an object")
    authorization_check = checks.get("authorization")
    originality_check = checks.get("originality")
    if (
        not isinstance(authorization_check, dict)
        or authorization_check.get("passed") is not True
    ):
        raise ProbeValidationError("current probe authorization check is not PASS")
    if (
        not isinstance(originality_check, dict)
        or originality_check.get("passed") is not True
    ):
        raise ProbeValidationError("current probe originality check is not PASS")
    if originality_check.get("signature_sha256") != signature_digest:
        raise ProbeValidationError("probe gate originality signature mismatch")

    families = verdict.get("families")
    if not isinstance(families, list):
        raise ProbeValidationError("probe gate families must be an array")
    matching_families = [
        item
        for item in families
        if isinstance(item, dict) and item.get("family_id") == family_id
    ]
    if len(matching_families) != 1:
        raise ProbeValidationError(
            "current probe gate must bind exactly one selected family"
        )
    family_summary = matching_families[0]
    expected_family_values = {
        "episode_id": episode_id,
        "runtime_pack_sha256": pack_sha256,
        "shot_count": len(pack.get("shots", [])),
    }
    for field, expected_value in expected_family_values.items():
        if family_summary.get(field) != expected_value:
            raise ProbeValidationError(
                f"probe gate family {field} does not match selected runtime pack"
            )

    bound_paths = (
        ("runtime pack", pack_path, pack_sha256),
        ("originality request", request_path, _sha256_path(request_path)),
        ("originality receipt", receipt_path, _sha256_path(receipt_path)),
        ("originality ledger", ledger_path, _sha256_path(ledger_path)),
        ("lineage receipt", lineage_path, lineage_sha256),
        ("probe gate verdict", verdict_path, verdict_sha256),
    )
    return ProbeAuthorizationEvidence(bound_files=bound_paths)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Durably replace one JSON object without exposing partial bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
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
        directory = os.open(
            path.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def _exclusive_run_lock(episode_dir: Path) -> Iterator[None]:
    """Hold one persistent, nonblocking destination lock for the whole run.

    The lock file deliberately remains on disk after release. Removing it would
    create a rename/unlink race where another process could lock a different
    inode for the same destination. ``validate_run`` ignores this file and only
    treats durable run state (receipt, context, or clip) as a resubmit blocker.
    """

    resolved_episode_dir = episode_dir.expanduser().resolve()
    try:
        resolved_episode_dir.mkdir(parents=True, exist_ok=True)
        handle = (resolved_episode_dir / RUN_LOCK_NAME).open("a+b")
    except OSError as exc:
        raise ProbeValidationError(
            f"camera-probe run lock cannot be opened: {resolved_episode_dir}: {exc}"
        ) from exc

    acquired = False
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise ProbeValidationError(
                    "camera-probe run already in progress for destination: "
                    f"{resolved_episode_dir}"
                ) from exc
            raise ProbeValidationError(
                f"camera-probe run lock failed: {resolved_episode_dir}: {exc}"
            ) from exc
        yield
    finally:
        if acquired:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProbeValidationError(f"{label} must be a non-empty string")
    return value.strip()


def _validate_flowkit_endpoint(endpoint: str) -> str:
    """Accept only the local FlowKit gateway, never an arbitrary HTTP target."""

    raw = _required_string(endpoint, "endpoint")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ProbeValidationError(
            "endpoint must be a valid loopback FlowKit URL"
        ) from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in FLOWKIT_ALLOWED_HOSTS
        or port != FLOWKIT_ALLOWED_PORT
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ProbeValidationError(
            "endpoint must be exactly the loopback FlowKit gateway on port 8100 "
            "with no credentials, path, query, or fragment"
        )
    return raw.rstrip("/")


def _required_canonical_uuid(value: Any, label: str) -> str:
    raw = _required_string(value, label)
    try:
        parsed = UUID(raw)
    except (ValueError, AttributeError) as exc:
        raise ProbeValidationError(f"{label} must be a canonical UUID") from exc
    canonical = str(parsed)
    if raw.lower() != canonical:
        raise ProbeValidationError(f"{label} must be a canonical UUID")
    return canonical


def _required_sha256(value: Any, label: str) -> str:
    raw = _required_string(value, label).lower()
    if len(raw) != 64 or any(character not in "0123456789abcdef" for character in raw):
        raise ProbeValidationError(f"{label} must be a 64-character SHA-256")
    return raw


def _read_json_object_with_sha(
    path: Path,
    label: str,
) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeValidationError(f"{label} unreadable: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProbeValidationError(f"{label} must be a JSON object")
    return payload, _sha256_bytes(raw)


def _required_finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProbeValidationError(f"{label} must be a finite JSON number")
    result = float(value)
    if not math.isfinite(result):
        raise ProbeValidationError(f"{label} must be a finite JSON number")
    return result


def _validate_scene_start_evidence(
    config: RunConfig,
    *,
    episode_id: str,
    runtime_pack_sha256: str,
    variant_id: str,
    shot_id: str,
    global_probe_id: str,
) -> SceneStartEvidence | None:
    """Bind an existing Flow context to one externally pinned PASS decision."""
    context_values = (
        config.existing_project_id,
        config.existing_video_id,
        config.scene_start_media_id,
    )
    supplied_count = sum(value is not None for value in context_values)
    if supplied_count not in (0, 3):
        raise ProbeValidationError(
            "existing_project_id, existing_video_id, and scene_start_media_id "
            "must be supplied together"
        )
    if supplied_count == 0:
        if any(
            value is not None
            for value in (
                config.scene_start_manifest,
                config.scene_start_authorization,
                config.scene_start_authorization_sha256,
            )
        ):
            raise ProbeValidationError(
                "scene-start evidence is only valid with all three existing-context IDs"
            )
        return None

    project_id = _required_canonical_uuid(
        config.existing_project_id,
        "existing_project_id",
    )
    video_id = _required_canonical_uuid(
        config.existing_video_id,
        "existing_video_id",
    )
    media_id = _required_canonical_uuid(
        config.scene_start_media_id,
        "scene_start_media_id",
    )
    if config.scene_start_manifest is None:
        raise ProbeValidationError(
            "scene_start_manifest is required with an existing Flow context"
        )
    if config.scene_start_authorization is None:
        raise ProbeValidationError(
            "scene_start_authorization is required with an existing Flow context"
        )
    if config.scene_start_authorization_sha256 is None:
        raise ProbeValidationError(
            "scene_start_authorization_sha256 is required with an existing Flow context"
        )
    expected_authorization_sha256 = _required_sha256(
        config.scene_start_authorization_sha256,
        "scene_start_authorization_sha256",
    )

    manifest_path = config.scene_start_manifest.expanduser().resolve()
    manifest, manifest_sha256 = _read_json_object_with_sha(
        manifest_path,
        "scene-start manifest",
    )
    if manifest.get("schema_version") != SCENE_START_MANIFEST_SCHEMA:
        raise ProbeValidationError(
            f"scene-start manifest schema must be {SCENE_START_MANIFEST_SCHEMA!r}"
        )
    run_id = _required_string(manifest.get("run_id"), "scene-start manifest.run_id")
    if manifest.get("episode_id") != episode_id:
        raise ProbeValidationError(
            "scene-start manifest episode_id does not match runtime pack"
        )

    project = manifest.get("project")
    if not isinstance(project, dict):
        raise ProbeValidationError("scene-start manifest.project must be an object")
    manifest_project_id = _required_canonical_uuid(
        project.get("id"),
        "scene-start manifest.project.id",
    )
    if manifest_project_id != project_id:
        raise ProbeValidationError(
            "scene-start project lineage does not match existing_project_id"
        )
    manifest_video_id = _required_canonical_uuid(
        project.get("video_id"),
        "scene-start manifest.project.video_id",
    )
    if manifest_video_id != video_id:
        raise ProbeValidationError(
            "scene-start video lineage does not match existing_video_id"
        )

    start_frame = manifest.get("start_frame")
    if not isinstance(start_frame, dict):
        raise ProbeValidationError("scene-start manifest.start_frame must be an object")
    if start_frame.get("role") != "scene_composition_i2v_start_frame":
        raise ProbeValidationError(
            "scene-start manifest.start_frame role is not an approved I2V start frame"
        )
    frame_project_id = _required_canonical_uuid(
        start_frame.get("project_id"),
        "scene-start manifest.start_frame.project_id",
    )
    if frame_project_id != project_id:
        raise ProbeValidationError(
            "scene-start project lineage does not match existing_project_id"
        )
    frame_media_id = _required_canonical_uuid(
        start_frame.get("media_id"),
        "scene-start manifest.start_frame.media_id",
    )
    if frame_media_id != media_id:
        raise ProbeValidationError(
            "scene-start media lineage does not match scene_start_media_id"
        )
    frame_path_raw = _required_string(
        start_frame.get("path"),
        "scene-start manifest.start_frame.path",
    )
    frame_path = Path(frame_path_raw).expanduser()
    if not frame_path.is_absolute():
        raise ProbeValidationError("scene-start frame path must be absolute")
    frame_path = frame_path.resolve()
    if not frame_path.is_file():
        raise ProbeValidationError(f"scene-start frame does not exist: {frame_path}")
    manifest_sha = _required_sha256(
        start_frame.get("sha256"),
        "scene-start manifest.start_frame.sha256",
    )
    actual_sha = _sha256_path(frame_path)
    if actual_sha != manifest_sha:
        raise ProbeValidationError(
            "scene-start file SHA does not match manifest: "
            f"expected={manifest_sha} actual={actual_sha}"
        )

    counts = manifest.get("generation_counts")
    if not isinstance(counts, dict):
        raise ProbeValidationError(
            "scene-start manifest.generation_counts must be an object"
        )
    if counts.get("image_generation_count") != 1:
        raise ProbeValidationError(
            "scene-start image_generation_count must be exactly 1"
        )
    if counts.get("video_generation_count") != 0:
        raise ProbeValidationError(
            "scene-start video_generation_count must be exactly 0"
        )

    gate_link = manifest.get("identity_gate")
    if not isinstance(gate_link, dict):
        raise ProbeValidationError(
            "scene-start manifest.identity_gate must be an object"
        )
    gate_path_raw = _required_string(
        gate_link.get("result_path"),
        "scene-start manifest.identity_gate.result_path",
    )
    gate_path = Path(gate_path_raw).expanduser()
    if not gate_path.is_absolute():
        raise ProbeValidationError("scene-start identity gate path must be absolute")
    gate_path = gate_path.resolve()
    gate, gate_sha256 = _read_json_object_with_sha(
        gate_path,
        "scene-start identity gate",
    )
    if gate.get("schema_version") != SCENE_START_GATE_SCHEMA:
        raise ProbeValidationError(
            f"scene-start identity gate schema must be {SCENE_START_GATE_SCHEMA!r}"
        )
    if gate.get("verdict") != "PASS":
        raise ProbeValidationError(
            "scene-start identity gate verdict must be exactly 'PASS'"
        )
    if gate.get("mock_mode") is not False:
        raise ProbeValidationError(
            "scene-start identity gate must declare mock_mode=false"
        )
    if gate.get("run_id") != run_id or gate.get("episode_id") != episode_id:
        raise ProbeValidationError(
            "scene-start identity gate run/episode lineage does not match manifest"
        )
    gate_project_id = _required_canonical_uuid(
        gate.get("project_id"),
        "scene-start identity gate.project_id",
    )
    if gate_project_id != project_id:
        raise ProbeValidationError(
            "scene-start identity gate project lineage does not match existing_project_id"
        )
    gate_frame_raw = _required_string(
        gate.get("start_frame_path"),
        "scene-start identity gate.start_frame_path",
    )
    if Path(gate_frame_raw).expanduser().resolve() != frame_path:
        raise ProbeValidationError(
            "scene-start identity gate frame path does not match manifest"
        )
    gate_sha = _required_sha256(
        gate.get("start_frame_sha256"),
        "scene-start identity gate.start_frame_sha256",
    )
    if gate_sha != actual_sha:
        raise ProbeValidationError(
            "scene-start gate image SHA does not match the supplied start frame"
        )
    face_count = gate.get("face_count")
    cosine = _required_finite_number(
        gate.get("cosine"),
        "scene-start identity gate.cosine",
    )
    pass_threshold = _required_finite_number(
        gate.get("pass_cosine_threshold"),
        "scene-start identity gate.pass_cosine_threshold",
    )
    hard_fail_threshold = _required_finite_number(
        gate.get("hard_fail_cosine_threshold"),
        "scene-start identity gate.hard_fail_cosine_threshold",
    )
    if not MIN_PASS_COSINE_THRESHOLD <= pass_threshold <= 1.0:
        raise ProbeValidationError(
            "scene-start PASS threshold must be in [0.600, 1.000]"
        )
    if not 0.0 <= hard_fail_threshold < pass_threshold:
        raise ProbeValidationError(
            "scene-start hard-fail threshold must be non-negative and below PASS threshold"
        )
    if (
        not isinstance(face_count, int)
        or isinstance(face_count, bool)
        or face_count != 1
        or not -1.0 <= cosine <= 1.0
        or cosine < pass_threshold
    ):
        raise ProbeValidationError(
            "scene-start PASS gate must contain exactly one face and cosine at or above "
            "its bound PASS threshold"
        )
    verifier = _required_string(
        gate.get("verifier"),
        "scene-start identity gate.verifier",
    )
    measurement = gate.get("measurement")
    if not isinstance(measurement, dict):
        raise ProbeValidationError(
            "scene-start identity gate.measurement must be an object"
        )
    if measurement.get("mock_mode") is not False:
        raise ProbeValidationError(
            "scene-start identity measurement must declare mock_mode=false"
        )
    if measurement.get("image_sha256") != actual_sha:
        raise ProbeValidationError(
            "scene-start identity measurement image SHA does not match the supplied frame"
        )
    measurement_face_count = measurement.get("face_count")
    if (
        not isinstance(measurement_face_count, int)
        or isinstance(measurement_face_count, bool)
        or measurement_face_count != face_count
    ):
        raise ProbeValidationError(
            "scene-start identity measurement face_count disagrees with gate decision"
        )
    measurement_cosine = _required_finite_number(
        measurement.get("cosine"),
        "scene-start identity gate.measurement.cosine",
    )
    if measurement_cosine != cosine:
        raise ProbeValidationError(
            "scene-start identity measurement cosine disagrees with gate decision"
        )
    if measurement.get("verifier") != verifier:
        raise ProbeValidationError(
            "scene-start identity measurement verifier disagrees with gate decision"
        )
    if gate.get("image_generation_count") != 1:
        raise ProbeValidationError(
            "scene-start identity gate image_generation_count must be exactly 1"
        )
    if gate.get("video_generation_count") != 0:
        raise ProbeValidationError(
            "scene-start identity gate video_generation_count must be exactly 0"
        )

    authorization_path = config.scene_start_authorization.expanduser().resolve()
    authorization, authorization_sha256 = _read_json_object_with_sha(
        authorization_path,
        "scene-start video authorization",
    )
    if authorization_sha256 != expected_authorization_sha256:
        raise ProbeValidationError(
            "scene-start authorization SHA does not match the externally pinned value: "
            f"expected={expected_authorization_sha256} actual={authorization_sha256}"
        )
    if authorization.get("schema_version") != SCENE_START_AUTHORIZATION_SCHEMA:
        raise ProbeValidationError(
            "scene-start authorization schema must be "
            f"{SCENE_START_AUTHORIZATION_SCHEMA!r}"
        )
    _required_canonical_uuid(
        authorization.get("authorization_id"),
        "scene-start authorization.authorization_id",
    )
    if authorization.get("authorization_scope") != SCENE_START_AUTHORIZATION_SCOPE:
        raise ProbeValidationError(
            "scene-start authorization scope must be exactly "
            f"{SCENE_START_AUTHORIZATION_SCOPE!r}"
        )
    expected_authorization_values = {
        "run_id": run_id,
        "episode_id": episode_id,
        "runtime_pack_sha256": runtime_pack_sha256,
        "variant_id": variant_id,
        "shot_id": shot_id,
        "global_probe_id": global_probe_id,
        "project_id": project_id,
        "video_id": video_id,
        "media_id": media_id,
    }
    for field, expected in expected_authorization_values.items():
        if authorization.get(field) != expected:
            raise ProbeValidationError(
                f"scene-start authorization {field} does not match the selected run"
            )

    bindings = authorization.get("bindings")
    if not isinstance(bindings, dict):
        raise ProbeValidationError(
            "scene-start authorization.bindings must be an object"
        )
    expected_binding_paths = {
        "manifest_path": manifest_path,
        "identity_gate_path": gate_path,
        "start_frame_path": frame_path,
    }
    for field, expected_path in expected_binding_paths.items():
        raw_path = _required_string(
            bindings.get(field),
            f"scene-start authorization.bindings.{field}",
        )
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute() or candidate.resolve() != expected_path:
            raise ProbeValidationError(
                f"scene-start authorization {field} does not match validated evidence"
            )
    expected_binding_hashes = {
        "manifest_sha256": manifest_sha256,
        "identity_gate_sha256": gate_sha256,
        "start_frame_sha256": actual_sha,
    }
    for field, expected_hash in expected_binding_hashes.items():
        bound_hash = _required_sha256(
            bindings.get(field),
            f"scene-start authorization.bindings.{field}",
        )
        if bound_hash != expected_hash:
            raise ProbeValidationError(
                f"scene-start authorization {field} does not match validated evidence"
            )

    decision = authorization.get("identity_decision")
    if not isinstance(decision, dict):
        raise ProbeValidationError(
            "scene-start authorization.identity_decision must be an object"
        )
    for field, expected in {
        "verdict": "PASS",
        "mock_mode": False,
        "verifier": verifier,
    }.items():
        if decision.get(field) != expected:
            raise ProbeValidationError(
                "scene-start authorization identity decision disagrees with gate: "
                f"{field}"
            )
    decision_face_count = decision.get("face_count")
    if (
        not isinstance(decision_face_count, int)
        or isinstance(decision_face_count, bool)
        or decision_face_count != face_count
    ):
        raise ProbeValidationError(
            "scene-start authorization identity decision disagrees with gate: "
            "face_count"
        )
    for field, expected in {
        "cosine": cosine,
        "pass_cosine_threshold": pass_threshold,
        "hard_fail_cosine_threshold": hard_fail_threshold,
    }.items():
        authorized_number = _required_finite_number(
            decision.get(field),
            f"scene-start authorization.identity_decision.{field}",
        )
        if authorized_number != expected:
            raise ProbeValidationError(
                "scene-start authorization identity decision disagrees with gate: "
                f"{field}"
            )

    return SceneStartEvidence(
        manifest_path=manifest_path,
        manifest_sha256=manifest_sha256,
        gate_path=gate_path,
        gate_sha256=gate_sha256,
        authorization_path=authorization_path,
        authorization_sha256=authorization_sha256,
        start_frame_path=frame_path,
        start_frame_sha256=actual_sha,
        project_id=project_id,
        video_id=video_id,
        media_id=media_id,
        gate_verdict="PASS",
        gate_face_count=1,
        gate_cosine=cosine,
        gate_pass_cosine_threshold=pass_threshold,
        gate_hard_fail_cosine_threshold=hard_fail_threshold,
        gate_verifier=verifier,
    )


def _assert_scene_start_evidence_unchanged(evidence: SceneStartEvidence) -> None:
    """Reject any gate-chain replacement after the initial local validation."""
    bound_files = (
        ("manifest", evidence.manifest_path, evidence.manifest_sha256),
        ("identity gate", evidence.gate_path, evidence.gate_sha256),
        ("authorization", evidence.authorization_path, evidence.authorization_sha256),
        ("start frame", evidence.start_frame_path, evidence.start_frame_sha256),
    )
    for label, path, expected_sha256 in bound_files:
        try:
            actual_sha256 = _sha256_path(path)
        except OSError as exc:
            raise ProbeValidationError(
                f"scene-start {label} changed after validation: {path}: {exc}"
            ) from exc
        if actual_sha256 != expected_sha256:
            raise ProbeValidationError(
                f"scene-start {label} changed after validation: "
                f"expected={expected_sha256} actual={actual_sha256}"
            )


def _assert_probe_authorization_unchanged(
    evidence: ProbeAuthorizationEvidence,
) -> None:
    """Reject pack, originality, lineage, or verdict replacement pre-spend."""

    for label, path, expected_sha256 in evidence.bound_files:
        try:
            actual_sha256 = _sha256_path(path)
        except OSError as exc:
            raise ProbeValidationError(
                f"probe {label} changed after validation: {path}: {exc}"
            ) from exc
        if actual_sha256 != expected_sha256:
            raise ProbeValidationError(
                f"probe {label} changed after validation: "
                f"expected={expected_sha256} actual={actual_sha256}"
            )


def _compose_flow_prompt(positive_prompt: str, negative_prompt: str) -> str:
    """Use the client's deterministic composer, with a safe local fallback."""
    composer = getattr(fk, "_compose_flow_prompt", None)
    if callable(composer):
        composed = composer(positive_prompt, negative_prompt)
    else:
        negative = negative_prompt.strip()
        composed = positive_prompt
        if negative:
            composed = (
                f"{positive_prompt}\n"
                f"The generated video must avoid {negative.rstrip('.')}."
            )

    if not isinstance(composed, str) or not composed.strip():
        raise ProbeValidationError("composed Flow prompt is blank")
    if negative_prompt and composed.count(negative_prompt.strip()) != 1:
        raise ProbeValidationError(
            "negative prompt must occur exactly once in the composed Flow prompt"
        )
    return composed


def validate_run(config: RunConfig) -> ValidatedRun:
    """Validate the whole local contract before opening any network socket."""
    _validate_flowkit_endpoint(config.endpoint)
    if config.credit_cap < 0:
        raise ProbeValidationError("credit_cap must be non-negative")
    if config.accounted_credits < 0:
        raise ProbeValidationError("accounted_credits must be non-negative")
    if config.measured_clip_cost <= 0:
        raise ProbeValidationError("measured_clip_cost must be positive")
    if config.timeout_s <= 0:
        raise ProbeValidationError("timeout_s must be positive")
    projected = config.accounted_credits + config.measured_clip_cost
    if projected > config.credit_cap:
        raise ProbeValidationError(
            "credit cap exceeded before network: "
            f"accounted={config.accounted_credits} + "
            f"measured_clip_cost={config.measured_clip_cost} = {projected} > "
            f"cap={config.credit_cap}"
        )

    pack_path = config.shot_pack.expanduser().resolve()
    try:
        raw = pack_path.read_bytes()
        pack = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeValidationError(
            f"runtime shot pack unreadable: {pack_path}: {exc}"
        ) from exc
    if not isinstance(pack, dict):
        raise ProbeValidationError("runtime shot pack must be a JSON object")
    if pack.get("schema_version") != EXPECTED_PACK_SCHEMA:
        raise ProbeValidationError(
            f"runtime shot pack schema must be {EXPECTED_PACK_SCHEMA!r}"
        )

    pack_sha256 = _sha256_bytes(raw)
    episode_id = _required_string(pack.get("episode_id"), "pack.episode_id")
    family_id = _required_string(pack.get("family_id"), "pack.family_id")
    _required_string(pack.get("creative_seed_id"), "pack.creative_seed_id")
    probe_authorization = _validate_probe_authorization(
        pack,
        pack_path=pack_path,
        pack_sha256=pack_sha256,
    )
    if pack.get("identity_token") != "A007":
        raise ProbeValidationError("pack.identity_token must be exactly 'A007'")
    if pack.get("aspect_ratio") != "9:16" or pack.get("resolution") != "720x1280":
        raise ProbeValidationError("runtime pack must be portrait 9:16 at 720x1280")

    shots = pack.get("shots")
    if not isinstance(shots, list) or len(shots) != 4:
        raise ProbeValidationError(
            "derived family pack must contain exactly four variants"
        )
    selected = [
        shot
        for shot in shots
        if isinstance(shot, dict) and shot.get("variant_id") == config.variant_id
    ]
    if len(selected) != 1:
        raise ProbeValidationError(
            f"variant_id {config.variant_id!r} must select exactly one shot; "
            f"matched {len(selected)}"
        )
    shot = selected[0]
    if shot.get("family_id") != family_id:
        raise ProbeValidationError("selected shot family_id does not match its pack")
    if shot.get("identity_tokens") != ["A007"]:
        raise ProbeValidationError(
            "selected shot identity_tokens must be exactly ['A007']"
        )
    for key in (
        "shot_id",
        "global_probe_id",
        "variant_seed_id",
        "creative_seed_id",
    ):
        _required_string(shot.get(key), f"shot.{key}")
    if shot.get("creative_seed_id") != pack.get("creative_seed_id"):
        raise ProbeValidationError(
            "selected shot creative_seed_id does not match its pack"
        )
    shot_index = shot.get("index")
    if (
        isinstance(shot_index, bool)
        or not isinstance(shot_index, int)
        or shot_index <= 0
    ):
        raise ProbeValidationError("shot.index must be a positive integer")
    if shot.get("duration_s") != 8:
        raise ProbeValidationError("camera probe duration_s must be exactly 8")
    if shot.get("aspect") != "9:16" or shot.get("resolution") != "720x1280":
        raise ProbeValidationError("selected shot must be portrait 9:16 at 720x1280")

    positive = _required_string(
        shot.get("positive_prompt", shot.get("prompt_positive")),
        "shot.positive_prompt",
    )
    negative = _required_string(
        shot.get("negative_prompt", shot.get("prompt_negative")),
        "shot.negative_prompt",
    )
    if shot.get("prompt_positive") not in (None, positive):
        raise ProbeValidationError("positive prompt aliases disagree")
    if shot.get("prompt_negative") not in (None, negative):
        raise ProbeValidationError("negative prompt aliases disagree")
    positive_word_count = len(positive.split())
    if positive_word_count > MAX_POSITIVE_PROMPT_WORDS:
        raise ProbeValidationError(
            "positive prompt exceeds the Tier-1 dialect cap before network: "
            f"{positive_word_count}>{MAX_POSITIVE_PROMPT_WORDS} words"
        )
    flow_prompt = _compose_flow_prompt(positive, negative)

    anchor_raw = _required_string(
        pack.get("anchor_image_path"), "pack.anchor_image_path"
    )
    anchor_path = Path(anchor_raw).expanduser().resolve()
    if not anchor_path.is_file():
        raise ProbeValidationError(f"A007 anchor does not exist: {anchor_path}")
    anchor_expected_sha = _required_string(
        pack.get("anchor_sha256"), "pack.anchor_sha256"
    )
    anchor_actual_sha = _sha256_path(anchor_path)
    if anchor_actual_sha != anchor_expected_sha:
        raise ProbeValidationError(
            "A007 anchor SHA-256 mismatch: "
            f"expected={anchor_expected_sha} actual={anchor_actual_sha}"
        )

    scene_start = _validate_scene_start_evidence(
        config,
        episode_id=episode_id,
        runtime_pack_sha256=pack_sha256,
        variant_id=config.variant_id,
        shot_id=shot["shot_id"],
        global_probe_id=shot["global_probe_id"],
    )

    episode_dir = config.episode_dir.expanduser().resolve()
    receipt_path = episode_dir / RECEIPT_NAME
    context_path = episode_dir / CONTEXT_NAME
    clip_path = episode_dir / "clips" / f"{shot_index:02d}.mp4"
    blockers = [
        path for path in (receipt_path, context_path, clip_path) if path.exists()
    ]
    if blockers:
        joined = ", ".join(str(path) for path in blockers)
        raise ProbeValidationError(
            "one-shot destination already contains run state; retrieval must be "
            f"recovered from the existing receipt, never resubmitted: {joined}"
        )

    # Force evaluation so a malformed episode id/family cannot hide behind
    # later network failures.  These locals make the validation intent clear.
    assert episode_id and family_id
    return ValidatedRun(
        config=config,
        pack=pack,
        shot=shot,
        anchor_path=anchor_path,
        pack_sha256=pack_sha256,
        positive_prompt=positive,
        negative_prompt=negative,
        flow_prompt=flow_prompt,
        scene_start=scene_start,
        probe_authorization=probe_authorization,
    )


def _extract_extension_connected(health: dict[str, Any]) -> bool:
    data = health.get("data")
    nested = data if isinstance(data, dict) else {}
    return (
        health.get("extension_connected") is True
        or nested.get("extension_connected") is True
    )


def _health_is_ready(health: dict[str, Any]) -> bool:
    data = health.get("data")
    nested = data if isinstance(data, dict) else {}
    statuses = (health.get("status"), nested.get("status"))
    explicit_ok = health.get("ok") is True or nested.get("ok") is True
    healthy_status = any(
        isinstance(status, str) and status.strip().lower() in {"ok", "healthy"}
        for status in statuses
    )
    return (explicit_ok or healthy_status) and _extract_extension_connected(health)


def _extract_live_credits(payload: dict[str, Any]) -> int:
    candidates = [payload.get("credits")]
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.append(data.get("credits"))
    for value in candidates:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    raise ProbePreflightError(
        f"live credits payload has no non-negative integer: {payload}"
    )


async def _preflight(endpoint: str, *, measured_clip_cost: int) -> int:
    health_url = urljoin(endpoint.rstrip("/") + "/", "health")
    credits_url = urljoin(endpoint.rstrip("/") + "/", "api/flow/credits")
    health = await fk._http_get_json(health_url, timeout_s=30)
    if (
        not isinstance(health, dict)
        or health.get("detail")
        or not _health_is_ready(health)
    ):
        raise ProbePreflightError(
            f"FlowKit health/extension preflight failed: {health}"
        )
    credits_payload = await fk._http_get_json(credits_url, timeout_s=30)
    if not isinstance(credits_payload, dict) or credits_payload.get("detail"):
        raise ProbePreflightError(
            f"FlowKit live-credit preflight failed: {credits_payload}"
        )
    credits = _extract_live_credits(credits_payload)
    if credits < measured_clip_cost:
        raise ProbePreflightError(
            f"insufficient live credits: have={credits}, need={measured_clip_cost}"
        )
    return credits


async def _live_credits(endpoint: str) -> int:
    url = urljoin(endpoint.rstrip("/") + "/", "api/flow/credits")
    payload = await fk._http_get_json(url, timeout_s=30)
    if not isinstance(payload, dict) or payload.get("detail"):
        raise ProbePreflightError(f"post-run live-credit read failed: {payload}")
    return _extract_live_credits(payload)


def _base_receipt(validated: ValidatedRun, *, credits_before: int) -> dict[str, Any]:
    pack = validated.pack
    shot = validated.shot
    config = validated.config
    projected = config.accounted_credits + config.measured_clip_cost
    source: dict[str, Any] = {
        "runtime_pack": str(config.shot_pack.expanduser().resolve()),
        "runtime_pack_sha256": validated.pack_sha256,
        "episode_id": pack["episode_id"],
        "family_id": pack["family_id"],
        "creative_seed_id": pack["creative_seed_id"],
        "originality_gate": pack.get("originality_gate"),
        "variant_id": shot["variant_id"],
        "variant_seed_id": shot["variant_seed_id"],
        "shot_id": shot["shot_id"],
        "global_probe_id": shot["global_probe_id"],
        "shot_index": shot["index"],
        "anchor_image_path": str(validated.anchor_path),
        "anchor_sha256": pack["anchor_sha256"],
        "scene_start_manifest": None,
        "scene_start_manifest_sha256": None,
        "scene_start_gate": None,
        "scene_start_gate_sha256": None,
        "scene_start_gate_verdict": None,
        "scene_start_gate_verifier": None,
        "scene_start_gate_face_count": None,
        "scene_start_gate_cosine": None,
        "scene_start_gate_pass_cosine_threshold": None,
        "scene_start_gate_hard_fail_cosine_threshold": None,
        "scene_start_authorization": None,
        "scene_start_authorization_sha256": None,
        "scene_start_image_sha256": None,
    }
    if validated.scene_start is not None:
        source.update(
            {
                "scene_start_manifest": str(validated.scene_start.manifest_path),
                "scene_start_manifest_sha256": validated.scene_start.manifest_sha256,
                "scene_start_gate": str(validated.scene_start.gate_path),
                "scene_start_gate_sha256": validated.scene_start.gate_sha256,
                "scene_start_gate_verdict": validated.scene_start.gate_verdict,
                "scene_start_gate_verifier": validated.scene_start.gate_verifier,
                "scene_start_gate_face_count": validated.scene_start.gate_face_count,
                "scene_start_gate_cosine": validated.scene_start.gate_cosine,
                "scene_start_gate_pass_cosine_threshold": (
                    validated.scene_start.gate_pass_cosine_threshold
                ),
                "scene_start_gate_hard_fail_cosine_threshold": (
                    validated.scene_start.gate_hard_fail_cosine_threshold
                ),
                "scene_start_authorization": str(
                    validated.scene_start.authorization_path
                ),
                "scene_start_authorization_sha256": (
                    validated.scene_start.authorization_sha256
                ),
                "scene_start_image_sha256": validated.scene_start.start_frame_sha256,
            }
        )

    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "runner_version": RUNNER_VERSION,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "generation_status": "pending",
        "retrieval_status": "not_started",
        "source": source,
        "prompt_hashes": {
            "positive_sha256": _sha256_bytes(validated.positive_prompt.encode("utf-8")),
            "negative_sha256": _sha256_bytes(validated.negative_prompt.encode("utf-8")),
            "flow_prompt_sha256": _sha256_bytes(validated.flow_prompt.encode("utf-8")),
        },
        "flow": {
            "endpoint": config.endpoint,
            "paygate": config.paygate,
            "context_mode": (
                "existing_scene_start"
                if validated.scene_start is not None
                else "fresh_anchor_start"
            ),
            "project_id": None,
            "video_id": None,
            "scene_id": None,
            "anchor_media_id": None,
            "start_image_media_id": None,
            "workflow_id": None,
            "media_id": None,
            "generate_call_count": 0,
            "download_call_count": 0,
        },
        "credits": {
            "cap": config.credit_cap,
            "accounted_before": config.accounted_credits,
            "measured_clip_cost": config.measured_clip_cost,
            # Historical field name retained for receipt compatibility. The
            # value is supplied by the operator/paygate contract; it is not a
            # workflow-specific measurement returned by Flow.
            "declared_clip_cost": config.measured_clip_cost,
            "clip_cost_source": "operator_supplied_paygate_parameter",
            "projected_accounted_after": projected,
            "live_before": credits_before,
            "live_before_observed_at": _utc_now(),
            "live_after_generation": None,
            "live_after_generation_observed_at": None,
            "live_balance_delta_after_generation_observed": None,
            "live_after_generation_observation_error": None,
            "live_after": None,
            # Backward-compatible arithmetic field. This compares two global
            # account snapshots and is not attribution to this one workflow.
            "live_delta": None,
            "live_balance_delta_observed": None,
            "live_delta_scope": LIVE_DELTA_SCOPE,
            "live_delta_is_exact_workflow_cost": False,
        },
        "artifact": {
            "mp4_path": str(
                config.episode_dir.expanduser().resolve()
                / "clips"
                / f"{shot['index']:02d}.mp4"
            ),
            "bytes": None,
            "sha256": None,
        },
        "error": None,
    }


async def _run_one_locked(config: RunConfig) -> dict[str, Any]:
    """Execute one charged generation and one retrieval call under the run lock."""
    validated = validate_run(config)
    _assert_probe_authorization_unchanged(validated.probe_authorization)
    if validated.scene_start is not None:
        _assert_scene_start_evidence_unchanged(validated.scene_start)
    credits_before = await _preflight(
        config.endpoint,
        measured_clip_cost=config.measured_clip_cost,
    )
    _assert_probe_authorization_unchanged(validated.probe_authorization)
    if validated.scene_start is not None:
        # Health/credit reads are non-mutating, but the local authorization
        # chain must still be identical before any remote scene or spend call.
        _assert_scene_start_evidence_unchanged(validated.scene_start)
    receipt = _base_receipt(validated, credits_before=credits_before)
    episode_dir = config.episode_dir.expanduser().resolve()
    receipt_path = episode_dir / RECEIPT_NAME
    context_path = episode_dir / CONTEXT_NAME
    shot = validated.shot

    if validated.scene_start is None:
        ctx = await fk.setup_episode_context(
            name=validated.pack["episode_id"],
            endpoint=config.endpoint,
            paygate=config.paygate,
            timeout_s=30,
        )
        ctx.anchor_image_path = str(validated.anchor_path)
    else:
        # Reuse the exact project/video that owns the generated start frame.
        # Deliberately leave anchor_image_path/media_id unset so no branch can
        # upload or substitute raw A007 as the I2V start image.
        ctx = fk.EpisodeContext(
            project_id=validated.scene_start.project_id,
            video_id=validated.scene_start.video_id,
            project_name=validated.pack["episode_id"],
            endpoint=config.endpoint,
            paygate=config.paygate,
        )
    receipt["flow"]["project_id"] = ctx.project_id
    receipt["flow"]["video_id"] = ctx.video_id

    # The selected context is durable before scene/upload/generation. Persist
    # again after scene creation so its ID is recoverable before any spend.
    _write_json_atomic(context_path, ctx.to_dict())

    scene_id = await fk._create_scene(
        ctx,
        shot_index=shot["index"],
        positive_prompt=validated.positive_prompt,
        timeout_s=30,
    )
    receipt["flow"]["scene_id"] = scene_id
    _write_json_atomic(context_path, ctx.to_dict())

    if validated.scene_start is None:
        start_image_media_id = await fk._upload_image_asset(
            ctx,
            image_path=validated.anchor_path,
            timeout_s=60,
        )
        ctx.anchor_media_id = start_image_media_id
        receipt["flow"]["anchor_media_id"] = start_image_media_id
    else:
        start_image_media_id = validated.scene_start.media_id
    receipt["flow"]["start_image_media_id"] = start_image_media_id

    if validated.scene_start is not None:
        # Re-check at the last possible instant before the sole charged call.
        _assert_scene_start_evidence_unchanged(validated.scene_start)
    # The creative and adapter authorization chain receives the same final
    # TOCTOU check as the identity gate immediately before the paid call.
    _assert_probe_authorization_unchanged(validated.probe_authorization)

    try:
        # This is the sole generation call in the entire runner.  There is no
        # loop and no exception path that returns here.
        workflow_id, media_id = await fk._generate_video(
            ctx,
            start_image_media_id=start_image_media_id,
            scene_id=scene_id,
            prompt=validated.flow_prompt,
            timeout_s=min(config.timeout_s, 180),
            shot_index=shot["index"],
            clip_cost_cr=config.measured_clip_cost,
        )
    except Exception as exc:
        receipt["generation_status"] = "failed"
        receipt["retrieval_status"] = "not_started"
        receipt["error"] = {"type": type(exc).__name__, "message": str(exc)}
        receipt["updated_at"] = _utc_now()
        _write_json_atomic(receipt_path, receipt)
        raise

    receipt["flow"]["workflow_id"] = workflow_id
    receipt["flow"]["media_id"] = media_id
    receipt["flow"]["generate_call_count"] = 1
    receipt["generation_status"] = "successful"
    receipt["retrieval_status"] = "pending"
    receipt["updated_at"] = _utc_now()
    # Critical ordering: charged IDs are durable before retrieval starts.
    _write_json_atomic(receipt_path, receipt)

    # Observe the global account balance immediately after the charged call,
    # before retrieval latency can widen the attribution window. This remains
    # an account-wide observation, never a claim that Flow returned the exact
    # cost of this workflow.
    try:
        credits_after_generation = await _live_credits(config.endpoint)
    except Exception as exc:
        receipt["credits"]["live_after_generation_observation_error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
    else:
        receipt["credits"]["live_after_generation"] = credits_after_generation
        receipt["credits"]["live_after_generation_observed_at"] = _utc_now()
        receipt["credits"]["live_balance_delta_after_generation_observed"] = (
            credits_before - credits_after_generation
        )
    receipt["updated_at"] = _utc_now()
    _write_json_atomic(receipt_path, receipt)

    # The first retrieval and every later recovery use one write-ahead protocol:
    # exact charged IDs and the initial receipt SHA are bound before network,
    # bytes land at deterministic staging, and only a validated MP4 is atomically
    # published. This removes the former crash window where the primary runner
    # could leave an unbound final MP4 that recovery had to reject.
    initial_recovery_receipt_sha256 = _sha256_path(receipt_path)
    try:
        return await probe_recovery.recover_one(
            probe_recovery.RecoveryConfig(
                receipt=receipt_path,
                expected_initial_receipt_sha256=(initial_recovery_receipt_sha256),
                timeout_s=min(config.timeout_s, 240),
                poll_interval_s=min(10, max(0, config.timeout_s // 10)),
            )
        )
    except probe_recovery.ProbeDownloadRecoveryError as exc:
        raise ProbeRetrievalError(
            "generation succeeded but retrieval failed; use receipt IDs and the "
            "bound recovery authorization to resume, and do not resubmit"
        ) from exc
    except probe_recovery.ProbeCreditReadError as exc:
        raise ProbeRetrievalError(
            "generation succeeded and the MP4 was recovered, but credit "
            "finalization failed; resume the bound recovery and do not resubmit"
        ) from exc
    except probe_recovery.ReceiptValidationError as exc:
        raise ProbeRetrievalError(
            "generation succeeded but crash-safe retrieval authorization failed; "
            "preserve the receipt and do not resubmit"
        ) from exc


async def run_one(config: RunConfig) -> dict[str, Any]:
    """Execute exactly one probe while exclusively owning its destination.

    Lock acquisition precedes local validation, so a concurrent invocation is
    rejected before health checks or any other FlowKit/client call. The same
    lock remains held through generation, retrieval, and the final receipt
    write, closing the prior absence-check time-of-check/time-of-use gap.
    """

    with _exclusive_run_lock(config.episode_dir):
        return await _run_one_locked(config)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate and retrieve exactly one approved WR3 camera probe",
    )
    parser.add_argument("--shot-pack", type=Path, required=True)
    parser.add_argument("--variant-id", required=True)
    parser.add_argument("--episode-dir", type=Path, required=True)
    parser.add_argument("--endpoint", default=fk.DEFAULT_ENDPOINT)
    parser.add_argument("--paygate", default=DEFAULT_PAYGATE)
    parser.add_argument("--credit-cap", type=int, required=True)
    parser.add_argument("--accounted-credits", type=int, required=True)
    parser.add_argument("--measured-clip-cost", type=int, required=True)
    parser.add_argument("--timeout-s", type=int, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--existing-project-id", default=None)
    parser.add_argument("--existing-video-id", default=None)
    parser.add_argument("--scene-start-media-id", default=None)
    parser.add_argument("--scene-start-manifest", type=Path, default=None)
    parser.add_argument("--scene-start-authorization", type=Path, default=None)
    parser.add_argument("--scene-start-authorization-sha256", default=None)
    return parser


async def _async_main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = RunConfig(
        shot_pack=args.shot_pack,
        variant_id=args.variant_id,
        episode_dir=args.episode_dir,
        endpoint=args.endpoint,
        paygate=args.paygate,
        credit_cap=args.credit_cap,
        accounted_credits=args.accounted_credits,
        measured_clip_cost=args.measured_clip_cost,
        timeout_s=args.timeout_s,
        existing_project_id=args.existing_project_id,
        existing_video_id=args.existing_video_id,
        scene_start_media_id=args.scene_start_media_id,
        scene_start_manifest=args.scene_start_manifest,
        scene_start_authorization=args.scene_start_authorization,
        scene_start_authorization_sha256=args.scene_start_authorization_sha256,
    )
    try:
        receipt = await run_one(config)
    except ProbeValidationError as exc:
        print(json.dumps({"ok": False, "stage": "validation", "error": str(exc)}))
        return 2
    except ProbePreflightError as exc:
        print(json.dumps({"ok": False, "stage": "preflight", "error": str(exc)}))
        return 3
    except ProbeRetrievalError as exc:
        print(json.dumps({"ok": False, "stage": "retrieval", "error": str(exc)}))
        return 6
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": "generation",
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
