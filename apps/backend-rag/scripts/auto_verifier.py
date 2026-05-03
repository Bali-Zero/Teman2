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
import re
import os
import subprocess
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
    verdict: str        # "FAITHFUL" | "UNFAITHFUL" | "UNCERTAIN"
    reason: str


@dataclass
class VerificationReport:
    total_claims: int
    verified_count: int                                                     # count of FAITHFUL verdicts
    verified_ratio: float
    passed: bool                                                            # ratio >= MIN_VERIFIED_RATIO
    results: list[ClaimVerificationResult] = field(default_factory=list)   # ALL results
    blocked_claims: list[str] = field(default_factory=list)                # IDs with UNFAITHFUL/UNCERTAIN


def extract_claim_ids(document_text: str) -> list[str]:
    """Extract unique [CLAIM-ID] markers from document, in order of first appearance."""
    seen: set[str] = set()
    unique: list[str] = []
    for cid in CLAIM_ID_PATTERN.findall(document_text):
        if cid not in seen:
            seen.add(cid)
            unique.append(cid)
    return unique


def load_claims_db(path: str) -> dict[str, dict[str, Any]]:
    """Load claims_db.json into a dict keyed by claim_id."""
    with open(path) as f:
        raw: list[dict[str, Any]] = json.load(f)
    return {c["claim_id"]: c for c in raw if "claim_id" in c}


def build_haiku_verification_prompt(claim: str, document_excerpt: str) -> str:
    return f"""You are a legal accuracy evaluator. Determine if the following claim faithfully and accurately represents the source document excerpt.

CLAIM (Italian): {claim}
DOCUMENT EXCERPT (source text): {document_excerpt}

Answer with exactly one of: FAITHFUL, UNFAITHFUL, or UNCERTAIN.
Then on a new line explain in one sentence why.

Format your response as:
VERDICT: <FAITHFUL|UNFAITHFUL|UNCERTAIN>
REASON: <one sentence>"""


_VERIFIER_RATE_LIMIT_RE = re.compile(
    r"rate.?limit|too many requests|429|exhausted|quota|hit your limit|"
    r"timeout after 90s|possibly rate limit|capacity|overloaded",
    re.IGNORECASE,
)
_VERIFIER_EXHAUSTED: dict[str, str] = {}


def _verifier_token_chain() -> list[tuple[str, str]]:
    chain: list[tuple[str, str]] = []
    for i in (1, 2, 3):
        tok = os.environ.get(f"CLAUDE_CODE_OAUTH_TOKEN_{i}", "").strip()
        if tok:
            chain.append((f"token_{i}", tok))
    legacy = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if legacy and not any(t == legacy for _, t in chain):
        chain.append(("token_legacy", legacy))
    chain.append(("keychain", ""))
    return chain


def call_claude_verifier(
    claim_id: str, claim_text: str, document_excerpt: str
) -> ClaimVerificationResult:
    """Verify a single claim via claude CLI (Max subscription).
    Multi-account fallback: TOKEN_1→2→3→legacy→keychain."""
    prompt = build_haiku_verification_prompt(claim_text, document_excerpt)

    for label, token in _verifier_token_chain():
        if label in _VERIFIER_EXHAUSTED:
            continue

        env = os.environ.copy()
        if token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        else:
            env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)

        try:
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions"],
                input=prompt, capture_output=True, text=True, timeout=60, env=env,
            )
        except subprocess.TimeoutExpired:
            _VERIFIER_EXHAUSTED[label] = "timeout"
            continue

        combined = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0 and _VERIFIER_RATE_LIMIT_RE.search(combined):
            _VERIFIER_EXHAUSTED[label] = "rate_limit"
            continue

        text = result.stdout.strip() if result.returncode == 0 else ""
        verdict, reason = "UNCERTAIN", text
        for line in text.split("\n"):
            if line.startswith("VERDICT:"):
                verdict = line.split(":", 1)[1].strip()
            elif line.startswith("REASON:"):
                reason = line.split(":", 1)[1].strip()
        return ClaimVerificationResult(claim_id=claim_id, verdict=verdict, reason=reason)

    # All tokens exhausted
    return ClaimVerificationResult(
        claim_id=claim_id, verdict="UNCERTAIN", reason="All Claude tokens exhausted"
    )


def verify_document(document_text: str, claims_db_path: str) -> VerificationReport:
    """Run full CRAG-light verification on a document."""
    claims_db = load_claims_db(claims_db_path)
    claim_ids = extract_claim_ids(document_text)
    total_claims = len(claim_ids)

    all_results: list[ClaimVerificationResult] = []
    verified_count = 0

    for cid in claim_ids:
        if cid not in claims_db:
            logger.warning("Claim %s not found in claims_db", cid)
            result = ClaimVerificationResult(
                claim_id=cid,
                verdict="UNFAITHFUL",
                reason="Claim ID not found in claims_db",
            )
        else:
            cd = claims_db[cid]
            document_excerpt = f"{cd.get('verbatim', '')} ({cd.get('pasal_ref', '')})"
            result = call_claude_verifier(cid, cd["claim"], document_excerpt)
            if result.verdict == "FAITHFUL":
                verified_count += 1
            else:
                logger.warning("Claim %s: %s — %s", cid, result.verdict, result.reason)

        all_results.append(result)

    verified_ratio = verified_count / total_claims if total_claims > 0 else 0.0
    passed = verified_ratio >= MIN_VERIFIED_RATIO
    blocked_claims = [r.claim_id for r in all_results if r.verdict != "FAITHFUL"]

    return VerificationReport(
        total_claims=total_claims,
        verified_count=verified_count,
        verified_ratio=verified_ratio,
        passed=passed,
        results=all_results,
        blocked_claims=blocked_claims,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", required=True)
    parser.add_argument("--claims-db", required=True)
    parser.add_argument("--output", default="/tmp/verification_report.json")
    args = parser.parse_args()

    document_text = Path(args.document).read_text(encoding="utf-8")
    report = verify_document(document_text, args.claims_db)

    with open(args.output, "w") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)

    status = "PASSED" if report.passed else "BLOCKED"
    print(f"\n{'OK' if report.passed else 'FAIL'} {status} — Verified {report.verified_count}/{report.total_claims} ({report.verified_ratio:.1%})")  # noqa: T201
    if not report.passed:
        print(f"Blocked: {report.blocked_claims}")  # noqa: T201
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
