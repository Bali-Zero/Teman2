---
date: 2026-05-25
domain: operations
client_case: nuzantara-internal
sources:
  - research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md
  - feat/agent-worktree-broker-2026-05-24:scripts/agent_start.py (710 LOC)
  - feat/redis-lease-registry-2026-05-24:scripts/agent_lease.py (568 LOC)
  - feat/redis-lease-registry-2026-05-24:.husky/pre-commit
  - feat/merge-queue-rulesets-2026-05-24:scripts/setup_merge_queue_rulesets.sh
  - feat/merge-queue-rulesets-2026-05-24:.github/CODEOWNERS
  - feat/repomap-cron-branch-cleanup-2026-05-24:* (L4 — non letto in dettaglio)
  - .claude/rules/cicatrix-scars.md (52 active + 7 archive)
panel_previous:
  - gemini-3.1-pro-preview
  - gpt-5.5-codex
  - deepseek-v4-pro
  - claude-opus-4-7
empirical_state_2026_05_25_0800_wita:
  - claude_processes_alive: 5
  - codex_processes_alive: 2
  - all_in_shared_main_checkout: true
  - stash_sibling_orphan_24h: 32
  - branches_local_total: 188
  - branches_recent_7d: 20
  - prs_sota_drafted_unmerged: 4 (#851 #852 #853 #854)
  - hours_since_sota_drafted: 13
---

# SOTA Workflow Gap Analysis + L5 Spec (Nuzantara AI Agent Workflow End-to-End)

> **Discovery 2026-05-25 08:00 WITA**: SOTA L1+L2+L3+L4 sono già stati shipped come PR draft 13h fa
> dal precedente Claude Opus (4-LLM panel convergente). Nessuno dei 4 PR è mergiato.
> Gli stash sibling-orphan continuano ad accumularsi (32 in 24h) perché il main checkout
> resta condiviso tra 7 processi AI attivi senza isolation enforcement attivo.

## 1. Cosa coprono L1-L4 (riassunto)

| Layer  | Componente                              | File chiave                                                                                                   | Cosa fa                                                                                                                                                                                  | Kill switch                                              |
| ------ | --------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| **L1** | Worktree broker                         | `scripts/agent_start.py` (710 LOC)                                                                            | Crea `.worktrees/<lane>-<task-id>/` per ogni session agent. Lane allowlist, TTL, WIP-safe cleanup, symlink venv/.env. Branch pattern `agent/<host>/<lane>/<task-id>`.                    | `AGENT_BROKER_ENABLED=false`                             |
| **L2** | Redis lease registry                    | `scripts/agent_lease.py` (568 LOC) + `.husky/pre-commit`                                                      | SET NX EX atomic per hot-zone path. Audit JSONL `~/.agent/leases.jsonl`. Graceful degradation Redis-down. Heartbeat extension + token-owned release.                                     | `AGENT_LEASE_ENFORCEMENT=false`                          |
| **L3** | GitHub merge queue + risk-path rulesets | `scripts/setup_merge_queue_rulesets.sh` + `.github/CODEOWNERS` + `.github/workflows/auto-merge-whitelist.yml` | Auto-merge whitelist (`docs/auto-sync-*`, `dependabot/*`, `chore/fmt-*`). CODEOWNERS Tier 1 paths: `/.github/workflows/`, `fly.toml`, `migrations_v2/`, `auth/`, `billing/`, `pricing/`. | `gh api -X DELETE` rollback                              |
| **L4** | Aider repomap cron + branch cleanup     | `scripts/build_repomap.sh` + cron 15min plist + SessionStart hook + `scripts/branch_graveyard_cleanup.sh`     | Tree-sitter repomap injected at SessionStart (5k token). Branch graveyard cleanup merged stale branches >30gg.                                                                           | `REPOMAP_ENABLED=false` + `BRANCH_CLEANUP_ENABLED=false` |

## 2. Gap Analysis — cosa NON coprono L1-L4

### Gap G1 — Adoption enforcement (P0 CRITICO)

L1+L2+L3+L4 sono **opt-in**. Niente forza un agent dispatch a invocare `agent_start.py`.

**Sintomo empirico 2026-05-25**: 5 Claude + 2 Codex attivi, **tutti su `/Users/nuzantara/Desktop/nuzantara`** main checkout. Zero usano `agent_start.py`. 32 stash sibling-orphan in 24h.

**Causa root**:

- CLAUDE.md L1-branch AGGIUNGE `## Agent Worktree Discipline` ma è solo documentazione descrittiva
- Nessun hook PreToolUse blocca `git checkout` / `git stash` nel main checkout
- Nessun hook SessionStart che AUTO-DISPATCH `agent_start.py` se cwd == main
- AGENTS.md (per Codex) NON è aggiornato — Codex continua a lavorare su main

**Mitigazione minima richiesta**:

1. Hook PreToolUse `worktree_isolation.py` (mirror `stop_verify.py` pattern T2.6): se `cwd == REPO_ROOT` AND tool=`Bash` AND command matches `git (checkout|stash|reset|merge)` → BLOCK con messaggio "use agent_start.py first".
2. Hook SessionStart `agent_workspace_setup.py`: se `cwd == REPO_ROOT` AND running as agent (Claude Code / Codex CLI detectable via env) → propose worktree create.
3. Skill `agent-session-discipline` invocabile via `/agent-start <lane> <task-id>` che incapsula `agent_start.py` + cd output.
4. AGENTS.md update parallelo a CLAUDE.md.

### Gap G2 — Cross-LLM worktree contract (P1)

L1 funziona per Claude Code. Codex CLI e Gemini agy CLI **NON conoscono** `agent_start.py`. Quando invocati da `codex exec` o `agy -p`, partono in main checkout e mutano files lì.

**Empirico**: 2 Codex processes attivi adesso con `cwd = /Users/nuzantara/Desktop/nuzantara`. Branch `codex-overnight/spark-alarm-*` (5 branch ultimi 24h) sono autori `Claude Opus` ma da spawn `codex exec`.

**Mitigazione**:

1. Wrapper `~/scripts/codex-spawn.sh` che fa `agent_start.py --lane codex --task-id <auto>` prima di `codex exec`, poi exec dentro worktree.
2. Wrapper analogo `~/scripts/agy-spawn.sh` per Gemini agy.
3. LaunchAgent che invocano Codex/Gemini devono usare i wrapper.

### Gap G3 — Sub-agent dispatch isolation (P1)

Quando Claude Code dispatcha un sub-agent via `Agent(subagent_type=X)`, il sub-agent eredita il working_dir del parent. Se il parent è su main checkout, il sub-agent lo è anche.

**Empirico**: 32 stash includono diversi "wave 3 team agent" sibling-orphan = sub-agent dispatched durante una wave che hanno scritto nel main checkout del parent.

**Mitigazione**:

1. Agent definitions YAML aggiungono `worktree_required: true` flag
2. Pre-dispatch validation: parent crea worktree via L1 prima del dispatch, passa path al sub-agent come env var
3. Sub-agent runtime SessionStart legge env e cd nel worktree assegnato

### Gap G4 — Workflow lifecycle end-to-end (P2)

L1-L4 coprono **isolation + merge gates**. Mancano fasi del lifecycle:

| Fase richiesta da Antonello                                  | L1-L4 coverage                                            | Gap                                                                                             |
| ------------------------------------------------------------ | --------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 1. Studio (read existing + memory + cicatrix)                | ❌                                                        | Manca skill `session-study` con checklist (mem recent + cicatrix grep + INDEX.md scan)          |
| 2. Pianificazione (Plan tool + 4-LLM panel se architectural) | ⚠️ parziale (CLAUDE.md menziona Federation Orchestrator)  | Manca trigger automatico 4-LLM panel su `architectural=true` lane                               |
| 3. Implementazione                                           | ✅ via L1 worktree                                        | OK                                                                                              |
| 4. Test (pytest scope + lint)                                | ❌                                                        | Manca pre-commit + pre-push lint completo (lock_step W41/W42 esistono ma non per nuova feature) |
| 5. Logging (research capture + memory save)                  | ❌                                                        | Manca skill `session-logging` che append research/operations/ + memory save type/importance     |
| 6. Commit (atomic + co-author + convention)                  | ⚠️ husky pre-commit verifica secrets/print, no convention | Manca lint commit message Conventional Commits                                                  |
| 7. Push (branch dedicato)                                    | ✅ via L1 branch pattern                                  | OK                                                                                              |
| 8. Merge (PR + CI gate + review)                             | ✅ via L3                                                 | OK                                                                                              |
| 9. Deploy (Fly rolling)                                      | ⚠️ esiste runbook scripts/post-deploy-verify.sh           | Manca pre-deploy gate "fly preflight" obbligatorio                                              |
| 10. Post-deploy verify (curl + screenshot + log-tail)        | ⚠️ esiste post-deploy-verify.sh                           | Manca skill `post-deploy-verify` invocabile + Telegram alert su fail                            |
| 11. Cleanup (stash drop + worktree gc + memory archive)      | ⚠️ L1 `--cleanup` + L4 branch graveyard                   | Manca cleanup orchestrator che chiude TUTTO con 1 comando                                       |
| 12. Pulizia infinita (Reflexion weekly)                      | ❌                                                        | Manca cron Sunday che misura adoption + violazioni + propone amendments                         |

### Gap G5 — Observability adoption metric (P1)

Nessun modo di sapere "quanti agenti rispettano L1-L4 vs quanti bypassano". Senza metric, Reflexion non può proporre amendments.

**Mitigazione**:

1. Cron daily 09:00 WITA: `scripts/audit_workflow_adoption.sh` legge:
   - `~/.agent/decisions/agent_starts.jsonl` (audit da L1)
   - `~/.agent/leases.jsonl` (audit da L2)
   - `git log --since 24h` con autore + branch pattern (agent/\* vs main direct)
   - `git stash list` count (delta vs yesterday)
2. Emit metric JSON in `~/.agent/decisions/workflow_adoption.jsonl`
3. Telegram alert se ratio (agent-isolated commit / total commit) < 80%
4. Reflexion weekly Sunday 02:00 WITA legge 7gg di metric e propone amendments

### Gap G6 — Hot-zone regex incompleto (P2)

L2 husky pre-commit ha questo hot-zone regex:

```
^(infra/launchagents/.*\.sh
 |apps/backend-rag/backend/db/migrations_v2/.*\.sql
 |shared/escalations.*\.jsonl
 |scripts/(nuzantara-sentinel|dlq_autopilot|pg-to-organism-bridge)\.py
 |\.github/workflows/.*
 |apps/backend-rag/backend/services/(auth|billing|pricing)/.*)$
```

Mancano hot-zone identificate empirical 2026-05-25:

- `~/Library/LaunchAgents/com.{balizero,nuzantara,cell,matagaruda,garuda}*.plist` (169 file, cicatrix W50/W51/W52)
- `research/operations/**/*.md` (research synthesis perduta come untracked 2026-05-24, ironicamente)
- `~/.claude/hooks/*.py` (config global)
- `~/.claude/skills/**/*.md` (skill library)
- `apps/wr2/**` e `apps/wr3/**` (orchestrator critical path)
- `apps/backend-rag/backend/services/integrations/*.py` (drive + email)
- `~/.codex/**` e `~/.gemini/**` (cross-LLM identity state)

**Mitigazione**: Phase 4 amendment a L2 regex + lease check pre-write tool (non solo pre-commit).

### Gap G7 — Recovery procedures per scenari edge (P2)

L1+L2 hanno --force flags ma manca runbook standardizzato per:

- Worktree corrupt (clone parziale, fs error)
- Lease holder process dead ma Redis non lo sa (TTL non ancora expired)
- Branch già esiste con stesso nome ma da agent precedente abbandonato
- Merge conflict tra 2 agent-worktree mergiate quasi-simultaneamente
- Cron LaunchAgent che parte mentre operator interactive su main

### Gap G8 — Reflexion + Voyager skill evolution (P3)

L4 ha repomap cron ma NON ha Reflexion loop. Manca:

- Cron Sunday 02:00 WITA che legge ultima settimana di adoption metric + cicatrix new + git log
- Synthesis LLM (Sonnet 4.6) che propone amendments a `~/.claude/skills/agent-session-discipline/lessons.md`
- Voyager-style skill library evolution (nuove skill `_proposed/` dopo 3+ usages)

## 3. L5 Spec — Roadmap chiusura gap

### Phase L5.1 — Adoption enforcement (P0, target oggi)

**Output**:

- `~/.claude/hooks/worktree_isolation.py` — PreToolUse hook (Bash) blocca git ops in main checkout
- `~/.claude/hooks/agent_workspace_setup.py` — SessionStart hook propone worktree create
- `~/.claude/skills/agent-session-discipline/SKILL.md` — invokable via `/agent-start <lane> <task-id>`
- Patch AGENTS.md con stessa sezione Agent Worktree Discipline di CLAUDE.md
- Test empirici: spawn fake Claude session, verifica blocco git checkout

**Effort**: 2h. **Dipendenze**: PR #852 (L1) DEVE essere mergiato prima.

### Phase L5.2 — Cross-LLM worktree contract (P1, target sett 1)

**Output**:

- `~/scripts/codex-spawn.sh` — wrapper che fa agent_start.py prima di codex exec
- `~/scripts/agy-spawn.sh` — wrapper analogo per Gemini agy
- Audit di tutti i LaunchAgent + cron che invocano Codex/Gemini → migrazione ai wrapper
- Test empirico: spawn codex via wrapper, verifica cwd dentro .worktrees/

**Effort**: 3h.

### Phase L5.3 — Sub-agent dispatch isolation (P1, target sett 1)

**Output**:

- Patch a `~/.claude/agents/*.yaml` con `worktree_required: true` flag
- Pre-dispatch validation in Agent tool wrapper
- Sub-agent runtime SessionStart legge env `AGENT_WORKTREE_PATH`

**Effort**: 4h. **Note**: richiede modifica del Claude Code Agent tool harness — potrebbe essere bloccato dall'esterno (Anthropic-side). Workaround: wrapper script.

### Phase L5.4 — Lifecycle workflow skills (P2, target sett 2)

**Output**:

- `~/.claude/skills/session-study/SKILL.md` — checklist study phase
- `~/.claude/skills/session-logging/SKILL.md` — research capture + memory save
- `~/.claude/skills/post-deploy-verify/SKILL.md` — curl + screenshot + log-tail orchestrator
- `~/.claude/skills/session-cleanup/SKILL.md` — stash drop + worktree gc + memory archive
- `scripts/lint_commit_convention.sh` — Conventional Commits validator
- Patch husky pre-commit con conventional-commits lint

**Effort**: 6h.

### Phase L5.5 — Observability adoption metric (P1, target sett 1)

**Output**:

- `scripts/audit_workflow_adoption.sh` — daily 09:00 WITA cron
- LaunchAgent `com.balizero.workflow-adoption.daily.plist`
- Telegram alert se adoption < 80%

**Effort**: 2h.

### Phase L5.6 — Hot-zone regex expansion (P2, target sett 1)

**Output**:

- Patch a `.husky/pre-commit` L2 hot-zone regex (+ 6 nuovi pattern empirici)
- Patch a `scripts/agent_lease.py` lease check anche pre-write (non solo pre-commit)

**Effort**: 1h.

### Phase L5.7 — Recovery runbook (P2, target sett 1)

**Output**:

- `docs/runbooks/agent-worktree-recovery.md` — 5 scenari edge documentati
- Test empirici per ogni scenario

**Effort**: 3h.

### Phase L5.8 — Reflexion + Voyager skill evolution (P3, target sett 2)

**Output**:

- `scripts/workflow-reflexion-weekly.py` — cron Sunday 02:00 WITA
- LaunchAgent `com.balizero.workflow-reflexion.weekly.plist`
- `~/.claude/skills/agent-session-discipline/lessons.md` (append-only)
- Voyager skill draft directory `~/.claude/skills/_proposed/`

**Effort**: 4h.

## 4. Dipendenze critiche

```
L5.1 (enforcement) ← BLOCKED BY: merge PR #852 (L1)
L5.2 (cross-LLM)   ← BLOCKED BY: merge PR #852 (L1)
L5.3 (sub-agent)   ← BLOCKED BY: merge PR #852 (L1)
L5.4 (lifecycle)   ← BLOCKED BY: L5.1 (skills need enforcement infra)
L5.5 (metric)      ← BLOCKED BY: merge PR #852 (L1) + #853 (L2)
L5.6 (hot-zone)    ← BLOCKED BY: merge PR #853 (L2)
L5.7 (recovery)    ← BLOCKED BY: L5.1 (need enforcement first)
L5.8 (reflexion)   ← BLOCKED BY: L5.5 (need metric data)
```

**Conclusione**: merge dei 4 PR draft L1-L4 è precondizione per tutto il resto. **Senza merge, niente di L5 ha senso**.

## 5. Raccomandazione operativa per Antonello

### Step 1 — Review + merge dei 4 PR SOTA draft (priorità P0, 30min)

In ordine consigliato (dependency-free):

1. **PR #851** (L3 merge queue + CODEOWNERS) — modifica `.github/workflows/` + rulesets. **Più rischiosa** (può bloccare CI futuro), merge **PER PRIMA** in modo che le seguenti seguano la regola.
2. **PR #854** (L4 repomap + branch cleanup) — additivo, basso rischio.
3. **PR #852** (L1 worktree broker) — additivo `scripts/`, ma modifica `CLAUDE.md` + 90 file modificati (probabilmente test cleanup / docstring). **Verifica diff prima del merge**.
4. **PR #853** (L2 redis lease + husky pre-commit) — più invasiva (modifica `.husky/pre-commit`, può blocccare commit futuri). Merge **PER ULTIMA** quando hai 5 minuti per testare un commit.

### Step 2 — Decisione su L5

Una volta L1-L4 mergiati, decidere:

- **Opzione A**: shippare L5.1 (enforcement) subito stesso giorno, per chiudere il "gap di adoption" che è il motivo per cui 32 stash si sono accumulati nelle 13h post-SOTA-drafting.
- **Opzione B**: aspettare 1 settimana di osservazione adoption naturale (CLAUDE.md update + skill `/agent-start`), poi se adoption < 80% shippare enforcement.

**Bias verso A**: i 13h post-shipping hanno prodotto 32 stash zero adoption. Empirical evidence suggerisce naturale adoption ≈ 0%. Enforcement è necessario.

### Step 3 — Sub-agent + cross-LLM (L5.2 + L5.3) come Wave 2

Una settimana dopo L5.1 enforcement. Permette di osservare comportamento Claude Code prima di estendere a Codex/Gemini/sub-agent.

## 6. Costo + decisione

| Voce                          | Costo  | Note                                                           |
| ----------------------------- | ------ | -------------------------------------------------------------- |
| Cloud LLM                     | $0     | Tutto Claude OAuth MAX + Gemini Ultra + DeepSeek $0.01/section |
| Wall-time L5.1 implementativo | ~2h    | Single Claude session in worktree dedicato                     |
| Wall-time Antonello           | ~30min | Review + sign-off 4 PR draft                                   |
| Risk                          | BASSO  | Tutto reversible via kill-switch + rollback script             |

## 7. Open questions per Antonello

1. **Accetto la dependency-chain**: nessun L5 può partire prima di L1-L4 mergiati. Conferma?
2. **Auto-merge whitelist** in L3 include `docs/auto-sync-*` + `dependabot/*` + `chore/fmt-*`. Vuoi aggiungere/togliere lane?
3. **Hot-zone regex L2** mancano 6 path empirici (LaunchAgent, research/operations, hooks, skills, wr2/wr3, integrations). Posso patcharli pre-merge di PR #853 o preferisci merge as-is e patch separato?
4. **Sub-agent dispatch isolation** L5.3 richiede mod agent definitions YAML — vuoi che proceda anche se Anthropic-harness side potrebbe bloccare?
5. **Telegram alert daily adoption** è abilitato o solo log file?
