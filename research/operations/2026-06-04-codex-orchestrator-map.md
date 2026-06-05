# Codex Orchestrator Map - 2026-06-04

Scope: map non-operative or partially operative surfaces, identify active
parallel lanes, and close one non-overlapping backend fix through tests.

## Machine and Sync

- Local machine: Pro, `nuzantara@Nuzantara`.
- `mini` SSH alias was unreachable during this session.
- `m5` / Air-M5 was reachable in a prior check but was not at the same repo
  head as this Pro worktree.
- Main checkout was busy and dirty on branch `fix/backup-fly-proxy-2026-06-03`.
- Codex mutation worktree: `.worktrees/ops-codex-orchestrator-map`.

## Active No-Touch Lanes

- Main checkout: occupied by Claude/Codex desktop flows; do not mutate there.
- WR2/WR3/FlowKit/media lanes: active or likely active; avoid asset/prompt/video
  automation unless explicitly assigned.
- WA, wa-mirror, OpenClaw, doc-intake, corpus, and CRM Guardian runtime lanes:
  active or scheduled; inspect live logs before changing worker behavior.
- M5 lanes include S1 events outbox, Olympus/db safety envelope, organism/world
  scan, golden visa/docs work. Avoid Olympus light-process registration changes
  until that lane resolves.

## Subagent Reuse

- Singer: backend/router/runtime audit. Confirmed manifest-vs-registration drift,
  `team_members` duplicate registration, compliance dry-run risk, Naga/intel/
  autonomous stubs, scheduler migrations, and legal KG OOM disable.
- Noether: frontend/MCP audit. Confirmed stale `apps/webapp` scope, unwired
  `apps/web`, admin war-room navigation gap, mouth frontend metrics no-op,
  streaming resume backlog, settings placeholders, E2E skips, MCP mock-only
  coverage and live-gated ops.
- Hooke: ops ownership audit. Confirmed main checkout occupancy, active local
  sessions, M5 divergence, and safe backend setup files for this worktree.

## Closed In This Worktree

- Registered manifest-declared API routers that were not mounted at runtime:
  `admin_email_health`, `admin_pii`, `admin_rate_limit`,
  `admin_self_healing`, `compliance_alerts`, `intel_observability`,
  `llm_costs`, `partners`, `research_control`, `war_room_dashboard`,
  and `workspace_analytics`.
- Registered RAG/BOTH routers in the heavy process where missing:
  `admin_rate_limit`, `admin_self_healing`, `intel_lake`,
  and `intel_observability`.
- Left `olympus.internal_router` full-only for light process because local
  comments and active M5 Olympus work mark it as internal/admin ownership.
- Removed the stale light registration for `team_members.router`; `team.py`
  remains the canonical `/api/team/members` router.
- Added AST-based parity coverage so future `_API/_BOTH` manifest entries must
  appear in full and light runtime registration, and `_RAG` entries are audited
  in an independent local check.
- Hardened `/api/war-room/metrics/*` with CRM admin auth before exposing it.
- Made compliance alert retrain `dry_run` non-mutating and covered it with a DB
  test before exposing the router.

## Verified

- `PYTHONPATH=. pytest backend/tests/setup/test_router_registration_parity.py backend/tests/setup/test_router_manifest.py backend/tests/unit/routers/test_war_room_dashboard_router.py backend/tests/services/compliance/test_alert_feedback.py -q`
  - Result: 33 passed.
- `PYTHONPATH=. pytest backend/tests/app/routers/test_compliance_alerts_router.py -q`
  - Result: 8 passed.
- `ruff check` on touched backend files.
  - Result: all checks passed.
- `python -c "from backend.app.dependencies import get_current_user; print('OK')"`
  - Result: OK.
- Independent AST audit:
  - `missing_full_api []`
  - `missing_light_api []`
  - `missing_heavy_rag []`
  - `registered_without_manifest []`
- Runtime registration smoke:
  - `full: 758 routes`
  - `light: 572 routes`
  - `heavy: 250 routes`

## Remaining Non-Operative / Partial Surfaces

High priority, backend:

- `autonomous_execution` and `services/rag/autonomous_executor.py`: feature flag
  is documented but not wired; execution remains POC/simulated.
- `naga.py`: session lookup and claims search are stubs or v1.1 placeholders.
- `intel.py` staging revalidate endpoint returns 501.
- `oracle_universal.py`: accepts fields that are logged/dropped instead of
  passed through to service.
- `whatsapp_onboarding_detector.py`: onboarding chain trigger returns mock
  result instead of invoking MCP.
- Trend Hunter adapters: XAI, Reddit, and Google Trends adapters return empty
  placeholder results.
- Legal ingestion KG extraction: intentionally disabled on Fly due 2GB OOM;
  only consider Pro/offline proof.
- Autonomous scheduler: several jobs intentionally migrated to Air/Pro cron or
  disabled due Fly auto-stop/self-call issues.

High priority, frontend/MCP:

- `apps/webapp` is stale scope; actual satellite appears to be `apps/web`, but
  `apps/web` is not a root workspace and imports `@nuzantara/ts-schemas`.
- Admin war-room metrics page exists but is not linked from admin sidebar.
- Mouth frontend metrics collection skips `/api/metrics/frontend` because the
  endpoint is not implemented.
- Chat streaming retry/resume is documented as incomplete.
- Settings integrations and user management contain local-state placeholders.
- MCP chains/browser/advanced ops have strong mock coverage but live operation
  remains opt-in and environment gated.

## Suggested Next Assignments

- Backend lane: Naga/intel/autonomous stubs, one feature per worktree.
- Frontend lane: `apps/web` workspace wiring and admin war-room discoverability.
- Ops lane: prove CRM Guardian/WA/doc-intake runtime from logs before changing
  worker automation.
- M5 lane: resolve Olympus/db safety work before changing light process exposure.

## 2026-06-05 Reusable Live Mapper

The manual map is now backed by `scripts/ops/orchestrator_live_map.py`, a
read-only CLI that gathers:

- `git worktree list --porcelain` for active isolated lanes.
- `gh pr list` for open remote branches and likely ownership.
- local process signals for Claude, Codex, Gemini, FlowKit, WA, and backend
  runtimes.
- high-signal incomplete markers in operative source roots.

It derives no-touch lanes first, then proposes candidate workstreams only when
the component area is not already owned by an open PR, active worktree, or live
runtime signal. This keeps the orchestration map reusable without relying on a
single stale report snapshot.

## 2026-06-05 Multi-Machine Extension

The live mapper can now include read-only remote observations before deriving
safe candidate workstreams:

```bash
python scripts/ops/orchestrator_live_map.py --include-m5 --format markdown
python scripts/ops/orchestrator_live_map.py --remote m5 --format json
python scripts/ops/orchestrator_live_map.py --remote air=air:/Users/balizero/Desktop/nuzantara
```

Remote collection is intentionally narrow: `ssh`, `git -C <repo> worktree list
--porcelain`, repo head metadata, and `ps aux`. It does not run remote cleanup,
does not send process signals, and does not call `gh` remotely. Remote
worktrees and process signals are tagged with their source machine, but their
lanes block local candidate generation globally. That is the operational rule
needed to avoid Codex and Claude Code working on the same feature from Pro and
Air-M5 at the same time.
