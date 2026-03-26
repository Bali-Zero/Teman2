#!/usr/bin/env python3
"""Verified Generator — Multi-Model Orchestrator for NB Knowledge Population.

7-step pipeline ("verifica sempre la verità con la legge"):
  1. Load claims_db for domain
  2. NLM Deep Research (Gemini) — trova normative aggiornate sul web
  3. Gemini CLI search — verifica vigenza delle leggi (Google Search grounded)
  4. NLM Oracolo (notebook di dominio) — citazioni precise dai PDF legali caricati
  5. DeepSeek R1 — ragionamento su coerenza legale e contraddizioni
  6. Claude CLI — assembla documento T2 con [CLAIM-ID] markers (Max subscription)
  7. auto_verifier — CRAG-light: verifica fedeltà ≥95% di ogni citazione

Each model contributes its strength:
  - NLM Deep Research: 40+ web sources, autonomous Gemini research
  - Gemini Search: Google Search grounded, verifies current law status
  - NLM Oracolo: citations directly from uploaded legal PDFs
  - DeepSeek R1: chain-of-thought for legal reasoning & contradiction detection
  - Claude CLI: final T2 assembly with [CLAIM-ID] markers
  - auto_verifier: CRAG-light faithfulness check on every cited claim

Usage:
    python scripts/verified_generator.py \\
        --domain immigration \\
        --topic "KITAS E31 Rinnovo: Procedura Completa" \\
        --output /tmp/nb2_kitas_renewal.txt

    # Skip slow steps for quick iteration:
    python scripts/verified_generator.py \\
        --domain property \\
        --topic "HGB: Diritto di Costruzione per Stranieri" \\
        --output /tmp/nb5_hgb.txt \\
        --skip-research --skip-reasoning
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
PROJECT_ROOT = SCRIPTS_DIR.parents[2]
CLAIMS_DB_DIR = SCRIPTS_DIR / "claims_db"
AI_DISPATCH = PROJECT_ROOT / "scripts" / "ai-dispatch.sh"
CLAIM_ID_PATTERN = re.compile(r"\[([A-Z]{2,3}-\d{3})\]")

# NLM notebook IDs per dominio (da ai-dispatch.sh oracolo-nb mapping)
DOMAIN_NB_TAGS: dict[str, str] = {
    "immigration": "immigration",
    "property": "property",
    "tax": "tax",
    "company": "company",
}

GENERATION_PROMPT = """You are a Bali Zero knowledge author writing operational guides for staff.

Domain: {domain}
Topic: {topic}
Language: Italian (professional, precise)

RESEARCH CONTEXT (from multi-model analysis):
{research_context}

LEGAL GROUNDING (from NLM notebooks — PDF citations):
{oracolo_context}

LEGAL REASONING (DeepSeek R1 chain-of-thought):
{reasoning_context}

CRITICAL RULES:
1. Every normative claim MUST be followed by its [CLAIM-ID] marker from claims_db
2. Only make claims that exist in the claims_db listed below
3. If you need to state something not in claims_db, write [NEEDS-VERIFICATION] instead
4. Structure: Introduction → Requirements → Procedure → Timing → Costs → FAQ
5. Ground every claim in actual Indonesian law — "verifica sempre la verità con la legge"

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

RESEARCH CONTEXT (from multi-model analysis):
{research_context}

LEGAL GROUNDING (from NLM notebooks — PDF citations):
{oracolo_context}

CRITICAL RULES:
1. Every normative claim MUST be followed by its [CLAIM-ID] marker from claims_db
2. Only make claims that exist in the claims_db listed below
3. Replace any [NEEDS-VERIFICATION] markers or unsupported claims with verified [CLAIM-ID] markers
4. Preserve the document structure where correct; fix only what is wrong
5. Ground every claim in actual Indonesian law — "verifica sempre la verità con la legge"

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


def run_dispatch(command: str, *args: str, timeout: int = 300) -> str:
    """Run ai-dispatch.sh command and return stdout. Empty string on failure."""
    if not AI_DISPATCH.exists():
        logger.warning("ai-dispatch.sh not found at %s", AI_DISPATCH)
        return ""
    cmd = [str(AI_DISPATCH), command] + list(args)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            logger.warning("ai-dispatch %s failed (rc=%d): %s", command, result.returncode, result.stderr[:200])
            return ""
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning("ai-dispatch %s timed out after %ds", command, timeout)
        return ""
    except Exception as e:
        logger.warning("ai-dispatch %s error: %s", command, e)
        return ""


def step_nlm_research(domain: str, topic: str, skip: bool) -> str:
    """Step 2: NLM Deep Research — Gemini autonomous web research (~40 sources)."""
    if skip:
        logger.info("  [SKIP] NLM Deep Research")
        return ""
    print("\nStep 2: NLM Deep Research (Gemini) — searching web sources...")  # noqa: T201
    query = f"Indonesian law {domain}: {topic} — current regulations, requirements, procedures 2024-2025"
    output = run_dispatch("research", query, "fast", timeout=120)
    if output:
        # research start is async — extract any immediate context from the response
        print(f"  Research initiated: {output[:200]}...")  # noqa: T201
        # Return the initiation confirmation as context (actual results in NB-9)
        return f"[NLM Deep Research initiated for: {query}]\n{output[:500]}"
    print("  Research unavailable — proceeding without web research")  # noqa: T201
    return ""


def step_gemini_search(domain: str, topic: str, skip: bool) -> str:
    """Step 3: Gemini CLI search — Google Search grounded law verification."""
    if skip:
        logger.info("  [SKIP] Gemini search")
        return ""
    print("\nStep 3: Gemini CLI search — verifying current law status...")  # noqa: T201
    query = (
        f"Indonesian {domain} law: {topic}. "
        f"What are the current legal requirements, procedures, timeframes, and fees? "
        f"Cite specific regulations (UU, PP, Peraturan Menteri) with article numbers."
    )
    output = run_dispatch("search", query, timeout=120)
    if output:
        print(f"  Gemini search: {len(output)} chars of grounded context")  # noqa: T201
        return output
    print("  Gemini search unavailable — proceeding without")  # noqa: T201
    return ""


def step_nlm_oracolo(domain: str, topic: str, skip: bool) -> str:
    """Step 4: NLM Oracolo — citations from domain-specific legal PDF notebook."""
    if skip:
        logger.info("  [SKIP] NLM Oracolo")
        return ""
    nb_tag = DOMAIN_NB_TAGS.get(domain, domain)
    print(f"\nStep 4: NLM Oracolo (NB: {nb_tag}) — querying legal PDF citations...")  # noqa: T201
    question = (
        f"What are the specific legal requirements, procedures, timeframes, and fees for: {topic}? "
        f"Provide exact citations with Pasal numbers."
    )
    output = run_dispatch("oracolo-nb", nb_tag, question, timeout=120)
    if output:
        print(f"  Oracolo: {len(output)} chars of cited legal context")  # noqa: T201
        return output
    print("  Oracolo unavailable — proceeding without PDF citations")  # noqa: T201
    return ""


def step_deepseek_reasoning(
    domain: str,
    topic: str,
    claims_db: dict[str, dict[str, Any]],
    search_context: str,
    oracolo_context: str,
    skip: bool,
) -> str:
    """Step 5: DeepSeek R1 671b — chain-of-thought legal reasoning."""
    if skip:
        logger.info("  [SKIP] DeepSeek R1 reasoning")
        return ""
    print("\nStep 5: DeepSeek R1 671b — legal reasoning & contradiction detection...")  # noqa: T201

    # Build a focused reasoning prompt
    claims_sample = "\n".join(
        f"[{cid}] {c['claim']}" for cid, c in list(claims_db.items())[:30]
    )
    reasoning_prompt = (
        f"Domain: Indonesian {domain} law. Topic: {topic}\n\n"
        f"I have {len(claims_db)} normative claims extracted from official Indonesian legal texts.\n"
        f"Sample claims:\n{claims_sample}\n\n"
        f"Search context summary:\n{search_context[:1000] if search_context else 'Not available'}\n\n"
        f"Legal citations from official PDFs:\n{oracolo_context[:1000] if oracolo_context else 'Not available'}\n\n"
        f"Task: Analyze these claims and context. Identify:\n"
        f"1. Any contradictions between claims or with search results\n"
        f"2. Which claims are most legally critical for a client guide\n"
        f"3. Any gaps — important legal facts not covered by the claims_db\n"
        f"4. Recommended structure for an operational guide on: {topic}\n"
        f"Be precise and legally grounded. Reference specific Indonesian regulations."
    )
    output = run_dispatch("reasoning", reasoning_prompt, timeout=180)
    if output:
        print(f"  DeepSeek R1: {len(output)} chars of legal reasoning")  # noqa: T201
        return output
    print("  DeepSeek R1 unavailable — proceeding without reasoning layer")  # noqa: T201
    return ""


def generate_document(
    domain: str,
    topic: str,
    claims_db: dict[str, dict[str, Any]],
    research_context: str,
    oracolo_context: str,
    reasoning_context: str,
    existing_text: str | None = None,
) -> str:
    """Step 6: Generate T2 document via claude CLI (Max subscription)."""
    claims_summary = build_claims_summary(claims_db)

    # Truncate contexts to avoid hitting token limits
    research_ctx = (research_context[:2000] if research_context else "Not available — proceed from claims_db only")
    oracolo_ctx = (oracolo_context[:3000] if oracolo_context else "Not available — proceed from claims_db only")
    reasoning_ctx = (reasoning_context[:2000] if reasoning_context else "Not available")

    if existing_text is not None:
        prompt = REVISION_PROMPT.format(
            domain=domain,
            topic=topic,
            existing_text=existing_text,
            research_context=research_ctx,
            oracolo_context=oracolo_ctx,
            claims_summary=claims_summary,
        )
    else:
        prompt = GENERATION_PROMPT.format(
            domain=domain,
            topic=topic,
            research_context=research_ctx,
            oracolo_context=oracolo_ctx,
            reasoning_context=reasoning_ctx,
            claims_summary=claims_summary,
        )

    result = subprocess.run(
        ["claude", "--print", "--dangerously-skip-permissions"],
        input=prompt, capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        logger.error("claude CLI error: %s", result.stderr[:500])
        sys.exit(1)
    return result.stdout.strip()


def validate_markers(document_text: str, claims_db: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Step 6b: Check all [CLAIM-ID] markers exist in claims_db. Returns (valid, missing)."""
    found = list(set(CLAIM_ID_PATTERN.findall(document_text)))
    missing = [cid for cid in found if cid not in claims_db]
    valid = [cid for cid in found if cid in claims_db]
    return valid, missing


def run_auto_verifier(document_path: str, claims_db_path: str) -> tuple[int, str]:
    """Step 7: Run auto_verifier.py subprocess. Returns (exit_code, report_path)."""
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
    """Optional: Run telegram_reviewer.py subprocess. Returns decision string."""
    reviewer = SCRIPTS_DIR / "telegram_reviewer.py"
    if not reviewer.exists():
        logger.info("telegram_reviewer.py not found — skipping human review")
        return "skipped"
    result = subprocess.run(
        [sys.executable, str(reviewer),
         "--report", report_path,
         "--document-name", document_name],
        capture_output=False,
    )
    return "approved" if result.returncode == 0 else "rejected"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Multi-model Verified Generation Pipeline for NB knowledge population")
    parser.add_argument("--domain", required=True, choices=["immigration", "property", "tax", "company"])
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--existing", default=None, help="Path to existing document to revise (optional)")
    parser.add_argument("--skip-research", action="store_true", help="Skip NLM Deep Research (faster)")
    parser.add_argument("--skip-search", action="store_true", help="Skip Gemini search (faster)")
    parser.add_argument("--skip-oracolo", action="store_true", help="Skip NLM Oracolo (faster)")
    parser.add_argument("--skip-reasoning", action="store_true", help="Skip DeepSeek R1 reasoning (faster)")
    parser.add_argument("--skip-telegram", action="store_true", help="Skip Telegram human review")
    args = parser.parse_args()

    print(f"\nVerified Generation Pipeline — {args.domain} / {args.topic}")  # noqa: T201
    print("=" * 70)  # noqa: T201
    print("Models: NLM Deep Research → Gemini Search → NLM Oracolo → DeepSeek R1 → Claude → CRAG")  # noqa: T201

    # Step 1: Load claims_db
    print("\nStep 1: Loading claims_db...")  # noqa: T201
    claims_db = load_claims_db(args.domain)
    print(f"  {len(claims_db)} claims loaded")  # noqa: T201

    # Step 2: NLM Deep Research (Gemini autonomous web search)
    research_context = step_nlm_research(args.domain, args.topic, args.skip_research)

    # Step 3: Gemini CLI search (Google Search grounded)
    search_context = step_gemini_search(args.domain, args.topic, args.skip_search)

    # Step 4: NLM Oracolo (domain legal PDF citations)
    oracolo_context = step_nlm_oracolo(args.domain, args.topic, args.skip_oracolo)

    # Step 5: DeepSeek R1 reasoning (legal coherence & contradiction detection)
    reasoning_context = step_deepseek_reasoning(
        args.domain, args.topic, claims_db,
        search_context, oracolo_context,
        args.skip_reasoning,
    )

    # Step 6: Claude CLI assembles T2 document with all context
    existing_text: str | None = None
    if args.existing:
        existing_text = Path(args.existing).read_text(encoding="utf-8")
        print("\nStep 6: Revising existing document via Claude CLI (Max)...")  # noqa: T201
    else:
        print("\nStep 6: Generating document via Claude CLI (Max)...")  # noqa: T201

    document_text = generate_document(
        args.domain, args.topic, claims_db,
        research_context or search_context,  # prefer research, fallback to search
        oracolo_context,
        reasoning_context,
        existing_text,
    )
    output_path = Path(args.output)
    output_path.write_text(document_text, encoding="utf-8")
    print(f"  Generated {len(document_text)} chars → {output_path}")  # noqa: T201

    # Step 6b: Validate [CLAIM-ID] markers
    print("\nStep 6b: Validating [CLAIM-ID] markers...")  # noqa: T201
    valid_ids, missing_ids = validate_markers(document_text, claims_db)
    print(f"  Valid: {len(valid_ids)}, Missing from DB: {len(missing_ids)}")  # noqa: T201
    if missing_ids:
        print(f"  WARNING: Unknown claim IDs will be flagged UNFAITHFUL: {missing_ids}")  # noqa: T201

    # Step 7: CRAG-light auto-verification
    print("\nStep 7: Running auto-verifier (CRAG-light)...")  # noqa: T201
    claims_db_path = str(CLAIMS_DB_DIR / f"{args.domain}_claims_db.json")
    exit_code, report_path = run_auto_verifier(str(output_path), claims_db_path)

    if exit_code == 0:
        print("  PASSED — all claims verified ≥95%")  # noqa: T201
        print(f"\nPipeline COMPLETE — document ready: {output_path}")  # noqa: T201
        print("  Next: upload to NLM using: nlm source_add --notebook-id <NB_ID> --source-type text")  # noqa: T201
        sys.exit(0)

    # Verification failed — load report
    try:
        with open(report_path) as f:
            report = json.load(f)
        ratio = report.get("verified_ratio", 0)
        print(f"  BLOCKED — {ratio:.0%} verified (need ≥95%)")  # noqa: T201
        print(f"  Blocked claims: {report.get('blocked_claims', [])}")  # noqa: T201
    except (OSError, json.JSONDecodeError):
        print("  BLOCKED — could not load verification report")  # noqa: T201

    # Optional: Telegram human review
    if not args.skip_telegram:
        print("\nStep 7b: Requesting human review via Telegram...")  # noqa: T201
        decision = run_telegram_review(str(output_path), report_path, f"{args.domain} — {args.topic}")
        if decision == "approved":
            print(f"\nApproved — document ready: {output_path}")  # noqa: T201
            sys.exit(0)
        elif decision == "skipped":
            print(f"\nVerification failed — review report: {report_path}")  # noqa: T201
            sys.exit(1)
        else:
            print("\nRejected — document NOT uploaded. Fix required.")  # noqa: T201
            print(f"  Review report: {report_path}")  # noqa: T201
            sys.exit(1)
    else:
        print(f"\nVerification failed — review report: {report_path}")  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
