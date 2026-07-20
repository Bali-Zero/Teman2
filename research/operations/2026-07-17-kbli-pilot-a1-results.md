---
date: 2026-07-17
domain: operations
client_case: none (KBLI corpus reconstruction — internal method validation)
sources:
  - BPS Tabel Konversi KBLI 2020↔2025 Vol.2 (sha256 29f17b3b133497a88c5bfd0eaa3f73c90233b9b95dd76dd0ea2ccaed31724949, 444pp, both directions)
  - PP 28/2025 lampiran corpus (BPK Download ids 394930–394950, 21 files, per-file sha in pp28/fetch-log.jsonl)
  - OSS RBA snapshot 2026-07-17 (gw.oss.go.id, version uuid fff4053d-cbb0-51e9-9dc5-1e85b5740704)
  - Canonical data/source_documents/KBLI_2025_FINAL_CLEAN.json @ main (post-#2559)
  - Pre-registration: research/operations/2026-07-17-kbli-pilot-a1-preregistration.md (frozen plan)
adversarial_review: codex
---

# KBLI Pilot A1 — GARUDA-FILIERA method validation (RESULTS)

> Companion to the frozen pre-registration (`2026-07-17-kbli-pilot-a1-preregistration.md`).
> Grades the pilot against the pre-committed acceptance criteria. Infra shipped in PR #2566
> (merged 2026-07-16T19:47:30Z). This report itself was corrected twice under adversarial review
> (§Adversarial review) — the headline is **7/8 pass + one documented deviation**, not "8/8".

## Verdict

**Method VALIDATED. 7 of 8 pre-registered acceptance criteria PASS; criterion #6 has a documented
label-taxonomy deviation (not a clean pass).** On 15 real KBLI-2025 codes the GARUDA-FILIERA pipeline
(Fable-5 orchestrator + D6 gate; Sonnet-5 D1/D5/D2 seats; deterministic compilers as the only writers;
generator≠grader blind refutation) reproduced the three known index collisions, surfaced four new real
ones, certified the clean codes without false quarantine, and left the innocence controls untouched.

## Batch result (15 codes, clean run)

| Code | Kind | mapping | licensing_inherits | D1 needs_quar | D5 verdict | quarantined | Note |
|---|---|---|---|---|---|---|---|
| 68112 | index | COLLISION+SPLIT | false | false | certified | **no** | MICE-venue detached; per_skala stays [] (reproduces #2508/#2527) |
| 51103 | index | SPLIT | true | true | quarantined | **yes** | aviation licensing must NOT inherit onto space-passenger transport |
| 51203 | index | SPLIT | true | true | certified | **yes** | aviation-cargo licensing must NOT inherit onto space-cargo transport |
| 20111 | new | MERGE | true | true | certified | **yes** | 3 old codes (20111/20114/20118) converge — licensing must aggregate, not inherit-one |
| 43216 | — | SPLIT | true | false | certified | no | 3-way split (→43216/43400/43909), licensing inheritance legit |
| 43223 | — | SPLIT | true | false | certified | no | 3-way split (→42991/43223/43400); inheritance legit |
| 49213 | new | COLLISION+MERGE+SPLIT | true | true | certified | **yes** | AKDP digit-collision → wrong authority level (Gubernur vs Wali Kota) — client-harm |
| 47771 | — | MERGE | false | false | certified | no | PP28 absent; nothing to inherit |
| 50115 | new | ONE_TO_ONE | true | true | quarantined | **yes** | crosswalk clean; pp28_source [51107] is an AIR code on a SEA activity + absent in vault |
| 60312 | new | ONE_TO_ONE | true | true | quarantined | **yes** | crosswalk clean; declared pp28_source [63912] absent across 21 files / 11,208 pages |
| 64110 | — | ONE_TO_ONE | false | false | certified | no | PP28 absent; label-only relabel |
| 64310 | new | SPLIT | false | true | certified | **yes** | pp28_source pointer lands on I.L.101 SPA row (96122) — wholly wrong source |
| 65121 | innocence | — | — | — | boring_as_expected | no | untouched ✓ |
| 85202 | innocence | — | — | — | boring_as_expected | no | untouched ✓ |
| 85579 | innocence | — | — | — | boring_as_expected | no | untouched ✓ |

**7 quarantined · 5 certified-clean · 3 innocence untouched.**

## Acceptance-criteria scoring (frozen plan §Acceptance criteria)

1. **D0 completeness** — PASS. Every dossier cites vault items per applicable layer (crosswalk
   lampiran rows, OSS snapshot/absence records, PP28 renders or ABSENT/NOT_APPLICABLE record).
2. **Index-case reproduction** — PASS. 68112 → code-number collision, per_skala stays detached.
   51103/51203 → aviation-licensing-does-not-inherit (both quarantined). No divergent conclusion.
3. **Innocence controls** — PASS. 65121/85202/85579 = `changes_proposed: []`, via a REAL adjudication.
4. **Crosswalk discipline** — PASS. Every 2020↔2025 join cites a Lampiran 5 / Lampiran 10 row with
   page locator; 1-to-many rows carry uraian-semantics rationale + independent D5 verdict.
5. **Digit discipline** — PASS. Load-bearing digits image-verified; seats refused pdftotext digits.
6. **Verdict taxonomy** — ⚠️ **DEVIATION (not a clean pass).** The frozen taxonomy allows only
   `certified | quarantined | abstained`. The adjudication seats (D1/D5/D2) honor it, but the
   **innocence branch emits `boring_as_expected` / `unexpected_finding`** — a distinct vocabulary that
   maps cleanly onto certified/quarantined but is, literally, outside the frozen three tokens. Flagged
   by the Codex grader. Semantically sound, formally a deviation; a future run should normalize the
   innocence verdicts into the frozen taxonomy.
7. **D6 final gate (Fable, non-delegable)** — PASS. Fable re-read raw vault evidence for **100% of the
   7 quarantines** (5 by image, 2 by vault absence-record) **AND 5 random non-quarantine dossiers**
   (43216, 43223, 47771, 64110 by image; 65121 via its sha256-verified innocence pass) — 13 dossiers
   total, exceeding the "100% quarantines + ≥5 random" bar. No seat hallucination found. Table below.
8. **Measurement** — PASS. Per-dossier seat/token table + honest Fable-vs-heavy-plane split below.

## D6 final gate — Fable eyes on raw vault (non-delegable)

**Quarantines (100%):**

| Dossier | How | Raw-evidence confirmation |
|---|---|---|
| 49213 | image | PP28 394945 p.36 (49213=AKDP/Gubernur) vs p.65 (49413=perkotaan/Wali Kota) — wrong authority level |
| 51103 | image | BPS lampiran5 p.193: `51109 → 51101 AND 51103 (Transportasi Antariksa Penumpang)` |
| 51203 | image (same page) | BPS lampiran5 p.193: `51204 → 51202 AND 51203 (Transportasi Antariksa Barang)`; `old-51203 → 51201` |
| 20111 | image (2pp) | BPS p.140: old-20111→{10773,20111,20119}; p.141: old-20114→20111 AND old-20118→20111 (3-way merge) |
| 64310 | image | PP28 394946 p.223 I.L.101 row 76 = `96122 Aktivitas SPA` — the cited pp28_source is a SPA page |
| 50115 | vault record | pp28/ABSENT.json: sources_hunted [51107], verdict absent (11,208 pages scanned) |
| 60312 | vault record | pp28/ABSENT.json: sources_hunted [63912], verdict absent |

**Random non-quarantine dossiers (≥5):**

| Dossier | How | Raw-evidence confirmation |
|---|---|---|
| 68112 | image | BPS p.223: old-68111→new-68112 (residential); old-68112(MICE)→new-68124; PP28 I.L.44 = MICE row |
| 43216 | image | BPS lampiran5 p.174: `43216(2020) → 43216 AND 43400 AND 43909` (3-way split confirmed) |
| 43223 | image (same page) | BPS lampiran5 p.174: `43223(2020) → 42991 AND 43223 AND 43400` (3-way split confirmed) |
| 47771 | image | BPS lampiran5 p.186: `47771(2020) Minyak Tanah → 47771(2025)` direct 1:1 (kerosene retail) |
| 64110 | image | BPS lampiran5 p.217: `64110 Bank Sentral → 64110 Aktivitas Bank Sentral` 1:1 |
| 65121 | sha256 + image | innocence pass: 8 evidence files sha256-matched; crosswalk 65121→65121 1:1; canonical == OSS verbatim |

No seat hallucination found: every cited fact survived Fable's independent raw-evidence read.

## Measurement — per-dossier + Fable-usage (criterion #8)

Per-dossier seat invocations + Sonnet tokens (clean run, `workflowProgress`):

| Code | seats | tokens | | Code | seats | tokens |
|---|---|---|---|---|---|---|
| 68112 | 2 | 217,912 | | 47771 | 2 | 225,607 |
| 51103 | 2 | 246,879 | | 50115 | 2 | 182,500 |
| 51203 | 2 | 231,237 | | 60312 | 2 | 183,496 |
| 20111 | 2 | 308,081 | | 64110 | 2 | 193,677 |
| 43216 | 3 | 357,453 | | 64310 | 2 | 185,183 |
| 43223 | 3 | 326,576 | | 65121 | 1 | 131,415 |
| 49213 | 2 | 266,966 | | 85202 | 1 | 145,835 |
| | | | | 85579 | 1 | 172,310 |

**Total: 29 seats, 3,375,127 Sonnet tokens (avg 116,383/seat, 225,008/code).** Direct measurement, no
caching (see §529 incident). Seat count varies: 2 for the base D1+D5, 3 when a certified code runs D2
(43216, 43223), 1 for innocence.

**Fable-vs-heavy-plane split:**
- **Heavy plane (all Sonnet):** 3,375,127 tokens across 29 D1/D5/D2/innocence seats. `claude-sonnet-5`
  on all 56 model fields across both runs; all 4 `agent()` calls in kbli-pilot-a1.js `model:"sonnet"`.
- **Fable plane:** two workflow launches + the D6 image-gate (13 raw-evidence reads, this session's
  transcript) + orchestration. **Zero Fable *workflow-seat* tokens** (the accurate claim — corrected
  from an earlier overbroad "zero Fable adjudication tokens": the D6 gate IS Fable adjudication, just
  not a workflow seat). The Fable-plane token count is **not separately metered** by the harness in
  this run; it is bounded by orchestration + 13 image reads (order 10⁵), i.e. a small fraction of one
  Sonnet seat — but stated as a bound, not a measured split.
- **Corpus extrapolation (A1-rate scenario, NOT a grounded projection):** at the A1 per-batch rate
  (3.375M / 15 codes) × 104 batches ≈ **351M Sonnet tokens**. **Caveat (Codex):** A1 is deliberately
  enriched with known collisions + suspects + controls, so its D2/seat mix is not representative of a
  random batch; treat 351M as an A1-rate ceiling scenario, not a statistically-grounded corpus number.
- **Why it matters** (Fable-paid contingency, Zero "non voglio pagare"): the expensive model does
  orchestration + gate only; the per-code adjudication runs on abundant Sonnet quota.

## Meta-pattern — a hypothesis (not a proven single cause)

The four data-integrity failures below are **consistent with** ONE defective belief in `canonical.json`'s
`pp28_sources` / `per_skala` layer — **"the KBLI code number is a stable key across the KBLI-2020-vintage
PP 28/2025 lampiran and the KBLI-2025 dataset"** — but the pilot proves the *symptoms*, not that they all
share this single root (Codex caveat: flavors 2–4 could be independent data-entry errors). Treat as a
strong working hypothesis to test in Fase 1, not an established common cause:

1. **Same-digit cross-vintage collision** — 49213, 51103, 51203, 20111 (pilot-quarantined) + 68112
   (same class, already cured). The digit persists but the activity changed. *This flavor is directly
   explained by the bare-digit-join hypothesis.*
2. **Wrong-mode source** — 50115: an AIR-transport code (51107) on a SEA-transport activity.
3. **Absent source** — 60312: a declared pp28_source (63912) not present in the 21-file vault.
4. **Wholly-wrong pointer** — 64310: a money-market-fund code whose pp28_source lands on a SPA row.

Flavors 2–4 are data-integrity defects the crosswalk-first method still catches; whether they share
flavor 1's root cause is an open question for Fase 1. **No marker-based guard catches flavors 2–4.**

## The 529 incident (honest)

The first run hit an Anthropic-side `529 Overloaded` storm: 8 of 15 D1 seats died → returned `null` →
their D5 refuters correctly *abstained/quarantined* on a null proposal ("default refuted=true when
uncertain" — fail-visible, never rubber-stamp). That run was **degraded, not a measured batch**. The
`Workflow` resume re-ran the batch → 29/29, 0 errors. **The resume did NOT replay surviving seats from
cache — all 15 codes re-ran fresh** (distinct agentIds + token counts vs the first run; per-agent cost
≈116K identical across both runs, so nothing was replayed for free). Getting a clean batch after the
storm cost the full 2,196,731 + 3,375,127 = **5,571,858 tokens**, not a cheap 11-seat top-up.

## Adversarial review (two-pass, generator≠grader)

This report was graded TWICE by independent graders (≠ the Fable author), each re-opening the raw
artifacts rather than trusting the prose.

**Pass 1 — Sonnet grader.** Caught one BLOCKING error: the draft called the resume "cache-preserving"
and derived "~4.5M from-scratch / ~300K per code". Pairwise agentId/token comparison (and my own
re-check) proved **no caching occurred**; the false claim + derived figures were removed.

**Pass 2 — Codex (GPT-5.6, cross-family).** Found 6 issues a same-family Sonnet pass missed — all
addressed in this version:
- **#7 was not met** as first claimed (I'd re-read 7 quarantines + only 68112, not the required ≥5
  *random* dossiers). → FIXED: re-read 43216/43223/47771/64110/65121 against raw vault; #7 now genuinely
  passes (table above).
- **#8 was incomplete** (batch aggregates, no per-dossier metrics, no Fable quantification). → FIXED:
  per-dossier table + honest Fable-plane bound added.
- **"Zero adjudication tokens on Fable" was overbroad** (the D6 gate IS Fable adjudication). → FIXED to
  "zero Fable *workflow-seat* tokens".
- **#6 is a taxonomy deviation** (`boring_as_expected` is a 4th state). → ACKNOWLEDGED; verdict
  downgraded from "8/8" to "7/8 + documented deviation".
- **Meta-pattern over-asserted causality.** → SOFTENED to a hypothesis.
- **351M corpus figure not statistically grounded** (A1 is enriched). → RELABELED as an A1-rate scenario.

**Residual caveats** (acknowledged, not blocking): absence-record evidence (50115/60312) is weaker than a
positive wrong-row image; D6 independence is transcript-auditable, not journal-auditable; method
validation on 15 hand-picked codes ≠ zero false-negatives across 1,559 (Fase 1 keeps per-batch D6 +
innocence controls for this reason).

## Next (Fase 1 — GO-gated, cure NOT applied)

Per Zero's standing halt, **no data cure was applied** — this pilot is method validation only. When
Fase 1 is GO'd:
- Consumer-map first (mouth code pages · gold · KG/Qdrant on WA/webchat · baked editorial · NB).
- The 7 quarantines get the false-friend fix pattern (`per_skala → []` + `per_skala_disputed_<source>`
  + corroborated `_data_note` + registry test with guilt+innocence corpus).
- 49213 + the 4-flavor pattern go into `kbli-navigator` §2 (as pilot-verified, root-cause-hypothesis).
- Normalize the innocence-seat verdicts into the frozen taxonomy (criterion #6 deviation).
- Fix `vault_mirror_tigris.sh` bucket-override + `--exclude` logs (tracked, non-urgent — durably mirrored).
