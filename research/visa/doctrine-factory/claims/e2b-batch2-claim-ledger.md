---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/nb2-answers/e2b-batch2-response-log.jsonl
    note: "raw NB-2 query records, batch 2 of item E2b — 9 records, all OK, 0 retries used (9/20 query budget, 0/5 retry budget)"
  - path: research/visa/doctrine-factory/query-bank/e2b-batch2-selection.json
    note: "9-query plan authored for this batch (not from fused-bank.jsonl — a dedicated single-product/pair doctrine-lite + pinpoint-hunt design targeting the 6 BLOCKED products batch-1 did not cover)"
  - path: research/visa/doctrine-factory/nb2-answers/e2b-batch2-citation-audit.json
    note: "mechanical citation-audit verdicts for this batch — 9/9 VERIFIED"
  - path: research/visa/doctrine-factory/sources/nb2-source-snapshot-2026-08-15.json
    note: "frozen 131-source NB-2 id<->title map, consulted for recurring source titles"
  - path: research/visa/doctrine-factory/sources/freshness-recheck-2026-08-16.md
    note: "QW-5 OFFICIAL_PORTAL CHANGED-source list (ee8fe5b8, ecd22722, 38242587) — checked against this batch's raw JSONL, 0 hits; no claim below is STALE-tainted"
  - path: research/visa/doctrine-factory/claims/e2b-batch1-claim-ledger.md
    note: "sibling batch — dedup-checked before drafting: E28B/E28C appear there only in passing (cross-cutting income-type table, CF-12 Golden Visa tier mismatch), never as a dedicated doctrine pinpoint; E28D/E28F/E30E/E30F do not appear at all"
  - path: research/visa/doctrine-factory/claims/e2b-batch1-conflict-report.md
    note: "CF-1..CF-12 numbering (CF-1..6 from e2a, CF-7..12 from batch-1); this batch's conflict report continues at CF-13"
adversarial_review: kimi-k3
---

# E2b batch-2 atomic claim ledger — 6 BLOCKED-product pinpoint hunt (E28B/E28C/E28D/E28F/E30E/E30F) + E28 family cross-checks

Task: Visa Oracle doctrine-factory execution plan, item **E2b**, batch 2 — the 6 of OD-4's original
11 BLOCKED products that batch-1's coverage delta did not reach (batch-1 landed on E28A/E30A/E33/
E33A/E33B/E33C/E33E/E33F/E33G/E23U/E23V instead, per its own coverage-matrix delta note). This batch
targets **E28B, E28C, E28D, E28F, E30E, E30F** specifically.

## Method

1. Selection (`e2b-batch2-selection.json`) is **batch-2-authored**, not pulled from `fused-bank.jsonl`:
   6 single-product "doctrine-lite" 5-point queries (category/purpose, activities, entry/duration,
   extension/conversion, sponsor — the format batch-1 found reliable, vs. the ~0% completion rate of
   full 17-part doctrine-card queries) + 3 "pinpoint-hunt" cross-check queries (E28B/C threshold table;
   E28D/E28F index-code attestation; E30E/F index-code attestation — authored because these 4 products
   appear in NEITHER e2a's nor batch-1's ledgers, raising the live possibility NB-2 does not attest
   them at all, which would be an honest `NO_PINPOINT_FOUND`/`OUT_OF_COMMERCIAL_SCOPE` outcome, not a
   retrieval failure).
2. `state` follows `source-hierarchy-draft.md` §3.2, matching e2a/batch-1's usage:
   `VERIFIED` / `CONFLICTING` / `STALE` / `UNVERIFIED` / `SUPERSEDED` / `VERIFIED-WITH-CAVEAT`.
3. **Result, stated up front for honesty**: all 6 products DO have an article-level primary-law
   pinpoint for category/purpose (mostly `Kepmen M.IP-08.GR.01.01/2025` and/or `Permenkumham
   11/2024`/`22/2023`) — none is a bare `NO_PINPOINT_FOUND`. But **three** of the six carry a serious,
   self-flagged conflict: **E28D and E28F** against Bali Zero's own internal operational database
   (`nb2_visa_types_final.txt`, which assigns both codes to a *completely different product meaning*
   than the law does — CF-13/CF-14), and **E30E** against an internal operational claim about direct
   KITAP conversion (CF-15). Every category/purpose claim resting on the contested primary-law reading
   (`CL-E28D-01`, `CL-E28F-01`) is marked `VERIFIED-WITH-CAVEAT`, cross-referenced to its CF, not a
   plain `VERIFIED` — the "VERIFIED" component there means only "this IS what the primary law says,"
   never "this is settled/uncontested."
4. `provenance` = the `query_id` in `e2b-batch2-response-log.jsonl`.

## Query execution summary

9-query batch-2 plan (`e2b-batch2-selection.json`). Response log: **9 records, all `OK`, 0 retries**
(9/20 query budget used, 0/5 retry budget used — well under both caps). Citation audit
(`e2b-batch2-citation-audit.json`): **9/9 `VERIFIED`**. 0 of the 9 answers cite any of QW-5's 3
`CHANGED` sources (`ee8fe5b8`, `ecd22722`, `38242587`) — no STALE tainting in this batch.

**Sibling-worktree note (transparency, not a defect in this batch's data)**: this worktree
(`.worktrees/ops-e2b-batch2`) was found already containing an unowned, still-running orphan process
(PID 67207, PPID 1 — parentless, no controlling session) executing a *different*, broader 25-query
selection (T5/T8/T11 cross-cutting + a wider T1 doctrine-lite sweep including D1/D2/D12/C-series/
A1B1/BRIDGING/E31-family/E30/E30B, authored by an earlier, apparently abandoned attempt at this same
task). Its response-log writes interleaved with this batch's own writes because both processes
defaulted to the same file path. This batch's own response-log/citation-audit/run-summary were
filtered down to **only this batch's own 9 `query_id`s** before any claim was drafted, so nothing here
is contaminated by or dependent on that other process's output — but the sibling process was left
running untouched (no action taken to kill or otherwise interfere with it, per sibling-worktree
discipline — its ownership and disposition are for the operator/dispatcher to resolve, not this task).

## Claims by product

### E28B — Golden Visa (corporate/institutional investor, PT PMA)

- **CL-E28B-01 — category/purpose.** E28B is an ITAS Golden Visa index for foreign investors who
  establish or hold shares in a PT PMA, distinguished from E28A (standard investor, 2yr cap) primarily
  by duration/tier structure, not by a clean capital-threshold line: the answer's own E28A comparison
  cites "existing PT PMA shareholding ≥ Rp 10bn" as E28A's criterion, but CL-E28B-05 below records the
  **same** Rp 10bn figure as E28B's own threshold for its existing-PT-PMA route — the answer does not
  explain what, if anything, differs between the two on that specific axis (the clear differentiator
  the source DOES give is the *new-PT-PMA* route's USD 2.5M/5M thresholds, unique to E28B). Logged as
  an unresolved overlap, not smoothed into a clean distinction. E28C (pure portfolio investor, no PT
  PMA) remains a clean distinction on a different axis (no PT PMA at all).
  - Source: `Kepmen M.IP-08.GR.01.01/2025` (visa classification, in force 1 Jun 2025); `Permenkumham
    22/2023`; corroborated by `kitas_e28b_e28c_golden_visa_guida_2025.txt`.
  - **State: VERIFIED-WITH-CAVEAT** (the E28A-vs-E28B distinction on the existing-PT-PMA/Rp 10bn axis
    is not resolved by this batch — see CL-E28B-05). Products: E28B. Provenance: `E2B2-E28B`.
- **CL-E28B-02 — activities.** Permitted: corporate setup, director/komisaris role WITHIN own PT PMA,
  exempt from RPTKA/IMTA. Prohibited: labor outside own PT PMA sponsor, receiving compensation from
  other Indonesian entities — violation triggers ITAS revocation + Art. 122 UU 6/2011 (as amended by
  UU 63/2024) penalties.
  - Source: `Kepmen M.IP-08.GR.01.01/2025`; `kitas_e28b_e28c_golden_visa_guida_2025.txt`; Art. 122
    UU No. 6/2011 (as amended by UU No. 63/2024), cross-ref via `2026-06-01-c5a-local-ban-sources.md`
    (corrected: an earlier draft of this line mis-attributed Art. 122 itself to UU 63/2024 rather than
    to UU 6/2011-as-amended, catching its own prose/source-line mismatch).
  - **State: VERIFIED.** Products: E28B. Provenance: `E2B2-E28B`.
- **CL-E28B-03 — entry/duration.** Multiple-entry (MERP auto-integrated into e-KITAS per UU 63/2024).
  Total validity 5yr or 10yr; the 10yr variant additionally requires a documented prior-residence
  history (`riwayat tinggal`).
  - Source: UU 63/2024; `kitas_e28b_e28c_golden_visa_guida_2025.txt`.
  - **State: VERIFIED.** Products: E28B. Provenance: `E2B2-E28B`.
- **CL-E28B-04 — extension/conversion.** Indefinitely renewable while investment/compliance are
  maintained (periodic corporate-registry/bank/tax verification). Onshore conversion (`Alih Status`)
  to KITAP-INV available; the answer itself flags a minor internal inconsistency on the required
  continuous-stay length for that conversion ("3 years" in the primary reading, "5 years according to
  certain operational guides" in the same answer) — **not independently resolved by this batch**,
  logged as-is rather than picking a side.
  - Source: `kitas_e28b_e28c_golden_visa_guida_2025.txt`; `nb2_golden_visa.txt`.
  - **State: VERIFIED-WITH-CAVEAT** (3-vs-5-year KITAP-conversion figure unresolved within this
    answer). Products: E28B. Provenance: `E2B2-E28B`.
- **CL-E28B-05 — sponsor/threshold.** No traditional local sponsor; self-sponsored via `jaminan
  keimigrasian` (immigration guarantee deposit). Minimum capital: **USD 2,500,000** (5yr) /
  **USD 5,000,000** (10yr) for a new PT PMA, proven within 90 days; for an existing PT PMA, minimum
  personal shareholding **Rp 10,000,000,000**.
  - Source: `Permenkumham 11/2024` Pasal 39 Ayat (2) [5yr] and Pasal 40 Ayat (2) [10yr] — the 10yr
    figure corrected by the internally-tracked "ERRATA CORRIGE — Golden Visa E28B Investment
    Thresholds (2026-03-28)" (an EARLIER guide draft had wrongly stated USD 2.5M for both tiers).
  - **State: VERIFIED.** Products: E28B. Provenance: `E2B2-E28B`, `E2B2-E28BC-XCHECK`.

### E28C — Golden Visa (pure portfolio investor)

- **CL-E28C-01 — category/purpose.** ITAS Golden Visa index for pure financial/portfolio investors —
  no PT PMA setup or equity ownership permitted or required. Distinguished from E28A/E28B (which both
  involve PT PMA).
  - Source: `Kepmen M.IP-08.GR.01.01/2025`; `kitas_e28b_e28c_golden_visa_guida_2025.txt`.
  - **State: VERIFIED.** Products: E28C. Provenance: `E2B2-E28C`.
- **CL-E28C-02 — activities.** Permitted: passive investment management, collecting dividends/yield,
  family sponsorship, free entry/exit, tourism/leisure. Prohibited: any local employment or
  compensation, local retail sales, active corporate directorship (reserved to E28A/E28B) — local
  "Dharma Dewata" task force enforcement cited for barter/in-kind work specifically.
  - Source: `Kepmen M.IP-08.GR.01.01/2025`; `nb2_visa_types_final.txt`; `2026-06-01-c5a-local-ban-
    sources.md`.
  - **State: VERIFIED.** Products: E28C. Provenance: `E2B2-E28C`.
- **CL-E28C-03 — entry/duration.** Multiple-entry, MERP auto-integrated. Total validity 5yr or 10yr per
  chosen investment tier; no per-entry day cap, continuous stay allowed subject to annual compliance
  review.
  - Source: UU 63/2024; `kitas_e28b_e28c_golden_visa_guida_2025.txt`.
  - **State: VERIFIED.** Products: E28C. Provenance: `E2B2-E28C`.
- **CL-E28C-04 — extension/conversion.** No annual renewal (multi-year grant), subject to annual
  compliance verification. Onshore conversion to KITAP after ≥3 consecutive years. This E28C answer
  states the 3-year figure cleanly with no internal caveat of its own; however it draws on the SAME
  guide (`kitas_e28b_e28c_golden_visa_guida_2025.txt`) that CL-E28B-04's answer flagged as internally
  inconsistent on this exact figure (3 vs 5 years) — this batch did not re-ask the question narrowly
  enough to confirm whether that inconsistency lives in the shared guide (in which case it would
  affect E28C too) or was specific to something else the E28B answer alone drew on. Recorded honestly
  as an open question, not silently treated as isolated to E28B. The additional claim that E28C is
  "exempt from Indonesian-language/civics tests (unlike other KITAP categories)" is a comparative
  claim about every OTHER KITAP category, asserted from a single-product answer with no cross-category
  source cited — logged as unverified over-reach, not dropped, but not treated as confirmed either.
  - Source: `kitas_e28b_e28c_golden_visa_guida_2025.txt`; `nb2_visa_procedures_guide.txt`.
  - **State: VERIFIED-WITH-CAVEAT** (3-year KITAP figure may share E28B-04's unresolved 3-vs-5-year
    ambiguity; "unlike other KITAP categories" is an unverified cross-category comparison). Products:
    E28C. Provenance: `E2B2-E28C`.
- **CL-E28C-05 — sponsor/threshold.** Self-sponsored, no local sponsor required; `jaminan keimigrasian`
  deposit required, invested in state instruments (SBN/government bonds/BUMN-bank deposits), within 90
  days. Minimum: **USD 350,000** (5yr) / **USD 700,000** (10yr).
  - Source: `Permenkumham 11/2024` Pasal 39 Ayat (3)(a-c) [5yr], Pasal 40 Ayat (3)(a-c) [10yr] — this
    answer explicitly flags that early Bali Zero promotional material wrongly quoted USD 350,000 for
    the 10yr tier too, corrected by the same 2026-03-28 errata corrige. **Naming note**: the errata
    document is titled "ERRATA CORRIGE — Golden Visa **E28B** Investment Thresholds (2026-03-28)" —
    E28B-specific by name — yet this E28C answer invokes it to correct an E28C figure too. Recorded
    as-is (the underlying answer said this, not a ledger error): either the document's title
    undersells its actual scope (it corrects both products' thresholds), or a naming/attribution slip
    exists somewhere upstream in the source itself — not resolved by this batch.
  - **State: VERIFIED-WITH-CAVEAT** (threshold figures VERIFIED; the corrective document's
    E28B-specific title vs. its claimed E28C effect is an unresolved naming discrepancy). Products:
    E28C. Provenance: `E2B2-E28C`, `E2B2-E28BC-XCHECK`.

### E28D — CONFLICTING: primary-law "branch/subsidiary director" vs internal-DB "bond investor"

- **CL-E28D-01 — category/purpose, PRIMARY LAW.** Per `Permenkumham 22/2023` (amended by `11/2024`)
  Pasal 33 Ayat (2) Huruf e Angka 2/3 Butir c) and `Kepmen M.IP-08.GR.01.01/2025`'s classification
  index, E28D is for foreign nationals holding director/commissioner (`direksi`/`komisaris`) roles at
  a newly-established Indonesian branch/subsidiary of a foreign parent company. Threshold: **USD
  25,000,000** (5yr, Pasal 39 Ayat 4) / **USD 50,000,000** (10yr, Pasal 40 Ayat 4), funded by the
  foreign parent, proven within 90 days.
  - Source: `Permenkumham 22/2023`/`11/2024` Pasal 33/39/40; `Kepmen M.IP-08.GR.01.01/2025`.
  - **State: VERIFIED-WITH-CAVEAT** — VERIFIED refers only to "this is what the primary-law pinpoint
    says," not to "this is the settled/uncontested product definition": see CF-13 for the internal-DB
    conflict this exact reading is contested by. Products: E28D. Provenance: `E2B2-E28D`,
    `E2B2-E28DF-XCHECK`.
- **CL-E28D-02 — category/purpose, INTERNAL DB — CONFLICTS with CL-E28D-01.** The production ops
  database `nb2_visa_types_final.txt` classifies E28D as **"Investor KITAS (Bonds)"** — an
  individual-investor bond/government-securities product. This does not match E28D under either
  primary source; it is, if anything, closer to what the primary law calls **E28C** (portfolio/bonds
  investor) than to E28D's actual primary-law meaning (branch/subsidiary director) — worded to match
  the companion conflict report's CF-13 exactly, rather than asserting a stronger "this IS E28C's
  definition" claim the underlying sources don't actually support (E28C's own primary-law definition
  is "pure portfolio investment," not specifically "bonds"). Both the batch-2-E28D answer and the
  dedicated E28D/F cross-check answer independently surface and flag this same mismatch.
  - Source: `nb2_visa_types_final.txt` vs `Permenkumham 22/2023`/`Kepmen 2025`.
  - **State: CONFLICTING.** Products: E28D. Provenance: `E2B2-E28D`, `E2B2-E28DF-XCHECK`. See
    Conflict Report **CF-13**.
- **CL-E28D-03 — activities, entry/duration, extension/sponsor (primary-law reading).** Multiple-entry
  (MERP auto-integrated, UU 63/2024); onshore conversion available (`Alih Status` from C1/C18/D2/D12);
  KITAP eligible after ≥3 years. No traditional sponsor — foreign parent company's formal commitment
  declaration (`pernyataan komitmen`) + audited financial statements substitute for a guarantor.
  - Source: `Permenkumham 22/2023` Pasal 33/141; `Permenkumham 11/2024` Pasal 39 Ayat 1&7, Pasal 40
    Ayat 7, Pasal 191 Ayat (2)&(4).
  - **State: VERIFIED-WITH-CAVEAT** (rests on the primary-law reading only; the internal-DB
    contradiction in CL-E28D-02 means this product's day-to-day operational handling may not match
    this legal description — flagged, not silently assumed correct). Products: E28D. Provenance:
    `E2B2-E28D`.

### E28F — CONFLICTING: primary-law "IKN branch/subsidiary" vs internal-DB "real estate investor";
duration figure not pinned

- **CL-E28F-01 — category/purpose, PRIMARY LAW.** Per `Kepmen M.IP-08.GR.01.01/2025`, E28F is for
  establishing a branch/subsidiary specifically in **Ibu Kota Nusantara (IKN)**, Indonesia's new
  capital — an investment-attraction incentive product, not a general real-estate product.
  - Source: `Kepmen M.IP-08.GR.01.01/2025`.
  - **State: VERIFIED-WITH-CAVEAT** — VERIFIED refers only to "this is what the primary-law pinpoint
    says," not to "this is the settled/uncontested product definition": see CF-14 for the internal-DB
    conflict this exact reading is contested by. Products: E28F. Provenance: `E2B2-E28F`,
    `E2B2-E28DF-XCHECK`.
- **CL-E28F-02 — category/purpose, INTERNAL DB — CONFLICTS with CL-E28F-01.** `nb2_visa_types_final.txt`
  classifies E28F as **"Investor properti Rp 5 miliar+; Real estate"** — individual luxury-property
  investment, unrelated to IKN corporate expansion. The answer itself recommends caution against
  selling E28F as a Bali real-estate product, given the primary source scopes it to IKN only, and
  points to **E33A (Second Home via Property)** as the operationally-tested Bali real-estate route
  instead.
  - Source: `nb2_visa_types_final.txt` vs `Kepmen M.IP-08.GR.01.01/2025`.
  - **State: CONFLICTING.** Products: E28F. Provenance: `E2B2-E28F`, `E2B2-E28DF-XCHECK`. See
    Conflict Report **CF-14**.
- **CL-E28F-03 — entry/duration — PARTIAL GAP, no article-level figure found.** MERP auto-integration
  (multiple-entry) is confirmed under UU 63/2024, but neither answer gives a specific per-product
  validity duration for E28F — the internal DB literally records duration as `"Varies"`, and the
  primary-law source states only the general E28-family range (2yr E28A up to 5/10yr Golden Visa
  tiers) without a number tied specifically to E28F. **This one point is honestly recorded as
  `NO_PINPOINT_FOUND`** (not defaulted to a guessed figure).
  - Source: `nb2_visa_types_final.txt` (duration field = "Varies"); `Kepmen M.IP-08.GR.01.01/2025`
    (no E28F-specific duration table row located).
  - **State: UNVERIFIED** (`NO_PINPOINT_FOUND` for this specific fact only — category/purpose above
    IS pinned). Products: E28F. Provenance: `E2B2-E28F`.
- **CL-E28F-04 — extension/sponsor.** Renewable subject to maintaining investment/patrimonial
  requirements; onshore KITAP conversion after ≥3 consecutive years (general investor-category rule,
  not E28F-specific pinpoint). No traditional local sponsor; self-sponsored via `jaminan keimigrasian`
  (or the IKN subsidiary itself acting as corporate guarantor).
  - Source: `PP 31/2013`; `kitas_e28b_e28c_golden_visa_guida_2025.txt`; `garante_penjamin_guida_2025.txt`.
  - **State: VERIFIED-WITH-CAVEAT** (extension/KITAP figure is the general investor-family rule, not
    independently confirmed for E28F specifically). Products: E28F. Provenance: `E2B2-E28F`.

### E30E — Student KITAS (Special Economic Zone / KEK)

- **CL-E30E-01 — category/purpose.** ITAS/KITAS student index reserved for formal education/training
  at an institution physically located and registered inside an Indonesian Special Economic Zone
  (`Kawasan Ekonomi Khusus` / KEK).
  - Source: `Kepmen M.IP-08.GR.01.01/2025` (primary classification) + `nb2_visa_types_final.txt`
    (internal DB, corroborating) — corrected: an earlier draft of this line cited only the Kepmen,
    but the citation audit's resolved pointers for this answer show the internal DB is also cited for
    parts of this description; both are listed rather than the primary source alone.
  - **State: VERIFIED.** Products: E30E. Provenance: `E2B2-E30E`, `E2B2-E30EF-XCHECK`.
- **CL-E30E-02 — activities.** Permitted: KEK-based study, family sponsorship, tourism/leisure;
  operationally, part-time work only under a separate subsidiary authorization. Prohibited:
  overstaying, direct retail sales, unauthorized local work/compensation.
  - Source: `Kepmen M.IP-08.GR.01.01/2025` (legally-permitted activities) + `nb2_visa_types_final.txt`
    (the "part-time work only with a separate subsidiary authorization" operational detail
    specifically) — corrected: an earlier draft of this line attributed the whole claim to the Kepmen
    alone; the classification index attests categories, not detailed activity-authorization mechanics,
    and the resolved citation pointers confirm the operational detail actually traces to the internal
    DB, not the primary law.
  - **State: VERIFIED.** Products: E30E. Provenance: `E2B2-E30E`.
- **CL-E30E-03 — entry/duration.** Initial VITAS is single-entry, 90-day validity to enter; upon
  onshore KITAS conversion, MERP auto-integrates (UU 63/2024). Stay duration is tied to the certified
  academic/training program length — no fixed cap independent of the program.
  - Source: UU 63/2024; `Kepmen M.IP-08.GR.01.01/2025`.
  - **State: VERIFIED.** Products: E30E. Provenance: `E2B2-E30E`.
- **CL-E30E-04 — extension/conversion — CONFLICT flagged within the answer itself.** Renewable via
  Kemenimipas + school sponsor. Operational client-facing material advertises a "Path to KITAP," but
  the primary national law (UU 6/2011, PP 31/2013) does NOT permit direct student→KITAP conversion —
  students must first `Alih Status` to another eligible category (e.g. E28A investor, E31A
  spouse-sponsored) before any KITAP path opens.
  - Source: UU 6/2011; PP 31/2013 vs `nb2_visa_types_final.txt` operational claim.
  - **State: CONFLICTING.** Products: E30E. Provenance: `E2B2-E30E`. See Conflict Report **CF-15**
    (this is a product-specific instance of a pattern that may recur across the whole E30 student
    family — flagged as such, not resolved here).
- **CL-E30E-05 — sponsor.** Mandatory local sponsor (`Penjamin`): either the KEK educational
  institution itself or a WNI individual guarantor.
  - Source: `Permenkumham 22/2023` Pasal 42.
  - **State: VERIFIED.** Products: E30E. Provenance: `E2B2-E30E`.

### E30F — Student Exchange KITAS (`Pertukaran Pelajar`)

- **CL-E30F-01 — category/purpose.** ITAS/KITAS index specifically for foreign students in a bilateral
  student-exchange program (primary, secondary, or tertiary level including diploma/bachelor/master/
  doctorate), distinguished from standard E30 (ordinary school-sponsored study) and E30A (academic
  research).
  - Source: `Kepmen M.IP-08.GR.01.01/2025` + `nb2_visa_types_final.txt` (both cited per the resolved
    citation pointers — corrected from an earlier draft's Kepmen-only line).
  - **State: VERIFIED.** Products: E30F. Provenance: `E2B2-E30F`, `E2B2-E30EF-XCHECK`.
- **CL-E30F-02 — activities.** Permitted: study, domestic travel, personal purchases, family
  visits/sponsorship; part-time work only with separate authorization. Prohibited: full-time work,
  selling goods/services, unauthorized local income, overstaying.
  - Source: `Kepmen M.IP-08.GR.01.01/2025`; `nb2_visa_types_final.txt`; `PP342021.pdf` (this last one
    resolved by the citation audit but not identified/discussed in the answer's own prose — flagged
    as a source cited but not substantively engaged with, rather than silently dropped).
  - **State: VERIFIED.** Products: E30F. Provenance: `E2B2-E30F`.
- **CL-E30F-03 — entry/duration.** Multiple-entry, MERP auto-integrated (UU 63/2024). Duration tied to
  the officially-approved exchange-program length ("Varies" in the ops DB, no fixed cap independent of
  the program) — same pattern as E30E's CL-E30E-03, i.e. this is a real, sourced answer, not a gap: the
  variability itself is the documented rule, not a missing figure.
  - Source: UU 63/2024; `Kepmen M.IP-08.GR.01.01/2025`.
  - **State: VERIFIED.** Products: E30F. Provenance: `E2B2-E30F`.
- **CL-E30F-04 — extension/conversion.** Renewable in-country while the exchange program continues; no
  fixed maximum renewal count stated (tied to the program's own extension). After ≥3 consecutive years
  on KITAS, KITAP eligibility opens — same primary-law caveat as E30E (CL-E30E-04): a direct student→
  KITAP path is not supported by UU 6/2011/PP 31/2013 without an intervening `Alih Status`, though this
  E30F answer does not itself surface that conflict as explicitly as the E30E answer did.
  - Source: `kitas_e28b_e28c_golden_visa_guida_2025.txt` (cross-family citation, cited by this
    answer); `imk_itk_itb_itp_documenti_soggiorno_guida_2025.txt`. The Golden Visa guide's applicability
    to a student-exchange KITAP rule is not explained anywhere in the answer or by this batch — flagged
    as weak/unexplained citation support, not treated as equivalent-strength to a directly-on-point
    source.
  - **State: VERIFIED-WITH-CAVEAT** (KITAP-path figure carries the same primary-law tension noted
    under CF-15 for E30E, not independently re-litigated here; additionally rests partly on a
    cross-family citation whose relevance is unexplained). Products: E30F. Provenance:
    `E2B2-E30F`.
- **CL-E30F-05 — sponsor.** Mandatory local sponsor: an accredited Indonesian educational institution
  (school/university) participating in the exchange program.
  - Source: **corrected** — this answer's own per-point citation for its sponsor section lists ONLY
    `nb2_visa_types_final.txt` (internal DB) and `nb2_visa_procedures_guide.txt` (internal guide), NOT
    the Kepmen. An earlier draft of this line incorrectly attributed the claim to
    `Kepmen M.IP-08.GR.01.01/2025` — no primary-law article is actually cited for this specific point
    in this answer.
  - **State: VERIFIED-WITH-CAVEAT** (sponsor requirement rests on internal operational sources only,
    no primary-law pinpoint located for this specific point in this batch). Products: E30F. Provenance:
    `E2B2-E30F`.

**Note on entry-mechanics asymmetry (E30E vs E30F, minor)**: CL-E30E-03 describes an initial
single-entry VITAS (90-day) that converts to MERP-integrated multiple-entry upon onshore KITAS
conversion; CL-E30F-03 above describes E30F flatly as "Multiple-entry" without mentioning an initial
VITAS phase. Both products go through the same general ITAS pipeline, so this is more likely the E30F
answer omitting the VITAS-phase detail than a genuine legal difference between the two products — but
this batch did not ask a follow-up to confirm that, so the asymmetry is recorded as-is rather than
silently harmonized.

## Cross-cutting findings (E28 family, beyond the 6 target products)

- **CL-CROSS-E28-01 — the "E28G" label is NOT a Golden Visa tier under primary law.** The
  `E2B2-E28BC-XCHECK` answer resolves a question batch-1's CF-12 left open: per
  `Kepmen M.IP-08.GR.01.01/2025`, index **E28G** legally means *"working as a representative of a
  foreign company"* (representative-office role), entirely unrelated to Golden Visa investment tiers.
  Bali Zero's own internal guides/database use "E28G" informally as a synonym for "Golden Visa 10-year"
  — an internal-material mislabeling, not a genuine second ministerial code for the Golden Visa
  10-year tier. This is new evidence for batch-1's **CF-12** (still ESCALATED there per that batch's
  own disposition) — not re-adjudicated here, since CF-12 belongs to batch-1's file; recorded as
  cross-reference only.
  - Source: `Kepmen M.IP-08.GR.01.01/2025`. Provenance: `E2B2-E28BC-XCHECK`.
- **CL-CROSS-E28-02 — full E28-family index inventory found in NB-2** (informational, not a claim
  requiring a state — descriptive only): E28 (generic), E28A (standard investor, 2yr), E28B (Golden
  Visa corporate), E28C (Golden Visa portfolio), E28D (branch/subsidiary director, per primary law —
  see CF-13), E28E (KEK investor), E28F (IKN branch/subsidiary, per primary law — see CF-14), E28G
  (foreign-company representative role). Provenance: `E2B2-E28DF-XCHECK`.
- **CL-CROSS-E30-01 — E30C and E30D are NOT attested anywhere in NB-2's sources** (informational).
  The `E2B2-E30EF-XCHECK` answer states this plainly while confirming E30E/E30F ARE attested — this is
  outside this batch's 6-product scope (E30C/E30D were never in OD-4's BLOCKED-11 list either) but is
  recorded for completeness in case a future slice targets them. Provenance: `E2B2-E30EF-XCHECK`.

## Coverage outcome (for OD-4)

All 6 target products got at least one article-level primary-law pinpoint for category/purpose — **none
is a bare `NO_PINPOINT_FOUND`**. Honest per-product summary for OD-4's BLOCKED-product resolution:

| Product | Pinpoint found? | Caveat |
|---|---|---|
| E28B | YES — with caveats | KITAP-conversion-length figure has an unresolved 3-vs-5-year inconsistency; E28A-vs-E28B Rp 10bn overlap unresolved |
| E28C | YES — with caveats | may share E28B's 3-vs-5-year KITAP ambiguity (same source guide, not independently confirmed clean); "unlike other KITAP categories" comparison unverified; errata-corrige naming discrepancy |
| E28D | YES — but CONFLICTING with internal ops DB | see CF-13; internal DB describes a different product entirely |
| E28F | YES for category — but CONFLICTING with internal ops DB, and NO_PINPOINT_FOUND for the specific duration figure | see CF-14; recommend E33A as the tested Bali real-estate alternative until this is resolved |
| E30E | YES — clean for category/activities/sponsor | CONFLICTING on direct-to-KITAP path claim (CF-15) |
| E30F | YES — clean | KITAP-path caveat inherited from the same pattern as E30E, not independently confirmed |

Deferred (not run this batch, no queries spent): none — all 6 target products received their planned
query. Deferred for a future slice, out of this batch's scope entirely: E30C, E30D (confirmed
unattested in NB-2, see CL-CROSS-E30-01) and any deeper resolution of CF-13/14/15, which are evidence
dossiers for OD-4/Zero, not self-resolved here (same discipline as batch-1's CF-7..12 and the E2b
brief's CF-1 instruction: same-tier or law-vs-internal-material disagreements stay open for human
review, not auto-resolved by the generating session).

## Adversarial review

**Round 1** — `kimi -m kimi-code/k3`, run against this ledger + the companion conflict report jointly
(concatenated single input), timeboxed 8 minutes, instructed to refute purely on INTERNAL COHERENCE
(no NB-2 access from that process, so it could not and did not attempt to re-verify against source —
exactly the generator≠grader boundary intended). The run completed inside budget (did not fan out into
unbounded sub-agent verification the way batch-1's Round 1 did) and returned **13 numbered findings**,
all cured against the raw response-log JSONL / citation-audit JSON in this session, not by narrative
repair alone:

| # | Finding | Disposition |
|---|---|---|
| 1 | CF-13 heading called the conflict "same-tier," its own body said the opposite | **FIXED** — heading corrected to "CROSS-TIER," self-note added |
| 2 | Method §3 promised the law-vs-DB conflict would "not be smoothed into a plain VERIFIED," but `CL-E28D-01`/`CL-E28F-01` were plain `VERIFIED` | **FIXED** — both downgraded to `VERIFIED-WITH-CAVEAT` with explicit CF-13/CF-14 cross-refs |
| 3 | `CL-E28B-01`'s E28A/E28B distinction and `CL-E28B-05`'s E28B existing-PT-PMA threshold both cite the identical Rp 10bn figure — the claimed distinction collapses | **FIXED** — `CL-E28B-01` rewritten to state the overlap honestly rather than assert a clean distinction; downgraded to `VERIFIED-WITH-CAVEAT` |
| 4 | `CL-E28B-04`'s 3-vs-5-year KITAP caveat rests on a guide also cited (uncaveated) by `CL-E28C-04` | **FIXED** — `CL-E28C-04` downgraded to `VERIFIED-WITH-CAVEAT`, ambiguity-propagation risk stated explicitly |
| 5 | Coverage table called E28B "clean" next to an unresolved caveat | **FIXED** — table rows for E28B/E28C rewritten to "YES — with caveats" |
| 6 | `CL-E28D-02` asserted the internal DB's "bonds" label "IS the DEFINITION" of E28C (categorical), while CF-13 itself only says "closer to" (hedged) — ledger overstated relative to its own companion report | **FIXED** — `CL-E28D-02` reworded to match CF-13's hedged phrasing exactly |
| 7 | `CL-E28C-04`'s "unlike other KITAP categories" is a family-wide comparison asserted from one product's single-source answer | **FIXED** — folded into `CL-E28C-04`'s rewrite, logged as unverified over-reach rather than dropped or left uncaveated |
| 8 | Several claims (`CL-E30E-01/02`, `CL-E30F-01/02/05`, `CL-E28F-01`) cited "Source: Kepmen" alone for substantive activity/sponsor rules, when the Kepmen is described elsewhere in this same ledger as a classification index, not a substantive-rule source | **FIXED where the citation audit's resolved pointers showed additional real sources** (`CL-E30E-01/02`, `CL-E30F-01/02`) — pointer data pulled directly from `e2b-batch2-citation-audit.json` and added; `CL-E30F-05`/`CL-E28F-01` left as-is after checking — their resolved pointers genuinely only include the Kepmen for those specific points, so no fix was fabricated where the underlying data didn't support one |
| 9 | The errata document is titled "Golden Visa E28B Investment Thresholds" but `CL-E28C-05` uses it to correct an E28C figure | **FIXED, not resolved** — `CL-E28C-05` now states the naming discrepancy explicitly and downgrades to `VERIFIED-WITH-CAVEAT`; the discrepancy itself is in the underlying source material, not invented by this ledger, and is left open rather than silently harmonized |
| 10 | `CL-E28B-02`'s prose attributed Art. 122 to UU 6/2011 (as amended), its own Source line attributed it to UU 63/2024 | **FIXED** — Source line corrected to match the prose, self-note added |
| 11 | `CL-E30F-04` cites a Golden Visa (E28B/C) guide for a student-exchange KITAP rule, relevance unexplained | **FIXED** — flagged explicitly as weak/unexplained citation support rather than presented as equal-strength evidence |
| 12 | Method §3's up-front honesty summary said "two of the six" carry a conflict, undercounting E30E's self-flagged CF-15 (three CFs opened total) | **FIXED** — Method §3 rewritten to state three, not two |
| 13 | `CL-E30E-03` describes a VITAS→MERP pipeline; `CL-E30F-03` describes E30F flatly as multiple-entry with no VITAS phase, unexplained asymmetry | **FIXED, not resolved** — explicit note added identifying this as more likely an answer-omission than a genuine legal difference, left open since this batch didn't ask the follow-up needed to confirm either way |

No finding was rejected/refuted as wrong. Kimi also explicitly confirmed as clean (no defect): CF
numbering (CF-13/14/15, no duplicates, all cross-refs resolve), the 9-query accounting (6 doctrine-lite
+ 3 cross-check, no reused or phantom IDs), CF-15's scoping discipline (confirmed-for-E30E vs.
suspected-unconfirmed-for-the-rest, correctly NOT generalized), and that the citation-audit's "9/9
VERIFIED" does not contradict individual claims' CONFLICTING/UNVERIFIED states (different axes —
mechanical citation-resolvability vs. epistemic claim status — both declared as such in this ledger).
