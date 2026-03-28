"""
Company-Centric CRM Models
SQLModel definitions for companies, client_company_links, company_documents, tax_records
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, Column, Date, Numeric, Text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from backend.app.modules.crm.models import Client


class Company(SQLModel, table=True):
    """
    Company model - Represents PT PMA, PT Perorangan, CV, etc.
    """

    __tablename__ = "companies"

    id: int | None = Field(default=None, primary_key=True)
    uuid: str | None = Field(default=None, unique=True, index=True, max_length=36)

    # Basic Info
    company_name: str = Field(max_length=255, nullable=False)
    company_type: str = Field(default="PT PMA", max_length=50)  # PT PMA, PT Perorangan, CV
    brand_name: str | None = Field(default=None, max_length=255)

    # Business Identification
    kbli_code: str | None = Field(default=None, max_length=20, index=True)
    kbli_description: str | None = Field(default=None, sa_column=Column(Text))
    nib: str | None = Field(default=None, max_length=50, unique=True, index=True)
    npwp_company: str | None = Field(default=None, max_length=50, unique=True, index=True)

    # Legal Documents
    akta_pendirian_no: str | None = Field(default=None, max_length=100)
    akta_pendirian_date: date | None = Field(default=None, sa_column=Column(Date))
    akta_perubahan_no: str | None = Field(default=None, max_length=100)
    akta_perubahan_date: date | None = Field(default=None, sa_column=Column(Date))
    sk_menhumkam_no: str | None = Field(default=None, max_length=100)
    sk_menhumkam_date: date | None = Field(default=None, sa_column=Column(Date))

    # Address & Contact
    registered_address: str | None = Field(default=None, sa_column=Column(Text))
    office_address: str | None = Field(default=None, sa_column=Column(Text))
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    company_phone: str | None = Field(default=None, max_length=50)
    company_email: str | None = Field(default=None, max_length=255)

    # Status & Metadata
    status: str = Field(
        default="active", max_length=50, index=True,
    )  # active, dormant, dissolved, in_setup
    setup_progress: int = Field(default=0)  # 0-100

    # Google Drive Integration
    google_drive_folder_id: str | None = Field(default=None, max_length=100)

    # Custom Fields
    custom_fields: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = Field(default=None, max_length=255)
    updated_by: str | None = Field(default=None, max_length=255)

    # Relationships
    client_links: list["ClientCompanyLink"] = Relationship(back_populates="company")
    documents: list["CompanyDocument"] = Relationship(back_populates="company")


class ClientCompanyLink(SQLModel, table=True):
    """
    Many-to-many relationship between clients and companies
    """

    __tablename__ = "client_company_links"

    id: int | None = Field(default=None, primary_key=True)

    # Relationships
    client_id: int = Field(foreign_key="clients.id", nullable=False, index=True)
    company_id: int = Field(foreign_key="companies.id", nullable=False, index=True)

    # Role & Association
    role: str = Field(
        default="shareholder", max_length=50,
    )  # Director, Commissioner, Shareholder, etc.
    is_primary: bool = Field(default=False)

    # Ownership Details
    ownership_percentage: Decimal | None = Field(default=None, sa_column=Column(Numeric(5, 2)))
    shares_count: int | None = None
    share_nominal_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2)))

    # Dates
    start_date: date | None = None
    end_date: date | None = None

    # Status
    status: str = Field(default="active", max_length=50)  # active, resigned, terminated, pending

    # Notes
    notes: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    company: Company | None = Relationship(back_populates="client_links")
    client: Optional["Client"] = Relationship(
        back_populates="company_links", sa_relationship_kwargs={"lazy": "selectin"},
    )


class CompanyDocument(SQLModel, table=True):
    """
    Documents specific to companies (akta, SK, NIB, etc.)
    """

    __tablename__ = "company_documents"

    id: int | None = Field(default=None, primary_key=True)
    uuid: str | None = Field(default=None, unique=True, max_length=36)

    # Relationship
    company_id: int = Field(foreign_key="companies.id", nullable=False, index=True)

    # Document Classification
    document_type: str = Field(max_length=100, nullable=False, index=True)
    document_subtype: str | None = Field(default=None, max_length=100)

    # Document Details
    document_number: str | None = Field(default=None, max_length=255)
    document_title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, sa_column=Column(Text))

    # Dates
    issue_date: date | None = None
    expiry_date: date | None = None
    reminder_date: date | None = None

    # File Storage
    storage_type: str = Field(default="google_drive", max_length=50)
    google_drive_file_id: str | None = Field(default=None, max_length=255)
    google_drive_file_url: str | None = Field(default=None, sa_column=Column(Text))
    file_name: str | None = Field(default=None, max_length=500)
    file_size_kb: int | None = None
    mime_type: str | None = Field(default=None, max_length=100)

    # Verification
    is_verified: bool = Field(default=False)
    verified_by: str | None = Field(default=None, max_length=255)
    verified_at: datetime | None = None

    # Status
    status: str = Field(
        default="active", max_length=50, index=True,
    )  # active, expired, archived, pending

    # Notes
    notes: str | None = Field(default=None, sa_column=Column(Text))

    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    uploaded_by: str | None = Field(default=None, max_length=255)

    # Relationships
    company: Company | None = Relationship(back_populates="documents")


class TaxRecord(SQLModel, table=True):
    """
    Tax information for both clients and companies
    """

    __tablename__ = "tax_records"

    id: int | None = Field(default=None, primary_key=True)
    uuid: str | None = Field(default=None, unique=True, max_length=36)

    # Polymorphic relationship
    entity_type: str = Field(max_length=20, nullable=False)  # 'client' or 'company'
    entity_id: int = Field(nullable=False, index=True)

    # Tax Identification
    npwp: str | None = Field(default=None, max_length=50, index=True)
    npwp_status: str | None = Field(default=None, max_length=50)
    tax_center: str | None = Field(default=None, max_length=100)  # KPP

    # Tax Types Registration
    is_pph21_registered: bool = Field(default=False)
    is_pph23_registered: bool = Field(default=False)
    is_pph25_registered: bool = Field(default=False)
    is_ppn_registered: bool = Field(default=False)
    is_pph29_registered: bool = Field(default=False)

    # Tax Period
    tax_year: int | None = None
    reporting_period: str | None = Field(default=None, max_length=20)

    # Obligations & Deadlines
    last_filing_date: date | None = None
    next_filing_date: date | None = None
    last_payment_date: date | None = None
    next_payment_date: date | None = None

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

    id: int | None = Field(default=None, primary_key=True)
    uuid: str | None = Field(default=None, unique=True, max_length=36)

    # Relationship
    entity_type: str = Field(max_length=20, nullable=False)  # 'client' or 'company'
    entity_id: int = Field(nullable=False, index=True)

    # Document Classification
    document_type: str = Field(max_length=100, nullable=False, index=True)
    tax_type: str | None = Field(default=None, max_length=50, index=True)  # PPh21, PPh23, PPN, etc.
    tax_year: int | None = None
    tax_period: str | None = Field(default=None, max_length=20)

    # Document Details
    document_number: str | None = Field(default=None, max_length=255)
    filing_date: date | None = None

    # Amounts
    reported_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(15, 2)))
    paid_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(15, 2)))
    currency: str = Field(default="IDR", max_length=10)

    # File Storage
    storage_type: str = Field(default="google_drive", max_length=50)
    google_drive_file_id: str | None = Field(default=None, max_length=255)
    google_drive_file_url: str | None = Field(default=None, sa_column=Column(Text))
    file_name: str | None = Field(default=None, max_length=500)

    # Status
    status: str = Field(default="filed", max_length=50)  # filed, paid, corrected, amended

    # Notes
    notes: str | None = Field(default=None, sa_column=Column(Text))

    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    uploaded_by: str | None = Field(default=None, max_length=255)


# Pydantic Models for API Request/Response
class CompanyCreate(SQLModel):
    company_name: str
    company_type: str = "PT PMA"
    kbli_code: str | None = None
    nib: str | None = None
    npwp_company: str | None = None
    registered_address: str | None = None
    city: str | None = None
    province: str | None = None
    company_email: str | None = None
    company_phone: str | None = None


class CompanyUpdate(SQLModel):
    company_name: str | None = None
    company_type: str | None = None
    kbli_code: str | None = None
    nib: str | None = None
    npwp_company: str | None = None
    akta_pendirian_no: str | None = None
    akta_pendirian_date: date | None = None
    akta_perubahan_no: str | None = None
    akta_perubahan_date: date | None = None
    sk_menhumkam_no: str | None = None
    sk_menhumkam_date: date | None = None
    registered_address: str | None = None
    office_address: str | None = None
    city: str | None = None
    province: str | None = None
    postal_code: str | None = None
    company_email: str | None = None
    company_phone: str | None = None
    status: str | None = None


class ClientCompanyLinkCreate(SQLModel):
    company_id: int
    role: str = "shareholder"
    is_primary: bool = False
    ownership_percentage: Decimal | None = None
    shares_count: int | None = None
    start_date: date | None = None


class CompanyDocumentCreate(SQLModel):
    document_type: str
    document_subtype: str | None = None
    document_number: str | None = None
    document_title: str | None = None
    description: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    google_drive_file_id: str | None = None
    google_drive_file_url: str | None = None
    file_name: str | None = None
    file_size_kb: int | None = None
    mime_type: str | None = None
