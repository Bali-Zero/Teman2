"""
Company Router - API endpoints for Company-Centric CRM
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.auth import get_current_user
from backend.app.db import get_session
from backend.app.modules.crm.company_models import (
    ClientCompanyLink,
    ClientCompanyLinkCreate,
    Company,
    CompanyCreate,
    CompanyDocument,
    CompanyDocumentCreate,
    CompanyUpdate,
    TaxRecord,
    TaxDocument,
)

router = APIRouter(prefix="/crm/companies", tags=["CRM Companies"])


# ========== COMPANY ENDPOINTS ==========

@router.get("", response_model=List[dict[str, Any]])
async def list_companies(
    request: Request,
    search: Optional[str] = Query(None, description="Search by name, NIB, or NPWP"),
    status: Optional[str] = Query(None, description="Filter by status"),
    kbli: Optional[str] = Query(None, description="Filter by KBLI code"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """List all companies with optional filters"""
    query = select(Company)
    
    if search:
        search_filter = (
            Company.company_name.ilike(f"%{search}%") |
            Company.nib.ilike(f"%{search}%") |
            Company.npwp_company.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
    
    if status:
        query = query.where(Company.status == status)
    
    if kbli:
        query = query.where(Company.kbli_code == kbli)
    
    query = query.order_by(Company.company_name).offset(skip).limit(limit)
    
    result = await session.execute(query)
    companies = result.scalars().all()
    
    # Get primary contacts count
    company_list = []
    for comp in companies:
        # Get associated clients
        links_result = await session.execute(
            select(ClientCompanyLink, Company)
            .where(ClientCompanyLink.company_id == comp.id)
            .options(selectinload(ClientCompanyLink.client))
        )
        links = links_result.all()
        
        company_data = {
            "id": comp.id,
            "uuid": comp.uuid,
            "company_name": comp.company_name,
            "company_type": comp.company_type,
            "nib": comp.nib,
            "npwp_company": comp.npwp_company,
            "kbli_code": comp.kbli_code,
            "status": comp.status,
            "setup_progress": comp.setup_progress,
            "city": comp.city,
            "created_at": comp.created_at,
            "associates_count": len(links),
        }
        company_list.append(company_data)
    
    return company_list


@router.post("", response_model=dict[str, Any])
async def create_company(
    request: Request,
    data: CompanyCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Create a new company"""
    user_email = current_user.get("email", "system")
    
    company = Company(
        company_name=data.company_name,
        company_type=data.company_type,
        kbli_code=data.kbli_code,
        nib=data.nib,
        npwp_company=data.npwp_company,
        registered_address=data.registered_address,
        city=data.city,
        province=data.province,
        company_email=data.company_email,
        company_phone=data.company_phone,
        created_by=user_email,
        updated_by=user_email,
    )
    
    session.add(company)
    await session.commit()
    await session.refresh(company)
    
    return {
        "id": company.id,
        "uuid": company.uuid,
        "company_name": company.company_name,
        "company_type": company.company_type,
        "status": company.status,
        "message": "Company created successfully",
    }


@router.get("/{company_id}", response_model=dict[str, Any])
async def get_company(
    request: Request,
    company_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Get company details with associates"""
    result = await session.get(Company, company_id)
    if not result:
        raise HTTPException(status_code=404, detail="Company not found")
    
    company = result
    
    # Get associates (clients linked to this company)
    links_result = await session.execute(
        select(ClientCompanyLink).where(
            ClientCompanyLink.company_id == company_id
        )
    )
    links = links_result.scalars().all()
    
    # Get documents
    docs_result = await session.execute(
        select(CompanyDocument).where(
            CompanyDocument.company_id == company_id
        ).order_by(CompanyDocument.created_at.desc())
    )
    documents = docs_result.scalars().all()
    
    # Get tax record
    tax_result = await session.execute(
        select(TaxRecord).where(
            TaxRecord.entity_type == "company",
            TaxRecord.entity_id == company_id
        )
    )
    tax_record = tax_result.scalar_one_or_none()
    
    return {
        "id": company.id,
        "uuid": company.uuid,
        "company_name": company.company_name,
        "company_type": company.company_type,
        "brand_name": company.brand_name,
        "nib": company.nib,
        "npwp_company": company.npwp_company,
        "kbli_code": company.kbli_code,
        "kbli_description": company.kbli_description,
        "akta_pendirian_no": company.akta_pendirian_no,
        "akta_pendirian_date": company.akta_pendirian_date,
        "akta_perubahan_no": company.akta_perubahan_no,
        "akta_perubahan_date": company.akta_perubahan_date,
        "sk_menhumkam_no": company.sk_menhumkam_no,
        "sk_menhumkam_date": company.sk_menhumkam_date,
        "registered_address": company.registered_address,
        "office_address": company.office_address,
        "city": company.city,
        "province": company.province,
        "postal_code": company.postal_code,
        "company_phone": company.company_phone,
        "company_email": company.company_email,
        "status": company.status,
        "setup_progress": company.setup_progress,
        "google_drive_folder_id": company.google_drive_folder_id,
        "custom_fields": company.custom_fields,
        "created_at": company.created_at,
        "updated_at": company.updated_at,
        "associates": [
            {
                "link_id": link.id,
                "client_id": link.client_id,
                "role": link.role,
                "is_primary": link.is_primary,
                "ownership_percentage": link.ownership_percentage,
                "shares_count": link.shares_count,
                "start_date": link.start_date,
                "status": link.status,
            }
            for link in links
        ],
        "documents": [
            {
                "id": doc.id,
                "uuid": doc.uuid,
                "document_type": doc.document_type,
                "document_subtype": doc.document_subtype,
                "document_number": doc.document_number,
                "document_title": doc.document_title,
                "issue_date": doc.issue_date,
                "expiry_date": doc.expiry_date,
                "status": doc.status,
                "google_drive_file_id": doc.google_drive_file_id,
                "file_name": doc.file_name,
            }
            for doc in documents
        ],
        "tax_record": {
            "id": tax_record.id,
            "npwp": tax_record.npwp,
            "npwp_status": tax_record.npwp_status,
            "tax_center": tax_record.tax_center,
            "compliance_status": tax_record.compliance_status,
            "next_filing_date": tax_record.next_filing_date,
        } if tax_record else None,
    }


@router.patch("/{company_id}", response_model=dict[str, Any])
async def update_company(
    request: Request,
    company_id: int,
    data: CompanyUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Update company details"""
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    user_email = current_user.get("email", "system")
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(company, key, value)
    
    company.updated_by = user_email
    company.updated_at = func.now()
    
    await session.commit()
    await session.refresh(company)
    
    return {
        "id": company.id,
        "company_name": company.company_name,
        "message": "Company updated successfully",
    }


@router.delete("/{company_id}")
async def delete_company(
    request: Request,
    company_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Delete a company"""
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    await session.delete(company)
    await session.commit()
    
    return {"message": "Company deleted successfully"}


# ========== CLIENT-COMPANY LINK ENDPOINTS ==========

@router.get("/{company_id}/clients", response_model=List[dict[str, Any]])
async def get_company_clients(
    request: Request,
    company_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Get all clients associated with a company"""
    # Verify company exists
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    result = await session.execute(
        select(ClientCompanyLink).where(
            ClientCompanyLink.company_id == company_id
        )
    )
    links = result.scalars().all()
    
    return [
        {
            "link_id": link.id,
            "client_id": link.client_id,
            "role": link.role,
            "is_primary": link.is_primary,
            "ownership_percentage": link.ownership_percentage,
            "shares_count": link.shares_count,
            "start_date": link.start_date,
            "status": link.status,
        }
        for link in links
    ]


@router.post("/{company_id}/clients/{client_id}/link", response_model=dict[str, Any])
async def link_client_to_company(
    request: Request,
    company_id: int,
    client_id: int,
    data: ClientCompanyLinkCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Link a client to a company with a specific role"""
    # Verify company exists
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Check if link already exists
    result = await session.execute(
        select(ClientCompanyLink).where(
            ClientCompanyLink.client_id == client_id,
            ClientCompanyLink.company_id == company_id
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail="Client is already linked to this company"
        )
    
    link = ClientCompanyLink(
        client_id=client_id,
        company_id=company_id,
        role=data.role,
        is_primary=data.is_primary,
        ownership_percentage=data.ownership_percentage,
        shares_count=data.shares_count,
        start_date=data.start_date,
    )
    
    session.add(link)
    await session.commit()
    await session.refresh(link)
    
    return {
        "link_id": link.id,
        "message": "Client linked to company successfully",
    }


@router.delete("/{company_id}/clients/{client_id}/link")
async def unlink_client_from_company(
    request: Request,
    company_id: int,
    client_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Remove link between client and company"""
    result = await session.execute(
        select(ClientCompanyLink).where(
            ClientCompanyLink.client_id == client_id,
            ClientCompanyLink.company_id == company_id
        )
    )
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    
    await session.delete(link)
    await session.commit()
    
    return {"message": "Client unlinked from company successfully"}


# ========== COMPANY DOCUMENT ENDPOINTS ==========

@router.get("/{company_id}/documents", response_model=List[dict[str, Any]])
async def get_company_documents(
    request: Request,
    company_id: int,
    doc_type: Optional[str] = Query(None, description="Filter by document type"),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Get documents for a company"""
    query = select(CompanyDocument).where(
        CompanyDocument.company_id == company_id
    )
    
    if doc_type:
        query = query.where(CompanyDocument.document_type == doc_type)
    
    query = query.order_by(CompanyDocument.created_at.desc())
    
    result = await session.execute(query)
    documents = result.scalars().all()
    
    return [
        {
            "id": doc.id,
            "uuid": doc.uuid,
            "document_type": doc.document_type,
            "document_subtype": doc.document_subtype,
            "document_number": doc.document_number,
            "document_title": doc.document_title,
            "description": doc.description,
            "issue_date": doc.issue_date,
            "expiry_date": doc.expiry_date,
            "reminder_date": doc.reminder_date,
            "status": doc.status,
            "is_verified": doc.is_verified,
            "google_drive_file_id": doc.google_drive_file_id,
            "google_drive_file_url": doc.google_drive_file_url,
            "file_name": doc.file_name,
            "file_size_kb": doc.file_size_kb,
            "mime_type": doc.mime_type,
            "notes": doc.notes,
            "created_at": doc.created_at,
        }
        for doc in documents
    ]


@router.post("/{company_id}/documents", response_model=dict[str, Any])
async def create_company_document(
    request: Request,
    company_id: int,
    data: CompanyDocumentCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Add a document to a company"""
    # Verify company exists
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    user_email = current_user.get("email", "system")
    
    document = CompanyDocument(
        company_id=company_id,
        document_type=data.document_type,
        document_subtype=data.document_subtype,
        document_number=data.document_number,
        document_title=data.document_title,
        description=data.description,
        issue_date=data.issue_date,
        expiry_date=data.expiry_date,
        google_drive_file_id=data.google_drive_file_id,
        google_drive_file_url=data.google_drive_file_url,
        file_name=data.file_name,
        file_size_kb=data.file_size_kb,
        mime_type=data.mime_type,
        uploaded_by=user_email,
    )
    
    session.add(document)
    await session.commit()
    await session.refresh(document)
    
    return {
        "id": document.id,
        "uuid": document.uuid,
        "message": "Document added successfully",
    }


@router.delete("/{company_id}/documents/{doc_id}")
async def delete_company_document(
    request: Request,
    company_id: int,
    doc_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Delete a company document"""
    result = await session.execute(
        select(CompanyDocument).where(
            CompanyDocument.id == doc_id,
            CompanyDocument.company_id == company_id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    await session.delete(document)
    await session.commit()
    
    return {"message": "Document deleted successfully"}


# ========== TAX RECORD ENDPOINTS ==========

@router.get("/{company_id}/tax", response_model=dict[str, Any])
async def get_company_tax_record(
    request: Request,
    company_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Get tax record for a company"""
    result = await session.execute(
        select(TaxRecord).where(
            TaxRecord.entity_type == "company",
            TaxRecord.entity_id == company_id
        )
    )
    tax_record = result.scalar_one_or_none()
    
    if not tax_record:
        return {"message": "No tax record found for this company"}
    
    # Get tax documents
    docs_result = await session.execute(
        select(TaxDocument).where(
            TaxDocument.entity_type == "company",
            TaxDocument.entity_id == company_id
        ).order_by(TaxDocument.created_at.desc())
    )
    tax_docs = docs_result.scalars().all()
    
    return {
        "id": tax_record.id,
        "uuid": tax_record.uuid,
        "npwp": tax_record.npwp,
        "npwp_status": tax_record.npwp_status,
        "tax_center": tax_record.tax_center,
        "is_pph21_registered": tax_record.is_pph21_registered,
        "is_pph23_registered": tax_record.is_pph23_registered,
        "is_pph25_registered": tax_record.is_pph25_registered,
        "is_ppn_registered": tax_record.is_ppn_registered,
        "is_pph29_registered": tax_record.is_pph29_registered,
        "tax_year": tax_record.tax_year,
        "reporting_period": tax_record.reporting_period,
        "last_filing_date": tax_record.last_filing_date,
        "next_filing_date": tax_record.next_filing_date,
        "compliance_status": tax_record.compliance_status,
        "custom_fields": tax_record.custom_fields,
        "tax_documents": [
            {
                "id": doc.id,
                "document_type": doc.document_type,
                "tax_type": doc.tax_type,
                "tax_year": doc.tax_year,
                "tax_period": doc.tax_period,
                "filing_date": doc.filing_date,
                "reported_amount": doc.reported_amount,
                "paid_amount": doc.paid_amount,
                "status": doc.status,
            }
            for doc in tax_docs
        ],
    }


# ========== CLIENT-SPECIFIC COMPANY ENDPOINTS ==========

@router.get("/by-client/{client_id}", response_model=List[dict[str, Any]])
async def get_client_companies(
    request: Request,
    client_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Get all companies linked to a client"""
    result = await session.execute(
        select(ClientCompanyLink, Company)
        .join(Company, ClientCompanyLink.company_id == Company.id)
        .where(ClientCompanyLink.client_id == client_id)
    )
    links = result.all()
    
    return [
        {
            "company_id": link.Company.id,
            "company_name": link.Company.company_name,
            "company_type": link.Company.company_type,
            "nib": link.Company.nib,
            "npwp_company": link.Company.npwp_company,
            "kbli_code": link.Company.kbli_code,
            "status": link.Company.status,
            "setup_progress": link.Company.setup_progress,
            "link_id": link.ClientCompanyLink.id,
            "role": link.ClientCompanyLink.role,
            "is_primary": link.ClientCompanyLink.is_primary,
            "ownership_percentage": link.ClientCompanyLink.ownership_percentage,
            "start_date": link.ClientCompanyLink.start_date,
        }
        for link in links
    ]
