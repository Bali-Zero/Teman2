---
adversarial_review: codex
---

# BLUE Dux note — DEFINITIVE SYNTHESIS + EXECUTION run

Same conversation as your ANALYSIS. Runtime limits are unchanged: you can read and write files inside
your worktree; shell commands are unavailable, do not attempt or circumvent them.

## Read first (all inside your worktree)
1. `.agent-receipts/udb-wave8-dux/ADVERSARY-FINDINGS.md` — the ONE consolidated adversarial pass
   (claude-opus-5-5, xhigh requested) over all eight proposals. Address every finding for your block and
   every cross-block finding that names it: accept and fix, or reject with evidence. No second round exists.
2. `research/operations/udb-wave8/B03/dux-requests/` — results of your admitted ANALYSIS requests
   (`RECEIPTS.json` says what ran, exit codes and hashes). Numbers there are observed; use them, do not
   re-estimate. A request marked DEFERRED or NOT_ADMITTED did not run.
3. `.agent-receipts/udb-wave8-siblings/` — pinned sibling ANALYSIS/PROPOSAL files (read-only, for the
   frozen contract and dependencies). Do not edit sibling material.
4. `.agent-receipts/udb-wave8-inputs-dux/` when present — pinned prior-work pre-images with sha256.

## Deliver in your owned report directory
- `DEFINITIVE-SYNTHESIS.md`: final design of your block deliverable, the adversarial dispositions table,
  facts / inference / unknowns kept separate.
- Your candidate files inside your block's `owned_code` from manifest.json. Reports and adapters only
  unless manifest.json says otherwise. Do not edit production application modules (`apps/**`), shared
  files, lockfiles, migrations or sibling directories. Tests for your adapters go next to them under
  `research/operations/udb-wave8/B03/` (pytest, stdlib only, no network, no live store access).
- `## DUX-REQUESTS` at the end of DEFINITIVE-SYNTHESIS.md: the exact commands the Dux must run to
  produce your evidence — at minimum the test command for your tests and the command that generates
  your census/report artifact from pinned inputs. Use ids `DUX-REQ-B03-1x` (10..19). Any native probe
  must name the existing admitted adapter or explain why it is read-only metadata only; the Dux decides.
- `RESULT.json` with exactly: block_id, status, block_closed, proofs, missing, tests, head_sha.
  You cannot observe test results or the commit yet: set tests to the requested commands with
  `"result": "PENDING_DUX_EXECUTION"`, head_sha to `"PENDING_DUX_COMMIT"`, and block_closed=false unless
  every acceptance criterion is already proved by evidence on disk. Never invent closure.
- `PR_BODY.md`: summary, scope, evidence paths, explicit missing evidence, and one `Bites:` line naming
  the real consumer and the observation that proves the change is in force.

## Boundaries
No client rows, values, PII, credentials or OSINT anywhere. The repository is PUBLIC. A consent,
credential or privilege you need becomes a concrete reviewable proposal file, never an assumed approval.
Final reply: at most 500 words, artifact paths and what remains missing.

## Pinned Dux documents (read-only, gitignored; cite by sha256)
- `.agent-receipts/udb-wave8-dux/ADVERSARY-FINDINGS.md` sha256 29c57f706bcc0dd8e7f492f3ffe5215598798ed173f452f19aa7a086c8faaf54
- `.agent-receipts/udb-wave8-dux/CONTRACT-CONVENTIONS.md` sha256 a7feea89fa64000d76c18a52d705dd008b4a6336a6d58af98c2618a13048c559
- `.agent-receipts/udb-wave8-dux/DUX-CONSOLIDATION.md` sha256 c39218718f496b643b550abf98ca40bd2755e74d3954caed953005eb5b906e14

CONTRACT-CONVENTIONS.md is the frozen value domain for the sibling fields; follow it exactly. DUX-CONSOLIDATION.md holds the binding Dux rulings on the adversarial findings (schema, freeze order, credentials, native exercises, your block).

## Block-specific Dux facts and decisions for B03
Use the pinned pre-images in .agent-receipts/udb-wave8-inputs-dux/prior/ (source-index-enhanced, jobs-*, cron-*, job-source-links, GITHUB-WORKFLOW-METADATA, SOURCE-BOUNDARY-PRO, LEAD-DELTA). Observed: naive joins index_* -> src_* matched 0/678 and CI-REGISTRATION-UNMATCHED -> workflow rows 0/114 (dux-requests/DUX-REQ-B03-02.out); your duplicate assumptions must be re-derived from the pre-images, not asserted. The 6030th lead is `runtime_mini_46522da0ef79d3aa7422ca41` and the five historical restore source references are listed verbatim in LEAD-DELTA.json (historical_source_references_retained): src_307bea3dfb94ec31, src_d073f505ff1671ad, src_def7a4c288a552af, src_cdf3ae5e4ecf861c, src_2f350566b97aee80. Check every consumer_id you cite exists (DUX-REQ-B03-03.out lists restore rows).
Deliver a deterministic census adapter (stdlib, reads only frozen + pinned inputs, refuses on any sha256 mismatch) that emits one row per lead (6030) with the frozen fields, an `x_disposition` in {active, retired, duplicate, excluded, unresolved} and `x_evidence_ref`, plus tests including negative cases. 'active' requires deployed-execution evidence; registration alone is not execution. Expect many `unresolved`; that is honest, not failure.

## Adversarial review

Fresh independent Codex review by `/root/b03_available_final_gate` inspected pre-attribution lines 1-39, 47-50, as pinned in `R1-DOCUMENT-REVIEW.json`. This is a scoped document review, not a complete document endorsement, implementation approval, native observation or final exact-head gate. Historical command/runtime statements are retained as recorded instructions and receipts, not newly observed events. Operational acceptance and the active denominator remain unproved.
