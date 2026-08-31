#!/usr/bin/env python3
"""
ZANTARA - 2026 Laws Ingestion Pipeline
Ingests 5 key 2026 laws from data/kb_sources/2026_updates/ into the RAG system.

Pipeline:
  1. PDF Parsing (+ OCR fallback)
  2. Google Drive Upload (→ BALI ZERO/PERATURAN)
  3. Text Cleaning (LegalCleaner)
  4. Metadata Extraction (Pattern + Gemini fallback)
  5. Tier Classification
  6. Hierarchical Indexing → Qdrant (dense 1536 + BM25 sparse + parent-child)
  7. Knowledge Graph Extraction → PostgreSQL (entities + relationships)
  8. Post-Ingestion Verification (Hybrid Search + Rerank2)

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python scripts/ingest_2026_laws.py
    PYTHONPATH=. python scripts/ingest_2026_laws.py --dry-run    # Preview only
    PYTHONPATH=. python scripts/ingest_2026_laws.py --file PMK    # Single file (partial match)
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path("/Users/nuzantara/nuzantara")
BACKEND_PATH = PROJECT_ROOT / "apps/backend-rag"
sys.path.insert(0, str(BACKEND_PATH))
sys.path.insert(0, str(BACKEND_PATH / "backend"))

# Load environment
from dotenv import load_dotenv

load_dotenv(BACKEND_PATH / ".env", override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "ingestion_2026_laws.log"),
    ],
)
logger = logging.getLogger("ingest_2026_laws")

# Target documents with marketing metadata
LAWS_2026 = [
    {
        # DECLARED IDENTITY -- read this before touching either entry below.
        #
        # Both PMK 1/2026 and Permen Imipas 1/2026 derive the SAME document_id
        # from the extracted (type, number, year) triple: `Permen_1_2026`. Every
        # Indonesian ministry numbers its regulations from 1 each year, so that
        # triple does not identify an instrument.
        #
        # Chunk ids are `{document_id}_Pasal_{n}` and Qdrant point ids are
        # `uuid5(chunk_id)`. On 2026-08-25 the collision destroyed 50 chunks of
        # this Coretax regulation when the immigration one was ingested over it,
        # with no error at all -- an overwrite IS a successful upsert.
        #
        # Declaring `document_id` here is how the corpus states which instrument
        # a file is, in the one place that actually knows. The service honours a
        # declared id as the storage key and refuses to write onto an identity
        # another source file already holds.
        "document_id": "PMK_1_2026",
        "filename": "PMK_1_2026_Coretax_System.pdf",
        "title": "PMK 1/2026 - Perubahan Keempat atas PMK 81/2024 tentang Ketentuan Perpajakan dalam rangka Pelaksanaan Sistem Inti Administrasi Perpajakan (Coretax)",
        "category": "perpajakan_2026",
        "marketing_title_it": "PMK 1/2026 - Coretax: Riforma Fiscale Digitale Indonesia",
        "marketing_title_en": "PMK 1/2026 - Coretax: Indonesia Digital Tax Reform",
    },
    {
        "filename": "PP_9_2026_THR_Gaji_13.pdf",
        "title": "PP 9/2026 - Pemberian Tunjangan Hari Raya dan Gaji Ketiga Belas kepada Aparatur Negara, Pensiunan, Penerima Pensiun, dan Penerima Tunjangan Tahun 2026",
        "category": "ketenagakerjaan_2026",
        "marketing_title_it": "PP 9/2026 - THR e Tredicesima per Dipendenti Pubblici 2026",
        "marketing_title_en": "PP 9/2026 - Hari Raya Allowance & 13th Month Salary 2026",
    },
    {
        "filename": "Pergub_Bali_14_2023_RPD_2024_2026.pdf",
        "title": "Pergub Bali 14/2023 - Rencana Pembangunan Daerah Provinsi Bali Tahun 2024-2026",
        "category": "perencanaan_bali",
        "marketing_title_it": "Pergub Bali 14/2023 - Piano Sviluppo Regionale Bali 2024-2026",
        "marketing_title_en": "Pergub Bali 14/2023 - Bali Regional Development Plan 2024-2026",
    },
    {
        "filename": "SE_Gubernur_Bali_09_2025_Bali_Bersih_Sampah.pdf",
        "title": "SE Gubernur Bali 09/2025 - Gerakan Bali Bersih Sampah",
        "category": "lingkungan_bali",
        "marketing_title_it": "SE Gubernur Bali 09/2025 - Gerakan Bali Bersih Sampah",
        "marketing_title_en": "SE Gubernur Bali 09/2025 - Bali Clean Waste Campaign",
    },
    {
        "filename": "UU_1_2023_KUHP_Baru.pdf",
        "title": "UU 1/2023 - Kitab Undang-Undang Hukum Pidana (KUHP Baru)",
        "category": "hukum_pidana",
        "marketing_title_it": "UU 1/2023 - Nuovo Codice Penale Indonesia (KUHP)",
        "marketing_title_en": "UU 1/2023 - Indonesia New Criminal Code (KUHP)",
    },
    # ── Immigration corpus, added 2026-08-24 ────────────────────────────────────
    # Every title below was read off the PDF's own heading, not inferred from the
    # file name — two files staged for this batch carried a WRONG name and were
    # renamed only because that check was run (Perpres 76/2024 is land allocation
    # for investment restructuring, NOT the Golden Visa; Permenkumham 34/2021 is a
    # Covid-era measure). Same discipline as the NB-2 loader's identity gate.
    #
    # Kepmen M.IP-19.GR.01.01/2025 enters as a `.txt`, NOT as its PDF. That PDF is
    # a SCAN with 0 extractable characters across 3 pages (verified: pypdf returns
    # an empty string for all three). CORRECTED: this does NOT mean the pipeline
    # would index it empty — `legal_ingestion_service.py` catches "No text
    # extracted" and falls back to OCR, Gemini Vision included
    # (`backend/core/parsers.py:117-126`), so the PDF path would have produced
    # SOME text. The `.txt` is used instead because a human-verified verbatim
    # transcription, read visually off the three pages, is more trustworthy than
    # an unreviewed OCR/Vision pass on a document this short — not because the
    # alternative was emptiness. It carries its own provenance header saying it
    # was transcribed, not extracted, so that distinction travels with the
    # content into retrieval. `.txt` is a first-class input here
    # (`backend/core/parsers.py:530`). The scanned PDF stays in the Drive
    # PERATURAN archive as the authentic artifact.
    #
    # Known gap, not fixed here: the provenance header lives only in the chunk
    # TEXT (may or may not survive chunking as one piece with the body), not in
    # a queryable metadata field — `source_url`/`effective_date` exist as
    # `ingest_legal_document` params and are never passed by this script for any
    # entry.
    # UU 6/2011 and Permenkumham 22/2023 are both left `current`, deliberately,
    # after considering and rejecting `historical_only`. Both are amended, not
    # repealed — UU 6/2011 by UU 63/2024 (in this batch) and two earlier
    # amendments not in this batch; Permenkumham 22/2023 by 11/2024 (also in
    # this batch). Marking either `historical_only` would remove its still-valid
    # UNAMENDED provisions from current-law retrieval, which is a worse failure
    # than the one being guarded against.
    #
    # KNOWN, UNRESOLVED GAP: `retrieval_scope` is a whole-DOCUMENT field. Neither
    # this script nor the ingestion service has any PASAL-level supersession
    # tracking, so the specific articles that 63/2024 and 11/2024 rewrote remain
    # retrievable from these base texts in their pre-amendment wording, with
    # equal standing to the amendment's own text. This is not fixed by this
    # entry list — it would need chunk-level supersession metadata the pipeline
    # does not have today.
    {
        "filename": "UU_6_2011_Keimigrasian.pdf",
        "title": "UU 6/2011 - Keimigrasian",
        "category": "keimigrasian",
        "marketing_title_it": "UU 6/2011 - Legge sull'Immigrazione (testo base)",
        "marketing_title_en": "UU 6/2011 - Indonesian Immigration Law (base text)",
    },
    {
        "filename": "UU_63_2024_Perubahan_Ketiga_UU_Keimigrasian.pdf",
        "title": "UU 63/2024 - Perubahan Ketiga atas Undang-Undang Nomor 6 Tahun 2011 tentang Keimigrasian",
        "category": "keimigrasian",
        "marketing_title_it": "UU 63/2024 - Terza Modifica alla Legge sull'Immigrazione",
        "marketing_title_en": "UU 63/2024 - Third Amendment to the Immigration Law",
    },
    {
        "filename": "Perpres_157_2024_Kementerian_Imigrasi_dan_Pemasyarakatan.pdf",
        "title": "Perpres 157/2024 - Kementerian Imigrasi dan Pemasyarakatan",
        "category": "keimigrasian",
        "marketing_title_it": "Perpres 157/2024 - Istituzione del Ministero Immigrazione e Penitenziari",
        "marketing_title_en": "Perpres 157/2024 - Ministry of Immigration and Corrections",
    },
    {
        "filename": "Perpres_76_2024_Perubahan_Perpres_70_2023_Pengalokasian_Lahan_Investasi.pdf",
        "title": "Perpres 76/2024 - Perubahan atas Peraturan Presiden Nomor 70 Tahun 2023 tentang Pengalokasian Lahan bagi Penataan Investasi",
        "category": "investasi",
        "marketing_title_it": "Perpres 76/2024 - Assegnazione Terreni per il Riordino degli Investimenti",
        "marketing_title_en": "Perpres 76/2024 - Land Allocation for Investment Restructuring",
    },
    {
        "filename": "Permenkumham_22_2023_Visa_dan_Izin_Tinggal.pdf",
        "title": "Permenkumham 22/2023 - Visa dan Izin Tinggal",
        "category": "keimigrasian",
        "marketing_title_it": "Permenkumham 22/2023 - Visti e Permessi di Soggiorno",
        "marketing_title_en": "Permenkumham 22/2023 - Visas and Stay Permits",
    },
    {
        "filename": "Permenkumham_11_2024_Perubahan_Visa_dan_Izin_Tinggal.pdf",
        "title": "Permenkumham 11/2024 - Perubahan atas Peraturan Menteri Hukum dan Hak Asasi Manusia Nomor 22 Tahun 2023 tentang Visa dan Izin Tinggal",
        "category": "keimigrasian",
        "marketing_title_it": "Permenkumham 11/2024 - Modifica al 22/2023 su Visti e Soggiorni",
        "marketing_title_en": "Permenkumham 11/2024 - Amendment to 22/2023 on Visas and Stay Permits",
    },
    {
        "filename": "Permenkumham_34_2021_Visa_Izin_Tinggal_Masa_Covid19.pdf",
        "title": "Permenkumham 34/2021 - Pemberian Visa dan Izin Tinggal Keimigrasian dalam Masa Penanganan Penyebaran Corona Virus Disease 2019 dan Dampak Pemulihan Ekonomi Nasional",
        "category": "keimigrasian",
        # Scoped HISTORICAL on its own time-bound subject matter — this is a
        # Covid-emergency instrument whose operative window has passed. NOT on a
        # verified repeal: no repeal of 34/2021 was found (Permen Imipas 6/2025
        # revokes Permenkumham *35*/2021, a different instrument). Ingested as
        # `current` it would be retrievable as law in force, which on a
        # client-facing surface is the failure that matters. Note the pipeline
        # makes the Drive archive BLOCKING for this scope
        # (`LegalIngestIntegrityError`), so this entry cannot land until the
        # Drive service-account credential is present — a loud failure, by
        # design, and the correct one.
        # Literal, not the imported constant: LAWS_2026 is a module-level data
        # literal that must stay `ast.literal_eval`-able. The value is pinned
        # against the real constant at run time, right below the import.
        "retrieval_scope": "historical_only",
        "marketing_title_it": "Permenkumham 34/2021 - Visti e Soggiorni nel Periodo Covid-19 (storico)",
        "marketing_title_en": "Permenkumham 34/2021 - Visas and Stay Permits during Covid-19 (historical)",
    },
    {
        "filename": "PermenImipas_2_2025_Pengawasan_Keimigrasian.pdf",
        "title": "Permen Imipas 2/2025 - Pengawasan Keimigrasian dan Tindakan Administratif Keimigrasian",
        "category": "keimigrasian",
        "marketing_title_it": "Permen Imipas 2/2025 - Vigilanza Migratoria e Provvedimenti Amministrativi",
        "marketing_title_en": "Permen Imipas 2/2025 - Immigration Supervision and Administrative Action",
    },
    {
        "filename": "PermenImipas_4_2025_Kartu_Perjalanan_Pebisnis_APEC.pdf",
        "title": "Permen Imipas 4/2025 - Kartu Perjalanan Pebisnis Asia Pacific Economic Cooperation",
        "category": "keimigrasian",
        "marketing_title_it": "Permen Imipas 4/2025 - Carta di Viaggio d'Affari APEC (ABTC)",
        "marketing_title_en": "Permen Imipas 4/2025 - APEC Business Travel Card (ABTC)",
    },
    {
        "filename": "PermenImipas_6_2025_Pencabutan_Permenkumham_35_2021.pdf",
        "title": "Permen Imipas 6/2025 - Pencabutan Peraturan Menteri Hukum dan Hak Asasi Manusia Nomor 35 Tahun 2021 tentang Konsultan Keimigrasian",
        "category": "keimigrasian",
        "marketing_title_it": "Permen Imipas 6/2025 - Abrogazione della Norma sui Consulenti per l'Immigrazione",
        "marketing_title_en": "Permen Imipas 6/2025 - Repeal of the Immigration Consultants Regulation",
    },
    {
        "filename": "PermenImipas_9_2025_Penambahan_Bebas_Visa_Kunjungan.pdf",
        "title": "Permen Imipas 9/2025 - Penambahan Daftar Negara, Pemerintah Wilayah Administratif Khusus Suatu Negara, dan Entitas Tertentu atau Pemegang Izin Tinggal Tertentu dari Suatu Negara yang Diberikan Bebas Visa Kunjungan",
        "category": "keimigrasian",
        # SUPERSEDED IN SUBSTANCE — deliberately NOT claimed as expressly
        # repealed. An earlier revision of this comment asserted that
        # PermenImipas 10/2026's Pasal 4 repeals THIS instrument; that was
        # wrong. Re-read verbatim, 10/2026 Pasal 4 names "Peraturan Menteri
        # Imigrasi dan Pemasyarakatan NOMOR 10 TAHUN 2025 ... (Berita Negara
        # Republik Indonesia Tahun 2025 Nomor 594)" — a DIFFERENT instrument,
        # which this repo does not hold. No primary text in our corpus repeals
        # 9/2025 by name, and 9/2025 itself contains no repeal clause.
        #
        # The scope is still historical_only, on the honest ground: 9/2025,
        # 10/2025 and 10/2026 are successive revisions of the SAME visa-free
        # country list under Perpres 95/2024 Pasal 5(4), and 10/2026 is the
        # operative one. Served as `current`, 9/2025 would answer "which
        # countries are visa-free?" with a stale list competing against the
        # live one — the exact failure historical_only exists to prevent.
        "retrieval_scope": "historical_only",
        "marketing_title_it": "Permen Imipas 9/2025 - Ampliamento dei Paesi Esenti da Visto di Visita (SUPERATO: la lista in vigore è il 10/2026)",
        "marketing_title_en": "Permen Imipas 9/2025 - Expanded Visa-Free Visit Country List (SUPERSEDED: the list in force is 10/2026)",
    },
    {
        "filename": "PermenImipas_14_2025_Tarif_Nol_Rupiah.pdf",
        "title": "Permen Imipas 14/2025 - Persyaratan dan Tata Cara Pengenaan Tarif Nol Rupiah terhadap Pelayanan Keimigrasian dan Biaya Beban",
        "category": "keimigrasian",
        "marketing_title_it": "Permen Imipas 14/2025 - Tariffa Zero per i Servizi Migratori",
        "marketing_title_en": "Permen Imipas 14/2025 - Zero-Rupiah Tariff for Immigration Services",
    },
    {
        # Declared for the same reason as PMK_1_2026 above: without it this
        # regulation and the Coretax one share the identity `Permen_1_2026`.
        "document_id": "PermenImipas_1_2026",
        "filename": "PermenImipas_1_2026_Perubahan_Pencegahan_dan_Penangkalan.pdf",
        "title": "Permen Imipas 1/2026 - Perubahan atas Peraturan Menteri Imigrasi dan Pemasyarakatan Nomor 13 Tahun 2025 tentang Pelaksanaan Pencegahan dan Penangkalan",
        "category": "keimigrasian",
        "marketing_title_it": "Permen Imipas 1/2026 - Modifica su Divieti di Uscita e di Ingresso",
        "marketing_title_en": "Permen Imipas 1/2026 - Amendment on Exit and Entry Bans",
    },
    {
        "filename": "PermenImipas_7_2026_Intelijen_Keimigrasian.pdf",
        "title": "Permen Imipas 7/2026 - Intelijen Keimigrasian",
        "category": "keimigrasian",
        "marketing_title_it": "Permen Imipas 7/2026 - Intelligence Migratoria",
        "marketing_title_en": "Permen Imipas 7/2026 - Immigration Intelligence",
    },
    {
        "filename": "Kepmen_MIP_19_GR0101_2025_Sistem_Kerja_TPI_TRANSKRIPSI.txt",
        "title": "Kepmen M.IP-19.GR.01.01/2025 - Sistem Kerja pada Tempat Pemeriksaan Imigrasi (transkripsi verbatim dari PDF hasil pindai)",
        "category": "keimigrasian",
        "marketing_title_it": "Kepmen M.IP-19/2025 - Organizzazione del Lavoro ai Posti di Frontiera (trascrizione)",
        "marketing_title_en": "Kepmen M.IP-19/2025 - Border Checkpoint Work System (transcription)",
    },
    {
        "filename": "PermenImipas_10_2026_Daftar_Negara_Bebas_Visa_Kunjungan.pdf",
        "title": "Permen Imipas 10/2026 - Penambahan Daftar Negara, Pemerintah Wilayah Administratif Khusus Suatu Negara, dan Entitas Tertentu yang Diberikan Bebas Visa Kunjungan",
        "category": "keimigrasian",
        "marketing_title_it": "Permen Imipas 10/2026 - Elenco Corrente dei Paesi Esenti da Visto di Visita",
        "marketing_title_en": "Permen Imipas 10/2026 - Current Visa-Free Visit Country List",
    },
]

# "legal_unified_2026" was a dead end: absent from collection_registry.py's
# CANONICAL_COLLECTION_ALIASES (so LegalIngestionService's preflight allowlist
# rejects it) and never selected by any live retrieval routing table
# (multi_hop.py / query_planner.py / kg_orchestrator.py / agentic/tools.py all
# route legal-domain queries to "legal_unified" only). Content ingested under
# the old name would sit in Qdrant unreachable by any user-facing query.
COLLECTION_NAME = "legal_unified"
SOURCE_DIR = PROJECT_ROOT / "data/kb_sources/2026_updates"


async def run_ingestion(dry_run: bool = False, file_filter: str | None = None):
    try:
        from backend.services.ingestion.legal_ingestion_service import (
            CURRENT_RETRIEVAL_SCOPE,
            HISTORICAL_RETRIEVAL_SCOPE,
            LegalIngestionService,
        )

        # Pin the literals used in LAWS_2026 against the real constants. If the
        # service ever renames a scope, this fails loudly here instead of
        # silently passing an unrecognised string into ingestion.
        # A declared identity that repeats inside this very list would
        # re-create by hand the exact collision the declaration exists to
        # prevent. Fail here, before the first byte is written, rather than
        # discovering it as missing chunks weeks later.
        declared_ids = [law["document_id"] for law in LAWS_2026 if law.get("document_id")]
        duplicate_ids = {i for i in declared_ids if declared_ids.count(i) > 1}
        if duplicate_ids:
            raise ValueError(
                f"LAWS_2026 declares the same document_id more than once: {sorted(duplicate_ids)}"
            )

        declared_scopes = {law.get("retrieval_scope") for law in LAWS_2026} - {None}
        known_scopes = {CURRENT_RETRIEVAL_SCOPE, HISTORICAL_RETRIEVAL_SCOPE}
        unknown_scopes = declared_scopes - known_scopes
        if unknown_scopes:
            raise RuntimeError(
                f"LAWS_2026 declares unknown retrieval_scope(s): {sorted(unknown_scopes)}; "
                f"the service accepts {sorted(known_scopes)}"
            )
        from backend.services.rag.hybrid_search import HybridSearchService
        from backend.services.rag.reranker import CrossEncoderReranker
    except ImportError as e:
        logger.error(f"Failed to import Nuzantara services: {e}")
        logger.info(f"PYTHONPATH: {sys.path}")
        return

    if not SOURCE_DIR.exists():
        logger.error(f"Source directory not found: {SOURCE_DIR}")
        return

    # Filter laws if --file specified
    laws = LAWS_2026
    if file_filter:
        laws = [law for law in laws if file_filter.lower() in law["filename"].lower()]
        if not laws:
            logger.error(f"No files matching filter: '{file_filter}'")
            return

    # Verify all files exist
    missing = []
    for law in laws:
        fp = SOURCE_DIR / law["filename"]
        if not fp.exists():
            missing.append(law["filename"])
    if missing:
        logger.error(f"Missing files: {missing}")
        return

    logger.info("=" * 60)
    logger.info("🇮🇩 NUZANTARA 2026 LAWS INGESTION PIPELINE")
    logger.info("=" * 60)
    logger.info(f"Source: {SOURCE_DIR}")
    logger.info(f"Collection: {COLLECTION_NAME}")
    logger.info(f"Documents: {len(laws)}")
    logger.info(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE INGESTION'}")
    logger.info("")
    for i, law in enumerate(laws):
        fp = SOURCE_DIR / law["filename"]
        size_mb = fp.stat().st_size / (1024 * 1024)
        logger.info(f"  [{i + 1}] {law['filename']} ({size_mb:.1f} MB)")
        logger.info(f"      Title: {law['title'][:80]}...")
        logger.info(f"      Category: {law['category']}")
    logger.info("")
    logger.info("Pipeline: Parse → Drive Upload → Clean → Metadata → Tier → Chunk+BM25+Embed → KG")
    logger.info("=" * 60)

    if dry_run:
        logger.info("🔍 DRY RUN — no data will be written. Exiting.")
        return

    # Initialize service
    service = LegalIngestionService(collection_name=COLLECTION_NAME)

    # Ensure collection exists with hybrid support (dense 1536 + BM25 sparse)
    logger.info(f"Ensuring collection '{COLLECTION_NAME}' exists with hybrid vectors...")
    await service.vector_db.create_collection(
        vector_size=1536,  # OpenAI text-embedding-3-small
        enable_sparse=True,  # BM25 sparse vectors
    )

    results = []
    start_all = time.time()

    for i, law in enumerate(laws):
        file_path = SOURCE_DIR / law["filename"]
        logger.info("")
        logger.info(f"━━━ [{i + 1}/{len(laws)}] {law['filename']} ━━━")
        logger.info(f"Title: {law['title']}")

        try:
            result = await service.ingest_legal_document(
                file_path=str(file_path),
                title=law["title"],
                category=law["category"],
                retrieval_scope=law.get("retrieval_scope", CURRENT_RETRIEVAL_SCOPE),
                # Entries that declare one get that identity as the storage key;
                # the rest keep the derived triple, so nothing already indexed
                # changes identity and no migration is owed.
                document_id=law.get("document_id"),
            )

            if result["success"]:
                kg_stats = result.get("kg_extraction", {})
                logger.info(
                    f"✅ SUCCESS: {law['filename']}\n"
                    f"   Chunks: {result['chunks_created']}\n"
                    f"   Structure: {result['structure']['bab_count']} BAB, "
                    f"{result['structure']['pasal_count']} Pasal\n"
                    f"   KG: {kg_stats.get('entities', 0)} entities, "
                    f"{kg_stats.get('relationships', 0)} relations\n"
                    f"   Time: {result['processing_time_seconds']:.1f}s"
                )
            else:
                logger.error(f"❌ FAILED: {law['filename']} — {result['error']}")

            results.append(result)

        except Exception as e:
            logger.error(f"💥 FATAL: {law['filename']} — {e}", exc_info=True)
            results.append({"success": False, "file": law["filename"], "error": str(e)})

    # Summary
    total_duration = time.time() - start_all
    success_count = sum(1 for r in results if r.get("success"))
    total_chunks = sum(r.get("chunks_created", 0) for r in results if r.get("success"))
    total_entities = sum(
        r.get("kg_extraction", {}).get("entities", 0) for r in results if r.get("success")
    )
    total_rels = sum(
        r.get("kg_extraction", {}).get("relationships", 0) for r in results if r.get("success")
    )

    logger.info("")
    logger.info("=" * 60)
    logger.info("🏁 INGESTION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total Documents: {len(laws)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {len(laws) - success_count}")
    logger.info(f"Total Chunks: {total_chunks}")
    logger.info(f"KG Entities: {total_entities}")
    logger.info(f"KG Relationships: {total_rels}")
    logger.info(f"Total Time: {total_duration / 60:.1f} minutes")
    logger.info("=" * 60)

    # Post-Ingestion Verification
    if success_count > 0:
        logger.info("")
        logger.info("🔍 Post-Ingestion Verification (Hybrid Search + Rerank2)...")
        try:
            hybrid_service = HybridSearchService()
            reranker = CrossEncoderReranker()

            test_queries = [
                "peraturan perpajakan coretax 2026",
                "tunjangan hari raya gaji 13 aparatur negara",
                "rencana pembangunan daerah bali",
                "gerakan bali bersih sampah",
                "kitab undang-undang hukum pidana KUHP baru",
                # Immigration corpus added 2026-08-24 — without these, a broken
                # or misindexed immigration document would still print
                # "Pipeline verified" (found in adversarial review of this batch:
                # the original 5 queries gave zero coverage to the 16 new docs).
                "visa dan izin tinggal keimigrasian",
                "daftar negara bebas visa kunjungan",
                "kementerian imigrasi dan pemasyarakatan",
                "sistem kerja tempat pemeriksaan imigrasi",
            ]

            for query in test_queries:
                search_results = await hybrid_service.search_hybrid(
                    query=query, collection=COLLECTION_NAME, limit=5
                )
                if search_results["results"]:
                    reranked = await reranker.rerank(
                        query=query, documents=search_results["results"], top_k=1
                    )
                    top = reranked[0]["text"][:80] if reranked else "N/A"
                    logger.info(
                        f"  ✅ '{query[:40]}...' → {len(search_results['results'])} hits → Top: {top}..."
                    )
                else:
                    logger.warning(f"  ⚠️ '{query[:40]}...' → 0 hits")

            logger.info("✅ Pipeline verified: Hybrid Search (Dense+BM25) + Rerank2 operational")

        except Exception as e:
            logger.warning(f"⚠️ Verification failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest 2026 Laws into Nuzantara RAG")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no ingestion")
    parser.add_argument("--file", type=str, help="Filter by filename (partial match)")
    args = parser.parse_args()

    asyncio.run(run_ingestion(dry_run=args.dry_run, file_filter=args.file))
