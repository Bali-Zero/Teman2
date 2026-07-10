#!/usr/bin/env python3
"""One-shot backfill: migrate inline base64 data:URI avatars to Tigris storage.

For every client whose avatar_url is a `data:` URI, decode the image, upload it
to the Tigris bucket (content-addressed key), and replace avatar_url with the
public https URL. Idempotent: rows already on https are skipped; re-running only
processes remaining data: rows.

Usage (on Pro, from apps/backend-rag with venv active):
    PYTHONPATH=. python3 backfill_avatars.py --dry-run   # report only
    PYTHONPATH=. python3 backfill_avatars.py --apply     # perform migration
"""
import argparse
import asyncio
import base64
import binascii
import hashlib
import os
import pathlib
import sys

import asyncpg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

_EXT = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp"}


def dburl():
    for cand in [pathlib.Path.home() / ".nuzantara-secrets.env"]:
        if cand.exists():
            for line in cand.read_text().splitlines():
                if line.startswith("DATABASE_URL_LOCAL="):
                    return line.split("=", 1)[1].strip().strip("'").strip('"')
    return os.environ.get("DATABASE_URL_LOCAL")


def parse_data_uri(uri: str):
    """Return (content_type, ext, raw_bytes) or None if not a valid image data URI."""
    if not uri.startswith("data:"):
        return None
    try:
        header, b64 = uri.split(",", 1)
    except ValueError:
        return None
    meta = header[len("data:"):]
    content_type = meta.split(";", 1)[0].lower() if meta else "image/jpeg"
    ext = _EXT.get(content_type)
    if ext is None:
        return None
    try:
        raw = base64.b64decode(b64)
    except (binascii.Error, ValueError):
        return None
    if not raw:
        return None
    return content_type, ext, raw


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="perform the migration (default: dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="report only (default)")
    ap.add_argument("--limit", type=int, default=100000)
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    from backend.services.canva_renderer_v2 import _tigris

    con = await asyncpg.connect(dburl(), timeout=30)
    rows = await con.fetch(
        "SELECT id, avatar_url FROM clients "
        "WHERE deleted_at IS NULL AND avatar_url LIKE 'data:%' "
        "ORDER BY id LIMIT $1",
        args.limit,
    )
    print(f"data:URI avatars to migrate: {len(rows)}  (mode={'APPLY' if apply else 'DRY-RUN'})")

    s3 = _tigris.get_s3_client() if apply else None
    migrated = skipped = failed = 0
    for r in rows:
        cid, uri = r["id"], r["avatar_url"]
        parsed = parse_data_uri(uri)
        if parsed is None:
            print(f"  client {cid}: UNPARSEABLE data URI (len={len(uri)}) — skip")
            skipped += 1
            continue
        content_type, ext, raw = parsed
        sha8 = hashlib.sha256(raw).hexdigest()[:8]
        key = f"client-avatar/{cid}/{sha8}.{ext}"
        public_url = f"https://{_tigris.PUBLIC_HOST}/{key}"
        if not apply:
            print(f"  client {cid}: {len(raw)} B {content_type} -> {public_url}")
            migrated += 1
            continue
        try:
            s3.put_object(Bucket=_tigris.BUCKET, Key=key, Body=raw,
                          ContentType=content_type, ACL="public-read")
            await con.execute(
                "UPDATE clients SET avatar_url=$1, updated_at=NOW() WHERE id=$2",
                public_url, cid,
            )
            migrated += 1
            if migrated % 25 == 0:
                print(f"  ... {migrated} migrated")
        except Exception as e:
            print(f"  client {cid}: FAILED {type(e).__name__}: {e}")
            failed += 1

    print(f"\nDONE: migrated={migrated} skipped={skipped} failed={failed}")
    # verify: how many data: avatars remain
    remain = await con.fetchval(
        "SELECT count(*) FROM clients WHERE deleted_at IS NULL AND avatar_url LIKE 'data:%'"
    )
    print(f"data:URI avatars remaining in DB: {remain}")
    await con.close()


asyncio.run(main())
