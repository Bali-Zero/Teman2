---
date: 2026-08-20
domain: visa
client_case: none — engine doctrine work (weekly re-attestation lane, RulePack seq-12 source re-stamp)
sources:
  - https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-calling-visa
  - https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-subjek-visa-on-arrival
  - https://www.imigrasi.go.id/siaran_pers/2024/04/23/izin-tinggal-peralihan-jembatani-proses-transisi-izin-tinggal-wna-di-ri
  - https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian/izin-tinggal-kunjungan-menjadi-izin-tinggal-terbatas
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31A
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31B
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31C
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31D
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31E
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31F
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31G
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31H
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31J
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D1
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D2
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D12
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E30A
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E30B
discovered_by: agent.air-m5.backend-rag.visa-seq12-restamp (3 reader agents + orchestrator)
adversarial_review: kimi-k3
---

# Live source re-verification for the seq-12 `verified_at` re-stamp (2026-08-20)

**Method** — same as QW-5 (`sources/freshness-recheck-2026-08-16.md`), the seq-9 inc3 recheck
(`inc3-pack-edits/freshness-2026-08-19.md`), and the seq-10 inc4 recheck
(`inc4-pack-edits/freshness-restamp-2026-08-19.md`): for each `OFFICIAL_PORTAL` source record in
`rulepack-prod-011.source.json`, the rules/products citing it were resolved via `source_refs` to
determine the exact fact the record is cited FOR, then the live page was fetched (`WebFetch`) and
its current content compared against that claimed fact. HTTP reachability alone was never treated
as proof. Fetches executed 2026-08-20 ~06:14–06:16 UTC by three parallel readers (1 =
lists/procedural, 2 = E31 family, 3 = D-series/E30), plus an independent orchestrator spot-check on
two records.

**Trigger** — this is a scheduled **weekly re-attestation** cycle, run on Zero's 2026-08-20 GO for
the weekly re-attestation cadence, NOT a reaction to a `DECISIVE_SOURCE_STALE` trip. All 18 records
carry a 7-day `MAX_AGE_SINCE_VERIFIED_AT`; the seq-9/seq-10 stamps put their due dates at
2026-08-25 (`ecd22722` E31E, stamped in the seq-9 fold at `2026-08-18T21:41:23Z` — note the
carried `verified_by` label ends `qw5-recheck-2026-08-19`: the label names the seq-9 fold cycle's
recheck date while the fetch itself ran 21:41Z the evening before; a pre-existing seq-9 label/stamp
skew, disclosed here, not introduced or repeated by this batch) and 2026-08-26 (the other 17: 16
stamped in the seq-10 fold between `04:20:00Z` and `04:22:00Z`, plus `2d090f3a` E31J at
`04:31:03Z` by the seq-10 orchestrator) — i.e. every record here was
re-verified 5-6 days **before** it would otherwise trip `HUMAN_REVIEW`. This is a **PRE-EXPIRY
re-stamp by design**: zero abstain gap — the engine never sees a stale-source path on any
rule/product these 18 records back.

## Verdict tally

| Verdict | Count | Records |
|---|---|---|
| CURRENT | 17 | bc309fa9, 38a6cb08, 3da72c7b, dcf08e19, 950a9f63, 570f2bc4, 40523028, 50457cd0, ecd22722, f9306203, 86880290, 153beca1, 2d090f3a, ca5a2ce8, d3ad622e, 5e64ec6b, cb1b7182 |
| CURRENT WITH EXCEPTION | 1 | 38242587 (E30A — see §17) |
| CHANGED | 0 | — |
| UNREACHABLE | 0 | — |

Every verdict below re-stamps `verified_at` to the record's actual fetch time and `verified_by` to
`agent.air-m5.backend-rag.visa-seq12-reader-<n>.qw5-recheck-2026-08-20` (reader-1 for the
lists/procedural batch, reader-2 for the E31 family + E31E, reader-3 for the D-series/E30 batch).
`content_sha256` is untouched everywhere: no page changed vs the prior seq-9/seq-10 description,
and the field tracks the page's content identity, not the stamp
(`test_seq7_sponsor_witnesses.py:220` precedent).

## Per-record findings

### 1. `bc309fa9` — Calling Visa country list — CURRENT — 2026-08-20T06:14Z
Facts cited for: the closed 6-entry Calling Visa list; Cameroon/Guinea must be ABSENT (seq-3
retroactive-cure premise). Live page: exactly 6 entries — Afganistan, Israel, Korea Utara, Liberia,
Nigeria, Somalia. No Kamerun, no Guinea. 1:1 match, identical to the seq-10 finding.

### 2. `38a6cb08` — VOA country list — CURRENT — 2026-08-20T06:14Z
Facts cited for: the ~97-country VOA-eligible list, Italy present. Live page: 97 entries, Italia
present (#32), Nigeria absent (consistent — Nigeria is calling-visa-only, per §1). Same count and
membership as seq-10.

### 3. `3da72c7b` — Izin Tinggal Peralihan press release — CURRENT — 2026-08-20T06:14Z
Facts cited for: bridging concept, 60-day validity, 3-day pre-expiry filing window. All three
confirmed verbatim: *"Izin tinggal tersebut menjadi 'jembatan' antara izin tinggal sebelumnya untuk
memperoleh izin tinggal baru"*; *"Masa berlaku Izin Tinggal Peralihan yakni 60 hari"*; *"...paling
lambat 3 (tiga) hari sebelum masa berlaku izin tinggal sebelumnya habis."* Word-for-word match to
seq-10.

### 4. `dcf08e19` — ITK→ITAS conversion service page — CURRENT — 2026-08-20T06:14Z
Facts cited for: 30-day pre-expiry filing window, 4-step conversion procedure. Confirmed:
*"Permohonan alih status ITK menjadi ITAS diajukan dalam waktu paling lama 30 hari sebelum jangka
waktu Izin Tinggal Kunjungan berakhir"* + the same 4-step Tata Cara Permohonan. Same
narrow-scope-corroborator caveat as seq-10 (silent on excluded ITK status codes, carried elsewhere,
no contradiction).

### 5. `950a9f63` — E31A — CURRENT — 2026-08-20T06:15Z
Facts cited for: spouse-of-WNI sponsor/classification fact, USD 2,000 living-costs fact. Confirmed:
*"E31A Visa Keluarga Suami/Istri WNI"* + *"bukti memiliki biaya hidup ... dengan jumlah minimal USD
$2000."* Identical wording to seq-10.

### 6. `570f2bc4` — E31B — CURRENT — 2026-08-20T06:15Z
Facts cited for: sponsor holds ITAS/ITAP. Confirmed by title *"E31B Visa Keluarga Suami/Istri
Pemegang ITAS/ITAP"* — carried by the classification, not a separate Persyaratan bullet, same
interpretive posture as seq-10.

### 7. `40523028` — E31C — CURRENT — 2026-08-20T06:15Z
Facts cited for: official proof of the parents' legally registered marriage (two routes),
birth-certificate proof. Confirmed on the live page. **Orchestrator spot-check (2026-08-20
~06:30Z, W65 independent re-fetch)**: the full two-route marriage-proof clause is verbatim on the
live page — *"Bukti pelaporan atau pencatatan pada Perwakilan Republik Indonesia atau instansi yang
berwenang di bidang pencatatan sipil dan akta perkawinan yang telah diterjemahkan dalam bahasa
Indonesia oleh penerjemah tersumpah; atau Buku nikah atau akta perkawinan yang dikeluarkan oleh
kementerian atau lembaga berwenang (jika perkawinan dilakukan di wilayah Indonesia)."* This confirms
reader 2's own read that its shorter extraction was a WebFetch artifact of that specific call, not
page drift — see Method gotchas below.

### 8. `50457cd0` — E31D — CURRENT — 2026-08-20T06:15Z
Facts cited for: step-child scope, sponsor requirement. Confirmed by title *"E31D Visa Keluarga Anak
Bawaan WNA Perkawinan Sah WNA-WNI"* + document set (birth certificate, parents' marriage proof, WNI
parent's Kartu Keluarga) — same implicit-but-unambiguous status as seq-10.

### 9. `ecd22722` — E31E — CURRENT — 2026-08-20T06:15Z
Facts cited for: parent holds a valid ITAS/ITAP/Visa Tinggal Terbatas (`REQ_SPONSOR_ITAS_ITAP` only
— the two `hf.e31e-*` HARD_FILTER rules were replaced off this record in the seq-9 fold and are out
of scope). Confirmed: *"Izin Tinggal Terbatas/Izin Tinggal Tetap atau Visa Tinggal Terbatas milik
orang tua yang masih berlaku."* No age/marital-status language found anywhere on the page,
consistent with the seq-9 replacement rationale — no regression back toward support for the rules
that no longer cite this record. **This record's prior write-up lives in
`inc3-pack-edits/freshness-2026-08-19.md` (seq-9 fold), not inc4** — it was re-stamped a day before
the E31A/B/C/D/F/G/H/J batch and was explicitly excluded from the inc4 doc by that doc's own line
46-47.

### 10. `f9306203` — E31F — CURRENT — 2026-08-20T06:15Z
Facts cited for: Indonesian court-decision proof of the legal relationship between the foreign child
and the Indonesian-citizen parent. Confirmed verbatim: *"Putusan pengadilan Indonesia yang
menjelaskan status hubungan hukum antara Warga Negara Asing dengan orangtua warga negara
Indonesia."*

### 11. `86880290` — E31G — CURRENT — 2026-08-20T06:15Z
Facts cited for: sponsor requirement + evisa account requirement, 6-month passport validity, USD
2,000/3-month bank-statement clause. All four cited facts confirmed verbatim (reader 2's live
quotes):
- Title/classification: *"E31G Visa Keluarga Orang Tua dari Anak WNI"*
- Sponsor: *"Anda membutuhkan penjamin/sponsor untuk mengajukan visa ini."*
- Sponsor evisa account: *"Penjamin (sponsor) harus memiliki akun di evisa.imigrasi.go.id sebelum
  mengajukan visa."*
- Passport validity: *"Paspor kebangsaan yang sah dan masih berlaku paling singkat 6 bulan sebelum
  masa berlakunya habis"*
- Funds clause: *"bukti memiliki biaya hidup selama berada di wilayah Indonesia berupa rekening
  koran 3 bulan terakhir..."* — exact match to seq-10.

### 12. `153beca1` — E31H — CURRENT — 2026-08-20T06:15Z
Facts cited for: child holds a valid ITAS/ITAP/Visa Tinggal Terbatas. Confirmed byte-for-byte:
*"Izin Tinggal Terbatas/Izin Tinggal Tetap atau Visa Tinggal Terbatas yang masih berlaku milik
anak."*

### 13. `2d090f3a` — E31J — CURRENT — 2026-08-20T06:15Z
Facts cited for: sibling holds a valid ITAS/ITAP, sponsor requirement, dependency-age (not expected
on this page, co-sourced with the Kepmen record `e3572ad2`). Confirmed verbatim (reader 2's live
quotes):
- Title/classification: *"E31J Visa Keluarga Anak yang Bergabung dengan Saudara Kandung Pemegang
  ITAS/ITAP"*
- Sponsor: *"Anda membutuhkan penjamin/sponsor untuk mengajukan visa ini."*
- Sibling holds ITAS/ITAP: *"Visa tinggal terbatas, Izin Tinggal Terbatas/Izin Tinggal Tetap atau
  Visa Tinggal Terbatas yang masih berlaku milik saudara kandung."* (plus *"Bukti jaminan dari
  Penjamin atau pernyataan komitmen saudara kandung."*)
- No dependency-age language on the page found — exactly matches seq-10 (that fact rides on the
  Kepmen co-source, as expected).

### 14. `ca5a2ce8` — D1 — CURRENT — 2026-08-20T06:15Z
Facts cited for: multi-entry support, passport validity, USD 2,000 funds, CV, itinerary, support
letter. All 6 cited facts reconfirmed verbatim against the live page (reader 3's quotes):
- Multi-entry / 60-day stay: *"Visa Kunjungan untuk beberapa kali masuk ke Indonesia dengan izin
  tinggal maksimal 60 hari"*
- Passport validity: *"dokumen perjalanan yang sah dan masih berlaku paling singkat 6 bulan sebelum
  masa berlakunya habis"*
- Funds (USD 2000): *"bukti memiliki biaya hidup selama berada di wilayah Indonesia berupa rekening
  koran 3 bulan terakhir atas nama Orang Asing atau penjamin sebesar minimal USD2000"*
- CV: *"curriculum vitae"* · Itinerary: *"rencana perjalanan (travel itinerary)"*
- Support letter: *"surat keterangan, undangan, atau korespondensi dari instansi pemerintah atau
  lembaga swasta"* OR *"surat keterangan dari suami/istri atau orang tua (WNI)"*
No drift.

### 15. `d3ad622e` — D2 — CURRENT — 2026-08-20T06:15Z
All 6 cited facts reconfirmed verbatim (reader 3's quotes — the wording overlaps D1's but each was
fetched and quoted from the D2 page itself, not inherited):
- Multi-entry: *"Visa Kunjungan untuk beberapa kali masuk ke Indonesia dengan izin tinggal maksimal
  60 hari setiap kedatangan"*
- Passport validity: *"dokumen perjalanan yang sah dan masih berlaku paling singkat 6 bulan sebelum
  masa berlakunya habis"*
- Funds: *"...sebesar minimal USD2000"* · CV: *"curriculum vitae"* · Itinerary: *"rencana
  perjalanan (travel itinerary)"*
- Support letter: *"surat keterangan, undangan, atau korespondensi dari instansi pemerintah atau
  lembaga swasta"*
- Business purpose (matches pack citation verbatim): *"berbisnis, mengikuti rapat, serta melakukan
  pembelian barang. Anda juga dapat melakukan pembicaraan, pembahasan, negosiasi, dan/atau
  menandatangani perjanjian bisnis"*
No drift.

### 16. `5e64ec6b` — D12 — CURRENT — 2026-08-20T06:15Z
Facts cited for: the shared D-series 6 facts (USD 5,000 variant) plus the non-convertibility
hard-filter `hf.d12-onshore-conversion-excluded`. Non-convertibility clause reconfirmed verbatim on
a targeted second fetch: *"...bisa diperpanjang untuk 180 hari berikutnya namun tidak bisa
dialihkan menjadi izin tinggal terbatas."* See Method gotchas below.

### 17. `38242587` — E30A — CURRENT WITH EXCEPTION — 2026-08-20T06:15Z
Facts cited for: 6-month passport validity, USD 2,000 living-costs. Both confirmed verbatim
(reader 3's live quotes):
- Passport validity: *"Paspor kebangsaan yang sah dan masih berlaku paling singkat 6 bulan sebelum
  masa berlakunya habis"*
- Funds (USD 2000): *"bukti memiliki biaya hidup selama berada di wilayah Indonesia berupa rekening
  koran 3 bulan terakhir atas nama Orang Asing atau penjamin dengan jumlah minimal USD $2000 (dua
  ribu Dolar Amerika Serikat) atau jumlah yang setara"*
Stay-policy cross-check: pack 365-730 days ↔ live *"Stay Duration: 1 or 2 years (selectable),
calculated from arrival date."* Match.
**Exception (unchanged, ledgered)**: `review.minor-without-guardian` is a GLOBAL rule whose sole
`source_ref` is this record; reader 3 searched the full live page text for "anak"/"wali"/"minor"/
"guardian" — zero occurrences of any of the four terms anywhere on the page. The exception still
stands as ledgered — not cured, not regressed, unchanged from the seq-10 finding.

### 18. `cb1b7182` — E30B — CURRENT — 2026-08-20T06:15Z
Facts cited for: passport validity, USD 2,000 living-costs, acceptance-letter and sponsor-proof
clauses backing `el.e30b-izin-belajar`. All confirmed verbatim (reader 3's live quotes):
- Passport validity: *"Paspor kebangsaan yang sah dan masih berlaku paling singkat 6 bulan sebelum
  masa berlakunya habis"* (identical to E30A)
- Funds: *"...dengan jumlah minimal USD $2000 (dua ribu Dolar Amerika Serikat) atau jumlah yang
  setara"* (identical wording to E30A, quoted from the E30B page itself)
- Acceptance letter (matches pack citation verbatim): *"Surat penerimaan dari institusi pendidikan
  yang mencantumkan lama masa pendidikan yang akan ditempuh orang asing."*
- Sponsor proof (matches pack citation verbatim): *"bukti penjaminan dari Penjamin yang merupakan
  perorangan atau institusi pendidikan di mana WNA menempuh pendidikan"*
Stay-policy cross-check: pack 365-1460 days ↔ live *"Stay Duration Options: 1 tahun, 2 tahun, atau
4 tahun."* Match.
Known terminology gap (reader 3 searched the live page for "Izin Belajar" and
"Kemdikbud"/"Kemendikbud" — zero occurrences of either) persists unchanged — recorded, not a
regression.

## Method gotchas

- **E31C extraction artifact (reader 2)**: the first WebFetch pass on record 7 (`40523028`)
  returned a truncated paraphrase of the two-route marriage-proof clause, missing the "...oleh
  penerjemah tersumpah; atau Buku nikah..." tail. Reader 2 flagged this itself as a likely
  summarizer artifact rather than page drift (the opening clause was byte-identical, nothing on the
  page contradicted the second route). **Confirmed by the orchestrator's independent W65
  spot-check** (§7 above): the full clause is verbatim on the live page. Lesson held: a single
  WebFetch pass can silently truncate/paraphrase a load-bearing verbatim quote even when the page
  itself has not changed.
- **D12 targeted re-fetch (reader 3)**: the first WebFetch pass on record 16 (`5e64ec6b`) conflated
  the non-convertibility clause (180-day extension, no conversion to ITAS) with a *different*,
  unrelated sentence elsewhere on the page (the general 1-2 year overall-duration blurb). Both
  sentences are genuinely present and not in conflict, but the summarizer silently merged/paraphrased
  them on first read. A second, narrowly-scoped fetch isolated the exact non-convertibility string.
  Lesson: do not trust a single WebFetch pass for a load-bearing verbatim quote when the
  summarizer's phrasing does not exactly match what is being checked against — re-fetch narrow.

## E30A/E30B PNBP price grounding

Re-confirmed live on both pages (not currently cited by a pack rule — informational only, grounds
the composed prices published on the E30A/E30B product pages):

| Product | 1 tahun | 2 tahun | 4 tahun |
|---|---|---|---|
| E30A | Rp 6.000.000 | Rp 8.500.000 | — |
| E30B | Rp 6.000.000 | Rp 8.500.000 | Rp 12.000.000 |

Pack `pricing_key.item_key` is `"E30A Education Visa (1 Year)"` / `"E30B Higher Education (1 Year)"`
only — the multi-year figures live on the page with no matching pack pricing_key at present;
flagged for whoever owns the pricing-key completeness question, not fixed here (out of scope — this
task is freshness re-verification, not pricing edits).

## Adversarial review

**Orchestrator independent spot-check (W65, 2026-08-20 ~06:30Z)** — two records re-fetched
independently by the orchestrator, outside the three reader agents' own fetches, to test for
phantom/fabricated quotes before folding the re-stamp:

1. `bc309fa9` (Calling Visa list) re-fetched independently: exactly 6 countries (Afganistan,
   Israel, Korea Utara, Liberia, Nigeria, Somalia), Kamerun and Guinea ABSENT — matches reader 1
   verbatim.
2. `40523028` (E31C) re-fetched independently: the full two-route marriage-proof clause is on the
   live page verbatim (quoted in §7 / Method gotchas above) — reader 2's truncation is confirmed to
   be a WebFetch extraction artifact of that specific call, not page drift.

Both spot-checks corroborate the reader findings; no fabricated quote, no verdict broader than its
evidence, no timestamp inconsistency found in either record. No CHANGED verdict was produced by
this batch — all 17 CURRENT verdicts and the 1 CURRENT WITH EXCEPTION stand as reported.

**Cross-family refuter: Kimi K3 (Moonshot), 2026-08-20 — generator≠grader with parentage
declared (W100):** the three readers, the assembler, and the orchestrator are all Claude-family;
the refuter seat is cross-family by construction. Codex GPT-5.6-sol was dispatched first and came
back quota-dead (usage limit until 2026-08-22) — the cascade fell to Kimi K3, which executed the
full review (both files cross-checked programmatically against the pack bytes).

Kimi's initial verdict was **FAIL — evidentiary, not computational**. It confirmed the machine
layer byte-perfect (all 18 restamps match the pack's current stamps exactly, advance correctly,
reader attribution consistent 1:1, canonical URLs = frontmatter sources, freshness policies
604800s across the board) and refuted the CAPTURE on six counts, every one accepted and repaired
in this same document before commit:

1. §11 E31G, §13 E31J, §14 D1, §17 E30A, §18 E30B claimed "confirmed verbatim" with zero quotes,
   and §15 D2 quoted 1 of 6 facts while inheriting the rest from the unquoted D1 section —
   contradicting the edit file's own "verbatim quotes per record" promise. **Repaired**: the
   readers' live quotes (which existed in their raw outputs all along — the assembly step had
   summarized them away) are now imported verbatim into all six sections; D2's quotes are its own
   page's, not inherited.
2. The "`2026-08-19T04:2x:xxZ`" shorthand for the 17 seq-10 stamps was false for `2d090f3a` E31J
   (`04:31:03Z`). **Repaired**: the Trigger paragraph now states the real range (16 records
   04:20-04:22, E31J 04:31:03Z).
3. `ecd22722`'s carried seq-9 stamp (`2026-08-18T21:41:23Z`) disagrees with its `verified_by`
   label date (`...2026-08-19`) — a pre-existing seq-9 label/stamp skew, not introduced here.
   **Disclosed** in the Trigger paragraph rather than silently repeated.

Kimi found lanes (b) id/stamp, (c) reader attribution, and (f) quote-supports-fact explicitly
CLEAN (every quote that was present does support its cited fact; the §6 E31B classification-carried
posture is disclosed, consistent with seq-10, and was noted, not refuted). With the six evidentiary
repairs applied, no REFUTED finding remains unaddressed; the FAIL bit exactly what it should have
and the capture now meets its own stated bar.
