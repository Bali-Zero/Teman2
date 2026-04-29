# kakuro-S1 — P0-0 `/health` endpoint classify

> Single-file prompt for one Claude Code Max x20 session.
> Macchina: **Pro** (`nuzantara@Nuzantara`). Worktree: `wt/p0-0-health-classify`.
> Session command: in your tmux pane, simply type:
>
>     leggi kakuro-S1 e esegui
>
> The session reads this file (you can paste path or full content) and proceeds autonomously.

---

## Mission

Implementa **P0-0** dal piano audit zero-crash 2026-04-29: il backend `/health` deve restituire HTTP 503 quando `app.state.startup_failed=True`, e Cell pulse deve classificare la salute sul body status, non solo HTTP code.

Foundation fix — **deve essere fatto prima di tutti gli altri P0** perché senza non si vede se gli altri funzionano.

## Context

- Repo: `/Users/nuzantara/Desktop/nuzantara`, branch `main`
- Audit master: `docs/audits/2026-04-29-zero-crash-audit/`
- Brainstorm dedicato (READ FIRST): [`11_brainstorms/P0-0_health_endpoint_classify.md`](../../11_brainstorms/P0-0_health_endpoint_classify.md)
- Cicatrice STRUCTURAL aperta: `.claude/rules/cicatrix-scars.md` — entry "Backend `/health` masks `app.state.startup_failed` (2026-04-29)"
- 6 libri sacri caricati al SessionStart automaticamente

## Files to touch (3)

1. `apps/backend-rag/backend/app/routers/health.py` — call `_check_startup_failed()` first; warmup deadline
2. `apps/backend-rag/backend/app/setup/app_factory.py` — track `startup_started_at`, `startup_complete`, do NOT raise on critical init failure
3. `apps/cell/cell/core/pulse.py` — classify health on body status, not just HTTP

## Files NOT to touch (off-limits per CLAUDE.md §12)

- `apps/backend-rag/backend/prompts/zantara_core.py`
- `apps/backend-rag/fly.toml`
- `.env.production`
- `apps/backend-rag/backend/alembic/env.py`

## Workflow

### Phase 1 — Cross-LLM brainstorm (START WITH THIS)

Before writing any code, dispatch the implementation question to 4 external LLMs in parallel via the coordination helper. Their analyses must be **independent** (not influenced by Opus opinion).

```bash
cd /Users/nuzantara/Desktop/nuzantara
source docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh

# Build brief (no Opus opinion — just the problem statement)
cat > /tmp/kakuro-S1-brief.txt <<'BRIEF'
You are giving an independent implementation strategy for this problem.

PROBLEM: In Nuzantara monorepo (Python FastAPI backend), the file
apps/backend-rag/backend/app/routers/health.py defines a helper function
_check_startup_failed(app) at lines 48-55 but never calls it from the
main health_check() handler at lines 147-266. As a consequence,
apps/backend-rag/backend/app/setup/app_factory.py:114-118 catches
RuntimeError from critical service init and sets app.state.startup_failed=True,
but /health endpoint keeps returning HTTP 200 with status='healthy'.
Fly.io auto-restart only fires on non-2xx, so a deterministically broken
backend stays "healthy" forever. This caused the 2026-04-29 03:11Z incident
on kita.balizero.com.

Additionally: apps/cell/cell/core/pulse.py classifies health green based
ONLY on (reading.reachable AND reading.status_code == 200). So even if
body says {"status": "startup_failed"}, Cell sees green. Same blind spot
in the organism's own nervous system.

YOUR TASK: Propose an IMPLEMENTATION STRATEGY for fixing both. Be specific:
- Exact code change in health.py to call _check_startup_failed
- Whether to ALSO add a warmup deadline (e.g., if startup takes > 180s, return 503)
- Whether to remove the `raise` in _init_critical_services so uvicorn can bind
  and serve degraded /health (this is graceful degradation per Symbiosis Law 4)
- How Cell pulse should classify body status field semantically
- Test strategy
- Rollback plan
- Edge cases I might miss

Constraints:
- Anthropic SDK is BANNED. Only `claude` CLI with OAuth. DeepSeek API allowed.
- Fly.io auto-restart only on non-2xx /health
- Cell is local on Pro, watches the backend via HTTP
- Backend on Fly has 2 machines (api + rag process groups)
- Symbiosis Law 4: "graceful degradation" means an organ down does not crash the whole organism
BRIEF

# Dispatch 4 LLMs in parallel
mkdir -p /tmp/kakuro-S1-brainstorms
coord_brainstorm "P0-0 /health classify implementation" /tmp/kakuro-S1-brief.txt /tmp/kakuro-S1-brainstorms

# Read all 4 outputs
echo "=== CODEX ==="; head -200 /tmp/kakuro-S1-brainstorms/codex.md
echo "=== GEMINI ==="; head -200 /tmp/kakuro-S1-brainstorms/gemini.md
echo "=== DEEPSEEK ==="; head -200 /tmp/kakuro-S1-brainstorms/deepseek.md
echo "=== NLM ==="; head -200 /tmp/kakuro-S1-brainstorms/notebooklm.md
```

After reading all 4, **synthesize convergent vs divergent points** in 5 bullet points. Then choose your final implementation strategy noting WHICH LLMs supported each decision.

### Phase 2 — Worktree setup

```bash
cd /Users/nuzantara/Desktop/nuzantara
git fetch origin
git worktree add -b feat/p0-0-health-classify ../nuzantara-wt/p0-0 origin/main
cd ../nuzantara-wt/p0-0

# Symlink venv (don't recreate, save 30s)
ln -sf /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv apps/backend-rag/.venv
```

### Phase 3 — TDD

Write the tests FIRST in:
- `apps/backend-rag/backend/tests/app/routers/test_health_startup_failed.py` (3 tests minimum)
- `apps/cell/cell/tests/test_pulse_classify.py` (3 tests minimum)

Run tests → expect failure. Then implement.

### Phase 4 — Implementation

Apply the strategy from Phase 1 synthesis. Each file change:

1. Read current state of file (not the brainstorm proposal — verify line numbers haven't drifted)
2. Edit
3. Run tests → expect pass
4. Run full test suite for those modules:

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/app/routers/test_health_startup_failed.py backend/tests/app/routers/ -q
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q  # smoke regression
```

### Phase 5 — Local end-to-end verification

```bash
cd apps/backend-rag && source .venv/bin/activate
SEARCH_FORCE_FAIL=1 PYTHONPATH=. uvicorn backend.app.main_api:app --port 8001 &
SERVER_PID=$!
sleep 8

# Should return 503 now (was returning 200 before fix)
curl -sI http://localhost:8001/health | head -1
# Expected: HTTP/1.1 503 Service Unavailable

curl -s http://localhost:8001/health | jq
# Expected: status="unhealthy", message contains "startup_failed"

kill $SERVER_PID
```

### Phase 6 — Cell pulse local verification

```bash
cd apps/cell  # may have separate venv
source venv/bin/activate 2>/dev/null || source .venv/bin/activate
PYTHONPATH=. pytest cell/tests/test_pulse_classify.py -v
# Expected: 3/3 tests pass
```

### Phase 7 — Commit + Push + Deploy (COORDINATED)

Use the coordination helpers — they hold locks so multiple sessions don't collide:

```bash
source /Users/nuzantara/Desktop/nuzantara/docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh

cd /Users/nuzantara/Desktop/nuzantara-wt/p0-0

# Stage selectively (do NOT stage venv symlink, brainstorm tmp, etc.)
git add apps/backend-rag/backend/app/routers/health.py
git add apps/backend-rag/backend/app/setup/app_factory.py
git add apps/cell/cell/core/pulse.py
git add apps/backend-rag/backend/tests/app/routers/test_health_startup_failed.py
git add apps/cell/cell/tests/test_pulse_classify.py

# Commit (waits if another session is committing)
coord_commit "fix(p0-0): /health returns 503 on startup_failed; Cell pulse classifies body

P0-0 from zero-crash audit 2026-04-29.

- backend/app/routers/health.py: call _check_startup_failed() at top of
  health_check; return 503 with structured error.
- backend/app/setup/app_factory.py: track startup_started_at, do NOT raise
  on critical init failure (graceful degradation per Symbiosis Law 4).
- cell/core/pulse.py: classify on body status field (unhealthy/startup_failed
  -> red, degraded/initializing -> yellow), not just HTTP code.
- 6 new tests covering: 503 on startup_failed, 503 on warmup timeout,
  200 on normal startup, 3 Cell classification cases.

Cicatrix STRUCTURAL 2026-04-29 'Backend /health masks startup_failed' resolved.
Fly auto-restart now triggers correctly on deterministic startup failures."

# Push (waits if another session is pushing)
coord_push origin feat/p0-0-health-classify

# Open PR (no lock needed — gh handles its own concurrency)
gh pr create --title "fix(p0-0): /health 503 on startup_failed + Cell pulse semantic classify" \
  --body-file <(cat <<EOF
## Summary
- /health returns 503 when app.state.startup_failed=True (was: 200)
- Warmup deadline 180s (was: indefinite "initializing")
- app_factory does not raise on critical init failure → uvicorn binds, serves degraded /health
- Cell pulse classifies on body status field, not just HTTP code

## Test plan
- [x] 6 unit tests added (3 health, 3 cell pulse) — all pass locally
- [x] Local boot with SEARCH_FORCE_FAIL=1 returns 503 (was 200)
- [x] Existing test_confidence.py smoke regression still passes
- [ ] Post-deploy: Fly /health probe returns 200 in steady state
- [ ] Post-deploy: introduce planned failure (cron) and verify 503 + Telegram alert

Cicatrix STRUCTURAL 2026-04-29 resolved.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)

# Auto-merge after CI green
gh pr merge --auto --squash

# Wait for fly-deploy.yml to complete (post-deploy verify)
echo "Waiting for fly-deploy CI..."
PR_NUMBER=$(gh pr view --json number -q .number)
bash /Users/nuzantara/Desktop/nuzantara/scripts/post-deploy-verify.sh $PR_NUMBER

# DEPLOY only if CI green AND post-deploy-verify approves
# (the post-deploy-verify already triggers fly auto-deploy via gh pr merge --auto;
# the coord_deploy_fly is here ONLY if you need a manual re-deploy)
# coord_deploy_fly nuzantara-rag

# Save MOS memory
~/.claude/scripts/mem save decision "P0-0 /health classify completed — PR #$PR_NUMBER merged. Fly /health now 503 on startup_failed. Cell pulse classifies body status. 6 new tests. Cicatrix STRUCTURAL 2026-04-29 resolved." 9
```

### Phase 8 — Cleanup worktree

```bash
cd /Users/nuzantara/Desktop/nuzantara
git worktree remove ../nuzantara-wt/p0-0
```

## Reporting

At end of session, output a single-message summary to the main tmux pane:

```
[kakuro-S1 DONE] P0-0 merged in PR #<num>. Fly deploy <success|fail>.
6 tests added. Cicatrix resolved. Brainstorms saved in /tmp/kakuro-S1-brainstorms.
Next: P0-1 can start (now unblocked).
```

## Failure modes — what to do

- **Brainstorm CLI fails (Codex/Gemini/DeepSeek)**: log the failure, retry once with diagnostic. If second attempt fails, proceed with remaining 3 LLMs. Document in commit message.
- **Tests fail after implementation**: do NOT commit. Diagnose root cause. If you can't fix in 1h, revert worktree and escalate via `mem save unresolved` + Telegram.
- **CI red on PR**: do NOT merge. Read CI logs, fix, push again. Auto-merge will resume when green.
- **`coord_commit` waits >30 min**: another session is stuck. Run `coord_status` to see who holds the lock. If stale (PID gone), break manually: `rm ~/.claude/locks/git-commit.lock`.
- **Off-limits file accidentally edited**: revert that file via `git checkout HEAD -- <file>`. Continue with other files.

## Autonomy boundary

This session operates under AUTONOMOUS_OPS L2. You CAN:
- Open PR, gh pr merge --auto, watch fly-deploy
- Telegram notify on success/failure (hotfix-notify.sh wired)
- Save MOS memory autonomously

You MUST ASK Antonello before:
- Force push, force-with-lease (any branch)
- Reverting an already-merged PR
- Editing off-limits files
- Adding new external service (paid API, new Fly app, new cron)
