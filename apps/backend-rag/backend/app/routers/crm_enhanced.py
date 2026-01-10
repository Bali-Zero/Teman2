"""
CRM Enhanced Routes - Family Members, Documents, Expiry Alerts

Provides endpoints for:
- Client family members (spouse, children)
- Document management with categories
- Expiry alerts with color indicators
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import is_crm_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crm", tags=["crm-enhanced"])


# ============================================
# MODELS
# ============================================


class FamilyMemberCreate(BaseModel):
    full_name: str
    relationship: str  # 'spouse', 'child', 'parent', 'sibling', 'other'
    date_of_birth: str | None = None
    nationality: str | None = None
    passport_number: str | None = None
    passport_expiry: str | None = None
    current_visa_type: str | None = None
    visa_expiry: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class FamilyMemberUpdate(BaseModel):
    full_name: str | None = None
    relationship: str | None = None
    date_of_birth: str | None = None
    nationality: str | None = None
    passport_number: str | None = None
    passport_expiry: str | None = None
    current_visa_type: str | None = None
    visa_expiry: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class DocumentCreate(BaseModel):
    document_type: str
    document_category: str | None = None  # 'immigration', 'pma', 'tax', 'personal'
    file_name: str | None = None
    file_id: str | None = None  # Google Drive file ID
    file_url: str | None = None
    google_drive_file_url: str | None = None
    expiry_date: str | None = None
    notes: str | None = None
    family_member_id: int | None = None  # If document belongs to family member
    practice_id: int | None = None


class DocumentUpdate(BaseModel):
    document_type: str | None = None
    document_category: str | None = None
    file_name: str | None = None
    file_id: str | None = None
    file_url: str | None = None
    google_drive_file_url: str | None = None
    expiry_date: str | None = None
    status: str | None = None
    notes: str | None = None
    is_archived: bool | None = None


class ClientProfileUpdate(BaseModel):
    avatar_url: str | None = None
    google_drive_folder_id: str | None = None
    date_of_birth: str | None = None
    passport_expiry: str | None = None
    company_name: str | None = None


# ============================================
# CLIENT PROFILE ENDPOINTS
# ============================================


@router.get("/clients/{client_id}/profile")
async def get_client_profile(
    client_id: int, pool=Depends(get_database_pool), current_user: dict = Depends(get_current_user)
):
    """
    Get enhanced client profile with family members, documents, and expiry alerts.
    """
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    async with pool.acquire() as conn:
        # Get client with extended fields
        client = await conn.fetchrow(
            """
            SELECT
                id, uuid, full_name, email, phone, whatsapp,
                nationality, passport_number, passport_expiry,
                date_of_birth, avatar_url, company_name,
                google_drive_folder_id, status, client_type,
                assigned_to, address, notes, tags, custom_fields,
                first_contact_date, last_interaction_date,
                created_at, updated_at
            FROM clients
            WHERE id = $1
            """,
            client_id,
        )

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # RBAC: Check if user has access to this client
        if not user_is_admin and (client["assigned_to"] or "").lower() != user_email:
            logger.warning(f"RBAC: User {user_email} denied access to client profile {client_id}")
            raise HTTPException(
                status_code=403, detail="You don't have access to this client profile"
            )

        # Get family members
        family_members = await conn.fetch(
            """
            SELECT
                id, full_name, relationship, date_of_birth,
                nationality, passport_number, passport_expiry,
                current_visa_type, visa_expiry, email, phone, notes,
                created_at, updated_at
            FROM client_family_members
            WHERE client_id = $1
            ORDER BY
                CASE relationship
                    WHEN 'spouse' THEN 1
                    WHEN 'child' THEN 2
                    ELSE 3
                END,
                full_name
            """,
            client_id,
        )

        # Get documents grouped by category
        documents = await conn.fetch(
            """
            SELECT
                d.id, d.document_type, d.document_category,
                d.file_name, d.file_id, d.file_url, d.google_drive_file_url,
                d.status, d.expiry_date, d.notes, d.family_member_id,
                d.practice_id, d.created_at, d.updated_at,
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
              AND (d.is_archived IS NULL OR d.is_archived = false)
            ORDER BY d.document_category, d.document_type
            """,
            client_id,
        )

        # Get expiry alerts
        expiry_alerts = await conn.fetch(
            """
            SELECT
                entity_type, entity_id, entity_name, document_type,
                expiry_date, days_until_expiry, alert_color
            FROM client_expiry_alerts_view
            WHERE client_id = $1
              AND alert_color IN ('expired', 'red', 'yellow')
            ORDER BY
                CASE alert_color
                    WHEN 'expired' THEN 1
                    WHEN 'red' THEN 2
                    WHEN 'yellow' THEN 3
                END,
                expiry_date
            """,
            client_id,
        )

        # Get active practices summary
        practices = await conn.fetch(
            """
            SELECT
                p.id, p.status, p.expiry_date,
                pt.code as practice_type_code,
                pt.name as practice_type_name,
                CASE
                    WHEN p.expiry_date <= CURRENT_DATE THEN 'expired'
                    WHEN p.expiry_date <= CURRENT_DATE + INTERVAL '8 months' THEN 'red'
                    WHEN p.expiry_date <= CURRENT_DATE + INTERVAL '12 months' THEN 'yellow'
                    ELSE 'green'
                END as alert_color
            FROM practices p
            JOIN practice_types pt ON p.practice_type_id = pt.id
            WHERE p.client_id = $1
            ORDER BY
                CASE p.status
                    WHEN 'in_progress' THEN 1
                    WHEN 'waiting_documents' THEN 2
                    WHEN 'submitted_to_gov' THEN 3
                    ELSE 4
                END,
                p.created_at DESC
            """,
            client_id,
        )

        return {
            "client": dict(client),
            "family_members": [dict(fm) for fm in family_members],
            "documents": [dict(d) for d in documents],
            "expiry_alerts": [dict(a) for a in expiry_alerts],
            "practices": [dict(p) for p in practices],
            "stats": {
                "family_count": len(family_members),
                "documents_count": len(documents),
                "practices_count": len(practices),
                "expired_count": sum(1 for a in expiry_alerts if a["alert_color"] == "expired"),
                "red_alerts": sum(1 for a in expiry_alerts if a["alert_color"] == "red"),
                "yellow_alerts": sum(1 for a in expiry_alerts if a["alert_color"] == "yellow"),
            },
        }


@router.patch("/clients/{client_id}/profile")
async def update_client_profile(
    client_id: int,
    data: ClientProfileUpdate,
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Update client profile fields (avatar, Google Drive folder, etc.)
    """
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    async with pool.acquire() as conn:
        # Check access
        check = await conn.fetchrow("SELECT assigned_to FROM clients WHERE id = $1", client_id)
        if not check:
            raise HTTPException(status_code=404, detail="Client not found")

        if not user_is_admin and (check["assigned_to"] or "").lower() != user_email:
            raise HTTPException(status_code=403, detail="You don't have access to this client")
    update_fields = []
    values = []
    param_num = 1

    if data.avatar_url is not None:
        update_fields.append(f"avatar_url = ${param_num}")
        values.append(data.avatar_url)
        param_num += 1

    if data.google_drive_folder_id is not None:
        update_fields.append(f"google_drive_folder_id = ${param_num}")
        values.append(data.google_drive_folder_id)
        param_num += 1

    if data.date_of_birth is not None:
        update_fields.append(f"date_of_birth = ${param_num}")
        values.append(data.date_of_birth)
        param_num += 1

    if data.passport_expiry is not None:
        update_fields.append(f"passport_expiry = ${param_num}")
        values.append(data.passport_expiry)
        param_num += 1

    if data.company_name is not None:
        update_fields.append(f"company_name = ${param_num}")
        values.append(data.company_name)
        param_num += 1

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(client_id)

    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE clients
            SET {", ".join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_num}
            """,
            *values,
        )

    return {"success": True, "message": "Client profile updated"}


# ============================================
# FAMILY MEMBERS ENDPOINTS
# ============================================


@router.get("/clients/{client_id}/family")
async def get_family_members(
    client_id: int, pool=Depends(get_database_pool), current_user: dict = Depends(get_current_user)
):
    """Get all family members for a client."""
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    async with pool.acquire() as conn:
        # Check access
        check = await conn.fetchrow("SELECT assigned_to FROM clients WHERE id = $1", client_id)
        if not check:
            raise HTTPException(status_code=404, detail="Client not found")

        if not user_is_admin and (check["assigned_to"] or "").lower() != user_email:
            raise HTTPException(status_code=403, detail="You don't have access to this client")

        members = await conn.fetch(
            """
            SELECT
                id, full_name, relationship, date_of_birth,
                nationality, passport_number, passport_expiry,
                current_visa_type, visa_expiry, email, phone, notes,
                created_at, updated_at,
                CASE
                    WHEN passport_expiry <= CURRENT_DATE THEN 'expired'
                    WHEN passport_expiry <= CURRENT_DATE + INTERVAL '8 months' THEN 'red'
                    WHEN passport_expiry <= CURRENT_DATE + INTERVAL '12 months' THEN 'yellow'
                    ELSE 'green'
                END as passport_alert,
                CASE
                    WHEN visa_expiry <= CURRENT_DATE THEN 'expired'
                    WHEN visa_expiry <= CURRENT_DATE + INTERVAL '8 months' THEN 'red'
                    WHEN visa_expiry <= CURRENT_DATE + INTERVAL '12 months' THEN 'yellow'
                    ELSE 'green'
                END as visa_alert
            FROM client_family_members
            WHERE client_id = $1
            ORDER BY
                CASE relationship
                    WHEN 'spouse' THEN 1
                    WHEN 'child' THEN 2
                    ELSE 3
                END,
                full_name
            """,
            client_id,
        )
        return [dict(m) for m in members]


@router.post("/clients/{client_id}/family")
async def create_family_member(
    client_id: int,
    data: FamilyMemberCreate,
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Add a family member to a client."""
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    async with pool.acquire() as conn:
        # Verify client exists and check access
        client = await conn.fetchrow("SELECT id, assigned_to FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        if not user_is_admin and (client["assigned_to"] or "").lower() != user_email:
            raise HTTPException(status_code=403, detail="You don't have access to this client")

        # Sanitize date fields - convert strings to date objects for asyncpg
        date_of_birth = None
        if data.date_of_birth:
            try:
                date_of_birth = datetime.strptime(data.date_of_birth, "%Y-%m-%d").date()
            except ValueError:
                date_of_birth = None

        passport_expiry = None
        if data.passport_expiry:
            try:
                passport_expiry = datetime.strptime(data.passport_expiry, "%Y-%m-%d").date()
            except ValueError:
                passport_expiry = None

        visa_expiry = None
        if data.visa_expiry:
            try:
                visa_expiry = datetime.strptime(data.visa_expiry, "%Y-%m-%d").date()
            except ValueError:
                visa_expiry = None

        member_id = await conn.fetchval(
            """
            INSERT INTO client_family_members (
                client_id, full_name, relationship, date_of_birth,
                nationality, passport_number, passport_expiry,
                current_visa_type, visa_expiry, email, phone, notes
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
            """,
            client_id,
            data.full_name,
            data.relationship,
            date_of_birth,  # Sanitized
            data.nationality,
            data.passport_number,
            passport_expiry,  # Sanitized
            data.current_visa_type,
            visa_expiry,  # Sanitized
            data.email,
            data.phone,
            data.notes,
        )

        return {"id": member_id, "success": True}


@router.patch("/clients/{client_id}/family/{member_id}")
async def update_family_member(
    client_id: int,
    member_id: int,
    data: FamilyMemberUpdate,
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Update a family member."""
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    async with pool.acquire() as conn:
        # Check access
        check = await conn.fetchrow("SELECT assigned_to FROM clients WHERE id = $1", client_id)
        if not check:
            raise HTTPException(status_code=404, detail="Client not found")

        if not user_is_admin and (check["assigned_to"] or "").lower() != user_email:
            raise HTTPException(status_code=403, detail="You don't have access to this client")
    # Date fields that need string → date object conversion for asyncpg
    date_fields = {"date_of_birth", "passport_expiry", "visa_expiry"}

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

    values.extend([member_id, client_id])

    async with pool.acquire() as conn:
        result = await conn.execute(
            f"""
            UPDATE client_family_members
            SET {", ".join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_num} AND client_id = ${param_num + 1}
            """,
            *values,
        )

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Family member not found")

    return {"success": True}


@router.delete("/clients/{client_id}/family/{member_id}")
async def delete_family_member(
    client_id: int,
    member_id: int,
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Delete a family member."""
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    async with pool.acquire() as conn:
        # Check access
        check = await conn.fetchrow("SELECT assigned_to FROM clients WHERE id = $1", client_id)
        if not check:
            raise HTTPException(status_code=404, detail="Client not found")

        if not user_is_admin and (check["assigned_to"] or "").lower() != user_email:
            raise HTTPException(status_code=403, detail="You don't have access to this client")

        result = await conn.execute(
            "DELETE FROM client_family_members WHERE id = $1 AND client_id = $2",
            member_id,
            client_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Family member not found")

    return {"success": True}


# ============================================
# DOCUMENTS ENDPOINTS
# ============================================


@router.get("/clients/{client_id}/documents")
async def get_client_documents(
    client_id: int,
    category: str | None = Query(
        None, description="Filter by category: immigration, pma, tax, personal"
    ),
    include_archived: bool = Query(False, description="Include archived documents"),
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Get all documents for a client, optionally filtered by category."""
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    async with pool.acquire() as conn:
        # Check access
        check = await conn.fetchrow("SELECT assigned_to FROM clients WHERE id = $1", client_id)
        if not check:
            raise HTTPException(status_code=404, detail="Client not found")

        if not user_is_admin and (check["assigned_to"] or "").lower() != user_email:
            raise HTTPException(status_code=403, detail="You don't have access to this client")

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
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Add a document to a client."""
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    async with pool.acquire() as conn:
        # Check access
        check = await conn.fetchrow("SELECT assigned_to FROM clients WHERE id = $1", client_id)
        if not check:
            raise HTTPException(status_code=404, detail="Client not found")

        if not user_is_admin and (check["assigned_to"] or "").lower() != user_email:
            raise HTTPException(status_code=403, detail="You don't have access to this client")

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

        return {"id": doc_id, "success": True}


@router.patch("/clients/{client_id}/documents/{doc_id}")
async def update_document(
    client_id: int,
    doc_id: int,
    data: DocumentUpdate,
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Update a document."""
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    async with pool.acquire() as conn:
        # Check access
        check = await conn.fetchrow("SELECT assigned_to FROM clients WHERE id = $1", client_id)
        if not check:
            raise HTTPException(status_code=404, detail="Client not found")

        if not user_is_admin and (check["assigned_to"] or "").lower() != user_email:
            raise HTTPException(status_code=403, detail="You don't have access to this client")
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

    return {"success": True}


@router.delete("/clients/{client_id}/documents/{doc_id}")
async def archive_document(
    client_id: int,
    doc_id: int,
    permanent: bool = Query(False, description="Permanently delete instead of archive"),
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Archive or delete a document."""
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    async with pool.acquire() as conn:
        # Check access
        check = await conn.fetchrow("SELECT assigned_to FROM clients WHERE id = $1", client_id)
        if not check:
            raise HTTPException(status_code=404, detail="Client not found")

        if not user_is_admin and (check["assigned_to"] or "").lower() != user_email:
            raise HTTPException(status_code=403, detail="You don't have access to this client")

        if permanent:
            result = await conn.execute(
                "DELETE FROM documents WHERE id = $1 AND client_id = $2", doc_id, client_id
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

    return {"success": True, "action": action}


# ============================================
# DOCUMENT CATEGORIES ENDPOINT
# ============================================


@router.get("/document-categories")
async def get_document_categories(pool=Depends(get_database_pool)):
    """Get all document categories for dropdowns."""
    async with pool.acquire() as conn:
        categories = await conn.fetch(
            """
            SELECT code, name, category_group, description, has_expiry
            FROM document_categories
            WHERE active = true
            ORDER BY sort_order, name
            """
        )
        return [dict(c) for c in categories]


# ============================================
# EXPIRY ALERTS ENDPOINTS
# ============================================


@router.get("/expiry-alerts")
async def get_all_expiry_alerts(
    alert_color: str | None = Query(None, description="Filter by color: expired, red, yellow"),
    assigned_to: str | None = Query(None, description="Filter by team member email"),
    limit: int = Query(100, le=500),
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Get all expiry alerts across all clients (for team dashboard)."""
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    async with pool.acquire() as conn:
        query = """
            SELECT
                entity_type, entity_id, entity_name, client_id, client_name,
                document_type, expiry_date, days_until_expiry, alert_color, assigned_to
            FROM client_expiry_alerts_view
            WHERE 1=1
        """
        params = []
        param_num = 1

        # RBAC: Non-admins only see their assigned clients' alerts
        if not user_is_admin:
            query += f" AND assigned_to = ${param_num}"
            params.append(user_email)
            param_num += 1
            logger.info(f"RBAC: User {user_email} alerts filtered to their assigned clients")
        elif assigned_to:
            # Admins can filter by specific assigned_to
            query += f" AND assigned_to = ${param_num}"
            params.append(assigned_to)
            param_num += 1

        query += f"""
            ORDER BY
                CASE alert_color
                    WHEN 'expired' THEN 1
                    WHEN 'red' THEN 2
                    WHEN 'yellow' THEN 3
                END,
                expiry_date
            LIMIT ${param_num}
        """
        params.append(limit)

        alerts = await conn.fetch(query, *params)
        return [dict(a) for a in alerts]


@router.get("/expiry-alerts/summary")
async def get_expiry_alerts_summary(pool=Depends(get_database_pool)):
    """Get summary counts of expiry alerts for dashboard."""
    async with pool.acquire() as conn:
        summary = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE alert_color = 'expired') as expired,
                COUNT(*) FILTER (WHERE alert_color = 'red') as red,
                COUNT(*) FILTER (WHERE alert_color = 'yellow') as yellow,
                COUNT(*) FILTER (WHERE alert_color = 'green') as green
            FROM client_expiry_alerts_view
            """
        )

        # Get top 5 urgent alerts
        urgent = await conn.fetch(
            """
            SELECT
                client_name, entity_name, document_type,
                expiry_date, days_until_expiry, alert_color
            FROM client_expiry_alerts_view
            WHERE alert_color IN ('expired', 'red')
            ORDER BY expiry_date
            LIMIT 5
            """
        )

        return {"counts": dict(summary), "urgent_alerts": [dict(a) for a in urgent]}
