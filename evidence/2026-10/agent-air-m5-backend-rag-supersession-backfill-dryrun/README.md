# Pasal-supersession backfill — corpus-wide DRY-RUN map (2026-10-06)

Follow-up to PR #7953 (`agent/air-m5/backend-rag/legal-pasal-supersession`), which
shipped the mechanism and left the corpus-wide retro-parse dry-run as an explicit
follow-up. This directory is that dry-run's output, plus the diagnosis it surfaced.

## Provenance / read-only proof

- Command (run on Pro, via `ssh pro`, worktree
  `~/Desktop/nuzantara/.worktrees/legal-supersession-dryrun` checked out at
  `origin/agent/air-m5/backend-rag/legal-pasal-supersession` + merge of fresh
  `origin/main`):
  `python scripts/backfill_pasal_supersession.py --collection legal_unified
  --amendment <UU_63_2024 pdf> --amendment <permenkumham_11_2024 pdf>`
  — **no `--apply`**.
- Read-only by construction, verified in code before running:
  `backfill_pasal_supersession.py` only calls `annotate_superseded_pasals(..., dry_run=True)`,
  and in that mode `backend/core/legal/supersession.py:305` counts matches and
  **never calls `set_payload`** — the only store access is `scroll_strict`.
  `QdrantClient.__init__` (`backend/core/qdrant_db.py:269`) builds a lazy HTTP
  client and writes nothing.
- Amendment sources:
  - `data/kb_sources/2026_updates/UU_63_2024_Perubahan_Ketiga_UU_Keimigrasian.pdf` (Pro, 1 MB)
  - `data/source_documents/t0_regulations/permenkumham_11_2024_perubahan_visa.pdf` (repo-tracked)
- Exit code 1 is the script's own "unresolved > 0" signal, not a crash.

## The map (verbatim in `dryrun-output.json`)

| amendment | clauses parsed | chunks WOULD be marked | unresolved |
|---|---|---|---|
| UU 63/2024 → base | 2 (of 9 visible directives in the PDF) | **0** | 2 — both bound to phantom `UU_6_2023` |
| Permenkumham 11/2024 → base | 1 (of 40 visible directives) | **0** | 1 — bound to phantom `UU_12_2006` |

**Result: zero chunks are markable by the mechanism as-is. The unresolved list is
the entire output, and every unresolved entry names a WRONG base document.**

Base-document census (read-only scrolls, verbatim in `base-doc-census.json`):

| document_id | chunks | notes |
|---|---|---|
| `UU_6_2011` | 413 | exists, pasal_number payloads present — the convention id in `KNOWN_PAIRS` is CORRECT |
| `Permen_22_2023` | 434 | exists, pasal_number payloads present — convention id CORRECT |
| `Permenkumham_22_2023` | 0 | does not exist (abbrev is `Permen`, not `Permenkumham`) |
| `UU_12_2006` | 0 | does not exist in this collection |
| `UU_6_2023` | 4685 | **EXISTS** (UU Cipta Kerja) but all pasal_number payloads empty |
| `UU_63_2024` | 38 | amendment itself already ingested |
| `Permen_11_2024` | 390 | amendment itself already ingested |

The #7953 handoff's worry — "base doc ids were assumed by convention" — resolves
favourably for the two KNOWN pairs: both convention ids hit real documents.
The dangerous twin showed up instead: the parser bound clauses to `UU_6_2023`,
which IS a real document (4685 chunks). It is only saved from a wrong --apply by
the fact that Cipta Kerja chunks carry no `pasal_number`, so the client-side
match finds nothing. That is luck, not protection.

## Root causes (diagnosed from the parser's own view of the cleaned text)

1. **Multi-line citations never match the target regex.** `_TARGET_INSTRUMENT`
   (`backend/core/legal/supersession.py:111`) joins citation tokens with
   `[^\S\n]+`. PDF extraction line-wraps real citations, e.g. Permenkumham
   11/2024 amends "Peraturan Menteri Hukum dan Hak Asasi Manusia\nNomor 22\n
   Tahun 2023" — the true target citation is NEVER recognized (the only targets
   found in that file are UU 39/2008, UU 6/2011, Perpres 18/2023 in the header
   body, and UU 12/2006 twice near the closing `dicabut` clause).
2. **`_TARGET_WINDOW_CHARS = 1200` is smaller than real enumerated amending
   lists.** The clause list in Permenkumham 11/2024 spans ~92k chars (items
   1–40); in UU 63/2024 the stamps ("SK No 243502 A / PRESIDEN / REPUBUK
   TNDONESIA") inflate each item to >1.2k chars. Only directives within 1200
   chars of a (possibly wrong) citation survive; everything else is skipped.
3. **Source-PDF erratum / extraction noise in the UU 63/2024 copy.** The parsed
   text contains "Undang-Undang Nomor 6 Tahun **2023**" where the instrument is
   the Perubahan Ketiga of UU 6/**2011** — so even the 2 clauses that DID bind
   bound to a phantom year. Whether this is a misprint in this unofficial PDF
   copy or OCR/stamp noise was not determined here.

## Recommendations (NOT applied in this PR — each is a design decision for the #7953 owner)

- Allow horizontal whitespace + single newlines between citation tokens in
  `_TARGET_INSTRUMENT` / `_CITATION_INLINE` (root cause 1). The constants.py
  ReDoS scar forbids unbounded overlap, not newlines; keep the pattern bounded.
- Replace the fixed 1200-char window with an explicit "amending-list" scope:
  the citation immediately preceding "diubah sebagai berikut:" governs the
  following enumerated list (root cause 2). Simply enlarging the window re-opens
  the cross-instrument guessing the window exists to prevent.
- Verify the UU 63/2024 source text against peraturan.go.id before any --apply
  (root cause 3); if the corpus copy is corrupt, replace it and re-ingest.
- Only after 1+2, re-run this dry-run; expect ~7 markable pasals for UU 6/2011
  (the ingested `UU_63_2024` doc itself carries pasals 3, 16, 24A, 64, 97, 102,
  103, 137 — an independent corroboration of the intended amendment list) and
  ~40 for Permen 22/2023 (directive list observed in the cleaned text).

## What was NOT done

- No `--apply`, no writes of any kind, against any store (lane rule).
- No code changes: every fix above alters the mechanism's documented
  anti-guessing policy (`supersession.py` docstring: no-target-in-window "is the
  honest no-op, not a guess") — a #7953-owner decision, reported not taken.
