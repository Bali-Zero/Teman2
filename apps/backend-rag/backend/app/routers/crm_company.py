"""
CRM Company Router - Re-exports from company_router for backward compatibility.

This module re-exports all company-centric CRM endpoints from the company_router
module to maintain consistency with the existing CRM router structure.
"""

# Re-export everything from the company_router module
from backend.app.modules.crm.company_router import router

__all__ = ["router"]
