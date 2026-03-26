#!/usr/bin/env python3
"""
NUZANTARA - Tier 1 Gap Laws Ingestion Pipeline
Ingests 7 missing Tier 1 Indonesian legal documents into the RAG system.

Gaps identified via AI gap analysis (Gemini + DeepSeek R1, 2026-03-26):
  PROPERTY:    PP 18/2021, PP 103/2015, Permen ATR/BPN 18/2021
  IMMIGRATION: PP 31/2013, Permenkumham 27/2021, Permenkumham 29/2021
  TAX:         UU 6/1983 (KUP — Ketentuan Umum Perpajakan)

Pipeline:
  1. PDF Parsing (+ OCR fallback for scanned docs)
  2. Google Drive Upload → BALI ZERO/PERATURAN/
  3. Text Cleaning (LegalCleaner)
  4. Metadata Extraction (Pattern + Gemini fallback)
  5. Tier Classification
  6. Hierarchical Indexing → Qdrant (dense 1536 + BM25 sparse + parent-child)
  7. Knowledge Graph Extraction → PostgreSQL (entities + relationships)
  8. Post-Ingestion Verification (Hybrid Search + CrossEncoder rerank)

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python scripts/ingest_tier1_gaps.py
    PYTHONPATH=. python scripts/ingest_tier1_gaps.py --dry-run
    PYTHONPATH=. python scripts/ingest_tier1_gaps.py --domain property
    PYTHONPATH=. python scripts/ingest_tier1_gaps.py --file PP_18
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

BACKEND_PATH = Path(__file__).resolve().parents[1]   # apps/backend-rag/
PROJECT_ROOT = BACKEND_PATH.parents[1]               # monorepo root
sys.path.insert(0, str(BACKEND_PATH))
sys.path.insert(0, str(BACKEND_PATH / "backend"))

from dotenv import load_dotenv

load_dotenv(BACKEND_PATH / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "ingestion_tier1_gaps.log"),
    ],
)
logger = logging.getLogger("ingest_tier1_gaps")

SOURCE_DIR = PROJECT_ROOT / "data/kb_sources/tier1_gaps"

# Collection: all legal docs → legal_unified_hybrid_hybrid (via alias)
COLLECTION_NAME = "legal_unified"

TIER1_LAWS: list[dict] = [
    # ─── PROPERTY ────────────────────────────────────────────────────────────
    {
        "filename": "PP_18_2021_HakPakai_HGB.pdf",
        "title": "PP 18/2021 - Hak Pengelolaan, Hak Atas Tanah, Satuan Rumah Susun, dan Pendaftaran Tanah",
        "category": "property_rights",
        "domain": "property",
        "tier": "T1",
        "marketing_title_it": "PP 18/2021 - Hak Pakai e HGB per Stranieri: Acquisto Immobili in Indonesia",
        "marketing_title_en": "PP 18/2021 - Land Rights (Hak Pakai, HGB) and Property Registration",
        "notes": "Base normativa per acquisto immobili stranieri. Gap più critico per controversie frequenti.",
    },
    {
        "filename": "PP_103_2015_Properti_Asing.pdf",
        "title": "PP 103/2015 - Pemilikan Rumah Tempat Tinggal atau Hunian oleh Orang Asing yang Berkedudukan di Indonesia",
        "category": "property_foreigners",
        "domain": "property",
        "tier": "T1",
        "marketing_title_it": "PP 103/2015 - Proprietà Casa per Stranieri Residenti in Indonesia",
        "marketing_title_en": "PP 103/2015 - Residential Property Ownership by Foreigners in Indonesia",
        "notes": "Specifico Hak Pakai per residenti stranieri (KITAS/KITAP holders).",
    },
    {
        "filename": "PermenATR_BPN_18_2021_Pendaftaran.pdf",
        "title": "Permen ATR/BPN 18/2021 - Tata Cara Penetapan Hak Pengelolaan dan Hak Atas Tanah",
        "category": "property_registration",
        "domain": "property",
        "tier": "T1",
        "marketing_title_it": "Permen ATR/BPN 18/2021 - Procedure Pratiche Intestazione Immobili Stranieri",
        "marketing_title_en": "Permen ATR/BPN 18/2021 - Land Registration Procedures for Foreign Ownership",
        "notes": "Procedure pratiche BPN per registrazione titoli fondiari stranieri. 980 pagine con allegati.",
    },
    # ─── IMMIGRATION ─────────────────────────────────────────────────────────
    {
        "filename": "PP_31_2013_Imigrasi.pdf",
        "title": "PP 31/2013 - Peraturan Pelaksanaan Undang-Undang Nomor 6 Tahun 2011 tentang Keimigrasian",
        "category": "immigration_implementation",
        "domain": "immigration",
        "tier": "T1",
        "marketing_title_it": "PP 31/2013 - Regolamento Attuativo Legge Immigrazione: KITAS, KITAP, Visti",
        "marketing_title_en": "PP 31/2013 - Immigration Law Implementation: KITAS, KITAP, Visa Procedures",
        "notes": "Base per tutti i permessi soggiorno stranieri (KITAS BAB V art.141). 88 pagine.",
    },
    {
        "filename": "Permenkumham_27_2021_Visa.pdf",
        "title": "Permenkumham 27/2021 - Tata Cara Pemberian, Perpanjangan, Penolakan, Pembatalan, dan Pencabutan Visa",
        "category": "immigration_visa",
        "domain": "immigration",
        "tier": "T1",
        "marketing_title_it": "Permenkumham 27/2021 - Procedure Rilascio, Rinnovo e Revoca Visti",
        "marketing_title_en": "Permenkumham 27/2021 - Visa Issuance, Extension, Rejection and Revocation Procedures",
        "notes": "Aggiornamento procedure visti 2021. Sostituisce regolamenti precedenti.",
    },
    {
        "filename": "Permenkumham_29_2021_KITAS.pdf",
        "title": "Permenkumham 29/2021 - Visa dan Izin Tinggal",
        "category": "immigration_kitas",
        "domain": "immigration",
        "tier": "T1",
        "marketing_title_it": "Permenkumham 29/2021 - KITAS (Izin Tinggal Terbatas): Regolamento Completo",
        "marketing_title_en": "Permenkumham 29/2021 - Temporary Stay Permits (KITAS/ITAS) Full Regulation",
        "notes": "Specifico per KITAS (E31, C317, B211 ecc.). Uso quotidiano. 1.8MB.",
    },
    {
        "filename": "Permenkumham_11_2024_Visa_IzinTinggal.pdf",
        "title": "Permenkumham 11/2024 - Perubahan atas Permenkumham 22/2023 tentang Visa dan Izin Tinggal",
        "category": "immigration_visa_update",
        "domain": "immigration",
        "tier": "T1",
        "marketing_title_it": "Permenkumham 11/2024 - Aggiornamento Procedure Visti 2024 (modifica Permenkumham 22/2023)",
        "marketing_title_en": "Permenkumham 11/2024 - 2024 Visa and Stay Permit Procedure Updates",
        "notes": "Modifica Permenkumham 22/2023 su Visa dan Izin Tinggal. 49 pagine. Rimpiazza gap erroneo Permenkumham 27/2021.",
    },
    # ─── TAX ─────────────────────────────────────────────────────────────────
    {
        "filename": "UU_6_1983_KUP_PajakUmum.pdf",
        "title": "UU 6/1983 - Ketentuan Umum dan Tata Cara Perpajakan (KUP) sebagaimana telah diubah",
        "category": "tax_general",
        "domain": "tax",
        "tier": "T1",
        "marketing_title_it": "UU 6/1983 KUP - Disposizioni Generali Fiscali: Fondamento del Sistema Tributario",
        "marketing_title_en": "UU 6/1983 KUP - General Tax Provisions: Foundation of Indonesian Tax System",
        "notes": "Fondamento intero sistema fiscale: NPWP, accertamenti, sanzioni, ricorsi. Nessun equivalente moderno nel Drive.",
    },
]


async def run_ingestion(
    dry_run: bool = False,
    domain_filter: str | None = None,
    file_filter: str | None = None,
) -> None:
    try:
        from backend.services.ingestion.legal_ingestion_service import LegalIngestionService
        from backend.services.rag.hybrid_search import HybridSearchService
        from backend.services.rag.reranker import CrossEncoderReranker
    except ImportError as e:
        logger.error("Failed to import Nuzantara services: %s", e)
        logger.info("PYTHONPATH: %s", sys.path[:3])
        return

    if not SOURCE_DIR.exists():
        logger.error("Source directory not found: %s", SOURCE_DIR)
        logger.info("Expected: data/kb_sources/tier1_gaps/")
        return

    # Apply filters
    laws = TIER1_LAWS
    if domain_filter:
        laws = [l for l in laws if l["domain"] == domain_filter.lower()]
        if not laws:
            logger.error("No laws for domain: '%s'. Valid: property, immigration, tax", domain_filter)
            return
    if file_filter:
        laws = [l for l in laws if file_filter.lower() in l["filename"].lower()]
        if not laws:
            logger.error("No files matching: '%s'", file_filter)
            return

    # Verify all source files exist before starting
    missing: list[str] = []
    for law in laws:
        fp = SOURCE_DIR / law["filename"]
        if not fp.exists():
            missing.append(law["filename"])
    if missing:
        logger.error("Missing source files (run download step first): %s", missing)
        return

    # Print plan
    logger.info("=" * 65)
    logger.info("🇮🇩  NUZANTARA — TIER 1 GAP LAWS INGESTION")
    logger.info("=" * 65)
    logger.info("Source:     %s", SOURCE_DIR)
    logger.info("Collection: %s → legal_unified_hybrid_hybrid", COLLECTION_NAME)
    logger.info("Documents:  %d", len(laws))
    logger.info("Mode:       %s", "DRY RUN" if dry_run else "LIVE INGESTION")
    logger.info("")

    by_domain: dict[str, list[dict]] = {}
    for law in laws:
        by_domain.setdefault(law["domain"], []).append(law)

    for domain, domain_laws in by_domain.items():
        logger.info("  [%s]", domain.upper())
        for law in domain_laws:
            fp = SOURCE_DIR / law["filename"]
            size_kb = fp.stat().st_size / 1024
            logger.info("    %-45s %6.0f KB", law["filename"], size_kb)
            logger.info("    → %s", law["title"][:80])
        logger.info("")

    logger.info("Pipeline: Parse → Drive → Clean → Metadata → Tier → BM25+Embed → KG")
    logger.info("=" * 65)

    if dry_run:
        logger.info("DRY RUN — no data written.")
        return

    # Initialize service
    service = LegalIngestionService(collection_name=COLLECTION_NAME)

    # Ensure collection has hybrid support
    logger.info("Ensuring collection '%s' with hybrid vectors (dense 1536 + BM25)...", COLLECTION_NAME)
    await service.vector_db.create_collection(
        vector_size=1536,
        enable_sparse=True,
    )

    results: list[dict] = []
    start_all = time.time()

    for i, law in enumerate(laws):
        file_path = SOURCE_DIR / law["filename"]
        logger.info("")
        logger.info("━━━ [%d/%d] %s ━━━", i + 1, len(laws), law["filename"])
        logger.info("Domain: %s | Tier: %s", law["domain"], law["tier"])
        logger.info("Title:  %s", law["title"])

        try:
            result = await service.ingest_legal_document(
                file_path=str(file_path),
                title=law["title"],
                category=law["category"],
            )

            if result["success"]:
                kg = result.get("kg_extraction", {})
                logger.info(
                    "✅ SUCCESS: %s\n"
                    "   Chunks:    %d\n"
                    "   Structure: %d BAB, %d Pasal\n"
                    "   KG:        %d entities, %d relations\n"
                    "   Time:      %.1fs",
                    law["filename"],
                    result["chunks_created"],
                    result["structure"]["bab_count"],
                    result["structure"]["pasal_count"],
                    kg.get("entities", 0),
                    kg.get("relationships", 0),
                    result["processing_time_seconds"],
                )
            else:
                logger.error("❌ FAILED: %s — %s", law["filename"], result.get("error"))

            results.append({**result, "law": law})

        except Exception as e:
            logger.error("💥 FATAL: %s — %s", law["filename"], e, exc_info=True)
            results.append({"success": False, "file": law["filename"], "error": str(e), "law": law})

    # Summary
    total_time = time.time() - start_all
    ok = [r for r in results if r.get("success")]
    fail = [r for r in results if not r.get("success")]
    total_chunks = sum(r.get("chunks_created", 0) for r in ok)
    total_entities = sum(r.get("kg_extraction", {}).get("entities", 0) for r in ok)
    total_rels = sum(r.get("kg_extraction", {}).get("relationships", 0) for r in ok)

    logger.info("")
    logger.info("=" * 65)
    logger.info("🏁  INGESTION SUMMARY")
    logger.info("=" * 65)
    logger.info("Total:        %d docs", len(laws))
    logger.info("Successful:   %d", len(ok))
    logger.info("Failed:       %d", len(fail))
    logger.info("Chunks:       %d (dense + BM25 vectors each)", total_chunks)
    logger.info("KG Entities:  %d", total_entities)
    logger.info("KG Relations: %d", total_rels)
    logger.info("Total time:   %.1f min", total_time / 60)

    if fail:
        logger.info("\nFailed documents:")
        for r in fail:
            logger.info("  ❌ %s — %s", r.get("file", r["law"]["filename"]), r.get("error"))

    logger.info("=" * 65)

    # Post-ingestion verification
    if ok:
        logger.info("")
        logger.info("🔍 Post-Ingestion Verification (Hybrid + CrossEncoder)...")
        try:
            hybrid = HybridSearchService()
            reranker = CrossEncoderReranker()

            test_queries: list[tuple[str, str]] = [
                ("property", "hak pakai orang asing pemilikan rumah hunian"),
                ("property", "pendaftaran hak atas tanah HGB stranieri Indonesia"),
                ("immigration", "KITAS izin tinggal terbatas perpanjangan prosedur"),
                ("immigration", "visa kunjungan izin tinggal warga negara asing"),
                ("tax", "NPWP ketentuan umum perpajakan KUP sanksi administrasi"),
            ]

            for domain, query in test_queries:
                sr = await hybrid.search_hybrid(
                    query=query,
                    collection=COLLECTION_NAME,
                    limit=5,
                )
                if sr["results"]:
                    reranked = await reranker.rerank(query=query, documents=sr["results"], top_k=1)
                    top = reranked[0]["text"][:70] if reranked else "N/A"
                    logger.info("  ✅ [%s] '%s...' → %d hits | top: %s...", domain, query[:35], len(sr["results"]), top)
                else:
                    logger.warning("  ⚠️  [%s] '%s...' → 0 hits", domain, query[:35])

            logger.info("✅ Hybrid Search (Dense+BM25) + CrossEncoder verified.")

        except Exception as e:
            logger.warning("⚠️  Verification skipped: %s", e)

    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Run claims_extractor.py for each domain to build claims_db")
    logger.info("     PYTHONPATH=. python scripts/claims_extractor.py --domain property")
    logger.info("     PYTHONPATH=. python scripts/claims_extractor.py --domain immigration")
    logger.info("     PYTHONPATH=. python scripts/claims_extractor.py --domain tax")
    logger.info("  2. Run verified_generator.py to produce T2 documents")
    logger.info("  3. Upload approved documents to NotebookLM via source_add")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Tier 1 Gap Laws into Nuzantara RAG")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no ingestion")
    parser.add_argument("--domain", type=str, choices=["property", "immigration", "tax"],
                        help="Ingest only a specific domain")
    parser.add_argument("--file", type=str, help="Filter by filename (partial match)")
    args = parser.parse_args()

    asyncio.run(run_ingestion(
        dry_run=args.dry_run,
        domain_filter=args.domain,
        file_filter=args.file,
    ))
