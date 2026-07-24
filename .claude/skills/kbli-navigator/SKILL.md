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

## 1. LIVE STATE (last update 2026-07-24 — keep current)

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

**W1 is CLOSED. Next per the Codex program: W2 (Batch-B prep — still NO-GO without Zero) / W3+.**

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
below, which pre-dates Batch A's closure). Batch B has a SIGNED design (#2801) but NO Zero GO
— per this program's own per-batch phase-gate rule, Batch B does not start without one.

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
PULL COMPLETE 15/15). **Still PENDING: cross-family GLM Appendix A screen for Lot 8 — not yet
run.** Lot 9 D0 (10 remaining sport-cluster members: 93127-93199 + 2 fresh controls 46201/96300;
12 codes total) evidence already pulled and independently verified, pins at
`/tmp/kbli-conductor-a1-0718/lot9-prelaunch-pins.md` — adjudication Workflow not yet launched.

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
  ALIGN-FLEET TODO):** (5) its `data/kbli-2025.json` was untracked in the 2026-03-28 cleanup and
  rotted (1,563 records, zero quarantine markers, 68112 still MICE) — **cure lane in flight**,
  branch `agent/air-m5/frontend/kbli-navigator-dataset-desync` (conductor-gated), re-tracking +
  extending `scripts/sync_kbli_dataset.sh`/`check-kbli-dataset-sync`. (6)
  `apps/kbli-navigator/lib/kbli-gold-content.ts` (~45K lines, hand-authored, separate from mouth
  gold) OVERRIDES cured data on 68112/49213 pages (verified in built HTML) — **OPEN, queued, task
  #19**.
- **Mouth gold cure LIVE** (#2794): 10 gold records' detached-code echoes cured
  (whatYouNeed/zantaraOpener/baliContext), PROVE-LIVE on 68123/60103; 63-phantom triage table
  `scripts/kbli_gold_remap_table_status.json` (48 unmapped / 8 ambiguous-SPLIT / 7
  single-candidate).
- **Batch-B pre-registration design SIGNED** (#2801 merged, REV-4b): determinism gate closed after
  4 Codex xhigh rounds + Gemini; OPEN gates before any lot: Phase-0 parser build + Zero's Legge-5
  ratifications. See §5.

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
   cured for the 73 quarantined rows by `kbli_documents_cure.py` (#2796, 2026-07-19), whole-table
   builder still missing (PENDING-ARMS)** · intel_2026/editorial → baked prose · `apps/kbli-navigator`
   app (knowledge.balizero.com — Next.js, NOT a native desktop app, see LIVE STATE) → its own
   `data/kbli-2025.json` fork (stale, cure in flight) AND its own `lib/kbli-gold-content.ts`
   override layer (OPEN, task #19) · NB sources. Fix the class across ALL consumers or explicitly
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
#2801 merged) — pre-registration determinism gate closed after 4 Codex xhigh rounds + Gemini; OPEN
gates before any lot: Phase-0 parser build + Zero's Legge-5 ratifications (AQL default, Tier-4
volume). See LIVE STATE.

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
