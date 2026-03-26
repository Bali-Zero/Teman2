#!/usr/bin/env python3
"""Verified Generator — Main Orchestrator for NB Knowledge Population.

6-step pipeline:
  1. Load claims_db for domain
  2. Generate T2 document via claude CLI — Max subscription (forces [CLAIM-ID] markers)
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

REVISION_PROMPT = """You are a Bali Zero knowledge author revising an existing operational guide for staff.

Domain: {domain}
Topic: {topic}
Language: Italian (professional, precise)

EXISTING DOCUMENT TO REVISE:
{existing_text}

CRITICAL RULES:
1. Every normative claim MUST be followed by its [CLAIM-ID] marker from claims_db
2. Only make claims that exist in the claims_db listed below
3. Replace any [NEEDS-VERIFICATION] markers or unsupported claims with verified [CLAIM-ID] markers
4. Preserve the document structure where correct; fix only what is wrong

AVAILABLE CLAIMS (use [CLAIM-ID] after each referenced claim):
{claims_summary}

Revise the document now. Keep 800-1200 words.
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


def generate_document(
    domain: str,
    topic: str,
    claims_db: dict[str, dict[str, Any]],
    existing_text: str | None = None,
) -> str:
    """Step 2: Generate (or revise) T2 document via claude CLI (Max subscription)."""
    claims_summary = build_claims_summary(claims_db)

    if existing_text is not None:
        prompt = REVISION_PROMPT.format(
            domain=domain,
            topic=topic,
            existing_text=existing_text,
            claims_summary=claims_summary,
        )
    else:
        prompt = GENERATION_PROMPT.format(
            domain=domain, topic=topic, claims_summary=claims_summary
        )

    # Pipe prompt via stdin to avoid shell escaping issues with long text
    result = subprocess.run(
        ["claude", "--print", "--dangerously-skip-permissions"],
        input=prompt, capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        logger.error("claude CLI error: %s", result.stderr[:500])
        sys.exit(1)
    return result.stdout.strip()


def validate_markers(document_text: str, claims_db: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Step 3: Check all [CLAIM-ID] markers exist in claims_db. Returns (valid, missing)."""
    found = list(set(CLAIM_ID_PATTERN.findall(document_text)))
    missing = [cid for cid in found if cid not in claims_db]
    valid = [cid for cid in found if cid in claims_db]
    return valid, missing


def run_auto_verifier(document_path: str, claims_db_path: str) -> tuple[int, str]:
    """Step 4: Run auto_verifier.py subprocess. Returns (exit_code, report_path)."""
    fd, report_path = tempfile.mkstemp(suffix="_verification_report.json")
    os.close(fd)
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "auto_verifier.py"),
         "--document", document_path,
         "--claims-db", claims_db_path,
         "--output", report_path],
        capture_output=True, text=True,
    )
    return result.returncode, report_path


def run_telegram_review(document_path: str, report_path: str, document_name: str) -> str:
    """Step 6: Run telegram_reviewer.py subprocess. Returns decision string ('approved'/'rejected')."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "telegram_reviewer.py"),
         "--report", report_path,
         "--document-name", document_name],
        capture_output=False,
    )
    return "approved" if result.returncode == 0 else "rejected"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Verified Generation Pipeline for NB knowledge population")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--existing", default=None, help="Path to existing document to revise (optional)")
    args = parser.parse_args()

    print(f"\nVerified Generation Pipeline — {args.domain} / {args.topic}")  # noqa: T201
    print("=" * 70)  # noqa: T201

    # Step 1
    print("\nStep 1: Loading claims_db...")  # noqa: T201
    claims_db = load_claims_db(args.domain)
    print(f"  {len(claims_db)} claims loaded")  # noqa: T201

    # Step 2
    existing_text: str | None = None
    if args.existing:
        existing_text = Path(args.existing).read_text(encoding="utf-8")
        print("\nStep 2: Revising existing document via claude CLI...")  # noqa: T201
    else:
        print("\nStep 2: Generating document via claude CLI...")  # noqa: T201
    document_text = generate_document(args.domain, args.topic, claims_db, existing_text)
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
    claims_db_path = str(CLAIMS_DB_DIR / f"{args.domain}_claims_db.json")
    exit_code, report_path = run_auto_verifier(str(output_path), claims_db_path)

    if exit_code == 0:
        print("  PASSED — all claims verified")  # noqa: T201
        print(f"\nPipeline COMPLETE — document ready: {output_path}")  # noqa: T201
        print("  Next: upload to NLM using notebooklm-mcp source_add")  # noqa: T201
        sys.exit(0)

    try:
        with open(report_path) as f:
            report = json.load(f)
        ratio = report.get("verified_ratio", 0)
        print(f"  BLOCKED — {ratio:.0%} verified (need >=95%)")  # noqa: T201
        print(f"  Blocked: {report.get('blocked_claims', [])}")  # noqa: T201
    except (OSError, json.JSONDecodeError):
        print("  BLOCKED — could not load verification report")  # noqa: T201

    # Step 5 (optional)
    nlm_url = os.environ.get("NLM_BRIDGE_URL", "")
    if nlm_url:
        print("\nStep 5: NLM cross-check... (not yet automated)")  # noqa: T201
    else:
        print("\nStep 5: Skipping NLM cross-check (NLM_BRIDGE_URL not set)")  # noqa: T201

    # Step 6
    print("\nStep 6: Requesting human review via Telegram...")  # noqa: T201
    decision = run_telegram_review(str(output_path), report_path, f"{args.domain} — {args.topic}")
    if decision == "approved":
        print(f"\nApproved — document ready: {output_path}")  # noqa: T201
        sys.exit(0)
    else:
        print("\nRejected — document NOT uploaded. Fix required.")  # noqa: T201
        print(f"  Review report: {report_path}")  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
