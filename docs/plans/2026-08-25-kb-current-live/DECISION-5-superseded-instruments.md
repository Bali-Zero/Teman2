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
>    scratch. That was wrong, and a peer review caught it before it shipped.** The marking
>    mechanism this decision needs **already exists, is already wired into the live query path,
>    is already non-bypassable, and has been used on exactly 2 of 84,283 points.** The real
>    decision is not "which mechanism do we build" — it's "why isn't the one we have used", and
>    "mark" now means _populate an existing field on the specific chunks that need it_, not
>    _design and ship a new filter_. Every section below reflects that correction; nothing here
>    was taken on the reviewer's word — every claim was re-run independently against
>    production before being written into this revision (see inline point-ids and the
>    full-corpus scan below).

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

| field             | populated on                                                                       | read by                                                                                                                                                                                                                                                                             | behaves as                                                                                                   |
| ----------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `legal_status`    | 77,539 / 84,283 pts (92.0%)                                                        | **nobody** in the live query path                                                                                                                                                                                                                                                   | inert — systemically false (50.3% `dicabut`, 7 of 9 spot-checked docs wrong) and consequence-free either way |
| `status_vigensi`  | 0 / 84,283 pts, 0 / 14 collections                                                 | `search_filters.py:86`, wired into every `legal_unified`/`tax_genius` query via `_requires_current_law_guard`                                                                                                                                                                       | armed, but tests a key nobody ever writes — fires on every query, excludes nothing                           |
| `retrieval_scope` | 4,697 `current` (5.57%) · **2 `historical_only`** (0.00%) · 79,584 absent (94.42%) | `search_filters.py:91`, same guard, **and re-asserted even when a caller explicitly disables other filtering** (`search_service.py:554-564`: `apply_filters is False` still rebuilds `exclude_historical=True` — comment: _"historical evidence is never eligible as current law"_) | **the only one of the three that actually bites**                                                            |

`retrieval_scope: historical_only` is excluded from every `legal_unified`/`tax_genius` search
via a hard `$ne` (Qdrant `must_not`, not a demotion), on a code path that survives even the
`apply_filters=False` internal-caller escape hatch. It is the field this campaign needs. It has
been used on **one document, two points** (`Perpres_43_2011__historical`) since whenever it was
built. Confirmed independently by a full scan of all 84,283 points (both `retrieval_scope` and
`metadata.retrieval_scope`) — not taken from the reviewer's count.

Two structural notes that make this more than a naming curiosity:

- Writing `retrieval_scope: historical_only` on a fresh ingest requires the ingestion service to
  call `ensure_keyword_payload_index` on **both** `retrieval_scope` and `metadata.retrieval_scope`
  (`legal_ingestion_service.py:567-569`) — this collection is flat-payload, so an unindexed key
  filter returns Qdrant HTTP 400, not "0 results" (mandate §4.1's general warning, confirmed here
  on the specific field this decision needs).
- `HISTORICAL_RETRIEVAL_SCOPE` is validated at ingestion time
  (`validate_legal_retrieval_scope`, `legal_ingestion_service.py:204`) against a two-value enum
  (`current` / `historical_only`) — it is a real, tested code path, not a stub.

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

**The cure for exactly this does not require a new field.** Set
`retrieval_scope: historical_only` on the four superseded chunks identified above (`UU_6_2011`
Pasal 102/103/137/16) and they stop answering as current law **today**, on every path that
calls `build_search_filter` — no deletion, no touch to `legal_status`, no new code. This is the
first cure in this whole campaign that can be shipped by populating a field the system already
enforces, rather than by building enforcement first. The honest cost, not hidden: it is **still
chunk/pasal-level work, one article at a time** — identifying which pasal an amendment rewrites
across all ~66 amendment relations in the corpus (`.claude/skills/modus/PENDING-ARMS.md:1374`
records this as the still-missing step: knowing _which_ chunk to mark). `retrieval_scope` is
the mechanism; it does not supply the list of what to mark. And it is **binary per chunk**: a
pasal partially amended in one ayat but not another has no way to say so — the field can only
say "this whole chunk is/isn't current."

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

### MARK — using the mechanism already armed (`retrieval_scope`), not building a new one

A client asking the same question gets the current article; the superseded chunk stops being
eligible as an answer at all, on every path through `build_search_filter` — because the guard
already runs and already excludes on this exact field. Measured facts that bound this option:

- `retrieval_scope: historical_only` is a **hard Qdrant `must_not`** (excluded from the query,
  invisible to reranking and fallback, not demoted) and it is **not disable-able**: even the
  internal `apply_filters=False` escape hatch rebuilds `exclude_historical=True` by explicit
  design (`search_service.py:554-564`, comment: "historical evidence is never eligible as
  current law"). Nothing needs to be built to make marking bite — it already does, on the 2
  points where it has been used.
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
- MARK is testable (a journey can assert "current instrument's phrase ranks, superseded
  instrument's phrase is either absent or explicitly historical"); REMOVE is not (absence needs
  the three-measurement standard of §4.2, on a moving 84,283→growing corpus).
- The work this option actually requires is **identifying which chunk to mark**, article by
  article, across the corpus's amendment relations — not designing or wiring a filter. That
  work is real (see Pasal 102/103/137/16 above; ~66 amendment relations corpus-wide per the
  2026-08-26 ledger entry) but it is retrieval-repair work, not retrieval-infrastructure work.

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

**MARK, using `retrieval_scope: historical_only` on identified superseded chunks — not REMOVE,
and not a new mechanism.** This is the same pick 2026-08-25's signature already made, now on
~100x the evidence, with the concrete confirmation (Pasal 102/103/137/16) that unmarked
pasal-level staleness is a real, present failure, and — the correction that matters most in
this revision — with the discovery that the enforcement path for this exact fix already exists,
is already non-bypassable, and is sitting almost entirely unused (2/84,283 points). The
remaining work is identifying which chunks to mark, not building or arming anything. Keep the
separate, slower `legal_status` repair on its own track, gated as described above; it protects
against a different and larger risk (document-level mislabeling) and should not block chunk-level
marking, which can start today.

## What we don't know

- **Closed in this revision**: which field actually gates retrieval. An earlier draft of this
  file treated `status_vigensi` as the mechanism to build and repair — that was wrong;
  `retrieval_scope` is the field that is armed, non-bypassable, and correct by design. Recorded
  here explicitly rather than silently overwritten, per the discipline this campaign asks of
  every lane: we had it wrong yesterday, a peer review caught it, both the old and the corrected
  claim were re-verified against source and against a live full-corpus scan before this file was
  rewritten.
- **New and still open**: _why_ `retrieval_scope: historical_only` has been used on only 2 of
  84,283 points, given the mechanism is real, tested, and has clearly existed for some time (the
  ingestion validator, the two required payload indexes, the non-bypassable guard are not
  quick additions). Two live hypotheses, neither checked here: it was built for one narrow pilot
  (`Perpres_43_2011__historical`) and never extended: or it was built as general
  infrastructure and the identification-of-what-to-mark step never landed. The difference
  matters for how much of "populate retrieval_scope on the superseded chunks" is genuinely new
  work versus resuming an abandoned rollout — worth one targeted grep of the commit that
  introduced the field before scoping lane-A2's task.
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
