---
date: 2026-07-21
domain: visa+property
adversarial_review: exempt-corrections-index
---

# Curated-QA corrections — 2026-07-21

> **Status:** Rounds 1-2 (`property-villa-rental`, `visa-second-home-variants`,
> `visa-catalog-sweep`) were applied + re-harvested to prod on 2026-07-20.
> **Round 3 (this PR)** adds 2 more files — `visa-golden-investor.jsonl` +
> `visa-working-kitas-depth.jsonl` — NOT yet applied (harvest recipe in the
> "Round 3" section at the end). Round 1-2 detail below is preserved as-is.

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

## Round 3 — 4 "suspicious / generic-hedging" review files (2026-07-21, this PR)

The team returned 4 more review files — `02 golden-investor`, `03 business-multientry`,
`07 student`, `18 working-kitas-depth`. Unlike the round-1/2 files, these 4 had ALREADY
been through a rigorous 2026-07-19 arbiter pass (primary-source pdftotext/OCR of PP 34/2021,
Permenaker 8/2021, Permenkumham 22/2023 + 11/2024, plus verbatim imigrasi-page fetches). And
the 4 reviewers were uniformly **legal-cautious** — almost every note is "verify X / don't
state as absolute," a *hedging request*, NOT a concrete factual dispute. Mechanically
softening every such note would degrade the KB (turn precise, sourced, brand-appropriate
answers into hedge-mush) and violate Bali Zero's own voice ("cite the regulation verbatim").
So each concrete, checkable claim was validated against primary/official sources, and only the
genuine ones were applied.

**Result: 3 rows corrected across 2 of the 4 files. The other 2 files
(`business-multientry`, `student`) are clean** — every concrete reviewer point there was
already addressed + primary-sourced in the current version.

### The 3 validated corrections

1. **`visa-golden-investor.jsonl` Q17 (E33 vs E28 comparison) — factual error, fixed.**
   Draft said base E33 Second Home gives "broad freedom to also tour, visit family, **work**,
   or study." **E33 is not a work visa.** Base E33 (the USD 130k-deposit / USD 1M-property
   route) is a pure *residence* permit; it does not authorize employment — paid work needs a
   separate work permit/KITAS. (Work appears only on the government-sponsored E33A/E33C
   variants, with dual-activity "rangkap kegiatan" reporting — see `visa-second-home-variants.jsonl`
   in this same dir, derived from live imigrasi fetches 2026-07-19.) The reviewer caught it,
   and it was internally inconsistent with this KB's own director-vs-worker line (golden Q14;
   student Q11/Q12). "work" removed; "E33 is not a work visa" stated explicitly.

2. **`visa-golden-investor.jsonl` Q5 (E28D) — missing figures added.** The draft
   conservatively omitted E28D's investment threshold. The official imigrasi E28D page states
   verbatim **US$25.000.000** (5-year) / **US$50.000.000** (10-year) — re-fetched 2026-07-21,
   corroborated by the reviewer's independent field claim. Amounts added.

3. **`visa-working-kitas-depth.jsonl` Q10 (RPTKA) — over-statement softened.** Draft said
   "every employer must have an approved RPTKA." **PP 34/2021 Pasal 19** (primary text,
   pdftotext 2026-07-21) exempts a narrow set from the RPTKA requirement itself:
   director/commissioner-shareholders, diplomatic/consular staff, and short-term
   emergency/vocational/start-up/business-visit/research workers. The KB already cited Pasal 19
   elsewhere (golden Q14) — this row just failed to reflect it. Exemptions added.

### Investigated, NOT changed (validated correct as-is)

- **golden Q18 fine schedule** — "Rp 6M → 36M by month six + 2%/month" is PP 34/2021 **Pasal 37**
  verbatim (Rp 6/12/18/24/30/36M) + Pasal 38 (2%/month). Exactly right; the reviewer's "verify"
  is satisfied, no change.
- **All of `visa-business-multientry.jsonl`** — C2-onshore-convert / D1-D2-cannot, 30-day
  alih-status, 60-day/3-day bridging visa, the explicit "31-day is wrong" correction, overstay
  10+10yr/lifetime — all already primary-sourced (Permenkumham 11/2024 pdftotext, PP 45/2024,
  UU 63/2024). No change.
- **All of `visa-student.jsonl`** — the reviewer's notes were 100% "verify against latest
  regulations"; the content is already imigrasi-page-verbatim + Permenkumham-22/2023-pdftotext
  sourced (one-visa-one-permit rule, C9/C9B, C22A/C22B, part-time-work prohibition). No change.

### How to apply Round 3 (2 files, operator-gated harvest)

```bash
cp research/curated-qa-corrections-2026-07-21/visa-golden-investor.jsonl \
   research/curated-qa-corrections-2026-07-21/visa-working-kitas-depth.jsonl \
   apps/backend-rag/data/curated_qa/
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python scripts/curated_qa_harvest.py --write-manifest data/curated_qa/visa-golden-investor.jsonl
PYTHONPATH=. python scripts/curated_qa_harvest.py --write-manifest data/curated_qa/visa-working-kitas-depth.jsonl
PYTHONPATH=. python scripts/curated_qa_harvest.py --qdrant
```

(Re-harvest is an in-place upsert — `_stable_point_id(question, domain)` is domain-scoped and
answer-independent — so no stale-point purge is needed. `--faq` not required: none of the 3
corrected rows change FAQ-sink eligibility in a way that needs the exact-match cache rebuilt
for this fix.)

## Round 4 — company/KBLI "signed lots" review (2026-07-20 review, applied 2026-07-21, this PR)

The team returned `11-company-kbli-signed-lots-REVIEW.docx` — 20 Q&A on specific KBLI 2025
codes (the "signed lots" dossier: 50113, 68126, 68129, 70100, 78109, 66123, 39001, 49296,
80190, 75002, 85321). Reviewer left **"ok"/agreement on 18 of 20** (Q10, Q13, Q17 actively
CONFIRM the draft). Two concrete signals; both validated before applying.

### The concrete signal — reviewer Q9 (75002), a methodological point that generalises

Reviewer: *"75002 is a new KBLI 2025 classification, and the foreign-investment list was
historically structured around KBLI 2020 classifications. Therefore '75002 is not listed as
restricted' does not automatically prove it is unrestricted for PMA."* **Validated correct** —
the Positive Investment List (Perpres 10/2021 as amended by 49/2021) is keyed to KBLI 2020;
a genuinely new/remapped 2025 code's ownership status is not provable from list-absence alone.
Confirmed three ways: (a) the dossier's OWN law_refs already flagged it internally —
75002 `"cross-vintage audit pending, internal-only caveat"`, 80190 `"true 2020 ancestor is
80200… inheritance not yet adjudicated"`; (b) our own dataset `status_mapping` provenance
field; (c) a cross-family regulatory check (Codex GPT-5.6, web-grounded) — Q1 confirmed the
principle; and it surfaced that **80190 (private security) is the sharpest case**: KBLI 2020
80200 carried a **49% foreign cap under Perpres 44/2016 Annex III** (repealed by Perpres
10/2021), sector is POLRI/BUJP-licensed (Perpol 6/2021), and **no current cap could be
established** → verdict *"REVIEW / current cap not established, NOT 100% proven."* BPS also
marks 75002 `"Kode/Cakupan Baru"`.

The gap was **check ≠ surface**: the authors recorded the caveat in internal metadata but the
client-facing answer stated ownership as a settled fact. The fix surfaces the existing caveat —
it does not invent new law.

### The 4 corrections applied

1. **Q11 (80190 security) — strongest.** Ownership downgraded from confident "TERBUKA 100%" to
   "recorded as 100% but current foreign-ownership ceiling not confirmed; sector historically
   restricted + POLRI-licensed; don't structure around full foreign ownership until confirmed."
   (A confident 100% here could be substantially wrong for a client — the E33-work class of error.)
2. **Q9 (75002 vet) — reviewer's target.** Ownership reframed as "recorded, cross-vintage
   confirmation pending" (BPS "Kode/Cakupan Baru"); lead softened "Ownership is open" → "On
   ownership"; added that owning the clinic ≠ the right to practise veterinary medicine (separate
   professional licensing).
3. **Q6 (70100 head office) — reviewer's additive note (correct).** Added: KBLI 70100 and 78109
   (labour placement) are separate activities; a multi-activity PT PMA needs both codes and is
   licensed per activity.
4. **Q16 (register now?) — consistency.** Narrowed "ownership settled even for flagged codes" to
   the general case, with the honest exception for genuinely new/remapped 2025 codes (points to
   Q9/Q11), so the dossier no longer self-contradicts.

### Investigated, NOT changed

- **39001 (carbon capture)** — the cross-family check found **no** current foreign-ownership cap;
  the draft already flags it "brand-new 2025 classification." Left confident (softening it would be
  hedge-mush against the evidence). The specific repealed regulation numbers live in the law_refs as
  leads for team confirmation, not as client-facing verbatim (W65 — a cross-family seat's citation
  is a lead, not gospel).
- **18/20 reviewer notes** were "ok"/agreement or the generic "system doesn't show scope/risk"
  observation (which the dossier already declares as a deliberate withheld-until-verified gap).

### How to apply Round 4 (1 file, operator-gated harvest)

```bash
cd /Users/balizero/nuzantara/apps/backend-rag
# 1) copy the CORRECTED file (absolute worktree path — verified, carries the caveats)
cp /Users/balizero/nuzantara/.worktrees/intel-curated-qa-r4-company-kbli/research/curated-qa-corrections-2026-07-21/company-kbli-signed-lots.jsonl \
   data/curated_qa/
# 2) GATE — must print the NEW text; if it prints the OLD confident line, STOP
if grep -q "do not structure a security business around full foreign ownership" data/curated_qa/company-kbli-signed-lots.jsonl; then
  echo "✅ fix applied — manifest + qdrant"
  source .venv/bin/activate
  PYTHONPATH=. python scripts/curated_qa_harvest.py --write-manifest data/curated_qa/company-kbli-signed-lots.jsonl
  PYTHONPATH=. python scripts/curated_qa_harvest.py --qdrant
else
  echo "❌ STOP: cp did not land the corrected file. Do NOT harvest."
fi
```

(In-place upsert — `_stable_point_id(question, domain)` domain-scoped, answer-independent — the
4 corrected rows overwrite their points at the same ids; no purge. Batch is company-domain, one
new batch_id after the edit.)

## Round 5 — ground-truth sweep of the same dossier (2026-07-21, this PR)

Round 4 processed the *team's* notes. This round re-checked all 11 dossier codes' ownership
claims against the canonical internal ground truth (`data/source_documents/
KBLI_2025_FINAL_CLEAN.json`, `l4_bali` field) and found **3 rows still contradicting it** —
the same error class as the villa round-2 finding (a blocked route presented as usable).
Full capture: `research/company/2026-07-21-kbli-signed-lots-round5-verification.md`.

1. **Q5 (70100 head office) — structural PMA block, HIGH confidence.** The dataset's l4_bali
   record is `CHIUSO_PMA_NO_BESAR, blocked: true`: OSS carries **no Usaha Besar scale row** for
   70100 (Mikro/Kecil/Menengah only) → the code is reserved for UMKM and a PT PMA (Usaha Besar
   by law) **cannot register under it at all**. The round-4 answer still said "open to full
   foreign ownership (TERBUKA, 100%)" and advised registering under 70100. Rewritten: paper
   TERBUKA vs practical unregistrability, scoping guidance corrected to **KBLI 64210** (the
   KBLI-2025 holding code — adversarial review caught the draft repeating the 2020-vintage
   "64200", which does not exist in KBLI 2025), and the finding re-attributed to the canonical
   dataset with its provenance caveats (HIGH mark inherited pre-detachment — logged in the
   capture).
2. **Q6 (70100 next steps) — sequencing fix.** "Nothing stops you from proceeding with company
   incorporation" was wrong for this code. Now: classification first (70100 substitute or
   64210), incorporation after; round-4's 78109 staffing note kept.
3. **Q13 (66123 crypto brokerage) — Bali moratorium caveat, LOW confidence (hedged).** l4_bali
   is `CHIUSO_MORATORIA_BALI, blocked: true` but `confidence: LOW, needs_review: true` (the
   risk-tier reading behind it was detached to `per_skala_disputed_pp28_collision`, pending
   GARUDA-FILIERA re-derivation). Added an explicitly-hedged Bali caveat: "would place it in
   the blocked group… treat Bali registrability as unresolved until confirmed." Not asserted
   as settled — mirrors the dataset's own confidence state.

**Investigated, NOT changed:** Q4 (68129) — `CHIUSO_BALI_PROPOSTO` is a *proposed*, not
effective, Bali closure (`blocked: false`). Q9/Q11/Q16 — round-4 amendments already correct.
The Q3 reviewer's "check dinas perhubungan" pointer for warehousing is **not supported**
(warehouse registration is TDG under PP 29/2021, trade/Kemendag lineage, via OSS) — logged as
a lead.

**Adversarial review (R1 gate):** FIX-THEN-SHIP from an independent seat (fresh Kimi
subagent with refuter brief — Codex MCP timed out ×2 and `codex exec` hung, so the
cross-model seat was unavailable; flagged for transparency). It caught one real error —
the "KBLI 64200" holding reference (2020 vintage; correct code 64210, verified in the
canonical dataset) — plus two calibration issues (70100 HIGH-mark provenance, 68129
justification resting on a detached payload). All fixed in place; full detail in the
capture's §Adversarial review.

### How to apply Round 5 (1 file, operator-gated harvest)

```bash
cd /Users/balizero/nuzantara/apps/backend-rag
# 1) copy the CORRECTED file (from the merged main checkout's research/ dir)
cp ../../research/curated-qa-corrections-2026-07-21/company-kbli-signed-lots.jsonl \
   data/curated_qa/
# 2) GATE — must print the NEW text; if not, STOP
if grep -q "cannot actually be registered under 70100" data/curated_qa/company-kbli-signed-lots.jsonl; then
  echo "✅ fix applied — manifest + qdrant"
  source .venv/bin/activate
  PYTHONPATH=. python scripts/curated_qa_harvest.py --write-manifest data/curated_qa/company-kbli-signed-lots.jsonl
  PYTHONPATH=. python scripts/curated_qa_harvest.py --qdrant
else
  echo "❌ STOP: cp did not land the corrected file. Do NOT harvest."
fi
```

(Same in-place upsert semantics as round 4 — 3 corrected rows overwrite their points at the
same stable ids; none is `verbatim_eligible`, so `--faq` is not required.)
