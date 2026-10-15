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
  - E28G "Golden Visa 10Y / Investasi Rp 5 miliar+" - not a current visa (no official page,
    not in the signed rulepack).

Sources (saved page texts, fetched 2026-10-15): `research/visa/2026-10-15-e28-pages/text/`.
Owner rulings 2026-10-15: E28A is sold as 2 years only; Investor KITAS 17.000.000 (offshore)
/ 19.000.000 (onshore) all-inclusive; E28B-F are handled at a price on consultation; the
"7-10 working days" window stays; E28G is not a current visa.

Field placement (the API exposes `requirements`, `restrictions`, `allowed_activities`, not
`description`): `requirements` = the page's document list plus its "Persyaratan khusus"
(thresholds, stated once per row); `allowed_activities` = what the page allows, no
documents; `restrictions` = the page's "Kegiatan yang dilarang". `duration` is the STAY
length; the 90-day ENTRY window of the visa sits in E28A `process_steps`. No PNBP amount is
written anywhere: one all-inclusive client price per product, never a government-fee split,
and the E28A step list no longer tells the client to pay a fee separately.

`cost_visa` for E28A: "IDR 17.000.000 (Offshore) / 19.000.000 (Onshore), all-inclusive",
the same shape the seed already uses for other offshore/onshore products. Two scenario
prices of the two catalogue products ("Investor KITAS 2 Years (Offshore)" / "(Altus/Onshore)"),
each bound to its label; not a range and not a fee split.

E28G: the row is KEPT but marked `metadata.retired = true` (replaced_by E28A/E28B/E28C) and
its text says it is not a current visa. `GET /api/knowledge/visa/` skips retired rows; the
detail lookup by code still answers with the "not a current visa" text. No schema change.

`name` is written for all six codes and the seed script carries the same names, as
`test_visa_types_seed_vs_migration_tripwire.py` requires (E28D / E28F names equal the ones
migration_126 / migration_125 already wrote, so those two are no-ops on the live rows).

ATOMIC AND REVERSIBLE. One transaction for the whole family: any error, any missing row,
any failed post-write check rolls EVERYTHING back and exits non-zero; the loop never
continues past an error. Before any write the full current rows of the six codes are
printed as ONE stdout line `PREIMAGE <json>` (public catalogue data, not PII); all other
output goes to stderr so `tee` captures a clean preimage file.

Dry-run is the default (prints the preimage and the per-field plan, writes nothing).
Idempotent: a second `--apply` finds nothing to change.

Run (prod; the deployed container already has DATABASE_URL). `fly-deploy.yml` runs only the
named `apply_migration_NNN.py` files, so this one never runs on merge - by hand:
    fly ssh console -a nuzantara-rag -C "python3 -" < migration_128_fix_e28_family_rows.py
    fly ssh console -a nuzantara-rag -C "python3 - --apply" < migration_128_fix_e28_family_rows.py \
        | tee ~/visa_types_e28_preimage.jsonl && chmod 600 ~/visa_types_e28_preimage.jsonl
Rollback: re-apply the `PREIMAGE` rows (UPDATE each column back from the saved JSON).

Cache: nothing reads `visa_types` through a cache (the router queries Postgres on every GET;
`invalidate_cache("zantara:knowledge_visa:*")` in the router runs only after its own writes
and has no reader), so there is nothing to invalidate after this migration.
"""

import asyncio
import json
import logging
import os
import sys

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kept a pure literal (ast.literal_eval-parseable by
# test_visa_types_seed_vs_migration_tripwire.py: it reads VISA_FIXES off disk without importing).
VISA_FIXES = {
    "E28A": {
        "name": "Investor Visa",
        "duration": "2 years",
        "cost_visa": "IDR 17.000.000 (Offshore) / 19.000.000 (Onshore), all-inclusive",
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
            "Tourism and visiting friends or family"
        ],
        "process_steps": [
            "Bali Zero checks the documents and files the visa application on evisa.imigrasi.go.id together with the sponsor; the government fee is paid by Bali Zero and is included in the price",
            "Immigration verifies the payment, builds the profile and verifies the application",
            "Approval and issuance of the visa",
            "The visa is valid for 90 days from issuance: enter Indonesia within that window or a new visa must be applied for",
            "The ITAS and the Re-entry Permit are issued automatically when the immigration officer admits the foreigner at the checkpoint"
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
        "name": "Investor Visa Pendirian Cabang atau Anak Perusahaan Golden Visa",
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
        "name": "Investor Visa Pendirian Cabang atau Anak Perusahaan di Indonesian New Capital (IKN)",
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
        "name": "E28G - Not a current visa (see E28A, E28B or E28C)",
        "duration": "Not applicable",
        "cost_visa": "Not applicable",
        "processing_time_normal": None,
        "extensions": None,
        "total_stay": None,
        "processing_time_express": None,
        "requirements": [
            "E28G is not a current Indonesian investor visa: it has no official Imigrasi page. For a long-stay investor visa see E28A (investor KITAS), E28B (Golden Visa, company establishment) or E28C (Golden Visa, capital market)"
        ],
        "restrictions": [],
        "allowed_activities": [],
        "benefits": [],
        "process_steps": [],
        "tips": [],
        "metadata": {
            "retired": True,
            "retired_reason": "not a current visa: no official Imigrasi page, not in the signed rulepack",
            "replaced_by": [
                "E28A",
                "E28B",
                "E28C"
            ]
        }
    }
}


CODES = list(VISA_FIXES)


def _differs(current: dict, field: str, target) -> bool:
    if field == "metadata":
        cur = current.get("metadata")
        if isinstance(cur, str):
            cur = json.loads(cur)
        cur = cur or {}
        return any(cur.get(k) != v for k, v in target.items())
    return current.get(field) != target


def plan(rows: dict[str, dict]) -> dict[str, dict]:
    """code -> {field: target} for the fields that still differ (pure)."""
    out: dict[str, dict] = {}
    for code, fix in VISA_FIXES.items():
        changes = {f: v for f, v in fix.items() if _differs(rows[code], f, v)}
        if changes:
            out[code] = changes
    return out


def build_update(code: str, changes: dict) -> tuple[str, list]:
    """UPDATE ... WHERE code = $n for one row. `metadata` is MERGED (||), never replaced."""
    sets: list[str] = []
    values: list = []
    for field, value in changes.items():
        values.append(value)
        if field == "metadata":
            sets.append(f"metadata = COALESCE(metadata::jsonb, '{{}}'::jsonb) || ${len(values)}::jsonb")
        else:
            sets.append(f"{field} = ${len(values)}")
    sets.append("last_updated = NOW()")
    values.append(code)
    return f"UPDATE visa_types SET {', '.join(sets)} WHERE code = ${len(values)}", values


async def _read_rows(conn) -> dict[str, dict]:
    recs = await conn.fetch("SELECT * FROM visa_types WHERE code = ANY($1::text[])", CODES)
    return {r["code"]: dict(r) for r in recs}


async def run_migration(apply: bool = False) -> bool:
    """True iff every code ended in a known-good state. Dry-run (apply=False) writes nothing."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        return False
    conn = await asyncpg.connect(db_url)
    try:
        await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
        rows = await _read_rows(conn)
        missing = [c for c in CODES if c not in rows]
        if missing:
            logger.error(f"MISSING row(s) {missing}: wrong database or deleted rows. Nothing written.")
            return False
        sys.stdout.write("PREIMAGE " + json.dumps(rows, default=str, sort_keys=True, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        todo = plan(rows)
        for code, changes in todo.items():
            logger.info(f"{code}: would change {sorted(changes)}")
        if not todo:
            logger.info("NO-OP: every row already matches every target field")
            return True
        if not apply:
            logger.info(f"dry-run: {len(todo)} row(s) would change; re-run with --apply")
            return True
        try:
            async with conn.transaction():
                for code, changes in todo.items():
                    sql, values = build_update(code, changes)
                    status = await conn.execute(sql, *values)
                    if status != "UPDATE 1":
                        raise RuntimeError(f"{code}: expected 'UPDATE 1', got {status!r}")
                after = await _read_rows(conn)
                if any(c not in after for c in CODES) or plan(after):
                    raise RuntimeError("post-write check failed inside the transaction")
        except Exception as exc:
            logger.error(f"ROLLED BACK, nothing changed: {type(exc).__name__}: {exc}")
            return False
        logger.info(f"COMMITTED: {len(todo)} row(s) updated")
        return True
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run_migration(apply="--apply" in sys.argv[1:])) else 1)
