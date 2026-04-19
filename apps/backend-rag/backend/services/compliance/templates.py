"""
Compliance Templates Service
Responsibility: Manage compliance templates
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class ComplianceType(str, Enum):
    """Type of compliance item"""

    VISA_EXPIRY = "visa_expiry"
    TAX_FILING = "tax_filing"
    LICENSE_RENEWAL = "license_renewal"
    PERMIT_RENEWAL = "permit_renewal"
    REGULATORY_CHANGE = "regulatory_change"
    DOCUMENT_EXPIRY = "document_expiry"


class ComplianceTemplatesService:
    """
    Service for managing compliance templates.

    Responsibility: Provide compliance templates and annual deadlines.
    """

    # Predefined compliance schedules
    ANNUAL_DEADLINES = {
        "spt_tahunan_individual": {
            "title": "SPT Tahunan (Individual Tax Return)",
            "deadline_month": 3,
            "deadline_day": 31,
            "description": "Annual tax return filing for individuals",
            "estimated_cost": 2000000,  # IDR for service
            "compliance_type": ComplianceType.TAX_FILING,
        },
        "spt_tahunan_corporate": {
            "title": "SPT Tahunan (Corporate Tax Return)",
            "deadline_month": 4,
            "deadline_day": 30,
            "description": "Annual tax return filing for corporations",
            "estimated_cost": 5000000,
            "compliance_type": ComplianceType.TAX_FILING,
        },
        "ppn_monthly": {
            "title": "Monthly VAT (PPn) Filing",
            "deadline_day": 15,  # Every month
            "description": "Monthly VAT reporting and payment",
            "estimated_cost": 500000,
            "compliance_type": ComplianceType.TAX_FILING,
        },
    }

    def get_template(self, template_key: str) -> dict | None:
        """
        Get compliance template by key.

        Args:
            template_key: Template key (e.g., "spt_tahunan_individual")

        Returns:
            Template dictionary or None
        """
        return self.ANNUAL_DEADLINES.get(template_key)

    def get_annual_deadlines(self) -> dict:
        """
        Get all annual deadline templates.

        Returns:
            Dictionary of annual deadlines
        """
        return self.ANNUAL_DEADLINES

    def list_templates(self) -> list[str]:
        """
        List all available template keys.

        Returns:
            List of template keys
        """
        return list(self.ANNUAL_DEADLINES.keys())

    def validate_template(self, template_key: str) -> bool:
        """
        Validate that a template key exists.

        Args:
            template_key: Template key to validate

        Returns:
            True if template exists
        """
        return template_key in self.ANNUAL_DEADLINES
