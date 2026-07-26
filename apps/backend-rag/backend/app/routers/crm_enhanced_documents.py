"""
CRM Enhanced - Document Management Endpoints

Split from crm_enhanced.py for maintainability.
Provides: document CRUD, categories, OCR status, visa extraction,
document upload (Base64 + Google Drive), document soft-delete.
"""

import base64
import hashlib
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.deps.crm_service_write import verify_crm_write_key
from backend.app.routers.crm_enhanced import (
    DocumentCreate,
    DocumentUpdate,
    _auto_ocr_visa,
    _dispatch_ocr_by_folder,
)
from backend.app.utils.crm_utils import verify_client_access
from backend.app.utils.logging_utils import get_logger
from backend.core.cache import invalidate_cache
from backend.db.repositories.client_repository import CORE_OWNER_IDS_SQL
from backend.phone_lock import lock_cores, phone_core, phone_value_state
from backend.services.common.background import spawn
from backend.services.crm.document_categorizer import CATEGORY_TO_FOLDER, auto_categorize_document
from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService

logger = get_logger(__name__)


def _access_not_preverified() -> bool:
    return False


def _parse_date_or_none(date_str: str | None) -> date | None:
    """Parse YYYY-MM-DD date string or return None."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        logger.debug(
            "crm_enhanced_documents.parse_date_invalid",
            extra={"raw": str(date_str)[:32]},
        )
        return None


def _row_get(row: Any, key: str) -> Any:
    """Subscript a DB row (asyncpg Record / dict), tolerating missing keys —
    test doubles built before a column was added must read as absent, not
    crash the gate."""
    try:
        return row[key]
    except (KeyError, TypeError):
        return None


router = APIRouter(prefix="/api/crm", tags=["crm-enhanced-documents"])

# ============================================
# DOCUMENTS ENDPOINTS
# ============================================


@router.get("/clients/{client_id}/documents")
async def get_client_documents(
    client_id: int,
    category: str | None = Query(
        None,
        description="Filter by category: immigration, pma, tax, personal",
    ),
    include_archived: bool = Query(False, description="Include archived documents"),
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> list[Any]:
    """
    Get all documents for a client, optionally filtered by category.
    """
    async with pool.acquire() as conn:
        await verify_client_access(client_id, current_user, conn, allow_assigned=True)
        query = """
            SELECT
                d.id, d.document_type, d.document_category,
                d.file_name, d.file_id, d.file_url, d.google_drive_file_url,
                d.status, d.expiry_date, d.notes, d.is_archived,
                d.family_member_id, d.practice_id,
                d.created_at, d.updated_at,
                fm.full_name as family_member_name,
                CASE
                    WHEN d.expiry_date <= CURRENT_DATE THEN 'expired'
                    WHEN d.expiry_date <= CURRENT_DATE + INTERVAL '8 months' THEN 'red'
                    WHEN d.expiry_date <= CURRENT_DATE + INTERVAL '12 months' THEN 'yellow'
                    ELSE 'green'
                END as alert_color
            FROM documents d
            LEFT JOIN client_family_members fm ON d.family_member_id = fm.id
            WHERE d.client_id = $1
        """
        params = [client_id]
        param_num = 2

        if category:
            query += f" AND d.document_category = ${param_num}"
            params.append(category)
            param_num += 1

        if not include_archived:
            query += " AND (d.is_archived IS NULL OR d.is_archived = false)"

        query += " ORDER BY d.document_category, d.document_type"

        docs = await conn.fetch(query, *params)
        return [dict(d) for d in docs]


@router.post("/clients/{client_id}/documents")
async def create_document(
    client_id: int,
    data: DocumentCreate,
    background_tasks: BackgroundTasks,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Add a document to a client. Auto-triggers OCR for passport documents.
    """
    async with pool.acquire() as conn:
        await verify_client_access(client_id, current_user, conn, allow_assigned=True, write=True)
        # Sanitize date field - convert string to date object for asyncpg
        expiry_date = None
        if data.expiry_date:
            try:
                expiry_date = datetime.strptime(data.expiry_date, "%Y-%m-%d").date()
            except ValueError:
                expiry_date = None

        doc_id = await conn.fetchval(
            """
            INSERT INTO documents (
                client_id, document_type, document_category,
                file_name, file_id, file_url, google_drive_file_url,
                expiry_date, notes, family_member_id, practice_id,
                status, storage_type
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'google_drive', 'google_drive')
            RETURNING id
            """,
            client_id,
            data.document_type,
            data.document_category,
            data.file_name,
            data.file_id,
            data.file_url,
            data.google_drive_file_url,
            expiry_date,  # Sanitized
            data.notes,
            data.family_member_id,
            data.practice_id,
        )

        # Auto-trigger OCR via dispatcher
        ocr_triggered = False
        if data.file_id and data.document_type:
            # Determine folder from category
            folder_hint = ""
            cat = (data.document_category or "").lower()
            if cat == "immigration":
                folder_hint = "01_Immigration"
            elif cat == "tax":
                folder_hint = "03_Tax"
            elif cat == "company":
                folder_hint = "02_Company"
            background_tasks.add_task(
                _dispatch_ocr_by_folder,
                pool,
                client_id,
                data.file_id,
                folder_hint,
                data.file_name or data.document_type,
                doc_id,
            )
            # Mark document as pending OCR
            await conn.execute(
                "UPDATE documents SET ocr_status = 'pending' WHERE id = $1",
                doc_id,
            )
            ocr_triggered = True

        # Notify client via portal that a new document was added
        try:
            from backend.services.portal.portal_notification_service import (
                PortalNotificationService,
            )

            notif_service = PortalNotificationService(pool)
            spawn(
                notif_service.notify_document_uploaded(
                    client_id=client_id,
                    document_type=data.document_type,
                    sent_by=current_user.get("email", "system"),
                    practice_id=data.practice_id,
                ),
            )
        except Exception as e:
            logger.error("Portal notification for doc upload failed: %s", e)

        await invalidate_cache("zantara:crm_clients_stats:*")
        return {
            "id": doc_id,
            "success": True,
            "ocr_triggered": ocr_triggered,
        }


@router.post("/clients/{client_id}/documents/bulk")
async def create_documents_bulk(
    client_id: int,
    documents: list[DocumentCreate],
    background_tasks: BackgroundTasks,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Bulk insert documents for a client - optimized for migration.

    This endpoint allows inserting multiple documents in a single transaction,
    significantly improving performance during large data migrations.

    Args:
        client_id: Client database ID
        documents: Array of documents to insert (max 100 per request)
        background_tasks: FastAPI background tasks for OCR
        pool: Database connection pool
        current_user: Authenticated user

    Returns:
        {
            "success": true,
            "inserted": 50,
            "document_ids": [123, 124, ...],
            "ocr_triggered": 2,
            "failed": 0
        }

    Raises:
        HTTPException: If max limit exceeded or client not found
    """
    user_email = current_user.get("email", "").lower()

    # Enforce maximum batch size
    MAX_BATCH_SIZE = 100
    if len(documents) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_BATCH_SIZE} documents per request. You provided {len(documents)}.",
        )

    if len(documents) == 0:
        raise HTTPException(status_code=400, detail="No documents provided")

    async with pool.acquire() as conn:
        await verify_client_access(client_id, current_user, conn, allow_assigned=True, write=True)

        inserted_ids = []
        ocr_count = 0
        failed_count = 0

        # Use transaction for atomic bulk insert
        async with conn.transaction():
            for doc in documents:
                try:
                    # Sanitize expiry_date: convert string to date object
                    expiry_date = None
                    if doc.expiry_date:
                        try:
                            expiry_date = datetime.strptime(doc.expiry_date, "%Y-%m-%d").date()
                        except ValueError:
                            logger.warning(
                                f"Invalid expiry_date format for {doc.file_name}: {doc.expiry_date}",
                            )
                            expiry_date = None

                    # Insert document
                    doc_id = await conn.fetchval(
                        """
                        INSERT INTO documents (
                            client_id, document_type, document_category,
                            file_name, file_id, file_url, google_drive_file_url,
                            expiry_date, notes, family_member_id, practice_id,
                            status, storage_type, uploaded_by
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'active', 'google_drive', $12)
                        RETURNING id
                        """,
                        client_id,
                        doc.document_type,
                        doc.document_category,
                        doc.file_name,
                        doc.file_id,
                        doc.file_url,
                        doc.google_drive_file_url,
                        expiry_date,
                        doc.notes,
                        doc.family_member_id,
                        doc.practice_id,
                        user_email,  # Track who uploaded
                    )

                    inserted_ids.append(doc_id)

                    # Queue OCR for passport documents
                    if doc.file_id and doc.document_type:
                        folder_hint = ""
                        cat = (doc.document_category or "").lower()
                        if cat == "immigration":
                            folder_hint = "01_Immigration"
                        elif cat == "tax":
                            folder_hint = "03_Tax"
                        elif cat == "company":
                            folder_hint = "02_Company"
                        background_tasks.add_task(
                            _dispatch_ocr_by_folder,
                            pool,
                            client_id,
                            doc.file_id,
                            folder_hint,
                            doc.file_name or doc.document_type,
                            doc_id,
                        )
                        await conn.execute(
                            "UPDATE documents SET ocr_status = 'pending' WHERE id = $1",
                            doc_id,
                        )
                        ocr_count += 1

                except Exception as e:
                    logger.error(f"Failed to insert document {doc.file_name}: {e}")
                    failed_count += 1
                    # Continue with other documents

        logger.info(
            f"Bulk inserted {len(inserted_ids)} documents for client {client_id}. "
            f"OCR queued: {ocr_count}, Failed: {failed_count}",
        )

        await invalidate_cache("zantara:crm_clients_stats:*")
        return {
            "success": True,
            "inserted": len(inserted_ids),
            "document_ids": inserted_ids,
            "ocr_triggered": ocr_count,
            "failed": failed_count,
            "client_id": client_id,
        }


@router.patch("/clients/{client_id}/documents/{doc_id}")
async def update_document(
    client_id: int,
    doc_id: int,
    data: DocumentUpdate,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Update a document.
    """
    # Date field that needs string → date object conversion for asyncpg
    date_fields = {"expiry_date"}

    update_fields = []
    values = []
    param_num = 1

    for field, value in data.model_dump(exclude_unset=True).items():
        # Convert date fields: empty string → None, valid string → date object
        if field in date_fields:
            if value == "" or value is None:
                value = None
            elif isinstance(value, str):
                try:
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    value = None

        if value is not None:
            update_fields.append(f"{field} = ${param_num}")
            values.append(value)
            param_num += 1

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.extend([doc_id, client_id])

    async with pool.acquire() as conn:
        await verify_client_access(client_id, current_user, conn, allow_assigned=True, write=True)
        result = await conn.execute(
            f"""
            UPDATE documents
            SET {", ".join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_num} AND client_id = ${param_num + 1}
            """,
            *values,
        )

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Document not found")

    await invalidate_cache("zantara:crm_clients_stats:*")
    return {"success": True}


@router.delete("/clients/{client_id}/documents/{doc_id}")
async def archive_document(
    client_id: int,
    doc_id: int,
    permanent: bool = Query(False, description="Permanently delete instead of archive"),
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Archive or delete a document.
    """
    async with pool.acquire() as conn:
        await verify_client_access(client_id, current_user, conn, allow_assigned=True, write=True)
        if permanent:
            result = await conn.execute(
                "DELETE FROM documents WHERE id = $1 AND client_id = $2",
                doc_id,
                client_id,
            )
            action = "deleted"
        else:
            result = await conn.execute(
                "UPDATE documents SET is_archived = true, updated_at = NOW() WHERE id = $1 AND client_id = $2",
                doc_id,
                client_id,
            )
            action = "archived"

        if result in ("DELETE 0", "UPDATE 0"):
            raise HTTPException(status_code=404, detail="Document not found")

    await invalidate_cache("zantara:crm_clients_stats:*")
    return {"success": True, "action": action}


# ============================================
# DOCUMENT CATEGORIES ENDPOINT
# ============================================


@router.get("/document-categories")
async def get_document_categories(
    pool: Any = Depends(get_database_pool),
    _current_user: dict = Depends(get_current_user),
) -> list[Any]:
    """Get all document categories for dropdowns."""
    async with pool.acquire() as conn:
        categories = await conn.fetch(
            """
            SELECT code, name, category_group, description, has_expiry
            FROM document_categories
            WHERE active = true
            ORDER BY sort_order, name
            """,
        )
        return [dict(c) for c in categories]


# ============================================
# OCR STATUS ENDPOINT
# ============================================


@router.get("/clients/{client_id}/ocr-status")
async def get_client_ocr_status(
    client_id: int,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get OCR processing status for a client's documents.
    Frontend polls this to know when OCR completes.
    """
    async with pool.acquire() as conn:
        await verify_client_access(client_id, current_user, conn, allow_assigned=True)
        docs = await conn.fetch(
            """
            SELECT id, document_type, file_name, ocr_status, ocr_completed_at,
                   ocr_extracted_data
            FROM documents
            WHERE client_id = $1
              AND ocr_status IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 10
            """,
            client_id,
        )

        pending = sum(1 for d in docs if d["ocr_status"] in ("pending", "processing"))
        completed = sum(1 for d in docs if d["ocr_status"] == "completed")

        return {
            "client_id": client_id,
            "pending_ocr": pending,
            "completed_ocr": completed,
            "documents": [dict(d) for d in docs],
        }


@router.post("/clients/{client_id}/extract-visa")
async def extract_visa_data(
    client_id: int,
    body: dict = Body(...),
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Extract visa/KITAS data from a document using Gemini Vision OCR.
    Updates the document's issue_date and expiry_date.

    Body: {"file_id": "...", "doc_id": 123}
    """
    async with pool.acquire() as conn:
        await verify_client_access(client_id, current_user, conn, allow_assigned=True, write=True)
    file_id = body.get("file_id")
    doc_id = body.get("doc_id")
    if not file_id:
        raise HTTPException(status_code=400, detail="file_id required")

    return await _auto_ocr_visa(pool, client_id, file_id, doc_id)


# ============================================
# EXPIRY ALERTS ENDPOINTS
# ============================================


# NEW ENDPOINTS (Frontend Integration)
# ============================================


class DocumentUploadBase64(BaseModel):
    file: str  # Base64
    file_name: str
    document_type: str
    mime_type: str | None = None
    notes: str | None = None
    subfolder_hint: str | None = None
    document_category: str | None = None
    expiry_date: str | None = None
    family_member_id: int | None = None
    practice_id: int | None = None
    company_id: int | None = None
    # Ownership token (Codex 2026-07-19 round 12, F12 gap 3): intake delivery
    # resolves the target client BY PHONE in a separate earlier request; this
    # carries the resolved phone core into the upload so the handler can prove,
    # atomically with the documents INSERT, that the target row still owns that
    # phone. Optional — human/frontend uploads address a reviewed client id and
    # don't send it.
    expected_phone_core: str | None = None


@router.post("/clients/{client_id}/documents/upload")
async def upload_document_base64(
    client_id: int,
    data: DocumentUploadBase64 = Body(...),
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    access_already_verified: bool = Depends(_access_not_preverified),
) -> dict[str, Any]:
    """
    Upload a document via Base64 (for frontend integration).
    Handles Google Drive upload and document creation.
    """
    # RBAC check before processing upload
    if access_already_verified is not True:
        async with pool.acquire() as _conn:
            await verify_client_access(
                client_id, current_user, _conn, allow_assigned=True, write=True
            )

    try:
        # Decode Base64
        try:
            file_content = base64.b64decode(data.file)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 file content")

        # Compute content hash for dedup
        content_hash = hashlib.md5(file_content).hexdigest()

        # Determine category — use explicit override or auto-categorize from filename
        if data.document_category:
            category = data.document_category
        else:
            cat_result = auto_categorize_document(data.file_name)
            category = cat_result["document_category"]
        folder_name = CATEGORY_TO_FOLDER.get(category, "99_Misc")

        async with pool.acquire() as conn:
            client = await conn.fetchrow(
                "SELECT id, full_name, google_drive_folder_id, client_type,"
                "       phone, phone_normalized, whatsapp"
                "  FROM clients WHERE id = $1",
                client_id,
            )

            if not client:
                raise HTTPException(status_code=404, detail="Client not found")

            def _owns_expected_core(row: Any) -> bool:
                # Column CONSISTENCY, not membership (Codex round 13, F12g3):
                # ownership is proven only when the row's phone columns agree
                # on EXACTLY the expected core. A divergent row (phone=A,
                # phone_normalized=B) is the same untrustworthy stale state the
                # delivery gate fails closed on — expected∈{A,B} must refuse.
                # Round 14 F19 + round 15 F23: absent/unusable/usable comes
                # from THE shared primitive (phone_value_state) — 'absent'
                # includes digit-free free-text like "n/a" (not a phone
                # CLAIM), 'unusable' (digit signal but no core) fails closed.
                # Round 16 F25: whatsapp joins the consistency set — the
                # resolver (UPSERT_MATCH_SQL) finds whatsapp-only owners, so
                # a row whose ONLY phone-ish value is whatsapp must be able
                # to prove ownership here, or the resolver arm can never
                # complete its own defining case.
                cores = set()
                for raw in (row["phone"], row["phone_normalized"], _row_get(row, "whatsapp")):
                    state, core = phone_value_state(raw)
                    if state == "absent":
                        continue
                    if state == "unusable":
                        return False
                    cores.add(core)
                return cores == {data.expected_phone_core}

            async def _sole_owner_is_target(_conn: Any) -> bool:
                # Round 14, F18: the token asserts SOLE ownership, not just
                # "the resolved row still owns the core" — a second legitimate
                # owner (allow_duplicate_phone create) appeared since the
                # resolve would make a fresh resolve ambiguous, so the upload
                # must refuse too. All cooperative phone writers serialize on
                # the phonecore advisory lock, making the authoritative in-TX
                # run of this check race-safe against them.
                rows = await _conn.fetch(
                    CORE_OWNER_IDS_SQL, [data.expected_phone_core]
                )
                return [r["id"] for r in rows] == [client_id]

            if data.expected_phone_core:
                # Fast pre-check (Codex round 12, F12 gap 3): the caller
                # resolved this client id BY PHONE in an earlier request; if
                # the row no longer owns that core — or no longer owns it
                # ALONE (F18) — uploading would attach the document to a
                # possibly wrong identity. Refuse before any Drive work. The
                # authoritative check re-runs under lock at INSERT.
                if not _owns_expected_core(client):
                    raise HTTPException(
                        status_code=409,
                        detail="phone_ownership_changed — re-resolve the client before upload",
                    )
                if not await _sole_owner_is_target(conn):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "phone_ownership_ambiguous — the phone core has "
                            "multiple live owners, re-resolve the client before upload"
                        ),
                    )

            if data.company_id is not None:
                company_link = await conn.fetchrow(
                    """
                    SELECT company_id
                    FROM client_company_links
                    WHERE client_id = $1 AND company_id = $2
                    LIMIT 1
                    """,
                    client_id,
                    data.company_id,
                )
                if not company_link:
                    raise HTTPException(
                        status_code=400, detail="Company is not linked to this client"
                    )

            drive_service = ServiceAccountDriveService()

            # Ensure Root Folder Exists — MUST go through the idempotent
            # chokepoint. The old inline create raced against the POST
            # /api/clients background task (passport upload lands ~15-25s
            # after creation, while the 16 subfolders are still being built)
            # and produced a twin "{id}_{name}" root folder on every new
            # client created with a passport scan.
            root_folder_id = client["google_drive_folder_id"]
            if not root_folder_id:
                try:
                    ensure_result = await drive_service.ensure_client_folder(
                        client_id=client["id"],
                        client_name=client["full_name"],
                        client_type=client["client_type"] or "individual",
                        db_pool=pool,
                    )
                    root_folder_id = ensure_result["root_folder_id"]
                except Exception as e:
                    logger.error("Failed to create root folder: %s", e)
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to create root folder: {e}",
                    ) from e

            # Ensure Subfolder Exists (Find or Create)
            try:
                structure = await drive_service.get_folder_structure(
                    root_folder_id=root_folder_id,
                )
            except Exception as e:
                # If structure fetch fails, maybe root folder is missing/deleted?
                # We'll just fail for now, or could try to recreate
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to access folder structure: {e}",
                ) from e

            subfolder = next((f for f in structure["folders"] if f["name"] == folder_name), None)
            if not subfolder:
                # Create subfolder
                try:
                    subfolder_data = await drive_service.create_folder(
                        name=folder_name,
                        parent_id=root_folder_id,
                    )
                    subfolder_id = subfolder_data["id"]
                except Exception as e:
                    raise HTTPException(
                        status_code=500, detail=f"Failed to create subfolder: {e}"
                    ) from e
            else:
                subfolder_id = subfolder["id"]

            # Handle subfolder_hint for nested subfolders (e.g. "Actual Visa" inside 01_Immigration)
            target_subfolder_id = subfolder_id
            subfolder_value = None  # for documents.subfolder column

            if data.subfolder_hint and data.subfolder_hint in ("Actual Visa", "Previous Visa"):
                subfolder_value = data.subfolder_hint
                # Find or create the nested subfolder inside the category folder
                try:
                    nested_structure = await drive_service.get_folder_structure(
                        root_folder_id=subfolder_id,
                    )
                    nested_folder = next(
                        (
                            f
                            for f in nested_structure["folders"]
                            if f["name"] == data.subfolder_hint
                        ),
                        None,
                    )
                    if not nested_folder:
                        nested_data = await drive_service.create_folder(
                            name=data.subfolder_hint,
                            parent_id=subfolder_id,
                        )
                        target_subfolder_id = nested_data["id"]
                    else:
                        target_subfolder_id = nested_folder["id"]
                except Exception as e:
                    logger.warning(f"Could not resolve subfolder_hint '{data.subfolder_hint}': {e}")

                # Visa rotation: if uploading to "Actual Visa", move existing actual to "Previous Visa"
                if data.subfolder_hint == "Actual Visa":
                    existing_actual = await conn.fetchrow(
                        """SELECT d.id, d.file_id FROM documents d
                           WHERE d.client_id = $1 AND d.subfolder = 'Actual Visa'
                             AND (d.is_archived IS NOT TRUE)
                           ORDER BY d.created_at DESC LIMIT 1""",
                        client_id,
                    )
                    if existing_actual and existing_actual["file_id"]:
                        # Find or create "Previous Visa" folder
                        prev_folder = (
                            next(
                                (
                                    f
                                    for f in nested_structure["folders"]
                                    if f["name"] == "Previous Visa"
                                ),
                                None,
                            )
                            if nested_structure
                            else None
                        )
                        if not prev_folder:
                            try:
                                prev_data = await drive_service.create_folder(
                                    name="Previous Visa",
                                    parent_id=subfolder_id,
                                )
                                prev_folder_id = prev_data["id"]
                            except Exception as e:
                                logger.error("Failed to create Previous Visa folder: %s", e)
                                prev_folder_id = None
                        else:
                            prev_folder_id = prev_folder["id"]

                        if prev_folder_id:
                            try:
                                await drive_service.move_file(
                                    user_email=current_user.get("email", ""),
                                    file_id=existing_actual["file_id"],
                                    new_parent_id=prev_folder_id,
                                    old_parent_id=target_subfolder_id,
                                )
                                await conn.execute(
                                    "UPDATE documents SET subfolder = 'Previous Visa', updated_at = NOW() WHERE id = $1",
                                    existing_actual["id"],
                                )
                                logger.info(
                                    f"Rotated visa doc {existing_actual['id']} to Previous Visa"
                                )
                            except Exception as e:
                                logger.error("Visa rotation failed: %s", e)

            # Upload File
            try:
                upload_result = await drive_service.upload_file_to_folder(
                    folder_id=target_subfolder_id,
                    file_content=file_content,
                    file_name=data.file_name,
                    mime_type=data.mime_type,
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Failed to upload to drive: {e}"
                ) from e

            # Create Document Record. When the caller sent an ownership token,
            # the INSERT commits ATOMICALLY with a re-verification under the
            # cooperative phonecore lock (Codex round 12, F12 gap 3): a
            # cooperative writer moving this phone blocks on the lock until we
            # commit; a non-cooperative move is caught by the locked re-read.
            # The Drive file already exists either way — an orphaned Drive file
            # is recoverable noise, a mis-attached document is not.
            async with conn.transaction():
                if data.expected_phone_core:
                    await lock_cores(
                        conn,
                        data.expected_phone_core,
                        phone_core(client["phone"]),
                        phone_core(client["phone_normalized"]),
                    )
                    # FOR UPDATE (round 13, F12g3): the advisory locks stop
                    # only COOPERATIVE writers — the row lock makes the
                    # re-check atomic with the INSERT against direct writers
                    # too (any concurrent UPDATE blocks until we commit).
                    _recheck = await conn.fetchrow(
                        "SELECT phone, phone_normalized, whatsapp FROM clients"
                        " WHERE id = $1 FOR UPDATE",
                        client_id,
                    )
                    if (
                        _recheck is None
                        or not _owns_expected_core(_recheck)
                        or not await _sole_owner_is_target(conn)
                    ):
                        # F17: the Drive file already exists and has no
                        # documents row — log the id as a structured
                        # reconciliation marker (no delete API on the service;
                        # an orphaned file is recoverable noise, a
                        # mis-attached document is not).
                        logger.error(
                            "orphaned_drive_file file_id=%s client_id=%s "
                            "reason=phone_ownership_changed",
                            upload_result.get("id"),
                            client_id,
                        )
                        raise HTTPException(
                            status_code=409,
                            detail=(
                                "phone_ownership_changed during upload — "
                                "document NOT attached, re-resolve the client"
                            ),
                        )
                doc_id = await conn.fetchval(
                    """
                    INSERT INTO documents (
                        client_id, document_type, document_category,
                        file_name, file_id, file_url, google_drive_file_url,
                        status, storage_type, notes, subfolder, expiry_date, content_hash,
                        family_member_id, practice_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'active', 'google_drive', $8, $9, $10, $11, $12, $13)
                    RETURNING id
                    """,
                    client_id,
                    data.document_type,
                    category,
                    data.file_name,
                    upload_result["id"],
                    upload_result.get("webViewLink"),
                    upload_result.get("webViewLink"),
                    data.notes,
                    subfolder_value,
                    _parse_date_or_none(data.expiry_date),
                    content_hash,
                    data.family_member_id,
                    data.practice_id,
                )

            company_document_id = None
            if data.company_id is not None:
                company_document_id = await conn.fetchval(
                    """
                    SELECT id
                    FROM company_documents
                    WHERE company_id = $1 AND google_drive_file_id = $2
                    """,
                    data.company_id,
                    upload_result["id"],
                )
                if company_document_id is None:
                    size_raw = upload_result.get("size")
                    file_size_kb = None
                    if size_raw:
                        try:
                            file_size_kb = max(1, int(size_raw) // 1024)
                        except (TypeError, ValueError):
                            file_size_kb = None

                    company_document_id = await conn.fetchval(
                        """
                        INSERT INTO company_documents (
                            company_id, document_type, google_drive_file_id,
                            google_drive_file_url, file_name, file_size_kb,
                            mime_type, notes, uploaded_by, status, is_verified
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'active', false)
                        RETURNING id
                        """,
                        data.company_id,
                        data.document_type,
                        upload_result["id"],
                        upload_result.get("webViewLink"),
                        data.file_name,
                        file_size_kb,
                        data.mime_type,
                        data.notes,
                        current_user.get("email", "system"),
                    )

            # Trigger OCR via dispatcher
            background_tasks.add_task(
                _dispatch_ocr_by_folder,
                pool,
                client_id,
                upload_result["id"],
                folder_name,
                data.file_name,
                doc_id,
                data.document_type,
            )
            await conn.execute(
                "UPDATE documents SET ocr_status = 'pending' WHERE id = $1",
                doc_id,
            )

            await invalidate_cache("zantara:crm_clients_stats:*")
            return {
                "success": True,
                "document_id": doc_id,
                "file_url": upload_result.get("webViewLink"),
                "ocr_triggered": True,
                "company_document_id": company_document_id,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upload failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/internal/clients/{client_id}/documents/upload")
async def upload_document_base64_internal(
    client_id: int,
    data: DocumentUploadBase64 = Body(...),
    pool: Any = Depends(get_database_pool),
    actor: str = Depends(verify_crm_write_key),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> dict[str, Any]:
    """Service-to-service intake upload path.

    Authenticated by ``X-CRM-Write-Key`` and hard-gated by
    ``WA_MIRROR_CRM_WRITE_ENABLED``. The actual upload implementation is the same
    path used by the frontend/manual reviewer; only the RBAC pre-check is skipped
    because Pro-side intake already resolved and gate-checked the target client.
    """
    return await upload_document_base64(
        client_id=client_id,
        data=data,
        pool=pool,
        current_user={
            "email": actor,
            "user_id": actor,
            "role": "service",
            "permissions": ["crm:write"],
        },
        background_tasks=background_tasks,
        access_already_verified=True,
    )


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    permanent: bool = False,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Delete a document (Soft delete by default).
    """
    async with pool.acquire() as conn:
        # Lookup client_id from document for RBAC check
        doc_row = await conn.fetchrow("SELECT client_id FROM documents WHERE id = $1", doc_id)
        if doc_row:
            await verify_client_access(
                doc_row["client_id"], current_user, conn, allow_assigned=True, write=True
            )
        if permanent:
            result = await conn.execute("DELETE FROM documents WHERE id = $1", doc_id)
        else:
            result = await conn.execute(
                "UPDATE documents SET is_archived = true, updated_at = NOW() WHERE id = $1",
                doc_id,
            )

        if result == "DELETE 0" or result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Document not found")

    await invalidate_cache("zantara:crm_clients_stats:*")
    return {"success": True, "action": "deleted" if permanent else "archived"}
