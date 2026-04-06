#!/usr/bin/env python3
"""Batch Claims Extractor — Tier 1 Gap Laws → claims_db.

Extracts normative claims from all Tier 1 PDF laws using Claude Haiku 4.5.
Processes PDFs in chunks (8000 chars each) to cover the full document.
Appends new claims to existing claims_db, deduplicating by verbatim quote.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python scripts/batch_claims_extractor.py --domain property
    PYTHONPATH=. python scripts/batch_claims_extractor.py --domain immigration
    PYTHONPATH=. python scripts/batch_claims_extractor.py --domain tax
    PYTHONPATH=. python scripts/batch_claims_extractor.py --all
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

BACKEND_PATH = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_PATH.parents[1]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("batch_claims")

SOURCE_DIR = PROJECT_ROOT / "data/kb_sources/tier1_gaps"
CLAIMS_DB_DIR = BACKEND_PATH / "scripts/claims_db"
CHUNK_SIZE = 7500  # chars per extraction call — under 8192-token limit

DOMAIN_PREFIXES: dict[str, str] = {
    "immigration": "IMM",
    "company": "COM",
    "tax": "TAX",
    "property": "PRO",
}

# Tier 1 PDFs grouped by domain with their instrument IDs
TIER1_BY_DOMAIN: dict[str, list[dict[str, str]]] = {
    "property": [
        {"filename": "PP_18_2021_HakPakai_HGB.pdf", "instrument_id": "PP-18-2021"},
        {"filename": "PP_103_2015_Properti_Asing.pdf", "instrument_id": "PP-103-2015"},
        {"filename": "PermenATR_BPN_18_2021_Pendaftaran.pdf", "instrument_id": "PermenATR-18-2021"},
        {"filename": "UU_5_1960_Agraria.pdf", "instrument_id": "UU-5-1960"},
        {"filename": "PP_18_2021_HakPengelolaan.pdf", "instrument_id": "PP-18-2021-HakPengelolaan"},
        {"filename": "PP_103_2015_PropertiAsing.pdf", "instrument_id": "PP-103-2015-JDIH"},
    ],
    "immigration": [
        {"filename": "PP_31_2013_Imigrasi.pdf", "instrument_id": "PP-31-2013"},
        {"filename": "Permenkumham_27_2021_Visa.pdf", "instrument_id": "Permenkumham-27-2021"},
        {"filename": "Permenkumham_29_2021_KITAS.pdf", "instrument_id": "Permenkumham-29-2021"},
        {"filename": "Permenkumham_11_2024_Visa_IzinTinggal.pdf", "instrument_id": "Permenkumham-11-2024"},
        {"filename": "UU_6_2011_Keimigrasian.pdf", "instrument_id": "UU-6-2011"},
    ],
    "company": [
        {"filename": "UU_40_2007_PT_Perseroan.pdf", "instrument_id": "UU-40-2007"},
        {"filename": "UU_25_2007_PenanamanModal.pdf", "instrument_id": "UU-25-2007"},
        {"filename": "PP_8_2021_ModalDasar.pdf", "instrument_id": "PP-8-2021"},
    ],
    "tax": [
        {"filename": "UU_6_1983_KUP_PajakUmum.pdf", "instrument_id": "UU-6-1983"},
        {"filename": "UU_36_2008_PPh.pdf", "instrument_id": "UU-36-2008"},
        {"filename": "UU_28_2007_KUP.pdf", "instrument_id": "UU-28-2007"},
        {"filename": "UU_42_2009_PPN.pdf", "instrument_id": "UU-42-2009"},
        {"filename": "PP_55_2022_Implementasi_HPP.pdf", "instrument_id": "PP-55-2022"},
        {"filename": "PP_58_2023_TER_PPh21.pdf", "instrument_id": "PP-58-2023"},
        {"filename": "PP_44_2024_PPN_12persen.pdf", "instrument_id": "PP-44-2024"},
        {"filename": "PMK_68_2022.pdf", "instrument_id": "PMK-68-2022"},
        {"filename": "PMK_66_2023.pdf", "instrument_id": "PMK-66-2023"},
        {"filename": "PMK_2026_PPN_001.pdf", "instrument_id": "PMK-PPN-2026"},
        {"filename": "UU_Akses_Info_Keuangan_Perpajakan.pdf", "instrument_id": "UU-AksesInfoKeu"},
        {"filename": "Perppu_Akses_Info_Keuangan_Perpajakan.pdf", "instrument_id": "Perppu-AksesInfoKeu"},
        {"filename": "UU_7_2021_HPP_Harmonisasi_Perpajakan.pdf", "instrument_id": "UU-7-2021"},
    ],
}

REQUIRED_CLAIM_FIELDS = frozenset({"claim", "verbatim", "pasal_ref", "instrument_id", "category"})


def generate_claim_id(domain: str, index: int) -> str:
    prefix = DOMAIN_PREFIXES.get(domain, domain[:3].upper())
    return f"{prefix}-{index:03d}"


def parse_claims_response(llm_output: str) -> list[dict[str, Any]]:
    # Strip markdown fences
    cleaned = re.sub(r"^```(?:json)?\n?", "", llm_output.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE)
    # Try direct parse
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: find the JSON array in the response (handles preamble text)
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, ValueError):
            pass
    logger.warning("Failed to parse LLM output as JSON (length=%d)", len(llm_output))
    return []


def validate_claim(claim: dict[str, Any]) -> bool:
    return all(field in claim and bool(claim[field]) for field in REQUIRED_CLAIM_FIELDS)


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


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n".join(parts)
    except Exception as e:
        logger.error("PDF extraction failed for %s: %s", pdf_path.name, e)
        return ""


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Split text into overlapping chunks of ~chunk_size chars, breaking at newlines."""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            # Find last newline before end to avoid mid-sentence breaks
            nl = text.rfind("\n", start, end)
            if nl > start + chunk_size // 2:
                end = nl + 1
        chunks.append(text[start:end])
        start = end
    return chunks


def build_prompt(chunk: str, instrument_id: str, domain: str) -> str:
    return f"""You are a legal analyst extracting normative claims from Indonesian law.
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


def extract_from_chunk(
    chunk: str,
    instrument_id: str,
    domain: str,
    chunk_idx: int,
    total_chunks: int,
) -> list[dict[str, Any]]:
    """Extract claims from a single text chunk via OpenAI gpt-4o-mini."""
    prompt = build_prompt(chunk, instrument_id, domain)
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


def process_document(
    doc: dict[str, str],
    domain: str,
    existing_verbatim: set[str],
) -> list[dict[str, Any]]:
    """Extract all claims from a single document."""
    pdf_path = SOURCE_DIR / doc["filename"]
    if not pdf_path.exists():
        logger.warning("Missing: %s", pdf_path)
        return []

    logger.info("Processing %s (%s)...", doc["filename"], doc["instrument_id"])
    text = extract_text_from_pdf(pdf_path)
    if not text:
        logger.warning("No text extracted from %s", doc["filename"])
        return []

    logger.info("  Extracted %d chars, splitting into chunks...", len(text))
    chunks = chunk_text(text)
    logger.info("  %d chunks to process", len(chunks))

    all_claims: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks, 1):
        claims = extract_from_chunk(chunk, doc["instrument_id"], domain, i, len(chunks))
        all_claims.extend(claims)
        time.sleep(0.5)  # brief pause between CLI invocations

    # Deduplicate by verbatim
    new_claims = []
    for c in all_claims:
        if validate_claim(c):
            verbatim = c["verbatim"][:80]  # normalize for dedup
            if verbatim not in existing_verbatim:
                existing_verbatim.add(verbatim)
                new_claims.append(c)

    logger.info("  → %d unique new claims from %s", len(new_claims), doc["instrument_id"])
    return new_claims


def run(domain: str) -> None:
    docs = TIER1_BY_DOMAIN.get(domain)
    if not docs:
        logger.error("No Tier 1 docs for domain: %s", domain)
        sys.exit(1)

    # Load existing claims_db
    existing = load_existing_claims_db(domain)
    existing_verbatim = {c.get("verbatim", "")[:80] for c in existing}
    logger.info("Domain: %s | Existing claims: %d | Documents to process: %d",
                domain, len(existing), len(docs))

    new_claims: list[dict[str, Any]] = []

    for doc in docs:
        doc_claims = process_document(doc, domain, existing_verbatim)
        new_claims.extend(doc_claims)

    if not new_claims:
        logger.info("No new claims found for domain: %s", domain)
        return

    # Stamp with IDs (continuing from existing)
    start_idx = len(existing) + 1
    prefix = DOMAIN_PREFIXES.get(domain, domain[:3].upper())
    for i, claim in enumerate(new_claims):
        claim["claim_id"] = f"{prefix}-{start_idx + i:03d}"

    merged = existing + new_claims
    save_claims_db(merged, domain)
    logger.info("✅ Domain %s: %d new claims added, total: %d", domain, len(new_claims), len(merged))


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch extract claims from Tier 1 PDFs")
    parser.add_argument("--domain", choices=list(TIER1_BY_DOMAIN), help="Single domain")
    parser.add_argument("--all", action="store_true", help="Process all domains sequentially")
    args = parser.parse_args()

    if args.all:
        for domain in TIER1_BY_DOMAIN:
            logger.info("=" * 60)
            logger.info("Processing domain: %s", domain.upper())
            logger.info("=" * 60)
            run(domain)
    elif args.domain:
        run(args.domain)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
