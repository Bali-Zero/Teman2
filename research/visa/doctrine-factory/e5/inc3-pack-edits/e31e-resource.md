---
adversarial_review: codex
date: 2026-08-19
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/sources/freshness-recheck-2026-08-16.md
    note: "QW-5 record #10 — ecd22722 flagged CHANGED, sole source_ref for both HARD_FILTER rules, live page found not to support either fact"
  - path: research/visa/doctrine-factory/claims/e2b-batch1-claim-ledger.md
    note: "CL-E31E-01 — the pinpoint claim, Permenkumham 22/2023 Pasal 33 ayat (2) lettera h angka 5"
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
    note: "source_records array — c9e6f0e4 (Permenkumham 22/2023, IMPLEMENTING_REGULATION, VERIFIED) already in the pack, previously cited only for E30 rules"
  - path: research/visa/doctrine-factory/cards/E31E.md
    note: "§3.3/§4/§7 — names the freshness residual as the card's #1 priority claim gap"
discovered_by: agent.air-m5.backend-rag.visa-e5-seq9-implementer-b
adversarial_review: none (single-implementer artifact, prepared for CP3 review)
---

# E31E re-sourcing — `hf.e31e-adult-excluded` / `hf.e31e-married-excluded` — GROUNDED (not OPEN)

## The defect

Per QW-5 record #10 (`freshness-recheck-2026-08-16.md`), the live E31E page
(`ecd22722-3e42-5808-be18-45fbb7d8e9c5`, `https://www.imigrasi.go.id/wna/daftar-visa-indonesia/
E31E`) is the SOLE `source_ref` for both `hf.e31e-adult-excluded` (`REQ_UNDER_18`, EXCLUDE if
age>=18) and `hf.e31e-married-excluded` (`REQ_UNMARRIED`, EXCLUDE if `marital_status != SINGLE`)
— two `safety_critical: true` HARD_FILTER rules — but the page's content does not corroborate
either the under-18 or the unmarried requirement.

## Re-verification (this session, live, 2026-08-19 — not carried forward from QW-5 unexamined)

Fetched `https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31E` fresh this turn. Result: no
age requirement stated, no marital-status requirement stated for the child applicant. The page
DOES state the parent-sponsor requirement verbatim: *"Izin Tinggal Terbatas/Izin Tinggal Tetap
atau Visa Tinggal Terbatas milik orang tua yang masih berlaku"* — confirming QW-5's finding still
holds today and confirming the page continues to support `el.e31e-sponsor-itas-itap` /
`el.e31e-child-itas-support` (see `freshness-2026-08-19.md` for the full freshness writeup and
timestamp).

## The claim that grounds under-18/unmarried

**`CL-E31E-01`** (`e2b-batch1-claim-ledger.md:277-291`), state **VERIFIED-WITH-CAVEAT**
(caveat is the SAME freshness flag being cured here, not a separate doctrinal weakness). Pinpoint,
quoted verbatim in the ledger: **`Permenkumham No. 22 Tahun 2023, Pasal 33 ayat (2) lettera h
angka 5`** — *"anak kandung yang belum berusia 18 (delapan belas) tahun dan belum kawin..."*
("biological child who is not yet 18 (eighteen) years old and not yet married...") — this single
clause grounds BOTH facts (`REQ_UNDER_18` and `REQ_UNMARRIED`) simultaneously. Provenance:
`VO-FUSED-T13-003`, `VO-FUSED-T14-005` (both VERIFIED-audited). Cross-corroborated by
`CL-CROSS-08` (`e2b-batch1-claim-ledger.md:555-568`, state VERIFIED), which independently cites
the same age-<=18-and-unmarried gate for the E31/E31B/E31E/E31J family from a second source
(`VO-FUSED-T10-009`, "Sezione 1.2 — KITAS Ricongiungimento Familiare per Figli Minori").

## The source_record: already in the pack, previously used only for E30

`rulepack-prod-007.source.json`'s `source_records` array already carries
`c9e6f0e4-5e84-572d-b1ca-e4e11ab50c24` — *"Permenkumham Nomor 22 Tahun 2023 tentang Visa dan Izin
Tinggal"*, `authority_type: IMPLEMENTING_REGULATION`, `status: VERIFIED`, `document_number:
"22/2023"`, `canonical_url: https://peraturan.bpk.go.id/Download/330147/Permenkumham%20Nomor%20
22%20Tahun%202023.pdf` — the EXACT regulation `CL-E31E-01` cites. This record is currently
referenced only by 8 E30-family rules (`el.e30-student-support`, `el.e30-living-cost-2000.{e30,
e30a,e30b}`, `el.e30-passport-validity.{e30,e30a,e30b}`, `el.e30b-izin-belajar` — verified by
grepping the pack this turn) with `locators` naming Pasal 42/105/113, three DIFFERENT articles of
the same regulation. It has zero references from any E31E rule as of seq-7.

**Disposition: GROUNDED, not OPEN.** This is a strictly-superior citation to `ecd22722` for these
two facts — an `IMPLEMENTING_REGULATION` primary source vs. a portal page the freshness-recheck
found does not support the facts at all, and it is an EXISTING pack record (no new source_record
object needs constructing/inventing). The concrete edit — append `{"kind": "ARTICLE", "value":
"Pasal 33"}` to `c9e6f0e4`'s `locators` (consistent with the pack's existing pattern of one record
accumulating every article it backs across its citing rules), then point
`hf.e31e-adult-excluded`/`hf.e31e-married-excluded`'s `source_refs` at `c9e6f0e4` instead of
`ecd22722` — is written out in full in `e31e-source-edits.json` in this directory.

## What this does NOT do

This is a sourcing-only fix (Step 4 scope). It does not touch either rule's `when` clause. In
particular, `hf.e31e-married-excluded`'s actual predicate (`marital_status != SINGLE`, which also
excludes DIVORCED/WIDOWED — not literally "married", as `E31E.md` §3.2/§4 already flags) is
UNCHANGED here — that is a rule-logic precision question the doctrine card raised separately, and
CL-E31E-01's "belum kawin" ("not yet married") wording arguably supports the `!= SINGLE` reading
being *correct* (DIVORCED/WIDOWED are also "not unmarried" in the ordinary sense), but this is not
re-adjudicated in this Step-4 artifact — noted for CP3, not decided here.

## Adversarial review

Reviewed 2026-08-19 by two cross-family refuter seats (Codex GPT-5.6 high; Kimi K3) as part
of the whole seq-9 fold working tree — both DROVE the real evaluator rather than reading the
diff. Findings touching this artifact and their dispositions are consolidated in
`../2026-08-19-e5-increment3-fold.md` §Adversarial review (fold doc); no finding against this
artifact survived undisposed.
