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

from dataclasses import dataclass


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
        renewal_pricing_key:   Key in bali_zero_official_prices_2026.json.
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
    nb2_ref: str | None = None  # NB-2 citation for audit (decision #9)


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
    "visa_voa_extension": RenewalRule(
        rule_id="visa_voa_extension",
        document_types=("visa",),
        visa_type_patterns=("b1", "voa", "visa on arrival", "arrival"),
        processing_days=5,
        lead_time_days=10,
        recommended_start_days=14,
        renewal_pricing_key="B1 Visa on Arrival Extension",
        required_docs=(
            "valid_passport",
            "current_visa_stamp",
        ),
        complexity=1.0,
        notes="VOA extension adds +30 days. Only 1 extension allowed per VOA entry.",
    ),
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
    # ── E33 Second Home senior routes (55+) ──────────────────────────────
    # These MUST be matched before "e33_second_home_renewal": the generic
    # rule's patterns ("e33", "second home") are substrings of every senior
    # string, and its checklist asks for the main-route USD 130k deposit /
    # USD 1M property title — neither of which applies to a senior client.
    # Matching is on the VISA CODE (language-invariant fact-key), not prose.
    "e33e_senior_renewal": RenewalRule(
        rule_id="e33e_senior_renewal",
        document_types=("visa", "kitas"),
        visa_type_patterns=("e33e",),
        processing_days=30,
        lead_time_days=120,
        recommended_start_days=150,
        renewal_pricing_key="E33E Second Home Senior (5 Years)",
        required_docs=(
            "valid_passport",
            "current_itas_card",
            "deposit_proof_usd_50k_own_name_bumn_bank",
            "bank_statement_3m_usd_2k_own_name",
            "passive_income_proof_usd_3k_per_month",
            "domicile_letter",
        ),
        complexity=2.0,
        notes="E33E senior (55+) 5-year route. The permit carries NO extension "
        "(catalogue extensions=(0,0)) — at expiry this is a fresh application, "
        "hence the long lead time and the new-application onshore pricing key. "
        "Financial gate is CUMULATIVE, not alternative: USD 50,000 own-name BUMN "
        "deposit AND a 3-month personal rekening koran of at least USD 2,000 AND "
        "USD 3,000/month passive income. NOT the main-route USD 130k deposit, and "
        "there is no property alternative on this route. NO sponsor — the page "
        "states it outright ('Anda tidak membutuhkan penjamin/sponsor'), which is "
        "the axis that separates this route from E33F.",
    ),
    "e33f_senior_renewal": RenewalRule(
        rule_id="e33f_senior_renewal",
        document_types=("visa", "kitas"),
        visa_type_patterns=("e33f",),
        processing_days=14,
        lead_time_days=60,
        recommended_start_days=75,
        renewal_pricing_key="E33F Second Home Senior (Extend)",
        required_docs=(
            "valid_passport",
            "current_itas_card",
            "sponsor_penjamin_documents",
            "bank_statement_3m_usd_2k_own_or_sponsor",
            "passive_income_proof_usd_3k_per_month",
            "domicile_letter",
        ),
        complexity=1.0,
        notes="E33F senior 1-year route, annually renewable. NO deposit exists "
        "here — never request a bank guarantee letter. But 'no deposit' does not "
        "mean 'income only': the route REQUIRES a penjamin/sponsor ('Anda "
        "membutuhkan penjamin/sponsor', the exact opposite of E33E) plus a "
        "3-month rekening koran of at least USD 2,000, which may be held in the "
        "foreigner's OR the sponsor's name, plus USD 3,000/month income. The "
        "official page publishes no minimum age for E33F.",
    ),
    "e33_senior_route_unspecified": RenewalRule(
        rule_id="e33_senior_route_unspecified",
        document_types=("visa", "kitas"),
        visa_type_patterns=("elderly", "lansia", "second home senior"),
        processing_days=30,
        lead_time_days=120,
        recommended_start_days=150,
        renewal_pricing_key=None,  # route unknown — quoting one would be a guess
        required_docs=(
            "valid_passport",
            "current_itas_card",
            "bank_statement_3m_usd_2k",
            "passive_income_proof_usd_3k_per_month",
            "domicile_letter",
            "route_confirmation_e33e_deposit_no_sponsor_or_e33f_sponsor_no_deposit",
        ),
        complexity=2.0,
        notes="Senior second-home client whose record does not carry the E33E/E33F "
        "code. Ask only for what BOTH routes require — the USD 2,000 3-month "
        "rekening koran and the USD 3,000/month income. The two things that "
        "actually diverge are asked for by neither: E33E wants a USD 50,000 "
        "deposit and NO sponsor, E33F wants a sponsor and NO deposit. Requesting "
        "either before the route is known sends the client after a document their "
        "route does not have. Lead time is the conservative (E33E) one: contacting "
        "early is recoverable, contacting late is not.",
    ),
    # ── E33 Second Home main route (5y permit — guarantee must be maintained) ──
    "e33_second_home_renewal": RenewalRule(
        rule_id="e33_second_home_renewal",
        document_types=("visa", "kitas"),
        visa_type_patterns=("e33", "second home"),
        processing_days=30,
        lead_time_days=120,
        recommended_start_days=150,
        renewal_pricing_key=None,  # owner-set all-inclusive pricing; no catalog key yet
        required_docs=(
            "valid_passport",
            "current_itas_card",
            "guarantee_proof_bank_confirmation_or_property_title",
            "domicile_letter",
        ),
        complexity=2.0,
        notes="E33 Second Home renewal — verify the USD 130k BUMN deposit (or "
        "USD 1M property) is still maintained before filing. Day-90 guarantee "
        "gate tracked separately by services/crm/e33_lifecycle.py.",
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
    # Senior second-home routes come BEFORE the generic E33 rule: "e33" and
    # "second home" are substrings of every senior string, so the generic rule
    # would otherwise capture them and hand out the main-route deposit checklist.
    "e33e_senior_renewal",
    "e33f_senior_renewal",
    "e33_senior_route_unspecified",
    "e33_second_home_renewal",
    "kitas_investor_extend",
    "kitas_retirement_extend",
    "kitas_spouse_extend",
    "kitas_dependent_extend",
    "imta_annual_renewal",
    "visa_voa_extension",
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
