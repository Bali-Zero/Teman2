---
adversarial_review: exempt-raw-panel-seat-output
---

## SEAT VERDICT
FIX-FIRST. The analysis is useful as a blocker inventory, but not usable as the plan basis until two corrections land: the “missing Next route” diagnosis is wrong, and SHADOW-on-v1 would collect invalid gate evidence because STEP-6c maps only 3 known facts out of the v2 engine’s 35 applicant-fact vocabulary.

Limit: I verified repo source at local HEAD, but live DNS/API and DB/Fly checks were not available from this lane. `curl https://www.balizero.com/...` and `curl https://kita.balizero.com/...` both failed with `Could not resolve host`, so the April DB counts and Fly-secret absence are not independently reverified here.

## CLAIM-BY-CLAIM
M1 broken feed: PARTIAL. The public v1 submit path is broken by the source contract, but not because “there is no Next route handler.” v1 posts only four fields to `/api/visa/match` and catches failure into WhatsApp fallback: [page.tsx](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/mouth/src/app/visa/match/page.tsx:251). A generic Next catch-all API proxy exists and exports POST: [route.ts](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/mouth/src/app/api/[...path]/route.ts:26), [route.ts](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/mouth/src/app/api/[...path]/route.ts:412). `next.config.ts` explicitly says API proxying is handled there: [next.config.ts](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/mouth/next.config.ts:311). The more likely repo-level failure is backend HybridAuth: `/api/visa/*` is registered as a router, but not in the public endpoint registry. `rg '"/api/visa|/api/v1/visa-oracle' public_endpoints.py` returns only `/api/v1/visa-oracle/*`, not `/api/visa/*`; HybridAuth returns 401 for non-public unauthenticated requests: [hybrid_auth.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/middleware/hybrid_auth.py:281).

Other route to the new engine: REFUTED. `maybe_spawn_shadow_match` is only called from `visa_check.py`; the public `/api/v1/visa-oracle/recommend` path is legacy scoring, not the new `visa_engine`: [visa_check.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/app/routers/visa_check.py:267), [visa_oracle.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/app/routers/visa_oracle.py:819).

M2 no RulePack: PARTIAL. Repo confirms only the TEST fixture pack exists: `find .../contracts/packs` returned `rulepack-test-c1-tourism.source.json` and `.signed.json`. Runtime also skips with no active pack: [shadow.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/services/visa_engine/shadow.py:597). Prod DB `0 rows` claim is unverified here.

M3 runtime dark: PARTIAL. Source confirms missing `VISA_ENGINE_MATCH_MODE` defaults OFF: [shadow.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/services/visa_engine/shadow.py:196). Missing facts-fingerprint key fails closed before save: [shadow.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/services/visa_engine/shadow.py:640). Actual Fly secret state is unverified from this seat.

M4 gate status: CONFIRMED directionally. Collector hard-codes G-b and G-d as unmeasured and never returns `enforce_ready=true`: [shadow_evidence.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/services/visa_engine/shadow_evidence.py:349). G-a/G-c cannot go green without rows, pack binding, citations, and categories: [shadow_evidence.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/services/visa_engine/shadow_evidence.py:286).

M5 traffic-vs-G-a: PARTIAL. Threshold is real: 1,000 distinct requests, 7 days, all categories, 30 codes: [SKILL.md](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/.agents/skills/visaoracle/SKILL.md:37), and collector constants match: [shadow_evidence.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/services/visa_engine/shadow_evidence.py:30). The “28 rows / 7 per day” traffic estimate is unverified here.

Proposed 6-step critical path: PARTIAL/WRONG ORDER. The fatal miss is schema validity. The engine has 35 applicant-collected fact paths plus 3 derived paths: [enums.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/services/visa_engine/enums.py:387). STEP-6c builds only nationality, purpose, stay days; “remaining 32 stay UNKNOWN(NOT_ASKED)”: [shadow.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/services/visa_engine/shadow.py:249). Budget is collected by v1 but not passed to SHADOW: [visa_check.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/app/routers/visa_check.py:267). Therefore fixing v1 before collection would produce rows, not valid v2 gate evidence.

## MISSED
P0: SHADOW must move to a full-fact v2 evaluate endpoint before any gate window. v1 can be repaired for business continuity, but it should not be the G-a/G-c evidence source.

P0: Do not add a blind Next BFF service-token shim as the primary fix. The generic proxy already exists. The auth contract is the issue: either add an exact public backend endpoint with documented public registry entry and in-router abuse controls, or add a narrowly scoped internal endpoint consumed by a dedicated Next route. Do not authenticate public users as a broad internal service.

P1: Category semantics mismatch. Migration 255 allows 8 categories including `other`: [255_visa_shadow_evidence.sql](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/db/migrations_v2/255_visa_shadow_evidence.sql:25). Collector excludes `OTHER` from required categories: [shadow_evidence.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/services/visa_engine/shadow_evidence.py:33). The plan must say whether `other` is excluded from volume breadth or only logged.

P1: G-c is stronger than the analysis implies: it validates citation references against pack sources, verified status, canonical URL, and legal/recorded periods: [shadow_evidence.py](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/backend-rag/backend/services/visa_engine/shadow_evidence.py:270). That means RulePack source hygiene is gate-critical, not just “citations present.”

P2: Track C is truly mock-only. The live v2 surface imports `mock-engine` and the file says it is a stand-in, not legal determinations: [mock-engine.ts](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/mock-engine.ts:1). The separate `recommendVisas()` client calls legacy `/api/v1/visa-oracle/recommend`: [api.ts](/Users/balizero/nuzantara/.worktrees/research-visa-architect-0723/apps/mouth/src/lib/visa-oracle/api.ts:238).

## CORRECTIONS
1. Split “fix feed” into two workstreams: restore v1 `/api/visa/match` for lead continuity, but declare it non-gating evidence unless it is upgraded to full `ApplicantFacts`.

2. Replace “Next route with service token” with: public, exact, rate-limited backend endpoint for anonymous v2 evaluation, or a dedicated Next route that calls a narrowly scoped internal backend endpoint. In both cases: schema validation, body-size cap, IP/session hash rate limit, no raw PII logs, no broad internal impersonation.

3. Move Track C wiring before the collection window. The v2 interview must produce the 35-path `ApplicantFacts` payload, including unknown reasons, citations output, and the same request fingerprint substrate.

4. Author the RulePack against the real full-fact schema, not the v1 adapter. Minimum slice must exercise all required categories and ≥30 product codes, but source records must be verified/in-force or G-c fails.

5. Update gate language: “7 required categories excluding `other`; `other` logged but not counted for breadth,” or change collector/schema deliberately. Do not leave the mismatch implicit.

6. Treat live April traffic and Fly secret state as claims needing a re-runnable receipt from Pro/Fly, not as accepted evidence in the final plan.

## SEQUENCING VERDICT
Current order is wrong for the gate. Correct order:

1. Repair v1 public auth path only as an operational hotfix.
2. Build v2 full-fact public evaluation endpoint and wire `/visa-oracle` to it.
3. Author, sign, provision, and activate the real production RulePack.
4. Arm SHADOW only after endpoint + pack + fingerprint key are present.
5. Run one smoke: one v2 interview request -> one `visa_decisions` row with full-fact provenance.
6. Then start the ≥7-day G-a/G-c window.
7. In parallel: independent G-b replay, metamorphic tests on real evaluator, traffic plan, and RulePack source hygiene.
8. G-d rollback drill remains last, after G-a/G-b/G-c are green.


codex exit=0
