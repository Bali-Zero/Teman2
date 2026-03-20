# Super Agent Design — Ricerca Interna Claude

**Data:** 2026-03-20
**Status:** Draft — in attesa risultati Gemini + Grok

---

## 1. Inventario Infrastruttura Disponibile

### OpenClaw Runtime

- **Versione:** 2026.3.7
- **Gateway:** `127.0.0.1:18789` (loopback, auth token)
- **CLI:** `openclaw agent --agent <id> --message <text> --thinking <level> --timeout <secs> --json`
- **Cron engine:** Built-in, supporta cron expressions, timezone, stagger, delivery Telegram
- **Session management:** Sessioni isolate per cron job (`sessionTarget: "isolated"`)

### Agenti Disponibili

| Agent    | Primary Model      | Fallbacks                   | Sandbox | Tools Deny                     |
| -------- | ------------------ | --------------------------- | ------- | ------------------------------ |
| `main`   | claude-opus-4-6    | qwen3.5:27b, qwen3.5:9b     | off     | nessuno                        |
| `social` | claude-haiku-4-5   | qwen3.5:9b                  | default | nessuno                        |
| `coder`  | ollama/qwen3.5:27b | claude-opus-4-6, qwen3.5:9b | off     | web_search, web_fetch, browser |

### Cron Jobs Esistenti (18 totali)

- `nightly-code-quality` (03:00 WITA) — linting via MCP, report Telegram. **Usa agent `coder`**.
- `system-doctor` (ogni 4h) — health check completo, usa `main` (Opus 4.6). **MODELLO da seguire.**
- `tech-orchestrator` (ogni 4h) — orchestrazione tecnica
- Vari business jobs (client-health, compliance, daily-ops, etc.)

### Modello da Seguire: system-doctor

Il system-doctor è il nostro agente più maturo:

- Gira ogni 4h con Claude Opus 4.6
- Sessione isolata (non inquina altre sessioni)
- Output: report markdown strutturato con emoji per severità
- Delivery: Telegram con report sintetico
- Duration: ~131 secondi per run
- Token usage: ~35K tokens/run (~$0.07/run → ~$0.42/giorno)
- Azioni: NESSUNA autonoma per problemi MEDIUM — solo reporting

---

## 2. Analisi Test Suite (Asset Critico)

### Composizione

- **454 file di test** totali
- **164 file** usano mock (MagicMock/AsyncMock)
- **157 file** con test async
- **86 file** dipendono da DB (asyncpg/db_pool)
- **Tempo full run:** ~7m 26s
- **Struttura:** unit/, integration/, services/, compliance/, channels/, generated/

### Metriche Ruff (Production Code)

Il codebase ha già 0 errori ruff con la config di default. Con `--select ALL`:

- 2683 `logging-f-string` (G004) — stile, non bug
- 941 `line-too-long` (E501) — cosmetico
- 833 `blind-except` (BLE001) — **potenziale area di miglioramento**
- 803 `fast-api-non-annotated-dependency` (FAST002) — FastAPI pattern
- 638 `error-instead-of-exception` (TRY400) — **area di miglioramento**
- 531 `any-type` (ANN401) — type safety
- 266 `missing-type-function-argument` (ANN001) — type safety
- 190 `datetime-now-without-tzinfo` (DTZ005) — **bug potenziale**
- 126 `complex-structure` (C901) — **area di miglioramento**

### Aree Prioritarie per il Super Agent

1. **blind-except (833)** — `except Exception` che mangiano errori silenziosamente
2. **datetime senza timezone (190)** — bug latente in un sistema che serve Bali (WITA)
3. **complex-structure (126)** — funzioni troppo complesse, candidati per refactor
4. **error-instead-of-exception (638)** — `logger.error()` dove servirebbe `logger.exception()`

---

## 3. Design del Super Agent

### Principio Fondamentale

**L'agente NON deve mai essere più intelligente di quello che può verificare.**

Se non può dimostrare che il suo fix è corretto (test che passano + ruff clean + no regression), NON deve committare.

### Architettura: 3 Livelli

```
┌──────────────────────────────────────────┐
│  LIVELLO 1: WATCHDOG (ogni 30 min)       │
│  Script Python locale, NO LLM            │
│  - pytest --tb=no -q → count passed      │
│  - Confronta con baseline                │
│  - Se passed < baseline → alert Telegram │
│  - Se passed > baseline → update baseline│
│  Costo: $0/giorno                        │
└──────────────┬───────────────────────────┘
               │ Se test suite verde
┌──────────────▼───────────────────────────┐
│  LIVELLO 2: SCOUT (ogni 6h, cron)       │
│  Agent: coder (Qwen 27b locale)          │
│  - ruff check → identifica top 3 issue   │
│  - Classifica per impatto/rischio         │
│  - Scrive report in .agent/decisions/     │
│  - Report Telegram con candidati          │
│  Costo: $0/giorno (Ollama locale)         │
└──────────────┬───────────────────────────┘
               │ Se candidato trovato + approvazione umana
┌──────────────▼───────────────────────────┐
│  LIVELLO 3: SURGEON (on-demand)          │
│  Agent: main (Claude Opus 4.6)           │
│  - Riceve task specifico dallo Scout     │
│  - git checkout -b auto-fix/xxx          │
│  - Applica fix chirurgico                │
│  - pytest → verifica no regression       │
│  - Scrive ADR in .agent/decisions/adr/   │
│  - git commit (branch isolata, mai main) │
│  - Report con diff e ADR                 │
│  Costo: ~$0.10-0.50/fix (Opus)           │
└──────────────────────────────────────────┘
```

### Perché 3 livelli e non 1?

| Livello  | Frequenza | Modello               | Rischio                | Costo      |
| -------- | --------- | --------------------- | ---------------------- | ---------- |
| Watchdog | 30min     | Nessuno (Python puro) | Zero                   | $0         |
| Scout    | 6h        | Qwen 27b locale       | Zero (solo lettura)    | $0         |
| Surgeon  | On-demand | Opus 4.6              | Basso (branch isolata) | ~$0.30/fix |

Il costo stimato mensile: **$0-15** (dipende da quanti fix il Surgeon fa).

### Fasi di Maturità

**Fase 1 (settimana 1): Solo Watchdog + Scout**

- Watchdog monitora, Scout identifica, nessuno fixa
- L'umano decide cosa fixare basandosi sui report Scout
- Validazione del sistema senza rischio

**Fase 2 (settimana 2-3): Surgeon con approvazione umana**

- Scout propone, umano approva, Surgeon esegue
- Fix solo su branch isolate
- ADR obbligatorio per ogni fix

**Fase 3 (mese 2+): Surgeon autonomo per task a basso rischio**

- Task definiti come "safe": formatting, type hints, docstrings
- Task definiti come "unsafe": logic changes, API changes, DB queries
- Il Surgeon esegue automaticamente solo task "safe"
- Task "unsafe" richiedono sempre approvazione

---

## 4. Guardrails Specifici

### File Intoccabili (mai modificare)

```
fly.toml
Dockerfile
.env*
backend/main.py
backend/main_cloud.py
backend/app/dependencies.py
backend/app/core/config.py
backend/prompts/zantara_core.py
alembic/
requirements*.txt
```

### Scope Permesso

```
# SAFE (Surgeon può fixare senza approvazione in Fase 3)
backend/services/**/*.py    — logic refactoring
backend/app/routers/**/*.py — router improvements
backend/utils/**/*.py       — utility improvements
backend/tests/**/*.py       — test improvements

# UNSAFE (richiede sempre approvazione)
backend/app/core/**/*.py    — core config
backend/db/**/*.py          — database layer
backend/prompts/**/*.py     — prompt engineering
backend/middleware/**/*.py  — auth/middleware
```

### Constraint Quantitativi

- Max diff per commit: **100 righe** (force small, reviewable changes)
- Max file modificati per commit: **3**
- Test passed DEVE essere >= baseline (hard constraint)
- Ruff violations NON possono aumentare (soft constraint)

### Circuit Breaker

- 3 fix consecutivi che falliscono il test → agente si ferma per 24h
- Alert Telegram al proprietario
- Log in `.agent/decisions/circuit_breaker_log.jsonl`

---

## 5. Metriche di Successo

### Week 1 (Watchdog + Scout only)

- [ ] Watchdog rileva correttamente le regressioni
- [ ] Scout identifica issue reali (non falsi positivi)
- [ ] Report Telegram sono utili e concisi
- [ ] Nessun intervento automatico sul codice

### Week 2-3 (Surgeon con approvazione)

- [ ] Surgeon produce fix che passano i test al primo tentativo (target: >80%)
- [ ] ADR sono leggibili e utili
- [ ] Branch isolate pulite, facili da revieware
- [ ] Tempo medio per fix: <5 minuti

### Month 2+ (Surgeon autonomo su task safe)

- [ ] Blind-except ridotti da 833 a <500
- [ ] Missing type hints ridotti da 266 a <100
- [ ] Complex structures ridotti da 126 a <80
- [ ] Nessuna regression introdotta (0 test rotti dall'agente)
- [ ] Costo mensile < $15

---

## 6. Domande Aperte (per Gemini + Grok)

1. **Il pattern "3 livelli" è overkill?** O c'è un modo più semplice che funziona?
2. **Circuit breaker:** 3 è il numero giusto? Spotify usa un numero diverso?
3. **ADR auto-generati:** Qualcuno li ha effettivamente trovati utili, o diventano rumore?
4. **Ollama locale come Scout:** Qwen 27b è abbastanza per identificare code smells, o serve un modello più grande?
5. **Costo reale:** $0.30/fix è realistico per Opus, o sottostimato?
6. **Concorrenza:** Come gestire se l'agente gira mentre sto committando? Git lock? Branch naming convention?

---

## 7. Implementazione Tecnica (Post-Ricerca)

### File da creare

```
apps/evaluator/core_guardian/
├── watchdog.py          # Livello 1: confronto baseline
├── scout.py             # Livello 2: identificazione issue
├── surgeon.py           # Livello 3: fix + ADR
├── guardrails.json      # Config: file intoccabili, scope, limiti
├── baseline.json        # Snapshot test suite (auto-updated)
└── README.md            # Documentazione operativa

.agent/decisions/
├── adr/                 # Architecture Decision Records
├── scout_reports/       # Report dello Scout
└── circuit_breaker.jsonl # Log circuit breaker
```

### Integrazione OpenClaw

```bash
# Watchdog: NON usa OpenClaw, gira come script Python puro via cron di sistema
# Scout: usa agent coder (locale, gratis)
openclaw cron add --name "core-guardian-scout" \
  --schedule "0 */6 * * *" --tz "Asia/Makassar" \
  --agent coder \
  --message "[scout prompt]" \
  --delivery telegram --to 1125336968

# Surgeon: usa agent main (Opus), invocato manualmente o dal Scout
openclaw agent --agent main --message "[surgeon prompt]" --thinking high --timeout 600
```
