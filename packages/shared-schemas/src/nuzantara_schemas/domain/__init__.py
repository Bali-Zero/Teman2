"""Domain-specific schemas for Indonesian business, visa, property, and tax."""

from nuzantara_schemas.domain.company import CompanyType, CompanyInfo
from nuzantara_schemas.domain.visa import VisaType, VisaInfo
from nuzantara_schemas.domain.property import PropertyRight, PropertyInfo
from nuzantara_schemas.domain.tax import TaxType, TaxInfo
from nuzantara_schemas.domain.kbli import KBLIEntry

__all__ = [
    "CompanyType", "CompanyInfo",
    "VisaType", "VisaInfo",
    "PropertyRight", "PropertyInfo",
    "TaxType", "TaxInfo",
    "KBLIEntry",
]
