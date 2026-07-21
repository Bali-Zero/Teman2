# Curated-QA corrections — 2026-07-21 (ready to apply, NOT yet applied)

Drafted after independently verifying 8 disputed team-review corrections
against official sources (see the 3 research captures in `research/property/`
and `research/visa/` in this same PR). 11 rows corrected across 3 files.

## Why this isn't already applied to `apps/backend-rag/data/curated_qa/`

Those files are **entirely gitignored** (`.gitignore` line 58-63) — local,
machine-specific working state, not part of the tracked repo tree. The
`worktree_file_write_check.py` / `worktree_isolation.py` hooks block any
Edit/Write/Bash write into the main checkout (including gitignored paths —
the guard is purely path-based, it doesn't check git-tracking status), and
a fresh git worktree cannot hold gitignored content either, so there is no
path-based way for a session to apply this edit to the live local file by
itself. This is a genuine gap between the worktree-isolation guardrail
(designed for tracked-content races) and gitignored local build artifacts.

Separately, `curated_qa_harvest.py`'s own docstring says: *"Do NOT run
against prod without Zero's review of the batch being loaded — this writes
into the same FAQ cache / curated_qa collection the live orchestrator reads
from."* Re-harvesting corrected Qdrant points is therefore an operator-gated
step regardless of the write-hook question.

## What's already live and wrong (right now)

`apps/backend-rag/data/curated_qa/_manifests/property-6aa6f302384c.json` and
`visa-*` manifests show `qdrant_committed: true` for the ORIGINAL (wrong)
villa-rental content — meaning the incorrect "PT PMA can hold KBLI 55203"
claim is already grounding real RAG answers via the `curated_qa` Qdrant
collection, even though `faq_committed: false` (not yet promoted to the
verbatim FAQ sink). The E33F/KITAP-RET rows are in the same state.

## How to apply (2 steps, ~1 minute, needs a shell with the write-hook off
or an operator running it directly — not from an agent session)

1. Copy the corrected files over the local originals:
   ```bash
   cp corrections/property-villa-rental.jsonl \
      corrections/visa-second-home-variants.jsonl \
      corrections/visa-catalog-sweep.jsonl \
      apps/backend-rag/data/curated_qa/
   ```
2. Re-harvest the corrected Qdrant points (review the diff first — this is
   the "Zero's review" gate the harvester's own docstring asks for):
   ```bash
   cd apps/backend-rag && source .venv/bin/activate
   PYTHONPATH=. python scripts/curated_qa_harvest.py --write-manifest \
     data/curated_qa/property-villa-rental.jsonl
   PYTHONPATH=. python scripts/curated_qa_harvest.py --write-manifest \
     data/curated_qa/visa-second-home-variants.jsonl
   PYTHONPATH=. python scripts/curated_qa_harvest.py --write-manifest \
     data/curated_qa/visa-catalog-sweep.jsonl
   PYTHONPATH=. python scripts/curated_qa_harvest.py --qdrant
   ```
   (`--faq` is not needed — none of the 11 corrected rows are
   `verbatim_eligible`/`JELAS`-promoted to the FAQ sink yet; only Qdrant
   grounding needs the fix. Re-check with `--dry-run` first if unsure.)

## What changed (11 rows, 3 files)

- `property-villa-rental.jsonl` — 9 of 20 rows. Root cause: the draft
  treated KBLI 55203 "Aktivitas Vila" as PMA-eligible; it is not (Usaha
  Menengah cap, no PT PMA tier). Corrected rows now point to the actual
  compliant paths: hotel bintang (55101-55105), apartemen hotel/serviced
  apartment (55204), or a management-only company (55901).
- `visa-second-home-variants.jsonl` — 1 of 18 rows (E33F cumulative cap).
  Corrected from "unconfirmed, maybe indefinite" to "capped — ~5 years
  annual renewal → Retirement KITAP, not an exception to the general ITAS
  6-year ceiling."
- `visa-catalog-sweep.jsonl` — 1 of 14 rows (KITAP-RET income threshold).
  Corrected from "unresolved USD 3,000 vs USD 1,500" to "USD 3,000/month
  is current; USD 1,500 is the superseded pre-2024 figure."

The C12/D12 rows in `visa-catalog-sweep.jsonl` were investigated and found
**already correct** — the reviewer's proposed changes there (D12 converts
to KITAS, no C12 60-day option, equal C12/D12 funds, D12 needs a sponsor)
are all wrong per `research/visa/2026-07-21-c12-d12-verification.md`. No
change applied to those rows.
