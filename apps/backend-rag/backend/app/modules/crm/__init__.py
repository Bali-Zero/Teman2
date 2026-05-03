"""
NUZANTARA PRIME - CRM Module
Client, Practice, and Interaction management
Company-Centric Architecture: Companies, Company Documents, Tax Records
"""

from .company_models import (
    ClientCompanyLink,
    Company,
    CompanyDocument,
    TaxDocument,
    TaxRecord,
)
from .models import Client, Interaction, Practice, PracticeType

__all__ = [
    # Core CRM Models
    "Client",
    "Practice",
    "PracticeType",
    "Interaction",
    # Company-Centric Models
    "Company",
    "ClientCompanyLink",
    "CompanyDocument",
    "TaxRecord",
    "TaxDocument",
]
