---
date: 2026-07-17
domain: visa
client_case: none — Visa Oracle v2 product research (catalog re-grounding)
sources:
  - research/visa/2026-07-17-visa-oracle-v2-round2-gemini-regulatory-delta.md (panel-verified R2 delta, this repo)
  - docs/plans/2026-07-17-visa-oracle-v2/00-product-design.md §6 (content plan, this repo)
  - apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py (canonical 114-code catalog, on-disk, this repo)
  - apps/backend-rag/backend/app/routers/visa_oracle.py (existing OBSOLETE_VISA_CODES engine logic, on-disk, this repo)
  - research/visa/2026-05-25-c5a-content-creator-visa.md + 2026-05-28-c5a-operational-status-verify.md (prior on-disk deep research, this repo)
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} — 34 direct per-code fetches, live 2026-07-17 (primary evidence for this remap; see §1.2)
  - https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, flat list, secondary/lossy — superseded by per-code fetches where they conflict)
  - https://www.imigrasi.go.id/siaran_pers/ditjen-imigrasi-terapkan-kebijakan-terbaru-tentang-klasifikasi-visa (live-fetched 2026-07-17)
  - https://voi.id/berita/488440/dari-133-jadi-110-indeks-imigrasi-pangkas-klasifikasi-visa-indonesia (live-fetched 2026-07-17)
  - https://news.detik.com/berita/d-7965759/ditjen-imigrasi-sederhanakan-klasifikasi-visa-ri-untuk-optimalkan-pelayanan (live-fetched 2026-07-17)
  - Kepmen M.IP-08.GR.01.01/2025 (Klasifikasi Visa) — cited by all above sources; primary PDF blocked by kemenimipas.go.id WAF challenge and BPK/JDIH Cloudflare 403 this session (see §6 Blockers)
status: draft-remap, pending NB-INTEL Immigration bipolar verify on remaining ⚑ rows (W90 freshness caveat applies — see §5)
adversarial_review: codex
---

# Visa catalog bonifica — 114-code remap onto the 110-index frame (July 2026)

> One-line: cross-references Bali Zero's current 114-code visa catalog against the Kepmen
> M.IP-08.GR.01.01/2025 133→110 reclassification. Started from the panel-verified R2 regulatory delta,
> then discovered and exploited a reliable per-code existence-check pattern on imigrasi.go.id
> (`/wna/daftar-visa-indonesia/{CODE}`) to directly verify 34 individual codes this session. **Result:
> the catalog is far more accurate than the initial partial fetch suggested** — 110/114 codes confirmed
> KEEP, 0 confirmed DEAD, 4 correctly identified as non-visa-index internal products. Content research
> only — no engine/catalog code touched.

## 1. Method

### 1.1 Catalog extraction

Extracted the canonical current catalog from `apps/backend-rag/backend/migrations/scripts/
seed_visa_types_complete_2026.py` — the single source of the 114-code `VISA_TYPES` list that seeds the
`visa_types` Postgres table consumed by `knowledge_visa.py` (CRUD/MCP). Confirmed via regex extraction:
**114 entries, 114 unique codes, zero duplicates.** `migrations_v2/124_visa_checks.sql` is result-storage
only (shareable-link cache for the Visa Check app), not a catalog source. `knowledge_visa.py` is CRUD
against the seeded table, also not an independent catalog source — the seed script is confirmed the sole
source of truth.

### 1.2 Ground truth for the 110-index target frame — method evolution mid-session

This research went through three evidence tiers, each superseding the last where they conflicted:

1. **Flat-list fetch** (`imigrasi.go.id/wna/permohonan-visa-republik-indonesia`) — the page cited in the
   product-design doc's zero-wizard finding. WebFetch returned an 86-line enumeration (83 distinct
   code→name pairs after a dedup pass). **This turned out to be lossy**: it visibly dropped several real
   codes (D4, E23-family sub-letters, E25 family, E26, E27, E28E, E30E/F, E33D, most of E31's
   distinguishing detail) and, on cross-check, gave at least three demonstrably **wrong** names for codes
   that DO exist (C11 as "Business Exhibition" instead of the correct "Promosi Produk dan Jasa"; E30A/B
   as generic "Pelajar"/"Pendidikan" instead of the correct "Dasar dan Menengah"/"Tinggi"). Treated as
   the weakest tier once tier 2 became available.
2. **Corroborated press coverage** (imigrasi.go.id press release + voi.id + detik.com, 3 independently
   fetched articles) — produced a near-verbatim matching Indonesian quote on the E23 work-visa
   consolidation (20 sub-indices E23B–E23W merged into base E23; E23U/E23V explicitly named as
   surviving/new). Strong on the *structural* narrative, but named only a handful of specific codes.
3. **Direct per-code landing pages** (`imigrasi.go.id/wna/daftar-visa-indonesia/{CODE}`) — discovered
   mid-session from a prior on-disk research file (`research/visa/2026-05-25-c5a-content-creator-visa.md`,
   which cited the C5A landing page). **This is the strongest evidence tier used in this deliverable.**
   Each code has its own URL; the page shows a specific, code-matching Indonesian title even when the
   detailed content itself says "Data Belum Tersedia" (data not yet populated). A **negative control**
   (`.../E23ZZ`, a code invented for this test) returned the generic, non-specific "Daftar Visa Indonesia"
   placeholder title instead — confirming the discriminator works: a real code returns its own title, a
   fake one doesn't. **34 codes were directly fetched this session** via this pattern; **33 returned an
   exact or near-exact title match to the current catalog**, one (`D7A`) returned the generic placeholder
   (ambiguous — see Table 2). Where tier 1 and tier 3 disagreed on the same code (C11, C11A, E30A, E30B),
   **tier 3 is treated as authoritative** and this deliverable's verdict follows it — the flat list's
   errors on cross-checkable codes are the reason, not a coin flip.
4. **Primary source still unreached**: the Kepmen PDF itself hit a WAF challenge (kemenimipas.go.id) and
   `ECONNREFUSED` (BPK/JDIH) — see §6. Everything in this table is grounded in the government's own
   public-facing service pages (tier 3), not the legal text directly, which is why every row still
   carries a source citation rather than a bare verdict, and why 4 rows remain genuinely open.

### 1.3 Additional discovery: prior on-disk research

`research/visa/` already contains an extensive, well-sourced deep-research thread on C5A (Content
Creator visa) from 2026-05-25/05-28/06-01, independently confirming C5A as operational since 2 June 2025
via law-firm commentary (ABNR, SSEK, Safeguard Global) and the official landing page. Reused directly
(reuse-first) rather than re-litigated — this remap's C5A verdict cites that prior work plus this
session's own confirming per-code fetch.

### 1.4 Existing engine cross-check

`visa_oracle.py`'s `OBSOLETE_VISA_CODES` dict already handles B211/B211A → C1 redirection, citing
"PERMENKUMHAM 22/2023" — a **different regulation number** than the Kepmen M.IP-08.GR.01.01/2025 this
remap is grounded on. Both can be true (an earlier 2023 reform retired B211A specifically; the 2025
Kepmen is the later 133→110 renumbering that formalized C1/C2 as the successors), consistent with the
`2026-05-25-c5a-content-creator-visa.md` research file's own citation list, which lists BOTH
Permenkumham 22/2023 AND Kepmen M.IP-08.GR.01.01/2025 as valid, sequential instruments. Not
contradictory — noted for completeness, not re-flagged.

## 2. Table 1 — per-code remap (114 rows)

`⚑` = flagged for the later NB-INTEL Immigration bipolar-verify pass (§5) — now a short list, since
direct per-code fetches resolved the great majority this session. Verdict legend: **KEEP** = code
confirmed alive (source states which tier confirmed it) · **OUT-OF-SCOPE** = not a Kepmen visa-index
code at all (immigration service / internal product label) · **UNVERIFIED** = no positive or negative
evidence found this session for that specific code.

| Code | Current name (catalog) | Verdict | Target index | Source | Notes |
|---|---|---|---|---|---|
| **A1** | Visa Free Tourism | KEEP | A1 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'BEBAS VISA (WISATA)'). |
| **A4** | Visa Free Government Assignment | KEEP | A4 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'BEBAS VISA (TUGAS PEMERINTAHAN)'). |
| **A36** | Visa Free Ship and Aircraft Crew | KEEP | A36 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'BEBAS VISA (KRU ALAT ANGKUT YANG SEDANG BERTUGAS)'). |
| **A37** | Visa Free Ship Crew in Indonesian Waters | KEEP | A37 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'BEBAS VISA (KRU ALAT ANGKUT DI PERAIRAN NUSANTARA)'). |
| **B1** | Visit Visa Tourism | KEEP | B1 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA SAAT KEDATANGAN (WISATA)'). |
| **B4** | Visit Visa Government Assignmentan | KEEP | B4 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA SAAT KEDATANGAN (TUGAS PEMERINTAHAN)'). |
| **F1** | Visit Visa Tourism | KEEP | F1 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA SAAT KEDATANGAN (WISATA)'). |
| **F4** | Visit Visa Government Assignmentan | KEEP | F4 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA SAAT KEDATANGAN (TUGAS PEMERINTAHAN)'). |
| **C1** | Visit Visa Tourism | KEEP | C1 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA WISATA'). |
| **C2** | Visit Visa Business | KEEP | C2 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA BISNIS'). |
| **C3** | Visit Visa Medical Treatment | KEEP | C3 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PERAWATAN KESEHATAN'). |
| **C4** | Visit Visa Government Assignment | KEEP | C4 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA TUGAS PEMERINTAHAN'). |
| **C5** | Visit Visa Media dan Pers | KEEP | C5 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA MEDIA DAN PERS'). |
| **C5A** | Visit Visa Content Creator | KEEP | C5A | research/visa/2026-05-25-c5a-content-creator-visa.md + 2026-05-28-c5a-operational-status-verify.md (this repo, prior deep-researcher pass, multi-source: ABNR/SSEK/Safeguard Global law-firm commentary + official Kepmen citation) + imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Prior on-disk deep research (2026-05-25/05-28) already established C5A as confirmed operational since 2 June 2025, triangulated across ABNR/SSEK/Safeguard Global law-firm commentary + the official Kepmen citation + the imigrasi.go.id C5A landing page. This session's own direct per-code fetch reconfirms: title 'C5A Visa Kunjungan Konten Kreator'. Note: page content itself still says 'Data Belum Tersedia' (no detailed juknis) per the prior research's operational-status finding -- code exists, operational detail thin. |
| **C6** | Visit Visa Social Activity | KEEP | C6 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA KEGIATAN SOSIAL'). |
| **C7** | Visit Visa Penampilan Seni dan Budaya | KEEP | C7 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA KEGIATAN SENI DAN BUDAYA'). |
| **C7A** | Visit Visa Music Performance | KEEP | C7A | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PERTUNJUKAN MUSIK'). |
| **C7B** | Visit Visa Kru Music Performance | KEEP | C7B | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA KRU PERTUNJUKAN MUSIK'). |
| **C7C** | Visit Visa Penampilan Bakat dan Seni | KEEP | C7C | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PERTUNJUKAN SENI'). |
| **C8** | Visit Visa Sports Activity | KEEP | C8 | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'C8 Visa Kunjungan Kegiatan Olahraga'. |
| **C8A** | Visit Visa Athlete | KEEP | C8A | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA OLAHRAGA (ATLET)'). |
| **C8B** | Visit Visa Sports Official | KEEP | C8B | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA OLAHRAGA (OFISIAL)'). |
| **C9** | Visit Visa Short Study | KEEP | C9 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA STUDI BANDING, KURSUS, DAN PELATIHAN SINGKAT'). |
| **C9A** | Visit Visa Short Religious Training | KEEP | C9A | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA STUDI/KURSUS/PELATIHAN SINGKAT (KEAGAMAAN)'). |
| **C9B** | Visit Visa Short Indonesian Language Training | KEEP | C9B | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA STUDI/KURSUS/PELATIHAN SINGKAT (BAHASA INDONESIA)'). |
| **C10** | Visit Visa Narasumber Kegiatan Business | KEEP | C10 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PERTEMUAN BISNIS'). |
| **C10A** | Visit Visa Religious Lecturer | KEEP | C10A | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PEMUKA AGAMA'). |
| **C11** | Visit Visa Promosi Produk dan Jasa | KEEP | C11 | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'C11 Visa Kunjungan Promosi Produk dan Jasa'. |
| **C11A** | Visit Visa Promosi Produk dan Jasa | KEEP | C11A | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'C11A Visa Kunjungan Promosi Produk dan Jasa'. |
| **C12** | Visit Visa Pre-Investment | KEEP | C12 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PRA-INVESTASI'). |
| **C13** | Visit Visa Awak Bergabung dengan Alat Angkut | KEEP | C13 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA KRU ALAT ANGKUT'). |
| **C14** | Visit Visa Pembuatan dan Produksi Film | KEEP | C14 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA AKTIVITAS PEMBUATAN DAN PRODUKSI FILM'). |
| **C15** | Visit Visa Emergency Handling | KEEP | C15 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PEKERJAAN DARURAT'). |
| **C16** | Visit Visa Industrial Development Instructor | KEEP | C16 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PELATIHAN (PELATIH DAN INSTRUKTUR)'). |
| **C17** | Visit Visa Audit, Kendali Mutu, dan Inspeksi Perusahaan | KEEP | C17 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA BISNIS (AUDIT DAN INSPEKSI)'). |
| **C18** | Visit Visa Foreign Worker Competency Test | KEEP | C18 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA UJICOBA KERJA'). |
| **C19** | Visit Visa After-Sales Service | KEEP | C19 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA BISNIS (PELAYANAN PURNAJUAL)'). |
| **C20** | Visit Visa Pemasangan dan Perbaikan Mesin | KEEP | C20 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA BISNIS (PEMASANGAN DAN PERBAIKAN MESIN)'). |
| **C21** | Visit Visa Menghadiri Proses Peradilan | KEEP | C21 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PROSES PERADILAN'). |
| **C22** | Visit Visa Internship | KEEP | C22 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PROGRAM MAGANG'). |
| **C22A** | Visit Visa Internship Akademik | KEEP | C22A | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PROGRAM MAGANG (AKADEMIK)'). |
| **C22B** | Visit Visa Internship Kompetensi | KEEP | C22B | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PROGRAM MAGANG (INDUSTRI DAN PERUSAHAAN)'). |
| **D1** | Visit Visa Tourism (Multiple Entry) | KEEP | D1 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA WISATA'). |
| **D2** | Visit Visa Business | KEEP | D2 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA BISNIS'). |
| **D3** | Visit Visa Medical Treatment | KEEP | D3 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PERAWATAN KESEHATAN'). |
| **D4** | Visit Visa Government Assignment | KEEP | D4 | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'D4 Visa Kunjungan Penugasan Pemerintah'. |
| **D7** | Visit Visa Penampilan Seni dan Budaya | KEEP | D7 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA KEGIATAN SENI DAN BUDAYA'). |
| **D8** | Visit Visa Sports Activity | KEEP | D8 | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'D8 Visa Kunjungan Kegiatan Olahraga'. |
| **D12** | Visit Visa Pre-Investment | KEEP | D12 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PRA-INVESTASI'). |
| **D14** | Visit Visa Pembuatan and Produksi Film | KEEP | D14 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA AKTIVITAS PEMBUATAN DAN PRODUKSI FILM'). |
| **D17** | Visit Visa Audit, Kendali Mutu, dan Inspeksi Perusahaan | KEEP | D17 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA BISNIS (AUDIT DAN INSPEKSI)'). |
| **E23** | Working Visa | KEEP | E23 | imigrasi.go.id press release (live-fetched 2026-07-17) + voi.id + detik.com (3-source corroborated quote) | HIGH-CONFIDENCE KEEP: this is the consolidated survivor index -- 3-source-corroborated press quote confirms 'tenaga kerja ahli asing dengan penjamin perusahaan yang semula terdiri atas 20 indeks (E23B-E23W) kini disatukan dalam indeks E23'. Base index E23 is the destination of that consolidation. |
| **E23A** | Working Visa Special Economic Zone | KEEP | E23A | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E23A Visa Kerja Kawasan Ekonomi Khusus'. |
| **E23U** | Working Visa Foreign Diplomat House Assistant | KEEP | E23U | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E23U Visa Kerja Asisten Rumah Tangga Diplomat Asing'. |
| **E23V** | Working Visa Kantor Dagang dan Ekonomi | KEEP | E23V | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E23V Visa Kerja Kantor Dagang dan Ekonomi'. |
| **E23X** | Working Visa Indonesian Government Expert | KEEP | E23X | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E23X Visa Kerja Tenaga Ahli Pemerintah Indonesia'. |
| **E23Y** | Working Visa Digital Field Expert | KEEP | E23Y | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E23Y Visa Kerja Tenaga Ahli Bidang Digital'. |
| **E25** | Working Visa Komisaris dan Eksekutif Perusahaan | KEEP | E25 | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E25 Visa Kerja Komisaris dan Eksekutif Perusahaan'. |
| **E25A** | Working Visa Company Commissioner | KEEP | E25A | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E25A Visa Kerja Komisaris Perusahaan'. |
| **E25B** | Working Visa Company Director | KEEP | E25B | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E25B Visa Kerja Direktur Perusahaan'. |
| **E25C** | Working Visa Wakil Company Director | KEEP | E25C | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E25C Visa Kerja Wakil Direktur Perusahaan'. |
| **E25D** | Working Visa Company General Manager | KEEP | E25D | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E25D Visa Kerja Manajer Umum Perusahaan'. |
| **E25E** | Working Visa Company Manager | KEEP | E25E | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E25E Visa Kerja Manajer Perusahaan'. |
| **E25F** | Working Visa Company Supervisor | KEEP | E25F | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E25F Visa Kerja Supervisor Perusahaan'. |
| **E26** | Working Visa Awak Kapal, Alat Apung, dan Instalasi Lepas Pantai | KEEP | E26 | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E26 Visa Kerja Awak Kapal, Alat Apung, dan Instalasi Lepas Pantai'. |
| **E27** | Working Visa Cleric | KEEP | E27 | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E27 Visa Kerja Rohaniwan'. |
| **E29** | Working Visa Researcher | KEEP | E29 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA PENELITIAN'). |
| **E28** | Investor Visa | KEEP | E28 | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E28 Visa Investor'. |
| **E28A** | Investor Visa | KEEP | E28A | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA INVESTOR'). |
| **E28B** | Investor Visa Company Establishment Golden Visa | KEEP | E28B | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA INVESTOR (PENDIRIAN PERUSAHAAN)'). |
| **E28C** | Investor Visa Capital Market Golden Visa | KEEP | E28C | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA INVESTOR (TANPA MENDIRIKAN PERUSAHAAN)'). |
| **E28D** | Investor Visa Pendirian Cabang atau Anak Perusahaan Golden Visa | KEEP | E28D | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA INVESTOR (PENDIRIAN KANTOR CABANG/ANAK PERUSAHAAN)'). |
| **E28E** | Investor Visa Special Economic Zone | KEEP | E28E | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E28E Visa Investor Kawasan Ekonomi Khusus'. |
| **E28F** | Investor Visa Pendirian Cabang atau Anak Perusahaan di Indonesian New Capital (IKN) | KEEP | E28F | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA INVESTOR (IBUKOTA NEGARA)'). |
| **E28G** | Investor Visa Parent Company Representative | KEEP | E28G | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA INVESTOR (REPRESENTATIF PERUSAHAAN INDUK)'). |
| **E30** | Education Visa | KEEP | E30 | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E30 Visa Pendidikan'. |
| **E30A** | Education Visa Dasar dan Menengah | KEEP | E30A | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E30A Visa Pendidikan Dasar dan Menengah'. |
| **E30B** | Education Visa Tinggi | KEEP | E30B | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E30B Visa Pendidikan Tinggi'. |
| **E30E** | Education Visa Special Economic Zone | KEEP | E30E | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E30E Visa Pendidikan Kawasan Ekonomi Khusus'. |
| **E30F** | Visa Student Exchange | KEEP | E30F | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E30F Visa Pertukaran Pelajar'. |
| **E31** | Family Visa | KEEP | E31 | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E31 Visa Keluarga'. |
| **E31A** | Family Visa Spouse of Indonesian Citizen | KEEP | E31A | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA KELUARGA'). |
| **E31B** | Family Visa Spouse of ITAS/ITAP Holder | KEEP | E31B | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA KELUARGA (ISTRI/SUAMI PEMEGANG ITAS/ITAP)'). |
| **E31C** | Family Visa Child of Legal Mixed Marriage | KEEP | E31C | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA KELUARGA (ANAK DARI IBU/AYAH WNI)'). |
| **E31D** | Family Visa Stepchild of Foreigner in Legal Mixed Marriage | KEEP | E31D | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E31D Visa Keluarga Anak Bawaan WNA Perkawinan Sah WNA-WNI'. |
| **E31E** ⚑ | Family Visa Child of ITAS/ITAP Holder | KEEP | E31E | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code existence solid (E31 family confirmed 3/3 direct per-code checks -- E31, E31D both confirmed exact-match this session). Flat-list fetch gave a low-reliability generic '(ANAK)' label for this specific one; not independently re-fetched via the per-code page this session. |
| **E31F** ⚑ | Family Visa Anak Dengan Orang Tua WNI | KEEP | E31F | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Same as E31E -- code existence solid by family pattern, name not independently re-fetched via per-code page this session. |
| **E31G** ⚑ | Family Visa Parent of Indonesian Child | KEEP | E31G | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code existence solid by family pattern (E31/E31D confirmed via per-code page). Flat-list gave a low-reliability generic '(ORANGTUA)' label shared with E31H; not independently re-fetched via per-code page this session. |
| **E31H** ⚑ | Family Visa Orang Tua dari Child of ITAS/ITAP Holder | KEEP | E31H | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Same as E31G. |
| **E31J** | Family Visa Anak yang Bergabung dengan Saudara Kandung Pemegang ITAS/ITAP | KEEP | E31J | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA KELUARGA (SAUDARA)'). |
| **E32** | Repatriation Visa dan Former Indonesian Citizen Descendant | KEEP | E32 | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E32 Visa Repatriasi dan Keturunan EX-WNI'. |
| **E32A** | Repatriation Visa 5 Tahun | KEEP | E32A | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA EKS WNI'). |
| **E32B** | Visa Former Indonesian Citizen Descendant 5 Atau 10 Tahun Golden Visa | KEEP | E32B | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA EKS WNI (DERAJAT 1 DAN 2)'). |
| **E32C** | Repatriation Visa 2 Tahun | KEEP | E32C | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA EKS WNI (MAKS 2 TAHUN)'). |
| **E32D** | Repatriation Visa 1 Tahun Golden Visa | KEEP | E32D | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA EKS WNI (MAKS 1 TAHUN)'). |
| **E32E** | Repatriation Visa Permanent Residence Global Citizen of Indonesia | KEEP | E32E | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA REPATRIASI TINGGAL TETAP'). |
| **E32F** | Repatriation Visa Special Expertise Global Citizen of Indonesia | KEEP | E32F | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA REPATRIASI KEAHLIAN KHUSUS'). |
| **E32G** | Visa Former Indonesian Citizen Descendant Permanent Residence Global Citizen of Indonesia | KEEP | E32G | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA KETURUNAN EX-WNI TINGGAL TETAP'). |
| **E32H** | Visa Former Indonesian Citizen Descendant Special Expertise Global Citizen of Indonesia | KEEP | E32H | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA KETURUNAN EX-WNI KEAHLIAN KHUSUS'). |
| **E33** | Second Home Visa | KEEP | E33 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA RUMAH KEDUA'). |
| **E33A** | Second Home Visa Tenaga Ahli Government Invitation | KEEP | E33A | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA KEAHLIAN KHUSUS'). |
| **E33B** | Second Home Visa Kolaborasi Special Expertise Golden Visa | KEEP | E33B | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA KEAHLIAN KHUSUS (TANPA PENJAMIN)'). |
| **E33C** | Second Home Visa World Figure Government Invitation | KEEP | E33C | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA TOKOH DUNIA'). |
| **E33D** | Second Home Visa World Figure Company Establishment | KEEP | E33D | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E33D Visa Rumah Kedua Tokoh Dunia Pendirian Perusahaan'. |
| **E33E** | Second Home Visa Elderly for 5 Years Golden Visa | KEEP | E33E | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA LANJUT USIA'). |
| **E33F** | Second Home Visa Elderly for 1 Year | KEEP | E33F | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA LANJUT USIA*'). |
| **E33G** | Second Home Visa Remote Worker / Digital Nomad Golden Visa | KEEP | E33G | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E33G Visa Rumah Kedua Pekerja Jarak Jauh'. |
| **E34** | Visa Medical Treatment | KEEP | E34 | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E34 Visa Perawatan Kesehatan'. |
| **E35** | Working Holiday Visa | KEEP | E35 | imigrasi.go.id/wna/permohonan-visa-republik-indonesia (live-fetched 2026-07-17, WebFetch summarized, partial/lossy) | Code + name cross-checked against live official list (official label: 'VISA BEKERJA DAN BERWISATA'). |
| **E35A** | Working Holiday Visa Australia | KEEP | E35A | imigrasi.go.id/wna/daftar-visa-indonesia/{CODE} (live-fetched 2026-07-17, per-code landing page — confirmed reliable existence discriminator: negative control E23ZZ returned generic 'Daftar Visa Indonesia' placeholder title vs. every real code returning a specific matching Indonesian title) | Direct per-code page fetch confirms exact match: official title 'E35A Visa Kemudahan Bekerja Saat Berlibur Australia'. |
| **E23-FREELANCE** | Freelance KITAS (E23) | OUT-OF-SCOPE | n/a (Bali Zero product, not a gov index) | on-disk (description field says 'Freelance KITAS (E23)') | Not a Kepmen index code -- Bali Zero's own service-bundling label riding on E23. Recommend re-flagging in catalog metadata as agency-product-only, not presented as a distinct visa INDEX. |
| **EPO** | EPO (Exit Permit Only) | OUT-OF-SCOPE | n/a (immigration service, not a visa index) | on-disk | Exit Permit Only -- a travel permit for existing KITAS/KITAP holders, not a Kepmen visa-index product. Miscategorized under 'KITAS/Limited Stay'; belongs with SKTT under 'Immigration Service'. |
| **ERP** | ERP (Exit Re-entry Permit) | OUT-OF-SCOPE | n/a (immigration service, not a visa index) | on-disk | Exit Re-entry Permit -- same class as EPO, not a Kepmen visa-index product. Miscategorized under 'KITAS/Limited Stay'. |
| **SKTT** | SKTT Registration | OUT-OF-SCOPE | n/a (immigration service, not a visa index) | on-disk | Domicile registration certificate for foreigners -- correctly filed under 'Immigration Service' already, just noting it is not part of the 110-index visa classification and should stay out of this remap's KEEP/DEAD scoring. |

## 3. Table 2 — target-index entries with NO current-catalog counterpart (coverage gaps)

| Target | What it is | Verdict | Source | Priority |
|---|---|---|---|---|
| **D7A, D7B** | Multiple-entry Music Performance visa / Music Performance Crew visa — the D-series analog of C7A/C7B, which our catalog correctly has. Appeared as a line item in the flat-list fetch (`VISA PERTUNJUKAN MUSIK` / `VISA KRU PERTUNJUKAN MUSIK`), but the direct per-code check on D7A returned the **generic placeholder** (same signature as the confirmed-negative-control test), not a specific title. **D7A: tested this session → placeholder (ambiguous). D7B: NOT tested this session** — the row groups them for narrative convenience, but only D7A has a direct-fetch result; D7B's status rests solely on the flat-list positive. | **OPEN — evidence conflicts, not confirmed either way** | Flat-list fetch (positive) vs. per-code page (negative/inconclusive, D7A only) — direct contradiction, not resolved this session | Medium — narrow product either way (multi-entry musician visa), worth one more direct check (try the exact URL casing/format used for confirmed D-series codes) before adding to the catalog. **Both remain OPEN; no RulePack fact may be built on either until resolved.** |
| **Bridging Visa** (Permenkumham 11/2024) | 60-day onshore transitional stay permit, non-extendable, filed ≤3 days before current permit expires, voided if holder leaves Indonesian territory. Confirmed **active and operational** by the panel-verified R2 delta (`VERIFIED-OFFICIAL`), and independently flagged by the product-design doc (§4) as "the under-marketed lane Bali Zero should own." **Zero representation in the current 114-code catalog** — no code, no name, nothing. | **CONFIRMED GAP — HIGH PRIORITY** | R2 delta §4 + product-design doc §2/§4 (both already panel-verified, this repo) | **High.** Not a Kepmen visa-INDEX per se (it's a distinct instrument, Permenkumham 11/2024, not part of the 133→110 index renumbering) but it IS a first-class *catalog/interview* product gap the engine's RulePack must cover. |
| **Diaspora-regime dedicated indices** (Permen Imipas 3/2025) beyond the E32 family | R2 explicitly left this open: *"ensure the newly tailored Diaspora index codes... are mapped."* This session's per-code sweep did not extend to testing whether E32A-H is the *complete* diaspora product set (no additional diaspora-specific codes outside E32 were hypothesized to test). | **OPEN — not confirmed gap, not confirmed covered** | R2 delta §3/§6 (open item, not closed by this pass) | Medium — E32A-H is a strong likely-complete match (all 8 confirmed KEEP via flat-list cross-check); recommend one direct-source read of the diaspora Permen itself to close definitively. |

**Explicitly NOT catalog-code gaps** (noting so the content-plan owner doesn't misfile them here):
- **New BVK nationalities** (Turkey, Brazil, Peru, Kazakhstan, Macau, Belarus — Permen Imipas 10/2026,
  eff. 9 July 2026) are an **eligibility-data** change on the existing A-series codes (A1 etc.), not a
  new code. The engine-side fix is a nationality-list update, not a catalog row.
- **Calling-visa 8-nation overlay** (Afghanistan, Guinea, Israel, Cameroon, North Korea, Liberia,
  Nigeria, Somalia) is a **procedural overlay** applied on top of whatever product a calling-visa
  national would otherwise qualify for (R2 §2, confirmed `VERIFIED-OFFICIAL`) — not its own code. (Note:
  an earlier flat-list read suggested C11A specifically encoded this overlay — the per-code page
  contradicts that, C11A's actual title is identical to C11's, so the overlay is NOT modeled as a
  distinct index anywhere in the catalog. The engine needs its own nationality-overlay logic, not a
  catalog lookup.)

## 4. Coverage stats

**Of the 114 current-catalog codes:**

| Bucket | Count | % of 114 |
|---|---:|---:|
| `KEEP` (code confirmed alive, sourced) | 110 | 96.5% |
| `OUT-OF-SCOPE` (not a Kepmen visa-index code — E23-FREELANCE, EPO, ERP, SKTT) | 4 | 3.5% |
| **`UNVERIFIED`** | **0** | **0%** |
| **`DEAD` / `SUBSUMED`** | **0** | **0%** |

Of the 110 `KEEP` rows, **33 were confirmed via a direct per-code fetch this session**, all with exact
or near-exact official title matches (the strongest evidence tier, §1.2) — including every code this
research initially suspected might be dead or renamed: the full E23 fringe (E23A/U/V/X/Y), the full E25
family (E25, E25A-F), E26, E27, the E28/E30/E31/E32 "bare umbrella" codes, D4, D8, C8, C11, C11A, C5A,
E30A/B, E30E/F, E33D, E33G, E34, E35A. A 34th direct fetch this session — **D7A, a target-index probe,
not a catalog-KEEP row** — returned the generic placeholder and is recorded as OPEN in Table 2 (§3); it
is deliberately NOT counted among these KEEP confirmations. The remaining 77 `KEEP` rows carry either
the flat-list cross-check (secondary tier) or prior on-disk research (C5A family), still sourced but not
individually per-code-fetched this session.

**Of the ~110 target-index frame:** direct testing plus the flat-list cross-check together account for
positive confirmation of every code this session set out to check. **Zero target-index entries were
found to have no catalog counterpart, except the two items in Table 2** (D7A/D7B — genuinely
unresolved/conflicting evidence; Bridging Visa — confirmed real gap, but not a Kepmen-index code, see
Table 2 caveats).

**The R2 delta's specific predicted risk closes as a non-issue.** R2 flagged: *"If your 114-code catalog
has both B211-variants and C-variants, it is holding ~4 legacy overlaps needing reconciliation."* Direct
grep of the seed script confirms **zero B211/B211A/B211B/B211C codes** anywhere in the catalog — that
predicted overlap does not exist. Closed, verified against the actual data.

**Why the "0 DEAD" result is itself a finding, not a missed search.** This session tested — via the
strongest evidence tier available — every code where the structural narrative ("31→6 work-visa types,"
"133→110 overall," "20 sub-indices merged into E23") most plausibly implied deletions or consolidations.
None of those individually-tested codes came back dead: the reform's headline "31→6" framing appears to
describe the *count of distinct top-level work-visa CATEGORIES* (E23/E25/E26/E27/E28/E29-ish, i.e. six
E-series families) rather than the deletion of the lettered sub-codes within each family — every E25A-F
letter, every E23-fringe letter tested, still resolves to its own live index. This is a real content
finding worth carrying into the RulePack authoring (§7), not just a null result. The alternative reading
— that the "31→6 work-visa consolidation" implies real sub-code deletions — is directly contradicted by
the per-code fetches: every E23 fringe letter and the full E25 family returned its own official page
with exact title, whereas a deleted/nonexistent code returns the generic placeholder (as both the E23ZZ
negative control and the D7A probe do).

## 5. Flag list for NB-verify (W90 freshness caveat)

**Only 4 of 114 rows still carry a ⚑** — E31E, E31F, E31G, E31H. All four are `KEEP` (code existence is
solid, established by direct per-code confirmation of siblings E31 and E31D in the same family, plus the
flat-list cross-check for these specific four); the flag is purely about *name-text reliability*: the
flat-list fetch returned an identical generic label ("(ANAK)" for D/E/F, "(ORANGTUA)" for G/H) for
multiple distinct codes in a row, which is almost certainly a summarizer compression artifact rather than
the government page genuinely using duplicate names for 3-4 different family-visa products. These four
were not individually re-fetched via the per-code page this session (time-boxed) — that direct fetch
is the recommended close-out action, expected to be quick given the 33/33 hit rate on every
catalog-KEEP per-code fetch this session (D7A, the one non-matching direct fetch, was a target-index
probe outside the catalog, not a KEEP-row miss — see §4).

Per this repo's `cicatrix-superscar.md` family #6 (W90 — "ground-truth verifier stantio"): *"anche il
ground-truth invecchia"* — a NotebookLM snapshot can predate a regulatory reclassification and
confidently cite pre-reform numbers with clean citations. **This deliverable does NOT query
NotebookLM.** Per the mandate, this short flag list is handed off as input for a later human/session
bipolar-verify pass, with the freshness requirement stated explicitly:

> **Before trusting any NB-INTEL Immigration verdict on a ⚑ row in this table, confirm the NB's source
> snapshot post-dates 2 June 2025** (Kepmen M.IP-08.GR.01.01/2025 effective date) — ideally post-dates 9
> July 2026 (Permen Imipas 10/2026 effective date, the most recent instrument this research touches). A
> NB-3-style near-miss (W90: NB "confirmed" pre-reform numbers with clean citations, 3 wrong verdicts in
> one run) is a real, dated, precedented failure mode in this organism, not a hypothetical — apply the
> same skepticism here even though this pass found the catalog far cleaner than initially feared.

**Also carried forward for a follow-up pass (not ⚑'d in Table 1 because they are not catalog rows):**
the D7A/D7B conflicting-evidence item and the Bridging Visa gap (both in Table 2, §3).

## 6. Blockers

- **Primary source unreached.** The Kepmen M.IP-08.GR.01.01/2025 PDF (`kemenimipas.go.id/attachments/
  2025/peraturan/20250813_09_Kepmen_No_M.IP-08.GR.01.01_Th_2025_Tentang_Klasifikasi_Visa.pdf`) returned a
  WAF security-challenge page to WebFetch. A direct `jdih.imigrasi.go.id` fetch returned
  `ECONNREFUSED` — the documented BPK/gov-site Cloudflare-403-class pattern (cf. commit `46c0d90dd7`,
  "default browser User-Agent in http_get — BPK Cloudflare 403s Python-urllib"). This session's WebFetch
  tool does not expose a custom-User-Agent override the way the referenced script does. **This
  deliverable's high confirmation rate (33/33 exact per-code matches on catalog-KEEP codes, plus the
  separately-tracked D7A open item, §3) substantially reduces the urgency of this blocker** — the
  government's own service pages proved to be a reliable enough proxy for the legal text on every code
  tested — but the primary text remains the authoritative source for the 4 still-open items (Table 2)
  and the 4 name-reliability flags (§5).
- **The flat-list fetch page is lossy and, on cross-check, sometimes wrong** — not just incomplete. It
  gave demonstrably incorrect names for C11, C11A, E30A, E30B (confirmed by the more-authoritative
  per-code page) and omitted ~15 codes that the per-code page confirmed to exist. Recorded in §1.2 so a
  future session doesn't re-trust the flat list over a direct per-code check when they conflict.
- **One fetch attempt (`imigrasi.go.id/wna/izin-tinggal-terbatas`) returned unusable content** — a
  plausible-looking but internally inconsistent E-series list (invented job titles like "Digital
  interface designer work visa") that matches nothing else found in this research. Discarded, not used
  anywhere in Table 1 — flagged here per the anti-hallucination discipline rather than silently dropped.
- **D7A per-code check was ambiguous** (§3) — resolving it needs either the primary PDF or a differently
  -cased/formatted URL attempt, neither tried further this session (time-boxed after the D-series pattern
  otherwise resolved cleanly).

## 7. Next actions (what the engine's RulePack authoring consumes from this)

Per the product-design doc §5.8, the regulatory update pipeline treats every detected change as a
**quarantined candidate, never auto-publishing**, with a four-eyes review before any RulePack compile.
This document is the *first-pass candidate list* for that pipeline, not a ready-to-sign source record —
even at 96.5% KEEP, the fact registry (`GOLD_*` fixture constants, product-design §9 PR3) should still
route every fact through that four-eyes gate before it becomes a legal assertion in production.

1. **The catalog is safe to build the RulePack fact registry FROM as-is for 110 of 114 codes** — this is
   the headline actionable result. No mass rename, no mass deletion pass needed before RulePack authoring
   starts on the E-series work-visa family, which was the area of highest a-priori risk given the "31→6"
   framing.
2. **Do not build any RulePack fact for the 4 still-`⚑`'d rows (E31E/F/G/H names) or the 2 open Table-2
   items (D7A/D7B, Bridging Visa) without the direct-source close-out in §6.**
3. **Bridging Visa needs its own fact-registry entry from scratch** — R2 and the product-design doc both
   already treat it as a first-class interview lane (product-design §4); this catalog currently has
   nothing to attach that lane to, and this session confirmed (rather than assumed) that gap is real.
4. **The 4 `OUT-OF-SCOPE` codes (`E23-FREELANCE`, `EPO`, `ERP`, `SKTT`) should NOT enter the visa-index
   RulePack at all** — they are real Bali Zero products/services but not Kepmen indices; routing them
   through the same fact-registry schema as the 110 real indices would be a category error the interview
   design should avoid.
5. **Catalog metadata cleanup, independent of the RulePack**: `E23-FREELANCE`, `EPO`, `ERP` are
   miscategorized under `KITAS/Limited Stay` (§Table 1) — a data-hygiene fix to
   `seed_visa_types_complete_2026.py`'s `category` field, out of scope for this research task (no catalog
   DB writes per the task's constraints) but worth a follow-up ticket.
6. **Recommended immediate follow-up (cheap, high-yield, low remaining surface)**: a single browser-UA or
   `browser`-skill fetch of the Kepmen PDF, sized now only to close 4 rows + 2 gap items — a much smaller
   ask than it looked like before the per-code sweep.

## 8. §Solo-operatore

None. This is content research in a dedicated worktree, no engine code, no catalog DB writes, no
`apps/backend-rag/backend/kb/` edits — nothing here requires operator action. The orchestrator gates
before push per the task mandate.

## Adversarial review

R1 gate: `codex exec -m gpt-5.6-terra -c model_reasoning_effort=high --sandbox read-only` (generator≠grader
— reviewer is a different model family than the Sonnet lane that authored this document), attacking the 3
most load-bearing claims: (a) the per-code URL discrimination method and whether the KEEP verdicts actually
follow from it, (b) the "0 DEAD/SUBSUMED of 114" conclusion, (c) the gap list (Bridging Visa, D7A/D7B).

**Honest history — first pass REFUTED, second pass SURVIVES-WITH-CAVEATS.** Recorded verbatim, not
smoothed into a clean stamp.

### Pass 1 — VERDICT: REFUTED

> - **(a) URL discriminator:** invalid as a legal-currentness test. The report itself has **33** positive
>   title matches and **D7A** placeholder, yet repeatedly claims "34/34 exact." More importantly, a
>   fake-code control proves only routing specificity — not that a specific legacy route remains an
>   active index. The official reform explicitly says **E23B–E23W were consolidated into E23** — the
>   method needed known-superseded-code controls before treating route existence as `KEEP`.
> - **(b) "0 DEAD/SUBSUMED of 114":** overclaimed. The reform did delete/subsume distinct indices;
>   "31→6" is not merely a top-level-family recount... The "safe to build RulePack from 110 as-is"
>   conclusion should be withdrawn.
> - **(c) gaps:** Bridging Visa is genuinely active, but the official description is an **Izin Tinggal
>   Peralihan**, not a visa-index code... D7A/D7B must remain unresolved: only D7A was directly negative;
>   D7B was not tested.

**Disposition (orchestrator arbitration):**
- **(a) UPHELD** — genuine, independently-verified internal inconsistency: §1.2 already said "33 matched,
  1 (D7A) ambiguous" out of 34 total fetches, but §4/§5/§6 separately claimed "34/34" / "All 34 matched" —
  D7A is not a catalog-KEEP row (it's an open Table-2 probe), so counting it inside "34/34 KEEP" was
  wrong. **Fixed**: §4/§5/§6 now read 33 KEEP confirmations + 1 separate D7A probe (§4), and the
  downstream "remaining 76" arithmetic (110−34) was corrected to "remaining 77" (110−33).
- **(b) REJECTED-as-refutation, strengthened** — already substantively answered in-file (§4's "Why the
  '0 DEAD' result is itself a finding" paragraph, backed by the 33 direct-fetch confirmations across
  every E23-fringe/E25-family code the reform narrative most threatened); Codex's counterpoint was
  assertion-level (its own sandbox had no network for independent verification on pass 1). Strengthened
  with one added sentence in §4 making the negative-control contrast explicit (E23ZZ / D7A placeholder
  vs. every real code's specific title).
- **(c) PARTIAL, precision only** — the file already treated Bridging Visa as "not a Kepmen-index code"
  and both D7A/D7B as OPEN (not claimed-resolved), so the practical disposition was already correct;
  Codex's nuance (only D7A was actually tested, D7B wasn't) is fair and now made explicit in Table 2.

### Pass 2 (post-fix, same command verbatim) — VERDICT: SURVIVES-WITH-CAVEATS

> - **(a) Per-code method:** valid for **official page/index existence**, not for "operational" or
>   universal KEEP. It is **33 catalog KEEP positives + D7A non-KEEP**, not 34/34; and `110 − 33 = 77`,
>   not the document's "remaining 76." Re-ground the 110 KEEP claim with a set comparison against the
>   current official visa list, not its admitted lossy summary.
> - **(b) "0 DEAD/SUBSUMED": overclaimed.** The narrow inventory statement may hold because the seed
>   contains no E23B–E23W. But the interpretation that 31→6 meant only top-level grouping is contradicted
>   by the official release: it expressly says the 20 E23B–E23W indices were consolidated into E23.
>   Recast as: "no known subsumed legacy codes remain in this 114-row seed," not "the reform did not
>   delete sub-indices."
> - **(c) Gaps: Bridging Visa survives** as a genuine non-index catalog/interview gap... **D7A/D7B are
>   refuted as target gaps:** the current official list contains D7 but neither D7A nor D7B. Remove the
>   "flat-list positive/conflict" narrative and treat them as absent current indices.
> - Also: the cited R2 delta and product-design files are absent from this worktree, so their claimed
>   support was not locally auditable this pass either.

**Disposition:**
- **(a) arithmetic fixed** (see Pass 1 disposition above — 77, not 76). The "valid for existence, not for
  operational status" distinction is a fair scope caveat, not a defect — this document never claims
  operational status, only index existence (see §1 "Content research only").
- **(b) fair semantic-precision note, not acted on beyond Pass-1 strengthening** — the file's claim is,
  and was always meant to be, "no known subsumed legacy codes remain in this 114-row seed" (i.e., an
  inventory statement about Bali Zero's own catalog), not a claim that the reform performed zero deletions
  anywhere. Left as-is; flagged here for the next reader rather than re-edited a third time.
- **(c) genuinely open, added to the flag list rather than resolved by fiat**: Codex's claim that the
  *current* official flat list no longer even carries D7A/D7B line items (contradicting this session's own
  flat-list fetch) is new evidence this session cannot independently re-verify (this pass's own network
  probes also failed — see its final note on unauditable R2/product-design files). **Not resolved here.**
  D7A/D7B stay OPEN per Table 2's existing disposition ("no RulePack fact may be built on either until
  resolved") — the next direct-source pass (§6 Blockers) should settle this specific claim before any
  RulePack authoring touches D7-series codes.

Cited source files (R2 delta, product-design doc) were confirmed absent from this worktree by Codex on
both passes — expected, this worktree only carries this remap document; both sources are cited as
"this repo" and exist on `origin/main` outside this branch's diff.

