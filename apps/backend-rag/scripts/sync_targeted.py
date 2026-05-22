"""
Sync Company and Tax docs -> Individual_CRM (via Shortcuts)
=============================================================
For each client linked to a company:
  1. Find client's Individual_CRM folder
  2. Create 02_Company and 03_Tax subfolders if missing
  3. Mirror subfolders from Company_CRM (00_AKTA, 01_NIB, etc.) into 02_Company
  4. AI Routing: classify stray files (in root or 99_Misc) via Heuristics and Ollama, route to canonical folders.
  5. Mirror subfolders from TAX DEPARTMENT into 03_Tax and create shortcuts there

Run:
    python3 scripts/sync_shortcuts_to_individual.py [--dry-run] [--limit N]
"""

import argparse
import asyncio
import io
import json
import logging
import os
import subprocess
import time

import asyncpg
import httpx
from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DB = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")
if "flycast" in DB and not os.getenv("FLY_APP_NAME"):
    DB = DB.replace("nuzantara-postgres.flycast:5432", "127.0.0.1:15432")
elif "localhost" in DB:
    DB = DB.replace("localhost", "127.0.0.1")

if not DB:
    DB = "postgresql://backend_rag_v2:2zEjit43IF6gNUV@127.0.0.1:15432/nuzantara_rag?sslmode=disable"

OAUTH_CLIENT_ID = "930328104463-m3g4gq72095rip08269kvt8s7et9ev12.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "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"
OAUTH_REFRESH_TOKEN = "1//0gbiun0bBkNVCCgYIARAAGBASNwF-L9IrGvLMkg0QQ7fz0x98C1zyFqsCvzyijl7NjxUXoJ8K_-BAN8t-ZuQyT5uIv2iVJUPSiMA"

COMPANY_SUBFOLDERS = ["00_AKTA", "01_NIB", "02_NPWP", "03_Profile_Perseroan"]
BALI_ZERO_ROOT_ID = "1hkOeV03YM5-sHbQhswYz809jsrnwC0At"

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
            "pageSize": "1000",
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
            "pageSize": "1000",
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


async def create_shortcut(
    client: httpx.AsyncClient, target_id: str, dest_folder_id: str, new_name: str
) -> str | None:
    headers = {"Authorization": f"Bearer {await get_token(client)}"}
    try:
        r = await client.post(
            "https://www.googleapis.com/drive/v3/files",
            headers=headers,
            params={"supportsAllDrives": "true"},
            json={
                "name": new_name,
                "mimeType": "application/vnd.google-apps.shortcut",
                "parents": [dest_folder_id],
                "shortcutDetails": {"targetId": target_id},
            },
        )
        if r.status_code == 200:
            return r.json().get("id")
        logger.warning(f"    Shortcut creation failed: {r.status_code} {r.text[:100]}")
        return None
    except Exception as e:
        logger.warning(f"    Shortcut error: {e}")
        return None


async def build_tax_folder_map(client: httpx.AsyncClient) -> dict[str, str]:
    logger.info("Building Tax folder map...")
    tax_map = {}
    root_subs = await list_subfolders(client, BALI_ZERO_ROOT_ID)
    tax_dept_id = root_subs.get("TAX DEPARTMENT")
    if not tax_dept_id:
        return tax_map
    tax_subs = await list_subfolders(client, tax_dept_id)
    members_id = tax_subs.get("Members")
    if not members_id:
        return tax_map
    consultants = await list_subfolders(client, members_id)
    for cons_name, cons_id in consultants.items():
        company_folders = await list_subfolders(client, cons_id)
        for comp_name, comp_id in company_folders.items():
            norm_name = comp_name.strip().lower()
            tax_map[norm_name] = comp_id
    logger.info(f"Built tax map with {len(tax_map)} entries.")
    return tax_map


async def classify_with_ollama(text: str) -> str:
    prompt = f"""Sei un classificatore automatico di documenti legali indonesiani.
Regole:
1. Devi rispondere SOLO con il nome esatto della cartella tra queste: '00_AKTA', '01_NIB', '02_NPWP', '03_Profile_Perseroan', o '99_Misc'.
2. Non aggiungere nient'altro.

Testo del documento:
{text[:2500]}

Rispondi con il nome della cartella:"""

    payload = json.dumps({"model": "qwen2.5:7b", "prompt": prompt, "stream": False})
    cmd = [
        "ssh", "mini",
        "curl", "-s", "-X", "POST", "http://localhost:11434/api/generate",
        "-d", "@-"
    ]

    # We use asyncio.to_thread to not block the event loop
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: subprocess.run(cmd, input=payload, capture_output=True, text=True)
    )
    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            return data.get("response", "99_Misc").strip()
        except Exception:
            pass
    return "99_Misc"


async def route_stray_file(http: httpx.AsyncClient, f: dict, dest_parent_id: str, dest_subs: dict, dry_run: bool) -> str:
    filename = f["name"]
    lower_name = filename.lower()

    # Heuristic Router
    category = None
    if "npwp" in lower_name:
        category = "02_NPWP"
    elif "nib" in lower_name:
        category = "01_NIB"
    elif "akta" in lower_name:
        category = "00_AKTA"
    elif "profile" in lower_name or "profil" in lower_name:
        category = "03_Profile_Perseroan"

    # AI Router (se ambiguo e PDF)
    if not category:
        if f["mimeType"] == "application/pdf":
            logger.info(f"      [AI Router] Downloading PDF to classify: {filename}")
            token = await get_token(http)
            resp = await http.get(
                f"https://www.googleapis.com/drive/v3/files/{f['id']}?alt=media",
                headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code == 200:
                try:
                    reader = PdfReader(io.BytesIO(resp.content))
                    text = "".join([page.extract_text() + "\n" for page in reader.pages[:2]])
                    category = await classify_with_ollama(text)
                    if category not in COMPANY_SUBFOLDERS:
                        category = "99_Misc"
                    logger.info(f"      [AI Router] Classified as {category}")
                except Exception as e:
                    logger.error(f"      [AI Router] Error parsing PDF {filename}: {e}")
                    category = "99_Misc"
            else:
                logger.error(f"      [AI Router] Failed to download {filename}: {resp.status_code}")
                category = "99_Misc"
        else:
            category = "99_Misc"

    # Get or create the destination subfolder
    dest_sub_id = dest_subs.get(category)
    if not dest_sub_id:
        if not dry_run:
            dest_sub_id = await create_folder(http, category, dest_parent_id)
            dest_subs[category] = dest_sub_id
            logger.info(f"    Created canonical/misc folder: {category}")
        else:
            dest_sub_id = f"DRY_RUN_{category}"
            dest_subs[category] = dest_sub_id

    return dest_sub_id


async def process_subfolders(
    http: httpx.AsyncClient,
    totals: dict,
    dry_run: bool,
    src_parent_id: str,
    dest_parent_id: str,
    subfolders_to_sync: list[str] = None,
    enable_ai_routing: bool = False
):
    src_subs = await list_subfolders(http, src_parent_id)
    dest_subs = await list_subfolders(http, dest_parent_id) if not dry_run else {}

    # Also sync root files
    root_files = await list_files(http, src_parent_id)
    if root_files:
        for f in root_files:
            target_dest_id = dest_parent_id
            if enable_ai_routing:
                target_dest_id = await route_stray_file(http, f, dest_parent_id, dest_subs, dry_run)

            # Check existing files in target_dest_id
            existing = set()
            if not dry_run and not target_dest_id.startswith("DRY_RUN"):
                target_files = await list_files(http, target_dest_id)
                existing = {x["name"] for x in target_files}

            if f["name"] in existing:
                totals["skipped"] += 1
                continue

            if not dry_run:
                if await create_shortcut(http, f["id"], target_dest_id, f["name"]):
                    totals["shortcuts_created"] += 1
                else:
                    totals["errors"] += 1
            else:
                totals["shortcuts_created"] += 1
                logger.info(f"      [DRY RUN] Would create shortcut for {f['name']} -> {target_dest_id}")

    # Sync subfolders
    for sub_name, src_sub_id in src_subs.items():
        if subfolders_to_sync is not None and sub_name not in subfolders_to_sync:
            if enable_ai_routing:
                # Process this non-canonical folder as a source of stray files
                stray_files = await list_files(http, src_sub_id)
                for f in stray_files:
                    target_dest_id = await route_stray_file(http, f, dest_parent_id, dest_subs, dry_run)
                    existing = set()
                    if not dry_run and not target_dest_id.startswith("DRY_RUN"):
                        target_files = await list_files(http, target_dest_id)
                        existing = {x["name"] for x in target_files}

                    if f["name"] in existing:
                        totals["skipped"] += 1
                        continue

                    if not dry_run:
                        if await create_shortcut(http, f["id"], target_dest_id, f["name"]):
                            totals["shortcuts_created"] += 1
                        else:
                            totals["errors"] += 1
                    else:
                        totals["shortcuts_created"] += 1
                        logger.info(f"      [DRY RUN] Would route stray {f['name']} (from {sub_name}) -> {target_dest_id}")
            continue

        dest_sub_id = dest_subs.get(sub_name)
        if not dest_sub_id:
            if not dry_run:
                try:
                    dest_sub_id = await create_folder(http, sub_name, dest_parent_id)
                    dest_subs[sub_name] = dest_sub_id
                    logger.info(f"    Created subfolder: {sub_name}")
                except Exception as e:
                    logger.warning(f"    Cannot create subfolder {sub_name}: {e}")
                    totals["errors"] += 1
                    continue
            else:
                dest_sub_id = f"DRY_RUN_{sub_name}"
                dest_subs[sub_name] = dest_sub_id

        existing_files = set()
        if not dry_run and dest_sub_id and not dest_sub_id.startswith("DRY_RUN"):
            files = await list_files(http, dest_sub_id)
            existing_files = {f["name"] for f in files}

        files = await list_files(http, src_sub_id)
        for f in files:
            if f["name"] in existing_files:
                totals["skipped"] += 1
                continue

            if not dry_run:
                result = await create_shortcut(http, f["id"], dest_sub_id, f["name"])
                if result:
                    totals["shortcuts_created"] += 1
                    existing_files.add(f["name"])
                else:
                    totals["errors"] += 1
            else:
                totals["shortcuts_created"] += 1
                logger.info(f"      [DRY RUN] Would shortcut {f['name']} -> {sub_name}")


async def main(dry_run: bool, limit: int) -> None:
    logger.info(f"{'DRY RUN — ' if dry_run else ''}Sync Company/Tax -> Individual via Shortcuts")
    conn = await asyncpg.connect(DB)

    try:
        links = await conn.fetch(
            """
            SELECT cl.id as client_id, cl.full_name, cl.google_drive_folder_id as client_drive,
                   c.id as company_id, c.company_name, c.google_drive_folder_id as company_drive
            FROM clients cl
            JOIN client_company_links ccl ON ccl.client_id = cl.id
            JOIN companies c ON c.id = ccl.company_id
            WHERE cl.google_drive_folder_id IS NOT NULL AND cl.id IN (712, 11136, 11197)
              AND cl.deleted_at IS NULL
            ORDER BY cl.id
            LIMIT $1
        """,
            limit,
        )

        logger.info(f"Links to process: {len(links)}")
        totals = {"shortcuts_created": 0, "skipped": 0, "errors": 0, "clients": 0}

        async with httpx.AsyncClient(timeout=30) as http:
            tax_map = await build_tax_folder_map(http)
            processed_clients = set()

            for i, link in enumerate(links):
                client_id = link["client_id"]
                client_name = link["full_name"]
                company_name = link["company_name"]
                client_drive = link["client_drive"]
                company_drive = link["company_drive"]

                logger.info(f"\n[{i + 1}/{len(links)}] {client_name} → {company_name}")
                client_subs = await list_subfolders(http, client_drive)

                # --- COMPANY DOCS (02_Company) ---
                company_sub_id = client_subs.get("02_Company")
                if not company_sub_id:
                    if not dry_run:
                        try:
                            company_sub_id = await create_folder(http, "02_Company", client_drive)
                        except Exception as e:
                            logger.warning(f"  Cannot create 02_Company: {e}")
                            totals["errors"] += 1
                            continue
                    else:
                        company_sub_id = "DRY_RUN_02_Company"
                    logger.info("  Created 02_Company")

                if company_drive:
                    await process_subfolders(
                        http, totals, dry_run,
                        src_parent_id=company_drive,
                        dest_parent_id=company_sub_id,
                        subfolders_to_sync=COMPANY_SUBFOLDERS,
                        enable_ai_routing=True
                    )

                # --- TAX DOCS (03_Tax) ---
                tax_sub_id = client_subs.get("03_Tax")
                if not tax_sub_id:
                    if not dry_run:
                        try:
                            tax_sub_id = await create_folder(http, "03_Tax", client_drive)
                        except Exception as e:
                            logger.warning(f"  Cannot create 03_Tax: {e}")
                            totals["errors"] += 1
                            continue
                    else:
                        tax_sub_id = "DRY_RUN_03_Tax"
                    logger.info("  Created 03_Tax")

                norm_comp_name = company_name.strip().lower()
                tax_folder_id = None
                for k, v in tax_map.items():
                    if k in norm_comp_name or norm_comp_name in k:
                        tax_folder_id = v
                        break

                if tax_folder_id:
                    await process_subfolders(
                        http, totals, dry_run,
                        src_parent_id=tax_folder_id,
                        dest_parent_id=tax_sub_id,
                        subfolders_to_sync=None, # Sync all subfolders in Tax
                        enable_ai_routing=False
                    )

                if client_id not in processed_clients:
                    processed_clients.add(client_id)
                    totals["clients"] += 1

                if (i + 1) % 10 == 0:
                    await asyncio.sleep(0.5)

        logger.info(f"\n{'=' * 50}")
        logger.info(f"Sync Shortcuts → Individual {'(DRY RUN)' if dry_run else 'COMPLETE'}")
        logger.info(f"  Links processed: {len(links)}")
        logger.info(f"  Clients        : {totals['clients']}")
        logger.info(f"  Shortcuts made : {totals['shortcuts_created']}")
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
