# TKA ↔ KBLI — Authoritative TKA Positive-List Dataset

**Status: research-grade authoritative national positive-list. NOT in the KBLI Navigator app.**

## What is authoritative

`tka_positive_list.json` — the **national** whitelist of foreign-worker (TKA) positions,
extracted verbatim from **Kepmenaker 228/2019** (`Kepmen_228_2019_OK.pdf`, 146 pages,
OCR via qwen2.5vl:7b, page-25 row-level-verified against a fresh independent re-OCR).

- **1562 jabatan** (job positions), each with its **ISCO/KBJI** code, Indonesian + English name,
  and (where present) requirements (`keterangan`).
- **Kategori: 100%** — every jabatan tagged with its Kategori (the level that maps to KBLI
  section A-U): Konstruksi, Pendidikan, Industri Pengolahan, Pertambangan dan Penggalian,
  Informasi dan Telekomunikasi, Aktivitas Keuangan dan Asuransi, Pengangkutan, Kesenian,
  Penyediaan Akomodasi, Pertanian, Pengadaan Listrik.
- **Golongan Pokok: 72%** — sub-sector tag where the OCR header was recoverable (best-effort).

## The regulatory model (why this shape)

The positive-list is a **single NATIONAL list valid across ALL KBLI codes** — it is NOT
KBLI-specific. A TKA may hold a jabatan on this list regardless of the company's specific
KBLI, subject to:
- **Closed-list** — Kepmenaker 349/2019: 18 HR/personalia jabatan **forbidden** to foreigners.
- **Director/Commissioner exemption** — those not managing personalia need no RPTKA jabatan slot (PP 34/2021).
- **RPTKA** — company-level licence; individual KITAS work permit flows from it.

## What is NOT done (honest gaps)

- **No per-KBLI join.** Deliberate (Zero, 2026-07-01): the decree's structure is national, not
  per-KBLI, so spreading it across 1559 codes would fake a specificity the law does not have.
  A KBLI→Kategori bridge is possible later but is a separate decision.
- **golongan_pokok null on 28%** of rows — OCR header lost on some continuation pages; not padded.
- **16 rows (~1%)** have ID+EN not perfectly split (OCR without column delimiter); text is verbatim, just unsegmented.

## Provenance
- `Kepmen_228_2019_OK.pdf` — https://jdih.kemnaker.go.id/asset/data_puu/Kepmen_228_2019_OK.pdf (Berlaku 2026-07-01)
- `pp_34_2021_penggunaan_tka.pdf` — umbrella RPTKA regulation
- Kepmenaker 349/2019 — closed-list (18 HR jabatan), extracted in the earlier Codex pass
- OCR: qwen2.5vl:7b on Mini-Pro2, 2026-07-01, num_ctx=8192
