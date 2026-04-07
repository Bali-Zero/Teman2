# Guardian V5 — Self-Evolving Intelligence

## Prompt per prossima sessione Claude Code (Opus 4.6, think MAX)

```
# MISSIONE: Guardian V5 — Auto-Evolving Code Intelligence

## Chi sei
Sei l'architetto principale di Nuzantara. Devi progettare e implementare il modulo di auto-evoluzione per Guardian V4, trasformandolo in V5: un sistema che impara, cresce, e si migliora da solo.

## Cosa hai
Guardian V4 è live con:
- Decision Logger: ogni azione → PostgreSQL (guardian_decisions, guardian_risk_scores, 2 tabelle, migration 098)
- Risk Scorer: 0-100 pesato (RBAC 40%, API 30%, Cache 20%, Dead Code 10%)
- Auto-Rollback: git tag snapshot, circuit breaker 3 rollback
- Regression Monitor: 1h post-merge, 3 check consecutivi → rollback
- Red Team: 20 test adversariali settimanali
- SEO Guardian: check giornaliero
- RAGAS Eval: 100 Q&A settimanali
- Surgeon: 2 fixer deterministici (DTZ005, ANN204) + Claude Code bridge (non usato in auto)
- Watchdog: 5 audit AST/regex, baseline enforcement
- learn.py: FILE VUOTO — è qui che devi lavorare

Il pezzo mancante: Guardian accumula dati (decisions, risk scores, fix results) ma non li usa per migliorarsi. learn.py deve diventare il cervello che chiude il loop.

## Il tuo processo

### Fase 1: Ricerca parallela
Dispatcha ai 3 LLM della federation SIMULTANEAMENTE (usa ai-dispatch.sh):

**Gemini (explore)**: "Analizza lo stato dell'arte su self-improving autonomous code agents. Sistemi di riferimento: SWE-agent, Qodo Cover Agent, Google AutoML applicato a code quality, GitHub Copilot Workspace plan→implement→validate. Focus su: feedback loop architecture, safety boundaries per sistemi che modificano se stessi, gradual autonomy expansion. Output: lista di pattern architetturali con pro/contro."

**DeepSeek (reasoning)**: "Dato un sistema che ha N decision records (timestamp, check_type, finding, severity, action_taken, risk_score) e M risk score snapshots nel tempo, progetta un algoritmo che: 1) identifica pattern ricorrenti nei finding, 2) calibra automaticamente i pesi del risk scorer basandosi su correlazione tra score pre-regressione e regressioni effettive, 3) genera nuovi check deterministici da pattern ripetuti 5+ volte. Vincoli: Python 3.11, no ML libraries, max $0.50/settimana per LLM calls. Output: pseudocodice delle 3 funzioni core."

**Codex (sandbox)**: "Testa questo concetto: dato il git log degli ultimi 30 giorni di un monorepo Python e i ruff violations attuali, è possibile predire quali file avranno nuovi bug la prossima settimana? Analizza la correlazione tra: frequenza di modifica, complessità ciclomatica, numero di import, e probabilità di regressione. Output: script Python che calcola un 'fragility score' per file."

### Fase 2: Sintesi autonoma
Raccogli i 3 output. NON copiarli — usali come input per il TUO ragionamento. Punti dove i 3 convergono = segnale forte. Punti dove divergono = serve il tuo giudizio. Punti che nessuno copre = blind spot da investigare.

La tua decisione finale deve essere coerente con:
- La codebase reale (leggi i file prima di decidere)
- I vincoli operativi (Air machine 16GB, $0 base / $0.50 LLM, no nuove dipendenze)
- Il principio "MODEL PROPOSES, PYTHON VALIDATES" del Surgeon
- I Golden Rules del progetto (async first, type hints, no hardcoded secrets, logger not print)

### Fase 3: Implementazione
Implementa learn.py e tutto ciò che serve. Il risultato deve:
1. Funzionare (test passing)
2. Essere sicuro (non può peggiorare il sistema)
3. Essere osservabile (logga in guardian_decisions con component='learn')
4. Crescere nel tempo (più dati accumula, meglio funziona)

## Vincoli
- Python 3.11, solo stdlib + asyncpg + httpx
- learn.py vive in apps/evaluator/core_guardian/
- Ogni modifica auto-generata passa per Surgeon (worktree isolato, 11 gate)
- File intoccabili: fly.toml, Dockerfile, dependencies.py, zantara_core.py, alembic/, middleware/, channels/
- Mai toccare file di test
- Budget: $0 ciclo base, max $0.50/settimana per ciclo LLM-assisted opzionale

## File da leggere PRIMA di progettare
- apps/evaluator/core_guardian/ (tutti i file V4)
- apps/evaluator/core_guardian/checks/ (i 5 audit)
- apps/evaluator/core_guardian/tests/ (pattern test)
- apps/backend-rag/backend/migrations/migration_098_guardian_decisions.py (schema DB)
```
