#!/usr/bin/env python3
"""Emit the W-J B1 input spec: the 2026 Bali applied PMA closure.

`data/kbli-filiera/**` is a guarded data plane (data_plane_guard.py,
registry `kbli-filiera`) — it may only be written by a compiler under
`scripts/kbli_filiera/`, never hand-edited. This is that compiler for the
ONE new input file this mission adds: the 18 KBLI-2020 business fields the
Bali Provincial Government closed to new PMA licensing on OSS (sources
below), the official Indonesian names (ANTARA Bali wording), and the two
control lists `cure_l4bali_applied_closure.py` derives its plan from:
`expected_2025_codes` (the 40, pinned — re-derived at run time from
`bps_2020_ancestors` and refused on drift) and `excluded_codes` (the 19 of
#6488, owned by W-H's adjudication, untouched here except the shared
`moratorium` object).

This script is a pure literal emitter — no computation, no network. Rerun
it any time to regenerate the file byte-for-byte (idempotent: the payload
below never changes without a source edit to this .py).

Usage:
  python scripts/kbli_filiera/emit_bali_applied_closure_spec.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = REPO_ROOT / "data" / "kbli-filiera" / "bali-applied-closure-2026.json"

SPEC = {
    "_what": (
        "The applied 2026 Bali PMA closure: 18 KBLI-2020 business fields the "
        "Bali Provincial Government closed to new foreign-ownership (PMA) "
        "licensing on OSS, and the KBLI-2025 codes that descend from them "
        "(via bps_2020_ancestors only)."
    ),
    "_scope": (
        "Input to scripts/kbli_filiera/cure_l4bali_applied_closure.py. That "
        "compiler writes ONLY l4_bali (+ l4_bali.moratorium on every record) "
        "— never pma_status/pma_max_asing/pma_kondisi/per_skala."
    ),
    "_mission": "SAETTA-20260915 W-J B1 (Dux Opus 5, M5)",
    "numbering": "KBLI 2020",
    "mapping_rule": "bps_2020_ancestors only — never bare digit-prefix matching, never pp28_sources",
    "effective": "third week of May 2026",
    "until": "until further policy",
    "approval": (
        "with the approval of the Minister of Investment/BKPM "
        "(persetujuan dari Menteri Investasi dan Hilirisasi/Kepala BKPM Republik Indonesia)"
    ),
    "sources": {
        "official": {
            "instrument": "Bali Provincial Government press release",
            "event": "2026-07-22",
            "published": "2026-07-24",
            "url": (
                "https://www.baliprov.go.id/web/gubernur-koster-batasi-akses-oss-untuk-"
                "pma-di-sejumlah-kbli-lindungi-umkm-lokal-dari-persaingan-tidak-sehat/"
            ),
            "quotes": [
                "sejak minggu ketiga Mei 2026",
                "hingga terdapat kebijakan lebih lanjut",
                "persetujuan dari Menteri Investasi dan Hilirisasi/Kepala BKPM Republik Indonesia",
            ],
        },
        "code_list": {
            "source": "ANTARA Bali",
            "published": "2026-07-23",
            "url": (
                "https://bali.antaranews.com/berita/410161/18-bidang-usaha-dengan-"
                "penanaman-modal-asing-pma-di-bali-ditutup-demi-jaga-usaha-lokal"
            ),
        },
        "request_letter": {
            "id": "B.27.000/642/PM/DPMPTSP",
            "date": "2026-01-28",
            "note": "request; Lampiran: -",
        },
    },
    "eighteen": {
        "55110": {"name": "Hotel Bintang (<6.000 m²)", "scope_qualifier": "building area under 6,000 m²"},
        "68111": {"name": "Real Estate yang dimiliki sendiri atau disewa"},
        "55120": {"name": "Hotel Melati (<6.000 m²)", "scope_qualifier": "building area under 6,000 m²"},
        "70209": {"name": "Aktivitas Konsultasi Manajemen Lainnya"},
        "77100": {"name": "Penyewaan Mobil, Bus, Truk, dan Sejenisnya"},
        "47711": {"name": "Perdagangan Eceran Pakaian"},
        "47511": {"name": "Perdagangan Eceran Tekstil"},
        "77311": {"name": "Penyewaan Motor Tanpa Hak Opsi"},
        "47249": {"name": "Perdagangan Eceran Makanan Lainnya"},
        "47991": {"name": "Perdagangan Eceran Keliling Komoditi Makanan dari Hasil Pertanian"},
        "55900": {"name": "Penyediaan Akomodasi Lainnya"},
        "56303": {"name": "Rumah Minum/Kafe"},
        "56305": {"name": "Rumah/Kedai Obat Tradisional"},
        "14120": {"name": "Penjahitan dan Pembuatan Pakaian Sesuai Pesanan"},
        "93111": {"name": "Fasilitas Stadion"},
        "93116": {"name": "Fasilitas Pusat Kebugaran/Fitness Center"},
        "93191": {"name": "Promotor Kegiatan Olahraga"},
        "70204": {"name": "Aktivitas Konsultansi Manajemen Industri"},
    },
    "expected_2025_codes": [
        "14120", "47211", "47212", "47213", "47214", "47215", "47216", "47219", "47249", "47511",
        "47711", "55101", "55102", "55103", "55104", "55105", "55106", "55400", "55901", "55909",
        "56303", "56305", "56400", "68111", "68112", "68123", "68125", "68126", "68127", "68129",
        "70202", "70203", "70209", "77100", "77311", "77510", "87303", "93111", "93116", "93191",
    ],
    "excluded_codes": {
        "codes": [
            "55201", "55203", "79903", "43110", "55209", "79110", "38110", "55202", "55300",
            "56102", "56304", "56306", "70201", "73300", "74199", "79901", "79902", "86995", "93114",
        ],
        "owner": "W-H (SAETTA-20260915)",
        "note": (
            "the 19 of #6488 — adjudicated under Perpres 49/2021 Lampiran II by a "
            "different compiler; l4_bali left untouched by this compiler except the "
            "shared moratorium object"
        ),
    },
    "moratorium": {
        "rule": (
            "Bali closed OSS to new PMA licensing for 18 business fields (KBLI 2020 "
            "numbering), not for every low/medium-low risk activity"
        ),
        "effective": "third week of May 2026",
        "until": "until further policy",
        "source": "Bali Provincial Government press release, 24 Jul 2026",
        "source_url": (
            "https://www.baliprov.go.id/web/gubernur-koster-batasi-akses-oss-untuk-"
            "pma-di-sejumlah-kbli-lindungi-umkm-lokal-dari-persaingan-tidak-sehat/"
        ),
        "request": (
            "Governor letter B.27.000/642/PM/DPMPTSP (28 Jan 2026), a request covering "
            "all low/medium-low risk PMA and virtual offices"
        ),
        "virtual_office": "requested in letter B.27.000/642/PM/DPMPTSP; application not confirmed",
    },
}


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(SPEC, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
