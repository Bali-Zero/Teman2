"""
Drive Changes Polling Service

Polls Google Drive for new files added to client folders,
then dispatches OCR via the central dispatcher.

Runs every 5 minutes via the autonomous scheduler.
"""

import logging
import os
import time
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import asyncpg

from backend.services.crm.document_categorizer import auto_categorize_document

logger = logging.getLogger(__name__)


@dataclass
class DriveCircuitBreaker:
    """
    Circuit breaker per il Drive polling.

    Stati:
    - closed: normale, poll eseguito
    - open: troppi errori consecutivi, poll saltato
    - half-open: tentativo di recovery dopo timeout

    Invia alert Telegram quando il circuit si apre.
    """

    failure_threshold: int = 3
    recovery_timeout: int = 300  # 5 minuti
    _failures: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _state: str = field(default="closed", init=False)

    @property
    def state(self) -> str:
        if self._state == "open":
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = "half-open"
        return self._state

    def record_success(self) -> None:
        self._failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failures += 1
        self._last_failure_time = time.time()
        if self._failures >= self.failure_threshold:
            if self._state != "open":
                logger.error(f"Drive circuit breaker OPEN dopo {self._failures} errori consecutivi")
            self._state = "open"

    async def call(
        self,
        fn: Callable[[], Awaitable[dict[str, Any]]],
        on_open: Callable[[str], None] | None = None,
    ) -> dict[str, Any] | None:
        """
        Esegue fn() se il circuit è closed/half-open.
        Ritorna None se il circuit è open (poll saltato silenziosamente).
        """
        current = self.state
        if current == "open":
            logger.warning("Drive circuit OPEN — poll saltato")
            return None

        try:
            result = await fn()
            self.record_success()
            if current == "half-open":
                logger.info("Drive circuit breaker: recovery OK — tornato CLOSED")
            return result
        except Exception as e:
            self.record_failure()
            if self._state == "open" and on_open:
                on_open(str(e))
            raise


# Singleton circuit breaker (persiste tra i poll della stessa sessione)
_drive_circuit_breaker = DriveCircuitBreaker()


def _send_telegram_alert(message: str) -> None:
    """Invia alert Telegram quando il circuit breaker si apre."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "413539912")
    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN non trovato — skip alert circuit breaker")
        return
    try:
        data = urllib.parse.urlencode(
            {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
            },
        ).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data,
            timeout=10,
        )
        logger.info("Telegram alert circuit breaker inviato")
    except Exception as ex:
        logger.warning(f"Telegram alert fallito: {ex}")


async def poll_drive_changes() -> dict[str, Any]:
    """
    Poll Google Drive for new files in client folders.

    1. Read page_token from system_settings
    2. Call Drive Changes API
    3. For each new file in a client subfolder, dispatch OCR
    4. Save new page_token

    Returns summary of what was processed.
    Gestito da DriveCircuitBreaker: si apre dopo 3 errori consecutivi.
    """

    def _on_circuit_open(error: str) -> None:
        alert_msg = (
            f"⚠️ <b>Drive Polling</b>: circuit breaker APERTO\n"
            f"Dopo {_drive_circuit_breaker.failure_threshold} errori consecutivi.\n"
            f"Ultimo errore: <code>{error[:200]}</code>\n"
            f"Recovery automatico in {_drive_circuit_breaker.recovery_timeout // 60} minuti."
        )
        _send_telegram_alert(alert_msg)

    try:
        result = await _drive_circuit_breaker.call(_do_poll_drive_changes, on_open=_on_circuit_open)
        if result is None:
            return {"status": "circuit_open", "processed": 0}
        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _do_poll_drive_changes() -> dict[str, Any]:
    """Logica effettiva del polling — chiamata tramite circuit breaker."""
    db_pool = None
    try:
        from backend.app.routers.crm_enhanced import _dispatch_ocr_by_folder
        from backend.services.integrations.service_account_drive_service import (
            ServiceAccountDriveService,
        )

        db_pool = await asyncpg.create_pool(
            os.environ["DATABASE_URL"],
            min_size=1,
            max_size=2,
        )

        drive_service = ServiceAccountDriveService()

        # 1. Get or initialize page token
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM system_settings WHERE key = 'drive_poll_page_token'",
            )
            if row:
                page_token = row["value"]
            else:
                # First run: get current token (won't return historical changes)
                page_token = await drive_service.get_start_page_token()
                await conn.execute(
                    """INSERT INTO system_settings (key, value, updated_at)
                    VALUES ('drive_poll_page_token', $1, NOW())""",
                    page_token,
                )
                logger.info(f"Drive poll: initialized page token {page_token}")
                return {"status": "initialized", "processed": 0}

        # 2. Get changes since last poll
        result = await drive_service.list_changes_since(page_token)
        changes = result["changes"]
        new_token = result["new_page_token"]

        if not changes:
            # Save new token even if no changes
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """UPDATE system_settings SET value = $1, updated_at = NOW()
                    WHERE key = 'drive_poll_page_token'""",
                    new_token,
                )
            return {"status": "no_changes", "processed": 0}

        # 3. Build lookup maps: subfolder_id → (client_id, subfolder_name)
        # Includes BOTH top-level (00_Profile) AND nested (02_Company/AKTA) subfolders
        async with db_pool.acquire() as conn:
            subfolders = await conn.fetch(
                "SELECT client_id, subfolder_name, subfolder_id FROM client_drive_subfolders",
            )

        subfolder_map: dict[str, tuple[int, str]] = {}
        for sf in subfolders:
            subfolder_map[sf["subfolder_id"]] = (sf["client_id"], sf["subfolder_name"])

        # Also build client root folder → client_id map (for fallback resolution)
        async with db_pool.acquire() as conn:
            clients_with_folders = await conn.fetch(
                "SELECT id, google_drive_folder_id FROM clients WHERE google_drive_folder_id IS NOT NULL",
            )

        root_folder_map: dict[str, int] = {}
        for c in clients_with_folders:
            root_folder_map[c["google_drive_folder_id"]] = c["id"]

        # 4. Process new files
        processed = 0
        skipped = 0
        for change in changes:
            if change.get("removed"):
                continue

            file_info = change.get("file")
            if not file_info or file_info.get("trashed"):
                continue

            # Skip folders
            if file_info.get("mimeType") == "application/vnd.google-apps.folder":
                continue

            file_id = file_info["id"]
            file_name = file_info.get("name", "")
            parents = file_info.get("parents", [])

            if not parents:
                continue

            parent_id = parents[0]

            # Check if parent is a known subfolder (top-level OR nested)
            if parent_id in subfolder_map:
                client_id, folder_name = subfolder_map[parent_id]
            elif parent_id in root_folder_map:
                # File in client root folder — skip (should be in a subfolder)
                skipped += 1
                continue
            else:
                # Unknown parent — try to resolve via Drive API
                # This catches nested folders not yet in client_drive_subfolders
                try:
                    parent_info = await drive_service.get_file_metadata(parent_id)
                    parent_name = parent_info.get("name", "")
                    parent_parents = parent_info.get("parents", [])

                    # Check if grandparent is a known subfolder (nested case)
                    if parent_parents and parent_parents[0] in subfolder_map:
                        client_id, _ = subfolder_map[parent_parents[0]]
                        folder_name = parent_name.lower()
                        # Register this nested folder for future polls
                        async with db_pool.acquire() as conn:
                            await conn.execute(
                                """INSERT INTO client_drive_subfolders
                                (client_id, subfolder_name, subfolder_id)
                                VALUES ($1, $2, $3)
                                ON CONFLICT (subfolder_id) DO NOTHING""",
                                client_id,
                                parent_name,
                                parent_id,
                            )
                        subfolder_map[parent_id] = (client_id, folder_name)
                        logger.info(
                            f"Drive poll: registered nested folder '{parent_name}' for client {client_id}",
                        )
                    else:
                        skipped += 1
                        continue
                except Exception:
                    skipped += 1
                    continue

            # Deduplicate: skip if file_id already in documents
            async with db_pool.acquire() as conn:
                existing = await conn.fetchval(
                    "SELECT id FROM documents WHERE file_id = $1",
                    file_id,
                )
                if existing:
                    skipped += 1
                    continue

            logger.info(
                f"Drive poll: new file '{file_name}' in {folder_name} for client {client_id}",
            )

            # Create document record with auto-categorization
            cat_result = auto_categorize_document(file_name)
            doc_category = cat_result["document_category"]
            async with db_pool.acquire() as conn:
                doc_id = await conn.fetchval(
                    """INSERT INTO documents (
                        client_id, document_type, document_category, file_name, file_id,
                        status, storage_type, ocr_status
                    ) VALUES ($1, $2, $3, $4, $5, 'active', 'google_drive', 'pending')
                    RETURNING id""",
                    client_id,
                    _infer_document_type(file_name, folder_name),
                    doc_category,
                    file_name,
                    file_id,
                )

            # Touch client updated_at so CRM reflects new document
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE clients SET updated_at = NOW() WHERE id = $1",
                    client_id,
                )

            # Dispatch OCR
            try:
                await _dispatch_ocr_by_folder(
                    client_id,
                    file_id,
                    folder_name,
                    file_name,
                    doc_id,
                )
                processed += 1
            except Exception as e:
                logger.error(f"Drive poll: OCR dispatch failed for {file_name}: {e}")

        # 5. Save new page token
        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE system_settings SET value = $1, updated_at = NOW()
                WHERE key = 'drive_poll_page_token'""",
                new_token,
            )

        logger.info(
            f"Drive poll: processed {processed}, skipped {skipped} from {len(changes)} changes",
        )
        return {
            "status": "ok",
            "changes": len(changes),
            "processed": processed,
            "skipped": skipped,
        }

    except Exception as e:
        logger.error(f"Drive poll failed: {e}", exc_info=True)
        raise  # ri-lancia per permettere al circuit breaker di contare i failures
    finally:
        if db_pool:
            await db_pool.close()


def _infer_document_type(filename: str, folder_name: str) -> str:
    """Infer document type from filename and folder name.

    Matches the official folder schema:
    - 00_Profile: passport, foto, address
    - 01_Immigration: e-visa, IMK/ITK, KITAS (NOT passport)
    - 02_Company: AKTA, NIB, NPWP company, Profile Perseroan
    - 03_Tax: SPT, LKPM, NPWP personal
    - 04_Family: passport/visa/kitas of family members
    - 99_Misc: everything else
    """
    fn = filename.lower()
    fl = folder_name.lower()

    # Keyword-based detection (priority order)
    if "passport" in fn or "paspor" in fn:
        return "passport"
    if any(kw in fn for kw in ["kitas", "kitap", "itas"]):
        return "kitas"
    if any(kw in fn for kw in ["visa", "voa", "b211", "evisa", "e-visa"]):
        return "visa"
    if "imk" in fn or "reentry" in fn:
        return "imk"
    if "itk" in fn:
        return "itk"
    if "akta" in fn:
        return "akta"
    if "nib" in fn or "berusaha" in fn or "oss" in fn:
        return "nib"
    if "npwp" in fn:
        return "npwp"
    if "spt" in fn:
        return "spt"
    if "lkpm" in fn:
        return "lkpm"
    if "profile perseroan" in fn or "company profile" in fn:
        return "profile_perseroan"

    # Fallback by folder (supports nested: "02_company/akta" → "akta")
    folder_map = {
        "00_profile": "profile_document",
        "01_immigration": "immigration_document",
        "02_company": "company_document",
        "03_tax": "tax_document",
        "04_family": "family_document",
        "99_misc": "misc_document",
        # Nested subfolders
        "akta": "akta",
        "nib": "nib",
        "npwp": "npwp",
        "profile perseroan": "profile_perseroan",
        "spt company": "spt_company",
        "spt personal": "spt_personal",
        "lkpm reports": "lkpm",
        "npwp personal": "npwp_personal",
    }
    return folder_map.get(fl, "other")
