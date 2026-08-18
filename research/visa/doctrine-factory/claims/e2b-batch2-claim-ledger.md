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
  - path: research/visa/doctrine-factory/nb2-answers/e2b-batch2b-response-log.jsonl
    note: "EXTENSION note (batch-2b, separate PR): 30 records — this session's own 25-query broader slice + 10 lost-and-recovered re-runs, kept in its OWN file so it never collides with this file's already-merged 9-record e2b-batch2-response-log.jsonl. See the '## E2b batch-2b EXTENSION' section below for the sibling-worktree collision this file's name change is a direct consequence of."
  - path: research/visa/doctrine-factory/query-bank/e2b-batch2b-selection.json
    note: "EXTENSION artifact: this session's own 25-query plan, kept separate from the already-merged e2b-batch2-selection.json"
  - path: research/visa/doctrine-factory/nb2-answers/e2b-batch2b-citation-audit.json
    note: "EXTENSION artifact: citation-audit verdicts for this session's own 30 records"
  - path: research/visa/doctrine-factory/query-bank/coverage-matrix-after-batch2b.json
    note: "EXTENSION artifact: combined coverage delta (batch-1 + already-merged batch-2's 9 + this EXTENSION's 25/30), built this session"
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

---

## E2b batch-2b EXTENSION — 27-PARTIAL-product closing slice + CF-7/8/10/12 pinpoint hunt

Task: item **E2b**, the SECOND, independently-dispatched slice of batch-2 work — assigned separately
from the 9-query 6-BLOCKED-product batch above (that batch merged as PR #4258 before this EXTENSION was
ready; this EXTENSION lands as its OWN follow-up PR). Targets: the 27 products the batch-1 coverage
delta left `PARTIAL` (prioritized by rule-count, highest first) plus 5 dedicated pinpoint-hunt queries
for CF-7/CF-8/CF-10/CF-12. **Additive**: everything above this line is the already-merged batch-2
section, unmodified in content (only the frontmatter `sources` list gained pointers to this section's
artifacts, which live under their OWN `e2b-batch2b-*` filenames to avoid touching the already-merged
`e2b-batch2-*` files).

### Sibling-worktree collision — full transparency

This session and the one that authored the batch-2 section above landed in the **same worktree/branch**
(`agent/air-m5/ops/e2b-batch2`, deterministic from `scripts/agent_start.py --lane ops --task-id
e2b-batch2`) at overlapping times — a genuine cicatrix-family-#5 sibling-race, not a hypothetical one.
Sequence, reconstructed from `git reflog` + this session's own tool-call record:

1. This session created the original worktree, wrote its own 25-query selection and a driver script,
   and started a background run.
2. Partway through (after ~10 of the 25 queries had completed and been durably appended to that
   worktree's `e2b-batch2-response-log.jsonl`), the OTHER session landed in the identical worktree,
   judged this session's live, still-running background process an "unowned, orphaned (PPID 1)"
   abandoned attempt (it was not orphaned — PPID 1 reparenting is a normal consequence of a
   backgrounded `&` process whose parent shell tool call already returned; the process was alive and
   owned by this session the whole time), reset the branch to a fresh `origin/main`, wrote its own
   9-query selection, ran its 9 queries, and **overwrote** the response-log file with a file containing
   only its own 9 records before drafting its claims and merging PR #4258.
3. This session's background process, still running, continued appending its own remaining ~20 records
   (queries #11-25 plus retries) onto that now-9-line file with `append_jsonl` (open-mode `"a"`, per
   `nb2_query.py` — never truncates). This is why the first 10 records this session actually obtained
   (`E2B2-T5-001/002/003`, `E2B2-T8-001/002`, `E2B2-T11-001`, `E2B2-T1-BRIDGING`, `E2B2-T1-E31J`,
   `E2B2-T1-E31BC`, `E2B2-T1-E31DE`) were **overwritten and permanently lost as raw text** by the
   sibling's reset — though this session's own run-summary (written by its own script at the end of its
   run, independent of the log file) durably recorded that all 10 DID return `status=OK` at the time
   they were asked, which is why they are re-run rather than treated as failures below.
4. **No destructive action was taken against the sibling's work in response** — nothing of theirs was
   discarded, reset, or rewritten; PR #4258 merged untouched. Once #4258 merged (before this session's
   own work was ready), a fresh worktree/branch (`agent/air-m5/ops/e2b-batch2b`) was created from
   updated `origin/main` per the dispatcher's instruction, and this EXTENSION lands as an additive edit
   to the (now-merged) files, with its own supporting artifacts under `e2b-batch2b-*` filenames so a
   third collision on the same filename cannot recur.

### Recovery re-run — 10 queries, honestly labeled

`E2B2-T5-001`, `E2B2-T5-002`, `E2B2-T5-003`, `E2B2-T8-001`, `E2B2-T8-002`, `E2B2-T11-001`,
`E2B2-T1-BRIDGING`, `E2B2-T1-E31J`, `E2B2-T1-E31BC`, `E2B2-T1-E31DE` were **re-issued verbatim**
(`tools/run_e2b_batch2b_recovery.py`) after the collision, appended to `e2b-batch2b-response-log.jsonl`.
**These are RE-RUNS, not the original series** — the append-only guarantee `nb2_query.py`'s own module
docstring describes ("Append-only. Never rewrites the file, never truncates") was violated once on this
branch, by the sibling's file-level overwrite (a script-level overwrite outside `nb2_query.py`'s own
writer, not a defect in that writer itself) — flagged here rather than presented as an unbroken chain.
All 10 re-runs returned `status=OK` on the first attempt. The original attempt's run-summary entries
(also `status=OK`, `attempt=1`, timestamped before the collision) are the only surviving evidence the
FIRST attempt succeeded — the raw answer TEXT from that first attempt is unrecoverable; the claims below
are drawn from the RE-RUN text only.

### Query execution summary (this EXTENSION)

25-query plan (family-grouped "doctrine-lite" 5-point queries for the T1 gap, the fused-bank's own
narrow T5/T8/T11 cross-cutting queries verbatim, and 5 pinpoint-hunt probes for CF-7/8/10/12) + 10
recovery re-runs = **35 live query attempts this session**. Combined with 5 in-run retries
(`E2B2-T1-E31FGH`, `E2B2-T1-E30`, `E2B2-T1-D1D2`, `E2B2-CF8-A` each timed out once and succeeded on
retry, and `E2B2-T1-C2` timed out on its retry too), the session used **40 of its `<=40` live-query
budget and 5 of its `<=5` retry budget — exactly at both caps, not comfortably under either one**. C2's
own retry IS the 5th and final retry that exhausted the retry budget (named explicitly in the C2 section
below, not omitted from the count). Citation audit (`e2b-batch2b-citation-audit.json`, run this session
over this EXTENSION's own 30-record log): **20 `VERIFIED`, 3 `PROSE_ONLY`, 6 `SKIPPED_TRANSPORT_ERROR`
(the 4 first-attempt timeouts + the 2 `E2B2-T1-C2` timeouts), 1 `NOT_COMPILABLE`** (`E2B2-T11-001` —
several bracket pointers beyond `[54]` don't resolve against the structured citations map; the claim
below is downgraded to `VERIFIED-WITH-CAVEAT` for this reason, not treated as clean `VERIFIED` despite
the rich, well-cited-looking prose). Combined with the already-merged batch-2 section's own 9/9
`VERIFIED`, the two files together (`e2b-batch2-citation-audit.json` + `e2b-batch2b-citation-audit.json`)
cover the full 39-record picture across both PRs.

### Claims by product (this EXTENSION)

**Method note**: family-grouped queries return one shared answer covering several products — claims
below are split per product but a shared `Provenance` query_id may support multiple products' claims.
Per this task's binding rule, `doctrine-lite`/`pinpoint-hunt` answers with no structured citation
resolution are `VERIFIED-WITH-CAVEAT`, never plain `VERIFIED` — the claim `state` field uses ONLY this
ledger's own Method §2 vocabulary (`VERIFIED`/`CONFLICTING`/`STALE`/`UNVERIFIED`/`SUPERSEDED`/
`VERIFIED-WITH-CAVEAT`); the citation-audit's own separate verdict vocabulary (`PROSE_ONLY`,
`NOT_COMPILABLE`, etc.) is cited in the `Source`/parenthetical line as the REASON for a
`VERIFIED-WITH-CAVEAT` state, never substituted for the state itself.

#### BRIDGING — Izin Tinggal Peralihan (onshore transitional stay permit)

**Coverage state: was TOTAL GAP after batch-1 (both attempts timed out there); now answered.**

- **CL-BRIDGING-01 — category/purpose.** BRIDGING is legally the "Visitor Stay Permit in the framework
  of Transition of Immigration Stay Permit" (*Izin Tinggal Kunjungan dalam rangka peralihan Izin Tinggal
  Keimigrasian*) — a procedural bridge preventing overstay while a new onshore stay-permit application
  is processed (VITAS/ITAS/ITAP transitions), not a stay-permit category in its own right.
  - Source: `Permenkumham No. 11 Tahun 2024` (per the answer's own citation, passage 183/535);
    `Permenkumham_27_2021_Visa.pdf` (passage 149/457/865). Citation-audit verdict: `PROSE_ONLY` (no
    structured citations/references field, pointers not independently resolvable).
  - **State: VERIFIED-WITH-CAVEAT.** Products: BRIDGING. Provenance: `E2B2-T1-BRIDGING`.
- **CL-BRIDGING-02 — activities are DELEGATED, not enumerated in primary law.** Permitted activities are
  limited to "certain activities" (*kegiatan tertentu*) whose specific definition the primary
  regulation delegates to the Director General of Immigration, not the statute itself — i.e. the
  activity boundary is not self-executing from `Permenkumham 11/2024` alone; local labor, commercial
  sales, and compensation from an Indonesian party are prohibited by the general cross-cutting rule
  (matching batch-1's T3-series findings), not a BRIDGING-specific carve-out.
  - Source: `Permenkumham No. 11 Tahun 2024` (passage 534/928).
  - **State: VERIFIED-WITH-CAVEAT.** Products: BRIDGING. Provenance: `E2B2-T1-BRIDGING`.
- Note: the answer did not fully cover points 3-5 (entry/duration, extension/conversion, sponsor)
  within its response length — this closes the coverage-matrix T1 gap (an answer now exists where none
  did) but does NOT constitute a complete doctrine card; a follow-up narrower query on BRIDGING's
  duration/extension/sponsor specifically is recommended before E5 treats this product as fully cured.

#### E31J — sibling reunification (minor with sibling ITAS/ITAP holder)

- **CL-E31J-01 — category/purpose.** `Permenkumham 11/2024` Art. 33(2)(h)(9) (new provision, in force
  3 May 2024) and Art. 50A(1) introduce a family-reunification index for a foreign minor (<18, unmarried)
  joining a sibling (*saudara kandung*) who holds an ITAS or ITAP; `Kepmen M.IP-08.GR.01.01/2025`
  codifies this under index **E31J**.
  - Source: `Permenkumham No. 11 Tahun 2024` Art. 33(2)(h)(9), Art. 50A(1); `Kepmen
    M.IP-08.GR.01.01/2025`.
  - **State: VERIFIED.** Products: E31J. Provenance: `E2B2-T1-E31J`.
- **CL-E31J-02 — activities.** Permitted: tourism, shopping, visiting family/friends, entry/exit during
  MERP validity. Prohibited: overstaying, selling goods/services, receiving compensation/wages/
  commission from an Indonesian person or entity.
  - Source: `Kepmen M.IP-08.GR.01.01/2025`.
  - **State: VERIFIED.** Products: E31J. Provenance: `E2B2-T1-E31J`.
- Note: this closes batch-1's "genuine content gap" flag on E31J (its dedicated `VO-FUSED-T1-030`-family
  doctrine card had never returned an `OK` answer before this EXTENSION).

#### E31B / E31C / E31D / E31E / E31F — FOURTH+FIFTH recurrence of the E31-index-letter primary-law-vs-
internal-DB mismatch (NOT a new production-risk finding — see disposition)

Three family-grouped answers (`E2B2-T1-E31BC`, `E2B2-T1-E31DE`, `E2B2-T1-E31FGH-RETRY`) all
independently, unprompted, surface the SAME internal-database index-letter confusion e2a's **CF-5** and
batch-1's **CF-9** already identified and disposed of:

- **Primary law** (per all three answers, citing `Permenkumham 22/2023`/`11/2024` and `Kepmen
  M.IP-08.GR.01.01/2025`): **E31B** = foreign spouse of an ITAS/ITAP holder; **E31C** = foreign child born
  of a marriage between a foreign national and an Indonesian citizen (WNI); **E31D** = foreign child of
  a foreign national married to a WNI (a closely related but distinct sub-case from E31C's own answer's
  framing — the two family-grouped answers are not perfectly harmonized on the E31C/E31D boundary
  either, logged as-is, not smoothed); **E31F** = foreign child reuniting with an Indonesian-citizen
  parent (`Penyatuan Keluarga`).
- **Internal DB** (`nb2_visa_types_final.txt`, per all three answers): **E31B** = child of KITAS/KITAP
  holder; **E31C** = parent of KITAS/KITAP holder; **E31D** = "Spouse KITAS (KITAS Holder Spouse)";
  **E31F** = ALSO "Spouse KITAS (KITAP Holder Spouse)" — the SAME internal-DB label the E31D answer
  independently gave, i.e. the internal DB attaches the spouse label to two different index letters
  across two independently-run queries, which is itself additional evidence of how unreliable that
  internal artifact is (not a claim that BOTH E31D and E31F are "really" the spouse index — neither is,
  per primary law).
- **CL-E31BCDEF-01 — the mismatch is CONFIRMED to recur a fourth/fifth time, independent of e2a and
  batch-1's own occurrences.** New EVIDENCE strengthening the case that `nb2_visa_types_final.txt`
  itself carries a genuine, recurring internal-artifact defect (now FOUR independent query rounds
  reproduce it, across FIVE affected index letters: B/C/D/E/F) — but per CF-5's already-checked
  disposition (verified directly against `seed_visa_types_complete_2026.py` and
  `rulepack-prod-007.source.json`, both showing the correct `E31B=spouse/E31D=stepchild/E31E=child-of-
  foreigner` production mapping), **production is unaffected**. This entry does not re-open CF-5/CF-9's
  disposition, only adds a fourth/fifth data point to it.
  - Source: `E2B2-T1-E31BC`, `E2B2-T1-E31DE`, `E2B2-T1-E31FGH-RETRY` (all `VERIFIED`-audited).
  - **State: CONFLICTING (NB-2-source only, production unaffected — see CF-5/CF-9).** Products: E31B,
    E31C, E31D, E31F. Provenance: `E2B2-T1-E31BC`, `E2B2-T1-E31DE`, `E2B2-T1-E31FGH-RETRY`. Cross-ref:
    `e2a-conflict-report.md` CF-5, `e2b-batch1-conflict-report.md` CF-9.
- **CL-E31B-legal-01 — E31B activities/entry/duration (primary-law reading).** Multiple-entry, standard
  family-reunification activity set (tourism/shopping/family visits permitted; local employment/sales
  prohibited without a separate E23 work permit).
  - Source: `Permenkumham No. 22 Tahun 2023`/`11/2024` Pasal 33(2)(h)(2); `Kepmen
    M.IP-08.GR.01.01/2025`.
  - **State: VERIFIED-WITH-CAVEAT** (rests on the primary-law reading; see CL-E31BCDEF-01's internal-DB
    conflict). Products: E31B. Provenance: `E2B2-T1-E31BC`.
- **CL-E31D-legal-01 — E31D activities (primary-law reading, distinctive point).** Uniquely among the
  E31 family, the primary-law text for E31D permits informal self-employment/business activity to
  support the family's livelihood, EXCLUDING formal employment relationships with an Indonesian company
  or individual (`"Melakukan pekerjaan dan/atau usaha untuk memenuhi kebutuhan hidup ... di luar
  hubungan kerja..."`) — a narrower but real activity allowance most other E31 sub-indices' answers in
  this batch did not surface.
  - Source: `Permenkumham No. 11/2024` (per the answer's own inline citation).
  - **State: VERIFIED-WITH-CAVEAT** (primary-law reading; internal-DB conflict per CL-E31BCDEF-01).
    Products: E31D. Provenance: `E2B2-T1-E31DE`.

#### E31G / E31H — thin backfill (retry-recovered, response budget consumed by E31F)

- **CL-E31GH-01 — coverage-matrix-closing but THIN.** The retried (narrowed) `E2B2-T1-E31FGH-RETRY`
  answer's response budget was consumed primarily by E31F's detailed dual-framework analysis (see
  CL-E31BCDEF-01 above); E31G and E31H did not receive comparably detailed treatment in the same answer.
  **Recorded honestly as a THIN backfill, not a full doctrine card** — the coverage-matrix T1 gap is
  closed (an answer touching all three products exists) but E31G/E31H's specific category/purpose/
  activity content should not be treated as E31F-grade in the eventual doctrine-card build.
  - Source: `E2B2-T1-E31FGH-RETRY`.
  - **State: VERIFIED-WITH-CAVEAT (thin).** Products: E31G, E31H. Provenance:
    `E2B2-T1-E31FGH-RETRY`.

#### E30 / E30B — family-grouped, retry-recovered

- **CL-E30-03 — E30 family index structure, per this EXTENSION's own answer.** (renamed from
  `CL-E30-01` to avoid ID collision with batch1's distinct claim; states unchanged) `Kepmen
  M.IP-08.GR.01.01/2025` subdivides the E30 Student KITAS family, per `E2B2-T1-E30-RETRY`, into: E30A
  (primary/secondary education), E30B (higher education — diploma/sarjana/master/doktor), E30E (KEK-zone
  institution), E30F (student exchange); E30 itself is the generic parent index ("*Mengikuti
  pendidikan*").
  - Source: `Kepmen M.IP-08.GR.01.01/2025` (source ID 49, passage cited); `nb2_visa_types_final.txt`
    (source ID 120).
  - **State: VERIFIED-WITH-CAVEAT** — flagged, not smoothed: the already-merged batch-2 section's own
    `CL-E30F-01` above describes E30A differently, in passing, as "academic research" rather than
    "primary/secondary education." Neither this EXTENSION nor that section asked a dedicated E30A
    doctrine-card question — both descriptions are asides inside answers primarily about OTHER products
    (E30/E30B here; E30F there). This is a genuine, UNRESOLVED cross-document discrepancy about what
    E30A actually covers, surfaced by this EXTENSION's own adversarial pass (see below) — not silently
    harmonized in either direction. A dedicated E30A doctrine-card query is recommended before E5 treats
    either description as settled. Products: E30, E30B. Provenance: `E2B2-T1-E30-RETRY`.
- Note: the retried (narrowed) answer's response was cut off before reaching the "Attività Consentite"
  detail section for E30/E30B specifically — closes the T1 coverage gap but, like BRIDGING and
  E31G/E31H above, is a thinner-than-ideal doctrine-card input; flagged, not hidden.

#### E30E / E30F — cross-check against the already-merged sibling section's own dedicated E30E/E30F
doctrine-lite answers

- **CL-E30EF-01 — corroborates the already-merged section's CL-E30E-01/CL-E30F-01 category/purpose
  findings.** This EXTENSION's own `E2B2-T1-E30EF` answer (asked independently, before this session was
  aware of the merged `E2B2-E30E`/`E2B2-E30F` answers above) reaches the SAME category/purpose
  conclusion for both products (KEK-zone institution / student-exchange program respectively), citing
  the same primary sources (`Kepmen M.IP-08.GR.01.01/2025`, `Permenkumham 22/2023`/`11/2024`,
  `UU 63/2024`). Treated as independent corroboration, not double-counted as two separate facts.
  - Source: `E2B2-T1-E30EF` (`VERIFIED`-audited).
  - **State: VERIFIED** (corroborates the already-merged section's own `VERIFIED` claims above).
    Products: E30E, E30F. Provenance: `E2B2-T1-E30EF` (cross-ref merged `E2B2-E30E`, `E2B2-E30F`).

#### D1 / D2 / D12 — redundant with the already-MERGED E3a slice (PR #4250/#4251), noted not re-litigated

`git log origin/main` confirms PR #4250 ("E3a slice doctrine cards: D1/D2/D12/E31B/E31D") and #4251
("E3a CF-1 resolution fast-follow") are **already MERGED to main**, predating this EXTENSION — meaning
D1/D2/D12 (and E31B/E31D, covered above under the E31 mismatch instead) already have dedicated,
presumably more thorough doctrine-card content elsewhere in the repo. This EXTENSION's own
`E2B2-T1-D1D2-RETRY`/`E2B2-T1-D12` answers are recorded below for coverage-matrix bookkeeping and
cross-check value ONLY — not presented as the primary doctrine-card source for these three products.

- **CL-D1D2D12-XCHECK-01 — D1 duration/extension figures cross-check.** `E2B2-T1-D1D2-RETRY` (citation
  audit: `PROSE_ONLY`) cites `Permenkumham 11/2024` Pasal 7(4)/(5) (validity tiers, up to 10yr total)
  and Pasal 16(1)/(2) (first-time-applicant caps) for D1 multiple-entry visit visas — consistent in
  shape with this EXTENSION's own `E2B2-T5-001`/`E2B2-T5-003` cross-cutting entry-duration findings
  below, no contradiction found.
  - **State: VERIFIED-WITH-CAVEAT (PROSE_ONLY, cross-check value only — see E3a for the authoritative
    doctrine card).** Products: D1, D2. Provenance: `E2B2-T1-D1D2-RETRY`.
- **CL-D12-XCHECK-01 — D12 category/purpose cross-check.** `E2B2-T1-D12` (citation audit: `PROSE_ONLY`)
  confirms D12 = "Prainvestasi" (pre-investment) under `Kepmen M.IP-08.GR.01.01/2025` Category 7 and
  `Permenkumham 11/2024`, consistent with batch-1's own `VO-FUSED-T1-*` D12 findings — no contradiction
  found, cross-check only.
  - **State: VERIFIED-WITH-CAVEAT (PROSE_ONLY, cross-check value only).** Products: D12. Provenance:
    `E2B2-T1-D12`.

#### A1 / B1 — visa-free entry / visa-on-arrival

- **CL-A1B1-01 — category/purpose.** A1 (*Bebas Visa Kunjungan*): visa-free entry for tourism, personal
  development, sightseeing (incl. yachting), family visits, transit, business consultations/negotiations
  /contract-signing (no local work). B1 (*Visa Kunjungan Saat Kedatangan*/VoA): same activity envelope,
  issued electronically on arrival to eligible nationalities.
  - Source: `Permenkumham No. 22/2023` Art. 10 & 18 (A1); Art. 12 & 32 (B1 issuance mechanics); `Kepmen
    M.IP-08.GR.01.01/2025` Allegato Sez. A.1.
  - **State: VERIFIED.** Products: A1, B1. Provenance: `E2B2-T1-A1B1`.
- Note: consistent with this EXTENSION's own `E2B2-T5-001` finding (below) that A1/B1-class products are
  single-entry and a single exit permanently voids the stay permit.

#### C1 / C6 — visit visa (tourism / other)

- **CL-C1C6-01 — regulatory hierarchy identified, product-specific detail thin.** The answer opens with
  a correct, detailed source-hierarchy classification (`UU 6/2011` as amended by `UU 63/2024`/`PP
  45/2024`; `Permenkumham 22/2023`/`11/2024`; `Kepmen M.IP-08.GR.01.01/2025`; `Permenimipas 5/2025`) but
  the response was truncated before delivering C1/C6's own category/purpose/activity content in detail
  (cut off mid-table). **Recorded honestly as a coverage-matrix-closing but THIN answer**, not a
  complete doctrine card.
  - Source: `E2B2-T1-C1C6` (`VERIFIED`-audited — the source-hierarchy portion resolves cleanly even
    though the product-specific portion is thin).
  - **State: VERIFIED-WITH-CAVEAT (thin).** Products: C1, C6. Provenance: `E2B2-T1-C1C6`.

#### C2 — GENUINE GAP, both attempts timed out

**Coverage state: TOTAL GAP, honestly unresolved.** `E2B2-T1-C2` timed out on both the initial attempt
and its narrowed retry (`E2B2-T1-C2-RETRY`) — the only product in this EXTENSION's 25-query selection
with zero live-query budget remaining to spend on a third attempt. **C2's own retry (`E2B2-T1-C2-RETRY`)
IS the 5th and final retry that exhausted the global `<=5` retry budget** (the other 4 —
`E31FGH`/`E30`/`D1D2`/`CF8-A` — each succeeded on their own retry) — named explicitly here so the retry
count in the "Query execution summary" section above and this section agree exactly. C2 remains the sole
`PARTIAL` product in `coverage-matrix-after-batch2b.json` (6 of 7 topics answered, T1 pending).

- **CL-C2-GAP-01 — no claim can be authored for C2's doctrine-card content from this EXTENSION.**
  - Source: none (both attempts TIMEOUT). Products: C2. Provenance: `E2B2-T1-C2`,
    `E2B2-T1-C2-RETRY` (both `SKIPPED_TRANSPORT_ERROR`).
  - Note: batch-1's own coverage delta already flagged C2 as needing T1+T5; this EXTENSION's
    `E2B2-T5-002` (below) DID close C2's T5 gap — only T1 (doctrine-card) remains open for C2.

#### E28B / E28C — cross-check against the already-merged sibling section's own dedicated E28B/E28C
answers

- **CL-E28BC-XCHECK-01 — corroborates CL-E28B-01/CL-E28C-01 and strengthens CL-E28B-05/CL-E28C-05's
  threshold figures.** This EXTENSION's `E2B2-T1-E28BC` answer independently reaches the SAME
  category/purpose split (E28B = corporate/PT-PMA investor; E28C = pure portfolio investor) and cites
  the SAME `Permenkumham 11/2024` Pasal 39(2)/40(2) threshold articles as the already-merged section's
  dedicated answers above, with no contradiction found.
  - Source: `E2B2-T1-E28BC` (`VERIFIED`-audited).
  - **State: VERIFIED** (corroborates the already-merged section's claims). Products: E28B, E28C.
    Provenance: `E2B2-T1-E28BC` (cross-ref merged `E2B2-E28B`, `E2B2-E28C`, `E2B2-E28BC-XCHECK`).

#### E28D / E28F — cross-check against the already-merged sibling section's own dedicated E28D/E28F
answers (CF-13/CF-14)

- **CL-E28DF-XCHECK-01 — corroborates CF-13/CF-14's primary-law-vs-internal-DB conflict, no new fact.**
  This EXTENSION's `E2B2-T1-E28DF` answer independently surfaces the SAME primary-law-vs-internal-DB
  mismatch for both E28D and E28F that the already-merged section's `CF-13`/`CF-14` already document in
  detail — treated purely as corroboration, no new claim content extracted (the merged section's own
  CL-E28D-01/02/03 and CL-E28F-01/02/03/04 remain the authoritative claims for these two products).
  - Source: `E2B2-T1-E28DF` (`VERIFIED`-audited).
  - **State: VERIFIED** (corroborates already-merged CF-13/CF-14, no independent new claim). Products:
    E28D, E28F. Provenance: `E2B2-T1-E28DF` (cross-ref merged `E2B2-E28D`, `E2B2-E28F`,
    `E2B2-E28DF-XCHECK`).

#### Cross-cutting findings (T5/T8/T11 — fused-bank verbatim queries)

- **CL-XCUT-T5-01 — single- vs multiple-entry, per product class.** Per `E2B2-T5-001`'s answer, C-series
  (naming C1, C2, C7, C8, C12, C18, C22 explicitly) and B-series VoA (B1-B4) are single-entry: any exit
  permanently voids the stay permit (ITK). D-series (D1/D2/D12) are multiple-entry. **Products list below
  is scoped to exactly what the answer names** — C6 is NOT explicitly named in this answer's own text
  (it is covered instead by `E2B2-T5-002` below, which DOES name C6 directly), so C6 is excluded from
  this claim's Products list even though it is a C-series product, to avoid asserting a fact this
  specific answer did not actually state for C6.
  - Source: `Permenkumham 22/2023` Pasal 8(1)(a), Pasal 11; `Kepmen M.IP-08.GR.01.01/2025`.
  - **State: VERIFIED.** Products: A1, B1, B2, B3, B4, C1, C2, C7, C8, C12, C18, C22, D1, D2, D12.
    Provenance: `E2B2-T5-001`.
- **CL-XCUT-T5-02 — C-series extension mechanics.** 60-day initial stay, up to 2 extensions of 60 days
  each (max 180 days total); filing window opens 14 days before expiry; a timely-filed-and-paid
  extension application suspends overstay accrual even if approval lands after the prior permit's
  expiry; new period starts the day after the prior permit's expiry. This answer's own query scope was
  specifically C1/C2/C6 (see `e2b-batch2b-selection.json`), which is why C6 appears here despite not
  appearing in `CL-XCUT-T5-01` above — the two claims are scoped to what each SPECIFIC answer actually
  covered, not harmonized into one combined C-series list.
  - Source: `Permenkumham` Pasal 95 & 97 (per the answer's own citation).
  - **State: VERIFIED.** Products: C1, C2, C6. Provenance: `E2B2-T5-002`.
- **CL-XCUT-T5-03 — D-series re-entry clock resets on exit, no minimum time abroad required.** Each
  re-entry on a D-series multiple-entry visa opens a fresh per-entry stay window; no minimum period
  abroad is mandated by national law before re-entry, though the answer flags an OPERATIONAL (not
  legal) risk of entry-refusal profiling for frequent immediate re-entries (>3-4/year "border runs").
  - Source: `UU 6/2011`/`63/2024`; `Permenkumham 22/2023`/`11/2024`; `Kepmen M.IP-08.GR.01.01/2025`.
  - **State: VERIFIED.** Products: D1, D2, D12. Provenance: `E2B2-T5-003`.
- **CL-XCUT-T8-01 — blackout windows.** No specific "must not exit" legal blackout window was identified
  as product-general; the answer instead frames constraints operationally (pending-application timing,
  local Kanim enforcement patterns) rather than citing a specific statutory exit prohibition.
  - Source: `E2B2-T8-001` (`VERIFIED`-audited, but the answer's own content does not assert a clean
    product-specific blackout rule).
  - **State: VERIFIED-WITH-CAVEAT** (answer is grounded but does not deliver a crisp per-product
    blackout-window table the query asked for). Products: ALL. Provenance: `E2B2-T8-001`.
- **CL-XCUT-T8-02 — KITAS without MERP: post-reform vs pre-reform.** Post-UU-63/2024 KITAS: MERP is
  automatically integrated at issuance — exiting without a separate MERP is not legally possible to get
  wrong. Pre-reform KITAS: exiting without the (then-separate) MERP document caused the KITAS to lapse
  immediately, with NO legal restoration path other than a fresh offshore VITAS application. Exempt:
  dual-citizen minors entering on an Indonesian passport with `Fasilitas Keimigrasian`.
  - Source: `UU No. 63/2024` (per the answer's own citation).
  - **State: VERIFIED.** Products: E28, E31, E33 (family-wide, per query scope). Provenance:
    `E2B2-T8-002`.
- **CL-XCUT-T11-01 — RPTKA filing.** RPTKA (Rencana Penggunaan Tenaga Kerja Asing) replaced IMTA
  entirely under `PP 34/2021` — RPTKA approval + DKP-TKA payment is now the sole work authorization,
  feeding E23 visa/KITAS issuance. Must be filed by the Indonesian employer (PT, PT PMA, CV, Yayasan,
  government body, or foreign representative office) — never by the foreign worker personally.
  - Source: `PP 34/2021` Pasal 1 angka 2 (per the answer's own citation).
  - **State: VERIFIED-WITH-CAVEAT** (citation audit verdict `NOT_COMPILABLE` — several bracket pointers
    beyond `[54]` in the fuller answer do not resolve against the structured citations map; the
    passages actually read and quoted above use pointers `[1]-[6]`, all resolved, but the answer's
    unresolved tail is flagged rather than silently ignored). Products: E23. Provenance:
    `E2B2-T11-001`.

### CF-7 / CF-8 / CF-10 / CF-12 pinpoint-hunt outcomes

Full dispositions are written in this EXTENSION's own conflict-report addendum
(`e2b-batch2-conflict-report.md`'s new "## EXTENSION — CF-7/8/10/12 pinpoint-hunt outcomes" section) to
keep this ledger's per-product structure intact. Summary for readers of this file: **all four resolve
cleanly with article-level primary-law pinpoints found this session** — CF-7 (E33E age = 55, per
`Kepmen M.IP-08.GR.01.01/2025` + `Permenkumham 11/2024` Pasal 61/62/101, superseding the pre-2024-reform
60-year figure that Bali Zero's own guide never updated); CF-8 (E33/E33E KITAP conversion = 3 years per
`Permenkumham 22/2023` Pasal 179(1), NOT Pasal 76 which governs cancellation only); CF-10 (E28A KITAP
conversion = 3 years per `PP 31/2013`/`Permenkumham 22/2023` Pasal 179(1)/173(c)); CF-12 (E28G is
legally a foreign-parent-company-representative role per `Kepmen M.IP-08.GR.01.01/2025`, not a Golden
Visa tier — independently corroborating the already-merged section's own `CL-CROSS-E28-01` above). None
of the four "5-year"/"60-year"/"5+ years" operational-guide figures is called erroneous outright — each
is named as what it demonstrably is (a stale or prudential figure that no longer/never matched the
governing article), per the task's hard honesty rule against dishonest one-sided framing on a resolved
conflict's losing side. **Note the terminology used by the already-merged section's own CL-CROSS-E28-01
above** ("still ESCALATED there per that batch's own disposition") **and this EXTENSION's own wording
below (batch-1's original CF-12 disposition was "OPEN, escalate to E5/operator")** — "ESCALATED" and
"OPEN (escalate-flagged)" describe the SAME batch-1 state, not two different ones; this EXTENSION uses
"OPEN" consistently below to match batch-1's own literal disposition text.

### Coverage outcome (this EXTENSION, for OD-4)

Combined with the already-merged batch-2 section above and batch-1: **26 of the 27 `PARTIAL` products
from `coverage-matrix-after-batch1.json` now reach `ALL_TOPICS_ANSWERED`** in
`query-bank/coverage-matrix-after-batch2b.json` (built this session, combining batch-1's per-topic
credit with both this EXTENSION's and the already-merged section's batch-2 answers) —
`coverage-matrix-after-batch2b.json`'s own `matrix` object is the checkable artifact for this arithmetic,
not this prose sentence alone. **C2 is the sole remaining `PARTIAL` product** (6/7 topics; T1
doctrine-card content genuinely absent — both attempts timed out). Several of the 26 "closed" products
carry an honest caveat (thin/PROSE_ONLY/redundant-with-E3a) rather than a clean full doctrine card — read
the per-product sections above, not just the coverage-state label, before treating any of them as
build-ready for E5.

### Adversarial review (this EXTENSION + re-covering the already-merged CF-13/14/15 section)

Per this task's binding constraint, the adversarial pass below was scoped to cover **this EXTENSION's
own new content AND the already-merged batch-2 section above (including CF-13/14/15)** — no section of
this combined file is adversarial-review-exempt just because it was authored by a different session and
already merged.

**Round 1** — `kimi -m kimi-code/k3`, instructed "NON usare sub-agent: analizza direttamente il testo",
run against the FULL combined file (already-merged batch-2 section + this EXTENSION, concatenated) plus
the companion conflict report, internal-coherence-only scope (no NB-2/tool access), 8-minute timebox.
**Killed at the timebox before delivering a formatted final verdict** — the process was still working
through its analysis when killed, same failure mode as batch-1's own Round 1. Per that same precedent
(batch-1's Round 1 killed-but-partial output was still used, not discarded), this session read the
partial stdout transcript directly and self-cured every concrete, unambiguous defect it had already
surfaced before being killed, rather than fabricating a clean pass or discarding a substantially-complete
review:

| # | Finding (extracted from Kimi's killed-mid-analysis transcript) | Disposition |
|---|---|---|
| 1 | "35 live query attempts... well inside the `<=40` budget" is numerically misleading — 35 + 5 retries = 40, exactly AT the cap, not "well inside" it | **FIXED** — Query execution summary above now states "used 40 of its `<=40` live-query budget and 5 of its `<=5` retry budget — exactly at both caps, not comfortably under either one" |
| 2 | The C2 section's retry-exhaustion parenthetical named only 4 retries (`E31FGH`/`E30`/`D1D2`/`CF8-A`), omitting C2's own retry as the 5th — inconsistent with the summary section's own list of 5 retries that DOES include C2 | **FIXED** — C2 section now explicitly states "C2's own retry (`E2B2-T1-C2-RETRY`) IS the 5th and final retry" |
| 3 | The original CF-12-UPDATE draft (conflict-report EXTENSION) described "Rp 5 miliar+" as "E28F's real-estate-investor threshold" in a way readable as asserting it a REAL, legitimate E28F threshold — but CF-14 (already-merged section) establishes E28F's ACTUAL primary-law meaning is IKN branch/subsidiary, and Rp 5 miliar+/real-estate is the INTERNAL DB's mismatched/disputed label for E28F, not a confirmed real threshold | **FIXED** — conflict-report EXTENSION's CF-12 UPDATE reworded to say the figure "belongs to E28F's INTERNAL-DB label (itself CF-14's own contested mismatch, not a confirmed real E28F threshold)" rather than presenting it as settled fact |
| 4 | "ESCALATED" (already-merged section's own CL-CROSS-E28-01 wording) vs "OPEN" (this EXTENSION's own wording) for batch-1's CF-12 disposition risked reading as two different claimed prior states | **FIXED** — added an explicit note above (CF-7/8/10/12 pinpoint-hunt outcomes section) clarifying both terms describe the same batch-1 disposition, quoting batch-1's own literal text ("OPEN, escalate to E5/operator") |
| 5 | `CL-BRIDGING-01`'s original draft used `State: PROSE_ONLY / VERIFIED-WITH-CAVEAT` — mixing the citation-audit's own verdict vocabulary into the claim `state` field, which this ledger's Method §2 explicitly reserves for a separate fixed vocabulary | **FIXED** — state field now reads plain `VERIFIED-WITH-CAVEAT`; `PROSE_ONLY` moved to the Source line as the stated REASON for the caveat |
| 6 | `CL-E30-03` (this EXTENSION; renamed from `CL-E30-01` to avoid an ID collision with batch1's distinct E30 validity-tiers claim) describes E30A as "primary/secondary education"; the already-merged section's own `CL-E30F-01` describes E30A, in passing, as "academic research" — a genuine unflagged cross-document contradiction about what E30A covers | **FIXED, not silently resolved** — `CL-E30-03` now states this discrepancy explicitly and recommends a dedicated E30A doctrine-card query rather than asserting either description as settled |
| 7 | `CL-XCUT-T5-01`'s `Products` field originally included C6 and A1 without the narrative text explicitly naming them, while `CL-XCUT-T5-02` separately covers C6 — risk of double-scoping/over-claiming beyond what each specific answer actually said | **FIXED** — `CL-XCUT-T5-01`'s Products list now excludes C6 (moved exclusively to `CL-XCUT-T5-02`, which DID ask about C6 specifically) with an explicit scoping note; A1's coverage is explained via its own cross-reference note under `CL-A1B1-01` instead of silently folded into the T5-01 Products list |

No finding required reversing a claim's `state` from `VERIFIED` to something weaker, or discarding a
source — all 7 were framing/scoping/wording precision fixes, applied against this session's own raw
JSONL/citation-audit evidence, not narrative repair alone. This EXTENSION's own text is the only content
edited; the already-merged batch-2 section above (including CF-13/14/15) required NO changes — Kimi's
partial transcript, read in full, raised no unresolved defect against that section specifically before
being killed (it re-confirmed several of that section's own prior-round fixes as still holding, e.g. the
"three of six" conflict count and the CF-13 CROSS-TIER heading correction).
