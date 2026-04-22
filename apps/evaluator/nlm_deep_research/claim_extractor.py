"""Claim extraction and classification for NLM Deep Research Pipeline.

Extracts atomic claims from NLM query responses, classifies them into
10 categories, scores confidence, and appends to the claims JSONL registry.
"""

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 10 claim categories per spec §3
CLAIM_CATEGORIES = [
    "LEGAL_CHANGE",
    "OPERATIONAL_CHANGE",
    "ENFORCEMENT_ACTION",
    "ENFORCEMENT_PATTERN",
    "POLICY_SIGNAL",
    "PROCEDURAL_STEP",
    "LOCAL_REGULATION",
    "DOCUMENT_REQUIREMENT",
    "FEE_CHANGE",
    "SOURCE_GAP",
    "SOURCE_REGISTRATION",
    "BASELINE_EXISTING",
    "SYSTEM_STATUS",
    "PROCESSING_TIME",
    "ELIGIBILITY_RULE",
]

# Confidence thresholds
CONFIDENCE_VERIFIED = 0.75
CONFIDENCE_PROVISIONAL = 0.55
CONFIDENCE_MONITORING = 0.35

# Confidence weights per spec §3
W_AUTH = 0.30
W_CORR = 0.25
W_SPEC = 0.15
W_TYPE = 0.12
W_RECENCY = 0.10
W_GEO = 0.08

# Tier authority scores
TIER_AUTHORITY: dict[int, float] = {
    0: 1.00,
    1: 0.95,
    2: 0.90,
    3: 0.80,
    4: 0.75,
    5: 0.60,
    6: 0.30,
}


@dataclass
class ClaimRecord:
    """Atomic verifiable claim extracted from NLM response."""

    claim_id: str
    claim_text: str
    category: str
    confidence_class: str
    confidence_score: float
    source_ids: list[str]
    extracted: str
    status: str = "active"
    geographic_scope: str = "NATIONAL"
    affected_visa_types: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    flags: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        return {k: v for k, v in asdict(self).items() if v}


def classify_confidence(score: float) -> str:
    """Classify confidence score into VERIFIED/PROVISIONAL/LOW."""
    if score >= CONFIDENCE_VERIFIED:
        return "VERIFIED"
    elif score >= CONFIDENCE_PROVISIONAL:
        return "PROVISIONAL"
    else:
        return "LOW"


def compute_confidence(
    highest_tier: int,
    source_count: int,
    has_specific_pasal: bool,
    is_regulatory: bool,
    days_since_pub: int,
    is_bali_specific: bool,
) -> float:
    """Compute confidence score using 6-factor weighted formula.

    Args:
        highest_tier: Best (lowest) tier among backing sources (0=T0, 6=T6)
        source_count: Number of distinct sources backing this claim
        has_specific_pasal: Whether claim cites specific pasal/ayat
        is_regulatory: Whether claim is about a regulation (vs operational)
        days_since_pub: Days since source publication
        is_bali_specific: Whether claim is specific to Bali
    """
    # S_auth: authority of best source
    s_auth = TIER_AUTHORITY.get(highest_tier, 0.50)

    # S_corr: corroboration from multiple sources
    s_corr = min(1.0, source_count / 3)

    # S_spec: specificity of claim
    s_spec = 1.0 if has_specific_pasal else 0.6

    # S_type: regulatory vs operational
    s_type = 1.0 if is_regulatory else 0.7

    # S_recency: temporal freshness
    if days_since_pub <= 30:
        s_recency = 1.0
    elif days_since_pub <= 180:
        s_recency = 0.8
    elif days_since_pub <= 365:
        s_recency = 0.6
    else:
        s_recency = 0.4

    # S_geo: geographic relevance
    s_geo = 0.9 if is_bali_specific else 1.0

    # Penalty: none by default
    penalty = 0.0

    score = (
        W_AUTH * s_auth
        + W_CORR * s_corr
        + W_SPEC * s_spec
        + W_TYPE * s_type
        + W_RECENCY * s_recency
        + W_GEO * s_geo
        - penalty
    )
    return round(min(1.0, max(0.0, score)), 3)


def generate_claim_id(prefix: str = "NB2") -> str:
    """Generate unique claim ID."""
    short_uuid = uuid.uuid4().hex[:8]
    return f"{prefix}-{short_uuid}"


def extract_claims_from_response(
    response_text: str,
    source_ids: list[str],
    query_cluster: str,
    sources_metadata: Optional[dict] = None,
) -> list[ClaimRecord]:
    """Extract atomic claims from an NLM query response.

    This performs basic extraction — splitting response into paragraphs
    and identifying claim-like statements. For production, this would
    be enhanced with LLM-assisted extraction.

    Args:
        response_text: Raw NLM response text
        source_ids: NLM source IDs cited in response
        query_cluster: Cluster letter (A-E)
        sources_metadata: Optional source registry for tier lookup
    """
    claims: list[ClaimRecord] = []
    now = datetime.now(timezone.utc).isoformat()

    # Split response into paragraphs, skip headers and empty lines
    paragraphs = [
        p.strip()
        for p in response_text.split("\n")
        if p.strip()
        and not p.strip().startswith("#")
        and not p.strip().startswith("**Nama File")
        and len(p.strip()) > 50
    ]

    for para in paragraphs:
        # Skip if it looks like a header or reference list
        if para.startswith("*") and para.endswith("*"):
            continue
        if para.startswith("|") or para.startswith("---"):
            continue

        # Detect regulatory references (pasal, ayat, UU, PP, Permen)
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
        "Extracted %d claims from response (%d paragraphs)", len(claims), len(paragraphs)
    )
    return claims


def _classify_category(text: str) -> str:
    """Classify claim into one of the defined categories based on keywords."""
    text_lower = text.lower()

    if any(w in text_lower for w in ["mencabut", "menggantikan", "perubahan", "amended", "revoked"]):
        return "LEGAL_CHANGE"
    if any(w in text_lower for w in ["tarif", "biaya", "pnbp", "fee", "rp ", "usd "]):
        return "FEE_CHANGE"
    if any(w in text_lower for w in ["deportasi", "overstay", "pelanggaran", "sanksi"]):
        return "ENFORCEMENT_ACTION"
    if any(w in text_lower for w in ["tim pora", "sidak", "operasi gabungan", "razia"]):
        return "ENFORCEMENT_PATTERN"
    if any(w in text_lower for w in ["prosedur", "langkah", "step", "tahap"]):
        return "PROCEDURAL_STEP"
    if any(w in text_lower for w in ["syarat", "persyaratan", "dokumen", "requirement"]):
        return "DOCUMENT_REQUIREMENT"
    if any(w in text_lower for w in ["perda", "pergub", "kabupaten", "provinsi"]):
        return "LOCAL_REGULATION"
    if any(w in text_lower for w in ["wajib", "dilarang", "eligible", "minimum"]):
        return "ELIGIBILITY_RULE"
    if any(w in text_lower for w in ["sistem", "portal", "online", "digital"]):
        return "SYSTEM_STATUS"
    if any(w in text_lower for w in ["hari kerja", "working days", "waktu proses"]):
        return "PROCESSING_TIME"

    return "OPERATIONAL_CHANGE"


def _detect_visa_types(text: str) -> list[str]:
    """Detect visa type references in claim text."""
    types = []
    patterns = {
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


def append_claims_to_registry(
    claims: list[ClaimRecord],
    claims_file: str | Path,
) -> int:
    """Append claims to the JSONL registry file.

    Args:
        claims: List of ClaimRecord to append
        claims_file: Path to the claims JSONL file

    Returns:
        Total number of claims in registry after append
    """
    claims_path = Path(claims_file)
    claims_path.parent.mkdir(parents=True, exist_ok=True)

    with open(claims_path, "a") as f:
        for claim in claims:
            f.write(json.dumps(claim.to_dict(), ensure_ascii=False) + "\n")

    # Count total claims
    total = sum(1 for _ in open(claims_path))
    logger.info("Appended %d claims to %s (total: %d)", len(claims), claims_path, total)

    # Yajña Ledger hook — record CLAIM_OFFERED for each new claim.
    # Optional, silent on failure, disabled by env YAJNA_LEDGER_DISABLED=1.
    try:
        from apps.evaluator.nlm_deep_research.yajna_ledger import (
            EVENT_CLAIM_OFFERED,
            append_events_batch,
        )

        # Infer nb key from claims_file path (e.g. nlm_nb4_claims.jsonl -> nb4)
        nb_key = ""
        stem = claims_path.stem  # e.g. nlm_nb4_claims
        parts = stem.split("_")
        for p in parts:
            if p.startswith("nb") and p[2:].isdigit():
                nb_key = p
                break

        append_events_batch(
            event_type=EVENT_CLAIM_OFFERED,
            nb=nb_key,
            entries=[
                (
                    c.claim_id,
                    {
                        "category": c.category,
                        "confidence": c.confidence_score,
                        "confidence_class": c.confidence_class,
                    },
                )
                for c in claims
            ],
        )
    except Exception as exc:  # pragma: no cover — hook must never block extractor
        logger.debug("yajna hook skipped: %s", exc)

    return total


def load_claims_count(claims_file: str | Path) -> int:
    """Count claims in JSONL registry."""
    claims_path = Path(claims_file)
    if not claims_path.exists():
        return 0
    return sum(1 for _ in open(claims_path))
