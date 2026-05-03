"""
Individual_CRM Reorg
====================
For each of 3,441 client folders in Individual_CRM:
1. Move passport files → 00_Profile (keep only 1, newest by name, move dupes to 99_Misc)
2. Move photo files → 00_Profile (keep only 1, move dupes to 99_Misc)
3. Move KITAS/E-Visa files → 01_Immigration
4. Move everything else → 99_Misc

Run:
    python3 scripts/individual_crm_reorg.py [--dry-run] [--limit N]
"""

import argparse
import asyncio
import logging
import time

import httpx

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

OAUTH_CLIENT_ID = "930328104463-m3g4gq72095rip08269kvt8s7et9ev12.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "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"
OAUTH_REFRESH_TOKEN = "1//0gbiun0bBkNVCCgYIARAAGBASNwF-L9IrGvLMkg0QQ7fz0x98C1zyFqsCvzyijl7NjxUXoJ8K_-BAN8t-ZuQyT5uIv2iVJUPSiMA"

INDIVIDUAL_CRM_ID = "1mNi2FkhZqP9inJH2Y1taXLCgS95UkYk4"
STANDARD_SUBS = ["00_Profile", "01_Immigration", "02_Company", "03_Tax", "04_Family", "99_Misc"]

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


async def list_files(client: httpx.AsyncClient, folder_id: str) -> list[dict]:
    """List all non-folder files in a folder."""
    headers = {"Authorization": f"Bearer {await get_token(client)}"}
    files = []
    pt = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "fields": "nextPageToken,files(id,name,modifiedTime,size)",
            "pageSize": "500",
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


async def list_subfolders(client: httpx.AsyncClient, folder_id: str) -> dict[str, str]:
    """Return {name: id} of subfolders."""
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


async def create_folder(client: httpx.AsyncClient, name: str, parent_id: str) -> str:
    """Create a subfolder, return its ID."""
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


async def move_file(
    client: httpx.AsyncClient, file_id: str, old_parent: str, new_parent: str
) -> None:
    """Move file from old_parent to new_parent."""
    headers = {"Authorization": f"Bearer {await get_token(client)}"}
    r = await client.patch(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        headers=headers,
        params={"addParents": new_parent, "removeParents": old_parent, "supportsAllDrives": "true"},
    )
    r.raise_for_status()


def classify(name: str) -> str:
    """Classify file by name → passport, photo, kitas, evisa, other."""
    nl = name.lower()
    if "passport" in nl or "paspor" in nl:
        return "passport"
    if "photo" in nl or "selfie" in nl or "foto" in nl:
        return "photo"
    if "kitas" in nl or ("itas" in nl and "kitas" not in nl and nl.startswith("itas")):
        return "kitas"
    if "kitas" in nl:
        return "kitas"
    if "kitap" in nl:
        return "kitas"
    if "e-visa" in nl or "evisa" in nl or "e_visa" in nl:
        return "evisa"
    return "other"


async def process_folder(client: httpx.AsyncClient, folder: dict, dry_run: bool) -> dict:
    """Process one client folder. Returns stats."""
    stats = {"moved": 0, "dedup": 0, "created_subs": 0}
    folder_id = folder["id"]
    folder["name"]

    # Get subfolders
    subs = await list_subfolders(client, folder_id)

    # Create standard subs if missing
    for sub in STANDARD_SUBS:
        if sub not in subs:
            if not dry_run:
                sid = await create_folder(client, sub, folder_id)
                subs[sub] = sid
                stats["created_subs"] += 1
            else:
                subs[sub] = f"DRY-{sub}"
                stats["created_subs"] += 1

    profile_id = subs.get("00_Profile", "")
    immigration_id = subs.get("01_Immigration", "")
    misc_id = subs.get("99_Misc", "")

    # Collect ALL files from root + all subfolders (except standard ones we'd move INTO)
    # We scan: root, and any non-standard subfolder
    sources: list[tuple[str, list[dict]]] = []

    # Root files
    root_files = await list_files(client, folder_id)
    if root_files:
        sources.append((folder_id, root_files))

    # Non-standard subfolders (move their contents too)
    for sub_name, sub_id in subs.items():
        if sub_name in STANDARD_SUBS:
            continue
        sub_files = await list_files(client, sub_id)
        if sub_files:
            sources.append((sub_id, sub_files))

    # Also scan files already in standard subs (for dedup)
    existing_in_profile = (
        await list_files(client, profile_id)
        if profile_id and not profile_id.startswith("DRY")
        else []
    )
    await list_files(client, immigration_id) if immigration_id and not immigration_id.startswith(
        "DRY"
    ) else []

    # Classify all source files
    passports: list[tuple[str, dict]] = []  # (parent_id, file)
    photos: list[tuple[str, dict]] = []
    kitas_evisa: list[tuple[str, dict]] = []
    others: list[tuple[str, dict]] = []

    for parent_id, files in sources:
        for f in files:
            cat = classify(f["name"])
            if cat == "passport":
                passports.append((parent_id, f))
            elif cat == "photo":
                photos.append((parent_id, f))
            elif cat in ("kitas", "evisa"):
                kitas_evisa.append((parent_id, f))
            else:
                others.append((parent_id, f))

    # Also check existing in profile/immigration for dedup counting
    existing_passport_count = sum(
        1 for f in existing_in_profile if classify(f["name"]) == "passport"
    )
    existing_photo_count = sum(1 for f in existing_in_profile if classify(f["name"]) == "photo")

    # PASSPORT: keep 1 (newest by modifiedTime), rest to 99_Misc
    if passports:
        # Sort by modifiedTime desc — keep newest
        passports.sort(key=lambda x: x[1].get("modifiedTime", ""), reverse=True)
        if existing_passport_count == 0:
            # Move best one to 00_Profile
            best_parent, best = passports[0]
            if best_parent != profile_id:
                if not dry_run:
                    await move_file(client, best["id"], best_parent, profile_id)
                stats["moved"] += 1
            dupes = passports[1:]
        else:
            # Already have passport in profile — all are dupes
            dupes = passports

        # Move dupes to 99_Misc
        for parent_id, f in dupes:
            if parent_id != misc_id:
                if not dry_run:
                    await move_file(client, f["id"], parent_id, misc_id)
                stats["dedup"] += 1

    # PHOTO: keep 1, rest to 99_Misc
    if photos:
        photos.sort(key=lambda x: x[1].get("modifiedTime", ""), reverse=True)
        if existing_photo_count == 0:
            best_parent, best = photos[0]
            if best_parent != profile_id:
                if not dry_run:
                    await move_file(client, best["id"], best_parent, profile_id)
                stats["moved"] += 1
            dupes = photos[1:]
        else:
            dupes = photos

        for parent_id, f in dupes:
            if parent_id != misc_id:
                if not dry_run:
                    await move_file(client, f["id"], parent_id, misc_id)
                stats["dedup"] += 1

    # KITAS/E-VISA → 01_Immigration
    for parent_id, f in kitas_evisa:
        if parent_id != immigration_id:
            if not dry_run:
                await move_file(client, f["id"], parent_id, immigration_id)
            stats["moved"] += 1

    # OTHERS → 99_Misc
    for parent_id, f in others:
        if parent_id != misc_id:
            if not dry_run:
                await move_file(client, f["id"], parent_id, misc_id)
            stats["moved"] += 1

    return stats


async def main(dry_run: bool, limit: int) -> None:
    logger.info(f"{'DRY RUN — ' if dry_run else ''}Individual_CRM Reorg")

    async with httpx.AsyncClient(timeout=30) as client:
        await get_token(client)

        # Get all client folders
        all_folders = []
        pt = None
        while True:
            headers = {"Authorization": f"Bearer {await get_token(client)}"}
            params = {
                "q": f"'{INDIVIDUAL_CRM_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
                "fields": "nextPageToken,files(id,name)",
                "pageSize": "1000",
            }
            if pt:
                params["pageToken"] = pt
            r = await client.get(
                "https://www.googleapis.com/drive/v3/files", headers=headers, params=params
            )
            r.raise_for_status()
            d = r.json()
            all_folders.extend(d.get("files", []))
            pt = d.get("nextPageToken")
            if not pt:
                break

        all_folders.sort(key=lambda x: x["name"])
        total = min(len(all_folders), limit)
        logger.info(f"Client folders: {len(all_folders)}, processing: {total}")

        totals = {"moved": 0, "dedup": 0, "created_subs": 0, "processed": 0, "errors": 0}
        sem = asyncio.Semaphore(20)  # 20 folders in parallel

        async def do_folder(i: int, folder: dict) -> None:
            async with sem:
                try:
                    stats = await process_folder(client, folder, dry_run)
                    totals["moved"] += stats["moved"]
                    totals["dedup"] += stats["dedup"]
                    totals["created_subs"] += stats["created_subs"]
                    totals["processed"] += 1

                    action_count = stats["moved"] + stats["dedup"]
                    if action_count > 0:
                        logger.info(
                            f"  [{i + 1}/{total}] {folder['name'][:45]}: +{stats['moved']} moved, {stats['dedup']} dedup"
                        )
                except Exception as e:
                    totals["errors"] += 1
                    logger.warning(f"  [{i + 1}/{total}] {folder['name'][:45]}: ERROR {e}")

        # Process in batches of 100
        folders_to_process = all_folders[:limit]
        for batch_start in range(0, len(folders_to_process), 100):
            batch = folders_to_process[batch_start : batch_start + 100]
            await asyncio.gather(*[do_folder(batch_start + j, f) for j, f in enumerate(batch)])
            logger.info(
                f"\n--- {min(batch_start + 100, total)}/{total} | moved={totals['moved']} dedup={totals['dedup']} errors={totals['errors']} ---\n"
            )

        logger.info(f"\n{'=' * 50}")
        logger.info(f"Individual_CRM Reorg {'(DRY RUN)' if dry_run else 'COMPLETE'}")
        logger.info(f"  Processed  : {totals['processed']}")
        logger.info(f"  Files moved: {totals['moved']}")
        logger.info(f"  Dedup      : {totals['dedup']}")
        logger.info(f"  Subs created: {totals['created_subs']}")
        logger.info(f"  Errors     : {totals['errors']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, limit=args.limit))
