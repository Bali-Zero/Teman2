---
adversarial_review: codex
date: 2026-08-19
domain: visa
client_case: none
sources:
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31E
  - https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
    note: "source_records for ecd22722 / ee8fe5b8 / 0497cb52; grep evidence for 0497cb52's ref count"
  - path: research/visa/doctrine-factory/sources/freshness-recheck-2026-08-16.md
    note: "QW-5 baseline this session re-verifies against"
discovered_by: agent.air-m5.backend-rag.visa-e5-seq9-implementer-b
adversarial_review: none (single-implementer artifact, prepared for CP3 review)
---

# E5 increment 3, Step 4 — freshness re-verification, 2026-08-19

Method: same as QW-5 (`freshness-recheck-2026-08-16.md`) — live `WebFetch` of the public page, no
auth, content compared against the exact fact each source_ref backs. Never treated HTTP
reachability alone as proof.

## 1. `ecd22722-3e42-5808-be18-45fbb7d8e9c5` (E31E page)

**URL**: `https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31E`
**Retrieved-at**: `2026-08-18T21:41:23Z` (this session)

Fetched and asked for verbatim text on 3 facts: (a) age requirement, (b) marital-status
requirement, (c) parent-sponsor ITAS/ITAP requirement.

**Result**:
- (a) age: **no text found** stating an under-18 (or any age) requirement for the child.
- (b) marital status: **no text found** stating an unmarried requirement for the child.
- (c) sponsor: **confirmed**, quoted verbatim: *"Izin Tinggal Terbatas/Izin Tinggal Tetap atau
  Visa Tinggal Terbatas milik orang tua yang masih berlaku"* (under "Persyaratan khusus").

**Verdict**: matches QW-5 exactly, re-confirmed independently this session — the page does NOT
support `hf.e31e-adult-excluded` / `hf.e31e-married-excluded`, and DOES support
`el.e31e-child-itas-support` / `el.e31e-sponsor-itas-itap` (the `REQ_SPONSOR_ITAS_ITAP` fact).

**Proposed `verified_at` bump**: **split by rule**, not a blanket bump on the source_record —
1. For the 2 HARD_FILTER rules: **no bump** — `ecd22722` is being REPLACED as their `source_ref`
   (see `e31e-source-edits.json`), not re-verified as their source. Bumping `verified_at` on a
   record that doesn't support the fact it was cited for would misrepresent freshness, not fix it.
2. For `el.e31e-child-itas-support` / `el.e31e-sponsor-itas-itap`, which keep citing `ecd22722`:
   **bump `verified_at` to `2026-08-18T21:41:23Z`**, `verified_by:
   "agent.air-m5.backend-rag.visa-e5-seq9-implementer-b.qw5-recheck-2026-08-19"` — the sponsor
   fact these two rules need IS confirmed live, today, verbatim quote above.

## 2. `ee8fe5b8-b0b4-544a-bf9a-fe53c3e316f2` (general "Izin Tinggal Keimigrasian" landing page)

**URL**: `https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian`
**Retrieved-at**: `2026-08-18T21:41:23Z` (this session)

Fetched and asked for the verbatim "Persyaratan Dokumen" section, checking for: 6-month passport
validity, USD 2000 proof-of-funds, CV, itinerary, support-letter requirements (the facts this
record is co-cited for on 18 rules + 3 product refs, per QW-5 record #4).

**Result**: the "Persyaratan Dokumen" section lists exactly 3 items — *"paspor atau dokumen
perjalanan yang masih berlaku"*, *"surat bukti penjaminan dari Penjamin..."*, *"surat pernyataan
yang menerangkan maksud dan tujuan berada di Indonesia"*. None of the 5 specific facts
(6-month validity / USD 2000 / CV / itinerary / support letter) appear.

**Verdict**: **CHANGED, confirmed** — matches QW-5 exactly. This is a residual, not resolved by
this session. **No `verified_at` bump.** Declared here per spec Step 4's instruction to "declare
the residual in CP3 — do not silently carry it": the CP3 package should carry forward QW-5's own
recommendation #1 (point the D1/D2/D12-specific pages — `ca5a2ce8`/`d3ad622e`/`5e64ec6b`, all
independently confirmed CURRENT by QW-5 — as the primary anchor for these 5 facts, or drop
`ee8fe5b8` from the co-source list) as an open CP3 item; re-pointing 18 rules' source_refs is a
scope larger than this session's Step 3/4 remit (those rules are outside E33E/E33G/E31E) and is
NOT attempted here.

## 3. `0497cb52-9c10-5ad5-a0ea-596e7678bd9b` (evisa student-visa FAQ)

**Method**: grep, not fetch — the spec's own instruction is "grep the assembled pack" for active
refs; since content freshness is moot for a record with zero citations, no live fetch was needed.

```
$ grep -c '0497cb52' apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
1
```

The single match is the record's own `source_records[]` entry. Independently confirmed via a
Python pass over the parsed JSON: **0** occurrences in `rules[].source_refs` (any of 100+ rules)
and **0** occurrences in `products[].source_refs`.

**Verdict**: **0 active refs, confirmed.** Recommend: **drop `0497cb52` from seq-9
`source_records`** entirely, per the spec's own instruction ("drop from source_records if truly 0
refs in seq-9"). Not performed here (this session does not assemble
`rulepack-prod-009.source.json` — that is Step 5, a different lane's scope) — recorded as the
concrete recommendation with the grep evidence above for whoever assembles seq-9.

## Summary table

| source_record | live check | verdict | action |
|---|---|---|---|
| `ecd22722` (for `hf.e31e-adult-excluded`/`hf.e31e-married-excluded`) | re-fetched 2026-08-19 | CHANGED, confirmed | replaced with `c9e6f0e4` (see `e31e-source-edits.json`) — no verified_at bump on ecd22722 for these 2 rules |
| `ecd22722` (for `el.e31e-child-itas-support`/`el.e31e-sponsor-itas-itap`) | re-fetched 2026-08-19 | CURRENT, confirmed | `verified_at` bump proposed to `2026-08-18T21:41:23Z` |
| `ee8fe5b8` | re-fetched 2026-08-19 | CHANGED, confirmed | residual, declared for CP3, no bump |
| `0497cb52` | grepped 2026-08-19 (0 refs, no fetch needed) | N/A (unreferenced) | recommend drop from seq-9 `source_records` |

No pack file was modified by this session (research capture + prepared artifacts only, per this
task's scope fence — assembly is Step 5, a different lane).

## Adversarial review

Reviewed 2026-08-19 by two cross-family refuter seats (Codex GPT-5.6 high; Kimi K3) as part
of the whole seq-9 fold working tree — both DROVE the real evaluator rather than reading the
diff. Findings touching this artifact and their dispositions are consolidated in
`../2026-08-19-e5-increment3-fold.md` §Adversarial review (fold doc); no finding against this
artifact survived undisposed.
