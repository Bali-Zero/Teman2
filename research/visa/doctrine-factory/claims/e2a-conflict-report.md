---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/claims/e2a-claim-ledger.md
  - path: research/visa/doctrine-factory/source-hierarchy-draft.md
    note: "binding precedence rule (§3) this report applies"
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
adversarial_review: kimi-k3
---

# E2a conflict report — D1/D2/D12 + E31B/E31D slice

Applies `source-hierarchy-draft.md` §3 (cross-level → loser `SUPERSEDED`; same-level disagreement → both
`CONFLICTING`, human-escalated) to every divergence found while building `e2a-claim-ledger.md`.

## Findings

### CF-1 — D2 annual cumulative cap (180 days/calendar year): PARTIALLY RESOLVED, category error re:
annual-vs-per-stay; DISSENTING CITATION on extension count — escalated, not resolved

**Live query `E2A-D2-DURATION` resolves this**, with a verbatim primary-law pinpoint: Permenkumham No.
11/2024 (amending 22/2023), Pasal 95(3): *"Perpanjangan Izin Tinggal Kunjungan ... diberikan untuk jangka
waktu paling lama 60 (enam puluh) Hari setiap kali perpanjangan ... dengan ketentuan keseluruhan Izin
Tinggal di Wilayah Indonesia tidak lebih dari 180 (seratus delapan puluh) Hari."* The answer states
explicitly: *"La legge nazionale primaria non prevede alcun limite cumulativo di 180 giorni all'anno per i
visti a ingressi multipli D2 ... La limitazione dei 180 giorni si applica esclusivamente alla durata del
singolo soggiorno continuativo in-country (60 giorni iniziali + 2 estensioni da 60 giorni)."* The original
internal-guide source (`0c22e859-...`, `visto_d2_d12_multiplo_guida_2025.txt`) that raised the "annual
cumulative" framing was IMPRECISE, not wrong on the number — 180 is correct, but it is a **per-continuous-
stay ceiling (60 base + up to 2×60 extensions), never an annual/calendar aggregate**.
**Residual finding, NOT silently smoothed over**: the SAME batch's `E2A-D12-VS-D2` comparison-table answer
independently states, in an unlabeled cell with no verbatim citation, *"Calendar-Year Cumulative Cap:
Maximum 180 Days cumulatively in any single calendar year"* for D2 — repeating the imprecise framing this
finding just resolved.

**Corrected disposition (post-adversarial-review, kimi-k3):** the previous version of this finding invoked
"source-hierarchy §3.1.3, resolved... on pinpoint strength" as though the hierarchy doctrine authorized a
pinpoint-citation tiebreaker for same-tier disagreement. It does not — `source-hierarchy-draft.md` §3.1.3
states same-level source disagreement is **never** resolved automatically; it always produces `CONFLICTING`,
human-escalated, with no pinpoint-strength exception. That framing was invented, not hierarchy-sanctioned,
and is retracted here.

On reflection this is not actually a cross-authority-level conflict in the §3 sense at all: both competing
answers (`E2A-D2-DURATION` and `E2A-D12-VS-D2`) are NB-2 LLM outputs referencing the same underlying
Permenkumham 11/2024 instrument, not two different-authority SOURCES per §1's 7 levels — so §3 does not
strictly govern this disagreement either way; it governs disagreement between sources, not between two
same-tier NB-2 answers of differing citation completeness. The verbatim-quoted, article-and-paragraph-
pinpointed answer (`E2A-D2-DURATION`, Pasal 95(3)) is treated as the operative doctrine for this ledger's
`CL-D2-03` because it carries a checkable primary-law citation the dissenting comparison-table cell
(`E2A-D12-VS-D2`) lacks — but this is now marked **NOT hierarchy-resolved, escalated for human/E3a review**,
not a closed conflict.

**Additional finding from this review, logged not silently picked**: the two answers disagree not only on
annual-vs-per-stay framing but also on the **number of extensions**: `E2A-D2-DURATION` implies up to 2×60-day
extensions (60 + 2×60 = 180), while `E2A-D12-VS-D2` states "one 60-day extension" only. Both readings total
180 days but disagree on extension count — this is logged explicitly here, not silently resolved by picking
one reading.

**Status: VERIFIED-WITH-CAVEAT (CL-D2-03)** — the per-stay-vs-annual category distinction is CONFIRMED
correct (180 is never a calendar-year aggregate); the comparison-table cell's imprecision on THAT point is
resolved. But the underlying citation-quality disagreement itself, plus the 1-vs-2-extensions discrepancy,
is **ESCALATED, not resolved** — flagged for human/E3a review before seq-9 authoring. Whoever authors D2's
seq-9 fact/rule: do not port "calendar-year cumulative cap" language into a new rule/fact (that part IS
settled); DO carry forward the open extension-count question. No pack rule currently encodes even the
per-stay version — E4/E5 gap, not compiled here.

### CF-2 — D12 total-validity conflict (1/2y vs 1/2/5y; extension-per-request vs hard cap): RESOLVED,
category error, not a numeric contradiction

Flagged by the blueprint query banks as `[bench]` (unresolved) before this task started (QB2-08 in
output-B; VO-NB2-088 in output-C). **Live query `E2A-D12-DURATION` resolves this** with a verbatim
primary-law pinpoint, Pasal 95(4) of Permenkumham No. 11/2024 (equivalent provision already present in the
source 22/2023): *"Perpanjangan Izin Tinggal Kunjungan ... dalam rangka prainvestasi diberikan dengan
jangka waktu 180 (seratus delapan puluh) Hari setiap kali perpanjangan ... dengan ketentuan keseluruhan
Izin Tinggal di Wilayah Indonesia tidak lebih dari 12 (dua belas) bulan."* The "1/2 years" and "1/2/5
years" figures the blueprints flagged as conflicting are answering **two different questions**, not
disagreeing on one: (a) the **visa validity tier** (the multi-year window during which entries are
permitted — 1/2/5 years per Pasal 5C(4)-(5), up to 10 years with a prior Indonesian stay record) is a
property of the VISA itself; (b) the **per-entry stay-plus-extension ceiling** (180 days base + extension,
capped at 12 months/360 days total per single entry, Pasal 95(4)) is a property of each individual STAY
inside that window. The extension is confirmed strictly per-entry, never extending the visa's own multi-
year validity. **Status: VERIFIED (CL-D12-03).** No pack rule currently encodes the 360-day per-entry
ceiling (only the pre-extension `intent.stay_days<=180` gate exists in seq-7) — E4/E5 gap, not compiled
here.

### CF-5 — E31B/E31D "index swap" claim: checked against the live system, REFUTED for production

Two independent NB-2 answers this session (`E2A-E31D-REFUTER-PURPOSE-ONLY`, `E2A-E31D-DOCS`) both cite the
SAME NB-2 internal source (`nb2_visa_types_final.txt`) claiming an internal "Nuzantara dev / visa_types
table" swaps E31B/E31D relative to primary law (Kepmen 2025: E31B=spouse, E31D=stepchild). **Checked
directly against the live production system this session** (not taken on NB-2's authority per the
anti-hallucination discipline): `apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py:1172,1200`
(canonical 114-code catalog) and `rulepack-prod-007.source.json`'s `products[].names` both show the
CORRECT mapping. **Disposition: REFUTED for the live production system as of this session** — no swap
exists in the code path that actually serves users. The swap DOES appear to exist inside `nb2_visa_types_
final.txt`, an NB-2-ingested source — worth locating and correcting at the NB-2 source level (operator
housekeeping), or simply a stale/external artifact NB-2 ingested that was never our production catalog.
Not a P0/production finding; recorded so the same claim is never re-raised as new without this disposition.

### CF-6 — D1/D2/D12 `el.*` rules co-cite a CHANGED-flagged general source (`ee8fe5b8-...`), undeclared
in the requirement-bundle claims

Found in the adversarial review (kimi-k3), independently re-verified this session against the pack JSON
and `freshness-recheck-2026-08-16.md`: the active pack's D1/D2/D12 `el.*` requirement-bundle rules (18 rules
total — `el.d1-*` ×6, `el.d2-*` ×6, `el.d12-*` ×6) all co-cite NB-2/pack source `ee8fe5b8-b0b4-544a-bf9a-
fe53c3e316f2` (`imigrasi.go.id.izin-tinggal-keimigrasian`, the general "Izin Tinggal Keimigrasian" portal
landing page), confirmed live via `grep`/`python3 -m json` against `rulepack-prod-007.source.json`'s
`source_refs` arrays. QW-5's record #4 (`research/visa/doctrine-factory/sources/freshness-recheck-2026-08-16.md`)
flagged this exact source **CHANGED** the day before this task ran: the general landing page's own
"Persyaratan Dokumen" section lists only 3 generic items and does **not** carry the specific 6-month
passport / USD 2,000 / CV / itinerary / support-letter requirements it is co-cited for.

None of `CL-D1-02`/`CL-D2-02`/`CL-D12-02` in the claim ledger mention this co-citation or its CHANGED
status — those claims are backed by QW-5's *other*, product-specific records (#15 `ca5a2ce8`, #16
`d3ad622e`, #17 `5e64ec6b`, all CURRENT and verbatim-confirmed), so the claims themselves remain sound. But
the pack's rules also lean on the CHANGED general page as a co-source, and that co-citation was silently
uncarried into the ledger. **Disposition: CONFIRMED.** Logged here so seq-9 authoring doesn't silently carry
the CHANGED leg forward; matching one-line caveats added to `CL-D1-02`/`CL-D2-02`/`CL-D12-02` in
`e2a-claim-ledger.md`. Not a claim-ledger defect (the claims' own sourcing is CURRENT) — a pack-hygiene
finding for E4/E5: either re-point the D1/D2/D12 `el.*` rules' generic-source leg at a URL that actually
carries the requirement text, or drop `ee8fe5b8` as a co-source where the product-specific pages + primary
law already suffice (QW-5's own recommendation for record #4).

### CF-3 — Source-namespace distinction: NB-2 catalog ≠ RulePack `source_records`

Not a doctrine conflict but a structural finding that shapes how every claim above is graded: the NB-2
citation IDs returned by `nlm notebook query` (e.g. `0c7e2212-...`, `0c22e859-...`) live in NB-2's own
131-source catalog (`sources/nb2-source-snapshot-2026-08-15.json`), which is a **different UUID space**
from the pack's 30 `source_records` (e.g. `ca5a2ce8-...` for the D1 portal page). A claim's NB-2 citation
resolving against the frozen snapshot proves it is not hallucinated; it does not by itself establish the
claim's authority level under `source-hierarchy-draft.md` §1 — several NB-2 sources are `type:
generated_text` internal compilations, not the primary Kepmen PDF or an official portal page. Most claims
in the ledger state explicitly which of the two namespaces they rest on (see CL-D2-01/CL-D12-01 vs
CL-D1-02/CL-D2-02/CL-D12-02, the latter cross-referencing QW-5's independently-verified OFFICIAL_PORTAL
evidence instead of re-deriving it from NB-2); a handful of cross-cutting/comparison claims (CL-D1-03,
CL-D-COMPARE, CL-D-FUNDS, CL-E31B-PRINCIPAL) cite only a query_id provenance without a resolved source_id —
acceptable for claims synthesizing multiple narrower VERIFIED claims, but flagged here so it isn't mistaken
for a per-claim guarantee. **Recommendation for E3/E5**: when the claim ledger is consumed by the compiler,
the pinpoint field must carry both the NB-2 source_id (audit trail) and, where available, the pack
`source_record_id` it corroborates or is superseded by — never conflate the two namespaces silently.

### CF-4 — E31B/E31D fail-open: structural findings independent of NB-2 doctrine (cross-referenced, not new)

Both `CL-E31B-STRUCT` and `CL-E31D-STRUCT` in the ledger are mechanical findings about the pack's rule JSON
itself, re-derived independently this session (matches adjudication-report.md finding #5). They are not
"conflicts" in the source-hierarchy sense — no two sources disagree — but they gate what the refuter
queries (`E2A-E31B-REFUTER-SPONSOR-STATUS`, `E2A-E31D-REFUTER-PURPOSE-ONLY`) need to answer: a narrower
fact/enum cannot be authored for seq-9 without doctrine backing for what "verified" sponsor status or a
"proven" step-parent relationship actually requires. Listed here for completeness of the conflict-report
scope declared in the task brief ("conflict report ... dedup, source precedence, versioni, supersessions"),
not because they are precedence conflicts.

## Dedup

No duplicate claims found across the 27-query slice (canary + this task's bank): D1/D2/D12 purpose,
requirement-bundle and duration claims are each backed by exactly one NB-2 citation set per product, with
QW-5's OFFICIAL_PORTAL verification used as the independent corroboration channel rather than re-querying
NB-2 for facts QW-5 already verified live (CL-D1-02/CL-D2-02/CL-D12-02/CL-D12-04). No versioning/supersession
event applies within this slice — all cited sources are the current/only version in the frozen 2026-08-15
snapshot and the active seq-7 pack; no source in this slice's citation set is itself superseded by another
snapshot entry.

## Status

All 24 live queries for this task completed (21 `OK`, 3 `TIMEOUT` — see `e2a-claim-ledger.md` execution
summary). **CF-2 is RESOLVED** with a primary-law pinpoint (genuine category error, no fact actually in
dispute — validity tier vs. per-entry ceiling answer two different questions). **CF-1 is NOT resolved as of
this review's correction — it is ESCALATED**: the annual-vs-per-stay category confusion is confirmed and
cured, but the underlying same-tier citation disagreement between `E2A-D2-DURATION` and `E2A-D12-VS-D2`
(plus the newly-logged 1-vs-2-extensions discrepancy) is not something `source-hierarchy-draft.md` §3
mechanically resolves — it governs cross-authority-level source disagreement, not two same-tier NB-2
answers of differing citation completeness — so this is flagged for human/E3a review, not closed. CF-3
(namespace distinction) and CF-4 (E31B/E31D structural findings, cross-referenced not new) stand as written
above; CF-5 (index-swap claim) is REFUTED for production, recorded to prevent re-litigation; CF-6 (CHANGED
co-source `ee8fe5b8` on 18 D1/D2/D12 rules) is CONFIRMED, logged for E4/E5. **One same-level disagreement in
this slice (CF-1) is genuinely open** — the earlier claim that both same-level disagreements resolved
"per §3.1.3's own escalation path (a disagreement is escalated only when it CANNOT be resolved by pinpoint
strength — both could)" is retracted: that pinpoint-strength escalation exception is not in §3.1.3 and was
invented. CF-1 is the CONFLICTING/escalated case this slice does carry.

## Adversarial review

Cross-family review run via `kimi -p "REFUTA questo documento" -m kimi-code/k3` (generator≠grader). The
findings specific to this file (CF-1's false hierarchy-citation and the missing extension-count discrepancy;
CF-3's "every claim" overclaim; the undeclared CHANGED co-source now filed as CF-6) are dispositioned in the
full table in `e2a-claim-ledger.md`'s `## Adversarial review` section — not duplicated here. This file's own
CF-1/CF-3/CF-6 edits above ARE the cure for those findings. See the ledger for the complete 15-finding
disposition table and net count.
