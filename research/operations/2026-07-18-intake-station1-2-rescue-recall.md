---
date: 2026-07-18
domain: operations
client_case: none (intake backlog, aggregate, PII-redacted)
sources:
  - local nuzantara_dev DB (SELECT-only, W87) — full-population scans of the 25,400 zero-candidate review_pending proposals
  - apps/backend-rag/backend/services/intake/routing.py::_match_folder_name (m227) — the fixed matcher
  - apps/backend-rag/backend/services/intake/drive_adapter.py — ingress (source_path build, enqueue)
  - scripts/intake_drive_folder_bridge.py + intake_station0_report.py + intake_reocr_sample.py (this branch)
  - memory discovery_refinery_panel_width_is_second_order_2026_07_18 + /intake skill corner
adversarial_review: codex
---

# Intake 0-candidate rescue — the folder-provenance lever (m227 root-only fix)

> **Headline:** the 24,277 Drive docs stuck at 0-candidate are stuck because fase4's
> folder-name matcher (`_match_folder_name`, m227) only ever inspected `source_path.split('/')[0]`
> — the **root** segment. For Drive that root is a **staff/category** folder (`PEMEGANG KITAS`,
> `EXTEND VISA`, `NOVI`…), never a client; the client folder lives DEEPER. So the folder signal
> that already exists in the code structurally never fired on Drive. **Fix: scan every segment.**
> Measured effect: **1,231 docs (5.1%) gain a folder candidate — 1,005 as clean single-client
> LINK_CANDIDATE** (~95% precision), from ~0 before. This fixes the ingress (future Drive docs
> resolve at enqueue) and, via reprocess, the backlog. It is the structural lever; re-OCR and
> OCR-name re-search are measured dead-ends (below).

All numbers full-population unless marked *sample*. PII (Law 2): counts, proposal_id/client_id ints,
similarity floats only — never a client/folder name or OCR text.

---

## 1. The population (exact)

`review_pending` = 35,779; **zero-candidate = 25,400** (drive 24,277 / whatsapp 1,123).
**Every zero-candidate carries fase4's verdict** `"no strong identifier, no fuzzy name >= 0.40"` / NO_MATCH.
`client_id_hint = 0` on all 24,277 drive docs (ingress never resolved a client). doc_type unknown 69%.

---

## 2. The bug (m227): folder matcher was root-only

`routing.py::_clean_folder_segment` did `str(source_path).split("/", 1)[0]` — the **first/root** segment
only. `resolve_entity` feeds that one segment to `_match_folder_name` (a NEVER-auto transport hint).

Measured Drive folder structure (`source_path`, 16 roots):

| root (staff/category) | docs | is it a client? |
|---|---|---|
| `PEMEGANG KITAS` (KITAS holders) | 1,945 | no — 467 client sub-folders under it |
| `EXTEND VISA` | 3,088 | no — 725 client sub-folders (depth 3) |
| `NOVI` / `MEGI` / `YANTI` / `YUDI` … (staff) | 6,038 / 3,352 / 3,054 / … | no — staff drives |

The client folder sits at **depth 2–3**, not the root. Root-only matching → the folder signal never
fired on Drive → all 24k land 0-candidate **despite the folder logic existing** (a #2 "exists≠armed"
shape: the code is there, but pointed at the wrong segment). The single-segment design was correct for
the **Dropbox** layout (client folder at root) and never adapted to Drive's deeper hierarchy.

---

## 3. The fix + its measured recall

`_match_folder_name` now scans **every** `source_path` segment (new `_folder_segments`), matches each
against `clients.full_name` + `companies.company_name`, dedups by (table,id) keeping the best score,
and applies the existing `FUZZY_APPLY_THRESHOLD=0.70` + ambiguity margin. Unchanged: folder is a
transport hint, **NEVER auto-attach** (2026-05-17 identity-hallucination scar); two distinct clients in
one path → AMBIGUOUS. `_clean_folder_segment` kept for the Dropbox layout + the parametrized test.

**Tests:** `test_intake_routing_folder.py` +10 (deep Drive path resolves, root-category never matches,
two-client path → AMBIGUOUS, same-client dedup). Full intake suite **466 passed, 1 skipped** — no regression.

**Real recall (production semantics: similarity ≥ 0.70, any segment, over the 24,277):**

| Outcome | docs | note |
|---|---|---|
| gains ≥1 folder candidate | **1,231 (5.1%)** | was ~0 (root-only never matched) |
| → unique 1 client → **LINK_CANDIDATE** | **1,005** | human-confirmable, never-auto |
| → multi-client → AMBIGUOUS | 226 | correctly surfaced, not guessed |

**Precision (validated on attached-drive ground truth):** when a `source_path` segment EXACTLY matches
a client name, it points to the TRUE client **19/20 = 95%**. The 0.70 fuzzy tier + ambiguity guard +
never-auto discipline contain the residual: a wrong folder candidate is human-reviewed, never mis-attributed.

---

## 4. The ceiling: 88% of client-folders name entities absent from the CRM

Folder resolution is bounded by the same structural wall as every other lever: **of the 4,057 distinct
client-folder segments, 3,591 (88.5%) match NO client even at loose similarity 0.50.** Breakdown:
~1,215 are person-name-like with no CRM match (**prospects / never-entered clients** — a data gap, not a
pipeline bug), ~1,966 are digit folders (case-id/passport/date sub-folders), ~224 category words
(scan/berkas/arsip). The CRM itself is near-empty of keys: **313 passports, 1 kitas, 62 company_names,
173 `google_drive_folder_id`** out of 11,748 clients. So the folder lever recovers the ~5% whose folder
names a catalogued client; the rest are genuinely uncatalogued. **Surfacing the ~1,215 person-folders
with no client is itself ops intelligence** (uncatalogued clients/prospects to enter).

---

## 5. Levers measured DEAD (why folder-provenance is the one that works)

- **Station 2 — OCR-name / strong-id re-search (no re-OCR), all 25.4k:** recovers **~9 docs (0.04%)**.
  strong-id→client 2 (clients lack the keys), person-name→client 7, company-name 1, transitive-blob 0.
  fase4 already ran strong-id + fuzzy-name≥0.40 correctly. Instrument validated (attached docs match own
  client at 0.79 avg, ≥0.45 in 90%) — the 7 is real signal, the subjects are simply not in the CRM.
- **Station 1 — re-OCR:** structurally blocked. Of the 25,400 blobs only **594 (2.3%) still exist on
  disk** (`intake-blob-retention` TTL=7d unlinked the rest); **0 of the 594 are stubs**. Drive re-fetch
  is possible (`source_ref="drive:<file_id>"`) but costs 24k downloads + 24k vision passes for a ~0.1%
  name→client ceiling. Confirmatory sample inconclusive (compute timeout under GPU contention) and moot
  given the pivot to folder-provenance.
- **Station 0 — dedup/junk (works on metadata, not the evicted blob):** 2,152 exact-dup + 203 hard-junk
  = **2,355 rows (9%)** can reach a correct terminal state (queue hygiene, not recovery). Reproducible:
  `scripts/intake_station0_report.py` (dry-run).

---

## 6. Recall answer + what ships

| Lever | recovery | precision | status |
|---|---|---|---|
| **Folder-provenance (m227 fix)** | **1,231 docs (5.1%)** → 1,005 LINK_CANDIDATE | ~95% | **SHIPPED (code + tests)** |
| Station 2 re-search | ~9 (0.04%) | — | dead-end (measured) |
| Station 1 re-OCR | ≤594 addressable, ~0.1% ceiling | — | blocked (blobs evicted) |
| Station 0 hygiene | 2,355 removable (terminal, not recovery) | deterministic | dry-run, operator-armed |

**The fix is dual-value:** (a) **ingress** — future Drive docs resolve their folder at enqueue (no more
`client_id_hint=0`-forever); (b) **backlog** — reprocessing the 24k via `intake_reprocess_backlog.py`
re-routes them through the fixed matcher, materialising the 1,005 LINK_CANDIDATEs into the review/panel
tier. Reprocess is a bulk re-route of shared state → measured (this report) → operator-armed apply, never
blind. NEVER auto-attach on folder alone (scar).

**Follow-ups (root cause, not this PR):** backfill `clients.google_drive_folder_id` for resolved folders
(durable folder_id→client link, so future docs corroborate by id not fuzzy name); extend blob-retention
TTL / cold-archive (so re-processing has raw material); enter the ~1,215 uncatalogued person-folders as
clients (closes the 88% gap at the source).

---

## Adversarial review

**Seat:** codex (GPT-5.6, read-only sandbox, 2 rounds, 2026-07-18) — generator≠grader on the m227 code fix.

- **Round 1** on the multi-segment change found one **MAJOR**: `AMBIGUITY_MARGIN` was applied GLOBALLY
  across candidates from different `source_path` segments (scores not comparable), so segment A@1.00 +
  segment B@0.80 collapsed to a single confident `LINK_CANDIDATE`, silently dropping B. Plus MINORs:
  `[A-Za-z]` alpha-check dropped Cyrillic/Arabic/CJK names; 2×N unbounded fuzzy queries; one tautological
  test. **All addressed** — two-level disambiguation (margin resolves homonyms WITHIN a segment; distinct
  entities across segments always surface as AMBIGUOUS), Unicode `str.isalpha()`, `_MAX_FOLDER_SEGMENTS=8`
  cap, and 3 genuine regression tests.
- **Round 2** on the fixed code (commit `9612ee4da`): **VERDICT CLEAN — no blocking defect.** Confirmed the
  MAJOR resolved (harness: A@1.00 + B@0.80 → AMBIGUOUS), never-auto invariant intact (folder alone never
  AUTO_ATTACH), best-score dedup correct, cap has no off-by-one, all 3 regression tests genuine. One
  **residual MINOR (non-blocking, pre-existing):** `len(seg) < 3` still drops 2-character CJK names (e.g.
  张伟) — rare for the Bali Zero client base; a script-aware min-length is a follow-up, not a blocker.

Full backend suite green (17,612 passed / 0 failed); folder-matcher tests 33/33.
