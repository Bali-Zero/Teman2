# Decision 5 — superseded instruments: remove or mark?

> ⚠️ **Status note, read before anything else.** `OWNER-SWITCHBOARD.md` already carries a
> **SIGNED** block (Zero, 2026-08-25, commit `41bd4c205`) picking **MARK** for Decision 5, on
> the evidence of one document pair (Permenkumham 22/2023 vs 29/2021, J4 ranking). This file
> was requested as a standalone Decision-5 brief and was built independently from a
> full-corpus census taken the next day (2026-08-26). It **confirms** MARK, but the picture
> changed twice while building it, and the second change is the important one:
>
> 1. The defect is ~100x the scale that grounded the original signature (50.3% of the corpus,
>    not one document pair), plus a concrete article-level failure the original brief didn't
>    have (below).
> 2. **A first draft of this file recommended building a document-level MARK mechanism from
>    scratch. That was wrong, and a peer review caught it before it shipped.** The
>    _enforcement_ mechanism this decision needs — the filter that keeps a marked chunk out of
>    "current law" answers — already exists, is already wired into the live query path, and is
>    non-bypassable. That correction stands.
> 3. **The correction above was itself half-true, and a second review caught the other half.**
>    "The reader exists" was read as "the fix is ready" — it isn't. The 2-points-of-84,283 fact
>    has a traceable cause: the only code path that ever writes `retrieval_scope:
historical_only` (`_quarantine_current_points`,
>    `legal_ingestion_service.py:341-357`) operates on a **whole document_id**, exists to
>    quarantine an entire prior edition **before a full replacement is ingested**, and has never
>    been exercised for a real document-vs-amendment pair in this corpus (verified below). There
>    is **no governed path that writes this field at chunk/pasal granularity** — the low-level
>    client call it would need (`QdrantClient.set_payload(ids, payload)`,
>    `qdrant_db.py:993`) exists but today is called only from two unrelated one-off KBLI
>    maintenance scripts, never from a legal-KB service. Every section below now separates "the
>    filter is armed" (true, unconditionally) from "the write path exists" (false, at the
>    granularity this decision needs) — the two were fused in the previous revision and that was
>    the error. Nothing here was taken on either reviewer's word: every claim in this note was
>    re-run independently against source and against production before this revision, and the
>    revision history above is kept rather than silently replaced, per the discipline this
>    campaign asks of every lane.

## The question, in three lines

`legal_unified` marks 42,420 of 84,283 points (50.3%, 198 of 388 documents) `legal_status:
dicabut` ("revoked"). At least 7 of 9 documents whose true status is externally verifiable are
marked wrong — including the pillars of the practice (Immigration Law, Company Law, Cipta
Kerja, Labor Law). Do we **REMOVE** what's marked revoked, or **MARK** it and keep it
retrievable?

## How much this actually touches

- **42,420 points / 198 documents** carry `dicabut` today (measured 2026-08-26,
  `legal_unified_hybrid_hybrid`, 84,283 points / 388 documents, both payload shapes read,
  completeness proven arithmetically — per-document point sums equal the collection total).
- Of those 198 dicabut-majority documents, **3 (661 points)** are simultaneously the target of
  an amendment title _present in this same corpus_ — i.e. provably alive, not merely
  suspected: `UU_6_2011` Keimigrasian (413 pts, amended by `UU_63_2024`), `UU_31_2004`
  Kepailitan (204 pts, 169 dicabut, amended by `UU_45_2009`), `UU_7_1983` PPh (44 pts, amended
  by `UU_36_2008`). This is a **lower bound**: title-based amendment matching only works for
  185 of 388 documents (the other half carry no `[CONTEXT:]` header the census can read), and
  requires an exact `TYPE_NOMOR_TAHUN` regex match. The 2026-08-26 ledger entry, working from
  the full per-point distribution rather than a per-document majority, independently found 2
  strict-form violations and 6 weak-form — same phenomenon, different threshold, consistent
  direction.
- **REMOVE, today, would delete at minimum those 661 points of in-force law** — and by the
  same logic probably far more, since 50.3% of the corpus carries a mark now shown untrustworthy
  in 7 of 9 spot-checked cases.

## Three fields, one concept, only one of them works — the inventory fact everyone after this file needs

`legal_unified` carries **three separate payload fields** that all speak to "is this chunk
current law", and they are not interchangeable. Verified against the live source
(`search_filters.py`, `search_service.py`, `legal_ingestion_service.py`) and against a fresh
full-corpus scan (84,283 points, both payload shapes, 2026-08-26):

| field             | populated on                                                                       | read by                                                                                                                                                                                                                                                                             | behaves as                                                                                                                                           |
| ----------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `legal_status`    | 77,539 / 84,283 pts (92.0%)                                                        | **nobody** in the live query path                                                                                                                                                                                                                                                   | inert — systemically false (50.3% `dicabut`, 7 of 9 spot-checked docs wrong) and consequence-free either way                                         |
| `status_vigensi`  | 0 / 84,283 pts, 0 / 14 collections                                                 | `search_filters.py:86`, wired into every `legal_unified`/`tax_genius` query via `_requires_current_law_guard`                                                                                                                                                                       | armed, but tests a key nobody ever writes — fires on every query, excludes nothing                                                                   |
| `retrieval_scope` | 4,697 `current` (5.57%) · **2 `historical_only`** (0.00%) · 79,584 absent (94.42%) | `search_filters.py:91`, same guard, **and re-asserted even when a caller explicitly disables other filtering** (`search_service.py:554-564`: `apply_filters is False` still rebuilds `exclude_historical=True` — comment: _"historical evidence is never eligible as current law"_) | **read side (enforcement): the only one of the three that actually bites. Write side: no governed path writes it at chunk granularity — see below.** |

`retrieval_scope: historical_only` is excluded from every `legal_unified`/`tax_genius` search
via a hard `$ne` (Qdrant `must_not`, not a demotion), on a code path that survives even the
`apply_filters=False` internal-caller escape hatch. **This is the enforcement half of what this
campaign needs, and it is solid.** It has been used on **one document, two points**
(`Perpres_43_2011__historical`) since whenever it was built. Confirmed independently by a full
scan of all 84,283 points (both `retrieval_scope` and `metadata.retrieval_scope`).

Two structural notes on the read side that make it more than a naming curiosity:

- Writing `retrieval_scope: historical_only` on a fresh ingest requires the ingestion service to
  call `ensure_keyword_payload_index` on **both** `retrieval_scope` and `metadata.retrieval_scope`
  (`legal_ingestion_service.py:567-569`) — this collection is flat-payload, so an unindexed key
  filter returns Qdrant HTTP 400, not "0 results" (mandate §4.1's general warning, confirmed here
  on the specific field this decision needs).
- `HISTORICAL_RETRIEVAL_SCOPE` is validated at ingestion time
  (`validate_legal_retrieval_scope`, `legal_ingestion_service.py:204`) against a two-value enum
  (`current` / `historical_only`) — it is a real, tested code path, not a stub.

**But the write side is missing at the granularity this decision needs, and this is the
correction to the previous revision.** The only code that ever writes this field is
`_quarantine_current_points` (`legal_ingestion_service.py:341-357`):

```python
async def _quarantine_current_points(vector_db, document_id) -> list[str]:
    """Mark a previous current-law version historical before replacement."""
    await vector_db.set_payload_by_filter(
        metadata_filter={"document_id": document_id},
        payload={"retrieval_scope": HISTORICAL_RETRIEVAL_SCOPE})
```

It filters on **`document_id` alone** — every point of a document, no partial selection — and
its one caller (`legal_ingestion_service.py:1070`) invokes it only as a pre-step before ingesting
a **full replacement edition** of the same `document_id`. It was never designed to, and cannot,
mark one pasal inside a document that otherwise stays current. Applying it to `UU_6_2011` today
would flip all 413 points — the entire base immigration law — to `historical_only`, removing it
wholesale from current-law answers. That is the same class of catastrophe the 2026-08-25
signature already warned against for `legal_status`, arrived at by a different mechanism.

A per-point write **is** technically available — `QdrantClient.set_payload(ids, payload)`
(`qdrant_db.py:993`) takes an explicit id list — but nothing in the legal-KB service layer calls
it. Its only two callers in the whole backend are one-off KBLI maintenance scripts
(`scripts/kbli_qdrant_risk_clear.py`, `scripts/kbli_lot10_partial_detach_93114_93191.py`),
unrelated to this corpus and carrying none of this decision's protections (no identity check
equivalent to `_assert_identity_unclaimed`, no audit trail, no undo path). Marking a specific
pasal chunk today means either building that governed path, or writing an unprotected ad-hoc
script against production — which is not a decision this file can wave through as "just data
work."

The 2-of-84,283 count is explained by this, not by neglect: `Perpres_43_2011__historical` is a
document _ingested directly under that suffixed identity as historical_ (there is no plain
`Perpres_43_2011` in the corpus for it to have been quarantined from — `_quarantine_current_points`
writes onto the _same_ `document_id`, it never renames one). It is not a residue of the
quarantine-before-replacement flow; it looks like a document loaded once, deliberately, as a
historical reference. **A genuine quarantine-before-replacement has apparently never been
exercised in this corpus**, despite the volume of amend-in-place cases this campaign has found
that would have been candidates for it.

## The concrete failure REMOVE-vs-MARK does not fully answer by itself

The mandate's own §7 framing says an amended article still answering with its old text is
worse than silence. Here is that exact failure, measured live, not argued:

**`UU_6_2011` Pasal 102 (Penangkalan / entry-ban duration) vs its amendment `UU_63_2024`
Pasal 102** — both retrieved from `legal_unified_hybrid_hybrid` on 2026-08-26, both carrying
`retrieval_scope: "current"` (the field the live guard actually checks), no chunk carries any
supersession pointer to the other (no such field exists in the payload schema on either
point):

|                             | point id                               | `legal_status` | `retrieval_scope` | text                                                                                                                               |
| --------------------------- | -------------------------------------- | -------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **base**, `UU_6_2011`       | `9583daba-2641-55f9-b79c-a1a7717deebd` | `dicabut`      | `current`         | _"Jangka waktu Penangkalan berlaku paling lama **6 (enam) bulan** dan setiap kali dapat diperpanjang paling lama 6 (enam) bulan."_ |
| **amendment**, `UU_63_2024` | `499793b0-cae2-5a19-9f0e-4f588da732e9` | `berlaku`      | `current`         | _"Jangka waktu Penangkalan berlaku paling lama **10 (sepuluh) tahun** dan dapat diperpanjang paling lama 10 (sepuluh) tahun."_     |

The maximum duration of an immigration entry-ban went from **6 months to 10 years** in this
amendment. A client asking "how long can a penangkalan last" can be answered from either
chunk — both are `retrieval_scope: current`, so the base chunk is not excluded by the guard
that actually runs (`retrieval_scope != historical_only` — see the field inventory above): its
`legal_status: dicabut` is irrelevant to retrieval either way, since nothing reads that field.
The cure is not to fix `legal_status`; it is to flip this one chunk's `retrieval_scope` to
`historical_only`, which the live guard already enforces. The same pattern repeats, measured on
the same document pair, for **Pasal 103** (implementing regulation moved
from Peraturan Pemerintah to Peraturan Menteri), **Pasal 137** (funding source expanded from
state-budget-only to state-budget-plus-other-sources), and **Pasal 16** (grounds for exit
refusal changed from "penyelidikan dan penyidikan" to "penyidikan dan penuntutan"). Three
other shared pasal (**1, 64, 97**) were checked and found textually unchanged — the method
does discriminate changed from unchanged articles, this is not an artifact of the regex.

Method note for auditability: comparison is keyed on the payload's own `pasal_number` field
(present on both documents), restricted to non-`penjelasan` chunks — not on a naive "Pasal N"
text-substring match, which over-matches cross-references to an article from inside a
different article (verified: a naive match found only 6 "common" pasal, mostly spurious
citations; the `pasal_number`-keyed match found 8, all genuine article bodies).

**Why this is a second, distinct defect from `legal_status` being wrong**: even a perfectly
repaired `legal_status` (document-level: "this whole instrument is dicabut/berlaku") does not
touch this failure, because `UU_6_2011` **is not wholly superseded** — it is the live base law,
amended article-by-article. A document-level MARK correctly keeps the whole document
retrievable (right call) but does nothing to stop Pasal 102's pre-2024 wording from being
served as if current.

**The cure for exactly this does not require a new field, but it does require a new write path.**
Setting `retrieval_scope: historical_only` on the four superseded chunks identified above
(`UU_6_2011` Pasal 102/103/137/16) would stop them answering as current law, on every path that
calls `build_search_filter` — no deletion, no touch to `legal_status`, no new _filter_ code. But
nothing in the service layer can make that write today at chunk granularity (see the write-side
gap above): the only existing writer is document-wide and would delete the whole of `UU_6_2011`
from current-law answers, which is worse than the defect it would fix. So the honest cost has
three parts, not one: (a) identifying which pasal an amendment rewrites, across all ~66
amendment relations in the corpus (`.claude/skills/modus/PENDING-ARMS.md:1374` records this as a
missing step); (b) building a governed per-point write path — with its own identity/audit/undo
protections, since none exists today — because the one governed writer that exists operates at
the wrong granularity; (c) deciding what a partially amended article should express, since
`retrieval_scope` is **binary per chunk** and cannot represent "ayat 2 changed, ayat 1 didn't."

## The two options, retrieval consequence measured

### REMOVE

What a client loses, permanently and unrecoverably, given 4.6 ("never delete without a
containment proof" — none exists here): at minimum the 661 points of the three documents
proven amended-not-repealed above, and — since the 50.3%/dicabut mark is shown wrong on 7 of 9
externally-checkable documents — an unknown, unbounded further slice of the other 195
dicabut-majority documents that have not yet been individually checked. A client asking about
the entry-ban duration, the KBLI/company-law provisions, or Ketenagakerjaan protections gets
**silence** on a topic Bali Zero answers every day, with no way to reconstruct what was there
short of re-acquiring source PDFs (§6 already records 20 of 31 damaged documents as
source-gone). Irreversible; also the harder option to test (§4.2: absence is a claim that
needs three measurements, not a green check).

### MARK — enforcement is armed, the writer at the needed granularity is not

A client asking the same question would get the current article, with the superseded chunk
excluded, on every path through `build_search_filter` — **once the chunk is actually marked.**
Measured facts that bound this option, split by side because the two do not carry the same
weight:

**Enforcement (read side) — solid, no work needed:**

- `retrieval_scope: historical_only` is a **hard Qdrant `must_not`** (excluded from the query,
  invisible to reranking and fallback, not demoted) and it is **not disable-able**: even the
  internal `apply_filters=False` escape hatch rebuilds `exclude_historical=True` by explicit
  design (`search_service.py:554-564`, comment: "historical evidence is never eligible as
  current law").
- It does **not** touch `legal_status` at all, so it carries none of the risk the earlier draft
  of this option (repair `legal_status`, wire it into `status_vigensi`) did: no chance of
  turning a 50.3%-of-corpus hard exclusion live on a field that is currently inert. The two
  problems (document `legal_status` is wrong; chunk `retrieval_scope` is under-used) are
  independent and should be worked independently — do not fold the `legal_status` repair into
  this option's critical path.
- What it does NOT protect, even fully populated: `HybridSearchService`
  (`backend/services/rag/hybrid_search.py`) never calls `build_search_filter` at all, and
  `prime.py:42` / `visa_oracle.py:1064` (the Visa Oracle chat endpoint) call search without
  `filters=`. MARK via `retrieval_scope` is real and non-bypassable on the path that uses it —
  and there are two production surfaces that don't use that path.

**Writing the mark (write side) — the actual remaining work, not yet started:**

- The only existing writer, `_quarantine_current_points`, is document-wide and exists solely to
  quarantine a full prior edition before a full replacement — using it on `UU_6_2011` would
  remove the entire base immigration law from current-law answers to fix four pasal. It cannot
  be reused as-is.
- A per-point writer (`QdrantClient.set_payload`) exists at the client-library level but has no
  service-layer caller for this purpose and none of this decision's expected protections
  (identity check, audit, undo). Building one is real engineering work, not a config change.
- Deciding what a partially-amended article should express is unresolved: `retrieval_scope` is
  binary per chunk, so "Pasal 102 fully rewritten" and "Pasal 16 one clause changed" are
  indistinguishable to the field as it exists.
- MARK is still testable in principle (a journey can assert "current instrument's phrase ranks,
  superseded instrument's phrase is either absent or explicitly historical") once a write path
  exists; REMOVE is not testable at all (absence needs the three-measurement standard of §4.2,
  on a moving 84,283→growing corpus). That comparative advantage survives the correction — it
  is the write-side readiness claim that does not.

## On the team's suggested third option ("record status, gate action on verification")

Re-examined against the corrected picture: this doesn't apply to `retrieval_scope` the way it
applied to the earlier (wrong) framing. `retrieval_scope` is **already live and already gated**
by construction — nothing about populating it turns on a dormant filter, because the filter is
already on. The sequencing risk lives specifically in `legal_status` → `status_vigensi`: **do
not** populate `status_vigensi` from `legal_status` before `legal_status` itself is repaired,
because that specific gesture (unlike `retrieval_scope`) would arm a 50.3%-of-corpus hard
exclusion against data still shown wrong. Keep that as a standing constraint on the _separate_
`legal_status` repair track, not as a condition on marking `retrieval_scope` — the latter has no
such landmine, which is exactly what makes it the option to act on now.

## Recommendation

**MARK, targeting `retrieval_scope: historical_only` at chunk granularity — not REMOVE.** This
is the same pick 2026-08-25's signature already made, now on ~100x the evidence, with the
concrete confirmation (Pasal 102/103/137/16) that unmarked pasal-level staleness is a real,
present failure. Two things are true at once, and this revision's correction is keeping them
separate rather than collapsing them into "it's basically done":

1. **The enforcement this decision needs already exists and needs no work** — the filter is
   armed, non-bypassable, and correctly scoped to exclude only what is explicitly marked
   historical.
2. **The writer this decision needs does not exist and is real, uncosted engineering work** —
   the only writer in the codebase operates at document granularity and would be destructive if
   reused here; a chunk-level writer has to be built, with its own protections, before any pasal
   gets marked.

REMOVE stays the wrong choice regardless: it is irreversible against data already shown wrong
on 7 of 9 checkable cases, and untestable per §4.2. But "pick MARK" should not be read as "the
fix is ready to ship" — it isn't. Recommend: (a) confirm MARK as the direction (unchanged from
2026-08-25), (b) open the write-path build as its own scoped unit of work — not a data-entry
task riding on the existing filter — before any pasal-level marking is attempted, (c) keep the
`legal_status` repair on its own separate track as before.

## What we don't know

- **Closed, round 1**: which field actually gates retrieval. An earlier draft of this file
  treated `status_vigensi` as the mechanism to build and repair — that was wrong; `retrieval_scope`
  is the field that is armed, non-bypassable, and correct by design.
- **Closed, round 2**: why `retrieval_scope: historical_only` has been used on only 2 of 84,283
  points. Answer, traced to source: **the only writer (`_quarantine_current_points`,
  `legal_ingestion_service.py:341-357`) is document-wide and fires solely as a pre-step before a
  full-document replacement ingest; no per-chunk writer exists anywhere in the service layer.**
  This was the second half of the "the mechanism is armed" finding, and treating "read side
  works" as "the fix is ready" was itself an error caught by a second review — recorded here
  rather than silently overwritten, matching the discipline this campaign asks of every lane:
  wrong yesterday in one way, wrong today in a narrower way, both corrections kept visible.
- **New and still open**: _why has a quarantine-before-full-replacement never been exercised in
  this corpus_, given how many amend-in-place cases this campaign has found (~66 amendment
  relations, at least 3 provably alive-but-marked-dicabut documents) that would plausibly have
  gone through a full-replacement re-ingest at some point. Not checked here: whether this
  corpus has simply never had a document replaced wholesale, or whether replacements happened
  through a path that bypasses `_quarantine_current_points` entirely.
- **The dicabut-and-amended count (661 pts / 3 docs) is a lower bound**, not a census: title
  matching only reaches 185/388 documents that carry a `[CONTEXT:]` header, and only catches
  the specific `PERUBAHAN ... ATAS <TYPE> NOMOR <N> TAHUN <YEAR>` phrasing. Documents with no
  header, or amendments phrased differently ("diubah dengan", partial insertions), are
  invisible to this method — the true count of alive-but-marked-dicabut documents is higher,
  not lower, than 3.
- **The "ground truth" column (which of the 9 documents is really `berlaku`/`dicabut`) is
  domain knowledge — reviewable, not self-proving.** The amendment invariant ("A titled
  `PERUBAHAN ... ATAS B` ⇒ B is not revoked") is self-contained and does not depend on that
  domain knowledge; do not fuse the two kinds of evidence as if they carried the same
  authority — the ledger entry is explicit about keeping them in separate columns.
- **The Pasal-level comparison covers exactly one document pair** (`UU_6_2011` /
  `UU_63_2024`), the pair named in the mandate as the first thing to try. It generalizes by
  construction to every other amended-base-law pair in the corpus (`UU_40_2007`/`UU_6_2023`,
  `Permen_22_2023`/`Permen_11_2024`, etc.) but those pairs were not individually re-run here.
- **The collection is not frozen while being audited** — the 2026-08-26 ledger entry notes
  84,283 points that day against 83,969 the day before (+314), most plausibly from parser-repair
  lanes in flight. Numbers in this file are a snapshot, not a fixed target.

## Side-note: Decision 2 (UU 25/2007), checked in passing, no new work implied

Census confirms **UU 25/2007 (Penanaman Modal / Investment Law) is PRESENT**: `document_id
UU_25_2007`, 65 points, title `UU - NO 25 - TAHUN 2007 - TENTANG PENANAMAN MODAL`, all marked
`dicabut`. The mandate's §7 line ("measured absent from the corpus and from every machine") is
wrong; `OWNER-SWITCHBOARD.md`'s own correction table already caught this on 2026-08-25 ("Present:
65 points ... Not absent; hollow") and Decision 2 is already signed on that corrected basis
("re-acquire UU 25/2007 whole"). This file's own count (65 points, same title, same status)
corroborates that correction independently — no new gesture needed here.
