"""Meta WhatsApp Cloud API — inbound media download (Anello 1a).

When a live WhatsApp message carries an attachment (image / document), the
webhook payload contains only a ``media_id`` — NOT the bytes. Retrieving the
file is a TWO-step Meta Cloud API dance:

1. ``GET https://graph.facebook.com/<api_version>/<media_id>`` with the Bearer
   token → JSON ``{"url": <signed-url>, "mime_type": ..., "sha256": ...,
   "file_size": ...}``. The ``url`` is short-lived (minutes) and itself
   requires the Bearer token to fetch.
2. ``GET <signed-url>`` with the SAME Bearer token → the raw bytes.

This module is a PURE function pair: it does Meta I/O + a local filesystem
write, and returns a small dataclass. It has ZERO database and ZERO Fly
coupling — *where* it runs (Fly vs Pro) is a deliberate downstream decision
(Law 2: client PII — passports, KTP — must ultimately live on sovereign local
storage, never third-party cloud). Callers own that placement; this module
only knows "a Bearer token, a media_id, and a directory to write into".

Reuses the same httpx async + ``Authorization: Bearer`` pattern as
``adapter.py`` send-path. The token is the existing ``WHATSAPP_ACCESS_TOKEN``
— Meta uses one token for both send and media-read (no separate scope), but
that is verified empirically with a real media_id on the Pro, not asserted
here.

Unit-testable on any machine: the two Meta GETs are injected via an
``httpx.AsyncClient`` the caller passes in, so tests mock the transport with
``httpx.MockTransport`` — no network, no Pro, no DB.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Meta caps Cloud API media at 100 MB; documents/images for intake are far
# smaller. Guard against a hostile/oversized response streaming us out of disk.
_MAX_MEDIA_BYTES = 100 * 1024 * 1024

_GRAPH_BASE = "https://graph.facebook.com"


class MediaDownloadError(Exception):
    """Raised when a media download cannot complete (Meta error, oversize,
    hash mismatch, write failure). Callers should treat the media as
    un-ingested and leave the source message for retry — never silently drop.
    """


@dataclass(frozen=True)
class DownloadedMedia:
    """Result of a successful media download.

    Attributes:
        blob_path: Absolute path of the saved file on local disk.
        mime_type: MIME type Meta reported for the media.
        sha256: Hex sha256 of the bytes actually written (recomputed locally,
            not trusted from Meta — see ``download_media``).
        byte_size: Number of bytes written.
        media_id: The Meta media_id this came from (provenance).
    """

    blob_path: str
    mime_type: str | None
    sha256: str
    byte_size: int
    media_id: str


async def _fetch_media_metadata(
    client: httpx.AsyncClient,
    *,
    media_id: str,
    access_token: str,
    api_version: str,
) -> dict:
    """Step 1: resolve a media_id to its signed URL + metadata.

    Returns the parsed Meta JSON (expects at least ``url``). Raises
    ``MediaDownloadError`` on any non-2xx or missing ``url``.
    """
    url = f"{_GRAPH_BASE}/{api_version}/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise MediaDownloadError(
            f"Meta media-metadata GET failed for media_id={media_id}: {exc}"
        ) from exc

    data = resp.json()
    if not isinstance(data, dict) or not data.get("url"):
        raise MediaDownloadError(
            f"Meta media-metadata for media_id={media_id} missing 'url' field"
        )
    return data


async def _fetch_media_bytes(
    client: httpx.AsyncClient,
    *,
    signed_url: str,
    access_token: str,
) -> bytes:
    """Step 2: download the raw bytes from the signed URL.

    The signed URL still requires the Bearer token. Enforces the size cap.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = await client.get(signed_url, headers=headers)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise MediaDownloadError(f"Meta media bytes GET failed: {exc}") from exc

    content = resp.content
    if len(content) > _MAX_MEDIA_BYTES:
        raise MediaDownloadError(
            f"Media exceeds {_MAX_MEDIA_BYTES} bytes (got {len(content)})"
        )
    if not content:
        raise MediaDownloadError("Meta returned an empty media body")
    return content


def _safe_blob_path(dest_dir: str | Path, media_id: str, mime_type: str | None) -> Path:
    """Build the on-disk path for a media blob.

    Names the file by media_id (Meta media_ids are opaque, unique, and contain
    no path separators) plus an extension inferred from the MIME type. This
    keeps writes idempotent-ish (same media_id → same path) and prevents any
    path traversal from a hostile media_id.
    """
    # media_id is Meta-generated (digits); defend anyway against separators.
    safe_id = media_id.replace("/", "_").replace("..", "_").strip()
    if not safe_id:
        raise MediaDownloadError("empty media_id")

    ext = _ext_for_mime(mime_type)
    return Path(dest_dir) / f"wa_{safe_id}{ext}"


def _ext_for_mime(mime_type: str | None) -> str:
    """Map a MIME type to a file extension. Falls back to ``.bin``."""
    if not mime_type:
        return ".bin"
    base = mime_type.split(";", 1)[0].strip().lower()
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
        "image/heic": ".heic",
        "image/heif": ".heif",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    }
    return mapping.get(base, ".bin")


async def download_media(
    client: httpx.AsyncClient,
    *,
    media_id: str,
    access_token: str,
    dest_dir: str | Path,
    api_version: str = "v18.0",
) -> DownloadedMedia:
    """Download one WhatsApp media object to local disk.

    Pure orchestration of the two Meta GETs + a local write. No DB, no Fly.
    The caller supplies the ``httpx.AsyncClient`` (so tests inject a
    ``MockTransport``) and the destination directory (so the caller owns the
    Law-2 sovereign-storage placement decision).

    Args:
        client: A persistent async HTTP client (Golden Rule #10 — never
            construct one per call).
        media_id: The Meta media_id from the inbound webhook.
        access_token: ``WHATSAPP_ACCESS_TOKEN`` (same token as send-path).
        dest_dir: Directory to write the blob into (created if absent).
        api_version: Meta Graph API version (default matches channel config).

    Returns:
        ``DownloadedMedia`` with the local path, MIME, locally-recomputed
        sha256, byte size, and provenance media_id.

    Raises:
        MediaDownloadError: on any Meta error, oversize, empty body, hash
            mismatch vs Meta's declared sha256, or filesystem write failure.
    """
    meta = await _fetch_media_metadata(
        client,
        media_id=media_id,
        access_token=access_token,
        api_version=api_version,
    )
    signed_url = meta["url"]
    mime_type = meta.get("mime_type")
    declared_sha256 = meta.get("sha256")

    content = await _fetch_media_bytes(
        client,
        signed_url=signed_url,
        access_token=access_token,
    )

    # Recompute the hash locally — never trust Meta's declared value blindly.
    # If Meta declared one and it disagrees, the transfer is corrupt: fail.
    local_sha256 = hashlib.sha256(content).hexdigest()
    if declared_sha256 and declared_sha256 != local_sha256:
        raise MediaDownloadError(
            f"sha256 mismatch for media_id={media_id}: "
            f"Meta={declared_sha256} local={local_sha256}"
        )

    blob_path = _safe_blob_path(dest_dir, media_id, mime_type)
    try:
        os.makedirs(blob_path.parent, exist_ok=True)
        # Write atomically: temp file + rename, so a crash mid-write never
        # leaves a truncated blob that a later dedup would treat as complete.
        tmp_path = blob_path.with_suffix(blob_path.suffix + ".part")
        with open(tmp_path, "wb") as fh:
            fh.write(content)
        os.replace(tmp_path, blob_path)
    except OSError as exc:
        raise MediaDownloadError(
            f"failed to write media blob for media_id={media_id}: {exc}"
        ) from exc

    logger.info(
        "⬇️  WA media downloaded: media_id=%s mime=%s bytes=%d → %s",
        media_id,
        mime_type,
        len(content),
        blob_path,
    )
    return DownloadedMedia(
        blob_path=str(blob_path),
        mime_type=mime_type,
        sha256=local_sha256,
        byte_size=len(content),
        media_id=media_id,
    )
