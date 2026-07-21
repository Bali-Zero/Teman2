---
date: 2026-07-21
domain: operations
client_case: null
sources:
  - research/operations/2026-07-19-kbli-batch-b-design.md (PR #2801, REV-4b, signed pre-registration)
  - scripts/kbli_filiera/parse_bps_crosswalk.py (Mini lane MANDATO MINI-A1, commit bd9f252edd + digest-fix)
  - scripts/kbli_filiera/phase0_gate.py (deterministic page-sampling, Mini lane)
  - data/kbli-filiera/bps-crosswalk/{edges-lampiran5,edges-lampiran10,parser-run-manifest}.json
  - research/operations/2026-07-21-kbli-batch-b-phase0-evidence/blind-pass-a-sonnet.json (Sonnet direct blind read, this session)
  - research/operations/2026-07-21-kbli-batch-b-phase0-evidence/blind-pass-b-kimi.json (Kimi K3 cross-family blind read, this session)
  - research/operations/2026-07-21-kbli-batch-b-phase0-evidence/gate-score.json (precision/recall scoring detail)
  - research/operations/2026-07-21-kbli-batch-b-phase0-evidence/reconciliation.json (Pass A vs Pass B per-page diff)
  - /Users/nuzantara/nuzantara-vault/bps/phase0-renders/ (300dpi page renders, outside git per #2550 data-plane guard)
status: PASS
adversarial_review: pending
---

# KBLI Batch-B — Phase-0 BPS crosswalk parser acceptance gate — CONDUCTOR VERDICT: PASS

## 0. What this gate is and why it exists

Per the signed Batch-B design (`2026-07-19-kbli-batch-b-design.md`, §1.4), **no Batch-B lot
(including Tier 4's AQL-sampled lots) may dispatch until the deterministic BPS crosswalk PDF
parser (`scripts/kbli_filiera/parse_bps_crosswalk.py`) passes a frozen, blind, one-shot
acceptance gate**: edge-level precision ≥0.995 AND recall ≥0.995 on a deterministically-sampled
20-page holdout, scored exactly once. This is the last open precondition named in the design
before Batch-B execution can begin.

## 1. Provenance chain (who built what, verified how)

- **Parser + page-sampling code**: built on the Mini machine under a separately-launched lane
  (MANDATO MINI-A1, `docs/plans/2026-07-19-mini-regia-motori.md`, PR #2847), discovered via
  sibling-race ground-check this session rather than duplicated. Independently code-reviewed this
  session (dispatched agent, position-anchored `pdfplumber` extraction confirmed not
  whitespace-splitting; `sebagian` tracking, `uraian` diffing, fail-closed unanchored-row handling,
  and full sha256 provenance pinning all verified against source; 10/10 tests passing; 2 minor,
  non-blocking findings noted in §7).
- **Digest freshness**: the committed `page-rank-table.json` was found STALE (keyed to an
  invalidated `parser_run_digest` predating a title-continuation-stitch bugfix). Re-derived fresh
  against the current digest `23182d27700a1b7b10af6023a993ee23331c55ff84e37518b15385a15381d9eb`,
  confirmed byte-identical across two independent runs (determinism proof), and independently
  re-confirmed this session as matching `data/kbli-filiera/bps-crosswalk/parser-run-manifest.json`'s
  own `parser_run_digest` field exactly — the parser output scored below is the current, non-stale
  run.
- **Page renders**: 20 pages at 300dpi, produced deterministically from the sha256-pinned source
  PDF, stored outside git tracking at `~/nuzantara-vault/bps/phase0-renders/` per the #2550
  data-plane guard (only sha256-pinned in a manifest, never committed).

## 2. The 20-page sample

Per the design's deterministic draw (`SHA256(parser_run_digest:lampiran_id:zero_padded_page)`
hex-ascending, greedy-fill 10/lampiran, odd/even final-rank split into tuning/holdout):

| Split | Lampiran 5 (2020→2025) | Lampiran 10 (2025→2020) |
|---|---|---|
| **TUNING** (freely re-examinable) | 171, 139, 142, 214, 217 | 441, 390, 382, 440, 438 |
| **HOLDOUT** (scored once, blind) | 238, 242, 240, 202, 131 | 370, 392, 415, 330, 411 |

## 3. Ground truth: two independent blind passes, cross-family

Per this program's own established discipline (W100: *"same-family blind agreement measures
transcription fidelity, not truth"*), a single-family (Claude-only) blind check would not
constitute independent verification. Two genuinely different model families read all 20 page
renders blind — no parser output, no prior edge/consistency JSON, no knowledge of each other's
output:

- **Pass A** — Sonnet 5, direct image read. 425 edges, 402 high / 23 medium / 0 low confidence, 0
  unreadable, 0 `sebagian` found (flagged explicitly as "can't rule out elsewhere in the document,"
  not asserted absent). 10 of 20 pages flagged with real classification/boundary difficulty
  (tangled N:M clusters, recurring catch-all source codes, one page-break orphan-text artifact) —
  none were legibility failures.
- **Pass B** — Kimi K3 (Moonshot, genuinely cross-family), vision-capable, confirmed to support
  image input empirically before committing to the full run. 426 edges, 423 high / 2 medium / 1
  low confidence, 1 `UNREADABLE` (self-flagged, not guessed), 0 `sebagian`. Ran as a detached
  background shell script that survived its dispatching subagent's own premature exit (the
  subagent paused waiting for an async notification that was never going to arrive — an
  "exists≠armato" near-miss caught by checking actual process/file state on disk rather than
  trusting the subagent's own completion summary) — script completed 20/20 pages with zero
  in-script errors after being independently polled to completion.

**Independent verification note**: both consolidated JSON outputs were confirmed on-disk (file
size, JSON validity, edge-count recount) via separate tool calls before being trusted, per this
program's anti-hallucination discipline — not accepted on the dispatching agents' self-reported
summaries alone.

### 3.1 Reconciliation

| Split | A edges | B edges | Matched | A-only | B-only | Agreement |
|---|---|---|---|---|---|---|
| TUNING | 207 | 208 | 207 | 0 | 1 | 99.52% |
| HOLDOUT | 218 | 218 | 218 | 0 | 0 | **100.00%** |

The sole disagreement (TUNING, page 441/Lampiran 10) was conductor-adjudicated by eye directly
against the render: Pass B emitted a placeholder edge
(`code_2020=UNREADABLE, code_2025=UNREADABLE`, confidence=low) for the page's top row, which is a
wrapped continuation of a title that started on the previous page — both code cells are genuinely
blank on this page (verified visually: the row reads only "...dan Rumah Tangga, Mobil, serta
Sepeda Motor" with empty code-1/code-3 columns, and the true first data row, 95400↔95230, follows
immediately below with both codes populated). Pass A's handling (silently omitting the artifact)
was correct; it is excluded from the frozen ground truth as not a genuine crosswalk edge. This is
the ONLY conductor edit to either blind pass's output, made on the TUNING half per the tuning/
holdout asymmetry — the HOLDOUT half required zero conductor intervention, preserving its
scored-once-blind integrity intact.

**Frozen ground truth = Pass A's edge set (425 edges), cross-family-corroborated by Pass B at
99.5–100% with the sole discrepancy resolved as a non-edge artifact, not a factual disagreement.**

## 4. Gate score

Parser output for the same 20 pages was extracted from `edges-lampiran5.json` /
`edges-lampiran10.json` (the full-corpus deterministic parser run, digest-verified fresh per §1)
and diffed against the frozen ground truth by exact `(pdf_page, code_2020, code_2025)` match.

| Split | Ground-truth edges | Parser edges | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|---|---|
| TUNING | 207 | 207 | 207 | 0 | 0 | 1.00000 | 1.00000 |
| **HOLDOUT** | **218** | **218** | **218** | **0** | **0** | **1.00000** | **1.00000** |

A manual spot-check (page 411, first 5 edges) confirmed the parser's `kbli_2020`/`kbli_2025` field
orientation aligns correctly with the blind passes' `code_2020`/`code_2025` fields for a
Lampiran-10 (reverse-direction) page — ruling out a systematic key-swap artificially producing a
perfect score.

## 5. Verdict

**HOLDOUT precision = 1.00000, recall = 1.00000 — both exceed the ≥0.995 acceptance threshold.**

**PHASE-0 GATE: PASS.**

This is a genuinely strong result (zero FP, zero FN across all 435 sampled edges), independently
triangulated three ways (Sonnet direct read × Kimi K3 cross-family read × deterministic parser)
with the single cross-pass discrepancy conductor-verified against the source render and resolved
as a non-edge artifact rather than silently averaged away.

## 6. What this unlocks / what is still required before Lot B-1

Phase-0 passing removes the parser-acceptance precondition. Two further preconditions remain
before ANY Batch-B lot (not just Tier 4) may dispatch, per the design's blanket rule:

1. **Tier-4 AQL parameters** (n, Ac, switching-state) must be computed from the frozen derivation
   rule using the measured HOLDOUT error rate (`max(1-precision, 1-recall) = 0.0` here — this pins
   the AQL class at the tightest standard value in the design's table, but the exact ISO 2859-1
   lookup and lot-size-dependent (n, Ac) pair have NOT yet been computed in this report and require
   re-grounding the design doc's own AQL table before computing — not done here to avoid
   fabricating standard-table values from memory). **Zero's Legge-5 ratification (accept-or-
   override) of the computed parameters is required regardless of what the frozen rule outputs.**
2. **≥5 fresh POS controls** — codes never named in any prior Batch A/B document or merged cure
   spec — conductor-eye-adjudicated directly on raw Lampiran page renders (design §3.1, B6 residual
   closure). This is an explicitly non-delegable conductor task, not yet started. A candidate
   exclusion list of 441 already-used codes was compiled this session
   (`.claude/skills/kbli-navigator/SKILL.md` LIVE STATE + all cure specs + membership manifests) to
   ground the "fresh" requirement.

## 7. Minor findings (non-blocking, for the record)

- `phase0_gate.py:389`'s handling of `unresolved-rows.json` has a latent Tier-2.5 gap (noted during
  independent code verification; does not affect this gate's PASS verdict since the 20-page sample
  had zero unresolved rows).
- The wrapped-row / N:M stratification in the page-sampling algorithm is near-vacuous on this
  specific PDF (nearly all eligible pages qualify as both strata simultaneously) — not a defect,
  just a weaker stratification signal than the design anticipated; does not affect this gate's
  statistical validity since the sample was still drawn correctly per the frozen deterministic
  rule.

## 8. Solo-operatore

None. This gate's evidence, adjudication, and verdict were produced entirely within session
permissions (subagent dispatch for the two blind passes, conductor's own eye-verification for the
one discrepancy and the render spot-checks, direct computation for reconciliation/scoring). The two
items in §6 that remain before Lot B-1 are NOT operator-only either — the AQL computation is
conductor work pending re-grounding, and the fresh-POS-controls task is explicitly conductor-only
per the design (not an operator category). Zero's Legge-5 ratification in §6.1 is the one genuine
business-decision checkpoint, consistent with this program's standing pattern (accept-or-override,
never silently proceed).
