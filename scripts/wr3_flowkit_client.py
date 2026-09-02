#!/usr/bin/env python3
"""WR3 Flow gateway client — Veo 3.1 Fast Tier_ONE clip generation.

Speaks to the live FlowKit gateway API (OpenAPI v1.1.0) running locally on
http://127.0.0.1:8100. Veo API is the SINGLE cloud touchpoint in the WR3 hot
path. All orchestration happens locally (Symbiosis Law 6).

Pipeline per episode (4 steps, all synchronous on portrait fast tier):

  1. setup_episode_context(name)
       → POST /api/projects          → project_id
       → POST /api/videos             → video_id
     Returns EpisodeContext (re-used across all shots).

  2. submit_clip(request, episode_context)
       per shot:
       2a. POST /api/scenes                  → scene_id
       2b. POST /api/flow/generate-image     → start_image media_id (synchronous)
       2c. POST /api/flow/generate-video     → workflow + media (synchronous on
                                                veo_3_1_i2v_s_fast_portrait Tier 1)
       2d. POST /api/flow/check-omni-status → workflow media URL/base64
           (legacy IDs retain GET /api/flow/media/<media_id>)
       2e. base64-decode → write episode_dir/clips/NN.mp4

Settings:
  endpoint        WR3_FLOWKIT_ENDPOINT (default http://127.0.0.1:8100)
  paygate         WR3_FLOWKIT_PAYGATE   (default PAYGATE_TIER_ONE — 20 cr/clip)
  watchdog        300s wall-clock per clip (Symbiosis Law 4 — degrade-loud on timeout)
  retry policy    up to 2 retries with strengthened prompt; 3rd fail → b-roll-curator fallback

Output:
  apps/war-room/output/episode/<slug>/clips/<n>.mp4
  apps/war-room/output/episode/<slug>/_flowkit_context.json  (project_id, video_id, per-shot scenes)
"""

from __future__ import annotations

import asyncio
import base64
import errno
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urljoin, urlsplit

import httpx

from wr3_credit_ledger import CLIP_COST_CR, record_spend
from wr3_placeholder_clip import render_placeholder_clip
from wr3_spend_authority import assert_spend_authorized, zero_spend_enabled

DEFAULT_ENDPOINT = os.environ.get("WR3_FLOWKIT_ENDPOINT", "http://127.0.0.1:8100")
DEFAULT_PAYGATE = os.environ.get("WR3_FLOWKIT_PAYGATE", "PAYGATE_TIER_ONE")
PER_CLIP_TIMEOUT_S = int(os.environ.get("WR3_FLOWKIT_TIMEOUT_S", "300"))
# SSOT is wr3_credit_ledger.CLIP_COST_CR (2026-08-23 fix) — this derives
# from it rather than re-reading WR3_FLOWKIT_CLIP_COST itself, so this
# constant and wr3_gatekeeper_check.py's CR_PER_CLIP can never disagree
# with EACH OTHER again. Same env var, same default — runtime behaviour is
# unchanged. The default (20) is a single empirical observation from
# 2026-05-20 on some paygate tier, NOT a verified cost for the tier this
# client actually requests below (`PAYGATE_TIER_ONE`) — the live gateway's
# traffic is ~81% a DIFFERENT tier (`PAYGATE_TIER_TIER1P5`, measured
# 2026-08-23), and per-clip cost is tier-dependent with no tier→credits
# table anywhere in this codebase. See wr3_credit_ledger.py's module
# docstring for the full measurement. Treat 20 as an unverified default,
# not a known truth.
DEFAULT_CLIP_COST_CR = CLIP_COST_CR
# UNMEASURED PLACEHOLDER — deliberately 0, deliberately an under-count, NOT a
# measurement. We do not yet know how many Flow credits
# /api/flow/generate-image actually consumes per call. Every real-mode ledger
# row for the image charge (source="_generate_start_image") is tagged with
# this constant so the gap stays visible in `wr3_credit_ledger.py report`
# instead of being silently absorbed into DEFAULT_CLIP_COST_CR. Override via
# WR3_FLOWKIT_IMAGE_COST_CR once the real per-call cost is measured.
DEFAULT_IMAGE_COST_CR = int(os.environ.get("WR3_FLOWKIT_IMAGE_COST_CR", "0"))
FLOWKIT_ALLOWED_HOSTS = frozenset({"127.0.0.1", "::1"})
FLOWKIT_ALLOWED_PORT = 8100
FLOW_MEDIA_PRIMARY_HOST = "flow-content.google"
FLOW_MEDIA_HOST_SUFFIX = ".googleusercontent.com"
FLOW_MEDIA_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
FLOW_MEDIA_MAX_REDIRECTS = 3
FLOW_MEDIA_MAX_BYTES = 128 * 1024 * 1024
FLOW_MEDIA_MIME_TYPES = frozenset({"video/mp4", "application/mp4"})
SHOT_RECEIPT_SCHEMA = "wr3.flowkit-shot-receipt.v1"
RENDER_RECEIPT_SCHEMA = "wr3.flowkit-render-receipt.v1"
PROJECT_BINDING_SCHEMA = "wr3.flow-project-binding.v1"
PROJECT_BINDING_POLICY = "one_project_per_episode"

# Backwards-compat alias — older callers passed plan="pro".
DEFAULT_PLAN = DEFAULT_PAYGATE


@dataclass(frozen=True)
class ClipRequest:
    shot_index: int
    positive_prompt: str
    negative_prompt: str = ""
    identity_tokens: tuple[str, ...] = ()  # e.g. ("A007-Zantara-anchor",)
    duration_s: int = 8
    resolution: str = "720x1280"  # 9:16 portrait
    aspect: str = "9:16"
    # Optional pre-generated start image media_id. When None the client
    # generates one via /api/flow/generate-image from positive_prompt.
    start_image_media_id: str | None = None
    image_prompt: str | None = None  # used if start_image_media_id is None


@dataclass(frozen=True)
class ClipResult:
    shot_index: int
    mp4_path: Path
    duration_ms: int
    cost_credits: int
    veo_job_id: str
    cascade_used: bool = False


@dataclass
class EpisodeContext:
    """Holds the FlowKit project+video IDs shared across all shots of one episode.

    Created once by setup_episode_context() at the start of an episode run,
    then passed to every submit_clip() invocation. Persisted to disk at
    episode_dir/_flowkit_context.json so reruns can resume without re-creating
    Flow resources.
    """

    project_id: str
    video_id: str
    project_name: str
    endpoint: str
    paygate: str
    scene_ids: dict[int, str] = field(default_factory=dict)  # shot_index → scene_id
    # Local path to the identity anchor PNG (e.g. zantara-face-anchor-v1.png).
    # When set, every shot without an explicit start_image_media_id uses the
    # uploaded anchor as the i2v start image so the rendered clip preserves the
    # A007 identity (verified cosine 0.91 vs 0.12 text-prompt). Persisted.
    anchor_image_path: str | None = None
    # Runtime cache of the uploaded anchor media_id — NOT persisted (media_ids
    # are project-scoped; re-uploaded per run, 0cr).
    anchor_media_id: str | None = field(default=None, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "video_id": self.video_id,
            "project_name": self.project_name,
            "endpoint": self.endpoint,
            "paygate": self.paygate,
            "scene_ids": {str(k): v for k, v in self.scene_ids.items()},
            "anchor_image_path": self.anchor_image_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EpisodeContext":
        return cls(
            project_id=data["project_id"],
            video_id=data["video_id"],
            project_name=data["project_name"],
            endpoint=data.get("endpoint", DEFAULT_ENDPOINT),
            paygate=data.get("paygate", DEFAULT_PAYGATE),
            scene_ids={int(k): v for k, v in (data.get("scene_ids") or {}).items()},
            anchor_image_path=data.get("anchor_image_path"),
        )


class FlowkitError(Exception):
    """Base for flowkit-layer errors."""


class FlowkitTimeoutError(FlowkitError):
    """Watchdog 300s exceeded for one clip."""


class FlowkitQuotaError(FlowkitError):
    """Flow Pro plan quota exceeded. Episode parked, Telegram P0 fires."""


class FlowkitProjectBindingError(FlowkitError):
    """The episode's immutable one-project binding is absent or inconsistent."""


class FlowkitNoResubmitError(FlowkitError):
    """The charging boundary may have been crossed; automatic retry is unsafe."""


class FlowkitGenerationAmbiguousError(FlowkitNoResubmitError):
    """The generate request was dispatched, but no durable workflow IDs returned.

    A timeout, transport failure, or malformed success response after the
    charging POST is not evidence that Flow rejected the render.  Callers must
    inspect the existing project before deciding whether a human-authorized
    resubmission is appropriate.
    """

    def __init__(self, *, project_id: str, scene_id: str, cause: Exception) -> None:
        self.project_id = project_id
        self.scene_id = scene_id
        self.cause = cause
        super().__init__(
            "generate-video was dispatched but its charge/workflow state is "
            "ambiguous; inspect the existing Flow project and do not resubmit "
            f"automatically (project_id={project_id}, scene_id={scene_id}): {cause}"
        )


class FlowkitStartImageAmbiguousError(FlowkitNoResubmitError):
    """A charged start-image request may exist without a returned media ID."""

    def __init__(
        self,
        *,
        project_id: str,
        scene_id: str | None,
        cause: BaseException,
        reason: str,
    ) -> None:
        self.project_id = project_id
        self.scene_id = scene_id
        self.cause = cause
        super().__init__(
            f"{reason}; generate-image was dispatched and its charge/media state "
            "is ambiguous, so this shot must not be resubmitted automatically "
            f"(project_id={project_id}, scene_id={scene_id or 'unknown'})"
        )


class FlowkitRetrievalError(FlowkitNoResubmitError):
    """A charged workflow exists, but its MP4 could not yet be recovered.

    This error is a hard retry boundary.  Callers may recover the exact
    ``workflow_id``/``media_id`` pair, but must never submit the shot again.
    """

    def __init__(
        self,
        *,
        workflow_id: str,
        media_id: str,
        destination: Path,
        cause: Exception,
    ) -> None:
        self.workflow_id = workflow_id
        self.media_id = media_id
        self.destination = destination
        self.cause = cause
        super().__init__(
            "video generation succeeded but MP4 retrieval failed; recover the "
            "existing workflow and do not resubmit "
            f"(workflow_id={workflow_id}, media_id={media_id}, "
            f"destination={destination}): {cause}"
        )


def _validate_flowkit_endpoint(endpoint: str) -> str:
    """Accept only the literal local FlowKit gateway and return its root URL."""
    if (
        not isinstance(endpoint, str)
        or not endpoint
        or endpoint != endpoint.strip()
        or any(ord(character) <= 32 or ord(character) == 127 for character in endpoint)
    ):
        raise FlowkitError(
            "endpoint must be the exact loopback FlowKit gateway on port 8100"
        )
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise FlowkitError(
            "endpoint must be the exact loopback FlowKit gateway on port 8100"
        ) from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in FLOWKIT_ALLOWED_HOSTS
        or port != FLOWKIT_ALLOWED_PORT
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or bool(parsed.query)
        or bool(parsed.fragment)
    ):
        raise FlowkitError(
            "endpoint must be the exact loopback FlowKit gateway on port 8100 "
            "with no credentials, non-root path, query, or fragment"
        )
    return endpoint.rstrip("/")


def _shot_receipt_path(episode_dir: Path, shot_index: int) -> Path:
    return episode_dir / f".wr3-flowkit-shot-{shot_index:04d}.json"


def _shot_lock_path(episode_dir: Path, shot_index: int) -> Path:
    return episode_dir / f".wr3-flowkit-shot-{shot_index:04d}.lock"


def _fsync_directory(directory: Path) -> None:
    """Durably commit a create/replace operation to its parent directory."""
    directory_fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _persist_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write one receipt atomically and fsync both file and parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
        _fsync_directory(path.parent)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@contextmanager
def _exclusive_flowkit_lock(path: Path, *, label: str) -> Iterator[None]:
    """Hold one non-blocking inode lock across a complete public operation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    acquired = False
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                raise
            raise FlowkitNoResubmitError(
                f"{label} is already in progress; no Flow request was submitted"
            ) from exc
        yield
    finally:
        if acquired:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _compose_flow_prompt(positive_prompt: str, negative_prompt: str) -> str:
    """Compose Flow's single prompt field without dropping negative constraints.

    FlowKit's ``/api/flow/generate-video`` schema has one ``prompt`` field, so
    ``ClipRequest.negative_prompt`` cannot travel as a separate JSON key.  Keep
    the positive prompt byte-for-byte intact and append one deterministic
    exclusion sentence only when a non-blank negative prompt exists.
    """
    negative = negative_prompt.strip()
    if not negative:
        return positive_prompt

    exclusion = f"The generated video must avoid {negative}"
    if not exclusion.endswith((".", "!", "?")):
        exclusion += "."
    if exclusion in positive_prompt:
        return positive_prompt

    separator = "\n" if positive_prompt else ""
    return f"{positive_prompt}{separator}{exclusion}"


async def _http_post_json(
    url: str, payload: dict[str, Any], timeout_s: int
) -> dict[str, Any]:
    """Minimal JSON POST using stdlib + asyncio.to_thread (no httpx import for parity)."""
    import urllib.request

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    def _do() -> dict[str, Any]:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return await asyncio.to_thread(_do)


async def _http_get_json(url: str, timeout_s: int) -> dict[str, Any]:
    """JSON GET that surfaces non-2xx responses as parsed JSON body (when available).

    On HTTPError (4xx/5xx), reads the error body and tries to parse it as JSON
    — Google Flow gateway returns `{"detail": {"error": {"code": N, ...}}}` for
    both success and failure. Caller decides how to treat each shape (poll on
    404, hard-fail on others).
    """
    import urllib.error
    import urllib.request

    def _do() -> dict[str, Any]:
        try:
            with urllib.request.urlopen(url, timeout=timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # Read the error body — same JSON shape as success endpoints
            try:
                body = e.read().decode("utf-8")
            except Exception:
                body = ""
            try:
                return (
                    json.loads(body)
                    if body
                    else {"detail": {"error": {"code": e.code}}}
                )
            except json.JSONDecodeError:
                return {"detail": {"error": {"code": e.code, "raw_body": body[:200]}}}

    return await asyncio.to_thread(_do)


async def _http_get_bytes(url: str, timeout_s: int) -> bytes:
    import urllib.request

    def _do() -> bytes:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return resp.read()

    return await asyncio.to_thread(_do)


def _is_allowed_flow_content_url(url: str) -> bool:
    """Return whether ``url`` is an HTTPS asset on Flow's real media hosts."""
    if (
        not isinstance(url, str)
        or not url
        or len(url) > 8_000
        or any(ord(character) <= 32 or ord(character) == 127 for character in url)
    ):
        return False
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    hostname = (parsed.hostname or "").lower()
    host_allowed = hostname == FLOW_MEDIA_PRIMARY_HOST or hostname.endswith(
        FLOW_MEDIA_HOST_SUFFIX
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
        and not parsed.fragment
    )


def _require_allowed_flow_content_url(url: str) -> None:
    if not _is_allowed_flow_content_url(url):
        raise FlowkitError(
            "workflow media URL is outside the approved HTTPS media hosts for "
            "flow-content.google"
        )


def _flow_media_content_length(headers: httpx.Headers) -> int | None:
    value = headers.get("content-length")
    if value is None:
        return None
    if not value.isascii() or not value.isdecimal():
        raise FlowkitError("workflow media response has an invalid Content-Length")
    return int(value, 10)


def _validate_mp4_payload(
    mp4_bytes: bytes,
    *,
    declared_mime: str | None = None,
) -> None:
    """Validate the bounded payload and its first ISO Base Media ``ftyp`` box."""
    if not mp4_bytes:
        raise FlowkitError("workflow media download returned zero bytes")
    if len(mp4_bytes) > FLOW_MEDIA_MAX_BYTES:
        raise FlowkitError("workflow media download exceeds the byte cap")
    if declared_mime is not None:
        normalized_mime = declared_mime.partition(";")[0].strip().lower()
        if normalized_mime not in FLOW_MEDIA_MIME_TYPES:
            raise FlowkitError(
                "workflow media response has an unsupported Content-Type"
            )

    if len(mp4_bytes) < 16 or mp4_bytes[4:8] != b"ftyp":
        raise FlowkitError(
            "workflow media bytes don't look like MP4 (not a valid MP4 payload)"
        )

    box_size = int.from_bytes(mp4_bytes[:4], "big")
    minimum_box_size = 16
    if box_size == 1:
        if len(mp4_bytes) < 24:
            raise FlowkitError(
                "workflow media bytes don't look like MP4 (invalid extended ftyp box)"
            )
        box_size = int.from_bytes(mp4_bytes[8:16], "big")
        minimum_box_size = 24
    if box_size < minimum_box_size or box_size > len(mp4_bytes):
        raise FlowkitError(
            "workflow media bytes don't look like MP4 (invalid ftyp box size)"
        )


async def _http_get_flow_content_bytes(
    url: str,
    timeout_s: int,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bytes:
    """Download one Flow MP4 with bounded, allowlisted manual redirects."""
    _require_allowed_flow_content_url(url)
    current_url = url
    timeout = httpx.Timeout(float(timeout_s))
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            transport=transport,
            trust_env=False,
        ) as client:
            for redirect_count in range(FLOW_MEDIA_MAX_REDIRECTS + 1):
                _require_allowed_flow_content_url(current_url)
                async with client.stream("GET", current_url) as response:
                    if response.status_code in FLOW_MEDIA_REDIRECT_STATUSES:
                        if redirect_count >= FLOW_MEDIA_MAX_REDIRECTS:
                            raise FlowkitError(
                                "workflow media response exceeded the redirect limit"
                            )
                        location = response.headers.get("location")
                        if not location:
                            raise FlowkitError(
                                "workflow media redirect has no Location header"
                            )
                        next_url = urljoin(current_url, location)
                        _require_allowed_flow_content_url(next_url)
                        current_url = next_url
                        continue
                    if response.status_code != 200:
                        raise FlowkitError(
                            "workflow media download returned a non-success HTTP status"
                        )

                    declared_length = _flow_media_content_length(response.headers)
                    if (
                        declared_length is not None
                        and declared_length > FLOW_MEDIA_MAX_BYTES
                    ):
                        raise FlowkitError(
                            "workflow media Content-Length exceeds the byte cap"
                        )
                    declared_mime = response.headers.get("content-type")
                    if declared_mime is None:
                        raise FlowkitError(
                            "workflow media response has no Content-Type"
                        )
                    content_encoding = response.headers.get("content-encoding")
                    if content_encoding not in (None, "", "identity"):
                        raise FlowkitError(
                            "workflow media response has an unsupported Content-Encoding"
                        )

                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(chunk) > FLOW_MEDIA_MAX_BYTES - len(body):
                            raise FlowkitError(
                                "workflow media download exceeds the byte cap"
                            )
                        body.extend(chunk)
                    result = bytes(body)
                    if declared_length is not None and declared_length != len(result):
                        raise FlowkitError(
                            "workflow media Content-Length does not match the body"
                        )
                    _validate_mp4_payload(result, declared_mime=declared_mime)
                    return result
    except FlowkitError:
        raise
    except asyncio.CancelledError as exc:
        raise FlowkitError(
            "workflow media download was cancelled; no retry was attempted"
        ) from exc
    except httpx.TimeoutException as exc:
        raise FlowkitError(
            "workflow media download timed out; no retry was attempted"
        ) from exc
    except httpx.HTTPError as exc:
        raise FlowkitError(
            "workflow media download failed; no retry was attempted"
        ) from exc
    except Exception as exc:
        raise FlowkitError(
            "workflow media download failed validation; no retry was attempted"
        ) from exc
    raise FlowkitError("workflow media download ended without a response")


def _write_mp4_atomic(dest: Path, mp4_bytes: bytes, *, media_id: str) -> None:
    """Validate an MP4 payload and replace ``dest`` only after a durable temp write."""
    _validate_mp4_payload(mp4_bytes)

    dest.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=dest.parent,
            prefix=f".{dest.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(mp4_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, dest)
        temp_path = None
        _fsync_directory(dest.parent)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _check_quota(resp_body: str | dict, *, where: str) -> None:
    """Detect quota/credit-exhausted upstream errors. Raises FlowkitQuotaError.

    Only fires on EXPLICIT error markers. Substring match on bare "credit" is
    too broad — successful responses include {"remainingCredits": N} which
    must not trigger quota path. We check (a) {"error": ...} envelope and
    (b) explicit quota tokens, never naked "credit".
    """
    # String inputs (legacy upstream message body) — keep tight signal list.
    if isinstance(resp_body, str):
        text = resp_body
        tight = (
            "QUOTA_EXCEEDED",
            "RESOURCE_EXHAUSTED",
            "insufficient credit",
            "insufficient_funds",
        )
        if any(n.lower() in text.lower() for n in tight):
            raise FlowkitQuotaError(f"{where}: {text[:200]}")
        return

    # Dict input — only inspect the {"error": …} envelope, never the success body.
    err_block = resp_body.get("error") if isinstance(resp_body, dict) else None
    if not err_block:
        return
    err_text = (
        json.dumps(err_block).lower()
        if isinstance(err_block, dict)
        else str(err_block).lower()
    )
    tight = (
        "quota_exceeded",
        "resource_exhausted",
        "insufficient credit",
        "insufficient_funds",
        "quota",
    )
    if any(n in err_text for n in tight):
        raise FlowkitQuotaError(f"{where}: {err_text[:200]}")


# ---------------------------------------------------------------------------
# Step 1 — per-episode project + video setup (call once per episode)
# ---------------------------------------------------------------------------


def _required_binding_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise FlowkitProjectBindingError(
            f"Flow project binding field {key!r} must be a non-blank exact string"
        )
    return value


def load_episode_project_binding(
    path: Path,
    *,
    episode_id: str,
    endpoint: str,
    paygate: str,
    expected_project_id: str | None = None,
    expected_video_id: str | None = None,
) -> EpisodeContext:
    """Load and validate the immutable project/video selected for one episode.

    This is intentionally local and side-effect free.  Callers can use it as a
    preflight before health, credit, or generation requests.
    """
    if (expected_project_id is None) != (expected_video_id is None):
        raise FlowkitProjectBindingError(
            "expected_project_id and expected_video_id must be supplied together"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FlowkitProjectBindingError(
            f"Flow project binding is unreadable: {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise FlowkitProjectBindingError("Flow project binding must be a JSON object")
    if payload.get("schema_version") != PROJECT_BINDING_SCHEMA:
        raise FlowkitProjectBindingError(
            f"Flow project binding schema must be {PROJECT_BINDING_SCHEMA!r}"
        )
    if payload.get("policy") != PROJECT_BINDING_POLICY:
        raise FlowkitProjectBindingError(
            f"Flow project binding policy must be {PROJECT_BINDING_POLICY!r}"
        )

    bound_episode_id = _required_binding_string(payload, "episode_id")
    project_id = _required_binding_string(payload, "project_id")
    video_id = _required_binding_string(payload, "video_id")
    bound_endpoint = _required_binding_string(payload, "endpoint")
    bound_paygate = _required_binding_string(payload, "paygate")
    canonical_endpoint = _validate_flowkit_endpoint(endpoint)

    if bound_episode_id != episode_id:
        raise FlowkitProjectBindingError(
            "Flow project binding belongs to a different episode: "
            f"expected={episode_id!r} actual={bound_episode_id!r}"
        )
    if _validate_flowkit_endpoint(bound_endpoint) != canonical_endpoint:
        raise FlowkitProjectBindingError(
            "Flow project binding endpoint does not match the current gateway"
        )
    if bound_paygate != paygate:
        raise FlowkitProjectBindingError(
            "Flow project binding paygate does not match the current run"
        )
    if expected_project_id is not None and project_id != expected_project_id:
        raise FlowkitProjectBindingError(
            "Flow project binding rejects a second project for this episode: "
            f"canonical={project_id} requested={expected_project_id}"
        )
    if expected_video_id is not None and video_id != expected_video_id:
        raise FlowkitProjectBindingError(
            "Flow project binding rejects a second video shell for this episode: "
            f"canonical={video_id} requested={expected_video_id}"
        )

    return EpisodeContext(
        project_id=project_id,
        video_id=video_id,
        project_name=episode_id,
        endpoint=canonical_endpoint,
        paygate=paygate,
    )


def _persist_episode_project_binding(path: Path, context: EpisodeContext) -> None:
    _persist_json_atomic(
        path,
        {
            "schema_version": PROJECT_BINDING_SCHEMA,
            "policy": PROJECT_BINDING_POLICY,
            "episode_id": context.project_name,
            "project_id": context.project_id,
            "video_id": context.video_id,
            "endpoint": context.endpoint,
            "paygate": context.paygate,
            "project_url": (
                f"https://labs.google/fx/tools/flow/project/{context.project_id}"
            ),
        },
    )


async def _create_episode_context_remote(
    name: str,
    *,
    endpoint: str,
    paygate: str,
    timeout_s: int,
) -> EpisodeContext:
    """Create one remote project/video pair; caller owns serialization."""
    # 1a. Create project — minimal body. Empirical 2026-05-20: passing
    # tool_name / material / allow_* causes upstream Google Flow API to return
    # 502 "Failed to parse Flow response: 'result'". Defaults applied server-side.
    project_url = urljoin(endpoint + "/", "api/projects")
    project_body: dict[str, Any] = {"name": name}
    try:
        proj_resp = await asyncio.wait_for(
            _http_post_json(project_url, project_body, timeout_s=timeout_s),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as e:
        raise FlowkitTimeoutError(f"project create timeout {timeout_s}s") from e

    project_id = proj_resp.get("id")
    if not project_id:
        raise FlowkitError(f"project create returned no id: {proj_resp}")

    # 1b. Create video shell — only fields we actually need at this point.
    video_url = urljoin(endpoint + "/", "api/videos")
    video_body: dict[str, Any] = {
        "project_id": project_id,
        "title": name,
        "orientation": "VERTICAL",
    }
    try:
        vid_resp = await asyncio.wait_for(
            _http_post_json(video_url, video_body, timeout_s=timeout_s),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as e:
        raise FlowkitTimeoutError(f"video create timeout {timeout_s}s") from e

    video_id = vid_resp.get("id")
    if not video_id:
        raise FlowkitError(f"video create returned no id: {vid_resp}")

    return EpisodeContext(
        project_id=project_id,
        video_id=video_id,
        project_name=name,
        endpoint=endpoint,
        paygate=paygate,
    )


async def setup_episode_context(
    name: str,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    paygate: str = DEFAULT_PAYGATE,
    timeout_s: int = 30,
    project_binding_path: Path | None = None,
    expected_project_id: str | None = None,
    expected_video_id: str | None = None,
) -> EpisodeContext:
    """Select exactly one Flow project + video shell for an episode.

    Without ``project_binding_path`` this preserves the legacy create-once
    behavior for programmatic callers.  Production/factory callers pass one
    shared binding path for every character, outfit, test, keyframe, and scene.
    The first caller either imports an explicitly expected existing pair or
    creates one pair and persists it atomically.  Every later caller reuses the
    pair; a divergent ID fails before any Flow request.
    """
    endpoint = _validate_flowkit_endpoint(endpoint)
    if (expected_project_id is None) != (expected_video_id is None):
        raise FlowkitProjectBindingError(
            "expected_project_id and expected_video_id must be supplied together"
        )

    if project_binding_path is None:
        if expected_project_id is not None and expected_video_id is not None:
            return EpisodeContext(
                project_id=expected_project_id,
                video_id=expected_video_id,
                project_name=name,
                endpoint=endpoint,
                paygate=paygate,
            )
        return await _create_episode_context_remote(
            name,
            endpoint=endpoint,
            paygate=paygate,
            timeout_s=timeout_s,
        )

    binding_path = project_binding_path.expanduser().resolve()
    lock_path = binding_path.with_name(f".{binding_path.name}.lock")
    with _exclusive_flowkit_lock(
        lock_path, label=f"Flow project binding {binding_path}"
    ):
        if binding_path.exists():
            return load_episode_project_binding(
                binding_path,
                episode_id=name,
                endpoint=endpoint,
                paygate=paygate,
                expected_project_id=expected_project_id,
                expected_video_id=expected_video_id,
            )

        if expected_project_id is not None and expected_video_id is not None:
            context = EpisodeContext(
                project_id=expected_project_id,
                video_id=expected_video_id,
                project_name=name,
                endpoint=endpoint,
                paygate=paygate,
            )
        else:
            context = await _create_episode_context_remote(
                name,
                endpoint=endpoint,
                paygate=paygate,
                timeout_s=timeout_s,
            )
        _persist_episode_project_binding(binding_path, context)
        return context


async def _create_scene(
    ctx: EpisodeContext,
    *,
    shot_index: int,
    positive_prompt: str,
    timeout_s: int = 30,
) -> str:
    """POST /api/scenes — returns scene_id. Caches on EpisodeContext.scene_ids."""
    if shot_index in ctx.scene_ids:
        return ctx.scene_ids[shot_index]

    url = urljoin(ctx.endpoint + "/", "api/scenes")
    body = {
        "video_id": ctx.video_id,
        "display_order": shot_index,
        "prompt": positive_prompt,
        "chain_type": "ROOT",
    }
    try:
        resp = await asyncio.wait_for(
            _http_post_json(url, body, timeout_s=timeout_s),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as e:
        raise FlowkitTimeoutError(f"scene create shot={shot_index} timeout") from e

    scene_id = resp.get("id")
    if not scene_id:
        raise FlowkitError(f"scene create returned no id shot={shot_index}: {resp}")
    ctx.scene_ids[shot_index] = scene_id
    return scene_id


async def _generate_start_image(
    ctx: EpisodeContext,
    *,
    prompt: str,
    timeout_s: int = 90,
    shot_index: int | None = None,
    scene_id: str | None = None,
) -> str:
    """POST /api/flow/generate-image — returns media_id (synchronous response).

    Charging call site (Veo credit-consuming, exact per-call cost unmeasured
    — see DEFAULT_IMAGE_COST_CR). `assert_spend_authorized` is the FIRST
    thing this function does — before any socket is opened — so a caller
    that reaches this function without a valid spend decision (including
    `scripts/wr3_probe_single_clip.py`, which calls this directly and
    bypasses `submit_clip`) fails closed with no HTTP attempted.

    `shot_index` is optional because some direct callers (the probe script)
    don't know it; when absent the ledger row records shot_index=-1 (the
    same "unknown shot" sentinel `wr3_credit_ledger.py`'s backfill CLI
    uses) rather than skip logging a real charge.
    """
    assert_spend_authorized(episode_id=ctx.project_name)
    _validate_flowkit_endpoint(ctx.endpoint)

    url = urljoin(ctx.endpoint + "/", "api/flow/generate-image")
    body = {
        "prompt": prompt,
        "project_id": ctx.project_id,
        "aspect_ratio": "IMAGE_ASPECT_RATIO_PORTRAIT",
        "user_paygate_tier": ctx.paygate,
    }
    try:
        resp = await asyncio.wait_for(
            _http_post_json(url, body, timeout_s=timeout_s),
            timeout=timeout_s,
        )
    except asyncio.CancelledError as exc:
        raise FlowkitStartImageAmbiguousError(
            project_id=ctx.project_id,
            scene_id=scene_id,
            cause=exc,
            reason="generate-image task was cancelled after dispatch",
        ) from exc
    except Exception as exc:
        raise FlowkitStartImageAmbiguousError(
            project_id=ctx.project_id,
            scene_id=scene_id,
            cause=exc,
            reason="generate-image response was unavailable after dispatch",
        ) from exc

    _check_quota(resp, where="generate-image")

    media = resp.get("media") or []
    if not media or not media[0].get("name"):
        cause = FlowkitError(f"generate-image returned no media: {str(resp)[:200]}")
        raise FlowkitStartImageAmbiguousError(
            project_id=ctx.project_id,
            scene_id=scene_id,
            cause=cause,
            reason="generate-image returned no media",
        ) from cause
    media_id = media[0]["name"]

    record_spend(
        episode_id=ctx.project_name,
        shot_index=shot_index if shot_index is not None else -1,
        credits=DEFAULT_IMAGE_COST_CR,
        mode="real",
        veo_job_id=media_id,
        source="_generate_start_image",
        clip_cost_cr=DEFAULT_IMAGE_COST_CR,
    )
    return media_id


async def _upload_image_asset(
    ctx: EpisodeContext,
    *,
    image_path: Path,
    timeout_s: int = 60,
) -> str:
    """POST /api/flow/upload-image — upload a LOCAL image, return its media_id.

    Used to inject the Zantara identity anchor as the i2v start image so the
    rendered clip preserves the A007 face. Empirically verified 2026-05-30:
    anchor start image → ArcFace cosine 0.91 (PASS) vs 0.12 for a text prompt.
    """
    url = urljoin(ctx.endpoint + "/", "api/flow/upload-image")
    body = {
        "file_path": str(image_path),
        "project_id": ctx.project_id,
        "file_name": image_path.name,
    }
    try:
        resp = await asyncio.wait_for(
            _http_post_json(url, body, timeout_s=timeout_s),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as e:
        raise FlowkitTimeoutError("upload-image timeout") from e

    _check_quota(resp, where="upload-image")

    media_id = resp.get("media_id")
    if not media_id:
        raise FlowkitError(f"upload-image returned no media_id: {str(resp)[:200]}")
    return media_id


async def _generate_video(
    ctx: EpisodeContext,
    *,
    start_image_media_id: str,
    scene_id: str,
    prompt: str,
    timeout_s: int = 180,
    shot_index: int | None = None,
    clip_cost_cr: int = DEFAULT_CLIP_COST_CR,
) -> tuple[str, str]:
    """POST /api/flow/generate-video — returns (workflow_id, video_media_id).

    Veo 3.1 Fast Tier_ONE portrait is synchronous → media is ready
    immediately upon HTTP 200. No polling required for this tier.

    THE charging call site (2026-08-23 fix): the Veo credit spend happens
    HERE, on this POST — not when the mp4 is later downloaded. The ledger
    write below fires immediately once workflow_id/video_media_id are
    parsed, so a subsequent `_download_video_media` failure (timeout,
    transient 500, whatever) can never leave a real charge unlogged. Before
    this fix `record_spend` lived in `submit_clip` AFTER the download
    succeeded — `wr3_render_episode.py` retries a failed shot up to 3x, so
    one shot could be charged 3x and logged 0x. `assert_spend_authorized` is
    the FIRST thing this function does, before any socket opens, so this
    also fails closed for `scripts/wr3_probe_single_clip.py`, which calls
    this function directly and bypasses `submit_clip` entirely.

    `shot_index` is optional (some direct callers don't know it); when
    absent the ledger row uses shot_index=-1, the same "unknown shot"
    sentinel `wr3_credit_ledger.py`'s backfill CLI uses, rather than skip
    logging a real charge. `clip_cost_cr` lets a caller record a measured
    live credit delta; omitting it preserves the existing SSOT default.
    """
    assert_spend_authorized(episode_id=ctx.project_name)
    _validate_flowkit_endpoint(ctx.endpoint)
    if (
        isinstance(clip_cost_cr, bool)
        or not isinstance(clip_cost_cr, int)
        or clip_cost_cr < 0
    ):
        raise FlowkitError("clip_cost_cr must be a non-negative integer")

    url = urljoin(ctx.endpoint + "/", "api/flow/generate-video")
    body = {
        "start_image_media_id": start_image_media_id,
        "prompt": prompt,
        "project_id": ctx.project_id,
        "scene_id": scene_id,
        "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
        "user_paygate_tier": ctx.paygate,
    }
    try:
        resp = await asyncio.wait_for(
            _http_post_json(url, body, timeout_s=timeout_s),
            timeout=timeout_s,
        )
    except asyncio.CancelledError as exc:
        raise FlowkitGenerationAmbiguousError(
            project_id=ctx.project_id,
            scene_id=scene_id,
            cause=exc,
        ) from exc
    except Exception as exc:
        # Once the charging POST is dispatched, a timeout or transport failure
        # cannot prove that Flow rejected the request. Retrying the whole shot
        # could therefore create a second paid workflow.
        raise FlowkitGenerationAmbiguousError(
            project_id=ctx.project_id,
            scene_id=scene_id,
            cause=exc,
        ) from exc

    _check_quota(resp, where="generate-video")

    workflows = resp.get("workflows") or []
    media = resp.get("media") or []
    if not workflows or not media:
        cause = FlowkitError(
            f"generate-video missing workflows/media: {str(resp)[:200]}"
        )
        raise FlowkitGenerationAmbiguousError(
            project_id=ctx.project_id,
            scene_id=scene_id,
            cause=cause,
        ) from cause
    workflow_id = workflows[0].get("name") or workflows[0].get("id") or ""
    video_media_id = media[0].get("name") or ""
    if not workflow_id or not video_media_id:
        cause = FlowkitError(
            "generate-video returned incomplete workflow/media identifiers: "
            f"{str(resp)[:200]}"
        )
        raise FlowkitGenerationAmbiguousError(
            project_id=ctx.project_id,
            scene_id=scene_id,
            cause=cause,
        ) from cause

    # Spend-truth ledger insert — fires here, at the actual charge, not at
    # download (see docstring). This is the one call site that actually
    # causes a Veo video charge.
    record_spend(
        episode_id=ctx.project_name,
        shot_index=shot_index if shot_index is not None else -1,
        credits=clip_cost_cr,
        mode="real",
        veo_job_id=workflow_id,
        source="_generate_video",
        clip_cost_cr=clip_cost_cr,
    )
    return workflow_id, video_media_id


async def _download_workflow_video_media(
    ctx: EpisodeContext,
    *,
    workflow_id: str,
    media_id: str,
    dest: Path,
    timeout_s: int = 240,
    poll_interval_s: int = 10,
) -> None:
    """Recover one already-generated workflow-backed Flow MP4 without resubmitting.

    This path performs read-only semantic polling against FlowKit's authenticated
    project snapshot. It never calls a generation endpoint. The response must
    echo the exact project, workflow, and primary media IDs supplied by the
    caller before either an encoded payload or signed Flow media URL is accepted.
    """
    if not ctx.project_id or not workflow_id or not media_id:
        raise FlowkitError(
            "workflow recovery requires project_id, workflow_id, and media_id"
        )

    url = urljoin(ctx.endpoint + "/", "api/flow/check-omni-status")
    request_body = {
        "project_id": ctx.project_id,
        "include_encoded_video": True,
        "workflows": [
            {
                "name": workflow_id,
                "primary_media_id": media_id,
                "project_id": ctx.project_id,
            }
        ],
    }
    deadline = asyncio.get_event_loop().time() + timeout_s
    last_status = "NO_RESPONSE"

    while asyncio.get_event_loop().time() < deadline:
        try:
            payload = await asyncio.wait_for(
                _http_post_json(url, request_body, timeout_s=min(timeout_s, 30)),
                timeout=min(timeout_s, 30),
            )
        except asyncio.TimeoutError:
            last_status = "POLL_TIMEOUT"
            await asyncio.sleep(poll_interval_s)
            continue

        if not isinstance(payload, dict):
            raise FlowkitError("workflow status response is not a JSON object")
        if payload.get("project_id") != ctx.project_id:
            raise FlowkitError(
                "workflow status project mismatch: "
                f"expected {ctx.project_id}, got {payload.get('project_id')!r}"
            )

        workflows = payload.get("workflows")
        if not isinstance(workflows, list):
            raise FlowkitError("workflow status response has no workflows list")
        matching = [
            item
            for item in workflows
            if isinstance(item, dict)
            and item.get("name") == workflow_id
            and item.get("primary_media_id") == media_id
        ]
        if len(matching) != 1:
            observed = [
                {
                    "name": item.get("name"),
                    "primary_media_id": item.get("primary_media_id"),
                }
                for item in workflows
                if isinstance(item, dict)
            ]
            raise FlowkitError(
                "workflow/media mismatch in status response: "
                f"expected ({workflow_id}, {media_id}), got {observed}"
            )

        item = matching[0]
        if item.get("project_id") != ctx.project_id:
            raise FlowkitError(
                "workflow item project mismatch: "
                f"expected {ctx.project_id}, got {item.get('project_id')!r}"
            )

        item_status = str(item.get("status") or "UNKNOWN")
        last_status = item_status
        if payload.get("status") == "FAILED" or item_status == "FAILED":
            raise FlowkitError(
                f"workflow {workflow_id[:8]} failed: {item.get('error') or item_status}"
            )
        if not item.get("done"):
            await asyncio.sleep(poll_interval_s)
            continue
        if item_status != "MEDIA_GENERATION_STATUS_SUCCESSFUL":
            raise FlowkitError(
                f"workflow {workflow_id[:8]} completed with unexpected status {item_status}"
            )

        media = item.get("media")
        if not isinstance(media, dict) or media.get("media_id") != media_id:
            raise FlowkitError(
                "completed workflow returned mismatched or missing media metadata"
            )

        encoded = media.get("encoded_video")
        if encoded is not None:
            if not isinstance(encoded, str) or not encoded:
                raise FlowkitError("workflow encoded_video is not a non-empty string")
            try:
                mp4_bytes = base64.b64decode(encoded, validate=True)
            except Exception as exc:
                raise FlowkitError(
                    f"media {media_id[:8]} base64 decode failed: {exc}"
                ) from exc
            _write_mp4_atomic(dest, mp4_bytes, media_id=media_id)
            return

        signed_url = media.get("url")
        if signed_url is not None:
            if not isinstance(signed_url, str) or not _is_allowed_flow_content_url(
                signed_url
            ):
                raise FlowkitError(
                    "workflow media URL is outside https://flow-content.google/"
                )
            mp4_bytes = await _http_get_flow_content_bytes(
                signed_url,
                timeout_s=min(timeout_s, 120),
            )
            _write_mp4_atomic(dest, mp4_bytes, media_id=media_id)
            return

        # A completed workflow can briefly precede signed-URL availability.
        # Keep polling the existing workflow only; never submit or retry Veo.
        await asyncio.sleep(poll_interval_s)

    raise FlowkitTimeoutError(
        f"workflow media {media_id[:8]} not recoverable after {timeout_s}s "
        f"(workflow={workflow_id[:8]}, last_status={last_status})"
    )


async def _download_video_media(
    ctx: EpisodeContext,
    *,
    media_id: str,
    dest: Path,
    timeout_s: int = 240,
    poll_interval_s: int = 10,
    workflow_id: str | None = None,
) -> None:
    """Download one MP4 via workflow-aware recovery or the legacy media API.

    When ``workflow_id`` is provided, use the read-only Omni project-status
    route and refuse any project/workflow/media mismatch. When omitted, keep
    the established legacy ``GET /api/flow/media/<media_id>`` polling behavior.

    Empirical 2026-05-20: generate-video returns media_id immediately but the
    backing Veo render is async. The media endpoint returns:
      - {"detail": {"error": {"code": 404, "status": "NOT_FOUND"}}} while pending
      - {"name": ..., "video": {"encodedVideo": "<base64>"}} once ready

    Polls every poll_interval_s up to timeout_s total. Veo 3.1 fast portrait
    typically ready in 30-90s.
    """
    if workflow_id is not None:
        await _download_workflow_video_media(
            ctx,
            workflow_id=workflow_id,
            media_id=media_id,
            dest=dest,
            timeout_s=timeout_s,
            poll_interval_s=poll_interval_s,
        )
        return

    url = urljoin(ctx.endpoint + "/", f"api/flow/media/{media_id}")
    deadline = asyncio.get_event_loop().time() + timeout_s

    payload: dict[str, Any] = {}
    while asyncio.get_event_loop().time() < deadline:
        try:
            payload = await asyncio.wait_for(
                _http_get_json(url, timeout_s=30),
                timeout=30,
            )
        except asyncio.TimeoutError:
            payload = {}
        # Known non-ready shapes (sleep & retry, NOT fatal):
        # (a) 404 NOT_FOUND envelope (Veo upstream not yet registered)
        # (b) 500 INTERNAL / 503 UNAVAILABLE while the media is materializing —
        #     empirically observed 2026-05-30 under PAYGATE_TIER_TIER1P5: Google
        #     returns 500 for the first ~40s after generate-video, then the MP4.
        #     Treating these as fatal killed all 18 C5a shots at poll #0.
        # (c) ok response but encodedVideo empty (rare transitional)
        if "detail" in payload and "error" in (payload.get("detail") or {}):
            err = payload["detail"]["error"]
            code = err.get("code")
            status = str(err.get("status", "")).upper()
            transient = code in (404, "404", 500, "500", 503, "503") or status in (
                "NOT_FOUND",
                "INTERNAL",
                "UNAVAILABLE",
            )
            if transient:
                # Still pending / transient backend hiccup — sleep and retry
                # (bounded by the outer deadline; persistent error → timeout).
                await asyncio.sleep(poll_interval_s)
                continue
            # Genuine terminal error (e.g. 400 INVALID_ARGUMENT) → fail loud.
            raise FlowkitError(f"media {media_id[:8]} download error: {err}")
        video = payload.get("video") or {}
        encoded = video.get("encodedVideo")
        if encoded:
            break
        # Empty encodedVideo + no error → also pending
        await asyncio.sleep(poll_interval_s)

    video = payload.get("video") or {}
    encoded = video.get("encodedVideo")
    if not encoded:
        raise FlowkitTimeoutError(
            f"media {media_id[:8]} not ready after {timeout_s}s polling. "
            f"Last payload keys: {list(payload.keys())}"
        )

    try:
        mp4_bytes = base64.b64decode(encoded, validate=True)
    except Exception as e:
        raise FlowkitError(f"media {media_id[:8]} base64 decode failed: {e}") from e

    _write_mp4_atomic(dest, mp4_bytes, media_id=media_id)


# ---------------------------------------------------------------------------
# Step 2 — per-shot pipeline
# ---------------------------------------------------------------------------


async def _submit_clip_impl(
    request: ClipRequest,
    *,
    episode_dir: Path,
    episode_context: EpisodeContext | None = None,
    endpoint: str = DEFAULT_ENDPOINT,
    paygate: str = DEFAULT_PAYGATE,
    timeout_s: int = PER_CLIP_TIMEOUT_S,
    # Legacy kwarg — older callers passed plan="pro". We map to paygate Tier 1.
    plan: str | None = None,
    _receipt_path: Path | None = None,
) -> ClipResult:
    """Submit a single Veo clip job. Watchdog timeout enforced by asyncio.wait_for.

    Raises FlowkitTimeoutError on watchdog hit, FlowkitQuotaError on plan exhaust,
    FlowkitError on any other gateway response.

    episode_context MUST be provided in real use. The legacy single-call
    path (no context) is preserved for tests by lazily creating a throwaway
    project — but in production wr3-clip-renderer creates the context once
    upstream and threads it through.
    """
    if zero_spend_enabled():
        # Zero-spend short-circuit — checked FIRST, before episode_context is
        # touched in any way, so this path NEVER calls _create_scene,
        # _generate_start_image, _generate_video, _download_video_media, or
        # setup_episode_context. episode_context may legitimately be None
        # here (render_shot_pack skips creating one under zero-spend) and
        # that must stay harmless — nothing below reads it.
        started = asyncio.get_event_loop().time()
        mp4_path = episode_dir / "clips" / f"{request.shot_index:02d}.mp4"
        await asyncio.to_thread(
            render_placeholder_clip,
            episode_id=episode_dir.name,
            shot_index=request.shot_index,
            dest=mp4_path,
        )
        duration_ms = int((asyncio.get_event_loop().time() - started) * 1000)
        record_spend(
            episode_id=episode_dir.name,
            shot_index=request.shot_index,
            credits=0,
            mode="placeholder",
            veo_job_id=None,
            source="submit_clip:zero_spend",
            clip_cost_cr=0,
        )
        return ClipResult(
            shot_index=request.shot_index,
            mp4_path=mp4_path,
            duration_ms=duration_ms,
            cost_credits=0,
            veo_job_id=f"placeholder:{episode_dir.name}:{request.shot_index:02d}",
        )

    effective_endpoint = (
        episode_context.endpoint if episode_context is not None else endpoint
    )
    _validate_flowkit_endpoint(effective_endpoint)

    if plan is not None and paygate == DEFAULT_PAYGATE:
        # legacy plan="pro" → Tier 1
        paygate = DEFAULT_PAYGATE

    if episode_context is None:
        # Lazy fallback — should NOT be hit in production. Logged via stderr.
        import sys as _sys

        print(
            f"[wr3-flowkit] WARN: submit_clip called without episode_context — "
            f"creating throwaway project for shot {request.shot_index}",
            file=_sys.stderr,
        )
        episode_context = await setup_episode_context(
            name=f"wr3-throwaway-{request.shot_index}",
            endpoint=endpoint,
            paygate=paygate,
        )

    started = asyncio.get_event_loop().time()

    # 2a. Scene (one per shot index)
    scene_id = await _create_scene(
        episode_context,
        shot_index=request.shot_index,
        positive_prompt=request.positive_prompt,
        timeout_s=30,
    )

    receipt: dict[str, Any] = {
        "schema_version": SHOT_RECEIPT_SCHEMA,
        "episode_id": episode_context.project_name,
        "shot_index": request.shot_index,
        "project_id": episode_context.project_id,
        "video_id": episode_context.video_id,
        "scene_id": scene_id,
    }

    def persist_receipt(status: str, **fields: Any) -> None:
        if _receipt_path is None:
            return
        receipt.update(fields)
        receipt["status"] = status
        _persist_json_atomic(_receipt_path, receipt)

    # 2b. Start image — precedence: explicit per-shot > episode anchor > text prompt.
    if request.start_image_media_id:
        start_image_id = request.start_image_media_id
    elif episode_context.anchor_image_path:
        # Upload the identity anchor once per episode, cache the media_id on ctx,
        # and reuse it as the i2v start image for every shot (preserves A007 face).
        if not episode_context.anchor_media_id:
            episode_context.anchor_media_id = await _upload_image_asset(
                episode_context,
                image_path=Path(episode_context.anchor_image_path),
            )
        start_image_id = episode_context.anchor_media_id
    else:
        img_prompt = request.image_prompt or request.positive_prompt
        persist_receipt("start_image_dispatch_pending")
        try:
            start_image_id = await _generate_start_image(
                episode_context,
                prompt=img_prompt,
                timeout_s=90,
                shot_index=request.shot_index,
                scene_id=scene_id,
            )
        except FlowkitStartImageAmbiguousError:
            persist_receipt("start_image_ambiguous")
            raise
        except FlowkitQuotaError:
            persist_receipt("start_image_rejected_quota")
            raise
        persist_receipt(
            "start_image_succeeded",
            start_image_media_id=start_image_id,
        )

    # 2c. Video generation (synchronous on portrait fast Tier 1).
    # The Veo charge — and its ledger record — happen INSIDE _generate_video,
    # not here and not after the download below. See that function's
    # docstring for why: charging on download success let a shot be billed
    # up to 3x (wr3_render_episode.py retries) and logged 0x whenever the
    # download step itself failed.
    persist_receipt(
        "video_dispatch_pending",
        start_image_media_id=start_image_id,
    )
    try:
        workflow_id, video_media_id = await _generate_video(
            episode_context,
            start_image_media_id=start_image_id,
            scene_id=scene_id,
            prompt=_compose_flow_prompt(
                request.positive_prompt,
                request.negative_prompt,
            ),
            timeout_s=min(timeout_s - 30, 180),
            shot_index=request.shot_index,
        )
    except FlowkitGenerationAmbiguousError:
        persist_receipt("video_ambiguous")
        raise
    except FlowkitQuotaError:
        persist_receipt("video_rejected_quota")
        raise

    persist_receipt(
        "generation_succeeded",
        workflow_id=workflow_id,
        media_id=video_media_id,
    )

    # 2d-e. Download base64 → MP4
    mp4_path = episode_dir / "clips" / f"{request.shot_index:02d}.mp4"
    try:
        await _download_video_media(
            episode_context,
            media_id=video_media_id,
            dest=mp4_path,
            timeout_s=120,
            workflow_id=workflow_id,
        )
    except Exception as exc:
        # The charged generation already exists.  Convert every recovery
        # failure into a distinct, ID-bearing error so the outer renderer can
        # never mistake it for a safe pre-generation retry.
        persist_receipt(
            "retrieval_failed",
            workflow_id=workflow_id,
            media_id=video_media_id,
        )
        raise FlowkitRetrievalError(
            workflow_id=workflow_id,
            media_id=video_media_id,
            destination=mp4_path,
            cause=exc,
        ) from exc

    duration_ms = int((asyncio.get_event_loop().time() - started) * 1000)
    persist_receipt(
        "completed",
        workflow_id=workflow_id,
        media_id=video_media_id,
    )

    return ClipResult(
        shot_index=request.shot_index,
        mp4_path=mp4_path,
        duration_ms=duration_ms,
        cost_credits=DEFAULT_CLIP_COST_CR,
        veo_job_id=workflow_id,
    )


async def submit_clip(
    request: ClipRequest,
    *,
    episode_dir: Path,
    episode_context: EpisodeContext | None = None,
    endpoint: str = DEFAULT_ENDPOINT,
    paygate: str = DEFAULT_PAYGATE,
    timeout_s: int = PER_CLIP_TIMEOUT_S,
    plan: str | None = None,
) -> ClipResult:
    """Run one shot under a durable, per-destination no-resubmit guard."""
    if zero_spend_enabled():
        return await _submit_clip_impl(
            request,
            episode_dir=episode_dir,
            episode_context=episode_context,
            endpoint=endpoint,
            paygate=paygate,
            timeout_s=timeout_s,
            plan=plan,
        )

    if (
        isinstance(request.shot_index, bool)
        or not isinstance(request.shot_index, int)
        or request.shot_index < 0
    ):
        raise FlowkitError("shot_index must be a non-negative integer")
    effective_endpoint = (
        episode_context.endpoint if episode_context is not None else endpoint
    )
    _validate_flowkit_endpoint(effective_endpoint)

    receipt_path = _shot_receipt_path(episode_dir, request.shot_index)
    lock_path = _shot_lock_path(episode_dir, request.shot_index)
    destination = episode_dir / "clips" / f"{request.shot_index:02d}.mp4"
    with _exclusive_flowkit_lock(
        lock_path,
        label=f"shot {request.shot_index}",
    ):
        if receipt_path.exists() or destination.exists():
            raise FlowkitNoResubmitError(
                f"shot {request.shot_index} has durable prior-run evidence and "
                "must not be resubmitted automatically"
            )
        return await _submit_clip_impl(
            request,
            episode_dir=episode_dir,
            episode_context=episode_context,
            endpoint=endpoint,
            paygate=paygate,
            timeout_s=timeout_s,
            plan=plan,
            _receipt_path=receipt_path,
        )


async def _render_shot_pack_impl(
    shot_pack_path: Path,
    episode_dir: Path,
    *,
    episode_context: EpisodeContext | None = None,
    max_retries_per_shot: int = 2,
    endpoint: str = DEFAULT_ENDPOINT,
    paygate: str = DEFAULT_PAYGATE,
    # Legacy
    plan: str | None = None,
) -> list[ClipResult]:
    """Render every shot in shot-pack.json sequentially.

    On a failure before a workflow is accepted: up to 2 retries. Once video
    generation succeeds, retrieval failure is never retried through
    ``submit_clip``; the exact workflow/media pair must be recovered instead.

    Creates a per-episode FlowKit project+video if episode_context is None
    (derives name from shot-pack JSON or path stem).

    Under WR3_ZERO_SPEND, setup_episode_context is skipped entirely (it
    opens sockets to create the Flow project/video shell) — every shot goes
    straight through submit_clip's own zero-spend placeholder path with
    episode_context left as whatever was passed in (typically None).
    """
    shot_pack = json.loads(shot_pack_path.read_text())
    shots = shot_pack.get("shots") or []
    results: list[ClipResult] = []

    zero_spend = zero_spend_enabled()
    created_context = False

    if not zero_spend:
        effective_endpoint = (
            episode_context.endpoint if episode_context is not None else endpoint
        )
        _validate_flowkit_endpoint(effective_endpoint)

    if not zero_spend and episode_context is None:
        episode_name = (
            shot_pack.get("episode_id")
            or shot_pack.get("topic", "")[:60]
            or episode_dir.name
            or f"wr3-{shot_pack_path.stem}"
        )
        episode_context = await setup_episode_context(
            name=episode_name,
            endpoint=endpoint,
            paygate=paygate,
        )
        created_context = True

    # Identity anchor (root-level shot-pack field) → drives i2v start image so
    # every shot preserves the A007 face. Only set if not already on the
    # context — and only when there IS a context (zero-spend never creates
    # one and submit_clip's placeholder path never reads it).
    if (
        not zero_spend
        and episode_context is not None
        and episode_context.anchor_image_path is None
    ):
        anchor_path = shot_pack.get("anchor_image_path")
        if anchor_path:
            episode_context.anchor_image_path = anchor_path

    # Persist only real-mode contexts created by this driver, as before, but
    # do it after applying the root-level identity anchor.  The old order
    # wrote ``anchor_image_path: null`` even though the in-memory context used
    # the anchor for every subsequent clip.  Zero-spend still creates and
    # writes no Flow context at all.
    if not zero_spend and created_context and episode_context is not None:
        ctx_path = episode_dir / "_flowkit_context.json"
        ctx_path.parent.mkdir(parents=True, exist_ok=True)
        ctx_path.write_text(json.dumps(episode_context.to_dict(), indent=2))

    for shot in shots:
        request = ClipRequest(
            shot_index=shot["index"],
            positive_prompt=shot.get("positive_prompt", ""),
            negative_prompt=shot.get("negative_prompt", ""),
            identity_tokens=tuple(shot.get("identity_tokens") or []),
            duration_s=int(shot.get("duration_s", 8)),
            resolution=shot.get("resolution", "720x1280"),
            aspect=shot.get("aspect", "9:16"),
            start_image_media_id=shot.get("start_image_media_id"),
            image_prompt=shot.get("image_prompt"),
        )

        last_error: Exception | None = None
        for attempt in range(max_retries_per_shot + 1):
            try:
                clip = await submit_clip(
                    request,
                    episode_dir=episode_dir,
                    episode_context=episode_context,
                    endpoint=endpoint,
                    paygate=paygate,
                )
                results.append(clip)
                break
            except FlowkitQuotaError:
                raise  # bubble up to clip-renderer for Telegram P0
            except FlowkitNoResubmitError:
                # The charging POST was dispatched or a paid workflow already
                # exists. Re-entering submit_clip could double-spend.
                raise
            except FlowkitError as e:
                last_error = e
                if attempt == max_retries_per_shot:
                    raise FlowkitError(
                        f"shot {request.shot_index} failed {attempt + 1} attempts; "
                        f"b-roll-curator fallback required. last_error={last_error}"
                    ) from e
        else:
            assert last_error is not None
            raise last_error

    return results


async def render_shot_pack(
    shot_pack_path: Path,
    episode_dir: Path,
    *,
    episode_context: EpisodeContext | None = None,
    max_retries_per_shot: int = 2,
    endpoint: str = DEFAULT_ENDPOINT,
    paygate: str = DEFAULT_PAYGATE,
    plan: str | None = None,
) -> list[ClipResult]:
    """Render a pack once under a durable episode-level no-resubmit guard."""
    if zero_spend_enabled():
        return await _render_shot_pack_impl(
            shot_pack_path,
            episode_dir,
            episode_context=episode_context,
            max_retries_per_shot=max_retries_per_shot,
            endpoint=endpoint,
            paygate=paygate,
            plan=plan,
        )

    effective_endpoint = (
        episode_context.endpoint if episode_context is not None else endpoint
    )
    _validate_flowkit_endpoint(effective_endpoint)

    shot_pack = json.loads(shot_pack_path.read_text())
    shots = shot_pack.get("shots") or []
    if not isinstance(shots, list):
        raise FlowkitError("shot pack shots must be a list")
    shot_indices: list[int] = []
    for shot in shots:
        if not isinstance(shot, dict):
            raise FlowkitError("every shot pack entry must be an object")
        shot_index = shot.get("index")
        if (
            isinstance(shot_index, bool)
            or not isinstance(shot_index, int)
            or shot_index < 0
        ):
            raise FlowkitError("every shot index must be a non-negative integer")
        shot_indices.append(shot_index)
    if len(shot_indices) != len(set(shot_indices)):
        raise FlowkitError("shot pack indices must be unique")

    receipt_path = episode_dir / ".wr3-flowkit-render-receipt.json"
    lock_path = episode_dir / ".wr3-flowkit-render.lock"
    render_receipt: dict[str, Any] = {
        "schema_version": RENDER_RECEIPT_SCHEMA,
        "episode_id": str(
            shot_pack.get("episode_id") or episode_dir.name or shot_pack_path.stem
        ),
        "shot_indices": shot_indices,
    }

    with _exclusive_flowkit_lock(lock_path, label="shot-pack render"):
        if receipt_path.exists():
            raise FlowkitNoResubmitError(
                "this shot pack has durable prior-run evidence and must not be rerun"
            )
        for shot_index in shot_indices:
            destination = episode_dir / "clips" / f"{shot_index:02d}.mp4"
            if (
                _shot_receipt_path(episode_dir, shot_index).exists()
                or destination.exists()
            ):
                raise FlowkitNoResubmitError(
                    f"shot {shot_index} has durable prior-run evidence; the shot pack "
                    "must not be rerun"
                )

        render_receipt["status"] = "started"
        _persist_json_atomic(receipt_path, render_receipt)
        try:
            results = await _render_shot_pack_impl(
                shot_pack_path,
                episode_dir,
                episode_context=episode_context,
                max_retries_per_shot=max_retries_per_shot,
                endpoint=endpoint,
                paygate=paygate,
                plan=plan,
            )
        except BaseException:
            render_receipt["status"] = "failed_no_resubmit"
            _persist_json_atomic(receipt_path, render_receipt)
            raise

        render_receipt["status"] = "completed"
        render_receipt["completed_shot_count"] = len(results)
        _persist_json_atomic(receipt_path, render_receipt)
        return results


if __name__ == "__main__":
    import sys

    print("WR3 Flowkit client — stub smoke test", file=sys.stderr)
    print(
        f"endpoint={DEFAULT_ENDPOINT} paygate={DEFAULT_PAYGATE} timeout_s={PER_CLIP_TIMEOUT_S}",
        file=sys.stderr,
    )
