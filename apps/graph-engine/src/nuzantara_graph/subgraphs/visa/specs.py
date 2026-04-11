"""Visa specifications and legacy type identification.

Moved from the old subgraphs/visa.py. The multi-step planner still needs
these for the initial "dominant visa" classification used by the composer.
"""

from __future__ import annotations

from typing import Any

from nuzantara_schemas.domain.visa import VisaType
from nuzantara_schemas.state import GraphState

VISA_SPECS: dict[str, dict[str, Any]] = {
    VisaType.KITAS: {
        "duration_months": 12,
        "extendable": True,
        "sponsor_required": True,
        "work_permit_included": True,
        "costs_usd": {"pnbp": 250, "telex": 100, "kitas_card": 50},
        "processing_days": 30,
        "requirements": [
            "Sponsoring company (PT PMA or PT PMDN)",
            "RPTKA (foreign worker utilization plan) approved by Ministry of Labor",
            "IMTA (work permit) via SPKP system",
            "E-Visa application via imigrasi.go.id",
            "Valid passport (min. 18 months validity)",
            "Photo 4x6cm red background",
            "CV/resume for position",
            "Company sponsorship letter",
        ],
    },
    VisaType.KITAP: {
        "duration_months": 60,
        "extendable": True,
        "sponsor_required": True,
        "work_permit_included": False,
        "costs_usd": {"pnbp": 570, "telex": 100, "kitap_card": 50},
        "processing_days": 45,
        "requirements": [
            "Held KITAS for minimum 3 consecutive years",
            "OR married to Indonesian citizen (2 years)",
            "OR retired (55+ with pension proof)",
            "Domicile in Indonesia",
            "Police clearance (SKCK)",
            "Financial proof (bank statements)",
        ],
    },
    VisaType.B211A: {
        "duration_months": 2,
        "extendable": True,
        "max_extensions": 4,
        "sponsor_required": True,
        "work_permit_included": False,
        "costs_usd": {"visa_fee": 120, "extension": 60},
        "processing_days": 5,
        "requirements": [
            "Sponsor (agent or individual Indonesian citizen)",
            "Valid passport (min. 6 months validity)",
            "Return/onward ticket",
            "Proof of funds",
            "Cannot work (social/business visit only)",
        ],
        "note": (
            "The B211 visit visa was abolished; replaced by C-series "
            "e-visas (C1/C2/C7)."
        ),
    },
    VisaType.VOA: {
        "duration_months": 1,
        "extendable": True,
        "max_extensions": 1,
        "sponsor_required": False,
        "work_permit_included": False,
        "costs_usd": {"arrival": 35, "extension": 35},
        "processing_days": 0,
        "requirements": [
            "Available at major airports and seaports",
            "Eligible passport holders (90+ countries)",
            "Return/onward ticket required",
            "Valid passport (min. 6 months validity)",
            "Cannot work",
            "Extension to 60 days at immigration office",
        ],
    },
    VisaType.E_VISA: {
        "duration_months": 2,
        "extendable": False,
        "sponsor_required": True,
        "work_permit_included": False,
        "costs_usd": {"visa_fee": 120},
        "processing_days": 3,
        "requirements": [
            "Apply online via molina.imigrasi.go.id",
            "Sponsor required",
            "Must convert to KITAS within 60 days if staying",
        ],
    },
    VisaType.SECOND_HOME: {
        "duration_months": 60,
        "extendable": True,
        "sponsor_required": False,
        "work_permit_included": False,
        "costs_usd": {"visa_fee": 300},
        "processing_days": 10,
        "requirements": [
            "Proof of funds: USD 130,000 in Indonesian bank",
            "OR property ownership in Indonesia",
            "OR proof of retirement income",
            "Health insurance valid in Indonesia",
            "No criminal record",
            "Cannot work (investment/retirement only)",
        ],
    },
}


def _identify_visa_type(state: GraphState) -> VisaType:
    """Determine visa type from extracted entities and query context."""
    entities = state.extracted_entities
    query_lower = state.query.lower()

    if "visa_type" in entities:
        vt = str(entities["visa_type"]).lower()
        if "kitas" in vt:
            return VisaType.KITAS
        if "kitap" in vt:
            return VisaType.KITAP
        if "b211" in vt:
            return VisaType.B211A
        if "voa" in vt or "arrival" in vt:
            return VisaType.VOA
        if "second home" in vt:
            return VisaType.SECOND_HOME

    if "kitas" in query_lower or "work permit" in query_lower or "izin kerja" in query_lower:
        return VisaType.KITAS
    if "kitap" in query_lower or "permanent" in query_lower:
        return VisaType.KITAP
    if "b211" in query_lower or "social" in query_lower:
        return VisaType.B211A
    if "voa" in query_lower or "visa on arrival" in query_lower or "tourist" in query_lower:
        return VisaType.VOA
    if "second home" in query_lower or "retire" in query_lower or "pensiun" in query_lower:
        return VisaType.SECOND_HOME

    return VisaType.KITAS
