---
date: 2026-08-19
domain: visa
client_case: none — engine doctrine work (E5 increment 4, RulePack seq-10 source re-stamp)
sources:
  - https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-calling-visa
  - https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-subjek-visa-on-arrival
  - https://www.imigrasi.go.id/siaran_pers/2024/04/23/izin-tinggal-peralihan-jembatani-proses-transisi-izin-tinggal-wna-di-ri
  - https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian/izin-tinggal-kunjungan-menjadi-izin-tinggal-terbatas
  - https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31A
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31B
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31C
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31D
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31F
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31G
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31H
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31J
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D1
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D2
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D12
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E30A
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E30B
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C2
discovered_by: agent.air-m5.backend-rag.visa-e5-seq10 (3 reader agents + orchestrator)
adversarial_review: codex
---

# Live source re-verification for the seq-10 `verified_at` re-stamp (2026-08-19)

**Method** — same as QW-5 (`sources/freshness-recheck-2026-08-16.md`) and the seq-9
inc3 recheck (`inc3-pack-edits/freshness-2026-08-19.md`): for each stale
`OFFICIAL_PORTAL` source record in `rulepack-prod-009.source.json`, the rules/products
citing it were resolved via `source_refs` to determine the exact fact the record is
cited FOR, then the live page was fetched (`WebFetch`) and its current content compared
against that claimed fact. HTTP reachability alone was never treated as proof. Fetches
executed 2026-08-19 04:20–04:31 UTC by three parallel readers (1 = lists/procedural,
2 = E31 family, 3 = D-series/E30 + C2 grounding probe) plus the orchestrator (E31J —
initially missed by the batch split; counted and recovered per the W107 "N of M"
discipline).

**Trigger** — 18/29 seq-9 source records were past their 7-day
`MAX_AGE_SINCE_VERIFIED_AT` window (17 stamped `2026-08-06T06:19:49Z`, due 08-13;
1 stamped `2026-08-08T00:00:00Z`, due 08-15). The engine correctly raises
`DECISIVE_SOURCE_STALE` → HUMAN_REVIEW on every path they decide, which is what this
re-stamp cures. (`ecd22722` E31E was already re-stamped in the seq-9 fold and is not
touched here.)

## Verdict tally

| Verdict | Count | Records |
|---|---|---|
| CURRENT | 16 | bc309fa9, 38a6cb08, 3da72c7b, dcf08e19, 950a9f63, 570f2bc4, 40523028, 50457cd0, f9306203, 86880290, 153beca1, 2d090f3a, ca5a2ce8, d3ad622e, 5e64ec6b, cb1b7182 |
| CURRENT WITH EXCEPTION | 1 | 38242587 (E30A — see §18) |
| CHANGED (re-confirmed) | 1 | ee8fe5b8 (see §5 — dropped in seq-10, not re-stamped) |
| UNREACHABLE | 0 | — |

Every CURRENT/CURRENT-WITH-EXCEPTION verdict below re-stamps `verified_at` to the
record's actual fetch time and `verified_by` to
`agent.air-m5.backend-rag.visa-e5-seq10-reader-<n>.qw5-recheck-2026-08-19` (orchestrator
for E31J). `content_sha256` is untouched everywhere: no page changed vs what QW-5
described, and the field tracks the page's content identity, not the stamp
(`test_seq7_sponsor_witnesses.py:220` precedent).

## Per-record findings

### 1. `bc309fa9` — Calling Visa country list — CURRENT — 2026-08-19T04:20:35Z
Live page lists exactly 6 entries under "Daftar Negara, Pemerintah Dari Daerah
Administrasi Khusus Suatu Negara, dan Entitas Tertentu": Afganistan, Israel, Korea
Utara, Liberia, Nigeria, Somalia. 1:1 match with the cited set; no Cameroon, no Guinea
(the seq-3 retroactive fix's premise holds). Identical to QW-5's finding.

### 2. `38a6cb08` — VOA country list — CURRENT — 2026-08-19T04:20:35Z
97 entries (exact match to the cited "~97"). Spot-checks: Italia present (#32),
Nigeria absent, Afrika Selatan (#1), Amerika Serikat (#3), Jerman (#35), Tiongkok
(#87), Jepang (#34). Same count and membership as QW-5.

### 3. `3da72c7b` — izin tinggal peralihan press release — CURRENT — 2026-08-19T04:20:35Z
All three cited facts verbatim: *"Izin tinggal tersebut menjadi 'jembatan' antara izin
tinggal sebelumnya untuk memperoleh izin tinggal baru"* (bridging concept); *"Masa
berlaku Izin Tinggal Peralihan yakni 60 hari"* (60-day validity); *"...paling lambat 3
(tiga) hari sebelum masa berlaku izin tinggal sebelumnya habis"* (3-day pre-expiry
window).

### 4. `dcf08e19` — ITK→ITAS conversion service page — CURRENT — 2026-08-19T04:20:35Z
*"Permohonan alih status ITK menjadi ITAS diajukan dalam waktu paling lama 30 hari
sebelum jangka waktu Izin Tinggal Kunjungan berakhir"* (30-day window) + the 4-step
procedure. Same narrow-scope-corroborator caveat as QW-5 #3 (silent on excluded ITK
status codes — carried elsewhere, no contradiction).

### 5. `ee8fe5b8` — izin-tinggal-keimigrasian landing — CHANGED (re-confirmed) — 2026-08-19T04:20:35Z
The "Persyaratan Dokumen" section still lists only 3 generic items: *"paspor atau
dokumen perjalanan yang masih berlaku"* (no 6-month figure), *"surat bukti penjaminan
dari Penjamin yang sama saat mengajukan visa"*, *"surat pernyataan yang menerangkan
maksud dan tujuan berada di Indonesia"*. None of the D1/D2/D12 facts it is co-cited for
(USD 2000/5000 funds, CV, itinerary, 6-month passport) appear. Two independent semantic
rechecks (2026-08-16 QW-5 #4, this one) now agree. **Seq-10 action**: remove its 3
remaining PRODUCT-level co-refs (D1/D2/D12 — left "out of Assembly decision #5's scope"
in seq-9) and drop the record (0497cb52 zero-refs precedent). Coverage is not thinned:
each product keeps its own dedicated page record (ca5a2ce8 / d3ad622e / 5e64ec6b), all
re-verified CURRENT below — QW-5 #15 already recommended exactly this anchoring.

### 6. `950a9f63` — E31A — CURRENT — 2026-08-19T04:20:00Z
*"bukti memiliki biaya hidup selama berada di wilayah Indonesia berupa rekening koran 3
bulan terakhir atas nama Orang Asing atau penjamin dengan jumlah minimal USD $2000"* —
exact match for the USD 2,000 living-costs fact.

### 7. `570f2bc4` — E31B — CURRENT — 2026-08-19T04:21:00Z
Title/classification: *"E31B Visa Keluarga Suami/Istri Pemegang ITAS/ITAP"*. The
sponsor-holds-ITAS/ITAP fact is carried by the classification (unambiguous), not by a
separate Persyaratan bullet — same interpretive caveat QW-5 recorded; unchanged.

### 8. `40523028` — E31C — CURRENT — 2026-08-19T04:22:00Z
The cited fact, verbatim on the live page: *"Bukti perkawinan orang tua berupa: Bukti
pelaporan atau pencatatan pada Perwakilan Republik Indonesia atau instansi yang
berwenang di bidang pencatatan sipil dan akta perkawinan yang telah diterjemahkan dalam
bahasa Indonesia oleh penerjemah tersumpah\*; atau Buku nikah atau akta perkawinan yang
dikeluarkan oleh kementerian atau lembaga berwenang (jika perkawinan dilakukan di
wilayah Indonesia)."* — official proof of the parents' legally registered marriage,
two routes (foreign registration + sworn translation, or Indonesian marriage book).
Direct match.

**Full Persyaratan transcription** (load-bearing: grounds claims CL-E31C-02/03 in
`claims/inc4-c2-e31c-claim-ledger.md`, verified against raw page HTML by reader 2):

Penjamin section: *"Anda membutuhkan penjamin/sponsor untuk mengajukan visa ini."* —
*"Penjamin (sponsor) harus memiliki akun di evisa.imigrasi.go.id sebelum mengajukan
visa bagi Orang Asing yang dia sponsori."*

General checklist:
1. *"Surat permohonan visa dari ayah/ibu Warga Negara Indonesia"* — application letter
   from the Indonesian-citizen father/mother.
2. *"Paspor kebangsaan yang sah dan masih berlaku paling singkat 6 bulan sebelum masa
   berlakunya habis, (untuk pemegang dokumen perjalanan selain paspor kebangsaan
   seperti paspor darurat, dokumen identitas, dll harus berlaku selama 12 bulan)"*
3. *"bukti memiliki biaya hidup selama berada di wilayah Indonesia berupa rekening
   koran 3 bulan terakhir atas nama Orang Asing atau penjamin dengan jumlah minimal USD
   $2000 (dua ribu Dolar Amerika Serikat) atau jumlah yang setara"*
4. *"pasfoto berwarna terbaru (setahun terakhir)."*
5. *"Daftar riwayat hidup"* — CV.
6. *"Riwayat perjalanan (itinerary)"*

Persyaratan khusus:
7. *"Bukti kelahiran berupa Akta kelahiran yang dikeluarkan oleh kementerian atau
   lembaga berwenang; atau Bukti pelaporan kelahiran pada Perwakilan Republik Indonesia
   atau instansi yang berwenang di bidang pencatatan sipil (jika Orang Asing lahir di
   luar wilayah Indonesia)."*
8. the marriage-proof clause quoted above (trailing asterisk's footnote text not present
   in the extracted body — likely a tooltip; flagged, not invented).
9. *"Kartu Keluarga (KK) ayah/ibu Warga Negara Indonesia."*

### 9. `50457cd0` — E31D — CURRENT — 2026-08-19T04:20:00Z
Title *"E31D Visa Keluarga Anak Bawaan WNA Perkawinan Sah WNA-WNI"* + *"Anda
membutuhkan penjamin/sponsor untuk mengajukan visa ini."* Step-child scope carried by
the classification and document set (birth certificate, parents' marriage proof, WNI
parent's Kartu Keluarga) — same implicit-but-unambiguous status QW-5 recorded.

### 10. `f9306203` — E31F — CURRENT — 2026-08-19T04:20:00Z
*"Putusan pengadilan Indonesia yang menjelaskan status hubungan hukum antara Warga
Negara Asing dengan orangtua warga negara Indonesia"* — exact match for the
court-decision fact.

### 11. `86880290` — E31G — CURRENT — 2026-08-19T04:20:00Z
Sponsor requirement + evisa account, *"Paspor sah berlaku paling singkat 6 bulan
sebelum masa berlakunya habis"*, *"rekening koran 3 bulan terakhir"* min *"USD $2000
... atau jumlah yang setara"* — all four cited facts verbatim.

### 12. `153beca1` — E31H — CURRENT — 2026-08-19T04:21:00Z
Persyaratan khusus, explicit bullet: *"Izin Tinggal Terbatas/Izin Tinggal Tetap atau
Visa Tinggal Terbatas yang masih berlaku milik anak."* + title *"E31H Visa Keluarga
Orang Tua dari Anak Pemegang ITAS/ITAP"* — exact match.

### 13. `2d090f3a` — E31J — CURRENT — 2026-08-19T04:31:03Z (orchestrator)
Title *"E31J Visa Keluarga Anak yang Bergabung dengan Saudara Kandung Pemegang
ITAS/ITAP"*; *"Anda membutuhkan penjamin/sponsor untuk mengajukan visa ini."*;
Persyaratan khusus: *"Visa tinggal terbatas, Izin Tinggal Terbatas/Izin Tinggal Tetap
atau Visa Tinggal Terbatas yang masih berlaku milik saudara kandung."* — both cited
facts (sibling sponsor + valid ITAS/ITAP) verbatim. No dependency-age language on the
page — same as QW-5 #14, whose verdict already noted the age rule is co-sourced with
`e3572ad2` (Kepmen) and does not rest on this page alone. No contradiction.

### 14. `ca5a2ce8` — D1 — CURRENT — 2026-08-19T04:21:51Z
All 6 cited facts verbatim: 6-month passport (*"dokumen perjalanan yang sah dan masih
berlaku paling singkat 6 bulan"*), USD 2000/3-month statement (*"...sebesar minimal
USD2000 atau dalam mata uang lain yang setara jumlahnya"*), *"curriculum vitae"*,
*"rencana perjalanan (travel itinerary)"*, support letter (institutional or WNI
spouse/parent), multi-entry tourism purpose.

### 15. `d3ad622e` — D2 — CURRENT — 2026-08-19T04:21:51Z
Same 6-fact structure as D1; business purpose verbatim (*"berbisnis, mengikuti rapat,
serta melakukan pembelian barang ... menandatangani perjanjian bisnis"*); multi-entry
confirmed.

### 16. `5e64ec6b` — D12 — CURRENT — 2026-08-19T04:21:51Z
USD 5000 (*"sebesar minimal USD5000"*), passport/CV/itinerary/support-letter clauses,
purpose (*"prainvestasi atau memulai usaha antara lain survei lapangan dan/atau studi
kelayakan"*), and non-convertibility verbatim (*"bisa diperpanjang untuk 180 hari
berikutnya namun tidak bisa dialihkan menjadi izin tinggal terbatas"*).

### 17. `cb1b7182` — E30B — CURRENT — 2026-08-19T04:21:51Z
Passport/USD-2000 clauses (same wording as E30A) + *"Surat penerimaan dari institusi
pendidikan yang mencantumkan lama masa pendidikan"* (acceptance letter) + *"bukti
penjaminan dari Penjamin yang merupakan perorangan atau institusi pendidikan"*. The
known terminology gap (no "Izin Belajar"/Kemdikbud wording) persists unchanged —
recorded, not a regression.

### 18. `38242587` — E30A — CURRENT WITH EXCEPTION — 2026-08-19T04:21:51Z
Cited facts confirmed verbatim: *"Paspor kebangsaan yang sah dan masih berlaku paling
singkat 6 bulan"* + *"...dengan jumlah minimal USD $2000 ... atau jumlah yang setara"*.
**Exception (unchanged from QW-5 #18)**: the full page text contains zero occurrences
of anak/wali/minor/guardian — the record remains the SOLE cited source for
`review.minor-without-guardian`, which it does not support. The re-stamp is honest for
the two facts above; the minor-without-guardian sourcing defect is a declared residual
(PENDING-ARMS row, E31E re-sourcing pattern is the known cure shape), NOT cured in
seq-10.

## C2 grounding probe (not a pack record — feeds the §3a cure decision in the spec)

Live https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C2 (2026-08-19T04:21:51Z),
Penjamin section quoted exactly: *"Anda tidak membutuhkan penjamin/sponsor untuk
mengajukan visa ini. Kecuali anda: Berstatus tanpa kewarganegaraan (stateless); atau
Pemegang dokumen perjalanan bukan paspor kebangsaan; atau Warga negara dari negara
tertentu yang ada di dalam daftar ini."* — no sponsor by default; the exceptions are
applicant-status-driven, never sponsor-entity-driven. The page names no corporate/
company-sponsor requirement anywhere; its one relationship-letter item may come from
*"instansi pemerintah atau lembaga swasta"* (government agency OR private institution).
No USD figure on this page. This **refutes** the candidate doctrinal claim "C2's
sponsor is corporate" (`sponsor.type == EMPLOYER`) and is recorded as conflict CF-17 in
`claims/inc4-c2-e31c-claim-ledger.md`, together with `CL-C2-03` (mandatory-penjamin
reading of Permenkumham 11/2024) and the product metadata (`sponsor_types:
["EMPLOYER"]`, not evaluator-consumed).

## Adversarial review

Seats: **Codex (GPT-5.6-sol xhigh)** + **Kimi K3** (both cross-family) — dispatched on
this document plus `source-restamp-edits.json` and the cure files before the fold was
finalized; ordered to refute the re-stamp evidence (fabricated quotes, verdicts broader
than their evidence, timestamps that don't line up, the E31J recovery, the ee8fe5b8
drop reasoning, the E30A exception handling). Verbatim-quote spot-checks against the
live pages were re-run by the reviewers, not trusted from this file. Outcomes touching
THIS document: 16 CURRENT verdicts **not refuted** by either seat; the E30A re-stamp
was challenged by both (Codex BLOCKER 2 / Kimi finding 4) and dispositioned
ACCEPTED-PARTIAL — the stamp attests the record honestly, the pre-existing
`review.minor-without-guardian` citation defect is escalated to its own PENDING-ARMS
row (grounded re-sourcing, E31E pattern) instead of being silently blessed or
un-groundedly patched; Kimi's wording nit on §5 is applied below (the two rechecks are
NAMED — 2026-08-16 QW-5 #4, verbatim-quoted, and 2026-08-19 reader-1's re-fetch —
rather than characterized). Full findings + dispositions for the whole inc4 edit set:
`cure-c2-e31c.md` §Adversarial review.
