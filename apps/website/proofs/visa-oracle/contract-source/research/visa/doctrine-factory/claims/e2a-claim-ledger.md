---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/nb2-answers/response-log.jsonl
    note: "raw NB-2 query records — prior QW-1 B0 canary (VO-NB2-003/004/005) + 24 new E2a queries this task"
  - path: research/visa/doctrine-factory/sources/nb2-source-snapshot-2026-08-15.json
    note: "frozen 131-source NB-2 id<->title map, citation resolution target"
  - path: research/visa/doctrine-factory/nb2-answers/e2a-citation-audit.json
    note: "mechanical citation-audit verdicts, this session, 31 records, 0 NOT_COMPILABLE"
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
    note: "active pack seq-7 (SHADOW) — rules the claims below feed, verified live via python3/json this session"
  - path: apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py
    note: "canonical 114-code visa catalog, cross-checked for CF-5 (E31B/E31D index-swap claim)"
  - path: research/visa/doctrine-factory/sources/freshness-recheck-2026-08-16.md
    note: "QW-5 OFFICIAL_PORTAL verdicts, cross-referenced for D1/D2/D12 requirement bundles"
adversarial_review: kimi-k3
---

# E2a atomic claim ledger — D1/D2/D12 + E31B/E31D refuter slice

Task: Visa Oracle doctrine-factory execution plan, item **E2a**, gated on QW-1 B0 canary (PASS,
`research/visa/doctrine-factory/2026-08-15-qw1-b0-canary.md`) and E1 owner ratification (per task
briefing, APPROVED 2026-08-17).

## Method

1. Every claim is one atomic legal fact, backed by ≥1 NB-2 query response, resolved against the frozen
   131-source snapshot via `tools/nb2_citation_audit.py` (mechanical, generator≠grader).
2. `state` follows `source-hierarchy-draft.md` §3.2: `VERIFIED` / `CONFLICTING` / `STALE` / `UNVERIFIED` /
   `SUPERSEDED`; `VERIFIED-WITH-CAVEAT` is used, non-standard, where a claim resolves cleanly but its sole
   citation is a lower-authority internal guide corroborated by a separate higher-tier channel (see CF-3).
3. **NB-2's own source catalog (131 sources) is a DIFFERENT namespace from the RulePack's `source_records`
   (30 curated entries)** — see CF-3.
4. `provenance` = the `query_id` in `response-log.jsonl`.

## Query execution summary

24 new live NB-2 queries (`e2a_queries.json`) + 3 reused B0-canary queries (`VO-NB2-003/004/005`, zero
re-query cost) = **27 of the 35-query slice cap** (8 headroom unused, logged per task instructions).
Of the 24 new queries: **21 returned `OK`, 3 hit the tool's 150s timeout** (`QueryTimeoutError`, durably
logged as `status=TIMEOUT` per `nb2_query.py`'s fail-loud contract, not silently dropped):
`E2A-D1-DOCTRINE`, `E2A-E31B-COMPARE`, `E2A-E31D-DOCTRINE` — all three were the widest "full doctrine
card" or 3-way comparison asks; every narrower/targeted query on the same product succeeded. This is
recorded honestly as a gap, not backfilled by inference from the successful narrower queries.

**Isolation gate** (re-verified this session, all 31 records — 24 new + 7 prior; the 31-record
isolation/citation-audit universe = 24 new E2a queries + 3 reused B0-canary queries + 4 earlier STEP-0/
transport-probe records from the same log file, which are not part of this task's 27-query budget
accounting but are still included in the full-log isolation/citation sweep for completeness): 31/31 distinct
`conversation_id_sent`, 0 equal the known-contaminated persistent id `3e8fe6db-...`, 0
`conversation_id_returned` mismatches. **Citation audit** (`nb2_citation_audit.py`, re-run this session
against the full 31-record log): **0 `NOT_COMPILABLE`**, 22 `VERIFIED`, 4 `PROSE_ONLY`, 3
`SKIPPED_TRANSPORT_ERROR` (the 3 timeouts, correctly skipped — no answer to audit), 2 `UNSUPPORTED`
(the 2 STEP-0 transport probes from QW-1, non-doctrine content, correctly flagged).

## Claims

### D1 — Tourism Multiple Entry

**CL-D1-01 — Purpose/scope.** D1 authorizes multiple tourism-purpose entries for recreation, personal
development, learning about tourist attractions (incl. yacht tourism), visiting friends/family, transit, or
MICE attendance.
- Source: NB-2 `0c7e2212-...` (**Kepmen M.IP-08.GR.01.01/2025 — Klasifikasi Visa**, `type: pdf`,
  primary/official) + `2d2ec0af-...` (`nb2_visa_types_final.txt`, internal guide, corroborating).
- **State: VERIFIED.** Products: D1. Provenance: `VO-NB2-003` (2026-08-15).
- Backs: `el.d1-multi-entry-support` (`PURPOSE_PRODUCT_MATCH`).

**CL-D1-02 — Requirement bundle (6-month passport, USD 2000 funds, CV, itinerary, support letter).**
Verified against the live `imigrasi.go.id/.../D1` OFFICIAL_PORTAL page in QW-5 (`ca5a2ce8-...`, record
#15, CURRENT, "page verbatim confirms all 6"); cross-referenced, not re-queried.
- **State: VERIFIED.** Products: D1. Provenance: QW-5 record #15.
- Backs: `el.d1-passport-validity`, `el.d1-funds-usd-2000`, `el.d1-cv-required`, `el.d1-itinerary-required`,
  `el.d1-support-letter`.
- Note: the pack's D1/D2/D12 el.* rules also co-cite `ee8fe5b8-...`, a general izin-tinggal-keimigrasian
  portal page flagged CHANGED in QW-5 record #4 (2026-08-16, the day before this task); QW-5's own records
  #15/#16/#17 backing this claim are unaffected (still CURRENT), but the co-citation is logged for whoever
  authors seq-9 so the CHANGED leg isn't silently carried forward (see Conflict Report CF-6).

**CL-D1-03 — Duration (per-entry, continuous, no annual cap in national law).** D1 stay per entry is
**60 continuous days**; visa validity tiers are **1, 2, or 5 years (up to 10 years for applicants with a
prior Indonesian stay record)**. National law states **no numeric annual/cumulative day-cap**; the only
constraint on frequent re-entry is an **operational (not legal) border-officer risk-discretion practice**
against frequent short-cycle border runs (3-4+ consecutive triggers suspicion), not a codified limit.
- Source: `E2A-D1-DURATION` (citations resolve `VERIFIED`, structured present) + `E2A-D1-BOUNDARY`
  (D1 vs C1 comparison, corroborating, same 60-day/validity-tier figures) + `E2A-D-CONT-CUM` (3-way
  cross-check, same figures).
- **State: VERIFIED.** Products: D1. Provenance: `E2A-D1-DURATION`, `E2A-D1-BOUNDARY`, `E2A-D-CONT-CUM`.
- Caveat: the "no annual cap" conclusion for D1/D12 rests on the NB-2 answers' silence on the topic rather
  than an explicit denial (unlike D2, where `E2A-D2-DURATION` explicitly states no such cap exists) —
  treated here as VERIFIED because it matches the primary-law text actually quoted (which contains no cap
  language for D1/D12 either), but flagged as a weaker evidentiary class than an explicit denial.
- **D1-DOCTRINE (full card) TIMED OUT** — the narrower queries above cover every fact the pack's D1 rules
  actually require; the full-card gap is a documentation-completeness loss, not a compilable-claim loss.

### D2 — Business Multiple Entry

**CL-D2-01 — Purpose/scope.** D2 authorizes multiple business-purpose entries: meetings/negotiations,
market research, visits to partners/suppliers, trade fairs, preliminary contract signing — absolute
prohibition on subordinate employment or local compensation.
- Source: NB-2 `0c22e859-...` (`visto_d2_d12_multiplo_guida_2025.txt`, `type: generated_text`, **internal
  guide — sole NB-2 citation for this specific claim**), corroborated by the independently-verified
  OFFICIAL_PORTAL page (`d3ad622e-...`, QW-5 record #16, CURRENT).
- **State: VERIFIED-WITH-CAVEAT** (see CF-3 — internal-guide-only NB-2 citation, upgraded to VERIFIED only
  via the separate QW-5 channel, never silently promoted on the internal guide's authority alone).
- Products: D2. Provenance: `VO-NB2-004` (2026-08-15) + QW-5 record #16.
- Backs: `el.d2-multi-entry-support` (`PURPOSE_PRODUCT_MATCH`),
  `hf.d2.indonesia-source-compensation` (`BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED`).
- The prohibition half of this claim was UNCOMPILED until seq-20 (2026-09-06): the only rule
  named above read `intent.purposes` and `intent.stay_days` and nothing else, so
  BUSINESS_MEETINGS + 60d + `work.indonesia_source_compensation = true` returned
  `SUPPORTED_CANDIDATES [D2]` with no review at all (measured on the signed seq-19 pack,
  `research/visa/2026-09-06-visa-oracle-decisiveness-investigation.md` §4 PR-1 edit 5).
  Compiled as EXCLUDE rather than REQUIRE_REVIEW per the owner ruling of 2026-09-06 (§5
  decision 2) — the ledger calls it an "absolute prohibition", and only an EXCLUDE lets the
  blanket `business_activity` review flag be retired later without a fail-open.

**CL-D2-02 — Requirement bundle.** Verified via QW-5 (`d3ad622e-...`, record #16, CURRENT, "verbatim
confirms all 6, identical structure to D1 page").
- **State: VERIFIED.** Products: D2. Provenance: QW-5 record #16.
- Backs: `el.d2-passport-validity`, `el.d2-funds-usd-2000`, `el.d2-cv-required`, `el.d2-itinerary-required`,
  `el.d2-support-letter`.
- Note: the pack's D1/D2/D12 el.* rules also co-cite `ee8fe5b8-...`, a general izin-tinggal-keimigrasian
  portal page flagged CHANGED in QW-5 record #4 (2026-08-16, the day before this task); QW-5's own records
  #15/#16/#17 backing this claim are unaffected (still CURRENT), but the co-citation is logged for whoever
  authors seq-9 so the CHANGED leg isn't silently carried forward (see Conflict Report CF-6).
- See also CL-D-FUNDS: the underlying Permenkumham 11/2024 Pasal 38(3) delegates the exact figure to the DG
  rather than hardcoding it in the statute itself; USD 2,000 is confirmed at the OFFICIAL_PORTAL operational
  layer (this claim's source), which is what an applicant actually faces.

**CL-D2-03 — Duration (60/entry, ≤2 extensions of 60d, 180d continuous ceiling per single stay,
NO annual/calendar-year cumulative cap).** `E2A-D2-DURATION` gives a **verbatim primary-law quote**:
Permenkumham No. 11/2024 (amending 22/2023), Pasal 95(3): *"Perpanjangan Izin Tinggal Kunjungan ...
diberikan untuk jangka waktu paling lama 60 (enam puluh) Hari setiap kali perpanjangan ... dengan
ketentuan keseluruhan Izin Tinggal di Wilayah Indonesia tidak lebih dari 180 (seratus delapan puluh)
Hari."* The answer explicitly states: *"La legge nazionale primaria non prevede alcun limite cumulativo di
180 giorni all'anno per i visti a ingressi multipli D2 se lo straniero effettua uscite e re-ingressi
(border run) [...]. La limitazione dei 180 giorni si applica esclusivamente alla durata del singolo
soggiorno continuativo in-country (60 giorni iniziali + 2 estensioni da 60 giorni)."* — i.e. the 180
figure is a **per-continuous-stay ceiling (60 base + up to 2×60 extensions), not an annual aggregate.**
- **CF-1, corrected (post-adversarial-review, kimi-k3) — ESCALATED, not hierarchy-resolved:** the SAME
  batch's `E2A-D12-VS-D2` comparison table, in a different cell with no verbatim citation, independently
  states *"Calendar-Year Cumulative Cap: Maximum 180 Days cumulatively in any single calendar year"* for D2
  — a DIFFERENT reading (annual aggregate vs per-stay ceiling) than `E2A-D2-DURATION`'s verbatim-quoted
  primary source. The earlier version of this note invoked "source-hierarchy §3.1.3... resolved on pinpoint
  strength" — that framing is retracted: §3.1.3 does not authorize a pinpoint-strength tiebreaker for
  same-tier disagreement; it says same-level source disagreement is never auto-resolved. On reflection this
  is not even a §3-governed cross-authority-level conflict — both answers are same-tier NB-2 outputs on the
  same underlying statute, not two different-authority SOURCES — so §3 does not mechanically resolve it
  either way. `E2A-D2-DURATION`'s verbatim article-and-paragraph pinpoint is treated as the operative
  doctrine here because it carries a checkable citation the dissenting cell lacks, but the disagreement
  itself is **escalated for human/E3a review, not closed**. Additionally: the two answers disagree not only
  on annual-vs-per-stay framing but also on the number of extensions (`E2A-D2-DURATION` implies 2×60-day
  extensions; `E2A-D12-VS-D2` states one 60-day extension only) — both total 180 days, logged not silently
  picked. See corrected Conflict Report CF-1.
- **State: VERIFIED-WITH-CAVEAT** (the 60/180-day primary-law pinpoint mechanics are solid and unchanged;
  the citation-disagreement resolution is now flagged escalated rather than closed, per CF-1's correction).
- Products: D2. Provenance: `E2A-D2-DURATION`, `E2A-D12-VS-D2` (dissenting cell).
- **No pack rule currently encodes this fact** (`intent.stay_days<=60` is the only D2 duration check in
  seq-7) — flagged for E4/E5 fact-vocabulary extension, not for this task to compile.

### D12 — Pre-Investment Multiple Entry

**CL-D12-01 — Purpose/scope.** D12 authorizes activities aimed at starting a business — field surveys
(*survei lapangan*) and/or feasibility studies (*studi kelayakan*) — exploratory pre-PT-PMA-incorporation
instrument. No subordinate work or local compensation.
- Source: NB-2 `0c7e2212-...` (Kepmen PDF, primary/official, exact index-table row quoted) + `0c22e859-...`
  (internal guide, corroborating).
- **State: VERIFIED.** Products: D12. Provenance: `VO-NB2-005` (2026-08-15).
- Backs: `el.d12-multi-entry-support` (`PURPOSE_PRODUCT_MATCH`).

**CL-D12-02 — Requirement bundle.** Verified via QW-5 (`5e64ec6b-...`, record #17, CURRENT).
- **State: VERIFIED.** Products: D12. Provenance: QW-5 record #17.
- Backs: `el.d12-passport-validity`, `el.d12-funds-usd-5000`, `el.d12-cv-required`,
  `el.d12-itinerary-required`, `el.d12-support-letter`.
- Note: the pack's D1/D2/D12 el.* rules also co-cite `ee8fe5b8-...`, a general izin-tinggal-keimigrasian
  portal page flagged CHANGED in QW-5 record #4 (2026-08-16, the day before this task); QW-5's own records
  #15/#16/#17 backing this claim are unaffected (still CURRENT), but the co-citation is logged for whoever
  authors seq-9 so the CHANGED leg isn't silently carried forward (see Conflict Report CF-6).

**CL-D12-03 — Duration (180/entry, extension mechanics, total-validity conflict RESOLVED).**
`E2A-D12-DURATION` gives a **verbatim primary-law quote of Pasal 95(4)**, Permenkumham No. 11/2024
(equivalent provision already present in the source 22/2023): *"Perpanjangan Izin Tinggal Kunjungan ...
dalam rangka prainvestasi diberikan dengan jangka waktu 180 (seratus delapan puluh) Hari setiap kali
perpanjangan ... dengan ketentuan keseluruhan Izin Tinggal di Wilayah Indonesia tidak lebih dari 12 (dua
belas) bulan."* — i.e. **180-day extension, total continuous stay per entry capped at 12 months (360
days).**
- **CF-2 RESOLVED, not merely deferred:** the blueprints' flagged `[bench]` conflict ("1/2-year vs
  1/2/5-year total validity") is resolved as a **category error, not a genuine numeric contradiction** —
  the answer separates two distinct concepts the earlier sources conflated: (a) **visa validity tier**
  (the window during which entries are permitted — 1/2/5 years, up to 10 with prior stay record, per
  Permenkumham 11/2024 Pasal 5C(4)-(5)) vs (b) **per-entry stay-plus-extension ceiling** (180 days base +
  extension, capped at 12 months/360 days total per single entry, Pasal 95(4)). Both figures are correct
  simultaneously because they answer different questions; the extension is confirmed **strictly per-entry**
  (`E2A-D12-DURATION`: "L'estensione del visto D12 è strettamente per-entry... non modifica né prolunga la
  validità del visto madre").
- **State: VERIFIED.** Products: D12. Provenance: `E2A-D12-DURATION`.
- **No pack rule currently encodes the 360-day per-entry ceiling** (only `intent.stay_days<=180` exists in
  seq-7's D12 eligibility gate, the pre-extension figure) — flagged for E4/E5, not compiled here.

**CL-D12-04 — Non-convertibility, extendability confirmed distinct.** D12 can be **extended onshore up to
12 months total per entry**, but **cannot be converted to an ITAS onshore** — conversion (*alih status*)
to E28A/E23-class stay permits requires exiting Indonesia and applying offshore.
- Source: `E2A-D12-CONVERSION` (structured citations present, resolves VERIFIED) + independently, QW-5
  record #17 OFFICIAL_PORTAL (`5e64ec6b-...`, CURRENT: "bisa diperpanjang ... namun tidak bisa dialihkan
  menjadi izin tinggal terbatas").
- **State: VERIFIED** (two independent channels agree). Products: D12. Provenance: `E2A-D12-CONVERSION`,
  QW-5 record #17.
- Backs: `hf.d12-onshore-conversion-excluded` (`D12_NOT_CONVERTIBLE`).

**CL-D12-05 — Site-visit boundary (D12 pre-investment vs unlawful operational inspection).** D12 covers
market research, land/site scouting, feasibility studies, legal/notarial consultation preliminary to
incorporation; it does NOT cover hands-on operational work, installation, audit/QC of an existing business,
or supervision — those exit the pre-investment scope entirely (per `E2A-D12-SITEVISIT`, corroborated by
`E2A-D12-VS-D2`'s comparison table, both citing `0c7e2212-.../0c22e859-...`).
- **State: VERIFIED.** Products: D12 (boundary rule, informs but does not directly back a named pack rule
  — no `activity.*`-scoped fact exists in seq-7 for D12 yet; flagged as an E4 fact-vocabulary candidate).
- Provenance: `E2A-D12-SITEVISIT`, `E2A-D12-VS-D2`.

### D1/D2/D12 cross-cutting

**CL-D-COMPARE — 3-way discriminator.** Confirms the per-entry/extension/funds figures above hold
consistently across a single 3-way comparison query (`E2A-D-3WAY-COMPARE`, citations resolve `VERIFIED`)
and the continuous-vs-cumulative cross-check (`E2A-D-CONT-CUM`, citations resolve `VERIFIED`): D1/D2 =
60 days continuous per entry, D12 = 180 days continuous per entry; no product has a numeric annual
aggregate cap in primary law (only D2's own duration answer explicitly denies one — see CL-D2-03/CF-1).
- **State: VERIFIED.** Products: D1, D2, D12. Provenance: `E2A-D-3WAY-COMPARE`, `E2A-D-CONT-CUM`.
- Caveat: the "no annual cap" conclusion for D1/D12 rests on the NB-2 answers' silence on the topic rather
  than an explicit denial (unlike D2, where `E2A-D2-DURATION` explicitly states no such cap exists) —
  treated here as VERIFIED because it matches the primary-law text actually quoted (which contains no cap
  language for D1/D12 either), but flagged as a weaker evidentiary class than an explicit denial.

**CL-D-FUNDS — Financial-proof minima.** D1 = USD 2,000 (3-month bank statement operational standard);
D2 = "sufficient living costs" without a hardcoded national figure (operationally treated as USD 2,000,
same tier as D1, per the same source family); D12 = USD 5,000 (confirmed independently in QW-5 record #17
and this query).
- **State: VERIFIED** for D1/D12 (numeric, primary-adjacent sourcing); **VERIFIED-WITH-CAVEAT** for D2 (no
  hardcoded national figure — the USD 2,000 D2 figure rests on the internal-guide/portal-page level, same
  caveat class as CL-D2-01).
- Products: D1, D2, D12. Provenance: `E2A-D-FUNDS`.
- This does not conflict with CL-D2-02's VERIFIED USD 2,000 figure — that claim rests on the
  OFFICIAL_PORTAL operational layer, which does hardcode the number even though the parent statute
  delegates it.

### E31B — Spouse of ITAS/ITAP Holder (fail-open refuter target)

**CL-E31B-STRUCT — Structural finding (verified live against the pack, independent of any NB-2 answer).**
Both `el.e31b-spouse-itas-support` and `el.e31b-sponsor-itas-itap` gate on
`{"fact":"family.sponsor_status_code","op":"known"}`. `known` is value-blind (any non-null value satisfies
it, including a sentinel like `"NONE"`) — re-derived independently this session against
`rulepack-prod-007.source.json`, matches `adjudication-report.md` finding #5. The frontend mitigation
(`mapFamilySponsorStatus()` never emits `KNOWN`) is a UI workaround, not a doctrine fix.
- **State: VERIFIED as a mechanical/structural finding.** Products: E31B.

**CL-E31B-01 — Doctrine card (partial — timed out on the full-card query, backed by narrower queries
instead).** E31B is a family-reunion visa for the foreign spouse of an ITAS/ITAP holder, defined by Kepmen
M.IP-08.GR.01.01/2025 as: *"Orang asing yang menggabungkan diri dengan suami atau istri pemegang Izin
Tinggal Terbatas atau Izin Tinggal Tetap."* Holder may reside for the duration aligned to the sponsor's
permit but is under absolute prohibition on local income-generating work (Pasal 122, UU 6/2011). Required
document verification includes an authenticated, sworn-translated marriage certificate (*Akta Nikah/Buku
Nikah*).
- Source: `E2A-E31B-REFUTER-SPONSOR-STATUS` (structured citations resolve `VERIFIED`) + `E2A-E31B-DOCTRINE`
  (OK, though the full card query started before the driver moved on — its answer IS in the log and DOES
  resolve VERIFIED per the audit; it is `E2A-E31B-COMPARE`, not `E2A-E31B-DOCTRINE`, that timed out).
- **State: VERIFIED.** Products: E31B. Provenance: `E2A-E31B-DOCTRINE`, `E2A-E31B-REFUTER-SPONSOR-STATUS`.

**CL-E31B-REFUTER — What "verified"/"known" sponsor status means per primary law — the P0 doctrine fix.**
Per **Permenkumham No. 22/2023 Pasal 44(2)(b)** (as amended by Permenkumham 11/2024), the sponsoring
spouse **must hold a currently-valid, non-expired ITAS or ITAP.** The **sole legal exception** (Pasal
44(3)) is where the sponsor's ITAS/ITAP is not yet issued but has been **replaced by an approved VITAS
(Visa Tinggal Terbatas)** for the spouse. Per **Pasal 119**, if the sponsor's status is unverifiable,
expired, absent, or "pending"/"in process", the officer issues an incompleteness notice and the applicant
has **2 working days** to cure it before **automatic, definitive rejection** (*permohonan ditolak*).
The answer states explicitly: *"Uno sponsor il cui ITAS/ITAP risulti scaduto, non verificato, non
registrato, assente o semplicemente dichiarato 'in corso di lavorazione' [...] non è mai sufficiente ad
attivare la pratica."* — i.e. **`family.sponsor_status_code` known-but-null-equivalent values are NEVER
sufficient; the compilable enum is `{ITAS_ACTIVE, ITAP_ACTIVE, VITAS_APPROVED}`, nothing else.**
- **State: VERIFIED** (verbatim primary-law pinpoint, Pasal 44(2)(b)/44(3)/119, Permenkumham 22/2023 jo.
  11/2024). Products: E31B. Provenance: `E2A-E31B-REFUTER-SPONSOR-STATUS`.
- **This is the compilable doctrine fix for seq-9**: narrow `el.e31b-spouse-itas-support` /
  `el.e31b-sponsor-itas-itap` from `{"op":"known"}` to `{"op":"in", "values":["ITAS_ACTIVE","ITAP_ACTIVE",
  "VITAS_APPROVED"]}` (exact fact-vocabulary naming is an E4 decision, not this task's).

**CL-E31B-PRINCIPAL — Principal-status eligibility.** Both categories of principal are eligible sponsors:
foreign workers holding E23/E25-family work permits AND investors holding E28/E28A/E28B/E28G — both
categories have an explicit, legally guaranteed right to bring spouse/minor unmarried children. The source
does not itself state the E31B rule differentiates by which principal category the sponsor falls under
(the ITAS/ITAP status check is category-agnostic).
- **State: VERIFIED-WITH-CAVEAT.** Products: E31B. Provenance: `E2A-E31B-PRINCIPAL-STATUS`.
- No verbatim primary-law pinpoint captured for this specific claim (E23/E25/E28-family principal
  eligibility) — the query_id provenance resolves against the frozen NB-2 snapshot (citation-audit
  VERIFIED) but the answer did not quote an article/paragraph the way the E31B/E31D REFUTER claims do.
  Treated as VERIFIED-WITH-CAVEAT, not full VERIFIED, until a pinpoint is captured.

### E31D — Stepchild of Foreigner in Mixed Marriage (fail-open refuter target)

**CL-E31D-STRUCT — Structural finding (verified live against the pack, independent of any NB-2 answer).**
All 3 `el.e31d-*` rules reduce, on inspection, to `intent.purposes intersects [FAMILY]` — the nested
`{"op":"all",...}` wrappers on `el.e31d-step-parent-relation`/`el.e31d-sponsor-mixed-marriage` add no
additional discriminating fact. None of the three checks `family.relation_to_sponsor`, a step-parent
fact, or the sponsor's marriage-registration status. Matches `adjudication-report.md` finding #5,
independently re-derived here.
- **State: VERIFIED as a mechanical/structural finding.** Products: E31D.

**CL-E31D-01 — Doctrine card (compiled from `E2A-E31D-COMPARE` + `E2A-E31D-REFUTER-PURPOSE-ONLY` +
`E2A-E31D-DOCS`; the full-card query `E2A-E31D-DOCTRINE` timed out).** E31D is reserved exclusively for
the foreign biological child of a foreign parent legally, registeredly married to an Indonesian citizen
(mixed marriage) — the child's step-parent is Indonesian. Per Kepmen 2025:
*"Menggabungkan diri bagi anak dari orang asing yang kawin secara sah dengan warga negara Indonesia."*
E31D holders are (uniquely among the E31 child-visa family, shared only with E31A) permitted informal/
independent/self-employed work — E31B/E31C/E31E/E31F/E31J strictly prohibit any work.
- **State: VERIFIED.** Products: E31D. Provenance: `E2A-E31D-COMPARE`, `E2A-E31D-REFUTER-PURPOSE-ONLY`.

**CL-E31D-REFUTER — Minimum discriminating fact vs any FAMILY-purpose visa — the P0 doctrine fix.**
Declaring general `FAMILY` purpose alone is **never sufficient**. Independent, certified, authenticated
proof is required of: (a) the specific child-to-foreign-parent relationship (birth certificate,
sworn-translated), (b) the foreign parent's legal, registered marriage to the Indonesian step-parent
(Buku Nikah/Akta Perkawinan if married in Indonesia; foreign certificate + Bukti Pelaporan if married
abroad), (c) the Indonesian step-parent's own identity/status as sponsor (Kartu Keluarga). Age/marital
eligibility: **under 18 and unmarried** (loses eligibility on turning 18 or marrying). Per Permenkumham
22/2023 Pasal 46(2), all three document classes are mandatory, verified/legalized/apostilled — under
**Permenkumham 29/2021 Pasal 183-184**, a mixed-marriage-based application (including E31D stepchild)
triggers a **mandatory on-site field check within 4 working days**.
- The answer states explicitly: *"There is no administrative mechanism where a simple unilateral
  declaration of intent or general family purpose bypasses these document-verification gates."*
- **State: VERIFIED** (verbatim primary-law pinpoints: Pasal 46(2) document list, Pasal 183-184 field
  check). Products: E31D. Provenance: `E2A-E31D-REFUTER-PURPOSE-ONLY`, `E2A-E31D-DOCS`.
- **This is the compilable doctrine fix for seq-9**: `el.e31d-step-parent-relation` needs a real
  `family.relation_to_sponsor == STEPCHILD`(-equivalent) check plus `family.stepparent_marriage_registered
  == true`; `el.e31d-sponsor-mixed-marriage` needs the sponsor's own identity/marriage-registration fact,
  not a repeated purpose-intersects check. Exact fact-vocabulary naming is E4's decision.

**CL-E31D-DOCS — Document list detail.** Confirms the four-document bundle above (birth certificate,
marriage proof [domestic or foreign+reporting], Kartu Keluarga, passport ≥6 months validity) with
sworn-translation/legalization requirement for non-English foreign documents.
- **State: VERIFIED.** Products: E31D. Provenance: `E2A-E31D-DOCS`.

## Query budget

27 of 35 used (24 live + 3 reused canary), 8 headroom unused, deferred nothing beyond the 3 documented
timeouts (partially covered by narrower successful queries, see above).

## Cross-referenced findings (not new claims, load-bearing for E5)

**CF-5 — E31B/E31D "index swap" claim, checked and REFUTED against the live system.** Two independent
answers this session (`E2A-E31D-REFUTER-PURPOSE-ONLY`, `E2A-E31D-DOCS`) both cite the SAME NB-2 internal
source (`nb2_visa_types_final.txt`, id `2d2ec0af-...`) claiming that an internal "Nuzantara dev /
visa_types table" mislabels E31D as "Spouse KITAS" and E31B as "Dependent KITAS (Child)" — the OPPOSITE
of the primary-law mapping (E31B=spouse, E31D=stepchild) both answers and this ledger otherwise confirm.
**Checked directly against the live production system this session, not taken on NB-2's authority**:
`apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py:1172,1200` (the canonical
114-code catalog) and `rulepack-prod-007.source.json`'s `products[].names` both show the CORRECT mapping
(E31B = "Family Visa Spouse of ITAS/ITAP Holder", E31D = "Family Visa Stepchild of Foreigner in Legal
Mixed Marriage"). **Disposition: REFUTED for the live system as of this session** — no index swap exists
in production. NB-2's own ingested `nb2_visa_types_final.txt` source evidently DOES contain a swap
somewhere (an artifact worth locating and correcting inside NB-2 itself, or a stale/external table that
was never our production catalog) — flagged for operator awareness, not treated as a live production bug.

## Adversarial review

Cross-family review run via `kimi -p "REFUTA questo documento" -m kimi-code/k3` (generator≠grader gate,
mandatory per this task's brief) against `e2a-claim-ledger.md`, `e2a-conflict-report.md`, and
`e2a-coverage-matrix.md` together. 15 findings raised (0 P0, 5 P1, 10 P2). Re-verified independently this
session before dispositioning (grep/`python3 -m json` against `rulepack-prod-007.source.json`,
`freshness-recheck-2026-08-16.md`, and `source-hierarchy-draft.md` where cited).

1. **[P1, CONFIRMED, cured]** `e2a-coverage-matrix.md`'s rule-count arithmetic was wrong: it stated 31
   rules/23-then-25-PRODUCTS via a "6+5+6+2+3+1=23, two more recounted below" line that didn't actually
   recount anything, while its own D2 table two lines later lists 6 `el.d2-*` rules, not 5. Corrected to
   30 total (6 GLOBAL + 24 PRODUCTS: D1×6, D2×6, D12×6+1 hard-filter, E31B×2, E31D×3), D2 section header
   fixed to "6 ELIGIBILITY rules".
2. **[P1, CONFIRMED, cured]** `e2a-coverage-matrix.md`'s CL-D2-03 line stated a "180-day annual cumulative
   cap" as the claim's substance — directly contradicting CF-1's own resolution (which says the opposite:
   a per-stay ceiling, not an annual cap). Reworded to state the correct per-stay-ceiling framing and to
   flag the now-escalated status.
3. **[P1, CONFIRMED, cured]** `e2a-conflict-report.md`'s CF-1 falsely invoked "source-hierarchy §3.1.3...
   resolved on pinpoint strength" — §3.1.3 authorizes no such tiebreaker; it mandates escalation for
   same-tier disagreement. Rewritten: the false hierarchy-citation is retracted, the disagreement is now
   marked escalated (not hierarchy-resolved), and a previously-unlogged discrepancy (2 extensions vs 1) is
   now recorded. Mirrored into CL-D2-03's own cross-reference paragraph in this file and into the
   conflict-report's closing Status section.
4. **[P1, CONFIRMED, cured]** `e2a-conflict-report.md`'s CF-3 overclaimed "every claim in the ledger states
   explicitly which of the two [namespaces] it rests on" — false for CL-D1-03, CL-D-COMPARE, CL-D-FUNDS,
   CL-E31B-PRINCIPAL, which cite only a query_id. Softened to "most claims... a handful... cite only a
   query_id provenance."
5. **[P1, CONFIRMED, cured]** The active pack's D1/D2/D12 `el.*` rules (18 rules) co-cite NB-2/pack source
   `ee8fe5b8-...`, flagged CHANGED in QW-5 record #4 (2026-08-16) — verified live via `grep`/`python3 -m
   json` against `rulepack-prod-007.source.json`'s `source_refs`. None of CL-D1-02/CL-D2-02/CL-D12-02
   mentioned this co-citation. Filed as new Conflict Report finding CF-6; matching one-line caveats added
   to all three claims above.
6. **[P2, CONFIRMED, cured]** CL-D2-02 (VERIFIED, D2 funds USD 2,000 via OFFICIAL_PORTAL) and CL-D-FUNDS
   (D2's underlying statute has no hardcoded figure) read as an apparent contradiction without the
   portal-vs-statute distinction spelled out. Cross-reference sentences added to both claims reconciling
   them (operational-layer hardcode vs statute-level delegation — not actually contradictory).
7. **[P2, CONFIRMED, cured]** CL-E31B-PRINCIPAL was marked VERIFIED with only a query_id, no article/
   paragraph pinpoint (unlike the E31B/E31D REFUTER claims, which do quote verbatim). Downgraded to
   VERIFIED-WITH-CAVEAT with an explanatory note.
8. **[P2, CONFIRMED, cured]** CL-D1-03 and CL-D-COMPARE's "no annual cap" conclusion for D1/D12 rests on
   the NB-2 answers' silence on the topic, not an explicit denial (unlike D2, where `E2A-D2-DURATION`
   explicitly denies a cap) — a weaker evidentiary class not previously flagged. Caveat sentences added to
   both claims; `state` left as VERIFIED (grounded in the quoted primary-law text's own silence on a cap,
   not pure absence-of-evidence).

The reviewer also raised several finer P2s reviewed and judged minor/stylistic — non-blocking: grading-
consistency nitpicks between CL-D12-05/CL-D2-01's evidentiary framing, CL-E31B-REFUTER's evidence class vs
CL-D2-03/CL-D12-03's, CL-D1-02's "all 6" wording, and CL-E31D-01 touching a source shared with the
CHANGED-flagged E31E portal page. These were reviewed and judged stylistic/non-blocking, not cured above.

Net: 8/15 raised findings were real defects and are cured above; the remaining ~7 were finer P2 stylistic
observations, reviewed and acknowledged but not requiring a text change.
