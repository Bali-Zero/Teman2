"""
Domain-Specific Formatting Instructions

Responsibility: Provide formatting instructions for domain-specific questions
(Visa, Tax, Company Setup) using standard templates.

Domains supported:
- visa: KITAS, work permits, visa applications
- tax: Indonesian taxation, NPWP, tax compliance
- company: PT PMA setup, business registration
"""


def get_domain_format_instruction(domain: str, language: str) -> str:
    """
    Get instruction for specific domain formatting (Visa, Tax, Company).

    Args:
        domain: Domain name ("visa", "tax", "company")
        language: Language code

    Returns:
        Instruction string with template
    """
    from services.response.standard_templates import (
        get_company_setup_template,
        get_tax_template,
        get_visa_template,
    )

    template = ""
    domain_name = ""

    if domain == "visa":
        template = get_visa_template(language)
        domain_name = "VISA/KITAS"
    elif domain == "tax":
        template = get_tax_template(language)
        domain_name = "TAX/PAJAK"
    elif domain == "company":
        template = get_company_setup_template(language)
        domain_name = "COMPANY SETUP (PT PMA)"
    else:
        return ""

    instruction = f"""
**FORMATTING RULE FOR {domain_name} QUESTIONS:**
You MUST use the following standard structure for your response.
Fill in the placeholders [...] with specific data from your retrieval.

TEMPLATE TO USE:
{template}

IMPORTANT:
- Keep the table structure exactly as shown.
- Do not invent data. If a field is unknown, write "Contact for details".
- Use the "Cost (Bali Zero)" field ONLY if you retrieved a price from get_pricing.
"""
    return instruction
