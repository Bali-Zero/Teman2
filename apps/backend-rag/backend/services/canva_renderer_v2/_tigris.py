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


def upload_pdf(s3: Any, pdf_path: Path, *, draft_id: str, prefix: str = "wr2-pdf") -> str:
    """Upload PDF to s3://BUCKET/{prefix}/{draft_id}.pdf, return public URL."""
    key = f"{prefix}/{draft_id}.pdf"
    body = pdf_path.read_bytes()

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
            logger.info("Tigris upload OK: %s (attempt %d)", key, attempt)
            return build_public_url(draft_id, prefix=prefix)
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
    """Best-effort delete. Never raises (S3 lifecycle is the safety net)."""
    key = f"{prefix}/{draft_id}.pdf"
    try:
        s3.delete_object(Bucket=BUCKET, Key=key)
        logger.info("Tigris delete OK: %s", key)
    except Exception as e:  # noqa: BLE001
        logger.warning("Tigris delete failed (swallowed): %s — %s", key, e)


def build_public_url(draft_id: str, *, prefix: str = "wr2-pdf") -> str:
    return f"https://{PUBLIC_HOST}/{prefix}/{draft_id}.pdf"
