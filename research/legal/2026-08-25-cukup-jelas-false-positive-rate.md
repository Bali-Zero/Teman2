---
date: 2026-08-25
domain: legal
client_case: none — KB current-live campaign, Lane P (parser capability)
adversarial_review: codex
sources:
  - live measurement against Qdrant collection `legal_unified_hybrid_hybrid`
    (registry name `legal_unified`), 84,283 points, scrolled in full
  - kb/inventory/legal_unified_2026.yaml (campaign context, measured_at 2026-08-25)
  - apps/backend-rag/backend/services/ingestion/legal_ingestion_service.py
  - apps/backend-rag/backend/core/legal/metadata_extractor.py
  - orchestrator's WhatsApp-mirror traffic census (60,004 inbound 2022-12→2026-08-24,
    10,929 question-bearing: immigration 2,752 / company 656 / tax 298 / property 187),
    relayed 2026-08-25, added to this report as an addendum after the initial
    measurement was already complete and shipped
---

# The §6 "Cukup jelas" damage signal: measured false-positive rate, and three
# findings that fell out of reading the sample

## Summary

The KB current-live campaign's §6 damage signal — a point whose `section` is
not `penjelasan` and whose text contains "Cukup jelas" (Indonesian legal
boilerplate meaning "sufficiently clear", used almost exclusively as
elucidation/commentary marking an article as needing no further explanation)
— reports **2,019 damaged fragments across 34 documents** in `legal_unified`.

That number had never been checked for innocence. It has now: a stratified
sample of 45 flagged fragments, spread across 34 distinct documents (every
document that has ANY flagged fragment), was read in full.

**Measured false-positive rate: 0/45 (0%), with document-level (not
fragment-level) sampling guarantees — see the statistical caveat in Method.**
Every sampled fragment was genuinely elucidation-style text. The 2,019/34
figure is not a fiction. A related structural signal exists that plausibly
catches additional elucidation content the substring match misses (Finding
3), but its precision is unvalidated and an earlier draft of that finding
over-claimed what the evidence supports — see Finding 3 for the corrected,
more cautious version.

## Method

`scripts/kb/cukup_jelas_sample.py` (whole-or-nothing: no `allow_partial`,
prints `BROKEN` and exits 3 rather than reporting a partial count) scrolled
all 84,283 points of `legal_unified_hybrid_hybrid` and flagged every point
where `section != "penjelasan"` (checked at both `payload.section` and
`payload.metadata.section`, since only 792/84,283 points carry `section` at
all — the two 2026-08-25 repairs, UU_6_2011 and UU_40_2007) AND
`re.search(r"cukup\s+jelas", text, re.IGNORECASE)` matched.

This reproduced the campaign's own reported numbers exactly: 2,019 fragments,
34 documents. That reproduction is itself useful — it confirms the campaign's
§6 figure was measured the same way this report re-measures it, not from a
different or stale run.

A sample of 45 was then drawn: shuffled document order (seed `20260825`,
fixed, not time-based per repo convention — `random`/`Date.now()` are banned
in reproducible tooling), then round-robin across documents until 45 items
were collected. This deliberately avoids "first 45 found", which would have
been dominated by `UU_6_2023` (726 of the 2,019) and told us little about the
other 33 documents.

Each of the 45 was read verbatim (not summarized, not classified by another
LLM call) and judged: **is this genuinely elucidation text sitting in an
article slot, or a legitimate occurrence** (a citation, an unrelated preamble,
ordinary non-idiomatic prose)?

**What this sampling design does and does not license statistically**
(corrected after adversarial review — see the Adversarial review section
below; an earlier draft of this report claimed a 95%-CI upper bound derived
from treating the sample as i.i.d. Bernoulli draws over the 2,019-fragment
population, which is wrong and has been removed). Round-robin across 34
documents means a document contributing 1 of the 2,019 fragments (most of
them) and a document contributing 726 (`UU_6_2023`) each get roughly 1-2
samples — the sample is closer to **stratified-by-document** than to a
uniform random draw over fragments, and fragments within one document are
NOT independent trials (most repeat the identical bare "Cukup jelas."
string). The defensible claim is: **34/34 damaged documents were represented
in the read-through, and 0 of the ~1-2 fragments read per document were
innocent.** That is strong document-level coverage and a genuinely
qualitative result (every document's damage pattern was internally
consistent — repeated boilerplate, not a mix of boilerplate and unrelated
hits), but it does NOT support a numeric confidence interval on the
fragment-level false-positive rate, and this report no longer claims one.

## Result: 45/45 genuine elucidation, 0 innocent occurrences

Patterns found across the sample, all consistent with genuine Penjelasan
(elucidation) content:

- Bare boilerplate: `"Cukup jelas."` — the overwhelming majority, especially
  in `UU_17_2008` and `PP_1_2011`.
- Per-`Ayat` lists mixing boilerplate with real explanatory prose for the
  ayat that isn't self-evident (e.g. `UU_11_2020` Ayat 5, `UU_66_2024`
  Ayat 3, `UU_28_2007`'s full numeric worked example for a tax penalty
  calculation).
- Explicit elucidation-section headers: `Keppres_29_1959` carries
  `"II. PASAL DEMI PASAL.\nTidak diberikan penjelasan, karena cukup jelas."`
  — a fragment that names its own section ("Article by article") and states
  outright that no explanation is given because it is sufficiently clear.
  `UU_4_1945` (see Finding 1) carries a fragment with the same
  `"II. PASAL DEMI PASAL"` heading followed by a real multi-sentence
  elucidation of an ASEAN agreement's 19 articles.
- `"Yang dimaksud dengan ... adalah ..."` ("what is meant by X is...") —
  the standard Indonesian legal glossing idiom, used exclusively in
  elucidation text, never in operative articles. Present throughout
  `UU_17_2008`'s Ayat-shaped fragments.

No fragment in the sample was a citation of another law's elucidation, an
unrelated preamble merely containing the phrase, or ordinary prose using
"cukup jelas" non-idiomatically. **The narrow question the mandate asked —
does this signal over-match — has a clean negative answer at the document
level: all 34 damaged documents were sampled, and every one showed a
consistent, genuine elucidation pattern with no innocent occurrence mixed
in.** (No numeric fragment-level confidence bound is claimed — see Method.)
Every sampled document's damage pattern (bare boilerplate repeated hundreds
of times, per the top-10 counts below) makes a hidden population of
qualitatively different, innocent occurrences within an already-sampled
document unlikely, though this is a qualitative read of the pattern, not a
statistical guarantee.

Top damaged documents (fragment count): `UU_6_2023` 726, `UU_17_2008` 337,
`PP_1_2011` 137, `UU_43_2009` 84, `UU_14_2025` 83, `UU_16_2025` 64,
`UU_66_2024` 61, `UU_11_2020` 53, `UU_28_2007` 52, `Perda_7_2015` 47.

## What was built: a gated regression test, not a new detector

The measured 0/45 result is a document-level, not a fragment-level,
guarantee (see Method), so "the signal is safe" is not claimed outright —
what is shipped is a formalization + regression gate that locks in exactly
what was verified, not a blanket endorsement:

- `scripts/kb/cukup_jelas_signal.py` — the §6 predicate
  (`is_unmarked_penjelasan_fragment`), extracted so the live measurement
  script and the CI test import the SAME definition rather than each
  restating it (a signal defined twice is a signal that can quietly diverge
  from what it claims to measure).
- `apps/backend-rag/backend/tests/unit/kb/test_cukup_jelas_damage_signal.py`
  — 20 tests (restructured once, after adversarial review — see that section
  below for what the earlier 19-test version got wrong):
  - 10 GUILT fixtures: verbatim text from 10 of the 45 manually-verified
    samples, spanning **10 distinct documents** (a runtime assertion in the
    test enforces this — an earlier draft repeated `UU_17_2008` and only
    covered 9) and every pattern found (bare, per-Ayat mix, explicit PASAL
    DEMI PASAL heading, substantive worked-example prose).
  - 5 TRUE-INNOCENCE fixtures (hard-asserted `False`): the
    `section: penjelasan` exclusion at both payload shapes (top-level and
    nested `metadata.section`, since the live sample exercises this path on
    only 792/84,283 points and would not itself catch a regression there), a
    no-phrase-at-all case, a word-boundary case (`"Ketercukupan anggaran dan
    kejelasan prosedur..."` — contains "cukup" and "jelas" as substrings of
    OTHER words, must not fire), and a missing-`text`-key case that must not
    crash.
  - 2 POSITIVE-CONTROL fixtures (hard-asserted `True`): case-insensitivity
    and whitespace-tolerance. An earlier draft mislabeled these as
    "innocence" cases even though they assert the opposite outcome —
    separated into their own list and test function.
  - 1 RESIDUAL-RISK fixture (hard-asserted `True`, "by design"): ordinary
    Indonesian prose using "cukup jelas" idiomatically and non-boilerplate
    (`"...prosedur permohonan izin sudah cukup jelas diatur dalam Pasal
    12..."`). This is flagged `True` — faithfully reproducing the campaign's
    own bare-substring definition, not a bug in this test — and is the
    fixture an earlier draft was missing entirely (adversarial review point
    B3). The 2026-08-25 sample found zero such cases among the 45 read, but
    45 samples cannot prove none exist among the remaining 1,974 unread
    fragments; this fixture documents that residual risk rather than
    hiding it.
  - 2 explicit mutation-proof tests, PLUS two mutations run BY HAND against
    the real source, TWICE — once before this restructuring and once after,
    to confirm the restructuring didn't quietly weaken them (both runs
    produced identical failure sets): removing the
    `section != "penjelasan"` guard turned 3 tests red (both
    `section:penjelasan` fixtures + the dedicated mutation-proof test);
    loosening the regex to two independent substring checks (dropping word
    adjacency) turned 2 tests red (the word-boundary fixture + its
    mutation-proof test). Both mutations were reverted each time; the suite
    is green (20/20) on the restored source. This satisfies the "every
    detector you write ships WITH guilt AND innocence tests, and you must
    show each going red under mutation" requirement literally, not just in
    prose.
- `research/legal/_cukup_jelas_sample.json` — the raw 45-item sample
  (regenerated identically: 84,283 points scrolled, 2,019 damaged, 34
  documents, same top-10 breakdown), committed for independent audit. An
  earlier draft measured but never shipped this file (adversarial review
  point B4).

No re-ingestion, no chunking change, no embedding re-index — the embedding
model stays FROZEN as required; this is a read-only classification of
existing payload.

## Finding 1 — WIZ-2 confirmed independently, with concrete impossible-identity examples

Sampling surfaced several documents whose `document_id` is chronologically
impossible, independent of anything to do with "Cukup jelas":

- **`UU_4_1945`** (two separate sampled points): body text is an "ASEAN
  Agreement on Electronic Commerce" ratification, referencing "22 Januari
  2019" and "Tambahan Lembaran Negara ... NOMOR 6728". No such law existed
  in 1945 — Indonesia's independence was declared in August 1945, and ASEAN
  itself did not exist until 1967.
- **`UU_1_1945`**: body text cites "Undang-Undang Nomor 7 Tahun 2014 tentang
  Perdagangan" — a 1945 law cannot cite a 2014 law.
- **`UU_2_1945`**: body text is explicitly titled (in its own `[CONTEXT: ...]`
  header) "PENETAPAN PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG NOMOR 1
  TAHUN 2O2O TENTANG KEBIJAKAN KEUANGAN NEGARA..." (a COVID-19-era financial
  stabilization Perpu, ratified as UU 2/2020). The document is almost
  certainly `UU_2_2020`, misidentified as `UU_2_1945`.

Mechanism, read from the current code
(`apps/backend-rag/backend/core/legal/metadata_extractor.py`): the extractor
already has an anti-fusion path
(`extract_title_identity` / `LEGAL_TITLE_PATTERN`, comment: "PREFERRED: all
three fields from ONE co-located title match, so they cannot be assembled out
of three different laws the document cites") which is precisely the class of
bug this data exhibits. The independent per-field fallback
(`NUMBER_PATTERN.search(text)` / `YEAR_PATTERN.search(text)`, lines 161-176)
is the "second place, demoted" path that mints a wrong identity when the
co-located title match fails — plausibly because these documents' body text
prominently and repeatedly cites "Undang-Undang Dasar ... Tahun 1945" (the
1945 Constitution), and an independent year-search anywhere in the document
would find that "1945" before the document's own actual promulgation year.

**This suggests these specific corrupted points predate the current
anti-fusion code path** (i.e. this may already be fixed going forward for new
ingests, but the existing Qdrant points were never re-ingested under the
fixed extractor). That is a hypothesis, not verified here — verifying it
would mean checking `git blame` on `extract_title_identity` against these
documents' ingestion timestamps, which is out of this lane's scope. Flagging
for whichever lane owns WIZ-2 / re-ingestion planning.

## Finding 2 — ANNEXED INSTRUMENTS confirmed: `UU_6_2023`'s 726 fragments are not one document

`UU_6_2023` (a ~5,300-character ratification act converting a Perpu into a
UU) accounts for 726 of the 2,019 damaged fragments — over a third. Sampled
fragments carry `[CONTEXT: ...]` headers naming pasal numbers like **Pasal
169, Pasal 297, Pasal 134, Pasal 82C, Pasal C (an OCR-garbled pasal marker)**.
A 5,300-character ratification act cannot have 297 articles. These are
elucidation fragments of the annexed Cipta Kerja instrument (Law No. 6/2023
converts PP 2/2022 on Cipta Kerja, and per the mandate's own §4.1 the
annexed instrument is ~1.33M characters), all carrying the CARRIER's
`document_id`. Confirms the mandate's Finding 2 (`UU_6_2023` "carries the
entire Cipta Kerja ... plus two elucidations") directly from sampled content,
independent of the mandate's own prior measurement.

## Finding 3 — a structural lead, CORRECTED after adversarial review: the
## naive reading was wrong, and the honest version is much weaker

**This section was substantially rewritten after adversarial review
(Codex, point D) found the original framing over-claimed.** The original
draft of this finding (preserved in git history on this branch, not
reproduced here) claimed a `has_ayat`/`has_context` metadata key-set split
was a "5.7x recall" elucidation-vs-article detector, ready for handoff. That
claim does not survive reading the code that produces the field.

Not asked for, but found while investigating the UNMARKED BOUNDARY class
(`UU_17_2008`, 471 "Cukup jelas" occurrences, 0 "PENJELASAN" headers — no
word-level rule can find where its elucidation section starts).

**What is actually measured** (full 84,283-point scroll, whole-or-nothing,
same discipline as the main measurement): legacy-shape points (the
78,486/84,283 majority with no top-level `document_id`) split into two
`metadata` key-set shapes — 12,624 points carry `has_ayat`/`ayat_count`/etc.,
59,171 carry `has_context`/`chunk_index`/etc., 12,488 carry neither. Of
those, 1,161 of the 12,624 `has_ayat`-shape points and 852 of the 59,171
`has_context`-shape points contain "Cukup jelas". These counts are real and
reproducible.

**What is NOT confirmed, and was wrongly asserted before**: that
`has_ayat=True` marks elucidation content. Reading
`apps/backend-rag/backend/core/legal/hierarchical_indexer.py` directly
(lines ~280-356, "Standard processing for small Pasal") shows `has_ayat` is
set by `len(extract_ayat_numbers(pasal_text)) > 0` — a pure text-regex count
of `Ayat(N)` markers — for **any** Pasal chunk under the 4,000-character
size threshold, unconditionally on the `section` value (`batang_tubuh` or
`penjelasan`). An ordinary OPERATIVE article that happens to be organized
into `Ayat (1)` / `Ayat (2)` sub-paragraphs — which is a very common,
unremarkable shape for Indonesian statute articles, not a special one — gets
`has_ayat=True` on exactly the same basis as a genuine elucidation entry.
The field carries no section information; it is confounded with ordinary
paragraph structure and the 4,000-character chunk-size cutoff, not with
elucidation-vs-article status. The one spot-check performed during the
original investigation (`UU_17_2023`, ambiguous prose that could be either
an elucidation restatement or an ordinary operative Ayat) is consistent with
this — it was never resolved, and the original draft reported it as an open
question while still headlining a "5.7x recall" number that assumed the
answer. **The correct statement is: `has_ayat` is not a validated
elucidation signal, and the 11,463-point "additional recall" figure from the
earlier draft should be treated as an artifact of chunk size, not evidence
of a detector.** No detector, no handoff recommendation, is being built on
`has_ayat` in light of this.

**A more promising, narrower, still-unresolved lead**: where a `hierarchy_path`
or `chunk_key` metadata field is present, `hierarchical_indexer.py`'s own
`prefix = "Pasal" if section == "batang_tubuh" else "Penjelasan_Pasal"`
logic (same file) means that field's string value DOES directly encode
elucidation-vs-article status by construction, not by inference — this was
verified live: on the 792 `modern_full` points (the two 2026-08-25 repairs,
UU_6_2011/UU_40_2007), `chunk_key` containing `"Penjelasan_Pasal"` matches
`section == "penjelasan"` 1:1 on every sampled row, with zero exceptions
found. **But** the same live check against `hierarchy_path`/`chunk_key` on
the four legacy top-damage documents most relevant to this mandate
(`UU_66_2024`, `UU_11_2020`, `UU_28_2007`, `UU_17_2008`) found **zero**
occurrences of `"Penjelasan_Pasal"` in any of them, despite these documents
demonstrably containing real elucidation content (per the sampled "Cukup
jelas" fragments themselves).

**This is now resolved, not open — the answer is "expected, not anomalous."**
A follow-up code investigation (grep across the whole repo + `git log --all
-S"Penjelasan_Pasal"`) found: (1) `hierarchy_path` is written by exactly ONE
code path in the entire repo, `hierarchical_indexer.py`; (2) the
`Penjelasan_Pasal`/`Pasal` prefix distinction is **one commit old** —
`git log --all -S"Penjelasan_Pasal"` returns exactly one commit, `f0a0eab22`
(2026-08-25 07:38:05 UTC, PR #4891), the SAME DAY as this investigation.
Before that commit, the chunk-id builder produced only `Pasal_{n}`
unconditionally — no elucidation/article distinction existed in
`hierarchy_path` at all prior to that commit, for ANY point; (3) the real
fork is a `flatten_payload` boolean in `qdrant_db.py`'s
`_build_point_payload` — only `hierarchical_indexer.py` calls it with
`flatten_payload=True` (producing the flat, top-level `document_id`/
`hierarchy_path`/`chunk_key` shape); the default (`flatten_payload=False`,
used by three OTHER ingestion callers —
`services/ingestion/ingestion_service.py`,
`services/ingestion/politics_ingestion.py`, `app/routers/oracle_ingest.py`,
none of which import `HierarchicalIndexer`) nests everything under
`metadata` instead — exactly the `legacy_metadata_text` shape that is
78,486 of 84,283 points. Those three callers are **structurally incapable**
of ever writing `hierarchy_path` in any naming convention — the field is not
present-but-differently-named on legacy points, it is simply never
constructed for them. Zero hits on the four legacy top-damage documents is
therefore the expected result, not a mystery: `hierarchy_path`/`chunk_key`'s
`Penjelasan_Pasal` naming convention is same-day, single-commit, and scoped
to the 792-point `modern_full` bucket — it was never going to appear on
points from a different, older ingestion pipeline.

**Handoff, corrected and now conclusive**: whichever lane owns the UNMARKED
BOUNDARY class should NOT start from `has_ayat` (retracted) NOR from
`hierarchy_path`/`chunk_key` on legacy-shape points (structurally absent,
not a lead worth chasing there). Any elucidation-vs-article signal for the
78,486-point legacy majority — which is where this mandate's actual
top-damage documents live — must be found elsewhere: raw chunk text, or
`metadata.section` where it happens to be present, or a genuinely new
signal this investigation did not attempt to build. No document-ordering
field was found to exist for a "pasal renumbering restart" boundary detector
either (`chunk_id` is a random per-point UUID, not a sequence number;
`metadata.pasal_number` values come back scrambled when sorted by
`chunk_id`) — that structural approach the mandate suggested remains
unvalidated and unbuilt, honestly, rather than shipped on a hope.

## What was NOT done, and why

- **No fix to `metadata_extractor.py`** (Finding 1's mechanism). This is a
  live-code change with re-ingestion implications for a class of documents
  (WIZ-2) explicitly owned as a separate, larger workstream in the campaign
  mandate — out of scope for a false-positive measurement lane.
- **No detector shipped for any Finding-3 structural signal.** The original
  `has_ayat` lead is retracted outright (confirmed confounded with ordinary
  paragraph structure and a 4,000-char chunk-size cutoff, not with
  elucidation status — see Finding 3). The `hierarchy_path`/`chunk_key`
  naming-convention lead is confirmed to be structurally scoped to the
  792-point `modern_full` bucket only — a same-day, single-commit addition
  (`f0a0eab22`, 2026-08-25) that three of the repo's four ingestion callers
  never construct at all, in any form — so it is not usable on the
  78,486-point legacy majority where this mandate's actual top-damage
  documents live. Neither is a detector worth shipping; the legacy-shape
  elucidation-vs-article problem remains genuinely unsolved by anything
  found in this investigation.
- **No deletions, no re-ingestion, no chunking change.** Embedding model
  (`text-embedding-3-small`, 1536 dims) untouched — nothing in this
  investigation required or would justify re-embedding.

## Addendum — client-facing surface vs. corpus hygiene, and a language note

Added after the measurement above was already complete and shipped, once the
orchestrator relayed a WhatsApp-mirror traffic census (60,004 inbound client
messages, 2022-12→2026-08-24; 10,929 question-bearing; immigration 2,752 /
company 656 / tax 298 / property 187). This section separates which of the
34 damaged documents sit on a surface clients actually reach from which are
corpus hygiene that happens to be structurally identical — the campaign's
deliverable is answers to real questions, not a clean-looking count.

Checked all 10 of the top-10-by-damage documents' `topic` metadata directly
against Qdrant (not guessed from the `document_id` alone):

| document | topic | fragments | client-facing? |
|---|---|---:|---|
| `UU_6_2023` | Cipta Kerja (conversion act, carries the annex) | 726 | **yes** — company + property |
| `UU_17_2008` | Pelayaran (shipping) | 337 | no |
| `PP_1_2011` | Perumahan dan Kawasan Permukiman (housing) | 137 | **yes** — property |
| `UU_43_2009` | Kearsipan (archives) | 84 | no |
| `UU_14_2025` | Ibadah Haji dan Umrah (hajj/umrah) | 83 | no |
| `UU_16_2025` | BUMN (state-owned enterprises), 4th amendment | 64 | marginal |
| `UU_66_2024` | Pelayaran, 3rd amendment (same family as `UU_17_2008`) | 61 | no |
| `UU_11_2020` | **Cipta Kerja** (the ORIGINAL omnibus law, not the carrier) | 53 | **yes** — company + property |
| `UU_28_2007` | Ketentuan Umum dan Tata Cara Perpajakan (KUP — tax procedure) | 52 | **yes** — tax |
| `Perda_7_2015` | Pendidikan Diniyah dan Pesantren (Islamic education) | 47 | no |

`UU_11_2020` matters beyond its own 53 fragments: it is the ORIGINAL Cipta
Kerja omnibus law (before Perpu 2/2022 → `UU_6_2023` re-ratified it) —
finding it independently in the top 10, on the SAME topic as `UU_6_2023`,
means the two client-facing findings are not one lucky hit but a pattern:
the corpus's single most cited business-law topic is also its single largest
damage source.

**Client-facing total among the top 10: `UU_6_2023` + `PP_1_2011` +
`UU_11_2020` + `UU_28_2007` = 968 fragments (48% of the full 2,019), against
company (656) + property (187) + tax (298) = 1,141 question-bearing messages
in the traffic census.** Corpus-hygiene total among the same top 10 (shipping
law, archives, hajj/umrah, BUMN, Islamic education): 676 fragments, against
traffic this investigation has no evidence clients ever generate.

This changes the priority ordering the mandate implied. `UU_17_2008`
(Pelayaran) is still the cleanest available SPECIMEN for developing the
UNMARKED BOUNDARY detector (471 "Cukup jelas" occurrences, zero "PENJELASAN"
headers, so it isolates the structural problem from every other document's
noise) — but it is corpus hygiene, not a client-facing fix. Whoever builds
that detector next should validate it on `UU_17_2008` for the clean signal,
then PROVE it on `UU_6_2023` / `UU_11_2020` / `PP_1_2011` / `UU_28_2007`
before calling the work done, because those four are where a client
question actually lands.

**Language note, since the team asked directly**: `is_unmarked_penjelasan_fragment`
and the `hierarchy_path`/`chunk_key` structural lead (Finding 3) both
classify STORED KB CONTENT — the Indonesian statute text sitting in Qdrant —
never the client's QUERY. Every document in `legal_unified` is an official
Indonesian legal instrument regardless of what language a client asks in
(English, Indonesian, Italian, Spanish, per the census); "Cukup jelas" and
the `hierarchy_path` naming convention are properties of that Indonesian
source text, not of anything query-side. Neither signal reads, tokenizes, or
makes any assumption about the client's question language, so there is no
query-language surface for either to break on. This is a genuine non-issue
for THESE two signals specifically — it would become a real issue only for a
downstream component that tries to MATCH a client's non-Indonesian question
against Indonesian statute phrasing (retrieval/embedding quality across that
language gap), which is outside what this lane measured or built.

## Adversarial review

Reviewed by `codex` (generator≠grader: the report/scripts/tests were handed
to an independent seat in read-only sandbox, not graded by the same session
that wrote them) against the shipped draft — sample, signal module, test
file, and report — before this remediation pass. Findings, verbatim intent,
and disposition:

- **A — invalid statistical claim.** The "0/45 hits → ~6.6% upper bound at
  95% CI, rule-of-three" language treated the round-robin document-stratified
  sample as an i.i.d. Bernoulli draw over the 2,019-fragment population. It
  is not: a 726-fragment document (`UU_6_2023`) and a 1-fragment document get
  roughly the same 1-2 sample slots, so the claimed confidence interval has
  no statistical basis. **Fixed** — the numeric bound was removed from both
  Method and Result; the report now claims only document-level coverage
  (34/34) with an explicit statement that no fragment-level confidence bound
  is defensible from this sampling design.
- **B1 — duplicate guilt fixture.** `GUILTY_SAMPLES` listed `UU_17_2008`
  twice, so the claimed "10 documents" was actually 9 distinct ones. **Fixed**
  — the duplicate was replaced with a new `UU_66_2024` fixture, and a runtime
  assertion (`len(set(document_ids)) == len(GUILTY_SAMPLES)`) now prevents
  silent recurrence.
- **B2 — mislabeled innocence fixtures.** Two of the original 7
  "INNOCENT_SAMPLES" actually asserted `expect=True` (case-insensitivity,
  whitespace-tolerance) — positive controls, not innocence cases, sharing one
  ambiguous list and field name. **Fixed** — split into
  `TRUE_INNOCENCE_SAMPLES` (hard-asserted `False`) and
  `POSITIVE_CONTROL_SAMPLES` (hard-asserted `True`), each with its own test
  function and explicit assertion direction.
- **B3 — missing critical innocence case.** No fixture tested "cukup jelas"
  used adjacently and idiomatically in ordinary, non-boilerplate prose — the
  one shape most likely to be a genuine false positive the 45-sample read
  didn't happen to catch. **Fixed** — added `RESIDUAL_RISK_SAMPLES` with an
  honest fixture, explicitly asserted `True` "by design" (faithfulness to the
  campaign's own bare-substring definition), with commentary stating plainly
  that 45 samples cannot rule out this shape existing among the 1,974 unread
  fragments.
- **B4 — the raw 45-sample JSON was measured but never shipped.** The
  original run's output was deleted after use; only prose summarized it, so
  independent audit of the actual sample was impossible. **Fixed** —
  `scripts/kb/cukup_jelas_sample.py` was re-run (reproducing identical
  totals: 84,283 scrolled, 2,019 damaged, 34 documents, same top-10) and its
  output committed at `research/legal/_cukup_jelas_sample.json`.
- **B5 — stale docstring path.** `cukup_jelas_signal.py`'s docstring pointed
  at a `kb/inventory/` path that was never the real output location and had
  since been deleted. **Fixed** — corrected to `research/legal/`.
- **C — mutation-proof tests.** Reviewed and found genuinely non-tautological
  (not decorative). **No change** — confirmed again in this remediation pass
  by re-running both hand-applied mutations against the restructured test
  file: identical failure sets both times (3 tests red on the section-guard
  removal, 2 tests red on the regex-adjacency loosening), suite green (20/20)
  on the restored source.
- **D — the `has_ayat`-as-elucidation-signal claim in Finding 3 does not hold
  up.** `has_ayat` is set by a pure text-regex count of `Ayat(N)` markers,
  unconditional on `section`, gated only by a 4,000-character chunk-size
  threshold (`hierarchical_indexer.py` lines ~280-356) — an ordinary
  OPERATIVE article with paragraph sub-structure gets the identical shape as
  genuine elucidation. The "5.7x recall" framing assumed what it needed to
  prove. **Fixed** — Finding 3 was rewritten to retract this claim outright
  and replace it with the narrower, code-verified `hierarchy_path`/
  `chunk_key` naming-convention lead. That lead's zero-hits-on-legacy-
  documents puzzle was initially reported as an open question, then CLOSED
  within this same remediation pass by a follow-up code investigation:
  `git log --all -S"Penjelasan_Pasal"` shows the naming convention is a
  same-day, single-commit addition (`f0a0eab22`, 2026-08-25, PR #4891), and
  the `flatten_payload` fork in `qdrant_db.py` means three of the repo's
  four ingestion callers never construct `hierarchy_path` at all — the
  field is structurally absent on legacy points, not present under a
  different name. Zero hits was the expected result, not a mystery.
- **E — overclaiming language** ("near-zero", "usable as-is", "undercounts...
  if anything", "5.7x recall") exceeded what 45 clustered observations plus
  an unvalidated structural lead support. **Fixed** — softened throughout:
  Summary, Result, and "What was built" no longer assert blanket safety or an
  unqualified recall multiplier; claims are now scoped to what was actually
  measured (document-level coverage, not a fragment-level guarantee; a
  formalization of what was verified, not an endorsement of the signal as
  "safe").

No finding was dismissed without a code or fixture change; nothing in this
list was addressed by adding words without changing the underlying claim,
script, or test.
