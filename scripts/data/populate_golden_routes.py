"""
Populate Golden Routes
Seeds the database with 50+ high-value canonical queries ("Golden Routes").
These routes map common user questions to specific documents and collections.
"""

import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

import asyncpg

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# from app.core.config import settings # Avoid Pydantic validation issues
DB_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- GOLDEN ROUTES DATA ---
# Format: (Canonical Query, [Collections], [Doc IDs], Hints)

ROUTES = [
    # --- VISA & IMMIGRATION ---
    (
        "How to get an Investor KITAS?",
        ["visa_oracle"],
        [],
        {"intent": "procedure", "entity": "visa_investor"},
    ),
    (
        "Requirements for KITAS E33",
        ["visa_oracle"],
        [],
        {"intent": "requirements", "entity": "visa_investor"},
    ),
    (
        "Cost of Investor KITAS",
        ["visa_oracle"],
        [],
        {"intent": "cost", "entity": "visa_investor"},
    ),
    (
        "Can I work with an Investor KITAS?",
        ["visa_oracle"],
        [],
        {"intent": "rights", "entity": "visa_investor"},
    ),
    (
        "How to apply for a Work KITAS?",
        ["visa_oracle"],
        [],
        {"intent": "procedure", "entity": "visa_work"},
    ),
    (
        "Requirements for Work Permit (IMTA)",
        ["visa_oracle"],
        [],
        {"intent": "requirements", "entity": "visa_work"},
    ),
    (
        "Retirement Visa requirements Indonesia",
        ["visa_oracle"],
        [],
        {"intent": "requirements", "entity": "visa_retirement"},
    ),
    (
        "Visa on Arrival cost and validity",
        ["visa_oracle"],
        [],
        {"intent": "info", "entity": "voa"},
    ),
    (
        "Second Home Visa requirements",
        ["visa_oracle"],
        [],
        {"intent": "requirements", "entity": "visa_second_home"},
    ),
    (
        "Golden Visa Indonesia benefits",
        ["visa_oracle"],
        [],
        {"intent": "benefits", "entity": "visa_golden"},
    ),
    # --- COMPANY REGISTRATION (PT PMA) ---
    (
        "Minimum capital for PT PMA",
        ["legal_unified"],
        [],
        {"intent": "requirements", "entity": "pt_pma"},
    ),
    (
        "How to set up a PT PMA in Indonesia?",
        ["legal_unified"],
        [],
        {"intent": "procedure", "entity": "pt_pma"},
    ),
    (
        "Can foreigners own 100% of a company?",
        ["legal_unified"],
        [],
        {"intent": "ownership", "entity": "pt_pma"},
    ),
    (
        "Negative Investment List (DNI) 2024",
        ["legal_unified"],
        [],
        {"intent": "restrictions", "entity": "pt_pma"},
    ),
    (
        "What is NIB and how to get it?",
        ["legal_unified"],
        [],
        {"intent": "info", "entity": "nib"},
    ),
    (
        "OSS registration process",
        ["legal_unified"],
        [],
        {"intent": "procedure", "entity": "oss"},
    ),
    (
        "Difference between PT PMA and PT Local",
        ["legal_unified"],
        [],
        {"intent": "comparison", "entity": "pt_pma"},
    ),
    (
        "Director and Commissioner requirements PT PMA",
        ["legal_unified"],
        [],
        {"intent": "requirements", "entity": "pt_pma"},
    ),
    (
        "Virtual office for PT PMA allowed?",
        ["legal_unified"],
        [],
        {"intent": "compliance", "entity": "pt_pma"},
    ),
    (
        "Closing a PT PMA (Liquidation)",
        ["legal_unified"],
        [],
        {"intent": "procedure", "entity": "pt_pma"},
    ),
    # --- TAXATION ---
    (
        "Corporate Income Tax rate Indonesia",
        ["tax_genius"],
        [],
        {"intent": "rate", "entity": "corporate_tax"},
    ),
    (
        "VAT (PPN) rate in Indonesia",
        ["tax_genius"],
        [],
        {"intent": "rate", "entity": "ppn"},
    ),
    (
        "Personal Income Tax rates (PPh 21)",
        ["tax_genius"],
        [],
        {"intent": "rate", "entity": "pph_21"},
    ),
    (
        "Withholding Tax (PPh 23) rates",
        ["tax_genius"],
        [],
        {"intent": "rate", "entity": "pph_23"},
    ),
    (
        "Tax for UMKM (0.5%)",
        ["tax_genius"],
        [],
        {"intent": "rate", "entity": "pph_final"},
    ),
    (
        "Tax treaty Indonesia Singapore",
        ["tax_genius"],
        [],
        {"intent": "treaty", "country": "singapore"},
    ),
    (
        "How to register for NPWP?",
        ["tax_genius"],
        [],
        {"intent": "procedure", "entity": "npwp"},
    ),
    (
        "Monthly tax reporting requirements",
        ["tax_genius"],
        [],
        {"intent": "compliance", "entity": "tax"},
    ),
    (
        "Annual Tax Return (SPT Tahunan) deadline",
        ["tax_genius"],
        [],
        {"intent": "deadline", "entity": "tax"},
    ),
    (
        "Tax on selling property in Indonesia",
        ["tax_genius"],
        [],
        {"intent": "rate", "entity": "property_tax"},
    ),
    # --- REAL ESTATE ---
    (
        "Can foreigners buy land in Indonesia?",
        ["legal_unified"],
        [],
        {"intent": "rights", "entity": "property"},
    ),
    (
        "Hak Pakai vs Hak Milik",
        ["legal_unified"],
        [],
        {"intent": "comparison", "entity": "property_right"},
    ),
    (
        "How to get Hak Guna Bangunan (HGB)?",
        ["legal_unified"],
        [],
        {"intent": "procedure", "entity": "hak_guna_bangunan"},
    ),
    (
        "Leasehold agreement for foreigners",
        ["legal_unified"],
        [],
        {"intent": "info", "entity": "leasehold"},
    ),
    (
        "Property ownership through PT PMA",
        ["legal_unified"],
        [],
        {"intent": "strategy", "entity": "pt_pma"},
    ),
    (
        "Nominee arrangement risks",
        ["legal_unified"],
        [],
        {"intent": "risk", "entity": "nominee"},
    ),
    # --- MANPOWER & LABOR ---
    (
        "Minimum wage Jakarta 2024",
        ["legal_unified"],
        [],
        {"intent": "rate", "entity": "wage"},
    ),
    (
        "Termination of employment (PHK) compensation",
        ["legal_unified"],
        [],
        {"intent": "calculation", "entity": "severance"},
    ),
    (
        "Maternity leave in Indonesia",
        ["legal_unified"],
        [],
        {"intent": "rights", "entity": "leave"},
    ),
    (
        "THR (Religious Holiday Allowance) calculation",
        ["legal_unified"],
        [],
        {"intent": "calculation", "entity": "thr"},
    ),
    (
        "Working hours regulation Indonesia",
        ["legal_unified"],
        [],
        {"intent": "regulation", "entity": "working_hours"},
    ),
    (
        "Outsourcing rules in Omnibus Law",
        ["legal_unified"],
        [],
        {"intent": "regulation", "entity": "outsourcing"},
    ),
    # --- KBLI (BUSINESS CLASSIFICATION) ---
    (
        "KBLI for Restaurant",
        ["legal_unified"],
        [],
        {"intent": "lookup", "entity": "kbli", "keyword": "restaurant"},
    ),
    (
        "KBLI for Software Development",
        ["legal_unified"],
        [],
        {"intent": "lookup", "entity": "kbli", "keyword": "software"},
    ),
    (
        "KBLI for Real Estate",
        ["legal_unified"],
        [],
        {"intent": "lookup", "entity": "kbli", "keyword": "real_estate"},
    ),
    (
        "KBLI for Management Consulting",
        ["legal_unified"],
        [],
        {"intent": "lookup", "entity": "kbli", "keyword": "consulting"},
    ),
    (
        "KBLI for Trading/Export-Import",
        ["legal_unified"],
        [],
        {"intent": "lookup", "entity": "kbli", "keyword": "trading"},
    ),
    (
        "How to find correct KBLI code?",
        ["legal_unified"],
        [],
        {"intent": "guide", "entity": "kbli"},
    ),
    # --- MISC ---
    (
        "Import tax for electronics",
        ["legal_unified"],
        [],
        {"intent": "rate", "entity": "import_tax"},
    ),
    (
        "Social Security (BPJS) for foreigners",
        ["legal_unified"],
        [],
        {"intent": "requirements", "entity": "bpjs"},
    ),
    (
        "Divorce law for mixed marriage",
        ["legal_unified"],
        [],
        {"intent": "law", "entity": "marriage"},
    ),
    (
        "Prenuptial agreement Indonesia",
        ["legal_unified"],
        [],
        {"intent": "info", "entity": "prenup"},
    ),
    # --- LOCAL ROUTES (INDONESIAN MARKET) ---
    # 1. Labor
    (
        "Cara hitung pesangon PHK",
        ["legal_unified"],
        [],
        {"intent": "calculation", "entity": "severance"},
    ),
    (
        "Hak cuti melahirkan karyawan",
        ["legal_unified"],
        [],
        {"intent": "rights", "entity": "maternity_leave"},
    ),
    (
        "Aturan jam kerja lembur Omnibus Law",
        ["legal_unified"],
        [],
        {"intent": "regulation", "entity": "overtime"},
    ),
    (
        "Cara klaim JHT BPJS Ketenagakerjaan",
        ["legal_unified"],
        [],
        {"intent": "procedure", "entity": "bpjs_claim"},
    ),
    (
        "PHK sepihak tanpa peringatan",
        ["legal_unified", "litigation_oracle"],
        [],
        {"intent": "rights", "entity": "unfair_dismissal"},
    ),
    # 2. Land & Property
    (
        "Cara cek sertifikat tanah asli atau palsu",
        ["property_unified"],
        [],
        {"intent": "procedure", "entity": "verify_land"},
    ),
    (
        "Biaya balik nama sertifikat tanah",
        ["property_unified"],
        [],
        {"intent": "cost", "entity": "title_transfer"},
    ),
    (
        "Sengketa tanah sertifikat ganda",
        ["litigation_oracle"],
        [],
        {"intent": "dispute", "entity": "double_cert"},
    ),
    (
        "Mengurus sertifikat tanah hilang",
        ["property_unified"],
        [],
        {"intent": "procedure", "entity": "lost_cert"},
    ),
    (
        "Perbedaan SHM dan HGB",
        ["property_unified"],
        [],
        {"intent": "comparison", "entity": "shm_hgb"},
    ),
    # 3. Family Law
    (
        "Syarat gugatan cerai di Pengadilan Agama",
        ["legal_unified", "litigation_oracle"],
        [],
        {"intent": "procedure", "entity": "divorce_islamic"},
    ),
    (
        "Pembagian harta gono-gini",
        ["litigation_oracle"],
        [],
        {"intent": "rights", "entity": "marital_assets"},
    ),
    (
        "Hak asuh anak setelah bercerai",
        ["litigation_oracle"],
        [],
        {"intent": "rights", "entity": "child_custody"},
    ),
    (
        "Hukum waris Islam vs Perdata",
        ["legal_unified"],
        [],
        {"intent": "comparison", "entity": "inheritance_law"},
    ),
    (
        "Cara buat surat wasiat yang sah",
        ["legal_unified"],
        [],
        {"intent": "procedure", "entity": "will"},
    ),
    # 4. Local Business
    (
        "Cara mendirikan PT Perorangan",
        ["legal_unified"],
        [],
        {"intent": "procedure", "entity": "pt_perorangan"},
    ),
    (
        "Pajak UMKM 0.5% syaratnya apa?",
        ["tax_genius"],
        [],
        {"intent": "requirements", "entity": "umkm_tax"},
    ),
    (
        "Izin edar BPOM untuk makanan",
        ["legal_unified"],
        [],
        {"intent": "procedure", "entity": "bpom"},
    ),
    (
        "Daftar merek HAKI online",
        ["legal_unified"],
        [],
        {"intent": "procedure", "entity": "trademark"},
    ),
    (
        "Syarat sertifikasi Halal gratis (Sehati)",
        ["legal_unified"],
        [],
        {"intent": "requirements", "entity": "halal_free"},
    ),
    # 5. Criminal & Litigation
    (
        "Hukum pencemaran nama baik di sosmed (UU ITE)",
        ["legal_unified", "litigation_oracle"],
        [],
        {"intent": "law", "entity": "defamation"},
    ),
    (
        "Penipuan investasi bodong lapor kemana?",
        ["litigation_oracle"],
        [],
        {"intent": "procedure", "entity": "fraud_report"},
    ),
    (
        "Ancaman hukuman penggelapan uang perusahaan",
        ["legal_unified", "litigation_oracle"],
        [],
        {"intent": "penalty", "entity": "embezzlement"},
    ),
    (
        "Wanprestasi vs Penipuan bedanya apa?",
        ["litigation_oracle"],
        [],
        {"intent": "comparison", "entity": "civil_vs_criminal"},
    ),
    (
        "Prosedur pelaporan polisi (LP)",
        ["legal_unified"],
        [],
        {"intent": "procedure", "entity": "police_report"},
    ),
    # 6. Immigration (Local Perspective)
    (
        "Syarat menjadi sponsor KITAS WNA",
        ["visa_oracle"],
        [],
        {"intent": "requirements", "entity": "sponsor_kitas"},
    ),
    (
        "Hukuman overstay bagi WNA",
        ["visa_oracle"],
        [],
        {"intent": "penalty", "entity": "overstay"},
    ),
    (
        "Cara mengurus KITAP ikut istri WNI",
        ["visa_oracle"],
        [],
        {"intent": "procedure", "entity": "kitap_spouse"},
    ),
    (
        "Anak berkewarganegaraan ganda (Affidavit)",
        ["visa_oracle"],
        [],
        {"intent": "procedure", "entity": "dual_citizenship"},
    ),
    # 7. Tax (Local Perspective)
    (
        "Tarif PPh 21 terbaru (TER)",
        ["tax_genius"],
        [],
        {"intent": "rate", "entity": "pph21"},
    ),
    (
        "Cara hitung PPh 23 jasa konsultan",
        ["tax_genius"],
        [],
        {"intent": "calculation", "entity": "pph23"},
    ),
    (
        "Syarat Pengusaha Kena Pajak (PKP)",
        ["tax_genius"],
        [],
        {"intent": "requirements", "entity": "pkp"},
    ),
    (
        "Sanksi tidak lapor realisasi investasi",
        ["tax_genius"],
        [],
        {"intent": "penalty", "entity": "investment_report"},
    ),
    # --- GENERIC TEMPLATES (DYNAMIC ROUTING) ---
    # These templates allow the AI to handle ANY Visa or KBLI not explicitly listed above.
    (
        "Requirements for [Visa Type]",
        ["visa_oracle"],
        [],
        {"intent": "requirements", "entity": "visa_generic"},
    ),
    (
        "Cost of [Visa Type]",
        ["visa_oracle"],
        [],
        {"intent": "cost", "entity": "visa_generic"},
    ),
    (
        "Procedure for [Visa Type]",
        ["visa_oracle"],
        [],
        {"intent": "procedure", "entity": "visa_generic"},
    ),
    (
        "Can I work with [Visa Type]?",
        ["visa_oracle"],
        [],
        {"intent": "rights", "entity": "visa_generic"},
    ),
    (
        "KBLI for [Business Activity]",
        ["legal_unified"],
        [],
        {"intent": "lookup", "entity": "kbli_generic"},
    ),
    (
        "Foreign ownership for KBLI [Code]",
        ["legal_unified"],
        [],
        {"intent": "ownership", "entity": "kbli_generic"},
    ),
    (
        "Capital requirements for KBLI [Code]",
        ["legal_unified"],
        [],
        {"intent": "requirements", "entity": "kbli_generic"},
    ),
    (
        "Tax rate for [Income Type]",
        ["tax_genius"],
        [],
        {"intent": "rate", "entity": "tax_generic"},
    ),
    (
        "Legal basis for [Topic]",
        ["legal_unified"],
        [],
        {"intent": "law", "entity": "legal_generic"},
    ),
]


async def populate_routes():
    """Populate Golden Routes"""
    db_url = DB_URL
    if not db_url:
        logger.error("❌ DATABASE_URL not set")
        return

    try:
        pool = await asyncpg.create_pool(db_url)
        async with pool.acquire() as conn:
            logger.info("🧹 Cleaning old Golden Routes...")
            await conn.execute("TRUNCATE TABLE golden_routes CASCADE")

            logger.info(f"🌟 Seeding {len(ROUTES)} Golden Routes...")
            for query, collections, doc_ids, hints in ROUTES:
                route_id = f"route_{uuid.uuid4().hex[:8]}"
                await conn.execute(
                    """
                    INSERT INTO golden_routes (
                        route_id, canonical_query, collections, document_ids, routing_hints, usage_count
                    ) VALUES ($1, $2, $3, $4, $5, 0)
                """,
                    route_id,
                    query,
                    collections,
                    doc_ids,
                    json.dumps(hints),
                )

        logger.info("✅ Golden Routes populated successfully!")
        await pool.close()

    except Exception as e:
        logger.error(f"❌ Error populating Golden Routes: {e}")


if __name__ == "__main__":
    asyncio.run(populate_routes())
