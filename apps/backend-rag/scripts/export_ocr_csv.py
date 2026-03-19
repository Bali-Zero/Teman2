"""Export OCR-extracted company data to CSV, aggregated by company."""

import asyncio
import csv
import json
import logging

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB = "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable"
OUT = "/tmp/drive_reorg/companies_ocr_extract.csv"


def format_people(people: list[dict]) -> str:
    """Format directors/commissioners list as string."""
    parts = []
    for p in people:
        name = p.get("name", "")
        pct = p.get("ownership_pct", 0)
        if name:
            parts.append(f"{name} ({pct}%)" if pct else name)
    return "; ".join(parts)


def format_kbli(codes: list) -> str:
    """Format KBLI codes list as string."""
    if not codes:
        return ""
    if isinstance(codes[0], dict):
        return ", ".join(c.get("code", "") for c in codes if c.get("code"))
    return ", ".join(str(c) for c in codes)


async def main() -> None:
    conn = await asyncpg.connect(DB)

    rows = await conn.fetch("""
        SELECT
            co.id as company_id,
            co.company_name,
            co.company_type,
            co.nib,
            co.npwp_company,
            co.akta_pendirian_no,
            co.akta_pendirian_date,
            co.sk_menhumkam_no,
            co.sk_menhumkam_date,
            co.registered_address,
            co.city,
            co.status,
            cd.id as doc_id,
            cd.document_type,
            cd.file_name,
            cd.ocr_extracted_data
        FROM company_documents cd
        JOIN companies co ON co.id = cd.company_id
        WHERE cd.ocr_status = 'completed'
            AND cd.ocr_extracted_data IS NOT NULL
        ORDER BY co.id, cd.id
    """)

    logger.info(f"Total OCR rows: {len(rows)}")

    # Aggregate by company
    companies: dict[int, dict] = {}
    for r in rows:
        cid = r["company_id"]
        raw = r["ocr_extracted_data"]
        ocr = json.loads(raw) if isinstance(raw, str) else raw

        if cid not in companies:
            companies[cid] = {
                "company_id": cid,
                "company_name": r["company_name"],
                "company_type": r["company_type"] or "",
                "nib": r["nib"] or "",
                "npwp_company": r["npwp_company"] or "",
                "akta_pendirian_no": str(r["akta_pendirian_no"] or ""),
                "akta_pendirian_date": str(r["akta_pendirian_date"] or ""),
                "sk_menhumkam_no": str(r["sk_menhumkam_no"] or ""),
                "sk_menhumkam_date": str(r["sk_menhumkam_date"] or ""),
                "registered_address_db": r["registered_address"] or "",
                "city": r["city"] or "",
                "status": r["status"] or "",
                # OCR fields (merged from all docs)
                "ocr_company_name": "",
                "notary_name": "",
                "deed_number": "",
                "deed_date": "",
                "directors": "",
                "commissioners": "",
                "authorized_capital": "",
                "paid_capital": "",
                "kbli_codes": "",
                "sk_number": "",
                "registered_address_ocr": "",
                "company_status_ocr": "",
                "docs_ocr_count": 0,
            }

        co = companies[cid]
        co["docs_ocr_count"] += 1

        # Merge: keep first non-empty
        if ocr.get("company_name") and not co["ocr_company_name"]:
            co["ocr_company_name"] = str(ocr["company_name"])
        if ocr.get("notary_name") and not co["notary_name"]:
            co["notary_name"] = str(ocr["notary_name"])
        if ocr.get("deed_number") and not co["deed_number"]:
            co["deed_number"] = str(ocr["deed_number"])
        if ocr.get("deed_date") and str(ocr["deed_date"]) != "YYYY-MM-DD" and not co["deed_date"]:
            co["deed_date"] = str(ocr["deed_date"])
        if ocr.get("directors") and not co["directors"]:
            co["directors"] = format_people(ocr["directors"])
        if ocr.get("commissioners") and not co["commissioners"]:
            co["commissioners"] = format_people(ocr["commissioners"])
        if ocr.get("authorized_capital") and not co["authorized_capital"]:
            val = ocr["authorized_capital"]
            if val and val != 0:
                co["authorized_capital"] = str(val)
        if ocr.get("paid_capital") and not co["paid_capital"]:
            val = ocr["paid_capital"]
            if val and val != 0:
                co["paid_capital"] = str(val)
        if ocr.get("kbli_codes") and not co["kbli_codes"]:
            co["kbli_codes"] = format_kbli(ocr["kbli_codes"])
        if ocr.get("sk_number") and not co["sk_number"]:
            co["sk_number"] = str(ocr["sk_number"])
        if ocr.get("registered_address") and not co["registered_address_ocr"]:
            co["registered_address_ocr"] = str(ocr["registered_address"])
        if ocr.get("company_status") and not co["company_status_ocr"]:
            co["company_status_ocr"] = str(ocr["company_status"])

    # Write CSV
    fields = list(list(companies.values())[0].keys())
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for co in sorted(companies.values(), key=lambda x: x["company_id"]):
            w.writerow(co)

    logger.info(f"Companies exported: {len(companies)}")
    logger.info(f"CSV saved: {OUT}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
