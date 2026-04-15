#!/usr/bin/env python3
"""
One-off: ingest 41 LKPM Q1 2026 OSS tanda terima PDFs from tax@balizero.com Drive.

Source of truth: Google Drive folder "LKPM Q1 2026" shared by tax@balizero.com.
Structure:
    LKPM Q1 2026/
      ├── LKPM Q1 2026 (DEWA AYU)/   ← 10 PT, 22 PDF
      └── LKPM Q1 2026 (Kadek)/       ← 7 PT, 19 PDF

Each PDF is an OSS "Tanda Terima" with one (Nomor Laporan, Nomor Kegiatan Usaha,
KBLI) triple. A PT typically has 1–5 PDFs per quarter, one per kegiatan_usaha.

What this script does:
1. For each of 17 PT: resolve company_id (15 from Lori's import + 2 new handled
   below: PT ITCHI DIGITAL BALI minimal-create, PT HANG LOOSE COMPAGNY already
   at id=2327).
2. Fix typo on client 11140 (Maurice Van Der MOER → MOERE) — user decision.
3. Upsert lkpm_client_config (reuses Lori's 59 where overlap; creates 1 new for
   ITCHI DIGITAL; 2327 = HANG LOOSE already has config).
4. Upsert lkpm_reports Q1 2026, mark oss_submitted=TRUE, copy first receipt
   as the row's canonical oss_receipt_number/url, set lkpm_assigned_to to the
   DEWA AYU or Kadek address based on the source folder.
5. Insert 41 rows into lkpm_receipts (one per PDF), UNIQUE on nomor_laporan.
6. After commit, pg_notify('lkpm_ingest_completed', payload) so the EventBus
   (backend/services/events/event_bus.py) dispatches lkpm.ingest_completed
   to KG Tax subgraph, portal notifications, audit log. Skip with --skip-event.
7. Send email report to zero@balizero.com + tax@balizero.com via Brevo
   (POST /api/notifications/send-email on nuzantara-rag.fly.dev).

Idempotent: safe to re-run. UNIQUE constraints prevent duplicates.
DRY-RUN default. Use --commit to actually write.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    DATABASE_URL=... PYTHONPATH=. python scripts/import_lkpm_q1_2026_receipts.py --dry-run
    DATABASE_URL=... PYTHONPATH=. python scripts/import_lkpm_q1_2026_receipts.py --commit

Non-derivable knowledge:
- "PT PIM HANG LOSE" (Kadek folder) is PT HANG LOOSE COMPAGNY in DB (id=2327).
  Confirmed by Pim De Boer client id=11139 + Maurice id=11140 both linked as
  Director/Commissioner on company_id=2327. PDF confirms Nama perusahaan.
- "PT Merakih Creation Bali" (DEWA AYU) is PT MERAKI CREATIONS BALI id=3097.
  Lori's script has a typo "Meraki Creation" (no s); DB says "Creations".
- "PT Ichi Digital" (DEWA AYU folder) is PT ITCHI DIGITAL BALI in OSS. Not in
  Lori's 59 and NOT in DB — minimal-create here.
- The 17th PT "PT PIM HANG LOSE" is NOT in Lori's list; it's already in DB as
  HANG LOOSE COMPAGNY (2327), so no minimal create.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from typing import Any

import asyncpg
import httpx

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


MARKER_CREATED_BY = "lkpm_q1_2026_receipts_import"

# Tax team Drive folder URLs (for reference in email report only).
DRIVE_ROOT_FOLDER_URL = (
    "https://drive.google.com/drive/folders/1l8Pg3bVVcfDYslRIUtJn-53l7rtjXK_V"
)


# ──────────────────────────────────────────────────────────────────────
# PT mapping: one entry per Drive subfolder → DB company_id + operator.
# `company_id=None` means minimal-create.
# ──────────────────────────────────────────────────────────────────────
PT_MAP: dict[str, dict[str, Any]] = {
    # ────────────── DEWA AYU folder (10 PT) ──────────────
    "PT Nayat Ibiza Beauty":          {"company_id": 3037, "operator": "dewaayu.tax@balizero.com"},
    "PT Paradise Beach Brothers":     {"company_id": 2962, "operator": "dewaayu.tax@balizero.com"},
    "PT Happy Events Bali Travel":    {"company_id": 3135, "operator": "dewaayu.tax@balizero.com"},
    "PT Itchi Digital Bali":          {"company_id": None, "operator": "dewaayu.tax@balizero.com"},  # minimal
    "PT Meraki Creations Bali":       {"company_id": 3097, "operator": "dewaayu.tax@balizero.com"},
    "PT Black Pork Consulting":       {"company_id": 1478, "operator": "dewaayu.tax@balizero.com"},
    "PT Singa Investments Bali":      {"company_id": 2758, "operator": "dewaayu.tax@balizero.com"},
    "PT Chloe Nature Escape":         {"company_id": 3203, "operator": "dewaayu.tax@balizero.com"},
    "PT Ichnos West Sumbawa":         {"company_id": 1897, "operator": "dewaayu.tax@balizero.com"},
    "PT Ventura Impact Positif":      {"company_id": 2375, "operator": "dewaayu.tax@balizero.com"},
    # ────────────── Kadek folder (7 PT) ──────────────
    "PT Jungle Dream House":          {"company_id": 1978, "operator": "kadek.tax@balizero.com"},
    "PT Urban Jungle Bali":           {"company_id": 2520, "operator": "kadek.tax@balizero.com"},
    "PT Karta Developers Paradise":   {"company_id": 1999, "operator": "kadek.tax@balizero.com"},
    "PT Domus Dei Amare":             {"company_id": 1645, "operator": "kadek.tax@balizero.com"},
    "PT Bali Nea Karma":              {"company_id": 1382, "operator": "kadek.tax@balizero.com"},
    "PT Bali Accommodation Management": {"company_id": 16,  "operator": "kadek.tax@balizero.com"},
    "PT Hang Loose Compagny":         {"company_id": 2327, "operator": "kadek.tax@balizero.com"},
}


# ──────────────────────────────────────────────────────────────────────
# Client typo fix
# ──────────────────────────────────────────────────────────────────────
CLIENT_NAME_FIXES: list[tuple[int, str, str]] = [
    # (client_id, current_name, target_name)
    (11140, "MAURICE VAN DER MOER", "MAURICE VAN DER MOERE"),
]


# ──────────────────────────────────────────────────────────────────────
# 41 OSS receipts extracted via MCP Google Drive reads on 2026-04-15.
# Each tuple: (
#   pt_key,           # key into PT_MAP
#   file_drive_id,
#   file_name,
#   nomor_laporan,
#   nomor_kegiatan_usaha,
#   kbli_code,
#   kegiatan_usaha_desc,
#   stage,            # KONSTRUKSI | PRODUKSI
#   oss_status,       # Terkirim | Disetujui
#   lokasi,
#   tanggal_diterima, # ISO date
#   nama_perusahaan_oss,
# )
# ──────────────────────────────────────────────────────────────────────
RECEIPTS: list[tuple[str, str, str, str, str, str, str, str, str, str, str, str]] = [
    # ───────── PT Nayat Ibiza Beauty (3) ─────────
    ("PT Nayat Ibiza Beauty", "1jDpRTmyy8ofviBkjXg2JkrUdadI8Qlk1",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 70209 PT Nayat.pdf",
     "LK6785433", "202412-1913-2514-6246-937", "70209", "Aktivitas Konsultasi Manajemen",
     "PRODUKSI", "Terkirim", "BJ Saren , Kab. Badung, Bali",
     "2026-04-13", "PT NAYAT IBIZA BEAUTY"),
    ("PT Nayat Ibiza Beauty", "1ULN0BCWJpznkW96aKxLkWVg_rqTejEZ6",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 68111 PT Nayat.pdf",
     "LK6779740", "202412-1913-1934-7086-055", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Disetujui", "BJ Saren , Kab. Badung, Bali",
     "2026-04-13", "PT NAYAT IBIZA BEAUTY"),
    ("PT Nayat Ibiza Beauty", "1atN0P45hjY8yKIf61qchQaawgqrmSHJ6",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 55900 PT Nayat.pdf",
     "LK6785564", "202412-1913-2936-9639-016", "55900", "Penyediaan akomodasi lainnya",
     "PRODUKSI", "Terkirim", "BJ Saren , Kab. Badung, Bali",
     "2026-04-13", "PT NAYAT IBIZA BEAUTY"),

    # ───────── PT Paradise Beach Brothers (3) ─────────
    ("PT Paradise Beach Brothers", "1zU5gYq5xJVNALI9od7P641sy2_R9c1T1",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 68111 PT Paradise beach brother.pdf",
     "LK6787700", "202408-1415-0425-6501-815", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2, Kab. Badung, Bali",
     "2026-04-13", "PT PARADISE BEACH BROTHERS"),
    ("PT Paradise Beach Brothers", "1rgnpDRTRb4hYR8oVmHbobuCh-MgFALrc",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 68111 PT Paradise beach brother 2.pdf",
     "LK6792924", "202411-1514-1222-7431-851", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Terkirim", "Beru, Kab. Sumbawa Barat, Nusa Tenggara Barat",
     "2026-04-13", "PT PARADISE BEACH BROTHERS"),
    ("PT Paradise Beach Brothers", "1bhESGFmp7DcvmG1WWlckI4qIZDHjZsjJ",
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 68111 PT Paradise beach Brother 3.pdf",
     "LK6793329", "202603-2518-5506-5383-642", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Terkirim", "",
     "2026-04-13", "PT PARADISE BEACH BROTHERS"),

    # ───────── PT Happy Events Bali Travel (5) ─────────
    ("PT Happy Events Bali Travel", "1Hi0ceYnN6tOV4WFenB67xdWHiYDsHktH",
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 62012 Happy Event.pdf",
     "LK6802976", "202301-2613-1521-4027-063", "6201", "Aktivitas Pemrograman Komputer",
     "KONSTRUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2 , Kab. Badung, Bali",
     "2026-04-13", "PT HAPPY EVENTS BALI TRAVEL"),
    ("PT Happy Events Bali Travel", "1giJnAg3VWGeuTdVKaUTPXh1rXfoK07aJ",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 46900 Happy Event.pdf",
     "LK6800328", "202301-2613-2208-1298-732", "4690", "Perdagangan besar berbagai macam barang",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2 , Kab. Badung, Bali",
     "2026-04-13", "PT HAPPY EVENTS BALI TRAVEL"),
    ("PT Happy Events Bali Travel", "1_D6z8_NKR4A1_s50TPlCDvrCA47OY5be",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 68111 Happy Event.pdf",
     "LK6802781", "202301-2613-0634-3384-998", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "KONSTRUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2 , Kab. Badung, Bali",
     "2026-04-13", "PT HAPPY EVENTS BALI TRAVEL"),
    ("PT Happy Events Bali Travel", "1327i52xLgw5JH6y5hNqUarXRGjIg9fO8",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 70209 Happy Event.pdf",
     "LK6799959", "202301-2613-1237-1092-408", "7020", "Aktivitas Konsultasi Manajemen",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2 , Kab. Badung, Bali",
     "2026-04-13", "PT HAPPY EVENTS BALI TRAVEL"),
    ("PT Happy Events Bali Travel", "1HUMMaEw-NU2ZxvYZvN5FScCZRvGOjjk3",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 68200 Happy Event.pdf",
     "LK6800480", "202301-2613-2544-6925-457", "6820", "Real estat atas dasar balas jasa (fee) atau kontrak",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2 , Kab. Badung, Bali",
     "2026-04-13", "PT HAPPY EVENTS BALI TRAVEL"),

    # ───────── PT Itchi Digital Bali (2) ─────────
    ("PT Itchi Digital Bali", "1aEEgjh4I3_JnNCWNDfikMfeqwbiL7oJj",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 70209 Ichi Digital.pdf",
     "LK6804588", "202403-2611-2849-0427-921", "7020", "Aktivitas Konsultasi Manajemen",
     "KONSTRUKSI", "Terkirim", "Jalan Raya Tumbakbayuh, Kab. Badung, Bali",
     "2026-04-13", "PT ITCHI DIGITAL BALI"),
    ("PT Itchi Digital Bali", "1vxOc0CEqK__iRde6cpUzDUpt8byWDXtT",  # pragma: allowlist secret
     "LKPM Triwuln 1 Jan-Mar 2026 KBLI 68111 Ichi Digital.pdf",
     "LK6804715", "202403-2611-4706-4479-302", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "KONSTRUKSI", "Terkirim", "Jalan Raya Tumbakbayuh, Kab. Badung, Bali",
     "2026-04-13", "PT ITCHI DIGITAL BALI"),

    # ───────── PT Meraki Creations Bali (3) ─────────
    ("PT Meraki Creations Bali", "1ilCObM4VkKKp_5RUlNzuhX72yRblLF2i",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 68200 Merakih.pdf",
     "LK6807779", "202210-1915-1548-6331-936", "6820", "Real estat atas dasar balas jasa (fee) atau kontrak",
     "PRODUKSI", "Terkirim", "JL. RAYA ANYAR GANG III NO. 2, Kab. Badung, Bali",
     "2026-04-13", "PT MERAKI CREATIONS BALI"),
    ("PT Meraki Creations Bali", "1395tvucSayM6DpghQ8n2EgMMk-bNYoUj",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-mar 2026 KBLI 68111 Merakih.pdf",
     "LK6807612", "202210-1915-1322-0963-280", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Terkirim", "JL. RAYA ANYAR GANG III NO. 2, Kab. Badung, Bali",
     "2026-04-13", "PT MERAKI CREATIONS BALI"),
    ("PT Meraki Creations Bali", "1sHonSXv1c651LKw_zV_iQmECmmRkD6_3",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 70209 Merakih.pdf",
     "LK6807461", "202210-1915-0740-1384-066", "7020", "Aktivitas Konsultasi Manajemen",
     "PRODUKSI", "Terkirim", "JL. RAYA ANYAR GANG III NO. 2, Kab. Badung, Bali",
     "2026-04-13", "PT MERAKI CREATIONS BALI"),

    # ───────── PT Black Pork Consulting (1) ─────────
    ("PT Black Pork Consulting", "1Cfukogi5GBvtRhSa0QabIrb6xkhZL5kp",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 70209 Black Pork.pdf",
     "LK6808765", "202406-2014-2052-0726-671", "7020", "Aktivitas Konsultasi Manajemen",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2, Kab. Badung, Bali",
     "2026-04-13", "PT BLACK PORK CONSULTING"),

    # ───────── PT Singa Investments Bali (1) ─────────
    ("PT Singa Investments Bali", "1EtGcmV_pO68OkN4LLYDVQVUKNKtb7OUn",
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 68111 Singa Invesment.pdf",
     "LK6865574", "202604-1411-1009-7769-182", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "KONSTRUKSI", "Terkirim", "",
     "2026-04-14", "PT SINGA INVESTMENTS BALI"),

    # ───────── PT Chloe Nature Escape (1) ─────────
    ("PT Chloe Nature Escape", "1SCy7AecmlwSTkhsf2Tdir0v1xjjFc0FF",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 68111 Chole Nature Escape.pdf",
     "LK6867389", "202504-2016-4144-5078-859", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Terkirim", "PROMENADE SHOP UNIT S11, Jl. Kayu Tulang No. 82, Kab. Badung, Bali",
     "2026-04-14", "PT CHLOE NATURE ESCAPE"),

    # ───────── PT Ichnos West Sumbawa (2) ─────────
    ("PT Ichnos West Sumbawa", "1XfZYaPZh1fsu6knjOwbTXCmprXd9fUcL",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 68111 Icnos West Sumbawa.pdf",
     "LK6868939", "202411-1511-0551-7115-951", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Terkirim", "Beru, Kab. Sumbawa Barat, Nusa Tenggara Barat",
     "2026-04-14", "PT ICHNOS WEST SUMBAWA"),
    ("PT Ichnos West Sumbawa", "1yqFQsX1MmYY8nERNat3m3DLjz-P-DswR",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 68111 Icnos West Sumbawa 2.pdf",
     "LK6868748", "202411-1410-0710-2462-808", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2, Kab. Badung, Bali",
     "2026-04-14", "PT ICHNOS WEST SUMBAWA"),

    # ───────── PT Ventura Impact Positif (2) ─────────
    ("PT Ventura Impact Positif", "1PCNCVojl7BUyLCbnAH2sGG6hvsZjfg9y",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 68111 Ventura Impact.pdf",
     "LK6871922", "202308-1906-3631-9903-626", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2, Kab. Badung, Bali",
     "2026-04-14", "PT VENTURA IMPACT POSITIF"),
    ("PT Ventura Impact Positif", "1GaOjx_EnUiUy_XAHF0RcjIJ5lM6q97Pi",  # pragma: allowlist secret
     "LKPM Triwulan 1 Jan-Mar 2026 KBLI 70209 Ventura Impact.pdf",
     "LK6871505", "202308-1906-3203-3714-379", "7020", "Aktivitas Konsultasi Manajemen",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2, Kab. Badung, Bali",
     "2026-04-14", "PT VENTURA IMPACT POSITIF"),

    # ───────── PT Jungle Dream House (1) ─────────
    ("PT Jungle Dream House", "1hUDzEPkFe433Sdp7qVudhpyZlJ_Shh4i",
     "PT Junggle Dream House (6811) - LKPM Q1.pdf",
     "LK6481443", "202501-2117-5140-1823-318", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Disetujui", "Jalan Pantai Balian, Kab. Tabanan, Bali",
     "2026-04-06", "PT JUNGLE DREAM HOUSE"),

    # ───────── PT Urban Jungle Bali (2) ─────────
    ("PT Urban Jungle Bali", "1hGbhkeccyz0EaI9-yql-6A5stEMyKBGM",  # pragma: allowlist secret
     "PT Urban Junggle (5519) - LKPM Q1.pdf",
     "LK6492198", "202503-1215-3024-4327-774", "5519", "Penyediaan Akomodasi jangka pendek lainnya",
     "PRODUKSI", "Disetujui", "Jalan Raya Anyar Gang III No. 2, Kab. Badung, Bali",
     "2026-04-06", "PT URBAN JUNGLE BALI"),
    ("PT Urban Jungle Bali", "18o0PiP0AJVWoJiov296PsuBCSEYXTqcl",  # pragma: allowlist secret
     "PT Urban Junggle (6811) - LKPM Q1.pdf",
     "LK6492100", "202503-1215-2229-3848-179", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Disetujui", "Jalan Raya Anyar Gang III No. 2, Kab. Badung, Bali",
     "2026-04-06", "PT URBAN JUNGLE BALI"),

    # ───────── PT Karta Developers Paradise (2) ─────────
    ("PT Karta Developers Paradise", "1fnF0kWg1gj8jbKjgQolf7azJ8sW7b2Zc",
     "PT Karta Developers Paradise  (6202) - LKPM Q1.pdf",
     "LK6868081", "202207-0512-5042-0097-355", "6202", "Aktivitas Konsultasi Komputer dan Manajemen Fasilitas Komputer",
     "KONSTRUKSI", "Terkirim", "JL. RAYA ANYAR GANG III NO. 2, Kab. Badung, Bali",
     "2026-04-14", "PT KARTA DEVELOPERS PARADISE"),
    ("PT Karta Developers Paradise", "1JSo119fHB_gvV-c271wDokN1Onz_1ExZ",
     "PT Karta Developers Paradise  (6201) - LKPM Q1.pdf",
     "LK6868213", "202207-0512-4707-4803-443", "6201", "Aktivitas Pemrograman Komputer",
     "KONSTRUKSI", "Terkirim", "JL. RAYA ANYAR GANG III NO. 2, Kab. Badung, Bali",
     "2026-04-14", "PT KARTA DEVELOPERS PARADISE"),

    # ───────── PT Domus Dei Amare (5) ─────────
    ("PT Domus Dei Amare", "1Oz9DTtyHFnZGVgQ3z0WZ0l41lwNKt5Jy",  # pragma: allowlist secret
     "PT Domus Dei Amare (4641) - LKPM Q1.pdf",
     "LK6873042", "202307-1111-1612-6799-342", "4641", "Perdagangan besar tekstil, pakaian dan alas kaki",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2, Kab. Badung, Bali",
     "2026-04-14", "PT DOMUS DEI AMARE"),
    ("PT Domus Dei Amare", "1NHZQ66mT54gOwxOZtbMlJkPz-OfPT4tU",  # pragma: allowlist secret
     "PT Domus Dei Amare (7020) - LKPM Q1.pdf",
     "LK6873567", "202307-1112-0131-6947-301", "7020", "Aktivitas Konsultasi Manajemen",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2, Kab. Badung, Bali",
     "2026-04-14", "PT DOMUS DEI AMARE"),
    ("PT Domus Dei Amare", "1mPcCu5tdNBZ6lEjytOdpj7fnh2R8Ombu",  # pragma: allowlist secret
     "PT Domus Dei Amare (4610) - LKPM Q1.pdf",
     "LK6873755", "202307-1112-1625-8969-212", "4610", "Perdagangan besar atas dasar balas jasa (fee) atau kontrak",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2, Kab. Badung, Bali",
     "2026-04-14", "PT DOMUS DEI AMARE"),
    ("PT Domus Dei Amare", "1hoLJu7BntdqJ8W-Jdc0C3vxuEwYlGdaf",  # pragma: allowlist secret
     "PT Domus Dei Amare (4649) - LKPM Q1.pdf",
     "LK6873152", "202307-1111-2441-9634-484", "4649", "Perdagangan Besar Barang Keperluan Rumah Tangga Lainnya",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2, Kab. Badung, Bali",
     "2026-04-14", "PT DOMUS DEI AMARE"),
    ("PT Domus Dei Amare", "12tUjXdYA9KXdvbxeNBGDnkRv_i8zoS61",  # pragma: allowlist secret
     "PT Domus Dei Amare (6811) - LKPM Q1.pdf",
     "LK6873441", "202307-1111-2855-6859-600", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III No. 2, Kab. Badung, Bali",
     "2026-04-14", "PT DOMUS DEI AMARE"),

    # ───────── PT Bali Nea Karma (4) ─────────
    ("PT Bali Nea Karma", "1cZSh3udg1DLe1abJcfHQUmSsm50hBLZD",
     "PT Bali Nea Karma (6820) - LKPM Q1.pdf",
     "LK6489143", "202410-3011-5341-9229-801", "6820", "Real estat atas dasar balas jasa (fee) atau kontrak",
     "PRODUKSI", "Disetujui", "Jl. Pengubugan Gg Kayu Merbau No. 1A, Kab. Badung, Bali",
     "2026-04-06", "PT BALI NEA KARMA"),
    ("PT Bali Nea Karma", "1bye_LbY0BA72Va4XJkgmceNhJg6gLFy8",  # pragma: allowlist secret
     "PT Bali Nea Karma (7020) - LKPM Q1.pdf",
     "LK6825034", "201912-2914-4940-0753-126", "7020", "Aktivitas Konsultasi Manajemen",
     "PRODUKSI", "Terkirim", "Jl. Pengubugan Gg Kayu Merbau No. 1A, Kab. Badung, Bali",
     "2026-04-13", "PT BALI NEA KARMA"),
    ("PT Bali Nea Karma", "14Smel5JTosbM-xpcdQp_Z2fmIJI95aAu",  # pragma: allowlist secret
     "PT Bali Nea Karma (6811) - LKPM Q1.pdf",
     "LK6489083", "202410-3011-4921-5825-692", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Disetujui", "Jl. Pengubugan Gg Kayu Merbau No. 1A, Kab. Badung, Bali",
     "2026-04-06", "PT BALI NEA KARMA"),
    ("PT Bali Nea Karma", "1Jnf1uZo7AlrE4eV3f7V73Er985vzjx7y",
     "PT Bali Nea Karma (5519) - LKPM Q1.pdf",
     "LK6489211", "202410-3011-5830-1204-361", "5519", "Penyediaan Akomodasi jangka pendek lainnya",
     "PRODUKSI", "Disetujui", "Jl. Pengubugan Gg Kayu Merbau No. 1A, Kab. Badung, Bali",
     "2026-04-06", "PT BALI NEA KARMA"),

    # ───────── PT Bali Accommodation Management (4) ─────────
    ("PT Bali Accommodation Management", "1Uu-R_xjyos58rT9lddsYYio_EeEsyUAP",
     "PT Bali Acomodation Management (6811) - LKPM Q1.pdf",
     "LK6864050", "202509-3010-1146-0343-037", "68111", "Real estat yang dimiliki sendiri atau disewa",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III E, Kab. Badung, Bali",
     "2026-04-14", "PT BALI ACCOMMODATION MANAGEMENT"),
    ("PT Bali Accommodation Management", "1ZlSPUGxFNRuSUsGQv3AE2iabgmSNpe2J",  # pragma: allowlist secret
     "PT Bali Acomodation Management (6820) - LKPM Q1.pdf",
     "LK6864227", "202509-3010-1503-6368-950", "6820", "Real estat atas dasar balas jasa (fee) atau kontrak",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III E, Kab. Badung, Bali",
     "2026-04-14", "PT BALI ACCOMMODATION MANAGEMENT"),
    ("PT Bali Accommodation Management", "1SW98K_f-A8KfrvyYn4ZFtd61B2zVPJl4",  # pragma: allowlist secret
     "PT Bali Acomodation Management (7020) - LKPM Q1.pdf",
     "LK6864327", "202509-3010-1817-2282-268", "7020", "Aktivitas Konsultasi Manajemen",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III E, Kab. Badung, Bali",
     "2026-04-14", "PT BALI ACCOMMODATION MANAGEMENT"),
    ("PT Bali Accommodation Management", "1xVMBgEfdkzuP8_gXiw_TaVnPF1wiX49J",  # pragma: allowlist secret
     "PT Bali Acomodation Management (4610) - LKPM Q1.pdf",
     "LK6864435", "202509-3010-2054-4377-656", "4610", "Perdagangan besar atas dasar balas jasa (fee) atau kontrak",
     "PRODUKSI", "Terkirim", "Jalan Raya Anyar Gang III E, Kab. Badung, Bali",
     "2026-04-14", "PT BALI ACCOMMODATION MANAGEMENT"),

    # ───────── PT Hang Loose Compagny (1) — aka Drive "PT PIM HANG LOSE" ─────────
    ("PT Hang Loose Compagny", "1rWK8_cUKauOnZoLivlynFOwK9x-7MyLs",  # pragma: allowlist secret
     "PT PIM Hang Lose  (7020) - LKPM Q1.pdf",
     "LK6871664", "202407-0315-3007-5765-036", "7020", "Aktivitas Konsultasi Manajemen",
     "KONSTRUKSI", "Terkirim", "Desa Sekongkang Bawah, Kab. Sumbawa Barat, Nusa Tenggara Barat",
     "2026-04-14", "PT HANG LOOSE COMPAGNY"),
]


# ──────────────────────────────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────────────────────────────


async def ensure_itchi_digital_bali_company(
    conn: asyncpg.Connection,
) -> tuple[int, bool]:
    """
    Ensure PT ITCHI DIGITAL BALI row exists in companies.
    Returns (company_id, was_created).
    """
    existing_id = await conn.fetchval(
        "SELECT id FROM companies WHERE upper(company_name) = upper($1) LIMIT 1",
        "PT ITCHI DIGITAL BALI",
    )
    if existing_id:
        logger.info(f"  PT ITCHI DIGITAL BALI already in DB: id={existing_id}")
        return int(existing_id), False
    new_id = await conn.fetchval(
        """
        INSERT INTO companies (
            company_name, company_type, status,
            created_at, created_by, updated_at, updated_by
        ) VALUES (
            $1, 'PT PMA', 'active',
            NOW(), $2, NOW(), $2
        )
        RETURNING id
        """,
        "PT ITCHI DIGITAL BALI",
        MARKER_CREATED_BY,
    )
    logger.info(f"  + minimal PT ITCHI DIGITAL BALI created: id={new_id}")
    return int(new_id), True


async def fix_client_typos(conn: asyncpg.Connection, stats: dict[str, int]) -> list[str]:
    """Apply CLIENT_NAME_FIXES. Returns list of human-readable changes for report."""
    changes: list[str] = []
    for cid, current, target in CLIENT_NAME_FIXES:
        actual = await conn.fetchval(
            "SELECT full_name FROM clients WHERE id = $1",
            cid,
        )
        if actual is None:
            logger.warning(f"  client id={cid} not found, skipping name fix")
            continue
        if actual == target:
            logger.info(f"  client id={cid} already has target name '{target}'")
            continue
        if actual != current:
            logger.warning(
                f"  client id={cid} has name '{actual}', not expected '{current}' — skipping",
            )
            continue
        await conn.execute(
            """
            UPDATE clients
               SET full_name = $1, updated_at = NOW(), updated_by = $2
             WHERE id = $3
            """,
            target,
            MARKER_CREATED_BY,
            cid,
        )
        stats["client_name_fixes"] += 1
        changes.append(f"client #{cid}: '{actual}' → '{target}'")
        logger.info(f"  ✓ client id={cid} renamed: '{actual}' → '{target}'")
    return changes


async def ensure_lkpm_config(
    conn: asyncpg.Connection,
    client_id: int,
    company_id: int,
    company_name: str,
) -> None:
    """
    Ensure lkpm_client_config row exists for this (client_id, company_id).
    UNIQUE constraint is on (client_id, company_id) — not client_id alone.
    """
    existing = await conn.fetchval(
        """
        SELECT id FROM lkpm_client_config
        WHERE client_id = $1 AND company_id = $2
        """,
        client_id,
        company_id,
    )
    if existing:
        return
    await conn.execute(
        """
        INSERT INTO lkpm_client_config (
            client_id, company_id, company_name,
            oss_creds_updated_by, oss_creds_updated_at,
            created_at, updated_at
        ) VALUES ($1, $2, $3, $4, NOW(), NOW(), NOW())
        ON CONFLICT (client_id, company_id) DO NOTHING
        """,
        client_id,
        company_id,
        company_name,
        MARKER_CREATED_BY,
    )


async def upsert_lkpm_report(
    conn: asyncpg.Connection,
    company_id: int,
    pt_key: str,
    operator: str,
    canonical_receipt: dict[str, str],
) -> tuple[int, str]:
    """
    Upsert Q1 2026 lkpm_reports row. Returns (id, action).
    action: 'inserted' | 'updated' | 'exists_noop'.

    Key by `company_id` (not `client_id`) because the Lori convention of
    setting `client_id = company_id` is inconsistent in the DB: most existing
    rows use a real CRM `client_id` (primary shareholder). We key by
    `company_id + quarter + year` instead — matches the UNIQUE constraint.

    For fresh inserts where no prior config/report exists, we still fall back
    to `client_id = company_id` to stay compatible with the 5 Lori rows using
    that convention. `lkpm_client_config` UNIQUE is `(client_id, company_id)`.
    """
    # Look up an existing lkpm_reports for this company in Q1 2026 (any
    # client_id — the UNIQUE covers the 3-tuple (client_id, company_id,
    # quarter, year) so there may be >1 if imported from different sources,
    # but in practice there's 0 or 1).
    existing = await conn.fetchrow(
        """
        SELECT id, client_id, oss_submitted, oss_receipt_number, lkpm_assigned_to
        FROM lkpm_reports
        WHERE company_id = $1 AND quarter = 'Q1' AND year = 2026
        ORDER BY id
        LIMIT 1
        """,
        company_id,
    )
    # Use the existing row's client_id, or fall back to company_id if creating new.
    client_id = existing["client_id"] if existing else company_id
    await ensure_lkpm_config(conn, client_id, company_id, pt_key)
    if existing is None:
        # Need to insert. Most NOT NULL scalar fields default to 0 via schema default,
        # but validation_alerts is NOT NULL with default '[]'.
        new_id = await conn.fetchval(
            """
            INSERT INTO lkpm_reports (
                client_id, company_id, quarter, year,
                status, validation_status, validation_alerts,
                client_approved, oss_submitted,
                oss_submitted_at, oss_submitted_by,
                oss_receipt_number, oss_receipt_file_url,
                data_source, has_ai_categorized_items, ai_categorized_count,
                lkpm_assigned_to,
                realized_equipment_domestic, realized_equipment_import,
                realized_building_domestic, realized_building_import,
                realized_vehicle_domestic, realized_vehicle_import,
                realized_land, realized_working_capital, realized_other,
                cumulative_equipment_domestic, cumulative_equipment_import,
                cumulative_building_domestic, cumulative_building_import,
                cumulative_vehicle_domestic, cumulative_vehicle_import,
                cumulative_land, cumulative_working_capital, cumulative_other,
                current_tki, current_tka, quarterly_revenue, annual_revenue,
                created_at, updated_at
            ) VALUES (
                $1, $2, 'Q1', 2026,
                'submitted', 'pending', '[]'::jsonb,
                FALSE, TRUE,
                NOW(), $3,
                $4, $5,
                'oss_receipt_import', FALSE, 0,
                $6,
                0,0,0,0,0,0,0,0,0,
                0,0,0,0,0,0,0,0,0,
                0,0,0,0,
                NOW(), NOW()
            )
            RETURNING id
            """,
            client_id,
            company_id,
            operator,
            canonical_receipt["nomor_laporan"],
            canonical_receipt["file_drive_url"],
            operator,
        )
        return int(new_id), "inserted"

    # Row exists. Mark submitted if not already, and set assigned_to if NULL.
    updates = []
    params: list[Any] = [existing["id"]]
    i = 2
    if not existing["oss_submitted"]:
        updates.append(
            f"oss_submitted=TRUE, oss_submitted_at=NOW(), oss_submitted_by=${i}",
        )
        params.append(operator)
        i += 1
    if not existing["oss_receipt_number"]:
        updates.append(f"oss_receipt_number=${i}")
        params.append(canonical_receipt["nomor_laporan"])
        i += 1
        updates.append(f"oss_receipt_file_url=${i}")
        params.append(canonical_receipt["file_drive_url"])
        i += 1
    if not existing["lkpm_assigned_to"]:
        updates.append(f"lkpm_assigned_to=${i}")
        params.append(operator)
        i += 1
    if not updates:
        return int(existing["id"]), "exists_noop"
    updates.append("updated_at=NOW()")
    q = f"UPDATE lkpm_reports SET {', '.join(updates)} WHERE id = $1"
    await conn.execute(q, *params)
    return int(existing["id"]), "updated"


async def upsert_receipt(
    conn: asyncpg.Connection, lkpm_report_id: int, receipt: dict[str, Any],
) -> str:
    """
    Insert a row into lkpm_receipts. UNIQUE on nomor_laporan.
    Returns action: 'inserted' | 'exists'.
    """
    existing = await conn.fetchval(
        "SELECT id FROM lkpm_receipts WHERE nomor_laporan = $1",
        receipt["nomor_laporan"],
    )
    if existing:
        return "exists"
    await conn.execute(
        """
        INSERT INTO lkpm_receipts (
            lkpm_report_id,
            nomor_laporan, nomor_kegiatan_usaha,
            kbli_code, kegiatan_usaha_desc,
            stage, oss_status,
            lokasi, tanggal_diterima,
            nama_perusahaan_oss,
            file_drive_id, file_drive_url, file_name,
            source, created_at, created_by, updated_at, updated_by
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, NOW(), $15, NOW(), $15
        )
        """,
        lkpm_report_id,
        receipt["nomor_laporan"],
        receipt["nomor_kegiatan_usaha"],
        receipt["kbli_code"] or None,
        receipt["kegiatan_usaha_desc"] or None,
        receipt["stage"] or None,
        receipt["oss_status"] or None,
        receipt["lokasi"] or None,
        date.fromisoformat(receipt["tanggal_diterima"]) if receipt["tanggal_diterima"] else None,
        receipt["nama_perusahaan_oss"] or None,
        receipt["file_drive_id"],
        receipt["file_drive_url"],
        receipt["file_name"],
        "drive_tax_team_q1_2026",
        MARKER_CREATED_BY,
    )
    return "inserted"


# ──────────────────────────────────────────────────────────────────────
# Core workflow
# ──────────────────────────────────────────────────────────────────────


def _receipt_tuple_to_dict(t: tuple[str, ...]) -> dict[str, Any]:
    (pt_key, fid, fname, nomor_laporan, nomor_kegiatan_usaha, kbli, desc,
     stage, status, lokasi, tanggal, nama_oss) = t
    return {
        "pt_key": pt_key,
        "file_drive_id": fid,
        "file_name": fname,
        "file_drive_url": f"https://drive.google.com/file/d/{fid}/view",
        "nomor_laporan": nomor_laporan,
        "nomor_kegiatan_usaha": nomor_kegiatan_usaha,
        "kbli_code": kbli,
        "kegiatan_usaha_desc": desc,
        "stage": stage,
        "oss_status": status,
        "lokasi": lokasi,
        "tanggal_diterima": tanggal,
        "nama_perusahaan_oss": nama_oss,
    }


async def run_import(conn: asyncpg.Connection, stats: dict[str, int]) -> dict[str, Any]:
    """
    Core loop. Caller owns the transaction.
    Returns a dict used to render the email/report.
    """
    # 1) ensure PT ITCHI DIGITAL BALI exists (minimal create if missing)
    itchi_id, itchi_created = await ensure_itchi_digital_bali_company(conn)
    PT_MAP["PT Itchi Digital Bali"]["company_id"] = itchi_id
    if itchi_created:
        stats["companies_minimal_created"] += 1

    # 2) apply name fixes on clients
    name_changes = await fix_client_typos(conn, stats)

    # 3) iterate receipts, grouped by pt_key
    grouped: dict[str, list[dict[str, Any]]] = {}
    for t in RECEIPTS:
        r = _receipt_tuple_to_dict(t)
        grouped.setdefault(r["pt_key"], []).append(r)

    report_rows: list[dict[str, Any]] = []
    for pt_key, receipts in grouped.items():
        pt_info = PT_MAP[pt_key]
        company_id = pt_info["company_id"]
        operator = pt_info["operator"]
        if company_id is None:
            logger.error(f"  ✗ {pt_key}: no company_id resolved — skipping")
            stats["errors"] += 1
            continue

        # Canonical receipt = the Disetujui one if any, else the first.
        canonical = next((r for r in receipts if r["oss_status"] == "Disetujui"), receipts[0])

        try:
            report_id, action = await upsert_lkpm_report(
                conn, company_id, pt_key, operator, canonical,
            )
            stats[f"lkpm_reports_{action}"] += 1
        except Exception as e:
            logger.error(f"  ✗ upsert_lkpm_report failed for {pt_key}: {e}")
            stats["errors"] += 1
            continue

        ins = exi = 0
        for r in receipts:
            try:
                a = await upsert_receipt(conn, report_id, r)
                if a == "inserted":
                    ins += 1
                    stats["receipts_inserted"] += 1
                else:
                    exi += 1
                    stats["receipts_exists"] += 1
            except Exception as e:
                logger.error(
                    f"  ✗ receipt {r['nomor_laporan']} for {pt_key}: {e}",
                )
                stats["errors"] += 1

        report_rows.append({
            "pt_key": pt_key,
            "company_id": company_id,
            "report_id": report_id,
            "operator": operator,
            "action": action,
            "receipts_total": len(receipts),
            "receipts_inserted": ins,
            "receipts_exists": exi,
            "approved_count": sum(1 for r in receipts if r["oss_status"] == "Disetujui"),
        })
        logger.info(
            f"  ✓ {pt_key:40s} company={company_id:>5}  rep={action:12s}  "
            f"receipts ins={ins} exists={exi}",
        )

    return {
        "pt_rows": report_rows,
        "name_changes": name_changes,
        "stats": stats,
    }


# ──────────────────────────────────────────────────────────────────────
# Event bus — pg_notify after successful commit
# ──────────────────────────────────────────────────────────────────────

# PG channel registered in backend/services/events/event_bus.py:PG_CHANNEL_MAP.
# Consumers (KG Tax sync, portal notifications, audit log) subscribe to the
# corresponding event type `lkpm.ingest_completed` via EventBus.
PG_CHANNEL_INGEST = "lkpm_ingest_completed"


async def emit_ingest_event(
    conn: asyncpg.Connection,
    result: dict[str, Any],
    source: str,
) -> bool:
    """
    Emit a pg_notify on `lkpm_ingest_completed` after the import tx commits.
    Must run AFTER the tx is closed — before that, other backends cannot see
    the new rows and reacting on the notify would hit an empty DB.

    Payload must be < 8KB (PG NOTIFY limit). We send only IDs, not full rows.
    """
    try:
        report_ids = [r["report_id"] for r in result["pt_rows"] if r.get("report_id")]
        company_ids = [r["company_id"] for r in result["pt_rows"] if r.get("company_id")]
        payload = {
            "quarter": "Q1",
            "year": 2026,
            "pt_count": len(result["pt_rows"]),
            "receipt_count": result["stats"]["receipts_inserted"],
            "report_ids": report_ids,
            "company_ids": company_ids,
            "source": source,
            "emitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        payload_str = json.dumps(payload, default=str)
        if len(payload_str) > 7500:
            logger.warning(
                f"EventBus: payload is {len(payload_str)} bytes, dropping company_ids",
            )
            payload.pop("company_ids", None)
            payload_str = json.dumps(payload, default=str)

        await conn.execute("SELECT pg_notify($1, $2)", PG_CHANNEL_INGEST, payload_str)
        logger.info(
            f"📡 pg_notify('{PG_CHANNEL_INGEST}'): "
            f"{payload['pt_count']} PT, {payload['receipt_count']} receipts",
        )
        return True
    except Exception as e:
        logger.error(f"Failed to emit ingest event: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────
# Email report via Brevo
# ──────────────────────────────────────────────────────────────────────

EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "")
# Schema: SendEmailRequest in backend/app/modules/notifications/router.py:62
# expects `to: str` (single address). Additional recipients go in `cc`
# (comma-separated). No `sender`, no `html_content` — use `body`.
REPORT_TO = "zero@balizero.com"
REPORT_CC = "tax@balizero.com"


def _render_email_html(result: dict[str, Any], dry_run: bool) -> str:
    s = result["stats"]
    title = "LKPM Q1 2026 — OSS receipts import report" + (" [DRY-RUN]" if dry_run else "")
    lines = [
        f"<h2 style='font-family:sans-serif'>{title}</h2>",
        f"<p>Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}</p>",
        "<h3>Summary</h3>",
        "<table cellpadding='4' style='border-collapse:collapse;font-family:sans-serif;font-size:13px'>",
        f"<tr><td>PDFs processed</td><td align='right'><b>{len(RECEIPTS)}</b></td></tr>",
        f"<tr><td>Receipts inserted</td><td align='right'>{s['receipts_inserted']}</td></tr>",
        f"<tr><td>Receipts already existed</td><td align='right'>{s['receipts_exists']}</td></tr>",
        f"<tr><td>lkpm_reports inserted</td><td align='right'>{s['lkpm_reports_inserted']}</td></tr>",
        f"<tr><td>lkpm_reports updated</td><td align='right'>{s['lkpm_reports_updated']}</td></tr>",
        f"<tr><td>lkpm_reports unchanged</td><td align='right'>{s['lkpm_reports_exists_noop']}</td></tr>",
        f"<tr><td>Minimal companies created</td><td align='right'>{s['companies_minimal_created']}</td></tr>",
        f"<tr><td>Client name fixes applied</td><td align='right'>{s['client_name_fixes']}</td></tr>",
        f"<tr><td>Errors</td><td align='right' style='color:red'>{s['errors']}</td></tr>",
        "</table>",
        "<h3>Per-PT breakdown</h3>",
        "<table cellpadding='6' style='border-collapse:collapse;font-family:sans-serif;font-size:12px;border:1px solid #ccc'>",
        "<tr style='background:#eee'><th>PT</th><th>company_id</th><th>Operator</th><th>Report action</th><th>Receipts</th><th>Disetujui</th></tr>",
    ]
    for row in sorted(result["pt_rows"], key=lambda r: r["pt_key"]):
        lines.append(
            "<tr>"
            f"<td>{row['pt_key']}</td>"
            f"<td align='right'>{row['company_id']}</td>"
            f"<td>{row['operator']}</td>"
            f"<td>{row['action']}</td>"
            f"<td align='right'>{row['receipts_inserted']} new / {row['receipts_exists']} existed</td>"
            f"<td align='right'>{row['approved_count']}</td>"
            "</tr>",
        )
    lines.append("</table>")
    if result["name_changes"]:
        lines.append("<h3>Client name fixes</h3><ul>")
        for c in result["name_changes"]:
            lines.append(f"<li>{c}</li>")
        lines.append("</ul>")
    lines.append(
        f"<p style='font-size:11px;color:#888'>Drive source folder: "
        f"<a href='{DRIVE_ROOT_FOLDER_URL}'>{DRIVE_ROOT_FOLDER_URL}</a></p>",
    )
    return "\n".join(lines)


async def send_email_report(result: dict[str, Any], dry_run: bool) -> bool:
    if not EMAIL_API_KEY:
        logger.warning("NUZANTARA_API_KEY not set — skipping email report")
        return False
    subject = (
        "[LKPM Q1 2026] OSS receipts import "
        + ("(DRY-RUN)" if dry_run else "committed")
    )
    body_html = _render_email_html(result, dry_run)
    payload = {
        "to": REPORT_TO,
        "cc": REPORT_CC,
        "subject": subject,
        "body": body_html,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                EMAIL_API_URL,
                json=payload,
                headers={"X-API-Key": EMAIL_API_KEY},
            )
            if r.status_code >= 400:
                logger.error(f"Email send failed: {r.status_code} {r.text[:400]}")
                return False
        logger.info(f"✉️  Report emailed to {REPORT_TO} (cc {REPORT_CC})")
        return True
    except Exception as e:
        logger.error(f"Email send exception: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────────────


class _DryRunRollback(Exception):
    """Sentinel to abort dry-run transaction cleanly."""


async def main(dry_run: bool, skip_email: bool, skip_event: bool) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 2

    logger.info("=" * 70)
    logger.info(f"LKPM Q1 2026 RECEIPTS import (dry_run={dry_run})")
    logger.info("=" * 70)
    logger.info(f"PT count        : {len(PT_MAP)}")
    logger.info(f"Receipts total  : {len(RECEIPTS)}")

    stats = {
        "companies_minimal_created": 0,
        "client_name_fixes": 0,
        "lkpm_reports_inserted": 0,
        "lkpm_reports_updated": 0,
        "lkpm_reports_exists_noop": 0,
        "receipts_inserted": 0,
        "receipts_exists": 0,
        "event_emitted": 0,
        "errors": 0,
    }

    conn = await asyncpg.connect(dsn, timeout=20)
    result: dict[str, Any] = {"pt_rows": [], "name_changes": [], "stats": stats}
    try:
        if dry_run:
            try:
                async with conn.transaction():
                    result = await run_import(conn, stats)
                    logger.info("\n⏪ DRY RUN — rolling back (no changes saved)")
                    raise _DryRunRollback()
            except _DryRunRollback:
                pass
        else:
            async with conn.transaction():
                result = await run_import(conn, stats)

        logger.info("\n" + "=" * 70)
        logger.info("STATS")
        logger.info("=" * 70)
        for k, v in stats.items():
            logger.info(f"  {k}: {v}")

        if not dry_run:
            logger.info("\n" + "=" * 70)
            logger.info("POST-COMMIT VERIFICATION")
            logger.info("=" * 70)
            tot_rec = await conn.fetchval("SELECT count(*) FROM lkpm_receipts")
            tot_q1 = await conn.fetchval(
                "SELECT count(*) FROM lkpm_reports WHERE quarter='Q1' AND year=2026 AND oss_submitted=TRUE",
            )
            logger.info(f"  lkpm_receipts total rows: {tot_rec}")
            logger.info(f"  lkpm_reports Q1 2026 submitted=TRUE: {tot_q1}")

            # Emit pg_notify AFTER tx committed (consumers must see new rows).
            # Run on a fresh connection context (current `conn` is fine — tx closed).
            if not skip_event and stats["errors"] == 0:
                emitted = await emit_ingest_event(
                    conn, result, source="tax_drive_manual_q1_2026",
                )
                if emitted:
                    stats["event_emitted"] = 1
    finally:
        await conn.close()

    if not skip_email:
        await send_email_report(result, dry_run)

    logger.info(
        f"\n{'DRY-RUN' if dry_run else 'COMMIT'} complete",
    )
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import 41 LKPM Q1 2026 OSS receipts")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually write to DB. Default is dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Rollback after pretending to write (default).",
    )
    parser.add_argument(
        "--skip-email",
        action="store_true",
        help="Skip sending the email report (still logs stats).",
    )
    parser.add_argument(
        "--skip-event",
        action="store_true",
        help="Skip emitting the pg_notify('lkpm_ingest_completed') event after commit.",
    )
    parser.add_argument(
        "--dump-json",
        metavar="PATH",
        help="Also write the parsed receipts payload as JSON to this path and exit.",
    )
    args = parser.parse_args()

    if args.dump_json:
        payload = [_receipt_tuple_to_dict(t) for t in RECEIPTS]
        with open(args.dump_json, "w", encoding="utf-8") as f:
            json.dump({"pt_map": PT_MAP, "receipts": payload}, f, indent=2, ensure_ascii=False)
        print(f"Wrote {len(payload)} receipts to {args.dump_json}")
        sys.exit(0)

    dry = not args.commit
    sys.exit(
        asyncio.run(
            main(dry_run=dry, skip_email=args.skip_email, skip_event=args.skip_event),
        ),
    )
