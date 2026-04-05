import asyncio
import hashlib
import os

import asyncpg


async def backfill_hash():
    db_url = os.environ.get("DATABASE_URL", "")
    conn = await asyncpg.connect(db_url)

    docs = await conn.fetch("""
        SELECT id, file_id, file_name FROM documents
        WHERE content_hash IS NULL AND file_id IS NOT NULL AND is_archived IS NOT TRUE
        ORDER BY id LIMIT 200
    """)
    print(f"Batch: {len(docs)} docs to hash")

    try:
        from backend.services.integrations.service_account_drive_service import (
            ServiceAccountDriveService,
        )
        svc = ServiceAccountDriveService()
        print("Drive SA connected")
    except Exception as e:
        print(f"SA init failed: {e}")
        await conn.close()
        return

    hashed = 0
    errors = 0
    for doc in docs:
        fid = doc["file_id"]
        fname = doc["file_name"]
        did = doc["id"]
        try:
            request = svc.service.files().get_media(fileId=fid)
            content = await asyncio.to_thread(request.execute)
            h = hashlib.md5(content).hexdigest()
            await conn.execute("UPDATE documents SET content_hash = $1 WHERE id = $2", h, did)
            hashed += 1
            if hashed % 50 == 0:
                print(f"  hashed {hashed}/{len(docs)}...")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ERROR doc {did} ({fname}): {str(e)[:80]}")

    print(f"\nDone: {hashed} hashed, {errors} errors out of {len(docs)}")

    # Check for hash duplicates
    dupes = await conn.fetch("""
        SELECT client_id, content_hash, COUNT(*) as cnt, array_agg(id ORDER BY created_at DESC) as ids
        FROM documents
        WHERE content_hash IS NOT NULL AND is_archived IS NOT TRUE
        GROUP BY client_id, content_hash HAVING COUNT(*) > 1
        LIMIT 50
    """)
    if dupes:
        print(f"\nHash duplicates found: {len(dupes)} groups")
        archived = 0
        for d in dupes:
            oldest = d["ids"][1:]
            await conn.execute("UPDATE documents SET is_archived = TRUE WHERE id = ANY($1::int[])", oldest)
            archived += len(oldest)
        print(f"Archived {archived} hash-based duplicates")
    else:
        print("\nNo hash duplicates found in this batch")

    remaining = await conn.fetchval("SELECT COUNT(*) FROM documents WHERE content_hash IS NULL AND file_id IS NOT NULL AND is_archived IS NOT TRUE")
    print(f"Remaining without hash: {remaining}")

    await conn.close()

asyncio.run(backfill_hash())
