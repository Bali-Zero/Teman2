#!/usr/bin/env python3
"""Verified Generator — Main Orchestrator for NB Knowledge Population.

6-step pipeline:
  1. Load claims_db for domain
  2. Generate T2 document with Claude Sonnet 4.6 (forces [CLAIM-ID] markers)
  3. Validate markers (every [CLAIM-ID] must exist in claims_db)
  4. Auto-verify with CRAG-light (auto_verifier.py subprocess)
  5. NLM cross-check (skipped if NLM_BRIDGE_URL not set)
  6. Telegram human review (telegram_reviewer.py subprocess)

Usage:
    python scripts/verified_generator.py \\
        --domain immigration \\
        --topic "KITAS E31 Rinnovo: Procedura Completa" \\
        --output /tmp/nb2_kitas_renewal.txt
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).parent
CLAIMS_DB_DIR = SCRIPTS_DIR / "claims_db"
CLAIM_ID_PATTERN = re.compile(r"\[([A-Z]{2,3}-\d{3})\]")

GENERATION_PROMPT = """You are a Bali Zero knowledge author writing operational guides for staff.

Domain: {domain}
Topic: {topic}
Language: Italian (professional, precise)

CRITICAL RULES:
1. Every normative claim MUST be followed by its [CLAIM-ID] marker from claims_db
2. Only make claims that exist in the claims_db listed below
3. If you need to state something not in claims_db, write [NEEDS-VERIFICATION] instead
4. Structure: Introduction → Requirements → Procedure → Timing → Costs → FAQ

AVAILABLE CLAIMS (use [CLAIM-ID] after each referenced claim):
{claims_summary}

Write the complete operational guide now. Be thorough (800-1200 words).
Every sentence that asserts a legal fact MUST have a [CLAIM-ID] marker."""


def load_claims_db(domain: str) -> dict[str, dict[str, Any]]:
    """Load claims_db for a domain. Exits if not found."""
    path = CLAIMS_DB_DIR / f"{domain}_claims_db.json"
    if not path.exists():
        logger.error("Claims DB not found: %s — run claims_extractor.py first", path)
        sys.exit(1)
    with path.open() as f:
        raw: list[dict[str, Any]] = json.load(f)
    return {c["claim_id"]: c for c in raw if "claim_id" in c}


def build_claims_summary(claims_db: dict[str, dict[str, Any]]) -> str:
    """Build compact claims list for generation prompt (cap at 80)."""
    lines = [f"[{cid}] {c['claim']} (ref: {c['pasal_ref']})" for cid, c in list(claims_db.items())[:80]]
    if len(claims_db) > 80:
        lines.append(f"... and {len(claims_db) - 80} more claims available")
    return "\n".join(lines)


def generate_document(domain: str, topic: str, claims_db: dict[str, dict[str, Any]], api_key: str) -> str:
    """Step 2: Generate T2 document with Claude Sonnet 4.6."""
    import anthropic

    prompt = GENERATION_PROMPT.format(
        domain=domain, topic=topic, claims_summary=build_claims_summary(claims_db)
    )
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def validate_markers(document_text: str, claims_db: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Step 3: Check all [CLAIM-ID] markers exist in claims_db. Returns (valid, missing)."""
    found = list(set(CLAIM_ID_PATTERN.findall(document_text)))
    missing = [cid for cid in found if cid not in claims_db]
    valid = [cid for cid in found if cid in claims_db]
    return valid, missing


def run_auto_verifier(document_path: Path, domain: str) -> tuple[bool, str]:
    """Step 4: Run auto_verifier.py subprocess. Returns (passed, report_path)."""
    claims_db_path = CLAIMS_DB_DIR / f"{domain}_claims_db.json"
    report_path = Path(tempfile.mktemp(suffix="_verification_report.json"))
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "auto_verifier.py"),
         "--document", str(document_path),
         "--claims-db", str(claims_db_path),
         "--output", str(report_path)],
        capture_output=True, text=True,
    )
    return result.returncode == 0, str(report_path)


def run_telegram_review(report_path: str, document_name: str) -> bool:
    """Step 6: Run telegram_reviewer.py subprocess. Returns True if approved."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "telegram_reviewer.py"),
         "--report", report_path,
         "--document-name", document_name],
        capture_output=False,
    )
    return result.returncode == 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Verified Generation Pipeline for NB knowledge population")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    print(f"\nVerified Generation Pipeline — {args.domain} / {args.topic}")  # noqa: T201
    print("=" * 70)  # noqa: T201

    # Step 1
    print("\nStep 1: Loading claims_db...")  # noqa: T201
    claims_db = load_claims_db(args.domain)
    print(f"  {len(claims_db)} claims loaded")  # noqa: T201

    # Step 2
    print("\nStep 2: Generating document with Claude Sonnet 4.6...")  # noqa: T201
    document_text = generate_document(args.domain, args.topic, claims_db, api_key)
    output_path = Path(args.output)
    output_path.write_text(document_text, encoding="utf-8")
    print(f"  Generated {len(document_text)} chars -> {output_path}")  # noqa: T201

    # Step 3
    print("\nStep 3: Validating [CLAIM-ID] markers...")  # noqa: T201
    valid_ids, missing_ids = validate_markers(document_text, claims_db)
    print(f"  Valid: {len(valid_ids)}, Missing from DB: {len(missing_ids)}")  # noqa: T201
    if missing_ids:
        print(f"  WARNING: Unknown claim IDs will be flagged UNFAITHFUL: {missing_ids}")  # noqa: T201

    # Step 4
    print("\nStep 4: Running auto-verifier (CRAG-light)...")  # noqa: T201
    passed, report_path = run_auto_verifier(output_path, args.domain)
    if passed:
        print("  PASSED — all claims verified")  # noqa: T201
        print(f"\nPipeline COMPLETE — document ready: {output_path}")  # noqa: T201
        print("  Next: upload to NLM using notebooklm-mcp source_add")  # noqa: T201
        sys.exit(0)

    with open(report_path) as f:
        report = json.load(f)
    ratio = report.get("verified_ratio", 0)
    print(f"  BLOCKED — {ratio:.0%} verified (need >=95%)")  # noqa: T201
    print(f"  Failed: {[r['claim_id'] for r in report.get('failed', [])]}")  # noqa: T201

    # Step 5 (optional)
    nlm_url = os.environ.get("NLM_BRIDGE_URL", "")
    if nlm_url:
        print("\nStep 5: NLM cross-check... (not yet automated)")  # noqa: T201
    else:
        print("\nStep 5: Skipping NLM cross-check (NLM_BRIDGE_URL not set)")  # noqa: T201

    # Step 6
    print("\nStep 6: Requesting human review via Telegram...")  # noqa: T201
    approved = run_telegram_review(report_path, f"{args.domain} — {args.topic}")
    if approved:
        print(f"\nApproved — document ready: {output_path}")  # noqa: T201
        sys.exit(0)
    else:
        print("\nRejected — document NOT uploaded. Fix required.")  # noqa: T201
        print(f"  Review report: {report_path}")  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
