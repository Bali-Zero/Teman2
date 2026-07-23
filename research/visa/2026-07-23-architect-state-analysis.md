---
date: 2026-07-23
domain: visa
client_case: none
author: Kimi (Air-M5) — architect state-analysis session
adversarial_review: human-zero
status: UNDER ADVERSARIAL REVIEW (4 seats: gemini / codex / glm / web-grounded)
---

# Visa Oracle v2 — architect state-analysis (verified 2026-07-23)

Machine: Air-M5 (thin client). Repo `nuzantara`, main HEAD `f3bf426de3` (M5↔Pro in sync).
Every claim below was verified against main on disk, live production (Fly + DB), or the live
public site — not from the skill ledger. Evidence transcripts included.

## Program frame (from /visaoracle skill)

Rebuild the Visa Oracle immigration funnel as Bali Zero's flagship public tool: interactive
decision tree guiding foreigners to the correct Indonesian visa/stay-permit path. Bar:
stunning aesthetics, zero wrong answers, demo-able to Ditjen Imigrasi, true expat guide.

ENFORCE-GATE (session may flip only when ALL green, never early):

- G-a VOLUME: ≥1,000 distinct real end-user requests processed by the engine in SHADOW,
  over ≥7 consecutive days, all 7 interview categories exercised, ≥30 distinct visa codes hit.
- G-b GOLD PERSONAS: 20/20 replay through the engine, zero unexplained divergences.
- G-c GROUNDING: every SHADOW verdict in the window carries valid citations, zero ungrounded
  claims (abstention on thin evidence = PASS).
- G-d ROLLBACK PROVEN: ENFORCE→OFF drill recorded, instantaneous, no redeploy.

Prerequisites: PR4 #2804 merged ✅; SHADOW wiring live on the real surface (STEP-6c).

## ✅ DONE (verified)

### Research phase — closed
3 rounds × 4 lanes persisted under `research/visa/` (round1: gemini survey, glm design,
codex architecture+red-team, web-verified, repo-map; round2: gemini regulatory-delta, glm
interview-design, codex engine-concretization [110KB spec], reuse-first OSS; round3: opus
arbitration → custom Python evaluator, ZEN → authoring/visual only).
Product design: `docs/plans/2026-07-17-visa-oracle-v2/00-product-design.md` +
`track-c-experience-spec.md`. Owner ruling R1: single client-facing all-inclusive price,
no PNBP/fee split.

### Track A — Engine: full chain merged on main
PR1 #2654 (foundations) → hotfix #2739 (4 gaps TDD) → PR1b #2745 (+residual #2795) →
PR2b #2757 (signed bundle RFC8785+Ed25519, anti-rollback) → PR3 #2773 (strong-Kleene
evaluator) → PR4 #2804 (bitemporal substrate) → PR5 #2841 (Decision evaluator, pure
tri-state orchestrator) → STEP-6a #2840/#2868 (activation writer, SECURITY DEFINER
`visa_activate_rule_pack()`) → PR-A1 #2869 (`compile_pack.py` + offline `sign_pack.py` +
first signed TEST pack fixture) → gold harness #2876 (M5: 20 self-authored personas +
metamorphic property tests) → ceremony runbook #2861 → STEP-6c #2916 (SHADOW wiring on
`POST /api/visa/match`, fire-and-forget audit eval) → STEP-6d #2930 (HMAC facts-fingerprint
identity provider) → #2952 (finite activation-system-period guard) → **#2982 (2026-07-22:
migration 255 SHADOW evidence substrate + PII-free fail-closed G-a/G-c collector +
CLI `scripts/visa_shadow_evidence.py`)**.

On disk (`apps/backend-rag/backend/services/visa_engine/`): ast, bundle, compiler, crypto,
enums, errors, evaluator, fact_registry, models, repository, schema_export, shadow,
shadow_evidence + contracts/ (10 JSON Schemas + packs/). Suite: 1,070 tests collected, all
runnable green (1 pre-existing skip: `visa_activation_executor` not provisioned).
Migrations `250_visa_engine_core.sql` … `255_visa_shadow_evidence.sql` all present.

Key ceremony DONE: kids `2026-07-test-1` (TEST) + `2026-07-prod-1` (PRODUCTION); private
Ed25519 keys on M5 `~/.config/nuzantara/visa-signing/` (0600); Fly secret
`VISA_ENGINE_TRUST_STORE_KEYS_JSON` staged on `nuzantara-rag` (digest `a68f076bc9993f0c`).
Runbook: `docs/runbooks/visa-engine-key-ceremony.md`.

Prod DB verification (read-only, 2026-07-23): `visa_decisions` HAS the migration-255 columns
(`request_fingerprint` BYTEA 32-byte check, `request_category` TEXT enum of 8 values,
`candidate_summary` JSONB, `grounding_summary`) → migrations 250–255 ARE applied in prod.

### Track C — Experience: live, mock-only
PR #2617 merged 2026-07-18: `https://www.balizero.com/visa-oracle` (200, noindex) is the
single Track C foundation; `/visa-v2` 308-redirects there. Living-tree experience, 5-state
RecommendState, 12-card catalog, EN/ID, WCAG AA, verdict tree→card morph (View Transitions),
tree tap-to-edit, real QR, checkable+printable checklist. 58 unit + 9 e2e.
**Still mock-only**: `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/mock-engine.ts` —
not wired to the real engine.
UI/UX adaptation spec EXISTS and is binding: `research/visa/2026-07-19-kimi-uiux-adaptation-spec.md`
(Kimi K3 design lead, Codex adversarial-reviewed). Core thesis: the shipped experience already
speaks the engine's 5-state vocabulary (PR0 freeze) → wiring is a "source swap behind a stable
rendering contract", not a redesign. Includes full state-mapping table, NEEDS_INPUT skeleton
design (missing from research lanes), 35-FactPath→questionId registry, citation/quote/freshness
rendering, client-synthesized TEMPORARILY_UNAVAILABLE on engine-unreachable.

### Track B — Content: FASE 1 done
PR #2602 (catalog bonifica: Kepmen M.IP-08/2025 133→110 index remap) MERGED 2026-07-17.
PR #2607 (Bridging Visa branch + D7A/D7B/D8A/D8B closeout + diaspora coverage) open w/ automerge.
Regulatory anchors established by round-2: dead B211* codes since M.IP-08/2025 (effective
2026-06-02 per dictum KELIMA), BVK nationality-only per Permen Imipas 10/2026 (19 states incl.
Macau; number-collision trap with Permenkumham 10/2026 Second Home), Permenkumham 36/2021
guarantor rules revoked by Permen Imipas 5/2025, regulatory cadence ~3-4 months.
Golden Visa stats VERIFIED-OFFICIAL: 1,274 visas / Rp52.1T as of 2026-05-18 (E28D Rp50.88T).

## 🔴 MISSING / RED (verified)

### M1 — THE SHADOW FEED IS BROKEN (discovered this session, not in the ledger)
The v1 wizard's POST never reaches the backend, and hasn't since ~2026-04-21:

- `visa_checks` (v1 table): **28 rows TOTAL, min 2026-04-18, max 2026-04-21** — zero rows in
  the last 3 months (read-only prod query).
- `curl https://www.balizero.com/api/visa/match` → GET **401**, POST **401**. There is NO
  Next.js route handler for it (`apps/mouth/src/app/api/visa/` does not exist) and NO rewrite
  (`next.config.ts:312` explicitly forbids /api/* rewrites: "Do NOT add rewrites for /api/*
  here as they conflict with the API route handler"). Unmatched /api/* paths on the site
  return 401 (probe: `/api/health` → 200, `/api/nonexistent-test` → 401).
- `curl https://kita.balizero.com/api/visa/match` (Fly backend direct) → **401
  `{"detail":"Authentication required"}`** — the endpoint is auth-gated on the backend too.
- The v1 page does a bare same-origin POST with no auth
  (`apps/mouth/src/app/visa/match/page.tsx:255-267`) and swallows failure:
  `catch { setSubmitError("We could not compute a recommendation…" + WhatsApp link) }` —
  every real user has been silently degraded to the error+WhatsApp fallback for 3 months.

Consequence: STEP-6c SHADOW wiring sits on a dead pipe. Even with secrets armed,
`visa_decisions` receives nothing. This is the absolute P0 — it also means the LIVE v1
funnel has been broken in production since launch week.

### M2 — No real RulePack exists
`contracts/packs/` contains only `rulepack-test-c1-tourism.{source,signed}.json` (fixture).
Prod: `visa_rule_packs` = 0 rows, `visa_ruleset_activations` = 0, `visa_source_records` = 0
(read-only prod query 2026-07-23). The legal content (110 bonified codes → signed rules,
≥30 codes / 7 categories needed for G-a breadth) has NOT been authored. Authoring tools are
done (#2869); signing custody is M5-only. This is the largest remaining work item, joint
Track A (compile/sign/activate) + Track B (legal content per code).

### M3 — Runtime not armed
Fly `nuzantara-rag` secrets (probed live 2026-07-23): only
`VISA_ENGINE_TRUST_STORE_KEYS_JSON` present. `VISA_ENGINE_MATCH_MODE` and
`VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON` ABSENT → Match SHADOW defaults OFF and the
identity provider fails closed. `visa_activation_executor` DB role not provisioned
(known test skip). Latest release v3897 deployed 2026-07-23 (code current, config dark).

### M4 — Gate criteria status
- G-a 🔴: feed broken (M1) + no pack (M2) + secrets (M3) + no collection window ever run.
- G-b 🟡: canonical 20-persona suite on main (PR5, `test_evaluator_gold.py` +
  `_gold_fixtures.py` vs real `evaluator.evaluate()`) green in CI — but NO accepted
  INDEPENDENT replay artifact (grader ≠ engine requirement). Follow-up owed: port M5's
  metamorphic properties (fact-order / rule-order invariance, monotonicity) onto the real
  evaluator; retire or demote M5's adapter-based harness.
- G-c 🔴: collector ready (#2982) but zero production rows to measure.
- G-d ⚪: deliberately not attempted before other gates green.

### M5 — Traffic reality vs G-a threshold (strategic risk, unmeasured by any criterion)
G-a needs ≥1,000 distinct real requests in ≥7 days. Historical organic rate at launch
(when the funnel worked): 28 requests / ~4 days ≈ 7/day. Even fully repaired, organic
traffic delivers the G-a volume in ~5 months, not 7 days. Options: (a) traffic drive
(SEO/Ads/placement — the flagship needs it anyway), (b) re-calibrate the criterion with the
owner, (c) longer window accepted. Owner decision required.

### M6 — Track C engine wiring not started
`/visa-oracle` is mock-only. The binding spec exists (source swap design). Does not block
the SHADOW gate (measured on v1 surface) but blocks the ENFORCE flip on the v2 surface.

### M7 — Track B FASE 2 not started
The 7 interview categories content (gated on #2602, open since 2026-07-17) has no LIVE
STATE entry since. Needed by both the RulePack (M2) and the UI (M6).

### M8 — Track D (Ditjen demo)
Blocked until G-b green.

## Proposed critical path (under review)

0. **Fix the feed (P0)**: diagnose intended path (two candidate layers: missing Next route
   vs backend auth floor); likely fix = Next route handler `/api/visa/match` that forwards
   to the backend with a service token (or public scoped endpoint with rate-limit). Verify
   first real row in `visa_checks`. Do this BEFORE arming secrets.
1. **Author the real RulePack** (Track A+B): content from bonified catalog, priority to the
   ≥30 codes / 7 categories G-a measures → sign on M5 → provision `visa_activation_executor`
   → activate in PRODUCTION.
2. **Arm SHADOW**: set `VISA_ENGINE_MATCH_MODE=shadow` +
   `VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON` on Fly (operator action, runbook exists);
   smoke-test end-to-end (1 funnel request → 1 `visa_decisions` row).
3. **Collection window**: ≥7 consecutive days, then re-runnable G-a/G-c measurement via
   `scripts/visa_shadow_evidence.py`.
4. **Parallel**: independent G-b replay (cross-family grader) + metamorphic port; Track C
   wiring per Kimi spec; Track B FASE 2; traffic plan decision (M5).
5. **G-d drill** once G-a/G-c green; then flip (session pre-authorized) with before/after
   capture.

## Open questions for the panel

- Is fixing the v1 feed the right P0, or should SHADOW be re-pointed at a NEW public
  evaluate endpoint (v2 surface) instead of repairing v1?
- Is the Next-route-with-service-token the right auth pattern, given the backend's
  auth floor and Law 2 constraints?
- Is the G-a threshold (1,000/7d) defensible as designed, or should it be re-proposed to
  the owner with the traffic data?
- What is the minimal correct RulePack slice that makes the gate meaningful (30 codes × 7
  categories vs full 110)?
- Anything in this analysis that is wrong, stale, or missing?

## Adversarial review — Fable 5 final gate

The panel disposition and surviving objections are recorded in
`2026-07-23-architect-review-synthesis.md`.
