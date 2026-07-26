#!/usr/bin/env python3
"""
Migration 125: Data-hygiene fix for 8 visa_types rows (E31F/E31G/E23A/E28F/E29/
E32C/E32D/E31J) — task #25.

Problem: live visa_types rows for these 8 codes described the WRONG topic
entirely (not just a swapped label) or carried stale legal language:

  - E31F ("Spouse KITAS — KITAP Holder Spouse") and E31G ("Dependent KITAS —
    KITAP Holder Child") actually describe E31B/E31E's topics. Verified via
    raw-HTML fetch (browser UA, bypassing the AI-summarization layer that
    drops <h2> titles) of imigrasi.go.id/wna/daftar-visa-indonesia/{code}:
    E31F's own H1 = "Visa Keluarga Anak Dengan Orang Tua WNI" (child with an
    Indonesian-citizen parent); E31G's own H1 = "Visa Keluarga Orang Tua dari
    Anak WNI" (parent of an Indonesian-citizen child). Both require a
    sponsor per their own "Penjamin (Sponsor)" section.
  - E23A allowed_activities carried stale "Wajib RPTKA dan IMTA" — IMTA was
    abolished by PP 34/2021 Pasal 6, replaced by "Pengesahan RPTKA" as the
    sole work-authorization mechanic (independently corroborated same day
    in the GARUDA-KITAS-WORKING-E23 CHATKB Perpres-sweep fix, same legal
    citation).
  - E28F said "Investor KITAS (Real Estate)" — wrong topic entirely. Raw
    HTML confirms official H1 = "Visa Investor Pendirian Cabang atau Anak
    Perusahaan di Ibu Kota Nusantara" (IKN new-capital branch/subsidiary
    investor visa for a director/commissioner role), zero relation to real
    estate.
  - E29's `name` said "Investor KITAS (Variant)" while its own
    allowed_activities already (correctly) described research — an
    internal name/content contradiction. Raw HTML confirms official H1 =
    "Visa Kerja Peneliti" (Working Visa — Researcher).
  - E32C/E32D shared IDENTICAL generic allowed_activities despite being
    genuinely different: raw HTML confirms E32C ("Visa Repatriasi 2 Tahun")
    requires a sponsor, E32D ("Visa Repatriasi 1 Tahun") does not — a
    literal opposite on the one differentiating fact. Live `name` fields
    also introduced an unverified "Child" framing not present in either
    official title.
  - E31J's `name`/allowed_activities were generic ("Dependent KITAS
    (Variant)"). Raw HTML confirms official H1 = "Visa Keluarga Anak yang
    Bergabung dengan Saudara Kandung Pemegang ITAS/ITAP" (child joining a
    sibling ITAS/ITAP holder), sponsor required.

Explicitly OUT of scope (verified, not touched):
  - C2's cost_visa (3.6M) — task's premise was wrong. 3.6M is PricingTool's
    current, deliberate, all-inclusive service price for "C2 Business"
    (verified via search_service_pricing), matching Golden Rule #11
    (PricingTool is the sole price SSOT) and the "one client-facing price,
    no PNBP-split" ruling. 2M is merely the bare government PNBP fee (also
    independently verified via raw HTML) — a different, non-conflicting
    fact. Not a hygiene bug; no change made.
  - E32D's "Golden Visa" name suffix — this suffix is a repeated, deliberate
    convention across many unrelated codes in the seed script (E28D,
    E33-family, Second-Home-family), i.e. a program-classification tag, not
    a per-page title claim. A separate arbiter pass (contested.md, same
    session) already investigated and rejected the narrower claim that the
    WORDS "Golden Visa" appear on E32D's own page title — that is a
    different question from the classification tag and is out of this
    migration's scope.

Ground truth source: raw HTML fetch (browser User-Agent) of each code's own
imigrasi.go.id detail page — the task's own mandated method, since the
AI-summarized/WebFetch-simplified layer structurally drops <h2> titles and
the "Penjamin (Sponsor)" section on these pages.

Run (prod, via the deployed container which already has DATABASE_URL):
    cat migration_125_fix_visa_family_descendant_hygiene.py | \
      fly ssh console -a nuzantara-rag -C "python3 -"
"""

import asyncio
import logging
import os

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Fields updated per code: name, description, allowed_activities, and (only
# where a definitively topic-mismatched restriction existed) restrictions.
# cost_visa / category / duration / requirements / benefits are untouched.
VISA_FIXES = {
    "E31F": {
        "name": "Family Visa Anak Dengan Orang Tua WNI",
        "allowed_activities": [
            "Anak dengan orang tua Warga Negara Indonesia (WNI)",
            "Membutuhkan penjamin/sponsor untuk pengajuan visa",
            "Tinggal bersama keluarga di Indonesia",
        ],
        "restrictions": ["No work without separate permit"],
    },
    "E31G": {
        "name": "Family Visa Parent of Indonesian Child",
        "allowed_activities": [
            "Orang tua dari anak Warga Negara Indonesia (WNI)",
            "Membutuhkan penjamin/sponsor untuk pengajuan visa",
            "Tinggal bersama anak di Indonesia",
        ],
        "restrictions": ["No work permitted"],
    },
    "E23A": {
        "allowed_activities": [
            "Bekerja di Kawasan Ekonomi Khusus (KEK)",
            "Fasilitas khusus untuk KEK",
            "Wajib Pengesahan RPTKA (IMTA telah dihapus, digantikan Pengesahan RPTKA sejak PP 34/2021 Pasal 6)",
        ],
    },
    "E28F": {
        "name": "Investor Visa Pendirian Cabang atau Anak Perusahaan di Indonesian New Capital (IKN)",
        "allowed_activities": [
            "Menjabat sebagai direksi atau komisaris pada perusahaan cabang/anak perusahaan yang didirikan di Ibu Kota Nusantara (IKN)",
            "Berinvestasi dan melakukan aktivitas bisnis terkait pendirian perusahaan",
            "Melakukan pembahasan, negosiasi, dan/atau menandatangani perjanjian bisnis",
        ],
        "restrictions": [],
    },
    "E29": {
        "name": "Working Visa Researcher",
        "allowed_activities": [
            "Melakukan kegiatan yang berkaitan dengan proyek penelitian",
            "Wajib izin dari Badan Riset dan Inovasi Nasional (BRIN)",
            "Dapat membawa anggota keluarga untuk tinggal di Indonesia",
            "Membutuhkan penjamin/sponsor dari institusi penelitian",
        ],
    },
    "E32C": {
        "name": "Repatriation Visa 2 Tahun",
        "allowed_activities": [
            "Untuk eks WNI atau keturunan WNI",
            "Masa tinggal maksimal 2 tahun",
            "Membutuhkan penjamin/sponsor untuk pengajuan visa",
            "Dapat bekerja dengan izin tambahan",
        ],
    },
    "E32D": {
        "name": "Repatriation Visa 1 Tahun Golden Visa",
        "allowed_activities": [
            "Untuk eks WNI atau keturunan WNI",
            "Masa tinggal maksimal 1 tahun",
            "Tidak membutuhkan penjamin/sponsor untuk pengajuan visa",
            "Dapat bekerja dengan izin tambahan",
        ],
    },
    "E31J": {
        "name": "Family Visa Anak yang Bergabung dengan Saudara Kandung Pemegang ITAS/ITAP",
        "allowed_activities": [
            "Anak yang bergabung dengan saudara kandung pemegang ITAS/ITAP",
            "Membutuhkan penjamin/sponsor untuk pengajuan visa",
            "Tinggal dan menempuh pendidikan di Indonesia",
        ],
    },
}


async def run_migration() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        return

    conn = await asyncpg.connect(db_url)
    logger.info("Connected to database")

    updated = 0
    for code, data in VISA_FIXES.items():
        # allowed_activities/restrictions/name etc. are native Postgres
        # text[]/varchar columns (verified live via information_schema,
        # 2026-07-19) — asyncpg maps Python list -> text[] directly, no
        # jsonb cast needed (that cast is only correct for the jsonb
        # columns cost_details/processing_timeline/metadata, none of which
        # this migration touches).
        set_clauses = []
        values = []
        idx = 1
        for field, value in data.items():
            set_clauses.append(f"{field} = ${idx}")
            values.append(value)
            idx += 1
        set_clauses.append("last_updated = NOW()")
        values.append(code)

        query = f"""
            UPDATE visa_types
            SET {", ".join(set_clauses)}
            WHERE code = ${idx}
            RETURNING code, name
        """
        try:
            row = await conn.fetchrow(query, *values)
            if row:
                logger.info(f"OK {code}: {row['name']}")
                updated += 1
            else:
                logger.warning(f"SKIP {code}: not found in database")
        except Exception as e:
            logger.error(f"ERROR {code}: {e}")

    await conn.close()
    logger.info(f"Migration complete: {updated} visa types updated")


if __name__ == "__main__":
    asyncio.run(run_migration())
