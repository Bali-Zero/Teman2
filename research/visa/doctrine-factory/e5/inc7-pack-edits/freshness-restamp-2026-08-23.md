---
date: 2026-08-23
domain: visa
client_case: none — engine doctrine work (E5 increment 7, RulePack seq-13 freshness-half source re-stamp)
sources:
  - https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-calling-visa
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
  - https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-subjek-visa-on-arrival
discovered_by: agent.s13-fresh (single-session reader, WebFetch, 2026-08-23)
adversarial_review: codex
---

# Live source re-verification for seq-13's freshness-half `verified_at` re-stamp (2026-08-23)

**Method** — QW-5 (verbatim quotation), same method as the seq-9/seq-10/seq-12 rechecks
(`inc4-pack-edits/freshness-restamp-2026-08-19.md`,
`inc5-pack-edits/freshness-restamp-2026-08-20.md`). For each of the 18 `OFFICIAL_PORTAL`
source records under `MAX_AGE_SINCE_VERIFIED_AT: 604800` in
`rulepack-prod-012.source.json` (sequence 12, version `2026.8.20`, all 18 stamped
`verified_at` `2026-08-20T06:14:00Z`/`06:15:00Z` by the seq-12 recheck, expiring
`2026-08-27T06:14Z`/`06:15Z`): resolved every rule (`rules[].source_refs`) AND every
product (`products[].source_refs`) citing the record, fetched the live page
(`WebFetch`), and compared its current text against the specific fact each citation
grounds. HTTP reachability alone is never treated as proof — every verdict below rests
on a verbatim quote. Fetches executed 2026-08-23, single session, no parallel readers
(unlike the 3-reader seq-10/seq-12 split — flagged under Confidence below).

**Trigger** — none of the 18 sources were stale when this recheck ran (window opens
2026-08-27T06:14/06:15Z). This is a **pre-emptive** re-check, run ~4 days ahead of
expiry so the re-stamp lands with a clean evidence base before the engine starts
stale-abstaining (the exact failure mode recorded for production in the 2026-08-19
seq-9 LIVE STATE entry, ~6 days of `DECISIVE_SOURCE_STALE` on every portal-decisive
path).

**Why this is seq-13's freshness half, not a standalone sequence** — `rulepack-prod-013.rules-only.json`
(PR #4660, a separate rule-tightening lane closing the E31C WNA-WNI nationality gap +
removing D12's ungrounded conjunct) is one of *two halves* of seq-13, by design:
`fold_pack_seq13_rules.py`'s own docstring states this fold covers ONLY the rule-graph
half, that a separate lane owns re-verifying the 18 `OFFICIAL_PORTAL` `source_records`
for freshness (that lane is this document), and that a third step combines both halves
into the real `rulepack-prod-013.source.json`. **An earlier pass through this task
mis-read that architecture and built a standalone `fold_pack_seq14.py` chaining
directly onto seq-12** — reasoning by analogy to seq-12 (itself a freshness-only
sequence) instead of reading seq-13's own docstring. That path was corrected the same
day it was built: a freshness-only pack forked off seq-12 would ship WITHOUT seq-13's
rules fixes (the E31C nationality gate and the D12 conjunct removal), and only one of
two sibling packs forked from the same parent can become the signed active pack.
`fold_pack_seq14.py` and its output were parked, uncommitted, under
`research/visa/doctrine-factory/e5/HELD-seq14-parked-2026-08-23/` for recoverability
only — not shipped, not a live fold. The combining third step (previously missing
entirely — no script, no `rulepack-prod-013.source.json` anywhere) is now owned by
lane `s13-join` (PR #4667), which consumes this document's evidence plus
`source-restamp-edits.json` in this directory as its freshness input.

## Verdict tally

| Verdict | Count | Records |
|---|---|---|
| **UNCHANGED** | **18** | bc309fa9, 3da72c7b, dcf08e19, 950a9f63, 570f2bc4, 40523028, 50457cd0, ecd22722, f9306203, 86880290, 153beca1, 2d090f3a, ca5a2ce8, d3ad622e, 5e64ec6b, 38242587, cb1b7182, 38a6cb08 |
| **CHANGED** | **0** | — |
| **UNREACHABLE** | **0** | — |

Every UNCHANGED verdict below re-stamps `verified_at`/`verified_by`. `content_sha256`
is untouched everywhere: no page's cited content differs from what the pack claims.

Two non-blocking observations are recorded below (§19, §20) — neither is a CHANGED
verdict, neither blocks the re-stamp.

## Per-record findings

### 1. `bc309fa9` — Calling Visa country list — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-calling-visa`
— cited by `review.calling-visa` (CALLING_VISA_REVIEW) and `review.citizenship-conflict`
(CITIZENSHIP_LIST_DIVERGENCE), grounding the embedded 6-code set `AF, IL, KP, LR, NG,
SO`. Live page, verbatim, under heading *"Daftar Negara, Pemerintah Dari Daerah
Administrasi Khusus Suatu Negara, dan Entitas Tertentu"*:
> 1. Afganistan 2. Israel 3. Korea Utara 4. Liberia 5. Nigeria 6. Somalia

Exact 1:1 match, 6/6, no Cameroon/Guinea (the seq-3 retroactive fix's premise still
holds).

### 2. `3da72c7b` — Izin Tinggal Peralihan press release (2024-04-24) — UNCHANGED
`https://www.imigrasi.go.id/siaran_pers/2024/04/23/izin-tinggal-peralihan-jembatani-proses-transisi-izin-tinggal-wna-di-ri`
— cited only at PRODUCT level (BRIDGING), grounding `stay_policy.maximum_days: 60` and
`extension_policy.allowed: false`. Live page, verbatim: *"Masa berlaku Izin Tinggal
Peralihan yakni 60 hari"* — exact match on the 60-day figure. Press-release date
confirmed still shown as *"24 Apr 2024"*. No sentence anywhere on the page states the
permit can be extended — consistent with `allowed: false`.

### 3. `dcf08e19` — ITK→ITAS conversion service page — UNCHANGED
`https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian/izin-tinggal-kunjungan-menjadi-izin-tinggal-terbatas`
— cited by `hf.bridging.from-visit-itk` (BRIDGING_FROM_VISIT_ITK_PROHIBITED, excluding
ITK-based statuses `ITK_FROM_BVK`/`ITK_FROM_VISIT_C`/`ITK_FROM_VISIT_D`/A1/C1/C2/C6 from
the Bridging product) and co-cited at BRIDGING product level. Live page, verbatim
title: *"Alih Status ITK menjadi ITAS"*; eligibility: *"Orang Asing dapat diberikan
alih status Izin Tinggal Kunjungan (ITK) menjadi Izin Tinggal Terbatas (ITAS)
berdasarkan permohonan."* Legal basis unchanged: *"Peraturan Menteri Hukum dan HAM RI
Nomor 22 Tahun 2023 tentang Visa dan Izin Tinggal"*. The page still describes this as
the SEPARATE conversion route for visit-permit holders — consistent with why they are
excluded from Bridging.

### 4. `950a9f63` — E31A (Visa Keluarga Suami/Istri WNI) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31A` — cited by
`el.e31a-spouse-wni-support` (PURPOSE_PRODUCT_MATCH) and `el.e31a-funds-2000`
(REQ_FUNDS_2000), plus product-level stay/extension. Live page, verbatim: stay *"1
tahun atau 2 tahun dihitung sejak tanggal kedatangan"* (matches `stay_policy` 365–730
days); funds *"bukti memiliki biaya hidup ... rekening koran 3 bulan terakhir ...
dengan jumlah minimal USD $2000"* — exact match; extension confirmed generically
allowed (*"Izin Tinggal dari jenis visa ini dapat diperpanjang"*), consistent with
`extension_policy.allowed: true` (the specific 5×365-day figure is carried by the
co-cited primary-law source, not this portal page, and was out of this task's 18-record
scope).

### 5. `570f2bc4` — E31B (Visa Keluarga Suami/Istri Pemegang ITAS/ITAP) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31B` — cited by
`el.e31b-spouse-itas-support` and `el.e31b-sponsor-itas-itap` (REQ_SPONSOR_ITAS_ITAP).
Title unchanged: *"E31B Visa Keluarga Suami/Istri Pemegang ITAS/ITAP"* — the
sponsor-holds-ITAS/ITAP fact is carried by the page's own classification (same
implicit-but-unambiguous status the seq-10/seq-12 rechecks recorded for this record).
Stay/extension text identical in shape to E31A.

### 6. `40523028` — E31C (Visa Keluarga Anak Hasil Perkawinan Sah WNA-WNI) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31C` — cited by
`el.e31c-child-mixed-marriage-support`, `el.e31c-mixed-marriage-parents`
(REQ_MIXED_MARRIAGE_PARENTS, `family.marriage_registered == true`) and
`hf.e31c-marriage-not-registered` (REQ_PARENTS_MARRIAGE_REGISTERED,
`family.marriage_registered == false` → EXCLUDE). Live page, verbatim: *"Bukti
perkawinan orang tua berupa: Bukti pelaporan atau pencatatan pada Perwakilan Republik
Indonesia atau instansi yang berwenang di bidang pencatatan sipil dan akta perkawinan
yang telah diterjemahkan dalam bahasa Indonesia oleh penerjemah tersumpah; atau Buku
nikah atau akta perkawinan yang dikeluarkan oleh kementerian atau lembaga berwenang
(jika perkawinan dilakukan di wilayah Indonesia)."* — this is exactly the
registered/recorded-marriage evidentiary standard the `family.marriage_registered`
fact encodes (the two accepted routes are foreign registration + sworn translation, or
an Indonesian-issued marriage book/certificate). Direct, current support for both the
SUPPORT and the EXCLUDE-on-unregistered rule.

*(Note: this record does NOT ground the applicant's own nationality/parentage
combination — that is a separate, already-known open item at the RULE level (the
E31C WNA-WNI nationality gap PR #4660 is closing), not a source-freshness defect.)*

### 7. `50457cd0` — E31D (Visa Keluarga Anak Bawaan WNA Perkawinan Sah WNA-WNI) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31D` — cited by
`el.e31d-stepchild-support`, `el.e31d-step-parent-relation`
(REQ_STEP_PARENT_RELATION), `el.e31d-sponsor-mixed-marriage`
(REQ_SPONSOR_MIXED_MARRIAGE). Title unchanged: *"E31D Visa Keluarga Anak Bawaan WNA
Perkawinan Sah WNA-WNI"*; requirements still include *"Bukti perkawinan orang tua"* and
an extension clause: *"Izin Tinggal dari jenis visa ini dapat diperpanjang dan dapat
dialihkan menjadi izin tinggal lainnya."*

### 8. `ecd22722` — E31E (Visa Keluarga Anak Pemegang ITAS/ITAP) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31E` — cited by
`el.e31e-child-itas-support` and `el.e31e-sponsor-itas-itap` (REQ_SPONSOR_ITAS_ITAP)
only (its two HARD_FILTER predicates were re-sourced away to primary law `c9e6f0e4` in
the seq-9 fold — confirmed still the case: this record has 2 ELIGIBILITY citations and
0 HARD_FILTER citations in the current pack). Live page, verbatim requirement:
*"Izin Tinggal Terbatas/Izin Tinggal Tetap atau Visa Tinggal Terbatas milik orang tua
yang masih berlaku"* — exact match for the parent-holds-ITAS/ITAP requirement.

### 9. `f9306203` — E31F (Visa Keluarga Anak dengan Orang Tua WNI) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31F` — cited by
`el.e31f-child-wni-parent-support` and `el.e31f-adult-age-review`
(E31F_ADULT_AGE_ADVISOR_CHECK, co-sourced with primary law `e3572ad2`). Title
unchanged: *"E31F Visa Keluarga Anak Dengan Orang Tua WNI"*. No age-18/marital-status
language on this specific page — same as the prior recheck's finding, and not a defect:
the rule is co-sourced with the Permenkumham record for the numeric threshold, this
portal page only needs to ground the product-purpose match, which it does.

### 10. `86880290` — E31G (Visa Keluarga Orang Tua dari Anak WNI) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31G` — cited by
`el.e31g-parent-wni-child-support`. Title unchanged: *"E31G Visa Keluarga Orang Tua
dari Anak WNI"*; eligibility for *"Orang tua dari Anak WNI"* with proof of legal
relationship (birth certificate/adoption decree) still described.

### 11. `153beca1` — E31H (Visa Keluarga Orang Tua dari Anak Pemegang ITAS/ITAP) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31H` — cited by
`el.e31h-parent-itas-child-support` and `el.e31h-sponsor-itas-itap`. Live page,
verbatim: *"Izin Tinggal Terbatas/Izin Tinggal Tetap atau Visa Tinggal Terbatas yang
masih berlaku milik anak"* — exact match for the child-sponsor-holds-ITAS/ITAP
requirement.

### 12. `2d090f3a` — E31J (Visa Keluarga Anak yang Bergabung dengan Saudara Kandung Pemegang ITAS/ITAP) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31J` — cited by
`el.e31j-sibling-itas-support`, `el.e31j-sponsor-itas-itap`, and
`el.e31j-dependency-age` (E31J_DEPENDENCY_AGE_ADVISOR_CHECK, co-sourced with primary
law). Live page, verbatim: *"Visa tinggal terbatas, Izin Tinggal Terbatas/Izin Tinggal
Tetap atau Visa Tinggal Terbatas yang masih berlaku milik saudara kandung"* — exact
match for the sibling-sponsor-holds-ITAS/ITAP requirement. No standalone
dependency-age text on the page — same as E31F, not a defect (co-sourced fact).

### 13. `ca5a2ce8` — D1 (Visa Kunjungan Wisata, multiple-entry) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D1` — cited by 6 rules
(multi-entry support, 6-month passport, USD 2000 funds, CV, itinerary, support
letter). Live page, verbatim: entry *"Visa Kunjungan untuk beberapa kali masuk ke
Indonesia"*; stay *"maksimal 60 hari setiap kedatangan"* (matches `stay_policy`
60/60); extension *"dapat memperpanjang izin tinggal ini beberapa kali hingga
maksimal 180 hari"* (arithmetically consistent with the pack's `maximum_extensions: 2,
days_per_extension: 60` → 60 + 2×60 = 180 total); funds *"rekening koran 3 bulan
terakhir ... sebesar minimal USD2000"*; passport *"masih berlaku paling singkat 6 bulan
sebelum masa berlakunya habis"*; CV/itinerary/support-letter all present verbatim
(*"curriculum vitae"*, *"rencana perjalanan (travel itinerary)"*, *"surat keterangan,
undangan, atau korespondensi dari instansi pemerintah atau lembaga swasta"*).

### 14. `d3ad622e` — D2 (Visa Kunjungan Bisnis, multiple-entry) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D2` — same 6-fact shape as D1;
all verbatim-confirmed identical (60-day stay, 180-day extension cap, USD 2000, 6-month
passport, CV/itinerary/support letter). Business purpose intact.

### 15. `5e64ec6b` — D12 (Visa Kunjungan Pra-Investasi, multiple-entry) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D12` — cited by 7 rules
including `hf.d12-onshore-conversion-excluded` (D12_NOT_CONVERTIBLE). Live page,
verbatim: stay *"izin tinggal maksimal 180 hari setiap kedatangan"* (matches
`stay_policy` 180/180); funds *"minimal USD5000 atau dalam mata uang lain yang setara
jumlahnya"* — exact match; passport 6-month clause identical to D1/D2; non-convertibility
*"tidak bisa dialihkan menjadi izin tinggal terbatas"* — exact match. Extension:
*"Anda dapat memperpanjang izin tinggal ini satu kali hingga keseluruhan masa tinggal
paling lama 12 bulan (1 tahun) atau 2 tahun, bergantung pada durasi visa yang Anda
pilih."* — the pack's `maximum_extensions: 1, days_per_extension: 180` (→ 360 days
total) matches the "1 tahun" branch exactly, and the pack's own `pricing_key.item_key`
is explicitly labeled `"D12 Business Investigation (1 Year)"` — i.e. the pack
deliberately models only the 1-year tier of what the live page shows is actually a
two-tier product (a "2 tahun" / Rp 7,000,000 tier also exists, priced separately on the
page: *"Masa tinggal 2 tahun Rp. 7.000.000"* vs *"Masa tinggal 1 tahun Rp.
5.000.000"*). This is **not** a CHANGED verdict — nothing the pack currently claims is
contradicted — but it is worth flagging: the D12 page supports a second, unmodeled
product variant. Scope note, not an action item for this fold.

### 16. `38242587` — E30A (Visa Pendidikan Dasar dan Menengah) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E30A` — cited by 7 rules
including `review.minor-without-guardian` (MINOR_WITHOUT_CONFIRMED_GUARDIAN). Live
page, verbatim: living cost *"bukti memiliki biaya hidup ... dengan jumlah minimal USD
$2000 (dua ribu Dolar Amerika Serikat)"* — exact match; passport *"Paspor kebangsaan
yang sah dan masih berlaku paling singkat 6 bulan sebelum masa berlakunya habis"* —
exact match. **Known, already-tracked residual (not new, not re-opened here):** the
page still contains zero occurrences of anak/wali/minor/guardian language — this record
remains the sole cited source for `review.minor-without-guardian`, which it does not
independently support. This exact gap was found and dispositioned ACCEPTED-PARTIAL
(escalated to its own PENDING-ARMS row, not silently patched) in the 2026-08-19 seq-10
recheck (`inc4-pack-edits/freshness-restamp-2026-08-19.md` §18) — this session
re-confirms the page is unchanged, the gap is unchanged, and no new action is implied.

### 17. `cb1b7182` — E30B (Visa Pendidikan Tinggi) — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E30B` — cited by 7 rules
including `el.e30b-izin-belajar` (STUDY_PERMIT_KEMDIKBUD). Live page, verbatim: stay
*"1 tahun 2 tahun, atau 4 tahun"* (matches `stay_policy` 365–1460 days — 1/2/4-year
options, min/max bracket correct); funds/passport clauses identical wording to E30A
(USD 2000 / 6-month passport). The known terminology gap persists unchanged: the page
text captured does not use the literal phrase "Izin Belajar"/Kemdikbud — consistent
with the seq-10 recheck's note that this is a recorded, non-regressive gap, not new.

### 18. `38a6cb08` — VOA country list — UNCHANGED
`https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-subjek-visa-on-arrival`
— cited by `el.b1.tourism` (B1_VOA_ELIGIBLE), `hf.b1.not-voa-nationality`
(VOA_NATIONALITY_ONLY), and `review.citizenship-conflict`. The pack embeds an explicit
97-country ISO-code list in both rules. Live page lists **97** countries, numbered
1–97. Full programmatic diff of the pack's 97 ISO codes against the live page's 97
country names (mapped to ISO-3166): **zero codes in the pack absent from the live
list, zero codes on the live list absent from the pack** — exact 97/97 set match.

## Two non-blocking observations (not CHANGED, not action items for this fold)

### 19. D12's unmodeled 2-year tier (source `5e64ec6b`, §15 above)
The live D12 page prices two distinct duration tiers (1 year / Rp 5,000,000 vs 2 years
/ Rp 7,000,000); the pack's `pricing_key.item_key` self-documents that only the 1-year
tier is modeled (`"D12 Business Investigation (1 Year)"`). Nothing currently asserted
by the pack is false — this is a scope gap, not a freshness defect. Worth a
PENDING-ARMS row if a future session wants to add the 2-year D12 variant as a second
`product_version`, but out of this fold's mandate (re-stamp sources, don't edit rules
or products).

### 20. E30A/E30B extension_policy is `UNKNOWN`/`allowed:false` by deliberate design
A generic boilerplate sentence *"Perpanjangan izin tinggal dapat dilakukan secara
online melalui evisa.imigrasi.go.id"* appears verbatim on both E30A and E30B, which on
its own could misread as "extension allowed". Checked before writing this up: this is
**not** a defect. `docs/audits/2026-08-06-visa-oracle-g1-source-decision-packet.md`
point 9 (Zero-approved, G1 gate) explicitly decided that *"all uncited [extension]
policies are explicit neutral UNKNOWN with reason EXTENSION_POLICY_NOT_VERIFIED; no
duration or positive claim is inferred"* — precisely because a single generic
"perpanjangan dapat dilakukan online" sentence repeated across ~11 different visa-type
pages is not curated, product-specific evidence for a *specific* extension count/
duration, and the schema enforces `status=UNKNOWN ⇒ allowed=false` as a fail-closed
invariant (`test_prod_sequence2_bundle.py`). Recorded here so a future reader doesn't
independently rediscover the same false lead.

## Timestamp method note (`verified_at`/`verified_by` for this batch)

**Corrected 2026-08-23, second pass.** An earlier draft of this note stamped all 18
records with `2026-08-23T06:14:23Z`, framed as "a genuine `date -u` reading taken
after all 18 fetches had been dispatched" versus a "later candidate reading". Neither
half of that framing survived scrutiny: `06:14:23Z` is four hours older than this
file's own on-disk mtime and earlier than this reading session was even spawned, so
it could not have been produced by an actual `date -u` call on this machine at any
point during the pass — it was a reconstruction from memory of a value never
independently re-verified, which is exactly the kind of unearned tool-output citation
the anti-hallucination discipline exists to catch. There was no real second
"candidate reading" to choose between; there was one unsourceable number.

Per-source fetch timestamps were not individually logged during the QW-5 verification
pass itself (no `date` command run before/after each `WebFetch` call), and there is no
way to reconstruct them retroactively. `verified_at` for all 18 restamped records is
therefore, honestly, a **single pass-level stamp applied at write time, not 18
independently observed fetch times.** The value below is a live reading taken in this
turn, at the moment this ledger was written — not reconstructed, not rounded:

```
$ date -u +%Y-%m-%dT%H:%M:%SZ
2026-08-23T10:44:48Z
```

`2026-08-23T10:44:48Z` is what `source-restamp-edits.json` in this directory records
as `new_verified_at` on all 18 entries. `current_verified_at`/`current_verified_by`
on each entry were independently re-verified against the actual bytes of
`rulepack-prod-012.source.json` (not assumed) before this edit — every value matches.

This is now the freshness half of **seq-13**, consumed by the seq-13 combining fold
(lane `s13-join`, PR #4667), not by any standalone seq-14 pack — an earlier version of
this work built a standalone `fold_pack_seq14.py`; that path was superseded the same
day (seq-13 was already architected as rules-half + freshness-half + a combining
step) and the fold script was parked, uncommitted, under
`research/visa/doctrine-factory/e5/HELD-seq14-parked-2026-08-23/` for recoverability
only.

## Confidence

High for all 18 UNCHANGED verdicts on the SPECIFIC facts each rule/product actually
cites the record for — every verdict above rests on a verbatim Indonesian quote fetched
live in this session, not on memory, cache, or a prior report's wording. The VOA
97-country set was diffed programmatically (ISO-code set equality), not eyeballed.

Two honesty caveats, both explicit rather than papered over:

1. **Single-reader session, no independent cross-check on the fetches themselves.**
   Unlike the seq-10/seq-12 rechecks (3 parallel readers + orchestrator, plus a
   subsequent Codex/Kimi adversarial pass on the pack edit before it landed), this
   report's 18 fetches were produced by one reader in one session. This document is
   not the head of its own PR — it is an input consumed by the seq-13 combining fold
   (lane `s13-join`, PR #4667); the `## Adversarial review` section below is left for
   whatever R1-gated review that PR undergoes to record findings against, and does not
   itself re-fetch the 18 live pages.
2. **WebFetch converts HTML→markdown through a small intermediate model before I see
   it.** Mitigated with narrow, quote-only prompts and, for the two records where the
   first answer was ambiguous or surprising (D12's extension sentence, the VOA count),
   re-fetching with a sharper prompt or cross-checking programmatically rather than
   accepting the first paraphrase. `content_sha256` was never recomputed — the
   verbatim quotes are the evidence, per the QW-5 method, not a byte-level hash
   comparison (and per team-lead's note, the Ditjen pages embed a per-request CSRF
   token so two identical-content fetches hash differently — `content_sha256`
   recomputation would be a false signal here, not a stronger one).

No source was UNREACHABLE and none returned anything resembling a 404, redirect, or
JS-only shell — all 18 `imigrasi.go.id` pages rendered readable server-side HTML text
in this session.

## Adversarial review

**Seat: codex (`gpt-5.6-sol`, effort high), 2026-08-23. Verdict: SHIP.** Independent,
generator≠grader — reviewer had no part in authoring the ledger or this report.
Scope: `source-restamp-edits.json` + this document only (the parked seq-14 fold was
explicitly excluded, marked out-of-scope). All findings REFUTED — none upheld:

- **Ledger** — 18/18 entries, exact 7-field edit-pair schema, every
  `current_verified_at`/`current_verified_by` cross-checked against
  `rulepack-prod-012.source.json`'s actual bytes (not eyeballed), restamp set
  identical to the 18 `OFFICIAL_PORTAL` records, no extra keys.
- **Timestamp** — ran `date -u` independently at review time (`10:52:06Z`), confirming
  `10:44:48Z` is fully plausible (~7 minutes earlier, consistent with normal session
  elapsed time). Confirmed the correction of the prior unsourceable value is disclosed
  openly rather than hidden, and that all 18 entries carry exactly the new timestamp.
- **Citations** — spot-checked E31C, D12, the Calling Visa list (6/6), and the VOA
  country list (97) against live official pages. The main `imigrasi.go.id` E31C/D12
  routes returned 403 to the reviewer's automated fetch (bot-blocking, not a content
  issue), so the reviewer independently located and verified the same verbatim text
  via official regional Ditjenim mirror pages: [E31C](https://kanwilditjenimkalbar.id/layanan-wna/e31c-visa-keluarga-anak-dari-ibu-ayah-wni/),
  [D12](https://kanwilditjenimkalbar.id/layanan-wna/d12-visa-pra-investasi/),
  [Calling Visa](https://jakartapusat.imigrasi.go.id/layanan/warga-negara-asing-wna/daftar-subjek-voa-bvk-calling-visa/daftar-subjek-calling-visa),
  [VOA](https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-subjek-visa-on-arrival).
  No invented citation or live-page drift found.
- **Scope/integrity** — no key or `content_sha256` mutation anywhere; the join fold's
  own guard admits only the seven declared fields. The HELD seq-14 material appears
  only in its parking narrative — no import, no test collection, no live fold.
- **R1 gate** — frontmatter + heading present; `python3 scripts/check_adversarial_review.py`
  independently run by the reviewer: `PASS — 1 research file(s) carry a valid
  adversarial review`.
