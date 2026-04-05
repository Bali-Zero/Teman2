"""
Renewal Rules — Deterministic rule table for predictive compliance engine.

Each RenewalRule defines:
- Which document/visa types it applies to
- Processing time (working days at immigration/authority)
- Lead time (days before expiry to START the process)
- Recommended action date (days before expiry to CONTACT the client)
- Pricing key for PricingService lookup
- Required documents checklist

All thresholds are configurable constants — never hardcoded in business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RenewalRule:
    """
    Describes how/when to renew a specific document type.

    Fields:
        rule_id:               Unique identifier for this rule.
        document_types:        Document categories this rule matches
                               ("visa", "kitas", "passport", "license").
        visa_type_patterns:    Substrings to match against current_visa_type
                               (case-insensitive). ["*"] = match any.
        processing_days:       Calendar days the authority typically takes.
        lead_time_days:        Days before expiry when the process should START.
        recommended_start_days: Days before expiry to CONTACT the client
                               (= lead_time_days + safety buffer).
        renewal_pricing_key:   Key in bali_zero_official_prices_2025.json.
                               None = not a Bali Zero service.
        required_docs:         Documents client must provide.
        complexity:            1.0 = simple extend, 2.0 = multi-permit, 3.0 = upgrade.
        notes:                 Human-readable notes for team.
    """

    rule_id: str
    document_types: tuple[str, ...]
    visa_type_patterns: tuple[str, ...]
    processing_days: int
    lead_time_days: int
    recommended_start_days: int
    renewal_pricing_key: str | None
    required_docs: tuple[str, ...]
    complexity: float = 1.0
    notes: str = ""


# ── Rule Registry ──────────────────────────────────────────────────────────────
#
# Ordered from most-specific to least-specific.
# RuleEngine.match() returns the first rule whose patterns all match.

RENEWAL_RULES: dict[str, RenewalRule] = {
    # ── KITAS Extends (most common) ───────────────────────────────────────────

    "kitas_investor_extend": RenewalRule(
        rule_id="kitas_investor_extend",
        document_types=("visa", "kitas"),
        visa_type_patterns=("investor", "KITAS Investor"),
        processing_days=14,
        lead_time_days=60,
        recommended_start_days=75,
        renewal_pricing_key="Investor KITAS 2 Years (Extend)",
        required_docs=(
            "valid_passport",
            "current_kitas_card",
            "company_deed",
            "company_nib",
            "domicile_letter",
        ),
        complexity=1.5,
        notes="Process via MOLINA. Confirm sponsor PT PMA still active.",
    ),

    "kitas_spouse_extend": RenewalRule(
        rule_id="kitas_spouse_extend",
        document_types=("visa", "kitas"),
        visa_type_patterns=("spouse",),
        processing_days=14,
        lead_time_days=60,
        recommended_start_days=75,
        renewal_pricing_key="Spouse 1 Year (Extend)",
        required_docs=(
            "valid_passport",
            "current_kitas_card",
            "marriage_certificate_apostille",
            "sponsor_kitas_or_kitap",
            "sponsor_ktp",
        ),
        complexity=1.0,
        notes="Sponsor KITAS must be valid for the duration of spouse KITAS.",
    ),

    "kitas_dependent_extend": RenewalRule(
        rule_id="kitas_dependent_extend",
        document_types=("visa", "kitas"),
        visa_type_patterns=("dependent",),
        processing_days=14,
        lead_time_days=60,
        recommended_start_days=75,
        renewal_pricing_key="Dependent 1 Year (Extend)",
        required_docs=(
            "valid_passport",
            "current_kitas_card",
            "sponsor_kitas_or_kitap",
            "birth_certificate_apostille",
        ),
        complexity=1.0,
        notes="Check if dependent is under 18; different docs for children.",
    ),

    "kitas_remote_worker_extend": RenewalRule(
        rule_id="kitas_remote_worker_extend",
        document_types=("visa", "kitas"),
        visa_type_patterns=("remote", "e33g", "digital nomad"),
        processing_days=14,
        lead_time_days=60,
        recommended_start_days=75,
        renewal_pricing_key="E33G Remote Worker (Extend)",
        required_docs=(
            "valid_passport",
            "current_kitas_card",
            "proof_of_income",
            "employment_contract_or_freelance_docs",
        ),
        complexity=1.0,
        notes="E33G extend — verify foreign income source documentation.",
    ),

    "kitas_retirement_extend": RenewalRule(
        rule_id="kitas_retirement_extend",
        document_types=("visa", "kitas"),
        visa_type_patterns=("retirement",),
        processing_days=14,
        lead_time_days=60,
        recommended_start_days=75,
        renewal_pricing_key="Retirement (Extend)",
        required_docs=(
            "valid_passport",
            "current_kitas_card",
            "pension_proof",
            "health_insurance",
            "bank_statement",
        ),
        complexity=1.0,
        notes="Altus/Onshore available. Confirm health insurance covers Bali.",
    ),

    "kitas_freelance_extend": RenewalRule(
        rule_id="kitas_freelance_extend",
        document_types=("visa", "kitas"),
        visa_type_patterns=("freelance", "e23"),
        processing_days=14,
        lead_time_days=60,
        recommended_start_days=75,
        renewal_pricing_key="Freelance E23 (Altus/Onshore)",
        required_docs=(
            "valid_passport",
            "current_kitas_card",
            "freelance_contract",
            "proof_of_income",
        ),
        complexity=1.5,
        notes="E23 6-month validity. Higher cost due to Altus processing.",
    ),

    # ── KITAS Working (complex — RPTKA + IMTA required) ──────────────────────

    "kitas_working_extend": RenewalRule(
        rule_id="kitas_working_extend",
        document_types=("visa", "kitas"),
        visa_type_patterns=("working", "work permit", "imta"),
        processing_days=30,
        lead_time_days=90,
        recommended_start_days=105,
        renewal_pricing_key="Working KITAS (Extend)",
        required_docs=(
            "valid_passport",
            "current_kitas_card",
            "rptka",
            "imta",
            "company_deed",
            "company_nib",
            "employee_agreement",
        ),
        complexity=2.0,
        notes="Bundle: RPTKA → IMTA → KITAS. Allow 30 working days.",
    ),

    # ── KITAP upgrade (long process, high value) ─────────────────────────────

    "kitap_investor_upgrade": RenewalRule(
        rule_id="kitap_investor_upgrade",
        document_types=("visa", "kitas"),
        visa_type_patterns=("kitap",),
        processing_days=60,
        lead_time_days=120,
        recommended_start_days=150,
        renewal_pricing_key="Investor KITAP + MERP",
        required_docs=(
            "valid_passport",
            "all_previous_kitas_cards",
            "police_clearance_skck",
            "company_deed",
            "company_financial_statements",
            "tax_clearance",
        ),
        complexity=3.0,
        notes="KITAP requires 5+ years continuous KITAS. Police clearance 3-month validity.",
    ),

    # ── Tourist / Short Stay ─────────────────────────────────────────────────

    "visa_tourist_extension": RenewalRule(
        rule_id="visa_tourist_extension",
        document_types=("visa",),
        visa_type_patterns=("c1", "tourist", "tourism"),
        processing_days=7,
        lead_time_days=14,
        recommended_start_days=21,
        renewal_pricing_key="C1 Tourism Extension",
        required_docs=(
            "valid_passport",
            "current_visa_stamp",
        ),
        complexity=1.0,
        notes="Extension adds +30 days. Only 1 extension allowed per C1 entry.",
    ),

    # ── Passport renewal (not a BZ service — advisory only) ──────────────────

    "passport_renewal": RenewalRule(
        rule_id="passport_renewal",
        document_types=("passport",),
        visa_type_patterns=("*",),
        processing_days=14,
        lead_time_days=180,
        recommended_start_days=210,
        renewal_pricing_key=None,  # Not a BZ service
        required_docs=(
            "old_passport",
            "id_photo_background_white",
            "embassy_appointment",
        ),
        complexity=1.0,
        notes="Advisory only — BZ does not process passports. Remind client to contact embassy. "
              "Passport must be valid for 6+ months beyond KITAS expiry.",
    ),

    # ── IMTA/RPTKA standalone renewal ────────────────────────────────────────

    "imta_annual_renewal": RenewalRule(
        rule_id="imta_annual_renewal",
        document_types=("license",),
        visa_type_patterns=("imta", "rptka"),
        processing_days=21,
        lead_time_days=60,
        recommended_start_days=75,
        renewal_pricing_key="Working KITAS (Extend)",  # Bundled in working package
        required_docs=(
            "current_imta",
            "current_rptka",
            "company_nib",
            "company_deed",
            "employee_agreement",
        ),
        complexity=2.0,
        notes="Annual permit for foreign workers. Usually bundled with Working KITAS renewal.",
    ),

    # ── Fallback rule — unknown/generic visa ─────────────────────────────────

    "generic_visa_renewal": RenewalRule(
        rule_id="generic_visa_renewal",
        document_types=("visa", "kitas", "license"),
        visa_type_patterns=("*",),
        processing_days=30,
        lead_time_days=90,
        recommended_start_days=105,
        renewal_pricing_key=None,
        required_docs=("valid_passport", "current_document"),
        complexity=1.5,
        notes="Generic fallback — consult with team for specific requirements.",
    ),
}


# ── Priority Query Order ───────────────────────────────────────────────────────
# Rules are checked in this order; first match wins.

RULE_PRIORITY_ORDER: tuple[str, ...] = (
    "kitap_investor_upgrade",
    "kitas_working_extend",
    "kitas_freelance_extend",
    "kitas_remote_worker_extend",
    "kitas_investor_extend",
    "kitas_retirement_extend",
    "kitas_spouse_extend",
    "kitas_dependent_extend",
    "imta_annual_renewal",
    "visa_tourist_extension",
    "passport_renewal",
    "generic_visa_renewal",
)


def match_rule(
    document_type: str,
    visa_type: str | None,
) -> RenewalRule:
    """
    Find the best matching renewal rule for a document.

    Checks rules in RULE_PRIORITY_ORDER.
    Returns the first rule where:
      - document_type is in rule.document_types
      - visa_type matches at least one pattern (case-insensitive substring)
        OR the rule has wildcard pattern ("*")

    Falls back to "generic_visa_renewal" if nothing matches.

    Args:
        document_type: One of "visa", "kitas", "passport", "license"
        visa_type:     Current visa type string (e.g., "KITAS Investor")

    Returns:
        Best matching RenewalRule.
    """
    doc_lower = document_type.lower()
    vt_lower = (visa_type or "").lower()

    for rule_id in RULE_PRIORITY_ORDER:
        rule = RENEWAL_RULES[rule_id]

        if doc_lower not in rule.document_types:
            continue

        # Wildcard matches any
        if "*" in rule.visa_type_patterns:
            return rule

        # Pattern match (substring, case-insensitive)
        if any(p.lower() in vt_lower for p in rule.visa_type_patterns):
            return rule

    return RENEWAL_RULES["generic_visa_renewal"]
