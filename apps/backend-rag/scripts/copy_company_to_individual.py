"""
Copy Company docs → Individual_CRM/02_Company
===============================================
For each client linked to a company (client_company_links):
  1. Find client's Individual_CRM folder (google_drive_folder_id)
  2. Find or create 02_Company subfolder
  3. Find company's Company_CRM folder (google_drive_folder_id)
  4. List company files (00_AKTA, 01_NIB, 02_NPWP, 03_Profile_Perseroan)
  5. Copy each file into client's 02_Company (skip if already exists by name)

Run:
    python3 scripts/copy_company_to_individual.py [--dry-run] [--limit N]
"""

import argparse
import asyncio
import logging
import os
import time

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DB = (
    os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")
    or "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable"
)

OAUTH_CLIENT_ID = "930328104463-m3g4gq72095rip08269kvt8s7et9ev12.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "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"
OAUTH_REFRESH_TOKEN = "1//0gbiun0bBkNVCCgYIARAAGBASNwF-L9IrGvLMkg0QQ7fz0x98C1zyFqsCvzyijl7NjxUXoJ8K_-BAN8t-ZuQyT5uIv2iVJUPSiMA"

COMPANY_SUBFOLDERS = ["00_AKTA", "01_NIB", "02_NPWP", "03_Profile_Perseroan"]

_token: str = ""
_token_expiry: float = 0


async def get_token(client: httpx.AsyncClient) -> str:
    global _token, _token_expiry
    if _token and time.time() < _token_expiry - 60:
        return _token
    resp = await client.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "refresh_token": OAUTH_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    _token = data["access_token"]
    _token_expiry = time.time() + data.get("expires_in", 3600)
    return _token


async def list_subfolders(client: httpx.AsyncClient, folder_id: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {await get_token(client)}"}
    r = await client.get(
        "https://www.googleapis.com/drive/v3/files",
        headers=headers,
        params={
            "q": f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "fields": "files(id,name)",
            "pageSize": "50",
        },
    )
    r.raise_for_status()
    return {f["name"]: f["id"] for f in r.json().get("files", [])}


async def list_files(client: httpx.AsyncClient, folder_id: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {await get_token(client)}"}
    files = []
    pt = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "fields": "nextPageToken,files(id,name,mimeType)",
            "pageSize": "200",
        }
        if pt:
            params["pageToken"] = pt
        r = await client.get(
            "https://www.googleapis.com/drive/v3/files", headers=headers, params=params
        )
        r.raise_for_status()
        d = r.json()
        files.extend(d.get("files", []))
        pt = d.get("nextPageToken")
        if not pt:
            break
    return files


async def create_folder(client: httpx.AsyncClient, name: str, parent_id: str) -> str:
    headers = {"Authorization": f"Bearer {await get_token(client)}"}
    r = await client.post(
        "https://www.googleapis.com/drive/v3/files",
        headers=headers,
        params={"supportsAllDrives": "true"},
        json={
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        },
    )
    r.raise_for_status()
    return r.json()["id"]


async def copy_file(
    client: httpx.AsyncClient, file_id: str, dest_folder_id: str, new_name: str
) -> str | None:
    """Copy a file to dest folder. Returns new file ID or None on error."""
    headers = {"Authorization": f"Bearer {await get_token(client)}"}
    try:
        r = await client.post(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/copy",
            headers=headers,
            params={"supportsAllDrives": "true"},
            json={"name": new_name, "parents": [dest_folder_id]},
        )
        if r.status_code == 200:
            return r.json().get("id")
        logger.warning(f"    Copy failed: {r.status_code} {r.text[:100]}")
        return None
    except Exception as e:
        logger.warning(f"    Copy error: {e}")
        return None


async def main(dry_run: bool, limit: int) -> None:
    logger.info(f"{'DRY RUN — ' if dry_run else ''}Copy Company docs → Individual 02_Company")

    conn = await asyncpg.connect(DB)

    try:
        # Get all client-company links where both have Drive folders
        links = await conn.fetch(
            """
            SELECT cl.id as client_id, cl.full_name, cl.google_drive_folder_id as client_drive,
                   c.id as company_id, c.company_name, c.google_drive_folder_id as company_drive,
                   ccl.role
            FROM clients cl
            JOIN client_company_links ccl ON ccl.client_id = cl.id
            JOIN companies c ON c.id = ccl.company_id
            WHERE cl.google_drive_folder_id IS NOT NULL
              AND c.google_drive_folder_id IS NOT NULL
              AND cl.deleted_at IS NULL
            ORDER BY cl.id
            LIMIT $1
        """,
            limit,
        )

        logger.info(f"Links to process: {len(links)}")
        totals = {"copied": 0, "skipped": 0, "errors": 0, "clients": 0}

        async with httpx.AsyncClient(timeout=30) as http:
            await get_token(http)

            processed_clients = set()

            for i, link in enumerate(links):
                client_id = link["client_id"]
                client_name = link["full_name"]
                company_name = link["company_name"]
                client_drive = link["client_drive"]
                company_drive = link["company_drive"]

                logger.info(f"\n[{i + 1}/{len(links)}] {client_name} → {company_name}")

                # Find or create 02_Company in client's Individual folder
                client_subs = await list_subfolders(http, client_drive)
                company_sub_id = client_subs.get("02_Company")
                if not company_sub_id:
                    if not dry_run:
                        try:
                            company_sub_id = await create_folder(http, "02_Company", client_drive)
                        except Exception as e:
                            logger.warning(f"  Cannot create 02_Company: {e}")
                            totals["errors"] += 1
                            continue
                    logger.info("  Created 02_Company")
                    totals["clients"] += 1

                # Get existing files in 02_Company (to avoid duplicates)
                existing = set()
                if company_sub_id and not dry_run:
                    existing_files = await list_files(http, company_sub_id)
                    existing = {f["name"] for f in existing_files}

                # List company's standard subfolders and their files
                company_subs = await list_subfolders(http, company_drive)
                copied_this = 0

                for sub_name in COMPANY_SUBFOLDERS:
                    sub_id = company_subs.get(sub_name)
                    if not sub_id:
                        continue

                    files = await list_files(http, sub_id)
                    for f in files:
                        if f["name"] in existing:
                            totals["skipped"] += 1
                            continue

                        if not dry_run:
                            result = await copy_file(http, f["id"], company_sub_id, f["name"])
                            if result:
                                totals["copied"] += 1
                                copied_this += 1
                                existing.add(f["name"])
                            else:
                                totals["errors"] += 1
                        else:
                            totals["copied"] += 1
                            copied_this += 1

                if copied_this > 0:
                    logger.info(f"  +{copied_this} files copied")

                if client_id not in processed_clients:
                    processed_clients.add(client_id)

                # Rate limit
                if (i + 1) % 10 == 0:
                    await asyncio.sleep(0.5)

                if (i + 1) % 50 == 0:
                    logger.info(
                        f"\n--- {i + 1}/{len(links)} | copied={totals['copied']} skipped={totals['skipped']} ---\n"
                    )

        logger.info(f"\n{'=' * 50}")
        logger.info(f"Copy Company → Individual {'(DRY RUN)' if dry_run else 'COMPLETE'}")
        logger.info(f"  Links processed: {len(links)}")
        logger.info(f"  Clients        : {len(processed_clients)}")
        logger.info(f"  Files copied   : {totals['copied']}")
        logger.info(f"  Skipped (exist): {totals['skipped']}")
        logger.info(f"  Errors         : {totals['errors']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, limit=args.limit))
