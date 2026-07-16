---
name: kbli-navigator
description: "KBLI Navigator corner — the live shared context for ALL KBLI corpus/product work (dataset, gold, KG, editorial, kbli pages on balizero.com). Load BEFORE touching any KBLI data or code, or when Zero says /kbli-navigator, 'kbli corpus', 'filiera', or references the July 2026 disease cluster. Holds: established truths (verified, with method), parked-cure state, Filiera methodology status, artifacts & access, blood-bought operating rules."
---

# /kbli-navigator — KBLI corpus & product corner

> Created 2026-07-16 on Zero's order after the July disease cluster. This file is the HOT CONTEXT
> shared by every Fable/Claude session and every Codex dispatch working on KBLI. It states what is
> PROVEN, what is PARKED, and the rules that were paid for in blood. **Update the LIVE STATE section
> whenever it changes — this corner is only useful if it stays true.**

## 0. The product (what all of this serves)

`balizero.com/kbli/<code>` (apps/mouth, 1,559 KBLI-2025 code pages) + the RAG/KG backend answering
KBLI questions on WhatsApp/webchat (`inspect_kbli`/`chat_kbli`/`search_kbli`). Clients make real
licensing/investment decisions on this data — a wrong risk row is client-facing harm (cf. Darinka
KBLI dispute). Honesty beats completeness: a declared gap ("licensing not yet published") is
acceptable; a plausible-but-wrong assertion is not.

## 1. LIVE STATE (last update 2026-07-16 ~10:45 UTC — keep current)

- **Per-code cure HALTED by Zero** pending Filiera phase GO. Nothing of the halted work reached prod.
- **Filiera KBLI methodology**: panel CONCLUDED (Codex red-team 15 findings/5 FATAL + Gemini
  costruttivo 12, incorporated). Doc: `research/operations/2026-07-16-kbli-filiera-methodology.md`
  (PR #2534, auto-merge armed). 9 principles, layers L0(vault)→L6(editorial), gates G13–G17 extending
  Garuda G1–G12, 4-phase rollout. **Phase GO = Zero (business decision, open).**
- **PR/branch map**:
  - MERGED & live: #2508 + #2527 (68112 detach: per_skala→[] + `per_skala_disputed_pp28_mice` +
    `_data_note` + gold whatYouNeed fix + regression tests) · #2523/#2524 (gold youllAlsoNeed remap
    20/83 + renderer fix) · #2496/#2494 (CRM avatar, unrelated) · #2532 (ship-lifecycle doctrine).
  - PARKED: PR #2528 (KG license-fix script, auto-merge DISARMED — resume within Fase 1 after F12
    language fix) · branch `agent/air-m5/infra/space-51103` on origin at `fc12e65fd3` (51103/51203
    detach, NO PR — `_data_note` needs corroboration language before opening) · fly apply NEVER run.
  - 63 phantom gold refs documented in `scripts/kbli_gold_remap_table.json` (await BPS-crosswalk
    adjudication).
- **KG prod is still contaminated** (by design, cure parked): 68112 serves MICE+agriculture licenses;
  ~68% of catalog serves the agriculture kewajiban via the shared perizinan node; 930 codes serve
  drifted `properties.uraian`.

## 2. ESTABLISHED TRUTH (verified — do not re-litigate, do not re-derive)

1. **68112 = code-number collision** (image-verified 3× on official BPK PDFs): PP 28/2025 Lampiran
   I.L (Pariwisata) p.I.L.44 row 25 codes 68112 as "Penyewaan Venue MICE dan Event Khusus"; BPS
   7/2025 (KBLI 2025) reassigned 68112 to residential leasing. Residential in PP28 = **68111**
   (Lampiran I.H, PUPR). No residential 68112 exists anywhere in PP28's 21 lampiran.
2. **False friends confirmed beyond 68112**: 51103/51203 (KBLI-2025 space transport carrying
   KBLI-2020 commercial-aviation licensing). High-concern suspects NOT yet adjudicated: 25200
   (weapons/ammunition — needs dedicated regulatory review), 11× 47xxx retail family, 20111, 32114,
   32906, 43216/43223. Sweep evidence: `research/operations/2026-07-16-kbli-false-friend-sweep.{md,json}`
   (currently only on the parked space branch).
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
   (FATAL-3). Gold `baliContext` texts are at risk.
7. **OSS API 404 ≠ regulatory absence** (F12): could be changed UUID, lag, WAF, access control.
   `ABSENT` verdicts require corroboration (e.g. absence in PP28 lampiran verified on image, or
   crosswalk evidence). The shipped 68112 note has corroboration; wording for future notes must say
   "no scope retrievable via OSS API (404), corroborated by <X>" — never bare "not published".
8. **KG diseases** (verified 2× on prod Postgres): perizinan nodes deduped BY NAME → 978 codes share
   ONE "NIB dan Sertifikat Standar" node whose kewajiban is agriculture text (852 edges); 187 agri-
   marked nodes reach ~1,065/1,568 codes. Router precedence bug: `props.get("uraian", description)`
   → properties.uraian wins; 930 codes drifted. The KG catalog has NO generator left in the repo.
9. **Bali moratorium overlay (l4_bali)**: verdicts were derived from (possibly collision-derived)
   risk levels, and the Gubernur letter's binding legal effect is unproven (F15) — treat "blocked"
   as conservative posture, not certified fact; re-derive reasons when true risk is known.
10. **Gold/editorial layers bake upstream errors**: they keep asserting stale facts after the source
    is fixed, and don't name the marker (no "MICE" in the baked prose) — marker-based guards can't
    catch them. Re-grounding a source MUST emit an invalidation list of derived surfaces.

## 3. ARTIFACTS & ACCESS (verified paths — check before use, cf. anti-hallucination)

- **Canonical dataset**: `data/source_documents/KBLI_2025_FINAL_CLEAN.json` (1,559 codes; tracked
  symlink `source_documents/` → same; mouth copy `apps/mouth/data/` kept byte-identical by
  `scripts/sync_kbli_dataset.sh` + CI `check-kbli-dataset-sync`). Sidecar sha:
  `apps/mouth/data/kbli-dataset-version.json`. Per-record provenance: `_source`, `_l1_source`,
  `_l2_source`/`_l2_status`, `pma_source`, `pp28_sources`, `l4_bali`, `intel_2026`.
- **Gold layer**: `apps/mouth/data/kbli-gold-all.json` (428 records) — served by
  `src/lib/kbli-data.server.ts`; remap table `scripts/kbli_gold_remap_table.json` (63 phantom rows).
- **OSS RBA API** (public app credential, zero PII): host `gw.oss.go.id`, header
  `user_key: $OSS_RBA_USER_KEY` (static credential of the government app — value in memory
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
- **Backend KG**: Postgres `kg_nodes` (`kbli:<code>`, `perizinan:<hash>`) + `kg_edges`
  (REQUIRES). Read-only: `scripts/pg.sh` / MCP `postgres-nuzantara` (combo `nuzantara_readonly`,
  proxy `127.0.0.1:15432`). Cure script (parked): `apps/backend-rag/backend/scripts/kg_kbli_license_fix.py`
  (dry-run default, `--apply` gated, `--only` mandatory, canonical-driven). Resync:
  `kg_kbli_resync.py` (now syncs properties.uraian too, PR #2528 branch).
- **Regression tests**: `scripts/tests/test_kbli_68112_pp28_mice_collision.py` — false-friend
  registry pattern (marker + audit-key + disclaimer "code-number collision"); extend it for every
  new false friend, never write a bare-substring guard (scar #3: guilt+innocence corpus mandatory).
- **Specs**: Filiera methodology `research/operations/2026-07-16-kbli-filiera-methodology.md`
  (PR #2534) · "Operazione Garuda 1559" spec (GPT-5.6 Sol, 2026-07-14) — Garuda certifies internal
  consistency; Filiera adds external truth.

## 4. OPERATING RULES (blood-bought — violating these re-opens closed wounds)

1. **Vintage-aware identity**: `KBLI2020:X ≠ KBLI2025:X`. Any cross-vintage join goes through the
   BPS conversion table; bare-digit joins are forbidden. This applies to PP28 AND Perpres 10/49 AND
   Kepmen 228/2019 TKA-categories AND any pre-2026 source.
2. **Crosswalk narrows, context adjudicates**: the citing entry's use-case decides, never
   title-similarity ("il contesto batte il titolo" — 63120→63900 lesson). Signature of a wrong
   remap: mapping_type=SPLIT applied as single code + boilerplate reasoning.
3. **Silence → corroborated abstention**: a 404/missing row is recorded as gap ONLY with a second
   independent signal; NEVER silently fill from another vintage/source (that silent fill IS the
   July disease).
4. **Detach > plausible remap**: "un phantom dichiarato è onesto, un rimappato sbagliato è una bugia
   in produzione."
5. **Digits from scans: image-verify** (pdftoppm 300dpi + eyes). pdftotext output of BPK scans is
   evidence of TEXT, never of DIGITS.
6. **Consumer-map before scoping any data fix**: canonical → mouth pages · gold → same pages ·
   KG/Qdrant → WA/webchat · intel_2026/editorial → baked prose · NB sources. Fix the class across
   ALL consumers or explicitly park the rest; "merged" ≠ "live" ≠ "every surface".
7. **Derived layers need invalidation**: after correcting any source fact, list which derived fields
   (gold whatYouNeed, editorial, l4_bali reason, KG properties, NB) were generated FROM it and
   schedule them; guards on markers won't catch baked prose.
8. **False-friend fix pattern** (use as-is): `per_skala` → `[]` + preserve old block under
   `per_skala_disputed_<source>` + `_data_note` with corroborated wording + entry in the registry
   test + innocence controls (legit codes with similar markers must not be touched).
9. **No new licensing values without provenance**: never author risk/license/authority values from
   plausibility — either a sourced row (with locator+vintage) or an honest "not yet defined".
10. **Ship-lifecycle**: per CLAUDE.md §2 doctrine — the session reviews, merges, arms, deploys,
    proves live. Sensitive data raises the adversarial gate (generator≠grader), never parks the
    merge on a human. Currently OVERRIDDEN for the parked cure by Zero's explicit halt (LIVE STATE).

## 5. WHO IS WHERE (2026-07-16)

- Session M5 `ac430002` (Fable, this corner's author): 68112 chain, false-friend sweep, KG audit,
  parked cures; agents goldfix/kgfix/sweep idle, worktrees `infra-space-51103`,
  `infra-kg-68112-licenses` hold the parked work.
- Parallel Fable session `f5892d39` (scratchpad holds `kbli-methodology-draft.md`,
  `codex-redteam-out.txt` 47k, `agy-costruttivo-out.txt`): authored Filiera + ran the panel → PR #2534.
- Earlier session `1cb1509a`: gold remap #2523/#2524 + remap table + context-beats-title lesson.
- Codex (GPT-5.6, `codex exec`): red-team seat on demand — give it THIS file + the specific artifact
  under review; it reads repo `AGENTS.md` and `.agents/skills/`.

## 6. MEMORY POINTERS (deep dives)

`discovery_kbli_68112_code_collision_pp28_vs_bps_2026_07_16` ·
`discovery_kbli_noscope_codes_per_skala_not_from_oss_2026_07_16` ·
`discovery_kg_perizinan_name_dedup_disease_2026_07_16` ·
`lesson_kbli_remap_gate_context_beats_title_2026_07_16` ·
`ops_kbli_cure_halted_filiera_panel_2026_07_16` ·
`feedback_merged_is_not_live_consumer_map_first_2026_07_16` ·
`discovery_oss_rba_kbli_api_extraction_2026_06_19` ·
`feedback_session_owns_full_ship_lifecycle_2026_07_16`
