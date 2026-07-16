#!/usr/bin/env python3
"""One-shot backfill — migrate legacy `data:` URI client avatars to Tigris.

Context (2026-07-16): `clients.avatar_url` must hold a storage URL. 19 of
1744 non-deleted rows still hold an inline base64 `data:` URI — legacy rows
that pre-date the validator added by PR #2494 / the `upload_client_avatar`
endpoint (apps/backend-rag/backend/app/routers/crm_clients.py). They are
currently harmless (the list endpoint nulls them out, `GET /{id}/avatar`
serves them, the edit form no longer echoes them back) but they bloat rows
and are the reason the whole avatar-generator-close saga exists.

This script decodes each poisoned row's `data:` payload, uploads the bytes
to Tigris using the EXACT SAME key/URL convention as the live upload
endpoint (`client-avatar/{client_id}/{sha8}.{ext}`, sha8 = first 8 hex of
sha256 of the bytes), and rewrites `avatar_url` to the resulting public
`https://` URL. After this runs clean, `avatar_url LIKE 'data:%'` should
match zero rows.

DRY-RUN IS THE DEFAULT — zero writes (no Tigris put_object, no UPDATE)
unless `--apply` is passed. Every row is reported with its would-be
outcome either way.

Idempotent + resumable: the candidate query filters on `avatar_url LIKE
'data:%' AND deleted_at IS NULL`, so a row already migrated (by this run or
a prior partial run) no longer matches and is left alone on re-run. One bad
row (malformed data URI, unsupported mime, upload failure, verify mismatch)
never aborts the batch — every row gets its own try/except and its own
line in the report.

PII discipline (hard rule): these are photos of real clients. This script
NEVER logs, prints, or writes the base64 payload or any decoded image
bytes anywhere — not to stdout, not to the JSONL report. Only client_id,
byte length, mime type, and the resulting storage key/URL are recorded.

Usage:
    # dry-run (default, no writes) — report only
    cd apps/backend-rag && source .venv/bin/activate
    DATABASE_URL="postgresql://..." PYTHONPATH=. \\
        python ../../scripts/backfill_avatar_data_uris.py

    # apply — uploads to Tigris + rewrites avatar_url
    DATABASE_URL="postgresql://..." PYTHONPATH=. \\
        python ../../scripts/backfill_avatar_data_uris.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import hashlib
import json
import logging
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill.avatar_data_uris")

# ── path bootstrap (mirrors scripts/wr2_ig_publish.py) ──────────────────
# `backend` is NOT editable-installed in the venv, so put apps/backend-rag
# on sys.path explicitly, derived from this file's location so the script
# is invocation-agnostic. Repo root = one parent up from scripts/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "apps" / "backend-rag"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


def parse_data_uri(avatar_url: str) -> tuple[str, bytes] | None:
    """Decode a `data:[<mediatype>][;base64],<payload>` URI.

    Mirrors the decode logic already live in `GET /{client_id}/avatar`
    (apps/backend-rag/backend/app/routers/crm_clients.py:1020-1029) so a
    backfilled avatar decodes identically to how it would have been served
    from the legacy inline path. Returns None on any malformed input (no
    comma, bad base64) — NEVER raises.
    """
    if not avatar_url.startswith("data:") or "," not in avatar_url:
        return None
    header, b64_payload = avatar_url.split(",", 1)
    mime = "image/jpeg"
    if header.startswith("data:") and ";" in header:
        mime = header[len("data:") :].split(";", 1)[0] or mime
    try:
        raw = base64.b64decode(b64_payload, validate=True)
    except (ValueError, binascii.Error):
        return None
    if not raw:
        return None
    return mime.lower(), raw


def derive_key(client_id: int, raw: bytes, ext: str) -> str:
    """`client-avatar/{client_id}/{sha8}.{ext}` — SAME convention as
    `upload_client_avatar()` (crm_clients.py:1094-1095) so backfilled
    avatars are indistinguishable from freshly-uploaded ones.
    """
    sha8 = hashlib.sha256(raw).hexdigest()[:8]
    return f"client-avatar/{client_id}/{sha8}.{ext}"


@dataclass
class RowResult:
    client_id: int
    status: str
    mime: str | None = None
    byte_length: int | None = None
    key: str | None = None
    url: str | None = None
    reason: str | None = None

    def to_report_dict(self) -> dict[str, Any]:
        # Only ever client_id / status / mime / byte_length / key / url /
        # reason — never the data: URI or decoded bytes (PII discipline).
        return {
            "client_id": self.client_id,
            "status": self.status,
            "mime": self.mime,
            "byte_length": self.byte_length,
            "key": self.key,
            "url": self.url,
            "reason": self.reason,
        }


async def put_object_with_retry(
    tigris_mod: Any, s3: Any, key: str, body: bytes, content_type: str
) -> None:
    """Upload with the same retry/backoff policy as `_tigris.upload_pdf` /
    `upload_png` — reused via the module's own retry primitives
    (`MAX_RETRIES`, `BACKOFF_BASE_S`, `_is_transient`, `TigrisError`)
    rather than duplicating a whole upload function whose key convention
    doesn't match ours.
    """
    last_exc: Exception | None = None
    for attempt in range(1, tigris_mod.MAX_RETRIES + 1):
        try:
            s3.put_object(
                Bucket=tigris_mod.BUCKET,
                Key=key,
                Body=body,
                ContentType=content_type,
                ACL="public-read",
            )
            return
        except Exception as e:
            last_exc = e
            if not tigris_mod._is_transient(e):
                raise tigris_mod.TigrisError(f"Tigris non-transient error: {e}") from e
            if attempt < tigris_mod.MAX_RETRIES:
                delay = tigris_mod.BACKOFF_BASE_S * (2 ** (attempt - 1))
                logger.warning(
                    "Tigris transient error attempt %d/%d for key=%s — sleep %.1fs",
                    attempt,
                    tigris_mod.MAX_RETRIES,
                    key,
                    delay,
                )
                await asyncio.sleep(delay)
    raise tigris_mod.TigrisError(f"Tigris exhausted retries for {key}: {last_exc}") from last_exc


async def process_row(
    *,
    client_id: int,
    avatar_url: str,
    apply: bool,
    content_types: dict[str, str],
    tigris_mod: Any,
    s3: Any,
    conn: Any,
) -> RowResult:
    """Migrate one poisoned row. Never raises — every failure mode returns
    a RowResult with a status the caller can count and report on.
    """
    parsed = parse_data_uri(avatar_url)
    if parsed is None:
        logger.warning("client_id=%s SKIP malformed data URI", client_id)
        return RowResult(
            client_id=client_id,
            status="skipped_malformed",
            reason="malformed data URI (no comma or bad base64)",
        )

    mime, raw = parsed
    ext = content_types.get(mime)
    if ext is None:
        logger.warning("client_id=%s SKIP unsupported mime=%s bytes=%d", client_id, mime, len(raw))
        return RowResult(
            client_id=client_id,
            status="skipped_unsupported_mime",
            mime=mime,
            byte_length=len(raw),
            reason=f"unsupported mime type: {mime}",
        )

    key = derive_key(client_id, raw, ext)
    url = f"https://{tigris_mod.PUBLIC_HOST}/{key}"

    if not apply:
        logger.info(
            "client_id=%s DRY-RUN would upload mime=%s bytes=%d -> %s",
            client_id,
            mime,
            len(raw),
            url,
        )
        return RowResult(
            client_id=client_id,
            status="would_migrate",
            mime=mime,
            byte_length=len(raw),
            key=key,
            url=url,
        )

    try:
        await put_object_with_retry(tigris_mod, s3, key, raw, mime)
    except Exception as e:
        logger.error("client_id=%s Tigris upload FAILED: %s", client_id, e)
        return RowResult(
            client_id=client_id,
            status="failed_upload",
            mime=mime,
            byte_length=len(raw),
            key=key,
            reason=str(e)[:200],
        )

    try:
        await conn.execute(
            "UPDATE clients SET avatar_url = $1, updated_at = NOW() WHERE id = $2",
            url,
            client_id,
        )
    except Exception as e:
        logger.error("client_id=%s DB UPDATE FAILED (object already in Tigris at %s): %s", client_id, key, e)
        return RowResult(
            client_id=client_id,
            status="failed_db",
            mime=mime,
            byte_length=len(raw),
            key=key,
            url=url,
            reason=str(e)[:200],
        )

    # Verify by readback — never trust the UPDATE's rowcount alone (probe
    # the work, not the proxy).
    try:
        verify = await conn.fetchval("SELECT avatar_url FROM clients WHERE id = $1", client_id)
    except Exception as e:
        logger.error("client_id=%s verify-readback query FAILED: %s", client_id, e)
        return RowResult(
            client_id=client_id,
            status="failed_verify",
            mime=mime,
            byte_length=len(raw),
            key=key,
            url=url,
            reason=f"readback query error: {str(e)[:160]}",
        )

    if not verify or not verify.startswith("https://"):
        logger.error("client_id=%s VERIFY MISMATCH: readback does not start with https://", client_id)
        return RowResult(
            client_id=client_id,
            status="failed_verify",
            mime=mime,
            byte_length=len(raw),
            key=key,
            url=url,
            reason="readback does not start with https://",
        )

    logger.info("client_id=%s MIGRATED mime=%s bytes=%d -> %s", client_id, mime, len(raw), url)
    return RowResult(client_id=client_id, status="migrated", mime=mime, byte_length=len(raw), key=key, url=url)


async def run(apply: bool, out_path: Path) -> int:
    import asyncpg

    from backend.app.routers.crm_clients import _AVATAR_CONTENT_TYPES
    from backend.services.canva_renderer_v2 import _tigris

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set — refusing to run (never hardcode credentials)")
        return 1

    conn = await asyncpg.connect(dsn, timeout=10)
    results: list[RowResult] = []
    try:
        rows = await conn.fetch(
            "SELECT id, avatar_url FROM clients WHERE avatar_url LIKE 'data:%' AND deleted_at IS NULL ORDER BY id"
        )
        logger.info("Found %d poisoned row(s) (avatar_url LIKE 'data:%%' AND deleted_at IS NULL)", len(rows))
        if not rows:
            logger.info("Nothing to backfill.")
            return 0

        # Only touch boto3 (needs AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY)
        # when we're actually going to upload — dry-run must not require
        # storage credentials at all.
        s3 = _tigris.get_s3_client() if apply else None

        for row in rows:
            result = await process_row(
                client_id=row["id"],
                avatar_url=row["avatar_url"],
                apply=apply,
                content_types=_AVATAR_CONTENT_TYPES,
                tigris_mod=_tigris,
                s3=s3,
                conn=conn,
            )
            results.append(result)
    finally:
        await conn.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for r in results:
            fh.write(json.dumps(r.to_report_dict()) + "\n")

    summary = Counter(r.status for r in results)
    logger.info(
        "SUMMARY apply=%s total=%d %s report=%s",
        apply,
        len(results),
        dict(summary),
        out_path,
    )
    if not apply:
        logger.info("DRY-RUN complete — zero writes performed. Re-run with --apply to migrate for real.")

    hard_failures = sum(
        1
        for r in results
        if r.status in ("failed_upload", "failed_db", "failed_verify")
    )
    return 1 if hard_failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform Tigris uploads + DB writes (default: dry-run, zero writes)",
    )
    parser.add_argument(
        "--out",
        default=str(
            Path.home() / "logs" / f"backfill-avatar-data-uris-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
        ),
        help="JSONL report path (client_id/status/mime/byte_length/key/url/reason only — never raw bytes)",
    )
    args = parser.parse_args()
    return asyncio.run(run(apply=args.apply, out_path=Path(args.out)))


if __name__ == "__main__":
    sys.exit(main())
