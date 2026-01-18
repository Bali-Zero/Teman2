#!/usr/bin/env python3
"""Update E33G visa with scraped data from imigrasi.go.id"""

import asyncio
import asyncpg
import os
import json


async def update_e33g():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    allowed_activities = json.dumps(
        [
            "Tinggal di Indonesia untuk melaksanakan tugas dari perusahaan luar negeri (remote work)",
            "Masuk dan keluar wilayah Indonesia selama Izin Masuk Kembali berlaku",
            "Aktivitas wisata dan mengunjungi teman/keluarga",
        ]
    )

    restrictions = json.dumps(
        [
            "Dilarang tinggal melebihi jangka waktu izin tinggal (overstay)",
            "Dilarang melakukan pekerjaan yang tidak sesuai dengan izin tinggal",
            "Dilarang melakukan penjualan barang atau jasa, kecuali diperlukan dalam pekerjaan",
            "Masa berlaku visa 90 hari sejak diterbitkan - harus digunakan dalam periodo tersebut",
        ]
    )

    process_steps = json.dumps(
        [
            "Buat akun di evisa.imigrasi.go.id",
            "Siapkan dokumen: paspor valid 6+ bulan, rekening 3 bulan (min USD 2000), pas foto, CV, itinerary",
            "Upload dokumen khusus: bukti penghasilan USD 60k/tahun, kontrak kerja perusahaan luar negeri",
            "Bayar biaya PNBP (total Rp 7.000.000)",
            "Tunggu proses verifikasi dan persetujuan (5 hari kerja)",
            "Visa diterbitkan - gunakan dalam 90 hari",
            "ITAS dan Izin Masuk Kembali otomatis terbit saat masuk Indonesia",
        ]
    )

    tips = json.dumps(
        [
            "Pastikan rekening menunjukkan penghasilan stabil USD 60k/tahun (bukan saldo saja)",
            "Kontrak kerja harus dengan perusahaan yang terdaftar DI LUAR Indonesia",
            "Tidak perlu sponsor/penjamin - bisa apply sendiri",
            "Perpanjangan bisa dilakukan online via evisa.imigrasi.go.id",
            "Bali Zero tip: Siapkan semua dokumen dalam PDF/JPEG sebelum mulai aplikasi",
        ]
    )

    result = await conn.fetchrow(
        """
        UPDATE visa_types
        SET allowed_activities = $1::jsonb,
            restrictions = $2::jsonb,
            process_steps = $3::jsonb,
            tips = $4::jsonb,
            updated_at = NOW()
        WHERE code = 'E33G'
        RETURNING code, name
    """,
        allowed_activities,
        restrictions,
        process_steps,
        tips,
    )

    if result:
        print(f"✅ Updated: {result['code']} - {result['name']}")
    else:
        print("❌ E33G not found - checking available E33 codes...")
        codes = await conn.fetch(
            "SELECT code, name FROM visa_types WHERE code LIKE 'E33%'"
        )
        for c in codes:
            print(f"  {c['code']}: {c['name']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(update_e33g())
