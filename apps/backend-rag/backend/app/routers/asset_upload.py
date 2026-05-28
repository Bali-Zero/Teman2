"""Asset upload proxy endpoint — forwards file bytes from authenticated callers
to Tigris S3 (nuzantara-warroom-images bucket) using container-side AWS creds.

Replaces:
- Cloudflared tunnel hacks (tactical bridge)
- Pro-side AWS_ACCESS_KEY_ID secret pollution (rejected 4/4 panel 2026-05-26)

Use cases:
- WR2 operator_driven mode hero JPG upload
- WR3 b-roll asset publishing
- Any local Pro/Mini script needing public HTTPS URL for Tigris-hosted media

Authentication: shared-secret bearer token (X-Asset-Upload-Token header).
Auth header reads env `ASSET_UPLOAD_TOKEN` env var (Fly secret, rotated quarterly).

Spec reference: docs/wr2/operator-driven-mode-spec-2026-05-26.md (P1.2)
Panel reference: research/operations/2026-05-26-wr2-canva-ig-4llm-panel-synthesis.md
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Annotated

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status

from backend.services.canva_renderer_v2 import _tigris

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assets", tags=["assets"])

_MAX_BYTES = 25 * 1024 * 1024  # 25MB — large enough for high-res hero JPG, small enough to reject abuse
_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "application/pdf",
}
_ALLOWED_PREFIXES = {
    "wr2-pdf",
    "wr2-hero",
    "wr3-broll",
    "wr3-audio",
    "carousel-session",
}


def _verify_token(provided: str | None) -> None:
    expected = os.environ.get("ASSET_UPLOAD_TOKEN", "").strip()
    if not expected:
        # Fail closed: if server has no token configured, refuse uploads.
        logger.error("ASSET_UPLOAD_TOKEN env var missing or empty — refusing upload")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Asset upload service not configured",
        )
    if not provided or provided.strip() != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Asset-Upload-Token",
        )


def _validate_prefix(prefix: str) -> None:
    if prefix not in _ALLOWED_PREFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"prefix must be one of {sorted(_ALLOWED_PREFIXES)}",
        )


def _validate_content_type(content_type: str | None) -> None:
    if not content_type or content_type.lower() not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"content_type {content_type!r} not allowed — accepted: {sorted(_ALLOWED_CONTENT_TYPES)}",
        )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: Annotated[UploadFile, File(description="Binary file to upload to Tigris")],
    prefix: Annotated[str, Form(description="Tigris key prefix (e.g. wr2-hero, wr3-broll)")],
    session_id: Annotated[str, Form(description="Session/carousel/episode slug for path nesting")],
    auth_token: Annotated[str | None, Header(alias="X-Asset-Upload-Token")] = None,
) -> dict[str, str | int]:
    """Upload a single asset to Tigris S3, return content-addressed public URL.

    Key format: `{prefix}/{session_id}/{sha256_first8}-{original_filename}`

    Response:
    ```json
    {
      "public_url": "https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-hero/c5a-2026-05-26/c9b1a93a-01-hero.jpg",
      "tigris_key": "wr2-hero/c5a-2026-05-26/c9b1a93a-01-hero.jpg",
      "sha256": "c9b1a93a139f7a62...",
      "bytes": 1727237,
      "content_type": "image/jpeg"
    }
    ```
    """
    _verify_token(auth_token)
    _validate_prefix(prefix)
    _validate_content_type(file.content_type)

    if not session_id or "/" in session_id or ".." in session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id must be non-empty and contain no path separators",
        )

    body = await file.read()
    size = len(body)
    if size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty body")
    if size > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"body {size} bytes exceeds {_MAX_BYTES}",
        )

    sha256_full = hashlib.sha256(body).hexdigest()
    sha8 = sha256_full[:8]
    safe_name = os.path.basename(file.filename or "asset")
    tigris_key = f"{prefix}/{session_id}/{sha8}-{safe_name}"

    s3 = _tigris.get_s3_client()
    try:
        s3.put_object(
            Bucket=_tigris.BUCKET,
            Key=tigris_key,
            Body=body,
            ContentType=file.content_type or "application/octet-stream",
            ACL="public-read",
        )
    except Exception as e:
        logger.exception("Tigris put_object failed for key=%s: %s", tigris_key, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tigris upload failed: {e}",
        ) from e

    public_url = f"https://{_tigris.PUBLIC_HOST}/{tigris_key}"
    logger.info(
        "Asset uploaded: key=%s bytes=%d sha8=%s session=%s",
        tigris_key,
        size,
        sha8,
        session_id,
    )

    return {
        "public_url": public_url,
        "tigris_key": tigris_key,
        "sha256": sha256_full,
        "bytes": size,
        "content_type": file.content_type or "application/octet-stream",
    }


@router.get("/health")
async def asset_upload_health() -> dict[str, str | bool]:
    """Lightweight health probe — no Tigris call, just env config check."""
    token_configured = bool(os.environ.get("ASSET_UPLOAD_TOKEN", "").strip())
    return {
        "status": "ok" if token_configured else "degraded_no_token",
        "token_configured": token_configured,
        "bucket": _tigris.BUCKET,
        "endpoint": _tigris.ENDPOINT,
    }
