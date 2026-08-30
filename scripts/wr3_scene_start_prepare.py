#!/usr/bin/env python3
"""Prepare one scene-first WR3 start frame from a project-scoped identity anchor.

This helper deliberately stops before video generation.  Its only paid action
is one ``POST /api/flow/generate-image`` request whose
``character_media_ids`` contains the A007 media already uploaded to the same
fresh Flow project and, optionally, one ordered A002 identity reference.  The
generated scene image, not either raw identity portrait, can then be supplied
explicitly to ``wr3_flowkit_client.submit_clip``.

Safety properties:

* dry-run is the default; ``--real-run`` is required to open a socket;
* all local inputs are validated before spend authorization or networking;
* an append-only reservation prevents the same ``run_id`` being submitted
  twice, including after a download or quality-gate failure;
* there is no retry loop: one process can invoke the image submitter once;
* the post-submit receipt is flushed before the CDN download begins;
* signed CDN URLs are never persisted;
* normalization is center cover-crop plus resize only.  Padding, mirrored
  edges, blurred fills, and synthetic extensions are not implemented;
* the manifest keeps identity-anchor lineage separate from the generated
  i2v start frame.

Expected context JSON (all fields are fail-closed)::

    {
      "schema_version": "wr3.scene-start-context.v1",
      "episode_id": "s01e13-residency-permit-probes-f01-v03",
      "project": {
        "id": "flow-project-uuid",
        "video_id": "flow-video-uuid",
        "name": "s01e13-scene-start-v03",
        "fresh_for_run": true,
        "endpoint": "http://127.0.0.1:8100",
        "paygate": "PAYGATE_TIER_TIER1P5"
      },
      "anchor_lineage": {
        "role": "identity_reference_only",
        "project_id": "flow-project-uuid",
        "media_id": "uploaded-a007-media-uuid",
        "path": "/absolute/path/to/a007.png",
        "sha256": "..."
      },
      "additional_identity_references": [
        {
          "reference_token": "A002",
          "role": "identity_reference_only",
          "project_id": "flow-project-uuid",
          "media_id": "uploaded-a002-media-uuid",
          "path": "/absolute/path/to/a002.png",
          "sha256": "..."
        }
      ]
    }

The ``fresh_for_run`` value is an operator assertion, not a remote freshness
check.  It is retained in the manifest with that epistemic label.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import re
import sys
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image

from wr3_flowkit_client import (
    _check_quota,
    _http_post_json,
)
from wr3_spend_authority import assert_spend_authorized


CONTEXT_SCHEMA = "wr3.scene-start-context.v1"
MANIFEST_SCHEMA = "wr3.scene-start-manifest.v1"
RECEIPT_SCHEMA = "wr3.scene-start-receipt.v1"
IDENTITY_GATE_SCHEMA = "wr3.scene-start-identity-gate.v1"
PORTRAIT_ASPECT = "IMAGE_ASPECT_RATIO_PORTRAIT"
DEFAULT_WIDTH = 720
DEFAULT_HEIGHT = 1280
IDENTITY_PASS_COSINE = 0.600
IDENTITY_HARD_FAIL_COSINE = 0.550
PRIMARY_IDENTITY_REFERENCE_TOKEN = "A007"
SECONDARY_IDENTITY_REFERENCE_TOKEN = "A002"
MAX_IDENTITY_REFERENCE_COUNT = 2
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})
_FLOWKIT_PORT = 8100
_FLOW_IMAGE_PRIMARY_HOST = "flow-content.google"
_FLOW_IMAGE_HOST_SUFFIX = ".googleusercontent.com"
_FLOW_IMAGE_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_FLOW_IMAGE_MAX_REDIRECTS = 3
_FLOW_IMAGE_MAX_BYTES = 32 * 1024 * 1024
_FLOW_IMAGE_MAX_PIXELS = 40_000_000
_FLOW_IMAGE_MAX_DIMENSION = 16_384
_FLOW_IMAGE_MIME_BY_FORMAT = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
DEFAULT_ARCFACE_ANCHOR = Path(
    os.environ.get(
        "WR3_ARCFACE_ANCHOR",
        str(
            Path.home()
            / "nuzantara/research/marketing/zantara-visual-dataset/v1/ingredients/"
            "zantara-anchor-A007.embedding.npy"
        ),
    )
)

SubmitImage = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
DownloadImage = Callable[[str], Awaitable[bytes]]
AuthorizeSpend = Callable[..., Any]


class SceneStartError(RuntimeError):
    """Base error for scene-first start-frame preparation."""


class SceneStartPreflightError(SceneStartError):
    """Local input or retrieved-raster validation failed."""


class SceneStartDuplicateRunError(SceneStartError):
    """The append-only receipt already contains this run id."""


@dataclass(frozen=True)
class ProjectScope:
    project_id: str
    video_id: str
    project_name: str
    endpoint: str
    paygate: str
    fresh_for_run: bool


@dataclass(frozen=True)
class AnchorLineage:
    project_id: str
    media_id: str
    path: Path
    sha256: str
    role: str = "identity_reference_only"
    reference_token: str = PRIMARY_IDENTITY_REFERENCE_TOKEN


@dataclass(frozen=True)
class SceneStartContext:
    episode_id: str
    project: ProjectScope
    anchor: AnchorLineage
    additional_identity_references: tuple[AnchorLineage, ...] = ()


@dataclass(frozen=True)
class SceneStartConfig:
    run_id: str
    context: SceneStartContext
    prompt: str
    destination: Path
    source_destination: Path
    manifest_path: Path
    receipt_path: Path
    shot_index: int
    real_run: bool = False
    target_width: int = DEFAULT_WIDTH
    target_height: int = DEFAULT_HEIGHT
    timeout_s: int = 180


@dataclass(frozen=True)
class RasterResult:
    png_bytes: bytes
    raw_sha256: str
    start_frame_sha256: str
    source_width: int
    source_height: int
    target_width: int
    target_height: int
    normalization: str
    crop_box: tuple[int, int, int, int]
    had_alpha: bool
    alpha_min: int | None
    black_edge_fractions: dict[str, float]
    seam_indicator: dict[str, Any]

    def report(self) -> dict[str, Any]:
        return {
            "valid_raster": True,
            "raw_sha256": self.raw_sha256,
            "start_frame_sha256": self.start_frame_sha256,
            "source_dimensions": [self.source_width, self.source_height],
            "target_dimensions": [self.target_width, self.target_height],
            "exact_9_16": self.target_width * 16 == self.target_height * 9,
            "normalization": self.normalization,
            "crop_box": list(self.crop_box),
            "fill_method": None,
            "had_alpha": self.had_alpha,
            "alpha_min": self.alpha_min,
            "black_edge_fractions": self.black_edge_fractions,
            "seam_indicator": self.seam_indicator,
        }


@dataclass(frozen=True)
class ParsedImageResponse:
    """Minimal, URL-bearing response data kept in memory only.

    ``download_url`` must never be serialized to the receipt or manifest.  A
    missing dimension pair is not a parse failure: the already-returned asset
    is downloaded once and its raster header becomes the dimension authority.
    """

    media_id: str
    download_url: str
    model: str
    seed: int
    reported_dimensions: tuple[int, int] | None


_MEDIA_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9._:-]{0,100}$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_string(data: Mapping[str, Any], key: str, *, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SceneStartPreflightError(f"{where}.{key} must be a non-empty string")
    return value.strip()


def _parse_identity_reference(
    raw: Mapping[str, Any],
    *,
    where: str,
    project_id: str,
    expected_reference_token: str,
    token_required: bool,
) -> AnchorLineage:
    lineage_project_id = _required_string(raw, "project_id", where=where)
    if lineage_project_id != project_id:
        raise SceneStartPreflightError(
            f"{where}.project_id must equal project.id; Flow media is project-scoped"
        )
    role = _required_string(raw, "role", where=where)
    if role != "identity_reference_only":
        raise SceneStartPreflightError(
            f"{where}.role must be 'identity_reference_only'"
        )
    token_raw = raw.get("reference_token")
    if token_raw is None and not token_required:
        reference_token = expected_reference_token
    else:
        reference_token = _required_string(raw, "reference_token", where=where)
    if reference_token != expected_reference_token:
        raise SceneStartPreflightError(
            f"{where}.reference_token must be {expected_reference_token!r}"
        )
    return AnchorLineage(
        project_id=lineage_project_id,
        media_id=_required_string(raw, "media_id", where=where),
        path=Path(_required_string(raw, "path", where=where)).expanduser(),
        sha256=_required_string(raw, "sha256", where=where).lower(),
        role=role,
        reference_token=reference_token,
    )


def _identity_references(context: SceneStartContext) -> tuple[AnchorLineage, ...]:
    additional = context.additional_identity_references
    if not isinstance(additional, tuple):
        raise SceneStartPreflightError(
            "additional_identity_references must be an ordered tuple"
        )
    if not all(isinstance(item, AnchorLineage) for item in additional):
        raise SceneStartPreflightError(
            "additional_identity_references must contain AnchorLineage values"
        )
    return (context.anchor, *additional)


def _identity_reference_record(lineage: AnchorLineage) -> dict[str, Any]:
    return {
        "reference_token": lineage.reference_token,
        "role": lineage.role,
        "project_id": lineage.project_id,
        "media_id": lineage.media_id,
        "path": str(lineage.path),
        "sha256": lineage.sha256,
    }


def _identity_reference_records(context: SceneStartContext) -> list[dict[str, Any]]:
    return [_identity_reference_record(item) for item in _identity_references(context)]


def _character_media_ids(context: SceneStartContext) -> list[str]:
    return [item.media_id for item in _identity_references(context)]


def _validate_identity_reference_lineages(context: SceneStartContext) -> None:
    """Validate ordered identity lineage, including local content identity."""
    references = _identity_references(context)
    if len(references) > MAX_IDENTITY_REFERENCE_COUNT:
        raise SceneStartPreflightError(
            f"no more than {MAX_IDENTITY_REFERENCE_COUNT} identity references are allowed"
        )
    expected_tokens = (
        PRIMARY_IDENTITY_REFERENCE_TOKEN,
        SECONDARY_IDENTITY_REFERENCE_TOKEN,
    )
    media_ids: set[str] = set()
    sha256_values: set[str] = set()
    for index, lineage in enumerate(references):
        where = (
            "anchor_lineage"
            if index == 0
            else f"additional_identity_references[{index - 1}]"
        )
        if lineage.reference_token != expected_tokens[index]:
            raise SceneStartPreflightError(
                f"{where}.reference_token must be {expected_tokens[index]!r}"
            )
        if lineage.project_id != context.project.project_id:
            raise SceneStartPreflightError(
                f"{where}.project_id must equal project.id; Flow media is "
                "project-scoped"
            )
        if lineage.role != "identity_reference_only":
            raise SceneStartPreflightError(
                f"{where}.role must be 'identity_reference_only'"
            )
        if not lineage.media_id.strip():
            raise SceneStartPreflightError(f"{where}.media_id must be non-empty")
        if lineage.media_id in media_ids:
            raise SceneStartPreflightError(
                "identity reference media_id values must be unique"
            )
        media_ids.add(lineage.media_id)
        if not _SHA256_RE.fullmatch(lineage.sha256):
            raise SceneStartPreflightError(
                f"{where}.sha256 must be 64 lowercase hex characters"
            )
        if lineage.sha256 in sha256_values:
            raise SceneStartPreflightError(
                "identity reference sha256 values must be unique"
            )
        sha256_values.add(lineage.sha256)
        if not lineage.path.is_absolute() or not lineage.path.is_file():
            raise SceneStartPreflightError(
                f"{where}.path must be an existing absolute file: {lineage.path}"
            )
        if _sha256_file(lineage.path) != lineage.sha256:
            raise SceneStartPreflightError(
                f"{where}.sha256 mismatch; refusing an unverified identity reference"
            )


def load_context(path: Path) -> SceneStartContext:
    """Load the strict project/anchor lineage contract from JSON."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SceneStartPreflightError(
            f"cannot read context JSON {path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise SceneStartPreflightError("context JSON root must be an object")
    if raw.get("schema_version") != CONTEXT_SCHEMA:
        raise SceneStartPreflightError(
            f"context schema_version must be {CONTEXT_SCHEMA!r}"
        )

    project_raw = raw.get("project")
    anchor_raw = raw.get("anchor_lineage")
    if not isinstance(project_raw, dict) or not isinstance(anchor_raw, dict):
        raise SceneStartPreflightError(
            "context requires project and anchor_lineage objects"
        )

    project_id = _required_string(project_raw, "id", where="project")
    if project_raw.get("fresh_for_run") is not True:
        raise SceneStartPreflightError(
            "project.fresh_for_run must be true (operator freshness assertion)"
        )
    project = ProjectScope(
        project_id=project_id,
        video_id=_required_string(project_raw, "video_id", where="project"),
        project_name=_required_string(project_raw, "name", where="project"),
        endpoint=_required_string(project_raw, "endpoint", where="project"),
        paygate=_required_string(project_raw, "paygate", where="project"),
        fresh_for_run=True,
    )
    _validate_flowkit_endpoint(project.endpoint)
    anchor = _parse_identity_reference(
        anchor_raw,
        where="anchor_lineage",
        project_id=project_id,
        expected_reference_token=PRIMARY_IDENTITY_REFERENCE_TOKEN,
        token_required=False,
    )
    additional_raw = raw.get("additional_identity_references", [])
    if not isinstance(additional_raw, list):
        raise SceneStartPreflightError(
            "additional_identity_references must be an ordered array"
        )
    if len(additional_raw) > 1:
        raise SceneStartPreflightError(
            "additional_identity_references may contain at most one A002 reference"
        )
    additional: list[AnchorLineage] = []
    for index, value in enumerate(additional_raw):
        where = f"additional_identity_references[{index}]"
        if not isinstance(value, dict):
            raise SceneStartPreflightError(f"{where} must be an object")
        additional.append(
            _parse_identity_reference(
                value,
                where=where,
                project_id=project_id,
                expected_reference_token=SECONDARY_IDENTITY_REFERENCE_TOKEN,
                token_required=True,
            )
        )
    context = SceneStartContext(
        episode_id=_required_string(raw, "episode_id", where="context"),
        project=project,
        anchor=anchor,
        additional_identity_references=tuple(additional),
    )
    _validate_identity_reference_lineages(context)
    return context


def _receipt_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("JSONL event is not an object")
                events.append(value)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SceneStartPreflightError(
            f"receipt {path} is not valid append-only JSONL at line "
            f"{locals().get('line_number', '?')}: {exc}"
        ) from exc
    return events


def _append_receipt(path: Path, event: Mapping[str, Any]) -> None:
    """Append and fsync one receipt event; never rewrite earlier events."""
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": RECEIPT_SCHEMA,
        "ts": _now_iso(),
        **dict(event),
    }
    try:
        with path.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        path.chmod(0o600)
    except OSError as exc:
        raise SceneStartError(f"cannot append durable receipt {path}: {exc}") from exc


def _reserve_run(config: SceneStartConfig, payload: Mapping[str, Any]) -> None:
    """Atomically reserve this run id before the one allowed submission."""
    import fcntl

    path = config.receipt_path
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SceneStartPreflightError(
                        f"receipt {path} has malformed JSON at line {line_number}"
                    ) from exc
                if not isinstance(event, dict):
                    raise SceneStartPreflightError(
                        f"receipt {path} line {line_number} is not an object"
                    )
                if event.get("run_id") == config.run_id:
                    raise SceneStartDuplicateRunError(
                        f"run_id {config.run_id!r} is already reserved; no resubmit allowed"
                    )
            reservation = {
                "schema_version": RECEIPT_SCHEMA,
                "ts": _now_iso(),
                "run_id": config.run_id,
                "phase": "submission_reserved",
                "episode_id": config.context.episode_id,
                "project_id": config.context.project.project_id,
                "anchor_media_id": config.context.anchor.media_id,
                "character_media_ids": _character_media_ids(config.context),
                "identity_reference_lineages": _identity_reference_records(
                    config.context
                ),
                "prompt_sha256": _sha256_bytes(config.prompt.encode("utf-8")),
                "request_sha256": _sha256_bytes(
                    json.dumps(payload, sort_keys=True).encode("utf-8")
                ),
            }
            handle.seek(0, os.SEEK_END)
            handle.write(json.dumps(reservation, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        path.chmod(0o600)
    except (SceneStartDuplicateRunError, SceneStartPreflightError):
        raise
    except OSError as exc:
        raise SceneStartError(f"cannot reserve run in receipt {path}: {exc}") from exc


def _validate_local_preflight(config: SceneStartConfig) -> None:
    """Fail before authorization/network if any local contract is unsafe."""
    if not _RUN_ID_RE.fullmatch(config.run_id):
        raise SceneStartPreflightError("run_id must match [A-Za-z0-9._-]+")
    if len(config.prompt.strip()) < 40:
        raise SceneStartPreflightError(
            "prompt must contain at least 40 non-blank characters"
        )
    if config.target_width <= 0 or config.target_height <= 0:
        raise SceneStartPreflightError("target dimensions must be positive")
    if config.target_width * 16 != config.target_height * 9:
        raise SceneStartPreflightError("target dimensions must be exact 9:16")
    if config.timeout_s <= 0:
        raise SceneStartPreflightError("timeout_s must be positive")
    if config.context.project.fresh_for_run is not True:
        raise SceneStartPreflightError(
            "project must be explicitly asserted fresh_for_run=true"
        )
    if not config.context.project.video_id.strip():
        raise SceneStartPreflightError("project.video_id must be a non-empty string")

    _validate_flowkit_endpoint(config.context.project.endpoint)
    _validate_identity_reference_lineages(config.context)

    output_paths = (
        config.destination,
        config.source_destination,
        config.manifest_path,
    )
    if len({path.resolve() for path in (*output_paths, config.receipt_path)}) != 4:
        raise SceneStartPreflightError(
            "destination, source, manifest, and receipt paths must be distinct"
        )
    if config.destination.suffix.lower() != ".png":
        raise SceneStartPreflightError("destination must use a .png suffix")
    for path in output_paths:
        if path.exists():
            raise SceneStartPreflightError(
                f"fresh destination required; path already exists: {path}"
            )
    for event in _receipt_events(config.receipt_path):
        if event.get("run_id") == config.run_id:
            raise SceneStartDuplicateRunError(
                f"run_id {config.run_id!r} already exists; no resubmit allowed"
            )


def build_generate_image_payload(config: SceneStartConfig) -> dict[str, Any]:
    """Build the sole Flow request with ordered, project-scoped identity media."""
    _validate_identity_reference_lineages(config.context)
    return {
        "prompt": config.prompt,
        "project_id": config.context.project.project_id,
        "aspect_ratio": PORTRAIT_ASPECT,
        "user_paygate_tier": config.context.project.paygate,
        "character_media_ids": _character_media_ids(config.context),
    }


class _SingleSubmit:
    """In-process backstop: the wrapped image submitter can run only once."""

    def __init__(self, submitter: SubmitImage) -> None:
        self._submitter = submitter
        self._used = False

    async def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._used:
            raise SceneStartDuplicateRunError(
                "image submitter already used once in this process"
            )
        self._used = True
        return await self._submitter(payload)


async def _network_submit(
    config: SceneStartConfig, payload: dict[str, Any]
) -> dict[str, Any]:
    url = urljoin(
        config.context.project.endpoint.rstrip("/") + "/",
        "api/flow/generate-image",
    )
    try:
        response = await asyncio.wait_for(
            _http_post_json(url, payload, timeout_s=config.timeout_s),
            timeout=config.timeout_s,
        )
    except asyncio.TimeoutError as exc:
        raise SceneStartError(
            "Flow image submission timed out; no retry was attempted"
        ) from exc
    _check_quota(response, where="scene-start generate-image")
    return response


def _validate_flowkit_endpoint(endpoint_value: str) -> None:
    """Allow only the literal local FlowKit HTTP gateway at port 8100."""
    try:
        endpoint = urlparse(endpoint_value)
        port = endpoint.port
    except (TypeError, ValueError) as exc:
        raise SceneStartPreflightError(
            "project.endpoint must be the exact local FlowKit HTTP gateway"
        ) from exc
    if (
        endpoint_value != endpoint_value.strip()
        or any(
            ord(character) <= 32 or ord(character) == 127
            for character in endpoint_value
        )
        or endpoint.scheme != "http"
        or endpoint.hostname not in _LOOPBACK_HOSTS
        or port != _FLOWKIT_PORT
        or endpoint.username is not None
        or endpoint.password is not None
        or endpoint.path not in {"", "/"}
        or bool(endpoint.params)
        or bool(endpoint.query)
        or bool(endpoint.fragment)
    ):
        raise SceneStartPreflightError(
            "project.endpoint must be http loopback 127.0.0.1/::1 on port 8100 "
            "with no credentials, non-root path, query, or fragment"
        )


def _is_allowed_flow_image_url(url: str) -> bool:
    """Return whether ``url`` is an HTTPS Flow image URL safe to request."""
    if (
        not isinstance(url, str)
        or not url
        or len(url) > 8_000
        or any(ord(character) <= 32 or ord(character) == 127 for character in url)
    ):
        return False
    try:
        parsed = urlparse(url)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    hostname = (parsed.hostname or "").lower()
    host_allowed = hostname == _FLOW_IMAGE_PRIMARY_HOST or hostname.endswith(
        _FLOW_IMAGE_HOST_SUFFIX
    )
    return (
        parsed.scheme == "https"
        and host_allowed
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
        and bool(parsed.path)
        and parsed.path.startswith("/")
        and not parsed.path.startswith("//")
        and not parsed.params
        and not parsed.fragment
    )


def _require_allowed_flow_image_url(url: str, *, where: str) -> None:
    if not _is_allowed_flow_image_url(url):
        raise SceneStartPreflightError(
            f"Flow generated-image {where} is outside the approved HTTPS media hosts"
        )


def _declared_content_length(headers: httpx.Headers) -> int | None:
    value = headers.get("content-length")
    if value is None:
        return None
    try:
        length = int(value, 10)
    except ValueError as exc:
        raise SceneStartPreflightError(
            "Flow image response has an invalid Content-Length"
        ) from exc
    if length < 0:
        raise SceneStartPreflightError(
            "Flow image response has an invalid Content-Length"
        )
    return length


def _detected_image_mime(raw_bytes: bytes) -> str | None:
    if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if (
        len(raw_bytes) >= 12
        and raw_bytes.startswith(b"RIFF")
        and raw_bytes[8:12] == b"WEBP"
    ):
        return "image/webp"
    return None


def _validate_downloaded_image_payload(
    raw_bytes: bytes,
    *,
    declared_mime: str | None = None,
) -> None:
    """Validate byte bound, MIME/magic agreement, and a complete raster decode."""
    if not raw_bytes:
        raise SceneStartPreflightError("Flow image download returned zero bytes")
    if len(raw_bytes) > _FLOW_IMAGE_MAX_BYTES:
        raise SceneStartPreflightError("Flow image download exceeds the byte cap")

    detected_mime = _detected_image_mime(raw_bytes)
    if detected_mime is None:
        raise SceneStartPreflightError(
            "Flow image bytes do not have an approved PNG, JPEG, or WebP signature"
        )
    if declared_mime is not None:
        normalized_mime = declared_mime.partition(";")[0].strip().lower()
        if normalized_mime not in _FLOW_IMAGE_MIME_BY_FORMAT.values():
            raise SceneStartPreflightError(
                "Flow image response has an unsupported Content-Type"
            )
        if normalized_mime != detected_mime:
            raise SceneStartPreflightError(
                "Flow image Content-Type does not match its byte signature"
            )

    try:
        with Image.open(io.BytesIO(raw_bytes)) as raster:
            raster_format = raster.format
            width, height = raster.size
            if (
                width <= 0
                or height <= 0
                or width > _FLOW_IMAGE_MAX_DIMENSION
                or height > _FLOW_IMAGE_MAX_DIMENSION
                or width * height > _FLOW_IMAGE_MAX_PIXELS
            ):
                raise SceneStartPreflightError(
                    "Flow image raster dimensions exceed the safety cap"
                )
            if getattr(raster, "n_frames", 1) != 1:
                raise SceneStartPreflightError(
                    "Flow image response must contain exactly one raster frame"
                )
            raster.load()
    except SceneStartPreflightError:
        raise
    except Exception as exc:
        raise SceneStartPreflightError(
            f"Flow image bytes cannot be decoded as a raster: {type(exc).__name__}"
        ) from exc

    pillow_mime = _FLOW_IMAGE_MIME_BY_FORMAT.get(str(raster_format).upper())
    if pillow_mime != detected_mime:
        raise SceneStartPreflightError(
            "Flow image decoder format does not match its byte signature"
        )


async def _download_flow_image_bytes(
    url: str,
    *,
    timeout_s: int,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bytes:
    """Fetch one Flow image with bounded, allowlisted manual redirects."""
    _require_allowed_flow_image_url(url, where="URL")
    timeout = httpx.Timeout(float(timeout_s))
    current_url = url
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            transport=transport,
            trust_env=False,
        ) as client:
            for redirect_count in range(_FLOW_IMAGE_MAX_REDIRECTS + 1):
                _require_allowed_flow_image_url(current_url, where="redirect")
                async with client.stream("GET", current_url) as response:
                    if response.status_code in _FLOW_IMAGE_REDIRECT_STATUSES:
                        if redirect_count >= _FLOW_IMAGE_MAX_REDIRECTS:
                            raise SceneStartPreflightError(
                                "Flow image response exceeded the redirect limit"
                            )
                        location = response.headers.get("location")
                        if not location:
                            raise SceneStartPreflightError(
                                "Flow image redirect has no Location header"
                            )
                        next_url = urljoin(current_url, location)
                        _require_allowed_flow_image_url(next_url, where="redirect")
                        current_url = next_url
                        continue
                    if response.status_code != 200:
                        raise SceneStartError(
                            "Flow image download returned a non-success HTTP status"
                        )

                    declared_length = _declared_content_length(response.headers)
                    if (
                        declared_length is not None
                        and declared_length > _FLOW_IMAGE_MAX_BYTES
                    ):
                        raise SceneStartPreflightError(
                            "Flow image Content-Length exceeds the byte cap"
                        )
                    declared_mime = response.headers.get("content-type")
                    if declared_mime is None:
                        raise SceneStartPreflightError(
                            "Flow image response has no Content-Type"
                        )

                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > _FLOW_IMAGE_MAX_BYTES:
                            raise SceneStartPreflightError(
                                "Flow image download exceeds the byte cap"
                            )
                    result = bytes(body)
                    _validate_downloaded_image_payload(
                        result,
                        declared_mime=declared_mime,
                    )
                    return result
    except (SceneStartError, SceneStartPreflightError):
        raise
    except httpx.TimeoutException as exc:
        raise SceneStartError(
            "start-frame download timed out; no retry was attempted"
        ) from exc
    except httpx.HTTPError as exc:
        raise SceneStartError(
            "start-frame download failed; no retry was attempted"
        ) from exc
    raise SceneStartError("Flow image download ended without a response")


async def _network_download(config: SceneStartConfig, url: str) -> bytes:
    try:
        return await asyncio.wait_for(
            _download_flow_image_bytes(url, timeout_s=config.timeout_s),
            timeout=config.timeout_s,
        )
    except asyncio.TimeoutError as exc:
        raise SceneStartError(
            "start-frame download timed out; no retry was attempted"
        ) from exc


def _response_media_candidate(
    raw_response: Any,
) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    """Return the first media item and generated-image mapping, if present.

    This inspection is deliberately non-throwing so it can produce a bounded
    recovery receipt even when the response later fails strict validation.
    """
    if not isinstance(raw_response, Mapping):
        return None, None
    media = raw_response.get("media")
    if not isinstance(media, list) or not media:
        return None, None
    first = media[0]
    if not isinstance(first, Mapping):
        return None, None
    image = first.get("image")
    if not isinstance(image, Mapping):
        return first, None
    generated = image.get("generatedImage")
    if not isinstance(generated, Mapping):
        return first, None
    return first, generated


def _positive_response_int(value: Any) -> int | None:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
        or value > 1_000_000
    ):
        return None
    return value


def _safe_model_label(value: Any) -> str:
    if isinstance(value, str) and _MODEL_RE.fullmatch(value):
        return value
    return ""


def _bounded_recovery_metadata(raw_response: Any) -> dict[str, Any]:
    """Build fixed-shape recovery evidence without serializing signed URLs.

    No arbitrary response strings or mapping keys are copied.  This makes the
    receipt useful for locating the already-created project asset while
    keeping it bounded and incapable of leaking a signed CDN query string.
    """
    media_count = 0
    if isinstance(raw_response, Mapping):
        media = raw_response.get("media")
        if isinstance(media, list):
            media_count = min(len(media), 1000)
    first, generated = _response_media_candidate(raw_response)
    media_id_raw: Any = None
    download_url_present = False
    model = ""
    seed = 0
    if generated is not None:
        media_id_raw = generated.get("mediaId")
        download_url_present = bool(
            isinstance(generated.get("fifeUrl"), str) and generated.get("fifeUrl")
        )
        model = _safe_model_label(generated.get("modelNameType"))
        seed_raw = generated.get("seed")
        if (
            isinstance(seed_raw, int)
            and not isinstance(seed_raw, bool)
            and -(2**63) <= seed_raw <= 2**63 - 1
        ):
            seed = seed_raw
    if not media_id_raw and first is not None:
        media_id_raw = first.get("name")
    media_id = (
        media_id_raw
        if isinstance(media_id_raw, str) and _MEDIA_ID_RE.fullmatch(media_id_raw)
        else None
    )

    width: int | None = None
    height: int | None = None
    dimensions_present = False
    if first is not None:
        dimensions = first.get("dimensions")
        if isinstance(dimensions, Mapping):
            dimensions_present = True
            width = _positive_response_int(dimensions.get("width"))
            height = _positive_response_int(dimensions.get("height"))
    reported_dimensions = [width, height] if width and height else None
    return {
        "response_is_mapping": isinstance(raw_response, Mapping),
        "media_array_present": bool(
            isinstance(raw_response, Mapping)
            and isinstance(raw_response.get("media"), list)
        ),
        "media_count_capped_at_1000": media_count,
        "first_media_is_mapping": first is not None,
        "generated_image_present": generated is not None,
        "candidate_media_id": media_id,
        "download_url_present": download_url_present,
        "dimensions_object_present": dimensions_present,
        "reported_dimensions": reported_dimensions,
        "dimensions_complete": reported_dimensions is not None,
        "model": model,
        "seed": seed,
        "raw_response_persisted": False,
        "signed_download_url_persisted": False,
    }


def _parse_scene_image_response(raw_response: Any) -> ParsedImageResponse:
    """Parse the returned asset identity; dimensions remain optional.

    The URL is accepted only from the repository's approved Flow media hosts
    and is retained in memory for the one download of this exact returned
    asset.  It is never included in an exception message or durable artifact.
    """
    first, generated = _response_media_candidate(raw_response)
    if first is None or generated is None:
        raise SceneStartPreflightError(
            "Flow response has no generated image media payload"
        )
    media_id_raw = generated.get("mediaId") or first.get("name")
    if not isinstance(media_id_raw, str) or not _MEDIA_ID_RE.fullmatch(media_id_raw):
        raise SceneStartPreflightError(
            "Flow response has no safe non-empty generated-image media id"
        )
    download_url = generated.get("fifeUrl")
    if not isinstance(download_url, str) or not download_url:
        raise SceneStartPreflightError(
            "Flow response has no generated-image download URL"
        )
    _require_allowed_flow_image_url(download_url, where="URL")

    width: int | None = None
    height: int | None = None
    dimensions = first.get("dimensions")
    if isinstance(dimensions, Mapping):
        width = _positive_response_int(dimensions.get("width"))
        height = _positive_response_int(dimensions.get("height"))
    reported_dimensions = (width, height) if width and height else None
    seed_raw = generated.get("seed")
    seed = (
        seed_raw
        if (
            isinstance(seed_raw, int)
            and not isinstance(seed_raw, bool)
            and -(2**63) <= seed_raw <= 2**63 - 1
        )
        else 0
    )
    return ParsedImageResponse(
        media_id=media_id_raw,
        download_url=download_url,
        model=_safe_model_label(generated.get("modelNameType")),
        seed=seed,
        reported_dimensions=reported_dimensions,
    )


def _cover_crop_box(
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> tuple[int, int, int, int]:
    """Return a deterministic centered cover-crop box, never an expansion."""
    if source_width * target_height > source_height * target_width:
        crop_width = max(1, source_height * target_width // target_height)
        left = (source_width - crop_width) // 2
        return (left, 0, left + crop_width, source_height)
    crop_height = max(1, source_width * target_height // target_width)
    top = (source_height - crop_height) // 2
    return (0, top, source_width, top + crop_height)


def _edge_black_fractions(gray: Image.Image) -> dict[str, float]:
    analysis = gray.resize((180, 320), Image.Resampling.BILINEAR)
    width, height = analysis.size
    band_x = max(2, round(width * 0.03))
    band_y = max(2, round(height * 0.03))

    def fraction(box: tuple[int, int, int, int]) -> float:
        crop = analysis.crop(box)
        values = list(crop.get_flattened_data())
        return round(sum(value <= 12 for value in values) / len(values), 6)

    return {
        "top": fraction((0, 0, width, band_y)),
        "bottom": fraction((0, height - band_y, width, height)),
        "left": fraction((0, 0, band_x, height)),
        "right": fraction((width - band_x, 0, width, height)),
    }


def _seam_indicator(gray: Image.Image) -> dict[str, Any]:
    """Find the strongest full-span horizontal or vertical discontinuity."""
    analysis = gray.resize((180, 320), Image.Resampling.BILINEAR)
    width, height = analysis.size
    pixels = list(analysis.get_flattened_data())

    best = {
        "axis": "horizontal",
        "position": 0,
        "mean_abs_delta": 0.0,
        "coherent_fraction": 0.0,
        "suspicious": False,
    }

    def consider(axis: str, position: int, differences: list[int]) -> None:
        nonlocal best
        mean_delta = sum(differences) / len(differences)
        coherent = sum(value >= 30 for value in differences) / len(differences)
        score = mean_delta * coherent
        previous_score = float(best["mean_abs_delta"]) * float(
            best["coherent_fraction"]
        )
        if score > previous_score:
            best = {
                "axis": axis,
                "position": position,
                "mean_abs_delta": round(mean_delta, 6),
                "coherent_fraction": round(coherent, 6),
                "suspicious": mean_delta >= 42.0 and coherent >= 0.72,
            }

    for row in range(max(2, height // 20), min(height - 1, height * 19 // 20)):
        base = row * width
        previous = (row - 1) * width
        consider(
            "horizontal",
            row,
            [abs(pixels[base + col] - pixels[previous + col]) for col in range(width)],
        )
    for column in range(max(2, width // 20), min(width - 1, width * 19 // 20)):
        consider(
            "vertical",
            column,
            [
                abs(pixels[row * width + column] - pixels[row * width + column - 1])
                for row in range(height)
            ],
        )
    return best


def normalize_and_validate_raster(
    raw_bytes: bytes,
    *,
    anchor_sha256: str,
    target_width: int = DEFAULT_WIDTH,
    target_height: int = DEFAULT_HEIGHT,
    expected_source_dimensions: tuple[int, int] | None = None,
    additional_identity_reference_sha256s: tuple[str, ...] = (),
) -> RasterResult:
    """Decode, cover-normalize, and run deterministic artifact indicators."""
    if not raw_bytes:
        raise SceneStartPreflightError("downloaded image is empty")
    raw_sha256 = _sha256_bytes(raw_bytes)
    if raw_sha256 == anchor_sha256:
        raise SceneStartPreflightError(
            "generated asset SHA equals A007 anchor SHA; scene start is not distinct"
        )
    if raw_sha256 in additional_identity_reference_sha256s:
        raise SceneStartPreflightError(
            "generated asset SHA equals an additional identity-reference SHA; "
            "scene start is not distinct"
        )
    try:
        with Image.open(io.BytesIO(raw_bytes)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(raw_bytes)) as source:
            if getattr(source, "n_frames", 1) != 1:
                raise SceneStartPreflightError(
                    "generated start frame must be one raster frame"
                )
            source.load()
            source_width, source_height = source.size
            if source_width <= 0 or source_height <= 0:
                raise SceneStartPreflightError(
                    "generated raster has invalid dimensions"
                )
            if source_width >= source_height:
                raise SceneStartPreflightError(
                    "generated raster must be portrait before normalization"
                )
            if (
                expected_source_dimensions is not None
                and (source_width, source_height) != expected_source_dimensions
            ):
                raise SceneStartPreflightError(
                    "Flow response dimensions "
                    f"{expected_source_dimensions[0]}x{expected_source_dimensions[1]} "
                    "do not match decoded raster dimensions "
                    f"{source_width}x{source_height}"
                )

            had_alpha = "A" in source.getbands() or "transparency" in source.info
            alpha_min: int | None = None
            if had_alpha:
                rgba = source.convert("RGBA")
                alpha_min, _alpha_max = rgba.getchannel("A").getextrema()
                if alpha_min < 255:
                    raise SceneStartPreflightError(
                        "generated raster contains transparent or semi-transparent pixels"
                    )
            rgb = source.convert("RGB")
    except SceneStartPreflightError:
        raise
    except Exception as exc:
        raise SceneStartPreflightError(
            f"downloaded bytes are not a valid raster: {type(exc).__name__}"
        ) from exc

    crop_box = _cover_crop_box(
        source_width,
        source_height,
        target_width,
        target_height,
    )
    full_box = (0, 0, source_width, source_height)
    if crop_box != full_box:
        normalization = "center_cover_crop_resize"
    elif (source_width, source_height) != (target_width, target_height):
        normalization = "resize"
    else:
        normalization = "none"
    normalized = rgb.crop(crop_box)
    if normalized.size != (target_width, target_height):
        normalized = normalized.resize(
            (target_width, target_height),
            Image.Resampling.LANCZOS,
        )

    gray = normalized.convert("L")
    black_edges = _edge_black_fractions(gray)
    suspicious_edges = [
        edge for edge, fraction in black_edges.items() if fraction >= 0.85
    ]
    seam = _seam_indicator(gray)
    failures: list[str] = []
    if suspicious_edges:
        failures.append("near-black border: " + ", ".join(sorted(suspicious_edges)))
    if seam["suspicious"]:
        failures.append(
            f"full-span {seam['axis']} seam near position {seam['position']}"
        )
    if failures:
        raise SceneStartPreflightError("; ".join(failures))

    output = io.BytesIO()
    normalized.save(output, format="PNG", compress_level=6)
    png_bytes = output.getvalue()
    start_frame_sha256 = _sha256_bytes(png_bytes)
    if start_frame_sha256 == anchor_sha256:
        raise SceneStartPreflightError(
            "normalized start-frame SHA equals A007 anchor SHA"
        )
    if start_frame_sha256 in additional_identity_reference_sha256s:
        raise SceneStartPreflightError(
            "normalized start-frame SHA equals an additional identity-reference SHA"
        )
    return RasterResult(
        png_bytes=png_bytes,
        raw_sha256=raw_sha256,
        start_frame_sha256=start_frame_sha256,
        source_width=source_width,
        source_height=source_height,
        target_width=target_width,
        target_height=target_height,
        normalization=normalization,
        crop_box=crop_box,
        had_alpha=had_alpha,
        alpha_min=alpha_min,
        black_edge_fractions=black_edges,
        seam_indicator=seam,
    )


def default_identity_result_path(manifest_path: Path) -> Path:
    """Return the manifest-linked, immutable identity-gate artifact path."""
    return manifest_path.with_name(f"{manifest_path.stem}-identity-gate.json")


def measure_still_identity_real(
    start_frame_path: Path,
    *,
    anchor_embedding_path: Path,
) -> dict[str, Any]:
    """Measure one still with real ArcFace; imports heavy dependencies lazily.

    This function is intentionally not called by image preparation.  The root
    orchestrator invokes it on Pro after reviewing the raster artifact.  A
    missing dependency or embedding fails loud; there is no mock fallback.
    """
    try:
        import cv2  # type: ignore
        import insightface  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise SceneStartError(
            "real still identity check requires insightface, onnxruntime, "
            "opencv-python, and numpy on Pro"
        ) from exc
    if not start_frame_path.is_file():
        raise SceneStartPreflightError(
            f"start frame missing for identity check: {start_frame_path}"
        )
    if not anchor_embedding_path.is_file():
        raise SceneStartPreflightError(
            f"ArcFace anchor embedding missing: {anchor_embedding_path}"
        )
    image = cv2.imread(str(start_frame_path))
    if image is None:
        raise SceneStartPreflightError(
            f"OpenCV could not decode start frame: {start_frame_path}"
        )
    anchor = np.load(anchor_embedding_path)
    norm = float(np.linalg.norm(anchor))
    if norm <= 0.0:
        raise SceneStartPreflightError("ArcFace anchor embedding has zero norm")

    app = insightface.app.FaceAnalysis(name="buffalo_l")
    app.prepare(ctx_id=0, det_size=(640, 640))
    faces = app.get(image)
    face_count = len(faces)
    cosine: float | None = None
    if face_count == 1:
        embedding = faces[0].normed_embedding
        cosine = float(np.dot(anchor / norm, embedding))
    return {
        "mock_mode": False,
        "verifier": "insightface-buffalo_l",
        "detector_size": [640, 640],
        "face_count": face_count,
        "cosine": cosine,
        "image_path": str(start_frame_path),
        "image_sha256": _sha256_file(start_frame_path),
        "anchor_embedding_path": str(anchor_embedding_path),
        "anchor_embedding_sha256": _sha256_file(anchor_embedding_path),
    }


def record_identity_gate_result(
    *,
    manifest_path: Path,
    receipt_path: Path,
    result_path: Path,
    run_id: str,
    measurement: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist a real still-identity verdict without importing InsightFace.

    Tests can supply a deterministic measurement mapping.  Production callers
    should pass the output of :func:`measure_still_identity_real`.  A mock
    result is rejected before any artifact or receipt is written.
    """
    if measurement.get("mock_mode") is not False:
        raise SceneStartPreflightError(
            "identity result must explicitly declare mock_mode=false"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SceneStartPreflightError(
            f"cannot read scene-start manifest {manifest_path}: {exc}"
        ) from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != MANIFEST_SCHEMA
    ):
        raise SceneStartPreflightError(
            "identity gate requires a valid scene-start manifest"
        )
    if manifest.get("run_id") != run_id:
        raise SceneStartPreflightError(
            "identity run_id does not match scene-start manifest"
        )
    counts = manifest.get("generation_counts") or {}
    if counts.get("image_generation_count") != 1:
        raise SceneStartPreflightError(
            "identity gate requires image_generation_count=1"
        )
    if counts.get("video_generation_count") != 0:
        raise SceneStartPreflightError(
            "identity gate requires video_generation_count=0"
        )

    start_frame = manifest.get("start_frame") or {}
    frame_path = Path(str(start_frame.get("path") or ""))
    expected_sha = start_frame.get("sha256")
    if not frame_path.is_absolute() or not frame_path.is_file():
        raise SceneStartPreflightError(
            "manifest start-frame path is not an existing file"
        )
    actual_sha = _sha256_file(frame_path)
    if expected_sha != actual_sha:
        raise SceneStartPreflightError("start-frame SHA no longer matches manifest")
    if measurement.get("image_sha256") != actual_sha:
        raise SceneStartPreflightError(
            "identity measurement image SHA does not match scene-start frame"
        )

    face_count = measurement.get("face_count")
    if (
        not isinstance(face_count, int)
        or isinstance(face_count, bool)
        or face_count < 0
    ):
        raise SceneStartPreflightError(
            "identity face_count must be a non-negative integer"
        )
    cosine_raw = measurement.get("cosine")
    cosine: float | None
    if face_count == 1:
        if not isinstance(cosine_raw, (int, float)) or isinstance(cosine_raw, bool):
            raise SceneStartPreflightError(
                "exactly-one-face identity result requires a numeric cosine"
            )
        cosine = float(cosine_raw)
        if not 0.0 <= cosine <= 1.0:
            raise SceneStartPreflightError("identity cosine must be in [0, 1]")
    else:
        cosine = None

    if face_count == 0:
        verdict = "HARD_FAIL"
        reason = "no face detected"
    elif face_count > 1:
        verdict = "REJECT"
        reason = f"expected exactly one face, detected {face_count}"
    elif cosine is not None and cosine < IDENTITY_HARD_FAIL_COSINE:
        verdict = "HARD_FAIL"
        reason = f"cosine {cosine:.6f} is below 0.550"
    elif cosine is not None and cosine < IDENTITY_PASS_COSINE:
        verdict = "REJECT"
        reason = f"cosine {cosine:.6f} is below 0.600"
    else:
        verdict = "PASS"
        reason = "exactly one face and cosine is at least 0.600"

    result = {
        "schema_version": IDENTITY_GATE_SCHEMA,
        "recorded_at": _now_iso(),
        "run_id": run_id,
        "episode_id": manifest.get("episode_id"),
        "project_id": (manifest.get("project") or {}).get("id"),
        "start_frame_path": str(frame_path),
        "start_frame_sha256": actual_sha,
        "mock_mode": False,
        "verifier": str(measurement.get("verifier") or "unspecified-real-verifier"),
        "face_count": face_count,
        "cosine": cosine,
        "pass_cosine_threshold": IDENTITY_PASS_COSINE,
        "hard_fail_cosine_threshold": IDENTITY_HARD_FAIL_COSINE,
        "verdict": verdict,
        "reason": reason,
        "image_generation_count": 1,
        "video_generation_count": 0,
        "measurement": dict(measurement),
    }
    _write_manifest_exclusive(result_path, result)
    _append_receipt(
        receipt_path,
        {
            "run_id": run_id,
            "phase": "identity_gate_recorded",
            "project_id": result["project_id"],
            "start_frame_sha256": actual_sha,
            "face_count": face_count,
            "cosine": cosine,
            "identity_verdict": verdict,
            "identity_result_path": str(result_path),
            "mock_mode": False,
            "image_generation_count": 1,
            "video_generation_count": 0,
        },
    )
    return result


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise SceneStartError(f"cannot write fresh artifact {path}: {exc}") from exc


def _write_manifest_exclusive(path: Path, manifest: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_exclusive(path, encoded)


async def prepare_scene_start(
    config: SceneStartConfig,
    *,
    submit_image: SubmitImage | None = None,
    download_image: DownloadImage | None = None,
    authorize_spend: AuthorizeSpend = assert_spend_authorized,
) -> dict[str, Any]:
    """Dry-run a plan or execute exactly one scene-start image submission."""
    _validate_local_preflight(config)
    payload = build_generate_image_payload(config)
    prompt_sha256 = _sha256_bytes(config.prompt.encode("utf-8"))
    if not config.real_run:
        return {
            "ok": True,
            "mode": "dry-run",
            "network_calls": 0,
            "run_id": config.run_id,
            "episode_id": config.context.episode_id,
            "request": payload,
            "prompt_sha256": prompt_sha256,
            "anchor_lineage": {
                "role": config.context.anchor.role,
                "project_id": config.context.anchor.project_id,
                "media_id": config.context.anchor.media_id,
                "path": str(config.context.anchor.path),
                "sha256": config.context.anchor.sha256,
            },
            "identity_reference_lineages": _identity_reference_records(config.context),
            "planned_start_frame": {
                "role": "scene_composition_i2v_start_frame",
                "path": str(config.destination),
                "target_dimensions": [config.target_width, config.target_height],
            },
        }

    # Spend authority is checked after every offline condition but before the
    # reservation and, critically, before the first possible socket.
    authorize_spend(episode_id=config.context.episode_id)
    _reserve_run(config, payload)

    if submit_image is None:

        async def submit_image(request: dict[str, Any]) -> dict[str, Any]:
            return await _network_submit(config, request)

    if download_image is None:

        async def download_image(url: str) -> bytes:
            return await _network_download(config, url)

    submit_once = _SingleSubmit(submit_image)

    try:
        raw_response = await submit_once(payload)
    except Exception as exc:
        _append_receipt(
            config.receipt_path,
            {
                "run_id": config.run_id,
                "phase": "submission_failed",
                "project_id": config.context.project.project_id,
                "character_media_ids": _character_media_ids(config.context),
                "error_kind": type(exc).__name__,
                "retry_attempted": False,
            },
        )
        raise SceneStartError(
            "Flow image submission failed; the run remains reserved and was not retried"
        ) from exc

    # Persist a fixed-shape, URL-free recovery breadcrumb before strict parsing
    # or dimension validation.  If downstream validation fails, operators can
    # still locate the one asset Flow already created without resubmitting.
    recovery_metadata = _bounded_recovery_metadata(raw_response)
    _append_receipt(
        config.receipt_path,
        {
            "run_id": config.run_id,
            "phase": "submission_response_received",
            "episode_id": config.context.episode_id,
            "project_id": config.context.project.project_id,
            "character_media_ids": _character_media_ids(config.context),
            "start_frame_media_id": recovery_metadata["candidate_media_id"],
            "recovery_metadata": recovery_metadata,
            "image_generation_count": 1,
            "video_generation_count": 0,
            "retry_attempted": False,
        },
    )

    try:
        parsed = _parse_scene_image_response(raw_response)
        if (
            parsed.reported_dimensions is not None
            and parsed.reported_dimensions[0] >= parsed.reported_dimensions[1]
        ):
            raise SceneStartPreflightError(
                "Flow response dimensions must describe a portrait raster"
            )
    except Exception as exc:
        _append_receipt(
            config.receipt_path,
            {
                "run_id": config.run_id,
                "phase": "submission_response_invalid",
                "project_id": config.context.project.project_id,
                "character_media_ids": _character_media_ids(config.context),
                "start_frame_media_id": recovery_metadata["candidate_media_id"],
                "error_kind": type(exc).__name__,
                "signed_download_url_persisted": False,
                "retry_attempted": False,
            },
        )
        raise SceneStartError(
            "Flow accepted the image call but returned unusable metadata; no retry allowed"
        ) from exc

    media_id = parsed.media_id
    reported_dimensions = parsed.reported_dimensions

    # Durable and deliberately URL-free: this MUST precede any CDN request.
    _append_receipt(
        config.receipt_path,
        {
            "run_id": config.run_id,
            "phase": "image_submitted",
            "episode_id": config.context.episode_id,
            "project_id": config.context.project.project_id,
            "anchor_media_id": config.context.anchor.media_id,
            "character_media_ids": _character_media_ids(config.context),
            "start_frame_media_id": media_id,
            "prompt_sha256": prompt_sha256,
            "model": parsed.model,
            "seed": parsed.seed,
            "reported_dimensions": (
                list(reported_dimensions) if reported_dimensions is not None else None
            ),
            "dimension_source": (
                "response_metadata"
                if reported_dimensions is not None
                else "decoded_raster_pending"
            ),
            "image_generation_count": 1,
            "video_generation_count": 0,
            "cost_status": "pending_external_credit_delta_measurement",
            "cost_measurement_method": "flow_credits_before_after",
            "ledger_write_performed": False,
            "signed_download_url_persisted": False,
            "retry_attempted": False,
        },
    )

    try:
        raw_bytes = await download_image(parsed.download_url)
    except Exception as exc:
        _append_receipt(
            config.receipt_path,
            {
                "run_id": config.run_id,
                "phase": "download_failed",
                "project_id": config.context.project.project_id,
                "character_media_ids": _character_media_ids(config.context),
                "start_frame_media_id": media_id,
                "error_kind": type(exc).__name__,
                "retry_attempted": False,
            },
        )
        raise SceneStartError(
            "start-frame download failed after submission; no retry was attempted"
        ) from exc

    try:
        _validate_downloaded_image_payload(raw_bytes)
        _write_exclusive(config.source_destination, raw_bytes)
        raster = normalize_and_validate_raster(
            raw_bytes,
            anchor_sha256=config.context.anchor.sha256,
            target_width=config.target_width,
            target_height=config.target_height,
            expected_source_dimensions=reported_dimensions,
            additional_identity_reference_sha256s=tuple(
                reference.sha256
                for reference in config.context.additional_identity_references
            ),
        )
    except SceneStartPreflightError as exc:
        _append_receipt(
            config.receipt_path,
            {
                "run_id": config.run_id,
                "phase": "validation_failed",
                "project_id": config.context.project.project_id,
                "character_media_ids": _character_media_ids(config.context),
                "start_frame_media_id": media_id,
                "source_path": str(config.source_destination),
                "source_sha256": _sha256_bytes(raw_bytes),
                "reason": str(exc),
                "retry_attempted": False,
            },
        )
        raise

    _write_exclusive(config.destination, raster.png_bytes)
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "created_at": _now_iso(),
        "run_id": config.run_id,
        "episode_id": config.context.episode_id,
        "project": {
            "id": config.context.project.project_id,
            "video_id": config.context.project.video_id,
            "name": config.context.project.project_name,
            "fresh_for_run": config.context.project.fresh_for_run,
            "freshness_basis": "operator_asserted_in_context",
            "paygate": config.context.project.paygate,
        },
        "anchor_lineage": {
            "role": config.context.anchor.role,
            "project_id": config.context.anchor.project_id,
            "media_id": config.context.anchor.media_id,
            "path": str(config.context.anchor.path),
            "sha256": config.context.anchor.sha256,
        },
        "identity_reference_lineages": _identity_reference_records(config.context),
        "start_frame": {
            "role": "scene_composition_i2v_start_frame",
            "project_id": config.context.project.project_id,
            "media_id": media_id,
            "source_path": str(config.source_destination),
            "path": str(config.destination),
            "sha256": raster.start_frame_sha256,
            **raster.report(),
        },
        "generation_counts": {
            "image_generation_count": 1,
            "video_generation_count": 0,
        },
        "generation": {
            "endpoint_path": "/api/flow/generate-image",
            "aspect_ratio": PORTRAIT_ASPECT,
            "character_media_ids": _character_media_ids(config.context),
            "prompt_sha256": prompt_sha256,
            "reported_dimensions": (
                list(reported_dimensions) if reported_dimensions is not None else None
            ),
            "source_dimension_authority": (
                "response_metadata_verified_against_decoded_raster"
                if reported_dimensions is not None
                else "decoded_raster"
            ),
            "single_submit_cap": 1,
            "submits_made": 1,
            "retries_made": 0,
            "cost_status": "pending_external_credit_delta_measurement",
            "cost_measurement_method": "flow_credits_before_after",
            "ledger_write_performed": False,
            "signed_download_url_persisted": False,
        },
        "identity_gate": {
            "status": "pending_real_arcface",
            "required_face_count": 1,
            "pass_cosine_threshold": IDENTITY_PASS_COSINE,
            "hard_fail_cosine_threshold": IDENTITY_HARD_FAIL_COSINE,
            "mock_allowed": False,
            "result_path": str(default_identity_result_path(config.manifest_path)),
        },
    }
    _write_manifest_exclusive(config.manifest_path, manifest)
    _append_receipt(
        config.receipt_path,
        {
            "run_id": config.run_id,
            "phase": "raster_preflight_completed",
            "project_id": config.context.project.project_id,
            "character_media_ids": _character_media_ids(config.context),
            "start_frame_media_id": media_id,
            "start_frame_sha256": raster.start_frame_sha256,
            "source_dimensions": [raster.source_width, raster.source_height],
            "source_dimension_authority": (
                "response_metadata_verified_against_decoded_raster"
                if reported_dimensions is not None
                else "decoded_raster"
            ),
            "manifest_path": str(config.manifest_path),
            "identity_gate_status": "pending_real_arcface",
            "image_generation_count": 1,
            "video_generation_count": 0,
            "retry_attempted": False,
        },
    )
    return {
        "ok": True,
        "mode": "real",
        "run_id": config.run_id,
        "project_id": config.context.project.project_id,
        "anchor_media_id": config.context.anchor.media_id,
        "character_media_ids": _character_media_ids(config.context),
        "identity_reference_lineages": _identity_reference_records(config.context),
        "start_frame_media_id": media_id,
        "source_path": str(config.source_destination),
        "start_frame_path": str(config.destination),
        "manifest_path": str(config.manifest_path),
        "receipt_path": str(config.receipt_path),
        "quality": raster.report(),
        "identity_gate_status": "pending_real_arcface",
        "identity_result_path": str(default_identity_result_path(config.manifest_path)),
        "image_generation_count": 1,
        "video_generation_count": 0,
        "submits_made": 1,
        "retries_made": 0,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare one project-scoped scene-first WR3 start frame"
    )
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--source-dest", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--shot-index", type=int, required=True)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--real-run",
        action="store_true",
        help="Authorize exactly one Flow image submit; default is network-free dry-run",
    )
    return parser


def _build_identity_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run and persist the real ArcFace gate for a prepared still"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--result", type=Path, default=None)
    parser.add_argument(
        "--anchor-embedding",
        type=Path,
        default=DEFAULT_ARCFACE_ANCHOR,
    )
    return parser


def _config_from_args(args: argparse.Namespace) -> SceneStartConfig:
    context_path = args.context.expanduser().resolve()
    prompt_path = args.prompt_file.expanduser().resolve()
    try:
        prompt = prompt_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SceneStartPreflightError(
            f"cannot read prompt file {prompt_path}: {exc}"
        ) from exc
    destination = args.dest.expanduser().resolve()
    source_destination = (
        args.source_dest.expanduser().resolve()
        if args.source_dest is not None
        else destination.with_name(f"{destination.stem}.source.img")
    )
    return SceneStartConfig(
        run_id=args.run_id,
        context=load_context(context_path),
        prompt=prompt,
        destination=destination,
        source_destination=source_destination,
        manifest_path=args.manifest.expanduser().resolve(),
        receipt_path=args.receipt.expanduser().resolve(),
        shot_index=args.shot_index,
        real_run=args.real_run,
        target_width=args.width,
        target_height=args.height,
        timeout_s=args.timeout,
    )


async def _async_main(argv: list[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if effective_argv and effective_argv[0] == "record-identity":
        identity_args = _build_identity_parser().parse_args(effective_argv[1:])
        manifest_path = identity_args.manifest.expanduser().resolve()
        receipt_path = identity_args.receipt.expanduser().resolve()
        result_path = (
            identity_args.result.expanduser().resolve()
            if identity_args.result is not None
            else default_identity_result_path(manifest_path)
        )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            run_id = str(manifest["run_id"])
            start_frame_path = Path(manifest["start_frame"]["path"])
            measurement = await asyncio.to_thread(
                measure_still_identity_real,
                start_frame_path,
                anchor_embedding_path=identity_args.anchor_embedding.expanduser().resolve(),
            )
            result = record_identity_gate_result(
                manifest_path=manifest_path,
                receipt_path=receipt_path,
                result_path=result_path,
                run_id=run_id,
                measurement=measurement,
            )
        except (SceneStartError, OSError, KeyError, json.JSONDecodeError) as exc:
            sys.stderr.write(
                json.dumps(
                    {
                        "ok": False,
                        "error_kind": type(exc).__name__,
                        "error": str(exc),
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            return 1
        sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
        return 0 if result["verdict"] == "PASS" else 2

    if effective_argv and effective_argv[0] == "prepare":
        effective_argv = effective_argv[1:]
    args = _build_parser().parse_args(effective_argv)
    try:
        result = await prepare_scene_start(_config_from_args(args))
    except SceneStartError as exc:
        sys.stderr.write(
            json.dumps(
                {"ok": False, "error_kind": type(exc).__name__, "error": str(exc)},
                sort_keys=True,
            )
            + "\n"
        )
        return 1
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
