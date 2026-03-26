#!/usr/bin/env python3
"""Claims Extractor — Step 1 of the Verified Generation Pipeline.

Reads T0/T1 source documents and uses Claude Haiku 4.5 to extract every
normative claim as a structured record with verbatim citation. Writes
output to scripts/claims_db/<domain>_claims_db.json.

Usage:
    python scripts/claims_extractor.py \\
        --domain immigration \\
        --source /path/to/law.txt \\
        --instrument-id UU-6-2011
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DOMAIN_PREFIXES: dict[str, str] = {
    "immigration": "IMM",
    "company": "COM",
    "tax": "TAX",
    "property": "PRO",
    "operations": "OPS",
    "editorial": "EDI",
    "lifestyle": "LIF",
}

REQUIRED_CLAIM_FIELDS = frozenset({"claim", "verbatim", "pasal_ref", "instrument_id", "category"})


def generate_claim_id(domain: str, index: int) -> str:
    """Generate a domain-prefixed zero-padded claim ID (e.g. IMM-001)."""
    prefix = DOMAIN_PREFIXES.get(domain, domain[:3].upper())
    return f"{prefix}-{index:03d}"


def parse_claims_response(llm_output: str) -> list[dict[str, Any]]:
    """Parse LLM JSON response into a list of claim dicts.

    Strips markdown code fences if present. Returns empty list on any parse failure.
    """
    cleaned = re.sub(r"^```(?:json)?\n?", "", llm_output.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse LLM output as JSON (length=%d)", len(llm_output))
        return []


def validate_claim(claim: dict[str, Any]) -> bool:
    """Check that a claim has all required fields with non-empty values."""
    return all(field in claim and bool(claim[field]) for field in REQUIRED_CLAIM_FIELDS)


def stamp_claims(claims: list[dict[str, Any]], domain: str, start_index: int = 1) -> list[dict[str, Any]]:
    """Add claim_id to each valid claim, filtering out invalid ones."""
    stamped: list[dict[str, Any]] = []
    idx = start_index
    for claim in claims:
        if validate_claim(claim):
            claim["claim_id"] = generate_claim_id(domain, idx)
            stamped.append(claim)
            idx += 1
        else:
            logger.warning("Skipping invalid claim (missing fields): %s", list(claim.keys()))
    return stamped


def load_existing_claims_db(output_path: Path) -> list[dict[str, Any]]:
    """Load existing claims_db JSON or return empty list."""
    if output_path.exists():
        with output_path.open() as f:
            return json.load(f)
    return []


def save_claims_db(claims: list[dict[str, Any]], output_path: Path) -> None:
    """Write claims list to JSON with pretty formatting."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(claims, f, ensure_ascii=False, indent=2)
    logger.info("Saved %d claims to %s", len(claims), output_path)


def build_extraction_prompt(source_text: str, instrument_id: str, domain: str) -> str:
    """Build the prompt for Claude Haiku claims extraction."""
    return f"""You are a legal analyst extracting normative claims from Indonesian law.
Source: {instrument_id} (domain: {domain})

Extract EVERY normative claim from the following text. A normative claim is:
- A requirement, prohibition, right, obligation, duration, fee, procedure, or sanction
- Something Bali Zero clients or staff need to know to comply with Indonesian law

For each claim output a JSON object with:
- "claim": Italian translation (1-2 sentences, precise)
- "verbatim": EXACT verbatim quote from source in Bahasa Indonesia (mandatory)
- "pasal_ref": exact reference e.g. "UU 6/2011 Pasal 71 Ayat 1"
- "instrument_id": "{instrument_id}"
- "category": one of: rule, procedure, duration, fee, document, sanction, right, prohibition

Output ONLY a valid JSON array. No explanation. No markdown. No preamble.

Source text:
---
{source_text[:8000]}
---"""


async def extract_claims_from_file(
    source_path: Path,
    instrument_id: str,
    domain: str,
    anthropic_api_key: str,
) -> list[dict[str, Any]]:
    """Extract claims from a source file using Claude Haiku 4.5."""
    import anthropic

    source_text = source_path.read_text(encoding="utf-8")
    prompt = build_extraction_prompt(source_text, instrument_id, domain)

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text
    claims = parse_claims_response(raw)
    logger.info("Extracted %d raw claims from %s", len(claims), instrument_id)
    return claims


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Extract normative claims from T0/T1 law sources")
    parser.add_argument("--domain", required=True, choices=list(DOMAIN_PREFIXES))
    parser.add_argument("--source", required=True, help="Path to source text file")
    parser.add_argument("--instrument-id", required=True, help="e.g. UU-6-2011")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    import asyncio
    source_path = Path(args.source)
    output_path = Path(__file__).parent / "claims_db" / f"{args.domain}_claims_db.json"
    existing = load_existing_claims_db(output_path)
    start_idx = len(existing) + 1

    new_claims = asyncio.run(
        extract_claims_from_file(source_path, args.instrument_id, args.domain, api_key)
    )
    stamped = stamp_claims(new_claims, args.domain, start_idx)
    all_claims = existing + stamped
    save_claims_db(all_claims, output_path)
    print(f"Added {len(stamped)} new claims. Total: {len(all_claims)}")  # noqa: T201


if __name__ == "__main__":
    main()
