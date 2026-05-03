"""Handoff package generation for NLM → Intel Scraper integration.

Generates versioned JSON handoff files that the scraper reads at 03:00 WITA.
Follows spec §5: file-based, zero coupling, atomic writes, audit trail.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Handoff directory
HANDOFF_DIR = os.path.expanduser("~/.agent/decisions/nlm_to_scraper/handoff")

# Schema version
SCHEMA_VERSION = "1.0"

# TRS (Topic Relevance Score) thresholds
TRS_HANDOFF = 0.65  # Minimum TRS for inclusion in handoff
TRS_CANDIDATE = 0.45  # Candidate but not auto-included
MAX_HANDOFF_FINDINGS = 5  # Max findings per handoff

# Integration modes
MODE_IGNORE = "IGNORE"  # No handoff file or empty
MODE_ENRICH = "ENRICH"  # Avg confidence < 0.75
MODE_PRIORITIZE = "PRIORITIZE"  # Avg confidence >= 0.75


def calculate_trs(
    claim_confidence: float,
    source_count: int,
    is_new_topic: bool,
    geographic_relevance: float = 1.0,
    days_since_extraction: int = 0,
) -> float:
    """Calculate Topic Relevance Score for handoff selection.

    TRS = 0.35*confidence + 0.25*corroboration + 0.20*novelty + 0.10*geo + 0.10*freshness

    Args:
        claim_confidence: Confidence score of the claim (0-1)
        source_count: Number of backing sources
        is_new_topic: Whether this is a novel finding
        geographic_relevance: Bali relevance (1.0=national, 0.9=bali-specific)
        days_since_extraction: Days since claim was extracted
    """
    # Confidence factor
    f_conf = claim_confidence

    # Corroboration factor
    f_corr = min(1.0, source_count / 3)

    # Novelty factor
    f_novel = 1.0 if is_new_topic else 0.5

    # Geographic relevance
    f_geo = geographic_relevance

    # Freshness decay
    if days_since_extraction <= 1:
        f_fresh = 1.0
    elif days_since_extraction <= 7:
        f_fresh = 0.8
    elif days_since_extraction <= 30:
        f_fresh = 0.5
    else:
        f_fresh = 0.3

    trs = (
        0.35 * f_conf
        + 0.25 * f_corr
        + 0.20 * f_novel
        + 0.10 * f_geo
        + 0.10 * f_fresh
    )
    return round(min(1.0, max(0.0, trs)), 3)


def classify_trs(trs: float) -> str:
    """Classify TRS into HANDOFF/CANDIDATE/SKIP."""
    if trs >= TRS_HANDOFF:
        return "HANDOFF"
    elif trs >= TRS_CANDIDATE:
        return "CANDIDATE"
    return "SKIP"


def determine_integration_mode(claims: list[dict]) -> str:
    """Determine integration mode from claim confidence distribution.

    Returns MODE_IGNORE, MODE_ENRICH, or MODE_PRIORITIZE.
    """
    if not claims:
        return MODE_IGNORE

    avg_confidence = sum(c.get("confidence_score", 0) for c in claims) / len(claims)

    if avg_confidence >= 0.75:
        return MODE_PRIORITIZE
    return MODE_ENRICH


def select_handoff_topics(
    claims: list[dict],
    max_topics: int = MAX_HANDOFF_FINDINGS,
) -> list[dict]:
    """Select top claims for handoff based on TRS.

    Args:
        claims: List of claim dicts with confidence_score, source_ids, etc.
        max_topics: Maximum number of topics to include

    Returns:
        List of selected claims with TRS scores
    """
    scored = []
    for claim in claims:
        trs = calculate_trs(
            claim_confidence=claim.get("confidence_score", 0),
            source_count=len(claim.get("source_ids", [])),
            is_new_topic=True,  # all claims from today's run are new
            geographic_relevance=0.9 if claim.get("geographic_scope") == "LOCAL_BALI" else 1.0,
            days_since_extraction=0,
        )
        claim_with_trs = {**claim, "trs": trs, "trs_class": classify_trs(trs)}
        scored.append(claim_with_trs)

    # Sort by TRS descending
    scored.sort(key=lambda c: c["trs"], reverse=True)

    # Filter to HANDOFF class, then take top N
    handoff = [c for c in scored if c["trs_class"] == "HANDOFF"][:max_topics]

    # If not enough HANDOFF, add CANDIDATEs
    if len(handoff) < max_topics:
        candidates = [c for c in scored if c["trs_class"] == "CANDIDATE"]
        handoff.extend(candidates[: max_topics - len(handoff)])

    logger.info(
        "Selected %d/%d claims for handoff (TRS range: %.3f-%.3f)",
        len(handoff),
        len(claims),
        handoff[-1]["trs"] if handoff else 0,
        handoff[0]["trs"] if handoff else 0,
    )
    return handoff


def generate_handoff(
    claims: list[dict],
    pipeline_run_id: str,
    notebook_id: str,
    query_cluster: str,
    queries_executed: int,
    domain_denylist: Optional[list[str]] = None,
) -> dict:
    """Generate complete handoff package per schema v1.0.

    Args:
        claims: All claims from today's pipeline run
        pipeline_run_id: Unique ID for this pipeline run
        notebook_id: NLM notebook ID
        query_cluster: Today's cluster letter (A-E)
        queries_executed: Number of queries executed today
        domain_denylist: URLs to exclude from scraper suggestions
    """
    # Select top topics
    selected = select_handoff_topics(claims)

    # Determine integration mode
    mode = determine_integration_mode(selected)

    # Build findings
    findings = []
    for i, claim in enumerate(selected):
        finding = {
            "finding_id": f"F-{pipeline_run_id[:8]}-{i+1:02d}",
            "headline": claim.get("claim_text", "")[:200],
            "category": claim.get("category", "OPERATIONAL_CHANGE"),
            "confidence_score": claim.get("confidence_score", 0),
            "confidence_class": claim.get("confidence_class", "LOW"),
            "geographic_scope": claim.get("geographic_scope", "NATIONAL"),
            "affected_visa_types": claim.get("affected_visa_types", []),
            "source_count": len(claim.get("source_ids", [])),
            "trs": claim.get("trs", 0),
        }
        findings.append(finding)

    # Build suggested topics for scraper
    suggested_topics = []
    for claim in selected[:3]:
        topic = {
            "topic": claim.get("claim_text", "")[:100],
            "confidence": claim.get("confidence_score", 0),
            "priority": "HIGH" if claim.get("confidence_score", 0) >= 0.75 else "MEDIUM",
        }
        suggested_topics.append(topic)

    # Avoid URLs
    avoid_urls = domain_denylist or []

    package = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_run_id": pipeline_run_id,
        "notebook_id": notebook_id,
        "query_cluster": query_cluster,
        "queries_executed": queries_executed,
        "integration_mode": mode,
        "key_findings": findings,
        "suggested_topics": suggested_topics,
        "scraper_hints": {
            "avoid_urls": avoid_urls[:10],
            "priority_domains": [
                "imigrasi.go.id",
                "kemnaker.go.id",
                "peraturan.go.id",
                "hukumonline.com",
            ],
        },
    }

    return package


def validate_handoff_schema(package: dict) -> tuple[bool, list[str]]:
    """Validate handoff package against schema v1.0.

    Returns:
        (is_valid, list_of_errors)
    """
    errors = []

    required_fields = [
        "schema_version",
        "generated_at",
        "pipeline_run_id",
        "notebook_id",
        "query_cluster",
        "queries_executed",
        "integration_mode",
        "key_findings",
    ]

    for field in required_fields:
        if field not in package:
            errors.append(f"Missing required field: {field}")

    if package.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"Schema version mismatch: {package.get('schema_version')} != {SCHEMA_VERSION}"
        )

    mode = package.get("integration_mode")
    if mode not in (MODE_IGNORE, MODE_ENRICH, MODE_PRIORITIZE):
        errors.append(f"Invalid integration mode: {mode}")

    findings = package.get("key_findings", [])
    if len(findings) > MAX_HANDOFF_FINDINGS:
        errors.append(f"Too many findings: {len(findings)} > {MAX_HANDOFF_FINDINGS}")

    return len(errors) == 0, errors


def save_handoff(package: dict, output_dir: Optional[str] = None) -> Path:
    """Save handoff package as dated JSON + latest.json symlink.

    Args:
        package: Validated handoff package dict
        output_dir: Override default handoff directory

    Returns:
        Path to the saved dated file
    """
    handoff_dir = Path(output_dir or HANDOFF_DIR)
    handoff_dir.mkdir(parents=True, exist_ok=True)

    # Dated filename
    date_str = datetime.now().strftime("%Y-%m-%d")
    dated_file = handoff_dir / f"{date_str}.json"
    latest_file = handoff_dir / "latest.json"

    # Atomic write: write to temp, then rename
    temp_file = handoff_dir / f".tmp_{date_str}.json"
    with open(temp_file, "w") as f:
        json.dump(package, f, indent=2, ensure_ascii=False)

    # Rename temp to final (atomic on POSIX)
    temp_file.rename(dated_file)

    # Update latest.json symlink
    if latest_file.exists() or latest_file.is_symlink():
        latest_file.unlink()
    latest_file.symlink_to(dated_file.name)

    logger.info(
        "Saved handoff: %s (%d findings, mode=%s)",
        dated_file,
        len(package.get("key_findings", [])),
        package.get("integration_mode"),
    )
    return dated_file
