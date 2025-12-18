"""
Populate Golden Routes (Simple)
"""

import asyncio
import json
import uuid

import asyncpg

ROUTES = [
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
]


async def populate():
    db_url = "postgres://localhost:5432/nuzantara_dev"
    print(f"Connecting to {db_url}...")
    try:
        conn = await asyncpg.connect(db_url)

        print("Cleaning old Golden Routes...")
        await conn.execute("TRUNCATE TABLE golden_routes CASCADE")

        print(f"Seeding {len(ROUTES)} Golden Routes...")
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

        await conn.close()
        print("✅ Golden Routes Populated")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(populate())
