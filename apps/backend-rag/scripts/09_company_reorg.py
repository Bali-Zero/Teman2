"""
09 Company Reorg — Drive Folder Organizer
==========================================
Per ogni company folder in Company_CRM:
  1. Lista file nella cartella
  2. Crea sottocartelle standard se mancanti: 00_AKTA, 01_NIB, 02_NPWP, 03_Profile_Perseroan, 99_Misc
  3. Classifica file per nome (regex)
  4. Sposta file nella sottocartella giusta
  5. Merge sottocartelle non-standard in quella standard corrispondente

Run:
    cd apps/backend-rag
    source venv/bin/activate
    python3 scripts/09_company_reorg.py [--dry-run] [--limit N] [--start-idx N]
"""

import argparse
import json
import logging
import os
import re
import time
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --- Config ---
COMPANY_CRM_ID = "1rLlr2G7TdNUmmvQ_xN9pZQLbPrDFjUsW"
STANDARD_FOLDERS = ["00_AKTA", "01_NIB", "02_NPWP", "03_Profile_Perseroan", "99_Misc"]
FOLDER_MIME = "application/vnd.google-apps.folder"
STATE_DIR = "/tmp/drive_reorg"
STATE_FILE = os.path.join(STATE_DIR, "reorg_state.json")

# OAuth credentials (same as bulk_populate)
OAUTH_CLIENT_ID = "930328104463-m3g4gq72095rip08269kvt8s7et9ev12.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "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"
OAUTH_REFRESH_TOKEN = "1//0gbiun0bBkNVCCgYIARAAGBASNwF-L9IrGvLMkg0QQ7fz0x98C1zyFqsCvzyijl7NjxUXoJ8K_-BAN8t-ZuQyT5uIv2iVJUPSiMA"

# Classification regex → standard folder
CLASSIFY: dict[str, re.Pattern] = {
    "00_AKTA": re.compile(r"akta|notaris|deed|sk.?kemen|sk.?ahu", re.IGNORECASE),
    "01_NIB": re.compile(r"nib|oss|izin.?usaha", re.IGNORECASE),
    "02_NPWP": re.compile(r"npwp|tax.?id", re.IGNORECASE),
    "03_Profile_Perseroan": re.compile(r"profil|profile|company.?profile", re.IGNORECASE),
}

# Non-standard folder names → standard folder mapping
FOLDER_MERGE_MAP: dict[str, str] = {
    "akta": "00_AKTA",
    "notaris": "00_AKTA",
    "deed": "00_AKTA",
    "sk": "00_AKTA",
    "nib": "01_NIB",
    "oss": "01_NIB",
    "npwp": "02_NPWP",
    "tax": "02_NPWP",
    "profil": "03_Profile_Perseroan",
    "profile": "03_Profile_Perseroan",
}

_oauth_access_token: str | None = None
_oauth_token_expiry: float = 0.0


def _get_oauth_access_token() -> str:
    """Get OAuth access token, refreshing if expired."""
    import urllib.parse
    import urllib.request

    global _oauth_access_token, _oauth_token_expiry

    if _oauth_access_token and time.time() < _oauth_token_expiry - 60:
        return _oauth_access_token

    data = urllib.parse.urlencode(
        {
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "refresh_token": OAUTH_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        }
    ).encode()

    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    _oauth_access_token = result["access_token"]
    _oauth_token_expiry = time.time() + result.get("expires_in", 3600)
    logger.info("OAuth token refreshed")
    return _oauth_access_token


def build_drive_service() -> Any:
    """Build Drive API service with OAuth."""
    token = _get_oauth_access_token()
    creds = Credentials(
        token=token,
        refresh_token=OAUTH_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=OAUTH_CLIENT_ID,
        client_secret=OAUTH_CLIENT_SECRET,
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_folder(service: Any, folder_id: str) -> list[dict]:
    """List all items in a Drive folder, handling pagination."""
    all_files: list[dict] = []
    page_token = None

    while True:
        try:
            results = (
                service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType)",
                    orderBy="name",
                    pageSize=200,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            all_files.extend(results.get("files", []))
            page_token = results.get("nextPageToken")
            if not page_token:
                break
        except HttpError as e:
            logger.warning(f"Drive list error for {folder_id}: {e}")
            break

    return all_files


def classify_file(filename: str) -> str:
    """Classify a file into a standard folder based on filename."""
    for folder_name, pattern in CLASSIFY.items():
        if pattern.search(filename):
            return folder_name
    return "99_Misc"


def match_nonstandard_folder(folder_name: str) -> str | None:
    """Match a non-standard folder name to a standard folder."""
    name_lower = folder_name.lower().strip()

    # Exact match with standard names
    for std in STANDARD_FOLDERS:
        if name_lower == std.lower():
            return None  # Already standard

    # Keyword match
    for keyword, target in FOLDER_MERGE_MAP.items():
        if keyword in name_lower:
            return target

    return None


def create_folder(service: Any, name: str, parent_id: str, dry_run: bool) -> str | None:
    """Create a folder in Drive. Returns folder ID or None in dry-run."""
    if dry_run:
        logger.info(f"    [DRY] Would create folder: {name}")
        return f"DRY_{name}"

    try:
        metadata = {
            "name": name,
            "mimeType": FOLDER_MIME,
            "parents": [parent_id],
        }
        folder = (
            service.files()
            .create(
                body=metadata,
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )
        time.sleep(0.3)  # Rate limit
        return folder["id"]
    except HttpError as e:
        logger.error(f"    Failed to create folder {name}: {e}")
        return None


def move_file(service: Any, file_id: str, old_parent: str, new_parent: str, dry_run: bool) -> bool:
    """Move a file from one folder to another."""
    if dry_run:
        return True

    try:
        service.files().update(
            fileId=file_id,
            addParents=new_parent,
            removeParents=old_parent,
            supportsAllDrives=True,
        ).execute()
        time.sleep(0.2)  # Rate limit
        return True
    except HttpError as e:
        logger.error(f"    Failed to move file {file_id}: {e}")
        return False


def load_state() -> dict:
    """Load resume state from JSON file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_idx": 0, "processed": 0, "errors": 0}


def save_state(state: dict) -> None:
    """Save resume state to JSON file."""
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def process_company(
    service: Any,
    company_folder: dict,
    idx: int,
    dry_run: bool,
) -> dict:
    """Process a single company folder: classify files and move to standard subfolders."""
    company_id = company_folder["id"]
    company_name = company_folder["name"]
    result = {
        "name": company_name,
        "created_folders": 0,
        "moved_files": 0,
        "merged_folders": 0,
        "errors": 0,
    }

    items = list_folder(service, company_id)
    if not items:
        return result

    folders = {f["name"]: f for f in items if f["mimeType"] == FOLDER_MIME}
    files = [f for f in items if f["mimeType"] != FOLDER_MIME]

    # 1. Create missing standard subfolders
    standard_ids: dict[str, str] = {}
    for std_name in STANDARD_FOLDERS:
        if std_name in folders:
            standard_ids[std_name] = folders[std_name]["id"]
        else:
            folder_id = create_folder(service, std_name, company_id, dry_run)
            if folder_id:
                standard_ids[std_name] = folder_id
                result["created_folders"] += 1
                logger.info(f"    + Created: {std_name}")

    # 2. Classify and move loose files
    for f in files:
        target = classify_file(f["name"])
        target_id = standard_ids.get(target)
        if not target_id:
            continue

        if dry_run:
            logger.info(f"    [DRY] Move '{f['name']}' → {target}")
        else:
            logger.info(f"    → Move '{f['name']}' → {target}")

        if move_file(service, f["id"], company_id, target_id, dry_run):
            result["moved_files"] += 1
        else:
            result["errors"] += 1

    # 3. Merge non-standard subfolders into standard ones
    for folder_name, folder_info in folders.items():
        target_std = match_nonstandard_folder(folder_name)
        if target_std is None:
            continue  # Already standard or no match

        target_id = standard_ids.get(target_std)
        if not target_id:
            continue

        # Get files in non-standard folder
        sub_files = list_folder(service, folder_info["id"])
        sub_files = [f for f in sub_files if f["mimeType"] != FOLDER_MIME]

        if not sub_files:
            continue

        logger.info(f"    🔀 Merging '{folder_name}' ({len(sub_files)} files) → {target_std}")
        result["merged_folders"] += 1

        for sf in sub_files:
            if move_file(service, sf["id"], folder_info["id"], target_id, dry_run):
                result["moved_files"] += 1
            else:
                result["errors"] += 1

    return result


def main(dry_run: bool, limit: int, start_idx: int) -> None:
    logger.info(f"{'DRY RUN — ' if dry_run else ''}Starting company reorg")
    logger.info(f"Company_CRM folder: {COMPANY_CRM_ID}")
    logger.info(f"Start index: {start_idx}, Limit: {limit}")

    service = build_drive_service()

    # List all company folders in Company_CRM
    logger.info("Listing company folders...")
    all_companies = list_folder(service, COMPANY_CRM_ID)
    company_folders = [f for f in all_companies if f["mimeType"] == FOLDER_MIME]
    company_folders.sort(key=lambda x: x["name"].lower())

    total = len(company_folders)
    logger.info(f"Found {total} company folders total")

    # Apply start_idx and limit
    to_process = company_folders[start_idx : start_idx + limit]
    logger.info(
        f"Processing {len(to_process)} companies (idx {start_idx} → {start_idx + len(to_process) - 1})"
    )

    stats = {
        "processed": 0,
        "created_folders": 0,
        "moved_files": 0,
        "merged_folders": 0,
        "errors": 0,
    }
    state = load_state()

    for i, company in enumerate(to_process):
        idx = start_idx + i
        logger.info(f"\n[{idx}/{total}] {company['name']}")

        try:
            result = process_company(service, company, idx, dry_run)
            stats["processed"] += 1
            stats["created_folders"] += result["created_folders"]
            stats["moved_files"] += result["moved_files"]
            stats["merged_folders"] += result["merged_folders"]
            stats["errors"] += result["errors"]

            if (
                result["created_folders"] == 0
                and result["moved_files"] == 0
                and result["merged_folders"] == 0
            ):
                logger.info("    ✓ Already organized")
            else:
                logger.info(
                    f"    ✓ {result['created_folders']} folders created, "
                    f"{result['moved_files']} files moved, "
                    f"{result['merged_folders']} folders merged"
                )
        except Exception as e:
            logger.error(f"    ERROR: {e}", exc_info=True)
            stats["errors"] += 1

        # Save state every 10 companies
        if (i + 1) % 10 == 0:
            state["last_idx"] = idx
            state["processed"] = stats["processed"]
            state["errors"] = stats["errors"]
            save_state(state)

        # Progress log every 50
        if (i + 1) % 50 == 0:
            logger.info(
                f"\n--- Progress: {i + 1}/{len(to_process)} ({stats['processed']} OK, {stats['errors']} errors) ---\n"
            )

        # Rate limit between companies
        time.sleep(0.5)

    # Final state save
    state["last_idx"] = start_idx + len(to_process) - 1
    state["processed"] = stats["processed"]
    state["errors"] = stats["errors"]
    save_state(state)

    logger.info("\n=== REORG SUMMARY ===")
    logger.info(f"  Companies processed : {stats['processed']}")
    logger.info(f"  Folders created     : {stats['created_folders']}")
    logger.info(f"  Files moved         : {stats['moved_files']}")
    logger.info(f"  Folders merged      : {stats['merged_folders']}")
    logger.info(f"  Errors              : {stats['errors']}")
    logger.info(f"  State saved to      : {STATE_FILE}")
    if dry_run:
        logger.info("  (DRY RUN — no changes made)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reorganize company Drive folders into standard structure"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no Drive changes")
    parser.add_argument(
        "--limit", type=int, default=100, help="Max companies to process (default 100)"
    )
    parser.add_argument(
        "--start-idx",
        type=int,
        default=0,
        help="Start from this index (default 0, use 1000 to resume)",
    )
    args = parser.parse_args()

    main(dry_run=args.dry_run, limit=args.limit, start_idx=args.start_idx)
