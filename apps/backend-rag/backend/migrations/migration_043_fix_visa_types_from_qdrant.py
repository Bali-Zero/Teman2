#!/usr/bin/env python3
"""
Migration 043: Fix visa_types with correct data from Qdrant visa_oracle collection.

Problem: visa_types table had garbage data (e.g., E28A had "6 months passport, return ticket"
         instead of "Rp 10 billion share ownership").

Solution: Populated allowed_activities, restrictions, process_steps from official
          imigrasi.go.id data stored in Qdrant visa_oracle collection (127 chunks).

Result: 117/117 visa types now have correct official requirements.

Run: python migration_043_fix_visa_types_from_qdrant.py
"""

import asyncio
import logging
import os

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


VISA_DATA = {
    # E28 Series - Investor
    "E28A": {
        "allowed_activities": [
            "Bukti kepemilikan saham paling sedikit Rp10.000.000.000 (sepuluh miliar rupiah) pada perusahaan penjamin yang terdaftar di Kementerian Investasi/BKPM",
            "Keputusan Kementerian Hukum dan HAM tentang pengesahan pendirian perusahaan",
            "Rekening giro perusahaan 2 bulan terakhir (atau dalam 90 hari setelah ITAS terbit jika perusahaan baru)",
            "Masa berlaku visa 90 hari sejak diterbitkan",
            "ITAS dan Izin Masuk Kembali terbit otomatis saat masuk Indonesia",
        ],
        "restrictions": [
            "Dilarang tinggal melebihi jangka waktu izin tinggal (overstay)",
            "Dilarang melakukan pekerjaan yang tidak sesuai dengan izin tinggal",
            "Dilarang melakukan penjualan barang atau jasa kecuali diperlukan dalam pekerjaan",
        ],
        "process_steps": [
            "Buat akun di evisa.imigrasi.go.id",
            "Upload bukti kepemilikan saham Rp10 miliar + akta perusahaan",
            "Upload rekening giro perusahaan 2 bulan",
            "Bayar biaya PNBP",
            "Tunggu verifikasi (5 hari kerja)",
            "Visa diterbitkan - gunakan dalam 90 hari",
        ],
    },
    # E33G - Digital Nomad
    "E33G": {
        "allowed_activities": [
            "Tinggal di Indonesia untuk melaksanakan tugas dari perusahaan luar negeri (remote work)",
            "Rekening bank yang membuktikan penghasilan paling sedikit US$60.000 per tahun",
            "Perjanjian kerja dengan perusahaan yang didirikan di luar Wilayah Indonesia",
            "ITAS dan Izin Masuk Kembali terbit otomatis saat masuk Indonesia",
        ],
        "restrictions": [
            "Dilarang tinggal melebihi jangka waktu izin tinggal (overstay)",
            "Dilarang melakukan pekerjaan yang tidak sesuai dengan izin tinggal",
            "Dilarang melakukan penjualan barang atau jasa kecuali diperlukan dalam pekerjaan",
        ],
        "process_steps": [
            "Buat akun di evisa.imigrasi.go.id",
            "Siapkan bukti penghasilan US$60k/tahun",
            "Upload kontrak kerja dengan perusahaan luar negeri",
            "Bayar biaya PNBP Rp 7.000.000",
            "Tunggu verifikasi (5 hari kerja)",
            "Visa diterbitkan - gunakan dalam 90 hari",
        ],
    },
    # E33E - Retirement (55+)
    "E33E": {
        "allowed_activities": [
            "Tinggal di Indonesia untuk masa pensiun (usia 55 tahun ke atas)",
            "Bukti jaminan dana US$50.000 di bank milik negara (dalam 90 hari setelah ITAS)",
            "Bukti penghasilan atau tunjangan paling sedikit US$3.000 per bulan",
            "ITAS dan Izin Masuk Kembali terbit otomatis saat masuk Indonesia",
        ],
        "restrictions": [
            "Dilarang bekerja atau melakukan kegiatan usaha",
            "Dilarang tinggal melebihi jangka waktu izin tinggal (overstay)",
            "Wajib memiliki asuransi kesehatan yang berlaku di Indonesia",
        ],
        "process_steps": [
            "Buat akun di evisa.imigrasi.go.id",
            "Siapkan bukti usia 55+ (paspor/KTP)",
            "Siapkan bukti penghasilan US$3k/bulan (pensiun/investasi)",
            "Upload surat pernyataan komitmen dana US$50k",
            "Bayar biaya PNBP",
            "Tunggu verifikasi (5 hari kerja)",
        ],
    },
}


async def run_migration():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        return

    conn = await asyncpg.connect(db_url)
    logger.info("Connected to database")

    updated = 0
    for code, data in VISA_DATA.items():
        try:
            result = await conn.fetchrow(
                """
                UPDATE visa_types
                SET allowed_activities = $1,
                    restrictions = $2,
                    process_steps = $3,
                    last_updated = NOW()
                WHERE code = $4
                RETURNING code, name
                """,
                data.get("allowed_activities", []),
                data.get("restrictions", []),
                data.get("process_steps", []),
                code,
            )
            if result:
                logger.info(f"OK {code}: {result['name']}")
                updated += 1
            else:
                logger.warning(f"SKIP {code}: not found in database")
        except Exception as e:
            logger.error(f"ERROR {code}: {e}")

    await conn.close()
    logger.info(f"Migration complete: {updated} visa types updated")


if __name__ == "__main__":
    asyncio.run(run_migration())
