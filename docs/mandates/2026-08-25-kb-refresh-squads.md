# MANDATE — Bring the knowledge base current to 2026-08-25, by topic squads

> **Launch this in a fresh session.** It is written to be handed to an orchestrator
> that will decompose it into squads. Everything below marked MEASURED was measured
> on 2026-08-25 against production; everything else must be measured before it is
> acted on. Do not treat this file as ground truth a week from now — re-measure the
> counts before you plan.

---

## 0. WORK ITEM ZERO — a year of nightly collection is in a drawer nobody opens

MEASURED 2026-08-25. The live Qdrant holds 14 collections. The one the retrieval
path reads is the alias `legal_unified` → `legal_unified_hybrid_hybrid`:

```
  84283  legal_unified_hybrid_hybrid   <- alias legal_unified, THIS is what is read
  15410  legal_unified_2026            <- written nightly; read by NOTHING
  10825  kbli_2025_final_oss
   3638  training_conversations_hybrid
   3513  balizero_news
   1979  immigration_circulars
   1873  kbli_2025_final_hybrid         <- alias kbli_2025_final
    808  curated_qa
    613  bali_zero_skills_hybrid
    525  intel_authoritative_sources
    340  tax_genius_hybrid
    246  kbli_tka_hybrid                <- alias kbli_tka
     90  visa_oracle
     70  bali_zero_pricing_hybrid
```

`infra/eventbus/regulatory_ingest_runner.py` ingests into
`collection_name="legal_unified_2026"`. That string appears **nowhere** in
`apps/backend-rag/backend/` outside the runner; `backend/core/collection_registry.py`
maps every legal alias to `legal_unified`. So the nightly regulatory watcher has
been depositing regulations into a collection no query reaches.

**Settle this before any new content is gathered**, or the whole campaign lands in
the same drawer:

1. Measure what is actually in `legal_unified_2026` — how many distinct documents,
   which dates, which payload shape, and how much of it is ALREADY in
   `legal_unified` (compare by `document_id` AND by content, never by count).
2. Decide and execute one of: promote it into `legal_unified`, point a reader at it,
   or retire it. State which, and why, in the ledger.
3. Repoint the runner accordingly, in a PR carrying a test that fails if the runner's
   collection name ever again names something the registry does not map.

Same family, already in flight: PR #4897 fixes the runner reporting `ok: True` for
ingests that failed and the CLI reporting `success: True` unconditionally. **Read its
outcome before trusting any historical "ingested" log.**

---

## 1. THE SHAPE OF THE WORK

Per topic squad, one loop, repeated until the topic is exhausted:

```
STUDY     → what does this sector actually consist of, as of 2026-08-25?
GAP       → what of that is NOT in the KB? (measured, both payload shapes)
CATALOGUE → write the missing inventory as a plain, consultable catalogue
ACQUIRE   → obtain the official source document
INGEST    → put it in, under a correct identity, whole
PROVE     → verify it is retrievable and says what the source says
```

**The loop never advances past a stage it cannot prove.** A stage that cannot be
proved is a finding, not something to route around: write it down, move to the next
item in the same topic.

---

## 2. THE SQUADS

One squad per topic. Each owns its topic end to end and writes nowhere else.

| #   | Squad                      | Scope                                                                                     | Primary collections                                     |
| --- | -------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| A   | **Immigration & visa**     | UU 6/2011 + amendments, Permenkumham / Permen Imipas, visa & stay-permit types, circulars | `legal_unified`, `visa_oracle`, `immigration_circulars` |
| B   | **Company & KBLI**         | UU 40/2007, PT / PMA formation, BKPM regulations, OSS, KBLI 2020/2025, capital rules      | `legal_unified`, `kbli_2025_final`, `kbli_tka`          |
| C   | **Tax**                    | UU KUP / PPh / PPN, PMK, e-Faktur & Coretax, treaties relevant to expatriates             | `legal_unified`, `tax_genius_hybrid`                    |
| D   | **Property & land**        | UU 5/1960, Hak Pakai / HGB / leasehold, PP 18/2021, zoning, Bali Perda                    | `legal_unified`                                         |
| E   | **Employment & HR**        | UU 13/2003 as amended by Cipta Kerja, Permenaker, foreign workers (RPTKA / IMTA), BPJS    | `legal_unified`, `kbli_tka`                             |
| F   | **Compliance & reporting** | LKPM, statutory deadlines, annual filings, sanctions                                      | `legal_unified`                                         |

**Squad G — repair**, running alongside. It gathers nothing new; it restores what is
already there and broken (§4).

---

## 3. THE CONTRACT EVERY SQUAD OBEYS

Not style preferences. Each one was paid for.

**3.1 — Measure BOTH payload shapes, always.**
`legal_unified` holds two generations of the same document: modern (top-level
`document_id`, `chunk_key`, `section`) and legacy (`{metadata, text}`, no
`chunk_key`). A probe filtering only `document_id` sees the modern generation and
says nothing about the other. MEASURED: `UU_6_2011` had 258 healthy modern points
AND 261 legacy points of which 118 were damaged — a one-shape probe reported "0
damaged". Query `document_id` **and** `metadata.document_id`, every time.

**3.2 — "Not in the KB" is a measurement, not an impression.**
Before declaring a regulation missing: search by identity
(`type_abbrev`/`number`/`year`), by title text, and by a distinctive verbatim phrase
from the source. Three misses, then it is missing. A document can be present under a
WRONG identity — this corpus holds a 2024 tax circular filed as a 2002 law — so
absence under the right name is not absence.

**3.3 — The catalogue is the deliverable even when the document is not.**
Where a squad finds a gap it cannot close, it still produces the entry: what the
instrument is, its official number and date, what it governs, where the official copy
lives, and why it could not be acquired. Catalogues land in
`research/<domain>/2026-08-25-<slug>.md` with the frontmatter of CLAUDE.md §15
(`date` / `domain` / `client_case` / `sources`). **Never auto-promote to
`apps/backend-rag/backend/kb/`** — that tree is curated by hand.

Catalogues are for a human to consult under pressure: plain tables, official numbers,
one line of what it does, the date it takes effect. No prose essays.

**3.4 — Identity before content.**
The identity guard (`_assert_identity_unclaimed`, PR #4869) refuses to write onto a
`document_id` held by a different source file. It is right and must not be disarmed.
To replace an edition with a fuller one: prove containment FIRST (same article
numbers, same openings), retire the old, then write. Downloading the source under the
SAME basename as the stored original avoids the false positive entirely.

**3.5 — A document goes in whole or not at all.**
PR #4896 makes a partially-read scan raise instead of storing an amputated law. Do
not reach for `allow_partial=True` to get past it. A scan that will not read is a
catalogue entry, not a workaround.

**3.6 — Never delete without a containment proof.**
Before retiring any stored fragment, prove its text survives elsewhere — fragment by
fragment — and print the ratio. MEASURED precedent: 42/42 and 261/261 before the two
deletions of 2026-08-25. One uncovered fragment means do not delete; report instead.

**3.7 — The embedding model is frozen.**
`text-embedding-3-small`, 1536 dims. Changing it invalidates the whole index. Any
proposal to change it is a separate mandate with a re-indexing plan, never a step
inside this one.

**3.8 — Generator ≠ grader.**
Whoever gathered or ingested a topic does not verify it. Every squad's output gets an
independent reader on fresh context, and PRs follow the repository's normal gates.

---

## 4. SQUAD G — the damage already measured (re-verify, do not re-derive)

MEASURED 2026-08-25 across all 84,361 points: **31 documents hold their own
commentary in article slots — 2,042 fragments.** Detection signal: a point whose
`section` is not `penjelasan` and whose text contains `Cukup jelas`.

**G1 — repairable now** (marked elucidation boundary, source obtainable).
Two worked examples to copy: `UU_40_2007` (202 points / 109 poisoned → 379 clean,
195 articles + 184 commentary) and `UU_6_2011` (413 clean; legacy copy retired after
a 261/261 containment proof). Remaining candidates measured MARKED: `UU_11_2020`,
`UU_3_2022`, `UU_23_2002` — the last two also carry an identity problem, see §3.2.

**G2 — needs a capability the parser does not have.** Over half the damage.

- _Unmarked boundary_: `UU_17_2008` (Pelayaran) contains **471** occurrences of
  "Cukup jelas" and **zero** occurrences of the word "PENJELASAN" in the extracted
  text; `UU_66_2024` likewise. No word-based rule can ever find that boundary — it
  needs a structural signal (for instance, the run of `Pasal N` entries whose entire
  body is a note), with its own guilt AND innocence tests.
- _Annexed instruments_: `UU_6_2023` is a ~5,300-character conversion act with the
  entire Cipta Kerja (1.33M characters) attached and two separate elucidations. The
  indexer has no concept of an annexed instrument. 726 damaged fragments wait on it.

**G3 — the source no longer exists anywhere.** 20 documents, ingested from
`/tmp/legal_uploads/` (deleted) or from `/Users/antonellosiano/Desktop/...` (the
laptop decommissioned 2026-05-05). `apps/kb/data/**` exists but holds **0 PDFs** and
git has no history of them. They must be re-acquired officially — the same errand
as §5.

**Where copies DO survive**: the Drive folder `BALI ZERO/PERATURAN`
(`1VswtJMuDWN8BIK9Jahmf19RteikLXlhO`) recovers 9 of them by exact filename.
⚠️ **List it through the DELEGATED identity** (`ServiceAccountDriveService`, which
calls `with_subject`). A bare service-account client lists **0 files** and returns
404 for files that same credential uploaded minutes earlier — a blind probe there
reports an empty archive rather than an inaccessible one.

---

## 5. ACQUIRING OFFICIAL SOURCES

`peraturan.go.id` answers **HTTP 200 with a 74KB HTML error page** for a missing
document. Judge a download by its first four bytes (`%PDF`), never by its status
code. And Indonesian ministries restart their numbering every year, so a filename is
never an identity — extract identity from the document's own title block.

Every acquired PDF is archived to `BALI ZERO/PERATURAN` after ingestion, under its
official name.

---

## 6. WHAT "CURRENT TO 2026-08-25" MEANS

A topic is current when, within its scope:

1. every instrument in force is present, under its correct identity, whole;
2. every superseded or revoked instrument is removed or marked superseded — an
   amended article still answering with its old text is worse than silence;
3. the catalogue lists both sets, with dates;
4. a retrieval probe over the topic's real questions returns the right instrument,
   from the collection the system actually reads.

Point 4 is the only one that proves the other three. **A count is not coverage.**

---

## 7. STOPPING

- Rule 8 of the PR contract applies: three reds for the same cause on the same
  surface and the item SUSPENDS with one ledger line; the squad moves on.
- A squad that finds a defect outside its topic writes it down and does not chase it.
- Business decisions — what we sell, what we advise, what a client is told — belong
  to Zero. Squads produce the material for those decisions; they never make them.

---

## 8. OPEN, OWED BY ZERO

- **The twenty questions the system must never get wrong.** They become the retrieval
  probe of §6.4; until they exist, point 4 is being approximated.
- **The official PDF of UU 25/2007** (Investment Law) — measured absent from the
  corpus, with no copy on any machine.
