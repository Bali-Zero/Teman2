#!/usr/bin/env python3
"""Auto-Verifier — Step 4 of the Verified Generation Pipeline.

Verifies every [CLAIM-ID] marker in a generated T2 document against
claims_db.json using CRAG-light (Claude Haiku 4.5 as evaluator).

Exit codes:
  0 — verification passed (>=95% claims verified)
  1 — verification failed (<95% or DB errors)

Usage:
    python scripts/auto_verifier.py \\
        --document /tmp/nb2_visa_guide.txt \\
        --claims-db scripts/claims_db/immigration_claims_db.json \\
        --output /tmp/verification_report.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CLAIM_ID_PATTERN = re.compile(r"\[([A-Z]{2,3}-\d{3})\]")
MIN_VERIFIED_RATIO = 0.95


@dataclass
class ClaimVerificationResult:
    claim_id: str
    found_in_db: bool
    haiku_verdict: str | None = None   # "FAITHFUL", "UNFAITHFUL", "UNCERTAIN"
    haiku_reason: str | None = None
    passed: bool = False


@dataclass
class VerificationReport:
    document_path: str
    claims_db_path: str
    total_markers: int = 0
    unique_claim_ids: int = 0
    found_in_db: int = 0
    verified: int = 0
    failed: list[ClaimVerificationResult] = field(default_factory=list)
    verified_ratio: float = 0.0
    passed: bool = False


def extract_claim_ids(document_text: str) -> list[str]:
    """Extract unique [CLAIM-ID] markers from document, in order of first appearance."""
    seen: set[str] = set()
    unique: list[str] = []
    for cid in CLAIM_ID_PATTERN.findall(document_text):
        if cid not in seen:
            seen.add(cid)
            unique.append(cid)
    return unique


def load_claims_db(claims_db_path: Path) -> dict[str, dict[str, Any]]:
    """Load claims_db.json into a dict keyed by claim_id."""
    with claims_db_path.open() as f:
        raw: list[dict[str, Any]] = json.load(f)
    return {c["claim_id"]: c for c in raw if "claim_id" in c}


def build_haiku_verification_prompt(claim: str, verbatim: str, pasal_ref: str) -> str:
    return f"""You are a legal accuracy evaluator. Determine if the following claim faithfully and accurately represents the verbatim source text.

CLAIM (Italian): {claim}
VERBATIM SOURCE (Bahasa Indonesia): {verbatim}
PASAL REFERENCE: {pasal_ref}

Answer with exactly one of: FAITHFUL, UNFAITHFUL, or UNCERTAIN.
Then on a new line explain in one sentence why.

Format your response as:
VERDICT: <FAITHFUL|UNFAITHFUL|UNCERTAIN>
REASON: <one sentence>"""


def call_haiku_verifier(
    claim_text: str, verbatim: str, pasal_ref: str, api_key: str
) -> tuple[str, str]:
    """Call Claude Haiku 4.5 to verify a single claim. Returns (verdict, reason)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": build_haiku_verification_prompt(claim_text, verbatim, pasal_ref)}],
    )
    text = response.content[0].text.strip()
    verdict, reason = "UNCERTAIN", text
    for line in text.split("\n"):
        if line.startswith("VERDICT:"):
            verdict = line.split(":", 1)[1].strip()
        elif line.startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()
    return verdict, reason


def verify_document(
    document_text: str,
    claims_db: dict[str, dict[str, Any]],
    document_path: str,
    claims_db_path: str,
    api_key: str,
) -> VerificationReport:
    """Run full CRAG-light verification on a document."""
    report = VerificationReport(document_path=document_path, claims_db_path=claims_db_path)
    claim_ids = extract_claim_ids(document_text)
    report.total_markers = len(CLAIM_ID_PATTERN.findall(document_text))
    report.unique_claim_ids = len(claim_ids)

    for cid in claim_ids:
        result = ClaimVerificationResult(claim_id=cid, found_in_db=cid in claims_db)
        if not result.found_in_db:
            report.failed.append(result)
            logger.warning("Claim %s not found in claims_db", cid)
            continue

        report.found_in_db += 1
        cd = claims_db[cid]
        verdict, reason = call_haiku_verifier(cd["claim"], cd["verbatim"], cd["pasal_ref"], api_key)
        result.haiku_verdict = verdict
        result.haiku_reason = reason
        result.passed = verdict == "FAITHFUL"

        if result.passed:
            report.verified += 1
        else:
            report.failed.append(result)
            logger.warning("Claim %s: %s — %s", cid, verdict, reason)

    total = report.unique_claim_ids
    report.verified_ratio = report.verified / total if total > 0 else 0.0
    report.passed = report.verified_ratio >= MIN_VERIFIED_RATIO
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", required=True)
    parser.add_argument("--claims-db", required=True)
    parser.add_argument("--output", default="/tmp/verification_report.json")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    document_text = Path(args.document).read_text(encoding="utf-8")
    claims_db = load_claims_db(Path(args.claims_db))
    report = verify_document(document_text, claims_db, args.document, args.claims_db, api_key)

    with open(args.output, "w") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)

    status = "PASSED" if report.passed else "BLOCKED"
    print(f"\n{'OK' if report.passed else 'FAIL'} {status} — Verified {report.verified}/{report.unique_claim_ids} ({report.verified_ratio:.1%})")  # noqa: T201
    if not report.passed:
        print(f"Failed: {[r.claim_id for r in report.failed]}")  # noqa: T201
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
