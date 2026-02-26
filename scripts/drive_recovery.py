#!/usr/bin/env python3
"""
Drive Recovery Script — Undo "nuzantara v6" damage to Individual_CRM folders.

The v6 workflow renamed 294 client folders (e.g. "Alejandro Jose Pruna Gomez" →
"10529_Aexandra Magalie Ruiz") and created empty duplicate folders.

This script:
1. Lists all folders in the Individual_CRM parent folder via Google Drive API
2. Cross-references with CRM database to identify originals vs duplicates
3. Restores original folder names
4. Deletes empty duplicate folders

Usage:
    # Dry run (default) — shows what would change, no mutations
    python scripts/drive_recovery.py

    # Execute recovery
    python scripts/drive_recovery.py --execute

    # Custom parent folder
    python scripts/drive_recovery.py --parent-folder-id <FOLDER_ID>

    # Export analysis to JSON
    python scripts/drive_recovery.py --export analysis.json

Requirements:
    pip install google-auth google-api-python-client httpx asyncpg python-dotenv
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Load .env from backend-rag if available
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent.parent / "apps" / "backend-rag" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()  # try cwd
except ImportError:
    pass

from google.oauth2 import service_account
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("drive_recovery")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DriveFolder:
    """A folder in Google Drive."""

    id: str
    name: str
    created_time: str = ""
    modified_time: str = ""
    file_count: int = 0
    subfolder_count: int = 0

    @property
    def parsed_id(self) -> int | None:
        """Extract numeric prefix (e.g. '10529' from '10529_Name')."""
        match = re.match(r"^(\d+)_", self.name)
        return int(match.group(1)) if match else None

    @property
    def parsed_name(self) -> str | None:
        """Extract name part after numeric prefix."""
        match = re.match(r"^\d+_(.+)$", self.name)
        return match.group(1) if match else None


@dataclass
class CRMClient:
    """A client from the CRM database."""

    id: int
    full_name: str
    email: str | None = None
    status: str = "active"
    drive_folder_id: str | None = None


@dataclass
class RecoveryAction:
    """A planned recovery action."""

    action: str  # "rename" | "delete" | "skip" | "unknown"
    folder: DriveFolder
    reason: str
    original_name: str | None = None
    crm_client: CRMClient | None = None
    confidence: float = 0.0


@dataclass
class RecoveryReport:
    """Full recovery analysis report."""

    timestamp: str = ""
    total_folders: int = 0
    actions: list[RecoveryAction] = field(default_factory=list)
    renamed: int = 0
    deleted: int = 0
    skipped: int = 0
    unknown: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Google Drive client
# ---------------------------------------------------------------------------

class DriveClient:
    """Google Drive API client using service account credentials."""

    SCOPES = ["https://www.googleapis.com/auth/drive"]

    def __init__(self) -> None:
        creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or os.environ.get(
            "GOOGLE_SERVICE_ACCOUNT"
        )
        if not creds_json:
            raise ValueError(
                "Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT env var "
                "with the service account JSON credentials."
            )

        import base64

        sa_info: dict[str, Any] | None = None

        # Try raw JSON
        try:
            parsed = json.loads(creds_json)
            if parsed.get("type") == "service_account":
                sa_info = parsed
        except json.JSONDecodeError:
            pass

        # Try base64
        if not sa_info:
            try:
                decoded = base64.b64decode(creds_json).decode("utf-8")
                parsed = json.loads(decoded)
                if parsed.get("type") == "service_account":
                    sa_info = parsed
            except Exception:
                pass

        if not sa_info:
            raise ValueError("Invalid service account credentials")

        base_creds = service_account.Credentials.from_service_account_info(
            sa_info, scopes=self.SCOPES
        )
        # Domain-wide delegation — impersonate Workspace user
        delegated_user = os.environ.get("GOOGLE_DELEGATED_USER", "zero@balizero.com")
        self.credentials = base_creds.with_subject(delegated_user)
        self.service = build("drive", "v3", credentials=self.credentials)
        logger.info("Google Drive client initialised (delegated as %s)", delegated_user)

    # ---- List folders ----

    async def list_folders(
        self, parent_id: str, page_size: int = 200
    ) -> list[DriveFolder]:
        """List all immediate child folders (handles pagination)."""
        query = (
            f"'{parent_id}' in parents "
            "and mimeType='application/vnd.google-apps.folder' "
            "and trashed=false"
        )
        folders: list[DriveFolder] = []
        page_token: str | None = None

        while True:
            request = self.service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, createdTime, modifiedTime)",
                pageSize=page_size,
                orderBy="name",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageToken=page_token,
            )
            result = await asyncio.to_thread(request.execute)

            for f in result.get("files", []):
                folders.append(
                    DriveFolder(
                        id=f["id"],
                        name=f["name"],
                        created_time=f.get("createdTime", ""),
                        modified_time=f.get("modifiedTime", ""),
                    )
                )

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        logger.info("Listed %d folders under parent %s", len(folders), parent_id)
        return folders

    # ---- Count children ----

    async def count_children(self, folder_id: str) -> tuple[int, int]:
        """Return (file_count, subfolder_count) for a folder."""
        # Count files (non-folders)
        file_q = (
            f"'{folder_id}' in parents "
            "and mimeType!='application/vnd.google-apps.folder' "
            "and trashed=false"
        )
        file_req = self.service.files().list(
            q=file_q,
            fields="files(id)",
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        file_result = await asyncio.to_thread(file_req.execute)
        file_count = len(file_result.get("files", []))

        # Count subfolders
        sub_q = (
            f"'{folder_id}' in parents "
            "and mimeType='application/vnd.google-apps.folder' "
            "and trashed=false"
        )
        sub_req = self.service.files().list(
            q=sub_q,
            fields="files(id)",
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        sub_result = await asyncio.to_thread(sub_req.execute)
        subfolder_count = len(sub_result.get("files", []))

        return file_count, subfolder_count

    # ---- Count children recursive ----

    async def count_all_files_recursive(self, folder_id: str) -> int:
        """Recursively count all files (non-folders) under a folder tree."""
        file_count, _ = await self.count_children(folder_id)

        # Get subfolders
        sub_q = (
            f"'{folder_id}' in parents "
            "and mimeType='application/vnd.google-apps.folder' "
            "and trashed=false"
        )
        sub_req = self.service.files().list(
            q=sub_q,
            fields="files(id)",
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        sub_result = await asyncio.to_thread(sub_req.execute)

        for sub in sub_result.get("files", []):
            file_count += await self.count_all_files_recursive(sub["id"])

        return file_count

    # ---- Rename ----

    async def rename_folder(self, folder_id: str, new_name: str) -> dict[str, Any]:
        """Rename a folder."""
        body = {"name": new_name}
        request = self.service.files().update(
            fileId=folder_id,
            body=body,
            fields="id, name",
            supportsAllDrives=True,
        )
        return await asyncio.to_thread(request.execute)

    # ---- Delete (trash) ----

    async def trash_folder(self, folder_id: str) -> dict[str, Any]:
        """Move a folder to trash (reversible)."""
        body = {"trashed": True}
        request = self.service.files().update(
            fileId=folder_id,
            body=body,
            fields="id, name, trashed",
            supportsAllDrives=True,
        )
        return await asyncio.to_thread(request.execute)

    # ---- Permanent delete ----

    async def delete_folder(self, folder_id: str) -> None:
        """Permanently delete a folder. USE WITH CAUTION."""
        request = self.service.files().delete(
            fileId=folder_id,
            supportsAllDrives=True,
        )
        await asyncio.to_thread(request.execute)


# ---------------------------------------------------------------------------
# CRM client loader
# ---------------------------------------------------------------------------

class CRMLoader:
    """Load CRM client data for cross-referencing."""

    def __init__(self) -> None:
        self.clients: dict[int, CRMClient] = {}
        self.clients_by_name: dict[str, CRMClient] = {}

    async def load_from_database(self, database_url: str | None = None) -> None:
        """Load clients from PostgreSQL."""
        import asyncpg

        db_url = database_url or os.environ.get("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL not set")

        conn = await asyncpg.connect(db_url)
        try:
            rows = await conn.fetch(
                """
                SELECT id, full_name, email, status, drive_folder_id
                FROM clients
                ORDER BY id
                """
            )
            for row in rows:
                client = CRMClient(
                    id=row["id"],
                    full_name=row["full_name"],
                    email=row.get("email"),
                    status=row.get("status", "active"),
                    drive_folder_id=row.get("drive_folder_id"),
                )
                self.clients[client.id] = client
                # Index by normalised name for fuzzy matching
                normalised = self._normalise(client.full_name)
                self.clients_by_name[normalised] = client

            logger.info("Loaded %d CRM clients from database", len(self.clients))
        finally:
            await conn.close()

    async def load_from_api(self, api_base: str | None = None) -> None:
        """Load clients from the Nuzantara backend API."""
        import httpx

        base = api_base or os.environ.get(
            "NUZANTARA_API_URL", "https://nuzantara-rag.fly.dev"
        )
        token = os.environ.get("NUZANTARA_API_TOKEN", "")

        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(base_url=base, headers=headers, timeout=60) as client:
            offset = 0
            limit = 200
            while True:
                resp = await client.get(
                    "/api/crm/clients",
                    params={"limit": limit, "offset": offset},
                )
                resp.raise_for_status()
                data = resp.json()
                clients_list = data.get("clients", data.get("data", []))
                if not clients_list:
                    break

                for c in clients_list:
                    crm_client = CRMClient(
                        id=c["id"],
                        full_name=c.get("full_name", c.get("name", "")),
                        email=c.get("email"),
                        status=c.get("status", "active"),
                        drive_folder_id=c.get("drive_folder_id"),
                    )
                    self.clients[crm_client.id] = crm_client
                    normalised = self._normalise(crm_client.full_name)
                    self.clients_by_name[normalised] = crm_client

                offset += limit
                if len(clients_list) < limit:
                    break

        logger.info("Loaded %d CRM clients from API", len(self.clients))

    def load_from_json(self, path: str) -> None:
        """Load clients from a local JSON file (fallback)."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        clients_list = data if isinstance(data, list) else data.get("clients", [])
        for c in clients_list:
            crm_client = CRMClient(
                id=c["id"],
                full_name=c.get("full_name", c.get("name", "")),
                email=c.get("email"),
                status=c.get("status", "active"),
                drive_folder_id=c.get("drive_folder_id"),
            )
            self.clients[crm_client.id] = crm_client
            normalised = self._normalise(crm_client.full_name)
            self.clients_by_name[normalised] = crm_client

        logger.info("Loaded %d CRM clients from %s", len(self.clients), path)

    def find_by_id(self, client_id: int) -> CRMClient | None:
        return self.clients.get(client_id)

    def find_by_name(self, name: str) -> CRMClient | None:
        normalised = self._normalise(name)
        return self.clients_by_name.get(normalised)

    @staticmethod
    def _normalise(name: str) -> str:
        """Normalise a name for fuzzy matching."""
        return re.sub(r"\s+", " ", name.strip().lower())


# ---------------------------------------------------------------------------
# Recovery analyser
# ---------------------------------------------------------------------------

class RecoveryAnalyser:
    """Analyse Drive folders and produce a recovery plan."""

    # Standard subfolders created by v6 workflow
    STANDARD_SUBFOLDERS = {
        "00_Profile",
        "01_Immigration",
        "02_Company",
        "03_Tax",
        "04_Family",
        "99_Misc",
    }

    def __init__(self, drive: DriveClient, crm: CRMLoader) -> None:
        self.drive = drive
        self.crm = crm

    async def analyse(
        self, folders: list[DriveFolder], check_contents: bool = True
    ) -> RecoveryReport:
        """
        Analyse folders and classify each one.

        Strategy:
        - Folders matching pattern "{id}_{name}" where CRM id exists:
            → Check if name matches CRM → if not, it was renamed by v6
        - Folders that are plain names (no numeric prefix):
            → These are ORIGINAL folders that were NOT touched by v6
        - Folders matching "{id}_{name}" where name does NOT match CRM:
            → v6 created these with wrong names — likely duplicates
        - Empty "{id}_{name}" folders created by v6 as duplicates:
            → Mark for deletion
        """
        report = RecoveryReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_folders=len(folders),
        )

        # Group folders by their numeric prefix for duplicate detection
        by_prefix: dict[int, list[DriveFolder]] = {}
        no_prefix: list[DriveFolder] = []

        for folder in folders:
            pid = folder.parsed_id
            if pid is not None:
                by_prefix.setdefault(pid, []).append(folder)
            else:
                no_prefix.append(folder)

        # --- Phase 1: Analyse prefixed folders ---
        for client_id, group in sorted(by_prefix.items()):
            crm_client = self.crm.find_by_id(client_id)

            if not crm_client:
                # No CRM match — cannot determine correct name
                for folder in group:
                    report.actions.append(
                        RecoveryAction(
                            action="unknown",
                            folder=folder,
                            reason=f"No CRM client with id={client_id}",
                            confidence=0.0,
                        )
                    )
                    report.unknown += 1
                continue

            expected_name = f"{client_id}_{crm_client.full_name}"

            if len(group) == 1:
                folder = group[0]
                if folder.name == expected_name:
                    # Already correct
                    report.actions.append(
                        RecoveryAction(
                            action="skip",
                            folder=folder,
                            reason="Name already matches CRM",
                            crm_client=crm_client,
                            confidence=1.0,
                        )
                    )
                    report.skipped += 1
                else:
                    # Renamed by v6 — needs restoration
                    report.actions.append(
                        RecoveryAction(
                            action="rename",
                            folder=folder,
                            reason=f"v6 renamed: '{folder.name}' → should be '{expected_name}'",
                            original_name=expected_name,
                            crm_client=crm_client,
                            confidence=0.95,
                        )
                    )
                    report.renamed += 1
            else:
                # Multiple folders with same prefix — pick the one with content
                await self._resolve_duplicates(group, crm_client, expected_name, report, check_contents)

        # --- Phase 2: Analyse non-prefixed folders ---
        for folder in no_prefix:
            # Try to match by name to CRM
            crm_client = self.crm.find_by_name(folder.name)
            if crm_client:
                # Original folder that v6 didn't touch, OR the original that
                # v6 renamed and a new prefixed folder was created
                expected = f"{crm_client.id}_{crm_client.full_name}"
                # Check if a prefixed version already exists
                prefixed_exists = crm_client.id in by_prefix
                if prefixed_exists:
                    # The prefixed one is the v6 duplicate; this is the original
                    report.actions.append(
                        RecoveryAction(
                            action="skip",
                            folder=folder,
                            reason=(
                                f"Original folder — prefixed duplicate "
                                f"'{expected}' exists and will be handled separately"
                            ),
                            crm_client=crm_client,
                            confidence=0.8,
                        )
                    )
                    report.skipped += 1
                else:
                    report.actions.append(
                        RecoveryAction(
                            action="skip",
                            folder=folder,
                            reason="Original folder, no prefixed duplicate found",
                            crm_client=crm_client,
                            confidence=0.9,
                        )
                    )
                    report.skipped += 1
            else:
                report.actions.append(
                    RecoveryAction(
                        action="skip",
                        folder=folder,
                        reason="No CRM match and no numeric prefix — leaving untouched",
                        confidence=0.5,
                    )
                )
                report.skipped += 1

        return report

    async def _resolve_duplicates(
        self,
        group: list[DriveFolder],
        crm_client: CRMClient,
        expected_name: str,
        report: RecoveryReport,
        check_contents: bool,
    ) -> None:
        """Resolve a group of folders with the same numeric prefix."""
        # Enrich with content counts if requested
        if check_contents:
            for folder in group:
                try:
                    files, subs = await self.drive.count_children(folder.id)
                    folder.file_count = files
                    folder.subfolder_count = subs
                except Exception as e:
                    logger.warning("Could not count children for %s: %s", folder.name, e)

        # Sort: folders with more content first
        group.sort(
            key=lambda f: (f.file_count + f.subfolder_count),
            reverse=True,
        )

        # The folder with content is the "keeper"
        keeper = group[0]
        duplicates = group[1:]

        # Rename keeper if needed
        if keeper.name != expected_name:
            report.actions.append(
                RecoveryAction(
                    action="rename",
                    folder=keeper,
                    reason=(
                        f"Keeper (has {keeper.file_count} files, "
                        f"{keeper.subfolder_count} subfolders): "
                        f"'{keeper.name}' → '{expected_name}'"
                    ),
                    original_name=expected_name,
                    crm_client=crm_client,
                    confidence=0.9,
                )
            )
            report.renamed += 1
        else:
            report.actions.append(
                RecoveryAction(
                    action="skip",
                    folder=keeper,
                    reason="Keeper — name already correct",
                    crm_client=crm_client,
                    confidence=1.0,
                )
            )
            report.skipped += 1

        # Delete empty duplicates
        for dup in duplicates:
            total_files = dup.file_count
            if check_contents and total_files == 0:
                # Also check recursively inside subfolders
                try:
                    recursive_count = await self.drive.count_all_files_recursive(dup.id)
                except Exception:
                    recursive_count = -1  # unknown

                if recursive_count == 0:
                    report.actions.append(
                        RecoveryAction(
                            action="delete",
                            folder=dup,
                            reason=(
                                f"Empty duplicate "
                                f"({dup.subfolder_count} empty subfolders, 0 files)"
                            ),
                            crm_client=crm_client,
                            confidence=0.95,
                        )
                    )
                    report.deleted += 1
                elif recursive_count > 0:
                    report.actions.append(
                        RecoveryAction(
                            action="skip",
                            folder=dup,
                            reason=(
                                f"Duplicate has {recursive_count} files inside — "
                                "manual review required"
                            ),
                            crm_client=crm_client,
                            confidence=0.3,
                        )
                    )
                    report.skipped += 1
                else:
                    report.actions.append(
                        RecoveryAction(
                            action="skip",
                            folder=dup,
                            reason="Could not verify contents — skipping for safety",
                            crm_client=crm_client,
                            confidence=0.0,
                        )
                    )
                    report.skipped += 1
            elif total_files > 0:
                report.actions.append(
                    RecoveryAction(
                        action="skip",
                        folder=dup,
                        reason=(
                            f"Duplicate has {total_files} files — "
                            "manual review required"
                        ),
                        crm_client=crm_client,
                        confidence=0.3,
                    )
                )
                report.skipped += 1
            else:
                # No content check — conservative skip
                report.actions.append(
                    RecoveryAction(
                        action="skip",
                        folder=dup,
                        reason="Duplicate — content not checked, skipping for safety",
                        crm_client=crm_client,
                        confidence=0.0,
                    )
                )
                report.skipped += 1


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class RecoveryExecutor:
    """Execute recovery actions against Google Drive."""

    def __init__(self, drive: DriveClient, dry_run: bool = True) -> None:
        self.drive = drive
        self.dry_run = dry_run
        self.executed: list[dict[str, Any]] = []
        self.errors: list[str] = []

    async def execute(self, report: RecoveryReport) -> None:
        """Execute all actions in the report."""
        mode = "DRY RUN" if self.dry_run else "LIVE"
        logger.info("=" * 60)
        logger.info("RECOVERY EXECUTION — %s MODE", mode)
        logger.info("=" * 60)

        renames = [a for a in report.actions if a.action == "rename"]
        deletes = [a for a in report.actions if a.action == "delete"]

        logger.info("Planned: %d renames, %d deletes", len(renames), len(deletes))

        # --- Execute renames first ---
        for action in renames:
            await self._execute_rename(action)

        # --- Then deletes ---
        for action in deletes:
            await self._execute_delete(action)

        # --- Summary ---
        logger.info("-" * 60)
        logger.info("EXECUTION COMPLETE")
        logger.info(
            "  Renames: %d executed, Deletes: %d executed, Errors: %d",
            sum(1 for e in self.executed if e["type"] == "rename"),
            sum(1 for e in self.executed if e["type"] == "delete"),
            len(self.errors),
        )

        if self.errors:
            logger.error("ERRORS:")
            for err in self.errors:
                logger.error("  - %s", err)

    async def _execute_rename(self, action: RecoveryAction) -> None:
        old_name = action.folder.name
        new_name = action.original_name
        if not new_name:
            self.errors.append(f"No target name for rename: {old_name}")
            return

        logger.info(
            "RENAME: '%s' → '%s' (confidence=%.2f)",
            old_name,
            new_name,
            action.confidence,
        )

        if self.dry_run:
            logger.info("  [DRY RUN] Would rename folder %s", action.folder.id)
            self.executed.append(
                {"type": "rename", "folder_id": action.folder.id, "old": old_name, "new": new_name, "dry_run": True}
            )
            return

        try:
            result = await self.drive.rename_folder(action.folder.id, new_name)
            logger.info("  ✅ Renamed to '%s'", result.get("name", new_name))
            self.executed.append(
                {"type": "rename", "folder_id": action.folder.id, "old": old_name, "new": new_name, "dry_run": False}
            )
        except Exception as e:
            msg = f"Failed to rename '{old_name}': {e}"
            logger.error("  ❌ %s", msg)
            self.errors.append(msg)

    async def _execute_delete(self, action: RecoveryAction) -> None:
        name = action.folder.name
        logger.info(
            "DELETE: '%s' (confidence=%.2f, reason: %s)",
            name,
            action.confidence,
            action.reason,
        )

        if self.dry_run:
            logger.info("  [DRY RUN] Would trash folder %s", action.folder.id)
            self.executed.append(
                {"type": "delete", "folder_id": action.folder.id, "name": name, "dry_run": True}
            )
            return

        try:
            # Move to trash (reversible) — NOT permanent delete
            await self.drive.trash_folder(action.folder.id)
            logger.info("  ✅ Trashed '%s'", name)
            self.executed.append(
                {"type": "delete", "folder_id": action.folder.id, "name": name, "dry_run": False}
            )
        except Exception as e:
            msg = f"Failed to trash '{name}': {e}"
            logger.error("  ❌ %s", msg)
            self.errors.append(msg)


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

def print_report(report: RecoveryReport) -> None:
    """Print a human-readable recovery report."""
    print("\n" + "=" * 70)
    print("DRIVE RECOVERY ANALYSIS REPORT")
    print(f"Timestamp: {report.timestamp}")
    print(f"Total folders scanned: {report.total_folders}")
    print("=" * 70)

    print(f"\n{'Action':<10} {'Confidence':<12} {'Folder Name':<45} {'Reason'}")
    print("-" * 120)

    for action in sorted(report.actions, key=lambda a: a.action):
        name = action.folder.name[:44]
        conf = f"{action.confidence:.0%}"
        print(f"{action.action.upper():<10} {conf:<12} {name:<45} {action.reason[:60]}")

        if action.action == "rename" and action.original_name:
            print(f"{'':>10} {'':>12} → {action.original_name[:44]}")

    print("\n" + "-" * 70)
    print("SUMMARY")
    print(f"  Renames:  {report.renamed:>4}")
    print(f"  Deletes:  {report.deleted:>4}")
    print(f"  Skipped:  {report.skipped:>4}")
    print(f"  Unknown:  {report.unknown:>4}")
    print(f"  TOTAL:    {report.total_folders:>4}")
    print("=" * 70)


def export_report(report: RecoveryReport, path: str) -> None:
    """Export report to JSON."""
    data = {
        "timestamp": report.timestamp,
        "total_folders": report.total_folders,
        "summary": {
            "renames": report.renamed,
            "deletes": report.deleted,
            "skipped": report.skipped,
            "unknown": report.unknown,
        },
        "actions": [
            {
                "action": a.action,
                "folder_id": a.folder.id,
                "folder_name": a.folder.name,
                "reason": a.reason,
                "original_name": a.original_name,
                "confidence": a.confidence,
                "crm_client_id": a.crm_client.id if a.crm_client else None,
                "crm_client_name": a.crm_client.full_name if a.crm_client else None,
                "file_count": a.folder.file_count,
                "subfolder_count": a.folder.subfolder_count,
            }
            for a in report.actions
        ],
        "errors": report.errors,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Report exported to %s", path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recover Google Drive folders damaged by nuzantara v6 workflow."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute recovery (default is dry-run)",
    )
    parser.add_argument(
        "--parent-folder-id",
        default=os.environ.get("GDRIVE_INDIVIDUALS_FOLDER_ID", ""),
        help="Google Drive parent folder ID for Individual_CRM",
    )
    parser.add_argument(
        "--crm-json",
        default=None,
        help="Path to CRM clients JSON export (alternative to DB/API)",
    )
    parser.add_argument(
        "--crm-source",
        choices=["db", "api", "json"],
        default="api",
        help="Source for CRM data (default: api)",
    )
    parser.add_argument(
        "--export",
        default=None,
        help="Export analysis to JSON file",
    )
    parser.add_argument(
        "--skip-content-check",
        action="store_true",
        help="Skip checking folder contents (faster but less accurate)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.8,
        help="Minimum confidence to execute an action (default: 0.8)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.parent_folder_id:
        logger.error(
            "Parent folder ID required. Set GDRIVE_INDIVIDUALS_FOLDER_ID env var "
            "or use --parent-folder-id."
        )
        sys.exit(1)

    # --- 1. Initialise Drive client ---
    logger.info("Step 1/4: Initialising Google Drive client...")
    drive = DriveClient()

    # --- 2. Load CRM data ---
    logger.info("Step 2/4: Loading CRM client data (source=%s)...", args.crm_source)
    crm = CRMLoader()

    if args.crm_source == "json":
        if not args.crm_json:
            logger.error("--crm-json required when --crm-source=json")
            sys.exit(1)
        crm.load_from_json(args.crm_json)
    elif args.crm_source == "db":
        await crm.load_from_database()
    else:
        await crm.load_from_api()

    if not crm.clients:
        logger.error("No CRM clients loaded — cannot cross-reference. Aborting.")
        sys.exit(1)

    # --- 3. List and analyse folders ---
    logger.info("Step 3/4: Listing folders and analysing damage...")
    folders = await drive.list_folders(args.parent_folder_id)

    analyser = RecoveryAnalyser(drive, crm)
    report = await analyser.analyse(
        folders, check_contents=not args.skip_content_check
    )

    print_report(report)

    if args.export:
        export_report(report, args.export)

    # --- 4. Execute (or dry-run) ---
    actionable = [
        a for a in report.actions
        if a.action in ("rename", "delete") and a.confidence >= args.min_confidence
    ]

    if not actionable:
        logger.info("No actionable items found. Nothing to do.")
        return

    dry_run = not args.execute
    if dry_run:
        logger.info(
            "\nThis was a DRY RUN. To execute, re-run with --execute flag."
        )
        logger.info(
            "%d actions would be taken (confidence >= %.0f%%).",
            len(actionable),
            args.min_confidence * 100,
        )
    else:
        logger.warning(
            "\n⚠️  LIVE EXECUTION: %d actions will be performed.", len(actionable)
        )
        # Filter report to only high-confidence actions
        filtered_report = RecoveryReport(
            timestamp=report.timestamp,
            total_folders=report.total_folders,
            actions=[
                a for a in report.actions
                if a.confidence >= args.min_confidence
            ],
        )

        executor = RecoveryExecutor(drive, dry_run=False)
        await executor.execute(filtered_report)

        if executor.errors:
            logger.error("Completed with %d errors — review log above.", len(executor.errors))
            sys.exit(1)

    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
