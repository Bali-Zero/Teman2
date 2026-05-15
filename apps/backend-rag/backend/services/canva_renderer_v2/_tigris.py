"""Tigris S3 client wrapper. boto3 put_object with 3-retry + delete + URL build.

Bucket: nuzantara-warroom-images (public-read prefix wr2-pdf/).
Endpoint: https://fly.storage.tigris.dev
Credentials: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY env (Tigris-compat).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

BUCKET = "nuzantara-warroom-images"
ENDPOINT = "https://fly.storage.tigris.dev"
PUBLIC_HOST = f"{BUCKET}.fly.storage.tigris.dev"

MAX_RETRIES = 3
BACKOFF_BASE_S = 2.0  # 2s, 4s, 8s

TRANSIENT_ERROR_CODES = {"503", "502", "504", "RequestTimeout", "SlowDown", "Throttling"}


class TigrisError(RuntimeError):
    """Tigris S3 operation failed after retries."""


def get_s3_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name="auto",
    )


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        return code in TRANSIENT_ERROR_CODES
    return isinstance(exc, BotoCoreError)


def upload_pdf(s3: Any, pdf_path: Path, *, draft_id: str,
               prefix: str = "wr2-pdf",
               content_addressed: bool = True) -> tuple[str, str]:
    """Upload PDF to Tigris S3, return (public_url, s3_key).

    Fix 2026-05-15 [Codex find]: previously key was hardcoded as
    `{prefix}/{draft_id}.pdf` — every retry/rerender overwrote the same
    URL while Canva or CDN could serve stale bytes. New default:
    content-addressed key `{prefix}/{draft_id}/{sha256_first8}.pdf` so
    each render version is its own URL. Legacy single-key mode retained
    via content_addressed=False for backwards compatibility.

    Fix 2026-05-16 [DeepSeek find]: returns (url, key) tuple so callers
    can pass the exact key to delete_pdf_by_key() on cleanup, avoiding
    orphaned S3 objects when Canva import fails.
    """
    import hashlib as _hl
    body = pdf_path.read_bytes()
    if content_addressed:
        sha8 = _hl.sha256(body).hexdigest()[:8]
        key = f"{prefix}/{draft_id}/{sha8}.pdf"
    else:
        key = f"{prefix}/{draft_id}.pdf"

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            s3.put_object(
                Bucket=BUCKET,
                Key=key,
                Body=body,
                ContentType="application/pdf",
                ACL="public-read",
            )
            logger.info("Tigris upload OK: %s (attempt %d, sha256=%s)",
                        key, attempt,
                        _hl.sha256(body).hexdigest()[:12])
            # Best-effort: verify Tigris HEAD before returning URL
            try:
                head = s3.head_object(Bucket=BUCKET, Key=key)
                logger.info("Tigris HEAD ok: ETag=%s, len=%s",
                            head.get("ETag", "?"), head.get("ContentLength", "?"))
            except Exception as e:  # noqa: BLE001
                logger.warning("Tigris HEAD verify failed (non-fatal): %s", e)
            return f"https://{PUBLIC_HOST}/{key}", key
        except (ClientError, BotoCoreError) as e:
            last_exc = e
            if not _is_transient(e):
                raise TigrisError(f"Tigris non-transient error: {e}") from e
            if attempt < MAX_RETRIES:
                delay = BACKOFF_BASE_S * (2 ** (attempt - 1))
                logger.warning(
                    "Tigris transient error attempt %d/%d: %s — sleep %.1fs",
                    attempt, MAX_RETRIES, e, delay,
                )
                time.sleep(delay)
    raise TigrisError(f"Tigris exhausted retries for {key}: {last_exc}") from last_exc


def delete_pdf(s3: Any, *, draft_id: str, prefix: str = "wr2-pdf") -> None:
    """Best-effort delete of LEGACY single-key path. Never raises.

    DEPRECATED: does NOT delete content-addressed keys. Use delete_pdf_by_key()
    with the key returned from upload_pdf().
    """
    key = f"{prefix}/{draft_id}.pdf"
    try:
        s3.delete_object(Bucket=BUCKET, Key=key)
        logger.info("Tigris delete OK: %s", key)
    except Exception as e:  # noqa: BLE001
        logger.warning("Tigris delete failed (swallowed): %s — %s", key, e)


def delete_pdf_by_key(s3: Any, *, key: str) -> None:
    """Best-effort delete of an exact S3 key (content-addressed or legacy). Never raises."""
    try:
        s3.delete_object(Bucket=BUCKET, Key=key)
        logger.info("Tigris delete_by_key OK: %s", key)
    except Exception as e:  # noqa: BLE001
        logger.warning("Tigris delete_by_key failed (swallowed): %s — %s", key, e)


def build_public_url(draft_id: str, *, prefix: str = "wr2-pdf") -> str:
    """Legacy URL builder. Returns predictable path even for content-addressed
    keys are now used by upload_pdf; this helper kept for old callers that
    pre-date the content-addressed change."""
    return f"https://{PUBLIC_HOST}/{prefix}/{draft_id}.pdf"
