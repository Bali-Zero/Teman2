---
date: 2026-08-25
domain: legal
client_case: none — KB current-live campaign, Lane P (parser capability)
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

**Measured false-positive rate: 0/45 (0%).** Every sampled fragment was
genuinely elucidation-style text. The 2,019/34 figure is not a fiction — it
undercounts the real problem, if anything (see Finding 3 below).

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
does this signal over-match — has a clean negative answer at this sample
size.** With 0/45 hits and a sample spanning every damaged document, standard
binomial reasoning puts the true FP rate's upper bound (95% CI, rule-of-three
approximation) at roughly 3/45 ≈ 6.6% even in the worst case a larger sample
might reveal — and every sampled document's damage pattern (bare boilerplate
repeated hundreds of times, per the top-10 counts below) makes a hidden
population of qualitatively different, innocent occurrences unlikely.

Top damaged documents (fragment count): `UU_6_2023` 726, `UU_17_2008` 337,
`PP_1_2011` 137, `UU_43_2009` 84, `UU_14_2025` 83, `UU_16_2025` 64,
`UU_66_2024` 61, `UU_11_2020` 53, `UU_28_2007` 52, `Perda_7_2015` 47.

## What was built: a gated regression test, not a new detector

Given the false-positive rate is near-zero, the signal is usable as-is. The
deliverable is a formalization + regression gate, not a new detector:

- `scripts/kb/cukup_jelas_signal.py` — the §6 predicate
  (`is_unmarked_penjelasan_fragment`), extracted so the live measurement
  script and the CI test import the SAME definition rather than each
  restating it (a signal defined twice is a signal that can quietly diverge
  from what it claims to measure).
- `apps/backend-rag/backend/tests/unit/kb/test_cukup_jelas_damage_signal.py`
  — 19 tests:
  - 10 GUILT fixtures: verbatim text from 10 of the 45 manually-verified
    samples, spanning 10 documents and every pattern found (bare, per-Ayat
    mix, explicit PASAL DEMI PASAL heading, substantive worked-example
    prose).
  - 7 INNOCENCE fixtures: the `section: penjelasan` exclusion (both payload
    shapes — top-level and nested `metadata.section`, since the live sample
    exercises this path on only 792/84,283 points and would not itself catch
    a regression there), a no-phrase-at-all case, a word-boundary case
    (`"Ketercukupan anggaran dan kejelasan prosedur..."` — contains "cukup"
    and "jelas" as substrings of OTHER words, must not fire), case-
    insensitivity and whitespace-tolerance in the positive direction, and a
    missing-`text`-key case that must not crash.
  - 2 explicit mutation-proof tests, PLUS two mutations run BY HAND against
    the real source during this investigation (not just simulated inline):
    removing the `section != "penjelasan"` guard turned 3 tests red
    (both `section:penjelasan` fixtures + the dedicated mutation-proof test);
    loosening the regex to two independent substring checks (dropping word
    adjacency) turned 2 tests red (the word-boundary fixture + its
    mutation-proof test). Both mutations were reverted; the suite is green
    (19/19) on the restored source. This satisfies the "every detector you
    write ships WITH guilt AND innocence tests, and you must show each going
    red under mutation" requirement literally, not just in prose.

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

## Finding 3 — a bigger, unvalidated lead: the corpus has a structural
## elucidation-vs-article signal that catches ~5x more than "Cukup jelas" does

Not asked for, but found while investigating the UNMARKED BOUNDARY class
(`UU_17_2008`, 471 "Cukup jelas" occurrences, 0 "PENJELASAN" headers — no
word-level rule can find where its elucidation section starts).

Legacy-shape points (the 78,486/84,283 majority with no top-level
`document_id`) carry a `metadata` dict whose KEY SET differs by which
ingestion sub-path produced the chunk, independent of chunk text:

- **Article ("Batang Tubuh") shape**: `has_context`, `chunk_index`,
  `chunk_length`, `content_length`, `total_chunks`.
- **Elucidation ("Penjelasan") shape**: `has_ayat`, `ayat_count`, `ayat_max`,
  `ayat_numbers`, `ayat_sequence_valid`, `ayat_validation_error`.

Measured across the FULL 84,283-point scroll (whole-or-nothing, same
discipline as the main measurement):

| bucket | total points | of which contain "Cukup jelas" |
|---|---|---|
| A = has_ayat shape | 12,624 | 1,161 (9.2%) |
| C = has_context shape | 59,171 | 852 (1.44%) |
| N = neither shape | 12,488 | 275 |

Two things this shows:

1. **The `has_ayat` shape catches 11,463 points that contain NO "Cukup
   jelas" at all** — substantive elucidation prose without the boilerplate
   phrase (e.g. `"Yang dimaksud dengan..."` glosses, or plain restatement
   text). That is **5.7x the entire 2,019-fragment §6 count**, in ONE
   structural bucket, using a field that is ALREADY in the payload (zero
   re-ingestion cost to read it).
2. **It is not a strict superset**: 852 of the 2,019 "Cukup jelas" fragments
   are in the `has_context` (article) shape, not `has_ayat` — bare
   single-line "Cukup jelas." elucidation entries with no per-Ayat breakdown
   apparently get chunked through the same code path as ordinary articles.
   A detector using `has_ayat` alone, without the substring signal, would
   MISS these — the two signals are complementary, not redundant.

**Why this is reported as a lead, not shipped as a detector**: precision was
NOT fully validated. One spot-checked `has_ayat` example
(`UU_17_2023`: `"Pemerintah Pusat dan Pemerintah Daerah bertanggung jawab
dalam penyelenggaraan pelayanan kedokteran untuk kepentingan hukum."`) reads
ambiguously — it could be genuine elucidation prose (a restatement without
the "Yang dimaksud dengan" tell) or, less likely but not ruled out, an
operative Ayat that happens to share the payload shape for an unrelated
reason. Confirming this needs either (a) reading the surrounding chunks in
document order, which requires a reliable chunk-ordering field this
investigation did NOT find (`chunk_id` is a random per-point UUID, not a
sequence number — sorting by it does not recover document order;
`metadata.pasal_number` values come back in a scrambled, non-monotonic
sequence when sorted by `chunk_id`, so the "does pasal numbering restart"
structural boundary test the mandate suggested could not be validated with
currently-available ordering metadata), or (b) a much larger, properly
stratified precision sample across more of the 12,624 `has_ayat` points than
this investigation's budget allowed.

**Handoff**: whichever lane owns the UNMARKED BOUNDARY class should start
from the `has_ayat`/`has_context` key-set split (cheap, already-computed,
5.7x the recall of substring matching) rather than reinventing a text-pattern
detector, but must run its own guilt+innocence validation before shipping —
this investigation deliberately stopped short of that to avoid shipping an
under-tested guard (superscar family #3 discipline: "nessuna guardia senza
test di innocenza E colpevolezza"). No document-ordering field currently
exists to support a "pasal renumbering restart" boundary detector; that would
need either an ingestion-time addition (`chunk_index` is scoped to the
article-shape sub-path only, not a document-wide sequence) or a
re-derivation from `chunk_length`/`content_length` byte-offset reconstruction
that this investigation did not attempt.

## What was NOT done, and why

- **No fix to `metadata_extractor.py`** (Finding 1's mechanism). This is a
  live-code change with re-ingestion implications for a class of documents
  (WIZ-2) explicitly owned as a separate, larger workstream in the campaign
  mandate — out of scope for a false-positive measurement lane.
- **No detector shipped for the `has_ayat` structural signal** (Finding 3).
  Precision unvalidated at the scale this would need before gating anything
  on it; shipping it now would repeat exactly the mistake this investigation
  was launched to check for.
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
and the `has_ayat` structural lead (Finding 3) both classify STORED KB
CONTENT — the Indonesian statute text sitting in Qdrant — never the client's
QUERY. Every document in `legal_unified` is an official Indonesian legal
instrument regardless of what language a client asks in (English, Indonesian,
Italian, Spanish, per the census); "Cukup jelas" and the `has_ayat` payload
shape are properties of that Indonesian source text, not of anything
query-side. Neither signal reads, tokenizes, or makes any assumption about
the client's question language, so there is no query-language surface for
either to break on. This is a genuine non-issue for THESE two signals
specifically — it would become a real issue only for a downstream component
that tries to MATCH a client's non-Indonesian question against Indonesian
statute phrasing (retrieval/embedding quality across that language gap), which
is outside what this lane measured or built.
