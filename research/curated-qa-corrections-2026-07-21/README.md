---
date: 2026-07-21
domain: visa+property
adversarial_review: exempt-corrections-index
---

# Curated-QA corrections — 2026-07-21 (ready to apply, NOT yet applied)

Drafted after independently verifying 8 disputed team-review corrections
against official sources (see the 3 research captures in `research/property/`
and `research/visa/` in this same PR), THEN put through an independent
adversarial review (Kimi K3) per this repo's R1 gate, which caught real
errors in the first draft — see "Round 2" below. 12 rows corrected across
3 files (9 property, 2 E33F, 1 KITAP-RET — one E33F row was touched twice,
once per round).

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
   cp research/curated-qa-corrections-2026-07-21/property-villa-rental.jsonl \
      research/curated-qa-corrections-2026-07-21/visa-second-home-variants.jsonl \
      research/curated-qa-corrections-2026-07-21/visa-catalog-sweep.jsonl \
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

## What changed (round 1 — team-review validation, 11 rows, 3 files)

- `property-villa-rental.jsonl` — 9 of 20 rows. Root cause: the draft
  treated KBLI 55203 "Aktivitas Vila" as PMA-eligible; it is not (Usaha
  Menengah cap, no PT PMA tier). Corrected rows pointed to hotel bintang
  (55101-55105), apartemen hotel/serviced apartment (55204), or a
  management-only company (55901) as "compliant routes" — **round 2 below
  found this list itself was wrong for Bali, see below.**
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

## Round 2 — adversarial review (Kimi K3), same day

Per this repo's R1 gate (generator≠grader — `check_adversarial_review.py`),
every research capture here went through an independent seat that tried to
refute it. It found real errors in the round-1 drafts, which have been
fixed in place (the counts/content above already reflect round-2 fixes;
this section documents what changed and why):

- **`property-villa-rental.jsonl` (7 of the 9 rows, revised further):**
  the round-1 draft called **KBLI 55901 (management-only)** and **KBLI
  55101-55105 (hotel bintang)** clean "compliant PMA routes." Bali Zero's
  own internal KBLI ground truth (`data/source_documents/
  KBLI_2025_FINAL_CLEAN.json`, `l4_bali` field) — independently checked
  against the raw dataset file, not just cited — shows **55901 is
  currently BLOCKED from new PMA registration in Bali** (island-wide
  moratorium on Low/Medium-Low-risk KBLI codes, effective 2026-05-13),
  despite being 100% foreign-open nationally; and **55101-55105 is only
  registrable as PMA in Bali by declaring a higher-risk project scope**
  (not a blanket-open route). Only **KBLI 55204 (apartemen hotel/serviced
  apartment)** is a clean, currently-open route. All 7 affected rows were
  rewritten to reflect this — see `research/property/
  2026-07-21-kbli-villa-pma-eligibility-verification.md` §Adversarial
  review for the full finding. This was the round-1 draft's biggest error:
  it offered a currently-blocked route to a client as compliant.
- **`visa-second-home-variants.jsonl` (the same E33F-cap row, citation
  fix only):** the round-1 draft cited "UU 6/2011 + PP 31/2013" for the
  6-year cumulative-cap rule and "Permenkumham 22/2023 Pasal 185" as the
  "exceptions" article. Primary-text extraction (pdftotext on the actual
  Permenkumham 22/2023 PDF) shows the operative cap article is **Pasal
  113**, and Pasal 185 defines which 4 activities get a 5-or-10-year
  *first grant* (not a generic exceptions clause). The conclusion (E33F
  capped, ~5yr→KITAP) was already correct and is unchanged — only the
  citations were fixed. See `research/visa/
  2026-07-21-e31j-e33f-kitap-verification.md` §Adversarial review.
- **`visa-catalog-sweep.jsonl` (KITAP-RET row) — investigated, NOT
  changed:** the adversarial-review seat also flagged "minimum age 55"
  for E33F as contradicted by the base Permenkumham 22/2023 text (which
  says 60). Independently pulling `permenkumham_11_2024_perubahan_visa.pdf`
  (already in this repo) and running `pdftotext` on it shows Permenkumham
  11/2024 explicitly amends Pasal 33/61/62 from 60 to "55 (lima puluh
  lima) tahun atau lebih" — so the original "age 55" claim was correct;
  the seat's own review hadn't completed checking the amending
  regulation. This is a live example of this repo's own documented scar
  pattern ("even the refuter hallucinates" / "ground-truth can itself be
  stale") — the seat's objection was investigated and found wrong, not
  blindly applied. No change made to this row.

**Why this matters for how you read this package**: round 1 alone would
have shipped a genuinely dangerous error (offering a blocked KBLI as a
compliant route). The adversarial-review step is not decorative — treat
any future single-pass correction to this KB with the same suspicion.
