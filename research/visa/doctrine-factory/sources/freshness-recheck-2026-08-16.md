---
date: 2026-08-16
domain: visa
client_case: none
sources:
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
  - https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-calling-visa
  - https://www.imigrasi.go.id/siaran_pers/2024/04/23/izin-tinggal-peralihan-jembatani-proses-transisi-izin-tinggal-wna-di-ri
  - https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian/izin-tinggal-kunjungan-menjadi-izin-tinggal-terbatas
  - https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian
  - https://evisa.imigrasi.go.id/front/faq/08cdfd2e-873e-4de7-9eeb-8f485828c155
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
discovered_by: agent.air-m5.ops.qw5-freshness-recheck
adversarial_review: codex
---

# QW-5 — Semantic freshness recheck of the 20 OFFICIAL_PORTAL sources (rulepack-prod-007)

**Recheck timestamp**: 2026-08-16T22:11 WITA (agent session)
**Active pack**: `rulepack-prod-007` (`apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json`, sequence 7, 30 `source_records`)
**Method**: for each `authority_type: OFFICIAL_PORTAL` source record, resolved the rules/products citing it via `source_refs` to determine the exact fact the record is cited FOR, then fetched the live page (`WebFetch`) and compared the page's current content against that claimed fact. HTTP reachability alone was never treated as proof — every verdict below is a content comparison.
**Trigger**: freshness_policy on all 20 records is `MAX_AGE_SINCE_VERIFIED_AT`, `max_age_seconds: 604800` (7 days). 19/20 records were `verified_at: 2026-08-06T06:19:49Z` (due 2026-08-13, now 3 days overdue); 1/20 (`imigrasi-voa-country-list`) was `verified_at: 2026-08-08T00:00:00Z` (due 2026-08-15, now 1 day overdue). All 20 are overdue as of this recheck.

## Verdict tally

| Verdict | Count |
|---|---|
| CURRENT (unqualified) | 16 |
| CURRENT WITH EXCEPTION (record supports its primary facts; ≥1 co-cited fact on the same page is unsupported — see #18) | 1 |
| CHANGED | 3 |
| UNREACHABLE | 0 |
| SUPERSEDED | 0 |
| **Total** | **20** |

Note (post-adversarial-review correction, Codex `gpt-5.6-terra`): record #18 (`imigrasi.go.id.e30a.daftar-visa-indonesia`) was originally tallied as unqualified CURRENT even though it is the sole, unsupported source for `review.minor-without-guardian` — the same defect class as the #10 CHANGED verdict, just lower safety weight (soft REVIEW trigger, not HARD_FILTER). Re-tallied here as CURRENT WITH EXCEPTION rather than reclassifying it CHANGED outright, because its two OTHER cited facts (passport validity, USD 2000 funds) are verbatim-confirmed on the page — only the `review.minor-without-guardian` citation is unsupported. Treat it with the same seq-9 urgency as a CHANGED record; see recommendation #4 below.

## Per-record verdicts

### 1. `imigrasi-calling-visa-country-list` (`bc309fa9-d14e-5625-b914-72fe4a68c19d`)
- **URL**: `.../daftar-negara-voa-bvk-calling-visa/daftar-negara-calling-visa`
- **Cited for**: `review.calling-visa` / `review.citizenship-conflict` — the 6-nationality Calling Visa list (AF, IL, KP, LR, NG, SO)
- **Checked**: fetched page; the "Daftar Negara, Pemerintah Dari Daerah Administrasi Khusus Suatu Negara, dan Entitas Tertentu" section lists exactly 6 entries: Afganistan, Israel, Korea Utara, Liberia, Nigeria, Somalia — matches AF/IL/KP/LR/NG/SO 1:1.
- **Verdict**: **CURRENT**. Minor caveat: the fetch model could not confirm the section is explicitly labeled "Calling Visa" on this exact sub-page (the label lives at the parent nav level) — content matches, labeling context not re-verified pixel-for-pixel.

### 2. `imigrasi-press-2024-04-24-izin-tinggal-peralihan` (`3da72c7b-783e-51e3-9168-6c54bce709ed`)
- **URL**: `.../siaran_pers/2024/04/23/izin-tinggal-peralihan-jembatani-proses-transisi-izin-tinggal-wna-di-ri`
- **Cited for**: product-level context on the bridging/transitional stay permit concept (Izin Tinggal Peralihan)
- **Checked**: page still live, describes the April 2024 regulation enabling onshore transition between stay permits without departing Indonesia, 60-day max validity, 3-day pre-expiry application window.
- **Verdict**: **CURRENT**.

### 3. `imigrasi-alih-status-itk-itas-service-page` (`dcf08e19-fbc3-5f96-93fa-0325b1ffe91d`)
- **URL**: `.../wna/izin-tinggal-keimigrasian/izin-tinggal-kunjungan-menjadi-izin-tinggal-terbatas`
- **Cited for**: co-source (with `9248b1d7-...`) on `hf.bridging.from-visit-itk` (`BRIDGING_FROM_VISIT_ITK_PROHIBITED`, applies to `current_status_code` ∈ {ITK_FROM_BVK, ITK_FROM_VISIT_C/D, A1, C1, C2, C6})
- **Checked**: page confirms the general ITK→ITAS alih-status procedure exists, with a 30-day-before-expiry application window; it does NOT itself state a prohibition — it describes the *normal* visit-ITK→ITAS path, not the specific excluded status codes.
- **Verdict**: **CURRENT** as a corroborating source for the alih-status procedure/timing; the actual prohibition claim rests on the co-cited source `9248b1d7-...` (not OFFICIAL_PORTAL, out of QW-5 scope). No contradiction found — the page is silent on the excluded codes, not counter to them. Flagged as a **narrow-scope corroborator** worth noting for seq-9 (see recommendations).

### 4. `imigrasi.go.id.izin-tinggal-keimigrasian` (`ee8fe5b8-b0b4-544a-bf9a-fe53c3e316f2`)
- **URL**: `.../wna/izin-tinggal-keimigrasian`
- **Cited for**: 21 `source_refs` total (18 rules + 3 product refs, per pack JSON) — general landing page co-cited (alongside the D1/D2/D12-specific pages and one other source) for `PASSPORT_VALIDITY_6_MONTHS_REQUIRED`, `PROOF_OF_FUNDS_D1/D2`, `CV_REQUIRED`, `ITINERARY_REQUIRED`, `SUPPORT_LETTER_REQUIRED` on D1/D2/D12
- **Checked**: page covers "Izin Tinggal Kunjungan" generically; its own "Persyaratan Dokumen" section lists only 3 items (valid passport, sponsor letter if applicable, statement of purpose) — it does **not** carry the specific 6-month/USD 2000/CV/itinerary requirements it is co-cited for.
- **Verdict**: **CHANGED**. Content no longer (or never did, at this granularity) supports the specific facts it's cited for at this URL. Not a false claim overall — the same facts ARE verified live on the D1 (`ca5a2ce8`), D2 (`d3ad622e`), D12 (`5e64ec6b`) product-specific pages (all CURRENT, see below) — but this general page is a weak/stale corroborator riding on 18 rules (+3 product refs). **Recommend for seq-9**: either point these rules' generic-source leg at a URL that actually carries the requirement text, or drop this record as a co-source where the product-specific page + primary-law source already suffice.

### 5. `evisa.imigrasi.go.id.faq.student-visa-prohibitions` (`0497cb52-9c10-5ad5-a0ea-596e7678bd9b`)
- **URL**: `https://evisa.imigrasi.go.id/front/faq/08cdfd2e-873e-4de7-9eeb-8f485828c155`
- **Cited for**: 0 rule/product refs in the current pack (orphan record — kept for context/future E30 prohibition rules)
- **Checked**: page exists and loads. It does contain a work-prohibition statement ("You are prohibited from doing work or employment," plus a ban on selling goods/services or receiving compensation from Indonesian entities) but is presented as a general-information block, not the structured Q&A pairs the record's title implies, and does not literally reference E30/E30A/E30B codes.
- **Verdict**: **CHANGED**. Page reachable and topically adjacent, but structure/content diverges from the record's implied claim (a dedicated student-visa FAQ Q&A). Low priority (0 active rule dependencies) but should be re-scoped or re-titled for seq-9 if it's ever wired into a rule.

### 6. `imigrasi.go.id.e31a.daftar-visa-indonesia` (`950a9f63-0b78-5a9e-ba12-9454e4b7dfb2`)
- **Cited for**: `PURPOSE_PRODUCT_MATCH`, `REQ_FUNDS_2000` (E31A spouse-of-WNI visa)
- **Checked**: page states "bukti memiliki biaya hidup ... dengan jumlah minimal USD $2000" — exact match.
- **Verdict**: **CURRENT**.

### 7. `imigrasi.go.id.e31b.daftar-visa-indonesia` (`570f2bc4-5120-561f-90ba-58fcd9507514`)
- **Cited for**: `PURPOSE_PRODUCT_MATCH`, `REQ_SPONSOR_ITAS_ITAP` (E31B spouse-of-ITAS/ITAP-holder visa)
- **Checked**: sponsor requirement present; ITAS/ITAP-holder status is embedded in the visa classification/title rather than a separately enumerated bullet, but is unambiguous from the page.
- **Verdict**: **CURRENT**.

### 8. `imigrasi.go.id.e31c.daftar-visa-indonesia` (`40523028-431b-5ae0-a937-277882f0f243`)
- **Cited for**: `PURPOSE_PRODUCT_MATCH`, `REQ_MIXED_MARRIAGE_PARENTS` (E31C mixed-marriage child visa)
- **Checked**: page requires official proof of the parents' legally registered marriage, from Indonesian civil registration or foreign authority with sworn translation — direct match.
- **Verdict**: **CURRENT**.

### 9. `imigrasi.go.id.e31d.daftar-visa-indonesia` (`50457cd0-b67f-5b88-bf66-33bcf62f3d9b`)
- **Cited for**: `PURPOSE_PRODUCT_MATCH`, `REQ_STEP_PARENT_RELATION`, `REQ_SPONSOR_MIXED_MARRIAGE`
- **Checked**: sponsor requirement present verbatim; step-parent relationship is implicit in the visa's defined scope ("Anak Bawaan WNA dari Perkawinan Sah WNA-WNI") plus required documents (birth certificate, parents' marriage proof, Indonesian parent's KK) rather than a standalone labeled bullet.
- **Verdict**: **CURRENT** (implicit-but-unambiguous match).

### 10. `imigrasi.go.id.e31e.daftar-visa-indonesia` (`ecd22722-3e42-5808-be18-45fbb7d8e9c5`)
- **Cited for**: `hf.e31e-adult-excluded` (age ≥18 → EXCLUDE, `REQ_UNDER_18`) and `hf.e31e-married-excluded` (marital status ≠ SINGLE → EXCLUDE, `REQ_UNMARRIED`) — **this record is the SOLE `source_ref` for both hard-filter rules** — plus `PURPOSE_PRODUCT_MATCH`, `REQ_SPONSOR_ITAS_ITAP`.
- **Checked**: page requires the parent-sponsor to hold valid ITAS/ITAP/Limited Stay Visa (matches `REQ_SPONSOR_ITAS_ITAP`), but contains **no text at all** stating an under-18 or unmarried requirement for the child applicant.
- **Verdict**: **CHANGED**. This is the most consequential finding of the recheck: two safety-relevant HARD_FILTER rules (age/marital exclusion) cite this page as their **only** source, and the live page does not corroborate either condition. Either the page dropped this language since verification, or the rule was authored from a different document (regulation text, not this portal page) and mis-attributed. **Recommend for seq-9**: re-source `hf.e31e-adult-excluded` / `hf.e31e-married-excluded` against the underlying regulation (Permenkumham/UU keimigrasian definition of minor dependent) or re-verify against an archived/cached version of this page before the next pack build; do not carry this citation forward unexamined.

### 11. `imigrasi.go.id.e31f.daftar-visa-indonesia` (`f9306203-0bdc-5dd8-9603-554e7eefedc8`)
- **Cited for**: `PURPOSE_PRODUCT_MATCH`; `el.e31f-adult-age-review` (co-sourced with `e3572ad2-...`, not OFFICIAL_PORTAL)
- **Checked**: page requires an Indonesian court decision establishing the legal parent-child relationship; no age limit or adult-review language on the page itself, but the adult-age-review rule has an independent co-source outside this record, so the rule is not solely dependent on this URL.
- **Verdict**: **CURRENT** (page supports `PURPOSE_PRODUCT_MATCH`; the age-review nuance is legitimately carried by the co-source, not this page — no contradiction).

### 12. `imigrasi.go.id.e31g.daftar-visa-indonesia` (`86880290-68c2-5220-8f9e-2350678e5f09`)
- **Cited for**: `PURPOSE_PRODUCT_MATCH` (E31G parent-of-WNI-child visa)
- **Checked**: page confirms purpose, mandatory sponsor with evisa.imigrasi.go.id account, USD 2000 funds proof, 6-month passport validity, legal proof of parent-child relationship.
- **Verdict**: **CURRENT**.

### 13. `imigrasi.go.id.e31h.daftar-visa-indonesia` (`153beca1-a24b-5440-bac0-b46c3d19da6f`)
- **Cited for**: `PURPOSE_PRODUCT_MATCH`, `REQ_SPONSOR_ITAS_ITAP` (E31H parent-of-ITAS/ITAP-child visa)
- **Checked**: page states the child-sponsor must hold valid ITAS/ITAP/Limited Stay Visa — exact match.
- **Verdict**: **CURRENT**.

### 14. `imigrasi.go.id.e31j.daftar-visa-indonesia` (`2d090f3a-5a93-5181-b3d1-253d87a1a17c`)
- **Cited for**: `PURPOSE_PRODUCT_MATCH`, `REQ_SPONSOR_ITAS_ITAP`; `el.e31j-dependency-age` (co-sourced with `e3572ad2-...`, not OFFICIAL_PORTAL)
- **Checked**: page requires sibling-sponsor guarantee + valid ITAS/ITAP; no dependency-age language on the page itself, but same co-source pattern as #11 — the age rule doesn't solely rest on this page.
- **Verdict**: **CURRENT** (same reasoning as #11 — no contradiction, dependency-age nuance legitimately carried elsewhere).

### 15. `imigrasi.go.id.d1.daftar-visa-indonesia` (`ca5a2ce8-83bb-58ec-b2d9-285833cf085a`)
- **Cited for**: all 6 D1 eligibility facts (`PURPOSE_PRODUCT_MATCH`, `PASSPORT_VALIDITY_6_MONTHS_REQUIRED`, `PROOF_OF_FUNDS_D1`, `CV_REQUIRED`, `ITINERARY_REQUIRED`, `SUPPORT_LETTER_REQUIRED`)
- **Checked**: page verbatim confirms all 6 — 6-month passport validity, USD 2000 funds via 3-month bank statement, recent photo, CV, itinerary, support letter (institutional or family).
- **Verdict**: **CURRENT**. This is the strong, authoritative source for the D1 requirement bundle — recommend it (not `ee8fe5b8`, see #4) as the primary anchor for these facts going forward.

### 16. `imigrasi.go.id.d2.daftar-visa-indonesia` (`d3ad622e-f2d9-5b31-8ede-bc87e6b9cc0e`)
- **Cited for**: all 6 D2 eligibility facts, same set as D1
- **Checked**: page verbatim confirms all 6, identical structure to D1 page.
- **Verdict**: **CURRENT**.

### 17. `imigrasi.go.id.d12.daftar-visa-indonesia` (`5e64ec6b-8fcc-5518-b70f-87bf22aa5e29`)
- **Cited for**: 6 D12 eligibility facts + `hf.d12-onshore-conversion-excluded` (`D12_NOT_CONVERTIBLE`)
- **Checked**: page confirms passport validity, USD 5000 funds, CV, itinerary, support letter, AND explicitly states the visa "bisa diperpanjang ... namun tidak bisa dialihkan menjadi izin tinggal terbatas" (extendable but not convertible to a limited stay permit) — direct match for the non-convertibility rule too.
- **Verdict**: **CURRENT**.

### 18. `imigrasi.go.id.e30a.daftar-visa-indonesia` (`38242587-f4da-5c31-b0ea-662f7fdc475c`)
- **Cited for**: `LIVING_COST_USD2000` ×3, `PASSPORT_VALIDITY_6_MONTHS_REQUIRED` ×3; `review.minor-without-guardian` (`MINOR_WITHOUT_CONFIRMED_GUARDIAN`) — **sole source_ref**
- **Checked**: page confirms 6-month passport validity and USD 2000 living-cost proof verbatim. However, it contains **no language** about special review procedures for a minor lacking a confirmed guardian.
- **Verdict**: **CURRENT WITH EXCEPTION**. Passport/funds facts are verbatim-confirmed; `review.minor-without-guardian` (sole `source_ref`) is NOT — same class of issue as #10 (sole-source rule with no page-level corroboration). Lower safety weight than #10 (this is a REVIEW-stage soft trigger, not a HARD_FILTER exclusion), but same recommendation: re-source or re-verify before seq-9.

### 19. `imigrasi.go.id.e30b.daftar-visa-indonesia` (`cb1b7182-1e29-58df-9aec-4e9bf66e10de`)
- **Cited for**: `LIVING_COST_USD2000` ×3, `PASSPORT_VALIDITY_6_MONTHS_REQUIRED` ×3; `el.e30b-izin-belajar` (`STUDY_PERMIT_KEMDIKBUD`, co-sourced with `c9e6f0e4-...` and `e3572ad2-...`)
- **Checked**: passport/funds requirements match verbatim. The page does **not** use the term "Izin Belajar" from Kemdikbud — instead it requires "Surat penerimaan dari institusi pendidikan yang mencantumkan lama masa pendidikan" (an institutional acceptance letter stating study duration).
- **Verdict**: **CURRENT**. The acceptance-letter requirement is the portal-facing precursor document to the Kemdikbud Izin Belajar process (not held on this page), and the rule has 2 other co-sources for the Izin Belajar specifics — no contradiction, terminology gap only. Note for seq-9: consider adding an explicit Kemdikbud-source citation if one isn't already among the co-sources' full text.

### 20. `imigrasi-voa-country-list` (`38a6cb08-041f-51e4-86e4-9e73243acd3a`)
- **URL**: `.../daftar-negara-voa-bvk-calling-visa/daftar-negara-subjek-visa-on-arrival`
- **Cited for**: `B1_VOA_ELIGIBLE`, `VOA_NATIONALITY_ONLY`, `CITIZENSHIP_LIST_DIVERGENCE`
- **Checked**: page lists 97 countries/entities — matches the record's locator note ("(97 entries)") exactly. Spot-checked presence of South Africa, USA, major EU states, ASEAN neighbors, Australia/NZ/Japan/China/Russia/Brazil — all present as expected for the VoA-eligible pool.
- **Verdict**: **CURRENT**. No "last updated" date visible on the page itself (same as at original verification) — this is a known limitation of the source, not a regression.

## Sources needing replacement/re-scoping for seq-9

1. **`ee8fe5b8-b0b4-544a-bf9a-fe53c3e316f2` (izin-tinggal-keimigrasian general page)** — CHANGED. Carries 21 `source_refs` (18 rules + 3 product refs) but its own content doesn't support the specific facts. Replace as primary anchor with the product-specific pages (`ca5a2ce8` D1, `d3ad622e` D2, `5e64ec6b` D12, all CURRENT and verbatim-matching) or drop from the co-source list.
2. **`ecd22722-3e42-5808-be18-45fbb7d8e9c5` (E31E page)** — CHANGED, **highest priority**: sole source for 2 safety-critical-adjacent HARD_FILTER rules (`hf.e31e-adult-excluded`, `hf.e31e-married-excluded`) that the live page does not corroborate. Needs a real regulatory source before seq-9 ships, or independent re-verification (cache/wayback check) that the page previously carried this language.
3. **`0497cb52-9c10-5ad5-a0ea-596e7678bd9b` (evisa FAQ)** — CHANGED, low priority (0 active rule refs). Re-title/re-scope to match actual page structure, or retire if never wired into a rule.
4. **`38242587-f4da-5c31-b0ea-662f7fdc475c` (E30A page)** — sole source for `review.minor-without-guardian`, page silent on that fact. Lower urgency than #2 (soft REVIEW trigger, not HARD_FILTER exclusion) but same class of defect — recommend adding a corroborating source or downgrading the citation confidence.

All other 16 OFFICIAL_PORTAL records are CURRENT with content directly supporting the facts they're cited for.

## No mutation performed

This recheck is read-only. No pack file (`.source.json` or `.signed.json`) under `apps/backend-rag/backend/services/visa_engine/contracts/packs/` was modified. Findings above feed seq-9 authoring; they are not applied here.

## Adversarial review

**Reviewer**: Codex (`gpt-5.6-terra`, `codex exec --sandbox read-only --skip-git-repo-check`), run on the finished report as a fresh (generator≠grader) pass — instructed to independently grep the pack JSON for the sole-source claims, verify `ee8fe5b8`'s ref-count, and sanity-check the report's own internal consistency (tallies, PII).

| Finding | Verdict | Disposition |
|---|---|---|
| `ee8fe5b8` has **21 `source_refs`**, not "21 rules" as originally worded — it's 18 rules + 3 product refs. | CONFIRMED | Fixed: reworded the "Cited for" line in record #4, the CHANGED-verdict sentence, and recommendation #1 to say "21 `source_refs` (18 rules + 3 product refs)" instead of "21 rules". |
| The three sole-source claims (`hf.e31e-adult-excluded`, `hf.e31e-married-excluded` → `ecd22722-...` only; `review.minor-without-guardian` → `38242587-...` only) are exact as described. | NOT-AN-ISSUE | No change — claims verified correct. |
| Tally arithmetic (17+3=20) is internally valid, but record #18 (E30A) was folded into unqualified CURRENT despite carrying the same "sole-source, unsupported fact" defect as the CHANGED record #10 (just for a soft REVIEW trigger, `review.minor-without-guardian`, instead of a HARD_FILTER). Recommended a `MIXED`/"CURRENT WITH EXCEPTION" category or tally footnote. | CONFIRMED | Fixed: introduced a "CURRENT WITH EXCEPTION" row in the tally table (16 unqualified CURRENT + 1 CURRENT WITH EXCEPTION + 3 CHANGED = 20), re-labeled record #18's verdict line to CURRENT WITH EXCEPTION, and added an explanatory note directly under the tally table. |
| No PII, credentials, tokens, or secrets found anywhere in the artifact — only public portal URLs and non-secret pack-JSON rule metadata. | NOT-AN-ISSUE | No change. |

Both CONFIRMED findings were cured in this file post-review (2026-08-16, same session). No verdict (CURRENT/CHANGED/UNREACHABLE/SUPERSEDED) was reversed by the review — only wording and tally granularity were corrected. Full Codex output archived at session tool-output `byhvbdwh9` (not committed — ephemeral).
