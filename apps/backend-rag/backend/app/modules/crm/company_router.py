"""
Company Router - API endpoints for Company-Centric CRM
Uses asyncpg like other CRM routers
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.app.dependencies import get_current_user, get_database_pool

router = APIRouter(prefix="/api/crm/companies", tags=["CRM Companies"])


# ========== HELPER FUNCTIONS ==========


def company_record_to_dict(record: asyncpg.Record) -> dict:
    """Convert asyncpg record to dict for Company"""
    return {
        "id": record["id"],
        "uuid": record["uuid"],
        "company_name": record["company_name"],
        "company_type": record["company_type"],
        "brand_name": record["brand_name"],
        "kbli_code": record["kbli_code"],
        "kbli_description": record["kbli_description"],
        "nib": record["nib"],
        "npwp_company": record["npwp_company"],
        "akta_pendirian_no": record["akta_pendirian_no"],
        "akta_pendirian_date": record["akta_pendirian_date"],
        "akta_perubahan_no": record["akta_perubahan_no"],
        "akta_perubahan_date": record["akta_perubahan_date"],
        "sk_menhumkam_no": record["sk_menhumkam_no"],
        "sk_menhumkam_date": record["sk_menhumkam_date"],
        "registered_address": record["registered_address"],
        "office_address": record["office_address"],
        "city": record["city"],
        "province": record["province"],
        "postal_code": record["postal_code"],
        "company_phone": record["company_phone"],
        "company_email": record["company_email"],
        "status": record["status"],
        "setup_progress": record["setup_progress"],
        "google_drive_folder_id": record["google_drive_folder_id"],
        "custom_fields": record["custom_fields"],
        "created_at": record["created_at"].isoformat() if record["created_at"] else None,
        "updated_at": record["updated_at"].isoformat() if record["updated_at"] else None,
        "created_by": record["created_by"],
    }


# ========== COMPANY ENDPOINTS ==========


@router.get("", response_model=list[dict[str, Any]])
async def list_companies(
    request: Request,
    search: str | None = Query(None, description="Search by name, NIB, or NPWP"),
    status: str | None = Query(None, description="Filter by status"),
    kbli: str | None = Query(None, description="Filter by KBLI code"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """List all companies with optional filters"""
    query = "SELECT * FROM companies WHERE 1=1"
    params = []

    if search:
        query += " AND (company_name ILIKE $1 OR nib ILIKE $1 OR npwp_company ILIKE $1)"
        params.append(f"%{search}%")

    if status:
        query += f" AND status = ${len(params) + 1}"
        params.append(status)

    if kbli:
        query += f" AND kbli_code = ${len(params) + 1}"
        params.append(kbli)

    query += f" ORDER BY company_name LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
    params.extend([limit, skip])

    async with db.acquire() as conn:
        rows = await conn.fetch(query, *params)

        companies = []
        for row in rows:
            comp = company_record_to_dict(row)
            # Get associates count
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM client_company_links WHERE company_id = $1", comp["id"]
            )
            comp["associates_count"] = count
            companies.append(comp)

        return companies


@router.post("", response_model=dict[str, Any])
async def create_company(
    request: Request,
    data: dict,
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Create a new company"""
    user_email = current_user.get("email", "system")

    query = """
        INSERT INTO companies (
            company_name, company_type, kbli_code, nib, npwp_company,
            registered_address, city, province, company_email, company_phone,
            created_by, updated_by
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $11)
        RETURNING id, uuid, company_name, company_type, status
    """

    async with db.acquire() as conn:
        row = await conn.fetchrow(
            query,
            data.get("company_name"),
            data.get("company_type", "PT PMA"),
            data.get("kbli_code"),
            data.get("nib"),
            data.get("npwp_company"),
            data.get("registered_address"),
            data.get("city"),
            data.get("province"),
            data.get("company_email"),
            data.get("company_phone"),
            user_email,
        )

        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "company_name": row["company_name"],
            "company_type": row["company_type"],
            "status": row["status"],
            "message": "Company created successfully",
        }


@router.get("/by-name", response_model=dict[str, Any] | None)
async def get_company_by_name_early(
    request: Request,
    name: str = Query(..., description="Company name to search for"),
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Find a company by name (ILIKE match) — must be before /{company_id} route"""
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM companies WHERE company_name ILIKE $1 ORDER BY id LIMIT 1",
            f"%{name}%",
        )
        if not row:
            return None

        company = company_record_to_dict(row)

        associates = await conn.fetch(
            """
            SELECT ccl.id as link_id, ccl.client_id, c.full_name as client_name,
                   ccl.role, ccl.is_primary, ccl.ownership_percentage,
                   ccl.shares_count, ccl.share_nominal_value, ccl.start_date, ccl.status
            FROM client_company_links ccl
            JOIN clients c ON ccl.client_id = c.id
            WHERE ccl.company_id = $1
            """,
            row["id"],
        )

        company["associates"] = [
            {
                "link_id": a["link_id"],
                "client_id": a["client_id"],
                "client_name": a["client_name"],
                "role": a["role"],
                "is_primary": a["is_primary"],
                "ownership_percentage": a["ownership_percentage"],
                "shares_count": a["shares_count"],
                "share_nominal_value": a["share_nominal_value"],
                "start_date": a["start_date"].isoformat() if a["start_date"] else None,
                "status": a["status"],
            }
            for a in associates
        ]

        return company


@router.get("/by-client/{client_id}", response_model=list[dict[str, Any]])
async def get_client_companies_early(
    request: Request,
    client_id: int,
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Get all companies linked to a client — must be before /{company_id} route"""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.*, ccl.id as link_id, ccl.role, ccl.is_primary,
                   ccl.ownership_percentage, ccl.shares_count,
                   ccl.share_nominal_value, ccl.start_date as link_start_date,
                   ccl.status as link_status
            FROM client_company_links ccl
            JOIN companies c ON ccl.company_id = c.id
            WHERE ccl.client_id = $1
            """,
            client_id,
        )

        results = []
        for r in rows:
            comp = company_record_to_dict(r)
            comp["company_id"] = comp.pop("id")
            comp["company_status"] = comp.pop("status")
            comp["link_id"] = r["link_id"]
            comp["role"] = r["role"]
            comp["is_primary"] = r["is_primary"]
            comp["ownership_percentage"] = r["ownership_percentage"]
            comp["shares_count"] = r["shares_count"]
            comp["share_nominal_value"] = r["share_nominal_value"]
            comp["start_date"] = r["link_start_date"].isoformat() if r["link_start_date"] else None
            comp["link_status"] = r["link_status"]
            results.append(comp)

        return results


@router.get("/{company_id}", response_model=dict[str, Any])
async def get_company(
    request: Request,
    company_id: int,
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Get company details with associates"""
    async with db.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM companies WHERE id = $1", company_id)
        if not row:
            raise HTTPException(status_code=404, detail="Company not found")

        company = company_record_to_dict(row)

        # Get associates
        associates = await conn.fetch(
            """
            SELECT ccl.*, c.full_name as client_name
            FROM client_company_links ccl
            JOIN clients c ON ccl.client_id = c.id
            WHERE ccl.company_id = $1
            """,
            company_id,
        )

        # Get documents
        documents = await conn.fetch(
            """
            SELECT id, uuid, document_type, document_subtype, document_number,
                   document_title, issue_date, expiry_date, status,
                   google_drive_file_id, file_name, created_at
            FROM company_documents
            WHERE company_id = $1
            ORDER BY created_at DESC
            """,
            company_id,
        )

        # Get tax record
        tax_row = await conn.fetchrow(
            "SELECT * FROM tax_records WHERE entity_type = 'company' AND entity_id = $1", company_id
        )

        company["associates"] = [
            {
                "link_id": a["id"],
                "client_id": a["client_id"],
                "client_name": a["client_name"],
                "role": a["role"],
                "is_primary": a["is_primary"],
                "ownership_percentage": a["ownership_percentage"],
                "shares_count": a["shares_count"],
                "start_date": a["start_date"].isoformat() if a["start_date"] else None,
                "status": a["status"],
            }
            for a in associates
        ]

        company["documents"] = [
            {
                "id": d["id"],
                "uuid": d["uuid"],
                "document_type": d["document_type"],
                "document_subtype": d["document_subtype"],
                "document_number": d["document_number"],
                "document_title": d["document_title"],
                "issue_date": d["issue_date"].isoformat() if d["issue_date"] else None,
                "expiry_date": d["expiry_date"].isoformat() if d["expiry_date"] else None,
                "status": d["status"],
                "google_drive_file_id": d["google_drive_file_id"],
                "file_name": d["file_name"],
            }
            for d in documents
        ]

        if tax_row:
            company["tax_record"] = {
                "id": tax_row["id"],
                "npwp": tax_row["npwp"],
                "npwp_status": tax_row["npwp_status"],
                "tax_center": tax_row["tax_center"],
                "compliance_status": tax_row["compliance_status"],
                "next_filing_date": tax_row["next_filing_date"].isoformat()
                if tax_row["next_filing_date"]
                else None,
            }

        return company


@router.patch("/{company_id}", response_model=dict[str, Any])
async def update_company(
    request: Request,
    company_id: int,
    data: dict,
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Update company details"""
    user_email = current_user.get("email", "system")

    # Build dynamic update query
    allowed_fields = [
        "company_name",
        "company_type",
        "kbli_code",
        "nib",
        "npwp_company",
        "akta_pendirian_no",
        "akta_pendirian_date",
        "akta_perubahan_no",
        "akta_perubahan_date",
        "sk_menhumkam_no",
        "sk_menhumkam_date",
        "registered_address",
        "office_address",
        "city",
        "province",
        "postal_code",
        "company_phone",
        "company_email",
        "status",
    ]

    updates = []
    params = []
    for field, value in data.items():
        if field in allowed_fields and value is not None:
            updates.append(f"{field} = ${len(params) + 1}")
            params.append(value)

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    updates.append(f"updated_by = ${len(params) + 1}")
    updates.append("updated_at = NOW()")
    params.append(user_email)
    params.append(company_id)

    query = f"UPDATE companies SET {', '.join(updates)} WHERE id = ${len(params)} RETURNING id, company_name"

    async with db.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        if not row:
            raise HTTPException(status_code=404, detail="Company not found")

        return {
            "id": row["id"],
            "company_name": row["company_name"],
            "message": "Company updated successfully",
        }


@router.delete("/{company_id}")
async def delete_company(
    request: Request,
    company_id: int,
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Delete a company"""
    async with db.acquire() as conn:
        result = await conn.execute("DELETE FROM companies WHERE id = $1", company_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Company not found")

        return {"message": "Company deleted successfully"}


# ========== CLIENT-COMPANY LINK ENDPOINTS ==========


@router.get("/{company_id}/clients", response_model=list[dict[str, Any]])
async def get_company_clients(
    request: Request,
    company_id: int,
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Get all clients associated with a company"""
    async with db.acquire() as conn:
        # Verify company exists
        exists = await conn.fetchval("SELECT 1 FROM companies WHERE id = $1", company_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Company not found")

        rows = await conn.fetch(
            """
            SELECT ccl.*, c.full_name as client_name
            FROM client_company_links ccl
            JOIN clients c ON ccl.client_id = c.id
            WHERE ccl.company_id = $1
            """,
            company_id,
        )

        return [
            {
                "link_id": r["id"],
                "client_id": r["client_id"],
                "client_name": r["client_name"],
                "role": r["role"],
                "is_primary": r["is_primary"],
                "ownership_percentage": r["ownership_percentage"],
                "shares_count": r["shares_count"],
                "start_date": r["start_date"].isoformat() if r["start_date"] else None,
                "status": r["status"],
            }
            for r in rows
        ]


@router.post("/{company_id}/clients/{client_id}/link", response_model=dict[str, Any])
async def link_client_to_company(
    request: Request,
    company_id: int,
    client_id: int,
    data: dict,
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Link a client to a company with a specific role"""
    async with db.acquire() as conn:
        # Verify company exists
        exists = await conn.fetchval("SELECT 1 FROM companies WHERE id = $1", company_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Company not found")

        # Check if link already exists
        existing = await conn.fetchrow(
            "SELECT 1 FROM client_company_links WHERE client_id = $1 AND company_id = $2",
            client_id,
            company_id,
        )
        if existing:
            raise HTTPException(status_code=400, detail="Client is already linked to this company")

        row = await conn.fetchrow(
            """
            INSERT INTO client_company_links (
                client_id, company_id, role, is_primary,
                ownership_percentage, shares_count, start_date
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            client_id,
            company_id,
            data.get("role", "shareholder"),
            data.get("is_primary", False),
            data.get("ownership_percentage"),
            data.get("shares_count"),
            data.get("start_date"),
        )

        return {
            "link_id": row["id"],
            "message": "Client linked to company successfully",
        }


@router.delete("/{company_id}/clients/{client_id}/link")
async def unlink_client_from_company(
    request: Request,
    company_id: int,
    client_id: int,
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Remove link between client and company"""
    async with db.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM client_company_links WHERE client_id = $1 AND company_id = $2",
            client_id,
            company_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Link not found")

        return {"message": "Client unlinked from company successfully"}


# ========== COMPANY DOCUMENT ENDPOINTS ==========


@router.get("/{company_id}/documents", response_model=list[dict[str, Any]])
async def get_company_documents(
    request: Request,
    company_id: int,
    doc_type: str | None = Query(None, description="Filter by document type"),
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Get documents for a company"""
    async with db.acquire() as conn:
        query = """
            SELECT id, uuid, document_type, document_subtype, document_number,
                   document_title, description, issue_date, expiry_date,
                   reminder_date, status, is_verified, google_drive_file_id,
                   google_drive_file_url, file_name, file_size_kb, mime_type,
                   notes, created_at
            FROM company_documents
            WHERE company_id = $1
        """
        params = [company_id]

        if doc_type:
            query += " AND document_type = $2"
            params.append(doc_type)

        query += " ORDER BY created_at DESC"

        rows = await conn.fetch(query, *params)

        return [
            {
                "id": r["id"],
                "uuid": r["uuid"],
                "document_type": r["document_type"],
                "document_subtype": r["document_subtype"],
                "document_number": r["document_number"],
                "document_title": r["document_title"],
                "description": r["description"],
                "issue_date": r["issue_date"].isoformat() if r["issue_date"] else None,
                "expiry_date": r["expiry_date"].isoformat() if r["expiry_date"] else None,
                "reminder_date": r["reminder_date"].isoformat() if r["reminder_date"] else None,
                "status": r["status"],
                "is_verified": r["is_verified"],
                "google_drive_file_id": r["google_drive_file_id"],
                "google_drive_file_url": r["google_drive_file_url"],
                "file_name": r["file_name"],
                "file_size_kb": r["file_size_kb"],
                "mime_type": r["mime_type"],
                "notes": r["notes"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]


@router.post("/{company_id}/documents", response_model=dict[str, Any])
async def create_company_document(
    request: Request,
    company_id: int,
    data: dict,
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Add a document to a company"""
    user_email = current_user.get("email", "system")

    async with db.acquire() as conn:
        # Verify company exists
        exists = await conn.fetchval("SELECT 1 FROM companies WHERE id = $1", company_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Company not found")

        row = await conn.fetchrow(
            """
            INSERT INTO company_documents (
                company_id, document_type, document_subtype, document_number,
                document_title, description, issue_date, expiry_date,
                google_drive_file_id, google_drive_file_url, file_name,
                file_size_kb, mime_type, uploaded_by
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            RETURNING id, uuid
            """,
            company_id,
            data.get("document_type"),
            data.get("document_subtype"),
            data.get("document_number"),
            data.get("document_title"),
            data.get("description"),
            data.get("issue_date"),
            data.get("expiry_date"),
            data.get("google_drive_file_id"),
            data.get("google_drive_file_url"),
            data.get("file_name"),
            data.get("file_size_kb"),
            data.get("mime_type"),
            user_email,
        )

        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "message": "Document added successfully",
        }


@router.delete("/{company_id}/documents/{doc_id}")
async def delete_company_document(
    request: Request,
    company_id: int,
    doc_id: int,
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Delete a company document"""
    async with db.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM company_documents WHERE id = $1 AND company_id = $2", doc_id, company_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Document not found")

        return {"message": "Document deleted successfully"}


# ========== TAX RECORD ENDPOINTS ==========


@router.get("/{company_id}/tax", response_model=dict[str, Any])
async def get_company_tax_record(
    request: Request,
    company_id: int,
    db: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """Get tax record for a company"""
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM tax_records WHERE entity_type = 'company' AND entity_id = $1", company_id
        )

        if not row:
            return {"message": "No tax record found for this company"}

        # Get tax documents
        docs = await conn.fetch(
            """
            SELECT id, document_type, tax_type, tax_year, tax_period,
                   document_number, filing_date, reported_amount, paid_amount,
                   status, file_name
            FROM tax_documents
            WHERE entity_type = 'company' AND entity_id = $1
            ORDER BY created_at DESC
            """,
            company_id,
        )

        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "npwp": row["npwp"],
            "npwp_status": row["npwp_status"],
            "tax_center": row["tax_center"],
            "is_pph21_registered": row["is_pph21_registered"],
            "is_pph23_registered": row["is_pph23_registered"],
            "is_pph25_registered": row["is_pph25_registered"],
            "is_ppn_registered": row["is_ppn_registered"],
            "is_pph29_registered": row["is_pph29_registered"],
            "tax_year": row["tax_year"],
            "reporting_period": row["reporting_period"],
            "last_filing_date": row["last_filing_date"].isoformat()
            if row["last_filing_date"]
            else None,
            "next_filing_date": row["next_filing_date"].isoformat()
            if row["next_filing_date"]
            else None,
            "compliance_status": row["compliance_status"],
            "custom_fields": row["custom_fields"],
            "tax_documents": [
                {
                    "id": d["id"],
                    "document_type": d["document_type"],
                    "tax_type": d["tax_type"],
                    "tax_year": d["tax_year"],
                    "tax_period": d["tax_period"],
                    "filing_date": d["filing_date"].isoformat() if d["filing_date"] else None,
                    "reported_amount": d["reported_amount"],
                    "paid_amount": d["paid_amount"],
                    "status": d["status"],
                }
                for d in docs
            ],
        }


# ========== CLIENT-SPECIFIC COMPANY ENDPOINTS ==========
# NOTE: by-name and by-client routes are defined BEFORE /{company_id} above to avoid routing conflicts
