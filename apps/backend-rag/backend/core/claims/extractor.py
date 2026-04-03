"""Claim extraction from research responses.

Splits response text into paragraphs, detects regulatory references,
geographic scope, and visa types, then scores each claim using the
shared confidence formula.
"""

import logging
import re
import uuid
from datetime import datetime, timezone

from backend.core.claims.confidence import classify_confidence, compute_confidence
from backend.core.claims.models import ClaimRecord

logger = logging.getLogger(__name__)


def generate_claim_id(prefix: str = "NB2") -> str:
    """Generate a unique claim ID with the given prefix."""
    short_uuid = uuid.uuid4().hex[:8]
    return f"{prefix}-{short_uuid}"


def extract_claims_from_response(
    response_text: str,
    source_ids: list[str],
    query_cluster: str,
    sources_metadata: dict | None = None,
) -> list[ClaimRecord]:
    """Extract atomic claims from a research response.

    Performs paragraph-based extraction: splits the response into
    paragraphs, filters headers and short lines, then classifies
    each remaining paragraph as a claim.

    Args:
        response_text: Raw response text from NLM or Naga.
        source_ids: Source IDs cited in the response.
        query_cluster: Cluster letter (A-E) for provenance tracking.
        sources_metadata: Optional dict mapping source_id to metadata
            (must contain ``tier`` key for authority scoring).

    Returns:
        List of ClaimRecord instances (may be empty).
    """
    claims: list[ClaimRecord] = []
    now = datetime.now(timezone.utc).isoformat()

    # Split into paragraphs, skip headers and short lines
    paragraphs = [
        p.strip()
        for p in response_text.split("\n")
        if p.strip()
        and not p.strip().startswith("#")
        and not p.strip().startswith("**Nama File")
        and len(p.strip()) > 50
    ]

    for para in paragraphs:
        # Skip markdown-style emphasis headers and table lines
        if para.startswith("*") and para.endswith("*"):
            continue
        if para.startswith("|") or para.startswith("---"):
            continue

        # Detect regulatory references (pasal, ayat, UU, PP, Permen, etc.)
        has_pasal = bool(
            re.search(r"(?i)(pasal|ayat|UU|PP|Permen|Kepmen|SE\s)", para)
        )
        is_regulatory = bool(
            re.search(
                r"(?i)(peraturan|undang|regulasi|ketentuan|ditetapkan|berlaku)",
                para,
            )
        )
        is_bali = bool(
            re.search(r"(?i)(bali|ngurah rai|denpasar|badung|gianyar)", para)
        )

        # Determine best tier from source metadata
        highest_tier = 2  # default T2
        if sources_metadata:
            for sid in source_ids:
                src = sources_metadata.get(sid, {})
                tier = src.get("tier", 2)
                highest_tier = min(highest_tier, tier)

        confidence = compute_confidence(
            highest_tier=highest_tier,
            source_count=len(source_ids),
            has_specific_pasal=has_pasal,
            is_regulatory=is_regulatory,
            days_since_pub=30,  # default recent
            is_bali_specific=is_bali,
        )

        # Classify category based on keywords
        category = _classify_category(para)

        # Geographic scope
        geo = "LOCAL_BALI" if is_bali else "NATIONAL"

        # Detect visa types mentioned
        visa_types = _detect_visa_types(para)

        claim = ClaimRecord(
            claim_id=generate_claim_id(),
            claim_text=para[:500],  # truncate to 500 chars
            category=category,
            confidence_class=classify_confidence(confidence),
            confidence_score=confidence,
            source_ids=source_ids,
            extracted=now,
            geographic_scope=geo,
            affected_visa_types=visa_types,
        )
        claims.append(claim)

    logger.info(
        "Extracted %d claims from response (%d paragraphs)",
        len(claims),
        len(paragraphs),
    )
    return claims


def _classify_category(text: str) -> str:
    """Classify claim text into one of the 15 canonical categories."""
    text_lower = text.lower()

    if any(
        w in text_lower
        for w in ["mencabut", "menggantikan", "perubahan", "amended", "revoked"]
    ):
        return "LEGAL_CHANGE"
    if any(
        w in text_lower for w in ["tarif", "biaya", "pnbp", "fee", "rp ", "usd "]
    ):
        return "FEE_CHANGE"
    if any(
        w in text_lower
        for w in ["deportasi", "overstay", "pelanggaran", "sanksi"]
    ):
        return "ENFORCEMENT_ACTION"
    if any(
        w in text_lower
        for w in ["tim pora", "sidak", "operasi gabungan", "razia"]
    ):
        return "ENFORCEMENT_PATTERN"
    if any(
        w in text_lower for w in ["prosedur", "langkah", "step", "tahap"]
    ):
        return "PROCEDURAL_STEP"
    if any(
        w in text_lower
        for w in ["syarat", "persyaratan", "dokumen", "requirement"]
    ):
        return "DOCUMENT_REQUIREMENT"
    if any(
        w in text_lower for w in ["perda", "pergub", "kabupaten", "provinsi"]
    ):
        return "LOCAL_REGULATION"
    if any(
        w in text_lower for w in ["wajib", "dilarang", "eligible", "minimum"]
    ):
        return "ELIGIBILITY_RULE"
    if any(
        w in text_lower for w in ["sistem", "portal", "online", "digital"]
    ):
        return "SYSTEM_STATUS"
    if any(
        w in text_lower for w in ["hari kerja", "working days", "waktu proses"]
    ):
        return "PROCESSING_TIME"

    return "OPERATIONAL_CHANGE"


def _detect_visa_types(text: str) -> list[str]:
    """Detect visa type references in claim text."""
    types: list[str] = []
    patterns: dict[str, str] = {
        "KITAS_E23": r"(?i)(E23|KITAS\s*kerja|TKA)",
        "KITAS_E28": r"(?i)(E28[ABCD]|golden\s*visa|investit)",
        "KITAS_E31": r"(?i)(E31|family|keluarga|dependent)",
        "KITAS_E33": r"(?i)(E33[A-G]|second\s*home|pensiun|silver\s*hair|digital\s*nomad)",
        "VISA_C1": r"(?i)(C1|B211A|tourist|wisata)",
        "VISA_C2": r"(?i)(C2|bisnis|business\s*visit)",
        "VOA": r"(?i)(VOA|visa\s*on\s*arrival|e-?VOA)",
        "KITAP": r"(?i)(KITAP|izin\s*tinggal\s*tetap|permanent)",
    }
    for vtype, pattern in patterns.items():
        if re.search(pattern, text):
            types.append(vtype)
    return types
