---
date: 2026-07-19
domain: operations
adversarial_review: exempt-session-capture
---

# Kimi first campaign — session capture (2026-07-18 → 2026-07-19)

> Author: Kimi K3 (Kimi Code CLI), Air-M5 thin-client · 184 goal-turns, ~5h wall · Type: session capture for cross-session continuity (NOT an architectural spec — exempt from refuter per R1 2b)

## 1. The campaign ("campagna completa" — Zero's fire order)

| Strike | Outcome | Proof |
|---|---|---|
| S1 P0 Security | **PR #2747 MERGED** — cleartext PG password purged from `config/monitoring/docker-compose.monitoring.yml` (env-var pattern) + JWT Phase-2 activation audit (`research/operations/2026-07-18-jwt-expiry-phase2-activation.md`, GLM-5.2 refuter SHIP) | `bali_secure` = 0 on main; report on main |
| S2 MCP 401 | **Fixed live** — root cause: stale inline `NUZANTARA_API_KEY` in `.mcp.json` shadowed the live key in Pro's `~/.nuzantara-secrets.env`. Live key propagated M5 (hash parity `42bc…`), stale keys stripped from `.mcp.json` on M5+Pro | 200/200 on `/api/crm/expiry-alerts` + `/api/memory/lam/episodes` |
| S3 WR2 | **Closed by evidence** — image stage found ALIVE (4/4 slides 2026-07-18 09:14); liveness scorer already cured by sibling growth-loop (#2631 transport + #2635 forced-choice). Receptor armed → **proven at scale 2026-07-19**: run_20260719_010004.json = 3 developing (60) + 12 evergreen; selector 05:10 `using live pool (3 items)` — first non-empty live pool in pipeline history | PR #2785 MERGED (ledger + corner closed) |
| S4 Truth | **PR #2760 MERGED** — AGENTS.md realigned (327 router mounts/746 services/1449 tests/no-Alembic/224 daemon/1559 SSG, `packages/kb` phantom removed) + ai-dispatch.sh machine detection (m5/pro live-verified) + peer Pro→mini | Numbers on main; detection live on both machines |
| S5 KG staging promotion | **PR #2764 MERGED + DEPLOYED + FIRST DRY-RUN ON PROD** — built the never-built second half of the quarantine pattern (migration_077's promise). 936-ln job + migration 247 (self-sufficient: creates staging tables IF NOT EXISTS) + 33 tests + shadow-first cron workflow. GLM-5.2 refuter CADE on v1 → v2 rework (no SKIP LOCKED, chunked ≤25 txns, advisory-lock singleton, fuzzy→rejected never auto-merged) | First dry-run: census **726 pending nodes + 652 edges** (106-day backlog), 118 fuzzy-quarantined, 0 failures, zero writes |

## 2. The army (what was built/studied this session)

- **Orchestrating mind**: Kimi K3 (1M ctx) with native swarm/goals/cron/hooks — Legio I.
- **Legio II cloud seats** (verified live via `scripts/arsenal_probe.py`): Fable 5 (`claude` OAuth, final constitutional gate), Gemini `agy`, Codex GPT-5.6 sol/terra/luna, **GLM 5.2 (z.ai, refuter — used 2× productively: SHIP on S1 audit, CADE on S5 design)**, NotebookLM `nlm`.
- **DeepSeek V4 Pro REMOVED from the arsenal by Zero's order** (was BALANCE_DEAD/402 at probes) — GLM 5.2 takes the refuter seat. Invocation: Keychain `glm-coding-plan-token` → `https://api.z.ai/api/anthropic/v1/messages`, model `glm-5.2`.
- **Doctrine absorbed**: Fable-5 GARUDA-FILIERA pattern (mente immobile + mechanical layer + quarantine + gold-set + durable state) → mapped onto Kimi-native capabilities. House loop: GROUND → DESIGN (council) → BUILD (worktree swarm) → VERIFY (generator≠grader) → SHIP+ARM → PROVE-LIVE (by content) → CAPTURE.

## 3. Hard-won lessons (new scars worth remembering)

1. **Migrations must be self-sufficient**: the v2 chain (092→246) never created `kg_*_staging` (they came from legacy migration_077). My 247 ALTERed nonexistent tables on a fresh CI schema — CI Backend Tests caught it. Antibody: apply any new migration on a FRESH PG before pushing (I verified the fix on PG17 scratch DB on Pro).
2. **`PYTHONPATH=.` makes asyncpg vanish on the Fly image** (documented scar, confirmed live): the ssh-console dry-run fails with `No module named 'asyncpg'` if you set PYTHONPATH=. — use plain `cd /app && python -m backend.scripts...` (like the migration jobs do).
3. **Worktree venvs go stale after requirements merges**: my S5 push failed when the merged visa-engine PR brought `rfc8785`/`rfc3339-validator` and the worktree `.venv` lacked them. Antibody: after merging main into a worktree, sync the venv with the lockfile before re-pushing.
4. **fly ssh console `-C` runs the command directly** (no shell): `cd` doesn't exist; wrap in `/bin/sh -c '...'` (the fly-deploy pattern).
5. **`ollama` binary exists on M5** despite AGENTS.md R2 — possible drift; unused, noted for the operator.
6. **`.mcp.json` points to `~/Desktop/nuzantara`** while sessions run in `/Users/balizero/nuzantara` — two checkouts, currently same commit, drift risk; canonical-checkout decision pending.

## 4. Operator-gated items (await Zero, all prepped)

1. **Rotate `bali_secure_2024!`** (in git history — rotation is the only true remediation; optional filter-repo scrub).
2. **Flip `JWT_ENFORCE_EXPIRY=true`** — GO checklist in the S1 report: measure expired-token audit volume (≥7d `fly logs`) → flip → monitor 401 rate → rollback = unset secret. Env var name verified (`config.py:1166-1170`, no env_prefix).
3. **Arm KG promotion job** from shadow to `--apply` (manual dispatch of `cron-kg-staging-promotion.yml` or repo var `KG_PROMOTION_MODE=apply`) after the shadow week. Backlog 726+652 drains at 50/day ≈ 15 days. 118 fuzzy-quarantined need a human adjudication surface.
4. **KTP cleartext** in `data/hr/ktp/` (untracked + gitignored + 0600 — no repo risk; at-rest decision is Zero's).
5. **`~/nuzantara` on Pro**: dirty + ahead 2 — PENDING-ALIGN (operator, sibling's live state untouched).
6. **AUTONOMOUS_OPS.md**: 37+ days vs its own 30-day recert rule — recertify.

## 5. The perfection plan (4 horizons, accepted by Zero 2026-07-19)

- **H0 (operator GO, prepped)**: password rotation · JWT flip · KG job arming · KTP vault decision
- **H1 (this week)**: verify first scheduled dry-run in Actions · stale-key sweep fleet-wide + `docs/runbooks/secret-rotation.md` · Pro align · AUTONOMOUS_OPS recert · canonical checkout decision for .mcp.json
- **H2 (2-4 weeks)**: armed `--apply` + backlog drain · 118 fuzzy adjudication surface · WR2 per-tier precision via IG metrics (refuter SERIO-5) · token revocation build (S03-S2)
- **H3 (antibodies)**: pre-push migration fresh-schema check · venv-refresh-after-merge hook · DOCSYNC marker for AGENTS.md numbers · `arsenal_probe.py` as session-start ritual

## 6. Restart prompt (next session)

> Read this file + `research/operations/2026-07-18-jwt-expiry-phase2-activation.md` + `research/operations/2026-07-18-kg-staging-promotion-job-design.md`. Campaign S1-S5 is DONE and proven; nothing from it is pending in-flight. Check `gh run list --workflow cron-kg-staging-promotion.yml` for the first scheduled dry-run. Residual operator items in §4. The perfection plan (§5) has Zero's blessing — H1 is the natural next mandate. GLM 5.2 is the refuter seat (DeepSeek dead, removed). Machine rules: M5 = thin client, heavy work via `ssh pro`, no fly/ollama/postgres locally, `fly ssh` needs `/bin/sh -c` and NO `PYTHONPATH=.`.
