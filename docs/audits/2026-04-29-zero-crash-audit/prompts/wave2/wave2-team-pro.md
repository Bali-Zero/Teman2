# wave2-team-pro — Sessione Pro con team agent (3 fix paralleli)

> Single-file prompt for one Claude Code Max x20 (Opus 4.7 max effort) on **Pro**.
> Comando di kickoff: `leggi wave2-team-pro e esegui`

---

## Mission

Sei l'orchestrator di un team agent `wave2-pro`. Lanci 3 sub-agent paralleli, ognuno gestisce 1 fix end-to-end (brainstorm → worktree → TDD → commit → PR → merge → deploy → verify). Tu coordini, monitori i lock condivisi, riporti progresso.

**Fix assegnati a Sessione 2 (Pro):**

| Agent | Fix | Effort | File principali |
|---|---|---|---|
| **agent-X** | **P0-2 fase 1** Outbox foundation | 1 giorno | migration 144, services/events/outbox.py, EventBus reconnect |
| **agent-Y** | **P1-8** escalations.jsonl → SQLite | 1 giorno | scripts/migrate_escalations_to_sqlite.py + cron prune |
| **agent-Z** | **NB-D** Vercel monorepo cross-import lint | 6h | .github/workflows/lint-cross-import.yml + pre-deploy gate |

**Sessione 1 (questa, mia)** sta lavorando su P0-1, NB-A, P1-11 in parallelo.
**Sessione 3 (Air)** sta lavorando su P0-5 fase 1, P1-7, P1-10 in parallelo.

Total: 9 worker concurrent. Coordinamento via lock files `~/.claude/locks/` (vedi `_coordination.sh` da Wave 1).

## Setup orchestrator

```bash
cd /Users/nuzantara/Desktop/nuzantara
source docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh

# Verify locks exist
coord_status

# Create team
# (uso di Agent tool con team_name="wave2-pro")
```

## Pattern uniforme per ogni agent del team

Ogni sub-agent che lanci deve:

1. **Brainstorm cross-LLM (BLOCKING)** — Codex GPT-5.5 + Gemini 3.1 Pro + DeepSeek v4-pro + NotebookLM NB-1 in parallelo via `coord_brainstorm`. Brief NON deve contenere opinion (no Opus seed). Sintetizza convergenze + divergenze prima di scrivere codice.

2. **Worktree isolato** `git worktree add -b feat/<fix> ../nuzantara-wt/<fix> origin/main`. Symlink venv: `ln -sf .../apps/backend-rag/.venv apps/backend-rag/.venv`.

3. **TDD**: scrivere tests PRIMA, verificare fail, implementare, verificare pass.

4. **Self-review** prima di commit: re-read diff, verifica contro brainstorm sintesi, controllo regressioni (smoke test su test esistenti).

5. **Coord commit + push + PR**:
   ```bash
   source /Users/nuzantara/Desktop/nuzantara/docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh
   coord_commit "feat(<id>): <subject>" <files>
   coord_push origin <branch>
   gh pr create --title "..." --body "..."
   gh pr merge --auto --squash
   ```

6. **Watch CI + deploy**:
   ```bash
   PR=$(gh pr view --json number -q .number)
   gh pr checks $PR --watch
   # When merged, watch deploy
   gh run watch $(gh run list --workflow="Deploy Backend to Fly.io" --limit 1 --json databaseId -q '.[0].databaseId')
   ```

7. **Verify deploy SUCCESS**:
   ```bash
   curl -sI https://nuzantara-rag.fly.dev/health | head -1   # Expected: HTTP/1.1 200
   curl -s https://nuzantara-rag.fly.dev/health | jq '.status'  # Expected: "healthy"
   ```
   Per fix DB: `fly ssh console -a nuzantara-rag --machine d894e65bede478 -C "..."` per verificare schema.

8. **MOS save** + cicatrix update + worktree cleanup.

9. **Reporta DONE solo dopo step 8 verificato.**

Il pattern è quello di Wave 1, NON è da inventare. Se un agent termina senza deploy verify, è KO.

## Brief per ogni agent

### agent-X — P0-2 fase 1 Outbox foundation

```
Implementa P0-2 fase 1 dal piano audit zero-crash 2026-04-29.

Brainstorm dedicato (READ FIRST): docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/P0-2_eventbus_outbox_pattern.md

Cicatrix STRUCTURAL aperta: .claude/rules/cicatrix-scars.md entry "EventBus is PG LISTEN/NOTIFY but Symbiosis docs say Redis Streams (2026-04-29)"

Reference impl esistente: apps/backend-rag/backend/services/bridge/outbox.py (Pro/Air bridge usa già Outbox per i propri eventi — generalizzane)

FASE 1 SCOPE: solo foundation. NON refactor dei pg_notify callsite esistenti (= fase 2, separato).

Files to touch (4):
1. apps/backend-rag/backend/db/migrations_v2/144_events_outbox.sql (NEW)
2. apps/backend-rag/backend/services/events/outbox.py (NEW)
3. apps/backend-rag/backend/services/events/__init__.py (extend EventBus replay-on-reconnect)
4. apps/backend-rag/backend/tests/services/events/test_outbox.py (NEW, 5 tests min)

OFF-LIMITS: zantara_core.py, fly.toml, .env*, alembic/env.py.

Brief per cross-LLM brainstorm (NO Opus opinion):
"PROBLEM: EventBus uses PG LISTEN/NOTIFY (NOT Redis Streams as Symbiosis.md docs claim).
When PG listener disconnects, every NOTIFY published in 5s reconnect window is silently lost
(pg_notify is volatile, no queue).
TASK: Design Outbox Pattern foundation: SQL migration table events_outbox + Python helper
publish/acknowledge/replay_unconsumed + EventBus reconnect handler calls replay
+ pruning policy (consumed >30 days deleted) + 5+ tests covering atomicity, replay,
ack idempotency, max_age filter.
Reference existing impl: services/bridge/outbox.py.
CONSTRAINTS: migration must have rollback section; pg_notify channel sanitized
via pg_quote_ident; consumers safe to re-process via _outbox_id idempotency check;
no callsite refactor in this PR."

Test plan: 5 unit tests + apply-all dry-run + smoke test_confidence.py.

Watch deploy + verify migration 144 applied via fly ssh.

Report DONE solo dopo deploy verificato e migration in _schema_versions.
```

### agent-Y — P1-8 escalations SQLite migration

```
Implementa P1-8 dal piano audit zero-crash 2026-04-29.

Riferimento: docs/audits/2026-04-29-zero-crash-audit/09_intervention_plan.md sezione P1-8.

PROBLEMA: shared/escalations_pro.jsonl ha 7404 lines pending (file append-only since inception, no rotation, no dedup, no consumer).
Disk grow unbounded. Performance walls quando un consumer cerca di parsare.

TASK: Migrate to SQLite con retention.

Files to touch (3):
1. scripts/migrate_escalations_to_sqlite.py (NEW)
2. ~/Library/LaunchAgents/com.nuzantara.escalations-prune.plist (NEW)
3. Update writers (dlq_autopilot.py and similar) per INSERT OR REPLACE INTO sqlite

Brief per cross-LLM brainstorm (NO Opus opinion):
"PROBLEM: shared/escalations_{pro,air}.jsonl 7404 lines pending. Append-only.
TASK: Migrate to SQLite tables (audit_id PK, job, type, severity, machine, created_at, resolved_at, raw_json),
indexed on (resolved_at IS NULL) for active queries. Cron daily 03:00 prunes resolved >30 days,
archives non-resolved >90 days. UPDATE writers (dlq_autopilot.py + maybe sentinel) per
INSERT OR REPLACE invece di append jsonl.
CONSTRAINTS: backward compatible (existing jsonl preserved as immutable archive);
no data loss durante migration; SQLite file in ~/.agent/decisions/escalations.sqlite."

Worktree: feat/p1-8-escalations-sqlite

Test plan:
- Migration script imports current jsonl into SQLite without dup
- Cron run prune drops resolved >30d
- New escalations land in SQLite via writer

Watch + verify post-deploy: ls -lah ~/.agent/decisions/escalations.sqlite (esiste e cresce normalmente, non file 0-byte).

Report DONE solo dopo verify.
```

### agent-Z — NB-D Vercel monorepo cross-import lint

```
Implementa NB-D dal piano audit zero-crash 2026-04-29.

Riferimento: docs/audits/2026-04-29-zero-crash-audit/09_intervention_plan.md sezione NB-D.

PROBLEMA: Se un'app satellite (apps/web, apps/admin-dashboard, ecc.) importa un workspace package che si rompe (es. via package.json broken peer dep), l'intero monorepo deploy Vercel fallisce.
Pre-deploy gate non controlla cross-import integrity.

TASK: Pre-deploy CI lint che verifica package.json integrity + workspace dependency resolution.

Files to touch (1-2):
1. .github/workflows/lint-cross-import.yml (NEW)
2. (Optional) scripts/lint_cross_import.sh (helper if logic is complex)

Brief per cross-LLM brainstorm (NO Opus opinion):
"PROBLEM: Vercel monorepo has 21 apps. If apps/X imports @nuzantara/some-package and that package's
peer-dep is broken, vercel build of apps/Y also breaks. Pre-deploy gate doesn't lint this.
TASK: Design CI workflow lint-cross-import.yml that:
1. For each apps/X, run `npm ls --workspaces` and check no UNMET peer / extraneous warnings
2. Verify package.json valid JSON in all apps + packages
3. Detect circular workspace imports (if any package depends on apps/X)
4. Fail PR if violations found.
CONSTRAINTS: tempo workflow < 2 min; non rompere current vercel build; ESLint compatible."

Worktree: feat/nb-d-vercel-cross-import-lint

Test plan:
- Plant a synthetic broken package.json in apps/web → CI fails
- Revert → CI passes
- Real apps verified clean via local run

Watch CI on the synthetic test. Verify gate triggers.

Report DONE quando workflow attivo + canary synthetic verified.
```

## Workflow tu (orchestrator)

```python
# Pseudo-code di quello che fai

# 1. Verify state
# - origin/main HEAD coerente con Wave 1 finale
# - 9 worker totali (3 mio + 3 tuo + 3 air-tuo) — verifica via gh pr list che non ci siano PR conflitto
# - lock files vuoti

# 2. Lancia il team con team_name="wave2-pro"
Agent(
  team_name="wave2-pro",
  name="agent-X",
  prompt="<brief P0-2 fase 1 sopra>",
  subagent_type="general-purpose"
)
Agent(
  team_name="wave2-pro",
  name="agent-Y",
  prompt="<brief P1-8 sopra>",
  subagent_type="general-purpose"
)
Agent(
  team_name="wave2-pro",
  name="agent-Z",
  prompt="<brief NB-D sopra>",
  subagent_type="general-purpose"
)

# 3. Ognuno parte in parallelo. I 3 condividono il team scratchpad
# (per "io ho il git-commit lock" / "ho aperto PR #XXX") e i lock files di disco.

# 4. Quando uno finisce: ricevi notification, verify, report ad Antonello.
# 5. Se uno blocca: SendMessage all'agent in difficoltà per debug, OR escalate.
```

## Failure modes per orchestrator

- **Agent X (P0-2) trova bug nei reference (services/bridge/outbox.py)**: SendMessage X "puoi proporre fix in stesso PR o spinoff?". Decide tu.
- **Agent Y (P1-8) chiede schema specifico**: rispondigli che schema è suo da designare basato su brainstorm sintesi.
- **Agent Z (NB-D) trova package.json broken in main**: stop work, escalate ad Antonello (è broken state preesistente, fuori scope NB-D).
- **Lock stuck >30min**: `coord_status`, break manualmente solo se PID dead.
- **Race su migration number**: 144 è next disponibile (S3 ha preso 142+143). Se altro agent sceglie 144 ANCHE, conflitto di file. Coord brief brain dice "144 è preso da P0-2".
- **Sessione 1 (mia) è ancora running**: agent X può finire prima — OK. Se PR #X dipende da PR #1 (improbabile), check via team scratchpad.

## Reporting

A fine sessione (quando tutti 3 agent done):
```
[wave2-team-pro DONE]
- agent-X (P0-2 fase 1): PR #<num> merged, deploy verified, migration 144 applied
- agent-Y (P1-8): PR #<num> merged, SQLite escalations file populated
- agent-Z (NB-D): PR #<num> merged, CI lint-cross-import canary green
- 0 blocker
- Brainstorms saved in /tmp/kakuro-S{X,Y,Z}-brainstorms
```

## L2 autonomy

Tutti i 3 agent operano L2 autonomous. Tu come orchestrator escali a Antonello via Telegram solo se:
- Off-limits file accidentally edited
- Production health drops sotto 95% durante deploy
- Una PR resta CI red >2h senza che l'agent reagisca
- Schema migration causes data loss risk

Nel resto: procedi.

## Pre-flight checklist prima di lanciare il team

- [ ] `coord_status` → lock files vuoti
- [ ] origin/main HEAD coerente (`git fetch && git log origin/main -1`)
- [ ] gh auth status Pro funziona (`gh auth status`)
- [ ] Wave 1 effettivamente chiusa (verifica `gh pr list --state open --search "head:feat/p0-"` returns []`)
- [ ] Sessione 1 (mia) ha già lanciato i suoi 3 agent (chiediti via team-mio scratchpad o via tmux/Slack)

Se tutto verde: lancia Agent x3.
