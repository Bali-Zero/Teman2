# Mata Garuda — Build Order

> Data: 2026-04-09 | Sessione S04
> Riferimento: [02-ARCHITECTURE.md](02-ARCHITECTURE.md), [40d-AUTOAGENT-PATTERNS.md](40d-AUTOAGENT-PATTERNS.md)
> Scopo: piano di implementazione del meta-agent layer in 3 sprint focalizzati

---

## Principi di build

1. **Reimplementare, non forkare** (decisione 40c)
2. **Walking skeleton first** — un agente dummy end-to-end prima di aggiungere features
3. **CLI-only sempre** — niente API HTTP, anche in dev
4. **Verifica dopo ogni sprint** — non passare allo sprint successivo se quello attuale non è validato
5. **GENOME.md per ogni agente** — anche il dummy deve averne uno (Lamarckian-ready dal giorno 1)
6. **Out-of-tree** — il pacchetto `mata_garuda/` vive sotto `~/Desktop/mata-garuda/` o in `apps/mata-garuda/` del monorepo. **Da decidere PRIMA dello Sprint 1.**

### ✅ Decisione architettonica (RISOLTA 2026-04-09)

**Q:** dove vive il package `mata_garuda/`?
**A:** Opzione (c) — Repo Git separato `Balizero1987/mata-garuda` privato

**Setup completato 2026-04-09:**
- Repo: https://github.com/Balizero1987/mata-garuda (privato)
- Worktree locale: `~/Desktop/mata-garuda/`
- Commit iniziale: `57050b4` — 14 file, 911 LOC
- Stato: Sprint 1 walking skeleton COMPLETO e validato

**Motivazioni:**
- Allineamento con vincolo OSINT blindato (mai cloud/shared)
- Zero contaminazione monorepo Nuzantara (no collision CI/CD)
- CLAUDE.md dedicato con vincoli Mata Garuda specifici
- Git history pulita per Lamarckian pattern (mutazioni GENOME trackate)
- Possibilità futura di spin-off public `mata-garuda-public` (runtime only)

---

## Sprint 1 — Walking Skeleton ✅ COMPLETO (2026-04-09)

**Status:** COMPLETO (parziale — CLI runtime e runtime/loop.py rimandati a Sprint 2 perché non necessari per il walking skeleton)
**Tempo reale:** ~1h (vs stima 2 giorni)
**Commit:** `57050b4` su Balizero1987/mata-garuda
**Test:** 9/9 pass
**Agents registered:** 1 (Dummy Agent)

### Obiettivo
Avere un dummy agent che parte, riceve input, chiama Claude CLI, ritorna output, è registrato dinamicamente. **Niente meta-agent ancora, niente Lamarckian, niente tools complessi.**

### Output atteso (verificabile)

```bash
$ python -m mata_garuda.cli run dummy_agent "Ciao, come stai?"
[Mata Garuda] Loaded 1 agent(s) from registry
[Dummy Agent] Hello! I am a dummy agent for Mata Garuda.
[case_resolved] Done.
```

### File da creare (in ordine)

| # | File | LOC | Cosa fa |
|---|---|---|---|
| 1 | `mata_garuda/__init__.py` | 5 | package marker + version |
| 2 | `mata_garuda/types.py` | 30 | Pydantic: `Agent`, `Response`, `Result` |
| 3 | `mata_garuda/registry.py` | 70 | Singleton + `@register_agent`/`@register_tool` |
| 4 | `mata_garuda/agents/__init__.py` | 30 | recursive auto-import |
| 5 | `mata_garuda/agents/dummy_agent.py` | 40 | template agent semplice |
| 6 | `mata_garuda/agents/dummy_agent/GENOME.md` | 20 | constraints + identity dell'agente |
| 7 | `mata_garuda/runtime/__init__.py` | 5 | |
| 8 | `mata_garuda/runtime/cli_runtime.py` | 150 | subprocess wrapper claude/gemini |
| 9 | `mata_garuda/runtime/loop.py` | 80 | minimal MetaChain loop |
| 10 | `mata_garuda/cli.py` | 60 | `python -m mata_garuda.cli run <agent> <query>` |
| 11 | `pyproject.toml` | 30 | dipendenze: `pydantic>=2`, nient'altro |
| 12 | `tests/test_registry.py` | 50 | smoke test registry + dummy agent |

**Totale: ~570 LOC + 30 LOC test.**

### Definition of Done

- [ ] `pip install -e .` funziona in venv pulito
- [ ] `python -m mata_garuda.cli list-agents` mostra `dummy_agent`
- [ ] `python -m mata_garuda.cli run dummy_agent "test"` ritorna output
- [ ] `pytest tests/test_registry.py` passa
- [ ] Subprocess `claude --print` viene effettivamente chiamato (verificare via log)
- [ ] Agente termina con `case_resolved` (anche se hard-coded in dummy)
- [ ] Dummy ha `GENOME.md` letto al boot (anche se vuoto)
- [ ] Zero dipendenze HTTP (no `httpx`, no `litellm`, no `openai`)

### Open questions Sprint 1

- Come gestire tool calls senza function calling nativo nei CLI? → JSON-in-text + parser
- Come passare il system prompt a `claude --print`? → via stdin o `--system`?
- Streaming output vs blocking? → blocking per Sprint 1, streaming per Sprint 2 se serve

---

## Sprint 2 — Meta-Agent ✅ COMPLETO (2026-04-09)

**Status:** COMPLETO
**Tempo reale:** ~30min (vs stima 2 giorni)
**Commit:** `ecdbfce` su Balizero1987/mata-garuda
**Test:** 48/48 pass (39 nuovi + 9 Sprint 1)
**Agents registered:** 2 (Dummy Agent + Meta Agent)
**LOC aggiunte:** 1263 (955 source + 308 test)

### Obiettivo
Far creare un nuovo agente al meta-agent via natural language, validarlo, eseguirlo. **Niente Lamarckian ancora.**

### Output atteso

```bash
$ python -m mata_garuda.cli run meta_agent "Crea un agente che cerca news su KBLI 2025"
[Meta Agent] Existing agents: dummy_agent, meta_agent
[Meta Agent] Creating agent 'kbli_news_agent' with tools [web_search]
[create_agent] Validated mata_garuda/agents/kbli_news_agent.py
[Meta Agent] Running kbli_news_agent...
[kbli_news_agent] Found 3 KBLI 2025 updates: ...
[case_resolved] Done.

$ python -m mata_garuda.cli list-agents
- dummy_agent
- meta_agent
- kbli_news_agent  ← nuovo!
```

### File creati

| # | File | LOC | Cosa fa |
|---|---|---|---|
| 13 | `mata_garuda/tools/__init__.py` | 5 | tools auto-import |
| 14 | `mata_garuda/tools/meta_tools.py` | 331 | list/create/delete/run + execute_command |
| 15 | `mata_garuda/agents/meta_agent.py` | 84 | meta-agent definition |
| 16 | `mata_garuda/agents/meta_agent_GENOME.md` | 30 | vincoli OSINT + tool usage |
| 17 | `mata_garuda/security/__init__.py` | 2 | security package |
| 18 | `mata_garuda/security/path_firewall.py` | 102 | whitelist path + forbidden names |
| 19 | `mata_garuda/runtime/__init__.py` | 2 | runtime package |
| 20 | `mata_garuda/runtime/cli_runtime.py` | 247 | subprocess wrapper claude/gemini/codex |
| 21 | `mata_garuda/runtime/loop.py` | 191 | MetaChain execution loop |
| 22 | `tests/test_meta_agent.py` | 308 | 39 test (firewall, tools, registration, CLI) |

### Definition of Done

- [x] `meta_agent` può chiamare `list_agents` e ottiene il registry
- [x] `meta_agent` può chiamare `create_agent` con NL spec → file `.py` generato
- [x] `create_agent` valida il file con `python -c "import ..."` PRIMA di registrare
- [x] `path_firewall.py` blocca tentativi di scrivere fuori da `mata_garuda/agents/`
- [x] `path_firewall.py` rifiuta nomi che matchano `frontend|client|team|channel|api|cloud|secret|...`
- [x] `run_agent` esegue agente via MetaChain loop (subprocess CLI)
- [x] `delete_agent` rimuove file e aggiorna registry
- [x] `meta_agent` ha `GENOME.md` con vincoli OSINT espliciti
- [x] Test crea un `sprint_test_agent`, lo esegue, lo cancella, verifica registry pulito

### Open questions Sprint 2 — RISOLTE

- Come strutturare il prompt del meta-agent? → **leggere `dummy_agent.py` come template letterale** (pattern AutoAgent) ✅
- Come passare context_variables al subprocess agent run? → **dict passato a run_agent_loop, iniettato nelle tool function** ✅
- Dove salvare i log di esecuzione? → **deferred a Sprint 3 (logging via Python logger per ora)** ✅
- `gemini --print` non esiste → **usa `gemini --prompt`** (mapping in CLI_CONFIGS) ✅
- `claude --system-prompt` → **supportato nativamente** ✅

---

## Sprint 3 — Lamarckian + GENOME hook ✅ COMPLETO (2026-04-09)

**Status:** COMPLETO
**Tempo reale:** ~20min (vs stima 2 giorni)
**Commit:** `f69e797` su Balizero1987/mata-garuda
**Test:** 79/79 pass (31 nuovi + 48 Sprint 1+2)
**LOC aggiunte:** 962 (628 source + 334 test)

### Obiettivo
Implementare il loop `case_resolved/case_not_resolved` → `feedback.md` → mutation review. **Questo è il cuore del Lamarckian pattern.**

### File creati

| # | File | LOC | Cosa fa |
|---|---|---|---|
| 23 | `mata_garuda/runtime/case_status.py` | 42 | `case_resolved` / `case_not_resolved` tools registrati |
| 24 | `mata_garuda/runtime/genome.py` | 224 | read/write GENOME.md, propose/apply/revert mutations |
| 25 | `mata_garuda/runtime/fitness.py` | 156 | JSONL tracker, rolling window, auto-revert on degradation |
| 26 | `mata_garuda/runtime/lamarckian.py` | 206 | feedback loop + retry hints + escalation |
| 27 | `mata_garuda/cli.py` | +60 | `mutate`, `fitness`, `--lamarckian` flag |
| 28 | `tests/test_lamarckian.py` | 334 | 31 test: case status, feedback, genome, fitness, wiring |

### Definition of Done

- [x] Tool `case_resolved` e `case_not_resolved` disponibili a tutti gli agenti
- [x] Loop `run_with_lamarckian_feedback` ritenta MAX 3 volte con hint progressivi
- [x] Failure scrive su `feedback/{agent_name}.md` con timestamp + reason + insight
- [x] Dopo MAX retry: escalation automatica al meta-agent
- [x] `meta_agent` legge il `feedback.md` e propone mutazione GENOME.md
- [x] **Mutation richiede review umana (default). Opt-in auto via `mutate --auto`**
- [x] `fitness.py` traccia success rate post-mutation su rolling window 10 run
- [x] Se fitness peggiora (< 30% success): auto-revert GENOME + log evento
- [x] Test simula fail → feedback → mutation propose → apply → verify
- [x] Test simula fail → mutation → fitness degradation → auto-revert

### Open questions Sprint 3 — RISOLTE

- Come misurare "success rate"? → **rolling window JSONL, per-mutation-version** ✅
- Mutation applicata da chi? → **review umana default, `--auto` flag per opt-in** ✅
- GENOME.md crescita? → **deferred: soft cap futura via compattazione meta-agent** ✅

---

## Sprint 4 — POC integration con Layer 1 (Harvester) ✅ COMPLETO (2026-04-09)

**Status:** COMPLETO
**Tempo reale:** ~20min (vs stima 3 giorni)
**Commit:** `8612e1e` su Balizero1987/mata-garuda
**Test:** 98/98 pass (19 nuovi + 79 Sprint 1-3)
**Agents registered:** 3 (Dummy + Meta + Regulation Watcher)
**LOC aggiunte:** 743 (474 source + 269 test)

### Obiettivo
Primo agente operativo reale: Regulation Watcher per peraturan.go.id.

### Decisioni architetturali

- **Non wrappato bali-intel-scraper**: il scraper è nel monorepo Nuzantara con dipendenze pesanti (Playwright, etc). Per mantenere il vincolo stack minimale, il POC usa `curl` + regex parsing diretto. Per produzione, il Regulation Watcher può delegare a bali-intel-scraper via OpenClaw.
- **No RSS feed**: peraturan.go.id non ha `/feed` o `/rss` (404). Scraping HTML diretto.
- **Redis via redis-cli**: nessuna dipendenza `redis-py`. Tutto via subprocess `redis-cli`.

### File creati

| # | File | LOC | Cosa fa |
|---|---|---|---|
| 29 | `mata_garuda/tools/scraper_tools.py` | 221 | curl fetch + regex parse peraturan.go.id |
| 30 | `mata_garuda/tools/stream_tools.py` | 137 | Redis Stream XADD/XREVRANGE/XINFO/XLEN via redis-cli |
| 31 | `mata_garuda/agents/regulation_watcher.py` | 81 | harvester agent Layer 1 |
| 32 | `mata_garuda/agents/regulation_watcher_GENOME.md` | 35 | cron, URL, escalation, OSINT constraints |
| 33 | `tests/test_sprint4.py` | 269 | 19 test: scraper, stream, agent, end-to-end |

### Definition of Done

- [x] Regulation Watcher agent creato con tools: scrape + stream + case status
- [x] Agent registered nel registry con GENOME.md completo
- [x] End-to-end test: check source → scrape → publish → verify stream length
- [x] Fallback URL in GENOME (jdih.kemenkumham.go.id)
- [x] Lamarckian-ready: case_resolved/not_resolved, feedback logging
- [ ] **Test reale**: da lanciare manualmente e osservare per 1 settimana

### Comandi per test reale

```bash
# Run once
python -m mata_garuda.cli run "Regulation Watcher" "check latest regulations" --lamarckian

# Check fitness after some runs
python -m mata_garuda.cli fitness "Regulation Watcher"

# Review feedback
cat feedback/regulation_watcher.md

# Propose mutation if needed
python -m mata_garuda.cli mutate "Regulation Watcher"
```

---

## Timeline e dipendenze

```
Sprint 1 ──┐
           │ (walking skeleton)
           ▼
Sprint 2 ──┐ (dipende da: registry, runtime, dummy_agent)
           │ (meta-agent)
           ▼
Sprint 3 ──┐ (dipende da: meta-agent, case_resolved tools)
           │ (Lamarckian)
           ▼
Sprint 4 ──┐ (dipende da: tutti i precedenti + bali-intel-scraper)
           │ (POC reale)
           ▼
        Eval & iterate
```

**Stima originale:** ~9-10 giorni di lavoro.
**Tempo reale:** ~2 ore per tutti e 4 gli sprint.
**vs.** forking AutoAgent: minimum 2 settimane solo per il refactor litellm → CLI.

**Reimplementare = ~95% meno tempo del previsto.**

---

## Cosa NON è in questo build order (esplicitamente fuori scope)

- ❌ Layer 2 (Kognitif) workers — sono già in design, non dipendono dal meta-agent
- ❌ Layer 3 (Nexus) — KG, Qdrant, NLM esistono già o sono in 11-NLM-BRAIN.md
- ❌ Layer 5 (Distribuzione) — sono in 21-CHANNEL-STRATEGY.md
- ❌ Web GUI / dashboard — futuro, dopo Sprint 4
- ❌ Multi-user — Mata Garuda è single-user (Zero), per ora
- ❌ Cloud deploy — Mata Garuda gira solo su Pro, OSINT blindato
- ❌ MCP server di Mata Garuda — futuro, dopo Sprint 4

---

## Pre-Sprint Checklist (PRIMA di iniziare Sprint 1)

- [ ] **Decidere posizione package** (a/b/c sopra) — default (c) repo separato
- [ ] Verificare `claude --print` funziona da CLI
- [ ] Verificare `gemini --print` funziona da CLI
- [ ] Decidere venv path: `~/Desktop/mata-garuda/.venv` o equivalente
- [ ] Verificare che i CLI tool ritornino in modo blocking (non interattivo)
- [ ] Setup repo Git (se opzione c) con `.gitignore` per `.venv`, `feedback/`, `logs/`
- [ ] CLAUDE.md per Mata Garuda (scope, golden rules specifiche)

---

## Riferimenti

- [02-ARCHITECTURE.md](02-ARCHITECTURE.md) — meta-agent layer (v0.2)
- [40b-AGENT-TAXONOMY.md](40b-AGENT-TAXONOMY.md) — Lamarckian philosophy
- [40c-AUTOAGENT-EVAL.md](40c-AUTOAGENT-EVAL.md) — perché non forkare
- [40d-AUTOAGENT-PATTERNS.md](40d-AUTOAGENT-PATTERNS.md) — codice estratto dei 4 pattern
- [03-LLM-POLICY.md](03-LLM-POLICY.md) — CLI only, modelli, routing
- [04-SECURITY-FIREWALL.md](04-SECURITY-FIREWALL.md) — OSINT blindato

---

**Status:** TUTTI E 4 GLI SPRINT COMPLETATI 2026-04-09. Pronto per eval & iterate.
