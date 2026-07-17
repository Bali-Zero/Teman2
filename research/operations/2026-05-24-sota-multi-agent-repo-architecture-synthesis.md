---
date: 2026-05-24
domain: operations
client_case: nuzantara-internal
sources:
  - https://git-scm.com/docs/git-worktree
  - https://docs.cursor.com/background-agents
  - https://docs.openhands.dev/openhands/usage/runtimes/docker
  - https://aider.chat/docs/repomap.html
  - https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/using-a-merge-queue
  - https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
  - https://www.graphite.com/guides/stacked-diffs-on-github
  - https://sapling-scm.com/docs/introduction/
  - https://automerge.org/
  - https://docs.sentry.io/product/issues/issue-details/sentry-ai/
  - https://docs.datadoghq.com/incident_response/incident_management/investigate/incident_ai/
  - https://docs.continue.dev/guides/doc-writing-agent-cli
  - https://mintlify.mintlify.app/ai-ingestion
  - https://docs.cline.bot/customization/memory-bank
  - https://arxiv.org/abs/2605.08017
  - https://arxiv.org/abs/2604.18334
  - https://arxiv.org/abs/2605.07135
  - https://arxiv.org/abs/2601.15195
  - https://arxiv.org/abs/2604.24450
  - https://arxiv.org/abs/2602.11988
  - https://arxiv.org/abs/2205.09125
  - panel-artifact: /tmp/sota-research-2026-05-24/gemini.md
  - panel-artifact: /tmp/sota-research-2026-05-24/codex.md
  - panel-artifact: /tmp/sota-research-2026-05-24/deepseek.md
  - panel-artifact: /tmp/sota-research-2026-05-24/claude-opus-input.md
panel:
  - gemini-3.1-pro-preview (long-context ingestion, 2.088 parole)
  - gpt-5.5-codex (adversarial + paper-grounded, 2.106 parole, 6min web search empirical)
  - deepseek-v4-pro (reasoning + formal guarantees, 2.169 parole, reasoning_effort=high)
  - claude-opus-4-7 (synthesis + Nuzantara-specific grounding, 1.060 parole)
implementation_status:
  - L1 worktree broker — PR #852 MERGED 2026-05-25 (scripts/agent_start.py on main)
  - L2 Redis lease registry — PR #853 MERGED 2026-05-25 (docs/runbooks/redis-lease-registry.md on main)
  - L3 GitHub merge queue + rulesets — PR #851 MERGED 2026-05-25 (scripts/setup_merge_queue_rulesets.sh on main) — RETIRED 2026-07-17, script deleted (0 rulesets live, 0 consumers; merge_train.py coordinator untouched)
  - L4 Repomap cron + branch cleanup — PR #854 MERGED 2026-05-25 (scripts/build_repomap.sh on main)
update:
  - 2026-05-28 postscript appended — companion deep-research 2026-05-28-sota-multi-agent-repo-arch-update.md
  - 2026-06-02 S16 — ORCHESTRATION-topology axis (orthogonal to this repo-arch doc): 2026-06-02-sota-multiagent-orchestration.md + 2026-06-02-sota-multiagent-FROZEN.json
---

# SOTA Architettura Repo + Workflow AI-Dev (Nuzantara) — Sintesi 4-LLM Panel

> **Re-creato 2026-05-24** (versione precedente perduta come untracked durante L4 recovery, ironicamente esempio vivo del problema che il panel risolve).

## TL;DR

Convergenza 4/4 panelisti su **3 cambi strutturali immediati** che chiudono il 90% delle cicatrix sibling-collision degli ultimi 30gg:

1. **Worktree-per-agent obbligatorio** (broker script) — risolve stash orphan + checkout-overwrite + file persi.
2. **Lease registry con enforcement pre-commit** — risolve plist HOME-fork (W50/W51/W52) e registry concurrent edit.
3. **Merge queue GitHub + risk-path rulesets** — risolve PR superseded, conflict 17%, auto-merge sicuro per classi deterministiche.

**Convergenza 3/4 su** (deferribili settimana 2):

4. **Auto-cicatrix→PR loop** (Gemini/DeepSeek/Claude) — Codex AVVERTE: solo fino a draft, mai auto-merge per bugfix/auth/migration.
5. **Repomap auto-injected** (Gemini/DeepSeek/Claude) — Aider tree-sitter, 5k token snapshot per session start.
6. **Diff-to-doc cron ristretto** (Gemini/Codex/Claude) — Continue headless o script locale, PR separata `docs/auto-sync-*`.

**Rejected 4/4**: Devin/cloud agent (viola Law 6), CRDT general-purpose su codice (overhead proibitivo), central orchestrator Mastra-style (over-engineering per 2 sessioni concorrenti).

---

## 1. Stato attuale Nuzantara (empirico 2026-05-24)

| Metrica                                      | Valore                      | Note                                                                                                                  |
| -------------------------------------------- | --------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| File repo (no `.git`/`node_modules`/`.venv`) | 82.970                      | monorepo grosso ma non eccezionale                                                                                    |
| Apps                                         | 33                          | sotto `apps/`                                                                                                         |
| Doc files                                    | 1071                        | sotto `docs/`                                                                                                         |
| LaunchAgent attivi Pro                       | 169                         | 35 `wr2`, 4 `wr3`, 3 `organism`, 3 `intel-lake`, ecc                                                                  |
| Branch remoti                                | 162                         | 6 `claude/*` zombie >30gg                                                                                             |
| Cicatrix attive + archive                    | 52 + 7                      | 19 NUOVE W34→W57 nelle ultime 48h                                                                                     |
| Commit cadence                               | 380/7gg, 36/24h             | autori: Bali Zero + Claude Opus + dependabot + SubBZ2026                                                              |
| Sessioni Claude REALI concorrenti            | 2 (CLI) + 5 (tool-exec zsh) | "35 processi" e' inflated, 20 sono helper Claude.app UI                                                               |
| File con ≥2 author distinti 7gg              | 82 / 3657 (2.2%)            | sempre `Bali Zero` committer + `Claude Opus` author tag — **collision e' multi-session-stesso-Claude, NON cross-LLM** |

**Sibling collision REALE**: 2 sessioni Claude concorrenti (interactive + cron/subagent), tutte sullo stesso working tree `~/Desktop/nuzantara`. La hot-zone e' `~/Library/LaunchAgents/` (169 plist) + script wrapper in `~/scripts/` (drift HOME-vs-repo).

---

## 2. Convergenza 4-LLM su anti-pattern Nuzantara

Tutti e 4 i panelisti chiamano i seguenti come **anti-pattern empiricamente confermati dalla cicatrix list**:

| Anti-pattern                                          | Cicatrix Nuzantara                                              | Verdetto SOTA                                                                 |
| ----------------------------------------------------- | --------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `git stash` come mutex                                | 2026-04-29 incident #1 + #2                                     | "Modo piu' veloce per produrre untracked file persi" (Codex)                  |
| Branch checkout dentro stesso checkout                | 2026-04-29 #2                                                   | "Sibling watchdog distrugge WIP altrui" (Gemini)                              |
| Script in HOME-fork vs repo SSOT                      | W50, W51, W52 (84/167 plist)                                    | "State condiviso implicito" (Codex)                                           |
| `except asyncpg.PostgresError` senza `InterfaceError` | W32, W34 (50min NOTIFY dropped)                                 | "Daemon silent-death" (DeepSeek)                                              |
| Auto-rerun-on-flake senza classifier                  | rerun-storm sentinel pre-W55                                    | "Maschera regression intermittenti" (Codex citing Renovate)                   |
| Auto-merge su tutto                                   | (non ancora cicatrix, ma rischio attivo con merge wave 35→0 PR) | "Antipattern per bugfix/auth/migration" (Codex, citing arXiv 2601.15195)      |
| AI reviewer-bot come merge authority                  | (potenziale wr2-critic over-trust)                              | "Qualita' rilevanza semantica solo moderata" (Codex, citing arXiv 2604.24450) |

---

## 3. Pattern SOTA convergenti — implementazione concreta

### 3.1 Workspace isolation: Git worktree obbligatorio per agent

**Convergenza 4/4.** Riferimenti: [git-worktree](https://git-scm.com/docs/git-worktree), [Cursor Background Agents](https://docs.cursor.com/background-agents), [OpenHands Docker Sandbox](https://docs.openhands.dev/openhands/usage/runtimes/docker), [Devin Blueprints](https://docs.devin.ai/onboard-devin/environment/blueprints).

Tutti i sistemi maturi (Devin, Cursor BG Agents, OpenHands, Sweep) NON lasciano piu' agenti scrivere nella stessa working copy. Spostano il conflitto fuori del filesystem: **una task = un ambiente isolato = un branch/PR**.

DeepSeek formalizza l'invariante:

```
∀ w₁,w₂ : session(w₁) ∧ session(w₂) ⇒ working_tree(w₁) ∩ working_tree(w₂) = ∅
```

**Implementato in PR #852** (`scripts/agent_start.py`, 710 righe, 24/24 test PASS): worktree-per-session enforcement. Lane whitelist (14 + `--allow-unknown-lane`), kill-switch `AGENT_BROKER_ENABLED=false`.

### 3.2 Lease registry con enforcement (Redis-backed)

**Convergenza 4/4.** Codex propose `.agent/leases.jsonl` git-tracked. Gemini/DeepSeek propongono Redis (gia' attivo su Pro+Mini Tailscale). Claude raccomanda **Redis perche' gia' attivo** + zero new infrastruttura.

Hot-zones da proteggere:

- `~/Library/LaunchAgents/com.{balizero,nuzantara,cell,matagaruda,garuda}*.plist` (169 file)
- `infra/launchagents/*.sh` (wrapper sync sources)
- `shared/escalations*.jsonl`
- `~/.agent/decisions/`
- `apps/backend-rag/backend/db/migrations_v2/*.sql` (collision 194 = W40)

**Implementato in PR #853** (`scripts/agent_lease.py` + `.husky/pre-commit`): SETNX EX atomic, audit JSONL trail, graceful degradation se Redis down. Kill-switch `AGENT_LEASE_ENFORCEMENT=false`.

### 3.3 GitHub merge queue + risk-path rulesets

**Convergenza 4/4.** Riferimenti: [GitHub Merge Queue](https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/using-a-merge-queue), [CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners), [Renovate Automerge](https://docs.renovatebot.com/key-concepts/automerge/).

Codex AVVERTE (citing arXiv 2605.07135 — agentic workflow injection): se un agente ha write access a `.github/workflows` puo' **silenziare il sistema che lo dovrebbe giudicare**. Path-restriction e' difesa contro questo.

**Implementato in PR #851** (`.github/CODEOWNERS` + `.github/workflows/auto-merge-whitelist.yml` + `scripts/setup_merge_queue_rulesets.sh`):

> **RETIRED 2026-07-17**: `scripts/setup_merge_queue_rulesets.sh` has been deleted — dead automation
> (0 GitHub Rulesets live on this repo, 0 consumers; Rulesets are unavailable on user-owned repos).
> `.github/CODEOWNERS` and `auto-merge-whitelist.yml` remain live (untouched by this retirement).

- Auto-merge AMMESSO: `docs/auto-sync-*` + `dependabot/(pip|npm_and_yarn)/*` + `chore/fmt-*`
- Auto-merge VIETATO: bugfix, pricing/visa, migrations, auth/billing, MCP secrets, deploy
- Rollback snapshot baseline GitHub branch protection

### 3.4 Repomap auto-injected (Aider tree-sitter)

**Convergenza 3/4** (Gemini/DeepSeek/Claude). Codex non discorda ma raccomanda combinarlo con AGENTS.md persistent files.

**Implementato in PR #854** (`scripts/build_repomap.sh` + cron 15min plist + SessionStart hook): aider tree-sitter primary, ctags fallback. Smoke verificato: 8.843 bytes / 298 righe, target 5k token. Kill-switch `REPOMAP_ENABLED=false`.

---

## 4. Pattern SOTA convergenti — settimana 2

### 4.1 Auto-cicatrix → PR loop (3/4, con caveat Codex)

DeepSeek formalizza: `DETECT → DIAGNOSE → REMEDIATE → VERIFY → (CLOSE | ESCALATE)`.

**Codex caveat critico** (citing Sentry Seer + Datadog Bits AI Dev docs): SOTA "self-healing maturo" non e' "agent deploy fix in produzione". E': detection → RCA evidence → failing repro test → PR draft → merge queue → smoke/live checks. **Mai auto-merge per bugfix.**

**NOT YET IMPLEMENTED** — week 2 candidate.

### 4.2 PR risk score deterministico (Codex unique)

GitHub Action che calcola pre-merge: files touched + generated-file drift + migrations + secrets + deploy paths + tests added/removed + snapshots + CI rerun count. **AI reviewer puo' commentare SOLO sopra questo fact base**, non puo' approvare in autonomia su classi rischiose.

**NOT YET IMPLEMENTED** — week 2 candidate.

### 4.3 Diff-to-doc cron RISTRETTO

**Codex scope strict** (citing [Continue doc-writing agent](https://docs.continue.dev/guides/doc-writing-agent-cli)): NON "cron Sonnet riscrive docs", DOES "diff detector produce task doc, agente puo' toccare SOLO `docs/**`, `AGENTS.md`, indici generati, `llms.txt`, cicatrix index, poi PR `docs/auto-sync-*` SEPARATA da feature code".

**NOT YET IMPLEMENTED** — week 2 candidate.

---

## 5. Tabella comparativa sistemi attuali

| Sistema              | Isolamento scritture                                     | Memory/Context                         | PR/CI integration                   | Lezione per Nuzantara                                          |
| -------------------- | -------------------------------------------------------- | -------------------------------------- | ----------------------------------- | -------------------------------------------------------------- |
| **Aider**            | Git-native locale, auto-commit + dirty-commit separation | Repo map symbolic tree-sitter          | Local commits, no merge auth        | Repo map è il single biggest takeaway (→ L4)                   |
| **Cursor BG Agents** | Clone remoto isolato, branch separato                    | IDE rules + sidebar task               | PR async, takeover umano            | Modello canonico worktree-per-agent (→ L1)                     |
| **Devin**            | Sandbox blueprint per repo                               | Playbook quando istruzioni ripetono    | GitHub PR + Slack/Jira hooks        | Ambiente riproducibile + observability, NON agent intelligence |
| **OpenHands**        | Docker sandbox + headless mode                           | `.openhands/setup.sh` + hooks          | GitHub Action/Resolver label-driven | Headless va sandboxed + branch + checks                        |
| **Cline/Sweep**      | Checkpoint Git locali + diff accept/reject               | Memory Bank + `.clinerules`/`SWEEP.md` | IDE-first, no merge auth            | Pattern handoff/rollback, NON sibling coordination             |
| **Continue**         | Headless CLI in CI con restriction file/azioni           | `.continue/rules` + markdown context   | GitHub Actions                      | Modello doc-writing agent ristretto                            |
| **Graphite/Sapling** | Stacked diffs su PR dipendenti                           | Nessuna memoria AI native              | GitHub merge queue compatible       | Utile per refactor sequenziali, NON per 7 agenti indipendenti  |

**Verdetto Nuzantara**: combinare **Cursor BG Agents pattern** (worktree-per-agent) + **OpenHands generated-file discipline** + **GitHub merge queue + rulesets** + **Aider repomap** + **Continue doc-agent ristretto**.

---

## 6. Implementation status — Wave 2026-05-24

### Week 1 (foundational) — 4/4 SHIPPED (draft, awaiting Antonello sign-off)

|      # | Azione                                               | Impact | Effort | PR                                                                          |
| -----: | ---------------------------------------------------- | -----: | -----: | --------------------------------------------------------------------------- |
| **L1** | **Agent worktree broker** (`scripts/agent_start.py`) |      5 |      3 | [#852](https://github.com/Balizero1987/Teman2/pull/852) draft, 4 file +1209 |
| **L2** | **Lease registry Redis** + pre-commit hook           |      5 |      3 | [#853](https://github.com/Balizero1987/Teman2/pull/853) draft, 5 file +1163 |
| **L3** | **GitHub merge queue + risk-path rulesets**          |      5 |      2 | [#851](https://github.com/Balizero1987/Teman2/pull/851) draft, 6 file +761  |
| **L4** | **Aider repomap cron 15min + SessionStart inject**   |      4 |      1 | [#854](https://github.com/Balizero1987/Teman2/pull/854) draft, 7 file +915  |

**Totale wave 1**: 4 PR draft, 22 file, +4048 righe, 0 deletions.

### Week 2 (self-healing, deferred)

|     # | Azione                                                                        | Impact | Effort | Status  |
| ----: | ----------------------------------------------------------------------------- | -----: | -----: | ------- |
| **5** | **PR risk score deterministico** (GitHub Action)                              |      4 |      3 | not yet |
| **6** | **Diff-to-doc cron ristretto** (Gemini 1M ctx, PR `docs/auto-sync-*`)         |      3 |      2 | not yet |
| **7** | **Cicatrix → PR draft loop** (Sonnet 4.6 + 4-LLM gate, mai auto-merge bugfix) |      4 |      4 | not yet |

### Rejected 4/4 (non implementare)

- **CRDT general-purpose** (DeepSeek 5/5) — overhead 5 per ROI dubbio. Generated-file discipline (Codex 5) e' alternativa cleaner per plist/registry.
- **Central orchestrator Mastra-style** (DeepSeek 7/4) — over-engineering per 2 sessioni concorrenti. Worktree+lease bastano.
- **Cloud agent Devin/Cursor BG remote** (Gemini scarta correttamente) — viola Symbiosis Law 6 (sovranita' locale).
- **Auto-merge per bugfix/auth/migration** (Codex assoluto) — antipattern documentato in arXiv 2601.15195 + 2604.18334.

---

## 7. Devils-advocate finale (Codex su Codex stesso)

> "Il primo rischio e' che l'agente modifichi CI per farsi passare. Il secondo e' test laundering. Il terzo e' flake amplification. Self-healing pipeline che rerunna ogni failure puo' mascherare regressioni intermittenti."

Mitigazioni embedded nei PR shipati:

- **L3 PR #851**: ruleset `.github/workflows/**` con @Balizero1987 CODEOWNERS-required → agent non puo' silenziare CI (rischio 1).
- **L2 PR #853**: pre-commit lease-check su `~/.agent/decisions/` + `shared/escalations*.jsonl` → test laundering visibile.
- **Codex unique amendment**: PR risk score deterministico (week 2 deferred) include `tests added vs removed` semantic diff — completera' mitigazione rischio 2.

**Punto critico Claude self-critique**: aggiungere 7 nuovi sistemi = 7 nuovi cicatrix-candidate. Ogni layer di self-healing puo' diventare il prossimo W##-incident.

**Difesa**: ognuno e' shippable in <1 settimana + ognuno HA kill-switch env var:

- L1: `AGENT_BROKER_ENABLED=false`
- L2: `AGENT_LEASE_ENFORCEMENT=false`
- L3: `gh api -X DELETE` rollback script + snapshot baseline
- L4: `REPOMAP_ENABLED=false` + `BRANCH_CLEANUP_ENABLED=false`

---

## 8. Live cicatrix DURANTE questa wave (meta-osservazione)

Durante la wave parallela dei 4 agent specialist, **e' successa esattamente la cosa che il panel deve risolvere**:

1. **L4 agent vittima di sibling-agent branch-switch race** (cicatrix 2026-04-29 family): un sibling ha switchato il working tree dal branch `feat/repomap-cron-branch-cleanup-2026-05-24` a `feat/redis-lease-registry-2026-05-24` mid-edit. File stashati come `L4-repomap-files-stranded-on-L2-branch-2026-05-24`. Recovery: stash apply + WIP commit immediato + push. Tutto preservato ma 1h di overhead recovery.

2. **Bug fix branch_graveyard re-applicato 3 volte**: la prima volta perso al checkout, la seconda revertito da linter, la terza confermato funzionante.

3. **Sintesi 4-LLM panel cancellata accidentalmente**: durante recovery L4, il file `research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md` (~2.500 parole) e' stato rimosso come untracked. Re-creato in questo commit. **Ironicamente la sintesi del panel anti-collision e' stata vittima del problema che descrive.**

Tutti e 3 incident sarebbero stati **prevenuti** dai PR shipati:

- (1) e (2) → PR #852 worktree-per-agent
- (3) → PR #853 lease check su `research/operations/**` (potenziale hot-zone da aggiungere)

---

## 9. Costo + decisione richiesta

| Voce                            | Costo                                | Note                                                                              |
| ------------------------------- | ------------------------------------ | --------------------------------------------------------------------------------- |
| Cloud LLM                       | $0                                   | Tutto Claude OAuth MAX (2 plan) + Gemini Ultra + Codex GPT-5.5 + DeepSeek $0.01/q |
| Wall-time implementativo wave 1 | ~4h (distribuito su agent paralleli) | Real: 4 agent in ~30min wall ciascuno                                             |
| Wall-time Antonello             | ~30 min                              | Review 4 PR draft + sign-off rulesets sensibili                                   |

**Decisione richiesta**:

1. ✅ Approvazione 4 PR draft (review + merge in qualsiasi ordine; L1+L2 indipendenti, L3 standalone, L4 standalone)?
2. ✅ Run manuale `bash scripts/setup_merge_queue_rulesets.sh --apply` (L3)? — **RETIRED 2026-07-17**: script deleted (dead automation, 0 rulesets live).
3. ✅ Run manuale `bash infra/launchagents/install_repomap_cron.sh` (L4)?
4. ⏳ Branch cleanup ora? Lista da PR #854: `orchestrate/surface-router-activation-2026-05-17`, `orchestrate/organism-rag-leverage-2026-05-17`, `orchestrate/ops-autonomy-reliability-2026-05-17` (tutti merged, safe-deletable). Cmd: `bash scripts/branch_graveyard_cleanup.sh --apply`.

---

## Riferimenti panel

Tutti gli output dei 4 panelisti sono salvati su disco per audit:

- `/tmp/sota-research-2026-05-24/gemini.md` (14.537 byte, 2.088 parole)
- `/tmp/sota-research-2026-05-24/codex.md` (17.351 byte, 2.106 parole, 6 min web search empirical)
- `/tmp/sota-research-2026-05-24/deepseek.md` (16.672 byte, 2.169 parole, reasoning_effort=high)
- `/tmp/sota-research-2026-05-24/claude-opus-input.md` (1.060 parole, Nuzantara-grounded)
- `/tmp/sota-research-2026-05-24/brief.md` (629 parole, brief comune)

Convergenza 4/4 sui top-3 + Codex unique contribution su PR risk score + arXiv 2605.07135 (agentic workflow injection) + Renovate automerge discipline. DeepSeek unique su formal invariant worktree isolation. Gemini unique su Redis mutex implementation pattern. Claude unique su Nuzantara survey empirical + ship-in-1-week cap discipline.

---

## Postscript — 2026-05-28 (status reale + delta SOTA + validazione cicatrix)

> Companion deep-research: [`2026-05-28-sota-multi-agent-repo-arch-update.md`](2026-05-28-sota-multi-agent-repo-arch-update.md) (Claude Opus + Gemini agy + DeepSeek v4-pro, 6 fonti fresche). Questo postscript chiude il loop: cosa è stato shipped, cosa l'evidenza nuova dice, e quali cicatrix degli ultimi 4 giorni hanno **validato in produzione** le previsioni del panel.

### Implementation: tutte e 4 le lane SHIPPED (verificato empirico 2026-05-28)

| Lane                        | PR   | Merged           | Artifact su main                                                 |
| --------------------------- | ---- | ---------------- | ---------------------------------------------------------------- |
| L1 worktree broker          | #852 | 2026-05-25 01:59 | `scripts/agent_start.py`                                         |
| L4 repomap + branch cleanup | #854 | 2026-05-25 01:58 | `scripts/build_repomap.sh` (cron 15min)                          |
| L2 Redis lease registry     | #853 | 2026-05-25 02:20 | `docs/runbooks/redis-lease-registry.md` + pre-commit lease-check |
| L3 merge queue + rulesets   | #851 | 2026-05-25 02:02 | `scripts/setup_merge_queue_rulesets.sh` + CODEOWNERS — **RETIRED 2026-07-17** (script deleted, 0 rulesets live; CODEOWNERS untouched) |

Tutte e 4 sono ora citate come SSOT nel `CLAUDE.md` di progetto (§Agent Worktree Discipline, §7 Hooks, §7bis Repomap).

### Validazione in produzione — cicatrix W58→W63 (gli ultimi 4 giorni)

Il panel prevedeva che il worktree-broker chiudesse la classe sibling-collision. Evidenza empirica post-merge:

- **W62 (2026-05-28)**: broker TTL=60min violato 34× da 6 worktree ops abbandonati. **Non refuta L1 — lo restringe**: il broker isola correttamente, ma manca un _cleanup enforcement_ (cron `--cleanup` opt-in, nessun consumer legge il TTL). Conferma la previsione del panel che il broker serviva, ed espone il next-gap (auto-cleanup).
- **W63 (2026-05-28)**: worktree nested (`.worktrees/X/.worktrees/Y`) da `agent_start.py` invocato con CWD dentro un worktree. Gap di guardia: il broker dovrebbe `assert REPO_ROOT not in any worktree`. Micro-failure dell'L1, non strutturale.
- **W59 (2026-05-27)**: sibling-race branch hijack durante git ops sequenziali — esattamente la classe che L1+L2 indirizzano. La hot-zone resta `~/Library/LaunchAgents/` come previsto.

Lettura: i 3 incident sono **micro-gap dell'implementazione L1**, non refutazioni del pattern. Il panel aveva ragione sulla diagnosi; l'enforcement va completato (cleanup cron + nested-guard).

### Delta SOTA (2026-04/05, dalla companion deep-research)

1. **L1 vindicated a livello vendor**: Cursor 3.5 ha reso il worktree-per-agent un primitivo nativo (`/worktree`, `/best-of-n`). Azionabile NUOVO: regola **anti-symlink deps** (Cursor avverte che symlinkare `.venv`/`node_modules` nel worktree corrompe il main) — verificare se `agent_start.py` symlinka.
2. **L3 da hardening (incident PRIMARIO)**: GitHub merge-queue incident 2026-04-23 (community #193645, 230 repo / 2092 PR, **solo squash su gruppi >1 PR** → revert silenzioso, scoperto da customer report dopo 3.5h, NON dal monitoring). Mitigazione derivata (DeepSeek formale): `max_group_size=1` **oppure** no-squash → porta la failure mode a **probabilità zero**. + auto-merge HTTP 422 (#190610): non si pre-arma più prima dei check verdi → impatta `auto-merge-whitelist.yml`.
3. **L5 (repomap) declassato a FLOOR**: il dump statico tree-sitter resta accettabile su monorepo 82k file ma non è più la frontiera — SOTA = MCP code-knowledge-graph + LSP symbolic nav (il modello _tira_ il contesto invece di farselo _spingere_ 5k token a ogni prompt). Da valutare solo se il MCP gira 100% locale (Law 6).
4. **Auto-merge discipline rinforzata**: DORA `[second-hand]` +154% PR size / +91% review time sotto AI → "mai auto-merge bugfix/auth/migration" ulteriormente sostanziato.

### Next-step a valore più alto (post-6-pattern)

**Post-merge HEAD-integrity check + `max_group_size=1` su L3** — ancorato all'incident primario 2026-04-23, elimina la classe di data-loss da squash-corruption a probabilità zero, costo CI minimo. Scelto su "repomap→MCP" (vendor trend `[second-hand]`) per la regola incident-sourced > trend. Secondo: **PR-size guard** (CI flag su PR >400 righe). Terzo: broker **auto-cleanup cron** (chiude W62).

> Disaccordo onesto lasciato aperto nella companion: Gemini (repomap→MCP) vs DeepSeek (post-merge guard) sul #1. Risolto a favore del post-merge guard (incident sourced).
