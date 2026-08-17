---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/nb2-answers/e2b-batch1-response-log.jsonl
    note: "raw NB-2 query records, batch 1 of item E2b — 42 records total: 34 OK, 8 TIMEOUT (7 unique query_ids + 1 retry)"
  - path: research/visa/doctrine-factory/query-bank/e2b-batch1-selection.json
    note: "40-query plan, query_id -> topic/category/target_products/provenance mapping used to group claims by product below"
  - path: research/visa/doctrine-factory/nb2-answers/e2b-batch1-citation-audit.json
    note: "mechanical citation-audit verdicts, pre-generated for this batch — 28 VERIFIED, 6 PROSE_ONLY, 8 SKIPPED_TRANSPORT_ERROR, 0 NOT_COMPILABLE"
  - path: research/visa/doctrine-factory/sources/nb2-source-snapshot-2026-08-15.json
    note: "frozen 131-source NB-2 id<->title map (hex source IDs), consulted for recurring source titles"
  - path: research/visa/doctrine-factory/sources/freshness-recheck-2026-08-16.md
    note: "QW-5 OFFICIAL_PORTAL verdicts — records #4 (ee8fe5b8, CHANGED) and #10 (ecd22722, CHANGED, sole source for two E31E HARD_FILTER rules) are directly load-bearing for this batch's E31E/E30A claims"
  - path: research/visa/doctrine-factory/claims/e2a-claim-ledger.md
    note: "frozen E2a template this file's format follows; also the source of CF-5 (E31B/E31D index-swap, REFUTED for production), cross-referenced below rather than re-litigated"
adversarial_review: kimi-k3
---

# E2b batch-1 atomic claim ledger — 34 fused-query NB-2 answers across 13 doctrine-card products + cross-cutting facts

Task: Visa Oracle doctrine-factory execution plan, item **E2b**, batch 1 of the 40-query slice
(`e2b-batch1-selection.json`). This ledger is raw material for an adversarial review step
(kimi-k3), not a finished PR-ready document — accuracy over polish, per the task brief's
generator≠grader instruction.

## Method

1. Every claim is one atomic legal/regulatory fact, backed by ≥1 NB-2 answer from this batch's
   34 `OK` records, cross-checked against that record's mechanical citation-audit verdict in
   `e2b-batch1-citation-audit.json`.
2. `state` follows `source-hierarchy-draft.md` §3.2: `VERIFIED` / `CONFLICTING` / `STALE` /
   `UNVERIFIED` / `SUPERSEDED`; `VERIFIED-WITH-CAVEAT` (non-standard, matching e2a's usage) is used
   where a claim resolves cleanly but rests on a lower-authority/thin citation, or where the answer's
   own audit verdict is `PROSE_ONLY` (no structured, independently resolvable citation — the answer's
   internal synthesis is not auto-verifiable the way a `VERIFIED`-audited answer's structured
   citations are).
3. Per the task's hard honesty constraint: a claim is downgraded to `UNVERIFIED` rather than upgraded
   to look complete whenever the source answer itself says the sources do not resolve the question,
   or whenever the only support is a single thin/PROSE_ONLY answer with no corroboration and no
   primary-law pinpoint. Thin/vague answers are called out as such, not smoothed over.
4. `provenance` = the `query_id` in `e2b-batch1-response-log.jsonl`. Where an answer's own inline
   footnote gives a simple integer NB-2 source ID (e.g. "ID: 14"), that is quoted alongside the
   document title — this batch's answers embed a per-answer integer ID scheme in their footnotes,
   distinct from the hex `sources_used` IDs in the JSONL header fields; both are legitimate NB-2
   citations, cited as they appear in the record actually read.
5. Six doctrine-card products (BRIDGING, E30B, E33E-doctrine-card, E31E-doctrine-card, E31J, E30)
   never returned an `OK` answer in this batch — their dedicated `VO-FUSED-T1-*` query timed out.
   Per task instruction, each is checked against every OTHER query in this batch for narrower
   backfill before being logged as a bare gap; the honest coverage state (TOTAL GAP / THIN BACKFILL /
   SUBSTANTIAL INDIRECT BACKFILL) is stated explicitly under each product heading, not inferred away.

## Query execution summary

40-query batch-1 plan (`e2b-batch1-selection.json`). Response log: **42 records — 34 `OK`, 8
`TIMEOUT`** (7 distinct query_ids timed out; `VO-FUSED-T1-003` timed out twice, as `VO-FUSED-T1-003`
and `VO-FUSED-T1-003-RETRY`, both logged honestly rather than the retry silently overwriting the
first failure). Citation audit (`e2b-batch1-citation-audit.json`, pre-generated, independently
re-tallied this session by parsing the JSON): **28 `VERIFIED`, 6 `PROSE_ONLY`, 8
`SKIPPED_TRANSPORT_ERROR`, 0 `NOT_COMPILABLE`** — the 8 `SKIPPED_TRANSPORT_ERROR` records are exactly
the 8 TIMEOUT response-log rows (correctly skipped, no answer to audit), confirming no silent record
loss between the two files.

The 6 `PROSE_ONLY` answers (`VO-FUSED-T1-038` E33G, `VO-FUSED-T1-013` E28A, `VO-FUSED-T1-010` E23,
`VO-FUSED-T4-004` E33, `VO-FUSED-T13-004` E33G/E23, `VO-FUSED-T14-003` E33/E33E) have no structured,
independently resolvable citation — their answers are readable, internally coherent, and cite sources
by name/date/passage in prose, but the mechanical audit cannot verify the pointer chain the way it
can for a `VERIFIED` answer. Every claim drawn from a `PROSE_ONLY` answer is marked
`VERIFIED-WITH-CAVEAT` below, never plain `VERIFIED`, unless corroborated by a separate `VERIFIED`
answer on the same fact.

## Claims

### BRIDGING — Izin Tinggal Peralihan (transitional stay permit)

**Coverage state: TOTAL GAP.** `VO-FUSED-T1-003` (the dedicated doctrine-card query) timed out twice
(`VO-FUSED-T1-003`, `VO-FUSED-T1-003-RETRY`). No other query in this batch's 34 `OK` answers targets
BRIDGING as a primary or secondary product — it does not appear in any `target_products` list besides
its own. `freshness-recheck-2026-08-16.md` records #2/#3 mention the general "Izin Tinggal
Peralihan" concept only tangentially, as a label on an OFFICIAL_PORTAL page being freshness-checked
for an unrelated product, with no doctrine content extracted. No backfill exists in this batch.

**CL-BRIDGING-GAP-01 — No claims can be authored for BRIDGING from this batch.**
- Source: none (both attempts timed out; no narrower query targets this product).
- **State: UNVERIFIED (gap, not a negative finding).** Products: BRIDGING. Provenance:
  `VO-FUSED-T1-003`, `VO-FUSED-T1-003-RETRY` (both `SKIPPED_TRANSPORT_ERROR`).
- Note: this is a genuine coverage hole for E5/the doctrine-card build, not a downgraded claim — say
  so honestly rather than inferring content from the product's name.

### E33G — Remote Worker KITAS

Backed by the dedicated doctrine card (`VO-FUSED-T1-038`, PROSE_ONLY) plus five remote-work queries
(T13-001/002/003/004/006), two threshold queries (T4-006, and T4-010 partially), one compensation
query (T6-005), and the cross-cutting T6-001 compensation-source test. This is the best-covered
product in the batch.

**CL-E33G-01 — Core eligibility test: foreign employer/client, no local payer, remote presence
permitted.** E33G permits a foreigner to reside and work physically in Indonesia provided the
employment/service relationship is formalized with an employer or client **not domiciled in
Indonesia** (`perusahaan yang tidak berkedudukan di Indonesia`); performing the work physically inside
Indonesia does NOT by itself make the compensation "Indonesian-sourced" — the decisive test is
payer/beneficiary location, not place of work.
- Source: `VO-FUSED-T1-038` (E33G doctrine card, PROSE_ONLY) corroborated by `VO-FUSED-T6-001`
  ("kitas_e33g_remote_work_guida_2025.txt", passaggi 380/382/384, ID: 111 — VERIFIED-audited) and
  `VO-FUSED-T13-001`/`VO-FUSED-T13-002` (remote-work eligibility, VERIFIED).
- **State: VERIFIED.** Products: E33G. Provenance: `VO-FUSED-T1-038`, `VO-FUSED-T6-001`,
  `VO-FUSED-T13-001`, `VO-FUSED-T13-002`.

**CL-E33G-02 — Income threshold: USD 60,000/year documented minimum.** E33G requires documented
proof of a minimum annual income of USD 60,000 (foreign employment contract, payslips, or
PayPal/bank statements).
- Source: `VO-FUSED-T6-001` ("kitas_e33g_remote_work_guida_2025.txt", passaggi 382/383/386, ID: 111,
  VERIFIED-audited) corroborated by `VO-FUSED-T4-006` (dedicated E33G threshold query, VERIFIED).
- **State: VERIFIED.** Products: E33G. Provenance: `VO-FUSED-T6-001`, `VO-FUSED-T4-006`.

**CL-E33G-03 — Work prohibition scope: any local-sourced compensation, monetary or in-kind, voids
eligibility.** Local compensation is defined broadly (`imbalan, upah, atau sejenisnya` — "compensation,
salary, or the like"), catching barter/in-kind exchange as well as cash; payment channel or currency
(foreign bank account, PayPal, crypto) is legally irrelevant if the payer/beneficiary is an Indonesian
entity. Violation is a criminal offense under UU 6/2011 Art. 122(a) (up to 5 years + Rp 500,000,000
fine); the facilitating Indonesian sponsor is exposed to the SAME penalty under Art. 122(b).
- Source: `VO-FUSED-T6-001` ("C5A Local-Work Prohibition — Legal Sources 2026-06-01", ID: 14,
  passaggi 134/137/138/142-144/149/150/152/154, VERIFIED-audited).
- **State: VERIFIED.** Products: E33G (this compensation-source test is cross-cutting — see also
  Cross-cutting section below for its application to visit/D-series visas and C5A).

**CL-E33G-04 — Remote-work classification questions (nationality-neutral, activity-type dependent).**
The T13 remote-work batch (`VO-FUSED-T13-001/002/003/004/006`) resolves several operational edges:
digital-nomad-style short remote stints under visit visas remain prohibited if any local payer exists
(same test as CL-E33G-03); E33G is compatible with owning/managing a foreign-registered company
remotely but not with drawing a local Indonesian salary; family riders are addressed under E33/E33E,
not E33G specifically (cross-reference Family section below).
- Source: `VO-FUSED-T13-001`, `VO-FUSED-T13-002`, `VO-FUSED-T13-003` (VERIFIED); `VO-FUSED-T13-004`
  (PROSE_ONLY, E33G/E23 boundary — thinner, treat as corroborating rather than sole support).
- **State: VERIFIED-WITH-CAVEAT.** Products: E33G. Provenance: `VO-FUSED-T13-001..006`. Caveat: the
  E23-boundary edge in T13-004 (when does remote consulting for a foreign client tip into needing an
  E23/RPTKA because the "client" is functionally a local employer) is PROSE_ONLY and thinner than the
  other four T13 answers — do not treat that specific boundary line as firmly resolved.

### E33 — Retirement / Second Home family (general doctrine card + E33A/E33E/E33F sub-facts)

Backed by the general E33 doctrine card (`VO-FUSED-T1-032`, VERIFIED) plus the T14
retirement-second-home batch (5 queries) and T4 threshold queries (T4-004 PROSE_ONLY, T4-010
VERIFIED).

**CL-E33-01 — E33 family structure and index split.** E33 is a family of retirement/second-home/
passive-income KITAS indices (E33, E33A, E33E "Silver Hair", E33F pension, E33G remote-work), each
with distinct eligibility gates (age, deposit, pension-proof, foreign-employer-proof respectively);
none authorize local paid employment.
- Source: `VO-FUSED-T1-032` (E33 doctrine card, VERIFIED, "every extracted prose pointer resolves").
- **State: VERIFIED.** Products: E33 (family), E33A, E33E, E33F, E33G. Provenance: `VO-FUSED-T1-032`.

**CL-E33-02 — CONFLICT: E33E minimum age 55 (legal text) vs 60 (repeated operational claim).** See
Conflict Report **CF-7** below — this is a real, well-corroborated numeric disagreement appearing
independently across `VO-FUSED-T1-032`, `VO-FUSED-T1-037`, `VO-FUSED-T4-004`, `VO-FUSED-T10-009`,
`VO-FUSED-T14-002`, `VO-FUSED-T14-004`.
- **State: CONFLICTING.** Products: E33, E33E. Provenance: see CF-7.

**CL-E33-03 — CONFLICT: E33/E33E to KITAP conversion — 3 years (Permenkumham 11/2024) vs 5 years
(operational guide).** See Conflict Report **CF-8**.
- Source: `VO-FUSED-T14-004` (self-flagged explicitly), corroborated (3-year figure) by
  `VO-FUSED-T1-032`, `VO-FUSED-T1-037`.
- **State: CONFLICTING.** Products: E33, E33E. Provenance: `VO-FUSED-T14-004`, `VO-FUSED-T1-032`,
  `VO-FUSED-T1-037`.

**CL-E33-04 — Deposit requirement: USD 50,000 minimum in a state-owned bank (E33E).** E33E ("Silver
Hair") requires a minimum blocked deposit of USD 50,000 in an Indonesian state-owned bank, plus proof
of monthly income/pension of at least USD 3,000.
- Source: `VO-FUSED-T4-009` (PNBP/threshold cross-reference table, "deposito vincolato di USD 50.000
  in banca statale per KITAS Silver Hair (E33E)", passaggi 76/77, VERIFIED-audited) corroborated by
  `VO-FUSED-T4-004`, `VO-FUSED-T10-009`, `VO-FUSED-T14-002`.
- **State: VERIFIED.** Products: E33E. Provenance: `VO-FUSED-T4-009`, `VO-FUSED-T4-004`,
  `VO-FUSED-T10-009`, `VO-FUSED-T14-002`.

**CL-E33-05 — Work prohibition and family riders.** E33/E33E/E33F holders may not hold local paid
employment; spouse/dependent-child riders are available under the family-code products (E31 family
line), addressed with an explicit age-≤18 rule for children in `VO-FUSED-T13-003`/`VO-FUSED-T14-005`
(cross-reference E31 section below).
- Source: `VO-FUSED-T14-005`, `VO-FUSED-T14-006` (VERIFIED).
- **State: VERIFIED.** Products: E33, E33E. Provenance: `VO-FUSED-T14-005`, `VO-FUSED-T14-006`.

### E30B — Higher-Education Student KITAS

**Coverage state: THIN BACKFILL.** `VO-FUSED-T1-020` (dedicated doctrine card) timed out. No other
query in this batch targets E30B directly; the only touches are indirect — `VO-FUSED-T1-019`'s
sibling-mismatch comparison table (E30A doctrine card, comparing E30A vs E30B labels) and
`VO-FUSED-T12-001`/`VO-FUSED-T12-005`'s general E30-family duration figures (1/2/4 years, discussed
under E30 below). Neither answer treats E30B's own eligibility gate (higher-education enrollment
proof, institution accreditation) as its primary subject.

**CL-E30B-01 — Sibling mismatch: Kepmen label vs operational database label.** Per the Kepmen
M.IP-08.GR.01.01/2025 classification, E30A = Basic/Secondary Education, E30B = Higher Education; the
operational DJI portal database instead labels E30A as "Student KITAS (Research)" and E30B as
"Student KITAS (Training)" — a naming mismatch flagged explicitly in `VO-FUSED-T1-019` as a "Sibling
Mismatch" between the primary-law index and the operational label a client actually sees on the
portal.
- Source: `VO-FUSED-T1-019` (E30A doctrine card, VERIFIED, self-flagged sibling-mismatch section).
- **State: VERIFIED-WITH-CAVEAT.** Products: E30A, E30B. Provenance: `VO-FUSED-T1-019`. Caveat: this
  claim describes the LABEL mismatch, not E30B's substantive eligibility requirements, which this
  batch never resolves — do not read this claim as a full E30B doctrine card.
- Note: E30B's general validity-tier figures (1/2/4 years) are shared with E30/E30A per
  `VO-FUSED-T12-005` — see E30 section below; this is the only other backfill for E30B in this batch.

### E33E — see E33 section above

E33E has no dedicated doctrine card in this batch (`VO-FUSED-T1-036` timed out), but is the
best-backfilled of the 6 timed-out products — see CL-E33-02 through CL-E33-05 and Conflict Report
CF-7/CF-8 above, all sourced from `VO-FUSED-T4-004`, `VO-FUSED-T4-010`, `VO-FUSED-T10-009`,
`VO-FUSED-T14-002` through `T14-006`. Coverage state: **SUBSTANTIAL INDIRECT BACKFILL** — deposit
amount, income floor, work prohibition, and KITAP-conversion path are all covered; only the dedicated
card's framing/narrative (permitted-activity list phrased for E33E specifically, rather than
extracted from cross-references) is missing.

### E31A — Family visa, spouse of Indonesian citizen

**CL-E31A-01 — Eligibility gate: marriage to an Indonesian citizen, registered.** E31A is granted to a
foreign spouse of an Indonesian citizen (WNI), conditioned on a legally registered marriage
(Kantor Urusan Agama / Catatan Sipil certificate) and sponsor status of the Indonesian spouse.
- Source: `VO-FUSED-T1-023` (E31A doctrine card, VERIFIED, "every extracted prose pointer resolves").
- **State: VERIFIED.** Products: E31A. Provenance: `VO-FUSED-T1-023`.

**CL-E31A-02 — Work rights differ from other family-line indices.** E31A (spouse of a WNI, mixed
marriage) is treated distinctly in NB-2's answers from E31B (spouse of an ITAS/ITAP-holder foreigner)
— the mixed-marriage E31A line carries broader local work-authorization language than the
foreigner-sponsored E31B/E31D family line, per the doctrine card's own comparison table.
- Source: `VO-FUSED-T1-023` (VERIFIED).
- **State: VERIFIED-WITH-CAVEAT.** Products: E31A. Provenance: `VO-FUSED-T1-023`. Caveat: this batch
  does not independently cross-check E31A's work-rights claim against a primary-law pinpoint the way
  e2a's E31B/E31D claims did — treat the differential as reported, not re-verified against
  Permenkumham text in this pass.

### E31E — Family visa, child of ITAS/ITAP holder (per Kepmen mapping)

**Coverage state: PARTIAL BACKFILL, with a load-bearing freshness warning.** `VO-FUSED-T1-027`
(dedicated doctrine card) timed out. Backfill comes from `VO-FUSED-T13-003` and `VO-FUSED-T14-005`
(family-code assignment discussions), which establish the age-≤18 rule and the E31B/E31E-vs-E31D
code question (see CF-9 below), but neither answer is a dedicated E31E permitted/prohibited-activity
or entry-type card.

**CL-E31E-01 — Age-≤18 rule for child dependents.** The E31-family child-dependent index requires the
child to be under 18 years of age at time of application; this batch's answers do not resolve the
exact index letter (E31B vs E31E) with full confidence — see CF-9.
- Source: `VO-FUSED-T13-003`, `VO-FUSED-T14-005` (both VERIFIED-audited).
- **State: VERIFIED-WITH-CAVEAT.** Products: E31E (as targeted by the query bank), E31B (per Kepmen
  mapping — see CF-9). Provenance: `VO-FUSED-T13-003`, `VO-FUSED-T14-005`.
- **Caveat — CRITICAL, carry forward:** `freshness-recheck-2026-08-16.md` record #10 (`ecd22722-
  3e42-5808-be18-45fbb7d8e9c5`, the E31E OFFICIAL_PORTAL page) is flagged **CHANGED** and is the SOLE
  `source_ref` for two live HARD_FILTER rules (`hf.e31e-adult-excluded`, `hf.e31e-married-excluded`) —
  the freshness-recheck found the live page contains NO text supporting either the under-18 or
  unmarried requirement it is cited for. Any claim in this ledger touching E31E age/marital-status
  eligibility inherits this CHANGED-source risk; it is NOT independently re-verified here, only
  flagged forward per the task's freshness-recheck discipline (matching e2a's CF-6 pattern).

### E30A — Basic/Secondary Education Student KITAS

**CL-E30A-01 — Eligibility: enrollment at an accredited basic/secondary institution, sponsor =
school.** E30A requires proof of enrollment (school acceptance letter) at an accredited Indonesian
basic/secondary institution, sponsored by the school itself, not a guardian-only relationship.
- Source: `VO-FUSED-T1-019` (E30A doctrine card, VERIFIED).
- **State: VERIFIED.** Products: E30A. Provenance: `VO-FUSED-T1-019`.

**CL-E30A-02 — Minor-without-guardian review requirement, sourced from a CURRENT-WITH-EXCEPTION
page.** `freshness-recheck-2026-08-16.md` record #18 (`38242587-f4da-5c31-b0ea-662f7fdc475c`, the E30A
OFFICIAL_PORTAL page) is graded CURRENT WITH EXCEPTION: it verbatim-supports the passport/funds facts
but is the SOLE, unsupported source for `review.minor-without-guardian` — the live page text does not
actually carry that specific sub-rule.
- Source: `freshness-recheck-2026-08-16.md` record #18 (cross-referenced, not re-queried this batch).
- **State: VERIFIED-WITH-CAVEAT.** Products: E30A. Provenance: freshness-recheck record #18. Caveat:
  same class of finding as e2a's CF-6 (co-citation drift) — flagged forward here for whoever authors
  the E30A doctrine card, not independently re-checked in this pass.

**CL-E30A-03 — Sibling mismatch with E30B.** See CL-E30B-01 above (same finding, both products).

### E28A — Investor KITAS

**CL-E28A-01 — Eligibility: PT PMA shareholding ≥ Rp 10 miliar, RPTKA/DKP-TKA exempt.** E28A holders
are foreign shareholders of a PT PMA with a verified equity stake of at least Rp 10,000,000,000; as
investors (not employees) they are exempt from RPTKA and DKP-TKA obligations.
- Source: `VO-FUSED-T1-013` (E28A doctrine card, **PROSE_ONLY** — no structured citation) corroborated
  by `VO-FUSED-T4-009` ("Verifica dell'atto costitutivo... prova di una quota azionaria di almeno 10
  miliardi di IDR", VERIFIED-audited) and `VO-FUSED-T6-001` (dividend/profit compensation taxonomy,
  VERIFIED-audited).
- **State: VERIFIED.** Products: E28A. Provenance: `VO-FUSED-T1-013`, `VO-FUSED-T4-009`,
  `VO-FUSED-T6-001`. (Upgraded from VERIFIED-WITH-CAVEAT because two independently VERIFIED-audited
  answers corroborate the PROSE_ONLY doctrine card on this specific figure.)

**CL-E28A-02 — CONFLICT: KITAP conversion timing — 3 years (PP 31/2013, primary law) vs "5+ years"
(commercial guide figure).** Self-flagged explicitly within `VO-FUSED-T1-013` itself as an internal
inconsistency between the primary-law figure and an erroneous commercial-guide claim. See Conflict
Report **CF-10**.
- **State: CONFLICTING.** Products: E28A. Provenance: `VO-FUSED-T1-013`.

### E33F — Pension KITAS

**CL-E33F-01 — Eligibility: documented foreign pension income, no local employment.** E33F requires
documented proof of a foreign-sourced pension (pension-fund statement or equivalent), and — like the
rest of the E33 family — prohibits local paid employment.
- Source: `VO-FUSED-T1-037` (E33F doctrine card, VERIFIED).
- **State: VERIFIED.** Products: E33F. Provenance: `VO-FUSED-T1-037`.

**CL-E33F-02 — Age/income figures shared with E33E discussion; same 55-vs-60 conflict surface
touched.** `VO-FUSED-T1-037` repeats the same 55/60 age-figure tension noted for E33E (CF-7) in its
own comparison table against E33E — corroborating that the conflict is not a one-off typo in a single
answer but recurs across the product family's own internal cross-references.
- Source: `VO-FUSED-T1-037` (VERIFIED).
- **State: CONFLICTING** (same underlying disagreement as CF-7 — not a separate CF number). Products:
  E33F, E33E. Provenance: `VO-FUSED-T1-037`.

### E31J — no product code found; flagged, not a doctrine-card gap

**Coverage state: TOTAL GAP, and the query itself may target a non-existent/renamed index.**
`VO-FUSED-T1-031` (dedicated doctrine card query) timed out, and — separately from the timeout — no
other answer in this batch's 34 `OK` records mentions an "E31J" index anywhere, including the T13/T14
family-line discussions that otherwise enumerate E31A/E31B/E31D/E31E extensively. This is worth
flagging distinctly from BRIDGING's gap: BRIDGING is a real product with zero backfill; E31J's absence
from every OTHER answer's family-line enumeration (which does cover E31A/B/D/E) raises the honest
possibility that E31J is a query-bank naming artifact rather than a live Kepmen index — this ledger
does not resolve which, and says so rather than guessing.

**CL-E31J-GAP-01 — No claims can be authored for E31J from this batch; index existence itself
unconfirmed by this batch's sources.**
- Source: none (timeout; zero incidental mentions across 34 other answers, including family-line
  enumerations that do cover E31A/B/D/E).
- **State: UNVERIFIED (gap; flag index-name uncertainty for E1/E5, do not silently assume it means
  E31D or another sibling).** Products: E31J. Provenance: `VO-FUSED-T1-031` (`SKIPPED_TRANSPORT_ERROR`).

### E30 — Study visa family (general)

**Coverage state: REASONABLE INDIRECT BACKFILL** via `VO-FUSED-T12-001` (Izin Belajar
authority-gap finding) and `VO-FUSED-T12-005` (C1/B1 vs C9 vs E30 boundary + duration figures), even
though `VO-FUSED-T1-018` (dedicated doctrine card) timed out.

**CL-E30-01 — Validity tiers: 1/2/4 years (mapped to E30/E30A/E30B, with E30B running longer for
multi-year higher-ed programs).** The E30 family carries validity tiers distinct from the
short-course C9 visit-visa alternative discussed at CL-cross-C9 below.
- Source: `VO-FUSED-T12-005` (C1/B1 vs C9 vs E30 boundary query, VERIFIED).
- **State: VERIFIED.** Products: E30, E30A, E30B. Provenance: `VO-FUSED-T12-005`.

**CL-E30-02 — Izin Belajar authority gap: NB-2 does not resolve which ministry currently issues the
student learning-permit endorsement post-Kemenimipas split.** `VO-FUSED-T12-001` explicitly states
that the sources do not contain a definitive, current answer for which body (Kemenimipas vs
Kemendikbud vs the school itself) issues the Izin Belajar endorsement required alongside an E30-family
KITAS, following the late-2024 Kemenimipas/Kemenkumham split — flagged by the answer itself as a
missing-information gap, not resolved by inference.
- Source: `VO-FUSED-T12-001` (VERIFIED-audited; the citation-audit verdict describes citation
  *structure*, not completeness of the underlying answer — this claim IS the honest "sources do not
  allow a conclusion" case the task instructions ask to preserve, not paper over).
- **State: UNVERIFIED (explicit sources-gap, self-flagged by the answer).** Products: E30. Provenance:
  `VO-FUSED-T12-001`.

### E23 — Working KITAS

**CL-E23-01 — Core mechanism: RPTKA-approved, DKP-TKA paid in full up front, KBLI-matched sponsor.**
E23 requires an approved RPTKA matching the sponsor company's KBLI code, full up-front payment of
DKP-TKA (USD 100/month/position, entire contract term), and mandatory TKI Pendamping counterpart
(1:1 for operational roles, 1:N for managerial roles) for technology-transfer compliance.
- Source: `VO-FUSED-T1-010` (E23 doctrine card, **PROSE_ONLY**) corroborated by `VO-FUSED-T4-009`
  (DKP-TKA figure and payment rule, VERIFIED-audited: "USD 100 al mese per posizione... deve essere
  pagata interamente in anticipo") and `VO-FUSED-T3-010` (TKI Pendamping 1:1/1:N ratio,
  "izin_kerja_tka_procedura_completa_2025.txt", passaggi 253/531-533/555, VERIFIED-audited).
- **State: VERIFIED.** Products: E23. Provenance: `VO-FUSED-T1-010`, `VO-FUSED-T4-009`,
  `VO-FUSED-T3-010`. (Upgraded from VERIFIED-WITH-CAVEAT — the PROSE_ONLY doctrine card's core figures
  are independently corroborated by two separately VERIFIED-audited answers.)

**CL-E23-02 — Operating restriction on visitors: absolute prohibition on machinery
operation/repair/install under B1/C2, narrow C15/C20 exceptions.** Only E23+RPTKA holders (with
mandatory TKI Pendamping) may legally operate machinery; C20/C19 carry narrow install/repair
exceptions, C15 a narrow emergency exception; B1/C2 visitors are absolutely prohibited from any
hands-on machinery operation, repair, or installation.
- Source: `VO-FUSED-T3-006` (installation/repair/maintenance classification, VERIFIED-audited).
- **State: VERIFIED.** Products: E23, C15, C16, C17, C18, C19, C20, D17, B1, C2. Provenance:
  `VO-FUSED-T3-006`.

### Cross-cutting (ALL products)

**CL-CROSS-01 — Compensation-source legal test: payer/beneficiary location decisive; place-of-work
alone insufficient; payment channel/currency irrelevant.** Full three-part test from `VO-FUSED-T6-001`
(the batch's dedicated cross-cutting compensation-source query, VERIFIED-audited):
(A) **Payer & Beneficiary Test — DECISIVE**: if the entity benefiting from the activity or paying the
compensation (cash or in-kind) is an Indonesian individual/PT/PT PMA/CV/local branch, the source is
legally Indonesian.
(B) **Place-of-Work Test — NOT decisive alone**: physically performing work in Indonesia (e.g. remote
work from a Bali laptop) does not by itself make compensation Indonesian-sourced — this is the entire
legal basis for E33G's design.
(C) **Payment-Channel Test — legally irrelevant**: currency, bank location, or payment method (wire,
PayPal, crypto, barter) does not change the legal characterization.
- Source: `VO-FUSED-T6-001` ("C5A Local-Work Prohibition — Legal Sources 2026-06-01", ID: 14,
  passaggi 134/138/141/150/154; "kitas_e33g_remote_work_guida_2025.txt", ID: 111, passaggi 380/382/384).
- **State: VERIFIED.** Products: ALL (governs E33G, D-series, visit visas, C5A, E23 boundary alike).
  Provenance: `VO-FUSED-T6-001`, corroborated by `VO-FUSED-T3-010` (barter/promotional-activity
  discussion, same legal test applied to training/coaching), `VO-FUSED-T6-005` (E33G/D1 compensation
  edge cases).

**CL-CROSS-02 — Compensation taxonomy table (stipendio/fee/reimbursement/per-diem/profit-dividend/
in-kind).** Six-row taxonomy from `VO-FUSED-T6-001`: **Stipendio/Salario** — prohibited on all
visit/passive visas, exclusive to E23; **Onorario/Fee** — prohibited if paid by an Indonesian client
without E23, permitted from foreign clients under E33G; **Reimbursement/Per-diem** — permitted under
C22 (no salary, expense reimbursement only) and C2/D2 (foreign-HQ-paid per-diem for on-site business
trips); **Profitto/Dividendo** — permitted for E28A/E28B/E28C investors and as foreign-sourced income
for E33E/E33F passive-visa holders; **In-kind/Barter** — categorically prohibited on tourist/visit
visas including C5A, treated as `imbalan dalam bentuk lain` under UU 13/2003 Art. 1(3)-(4) and PP
34/2021 Art. 1(2).
- Source: `VO-FUSED-T6-001` (VERIFIED-audited).
- **State: VERIFIED.** Products: ALL. Provenance: `VO-FUSED-T6-001`.

**CL-CROSS-03 — PNBP fee schedule (PP 45/2024), by product family, current as of this batch's
sources.** Full schedule extracted from `VO-FUSED-T4-009` (VERIFIED-audited, "Lampiran III.B/C" table):
- **Visit visas (single entry)**: 7 days Rp 250,000 / 14 days Rp 350,000 / 30 days Rp 500,000 / 60 days
  Rp 1,000,000 / 90 days Rp 1,500,000 / 180 days Rp 2,000,000 (Lampiran III.B.1.a-f).
- **D-series (multiple entry)**: base fee by total validity — ≤60d Rp 1,500,000 / ≤90d Rp 2,000,000 /
  ≤180d Rp 2,500,000 / ≤1y Rp 3,000,000 / ≤2y Rp 5,000,000 / ≤5y Rp 10,000,000 / ≤10y Rp 15,000,000
  (Lampiran III.B.2.a-g) **plus** a verification fee: Category I Rp 1,000,000 for D2 (Permenkumham
  11/2024 Pasal 26(3)), Category II Rp 2,000,000 for D12 (Pasal 26(4)), Rp 0 exemption for D1
  (Pasal 26(5)).
- **KITAS (ITAS)**: ≤30d Rp 500,000 / ≤60d Rp 1,000,000 / ≤90d Rp 1,500,000 / ≤6mo Rp 2,000,000 / ≤1y
  Rp 3,000,000 / ≤2y Rp 5,000,000 / ≤5y Rp 7,000,000 / ≤10y Rp 12,000,000 (Lampiran III.C.2.a-h).
  VITAS Rp 500,000 (Lampiran III.B.3); consular VITAS fee operationally USD 150.
- **KITAP (ITAP)**: ≤5y Rp 7,000,000 / ≤10y Rp 12,000,000 / indefinite Rp 15,000,000 (Lampiran
  III.C.3.a-c).
- **DKP-TKA**: USD 100/month/position, paid in full up front for the contract term; PT PMA
  investor-shareholders (E28A/E28B) are exempt (no RPTKA).
- **Bali Tourist Levy**: Rp 150,000 per foreign visitor on arrival (Perda Bali 2/2025), KITAS/KITAP
  holders theoretically exemptable via the Love Bali portal.
- **State: VERIFIED.** Products: ALL. Provenance: `VO-FUSED-T4-009`.
- Note: this fee table is DIFFERENT from the RulePack's `source_records`/PricingTool figures — per
  Bali Zero's "REGOLA PREZZI ASSOLUTA" internal directive (cited within the same answer, ID range
  30-32), clients are quoted a single all-inclusive PricingTool figure, never the raw PNBP breakdown.
  This claim documents the PNBP-only regulatory schedule for doctrine purposes, not a client quote.

**CL-CROSS-04 — CONFLICT: MERP fee schedule vs automatic-integration rule.** `VO-FUSED-T4-009`
self-flags a direct conflict between PP 45/2024 (which prices a standalone MERP fee, e.g. Rp
1,500,000/year) and UU 63/2024 (which states MERP is automatically integrated into every KITAS/KITAP
at issuance, no separate procedure or fee). See Conflict Report **CF-11**.
- **State: CONFLICTING.** Products: ALL (KITAS/KITAP). Provenance: `VO-FUSED-T4-009`.

**CL-CROSS-05 — Sponsor rules (T7-001): One Sponsor Policy and Penjamin liability.** Under SE No.
3/836/PK.04/I/2026 (Jan 2026, "One Sponsor Policy"), an RPTKA/ITK sponsor match is required — the
company named on the RPTKA must be the same entity sponsoring the ITAS application, closing a
previously-exploitable mismatch. Separately, Permenimipas No. 5/2025 (repealing Permenkumham 36/2021)
redefines Penjamin (guarantor) obligations: the sponsor is jointly liable for the foreigner's conduct,
including facilitation liability under UU 6/2011 Art. 122(b) for barter/promotional-activity abuse
(cross-references CL-CROSS-01/02 above).
- Source: `VO-FUSED-T7-001` (VERIFIED-audited).
- **State: VERIFIED.** Products: ALL. Provenance: `VO-FUSED-T7-001`.

**CL-CROSS-06 — Nationality-based rules (T9-001): sources incomplete on country-specific lists.** The
answer to `VO-FUSED-T9-001` explicitly states that NB-2's sources do not contain a complete, current
list of visa-exempt or VOA-eligible nationalities — it can confirm the EXISTENCE of nationality-tiered
treatment (VOA-eligible list vs full-application-required list) but not enumerate the current roster
with confidence, and says so rather than guessing a list.
- Source: `VO-FUSED-T9-001` (VERIFIED-audited; again, citation *structure* verified, not completeness
  of the underlying content — this is a genuine sources-gap, honestly reported by the answer itself).
- **State: UNVERIFIED (explicit sources-gap on the country-list specifics; the existence of
  nationality-tiering itself is VERIFIED).** Products: ALL (visit-visa family especially). Provenance:
  `VO-FUSED-T9-001`.

**CL-CROSS-07 — Enforcement posture (T15-001): Dharma Dewata task force + substance-over-form
standard.** Active since April 2026 in Bali (Canggu, Ubud, Kuta), the Dharma Dewata Immigration
Patrol Task Force conducts physical inspection + social-media monitoring. Ditjen Imigrasi's own
23-May-2026 public statement establishes a substance-over-form enforcement standard: "what is
evaluated is not only whether a person is paid, but also the purpose of arrival, the form of the
activity, and its economic impact" — meaning unpaid/barter activity with economic substance is treated
the same as paid work for enforcement purposes.
- Source: `VO-FUSED-T15-001` (VERIFIED-audited).
- **State: VERIFIED.** Products: ALL. Provenance: `VO-FUSED-T15-001`.

**CL-CROSS-08 — Family/minors general rules (T10-009): family-code assignment and minor-specific
gates.** Establishes the general family-code framework (spouse/child dependent riders attach to a
principal's E28/E31/E33 index), the age-≤18 gate for child dependents (see CL-E31E-01), and flags that
minor-specific document requirements (birth certificate legalization, guardian consent) are handled
inconsistently across the product-specific pages this batch touched (cross-reference CL-E30A-02's
minor-without-guardian finding).
- Source: `VO-FUSED-T10-009` (VERIFIED-audited).
- **State: VERIFIED.** Products: ALL family-line products (E28, E31, E33). Provenance:
  `VO-FUSED-T10-009`.

**CL-CROSS-09 — Activity-boundary C-series map (T3-002/005/006/007/010): a coherent, cross-referenced
classification of who may do what.** This batch's five T3 activity-boundary queries (`T3-002`,
`T3-005`, `T3-006`, `T3-007`, `T3-010`) together resolve a consistent map:
- **C15/C16/C17/C18/C19/C20** — narrow technical-assistance/emergency/audit/commissioning/testing/
  install-repair visit-visa categories, each with a specific compensation and duration ceiling (C18
  Work Trial: max 90 days non-renewable, no salary; C20/C19: install/repair exception to the
  machinery-operation prohibition).
- **C21** — training-instructor visit visa, requires formal invitation from a registered Indonesian
  training institution, honorarium permitted, no subordinate employment relationship.
- **C10** — MICE business-speaker visa, honorarium explicitly permitted, subordinate employment
  prohibited.
- **C7/C7C** — arts/culture and talent visas, strictly non-commercial, only expense reimbursement or
  in-kind facilitation permitted, financial compensation prohibited.
- **D17** — multiple-entry sibling of C17 (audit/technical-assistance), same activity scope, multi-
  entry validity.
- **C9/C22/C22B** — receiving-side categories (short study, internship max 12 months no salary, skills
  development), distinct from the delivering-side categories above.
- The Dharma Dewata substance-over-form standard (CL-CROSS-07) and the barter-is-compensation rule
  (CL-CROSS-01/02) apply uniformly across this entire C-series map — a "free" workshop/training
  session can still trigger enforcement if it generates promotional/economic value for an Indonesian
  beneficiary.
- Source: `VO-FUSED-T3-002`, `VO-FUSED-T3-005`, `VO-FUSED-T3-006`, `VO-FUSED-T3-007`, `VO-FUSED-T3-010`
  (all VERIFIED-audited).
- **State: VERIFIED.** Products: C7, C7C, C9, C10, C15, C16, C17, C18, C19, C20, C21, C22, C22B, D17.
  Provenance: `VO-FUSED-T3-002`, `VO-FUSED-T3-005`, `VO-FUSED-T3-006`, `VO-FUSED-T3-007`,
  `VO-FUSED-T3-010`.

**CL-CROSS-10 — C5A "content creator" index: dormant on the operational portal.** As of 2026-06-01,
the official Kepmen index page for C5A shows only the visa title with body text "Data Belum Tersedia"
("data not yet available") — the index exists in name in the tariff/visa list but is not
self-service-operational; C5A is subject to the SAME compensation-source prohibition as other visit
visas (foreign-sourced monetization e.g. AdSense permitted, any Indonesia-sourced payment or barter
prohibited under CL-CROSS-01/02). Bali Zero's internal practice anchors formal legal citations to the
sibling C5 (Media/Press) index, which is fully live on the portal and shares the same legal matrix,
rather than to the dormant C5A page.
- Source: `VO-FUSED-T3-010`, `VO-FUSED-T6-001` (both VERIFIED-audited, independently corroborating the
  dormancy finding).
- **State: VERIFIED.** Products: C5A, C5. Provenance: `VO-FUSED-T3-010`, `VO-FUSED-T6-001`.

**CL-CROSS-11 — CONFLICT: Golden Visa investment-tier index mismatch (E28B/E28C/"E28G").** See
Conflict Report **CF-12** — an internal "E28G" index label used in some Bali Zero materials does not
cleanly match either E28B (corporate, 10yr, USD 5M) or E28C (portfolio, 10yr, USD 700K) investment
tiers.
- **State: CONFLICTING.** Products: E28B, E28C. Provenance: `VO-FUSED-T4-010` (self-flagged, noting a
  2026-03-28 errata corrige).

## Query budget

40-query batch-1 plan; 42 records logged (34 OK + 8 TIMEOUT, one query retried once). No queries
deferred beyond the 7 documented dedicated-doctrine-card timeouts — each checked against every other
answer in the batch for backfill before being logged as a gap (see per-product Coverage state notes
for BRIDGING/E30B/E33E/E31E/E31J/E30).

## Cross-referenced findings (not new claims, load-bearing for E5)

**Re: e2a's CF-5 (E31B/E31D index-swap claim, REFUTED for production).** This batch's family-line
answers (`VO-FUSED-T1-032`, `VO-FUSED-T13-003`, `VO-FUSED-T14-005`) independently reproduce the SAME
confusion e2a's CF-5 already investigated — NB-2's answers in this batch also frame the spouse/child
E31 sub-index assignment inconsistently across different answers (sometimes E31B=spouse/E31E=child
per the Kepmen table, sometimes internal Bali Zero materials cited within the same answers use
E31D=spouse/E31B-or-E31E=child). **This is NOT logged as a new conflict number** — it is the same
underlying NB-2-source-level artifact e2a's CF-5 already disposed of (REFUTED for the live production
system; the swap exists only inside NB-2's ingested `nb2_visa_types_final.txt`, not in
`seed_visa_types_complete_2026.py` or the live RulePack). Recorded here so E5 does not re-litigate it
as new: **the recurrence across this batch's independent queries is itself evidence the NB-2-source-
level artifact is real and worth an operator housekeeping fix at the NB-2 ingestion level**, even
though it is confirmed harmless to production per CF-5's disposition.

## Adversarial review

Kimi K3 refutation (`~/.kimi-code/bin/kimi -m kimi-code/k3`, timebox 8 min) was launched against the
full text of this ledger plus the companion conflict report. Within the timebox it did not reach a
verdict: it opened by re-verifying file existence and the response-log/citation-audit tallies (both
confirmed matching this ledger's own numbers), then began fanning out into recursive sub-agent
exploration (spot-checking individual claim citations against the raw JSONL) that would have exceeded
the 8-minute budget — killed per orchestrator instruction rather than let run unbounded, per this task's
explicit `≤40 live queries` discipline (an unbounded verification pass is a different kind of budget
violation than a live NB-2 query, but the same spirit: bounded, accountable spend).

Before killing it, Kimi's own partial trace flagged one apparent internal-consistency question worth
recording and disposing of here rather than leaving open: it noted the `## Query execution summary`
states "7 distinct query_ids timed out" while the `## Claims` section elsewhere describes only "six
doctrine-card products [that] never returned an OK answer" (BRIDGING, E30B, E33E, E31E, E31J, E30) — a
6-vs-7 mismatch. **Verified directly against `e2b-batch1-response-log.jsonl` in this turn (not taken on
Kimi's word): the 7th query_id is `VO-FUSED-T1-038` (E33G)**, whose FIRST attempt (killed mid-run
process, before the v2 restart) logged a `TIMEOUT` record, but whose actual final attempt — run by v2 as
a fresh, independent call, per this script's documented resume behavior — returned `status: OK` and is
the source this ledger cites for CL-E33G-01/etc. Both records are real and both are logged (append-only,
nothing overwritten, matching this batch's honesty convention for `VO-FUSED-T1-003`/`-RETRY`): the
response-log's "7 unique query_ids timed out" is a true count of raw log rows, not a claim that 7
products lack an answer. **No claim in this ledger is affected — T1-038/E33G is correctly sourced from
its succeeding attempt, and the six-product doctrine-card-gap list is correct.** Disposition:
**not a defect, self-verified and documented** rather than left as an unresolved flag.

No other finding from Kimi's partial run reached a stated conclusion (it was still dispatching
verification sub-agents on citation content — T6-001, T4-009/CF-11, T1-013/CF-10, T4-010/CF-12, the
age-55-vs-60 CF-7 corroboration set — when killed). Those specific claims were NOT independently
re-verified by this review beyond the mechanical citation-audit already reported in Query execution
summary. Flagging this honestly rather than implying a completed adversarial pass: **this ledger's
CF-7/CF-8/CF-10/CF-12 conflicts and the claims built on PROSE_ONLY answers carry the same evidentiary
weight stated in their own text (self-flagged, corroboration-count-based) — no additional independent
refutation was completed on them this round.** A follow-up batch or operator review should re-attempt
the Kimi pass with a narrower per-claim scope (e.g. one claim per invocation) rather than a single
whole-ledger prompt, which is what caused the fan-out that blew the timebox.
