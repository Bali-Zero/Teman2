---
name: kbli-navigator
description: "KBLI Navigator corner — the live shared context AND the full plan-to-the-end for ALL KBLI corpus/product work (dataset, gold, KG, editorial, kbli pages on balizero.com). Load BEFORE touching any KBLI data or code, or when Zero says /kbli-navigator, 'kbli corpus', 'filiera', 'garuda', or references the July 2026 disease cluster. Holds: the north star (re-validate all 1,559 codes), established truths (verified, with method), LIVE STATE, the GARUDA-FILIERA roadmap (phases 0-3, D0-D6 protocol, batches, seats), artifacts & access, blood-bought operating rules."
---

# /kbli-navigator — KBLI corpus & product corner (project brain)

> Created 2026-07-16 on Zero's order after the July disease cluster; promoted to the standing
> project brain on 2026-07-17 ("crea la skill del contesto così da avere il nostro progetto sempre
> pronto — tutto il contesto e il piano fino alla fine"). This file is the HOT CONTEXT shared by
> every Fable/Claude session and every Codex dispatch working on KBLI. It states the GOAL, what is
> PROVEN, what is IN FLIGHT, the PLAN to the end, and the rules paid for in blood.
> **Update the LIVE STATE section whenever it changes — this corner is only useful if it stays true.**

## 0. The product + the north star

`balizero.com/kbli/<code>` (apps/mouth, 1,559 KBLI-2025 code pages) + the RAG/KG backend answering
KBLI questions on WhatsApp/webchat (`inspect_kbli`/`chat_kbli`/`search_kbli`). Clients make real
licensing/investment decisions on this data — a wrong risk row is client-facing harm (cf. Darinka
KBLI dispute). Honesty beats completeness: a declared gap ("licensing not yet published") is
acceptable; a plausible-but-wrong assertion is not.

**THE NORTH STAR (do not lose it): re-validate the WHOLE navigator — all 1,559 codes — against
government ground truth, code by code.** The 8 collision codes cured so far are the _proven pilot
pattern_, NOT the goal. The goal is a navigator where every rendered risk / licensing / PMA / Bali
fact is either government-sourced (with a citable locator + vintage) or an honest declared gap —
zero silent cross-vintage fill anywhere in the catalog. §5 is the plan that gets us there.

## 1. LIVE STATE (last update 2026-07-25 — keep current)

**RENDER-TRUTH PASS — 2026-07-25. Two defects found by PROBING THE LIVE PRODUCT, both invisible to
every existing gate, both measured on the real data before a line was written.**

**(a) The catalogue spoke pipeline at its clients.** `intel_2026.editorial` was authored by an LLM
NARRATING THE JSON RECORD, so internal symbols reached readers verbatim: **`Bali status:
OK_or_HIGHER_RISK` on 908 "By the numbers" cells across 1,141 codes (73% of the catalogue)**, +725
occurrences inside editorial prose, +8 in `l4_bali.reason`, +**113 of the 428 GOLD codes**. Cured at
RENDER (`apps/mouth/src/lib/kbli-status-labels.ts`) by resolving each symbol to the label
`BaliStatusBadge`/`TransitionBadge` already used — the labels existed, they were simply unreachable
from the editorial renderer. **Presentation only: symbol and label denote the same verdict, no fact
moved.** Deliberate non-targets, both test-pinned: **TERBUKA/TERTUTUP/TERBATAS stay Indonesian**
(terms of art the product teaches), and **`_data_note` stays verbatim** (there a symbol is a CITATION
of the record used as divergence evidence — rewriting evidence corrupts the audit trail).
Coverage is a **deny list** (walk everything, skip only `_l3_regen` + `coverImage`), so a field added
tomorrow is covered by default. Gate `kbli-internal-leak.test.ts` measures BOTH data files and also
**ratchets a SEPARATE debt it cannot fix: 392 codes narrate raw field names** ("l4_bali_blocked is
false", `pma_max_asing`) — that class needs an editorial rewrite (W5), and the ratchet only falls.

> Cross-family gate (Kimi K3, generator≠grader) returned **2 real BLOCKERs**, both re-measured on disk
> before acting: the gold layout renders `gold.*` DIRECTLY from `getGoldContent()`, bypassing the
> loader cure entirely; and the first gate was blind to that very file. Cured at the `getGoldContent`
> choke point (covers the page + `/api/kbli/gold/[code]` at once).

**(b) 95 codes CERTIFIED a Bali verdict derived from a basis the same record calls unverifiable.**
`l4_bali.confidence` MEDIUM/HIGH + `needs_review:false` while `per_skala == []` — **24 of them
`blocked: true` at HIGH confidence**, i.e. the page tells a client "a PT PMA cannot register this in
Bali", stated as settled, on a detached risk tier. Cured with the ALREADY-SANCTIONED wave-1 treatment
(`cure_l4bali_disclosure.py`: confidence→LOW, needs_review→true, reason disclosure-wrapped with the
original preserved verbatim; **`status` and `blocked` are NEVER touched** — flipping either is a
re-derivation that needs the true tier, F15). Spec `cure_specs/l4bali_gap_disclosure_2026_07_25.json`
(95 codes), emitter `emit_l4bali_gap_disclosure_spec.py`, structural predicates shared with the writer
in `_l4bali_basis.py`. Applied + content-verified on **all FIVE dataset copies** (canonical, mouth,
kbli-navigator, and the two gitignored backend-rag copies the sync script also writes); catalogue-wide
disclosed count 57 → **152**.

> **The cross-family gate (Kimi K3, generator≠grader) earned its keep — 4 of its 5 findings were real,
> each re-verified on disk before acting (W65), and one was refuted with evidence:**
>
> 1. **A THIRD shape of dead basis, invisible to the wave-2 selector — found, cured.** `per_skala == []`
>    is itself a PROXY for "the basis is gone", and PR #2921's `partial_detach` primitive breaks it:
>    rows survive while the tier the verdict cites does not. **`93114`** read `APERTO_BALI_RISCHIO_ALTO`,
>    `blocked:false`, **HIGH confidence**, reason _"the Besar scale is 'Tinggi'"_ — with NO Besar row
>    left in the record (the tier lives in the disowned block). It failed in the PERMISSIVE direction:
>    the page told a client the code IS registrable by a PT PMA. Cured via a new `detached_tier` basis
>    that re-derives the status from the surviving rows with the SAME function that wrote it
>    (`resolve_kbli_l4_needs_review.besar_risk`) and fires only on a mismatch. Catalogue-wide census of
>    the class: 3 partial detaches (`49213`, `93114`, `93191`), exactly 1 inconsistent.
> 2. **A client-facing sentence asserted an HTTP status we never observed — rewritten.** The first
>    `no_oss_scope` suffix said _"(the scope endpoint returns 404)"_. `_l2_status = no_oss_risk` is
>    written by `build_kbli_l2_oss_risk.py:163` for a MISSING dump line, ANY non-200, **or**
>    `success:false` — asserting `404` inside the sentence whose whole job is honesty is the disease
>    itself (F12). Now: _"could not be retrieved from the OSS API when this dataset was built"_ —
>    independently corroborated by `KBLI_2025_OSS_GROUND_TRUTH.json` (`ruang_lingkup_no_scope: 221`,
>    `ruang_lingkup_errors: 0`, all 54 at `_rl_status: "no_scope"`).
> 3. **Wave 1's disclosure sentence narrated two JSON keys at clients — migrated catalogue-wide.** It
>    read _"detached to `per_skala_disputed_pp28_collision` (see `_data_note`)"_, and `kbli-faq.ts:42`
>    splices that verbatim into a published FAQ answer. Fixing only the new codes would have shipped a
>    half-fixed class + two dialects, so `--reword-legacy` migrated **all 57 wave-1 records** too.
>    Now **0 of 1,559 verdict sentences name a pipeline field**, pinned by a test that measures the
>    live catalogue. The key is not lost — it stays on the record, in `_data_note`, and in the spec.
> 4. **Editorial residue is now declared instead of silent.** `_meta.editorial_residue` records that
>    **95 of 95** cured codes still carry `intel_2026` prose stating a risk tier as FACT ("as a
>    medium-high/high-risk activity"), so on those pages the article body and the badge now disagree.
>    The cure deliberately does not touch editorial prose; wave 1 flagged this class and wave 2 had
>    dropped the practice.
> 5. **REFUTED with evidence — `93111`/`93112`/`93119`/`93191`.** The gate called these false negatives
>    (they carry `_l2_status: no_oss_risk` AND a surviving row). They are NOT: each has
>    `pp28_sources` populated (a declared PP28 locator) and their stored verdict still follows from the
>    row they keep — and all four were adjudicated by the signed Batch-A Lot-8/9 gates. Their real
>    exposure is the PP28 **vintage-2020** axis (FATAL-2), already tracked catalogue-wide — not this
>    wave. Recorded here so the next session does not re-derive it.

> **META-PATTERN — THE SELECTOR IS THE DISEASE (THIRD sighting in one session; this is now a rule).**
> Wave 1 cured 57 of these and left 94 not because it failed, but because **it selected on a MARKER
> (`per_skala_disputed_*` present) instead of on the STATE (the layer this verdict derives from is a
> declared gap)** — so 54 codes detached without ever receiving a marker were not skipped, not
> reported, simply **unreachable by the tool**. This is the exact shape already recorded in this
> corner for the PHANTOM CODES ("every cure tool keys off _a canonical record exists_ → a code living
> only downstream is unreachable by all of them"). **RULE: every cure tool must state whether its
> scope is 'records carrying marker X' or 'records in state Y', and prefer the STATE.** A marker is
> an artefact of which lot happened to touch a code; the state is the defect.
> **And the wave-2 selector fell into it too, one level down** (found by the adversarial gate, not by
> us): `per_skala == []` is ITSELF a marker standing in for the state "this verdict's basis is gone".
> A partial detach leaves rows behind, so the marker reads INTACT while the cited tier is gone — 93114.
> The cure for a proxy is to ask the question the proxy was standing in for: **re-derive the verdict
> from what the record holds NOW, with the same function that wrote it, and compare.** That is
> `_l4bali_basis.status_matches_surviving_rows`, and it is deliberately restricted to the three
> statuses whose derivation is TOTAL in `besar_risk` — the other three come from a different pass
> (lowest tier across all scales), so re-deriving them here would manufacture false mismatches.
> Undecidable is recorded as undecidable, never as clean.
> The wave-2 selector is structural — `l4_bali.status` enum identity + a dead-basis shape + a
> corroborating signal — and **fails loud on an unclassified status** rather than guessing (an
> unclassified enum cannot be known to derive from the detached layer). It deliberately EXCLUDES
> TERTUTUP/TERBATAS/CHIUSO_REGOLATORE_SETTORIALE: those derive from `pma_status` or a sector
> regulator, bases that are intact, so disclosing a derivation defect there would itself be false.
> (Corrective note for anyone reading an earlier draft: a first prose-based count said "134 codes /
> 64 blocked". That over-counted by matching risk words in the reason of PMA-derived verdicts. The
> structural number is **95 / 24** — 40 disputed-key + 54 no-OSS-scope + 1 partial-detach. The spec
> file IS the census; a number that lives only in prose rots, so a test now pins it to the artefact.)

**⚠️ AWAITS ZERO (Legge 5) — three linked editorial calls, investigation CLOSED, no cure past the gate:**

1. **17 codes attribute to OSS an observation OSS never served, client-facing, at `blocked: true`.**
   Their reason reads _"OSS has no Usaha Besar scale row → a PT PMA is barred"_ — and **7 of the 17 go
   further and enumerate _"(only Mikro/Kecil/Menengah)"_**. But all 17 (verified on canonical, this is
   the whole `CHIUSO_PMA_NO_BESAR` slice of the wave: `47771 52211 70100 91424 93115 93121 93122 93123
93125 93126 93128 93129 93192 93194 93195 93197 93199`) carry `_l2_status: no_oss_risk` — OSS
   returned **no scope at all** — plus a disputed key: their ONLY scale rows ever lived in the
   **disowned PP28 vintage-2020 block**. Two different sentences are in play and they do not fail the
   same way: _"OSS has no Besar row"_ is trivially TRUE when OSS serves nothing (though the reader
   hears "OSS says UMKM-only", which is not what a 404 says), while the enumeration _"only
   Mikro/Kecil/Menengah"_ is **unsupportable** — it is a positive claim about rows OSS never served,
   read off the repudiated block. The wave-2 cure DISCLOSES all 17 (confidence LOW + needs_review) but
   does **not** rewrite the sentence: correcting a client-facing claim is editorial.
   **Decision needed: rewrite (and to what — "OSS serves no scope for this code" vs the current
   UMKM-reserved framing), or leave it disclosed as-is?**
2. **May a verdict stand at all once its basis is disowned?** 24 codes now read "blocked, low
   confidence, needs review". The conservative posture (F15) says keep the block; the honesty
   contract says we are asserting a commercially decisive NO on data we do not trust. **And it cuts
   both ways**: `93114` asserts the OPPOSITE — `blocked:false`, _"Registrable by a PT PMA in Bali"_ —
   on a tier equally disowned. A client acting on a wrong NO loses an option; a client acting on a
   wrong YES spends money on a company that cannot be licensed.
   **Options: (i) keep the verdict + disclosed [current, shipped]; (ii) flip to NON_CLASSIFICABILE
   like the 8 pilot codes; (iii) keep it but suppress the verdict from the hero badge.**
3. **RECORDED, not a pending decision — a prior signed classification was falsified by the data.**
   The wave-1 test listed `47771`, `52211`, `70100` under CLEAN_CODES ("clean structural", asserted
   byte-unchanged) on the belief that their verdict rests on a structural OSS observation independent
   of the risk tier. The evidence in (1) refutes that belief. They were RECLASSIFIED in this ship —
   moved out of CLEAN_CODES into `WAVE2_RECLASSIFIED_FROM_CLEAN` with a new test that pins both the
   reclassification AND its evidence (`_l2_status == no_oss_risk`, `per_skala == []`, disputed key
   present, disclosure marker present, `status`/`blocked` unchanged, original reason preserved). Noted
   here because a signed classification being overturned by later evidence is exactly the thing that
   must never happen silently — it belongs in the corner even though nothing awaits a ruling.

**L2.1 — `whatChanged` PROVENANCE PASS: CURED on both in-repo surfaces (PR #TBD, 2026-07-25).
The field had THREE live vintages, not one.**

Censused on every surface that serves it, `intel_2026.whatChanged` carried three defects:

|                              | canonical | gold | KG (`kg_nodes.properties`) | `kbli_documents`          | Qdrant                   |
| ---------------------------- | --------: | ---: | -------------------------: | ------------------------- | ------------------------ |
| A false renumbering claim    |         4 |    1 |                          4 | —                         | inside the embedded text |
| B mid-word truncation @216   |        13 |    2 |                         13 | —                         | inside the embedded text |
| C contradicted predecessor   |         4 |    1 |                          4 | —                         | inside the embedded text |
| population holding the field |     1,559 |  428 |                      1,554 | **0 — verified negative** | 428 `doc_type=kbli_gold` |

**`apps/mouth/data/kbli-gold-all.json` WINS over canonical on the rendered page.**
`kbli-data.server.ts::transformCode` takes `whatChanged` (and `whatItMeans`/`whatYouNeed`/
`zantaraOpener`/`youllAlsoNeed`; `baliContext` only if the code is NOT blocked or the gold text does
not read as a foreign-ownership go-ahead) from gold whenever an entry exists, and
`app/kbli/[code]/page.tsx:428` renders `gold.whatChanged` directly. **Curing canonical alone changes
nothing a client sees for those 428 codes** — and a canonical-only immune organ proves nothing.
Standing rule for every future editorial cure: say which of the two files you wrote, and put the
organ on the surface that WINS. The canonical was in the data-plane registry and gold was not — the
guarded file was the one that loses; `kbli-gold-all.json` is now registered too.

- **C is the shape that inverts a client's decision.** `46415`/`46496` said _"→ KBLI 2025: 46415
  (confermato). Verifica e aggiornamento NIB"_ — _your code carried over unchanged_ — while
  `status_mapping` is `CODICE_RINUMERATO` and the layers record a DIFFERENT 2020 origin.
  `49296`/`64210` named `49299`/`64190` while the layers hold `49424`/`64200`.
  **Cured by DELETION, never by correction:** on 46415 the layers disagree with each other
  (pp28/`kbli_2020_source` = 46694, BPS = 46419), so substituting "the right number" would be us
  picking a winner and publishing it as fact. The replacement names every code our layers DO hold
  and declares the mapping unconfirmed. **Which layer is true is an open source adjudication** for
  46415 / 46496 / 49296 / 64210 (PENDING-ARMS).
- **B cannot restore what was lost.** 13 texts were cut mid-word at exactly 216 chars; the trim drops
  the fragment only. `46411` and `46631` are left with almost nothing (46631 = its opening sentence
  alone) — named on every run rather than discovered on the page; restoring prose is editorial.
- **8 gold codes have no canonical record** (`64921`, `85300`, `85491`, `85499`, `85600`, `86903`,
  `96120`, `96130`). Inert — `generateStaticParams` iterates canonical and `dynamicParams = false` —
  but this is the phantom class on a 5th store, so it is pinned by a test.
- **One decision function** (`scripts/kbli_filiera/_whatchanged_basis.py::plan_text`) serves all three
  surfaces; gold carries no crosswalk fields, so gold is judged by the CANONICAL record. The KG
  applier (`backend/scripts/kg_whatchanged_cure.py`) holds NO logic — it consumes a compiler-emitted
  spec whose entries pin `md5` of the text the decision was made against, and refuses to write on
  drift.
- **Innocence measured on real data:** of the 45 KG nodes opening with the template sentence, **28
  are deliberately untouched and every one really does record a predecessor — 0 misses.**

**NEXT AFTER THIS — L2.2, `whatYouNeed` on gapped codes. RE-MEASURED STRUCTURALLY 2026-07-26 —
the "~41 from prose" figure is RETIRED, and the finding it was hiding is bigger than the number.**

Re-run with `_l4bali_basis.gap_basis()` as the selector (structural, as this section previously
demanded) instead of prose matching:

|                                             |                                                                                                                                                                                                         |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| gapped population                           | **218** — not 217. `disputed_key` 116 + `no_oss_scope` 101 + `detached_tier` 1. The 218th is the partial-detach case, which still has surviving rows and so is invisible to a `per_skala == []` filter. |
| carrying `_data_note` (cured)               | **117**                                                                                                                                                                                                 |
| cured set vs `disputed_key`+`detached_tier` | **SET-IDENTICAL**                                                                                                                                                                                       |
| `no_oss_scope` codes ever cured             | **0**                                                                                                                                                                                                   |

**That is the finding.** The `whatYouNeed` cure's scope was the disputed-key class; the **101
`no_oss_scope` codes were never in it at all** — not partially cured, never selected. Of those 101:
**43 name a risk tier with no gap language**, 44 are clean descriptive prose, 14 already disclose.

The old "~41" was numerically close to 43 by coincidence, off the wrong population, and its
approximate-ness masked a scope hole rather than a counting error.

**The worst shape, verified in full on `79909`:** the record carries `_l2_status: no_oss_risk`,
`_l2_source: null`, `per_skala: []`, `kategori_risiko: null` — OSS returned **no risk scope at
all** — while the client-facing text says _"its **OSS risk class** at the large-enterprise (Besar)
scale **is** medium-high or high"_ and concludes _"A PT PMA can pursue this code in Bali, subject to
the standard licensing for its risk class."_ It attributes to OSS a classification OSS never
returned, then builds a go-ahead on it. Same family as L1.2.

The 43: `65123 72201 72202 79909 84113 84122 84130 84144 84146 85103 85104 85204 85314 85317 85318
85581 85582 85583 85584 85586 85587 85589 87101 87102 87202 87302 87991 87992 87993 88101 88902
88903 88904 88905 91421 91423 94110 94121 94122 94910 94990 97000 98100`.

**META-PATTERN, third sighting — the selector is the disease.** Every cure in this programme has so
far selected on a MARKER or a PROXY of the state rather than on the STATE: wave 1 on
`per_skala_disputed_*`, wave 2 on `per_skala == []` (defeated by a PARTIAL detach), and this one on
the disputed-key class (blind to `no_oss_scope`). Each time the population the tool could _see_ was
a strict subset of the population that was _sick_. The cure is to re-derive the state with the same
function that wrote it — which is exactly what `gap_basis()` is for, and what L2.1's
`_whatchanged_basis.plan_text` does for its own three passes.

**Cure shape is NOT mechanical — and "surgical clause removal" is RULED OUT, measured, not
assumed.** Unlike L2.1 pass A these are not a template sentence, and a compiler must not author
replacement prose (the constraint that left `46411`/`46631` thin). The obvious fallback — delete the
tier-asserting clause and append a recorded gap sentence — was tested against the 43 and does not
survive: **40 of 43 are WELDED**, i.e. the tier claim shares its sentence with a fact the reader
still needs (PMA openness, moratorium status, `TERTUTUP`/`TERBUKA`). The 3 the check called
"separable" are welded too on reading — the predicate just missed them. Structure: 32 records carry
1 tier-sentence of 2, 9 carry 1 of 3, 2 are a single sentence. Deleting the clause mangles the
paragraph; deleting the sentence removes facts the page is right to state. Example (`79909`):

> _"Nationally this activity is open to foreign ownership, and in Bali it is NOT blocked by the
> 13 May 2026 moratorium — **its OSS risk class at the large-enterprise (Besar) scale is medium-high
> or high**, which the moratorium leaves open."_

**So L2.2 is an EDITORIAL lane, not a compiler lane** — same bucket as the 95 tier-asserting texts
and the 392 field-name narrations already in PENDING-ARMS, generator≠grader mandatory.

**Lead worth chasing first:** the tier in these sentences looks like an **orphan of the detach** —
`l4_bali.status` (`OK_or_HIGHER_RISK`, …) was derived from `per_skala` BEFORE the rows were
detached, and the prose narrates that derived verdict. If so, this is L1.2's disease on a second
surface, and L1.2's cure shape (structural disclosure on the derived verdict via
`_l4bali_basis.still_certifies` / the `[derivation under review]` prefix) may apply mechanically to
the VERDICT even though the PROSE needs an editor. Verify that provenance before designing the lane.

**SUPERSEDED CENSUS (kept for the correction it records):**

- **4 codes assert a KBLI-2020 renumbering with NO recorded predecessor anywhere.** `64995`, `85691`,
  `85692`, `90113` — `status_mapping: BPS_ONLY`, `pp28_sources: []`, `kbli_2020_source: null` **and
  `bps_2020_ancestors: null`** — yet their `whatChanged` opens with _"Renumbered/adjusted from KBLI
  2020."_. `64995` contradicts itself inside the same paragraph: _"Renumbered/adjusted from KBLI 2020. Codice completamente nuovo in KBLI 2025"_. FACTUAL defect (a provenance claim nothing in the
  record supports), curable by a `scripts/kbli_filiera/` compiler — and the honest replacement is
  _"no KBLI-2020 predecessor is recorded for this code"_, **never** _"new in 2025"_: absence of a
  crosswalk row is not evidence the activity did not exist (that inference is how this class of
  defect is born).
  > **Correction, and why it matters:** an earlier pass in this same session listed **8** codes here.
  > Re-measured on the live canonical after Batch-B's `bps_2020_ancestors` populate landed
  > (2026-07-24, #3082), **4 of those 8 now DO carry a BPS ancestor with a lampiran locator** —
  > `65121→65121`, `85571→78421`, `85693→74321`, `85694→74322` — so their claim is plausibly TRUE
  > (85571's own text already said "Migrated from KBLI 78421"). Their residual issue is a lesser one:
  > `adjudication_status: mechanical-only` / `inheritance_verdict: not-adjudicated`, i.e. the prose
  > states as settled what the record marks as un-adjudicated. A census taken before a sibling lane
  > lands is stale by the time you cure it — re-measure at cure time, never cite the old number.
- **215 `whatChanged` texts mix Italian into client-facing English** (not "10" — that earlier figure
  was a sample read as a population, W97). Two shapes: an English sentence with `"PP28 usa
c[odice]…"` appended, and fully-Italian ones like `"KBLI 2020→2025 mapping: codice rinumerato."`.
  This is editorial, not factual, and belongs to the same editorial-rewrite lane as the 95 tier-
  asserting texts + the 392 field-name narrations (all three tracked in modus PENDING-ARMS).

**W2 / BATCH-B IS UNDERWAY (the "W2 NO-GO" line further down is STALE — Zero gave GO and it has shipped
in mechanical, additive increments).** Chain so far, all merged + proven:

- **Phase-0 gate — SHIPPED (PR #3080, PASS).** BPS 2020↔2025 crosswalk parser + acceptance gate; relation
  digest `ca9e7ffc`, P=R=1.0 on 211 edges; Kimi red-team → 4 fixes. (item-10 Tier-4 AQL default **0.010%
  still awaits Zero's Legge-5 ruling** — the one true open Zero-gate on the mechanical pipeline.)
- **Step 2 — populate SHIPPED (PR #3082, squash `e9f71479`).** Additive canonical field
  `bps_2020_ancestors` written **mechanical-only** onto the **1,338 OSS-native** codes (`_l2_status is
null`); Batch-A's 221 untouched. `inheritance_verdict` always `not-adjudicated` — mechanical presence
  NEVER implies regime transfer. Gate-content-bound (recompute `_relation_digest`), additive-proven 2 ways.
- **Step 4 — SURFACE SHIPPED + PROVEN-LIVE (PR #3095, squash `bc52c788`, 2026-07-25, apps/mouth only).**
  New labeled **"BPS crosswalk"** element on `/kbli/<code>` rendering the field — the FIRST runtime reader
  (was dormant). **Zero chose "additive: new BPS element (safe)"** over re-pointing the legacy `previousCodes`
  (a data-audit proved re-point unsafe). Diff **153 insertions / 0 deletions** → legacy "Previous codes"
  BYTE-UNTOUCHED, zero regression. Honest framing verbatim on prod: _"provenance only, not a licensing
  claim: the regulatory regime of these predecessor codes has not been adjudicated as transferring."_
  **Cross-family gate (generator≠grader; Kimi K3 — Codex 401-dead) CAUGHT A BLOCKER**: the first draft
  LINKED each ancestor to `/kbli/<c>`, but ancestors are KBLI-**2020** vintage while `/kbli/<c>` is a **2025**
  page — verified on real data, **317** ancestor codes coincide with an UNRELATED 2025 code (wrong-vintage
  link = client harm; `KBLI2020:X ≠ KBLI2025:X`). Fix: **ancestors render as PLAIN TEXT, never linked.**
  Proven live on the collision case `01138` (ancestor `01283` = `<span>` plain text, **0** `<a href=.../kbli/01283>`
  on the page). Detail: memory `ops_kbli_batch_b_step4_shipped_2026_07_25`. GOTCHA: `/kbli` pages are
  **SSG+ISR** — `?cb=` does NOT force a fresh render, so a stale edge-cache can serve an old prerender for
  minutes (seen on `01111`); not a gate (twin `01118` renders its self-code fine).

**⚠️ OPEN FINDING surfaced by step 4 — AWAITS ZERO'S EDITORIAL RULING (Legge 5).** Step 4 made VISIBLE that
the two predecessor sources disagree. Grounded on the canonical data (1,338 Batch-B): **703 identical
(pp28 == BPS)**, **635 divergent** (328 where the OFFICIAL BPS knows ancestors the legacy pp28 drops · 69
where pp28 has extra · 238 mixed), and **560 codes render BOTH elements with DIFFERENT 2020 codes side by
side on prod right now** (e.g. `01138`: legacy "Previous codes" = `01122` vs BPS = `01283`; `01309`: `02119`
vs `01302`, disjoint). They are two DIFFERENT sources: **BPS crosswalk = the official government conversion
table** ("which 2020 code does this 2025 code descend from"); **pp28 = a PP28-risk regulatory citation**, not
a real crosswalk. So the element did not create a bug — it EXPOSED that the legacy "Previous codes" likely
over-promises on ~635 codes. **Decision put to Zero (3 options): (a) keep both + a source-note, (b) BPS is
authoritative → demote/relabel the legacy pp28 element, (c) hold + adjudicate the 635 vs ground-truth
(tier-1, heavy).** He interrupted the option-picker with "salva tutto in /kbli-navigator" — so this is
PARKED here awaiting his choice; NO cure/reconciliation started (investigation was read-only). The **211**
figure used earlier was a narrower cut of this same phenomenon; the accurate numbers are 635 divergent /
560 visible.

**Still-open on the program**: Step 3 (per-code `bps_2020_ancestors` correction-key in the cure-spec
compilers) NOT started; item-10 AQL 0.010% awaits Zero; the legacy `previousCodes` has the SAME latent
vintage-link issue (it links pp28 2020 codes to 2025 pages) — pre-existing, candidate follow-up.

---

**W1 PUBLIC-SURFACE HONESTY PASS — SHIPPED & PROVEN-LIVE 2026-07-24 (PR #3049, squash `23fa765e61`).**
Context: a Codex session (rollout `019f83fc`) had been conducting a 7-work-package program (W0→W7) to
take the Navigator to BKPM-presentable. W0 (census/governance/role-contract) closed 2026-07-23; its W1
commits were authored locally but **never survived** (worktree lost, no branch). Zero's read of that
stretch — _"siamo da 10 giorni su W0"_ / _"molto controllo, zero miglioramenti visibili"_ — is the
standing constraint on this program: **W1+ must produce visible product change, not more governance docs.**
Reconciling W1's 5 declared targets against disk found only 2 real:

- **`46100`** — FALSE ALARM. The batch-B design's own REV-2 self-correction (`d7d9486007`, "46100/52101
  were not inconsistent") already retracted it; `52101`/`10433` were cured in #2786. Nothing to do.
- **`68112` / `93114`** — already cured and live (Fase-1 cure + #2926). Nothing to do.
- **"~30% Blocked in Bali" hero stat** (`apps/mouth/src/app/kbli/page.tsx`) — CURED. Was a hardcoded
  guess whose tooltip asserted the moratorium as settled law. Now **computed at render from
  `getAllCodes()`** (`baliL4.blocked` → 518/1559 = 33%; same in-memory cache `getSections()` already
  uses, zero extra I/O) so it self-corrects as cures land, and the copy matches the F15 posture +
  `KBLIProvenancePanel`'s existing "conservative posture" register: _"a working assessment, not a
  certified legal determination."_
- **PT PMA capital claim** in `buying-a-bali-villa-in-2026-…` (**EN/IT/ID/RU, all 4 locales**) — CURED.
  Asserted a flat "IDR 10bn minimum authorized capital", conflating the two BKPM 5/2025 thresholds.
  Now: **2.5bn paid-up at incorporation + a separate >10bn total investment plan per KBLI line**, and
  states the nuance the article had dropped — **for hospitality/property, land+building ARE inside that
  total** (they're excluded for other sectors). Grounded on two already-correct in-repo articles
  (`bkpm-regulation-5-2025-fdi.mdx`, `consulting-business-guide.it.mdx`) read BEFORE editing —
  deliberately NOT a regex sweep on "10 miliar" (rule #1/F-BKPM: E28A KITAS's 10bn is a genuine,
  unrelated immigration threshold and was verified untouched).

**PROVE-LIVE (both consuming surfaces, curl'd on prod):** `balizero.com/kbli` serves `~33%` + the new
tooltip · the villa article serves the corrected claim in EN and — via the **`?lang=` query param, NOT
a URL suffix** (locale routing gotcha, cost one false-negative probe) — in IT/ID/RU, stale copy gone in
all four. `llms-full.txt` deliberately NOT hand-committed: `npm run build` regenerates it from source
content, so the fix propagates on the next Vercel build (hand-committing it would have dragged 11 days
of unrelated derived drift + tripped the PII gate, which is exactly where the lost Codex W1 got stuck).

**Collateral (repo-wide, not KBLI):** this PR was blocked for hours by a red `npm audit` gate failing on
EVERY open PR — 3 new advisories (`hono` ≤4.12.26, `@hono/node-server` ≤2.0.9, `find-my-way` ≤9.6.0)
landed ABOVE the existing override floors, so the floors aged out silently (W98 / family #2). Diagnosed
and fixed here (#3052); a parallel lane shipped the same cure with strictly higher floors first (#3053,
`hono >=4.12.31`) so #3052 was closed as superseded — verified by CONTENT on main (W88), not by proxy.

**4th-SURFACE LEAK FOUND & CURED IN PROD — 2026-07-24, same session, no PR needed (data-plane
apply of already-merged cures).** Hunting for remaining W1-class public lies, a read-only census of
`kbli_documents` against canonical found the Lot-8/Lot-9 cures had landed on canonical + KG + Qdrant
but **skipped the 4th surface**: of the **217** codes whose canonical `per_skala` is `[]` (detached,
licensing disputed/unverifiable), **18 still carried populated `per_skala` rows in `kbli_documents`**
— which `chat_kbli` injects VERBATIM into the LLM context, i.e. the exact 50113 disease still live
on WhatsApp/webchat. All 18 were the sport/klub cluster: `91425` + `93113/93115/93121/93122/93123/
93124/93125/93126/93127/93128/93129/93192/93193/93194/93195/93197/93199`; none carried `_data_note`,
confirming the cure had simply never been run for them.
Cure: `kbli_documents_cure.py --only <18> --dataset <raw URL pinned to main SHA `5d689084d1`> --apply`,
run on Fly (the dataset is NOT in the image — pass a **commit-pinned** raw URL, never a moving `main`).
Dry-run first: 18/18 eligible, 0 skipped, all `[GAP]` class. All 18 verified eligible beforehand
(`per_skala_disputed_pp28_collision` marker + `intel_2026.whatYouNeed` present) so the tool wrote only
canonical-derived honest-gap prose — never an invented value (rule #9).
**VERIFIED INDEPENDENTLY after apply** (re-read via the read-only role, not the tool's own report):
the 18 → 0 licensing rows / 18 `_data_note`; forensic archive `kbli_documents_archive` captured 18
pre-cure rows; and the **global** invariant now holds — **217 detached codes, 0 still serving
licensing**. **PROVE-LIVE on the consuming surface**: `chat_kbli` for 93121 now answers _"the specific
risk tier and exact licensing workflows … are currently unconfirmed … We do not estimate or guess risk
tiers … verify directly at oss.go.id"_, and states the capital doctrine correctly (2.5bn paid-up +

> 10bn investment, BKPM 5/2025 superseding 4/2021 — #2813's generation-layer fix confirmed working).
> **Standing check for every future lot**: after a cure lands on canonical, re-run the
> detached-vs-`kbli_documents` census — a lot can be "closed" on 3 surfaces and still lie on the 4th.

**W1 is CLOSED. W2/Batch-B is now UNDERWAY and shipping (see the top LIVE-STATE entry: Phase-0 gate #3080,
step-2 populate #3082, step-4 surface #3095). The "still NO-GO" wording below is superseded — Zero GO'd it.**

**Batch A CLOSED 2026-07-21 (114/114, 0 remaining)** — the full "A-serving" 114-code sweep
(113 A-serving/pp28 + 80190 A-serving/orphan) is done. Final tally: 109 full detach + 2
tier-scoped partial detach (93114, 93191 — first production use of PR #2921's
`partial_detach` primitive, built after the SAME gap was confirmed twice, Lot 8 then Lot 9) +
3 certified-clean/no-cure (93111, 93112, 93119 — quarantine was a tooling artifact, not a
record defect; resolved via PP28 Pasal 8(1) grounding + derived_license inapplicability).
Lot 10 report: research/operations/2026-07-21-kbli-batch-a-lot10-conductor-gate.md. Program
closure synthesis: research/operations/2026-07-21-kbli-batch-a-closure.md.
**Residual: PR #2926** (one-off KG/Qdrant partial-detach for 93114/93191, audit-trail only —
production already correct, independently re-verified live) is OPEN, blocked by an unrelated
npm-audit CI gate that PR #2931 healed on main AFTER #2926's own CI ran — a rebase was pushed
2026-07-21 to pick up the fix; check PR #2926's current state before assuming still-blocked.
**What's NOT done:** Batch A was a SUBSET of the ~221 no-scope population (8 pilot + 114 Batch
A = 122 adjudicated; ≈99 genuinely untouched remain — supersedes the stale "~213" figure
below, which pre-dates Batch A's closure). Batch B had a SIGNED design (#2801); it has since been GO'd by
Zero and is shipping mechanically (Phase-0 gate #3080 · step-2 populate #3082 · step-4 surface #3095 — see
the top LIVE-STATE entry). The one open Zero-gate on Batch B is the Tier-4 AQL 0.010% default (#3080).

**Lot 7 (A-L7) — CLOSED 2026-07-20** (closure PR #2885, squash `7fc6c18f3c`, merged
2026-07-20T11:01:47Z — pure-docs: gate reports, corner updates, ledger entries, zero code/data
changes; needed 5 rounds of manual `git merge origin/main` conflict resolution against a
fast-advancing main, see PENDING-ARMS). The gate, cure, cross-family GLM Appendix A adjudication,
and the 41013 post-refinement re-run (refinement #2 VALIDATED, 41013 kept as a contract artifact,
refinement #3 FILED) had already landed on main via the prior lot-cycle PRs — #2885 formally closes
the corner narrative and ledger for the lot, nothing left open.

**Lot 8 (A-L8) — D6 gate SECOND SIGNED 2026-07-20 + cure MERGED** (gate PR #2892, squash
`66ee3932e4`; cure PR #2896, both on main; report
`research/operations/2026-07-20-kbli-batch-a-lot8-conductor-gate.md`):
15/15 codes adjudicated (13 members + 2 controls) — 0 certified, 13 quarantined, both calibration
floors breached (m1 0.615<0.75, m2 0.000 outside [0.2,0.85]) but root-caused as a genuine finding,
not a pipeline defect: this activity family (91425 + the whole 931xx sport/klub cluster) has
unusually poor PP28 primary-source-locatability. Findings: 1 genuine `payload_cross_contamination`
(91425 — pp28_sources cited a wrong neighbor code, conductor-eye image-verified), 6 genuine
`source_absent_in_vault` on exhaustive 21-file/11,208-page scans (93113/93115/93122/93123/93125/93126),
1 wrong-pointer via a reproducible "hot trap page" (93121, same trap page also hit control 63101 —
2nd sighting), 1 both-tiers-absent (93124), and 4 held UN-cured because the underlying crosswalk+
licensing is genuinely sound and only a synthetic derived field lacks formula coverage (93111/93112/ 93119) or the compiler lacks a tier-scoped detach primitive (93114) — detaching these would destroy
good data, not fix a defect (see PENDING-ARMS for both open items). Cure spec
(`scripts/kbli_filiera/cure_specs/batch_a_lot8.json`, 9 codes) **APPLIED to canonical via #2896**.
**Surfaces DONE** (KG detach + Qdrant clear + cache bust + prove-live, all independently
re-verified this session for the 9 cured codes).
**Red-team: Codex/agy both unavailable** (Codex re-authenticated but hard quota-limited until
2026-08-19 on this ChatGPT account; `agy` hung on two independent re-probes) — **Kimi K3 used as
cross-family substitute seat** instead of waiting a month, verdict **CONFIRMED-WITH-NOTES** (none
of the 13 dispositions refuted; 2 MEDIUM + 3 LOW audit-trail defects found and cured in the second
signing — canonical hash pin, disputed-key report/spec mismatch, a lampiran-letter mislabel, a
line citation, one typo). Full findings in the report's Adversarial review section. Also an
evidence-loss incident this cycle (first launch hit an empty evidenceRoot, all ~15 seats correctly
fail-closed rather than hallucinate — re-pulled and independently re-verified before relaunch,
PULL COMPLETE 15/15). **Cross-family Appendix A screen for Lot 8 — DONE** (PR #2909, Kimi K3
substitute seat — Codex/agy both dead at the time): verdict **m1 2/2 match**, one real gold-layer
staleness bug found and fixed in the same session; caveats explicitly declared (no Next.js build
run). **Lot 9 — DONE**: D6 gate SECOND SIGNING complete (PR #2911, Kimi K3 adversarial review,
none of the dispositions refuted) + cure APPLIED (PR #2913: 8 detach + 2 tier-scoped-held +
status_mapping/whatChanged fixes), both merged to main. Lot 9 evidence pins (now historical) were
at `/tmp/kbli-conductor-a1-0718/lot9-prelaunch-pins.md`.

**Where the 1,559 actually stand (grounded on the Filiera methodology census):**

- **1,338 / 1,559** carry OSS-native `ruang_lingkup` (vintage-2025 pure) → structurally safe from
  cross-vintage contamination. This is the trustworthy core.
- **~221 no-scope codes** (OSS ruang-lingkup 404) had `per_skala` **silently filled from PP28/curatela
  (vintage 2020), NOT OSS** (`_l2_status: no_oss_risk`, `_l2_source: null`). Each is a false-friend
  SUSPECT until crosswalk-adjudicated. **This ~221 set is the heart of the remaining risk.**
- The **`pma_status` layer** (Perpres 10/2021 + 49/2021) is ALSO vintage-2020 → a separate
  cross-vintage axis needing per-code crosswalk adjudication across the whole catalog (FATAL-2).
- The **68% KG dedup disease** + gold/editorial baked errors are orthogonal contamination layers.

**What is CURED & PROVEN-LIVE (the pilot slice — 8 of the ~221):** 68112 + the 7 quarantined
false-friends **49213, 51103, 51203, 20111, 50115, 60312, 64310**:

- **Risk residual CLOSED** (#2597, merge `4c6f43bc6b`, Fly **v3800** + Vercel READY): backend
  `_resolve_risk_profile()` = `qdrant_risk or licenses[0].risk or "Not classified"` (honest, not a
  false "Low"); frontend `getRiskLevel`/`getRiskBadge`/`RiskGauge` render "Not classified". Qdrant
  `kategori_risiko` cleared for the 6 no_oss (68112/51103/51203/50115/60312/64310); **49213/20111
  cleared too** after evidence review (both confirmed collisions). `inspect_kbli` cache busted →
  WA/webchat proven-live.
- **KG** (#2596 script MERGED; DB cured): all 8 have 0 REQUIRES edges, disputed targets archived in
  `properties._disputed_requires`, `licensing_status` → `PENDING_REGULATION`.
- **Canonical `per_skala` detached** (#2589 MERGED): `per_skala=[]` + `per_skala_disputed_pp28_*`
  preserved + `_data_note`; 4 copies synced, sidecar bumped.
- **`intel_2026.whatYouNeed` honest-gap** (2026-07-17, branch `agent/air-m5/mouth/kbli-whatyouneed`,
  commits `c724cd8bca` canonical + `344a928bed` gold — LANDING, push armed under M5 fleet
  contention): 7 canonical texts + **2 gold texts (49213, 50115 — gold MASKS intel_2026 on
  /kbli/<code>, LicensingSection parses gold.whatYouNeed directly)**, all Codex-gated PASS. The
  other 5 are not in gold. → after this lands + Vercel rebuild, the 8-code pilot is fully honest on
  every consuming surface.
- **KG dedup partial cure** #2528 landed (scoped); root fix is Fase 2 (below).
- **TRACK-P product/UI layer PROVEN-LIVE** (2026-07-18, PR #2632 + badge-fix PR #2643, both merged, `apps/mouth` only — data-plane untouched): every `/kbli/<code>` page now RENDERS the honesty contract. A **provenance badge** (verified 1,336 / crosswalk-pending 215 / not-classifiable 8) derived in `apps/mouth/src/lib/kbli-provenance.ts` from structured markers ONLY (`_l2_source` EXACT-match `OSS_RBA_resiko_2025`, `_l2_status`, `per_skala_disputed_*` keys — never prose; disputed wins precedence over a stale OSS marker on 49213/20111; unknown marker → `unverified_source`, no invented vintage). A **"Sources & Verification"** per-layer panel (source + KBLI vintage + verdict; PMA disclosed as Perpres 10/49 vintage-2020 audit-pending). A **"Regulatory Divergence"** section on the 8 cured codes (verbatim `_data_note` + detached rows as audit trail + citation chips conditional on markers). FAQ (visible + FAQPage JSON-LD), Article JSON-LD, both key-facts grids and every RiskBadge carry the crosswalk-pending qualifier; not-classifiable codes no longer claim "special/sectoral regime". Wording rule F12 enforced (404 = "not retrievable via OSS API", never "not published"; detach copy speaks only about OUR verification, never asserts regulatory absence). Codex GPT-5.6 adversarial gate, 7 rounds (2 BLOCKER + 6 MAJOR cured) → SHIP. Also fixed the `TransitionBadge` (Direct Match/Renumbered/Aggregated/New-in-2025) from hardcoded light-mode Tailwind to `--kbli-*` dark-theme tokens (PR #2643). **BOUNDARY (recorded so nobody re-investigates):** `kbli-explorer` (the AI-chat inspect surface) canNOT show this provenance client-side — it consumes `/api/v1/kbli-notebook/inspect/<code>` returning `KBLIDetail`, which carries NO markers (`risk_profile`/`licensing_status` only). Aligning it is a BACKEND payload change (expose the verification state in `inspect_kbli`), NOT an apps/mouth task. Cured codes already degrade correctly there via the #2596/#2597 backend cure. **Follow-ups still open (owner/lane-gated, not apps/mouth):** F12-conformant rewrite of the verbatim `_data_note` texts (data-plane, filiera compilers); PMA verdict re-label on PMABadge/hero across all 1,559 pages (FATAL-2 axis, Zero decision — Legge 5).

**PHANTOM CODES — a class no cure tool could reach (found + CURED + PROVEN-LIVE 2026-07-24, #3070/#3072/#3073):**

`kbli_documents` is a strict SUPERSET of the canonical catalogue: **1,563 rows vs 1,559 codes**.
The 4 extras are KBLI **2020** codes — `26120`, `60111`, `82920`, `85598` — carrying full 2020
licensing payloads. The router's direct-code path (`kbli_notebook_chat.py:715`) resolves ANY
5-digit code in the user's question straight against this table, so a phantom row WINS an
exact-match lookup. Live prod proof before the cure: **82920** → _"Yes, a PT PMA can absolutely
run this business"_ + per-scale risk tiers + Gubernur authority + ISO 9001 (the 2025 catalogue
split 82920 into 82921-82929 + 39002); **60111** → _"TERBUKA, 100% open to foreign ownership"_ +
a full ISR/Kominfo permit path + _"register your NIB under KBLI 60111"_ — for a **government**
radio-broadcasting code retired in 2025.

> **STRUCTURAL LESSON — why this survived every previous cure.** EVERY cure tool in the fleet keys
> off _"a canonical record exists"_: `kbli_documents_cure.py` skips on "no `per_skala_disputed_*`
> marker", `kg_kbli_license_fix.py` skips on `record is None` → "not in canonical dataset". That is
> exactly what a phantom code lacks, so **a code living only downstream is unreachable by all of
> them**. Any future cure tool must decide whether its scope is "codes the canonical knows about" or
> "rows that actually exist in the store" — and say so explicitly.

Cure: `backend/scripts/kbli_documents_phantom_cure.py` — TWO arms, `--only` mandatory, no sweep
flag, `--census` reports the phantom set without writing. Rows are rewritten into a
superseded-code notice (2020 payload archived under `*_superseded_kbli2020` + verbatim in
`kbli_documents_archive`); 2025 successors come ONLY from the canonical crosswalk fields
(`kbli_2020_source`/`pp28_sources`), each with its `mapping_note` verbatim — the crosswalk carries
weak auto-matches (39002 "Penyimpanan Karbon" ← 82920 "packaging" at score=71%) and neither silent
inclusion nor silent exclusion (W97) is acceptable. The `--kg` arm detaches **53 REQUIRES edges**
(26120=19, 60111=2, 82920=27, 85598=5), the channel `inspect_kbli` turns into `licenses` and
`_resolve_risk_profile` turns into the risk label.

**FULL CONSUMER MAP for the phantom class, censused 2026-07-24 — the phantom codes live in exactly
TWO stores.** The verified negatives are recorded here so no session re-derives them:

| Surface                                        | Phantom codes present? | Evidence                                                                 |
| ---------------------------------------------- | ---------------------- | ------------------------------------------------------------------------ |
| `kbli_documents` (→ `chat_kbli`)               | **YES — 4**            | 1,563 rows vs 1,559 canonical                                            |
| `kg_nodes`/`kg_edges` (→ `inspect_kbli`)       | **YES — 4 + 53 edges** | all 4 nodes live, `licensing_status: REGULATED`, `pma_status: TERBUKA`   |
| Qdrant (→ `search_kbli`)                       | NO                     | `search_kbli` returns only 2025 codes; zero phantom points               |
| canonical / `apps/mouth` `/kbli/<code>`        | NO                     | phantom absent by definition — pages are generated from the 1,559        |
| `apps/kbli-navigator/data/kbli-2025.json`      | NO                     | **byte-identical to canonical** (blob `2417c876`, same on `origin/main`) |
| `apps/kbli-navigator/lib/kbli-gold-content.ts` | NO                     | zero occurrences of any of the 4 codes                                   |

> **CORRECTION to the "Surfaces 5 & 6" block below (2026-07-24):** it describes surface 5 as rotted
> (1,563 records, zero quarantine markers, cure "in flight"). That is **STALE** — the cure landed:
> the file is tracked, is 1,559 records, and its blob is IDENTICAL to the canonical dataset on
> `origin/main` (verified by content per W88, not by branch name or PR state). Surface 6's gold
> override is likewise clean of phantoms, though its 68112/49213 override issue is a SEPARATE
> question this census does not speak to.

Cross-family adversarial gate: **Kimi K3 → SHIP-WITH-FIXES**, 2 MAJOR both fixed (metadata
neutralisation was a whitelist-of-two → now FAIL-CLOSED on any unrecognised metadata key; the
canonical catalogue was trusted blind though "phantom" is _defined_ by it → `validate_dataset()`

- `--apply` refused against the unpinned `main` URL + dataset sha256 recorded in every cured row).
  **The Codex seat is 401 token-revoked** (not quota) — needs an interactive `codex login`,
  `operator[GUI]`.

**APPLIED + PROVEN-LIVE on every consuming surface (2026-07-24, Fly v3910→v3912).** Both arms ran
on prod (dataset pinned to SHA `e6deb07a25`, never `main` — the script refuses `--apply` against the
unpinned URL). Independently re-verified by reading the DB with the read-only role, NOT the tool's
own report:

- `kbli_documents`: 4 rows → 0 licensing rows, `licensing_status: NOT_IN_KBLI_2025`,
  `pma_status: Verify at OSS`, `_data_note` + `*_superseded_kbli2020` archive present, the false
  `kode_kbli_2025` key removed.
- KG: **0 REQUIRES edges** left on the 4 nodes, 53 archived (19/2/27/5 — exact match to pre-cure),
  nodes marked `NOT_IN_KBLI_2025`.
- `chat_kbli`: answers "82920 is an obsolete KBLI 2020 code … you cannot use it on OSS today",
  lists the 2025 successors, refuses to guess risk tiers. ✅
- `inspect_kbli`: all 4 return `licenses: []`, `risk_profile: "Not classified"`,
  `licensing_status: NOT_IN_KBLI_2025`, `pma_status: Verify at OSS` — the plantation-contaminated
  packaging payload is gone. ✅

**Cache trap paid for here (now a tracked tool — `backend/scripts/kbli_inspect_cache_bust.py`,
#3072 + fail-loud fix #3073):** `inspect_kbli` caches the whole `KBLIDetail` under
`kbli_inspect_v2_{code}` with a **30-day** TTL (`get_kbli_ttl`), on Redis (survives restart). Two
gemini traps, both catalogued in memory `lesson_inspect_kbli_cache_poison_and_bust_redis_init_2026_07_24`:
(1) INSPECTING a cached surface BEFORE curing it poisons its entry for the TTL — my pre-cure
diagnostic call is why `inspect_kbli` 82920 kept lying after the DB was clean; (2) a one-shot
eviction tool that does NOT call `RedisManager.get_instance().initialize()` degrades to an empty
per-process in-memory LRU and reports a FALSE CLEAN ("0/4 had a cache entry" while Redis held them).
The tool now inits RedisManager, logs `cache backend: shared Redis`, and exits non-zero if REDIS_URL
is configured but unreachable. **RULE for every future KBLI cure on a cached surface: cure the store
→ `kbli_inspect_cache_bust.py --only <codes> --apply` → re-verify the surface. Curing the store is
not curing the surface.**

**Surfaces 4-6 + capital doctrine + Batch-B (M5 conductor-verified 2026-07-19):**

- **Surface 4 — `kbli_documents` Postgres table, CURED IN PROD** (#2796 merged + fly apply): table
  seeded 2026-02-18, no builder, injected VERBATIM into `chat_kbli`'s LLM context
  (`kbli_notebook_chat.py:635/:699`) — served fabricated licensing for quarantined codes (live
  proof: 50113 asserted Menengah Tinggi/KSOP/BKI/STCW + Rp10bn from the revoked BKPM 4/2021).
  Cure `backend/scripts/kbli_documents_cure.py` (provenance-bound, dry-run default, `--only`
  mandatory) applied to 86 codes (85 gap→`PENDING_REGULATION`, 49213 restored rows preserved);
  forensic archive `kbli_documents_archive` (86 rows, one-shot); PROVE-LIVE: `chat_kbli` 50113
  now serves the honest gap. PENDING-ARMS: whole-table refresh (~1,473 unmanaged rows), KG
  variant-node cleanup, `search_kbli` "Unknown" label.
- **Generation-layer capital doctrine corrected** (#2813, armed, in CI): `chat_kbli`'s prompt had
  Rp10bn-as-paid-up HARDCODED in 5 places; corrected to the BKPM 5/2025 two-threshold doctrine
  (modal disetor 2.5bn ≠ investment value >10bn/KBLI/location) + a new abstention rule (never
  estimate a risk tier by analogy).
- **Surfaces 5 & 6 — `apps/kbli-navigator` (knowledge.balizero.com; it is a Next.js/Vercel+Netlify
  app, NOT the "native desktop app" §5 describes — mislabel found during Batch-B design work,
  ALIGN-FLEET TODO): BOTH CURED ON MAIN — re-verified on `origin/main` 2026-07-24, this entry
  previously said otherwise and was STALE.** (5) `data/kbli-2025.json` now carries **1,559**
  records (not the rotted 1,563) and 68112 reads correctly — residential title, `per_skala: []`,
  `per_skala_disputed_pp28_mice` + `_l2_status` + `_data_note` markers present; the desync cure
  landed. (6) `lib/kbli-gold-content.ts` no longer overrides the cure: its 68112 entry is the
  honest-gap text that NAMES the collision ("code-number collision … MICE-venue rental … do not
  apply to residential leasing and have been removed"), and 49213 correctly frames AKDP/AKAP as
  the DIFFERENT regulatory basis it is excluded from. **Do NOT re-open these as work items.**
  Residual on this app: it is **SSO-gated** (`/kbli/<code>` → 307 → `kita.balizero.com/login`),
  so it is an INTERNAL/team surface, not an anonymous-public one — anonymous curl can never
  prove-live it (cf. [[discovery_nuzantara_rag_401_precedes_routing_2026_07_22]]); a real
  prove-live there needs authenticated browser QA.
- **Mouth gold cure LIVE** (#2794): 10 gold records' detached-code echoes cured
  (whatYouNeed/zantaraOpener/baliContext), PROVE-LIVE on 68123/60103; 63-phantom triage table
  `scripts/kbli_gold_remap_table_status.json` (48 unmapped / 8 ambiguous-SPLIT / 7
  single-candidate).
- **Batch-B pre-registration design SIGNED** (#2801 merged, REV-4b): determinism gate closed after
  4 Codex xhigh rounds + Gemini. **Phase-0 parser gate PASSED** (report
  `research/operations/2026-07-21-kbli-batch-b-phase0-parser-gate.md`: 20-page holdout, 100%
  precision/recall, cross-family Sonnet+Kimi K3 blind verification) and the parser+FULL-CORPUS
  crosswalk relation (`scripts/kbli_filiera/bps_crosswalk_parser.py` + `bps_phase0_gate.py`,
  `data/kbli-filiera/phase0/bps_crosswalk.json` — 1,559/1,559 codes with BPS ancestry) shipped
  2026-07-24 via PR #3083 (was orphaned in a local worktree, un-orphaned and merged this session).
  **Still open before Lot B-1 can dispatch**: (a) `populate_bps_ancestors.py`, the canonical-WRITE
  compiler that mutates `bps_2020_ancestors` from the relation — not yet built (step 2 of 3; the
  full-corpus PARSE is done, the canonical WRITE is not); (b) Tier-4 population count — requires
  applying the design's §1.5 tiering logic to the now-available relation, not yet run; (c) Tier-4
  AQL parameters (n/Ac/switching state) computed from that count + the measured 0.0 holdout error
  rate per the frozen ISO 2859-1 rule, then Zero's Legge-5 accept-or-override ratification — not
  yet computed; (d) 5 fresh POS controls, conductor-eye-adjudicated on raw Lampiran renders —
  explicitly non-delegable, not yet started. See §5.

**What is NOT done (the actual remaining program):** ~213 no-scope codes un-adjudicated · the
`pma_status` cross-vintage audit across the catalog · the KG 68% disease at the root · the 63
phantom gold-remap rows · Batches A(remainder)/B/C/D of the Filiera sweep. See §5.

**Batch-0 vault base DONE — extraction still BLOCKED (2026-07-18, LANE-B0 task #8, PR #2622 merged `17f360df4`):**
raw-evidence vault live on Mini `~/nuzantara-vault/` (bps 1 + oss 4,933 + pp28 21 blobs) ·
manifest committed `data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json` (4,955
entries, all sha256+provenance, deterministic; file sha256 `e7d25a37…`) · Tigris mirror
proven-live 4,959/4,959 at `nuzantara-backups/kbli-vault/` · OSS coverage 6,236/6,236
(code,endpoint) pairs — 1,303 absences at 3 probes each, no-scope set EXACTLY 221 (zero drift
vs census). **Open quarantines (proposed in PR #2622, NOT resolved):** BPS Vol.1 missing
(Turnstile → browser lane) · Perpres-annex compiler not built · absence ≥72h window needs one
probe after 2026-07-19T18:10Z · stray mirror copy in `nuzantara-warroom-images/kbli-vault/`
(pre-fix run) to delete. **EXTRACTION GATE — collapsed to ONE precondition (updated 2026-07-18):** the gate is now just **P0 membership** (#2640 LANDING; the Detect Secrets git-SHA false-positive on `canonical_revision` was fixed via a durable auto-triage rule for `data/kbli-filiera/membership/`, proven end-to-end; auto-merge armed SQUASH). Two prior "gates" dissolved: (a) **renders are NOT a bulk pre-build** — the PP28 300-dpi renders are produced **on-demand per-code at D2** from the sha256-pinned PP28 PDFs (`pdftoppm -r 300`, deterministic, offline); (b) the **OSS endpoint inventory is DONE** (6,236/6,236 pairs, in the manifest). **P1-v2 UNBLOCKED — LANE CLAIM (D12 anti-collision): the P1-v2 second vault wave is OWNED by the S2/Pro conductor session (MANDATO GARUDA), claimed 2026-07-19 on Zero's GO** (supersedes the 2026-07-18 HELD ruling _"aspetti dopo il Pilota A1"_ — Pilota A1 measured, GO issued). Scope of the claimed lane: fetch + sha256 + vault manifest ADDENDUM on Mini (via ssh) for Perpres 10/2021 + 49/2021 investment annexes, Bali (Gubernur letter B.27.000/642/PM/DPMPTSP) + Kepmenaker 228/2019, with DATED per-instrument status snapshots and per-instrument provenance. Facet rules (Zero, verbatim intent): `pma_status`/`l4_bali`/TKA facets stay **abstain fail-safe** (A1/A5/A6) and unlock ONLY per-code where the wave is grounded — **never a global lift**; current Batch-A lots continue in parallel under abstain until the wave is ready. **Wave status 2026-07-19: DELIVERED** — 8 instrument blobs fetched + sha256'd on the Mini vault (`~/nuzantara-vault/p1v2/`) with 4 dated per-instrument status snapshots; manifest addendum `data/kbli-filiera/manifest/vault-manifest-p1v2-2026-07-19.json` MERGED (#2811, hashes independently re-verified via ssh; claim PR #2808). Next: per-code facet-unlock design (fase 2 — no facet unlocks yet, abstain still in force everywhere). **Disjointness: the M5 Fable session owns Batch B (branch `agent/air-m5/docs/batch-b-design`) — this lane does not touch Batch-B artifacts; the M5 lane does not touch the P1-v2 vault wave.** First-writer-owns per scar D12. **⇒ Pilota A1 starts on the OSS+PP28+BPS core the moment P0 is on main.** Genuinely-deferred (NOT gates): BPS Vol.1 (Turnstile → browser lane), absence-window one probe after 2026-07-19T18:10Z, stray warroom mirror copy to delete.

**Batch-A Lot 1 conductor gate SIGNED, second signing post-red-team (2026-07-18, MANDATO S2
session):** final verdict **13/13 quarantine, 0 certified** on the first A-serving lot (a
contiguous taxonomy-ordered segment, divisions 01→39 — NOT a random sample; no extrapolation to
the full ~221 class claimed, but fail-safe: every no-scope code is a SUSPECT until proven). The
lane (same-family Sonnet D1/D5) had certified 8 clean; 7 were FALSE-clean on content evidence
(Codex refuter 2: 02402, 38222 · blind-GLM-with-vision 5: 05200, 01287, 02201, 08920, 36003) and
the 8th (19206) was quarantined under the plan's preregistered divergence rule (A-6(a): two
cross-family seats vs the conductor's own picked clean — caught by the mandated full-report
red-team, Codex sol FIX-FIRST 4 BLOCKER/4 MAJOR/4 MINOR, all cured not argued down). Disease
categories censused: **payload_cross_contamination** (licensing payload whose content belongs to
another activity), **unresolvable_source_pointer** (pp28*sources row not retrievable from the
pinned corpus as hunted — NOT asserted nonexistent; earned ABSENT needs the image-grade scan),
**mapping_metadata_false**, **split-generic-payload** (19206). Meta-pattern: \_same-family blind
agreement measures transcription fidelity, not truth; a provenance pointer is not a content
check* → cross-family IMAGE-GROUNDED blind D5 + D4 content-vs-scope check are now LANE protocol
(GO package §10). Calibration: FOUR declared breaches — m1 ❌ 0.385 (cross-family extractor IAA;
the lane's blindness measured), m2 ❌ 0.000, m3 ⚠️ new-category pause, m5 ❌ NEG 7/8 (49213
miss) — via plan amendments A-4/A-5/A-6; never silently resumed. **m5 HALT LIFTED (A-6(b)
RESOLVED, same session):** the 49213 NEG miss was adjudicated per-ancestor on image-grade renders
(49213-2025 = merge of {49214, 49219, 49413}-2020; all 3 PP28 regimes verified BY EYE identical —
NIB+SS, Bupati/Wali Kota — the unique case where a merge's ancestors converge, vs 01700 where they
diverge) → the miss is a certifiable-restore case, not a silent gap; restore of 49213 is a
scheduled data-plane cure (dedicated PR, `pp28_sources=['49214','49219','49413']`). Artifacts:
report `research/operations/2026-07-18-kbli-batch-a-lot1-conductor-gate.md` (signed, §12
receipts) · cure spec `scripts/kbli_filiera/cure_specs/batch_a_lot1.json` (13 codes, detach-only,
no substitute values, PMA/l4/TKA still abstain) · registry test
`scripts/tests/test_kbli_batch_a_lot1_registry.py` (module-gated on `_cure_applied()`) · Qdrant
clear tool `apps/backend-rag/backend/scripts/kbli_qdrant_risk_clear.py` (dry-run default,
`--codes` required). None of the 13 in gold (verified vs all 428); KG has 147 live REQUIRES edges
across the 13 (counted on prod) → detach via `kg_kbli_license_fix.py` post-apply. **GO GRANTED
(Zero, 2026-07-18, Legge 5): explicit "go" on the Batch-A remainder + EXTENDED GO ("quando
finisce lot 2 procedi con gli altri lot senza fermarti") — continuous lot-by-lot execution of the
whole remainder (~101 in-scope codes, lots 2→~9) under the amended lane protocol, no per-lot GO
needed; Zero is notified at Lot 2 kickoff. A-6(c) precondition (calibration registry v2
re-emission on the cured canonical) ships in the governance PR before the Lot 2 lane starts.**

**Batch-A SWEEP PROGRESS — Lots 1-5 (dense recap 2026-07-19, MANDATO S2 continuous run; supersedes the Lot-1-only block above for current state):**

- **91/114 original in-scope adjudicated across 7 lots — 91/91 QUARANTINED, 0 certified.
  L7 fully applied+surfaced (cured-and-live cumulative 91/1,559 incl. pilot).**
  Census by lot: L1 13 (div 01→39, gate report 2026-07-18-...lot1..., cure applied+surfaced) ·
  L2 13 (#2753 gate, #2761 cure) · L3 13 (#2768 gate, #2769 cure) · L4 13 (#2774 gate, #2776
  cure incl. runner innocence-PROMPT fix; 64955 wrong-parent flagship; ALL TEN 66xxx carry the
  identical cooperative-rating payload) · L5 13 (gate #2788 MERGED, cure #2778 merged incl.
  runner INNOCENCE_SCHEMA symmetric-blind fix; members 66192→70100) · **L6 13 (#2803 gate —
  incl. the 80190 certification REVOKED→re-quarantined, W100-L6 rule "conductor's eyes on the
  FULL canonical record for every certification"; #2800 cure incl. certification-contract gen-2:
  `exposed_facts_inventory` REQUIRED + fail-closed `factsInventoryUnverified`; surfaces 13/13
  PROVEN-LIVE, spot-check 80190)** · **L7 13 CLOSED end-to-end (gate #2837, cure spec+contract
  #2831, data-apply #2878, surfaces PROVEN-LIVE 2026-07-20 — conductor spot-check on the largest
  cluster 86201/27 disputed-edges + 86203/91424, independent of the applier's own report): 6
  source_absent {85403,85404,86109,86201,86202,86203} / 4 payload {85330 aviation PAGE-BLEED,
  85401 51108-fan, 86102, 91212} / 1 collision {90111, ISO-9001 matcher-trap} / 1
  illegitimate-inheritance {91222} / 1 unresolvable {91424}; Appendix A cross-family GLM
  adjudicated (m1 5/5 no verdict overturned, NEG surfaced 2 real editorial-layer deviations on
  52239/68127 — FILED, POS 2/2 clean); 41013 control re-run LIVE post-refinement (wf_644964d5-783):
  refinement #2 (derived-fact rule, Pasal 225(1) MT / 230 Tinggi / 124(4) derived-license)
  VALIDATED, 41013 converts to "contract artifact" but stays quarantined pending refinement #3
  (tier-label join, FILED). 96 KG REQUIRES edges removed (86201 alone = 27), Qdrant risk cleared,
  13 cache keys busted, `kbli_documents` 4th surface applied (13/99 cumulative, whole-table
  builder still missing). **In-scope remainder: 23** (of 221 total, invariant) → **2 lots to
  finish** (L8 12+1/L9 10 — see membership split below; L8 gated on refinement #2, now shipped).
  **[HISTORICAL — superseded]** this whole dense-recap block is dated 2026-07-19, mid-sweep; L8,
  L9, and L10 have since all CLOSED (see **Batch A CLOSED 2026-07-21 (114/114, 0 remaining)** at
  the top of this section, which is the current top-line state) — "2 lots to finish" no longer
  applies, kept here only as the sweep's own historical log.
  Surfaces: L1-L4 + L6 + L7 applied and PROVEN-LIVE (KG REQUIRES edges removed, Qdrant risk
  cleared, cache busted, backend inspect + mouth SSR eye-verified per lot); **L5 surfaces
  INDEPENDENTLY RE-PROVEN 2026-07-19** (prod KG query: 13/13 zero REQUIRES edges +
  `PENDING_REGULATION` + disputed archived; live `inspect/66192` returns risk "Not classified",
  licenses []). Governance: calibration **v3\*\* on main (#2777, supersedes conflicted #2772) — NEG
  47 salt "v3", POS 8, `pos_preverification_required`, burned-set 16 (extended to 119+ post-L7 D0
  back-reconstruction, see Lot 8 pins).
- **Per-lot cycle (proven 5×, ~2h):** lane Workflow (launcher `/tmp/kbli-conductor-a1-0718/
lotN-launcher.js`, byte-exact membership injection via Python, canonical-sha fence) → conductor
  D6 gate + by-eye renders → FIRST signing → codex sol xhigh red-team (FULL-output capture, W97)
  → cures → SECOND signing (now with immutable artifact manifest: sha256 of raw/journal/renders/
  canonical + runner blob — L5 innovation, keep it) → cross-family GLM 5.2 pass (m1 sample +
  m5-NEG + m5-POS w/ conductor exposed-codes screen) → Appendix A adjudication → gate PR →
  cure PR (conductor gates the diff, then arms auto-merge) → surfaces → next lot.
  **W100 held 5/5 lots: every first signing was FIX-FIRSTed; substance (quarantine verdicts)
  survived every pass — the errors live in the conductor's audit trail, never in the verdicts.**
- **Program-level discoveries (L4-L5):** (a) cooperative-payload ROOT traced: PP28 lampiran row
  66292 is KBLI-2020-vintage ("Pemeringkat UMKM dan Koperasi", true 2025 home = 66198); one
  vintage-blind digit-string join poisoned 17+ codes across div 66. (b) The 68-division fan
  (2020-68111 → 7 children incl. BOTH halves of the pilot's 68112 collision: residential←68111,
  MICE→68124) is conductor-eye-verified on the BPS table — the collision factory. (c)
  Vision-read STRUCTURED labels (mapping_type) are soft — verdict bits + citations are the
  load-bearing signal; never use structured labels as concordance keys (L4 Appendix A meta-note).
  (d) The metadata-crosswalk disease also lives in the 1,336 "verified" OSS-native set
  (FATAL-4 candidate — Zero/Legge-5 product decision pending). (e) Innocence-control blindness
  took TWO generations to fix: prompt leak (#2776) then SCHEMA leak (#2778 symmetric pipeline,
  runner-side normalization) — third instance of the fix-begets-twin-bug family; controls from
  L1-L5 are all recorded as ANCHORED NON-BLIND FIXTURES. **True-blind era (L6-L7): the symmetric
  path ran live; 59140/59201 RETIRED after 4 reuses; from L7 every lot draws FRESH controls,
  burned after one use. The L7 fresh pair proved the policy's worth: 20232 (picked for expected
  cleanliness) itself carries a false MATCH_LANGSUNG, and 41013 asserts fiktif_positif with no
  citable provenance (correct fail-closed demote → drove contract refinement #2).**
- **Standing infra state:** Redis lease registry NOAUTH from sessions → LEASE-GUARD SKIPPED
  declared in every gate with compensating isolation. Local vault mirror on Pro
  (`~/nuzantara-vault`) serves dossier_pull without Mini. GLM seat: `claude --print` +
  `CLAUDE_CONFIG_DIR=~/.claude-glm` + keychain token, probe-first from staging BASE.
- **Standalone metadata cure-list BACKLOG (grows lot-by-lot, not yet a dedicated spec+PR — the
  only place this list is currently tracked; update here when it changes):** `01629` + `71204`
  (Lot 5 gate §m5-POS, 2026-07-19 — multi-parent crosswalk metadata false, evidence-gated) ·
  `59140` pp28-label (Lot 6 gate §3.4 — OSS-native, pp28_sources unverifiable, per_skala provenance
  sound by marker) · **`20232` (Lot 7 gate §3.4, 2026-07-19 — fresh SELECTED control, conductor-eye
  SPLIT on lampiran5_p156-156.png printed p.142: canonical `status_mapping='MATCH_LANGSUNG'`/"scope
  unchanged" refuted by two consecutive rows, 2025-20232 + 2025-20235; per rule #9 NOT detached in
  the Lot 7 cure — OSS-native, healthy per_skala).** All four are `metadata_only` candidates (same
  compiler action as 52101/46100/10433/`metadata_fixes_2026_07_19.json` — status_mapping/whatChanged/
  pp28_sources correction, per_skala untouched) pending a dedicated evidence-gated spec+PR; none has
  a canonical write yet.

**Governance flags:**

- **Filiera methodology**: panel CONCLUDED. Doc `research/operations/2026-07-16-kbli-filiera-methodology.md`
  (#2534 MERGED); execution program `research/operations/2026-07-16-kbli-garuda-filiera-workflow.md`
  (#2538 MERGED). **Phase GO is PER BATCH (Legge 5, Zero).** Pilot A1 (~the 8 above) done; the
  measured pilot report is the basis for the batch-A-remainder GO.
- **BKPM discrepancy findings stay INTERNAL** (Zero, 2026-07-16): the 68112 surat klarifikasi stays
  drafted in the drawer, not sent, without a fresh Zero GO.
- **PMA primary-verdict labeling — RULED (Zero, 2026-07-18, Legge 5):** the headline PMA verdict
  (hero PMABadge + verdict banner + Foreign-Ownership key-facts cells + OG status chip) STAYS a clean
  OPEN/RESTRICTED/CLOSED. The Perpres-10/49 vintage-2020 + crosswalk-pending status (FATAL-2 axis) is
  disclosed ONLY in the TRACK-P "Sources & Verification" panel (already live), NOT stamped on the
  headline verdict. Rationale: the PMA values are the in-force investment-list annexes (not the
  per_skala silent-fill disease), largely correct; the FATAL-2 per-code crosswalk refines the
  underlying values later. → the "PMA re-label" follow-up is CLOSED (ruled), not open — do not
  re-open without a fresh Zero GO.

- **data-plane guard LIVE** (#2550): only `scripts/kbli_filiera/` compilers may write the canonical
  KBLI dataset + `data/kbli-filiera/**`; interactive hand-edits BLOCKED. Registry
  `infra/claude-hooks/data-plane-registry.json` is the extension point. Kill switch
  `DATA_PLANE_GUARD_OFF=1`. (gold `kbli-gold-all.json` is NOT yet registered — editable, but pin
  every change with a regression test, cf. the 49213/50115 gold cure.)

**CHATKB cantiere `company-kbli-signed-lots` — 3-seat review (GLM+Claude+Codex), ARBITER-verified
(2026-07-19).** Dossier on M5:
`~/Desktop/CHATKB-CANTIERE-2026-07-19/company-kbli-signed-lots/{FINAL.md,gate-verdict.md,contested.md}`
(not shipped to `curated_qa` yet). **Established truth added to §2 below**: PP 28/2025
primary-verified via BPK registry `peraturan.bpk.go.id/Details/319773` ("Mencabut: PP No. 5 Tahun
2021") — the current in-force licensing instrument, GLM-live-checked. **Open follow-ups for this
corner (flagged only, nothing fixed here):**

1. **HIGH-PRIORITY unresolved**: 78109 and 80190 "TERBUKA 100%" ownership claims flagged against
   historical precedent (78xx labour-placement family; BUJP private-security regime) — two
   independent web passes found neither confirmation nor refutation. Needs a direct DPI-annex
   (Perpres 10/2021 jo. 49/2021 lampiran) read before either claim is committed client-facing.
2. **PROD self-contradiction risk**: live `inspect_kbli`/`chat_kbli` still serve the disproven
   contaminated payloads for 78109 (LPK-mixed, `risk_profile: "Menengah Tinggi"`, 16 license rows
   incl. the disproven LPK block) and 80190 (`risk_profile: "Tinggi"`) — KG/Qdrant resync pending.
   A live tool call mid-conversation can still contradict the cured dossier answer for either code.
3. **85321 crosswalk parent implausible**: the dossier's claimed true crosswalk parent {51108
   "Angkutan Udara Bukan Niaga" air-transport} is flagged implausible for a vocational-education
   code — re-check the BPS Vol.2 Lampiran 5 p.193 render. Confirmed separately: 85321's own title is
   "...Pemerintah" (government-operated type only); the private route is sibling code **85322**,
   whose ownership status is NOT yet verified.
4. **70100 ≠ passive holding**: the official OSS scope note for 70100 (Aktivitas Kantor Pusat)
   explicitly EXCLUDES passive holding-company activity → redirects to KBLI **64200**, whose
   ownership status is NOT yet verified.
5. **Q14/39001 provenance gap**: the dossier cites "BPS Vol.2 Lampiran 5 p.170, image-verified" for
   39001 with NO Lot number / workflow run-ID (every other code in this dossier cites one) — confirm
   the real Lot number for 39001 from `cure_specs`/workflow records before this row ships to
   `curated_qa`.

## 2. ESTABLISHED TRUTH (verified — do not re-litigate, do not re-derive)

1. **68112 = code-number collision** (image-verified 3× on official BPK PDFs): PP 28/2025 Lampiran
   I.L (Pariwisata) p.I.L.44 row 25 codes 68112 as "Penyewaan Venue MICE dan Event Khusus"; BPS
   7/2025 (KBLI 2025) reassigned 68112 to residential leasing. Residential in PP28 = **68111**
   (Lampiran I.H, PUPR). No residential 68112 exists anywhere in PP28's 21 lampiran.
2. **False friends confirmed beyond 68112**: 51103/51203 (space transport carrying KBLI-2020
   commercial-aviation licensing); 49213 (intra-city urban transport carrying the inter-city AKDP
   authority Gubernur, correct = Wali Kota/Bupati); 50115 (int'l sea tourism carrying the wrong AIR
   source 51107 which does not exist in PP28); 20111 (many-to-one merge single-source); 60312; 64310. High-concern suspects NOT yet adjudicated: 25200 (weapons/ammunition — dedicated
   regulatory review), 11× 47xxx retail family, 32114, 32906, 43216/43223. Sweep evidence:
   `research/operations/2026-07-16-kbli-false-friend-sweep.{md,json}`.
3. **~221 no-scope codes**: OSS ruang-lingkup 404 → their `per_skala` was silently filled from
   PP28/curatela, NOT OSS (`_l2_status: no_oss_risk`, `_l2_source: null`). Every one is
   false-friend-suspect until crosswalk-adjudicated.
4. **The official BPS conversion table (tabel kesesuaian KBLI 2020↔2025) EXISTS** — fetch fresh from
   bps.go.id (KBLI 2025 page; Codex red-team verified 2026-07-16). It is **one-to-many/many-to-one**:
   it narrows candidates but regulatory inheritance still needs per-activity adjudication (FATAL-1).
5. **The vintage defect is NOT only PP28**: Perpres 10/2021 + 49/2021 investment annexes are ALSO
   KBLI-2020-vintage → the whole `pma_status` layer needs the same cross-vintage treatment (FATAL-2).
6. **Permen BKPM 4/2021 is REVOKED** by Permen Investasi/Hilirisasi-BKPM 5/2025 (in force
   2025-10-02) → any Rp10bn-per-KBLI-per-location capital claims citing 4/2021 are stale-sourced
   (FATAL-3). Paid-up PMA = 2,5 mld under BKPM 5/2025; the >10 mld/KBLI/lokasi total is a SEPARATE
   rule; E28A 10 mld is an immigration rule — never sweep blindly on "10 miliar". Gold `baliContext`
   texts are at risk.
7. **OSS API 404 ≠ regulatory absence** (F12): could be changed UUID, lag, WAF, access control.
   `ABSENT` verdicts require corroboration (absence in PP28 lampiran verified on image, or crosswalk
   evidence). Wording for notes must say "no scope retrievable via OSS API (404), corroborated by
   <X>" — never bare "not published".
8. **KG diseases** (verified 2× on prod Postgres): perizinan nodes deduped BY NAME → 978 codes share
   ONE "NIB dan Sertifikat Standar" node whose kewajiban is agriculture text (852 edges); 187 agri-
   marked nodes reach ~1,065/1,568 codes. Router precedence bug: `props.get("uraian", description)`
   → properties.uraian wins; 930 codes drifted. The KG catalog has NO generator left in the repo
   (Fase 2 rebuilds it).
9. **Bali moratorium overlay (l4_bali)**: verdicts were derived from (possibly collision-derived)
   risk levels, and the Gubernur letter's binding legal effect is unproven (F15) — treat "blocked"
   as conservative posture, not certified fact; re-derive reasons when true risk is known.
10. **Gold/editorial layers bake upstream errors**: they keep asserting stale facts after the source
    is fixed, and don't name the marker (no "MICE" in the baked prose) — marker-based guards can't
    catch them. Re-grounding a source MUST emit an invalidation list of derived surfaces. **Gold
    takes precedence over intel_2026 for editorial fields on /kbli/<code>** (kbli-data.server.ts
    merges gold first; LicensingSection.tsx parses gold.whatYouNeed DIRECTLY) — so a canonical fix
    is invisible on a gold code until gold is cured too (49213/50115 lesson, 2026-07-17).
11. **PP 28/2025 is primary-source-verified as the current in-force licensing instrument**: BPK
    registry `peraturan.bpk.go.id/Details/319773` ("Mencabut: PP No. 5 Tahun 2021"), GLM-live-checked
    2026-07-19 during the CHATKB `company-kbli-signed-lots` 3-seat review. Supersedes any lingering
    "PP 28/2019" reference — the correct current-instrument citation for this corner.

## 3. ARTIFACTS & ACCESS (verified paths — check before use, cf. anti-hallucination)

- **Canonical dataset**: `data/source_documents/KBLI_2025_FINAL_CLEAN.json` (1,559 codes; tracked
  symlink `source_documents/` → same; mouth copy `apps/mouth/data/` kept byte-identical by
  `scripts/sync_kbli_dataset.sh` + CI `check-kbli-dataset-sync`; 2 gitignored RAG runtime copies
  rebuilt in-container). Sidecar sha: `apps/mouth/data/kbli-dataset-version.json`. Per-record
  provenance: `_source`, `_l1_source`, `_l2_source`/`_l2_status`, `pma_source`, `pp28_sources`,
  `l4_bali`, `intel_2026`, `_data_note`, `per_skala_disputed_*`. **WRITE ONLY via
  `scripts/kbli_filiera/` compilers** (data-plane guard #2550). Cure compiler:
  `scripts/kbli_filiera/cure_canonical_collisions.py` (spec-driven `cure_specs/fase1_collisions.json`;
  detaches per_skala AND honest-gaps intel_2026.whatYouNeed, idempotent; `--apply` syncs + bumps
  sidecar).
- **Gold layer**: `apps/mouth/data/kbli-gold-all.json` (428 records, keyed by code) — served by
  `apps/mouth/src/lib/kbli-data.server.ts`; remap table `scripts/kbli_gold_remap_table.json` (63
  phantom rows). NOT data-plane-guarded — edit value-in-place + pin with a regression test.
- **OSS RBA API** (public app credential, zero PII): host `gw.oss.go.id`, header
  `user_key: $OSS_RBA_USER_KEY` (static gov-app credential — value in memory
  `discovery_oss_rba_kbli_api_extraction_2026_06_19`). Endpoints: `/v2/portal/kbli?id_version=<uuid>`
  (list), `/v2/portal/kbli/{uuid}` (detail), `/v2/portal/kbli/ruang-lingkup/{uuid}` (risk rows; 404
  legit for no-scope), `/relasi/{uuid}`, `/umku/{uuid}`. KBLI-2025 version uuid:
  `fff4053d-cbb0-51e9-9dc5-1e85b5740704`. Code→uuid map:
  `data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json`. TRAP: urllib honors system proxy — use
  `ProxyHandler({})` or `curl --noproxy '*'`.
- **PP 28/2025 lampiran corpus**: peraturan.bpk.go.id Download ids **394930–394950** (21 files:
  Lampiran I.A–I.V by MINISTRY sector — letters ≠ KBLI category letters! — + II/III/IV; body PDF
  381375 has zero KBLI codes). **OCR TRAP: digit 1 renders as t/l/I ("68112"→"681t2") → `grep <code>`
  false-negatives. For any load-bearing digit: `pdftoppm -f <p> -l <p> -r 300 -png` + visual read.**
- **BPS crosswalk** (Fase 1 engine, F1): tabel konversi KBLI 2020↔2025, publication 2026-04-22 on
  bps.go.id — ingest fresh as a first-class dataset before the sweep.
- **Backend KG**: Postgres `kg_nodes` (`kbli:<code>`, `perizinan:<hash>`) + `kg_edges` (REQUIRES).
  Read-only: `scripts/pg.sh` / MCP `postgres-nuzantara` (combo `nuzantara_readonly`, proxy
  `127.0.0.1:15432`). Cure/resync scripts: `apps/backend-rag/backend/scripts/kg_kbli_license_fix.py`
  (dry-run default, `--apply` gated, `--only` mandatory, canonical-driven) + `kg_kbli_resync.py`.
- **Regression tests**: `scripts/tests/test_kbli_false_friend_registry.py` (all 8 codes: detach +
  audit + marker discipline + gold cure for 49213/50115; folds in the original 68112 test) +
  `scripts/kbli_filiera/tests/test_cure_canonical_collisions.py` (the whatYouNeed compiler). Extend
  the registry for every new false friend; never a bare-substring guard (scar #3: guilt+innocence
  corpus mandatory).
- **Filiera program state**: `data/kbli-filiera/` — dossier event-logs, quarantine ledger,
  `batch-reports/` signed reports (censuses, verdicts, IAA, gold-set hits).
- **Specs**: methodology `research/operations/2026-07-16-kbli-filiera-methodology.md` (#2534) ·
  execution/workflow `research/operations/2026-07-16-kbli-garuda-filiera-workflow.md` (#2538) ·
  "Operazione Garuda 1559" (GPT-5.6 Sol, 2026-07-14) — Garuda certifies internal consistency;
  Filiera adds external truth.

## 4. OPERATING RULES (blood-bought — violating these re-opens closed wounds)

1. **Vintage-aware identity**: `KBLI2020:X ≠ KBLI2025:X`. Any cross-vintage join goes through the
   BPS conversion table; bare-digit joins are forbidden (CI-lint). Applies to PP28 AND Perpres 10/49
   AND Kepmen 228/2019 TKA-categories AND any pre-2026 source.
2. **Crosswalk narrows, context adjudicates**: the citing entry's use-case decides, never
   title-similarity ("il contesto batte il titolo" — 63120→63900 lesson). Signature of a wrong
   remap: mapping_type=SPLIT applied as single code + boilerplate reasoning.
3. **Silence → corroborated abstention**: a 404/missing row is recorded as gap ONLY with a second
   independent signal; NEVER silently fill from another vintage/source (that silent fill IS the
   July disease).
4. **Detach > plausible remap**: "un phantom dichiarato è onesto, un rimappato sbagliato è una bugia
   in produzione."
5. **Digits from scans: image-verify** (pdftoppm 300dpi + eyes). pdftotext of BPK scans is evidence
   of TEXT, never of DIGITS.
6. **Consumer-map before scoping any data fix**: canonical → mouth `/kbli/<code>` SSR · **gold →
   same pages, and gold WINS over intel_2026** · KG/Qdrant → WA/webchat via `inspect_kbli` ·
   **`kbli_documents` (Postgres) → `chat_kbli` LLM context via
   `_fetch_parent_documents_from_kbli_table()` + direct 5-digit lookup
   (`apps/backend-rag/backend/app/routers/kbli_notebook_chat.py:635,699`) — the 4th surface,
   cured by `kbli_documents_cure.py` (#2796, 2026-07-19) — and **RECONCILED 2026-07-24: all 217
   canonical-detached codes now serve 0 licensing rows here (was 18 leaking, see LIVE STATE)**;
   whole-table builder still missing (PENDING-ARMS)** · intel_2026/editorial → baked prose · `apps/kbli-navigator`
   app (knowledge.balizero.com — Next.js, NOT a native desktop app, see LIVE STATE) → its own
   `data/kbli-2025.json` fork AND its own `lib/kbli-gold-content.ts` override layer (**both CURED
   on main, re-verified 2026-07-24 — still consumers to check on every future cure, but not open
   work items**) · NB sources. Fix the class across ALL consumers or explicitly
   park the rest; "merged" ≠ "live" ≠ "every surface".
7. **Derived layers need invalidation**: after correcting any source fact, list which derived fields
   (gold whatYouNeed, editorial, l4_bali reason, KG properties, NB) were generated FROM it and
   schedule them; guards on markers won't catch baked prose.
8. **False-friend fix pattern** (use as-is): `per_skala` → `[]` + preserve old block under
   `per_skala_disputed_<source>` + `_data_note` with corroborated wording + honest-gap
   intel_2026.whatYouNeed (+ gold whatYouNeed if the code is in gold) + entry in the registry test +
   innocence controls (legit neighbor codes with similar markers must not be touched).
9. **No new licensing values without provenance**: never author risk/license/authority values from
   plausibility — either a sourced row (locator+vintage) or an honest "not yet defined". Client-facing
   honest-gap prose gets a Codex cross-family gate (generator≠grader) before ship.
10. **Ship-lifecycle**: per CLAUDE.md §2 — the session reviews, merges, arms, deploys, proves live.
    Sensitive data raises the adversarial gate, never parks the merge on a human. GO is per-batch
    (Legge 5) for the sweep; the ship of an already-GO'd batch is fully the session's.

## 5. THE PLAN — GARUDA-FILIERA roadmap to the end

> Garuda certifies INTERNAL consistency (the 1,559 agree with each other); Filiera adds EXTERNAL
> truth (each fact traces to a dated government source through the correct vintage). The end-state:
> every rendered fact is government-sourced-with-locator OR an honest declared gap. Discrepancy
> findings against BKPM/OSS stay INTERNAL (product feature: "we show the divergence with citations").

### Seats (execution program, workflow doc §2) — family-independent by design

- **Mente immobile / final gate**: **Fable 5** (max effort, interactive) — batch plans + acceptance
  criteria, quarantine adjudication, the final EMPIRICAL gate against raw vault evidence, sign-off.
  Never extracts, never writes data. Window dead → program SUSPENDS at a batch boundary (durable
  state carries; no weaker substitute for the final gate).
- **Extractor**: **Sonnet 5** (implementer tier) — reads located rows, writes candidate facts.
- **Vision locator**: **qwen2.5vl:7b** (Ollama on Mini) — page/row triage on 300-dpi renders,
  LOCATOR ONLY, never the reader.
- **Red-team**: **Codex GPT-5.6-sol** (xhigh, read-only sandbox) — attacks mapping proposals + batch
  reports. Family-independence: extractor ≠ refuter ≠ red-team FAMILIES per batch.
- **Operator**: **Zero** (Legge 5) — batch GO, publish decisions, consents.

### Per-code scientific protocol — dossier D0→D6 (workflow doc §3)

Each batch pins a vault-manifest revision; per-code lease `agent_lock:kbli-dossier:<code>`.

- **D0 Evidence pull** (deterministic): vault items for the code — BPS row, dated OSS snapshot, PP28
  lampiran rows. Endpoint inventories + negative controls so ABSENT is corroborated, not assumed.
- **D1 Crosswalk adjudication**: NO deterministic acceptance, not even 1-to-1 (uraian-equivalence
  check) — the 2020 ancestor is a candidate, the use-case adjudicates.
- **D2 Extraction** (image-verified, self-confirming): qwen2.5vl locates the row → Sonnet reads it;
  self-confirming to resist locator poisoning.
- **D3 Assembly** (deterministic): strict schema, per-fact provenance (locator + vintage) + confidence.
- **D4 Discrepancy & completeness scan**: cross-layer comparison; completeness invariants catch
  omission blindness.
- **D5 Independent verification** (anti-correlation): the refuter does BLIND re-extraction, does not
  grade its own work; divergence → quarantine. Inter-extractor agreement tracked per batch.
- **D6 Batch gate**: deterministic censuses + gates G13–G17 → **Fable final empirical gate** (§ sampling)
  against RAW vault evidence, never seat summaries → sign-off → compiler emits canonical vNext.

### Batches (risk classes, live enumeration 2026-07-16 — sizes may overlap across criteria)

| Batch | Set                                                                                      | Size      | Regime                        |
| ----- | ---------------------------------------------------------------------------------------- | --------- | ----------------------------- |
| **A** | PP28-derived licensing, no OSS source (the ~no-scope heart; includes the 68112 siblings) | **119**   | **100% Fable review**         |
| **B** | Cross-code stitches (`pp28_sources` → other codes)                                       | **478**   | AQL tightened start; D1-heavy |
| **C** | (taxonomy remainder)                                                                     | **~1263** | AQL adaptive                  |
| **D** | (residual class)                                                                         | **~175**  | AQL adaptive                  |

Processed in taxonomy order. Sampling = ISO-2859-spirit AQL (start tightened, loosen only on a
clean run of batches), NOT naive 10%/min-12 (red-team F6). No throughput promises before measurement.

**Batch B design SIGNED 2026-07-19** (REV-4b, `research/operations/2026-07-19-kbli-batch-b-design.md`,
#2801 merged) — pre-registration determinism gate closed after 4 Codex xhigh rounds + Gemini.
Phase-0 parser gate PASSED + full-corpus BPS crosswalk relation shipped (PR #3083, 2026-07-24).
Remaining gates before any lot: `populate_bps_ancestors.py` canonical-write compiler (not built),
Tier-4 population count + AQL parameters (not computed), Zero's Legge-5 ratifications (AQL default,
Tier-4 volume — pending those numbers), 5 fresh POS controls (not started). See LIVE STATE.

### The four phases (methodology doc §rollout)

- **Phase 0 — Garuda lands** (internal consistency; BE1/BE2 recertify). Cross-vintage rows flagged
  "regulatory basis pending crosswalk audit" until Phase 1 clears them. → substantially DONE.
- **Phase 1 — Collision sweep** (bounded, deterministic): ingest the BPS conversion table; run D0–D6
  over Batches A→D; re-derive every no-scope / cross-vintage row via its correct 2020 ancestor or
  detach-to-honest-gap; re-adjudicate the 63 phantom gold-remap rows through the same machinery;
  extend the cross-vintage treatment to the `pma_status` layer (FATAL-2). Output: **zero unaudited
  cross-vintage rows in the catalog.** → **pilot A1 (the 8 codes) DONE & proven-live; Batch A
  remainder (~111) + B/C/D REMAIN** (each is a per-batch Zero GO).
- **Phase 2 — Reproducible compilers**: a canonical builder (vault + curatela → canonical vNext,
  deterministic, re-runnable) + a per-code **KG regenerator** that fixes the 68% dedup disease AT THE
  ROOT (the KG catalog currently has no generator — spot-deleting edges is not the cure). G16 live.
- **Phase 3 — Refresh loop**: OSS re-snapshot cron (Mini, rate-budgeted) + JDIH/ministry watchers
  integrated with regulatory-watcher; the **221 no-scope watchlist** (when OSS publishes a scope, it
  triggers re-adjudication); deltas feed the same queue. Keeps the navigator true over time.

### Definition of DONE (the whole navigator validated)

Every one of the 1,559 codes: risk / licensing / PMA / Bali facts each carry a government locator +
vintage OR an honest declared gap; zero silent cross-vintage fill; KG regenerated from a real
generator; gold/editorial invalidated-and-rebuilt where their source changed; a running refresh loop.

### Immediate next actions (when the current ship lands)

1. Finish the 8-code ship: push → PR → `--auto --squash` → merge → Vercel → PROVE-LIVE
   `curl /kbli/{51103,49213,50115,64310,20111,51203,60312}` shows honest-gap.
2. ALIGN-FLEET: rebuild the native `kbli-navigator` desktop app (M5/Pro/Mini) off the new canonical.
3. Write the pilot-A1 measured report (IAA, discrepancy census, cost) → basis for the Batch-A GO.
4. On Zero's Batch-A GO: ingest the BPS crosswalk, stand up the D0–D6 dossier machinery, run the
   119 Batch-A codes at 100% Fable review.

## 6. WHO IS WHERE / MEMORY POINTERS

- Sessions are ephemeral; the durable state is on disk (this file + `data/kbli-filiera/` + the memory
  files below). A Codex red-team seat is on-demand: give it THIS file + the artifact under review.
- **Deep-dive memories**: `ops_kbli_fase1_cure_applied_residual_risk_editorial_2026_07_17` (the 8-code
  cure state, all layers) · `discovery_kbli_49213_akdp_collision_pilot_a1_2026_07_17` (pilot A1) ·
  `discovery_kbli_68112_code_collision_pp28_vs_bps_2026_07_16` ·
  `discovery_kbli_noscope_codes_per_skala_not_from_oss_2026_07_16` ·
  `discovery_kg_perizinan_name_dedup_disease_2026_07_16` ·
  `lesson_kbli_remap_gate_context_beats_title_2026_07_16` ·
  `feedback_merged_is_not_live_consumer_map_first_2026_07_16` ·
  `discovery_oss_rba_kbli_api_extraction_2026_06_19` ·
  `feedback_session_owns_full_ship_lifecycle_2026_07_16` · `fact_bkpm_5_2025_paidup_capital_2_5_mld_2026_07_16`.
