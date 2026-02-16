"""
Company-Centric CRM Models
SQLModel definitions for companies, client_company_links, company_documents, tax_records
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String, Text, Boolean, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from backend.app.modules.crm.models import Client


class Company(SQLModel, table=True):
    """
    Company model - Represents PT PMA, PT Perorangan, CV, etc.
    """
    __tablename__ = "companies"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: Optional[str] = Field(default=None, unique=True, index=True, max_length=36)
    
    # Basic Info
    company_name: str = Field(max_length=255, nullable=False)
    company_type: str = Field(default="PT PMA", max_length=50)  # PT PMA, PT Perorangan, CV
    brand_name: Optional[str] = Field(default=None, max_length=255)
    
    # Business Identification
    kbli_code: Optional[str] = Field(default=None, max_length=20, index=True)
    kbli_description: Optional[str] = Field(default=None, sa_column=Column(Text))
    nib: Optional[str] = Field(default=None, max_length=50, unique=True, index=True)
    npwp_company: Optional[str] = Field(default=None, max_length=50, unique=True, index=True)
    
    # Legal Documents
    akta_pendirian_no: Optional[str] = Field(default=None, max_length=100)
    akta_pendirian_date: Optional[date] = Field(default=None, sa_column=Column(Date))
    akta_perubahan_no: Optional[str] = Field(default=None, max_length=100)
    akta_perubahan_date: Optional[date] = Field(default=None, sa_column=Column(Date))
    sk_menhumkam_no: Optional[str] = Field(default=None, max_length=100)
    sk_menhumkam_date: Optional[date] = Field(default=None, sa_column=Column(Date))
    
    # Address & Contact
    registered_address: Optional[str] = Field(default=None, sa_column=Column(Text))
    office_address: Optional[str] = Field(default=None, sa_column=Column(Text))
    city: Optional[str] = Field(default=None, max_length=100)
    province: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    company_phone: Optional[str] = Field(default=None, max_length=50)
    company_email: Optional[str] = Field(default=None, max_length=255)
    
    # Status & Metadata
    status: str = Field(default="active", max_length=50, index=True)  # active, dormant, dissolved, in_setup
    setup_progress: int = Field(default=0)  # 0-100
    
    # Google Drive Integration
    google_drive_folder_id: Optional[str] = Field(default=None, max_length=100)
    
    # Custom Fields
    custom_fields: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(default=None, max_length=255)
    updated_by: Optional[str] = Field(default=None, max_length=255)
    
    # Relationships
    client_links: list["ClientCompanyLink"] = Relationship(back_populates="company")
    documents: list["CompanyDocument"] = Relationship(back_populates="company")


class ClientCompanyLink(SQLModel, table=True):
    """
    Many-to-many relationship between clients and companies
    """
    __tablename__ = "client_company_links"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Relationships
    client_id: int = Field(foreign_key="clients.id", nullable=False, index=True)
    company_id: int = Field(foreign_key="companies.id", nullable=False, index=True)
    
    # Role & Association
    role: str = Field(default="shareholder", max_length=50)  # Director, Commissioner, Shareholder, etc.
    is_primary: bool = Field(default=False)
    
    # Ownership Details
    ownership_percentage: Optional[Decimal] = Field(
        default=None, 
        sa_column=Column(Numeric(5, 2))
    )
    shares_count: Optional[int] = None
    share_nominal_value: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(12, 2))
    )
    
    # Dates
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    
    # Status
    status: str = Field(default="active", max_length=50)  # active, resigned, terminated, pending
    
    # Notes
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    company: Optional[Company] = Relationship(back_populates="client_links")
    client: Optional["Client"] = Relationship(
        back_populates="company_links", 
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class CompanyDocument(SQLModel, table=True):
    """
    Documents specific to companies (akta, SK, NIB, etc.)
    """
    __tablename__ = "company_documents"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: Optional[str] = Field(default=None, unique=True, max_length=36)
    
    # Relationship
    company_id: int = Field(foreign_key="companies.id", nullable=False, index=True)
    
    # Document Classification
    document_type: str = Field(max_length=100, nullable=False, index=True)
    document_subtype: Optional[str] = Field(default=None, max_length=100)
    
    # Document Details
    document_number: Optional[str] = Field(default=None, max_length=255)
    document_title: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # Dates
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    reminder_date: Optional[date] = None
    
    # File Storage
    storage_type: str = Field(default="google_drive", max_length=50)
    google_drive_file_id: Optional[str] = Field(default=None, max_length=255)
    google_drive_file_url: Optional[str] = Field(default=None, sa_column=Column(Text))
    file_name: Optional[str] = Field(default=None, max_length=500)
    file_size_kb: Optional[int] = None
    mime_type: Optional[str] = Field(default=None, max_length=100)
    
    # Verification
    is_verified: bool = Field(default=False)
    verified_by: Optional[str] = Field(default=None, max_length=255)
    verified_at: Optional[datetime] = None
    
    # Status
    status: str = Field(default="active", max_length=50, index=True)  # active, expired, archived, pending
    
    # Notes
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    uploaded_by: Optional[str] = Field(default=None, max_length=255)
    
    # Relationships
    company: Optional[Company] = Relationship(back_populates="documents")


class TaxRecord(SQLModel, table=True):
    """
    Tax information for both clients and companies
    """
    __tablename__ = "tax_records"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: Optional[str] = Field(default=None, unique=True, max_length=36)
    
    # Polymorphic relationship
    entity_type: str = Field(max_length=20, nullable=False)  # 'client' or 'company'
    entity_id: int = Field(nullable=False, index=True)
    
    # Tax Identification
    npwp: Optional[str] = Field(default=None, max_length=50, index=True)
    npwp_status: Optional[str] = Field(default=None, max_length=50)
    tax_center: Optional[str] = Field(default=None, max_length=100)  # KPP
    
    # Tax Types Registration
    is_pph21_registered: bool = Field(default=False)
    is_pph23_registered: bool = Field(default=False)
    is_pph25_registered: bool = Field(default=False)
    is_ppn_registered: bool = Field(default=False)
    is_pph29_registered: bool = Field(default=False)
    
    # Tax Period
    tax_year: Optional[int] = None
    reporting_period: Optional[str] = Field(default=None, max_length=20)
    
    # Obligations & Deadlines
    last_filing_date: Optional[date] = None
    next_filing_date: Optional[date] = None
    last_payment_date: Optional[date] = None
    next_payment_date: Optional[date] = None
    
    # Status
    compliance_status: str = Field(default="compliant", max_length=50, index=True)
    
    # Custom Fields
    custom_fields: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TaxDocument(SQLModel, table=True):
    """
    Tax-specific documents (SPT, bukti potong, etc.)
    """
    __tablename__ = "tax_documents"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: Optional[str] = Field(default=None, unique=True, max_length=36)
    
    # Relationship
    entity_type: str = Field(max_length=20, nullable=False)  # 'client' or 'company'
    entity_id: int = Field(nullable=False, index=True)
    
    # Document Classification
    document_type: str = Field(max_length=100, nullable=False, index=True)
    tax_type: Optional[str] = Field(default=None, max_length=50, index=True)  # PPh21, PPh23, PPN, etc.
    tax_year: Optional[int] = None
    tax_period: Optional[str] = Field(default=None, max_length=20)
    
    # Document Details
    document_number: Optional[str] = Field(default=None, max_length=255)
    filing_date: Optional[date] = None
    
    # Amounts
    reported_amount: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(15, 2)))
    paid_amount: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(15, 2)))
    currency: str = Field(default="IDR", max_length=10)
    
    # File Storage
    storage_type: str = Field(default="google_drive", max_length=50)
    google_drive_file_id: Optional[str] = Field(default=None, max_length=255)
    google_drive_file_url: Optional[str] = Field(default=None, sa_column=Column(Text))
    file_name: Optional[str] = Field(default=None, max_length=500)
    
    # Status
    status: str = Field(default="filed", max_length=50)  # filed, paid, corrected, amended
    
    # Notes
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    uploaded_by: Optional[str] = Field(default=None, max_length=255)


# Pydantic Models for API Request/Response
class CompanyCreate(SQLModel):
    company_name: str
    company_type: str = "PT PMA"
    kbli_code: Optional[str] = None
    nib: Optional[str] = None
    npwp_company: Optional[str] = None
    registered_address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    company_email: Optional[str] = None
    company_phone: Optional[str] = None


class CompanyUpdate(SQLModel):
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    kbli_code: Optional[str] = None
    nib: Optional[str] = None
    npwp_company: Optional[str] = None
    akta_pendirian_no: Optional[str] = None
    akta_pendirian_date: Optional[date] = None
    akta_perubahan_no: Optional[str] = None
    akta_perubahan_date: Optional[date] = None
    sk_menhumkam_no: Optional[str] = None
    sk_menhumkam_date: Optional[date] = None
    registered_address: Optional[str] = None
    office_address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    company_email: Optional[str] = None
    company_phone: Optional[str] = None
    status: Optional[str] = None


class ClientCompanyLinkCreate(SQLModel):
    company_id: int
    role: str = "shareholder"
    is_primary: bool = False
    ownership_percentage: Optional[Decimal] = None
    shares_count: Optional[int] = None
    start_date: Optional[date] = None


class CompanyDocumentCreate(SQLModel):
    document_type: str
    document_subtype: Optional[str] = None
    document_number: Optional[str] = None
    document_title: Optional[str] = None
    description: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    google_drive_file_id: Optional[str] = None
    google_drive_file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size_kb: Optional[int] = None
    mime_type: Optional[str] = None
