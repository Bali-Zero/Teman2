"""
NUZANTARA PRIME - CRM Module
Client, Practice, and Interaction management
Company-Centric Architecture: Companies, Company Documents, Tax Records
"""

from .models import Client, Interaction, Practice, PracticeType
from .company_models import (
    Company,
    ClientCompanyLink,
    CompanyDocument,
    TaxRecord,
    TaxDocument,
)

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
