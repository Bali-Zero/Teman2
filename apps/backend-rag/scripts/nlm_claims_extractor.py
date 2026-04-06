#!/usr/bin/env python3
"""NLM Claims Extractor — extract claims from NLM source content directly.

Uses `nlm source content` to get text, then gpt-4o-mini for extraction.
Appends to existing claims_db, deduplicating by verbatim quote.

Usage:
    cd apps/backend-rag
    source venv/bin/activate
    OPENAI_API_KEY=... PYTHONPATH=. python scripts/nlm_claims_extractor.py \
        --notebook 933509f9-1561-403d-bd44-4a7a67a36df2 --domain company
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nlm_claims")

CLAIMS_DB_DIR = Path(__file__).resolve().parents[0] / "claims_db"
CHUNK_SIZE = 7500

DOMAIN_PREFIXES: dict[str, str] = {
    "immigration": "IMM",
    "company": "COM",
    "tax": "TAX",
    "property": "PRO",
    "operations": "OPS",
    "editorial": "EDI",
    "lifestyle": "LIF",
}

REQUIRED_CLAIM_FIELDS = frozenset(
    {"claim", "verbatim", "pasal_ref", "instrument_id", "category"}
)

# Sources to skip (KBLI lampiran, already extracted, non-regulatory)
SKIP_TITLES = {
    "2.10_Lampiran_I.J-I.P_Pariwisata-Kesehatan.pdf",
    "2.7_Lampiran_I.G_Perdagangan.pdf",
}


def parse_claims_response(llm_output: str) -> list[dict[str, Any]]:
    cleaned = re.sub(r"^```(?:json)?\n?", "", llm_output.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, ValueError):
        pass
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, ValueError):
            pass
    return []


def validate_claim(claim: dict[str, Any]) -> bool:
    return all(field in claim and bool(claim[field]) for field in REQUIRED_CLAIM_FIELDS)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            nl = text.rfind("\n", start, end)
            if nl > start + chunk_size // 2:
                end = nl + 1
        chunks.append(text[start:end])
        start = end
    return chunks


def derive_instrument_id(title: str) -> str:
    """Derive instrument ID from source title."""
    # PP_28_2025.pdf -> PP-28-2025
    m = re.match(r"^(UU|PP|PMK|Perpres|Permen\w*|Perka_\w+|POJK|Kepmen\w*)_?(\d+)_(\d{4})", title)
    if m:
        prefix = m.group(1).replace("_", "-")
        return f"{prefix}-{m.group(2)}-{m.group(3)}"
    # "PP Nomor 28 Tahun 2025.pdf"
    m2 = re.match(r"^(UU|PP|PMK|Perpres)\s+(?:No(?:mor)?\.?\s+)?(\d+)\s+(?:Tahun\s+)?(\d{4})", title)
    if m2:
        return f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}"
    return title.replace(".pdf", "").replace(" ", "-")[:30]


def get_source_content(source_id: str) -> str:
    """Get raw source content from NLM."""
    try:
        result = subprocess.run(
            ["nlm", "source", "content", source_id],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        logger.warning("nlm source content failed: %s", result.stderr[:200])
        return ""
    except Exception as e:
        logger.warning("nlm source content error: %s", e)
        return ""


def extract_from_chunk(
    chunk: str,
    instrument_id: str,
    domain: str,
    chunk_idx: int,
    total_chunks: int,
) -> list[dict[str, Any]]:
    """Extract claims via OpenAI gpt-4o-mini."""
    prompt = f"""You are a legal analyst extracting normative claims from Indonesian law.
Source: {instrument_id} (domain: {domain})

Extract EVERY normative claim from the following text. A normative claim is:
- A requirement, prohibition, right, obligation, duration, fee, procedure, or sanction
- Something Bali Zero clients or staff need to know to comply with Indonesian law

For each claim output a JSON object with:
- "claim": Italian translation (1-2 sentences, precise)
- "verbatim": EXACT verbatim quote from source in Bahasa Indonesia (mandatory, max 100 chars)
- "pasal_ref": exact reference e.g. "PP 18/2021 Pasal 5 Ayat 2"
- "instrument_id": "{instrument_id}"
- "category": one of: rule, procedure, duration, fee, document, sanction, right, prohibition

Output ONLY a valid JSON array. No explanation. No markdown. No preamble.

Source text:
---
{chunk}
---"""
    try:
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not set")
            return []
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=8192,
        )
        raw = response.choices[0].message.content or ""
        claims = parse_claims_response(raw)
        logger.info("  Chunk %d/%d → %d claims", chunk_idx, total_chunks, len(claims))
        return claims
    except Exception as e:
        logger.warning("  Chunk %d/%d failed: %s", chunk_idx, total_chunks, e)
        return []


def load_existing_claims_db(domain: str) -> list[dict[str, Any]]:
    path = CLAIMS_DB_DIR / f"{domain}_claims_db.json"
    if path.exists():
        with path.open() as f:
            return json.load(f)
    return []


def save_claims_db(claims: list[dict[str, Any]], domain: str) -> None:
    CLAIMS_DB_DIR.mkdir(parents=True, exist_ok=True)
    path = CLAIMS_DB_DIR / f"{domain}_claims_db.json"
    with path.open("w") as f:
        json.dump(claims, f, ensure_ascii=False, indent=2)
    logger.info("Saved %d claims to %s", len(claims), path)


def get_notebook_pdf_sources(notebook_id: str, already_extracted: set[str]) -> list[dict[str, str]]:
    """Get list of PDF sources from NLM notebook."""
    try:
        result = subprocess.run(
            ["nlm", "notebook", "get", notebook_id],
            capture_output=True,
            text=True,
            timeout=30,
        )
        nb = json.loads(result.stdout)["value"]
        sources = []
        for s in nb["sources"]:
            title = s["title"]
            if (
                title.endswith(".pdf")
                and title not in SKIP_TITLES
                and title not in already_extracted
            ):
                sources.append({"id": s["id"], "title": title})
        return sources
    except Exception as e:
        logger.error("Failed to get notebook: %s", e)
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract claims from NLM sources")
    parser.add_argument("--notebook", required=True, help="NLM notebook ID")
    parser.add_argument("--domain", required=True, choices=list(DOMAIN_PREFIXES))
    parser.add_argument("--skip", nargs="*", default=[], help="Source titles to skip")
    args = parser.parse_args()

    existing = load_existing_claims_db(args.domain)
    existing_verbatim = {c.get("verbatim", "")[:80] for c in existing}
    {c.get("instrument_id", "") for c in existing}

    already_extracted_titles = set(args.skip) | SKIP_TITLES
    sources = get_notebook_pdf_sources(args.notebook, already_extracted_titles)

    logger.info(
        "Domain: %s | Existing: %d claims | PDF sources to process: %d",
        args.domain,
        len(existing),
        len(sources),
    )

    all_new_claims: list[dict[str, Any]] = []

    for src in sources:
        instrument_id = derive_instrument_id(src["title"])

        logger.info("Processing %s (%s)...", src["title"], instrument_id)
        text = get_source_content(src["id"])
        if not text or len(text) < 100:
            logger.warning("  Skipping — no content (%d chars)", len(text))
            continue

        chunks = chunk_text(text)
        logger.info("  %d chars, %d chunks", len(text), len(chunks))

        doc_claims: list[dict[str, Any]] = []
        for i, chunk in enumerate(chunks, 1):
            claims = extract_from_chunk(chunk, instrument_id, args.domain, i, len(chunks))
            doc_claims.extend(claims)
            time.sleep(0.3)

        # Dedup
        new_for_doc = []
        for c in doc_claims:
            if validate_claim(c):
                verbatim = c["verbatim"][:80]
                if verbatim not in existing_verbatim:
                    existing_verbatim.add(verbatim)
                    new_for_doc.append(c)

        logger.info("  → %d unique new claims from %s", len(new_for_doc), instrument_id)
        all_new_claims.extend(new_for_doc)

    if not all_new_claims:
        logger.info("No new claims found")
        return

    # Stamp IDs
    prefix = DOMAIN_PREFIXES.get(args.domain, args.domain[:3].upper())
    start_idx = len(existing) + 1
    for i, claim in enumerate(all_new_claims):
        claim["claim_id"] = f"{prefix}-{start_idx + i:03d}"

    merged = existing + all_new_claims
    save_claims_db(merged, args.domain)
    logger.info(
        "✅ %s: %d new claims, total: %d",
        args.domain,
        len(all_new_claims),
        len(merged),
    )


if __name__ == "__main__":
    main()
