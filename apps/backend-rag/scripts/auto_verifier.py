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
import subprocess
import sys
import time
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
    r"rate.?limit|too many requests|(?<![\d/])429(?![\d/])|exhausted|quota|hit your limit|"
    r"usage limit|weekly limit|timeout after 90s|possibly rate limit|"
    r"capacity|overloaded",
    re.IGNORECASE,
)
_VERIFIER_AUTH_RE = re.compile(
    r"authentication (?:failed|required|expired)|auth required|login required|"
    r"please (?:log in|login)|not logged in|not authenticated|"
    r"invalid[_ ](?:grant|token)|token[_ ]revoked|refresh_token|"
    r"unauthori[sz]ed|(?<![\d/])401(?![\d/])",
    re.IGNORECASE,
)
_VERIFIER_RATE_DIAGNOSTIC_RE = re.compile(
    r"\s*(?:error(?:\s*[:\-]\s*|\s+))?(?:rate.?limit(?:ed| reached| exceeded)?|"
    r"too many requests|(?:http(?: status)?\s*)?429(?:\b.*)?|"
    r"(?:quota|usage limit|weekly limit|capacity)\s+"
    r"(?:exhausted|exceeded|reached|unavailable)(?:\b.*)?|"
    r"(?:you(?:'ve| have)\s+)?hit your limit(?:\b.*)?|"
    r"out of extra usage(?:\b.*)?|service (?:is )?overloaded(?:\b.*)?)\s*",
    re.IGNORECASE | re.DOTALL,
)
_VERIFIER_AUTH_DIAGNOSTIC_RE = re.compile(
    r"\s*(?:error(?:\s*[:\-]\s*|\s+))?(?:401\s+unauthori[sz]ed(?:\b.*)?|"
    r"unauthori[sz]ed(?:\b.*)?|authentication (?:failed|required|expired)(?:\b.*)?|"
    r"auth required(?:\b.*)?|login required(?:\b.*)?|"
    r"please (?:log in|login)(?:\b.*)?|not (?:logged in|authenticated)(?:\b.*)?|"
    r"invalid[_ ](?:grant|token)(?:\b.*)?|token[_ ]revoked(?:\b.*)?|"
    r"refresh_token(?:\b.*)?)\s*",
    re.IGNORECASE | re.DOTALL,
)
_VERIFIER_EXHAUSTED: dict[str, str] = {}
_OAUTH_SCRUB_KEYS = frozenset(
    {
        "GOOGLE_APPLICATION_CREDENTIALS",
        "CLOUD_ML_REGION",
        "GOOGLE_API_KEY",
    }
)
_OAUTH_SCRUB_PREFIXES = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_CODE_USE_",
    "ANTHROPIC_",
    "AWS_",
    "VERTEX_AI_",
    "OPENAI_",
    "OPENROUTER_",
    "GEMINI_",
    "DEEPSEEK_",
    "TOGETHER_",
    "FIREWORKS_",
    "MISTRAL_",
    "COHERE_",
    "GROQ_",
    "XAI_",
    "PERPLEXITY_",
)


def _verifier_oauth_env(token: str) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in _OAUTH_SCRUB_KEYS
        and not key.startswith(_OAUTH_SCRUB_PREFIXES)
    }
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    else:
        env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    return env


def _verifier_token_chain() -> list[tuple[str, str]]:
    chain: list[tuple[str, str]] = []
    seen: set[str] = set()
    for i in (1, 2, 3, 4, 5):
        tok = os.environ.get(f"CLAUDE_CODE_OAUTH_TOKEN_{i}", "").strip()
        if tok and tok not in seen:
            chain.append((f"token_{i}", tok))
            seen.add(tok)
    legacy = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if legacy and legacy not in seen:
        chain.append(("token_legacy", legacy))
    chain.append(("keychain", ""))
    return chain


def _verifier_retry_reason(stdout: str, stderr: str) -> str | None:
    """Classify account-local diagnostics without scanning valid stdout prose."""
    if _VERIFIER_RATE_LIMIT_RE.search(stderr or ""):
        return "rate_limit"
    if _VERIFIER_AUTH_RE.search(stderr or ""):
        return "auth"

    stripped = (stdout or "").strip()
    if not stripped:
        return None
    diagnostic = ""
    try:
        envelope = json.loads(stripped)
    except json.JSONDecodeError:
        envelope = None
    if isinstance(envelope, dict) and (
        envelope.get("is_error")
        or envelope.get("type") == "error"
        or (
            envelope.get("type") == "result"
            and envelope.get("subtype") not in (None, "success")
        )
    ):
        diagnostic = " ".join(
            str(envelope.get(key, ""))
            for key in ("error", "message", "result", "subtype")
        )
        if _VERIFIER_RATE_LIMIT_RE.search(diagnostic):
            return "rate_limit"
        if _VERIFIER_AUTH_RE.search(diagnostic):
            return "auth"
        return None
    if _VERIFIER_RATE_DIAGNOSTIC_RE.fullmatch(stripped):
        return "rate_limit"
    if _VERIFIER_AUTH_DIAGNOSTIC_RE.fullmatch(stripped):
        return "auth"
    return None


def call_claude_verifier(
    claim_id: str, claim_text: str, document_excerpt: str
) -> ClaimVerificationResult:
    """Verify a single claim via claude CLI (Max subscription).
    Multi-account fallback: TOKEN_1→2→3→4→5→legacy→keychain."""
    prompt = build_haiku_verification_prompt(claim_text, document_excerpt)
    deadline = time.monotonic() + 60
    chain = _verifier_token_chain()

    for position, (label, token) in enumerate(chain):
        if label in _VERIFIER_EXHAUSTED:
            continue

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        attempt_timeout = max(0.1, remaining / (len(chain) - position))
        env = _verifier_oauth_env(token)

        try:
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions",
                 "--max-budget-usd", "1"],
                input=prompt, capture_output=True, text=True,
                timeout=attempt_timeout, env=env,
            )
        except subprocess.TimeoutExpired:
            _VERIFIER_EXHAUSTED[label] = "timeout"
            continue

        retry_reason = _verifier_retry_reason(result.stdout, result.stderr)
        if retry_reason is not None:
            _VERIFIER_EXHAUSTED[label] = retry_reason
            continue
        if result.returncode != 0:
            return ClaimVerificationResult(
                claim_id=claim_id,
                verdict="UNCERTAIN",
                reason=f"Claude CLI failed via {label}",
            )

        text = result.stdout.strip()
        if not text:
            _VERIFIER_EXHAUSTED[label] = "empty_output"
            continue
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
    print(f"\n{'OK' if report.passed else 'FAIL'} {status} — Verified {report.verified_count}/{report.total_claims} ({report.verified_ratio:.1%})")
    if not report.passed:
        print(f"Blocked: {report.blocked_claims}")
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
