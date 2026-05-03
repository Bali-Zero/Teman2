"""
Portal documents mixin.

Handles the client-portal document pipeline:
- list documents with filters (get_documents)
- upload with virus scan, OCR, expiry extraction, Google Drive push
  (upload_document + _upload_to_drive / _upload_with_service_account /
  _get_or_create_drive_folder / _notify_lead_about_document)

Also owns the filename / category / Drive-folder classification helpers
used exclusively by the upload path.

Depends on PortalService for:
- self.pool                         (asyncpg pool)
- self._metrics                     (upload counters dict)
- self._upload_rate_limits          (rate-limit state)
- self.MAX_UPLOADS_PER_WINDOW / self.RATE_WINDOW_SECONDS
- self._is_undefined_column_error / _is_undefined_table_error
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.app.utils.logging_utils import get_logger
from backend.services.common.background import spawn
from backend.services.common.cache import cache_invalidating
from backend.services.portal._rbac import ClientContext, require_client_access
from backend.services.portal.document_processing import (
    DocumentOCR,
    ExpiryDetector,
    VirusScanner,
)

logger = get_logger(__name__)


class PortalDocumentsMixin:
    """Client-portal document listing + upload pipeline (Drive / OCR / virus scan)."""

    pool: asyncpg.Pool
    _metrics: dict[str, int]
    _upload_rate_limits: dict[int, list[float]]
    MAX_UPLOADS_PER_WINDOW: int
    RATE_WINDOW_SECONDS: int


    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal and unsafe chars."""
        import re

        # Remove path components
        filename = filename.replace("\\", "/").split("/")[-1]
        # Remove unsafe characters
        filename = re.sub(r"[^\w\-\.]", "_", filename)
        # Limit length
        if len(filename) > 200:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = name[:195] + ("." + ext if ext else "")
        return filename
    @staticmethod
    def _classify_document_category(document_type: str, file_name: str) -> str:
        """Auto-classify document_category from document_type and filename."""
        dt = (document_type or "").lower()
        fn = (file_name or "").lower()
        combined = f"{dt} {fn}"

        # Immigration
        if any(k in combined for k in (
            "kitas", "kitap", "visa", "evisa", "voa", "permit", "imta", "rptka", "itas",
        )):
            return "immigration"

        # Personal
        if any(k in combined for k in (
            "passport", "paspor", "ktp", "photo", "foto", "cv ", "resume",
            "domisili", "skck", "surat keterangan",
        )):
            return "personal"

        # Company / PMA
        if any(k in combined for k in (
            "akta", "pendirian", "perubahan", "nib", "npwp", "sk ", "profil perseroan",
            "sertifikat standar", "kbli", "sppl", "pks", "kontrak", "contract",
        )):
            return "pma"

        # Tax
        if any(k in combined for k in ("tax", "pajak", "spt", "efin", "pph", "ppn")):
            return "tax"

        # Family
        if any(k in combined for k in ("akte lahir", "akta lahir", "birth", "nikah", "marriage")):
            return "family"

        return "other"

    @staticmethod
    def _get_drive_folder_for_category(category: str) -> str:
        """Map document category to Drive folder name for OCR dispatch."""
        category_map = {
            "immigration": "01_Immigration",
            "personal": "00_Profile",
            "pma": "02_Company",
            "tax": "03_Tax",
            "family": "04_Family",
        }
        return category_map.get((category or "").lower(), "99_Misc")
    # ================================================
    # DOCUMENTS
    # ================================================

    @require_client_access
    async def get_documents(
        self,
        client_id: int,
        document_type: str | None = None,
        *,
        current_user: ClientContext,
    ) -> list[dict[str, Any]]:
        """Get all client-visible documents."""
        async with self.pool.acquire() as conn:
            query = """
                SELECT d.id, d.document_type, d.file_name, d.status,
                       d.expiry_date, d.file_url, d.file_size_kb, d.created_at,
                       p.id as practice_id, pt.name as practice_name
                FROM documents d
                LEFT JOIN practices p ON p.id = d.practice_id
                LEFT JOIN practice_types pt ON pt.id = p.practice_type_id
                WHERE d.client_id = $1
                AND d.client_visible = true
            """
            params = [client_id]

            if document_type:
                query += " AND d.document_type = $2"
                params.append(document_type)

            query += " ORDER BY d.created_at DESC"

            documents = await conn.fetch(query, *params)

            return [
                {
                    "id": d["id"],
                    "type": d["document_type"],
                    "name": d["file_name"],
                    "status": d["status"],
                    "expiry_date": d["expiry_date"].isoformat() if d["expiry_date"] else None,
                    "size_kb": d["file_size_kb"],
                    "practice_id": d["practice_id"],
                    "practice_name": d["practice_name"],
                    "downloadable": d["status"] in ("verified", "issued")
                    and d["file_url"] is not None,
                    "created_at": d["created_at"].isoformat(),
                }
                for d in documents
            ]

    @cache_invalidating([
        lambda self, client_id, *a, **k: f"zantara:portal_documents:{client_id}:*",
        "zantara:portal_documents:*",
        "zantara:portal_timeline:*",
    ])
    @require_client_access
    async def upload_document(
        self,
        client_id: int,
        file_content: bytes,
        file_name: str,
        document_type: str,
        mime_type: str | None = None,
        practice_id: int | None = None,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """
        Upload a document for a client with full processing:
        - Virus scanning
        - Google Drive upload with folder structure
        - OCR text extraction
        - Expiry date detection
        - Email notification to assigned lead
        """
        processing_results = {
            "virus_scan": None,
            "drive_upload": None,
            "ocr": None,
            "expiry_detection": None,
        }

        # =========================================================================
        # STEP 1: VIRUS SCAN
        # =========================================================================
        scan_result = VirusScanner.scan(file_content, file_name)
        processing_results["virus_scan"] = scan_result

        if not scan_result["clean"]:
            logger.warning(
                f"🚨 THREAT DETECTED in upload from client {client_id}: "
                f"{file_name} - Threats: {scan_result['threats']}",
            )
            raise ValueError(
                f"Security threat detected in file: {', '.join(scan_result['threats'])}. "
                "Upload blocked for security reasons.",
            )

        logger.info(f"✅ Virus scan passed for {file_name}")

        # Calculate file size
        file_size_kb = len(file_content) // 1024

        # Memory optimization: skip OCR for very large files (> 50MB)
        skip_ocr = file_size_kb > 51200  # 50MB
        if skip_ocr:
            logger.warning(f"File too large for OCR ({file_size_kb}KB), skipping: {file_name}")

        # =========================================================================
        # STEP 0: RATE LIMITING & VALIDATION
        # =========================================================================
        # Check rate limit
        now = datetime.now(timezone.utc).timestamp()
        client_uploads = self._upload_rate_limits.get(client_id, [])
        # Clean old entries outside window
        client_uploads = [t for t in client_uploads if now - t < self.RATE_WINDOW_SECONDS]
        if len(client_uploads) >= self.MAX_UPLOADS_PER_WINDOW:
            raise ValueError(
                f"Rate limit exceeded: max {self.MAX_UPLOADS_PER_WINDOW} uploads per 15 minutes",
            )
        client_uploads.append(now)
        self._upload_rate_limits[client_id] = client_uploads

        # Validate MIME type
        if mime_type and not VirusScanner.validate_mime_type(mime_type):
            raise ValueError(f"File type not allowed: {mime_type}")

        # Sanitize filename
        file_name = self._sanitize_filename(file_name)

        async with self.pool.acquire() as conn:
            # Check for duplicate file (same hash, same client, last 1 hour)
            duplicate = await conn.fetchrow(
                """
                SELECT id, file_name, created_at
                FROM documents
                WHERE client_id = $1
                AND file_name LIKE $2
                AND created_at > NOW() - INTERVAL '1 hour'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                client_id,
                f"%{file_name}%",
            )
            if duplicate:
                logger.info(
                    f"Duplicate file detected: {file_name} uploaded at {duplicate['created_at']}",
                )
                raise ValueError(f"File already uploaded recently at {duplicate['created_at']}")

            # Verify practice belongs to client if provided
            if practice_id:
                practice = await conn.fetchrow(
                    "SELECT id FROM practices WHERE id = $1 AND client_id = $2",
                    practice_id,
                    client_id,
                )
                if not practice:
                    raise ValueError("Practice not found or not accessible")

            # Get client info
            client = await conn.fetchrow(
                "SELECT email, full_name, assigned_to FROM clients WHERE id = $1 AND deleted_at IS NULL",
                client_id,
            )

            if not client:
                raise ValueError(f"Client {client_id} not found")

            # =========================================================================
            # STEP 2: GOOGLE DRIVE UPLOAD
            # =========================================================================
            drive_result = await self._upload_to_drive(
                conn=conn,
                client_id=client_id,
                client_name=client["full_name"],
                document_type=document_type,
                file_content=file_content,
                file_name=file_name,
                mime_type=mime_type,
            )
            processing_results["drive_upload"] = drive_result

            # =========================================================================
            # STEP 3: OCR TEXT EXTRACTION (using Gemini Vision - same as passport box)
            # =========================================================================
            if skip_ocr:
                ocr_result = {
                    "text": "",
                    "pages": 0,
                    "success": False,
                    "error": "File too large for OCR (>50MB)",
                }
            else:
                ocr_result = await DocumentOCR.extract_text(
                    file_content=file_content, file_name=file_name, mime_type=mime_type,
                )
            processing_results["ocr"] = ocr_result

            if ocr_result["success"]:
                logger.info(
                    f"📄 OCR extracted {len(ocr_result['text'])} chars "
                    f"from {file_name} ({ocr_result['pages']} pages)",
                )
            else:
                logger.warning(f"⚠️ OCR failed for {file_name}: {ocr_result.get('error')}")

            # =========================================================================
            # STEP 4: EXPIRY DATE DETECTION
            # =========================================================================
            expiry_result = ExpiryDetector.detect_expiry(
                text=ocr_result.get("text", ""), document_type=document_type,
            )
            processing_results["expiry_detection"] = expiry_result

            if expiry_result["expiry_date"]:
                logger.info(
                    f"📅 Expiry date detected for {document_type}: "
                    f"{expiry_result['expiry_date']} (confidence: {expiry_result['confidence']})",
                )

            # =========================================================================
            # STEP 5: SAVE TO DATABASE (with transaction)
            # =========================================================================
            # Auto-classify document_category from document_type
            doc_category = self._classify_document_category(document_type, file_name)

            async with conn.transaction():
                try:
                    doc = await conn.fetchrow(
                        """
                        INSERT INTO documents (
                            client_id, practice_id, document_type, document_category, file_name,
                            status, uploaded_by, uploaded_source, file_size_kb, mime_type,
                            storage_type, storage_path, file_id, file_url,
                            extracted_text, expiry_date,
                            client_visible, created_at
                        )
                        VALUES (
                            $1, $2, $3, $13, $4, 'received', $5, 'client', $6, $7,
                            'google_drive', $8, $9, $10,
                            $11, $12,
                            true, NOW()
                        )
                        RETURNING id, document_type, file_name, status, created_at, expiry_date
                        """,
                        client_id,
                        practice_id,
                        document_type,
                        file_name,
                        client["email"],
                        file_size_kb,
                        mime_type,
                        drive_result.get("folder_path"),
                        drive_result.get("file_id"),
                        drive_result.get("file_url"),
                        ocr_result.get("text")[:10000]
                        if ocr_result.get("text")
                        else None,  # Limit text size
                        expiry_result.get("expiry_date"),
                        doc_category,
                    )
                except Exception as e:
                    # Backward compatibility: try without new columns
                    if self._is_undefined_column_error(e):
                        doc = await conn.fetchrow(
                            """
                            INSERT INTO documents (
                                client_id, practice_id, document_type, file_name,
                                status, uploaded_by, file_size_kb, mime_type,
                                storage_type, client_visible
                        )
                        VALUES ($1, $2, $3, $4, 'received', $5, $6, $7, 'google_drive', true)
                        RETURNING id, document_type, file_name, status, created_at, expiry_date
                        """,
                            client_id,
                            practice_id,
                            document_type,
                            file_name,
                            client["email"],
                            file_size_kb,
                            mime_type,
                        )
                else:
                    raise

            # =========================================================================
            # STEP 6: CREATE TIMELINE EVENT
            # =========================================================================
            try:
                timeline_desc = f"{file_name} uploaded successfully"
                if expiry_result.get("expiry_date"):
                    timeline_desc += f" (Expiry detected: {expiry_result['expiry_date']})"

                await conn.execute(
                    """
                    INSERT INTO timeline_events (
                        client_id, practice_id, event_type, title,
                        description, event_date, client_visible, color
                    )
                    VALUES ($1, $2, 'document_received', 'Document received',
                            $3, NOW(), true, 'success')
                    """,
                    client_id,
                    practice_id,
                    timeline_desc,
                )
            except Exception as e:
                if not self._is_undefined_table_error(e):
                    logger.warning(f"Could not create timeline event for upload: {e}")

            logger.info(
                f"✅ Document processed and stored: {file_name} for client {client_id}, "
                f"size: {file_size_kb}KB, type: {document_type}, "
                f"drive_id: {drive_result.get('file_id', 'N/A')}",
            )

            # =========================================================================
            # STEP 6b: SMART OCR DISPATCH (passport/visa/npwp/nib extraction)
            # =========================================================================
            try:
                from backend.services.documents.ocr_dispatcher_service import (
                    dispatch_ocr_by_folder,
                )

                file_id_for_ocr = drive_result.get("file_id")
                if file_id_for_ocr:
                    doc_category = self._classify_document_category(document_type, file_name)
                    folder_hint = self._get_drive_folder_for_category(doc_category)
                    spawn(
                        dispatch_ocr_by_folder(
                            db_pool=self.pool,
                            client_id=client_id,
                            file_id=file_id_for_ocr,
                            folder_name=folder_hint,
                            filename=file_name,
                            doc_id=doc["id"],
                            document_type=document_type,
                        ),
                    )
                    logger.info(f"Smart OCR dispatch triggered for portal upload: {file_name}")
            except Exception as e:
                logger.error(f"Smart OCR dispatch failed for portal upload {file_name}: {e}")

            # =========================================================================
            # STEP 7: NOTIFY ASSIGNED LEAD
            # =========================================================================
            spawn(
                self._notify_lead_about_document(
                    client_id=client_id,
                    document_name=file_name,
                    document_type=document_type,
                    expiry_date=expiry_result.get("expiry_date"),
                    drive_url=drive_result.get("file_url"),
                ),
            )

            # Update metrics
            self._metrics["uploads_total"] += 1
            if drive_result.get("success"):
                self._metrics["drive_uploads"] += 1
            if ocr_result.get("success"):
                self._metrics["ocr_processed"] += 1

            return {
                "id": doc["id"],
                "type": doc["document_type"],
                "name": doc["file_name"],
                "status": doc["status"],
                "size_kb": file_size_kb,
                "created_at": doc["created_at"].isoformat(),
                "expiry_date": expiry_result.get("expiry_date"),
                "extracted_text_preview": (
                    ocr_result.get("text", "")[:200] + "..."
                    if ocr_result.get("text") and len(ocr_result.get("text", "")) > 200
                    else ocr_result.get("text", "")
                ),
                "processing": {
                    "virus_clean": scan_result["clean"],
                    "ocr_pages": ocr_result.get("pages"),
                    "drive_uploaded": drive_result.get("success", False),
                },
            }

    async def _upload_to_drive(
        self,
        conn: asyncpg.Connection,
        client_id: int,
        client_name: str,
        document_type: str,
        file_content: bytes,
        file_name: str,
        mime_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload file to Google Drive with organized folder structure.

        Folder structure:
        Zantara Portal Uploads/
        └── {client_id}_{client_name}/
            └── {document_type}/
                └── {timestamp}_{file_name}

        Returns:
            {
                "success": bool,
                "file_id": str | None,
                "file_url": str | None,
                "folder_path": str,
                "error": str | None
            }
        """
        result = {
            "success": False,
            "file_id": None,
            "file_url": None,
            "folder_path": "",
            "error": None,
        }

        try:
            from backend.app.core.config import settings
            from backend.services.integrations.google_drive_service import GoogleDriveService
            from backend.services.integrations.team_drive_service import TeamDriveService

            # Try OAuth first, fallback to Service Account
            drive_service = GoogleDriveService(self.pool)
            use_service_account = False

            # Check if Drive is configured
            if not drive_service.is_configured():
                logger.warning("OAuth not configured, trying Service Account...")
                use_service_account = True
            else:
                # Check if we have a valid token
                token = await drive_service.get_valid_token("SYSTEM")
                if not token:
                    logger.warning("No valid OAuth token, trying Service Account...")
                    use_service_account = True

            # Use Service Account if OAuth unavailable
            if use_service_account:
                team_drive = TeamDriveService(db_pool=self.pool)
                if not team_drive.service_account_available:
                    logger.error("Service Account also not available")
                    result["error"] = "No Drive authentication available"
                    return result
                # Use Service Account for upload
                return await self._upload_with_service_account(
                    team_drive,
                    client_id,
                    client_name,
                    document_type,
                    file_content,
                    file_name,
                    mime_type,
                    result,
                )

            # Continue with OAuth
            user_id = "SYSTEM"

            # Get or create root folder for portal uploads
            root_folder_id = await self._get_or_create_drive_folder(
                drive_service,
                user_id,
                folder_name="Zantara Portal Uploads",
                parent_id=settings.google_drive_root_folder_id or "root",
            )

            if not root_folder_id:
                result["error"] = "Failed to create root folder"
                return result

            # Create/get client folder
            safe_client_name = "".join(
                c for c in client_name if c.isalnum() or c in (" ", "_")
            ).rstrip()
            client_folder_name = f"{client_id}_{safe_client_name[:30]}"  # Limit name length

            client_folder_id = await self._get_or_create_drive_folder(
                drive_service, user_id, folder_name=client_folder_name, parent_id=root_folder_id,
            )

            if not client_folder_id:
                result["error"] = "Failed to create client folder"
                return result

            # Create/get document type folder
            type_folder_name = document_type.replace("_", " ").title()
            type_folder_id = await self._get_or_create_drive_folder(
                drive_service, user_id, folder_name=type_folder_name, parent_id=client_folder_id,
            )

            if not type_folder_id:
                result["error"] = "Failed to create type folder"
                return result

            # Add timestamp to filename to avoid collisions
            timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            drive_file_name = f"{timestamp}_{file_name}"

            # Upload file with retry logic
            max_retries = 3
            upload_result = None

            for attempt in range(max_retries):
                try:
                    upload_result = await drive_service.upload_file_to_folder(
                        user_id=user_id,
                        folder_id=type_folder_id,
                        file_content=file_content,
                        file_name=drive_file_name,
                        mime_type=mime_type,
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                        logger.warning(
                            f"Drive upload attempt {attempt + 1} failed, retrying in {wait_time}s: {e}",
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        raise  # All retries exhausted

            if upload_result:
                result["success"] = True
                result["file_id"] = upload_result.get("id")
                result["file_url"] = (
                    upload_result.get("webViewLink")
                    or f"https://drive.google.com/file/d/{upload_result.get('id')}/view"
                )
                result["folder_path"] = (
                    f"Zantara Portal Uploads/{client_folder_name}/{type_folder_name}"
                )

                logger.info(
                    f"📁 File uploaded to Drive: {drive_file_name} (ID: {upload_result.get('id')})",
                )
            else:
                result["error"] = "Upload failed after all retries"

        except Exception as e:
            logger.error(f"Failed to upload to Google Drive: {e}", exc_info=True)
            result["error"] = str(e)

        return result

    async def _upload_with_service_account(
        self,
        team_drive: Any,
        client_id: int,
        client_name: str,
        document_type: str,
        file_content: bytes,
        file_name: str,
        mime_type: str | None,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Upload file using Service Account (fallback when OAuth fails)."""
        try:
            from datetime import datetime

            from backend.app.core.config import settings

            # Create folder structure
            timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            safe_client_name = "".join(
                c for c in client_name if c.isalnum() or c in (" ", "_")
            ).rstrip()[:30]
            folder_path = f"Zantara Portal Uploads/{client_id}_{safe_client_name}/{document_type.replace('_', ' ').title()}"
            drive_file_name = f"{timestamp}_{file_name}"

            # Upload using Service Account
            file_metadata = {
                "name": drive_file_name,
                "parents": [settings.google_drive_root_folder_id or "root"],
            }

            import io

            from googleapiclient.http import MediaIoBaseUpload

            media = MediaIoBaseUpload(
                io.BytesIO(file_content),
                mimetype=mime_type or "application/octet-stream",
                resumable=True,
            )

            uploaded_file = (
                team_drive.drive_service.files()
                .create(body=file_metadata, media_body=media, fields="id, name, webViewLink")
                .execute()
            )

            result["success"] = True
            result["file_id"] = uploaded_file.get("id")
            result["file_url"] = uploaded_file.get(
                "webViewLink", f"https://drive.google.com/file/d/{uploaded_file.get('id')}/view",
            )
            result["folder_path"] = folder_path
            result["method"] = "service_account"

            logger.info(
                f"📁 File uploaded via Service Account: {drive_file_name} (ID: {uploaded_file.get('id')})",
            )

        except Exception as e:
            logger.error(f"Service Account upload failed: {e}", exc_info=True)
            result["error"] = f"Service Account upload failed: {str(e)}"

        return result

    async def _get_or_create_drive_folder(
        self, drive_service: Any, user_id: str, folder_name: str, parent_id: str = "root",
    ) -> str | None:
        """
        Get existing folder or create new one in Google Drive.

        Returns:
            Folder ID or None if failed
        """
        try:
            # Search for existing folder using list_files with filter
            files_result = await drive_service.list_files(
                user_id=user_id, folder_id=parent_id, page_size=100,
            )

            for file in files_result.get("files", []):
                if (
                    file.get("name") == folder_name
                    and file.get("mimeType") == "application/vnd.google-apps.folder"
                ):
                    logger.debug(f"Found existing folder '{folder_name}' with ID: {file['id']}")
                    return file["id"]

            # Create new folder
            new_folder = await drive_service.create_folder(
                user_id=user_id, name=folder_name, parent_id=parent_id,
            )

            logger.info(f"Created new folder '{folder_name}' with ID: {new_folder.get('id')}")
            return new_folder.get("id")

        except Exception as e:
            logger.error(f"Failed to get/create folder '{folder_name}': {e}")
            return None

    async def _notify_lead_about_document(
        self,
        client_id: int,
        document_name: str,
        document_type: str,
        expiry_date: str | None = None,
        drive_url: str | None = None,
    ) -> None:
        """
        Send email notification to assigned lead when client uploads a document.

        This runs async (fire-and-forget) to not block the upload response.
        """
        try:
            from backend.services.integrations.zoho_email_service import ZohoEmailService

            zoho_service = ZohoEmailService(self.pool)

            async with self.pool.acquire() as conn:
                # Get client name and assigned lead
                client = await conn.fetchrow(
                    """
                    SELECT c.full_name, c.assigned_to
                    FROM clients c
                    WHERE c.id = $1
                    """,
                    client_id,
                )

                if not client:
                    logger.debug(f"Client {client_id} not found, skipping notification")
                    return

                # Fallback to admin if no assigned lead
                lead_email = client["assigned_to"] or "zero@balizero.com"

                # Build email content
                doc_type_display = document_type.replace("_", " ").title()

                subject = f"📄 Nuovo Documento Caricato - {client['full_name']}"

                # Build extra info section
                extra_info = ""
                if expiry_date:
                    extra_info += f"• Data Scadenza Rilevata: {expiry_date}\n"
                if drive_url:
                    extra_info += f"• Link Drive: {drive_url}\n"

                body = f"""Ciao,

Il cliente {client["full_name"]} ha caricato un nuovo documento nel portale.

Dettagli:
• File: {document_name}
• Tipo: {doc_type_display}
• Cliente: {client["full_name"]}
{extra_info}
Accedi al workspace per visualizzare e verificare il documento:
https://kita.balizero.com/clients/{client_id}

---
Questa è una notifica automatica da Bali Zero CRM.
"""

                # Primary: Brevo
                sent = False
                try:
                    import os

                    import httpx

                    _api_url = os.getenv(
                        "INTERNAL_EMAIL_API_URL",
                        "https://nuzantara-rag.fly.dev/api/notifications/send-email",
                    )
                    _api_key = os.getenv("NUZANTARA_API_KEY", "")
                    html_body = body.replace("\n", "<br>")
                    async with httpx.AsyncClient(timeout=30.0) as http_client:
                        resp = await http_client.post(
                            _api_url,
                            headers={"X-API-Key": _api_key},
                            json={"to": lead_email, "subject": subject, "body": html_body},
                        )
                        resp.raise_for_status()
                    sent = True
                    logger.info(f"📧 Document upload notification sent to {lead_email} via Brevo")
                except Exception as brevo_err:
                    logger.warning(f"Brevo failed for doc notification, trying Zoho: {brevo_err}")

                # Fallback: Zoho
                if not sent:
                    await zoho_service.send_email(
                        to_email=lead_email,
                        subject=subject,
                        body=body,
                    )
                    logger.info(
                        f"📧 Document upload notification sent to {lead_email} via Zoho",
                    )

                # Also insert CRM notification alert for the bell
                try:
                    await conn.execute(
                        """
                        INSERT INTO notification_alerts
                            (client_id, alert_type, status, message, email_subject)
                        VALUES ($1, 'portal_document_upload', 'sent', $2, $3)
                        ON CONFLICT ON CONSTRAINT uq_notification_alert_daily DO NOTHING
                        """,
                        client_id,
                        f"{client['full_name']} uploaded {document_type.replace('_', ' ')} via portal",
                        f"[Portal] {client['full_name']} uploaded {document_type.replace('_', ' ').title()}",
                    )
                except Exception as alert_err:
                    logger.debug(f"CRM alert insert failed (non-critical): {alert_err}")

        except Exception as e:
            # Don't fail upload if notification fails
            logger.error(f"Failed to send document upload notification: {e}", exc_info=True)


__all__ = ["PortalDocumentsMixin"]
