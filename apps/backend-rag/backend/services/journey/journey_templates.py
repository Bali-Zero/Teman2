"""
Journey Templates Service
Responsibility: Manage journey templates
"""

import logging

logger = logging.getLogger(__name__)


class JourneyTemplatesService:
    """
    Service for managing journey templates.

    Responsibility: Provide predefined journey templates for common scenarios.
    """

    # Journey templates
    JOURNEY_TEMPLATES = {
        "pt_pma_setup": {
            "title": "PT PMA Company Setup",
            "description": "Complete incorporation of Foreign Investment Company (PT PMA)",
            "steps": [
                {
                    "step_id": "name_approval",
                    "title": "Company Name Approval",
                    "description": "Submit company name to KEMENKUMHAM for approval",
                    "prerequisites": [],
                    "required_documents": [
                        "Proposed company names (3 options)",
                        "Business plan summary",
                    ],
                    "estimated_duration_days": 3,
                },
                {
                    "step_id": "notary_deed",
                    "title": "Notary Deed Preparation",
                    "description": "Prepare Articles of Association (Akta Pendirian) with notary",
                    "prerequisites": ["name_approval"],
                    "required_documents": [
                        "Approved company name",
                        "Shareholder passports",
                        "Shareholder KTP/KITAS",
                        "Company address proof",
                    ],
                    "estimated_duration_days": 5,
                },
                {
                    "step_id": "nib_application",
                    "title": "NIB Application (OSS)",
                    "description": "Apply for Business Identification Number via OSS system",
                    "prerequisites": ["notary_deed"],
                    "required_documents": ["Notarized deed", "KBLI codes", "Investment plan"],
                    "estimated_duration_days": 7,
                },
                {
                    "step_id": "npwp_registration",
                    "title": "NPWP Tax Registration",
                    "description": "Register company for Tax ID (NPWP) and VAT (PKP if required)",
                    "prerequisites": ["nib_application"],
                    "required_documents": ["NIB", "Company deed", "Domicile letter"],
                    "estimated_duration_days": 14,
                },
                {
                    "step_id": "bank_account",
                    "title": "Corporate Bank Account",
                    "description": "Open corporate bank account and deposit minimum capital",
                    "prerequisites": ["npwp_registration"],
                    "required_documents": [
                        "NIB",
                        "NPWP",
                        "Company deed",
                        "Director ID",
                        "Domicile letter",
                    ],
                    "estimated_duration_days": 7,
                },
                {
                    "step_id": "virtual_office",
                    "title": "Virtual Office Setup",
                    "description": "Establish registered office address (can be virtual)",
                    "prerequisites": ["bank_account"],
                    "required_documents": ["Lease agreement or virtual office contract"],
                    "estimated_duration_days": 3,
                },
                {
                    "step_id": "director_kitas",
                    "title": "Director KITAS Application",
                    "description": "Apply for work permit and KITAS for foreign director(s)",
                    "prerequisites": ["nib_application", "bank_account"],
                    "required_documents": [
                        "Passport",
                        "Company NIB",
                        "IMTA",
                        "Sponsor letter",
                        "Health certificate",
                    ],
                    "estimated_duration_days": 30,
                },
            ],
        },
        "kitas_application": {
            "title": "KITAS Work Permit Application",
            "description": "Complete process for obtaining KITAS (Limited Stay Permit) for work",
            "steps": [
                {
                    "step_id": "sponsor_letter",
                    "title": "Obtain Sponsor Letter",
                    "description": "Get sponsor letter from Indonesian company",
                    "prerequisites": [],
                    "required_documents": ["Company NIB", "NPWP", "Domicile letter"],
                    "estimated_duration_days": 3,
                },
                {
                    "step_id": "imta_application",
                    "title": "IMTA Application",
                    "description": "Apply for Work Permit (IMTA) from Ministry of Manpower",
                    "prerequisites": ["sponsor_letter"],
                    "required_documents": [
                        "Sponsor letter",
                        "Company documents",
                        "Job description",
                        "Educational certificates",
                    ],
                    "estimated_duration_days": 14,
                },
                {
                    "step_id": "kitas_application",
                    "title": "KITAS Application",
                    "description": "Apply for KITAS at Immigration Office",
                    "prerequisites": ["imta_application"],
                    "required_documents": [
                        "IMTA",
                        "Passport",
                        "Sponsor letter",
                        "Health certificate",
                        "Police clearance",
                    ],
                    "estimated_duration_days": 30,
                },
            ],
        },
        "property_purchase": {
            "title": "Property Purchase Process",
            "description": "Complete property acquisition process in Indonesia",
            "steps": [
                {
                    "step_id": "due_diligence",
                    "title": "Due Diligence",
                    "description": "Verify property ownership, permits, and legal status",
                    "prerequisites": [],
                    "required_documents": ["Property certificate (SHM/HGB)", "SPPT PBB"],
                    "estimated_duration_days": 14,
                },
                {
                    "step_id": "purchase_agreement",
                    "title": "Purchase Agreement",
                    "description": "Sign purchase agreement and pay deposit",
                    "prerequisites": ["due_diligence"],
                    "required_documents": ["SPA draft", "Identity documents"],
                    "estimated_duration_days": 7,
                },
                {
                    "step_id": "payment_settlement",
                    "title": "Payment Settlement",
                    "description": "Complete payment and transfer ownership",
                    "prerequisites": ["purchase_agreement"],
                    "required_documents": ["Payment proof", "Transfer documents"],
                    "estimated_duration_days": 5,
                },
            ],
        },
    }

    def get_template(self, template_key: str) -> dict | None:
        """
        Get journey template by key.

        Args:
            template_key: Template key (e.g., "pt_pma_setup")

        Returns:
            Template dictionary or None
        """
        return self.JOURNEY_TEMPLATES.get(template_key)

    def list_templates(self) -> list[str]:
        """
        List all available template keys.

        Returns:
            List of template keys
        """
        return list(self.JOURNEY_TEMPLATES.keys())

    def validate_template(self, template_key: str) -> bool:
        """
        Validate that a template key exists.

        Args:
            template_key: Template key to validate

        Returns:
            True if template exists
        """
        return template_key in self.JOURNEY_TEMPLATES
