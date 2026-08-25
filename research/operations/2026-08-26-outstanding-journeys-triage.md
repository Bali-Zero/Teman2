---
date: 2026-08-26
domain: operations
client_case: none
adversarial_review: kimi
sources:
  - kb/journeys/{immigration,company,tax,property}.yaml (origin/feature/kb-current @ 9cb41f45a)
  - kb/inventory/{immigration,company,tax,property}.yaml (same ref)
  - kb/ops/probe_retrieval.py (read-only, re-run against production 2026-08-26 — not modified)
  - scripts/kb/kb_inventory_probe.py (read-only, method reused for the census pattern — not modified)
  - /tmp/triage_scan.py, /tmp/triage_scan2.py (this session's own read-only verification scripts, not committed)
  - team-lead's isolated-overlay expansion re-measurement (2026-08-26, verbal report via teammate message — google-genai==2.18.1 pip-installed --target, PYTHONPATH-prepended for the probe process only, shared venv unmodified)
  - team-lead's `scripts/ci/legal_status_read_lint.py` AST read/write-site census (2026-08-26, verbal report — 0 reads of `legal_status` outside diagnostics, scope apps/+scripts/+kb/)
  - apps/backend-rag/backend/services/search/{search_filters,search_service}.py, apps/backend-rag/backend/services/ingestion/ingestion_service.py (read-only, this session — traced the one live exclusion filter to `status_vigensi`, a different field, and confirmed it 0/84,283-populated on legal_unified)
  - production Qdrant `legal_unified_hybrid_hybrid` (84,283 points, single full scroll, 2026-08-26)
  - team-lead's own read-only same-value measurement on J4 (2026-08-26, verbal report — `legal_status` absent from both documents' embedded text; identical `dicabut` value on winner and loser, 402/402 vs 340/340), independently reproduced this session (/tmp/j4investigate/measure1_same_field.py)
  - team-lead's own corpus-wide `legal_status` ground-truth measurement (2026-08-26, verbal report — 9 documents with independently known status, 7 contradicted by their own marking, including two self-consistent proofs needing no external source: `UU_63_2024` titled "PERUBAHAN KETIGA ATAS UU NOMOR 6 TAHUN 2011" yet marked `berlaku` while `UU_6_2011` itself is marked `dicabut`; `Permen_11_2024` titled as amending `Permen_22_2023`) — primary source for the corpus-wide verdict below; this session's own aggregate scroll (/tmp/j4investigate/aggregate_and_perdoc.py, same 84,283-point totals) is corroboration only
  - apps/backend-rag/backend/core/legal/constants.py (read-only, this session — `STATUS_PATTERNS` comment block confirms the write-side mechanism is RETIRED as of 2026-08-25, Lane P kb-p2-status-retire-0825, already merged to `feature/kb-current`)
  - team-lead's `git log -L` verification on `kb/journeys/company.yaml`'s company-J7 line (2026-08-26, verbal report — the line was born correct in the original lane-B commit `6ba56e9ab` and was never edited) and their probe-matcher sweep of all 41 `verbatim_phrase` journeys (2026-08-26, verbal report — only 4 phrases genuinely absent anywhere: immigration-J2/J8, tax-J5/J8)
  - kb/ops/probe_retrieval.py's `normalize()` function, imported directly (not reimplemented) this session to independently re-check company-J7 (/tmp/j4investigate/verify_companyj7.py) — reproduces the team lead's single-hit finding exactly, point `004ac9d4-262b-503e-939c-8f3d6f7d27e0`
  - adversarial review by `kimi` (Kimi K3, 2026-08-26) against this file and the companion WIZ-1
    document — 9 findings (C1-C9 across both files), all independently re-verified this session
    before any correction was applied; see "Adversarial review" section below
  - apps/backend-rag/backend/services/search/search_service.py:520-580 (read-only, this session —
    verified `apply_filters=False` rebuilds the filter with `exclude_repealed=False`, correcting
    this file's own earlier "regardless of `apply_filters`" claim, C2 below)
  - `/tmp/c3_measure.py` (this session, not committed) — direct Qdrant retrieval of both
    company-J7's point (`004ac9d4-262b-503e-939c-8f3d6f7d27e0`) and company-J9's point
    (`0027f82d-347e-5e83-8371-ee48564649d3`), cross-checked with `kb.ops.probe_retrieval.normalize`
    (imported, not reimplemented) — resolves the C3 contradiction the reviewer flagged: they are two
    different points, each carrying only its own journey's phrase
  - `/tmp/c4_measure.py` (this session, not committed) — direct Qdrant point-count of
    `Permen_22_2023` (402), `Permen_29_2021` (340), `Permen_11_2024` (345) — the reviewer's C4
    finding ("340 vs 345 for the same document") does not hold: these are three different
    documents, each count independently correct; no fix applied
---

# Outstanding-journeys triage — 24 reds, classified and costed, zero writes

> TRIAGE ONLY. No collection was written to. No `kb/journeys/*.yaml` or `kb/inventory/*.yaml` file
> was edited. `kb/ops/probe_retrieval.py`, `kb/ops/probe_history.py`,
> `scripts/ci/legal_status_read_lint.py`, `scripts/kb/kb_inventory_probe.py`,
> `backend/core/legal/*`, and both `test_kb_*_contract.py` files were read, never touched.

## Method

1. Re-ran `apps/backend-rag/.venv/bin/python kb/ops/probe_retrieval.py kb/journeys/<topic>.yaml --json`
   for all four topics against production, today. **Zero drift**: every recorded `probe_state`
   matched the fresh measurement, exit code 2 (OUTSTANDING) on all four files, confirming the
   24-red count in the mandate (5+9+7+3) is current, not stale.
2. Confirmed the degraded-path venv is unchanged and did not touch it: `google-genai` installed
   `1.75.0` vs repo lock `2.18.1`; `qdrant-client` installed `1.13.3`, whose own compatibility
   warning reports the live server at `1.16.3`, while the repo lock pins `1.19.0` — a three-way
   version spread (installed / server-reports / repo-pins-for-next-upgrade), not the two-way one
   the mandate text stated. Multilingual query expansion is confirmed still broken (same
   `TypeError: 'async for' requires an object with __aiter__ method` on every run).
3. Wrote one standalone, read-only script (`/tmp/triage_scan.py`, never committed) that opens a
   **single full scroll** of `legal_unified_hybrid_hybrid` (84,283 points, confirmed by count) and,
   for each of the 24 outstanding journeys' `(instrument_id, verbatim_phrase)` pairs, checks in one
   pass: (a) total point count under that instrument_id — reading `document_id` (top-level) OR
   `metadata.document_id` (nested), i.e. methods 1+2 of the mandate's three-method absence proof,
   combined the same way `chunk_instrument()` in `probe_retrieval.py` already does it; (b) whether
   the normalized phrase appears **anywhere in the whole collection**, under which document_id(s) —
   method 3, content search, done once for all 24 phrases rather than 24 separate scrolls.
4. One follow-up targeted script (`/tmp/triage_scan2.py`) for a single row (company-J7) where the
   full-scan result needed a closer read to explain, below. **This script's own needle-splitting
   was the source of a wrong conclusion, corrected 2026-08-26 by the team lead — see the
   "Matcher methodology correction" section below.**
5. **The degraded-path caveat below was retracted the same day, by measurement, not argument.**
   The team lead ran the pinned `google-genai==2.18.1` in an **isolated overlay**
   (`pip install --target`, prepended to `PYTHONPATH` for the probe's process only) rather than
   touching the shared venv this and other lanes were measuring against concurrently — verified
   afterward that the shared venv stayed at `1.75.0`. Result, compared by **journey index**, not
   just cardinality (two different index sets can share a count, which would have read as
   "identical" falsely):

   | topic | degraded | with overlay (no DEGRADED banner) |
   |---|---|---|
   | immigration | 5 of 11 | 5 of 11 — same indices |
   | company | 9 of 11 | 9 of 11 — same indices |
   | property | 3 of 9 | 3 of 9 — same indices |
   | tax | 7 of 10 | 7 of 10 — same indices |

   **No red in this table is a false negative produced by the restricted/expansion-broken search
   path.** The venv itself is still mispinned (a standing ledger item — every run without the
   overlay is degraded again), but that no longer qualifies any of the 24 verdicts below. Per-row
   "would this hold under expansion" hedging is therefore removed from the table; see the closing
   note in place of the old per-class breakdown.

Full raw output of both scripts is not reproduced verbatim here for space; the specific hits cited
per row below are real point IDs from that scan, quotable on request.

## The table

Legend — **Classe**: A=strumento assente · B=presente ma non recuperato · C=identità sbagliata ·
D=canary violato · E=percorso sbagliato. **Scrittura?**: whether the proposed cura requires a
production write (Qdrant upsert/payload-patch) or not.

| Topic | # | instrument_id | Classe | Prova (comando/risultato reale) | Cura proposta | Scrittura? |
|---|---|---|---|---|---|---|
| immigration | 3 | Permen_22_2023 | **B** | Full scroll: phrase found, attributed to `Permen_22_2023` (point `013faf15-…`). `kb/inventory/immigration.yaml` independently scanned all 402 points and confirms Golden Visa provisions present verbatim. Reworded from official term → colloquial "KITAS" and re-run twice; stably red both times, not a boundary flicker. | Retrieval ranking (penjelasan/competing-article weighting or a de-dup pass) — not an ingest gap. | No |
| immigration | 4 | Permen_29_2021 (canary, target Permen_22_2023) | **D** | `kb/ops/probe_retrieval.py`: measured GREEN, rank 3 — the **revoked** Permen_29_2021 text outranks the current Permen_22_2023 for a live ITAS-duration question. **CORRECTED 2026-08-26, after the team lead's own read-only lint contradicted my first write-up — re-verified, they are right, I was wrong.** `LANE-A-1`'s framing ("this is exactly Decision 5's concern") led me to state `legal_status` as the *cause* of the ranking; that is a correlation, not a proven mechanism, and it does not survive an actual causal check. Verified myself, independently, in two ways: (1) full-repo grep + the team lead's AST lint (`legal_status_read_lint.py`, scope widened to `apps/`/`scripts/`/`kb/`) — the only reads of `legal_status` anywhere outside tests are in diagnostic/repair scripts (`kb/ops/probe_history.py`, `scripts/kb/{audit,probe_legal_status_marking,propose_legal_status_repair}.py`, `scripts/ci/legal_status_read_lint.py`) and the ingestion writer itself (`metadata_extractor.py`) — **zero** reads in `backend/services/search/` or `backend/services/rag/`. (2) The **one** live exclusion filter that IS wired into every `SearchService.search()` call whenever `apply_filters` is `None` (the default) or `True` (`_prepare_search_context` builds `chroma_filter` with `exclude_repealed=True` by default — the docstring claiming "filters disabled by default" is itself wrong, but that is a separate, smaller bug) is `build_search_filter()` in `search_filters.py:12/28/55-86`, and it excludes `status_vigensi == "dicabut"`. **CORRECTED 2026-08-26**: this row originally said the filter is wired in "regardless of `apply_filters`" — that is false. Verified at `search_service.py:554-564`: `apply_filters=False` rebuilds `chroma_filter` with `exclude_repealed=False` (keeping only `exclude_historical=True`), so an internal caller that explicitly disables filters genuinely disables this one too. This does not change the conclusion below — every external query takes the default/unset path, and that path IS unconditionally gated on this filter — a **different field name** than `legal_status`. A fresh full-collection scroll (84,283 points, this session) found `status_vigensi` on **0** points, top-level or nested, anywhere in `legal_unified` — it is written only by the unrelated general-book ingestion path (`services/ingestion/ingestion_service.py`, distinct from `legal_ingestion_service.py`), never by the legal pipeline. So the code's only live filter is permanently a no-op for this collection, for a reason that has nothing to do with `legal_status`'s wrong marking. **`legal_status` is inert. My root-cause claim was wrong.** The actual cause of Permen_29_2021 outranking Permen_22_2023 here is **not established** — a plausible, unverified hypothesis is plain lexical/semantic relevance (Permen_29_2021's indexed chunk states a duration figure directly; Permen_22_2023's competing chunk for this exact question is a definitional clause) — but this is a hypothesis, not a measurement, and no further investigation was done here. **STRENGTHENED 2026-08-26** — the team lead ran their own read-only measurement rather than wait for a file:line rebuttal, and it closes the question harder than the argument above: on a real chunk from each document, `legal_status` is **absent from the embedded text itself** (so it cannot be shaping the vector either — closes option (b) of the team lead's original three-way question), and — the fact that actually decides this — **the field carries the identical value on both sides**: `Permen_22_2023` 402/402 `dicabut`, `Permen_29_2021` 340/340 `dicabut` (independently reproduced this session, `/tmp/j4investigate/measure1_same_field.py`, same full-scroll method). A field with the same value on the winner and the loser cannot be what orders one above the other, regardless of whether anything ever reads it — this is now a stronger claim than "inert," it's "constant, hence uninformative." Direct consequence for the repair: patching only `Permen_22_2023` to `berlaku` leaves `Permen_29_2021` at `dicabut` unchanged and is *provably* incapable of moving this ranking; the only repair shape that could even in principle touch it — also flipping `Permen_29_2021` — has never been proposed and is not authorized on this basis (`Permen_29_2021` genuinely is superseded; there is no ground-truth source to flip it to). | **Retracted.** `scripts/kb/propose_legal_status_repair.py` would not change what this journey measures — confirmed, not merely doubted, since the field it patches is never read at query time. Do not run it to "fix" J4. It may still be worth doing as an independent DATA-QUALITY correction (1,484 points are simply mismarked, and a naming-mismatch dead filter is itself worth a ticket so nobody assumes `exclude_repealed` protects anything today), but that is decoupled from this canary. J4's actual cure needs its actual cause found first — not scoped in this triage. | **No** — not for this defect. (The metadata patch is a separate, smaller, still-valid data-quality fix with no bearing on retrieval.) |
| immigration | 5 | UU_6_2011 | **B** | Full scroll: phrase found, attributed to `UU_6_2011` (point `00aa451d-…`). Journey's own note: phrase is in a `section: penjelasan` chunk (commentary), not the operative Pasal — plausible cause is a penjelasan chunk out-competing denser operative text for this question's embedding. | Re-rank weighting / a penjelasan de-boost — not an ingest gap. | No |
| immigration | 6 | UU_63_2024 | **B** | Full scroll: phrase found, attributed to `UU_63_2024` (2 hits, both correctly attributed). `LANE-A-4`: the instrument's 38 points are split across **two unreconciled ingestion generations** (10 `modern_id_only` + 28 `legacy_metadata_text`) for the same 10-article law, plausibly under-competing against `UU_6_2011`'s 413 points for a general re-entry question. History: flaky red/green at the rank-10 boundary under the *original* official-terminology wording; **stably red** across 3 runs after rewording to colloquial "KITAS" phrasing. | Reconcile the two ingestion generations into one (a re-ingest/consolidation), which is more than a pure ranking tweak — this is a write, unlike the other B rows in this table. | **Yes** (reconciliation write), unlike most B rows here |
| immigration | 10 | Permen_22_2023 | **B** | Full scroll: phrase found under **both** `Permen_22_2023` and `Permen_11_2024` (3 hits total). `LANE-A-6` confirms the Pasal 185/186 "lanjut usia" (60+) clause is genuinely present by direct scroll — but a targeted search of all 402+345 points for `hak pakai`/`deposit`/`deposito` found **zero** hits either. Measured red 3 stable runs. | Two separate needs bundled in one journey: (1) ranking — the visa-eligibility half alone doesn't even clear top-10; (2) a genuine content gap on the property-tenure half (`hak pakai`), which is Lane D's domain per `LANE-A-6`, not a ranking fix. | No for (1); the (2) half needs Lane D content that may not exist anywhere yet — not scoped here |
| company | 1 | UU_40_2007 | **B** | Full scroll: phrase found, attributed to `UU_40_2007` (point `06bebfd9-…`), the already-repaired 379-point clean edition. | Ranking (a merger/acquisition/spin-off provision competing poorly against a client-phrased English paraphrase of an Indonesian statute). | No |
| company | 2 | PP_7_2025 | **B** | Full scroll: phrase found, attributed to `PP_7_2025` (point `049a486c-…`). KBLI 2025 (3,522 points, clean of §6 signal). | Ranking — a KBLI classification description competing poorly against a client paraphrase. | No |
| company | 3 | PP_7_2025 | **B** | Full scroll: phrase found, attributed to `PP_7_2025`, **the same point id** (`049a486c-…`) as journey 2 — the two journeys' phrases are the code title and the code description of the *same* KBLI entry. | Same as journey 2 — likely the same ranking fix resolves (or fails) both together. | No |
| company | 5 | UU_49_2021 | **B** | Full scroll: phrase found under **both** `UU_49_2021` (correct) and `UU_6_2023` (the Cipta Kerja omnibus, 4,685 pts — the single largest document in the whole collection per `LANE-A-1`'s corpus-wide scale note). The much larger omnibus document is the more likely rank competitor. | Ranking / per-document score normalization (a 4,685-pt document structurally dominates a 4-pt one on any naive score). | No |
| company | 6 | UU_25_2007 | **B**, corrected from an initial read of A | Full scroll: phrase **found**, attributed to `UU_25_2007` (point `9a76e89e-…`). `uu_25_2007_fragment_categorisation` in the inventory documents this instrument as 0/65 *operative*-article points (100% Penjelasan/boilerplate) — but this specific journey is explicitly the **"HOLLOW-INSTRUMENT diagnostic"**: its own note says a green here "does not mean the instrument is whole," i.e. the phrase living in Penjelasan narrative prose is the *expected*, already-anticipated shape of a positive hit. My independent re-scan confirms the phrase is genuinely there, correctly attributed — it simply isn't ranking top-10. | Ranking. Separately (already tracked, not re-derived here): the instrument itself needs its operative body ingested — `disposition` in `company.yaml` already stops this at "step 1 of 3" (containment proved, not yet re-ingested) — but that's a different, already-known, already-out-of-band unit of work, not what THIS journey's red is diagnosing. | No (for this journey's own red) |
| company | 7 | Permen_5_2025 | **B** | **CORRECTED 2026-08-26 — the team lead checked this row and it did not hold; independently re-verified, they are right.** `kb/journeys/company.yaml`'s `verbatim_phrase` **does** include "Berusaha" (re-read fresh: `"sebagai dasar pemrosesan Perizinan Berusaha Berba sis Risiko sesuai ketentuan peraturan perundang-undangan"`; the team lead confirmed via `git log -L` on the original lane-B commit that the line was born this way and was never edited). My original claim that the journey silently dropped the word was a transcription error on **my own side**, made when I copied the phrase into an ad-hoc follow-up script — not a defect in the yaml. The real mechanism: the corpus text carries a newline mid-phrase (`"...Berba sis Risiko sesuai \nketentuan..."`), which `kb/ops/probe_retrieval.py`'s own `normalize()` (whitespace-collapse + lowercase) already handles and my ad-hoc needle-splitting did not. Independently reproduced this session by **importing that exact function** (`from kb.ops.probe_retrieval import normalize`, not reimplementing it) and re-scanning all 4,722 `Permen_5_2025` points: **1 exact normalized match**, point `004ac9d4-262b-503e-939c-8f3d6f7d27e0`, under the correct claimed instrument. This is a genuine retrieval miss — one point out of 84,283 doesn't rank for this cross-topic (KKPR-zoning × OSS-licensing), Spanish-language, client-phrased question — not a malformed journey. Retract the earlier "can never match regardless of retrieval quality" claim; it is false. | Ranking (a single low-density point competing for a compound zoning×licensing question is a classic long-tail retrieval miss, not an ingest gap). | No |
| company | 8 | UU_40_2007 | **B** | Full scroll: phrase found, attributed to `UU_40_2007` (point `007182fc-…`). | Ranking. | No |
| company | 9 | Permen_5_2025 | **B** | Full scroll: phrase found, attributed to `Permen_5_2025` (point `0027f82d-347e-5e83-8371-ee48564649d3`). **CORRECTED 2026-08-26** — this row previously claimed 0027f82d was "the same physical point that also carries journey 7's 'Berbasis Risiko' boilerplate"; that contradicted company-J7's own row above (which found exactly **1** normalized match for J7's phrase, at a different point, `004ac9d4-262b-503e-939c-8f3d6f7d27e0`) and did not survive a direct measurement. Retrieved both points from production and cross-checked with `kb.ops.probe_retrieval.normalize` (imported, not reimplemented): `0027f82d`'s text is a distinct chunk (`KETUJUH : Fasilitas Pajak Penghasilan sebagaimana dimaksud...`) containing J9's own phrase and **not** J7's; `004ac9d4`'s text contains J7's phrase and **not** J9's. They are two different points in the same 4,722-point `Permen_5_2025` instrument, each correctly matching only its own journey's phrase — real, present regulation text either way, just not ranking for the cross-topic B×C paraphrase. J7's "1 exact normalized match" claim stands unaffected; this is a second, independent match, not the same point. | Ranking (cross-topic compound question competing against single-topic phrasing). | No |
| company | 11 | PP_28_2025 | **B** | Full scroll: phrase found, attributed to `PP_28_2025` (point `0189c802-…`), one of the 855 points NOT flagged by the §6 damage signal (32/887 are). | Ranking. | No |
| tax | 2 | PP_8_1983 | **E** | Phrase found, attributed to `PP_8_1983` (confirmed, plus a second hit under `UU_8_1983`). The journey's own note calls the measured RED **"good news"** — surfacing this stale 10% rate would be a Decision-5 violation (superseded content answering as current), exactly the shape immigration's canaries exist to catch. But this journey's `expectation:` field is `retrieves`, not `must_not_retrieve` — so the schema's own `journey_satisfaction()` marks it **unsatisfied** for behaving safely, and a "fix" that made it rank higher would make the corpus *worse*, not better. The journey's contract is inverted relative to its own documented intent. **CONFIRMED 2026-08-26 — the team lead reviewed this call independently and it holds**, and adds the consequence I hadn't spelled out: correcting `expectation` to `must_not_retrieve` does **not** remove this red — the phrase is found (2 hits), so under `must_not_retrieve` semantics `journey_satisfaction()` still marks it unsatisfied, and it stays exactly as red as today. What changes is the *meaning*: today it silently reads as "retrieval failed to surface something useful" (a ranking-improvement target); corrected, it reads as "the corpus surfaces a superseded rate for a live-rate question" — a canary correctly firing on real poison. The second is the true, and worse, state of the corpus, and should be stated rather than left for whoever fixes the field to discover on their own. | None on the corpus. Correct the journey: either flip `expectation` to `must_not_retrieve` (making it an explicit canary, like immigration J2/J4/J8 — this keeps the row red, by design, with the corrected meaning above), or retire it in favour of tax-J8 (`UU_7_2021`/HPP), which already tests the thing that actually needs fixing — the *correct* current rate being retrievable. | No — journey-file correction only |
| tax | 5 | KEP_55_PJ_2026 | **A** | `instrument_counts["KEP_55_PJ_2026"] = 0`; phrase not found anywhere in 84,283 points. Matches `kb/inventory/tax.yaml`'s own 3-method confirmation (document_id 0 hits, metadata.document_id 0 hits, cross-check against the retired `legal_unified_2026` collection: 21/21 chunks exist there under book_title "Keputusan Direktur Jenderal Pajak Nomor KEP-55/PJ/2026", never promoted). My independent full-collection content scan is a 4th, convergent method. | Acquire/ingest this DJP Kepdirjen instrument (or promote+relabel the 21 already-known chunks from `legal_unified_2026`, which exist under a `TAX_UNKNOWN_UNKNOWN` id there and would need identity repair, not fresh acquisition). | **Yes** |
| tax | 6 | UU_36_2008 | **B** | Full scroll: phrase found, attributed to `UU_36_2008` (correct), **also** under `TASSE_7_1983` and `UU_6_2023` — three editions/citations of the same evolving PPh-subject provision. Journey's own note: manual top-10 inspection shows `TASSE_7_1983` and `Permen_1_2026` (the 1,506-pt contaminated document, `LANE-A-1`/out-of-scope finding) dominating instead — a genuine ranking miss, not an ingestion gap. | Ranking / possibly de-weighting `Permen_1_2026`'s outsized, partly-contaminated footprint generally (it is independently flagged in `company.yaml`'s out-of-scope findings as a 7-8-way ministry collision). | No |
| tax | 7 | PER_7_PJ_2025 | **A** | `instrument_counts["PER_7_PJ_2025"] = 0`. Phrase **is** found elsewhere in the corpus — under `Permen_81_2024` (the Coretax base reg, in-scope and green on J3) and `UU_7_1945` (the garbled-identity HPP fragment `TAXC-5` already documents) — but never under the journey's actual target, `PER_7_PJ_2025` (the specific implementing DJP regulation), confirmed absent by 4 independent methods in `kb/inventory/tax.yaml` (id variants, the retracted `Permen_32_2022` lead, category scan, WebSearch). The underlying *legal fact* (NIK=NPWP) is answerable from Permen_81_2024/UU_7_1945; this specific *instrument* is not in the KB under any identity. | Acquire PER-7/PJ/2025 specifically — the general fact is already present elsewhere, but this journey is deliberately scoped to the implementing regulation itself (the journey file says so explicitly), so a broader-instrument workaround is not what was asked for. | **Yes** |
| tax | 8 | UU_7_2021 (HPP) | **A** | `instrument_counts["UU_7_2021"] = 0`; phrase (the 11%-VAT-rate provision) not found **anywhere** in 84,283 points — including not under `UU_7_1945`, the garbled HPP fragment `TAXC-5` found for a *different* HPP provision (NIK-NPWP, Pasal 2 ayat 1a). So the mislabeled fragment does not cover this journey's specific need; it is a different slice of HPP, not the whole law. | A full acquisition of UU 7/2021 is the honest cure — the existing `UU_7_1945` fragment is not a shortcut for THIS provision, only for the NIK-NPWP one (which is tax-J7's territory in spirit, though a different target instrument). Worth checking, before any fresh download, whether `UU_7_1945`'s 31 points can be *expanded* (same source, more pages) rather than acquiring a second, separate ingest of the same law under two identities. | **Yes** |
| tax | 9 | Permen_1_2026 | **B** | Full scroll: phrase found, attributed to `Permen_1_2026` (3 hits) — the **identical** instrument+phrase as tax-J4, which measures GREEN at rank 1 under Indonesian statute-phrasing. J9 asks the same underlying fact in colloquial English and measures RED. Journey's own note names this a "phrasing-sensitivity gap," not an ingestion gap. **Confirmed NOT a query-expansion artifact** (see below) — the single cleanest same-fact minimal-pair in the whole set (J4 green, J9 red, nothing else changed but question language) is a genuine ranking gap. | Ranking / cross-lingual retrieval. | No |
| tax | 10 | UU_36_2008 | **B** | Same evidence as tax-J6 (identical phrase, identical attribution) — measured red, consistent with J6, "reinforcing this is a genuine ranking issue rather than one query's bad luck" per the journey's own note. | Same as J6. | No |
| property | 1 | UU_5_1960 | **B** | Full scroll: phrase found, attributed to `UU_5_1960` (point `7ebdcd3b-…`), the 216-point clean-of-§6-signal instrument. `property.yaml`'s own header states every phrase in the file was pulled character-for-character from a real chunk. | Ranking (confirmed genuine — not a query-expansion artifact, see below). | No |
| property | 2 | UU_5_1960 | **B** | Full scroll: phrase found, attributed to `UU_5_1960` (point `c7e9ae7c-…`). | Ranking (same as property-J1). | No |
| property | 9 | PP_6630_2021 | **B** | Full scroll: phrase found, attributed to **both** `PP_6630_2021` and `Permen_18_2021` — the identical phrase as property-J4, which measures GREEN at rank 2. Journey's own note: "the KB has no bridge between lane A's KITAS-deposit rule and lane D's Hak Pakai duration clause, so a compound cross-lane question retrieves neither half coherently... This red is the finding, not a defect in the journey." | Ranking is unlikely to be the whole story here — a compound A×D question may need multi-hop synthesis this single-collection retrieval doesn't attempt, which is a different (and larger) unit of work than a rerank tweak. Recorded as the orchestrator's own designed finding, not re-litigated here. | No (not a corpus write; may not even be a pure-retrieval fix) |

## The degraded-path question — retracted, measured

Every row in the table above was independently checked against production with working
multilingual query expansion (the isolated-overlay measurement in Method step 5): **the outstanding
set is identical, index for index, degraded or not.** So the class-by-class hedge this section used
to carry is gone — none of it was ever a real possibility once the same-day measurement landed:

- **Class A (3 rows)** was already unaffected by construction — absence-of-document is a fact about
  what was ingested, not about query-side expansion — and the overlay measurement confirms the same
  outstanding set regardless.
- **Class B (19 rows** — corrected 2026-08-26; company-J7 moved here from Class E, see the
  Aggregate table below, which this bullet previously did not match), including the ones that most
  looked like cross-lingual gaps (company J1/J3/J5/J6/J7/J8/J11, tax J9, property J1/J2/J9 — client
  questions in EN/IT/ES against Indonesian statute text; tax-J9 in particular is the identical
  instrument+phrase as green tax-J4, differing only by question language) — none of them flip. The
  ranking/chunking cures proposed per row still stand, undiluted by any "but maybe expansion fixes
  it for free" possibility.
- **Class D (1 row)** and **Class E (1 row** — dropped from 2 to 1 by the same company-J7
  correction) were never expansion-dependent to begin with (a metadata defect and one malformed
  journey, respectively) — consistent with the measurement.

The venv mismatch remains a real, open fact (google-genai `1.75.0` installed vs `2.18.1` pinned;
qdrant-client `1.13.3` vs server-reported `1.16.3` vs lock-pinned `1.19.0`) and every run against
the shared venv is still degraded — but it no longer casts doubt on any verdict in this table.

## The corpus-wide `legal_status` question — answered by the team lead, ownership moved to lane-A2

While this session was mid-investigation on immigration-J4, the team lead independently measured
the aggregate `legal_status` distribution across all 84,283 points of `legal_unified_hybrid_hybrid`
(`dicabut` 50.3% / 42,420 pts, `berlaku` 31.0% / 26,107, `None`/absent the remaining 18.7%) and
asked whether this is a real corpus fact or a systemic mismarking, with an explicit instruction not
to open any write PR until it had a measured answer. **This session reproduced the same aggregate
independently** (`/tmp/j4investigate/aggregate_and_perdoc.py` — identical totals; also found 202
distinct `document_id`s carry any `dicabut` point, 190 of those wholly so — a document-level signal,
not per-chunk noise) — but the team lead answered the actual question themselves, with a stronger,
self-contained proof that needs no external source: **on 9 documents with independently known
status, 7 are contradicted by their own `legal_status` marking** — including `UU_6_2011`
(Immigration Law), `UU_40_2007` (Company Law), `UU_6_2023` (Cipta Kerja), and `UU_13_2003`
(Ketenagakerjaan), all four marked `dicabut` on 100% of their own chunks. And the corpus
contradicts itself without leaving the collection: it holds `UU_63_2024`, marked `berlaku`, titled
*"PERUBAHAN KETIGA ATAS UU NOMOR 6 TAHUN 2011 TENTANG KEIMIGRASIAN"* (third amendment to UU
6/2011) — an in-force amendment to a supposedly-revoked law does not hold together. The same shape
closes immigration-J4's own pair: `Permen_11_2024` is titled as amending `Permen_22_2023` directly.

**Verdict: confirmed systemic mismarking, not a real corpus fact** — measured by the team lead,
reproduced in aggregate by this session, not merely plausible. This corroborates
`kb/inventory/immigration.yaml`'s pre-existing `LANE-A-1` finding (dated 2026-08-25, already in
`feature/kb-current` before this triage started), which named the same root cause: `STATUS_PATTERNS`
in `apps/backend-rag/backend/core/legal/constants.py`, a bare regex with zero disambiguation of
what or whom a `dicabut`/`berlaku` match refers to — read this session, that mechanism is already
**RETIRED** (2026-08-25, "Lane P, kb-p2-status-retire-0825", merged into `feature/kb-current`
before this triage's tip). Nothing writes fresh `legal_status` values any more;
`scripts/ci/legal_status_read_lint.py` gates reads of the stale ones already on disk.

**Ownership and scope, per the team lead's explicit instruction**: the `legal_status` corpus-wide
remediation is now **lane-A2's** — they have the full census and the artefact spec. **This triage
does not open, and will not open, any write PR on this field.** Nothing here is proposing a repair;
the direction the original (retracted) J4 hypothesis pointed in was right (`Permen_22_2023` should
not read `dicabut`) even though the specific cause and scale attributed to it were wrong — lane-A2
owns getting that corrected, gated by its own invariant probe (red-before/green-after), not by
anything in this document.

**Answer to "which other red journeys shared J4's retracted cause": none.** All 24 rows were
searched for `legal_status`/`LANE-A-1` mentions — three matches total. Immigration-J4 (above, the
only causal use — retracted). Company-J5 cites `LANE-A-1` only for `UU_6_2023`'s point-count scale
(a ranking-competitor-size fact, not a status value). Tax-J6/J10 cite `LANE-A-1` only for
`Permen_1_2026`'s point-count/contamination scale — same, no status causation. Immigration is also
the only topic carrying any `must_not_retrieve` canary (`immigration.yaml` lines 95/145/228 — J2
and J8 are green; J4 is the only outstanding one). No other row needs the winner-vs-loser
re-measurement the team lead specified.

## Matcher methodology correction — reused the probe's own `normalize()`, not a reimplementation

The team lead caught a defect in this triage's own tooling on company-J7 (below): my ad-hoc
follow-up script split the verbatim phrase into shorter needles instead of testing it whole, and I
mistranscribed **"Berusaha"** out of the phrase entirely when copying it into that script — the
`kb/journeys/company.yaml` text was correct all along (confirmed via `git log -L` on the original
lane-B commit: never edited). The corpus text also carries a mid-phrase newline, which
`kb/ops/probe_retrieval.py`'s own `normalize()` (whitespace-collapse + lowercase) already handles
and my ad-hoc needle-splitting did not. Independently reproduced this session by **importing that
exact function** (`from kb.ops.probe_retrieval import normalize`, not reimplementing it) and
re-scanning: 1 exact normalized match, point `004ac9d4-262b-503e-939c-8f3d6f7d27e0`, under the
correct claimed instrument. Company-J7 is reclassified B below.

The team lead then ran the same probe-matcher check across **all 41** `verbatim_phrase` journeys
in the four files (not just the 24 red ones) and reports: only **4 phrases are genuinely absent
from the corpus anywhere** — immigration-J2, immigration-J8, tax-J5, tax-J8. The other 37,
including company-J7, exist somewhere. This session's own Class A calls (tax-5, tax-7, tax-8) are
unaffected: tax-5 and tax-8 are on the team lead's confirmed-absent list, and tax-7's Class A call
was never a phrase-absence claim — it was an instrument-specific absence (`PER_7_PJ_2025`), with
the underlying phrase/fact explicitly noted as present elsewhere (`Permen_81_2024`, `UU_7_1945`)
in that row already. A check of every other row in this table found no other "phrase not found
anywhere" claim, so no further reclassification follows from this sweep.

## Aggregate

| Classe | Count | Requires production write |
|---|---|---|
| A — strumento assente | 3 (tax-5, tax-7, tax-8) | Yes, all 3 |
| B — presente ma non recuperato | 19 (adds company-J7, corrected 2026-08-26 from E) | No for 17; **Yes** for immigration-J6 (ingest-generation reconciliation, not a pure rerank); ambiguous/likely-no-but-not-pure-ranking for property-J9 |
| C — identità sbagliata | 0 | — |
| D — canary violato | 1 (immigration-J4) | **No** (corrected 2026-08-26 — `legal_status` is confirmed inert at retrieval time; the previously-proposed repair does not touch this defect's actual, unestablished cause) |
| E — percorso sbagliato | 1 (tax-J2) | No |

**24 total.** Class E dropped from 2 to 1 (company-J7 corrected to B, 2026-08-26) — not a
consistent slice (1/24, ~4%), so this still does not meet the bar for stopping and flagging before
finishing the table. The one remaining E finding is cheap, concrete, and worth fixing before
anyone spends effort "curing the corpus" against a miswritten journey contract.

**Groupable into single units of work:**

1. ~~Re-run all four probes once the venv's `google-genai`/`qdrant-client` mismatch is resolved,
   before touching ranking code.~~ **Already done** (isolated overlay, Method step 5) — result: no
   change, identical outstanding set. Not a gate on any of the work below; drop it from the plan.
   The venv mispin itself is still worth fixing as a standing hygiene item (every un-overlaid run
   is degraded again), but it no longer blocks or de-risks anything in this table.
2. ~~immigration-J4's `legal_status` repair~~ — **RETRACTED, causally disproven twice over,
   2026-08-26** (see the J4 row above): first because the field is never read at retrieval time
   (AST lint + `status_vigensi` being the actual, unpopulated filter target), second and more
   decisively because the team lead measured `legal_status` as *identical* on both the winner and
   the loser (402/402 vs 340/340 `dicabut`) — a constant cannot explain a ranking. Do not run
   `propose_legal_status_repair.py` for this journey; it cannot move J4's outcome under any
   reading. The field's corpus-wide mismarking (see the new section above) is real — confirmed by
   the team lead, not this triage — but its remediation now belongs to **lane-A2**, not to any unit
   of work this triage proposes. This triage opens no write PR on that field.
3. **tax-J5 + tax-J7 acquisition** — both DJP-issued (Kepdirjen / Perdirjen), both confirmed
   absent by convergent methods, both candidates for the *same* "recover from `legal_unified_2026`
   or re-acquire from pajak.go.id" workflow the mandate's §1 already describes for other
   instruments. Natural single batch.
4. **tax-J8 (HPP) is its own acquisition**, not groupable with the DJP pair above (different
   issuing authority, different source, a full UU not a Kepdirjen/Perdirjen) — but check whether
   `UU_7_1945`'s existing 31-point fragment can be *expanded* (same source document, more pages)
   before starting a second, separate ingest of the same law under a second identity.
5. ~~company-J7 + tax-J2, a single "journey QA pass"~~ — **company-J7 removed from this item,
   corrected 2026-08-26** (see the row above): it is not a text-correction/journey-QA case at all,
   it is a genuine one-point-in-84,283 retrieval miss. It is not grouped below either — a single
   low-density point competing on a compound cross-topic (zoning×licensing), cross-lingual
   (Spanish) question does not share a mechanism with either lever in item 6, so it stands as its
   own, ungrouped B row. **tax-J2 alone remains here**: one journey-file correction
   (`expectation: retrieves` → `must_not_retrieve`), no production risk, no shared code with
   anything else — but per the row above, applying it does not remove a red; it only corrects what
   the red means. Land it whenever convenient; it is not urgent in the way a false-red would be.
6. **Two candidate reranking levers, each touching multiple B rows**, worth trying independently
   rather than assumed to be the same fix: (a) a penjelasan/commentary de-boost relative to
   operative-article chunks (immigration-J5, company-J6) and (b) per-document score normalization
   so a large document (UU_6_2023 at 4,685 pts, Permen_1_2026 at 1,506 pts) does not structurally
   drown out a thin one for a shared topic (company-J5, tax-J6/J10, immigration-J6). Neither is
   proven here — these are hypotheses grouped by shared mechanism, not verified fixes.

## Adversarial review

**Seat:** `kimi` (Kimi K3), 2026-08-26, cross-family review of this file and the companion WIZ-1
document (`2026-08-26-wiz1-regulatory-ingest-route.md`), against `origin/feature/kb-current`.

**Verdict: SURVIVES_WITH_LIMITS.** No central thesis of this triage was refuted. The reviewer found
4 corner defects in this file (C1-C4 below), all corner-level (stale internal counts, an overbroad
code claim, a real point-identity contradiction, and one finding that on independent measurement
turned out not to hold). None touch the triage's central classification (24 rows, 3/19/0/1/1 across
classes A-E) or its recommendation to leave `legal_status` remediation to lane-A2.

**What the reviewer independently verified** (not merely re-read): re-derived the winner/loser
`legal_status` values on immigration-J4 (`Permen_22_2023` 402/402, its canary `Permen_29_2021`
340/340, both `dicabut`) rather than trusting this file's prose; checked the `apply_filters` claim
against the actual `search_service.py` code path; retrieved both cited Qdrant points on the
company-J7/J9 pair rather than trusting the "same point" claim.

**Findings and what was corrected, each independently re-verified by this session before any fix
was applied — no correction below was applied on the reviewer's word alone:**

- **C1** — the "degraded-path" section's per-class counts (Class B "18 rows", Class E "2 rows")
  were stale against this file's own Aggregate table (B=19, E=1) after the company-J7 E→B
  reclassification. **Fixed** — aligned to the Aggregate, with a note explaining the drift.
- **C2** — the immigration-J4 row claimed the repeal-exclusion filter is wired in "regardless of
  `apply_filters`". **Fixed** — verified at `search_service.py:554-564`: `apply_filters=False`
  rebuilds the filter with `exclude_repealed=False`; the filter is unconditional only for the
  `None`/`True` paths (i.e. every external query, which is what the row's conclusion actually
  needs). The conclusion — the live filter targets `status_vigensi`, not `legal_status`, and is
  0-populated — is unaffected.
- **C3** — the company-J7 row (1 exact match for its phrase, at point `004ac9d4-…`) and the
  company-J9 row (claiming its point `0027f82d-…` "also carries journey 7's boilerplate") were
  mutually contradictory: if true, J7's own scan should have found 2 matches, not 1. **Fixed by
  measurement, not by picking a side**: retrieved both full point IDs from production
  (`004ac9d4-262b-503e-939c-8f3d6f7d27e0` and `0027f82d-347e-5e83-8371-ee48564649d3`) and
  cross-checked each against both phrases using `kb.ops.probe_retrieval.normalize` (imported, not
  reimplemented). They are two distinct points; each contains only its own journey's phrase. The
  J9 row's claim was the wrong one — corrected.
- **C4** — flagged as a possible 340-vs-345 numeric contradiction for "the same document"
  (`Permen_29_2021`/`Permen_11_2024`). **Does not hold, no fix applied.** Direct production
  measurement: `Permen_22_2023`=402, `Permen_29_2021`=340, `Permen_11_2024`=345 — three different
  documents, each count independently correct. The reviewer's premise that these two counts refer
  to one document was a misreading of two unrelated passages (J4's canary pair vs. J10's
  ranking-competitor pair); no numeric error exists here.

**What the reviewer explicitly declared it could not verify, and why:** no production Qdrant
credentials — every point-level and count claim in the reviewer's findings (C3, C4) was a *reasoned
inference from this file's own text*, not an independent measurement against production; this
session supplied the missing measurement for both. The reviewer also did not have access to
re-derive the 12-sample vs. full-population question in the companion WIZ-1 file from anything
other than that file's own tables — its C5/C7 findings are consistency checks on the document's
internal arithmetic, not independent production measurements (this session separately re-ran the
live extractor against the full 48-delta population and confirms both numbers, see the WIZ-1
document's own Adversarial review section).
