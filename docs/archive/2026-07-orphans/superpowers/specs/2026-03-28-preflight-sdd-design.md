# Preflight SDD — Specification-Driven Development Pre-Implementation Workflow

**Date:** 2026-03-28
**Status:** Approved
**Validated by:** NLM NB-1 (Nuzantara Codebase & Architecture) — 20 citations, 2026-03-28

---

## 1. Goal

Formalizzare una regola obbligatoria di pre-implementazione: prima di scrivere codice su qualsiasi
task non triviale, eseguire un ciclo multi-agente di brainstorming+validazione che produce una
**spec come deliverable di prima classe**. Il codice è output secondario; la spec sopravvive
al codice.

**Outcome atteso:** Ridurre bug da assunzioni non verificate, evitare conflitti architetturali,
ancorare ogni implementazione alla ground truth del codebase.

---

## 2. Trigger — Quando eseguire il Preflight

Trigger **oggettivi** (non basati su giudizio):

| Trigger                                                                  | Livello |
| ------------------------------------------------------------------------ | ------- |
| Task tocca 3+ file in app diverse                                        | L1      |
| Nuova feature che non esiste nel codebase                                | L1      |
| Modifica a `dependencies.py`, `service_initializer.py`, `app_factory.py` | L2      |
| Refactor che tocca 3+ app del monorepo                                   | L2      |
| Schema change (Alembic migration)                                        | L2      |
| KBLI, visa, normativa indonesiana (Claude hallucina)                     | L2      |
| Pre-deploy Fly.io backend                                                | L2      |
| Nuova architettura o pattern di sistema                                  | L3      |
| Feature critica per produzione (auth, billing, RAG pipeline)             | L3      |

**Non richiedono preflight:** Fix bug isolato (1-2 file), aggiornamento componente UI singolo,
fix typo/lint, update doc.

---

## 3. Pipeline — 3 Livelli

### L1 — Quick Scan (10-15 min)

```
explore → reasoning → spec
```

- `gemini-explore`: mappa dipendenze e pattern esistenti (1M ctx)
- `deepseek-reasoning`: analizza approcci e trade-off
- Output: spec in `docs/superpowers/specs/`

### L2 — Full Preflight (45 min)

```
explore + search (parallel) → NLM validation → reasoning → redteam → spec
```

- `gemini-explore` + `gemini-search` in parallelo
- NLM `oracolo` (NB-1 codebase): validation gate con citazioni
- `deepseek-reasoning`: propone 2-3 approcci
- `claude-review`: red team della soluzione proposta
- Output: spec + log in `audit.jsonl`

### L3 — Deep Preflight (90 min)

```
[L2 completo] → codex-sandbox → secondo ciclo NLM → HITL → spec
```

- Come L2 + `codex-sandbox` per prototipo isolato
- Secondo passaggio NLM per validare il prototipo
- Human-in-the-loop (HITL): approvazione umana prima di spec finale

---

## 4. Ruolo di NLM nel Preflight

**NLM è un SERVICE, non un AGENT** (tassonomia v3.1).

- **Chiamato da:** l'orchestratore direttamente (non classificato/dispatchato)
- **Quando:** DOPO explore+search, PRIMA di reasoning
- **Ruolo:** Validation gate — ancora la proposta alla ground truth interna con citazioni precise
- **Non è:** un partecipante al brainstorming, non genera idee

```
explore → search → [NLM GATE] → reasoning → spec
                        ↓
               anchoring con citazioni da NB-1
               segnala conflitti architetturali
               identifica file esistenti rilevanti
```

**NB-1 usato:** `f6ecd115-dd89-4c9b-b3dd-071e0e2f1876` — "Nuzantara Codebase & Architecture"
(72 sources, auto-refresh daily 04:30 WITA via `nlm_nb1_daily_refresh` cron su Air)

**NLM Fallback** (CRITICO — finding NB-1):
Se NLM non risponde entro 60s o auth fallisce:

1. Log degradazione in `audit.jsonl` con `"nlm_status": "unavailable"`
2. Sostituire con `gemini-search "codebase architecture {task}"` come fallback
3. NON bloccare la pipeline su NLM failure — il preflight continua in modalità degradata

---

## 5. Implementazione

### 5.1 Location — Python ADK in `workflows.py` (CRITICO — finding NB-1)

> ⚠️ NB-1 finding critico: implementare `preflight` in `ai-dispatch.sh` bash
> **viola** la Federation v3 architecture. `ai-dispatch.sh` è wrapper thin.
> La logica di orchestrazione complessa DEVE vivere in `apps/federation/workflows.py`.

**Approccio scelto:** Nuovo `Workflow` Python in `workflows.py` con DAG di step.

**`ai-dispatch.sh` ruolo:** thin wrapper che chiama
`python -m apps.federation.workflows run preflight-l1 "task"`.

### 5.2 Nuovi Workflow da registrare in `workflows.py`

```python
# --- 6. Preflight L1 — Quick Scan ---
register(Workflow(
    id="preflight-l1",
    name="Preflight L1 — Quick Scan",
    description="Pre-implementation: explore + reasoning → spec (10-15 min)",
    steps=[
        WorkflowStep(
            name="explore",
            agent="gemini-explore",
            prompt_template="Mappa il codebase per: {task}. Identifica file rilevanti, "
                "pattern esistenti, dipendenze critiche. Usa 1M context. "
                "Focus su: apps/backend-rag/, apps/mouth/, apps/federation/.",
        ),
        WorkflowStep(
            name="reasoning",
            agent="deepseek-reasoning",
            prompt_template="Proponi 2-3 approcci per: {task}. "
                "Contesto codebase: {prev_explore}. "
                "Per ogni approccio: trade-off, rischi, compatibilità con pattern esistenti.",
            depends_on=["explore"],
        ),
    ],
))

# --- 7. Preflight L2 — Full ---
register(Workflow(
    id="preflight-l2",
    name="Preflight L2 — Full Preflight",
    description="Pre-implementation: explore+search → NLM → reasoning → redteam → spec (45 min)",
    steps=[
        WorkflowStep(
            name="explore",
            agent="gemini-explore",
            prompt_template="Mappa il codebase per: {task}. Identifica file, pattern, "
                "dipendenze critiche. Focus su apps/backend-rag/, apps/mouth/, apps/federation/.",
        ),
        WorkflowStep(
            name="search",
            agent="gemini-search",
            prompt_template="Cerca best practice e pattern 2025-2026 per: {task}. "
                "Se rilevante: normativa indonesiana, KBLI 2025, Fly.io/Vercel patterns.",
        ),
        # NLM step: orchestratore chiama direttamente via oracolo service (NON dispatch)
        # Il WorkflowStep nlm-validate usa agent="claude-code" che esegue:
        #   ./scripts/ai-dispatch.sh oracolo-nb NB-1 "<combined explore+search output>"
        WorkflowStep(
            name="nlm-validate",
            agent="claude-code",  # orchestratore proxy — chiama NLM service direttamente
            prompt_template="Consulta NB-1 (Nuzantara Codebase) su: {task}. "
                "Esegui: ./scripts/ai-dispatch.sh oracolo-nb f6ecd115 '{prev_explore}'. "
                "Riporta citazioni e finding critici. "
                "Se NLM non disponibile: log in audit.jsonl e continua con fallback search.",
            depends_on=["explore", "search"],
        ),
        WorkflowStep(
            name="reasoning",
            agent="deepseek-reasoning",
            prompt_template="Proponi 2-3 approcci per: {task}. "
                "Codebase: {prev_explore}. Search: {prev_search}. "
                "NLM validation: {prev_nlm-validate}. "
                "Per ogni approccio: trade-off, rischi, compatibilità architetturale.",
            depends_on=["nlm-validate"],
        ),
        WorkflowStep(
            name="redteam",
            agent="claude-review",
            prompt_template="Red team: trova falle nell'approccio proposto per {task}. "
                "Analisi: {prev_reasoning}. NLM findings: {prev_nlm-validate}. "
                "Verifica: sicurezza, breaking changes, performance, data integrity.",
            depends_on=["reasoning"],
        ),
    ],
))

# --- 8. Preflight L3 — Deep ---
register(Workflow(
    id="preflight-l3",
    name="Preflight L3 — Deep Preflight",
    description="Pre-implementation: L2 + sandbox prototype + second NLM + HITL (90 min)",
    steps=[
        # Steps L2 (explore, search, nlm-validate, reasoning, redteam) +
        WorkflowStep(
            name="sandbox-proto",
            agent="codex-sandbox",
            prompt_template="Prototipa in sandbox isolato: {task}. "
                "Approccio scelto: {prev_reasoning}. "
                "NON toccare database reale. Testa il caso principale.",
            depends_on=["redteam"],
        ),
        WorkflowStep(
            name="nlm-validate-proto",
            agent="claude-code",
            prompt_template="Seconda validazione NLM su prototipo: {prev_sandbox-proto}. "
                "Verifica che il prototipo sia coerente con architettura in NB-1.",
            depends_on=["sandbox-proto"],
        ),
    ],
))
```

### 5.3 `orchestrator.py` — aggiornare `classify_task()`

Aggiungere al `CLASSIFY_PROMPT` la sezione preflight triggers:

```python
PREFLIGHT_TRIGGERS = {
    "L1": [
        "new feature", "add endpoint", "new component", "nuova feature",
        "nuovo endpoint", "aggiungi"
    ],
    "L2": [
        "refactor", "migration", "alembic", "kbli", "visa", "normativa",
        "deploy", "dependencies.py", "service_initializer"
    ],
    "L3": [
        "architecture", "architettura", "auth", "billing", "rag pipeline",
        "sistema critico", "critical system"
    ],
}
```

Aggiungere logica in `run_federation()`:

```python
preflight_level = detect_preflight_level(task)
if preflight_level:
    return await execute_workflow(f"preflight-{preflight_level}", task)
```

### 5.4 Audit logging per escape hatch (finding NB-1)

Ogni bypass del preflight (--skip-preflight o --no-preflight) DEVE loggare in `audit.jsonl`:

```python
def log_preflight_bypass(task: str, reason: str, user: str = "unknown") -> None:
    """Log any preflight bypass to audit trail."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "preflight_bypass",
        "task": task[:200],
        "reason": reason,
        "user": user,
        "machine": os.uname().nodename,
    }
    AUDIT_FILE.parent.mkdir(exist_ok=True)
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
```

### 5.5 `ai-dispatch.sh` — thin wrapper

Aggiungere case branch nel dispatch script (thin, delega a Python):

```bash
preflight|preflight-l1|preflight-l2|preflight-l3)
    LEVEL="${COMMAND/preflight/}"
    LEVEL="${LEVEL:-l2}"  # default L2
    LEVEL="${LEVEL#-}"    # rimuovi leading dash
    TASK="${EXTRA:-$2}"
    if [ -z "$TASK" ]; then
        echo "Usage: $0 preflight[-l1|-l2|-l3] \"task description\""
        exit 1
    fi
    python -m apps.federation.workflows run "preflight-${LEVEL}" "$TASK"
    ;;
```

---

## 6. Spec Output

Ogni run preflight produce:

- **`docs/superpowers/specs/YYYY-MM-DD-<slug>-preflight.md`** — spec documento
- **`ai-dispatch-output/preflight-<timestamp>.json`** — output grezzo agenti
- **`ai-dispatch-output/audit.jsonl`** — append-only audit log

Struttura spec output:

```markdown
# <Feature> — Preflight Spec

**Preflight level:** L2
**Date:** YYYY-MM-DD
**NLM validated:** yes/no (fallback: gemini-search)

## Exploration findings

## Regulatory/search findings

## NLM validation (citations)

## Proposed approaches (2-3)

## Red team findings

## Recommended approach

## Files to create/modify

## Known risks
```

---

## 7. Regola CLAUDE.md

Il seguente testo va aggiunto in `CLAUDE.md §2` (Claude Code Behavior Rules):

````markdown
### Preflight SDD Rule (OBBLIGATORIO)

Prima di implementare qualsiasi task non triviale, eseguire il preflight:

| Trigger (oggettivo)                              | Livello |
| ------------------------------------------------ | ------- |
| Task tocca 3+ file in app diverse                | L1      |
| Nuova feature (non esiste nel codebase)          | L1      |
| Modifica a dependencies.py / service_initializer | L2      |
| Refactor 3+ app, Alembic migration, KBLI/visa    | L2      |
| Pre-deploy Fly.io backend                        | L2      |
| Nuova architettura, feature critica produzione   | L3      |

**Esecuzione:**

```bash
./scripts/ai-dispatch.sh preflight "descrizione task"       # L2 default
./scripts/ai-dispatch.sh preflight-l1 "task semplice"      # L1 quick
./scripts/ai-dispatch.sh preflight-l3 "task critico"       # L3 deep
```
````

**Regola NLM:** NLM è un SERVICE (tassonomia v3.1), non un agente. È il gate di
validazione chiamato DOPO explore+search, PRIMA di reasoning. Se NLM non disponibile:
log in audit.jsonl + fallback a gemini-search — il preflight NON si blocca.

**Escape hatch:** `--skip-preflight` disponibile per fix urgenti, MA logga in
`ai-dispatch-output/audit.jsonl` con motivo obbligatorio.

```

---

## 8. NB-1 Update

Dopo implementazione:
1. Aggiungere `docs/superpowers/specs/2026-03-28-preflight-sdd-design.md` come source in NB-1
2. Aggiungere `apps/federation/workflows.py` (aggiornato) come source refresh
3. Trigger refresh NB-1: `./scripts/ai-dispatch.sh oracolo-nb f6ecd115 "preflight workflow added"`

---

## 9. Implementation Order

1. `workflows.py` — registra Workflow preflight-l1, l2, l3
2. `orchestrator.py` — aggiunge PREFLIGHT_TRIGGERS + `log_preflight_bypass()`
3. `ai-dispatch.sh` — aggiunge case branch thin wrapper
4. `CLAUDE.md §2` — aggiunge Preflight SDD Rule
5. NB-1 — aggiunge spec come source
6. Commit + push

---

## 10. Out of Scope

- UI per gestire preflight spec (non serve)
- Integrazione con GitHub PR (futura, non ora)
- Metriche di qualità preflight (YAGNI)
- Versioning automatico spec (YAGNI)

---

*Spec prodotta con: NLM NB-1 (20 citazioni) + DeepSeek R1 + Codex + Gemini search*
*NB-1 finding critici incorporati: Python ADK > bash, NLM fallback, audit trail*
```
