#!/usr/bin/env python3
"""
Migration 128: the live `visa_types` E28 rows say only what the official Imigrasi
pages say (audit `research/visa/2026-10-15-e28-family-audit.md` F70-F74; PR C2).

Served today by `get_visa_details` (MCP) / `GET /api/knowledge/visa/code/{code}`:
  - E28B "Investasi minimal Rp 2.5 miliar" (the page says USD 2.5M / 5M), name "Golden Visa 5Y"
  - E28C missing the 10-year tier; "Dilarang bekerja" and "Tidak perlu mendirikan PT PMA" are not on the page
  - E28F/E28D without thresholds; E28A documents "Passport photo 4x6 red background" and
    "Return/onward ticket" that the page does not list, the page's bank statement / CV /
    itinerary / application letter missing, document lines filed under `allowed_activities`
  - E28A `cost_visa` "17.000.000 - 19.000.000 IDR" (a range spanning two products)
  - E28G "Golden Visa 10Y / Investasi Rp 5 miliar+" — not a current visa (no official page,
    not in the signed rulepack).

Sources (saved page texts, fetched 2026-10-15): `research/visa/2026-10-15-e28-pages/text/`.
Owner rulings 2026-10-15: E28A is sold as 2 years only; Investor KITAS 17.000.000 (offshore)
/ 19.000.000 (onshore) all-inclusive; E28B-F are handled at a price on consultation; the
"7-10 working days" processing window stays; E28G is not a current visa.

Field placement (the API exposes `requirements`, `restrictions`, `allowed_activities`, not
`description`): `requirements` = the page's document list plus its "Persyaratan khusus"
(thresholds, stated once per row); `allowed_activities` = what the page allows, no
documents; `restrictions` = the page's "Kegiatan yang dilarang". No PNBP amount is written
anywhere: one all-inclusive client price per product, never a government-fee split.

`cost_visa` for E28A: the labelled pair "IDR 17.000.000 (offshore) / IDR 19.000.000
(onshore), all-inclusive". It is not a range (no "17-19" span): each number is bound to its
own scenario, the two catalogue products "Investor KITAS 2 Years (Offshore)" and "(Altus/
Onshore)". Writing only the offshore price would under-quote an onshore client.

E28G: the router (`app/routers/knowledge_visa.py`) does `SELECT * FROM visa_types` with no
status / hidden / retired / active filter, and the MCP tools call it verbatim, so there is
NO retire mechanism today. The row is therefore rewritten to say it is not a current visa
and to point to E28B / E28C, with no threshold. A real retire flag in the router is a
separate change.

`name` is written for E28B, E28C and E28G only, and the seed script
(`scripts/seed_visa_types_complete_2026.py`) carries the same names, as
`test_visa_types_seed_vs_migration_tripwire.py` requires. E28D / E28F names are untouched
(migration_126 / migration_125 stay the latest word on them).

Idempotent: each UPDATE is guarded by `IS DISTINCT FROM` on every field it sets; a re-run is
a 0-row no-op per code. Same manual pattern as migration_126 (not the `migrations_v2/*.sql`
runner). Run (prod, deployed container already has DATABASE_URL):
    cat migration_128_fix_e28_family_rows.py | \
      fly ssh console -a nuzantara-rag -C "python3 -"

Cache: `visa_types` reads are cached under `zantara:knowledge_visa:*`; a direct UPDATE does
not invalidate it, so after applying, invalidate that namespace (see migration_126) or the
old rows are served until TTL expiry. Applying is the orchestrator's job, not this script's.
"""

import asyncio
import logging
import os

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kept a pure literal (ast.literal_eval-parseable by
# test_visa_types_seed_vs_migration_tripwire.py: it reads VISA_FIXES off disk without importing).
VISA_FIXES = {
    "E28A": {
        "duration": "2 years",
        "cost_visa": "IDR 17.000.000 (offshore) / IDR 19.000.000 (onshore), all-inclusive",
        "processing_time_normal": "7-10 working days",
        "requirements": [
            "Sponsor required (the investment company)",
            "Visa application letter",
            "Passport valid at least 6 months before expiry",
            "Bank statement of the last 3 months in the foreigner's or sponsor's name, minimum USD 2,000 or equivalent",
            "Recent colour passport photo (within the last year)",
            "Curriculum vitae (CV)",
            "Itinerary",
            "Proof of the applicant's own shareholding of at least Rp10.000.000.000 in the sponsoring company, registered with the Ministry of Investment/BKPM",
            "If the shareholding is lower and the applicant holds a director or commissioner position, a work visa for that position must be applied for instead",
            "Ministry of Law decree approving the company's establishment",
            "Company current account statements for the last 2 months (a company set up less than 2 months ago may file them at the immigration office within 90 days after the ITAS is issued)"
        ],
        "restrictions": [
            "No overstay allowed",
            "Work must match permit type",
            "No sales of goods/services except as required for work"
        ],
        "allowed_activities": [
            "Invest and carry out business- and investment-related activities, including company establishment",
            "Serve as director or commissioner of the company in which the foreigner has invested",
            "Supervise the production of goods or services at the company (office, factory or similar site)",
            "Bring family to live in Indonesia",
            "Exit and re-enter Indonesia while the Re-entry Permit is valid",
            "Education through the Residence Permit Rangkap Kegiatan mechanism",
            "Tourism, shopping and visiting friends or family"
        ]
    },
    "E28B": {
        "name": "E28B - Investor Golden Visa (Company Establishment)",
        "duration": "5 or 10 years",
        "cost_visa": "Contact for Quote",
        "requirements": [
            "Paspor kebangsaan yang sah dan masih berlaku paling singkat 6 bulan sebelum masa berlakunya habis",
            "Rekening koran 3 bulan terakhir atas nama Orang Asing atau penjamin, minimal US$2.000 atau setara",
            "Pasfoto berwarna terbaru (setahun terakhir)",
            "Daftar riwayat hidup (CV)",
            "Rincian perjalanan (itinerary)",
            "Tidak membutuhkan penjamin/sponsor",
            "Bukti kepemilikan saham pada perusahaan di luar Indonesia yang tercantum dalam laporan audit keuangan perusahaan induk dari kantor akuntan publik berstandar internasional",
            "Bukti nilai omzet/penjualan di perusahaan luar negeri dalam laporan keuangan yang telah diaudit menurut standar internasional",
            "Pernyataan komitmen mendirikan perusahaan di Indonesia dengan modal ditempatkan (saham) atau nilai investasi paling sedikit US$2.500.000 (masa tinggal 5 tahun) atau US$5.000.000 (masa tinggal 10 tahun), dipenuhi dalam 90 hari sejak tanggal masuk ke Indonesia"
        ],
        "restrictions": [
            "Tinggal di wilayah Indonesia melebihi masa berlaku izin tinggal",
            "Melakukan pekerjaan yang tidak sesuai dengan jenis izin tinggal",
            "Melakukan kegiatan yang tidak sesuai dengan uraian kegiatan dan hak yang diberikan, kecuali telah mengajukan perubahan atau pengajuan rangkap jenis kegiatan"
        ],
        "allowed_activities": [
            "Berinvestasi dan melakukan aktivitas yang berhubungan dengan bisnis, investasi, dan pendirian perusahaan",
            "Menjabat sebagai anggota direksi atau anggota dewan komisaris pada perusahaan tempat investasi ditanamkan",
            "Mengawasi proses produksi barang atau jasa di perusahaan yang didirikan (kantor, pabrik, atau tempat sejenis)",
            "Membawa keluarga untuk tinggal di Indonesia",
            "Keluar-masuk Indonesia selama Izin Masuk Kembali masih berlaku",
            "Mengikuti pendidikan melalui mekanisme Rangkap Kegiatan Izin Tinggal",
            "Melakukan aktivitas wisata, pembelian barang, serta mengunjungi teman atau keluarga",
            "Menerima imbalan atau fasilitas atas investasi yang ditanamkan"
        ]
    },
    "E28C": {
        "name": "E28C - Investor Golden Visa (Capital Market)",
        "duration": "5 or 10 years",
        "cost_visa": "Contact for Quote",
        "requirements": [
            "Paspor kebangsaan yang sah dan masih berlaku paling singkat 6 bulan sebelum masa berlakunya habis",
            "Rekening koran 3 bulan terakhir atas nama Orang Asing atau penjamin, minimal US$2.000 atau setara",
            "Pasfoto berwarna terbaru (setahun terakhir)",
            "Daftar riwayat hidup (CV)",
            "Rincian perjalanan (itinerary)",
            "Tidak membutuhkan penjamin/sponsor",
            "Bukti kepemilikan obligasi pemerintah Indonesia, saham pada perusahaan terbuka di Indonesia, atau reksadana paling sedikit US$350.000 (masa tinggal 5 tahun)",
            "Masa tinggal 10 tahun: bukti kepemilikan obligasi pemerintah Indonesia, saham pada perusahaan terbuka di Indonesia, atau reksadana paling sedikit US$700.000; atau bukti kepemilikan rumah susun/apartemen senilai paling sedikit US$1.000.000"
        ],
        "restrictions": [
            "Tinggal di wilayah Indonesia melebihi masa berlaku izin tinggal",
            "Melakukan pekerjaan yang tidak sesuai dengan jenis izin tinggal",
            "Melakukan kegiatan yang tidak sesuai dengan uraian kegiatan dan hak yang diberikan, kecuali telah mengajukan perubahan atau pengajuan rangkap jenis kegiatan"
        ],
        "allowed_activities": [
            "Berinvestasi dan melakukan aktivitas yang berhubungan dengan bisnis dan investasi",
            "Membawa keluarga untuk tinggal di Indonesia",
            "Keluar-masuk Indonesia selama Izin Masuk Kembali masih berlaku",
            "Melakukan aktivitas wisata, pembelian barang, serta mengunjungi teman atau keluarga",
            "Menerima imbalan atau fasilitas atas investasi yang ditanamkan"
        ]
    },
    "E28D": {
        "duration": "5 or 10 years",
        "cost_visa": "Contact for Quote",
        "requirements": [
            "Paspor kebangsaan yang sah dan masih berlaku paling singkat 6 bulan sebelum masa berlakunya habis",
            "Rekening koran 3 bulan terakhir atas nama Orang Asing atau penjamin, minimal US$2.000 atau setara",
            "Pasfoto berwarna terbaru (setahun terakhir)",
            "Daftar riwayat hidup (CV)",
            "Rincian perjalanan (itinerary)",
            "Tidak membutuhkan penjamin/sponsor",
            "Pernyataan komitmen bahwa perusahaan asing (induk) akan menanamkan investasi paling sedikit US$25.000.000 (masa tinggal 5 tahun) atau US$50.000.000 (masa tinggal 10 tahun), dipenuhi dalam 90 hari sejak tanggal masuk ke Indonesia"
        ],
        "restrictions": [
            "Tinggal di wilayah Indonesia melebihi masa berlaku izin tinggal",
            "Melakukan pekerjaan yang tidak sesuai dengan jenis izin tinggal",
            "Melakukan kegiatan yang tidak sesuai dengan uraian kegiatan dan hak yang diberikan, kecuali telah mengajukan perubahan atau pengajuan rangkap jenis kegiatan"
        ],
        "allowed_activities": [
            "Menjabat sebagai anggota direksi atau anggota dewan komisaris pada perusahaan cabang/anak perusahaan yang didirikan di Indonesia",
            "Berinvestasi dan melakukan aktivitas yang berhubungan dengan bisnis, investasi, dan pendirian perusahaan, termasuk pembahasan, negosiasi, dan/atau penandatanganan perjanjian bisnis",
            "Mengawasi proses produksi barang atau jasa di perusahaan yang didirikan (kantor, pabrik, atau tempat sejenis)",
            "Membawa keluarga untuk tinggal di Indonesia",
            "Keluar-masuk Indonesia selama Izin Masuk Kembali masih berlaku",
            "Melakukan aktivitas wisata, pembelian barang, serta mengunjungi teman atau keluarga",
            "Menerima imbalan atau fasilitas atas investasi yang ditanamkan"
        ]
    },
    "E28F": {
        "duration": "5 or 10 years",
        "cost_visa": "Contact for Quote",
        "requirements": [
            "Paspor kebangsaan yang sah dan masih berlaku paling singkat 6 bulan sebelum masa berlakunya habis",
            "Rekening koran 3 bulan terakhir atas nama Orang Asing atau penjamin, minimal US$2.000 atau setara",
            "Pasfoto berwarna terbaru (setahun terakhir)",
            "Daftar riwayat hidup (CV)",
            "Rincian perjalanan (itinerary)",
            "Tidak membutuhkan penjamin/sponsor",
            "Pernyataan komitmen bahwa perusahaan asing (induk) akan menanamkan investasi paling sedikit US$5.000.000 (masa tinggal 5 tahun) atau US$10.000.000 (masa tinggal 10 tahun), dipenuhi dalam 90 hari sejak tanggal masuk ke Indonesia"
        ],
        "restrictions": [
            "Tinggal di wilayah Indonesia melebihi masa berlaku izin tinggal",
            "Melakukan pekerjaan yang tidak sesuai dengan jenis izin tinggal",
            "Melakukan kegiatan yang tidak sesuai dengan uraian kegiatan dan hak yang diberikan, kecuali telah mengajukan perubahan atau pengajuan rangkap jenis kegiatan"
        ],
        "allowed_activities": [
            "Menjabat sebagai anggota direksi atau anggota dewan komisaris pada perusahaan cabang/anak perusahaan yang didirikan di Ibu Kota Nusantara",
            "Berinvestasi dan melakukan aktivitas yang berhubungan dengan bisnis, investasi, dan pendirian perusahaan, termasuk pembahasan, negosiasi, dan/atau penandatanganan perjanjian bisnis",
            "Mengawasi proses produksi barang atau jasa di perusahaan yang didirikan (kantor, pabrik, atau tempat sejenis)",
            "Membawa keluarga untuk tinggal di Indonesia",
            "Keluar-masuk Indonesia selama Izin Masuk Kembali masih berlaku",
            "Melakukan aktivitas wisata, pembelian barang, serta mengunjungi teman atau keluarga",
            "Menerima imbalan atau fasilitas atas investasi yang ditanamkan"
        ]
    },
    "E28G": {
        "name": "E28G - Not a current visa (see E28B or E28C)",
        "duration": "Not applicable",
        "cost_visa": "Not applicable",
        "extensions": None,
        "total_stay": None,
        "processing_time_normal": None,
        "processing_time_express": None,
        "requirements": [
            "E28G is not a current Indonesian investor visa: it has no official Imigrasi page. For a long-stay investor visa see E28A (investor KITAS), E28B (Golden Visa, company establishment) or E28C (Golden Visa, capital market)"
        ],
        "restrictions": [],
        "allowed_activities": [],
        "benefits": [],
        "process_steps": [],
        "tips": []
    }
}


async def run_migration() -> bool:
    """Returns True iff every code in VISA_FIXES ended in a known-good state
    (updated this run, or already-applied). False on ANY error or missing
    row — the caller turns that into a non-zero exit code so a `fly ssh`
    run that silently failed does not look identical to success (the
    "SKIP: not found, or already at target" ambiguity migration_125 itself
    had — this version distinguishes the two and treats "not found" as an
    error, not a routine skip: a missing row means a typo'd code or the
    wrong database, and staying quiet about that is exactly the kind of gap
    this migration exists to close for E28D).
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        return False

    conn = await asyncpg.connect(db_url)
    logger.info("Connected to database")

    updated = 0
    already_applied = 0
    errors = 0
    try:
        for code, data in VISA_FIXES.items():
            # allowed_activities/restrictions/name are native Postgres
            # text[]/varchar columns (same schema migration_125 verified
            # live 2026-07-19) — asyncpg maps Python list -> text[]
            # directly, no jsonb cast needed.
            set_clauses = []
            values = []
            idx = 1
            for field, value in data.items():
                set_clauses.append(f"{field} = ${idx}")
                values.append(value)
                idx += 1
            set_clauses.append("last_updated = NOW()")

            # Idempotency guard: touch the row if ANY of the fields we set
            # still differs from its target value — not just `name`. A
            # name-only guard would silently skip a row that has the right
            # name but stale allowed_activities/restrictions (e.g. a prior
            # partial hand-fix), which is the same "looks fixed, wasn't"
            # shape this migration exists to close.
            distinct_clauses = [f"{field} IS DISTINCT FROM ${i + 1}" for i, field in enumerate(data)]
            code_idx = idx
            values.append(code)

            query = f"""
                UPDATE visa_types
                SET {", ".join(set_clauses)}
                WHERE code = ${code_idx} AND ({" OR ".join(distinct_clauses)})
                RETURNING code, name
            """
            try:
                row = await conn.fetchrow(query, *values)
                if row:
                    logger.info(f"OK {code}: {row['name']}")
                    updated += 1
                else:
                    exists = await conn.fetchval(
                        "SELECT 1 FROM visa_types WHERE code = $1", code
                    )
                    if exists:
                        logger.info(
                            f"NO-OP {code}: row already matches every target field "
                            "(idempotent re-run)"
                        )
                        already_applied += 1
                    else:
                        logger.error(
                            f"MISSING {code}: no row in visa_types for this code — "
                            "typo'd code, wrong database, or the row was deleted. "
                            "This is NOT the routine no-op case."
                        )
                        errors += 1
            except Exception as e:
                logger.error(f"ERROR {code}: {e}")
                errors += 1
    finally:
        await conn.close()

    logger.info(
        f"Migration complete: {updated} updated, {already_applied} already-applied, "
        f"{errors} error(s) out of {len(VISA_FIXES)} code(s)"
    )
    return errors == 0


if __name__ == "__main__":
    import sys

    ok = asyncio.run(run_migration())
    sys.exit(0 if ok else 1)
