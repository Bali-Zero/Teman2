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
---

# KBLI Pilot A1 — GARUDA-FILIERA method validation (RESULTS)

> Companion to the frozen pre-registration (`2026-07-17-kbli-pilot-a1-preregistration.md`).
> This file reports what the pilot actually produced and grades it against the pre-committed
> acceptance criteria. Infra shipped in PR #2566 (merged 2026-07-16T19:47:30Z).

## Verdict

**PASS on all 8 pre-registered acceptance criteria.** The GARUDA-FILIERA method is validated on
15 real KBLI-2025 codes: Fable-5 orchestrator (no hands) → Sonnet-5 D1/D5/D2 seats → deterministic
compilers as the only writers, with a generator≠grader blind refutation (D5) and a Fable
non-delegable image-gate (D6) against raw vault evidence. The blind refuters reproduced the three
known index-case collisions, surfaced new real ones, certified the clean codes without false
quarantine, and left the innocence controls untouched.

## Batch result (15 codes, clean run)

| Code | Kind | mapping | licensing_inherits | D1 needs_quar | D5 verdict | quarantined | Note |
|---|---|---|---|---|---|---|---|
| 68112 | index | COLLISION+SPLIT | false | false | certified | **no** | MICE-venue detached; per_skala stays [] (reproduces #2508/#2527) |
| 51103 | index | SPLIT | true | true | quarantined | **yes** | aviation licensing must NOT inherit onto space-passenger transport |
| 51203 | index | SPLIT | true | true | certified | **yes** | aviation-cargo licensing must NOT inherit onto space-cargo transport |
| 20111 | new | MERGE | true | true | certified | **yes** | 3 old codes (20111/20114/20118) converge — licensing must aggregate, not inherit-one |
| 43216 | — | SPLIT | true | false | certified | no | 3-way split, licensing inheritance legit |
| 43223 | — | SPLIT | true | false | certified | no | split undercount corrected; inheritance legit |
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
   lampiran rows, OSS snapshot/absence records, PP28 renders or ABSENT.json).
2. **Index-case reproduction** — PASS. 68112 → code-number collision, per_skala stays detached.
   51103/51203 → aviation-licensing-does-not-inherit (both quarantined). No divergent conclusion.
3. **Innocence controls** — PASS. 65121/85202/85579 = `boring_as_expected`, zero proposed changes,
   via a REAL adjudication (not a null-default — confirmed on the clean run).
4. **Crosswalk discipline** — PASS. Every 2020↔2025 join cites a Lampiran 5 / Lampiran 10 row with
   page locator; 1-to-many rows carry uraian-semantics rationale + independent D5 verdict.
5. **Digit discipline** — PASS. Load-bearing digits image-verified; seats explicitly refused
   pdftotext digit-strings (681t2 lesson honored).
6. **Verdict taxonomy** — PASS. Every non-deterministic fact ends `certified | quarantined | abstained`.
7. **D6 final gate (Fable, non-delegable)** — PASS. Fable re-read raw vault evidence for **100% of
   quarantines** (5 by image, 2 by vault ABSENT record) plus certified index case 68112 — 8 dossiers
   against raw evidence, exceeding the "≥5 random" floor. Details below.
8. **Measurement (Zero's Fable-usage question)** — PASS. Numbers below.

## D6 final gate — Fable eyes on raw vault (non-delegable)

| Dossier | How verified | Raw-evidence confirmation |
|---|---|---|
| 49213 | image | PP28 394945 p.36 (49213=AKDP/Gubernur) vs p.65 (49413=perkotaan/Wali Kota) — wrong authority level |
| 68112 | image (prior) + D5 render_refs | BPS p.223: old-68111→new-68112 (residential); old-68112(MICE)→new-68124; PP28 I.L.44 = MICE row |
| 51103 | image | BPS lampiran5 p.193: `51109 → 51101 AND 51103 (Transportasi Antariksa Penumpang)` |
| 51203 | image (same page) | BPS lampiran5 p.193: `51204 → 51202 AND 51203 (Transportasi Antariksa Barang)`; `old-51203 → 51201` |
| 20111 | image (2pp) | BPS p.140: old-20111→{10773,20111,20119}; p.141: old-20114→20111 AND old-20118→20111 (3-way merge) |
| 64310 | image | PP28 394946 p.223 I.L.101 row 76 = `96122 Aktivitas SPA` — the cited pp28_source is a SPA page |
| 50115 | vault record | pp28/ABSENT.json: sources_hunted [51107], verdict absent (11,208 pages scanned) |
| 60312 | vault record | pp28/ABSENT.json: sources_hunted [63912], verdict absent |

No seat hallucination found: every quarantine reason survived Fable's independent raw-evidence read.

## Meta-pattern — one disease, four contamination flavors

Every quarantine is a symptom of ONE defective belief baked into `canonical.json`'s
`pp28_sources` / `per_skala` licensing layer: **"the KBLI code number is a stable key across the
KBLI-2020-vintage PP 28/2025 lampiran and the KBLI-2025 dataset."** It is not — the 2020→2025
transition renumbered and re-partitioned codes, so a bare-digit join silently attaches the wrong
regulatory row. The pilot shows the defect manifests in four distinct flavors, all caught by the
same crosswalk-first method:

1. **Same-digit cross-vintage collision** — 68112, 49213, 51103, 51203, 20111. The digit persists
   but the activity changed (residential vs MICE; intra-city bus vs AKDP; space vs aviation transport).
2. **Wrong-mode source** — 50115: an AIR-transport code (51107) attached to a SEA-transport activity.
3. **Absent source** — 60312: a declared pp28_source (63912) that does not exist in the 21-file vault.
4. **Wholly-wrong pointer** — 64310: a money-market-fund code whose pp28_source lands on a SPA row.

The cure is the BPS conversion table (both directions) + per-activity adjudication — exactly what
the filiera L0→L1 layers mechanize. **No marker-based guard can catch flavors 2–4** (they are not
detectable from the code string alone); only a source-existence + vintage-reconciliation check does.

## Measurement — Fable-usage saved

The whole point of the architecture: the heavy per-code adjudication (D1 crosswalk proposal + D5
blind refutation + D2 image-extraction) runs entirely on **Sonnet** (verified: `agent(...,
{model:"sonnet"})` at kbli-pilot-a1.js lines 282/298/305/318). Fable does ONLY orchestration + the
non-delegable D6 image-gate.

| Run | agents | done/err | Sonnet subagent tokens | wall |
|---|---|---|---|---|
| First (529 storm) | 27 | 19 / 8 | 2,196,731 | ~14.5 min |
| Clean resume (cache-preserving) | 29 | 29 / 0 | 3,375,127 | ~13.1 min |

- **A clean 15-code batch = 29 Sonnet seat-invocations.** The producing run measured **3.38M Sonnet
  tokens** (8 agents replayed free from cache); a from-scratch clean batch estimates **~4.5M**
  (~300K tokens/code). **All on Sonnet; zero adjudication tokens on Fable.**
- **Fable's share** = 2 workflow launches + the D6 image-gate (8 raw-evidence reads) + orchestration —
  a small fraction of one seat's budget, and structurally the *only* thing Fable touches.
- **Corpus projection** (1,559 codes ÷ 15 ≈ 104 batches): **~350–470M Sonnet tokens** of adjudication
  kept entirely off Fable.
- **Why it matters doubly** (Fable-paid contingency, Zero "non voglio pagare"): if/when Fable becomes
  a metered endpoint, this split is what makes reconstructing 1,559 codes affordable — the expensive
  model touches ~2–5% of the token work, all of it orchestration/gate, none of it adjudication.

## The 529 incident (honest)

The first run hit an Anthropic-side `529 Overloaded` storm: 8 of 15 D1 seats died → returned `null`
→ their D5 refuters correctly *abstained/quarantined* on a null proposal ("default refuted=true when
uncertain" — fail-visible, never rubber-stamp). That run was **degraded, not a measured batch**. The
`Workflow` resume is cache-preserving: it replayed the 7 surviving codes for free and re-ran only the
11 dead seats once the storm passed → 29/29, 0 errors. Even *degraded*, the blind refuters had already
reproduced the known collisions and surfaced 49213 — a robustness signal, not a substitute for the
clean run.

## Next (Fase 1 — GO-gated, cure NOT applied)

Per Zero's standing halt, **no data cure was applied** — this pilot is method validation only. When
Fase 1 is GO'd:
- Consumer-map first (mouth code pages · gold · KG/Qdrant on WA/webchat · baked editorial · NB).
- The 7 quarantines get the false-friend fix pattern (`per_skala → []` + `per_skala_disputed_<source>`
  + corroborated `_data_note` + registry test with guilt+innocence corpus).
- 49213 + the 4-flavor meta-pattern go into `kbli-navigator` §2 established truths.
- Fix `vault_mirror_tigris.sh` bucket-override (mirror landed in `nuzantara-warroom-images`, should be
  `nuzantara-backups`) + `--exclude` logs (tracked, non-urgent — vault is durably mirrored).

## Adversarial review

Findings in this report were produced under generator≠grader by construction: D1 (proposal) and D5
(blind refutation) are independent Sonnet seats, and D6 is Fable re-reading raw vault images the
seats never authored. Every factual claim carries a re-executable locator (harness token counts;
BPS/PP28 page numbers; `pp28/ABSENT.json` records) so a reviewer can reproduce it from the pinned
vault (sha 29f17b3b…), not from this prose. The R1 concern (no self-graded homework) is therefore
met at the finding level. Residual limitations a refuter should hold against the *conclusions*:

- **Absence is weaker than a positive collision.** The 50115/60312 quarantines rest on
  `ABSENT.json` (a vault-scout "not found in 21 files / 11,208 pages" claim), not a positive
  wrong-row image. A legitimate PP28 row for 51107/63912 could exist in a volume outside the pinned
  21-file corpus. Correct posture: quarantine (conservative), NOT a certified "source is bogus" —
  matches what the seats emitted (needs_quarantine, pending a targeted D2/wider hunt).
- **Corpus projection is A1-representative only.** The ~350–470M-token figure assumes batch-A codes
  generalize; classes B/C/D (different layer coverage, more/less PP28 presence) may shift per-code
  cost. Stated as a projection, not a measured corpus number.
- **From-scratch batch cost is an estimate.** The measured 3.38M ran with 8 cached replays; the
  ~4.5M from-scratch figure is inferred, not directly measured.
- **Method validation ≠ data correctness at scale.** Passing on 15 hand-picked codes (3 known index
  cases + suspects + controls) proves the pipeline catches what it should on this sample; it does not
  prove zero false-negatives across 1,559 codes. Fase 1 keeps per-batch D6 + innocence controls for
  exactly this reason.
