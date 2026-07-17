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

## 1. LIVE STATE (last update 2026-07-17 — keep current)

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
(pre-fix run) to delete · PP28 300-dpi renders pending. **EXTRACTION GATE: D0-D6 cannot start until the PP28 300-dpi renders exist + the P1-v2 addendum lands (instrument status snapshots, OSS endpoint inventory — see #2622 conductor comment) + the P0 membership artifact is emitted.**

**Governance flags:**

- **Filiera methodology**: panel CONCLUDED. Doc `research/operations/2026-07-16-kbli-filiera-methodology.md`
  (#2534 MERGED); execution program `research/operations/2026-07-16-kbli-garuda-filiera-workflow.md`
  (#2538 MERGED). **Phase GO is PER BATCH (Legge 5, Zero).** Pilot A1 (~the 8 above) done; the
  measured pilot report is the basis for the batch-A-remainder GO.
- **BKPM discrepancy findings stay INTERNAL** (Zero, 2026-07-16): the 68112 surat klarifikasi stays
  drafted in the drawer, not sent, without a fresh Zero GO.
- **data-plane guard LIVE** (#2550): only `scripts/kbli_filiera/` compilers may write the canonical
  KBLI dataset + `data/kbli-filiera/**`; interactive hand-edits BLOCKED. Registry
  `infra/claude-hooks/data-plane-registry.json` is the extension point. Kill switch
  `DATA_PLANE_GUARD_OFF=1`. (gold `kbli-gold-all.json` is NOT yet registered — editable, but pin
  every change with a regression test, cf. the 49213/50115 gold cure.)

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
   intel_2026/editorial → baked prose · native `kbli-navigator` desktop app (M5/Pro/Mini) reads the
   canonical too · NB sources. Fix the class across ALL consumers or explicitly park the rest;
   "merged" ≠ "live" ≠ "every surface".
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
