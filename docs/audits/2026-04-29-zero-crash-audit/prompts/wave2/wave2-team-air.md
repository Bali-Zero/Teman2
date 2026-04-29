# wave2-team-air — Sessione Air con team agent (3 fix paralleli)

> Single-file prompt for one Claude Code Max x20 (Opus 4.7 max effort) on **Air**.
> Comando di kickoff: `leggi wave2-team-air e esegui`

---

## Mission

Sei l'orchestrator di un team agent `wave2-air`. Lanci 3 sub-agent paralleli, ognuno gestisce 1 fix end-to-end (brainstorm → worktree → TDD → commit → PR → merge → deploy → verify).

**Fix assegnati a Sessione 3 (Air):**

| Agent | Fix | Effort | File principali |
|---|---|---|---|
| **agent-X** | **P0-5 fase 1** httpx audit only | 2h | rg + report. NO rewrite (= fase 2). |
| **agent-Y** | **P1-7** NLM auto-recovery | 4h | ~/scripts/system_doctor.py extension |
| **agent-Z** | **P1-10** i18n provider per route group lint | 4h | scripts/lint_i18n_providers.sh + GH workflow |

**Sessione 1 (Pro mia)** sta lavorando su P0-1, NB-A, P1-11.
**Sessione 2 (Pro tua)** sta lavorando su P0-2 fase 1, P1-8, NB-D.

Total: 9 worker concurrent. Coordinamento via lock files (`~/.claude/locks/` su Pro, fortunatamente filesystem-shared via federation o ssh). 

> ⚠️ Nota Air: i lock files `~/.claude/locks/` su Air sono local Air-side. Ogni macchina ha i suoi.
> Per coordinamento Pro+Air su gh push/merge: gh API è transactional su GitHub side, due `gh push` simultanei sullo stesso branch sarebbero bloccati comunque dal remote. Lock files prevengono race su STESSA macchina.

## Air setup notes

- Repo path: `/Users/antonellosiano/Projects/nuzantara`
- Venv path: `apps/backend-rag/venv` (NOT `.venv`!)
- gh auth Air: probabilmente scaduto. Pattern preesistente (memoria 2026-04-21): se gh auth Air fail, usa `ssh pro 'gh ...'` come fallback automatico. NON chiedere ad Antonello di fare auth.
- Memory `pattern_antonello_non_dev_2026_04_29`: NON chiedere ad Antonello azioni shell. Ogni problema → escala via shared/escalations_air.jsonl o Telegram, OR usa fallback ssh pro.

## Setup orchestrator

```bash
cd ~/Projects/nuzantara

# Sync da origin
git fetch origin && git checkout main && git pull origin main 2>&1 | tail -3

# Coordination helpers
source docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh
coord_status

# Verify gh auth (likely fail on Air)
gh auth status 2>&1 | head -5
# If fail: tutti i `gh` commands degli agent devono usare 'ssh pro "gh ..."' wrapper
```

## Pattern uniforme per ogni agent del team (idem wave2-team-pro)

1. **Brainstorm cross-LLM** (Codex + Gemini + DeepSeek + NotebookLM) via `coord_brainstorm`. NO Opus seed.
2. **Worktree isolato** `git worktree add -b feat/<fix> ../nuzantara-wt/<fix> origin/main` (Air path: `~/Projects/nuzantara-wt/...`)
3. **TDD**: tests prima
4. **Self-review** prima di commit
5. **Coord commit + push + PR** (se gh Air fail: `ssh pro 'cd ~/Desktop/nuzantara && gh pr create ...'`)
6. **Watch CI + deploy** + **verify deploy success**
7. **MOS save** + worktree cleanup
8. **Report DONE solo dopo step 7 verificato**

## Brief per ogni agent

### agent-X — P0-5 fase 1 httpx audit only

```
Implementa P0-5 fase 1 SOLO AUDIT (no rewrite) dal piano audit zero-crash 2026-04-29.

Riferimento: docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/P0-5_httpx_dependencies_audit.md

PROBLEMA: Golden Rule #10 violations (httpx.AsyncClient instantiated in method bodies / loops, leaking sockets).
Stima: 50-200 callsites in apps/backend-rag/backend/.

FASE 1 SCOPE: SOLO AUDIT.
- Identifica tutti i callsites violatori
- Genera report markdown classificato (module-scope, function-body, loop-body, async-with-context)
- NESSUN rewrite. La fase 2 (rewrite) aspetta che P0-1 sia in main per evitare conflict su dependencies.py.

Files to touch:
1. scripts/audit_httpx_violations.sh (NEW) — rg + classification + report
2. docs/audits/2026-04-29-zero-crash-audit/p0-5-httpx-audit-report.md (NEW) — output

Brief per cross-LLM brainstorm:
"PROBLEM: ~50-200 httpx.AsyncClient() instantiations in apps/backend-rag/backend/, mostly violating Golden Rule #10
(persistent client must live module-scope with lifespan close, not per-request).
TASK: Design audit script that:
1. rg --type py 'httpx.AsyncClient(' apps/backend-rag/backend/
2. Filter via context: exclude legitimate `async with httpx.AsyncClient()` blocks (auto-close OK)
3. Classify each match: module-scope-singleton (OK), function-body (VIOLATION), loop-body (CRITICAL),
   test-fixture (OK if scoped properly)
4. Output report markdown with file:line + classification + suggested fix
5. NO rewrite — only inventory.

CONSTRAINTS: report must be deterministic (sort by filename); script idempotent."

Worktree: feat/p0-5-httpx-audit (Air worktree: ~/Projects/nuzantara-wt/p0-5)

Test plan: run audit on current main, verify report classification on at least 5 known violators.

PR: small (only script + report).

Watch deploy: questo PR non deploya backend (no code change). Solo CI ruff/lint check.

Report DONE quando PR merged + audit report committed in repo (visible in main).
```

### agent-Y — P1-7 NLM auto-recovery

```
Implementa P1-7 dal piano audit zero-crash 2026-04-29.

Riferimento: docs/audits/2026-04-29-zero-crash-audit/09_intervention_plan.md sezione P1-7.

PROBLEMA: 5 NLM pipelines in DLQ persistente (nlm_nb1_daily_refresh, nlm_nb6_ops_compliance,
nlm_nb7_editorial, nlm_nb8_expat_life, weekly_report). 8/9 NB pipelines exit in 3-5ms (openclaw
dispatcher bug). claim_extractor.py:216 blocks NB-2 on CB_NLM=OPEN.
Memory: discovery_2026_04_24 + audit memoria.

TASK: ~/scripts/system_doctor.py extension che:
1. Detect pipelines stuck >24h (state file last_success_ts age)
2. Tenta auto-rerun per ognuna
3. Telegram alert SOLO se rerun fail (non spam)

Files to touch:
1. ~/scripts/system_doctor.py (extension function check_nlm_pipelines_stuck())

Brief per cross-LLM brainstorm:
"PROBLEM: 5 NLM pipelines stuck >24h, no auto-recovery, Telegram-only after manual triage.
state_dir: Path.home() / '.agent/decisions/state' has <pipeline>.json with last_success_ts.
TASK: Function check_nlm_pipelines_stuck() called by system_doctor.py cron 08:00:
1. Walk state_dir for nlm_*.json
2. age_hours = (now - last_success_ts) / 3600
3. If age_hours > 24: subprocess.run(python -m apps.evaluator.nlm_deep_research.<pipeline> --retry, timeout=300)
4. If rerun.returncode != 0: send_telegram_warning(<pipeline>, age, stderr)
5. Return list of stuck/recovered/failed for system_doctor summary report.
CONSTRAINTS: subprocess timeout 300s; non blocchi cron run; idempotent (rerunning healthy pipeline = no-op)."

Worktree: feat/p1-7-nlm-auto-recovery (Air, ~/Projects/nuzantara-wt/p1-7)

Test plan:
- Plant synthetic stuck state file (last_success_ts = 0)
- Run system_doctor --check-nlm
- Verify rerun attempted + result classified

Watch deploy: questo non è backend-rag deploy, è local script Pro (Air doesn't have system_doctor.py).
NB: file fisico è in ~/scripts/ su Pro, ma agent Y può comunque modificarlo VIA ssh pro IF gh auth funziona,
OR può aprire PR nel repo dove va committato come scripts/system_doctor.py shared (verifica se esiste in repo).

Report DONE quando:
- PR merged (se va in repo) OR fix in place su Pro via ssh
- Synthetic test passes
- system_doctor cron prossima esecuzione 08:00 testimonia auto-recovery works
```

### agent-Z — P1-10 i18n provider per route group lint

```
Implementa P1-10 dal piano audit zero-crash 2026-04-29.

Riferimento: docs/audits/2026-04-29-zero-crash-audit/09_intervention_plan.md sezione P1-10.

PROBLEMA: PR #273 white-screen pattern. Adding useTranslation() to component without ancestor
<I18nProvider> causes throw → unmount → white screen. Nessun lint preemptive.

TASK: AST-based CI lint script + GH Actions workflow.

Files to touch:
1. scripts/lint_i18n_providers.sh (NEW) — bash + grep semplice
2. .github/workflows/lint-i18n-providers.yml (NEW) — CI gate

Brief per cross-LLM brainstorm:
"PROBLEM: apps/mouth/src/app/ has 4+ route groups (workspace, blog, book, portal).
Each has layout.tsx. Some import I18nProvider, some don't. If a descendant component imports
useTranslation() and ancestor layout doesn't have <I18nProvider>, runtime throw → white screen.
Pattern PR #273 (memory lesson 2026-04-27).
TASK: Lint script (bash, no AST parser needed):
1. For each route group dir apps/mouth/src/app/(*)/, check layout.tsx
2. has_provider=$(grep -l 'I18nProvider' layout.tsx)
3. descendants_use=$(rg -l 'useTranslation()' inside that route group dir)
4. If descendants_use AND NOT has_provider: VIOLATION
5. Exit 1 if any violation; output file:line for each
+ GH workflow runs on PR touching apps/mouth/src/app/.
CONSTRAINTS: false positives 0 (don't flag if useTranslation() is imported only as type, not called);
script <5s on full mouth/."

Worktree: feat/p1-10-i18n-lint (Air, ~/Projects/nuzantara-wt/p1-10)

Test plan:
- Run lint on current main → exit 0
- Plant synthetic violation (useTranslation in (workspace) without provider) → exit 1
- Revert plant → exit 0
- CI workflow validates same logic

Watch CI: questo PR è frontend only. CI gate is the new workflow + Vercel preview build.

Report DONE quando:
- PR merged
- Synthetic violation triggers CI fail (verified via test PR or local exec)
- Real apps/mouth/ passes
```

## Workflow tu (orchestrator Air)

```python
# 1. Verify state Air
# - main aggiornato a origin/main commit corrente
# - venv venv (NOT .venv)
# - lock files Air-local empty (lock cross-machine non c'è, gh API è remote-transactional comunque)

# 2. Lancia team
Agent(
  team_name="wave2-air",
  name="agent-X",
  prompt="<brief P0-5 audit sopra>",
  subagent_type="general-purpose"
)
Agent(
  team_name="wave2-air",
  name="agent-Y",
  prompt="<brief P1-7 sopra>",
  subagent_type="general-purpose"
)
Agent(
  team_name="wave2-air",
  name="agent-Z",
  prompt="<brief P1-10 sopra>",
  subagent_type="general-purpose"
)

# 3. Monitor + report
```

## Failure modes specifici Air

- **gh auth fail**: tutti gli agent hanno `ssh pro 'gh ...'` come fallback. Memory pattern saved.
- **venv path confusion**: ricordare `apps/backend-rag/venv` non `.venv`.
- **Pull/push race con Pro**: gh API è transactional su GitHub side. Due push simultanei sullo stesso branch falliscono. Branch nomi distinti per agent X, Y, Z preventono.
- **Network blip Air**: tutti gli agent retry idempotente.

## Reporting

```
[wave2-team-air DONE]
- agent-X (P0-5 audit): PR #<num> merged, audit report in repo
- agent-Y (P1-7 NLM): PR #<num> merged + system_doctor cron tested
- agent-Z (P1-10 i18n): PR #<num> merged, lint workflow active
- 0 blocker
- Brainstorms in /tmp/wave2-air-brainstorms
```

## L2 autonomy

Tutti L2. Escala solo:
- Off-limits file editato
- gh auth Pro fail E ssh pro fail E gh auth Air fail simultaneamente (= unable to PR)
- Conflict su origin/main commit di Wave 2 Pro mentre tu stavi pushando
- Real production /health drop

## Pre-flight checklist Air

- [ ] `whoami` = `antonellosiano` (= sei su Air)
- [ ] `cd ~/Projects/nuzantara` = repo path corretto
- [ ] `git fetch origin && git checkout main && git pull origin main` aggiornato
- [ ] `gh auth status` (verifica, accetta failed)
- [ ] `ssh pro 'gh auth status'` (fallback verificato)
- [ ] Sessione 1 (Pro mia) ha lanciato i suoi agent (verifica non si sovrappongano per file/branch)
- [ ] Sessione 2 (Pro tua) ha lanciato i suoi agent (NON c'è conflitto di file: P0-2/P1-8/NB-D vs Air P0-5/P1-7/P1-10 — distinct namespaces)

Se tutto verde: lancia Agent x3.
