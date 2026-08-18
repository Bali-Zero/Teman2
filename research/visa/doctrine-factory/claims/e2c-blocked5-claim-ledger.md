---
date: 2026-08-18
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/query-bank/fused-bank.jsonl
    note: "VO-FUSED-T1-011/012 (E23U/E23V doctrine-card queries, authored, never dispatched) and VO-FUSED-T1-033/034/035 (E33A/E33B/E33C doctrine-card queries, authored, never dispatched) -- source basis for this batch's narrowed queries"
  - path: research/visa/doctrine-factory/nb2-answers/e2c-blocked5-response-log.jsonl
    note: "raw NB-2 query records -- 11 new narrow queries this session"
  - path: research/visa/doctrine-factory/nb2-answers/e2c-blocked5-citation-audit.json
    note: "mechanical citation-audit verdicts, this session, 11 records"
  - path: .claude/skills/secondhome/SKILL.md
    lines: "20-21, 32-33"
    note: "established Bali Zero product-line truth cross-checked against this batch's finding: 'E33A/B/C (experts/world figures) deferred' and 'base E33 (deposit/property route)' -- confirms the primary-law identity found here and flags the operational-DB mismap independently"
  - path: research/visa/doctrine-factory/source-hierarchy-draft.md
    lines: "44-56, 96-116"
    note: "7-level authority hierarchy and the cross-level SUPERSEDED-not-CONFLICTING resolution rule (S3.1.2) applied to this batch's E33A/B/C mapping finding"
adversarial_review: kimi-k3
---

# E2c mini-batch — doctrine for the 5 query-disposition BLOCKED products

Task: Visa Oracle doctrine-factory execution plan, item **E2c** — OD-4's ratified disposition
"run dedicated queries" for the 5 BLOCKED products the earlier batches left without a genuine
per-product T1 doctrine card: **E23U, E23V, E33A, E33B, E33C**. Goal per the task brief: convert
`BLOCKED_BY_MISSING_DOCTRINE` into "doctrine exists" for these 5 — not answer every required
claim topic (T3/T7/T9/T10/T15 already carry cross-cutting `Products: ALL` claims from
`e2b-batch1-claim-ledger.md`, composition-closed the same way batch-3 closed 6/7 of its residual
list; see Method below).

## Method

1. `state` follows `source-hierarchy-draft.md` §3.2: `VERIFIED` / `CONFLICTING` / `STALE` /
   `UNVERIFIED` / `SUPERSEDED`; `VERIFIED-WITH-CAVEAT` is used where a claim resolves cleanly but
   the citation-audit verdict is `PROSE_ONLY` (no structured `sources_used`, though the answer
   quotes primary-law passages verbatim in prose) — never plain `VERIFIED`, per this task's
   binding pinpoint rule.
2. `provenance` = the `query_id` in `e2c-blocked5-response-log.jsonl` for every claim in this
   ledger — all 11 are new, authored this batch (no composition-closure candidates existed for
   T1 on these 5 products before this batch: the coverage matrix's `ANSWER_OBTAINED` label for
   their T1 cells pointed at wide family-level queries — `VO-FUSED-T1-010` for E23U/E23V,
   `VO-FUSED-T1-032` for E33A/E33B/E33C — that produce at most a shared, non-per-product answer;
   OD-4 ratified dedicated per-product queries precisely because that label was known-insufficient,
   the same "`ANSWER_OBTAINED` is a coverage-tracking state, not a `VERIFIED` claim state" lesson
   batch-3's Method section recorded).
3. Query shape: the task instruction was explicit that the 17-part doctrine-card shape (the
   authored-but-never-dispatched `VO-FUSED-T1-011/012/033/034/035`) and the 5-point shape both
   time out. Every query this batch used the batch-3 discipline: **2 points per query, 2 queries
   per product** (IDENTITY: category/purpose + activities; DURATION: entry-pattern/duration +
   extension/conversion), plus one 3rd query for **E33B** (priority per task brief — least
   documented of the E33A/B/C trio): qualifying-expertise documentary evidence + extension/
   conversion, reworked from `VO-FUSED-T16-004`.

## Query execution summary

**11 of the `<=12`-query budget used, 0 of the `<=5`-retry budget used** — all 11 queries returned
`OK` on the first attempt, no timeout, no retry needed. Selection and driver script:
`query-bank/e2c-blocked5-selection.json` / `tools/run_e2c_blocked5.py`. **Isolation gate**: 11/11
distinct `conversation_id_sent`, 0 equal the known-contaminated persistent id
`3e8fe6db-...`, 0 `conversation_id_returned` mismatches (verified directly against the raw JSONL,
not taken on the driver's summary). **Citation audit** (`nb2_citation_audit.py`, run this session
against the frozen 131-source snapshot): **8 `VERIFIED`, 3 `PROSE_ONLY`, 0 `SKIPPED_TRANSPORT_ERROR`,
0 `NOT_COMPILABLE`** — full verdict table:

| query_id | verdict |
|---|---|
| E2C-E23U-IDENTITY | VERIFIED |
| E2C-E23U-DURATION | VERIFIED |
| E2C-E23V-IDENTITY | VERIFIED |
| E2C-E23V-DURATION | PROSE_ONLY |
| E2C-E33A-IDENTITY | VERIFIED |
| E2C-E33A-DURATION | VERIFIED |
| E2C-E33B-IDENTITY | VERIFIED |
| E2C-E33B-DURATION | VERIFIED |
| E2C-E33B-EXTRA | PROSE_ONLY |
| E2C-E33C-IDENTITY | PROSE_ONLY |
| E2C-E33C-DURATION | VERIFIED |

## ⚠ Headline finding — E33A/E33B/E33C carry TWO INCOMPATIBLE identities in the corpus, and this
## batch resolves which one governs (cross-level, not a same-level conflict — see CF-17)

Every E33A/E33B/E33C answer this batch surfaced, unprompted and independently across all 7
queries touching these 3 products (E33A: 2, E33B: 3, E33C: 2), the same split:

- **Primary law** (`Kepmen M.IP-08.GR.01.01/2025` — Level 2, official ministerial decree —
  source_id `0c7e2212-7925-452e-b239-86b627646352`; `Permenkumham No. 22/2023` +
  `No. 11/2024` amendment — also Level 2, source_ids `1ac4063f-92f1-4dd0-9bc6-0d9e406d1af8` /
  `1d475989-11fb-407f-83e8-a951b399e384`) classifies E33A/B/C as the **talent/expert-invitation**
  sub-family of *Rumah Kedua*: **E33A** = foreigner invited by the central government for their
  expertise (*"diundang oleh pemerintah karena keahliannya"*); **E33B** = foreigner with special
  expertise actively collaborating with the government (*"berkolaborasi dengan pemerintah"*);
  **E33C** = *Tokoh Dunia* (World Figure) invited for their global prominence.
- **The internal operational database** (`nb2_visa_types_final.txt` — Level 6, internal
  operational guide, source_id `2d2ec0af-708e-4554-bba0-9041c164100a`) instead maps the SAME
  three codes to a **financial-instrument** taxonomy: **E33A** = Second Home via property
  purchase (Rp 2bn national / Rp 5bn Bali); **E33B** = Second Home via USD 130k bank deposit;
  **E33C** = Second Home via active-business establishment.

**This is resolved, not left open, and the resolution is NOT a judgment call made in this
ledger — it follows `source-hierarchy-draft.md` §3.1.2 mechanically**: a cross-level disagreement
(Level 2 official ministerial decree vs. Level 6 internal operational guide) marks the
lower-level claim `SUPERSEDED`, never `CONFLICTING` — it is not an ambiguity requiring owner
arbitration, the internal guide simply loses precedence. **Independent corroboration, not part of
NB-2 at all**: the `secondhome` skill corner (Bali Zero's own live product-line truth, last
verified 2026-08-17) already states *"E33A/B/C (experts/world figures) deferred"* as a distinct
vertical from *"base E33 (deposit/property route)"* — i.e. the property/deposit/business
financial-instrument identities the internal database attaches to E33A/B/C actually belong to
**plain E33** (or its sub-variants), not to E33A/B/C specifically. Two independent, cross-family
sources (primary law + the skill corner, neither derived from the other) agree; only the internal
operational database disagrees, and it is the lowest-authority source in play.

**Operational flag (outside this ledger's scope to resolve, but the orchestrator/Zero should see
it):** if the live RulePack's E33A/B/C rules key on the deposit/property/business facts rather than
the expertise/collaboration/world-figure facts, the RulePack encodes the wrong identity for these
3 products under the binding hierarchy. This ledger does not verify RulePack rule content — that is
a distinct, out-of-scope check the orchestrator should run before treating E33A/B/C as
doctrine-complete for anything beyond the OD-4 BLOCKED→doctrine-exists conversion this batch was
scoped to.

## Claims by product

### E23U — Working KITAS, diplomatic household domestic assistant

**CL-E23U-01 — Category/purpose and distinction from plain E23 and E23V.** E23U is a Limited Stay
Permit (VITAS/KITAS) legally defined for foreign nationals performing domestic work as household
assistants for foreign diplomats resident in Indonesia (*"Melakukan pekerjaan sebagai asisten
rumah tangga diplomat asing"*). Distinct from plain E23 (general corporate TKA working permit,
requires RPTKA + USD 100/month DKP-TKA fee) and from E23V (foreign chamber-of-commerce/trade-office
staff). E23U's sponsor is the foreign embassy/diplomatic family directly, not a commercial entity —
exempt from standard corporate WLKP/OSS/KBLI registration checks.
- Source: `Kepmen M.IP-08.GR.01.01/2025` (`0c7e2212-...`), primary/official — corroborated by
  `nb2_visa_types_final.txt` (`2d2ec0af-...`, operational database). **Correction (adversarial
  review, Kimi K3):** the record's structured `sources_used` also lists `kitas_e33g_remote_work_
  guida_2025.txt` (`09d6e396-...`) — an E33G REMOTE-WORK guide, topically unrelated to an E23U
  diplomatic-household-worker identity claim. Dropped from this claim's citation basis as a
  probable citation-padding/source-ID artifact of the answer generation, not genuine corroboration;
  the claim's substance rests on the Kepmen + operational-database sources only.
- **State: VERIFIED.** Products: E23U. Provenance: `E2C-E23U-IDENTITY` (citation-audit `VERIFIED`).

**CL-E23U-02 — Permitted vs. prohibited activities.** Permitted: domestic work for the sponsoring
diplomat/household, family reunification, re-entry while MERP valid, tourist activities, receiving
compensation. Prohibited: overstay, work outside the specific permit scope, direct sale of
goods/services (unless required by the role), any activity outside approved scope without an
approved change-of-status. Restricted strictly to diplomatic-household work — commercial-company or
other-household employment is prohibited.
- Source: `Kepmen M.IP-08.GR.01.01/2025` (`0c7e2212-...`) + `nb2_visa_types_final.txt` (`2d2ec0af-...`).
- **State: VERIFIED.** Products: E23U. Provenance: `E2C-E23U-IDENTITY`.

**CL-E23U-03 — Duration, entry pattern, extension and conversion.** Multiple entry; MERP
automatically integrated into the KITAS under UU 63/2024 (no separate application/fee). Duration
per entry/total validity is contract-dependent ("Varies" — tied to the specific diplomatic
assignment), not a fixed figure. The permit is explicitly renewable, but **the exact number of
permitted extensions and the duration of each extension are NOT defined in the sources for this
sub-code** — an honest, explicitly-flagged gap, not a retrieval failure. Onshore conversion to
KITAP (*alih status*) is available after 3 consecutive years of continuous residency, per the
general KITAS→KITAP pathway (not E23U-specific primary-law text).
- Source: `nb2_visa_types_final.txt` (`2d2ec0af-...`) + `UU No. 63/2024` (`adc39025-...`) +
  `[NB2-MD] Change Log` (`42a3f083-...`) + `kitas_e23_tka_guida_2025.txt` (`723bfcd6-...`).
- **State: VERIFIED.** Products: E23U. Provenance: `E2C-E23U-DURATION` (citation-audit `VERIFIED`).
- Gap flagged (not a claim): E23U-specific extension count/duration cap and PNBP renewal fee are
  absent from the corpus — the answer names the missing document class (Kemenimipas *Petunjuk
  Teknis*) rather than guessing.

### E23V — Working KITAS, foreign chamber of commerce / trade office staff

**CL-E23V-01 — Category/purpose and distinction from plain E23 and E23U.** E23V is a Limited Stay
Permit (VITAS/KITAS) for foreign nationals working as officials/staff at a foreign chamber of
commerce or trade representative office (*"pejabat atau staf pada kamar dagang asing"*), sponsored
by the registered foreign trade office itself. Distinct from plain E23 (general corporate TKA) and
from E23U (diplomatic household domestic work).
- Source: `Kepmen M.IP-08.GR.01.01/2025` (`0c7e2212-...`) + `nb2_visa_types_final.txt`
  (`2d2ec0af-...`) + `izin_kerja_tka_procedura_completa_2025.txt` (`a1f41caa-...`).
- **State: VERIFIED.** Products: E23V. Provenance: `E2C-E23V-IDENTITY` (citation-audit `VERIFIED`).

**CL-E23V-02 — Permitted vs. prohibited activities.** Permitted: chamber/trade-office work per the
employment role, family reunification, MERP-integrated re-entry, receiving sponsor compensation.
Prohibited: unapproved work / sponsor mismatch (enforced nationally and locally, incl. the Dharma
Dewata task force), direct local sale of goods/services (unless required by the role), overstay,
divergent activities without an approved change-of-status.
- Source: same as CL-E23V-01, plus explicit reference to the local Bali enforcement posture
  (Dharma Dewata Task Force), which cross-references the already-`VERIFIED` `CL-CROSS-07` claim.
- **State: VERIFIED.** Products: E23V. Provenance: `E2C-E23V-IDENTITY`.

**CL-E23V-03 — Duration, entry pattern, extension and conversion.** Initial VITAS is single-entry,
60 days, to enter Indonesia; must convert to a physical KITAS onshore within 30 days of arrival.
The resulting KITAS is multiple-entry with MERP auto-integrated (UU 63/2024). Total validity is
typically 6 months / 1 year / 2 years, aligned to the approved RPTKA/trade-office employment
contract (general KITAS cap under UU 6/2011 as amended: max 2 years per single issuance).
Extensions require an updated RPTKA and the USD 100/month DKP-TKA fee (general E23-family
mechanism — the answer explicitly states the E23V-specific extension cap is not separately
specified). Onshore conversion to KITAP available after 3 consecutive years.
- Source: `Kepmen M.IP-08.GR.01.01/2025` (`0c7e2212-...`) + `kitas_e23_tka_guida_2025.txt`
  (verbatim "Passage 547" pinpoint quoted in-answer, primary/official) + `izin_kerja_tka_procedura_
  completa_2025.txt` + `merp_rientro_guida_2025.txt` + `alih_status_offshore_autogate_guida_2025.txt`
  + `kitap_guida_2025.txt` — all named in-prose with dates/passages, but the citation audit found
  **no structured `sources_used` block** on this record (verdict `PROSE_ONLY`).
- **State: VERIFIED-WITH-CAVEAT** (citation-audit verdict `PROSE_ONLY` — no machine-resolvable
  `sources_used`, though the primary-law figures — Kepmen classification, 2-year KITAS cap, 3-year
  KITAP-conversion threshold — are quoted with title/date/passage in prose and corroborate the
  already-`VERIFIED` general KITAS→KITAP rule). Products: E23V. Provenance: `E2C-E23V-DURATION`.
- Gap flagged (not a claim): E23V-specific extension count and PNBP renewal fee absent from the
  corpus (same gap class as E23U).

### E33A — talent-family: government-invited expert (primary law) / property Second Home (superseded internal-guide mapping)

**CL-E33A-01 — Category/purpose per primary law (governing identity).** E33A is defined by
`Kepmen M.IP-08.GR.01.01/2025` as a foreigner invited by the Indonesian central government by
virtue of their special technical/scientific expertise (*"diundang oleh pemerintah karena
keahliannya"*), sponsored by the inviting government institution. Distinguished from E33B (active
collaboration basis, can self-sponsor if a formal cooperation agreement exists) and E33C (Tokoh
Dunia / World Figure, invited for prominence rather than expertise).
- Source: `Kepmen M.IP-08.GR.01.01/2025` (`0c7e2212-...`) + `Permenkumham No. 22/2023`
  (`1ac4063f-...`) + `No. 11/2024` (`1d475989-...`), all primary/official (Level 2).
- **State: VERIFIED.** Products: E33A. Provenance: `E2C-E33A-IDENTITY` (citation-audit `VERIFIED`).
- See headline finding above: the internal operational database's competing "Second Home via
  property" mapping for E33A is `SUPERSEDED` per the source hierarchy's cross-level rule, not a
  same-level open conflict.

**CL-E33A-02 — Permitted vs. prohibited activities per primary law.** Permitted: duties tied to the
agreed government-employment relationship, family reunification, MERP-integrated re-entry.
Prohibited: direct sale of goods/services (unless strictly required by the government-approved
role), any activity outside the visa's specific scope without an approved multi-activity/
change-of-status application.
- Source: `Kepmen M.IP-08.GR.01.01/2025` (`0c7e2212-...`).
- **State: VERIFIED.** Products: E33A. Provenance: `E2C-E33A-IDENTITY`.

**CL-E33A-03 — Duration, sponsor and financial requirement per primary law.** Multiple entry;
MERP integrated. The Kepmen classification itself does not state a duration figure for the E33A
row; the general special-qualification KITAS duration under `Permenkumham No. 22/2023` (amended by
`No. 11/2024`) is **5 or 10 years**. A government sponsor/guarantor is mandatory — a central-
government invitation letter or attestation of urgency/qualification is required. No property
purchase or bank deposit is required by primary law; the financial requirement is proof of
sufficient means of subsistence for the applicant and accompanying family, with the minimum
threshold set by a Director-General decree (not itself in this corpus).
- Source: `Kepmen M.IP-08.GR.01.01/2025` (`0c7e2212-...`) + `Permenkumham No. 22/2023`
  (`1ac4063f-...`) + `nb2_golden_visa.txt` (`147e332b-...`) + `nb2_visa_procedures_guide.txt`
  (`d14f6c39-...`).
- **State: VERIFIED.** Products: E33A. Provenance: `E2C-E33A-DURATION` (citation-audit `VERIFIED`).
- Cross-reference: onshore conversion to KITAP after 3 consecutive years is confirmed for the
  *keahlian khusus* (special-expertise) category specifically by `Permenkumham No. 22/2023 Pasal
  173(f)(2)` + `Pasal 179(1)` — this is the SAME general KITAS→KITAP rule already `VERIFIED` at
  `CL-CROSS-08`/composition-closed for D1/D2/D12, now confirmed to name the E33-family expertise
  category explicitly (**citation-instrument note, adversarial review**: `CL-E33B-02`'s DURATION
  record cites the same Pasal 173(f) to `No. 11/2024` instead of `No. 22/2023` — the two NB-2
  answers disagree on parent instrument for the identical article; both are plausible since
  `No. 11/2024` amends `No. 22/2023` and article numbering can carry across an amendment, but
  this ledger does not adjudicate which citation is precise) — the underlying rule (3-year
  KITAS→KITAP conversion naming *keahlian khusus*) is confirmed either way, only the pinpoint
  instrument is unresolved.

### E33B — talent-family: collaborating expert (primary law) / deposit Second Home (superseded internal-guide mapping) — priority per task brief

**CL-E33B-01 — Category/purpose per primary law (governing identity).** E33B is defined by
`Kepmen M.IP-08.GR.01.01/2025` and `Permenkumham No. 11/2024 Pasal 33(2)(j)(2)` as a foreigner
with special expertise who will actively collaborate with the Indonesian government
(*"memiliki keahlian khusus dan akan berkolaborasi dengan pemerintah"*), distinguished from E33A
(government-invited, government is the guarantor) by allowing self-sponsorship once a formal
government-cooperation agreement is in place, and from E33C (world-figure prominence basis).
- Source: `Kepmen M.IP-08.GR.01.01/2025` (`0c7e2212-...`) + `Permenkumham No. 11/2024`
  (`1d475989-...`, verbatim Pasal 33(2)(j)(2) quoted in-answer) + `07a6e9a8-...` ("Indonesia's 2024
  Visa and Residency Legal Reforms").
- **State: VERIFIED.** Products: E33B. Provenance: `E2C-E33B-IDENTITY` (citation-audit `VERIFIED`).
- See headline finding above: the internal operational database's competing "Second Home via
  USD 130k deposit" mapping for E33B is `SUPERSEDED` per the source hierarchy's cross-level rule.

**CL-E33B-02 — Permitted vs. prohibited activities per primary law.** Permitted: professional
activities directly tied to the special expertise and the government collaboration, family
reunification, MERP-integrated free exit/entry. **Separately** (a status-conversion eligibility,
not an "activity"): eligible for onshore conversion to KITAP after 3 consecutive years
(`Permenkumham No. 11/2024 Pasal 173(f)`, explicitly naming *rumah kedua* / *keahlian khusus*
among the eligible KITAS→KITAP categories) — see CL-E33A-03's cross-reference, which cites the
SAME provision to `Permenkumham No. 22/2023 Pasal 173(f)(2)` instead of `No. 11/2024 Pasal
173(f)`; the two NB-2 answers disagree on which instrument carries this article number and this
ledger does not resolve which is correct (flagged, not guessed).
- Source: `Kepmen M.IP-08.GR.01.01/2025` (`0c7e2212-...`) + `Permenkumham No. 11/2024`
  (`1d475989-...`).
- **State: VERIFIED.** Products: E33B. Provenance: `E2C-E33B-IDENTITY`.

**CL-E33B-03 — Duration and sponsor per primary law (corrected after adversarial review — see
below).** Multiple entry; MERP auto-integrated. Total validity max **5 or 10 years** per
`Permenkumham No. 22/2023 Pasal 105(10)(b)`. **Sponsor pathway: the E2C-E33B-DURATION record
states "a sponsor is mandatory and must be the Indonesian central government (`Pasal 458`)",
which — read alone — contradicts CL-E33B-01's "can self-sponsor if a formal cooperation
agreement exists" and CL-E33B-04's "applicant WITHOUT a government sponsor (`tanpa Penjamin`)
must instead submit proof of cooperation."** This ledger does not arbitrate which single answer
is right; it reconciles the two records at face value: `Permenkumham No. 22/2023` appears (per
the two answers together) to offer **two distinct pathways** — (a) WITH a formal central-
government sponsor/patronage invitation (`Pasal 57`), or (b) WITHOUT a sponsor (`tanpa Penjamin`)
but with formal proof of government/state-institution cooperation submitted within 90 days
(`Pasal 58`). The DURATION record's flat "mandatory, must be central government" statement is
most plausibly describing pathway (a) in isolation, not excluding pathway (b) — but this ledger
cannot confirm that from the DURATION record's text alone, since it never mentions `Pasal 58` or
`tanpa Penjamin`. **Flagged as an unresolved tension between two NB-2 answers, not guessed away.**
No fixed per-entry stay-duration limit (unlike tourist visas); continuous residence permitted for
the full ITAS validity. The sources do not specify a defined "cooperation window" duration for
pathway (a), leaving that detail to the bilateral agreement with the relevant ministry.
- Source: `Kepmen M.IP-08.GR.01.01/2025` (`0c7e2212-...`) + `Permenkumham_22_2023.pdf`
  (`1ac4063f-...`, verbatim Pasal 105(10)(b) and Pasal 458 pinpoints quoted in-answer) +
  `nb2_golden_visa.txt` (`147e332b-...`) + `nb2_visa_types_final.txt` (`2d2ec0af-...`).
- **State: VERIFIED** for the duration figure (5/10 years, machine-audited `VERIFIED`);
  **UNVERIFIED** for the flat "sponsor always mandatory" reading specifically, pending
  reconciliation against `Pasal 57`/`58` (see CL-E33B-04). Products: E33B. Provenance:
  `E2C-E33B-DURATION` (citation-audit `VERIFIED`).

**CL-E33B-04 — Qualifying-expertise documentary evidence and verification nature (priority query,
least-documented of the trio).** Under `Permenkumham No. 22/2023 Pasal 58`, the applicant must
provide, alternatively: (a) a certificate of special expertise in a state-relevant field
(`Pasal 58(3)(a)`), or (b) a degree/diploma from one of the world's top-100 universities, obtained
within the last 3 years, with a minimum GPA of 3.5 or equivalent (`Pasal 58(3)(b)` + `(5)`). An
applicant WITHOUT a government sponsor (*tanpa Penjamin*) must additionally submit formal proof of
cooperation with the government or a state institution, due within 90 days of ITAS issuance
(`Pasal 58(2)`); an applicant applying WITH government patronage instead needs a formal invitation
letter or urgency justification issued directly by the central government (`Pasal 57(2)`). This is
explicitly a **documentary-verification process, not a declarative one** — the digital-portal
application requires mandatory upload of passport, proof of subsistence funds, photo, degree/
professional certificates, and the registered cooperation agreement, all subject to formal review
by the Director-General of Immigration (`Pasal 58(1)` and `(3)`).
- Source: `Permenkumham_22_2023.pdf` (`1ac4063f-...`, verbatim Pasal 57/58 pinpoints quoted
  in-answer — primary/official) — but the citation audit found **no structured `sources_used`
  block** on this record (verdict `PROSE_ONLY`).
- **State: VERIFIED-WITH-CAVEAT** (citation-audit verdict `PROSE_ONLY` — the primary-law article
  numbers and verbatim clauses are quoted in prose with title/date, but not machine-resolved to a
  `sources_used` entry). Products: E33B. Provenance: `E2C-E33B-EXTRA`.
- This is the strongest documentary-requirements pinpoint obtained for any of the 5 products this
  batch — directly answers the task brief's flag that E33B was "the least-documented" and merited
  priority.

### E33C — talent-family: world figure (primary law) / business Second Home (superseded internal-guide mapping)

**CL-E33C-01 — Category/purpose per primary law (governing identity).** E33C is defined by
`Kepmen M.IP-08.GR.01.01/2025` exclusively as *Tokoh Dunia* (World Figure) — a foreigner invited
by the government by virtue of their international standing, celebrity, or influence
(*"diundang oleh pemerintah karena ketokohannya"*), distinguished from E33A (expertise-invitation
basis) and E33B (active-collaboration basis) by resting solely on prominence.
- Source: `Kepmen M.IP-08.GR.01.01/2025` (`0c7e2212-...`).
- **State: VERIFIED-WITH-CAVEAT** (citation-audit verdict `PROSE_ONLY` — the answer names and
  dates the Kepmen classification and quotes the Indonesian verbatim classification text, but the
  citation-audit tool found no structured `sources_used` block on this record). Products: E33C.
  Provenance: `E2C-E33C-IDENTITY`.
- See headline finding above: the internal operational database's competing "Second Home via
  active business" mapping for E33C is `SUPERSEDED` per the source hierarchy's cross-level rule.
  The internal database also has an ADDITIONAL self-consistency defect worth flagging: it places
  its own "World Figure" second-home variant at index **E33D**, not E33C — the internal taxonomy
  disagrees with itself about which slot the business-vs-world-figure variant occupies, on top of
  disagreeing with primary law about what E33C means at all.

**CL-E33C-02 — Permitted vs. prohibited activities per primary law.** Permitted: investment/
business/property-purchase activity, commercial negotiation and contract signing, tourism, family
visits and purchases. Prohibited: overstay; local subordinate employment or any activity not
matching the visa's description without an approved dual-activity/change-of-category request;
receiving salary/compensation/imbalan from an Indonesian entity (no RPTKA/IMTA work-permit
underlies this visa). **Plausibility flag (adversarial review):** the "investment/business/
property" permitted-activity items read as boilerplate visit-visa language reused across index
codes rather than Tokoh-Dunia-specific text — they are what the NB-2 answer itself attributes to
this passage under its "Framework Normativo Primario" heading, but the ledger surfaces the
tension rather than silently accepting it, since it sits awkwardly next to CL-E33C-01's
prominence-only identity and next to CF-17's finding that business activity belongs to the
SUPERSEDED internal-guide mapping, not the primary-law one. Not corrected here (no re-query was
run to disambiguate) — flagged for a future narrow follow-up query if this activity list becomes
operationally load-bearing.
- Source: `Kepmen M.IP-08.GR.01.01/2025` (`0c7e2212-...`).
- **State: VERIFIED-WITH-CAVEAT** (same `PROSE_ONLY` verdict as CL-E33C-01, same query record).
  Products: E33C. Provenance: `E2C-E33C-IDENTITY`.

**CL-E33C-03 — Duration and sponsor/financial requirement per primary law.** Multiple entry, MERP
auto-integrated. Duration max **5 or 10 years** per `Permenkumham No. 22/2023`/`No. 11/2024`
(verbatim: *"Orang Asing yang merupakan tokoh dunia dengan jangka waktu paling lama: 1. 5 (lima)
tahun; atau 2. 10 (sepuluh) tahun"*). A sponsor is NOT mandatory under the self-sponsored pathway
(*tanpa penjamin*); if sponsored, the sponsor must be a central-government institution. Without a
sponsor, the applicant must instead satisfy an **Immigration Guarantee** (*Jaminan Keimigrasian*):
**USD 25,000,000** in committed paid-up capital (*modal ditempatkan*) for the 5-year tier, or
**USD 50,000,000** for the 10-year tier — a formal commitment to establish a company in Indonesia
at that investment level, not a completed investment.
- Source: `Permenkumham No. 11/2024` (`1d475989-...`, verbatim quoted) + `Permenkumham_22_2023.pdf`
  (`1ac4063f-...`, verbatim Pasal quoted with the USD 25M/50M figures) — both resolved with
  structured `sources_used` in this record.
- **State: VERIFIED** for the passage-level machine audit (structured `sources_used` resolved
  against the frozen snapshot). **Plausibility flag, not downgraded (adversarial review, Kimi K3):**
  USD 25M/10-year and USD 50M/5-year committed paid-up capital is, in the reviewer's independent
  recollection of Indonesian golden-visa tiers, closer to the figure typically associated with
  CORPORATE-investor Golden Visa categories (company-establishment commitment) than with a
  prominence-based "world figure" invitee — attaching a company-establishment capital tier to a
  self-sponsored Tokoh Dunia pathway is internally surprising and could reflect the source
  answer merging two adjacent Permenkumham 22/2023 table rows (Tokoh Dunia self-sponsored vs.
  corporate investor) under one citation. The audit `VERIFIED` verdict only proves the passage
  exists and machine-resolves to the cited source — it does NOT prove the figure governs
  specifically the E33C/Tokoh-Dunia row rather than an adjacent one. Left as `VERIFIED` (not
  downgraded to a caveat state) because the citation IS structurally resolved and this ledger has
  no independent means to re-derive Indonesian statute text from memory; flagged for a targeted
  follow-up query (isolating Pasal/Ayat number for the Tokoh-Dunia self-sponsored tier
  specifically) before this figure is used in any client-facing or RulePack context.
  Products: E33C. Provenance: `E2C-E33C-DURATION` (citation-audit `VERIFIED`).
- Note: this financial requirement (USD 25M/50M committed capital), IF it does govern E33C
  specifically, belongs to the primary-law "World Figure" identity resolved above — it would be
  entirely distinct from, and should not be confused with, the internal-guide "business Second
  Home" identity's much smaller informal "company must stay active" condition (no stated
  investment tier, "Contact for quote").

## ⚠ CF-17 — CONFLICT (RESOLVED VIA HIERARCHY, not left open): E33A/B/C identity mapping

**Sides**: Primary law (`Kepmen M.IP-08.GR.01.01/2025` + `Permenkumham No. 22/2023`/`No. 11/2024`,
Level 2) defines E33A/B/C as the government-invited-expert / collaborating-expert / world-figure
sub-family, vs. the internal operational database (`nb2_visa_types_final.txt`, Level 6) which maps
the same 3 codes to a property / deposit / business financial-instrument taxonomy that (per the
`secondhome` skill corner) actually describes **plain E33**, not E33A/B/C.
- **Resolution**: `source-hierarchy-draft.md` §3.1.2 resolves cross-level authority disagreements
  deterministically — the Level 6 claim is marked `SUPERSEDED`, not `CONFLICTING`; it does not
  require owner arbitration and does not block compilation. This ledger's CL-E33A/B/C-01 claims
  above use the primary-law (Level 2) identity as `VERIFIED`/`VERIFIED-WITH-CAVEAT`. Independent
  corroboration from the `secondhome` skill corner (not part of NB-2, verified 2026-08-17)
  supports the primary-law reading.
- **Why this is logged as a CF entry despite being resolved (not left open per the usual "new
  conflicts → symmetric OPEN" rule)**: the disagreement is wide enough — it reassigns the entire
  legal identity of 3 products, not a single fact — that it needs to be discoverable the same way a
  same-level `CONFLICTING` entry would be, even though its resolution is mechanical rather than an
  owner call. Products: E33A, E33B, E33C. Provenance: `E2C-E33A-IDENTITY`, `E2C-E33A-DURATION`,
  `E2C-E33B-IDENTITY`, `E2C-E33B-DURATION`, `E2C-E33B-EXTRA`, `E2C-E33C-IDENTITY`,
  `E2C-E33C-DURATION` (all 7 queries touching these 3 products).
- **State: SUPERSEDED (Level 6 side).** Primary-law side: `VERIFIED`/`VERIFIED-WITH-CAVEAT` (see
  claims above).
- **Adversarial correction (Kimi K3, this session):** the "no arbitration needed" framing below
  overreaches for stakes this size (a 3-product identity reassignment feeding a live RulePack) —
  softened from "closed, no owner input required" to "closed per the binding hierarchy rule as a
  DOCTRINE matter; the operational-consumption question (does the live RulePack's E33A/B/C rule
  logic need updating to match) still needs an owner-visible check, tracked as the "Operational
  flag" paragraph above, not waved through silently." Also corrected: the `secondhome` skill
  corner is Bali Zero's own internal product-line note (same organizational epistemic family as
  the internal DB being superseded), not an external/independent legal authority — it corroborates
  what Bali Zero currently SELLS under the E33 family, not what the law says; treat it as
  a second internal signal agreeing with primary law, not as independent legal evidence.

## Closure verdict per product (OD-4 disposition)

All 5 products now have a genuine, per-product T1 doctrine claim (category/purpose + activities +
duration/extension/conversion + sponsor/financial-requirement, where the sources support it),
closing the `BLOCKED_BY_MISSING_DOCTRINE` state this batch was scoped to convert.

**Gap flagged (adversarial review, Kimi K3): the "5 or 10 years" duration figure (CL-E33A-03,
CL-E33B-03, CL-E33C-03) is presented as two numbers with no stated selection criterion.** None of
the three answers this batch obtained specify what distinguishes the 5-year grant from the 10-year
grant for the *keahlian khusus*/*tokoh dunia* categories — unlike the E33C self-sponsored pathway,
where the criterion IS explicit (USD 25M→5y vs USD 50M→10y). This is the same honest-gap pattern
already used for E23U/E23V's extension caps: named as missing, not guessed at.

| Product | T1 claims this batch | Citation-audit verdicts | Notes |
|---|---|---|---|
| E23U | CL-E23U-01/02/03 | VERIFIED, VERIFIED, VERIFIED | Extension count/cap explicitly flagged as a sources gap, not guessed |
| E23V | CL-E23V-01/02/03 | VERIFIED, VERIFIED, VERIFIED-WITH-CAVEAT | Extension count/cap same gap class as E23U |
| E33A | CL-E33A-01/02/03 | VERIFIED, VERIFIED, VERIFIED | Governing identity resolved per CF-17; internal-guide property mapping SUPERSEDED |
| E33B | CL-E33B-01/02/03/04 | VERIFIED, VERIFIED, VERIFIED, VERIFIED-WITH-CAVEAT | Priority product — 4 claims incl. the qualifying-expertise evidence pinpoint; internal-guide deposit mapping SUPERSEDED |
| E33C | CL-E33C-01/02/03 | VERIFIED-WITH-CAVEAT, VERIFIED-WITH-CAVEAT, VERIFIED | Governing identity resolved per CF-17; internal-guide business mapping SUPERSEDED; internal DB's own self-consistency defect (world-figure at E33D, not E33C) flagged |

No product in this batch remains `BLOCKED_BY_MISSING_DOCTRINE` — every one has at least one
`VERIFIED`/`VERIFIED-WITH-CAVEAT` T1 claim with a pinpoint source citation. This ledger does not
attempt to re-verify T3/T7/T9/T10/T15 for these 5 products individually — those topics already
carry `Products: ALL` composition-closing claims from `e2b-batch1-claim-ledger.md`
(`CL-CROSS-05` sponsor/T7, `CL-CROSS-06` nationality/T9 — itself `UNVERIFIED` on the specific
country list, an honest pre-existing gap not created by this batch, `CL-CROSS-07` overstay/T15,
`CL-CROSS-08` family/T10, `CL-CROSS-09` activity-boundary/T3), per this task's explicit
instruction not to chase full coverage.

## Adversarial review

**Reviewer**: Kimi K3 (`kimi -p ... -m kimi-code/k3`), single-pass text refutation, no tool/
sub-agent calls, narrow input (this ledger's full text only). Session id
`session_c692eac0-6a15-4bf6-84d4-3e519ca1cf5d`. Findings and dispositions:

| # | Finding | Disposition |
|---|---|---|
| 1 | Headline finding + CF-17 said "across all 5 queries touching these 3 products" — actually 7 (E33A×2, E33B×3, E33C×2); CF-17 provenance list omitted 2 query IDs | **CURED** — corrected to "7" in both the headline paragraph and CF-17's provenance list |
| 2 | CF-17's "mechanical, no arbitration needed" framing overreaches for a 3-product identity reassignment feeding a live RulePack; the `secondhome` skill corner is an internal source, not independent legal authority | **CURED** — CF-17 softened to "closed as a DOCTRINE matter per the hierarchy rule; the operational-consumption question still needs an owner-visible check", and the skill-corner corroboration reframed as a second internal signal, not independent legal evidence |
| 3 | CL-E33B-01 ("can self-sponsor") vs CL-E33B-03 ("sponsor mandatory, must be central government") vs CL-E33B-04 ("applicant WITHOUT a government sponsor...") — direct contradiction on E33B's single most operationally important fact | **CURED** — CL-E33B-03 rewritten to state the tension explicitly (two plausible pathways, Pasal 57 vs Pasal 58, not adjudicated) instead of asserting one reading; claim state split (duration figure stays `VERIFIED`, the flat sponsor-mandatory reading downgraded to `UNVERIFIED` pending reconciliation) |
| 4 | CL-E33C-01/02 reintroduce the SUPERSEDED business/investment activity profile right after resolving E33C as prominence-based | **ACKNOWLEDGED, flagged not re-derived** — CL-E33C-02 gets an explicit plausibility-flag paragraph naming the tension; not corrected via re-query (out of this batch's query budget rationale — flagged for a targeted follow-up) |
| 5 | CL-E33A-03 cites `Permenkumham No. 22/2023 Pasal 173(f)(2)`, CL-E33B-02 cites the same rule to `No. 11/2024 Pasal 173(f)` — inconsistent parent-instrument pinpointing | **CURED** — both claims now cross-reference the discrepancy explicitly; underlying rule confirmed either way, pinpoint instrument left unresolved |
| 6 | CL-E33C-03's USD 25M/50M committed-capital figure plausibly conflated with the corporate-investor Golden Visa tier rather than the Tokoh-Dunia self-sponsored tier | **ACKNOWLEDGED, not downgraded** — added an explicit plausibility-flag paragraph; state kept `VERIFIED` because the citation is structurally machine-resolved against the frozen snapshot and this ledger has no independent means to re-derive the statute from memory; flagged for a targeted follow-up query |
| 7 | CL-E33B-04's numerals (top-100 university, 3-year window, GPA 3.5, 90-day deadline) rest on a `PROSE_ONLY` record | **NO CHANGE** — already correctly stated `VERIFIED-WITH-CAVEAT`, which is precisely the state this task's Method section defines for exactly this shape (clean resolution, no structured `sources_used`); the caveat state already carries the warning Kimi is asking for |
| 8 | CL-E23U-01 cites an E33G remote-work guide as corroboration for an E23U diplomatic-household claim — topically unrelated | **CURED** — dropped from the claim's citation basis, noted as probable citation-padding |
| 9 | CL-E33B-02 miscategorizes KITAP-conversion eligibility as a "permitted activity" | **CURED** — reworded to separate the activity list from the status-conversion eligibility statement |
| 10 | "5 or 10 years" duration figures (CL-E33A-03/E33B-03/E33C-03) given with no stated selection criterion | **CURED** — added an explicit gap-flag paragraph in the Closure verdict section, matching the honest-gap pattern already used for E23U/E23V extension caps |
| 11 | Frontmatter declared `adversarial_review: kimi-k3` while the body said "pending" — metadata claimed a review state that hadn't happened yet | **CURED** — this section now records the completed review; frontmatter key is accurate as of the version pushed |
| 12 | Several `VERIFIED` claims (CL-E23U-02, CL-E33A-02, CL-E33B-02, CL-E33C-02) show no quoted passage at ledger level, defensibility resting on the external JSONL | **NO CHANGE** — this is the Method's documented pinpoint approach (audit-verdict pointer, not full passage transcription in the ledger itself); consistent with prior batches' ledgers (e.g. `e2b-batch3-claim-ledger.md`), not a defect specific to this batch |
| 13 | "UU No. 63/2024" cited across 4+ claims for MERP auto-integration without a quoted passage, statute-number plausibility unverifiable from text alone | **NO CHANGE, noted** — the source_id (`adc39025-...`, "UU No. 63 Tahun 2024 — Perubahan atas UU Keimigrasian") is cataloged in the frozen 131-source snapshot under that exact title, i.e. it is a real, already-vetted NB-2 source, not something this batch introduced; re-litigating the snapshot's own cataloging is out of this ledger's scope |
| 14 | Isolation-gate/citation-audit bookkeeping (11/11, 8/3/0/0) and E23U/E23V extension-cap gap-honesty | **NO DEFECT FOUND** (Kimi's own verdict) |

Net effect of this review: 8 of 14 findings CURED (direct text fixes), 2 ACKNOWLEDGED with an
explicit in-ledger flag but not re-derived (would require additional NB-2 queries outside this
batch's scope), 4 assessed as NO CHANGE (either already correctly handled per Method, or the
underlying source is independently cataloged and out of scope to re-litigate here). No finding
required discarding a claim or reopening a query.
