---
date: 2026-07-17
domain: visa
client_case: none — product research (Visa Oracle v2 rebuild)
sources: multi-LLM panel round 1 (lane: sonnet-explore-scout)
status: round-1 raw lane output, faithfully preserved
adversarial_review: codex
---

# Round 1 — Scout lane (Explore/Sonnet): existing Visa Oracle v1 map (2026-07-17)

CRITICAL FLAG: the funnel is LIVE on www.balizero.com/visa (last commit 2026-07-14, 29 commits/90d). Mandate confirmed by Zero: rebuild targets the experience + content layer knowingly, not greenfield.

## 1. Frontend — apps/mouth (Next.js 16, React 19, Tailwind, "mouth" v5.2.0)
Serves www.balizero.com (+ kita/my/prime per INDEX.md:33). Subhi's primary surface.
Live funnel (PR #165 "feat(visa): unify Check + Oracle into single funnel at /visa", merged 2026-04-21):
- `apps/mouth/src/app/visa/page.tsx` — entry branch selector "Are you already in Indonesia?" → Yes→/visa/clock, No→/visa/match. Uses AppFrame/AppBranchSelector/useFunnelApp from @balizero/core.
- `visa/clock/page.tsx` (133 l.) + `clock/[hash]/page.tsx` — in-country branch: visa_type + entry_date → expiry countdown/timeline.
- `visa/match/page.tsx` (315 l.) + `match/[hash]/page.tsx` — planning branch: 4-step wizard (nationality → purpose → duration → budget) via AppWizard; decision tree in `apps/mouth/src/lib/visa-oracle/quiz-logic.ts` (84 l., 7 purposes incl. digital_nomad/retire/study).
- `visa/layout.tsx`, `privacy/page.tsx`, `terms/page.tsx`.
- `components/visa/`: VisaChat.tsx (341 l., conversational AI on top → /visa-oracle/chat), ChatAccordion.tsx (on BOTH result pages), ConfidenceBadge.tsx, ConsentBanner.tsx, HandoffWaLink.tsx, QuestionCounter.tsx, WhatsAppCTA.tsx.
- `lib/visa-oracle/`: quiz-logic.ts, storage.ts, api.ts, types.ts, nationalities.ts + tests.
- `components/funnel/`: funnel-nav.ts, SessionInit.tsx, HeaderWhatsAppCTA.tsx, PropertyEligibilityBody.tsx, TaxCalendarBody.tsx — the funnel pattern is a GENERALIZED app abstraction (visa/property/tax).
- `e2e/visa-funnel-fusion.spec.ts` (93 l.) Playwright E2E.
- `app/(assessment)/assessment/` — separate flow, relation UNKNOWN (unmapped).
- `components/blog/interactive/DecisionTree.tsx` (553 l.) — separate generic reusable tree primitive for MDX articles.
Shared lib: `packages/core/` (@balizero/core) — components/apps/AppFrame.tsx, AppBranchSelector.tsx, components/FunnelFrame.tsx, analytics/useFunnelApp.ts, funnel-app.ts, funnel-view.ts. HIGHLY reusable.

## 2. Backend — apps/backend-rag (FastAPI), all registered in app/setup/router_registration.py (lines 209, 411, 472, 635, 825, 963; two registration blocks noted, not diffed)
- `routers/visa_check.py` (346 l.) — prefix /api/visa: POST /check/start, /clock, /match, GET /clock/{hash}, /match/{hash}. Comment router_registration.py:144 "[4APPS] Homepage Visa Check app".
- `routers/visa_oracle.py` (928 l.) — prefix /visa-oracle, public/no-auth: POST /recommend, /chat, /handoff, GET /visa-types, /visa-types/{code}.
- `routers/knowledge_visa.py` — /api/knowledge/visa full CRUD over visa_types; backs MCP list_visa_types/get_visa_details (nuzantara_mcp/tools/knowledge.py:116,127).
- services/visa_check/: catalogue.py, clock.py, match_tree.py (the decision-tree logic), pricing_bridge.py (→PricingTool), repository.py.
- services/visa_oracle/visa_oracle_service.py (471 l.): recommend_visas(), get_all_visa_types(), build_whatsapp_message(), build_telegram_summary(), _score_visa(), _parse_duration_days().
- services/visa_unified/bridge.py (134 l.) — bridges Check + Oracle.
- services/rag/kg_subgraph_visa.py — visa KG subgraph. services/compliance/visa_expiry_team_notifier.py — cron notifier.
- Tests: test_visa_oracle.py, test_visa_oracle_service.py, visa_check/test_match_tree.py, test_router_jwt.py, visa_oracle/test_chat_jwt.py, test_kg_subgraph_visa.py, test_visa_expiry_team_notifier.py.

## 3. Data
- migrations_v2/124_visa_checks.sql — visa_checks table, 2 branches, hash shareable URLs (renumbered 121→124).
- migrations_v2/148_practice_types_bridging_visa.sql — "Bridging Visa" practice_type (3.5M IDR) in CRM catalog.
- migrations/migration_073_visa_lifecycle.py, 080a_visa_oracle_sessions.py, 109_funnel_sessions.py, 122_practice_types_visa_d1_5yr.py, 043_fix_visa_types_from_qdrant.py.
- migrations/scripts/seed_visa_types_complete_2026.py — 114 visa codes (A1/A4/A36/A37, B1/B4, C1-C22B incl. C5A, D1-D17, E23-E23Y, E25/E25A/E25B, E28A, E33/E33A-E33G, F1/F4) — canonical catalog.
- data/visa_oracle_cleanup_2026-04-16/ — NotebookLM-sourced rule extraction (nb2_rules_groups_1to5.md, nb2_inquiry_D_operational.md).
- apps/kb/data/immigration — UNEXAMINED.

## 4. Paper trail
- docs/plans/2026-04-19-4apps/01-visa-check.md (218 l.) — THE executed v1 spec (acceptance criteria all match live code).
- docs/superpowers/plans/2026-04-04-visa-oracle-implementation.md (2368 l.) + specs/2026-04-04-visa-oracle-design.md (522 l.).
- docs/superpowers/plans/2026-04-21-visa-funnel-fusion.md (2386 l.) + spec (342 l.) → PR #165.
- docs/superpowers/plans/2026-04-21-visa-catalogue-rebuild.md (1695 l.).
- docs/superpowers/plans/2026-04-17-v2-rollout-00-master.md + 02-funnel-hub.md (630 l.) — "4 apps" homepage rollout.
- skills/nuzantara-domain-knowledge/.../immigration-and-visas.md (46 l.).
- No visa corner existed in .claude/skills/ before tonight.

## 5. Assessment
Reusable even in rebuild: @balizero/core funnel primitives, 114-code seed, match_tree.py logic (as input), DB schema. Dead/uncertain: (assessment)/ flow, apps/kb/data/immigration. GA4: 11 visa_quiz_* events instrumented (April).

## Adversarial review

**Seat:** codex (GPT-5.6-terra-high adversarial grading, 2026-07-17)
**Verdict:** SURVIVES-WITH-CAVEATS

Challenged points:
- UI/router files and their line counts match disk — confirmed.
- Both cited migration paths are wrong; the actual paths are `backend/db/migrations_v2/` and
  `backend/migrations/scripts/`.
- "114 canonical codes" is a seed-data count, not a regulatory-authority count — should not be cited as
  if it were the latter.

This section is an appended R1-gate artifact (generator≠grader); the file body above is preserved
verbatim as the faithful record of this panel lane's original output.
