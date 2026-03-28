# CELL v2 — Sensori + Memoria Persistente + Test Reasoner

**Data:** 2026-03-28
**Stato:** Approvato
**Scope:** `apps/cell/`

---

## Obiettivo

Tre miglioramenti indipendenti all'organismo CELL:

1. **Sensori aggiuntivi** — CELL percepisce DB, Qdrant e errori 5xx oltre al semplice `/health`
2. **Memoria FAISS persistente** — i pattern appresi sopravvivono ai restart via PostgreSQL
3. **Test del reasoner** — verifica empirica che il cervello LLM si attivi correttamente su RED

---

## 1. Nuovi Sensori

### Architettura

Il `PulseEngine` chiama attualmente un solo `HealthSensor`. Diventa un aggregatore
di più sensori che restituiscono ciascuno un `SensorReading` con `status` e `metadata`.

```
PulseEngine
  ├── HealthSensor        (già esiste) → /health
  ├── DatabaseSensor      (nuovo)      → /health .database.status
  ├── QdrantSensor        (nuovo)      → /health .database.collections / total_documents
  └── ErrorRateSensor     (nuovo)      → /api/metrics/errors (nuovo endpoint leggero)
```

### Sensori

**DatabaseSensor** (`sensors/database_sensor.py`)

- Legge `body.database.status` dalla risposta `/health` (già disponibile nel `HealthReading`)
- `connected` → GREEN, altro → YELLOW, assente → RED
- Nessuna chiamata HTTP aggiuntiva (riusa il body già fetchato)

**QdrantSensor** (`sensors/qdrant_sensor.py`)

- Legge `body.database.collections` e `body.database.total_documents` da `/health`
- Confronta con la lettura precedente (stato interno)
- Collections < 8 → YELLOW; drop docs > 5% rispetto a baseline → YELLOW
- Nessuna chiamata HTTP aggiuntiva

**ErrorRateSensor** (`sensors/error_rate_sensor.py`)

- Chiama `GET /api/cell/metrics` (nuovo endpoint backend, 1 query SQL)
- Conta 5xx negli ultimi 5 minuti da `cell_pulse_log.error_message`
- > 3 errori in 5min → YELLOW; > 10 → RED
- Cooldown: usa timestamp ultima lettura, non chiama più di 1x/min

### Aggregazione nel PulseEngine

Il `PulseEngine` aggrega i risultati: lo status finale è il peggiore tra tutti i sensori.
I metadata di ogni sensore vengono passati al `SlowReasoner` come contesto aggiuntivo.

### Vettore FAISS esteso

Da 5 a 8 dimensioni:

```
[green, yellow, red, rt_norm, budget_norm, db_ok, qdrant_ok, error_rate_norm]
```

---

## 2. Memoria FAISS Persistente

### Problema

`PatternIndex` è in-memory: a ogni restart di CELL (boot, crash, deploy) si azzera.
CELL ricomincia da zero invece di sfruttare la storia accumulata.

### Soluzione

Aggiungere persistenza via PostgreSQL (asyncpg già disponibile in `cell/core/db.py`).

### Schema DB

```sql
CREATE TABLE IF NOT EXISTS cell_patterns (
    id              SERIAL PRIMARY KEY,
    health_status   VARCHAR(16) NOT NULL,
    response_time_ms INTEGER NOT NULL,
    budget_pct      FLOAT NOT NULL,
    action          VARCHAR(64) NOT NULL,
    reason          TEXT NOT NULL,
    confidence      FLOAT NOT NULL,
    tier_used       INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cell_patterns_created_at ON cell_patterns (created_at DESC);
```

### Modifiche a PatternIndex

- `__init__`: al boot chiama `await load_from_db()` — carica gli ultimi 500 pattern
- `add()`: aggiunge al FAISS index in-memory E chiama `await persist_to_db(entry)`
- `persist_to_db()`: INSERT nella tabella `cell_patterns` (fire-and-forget, errori loggati)
- `load_from_db()`: SELECT ultimi 500 ordinati per `created_at DESC`, ricostruisce index

### Interfaccia

```python
class PatternIndex:
    async def load_from_db(self) -> int: ...          # returns count loaded
    async def persist_to_db(self, entry: PatternEntry) -> None: ...
    def add(self, ...) -> None: ...                   # sync (FAISS) + async persist
    def find_similar(self, ...) -> PatternEntry | None: ...
```

`add()` resta sincrono per il FAISS; `persist_to_db` viene schedulata come task asyncio.

### Integrazione in main.py

Dopo la creazione del `PatternIndex`, aggiungere:

```python
patterns_loaded = await pattern_index.load_from_db()
logger.info(f"PatternIndex: {patterns_loaded} patterns loaded from DB")
```

---

## 3. Test Reasoner su RED

### Obiettivo

Verifica empirica end-to-end che il `SlowReasoner` proponga un'azione sensata
quando il backend è RED, e che il `DNAInterpreter` la validi correttamente.

### File

`apps/cell/tests/test_reasoner_red.py`

### Struttura del test

```python
async def test_reasoner_proposes_action_on_red():
    """Verifica che su RED il reasoner proponga restart_service o alert_human."""
    reasoner = SlowReasoner(gemini_api_key=os.environ.get("GOOGLE_API_KEY", ""))
    interpreter = DNAInterpreter()

    proposal = await reasoner.think(
        health_status="red",
        response_time_ms=30_000,
        error_message="Connection refused",
        recent_history=[{"health_status": "red"} * 5],
        budget_spent=0.5,
        budget_limit=10.0,
    )

    assert proposal.action in ("restart_service", "alert_human", "read_logs")
    assert proposal.confidence >= 0.6
    assert proposal.tier_used in (0, 1)  # Qwen o Gemini, non Opus

    validation = interpreter.validate(
        action_name=proposal.action,
        budget_spent=0.5,
        budget_limit=10.0,
        confidence=proposal.confidence,
    )
    assert validation.approved or validation.rule_violated is not None  # approvato o bloccato con motivo

async def test_reasoner_no_action_on_green():
    """Verifica che su GREEN il reasoner non proponga azioni."""
    reasoner = SlowReasoner(gemini_api_key=os.environ.get("GOOGLE_API_KEY", ""))

    proposal = await reasoner.think(
        health_status="green",
        response_time_ms=3_000,
        error_message="",
        recent_history=[],
        budget_spent=0.0,
        budget_limit=10.0,
    )

    assert proposal.action == "none"
```

### Esecuzione

```bash
cd apps/cell && source .venv/bin/activate
GOOGLE_API_KEY=... PYTHONPATH=. pytest tests/test_reasoner_red.py -v -s
```

Il flag `-s` mostra l'output LLM in tempo reale per debug.

---

## Ordine di implementazione

1. **Memoria persistente** (migration DB + PatternIndex) — fondamenta, nessuna dipendenza
2. **Test reasoner** — verifica lo stato attuale, poi si arricchisce con i nuovi sensori
3. **Nuovi sensori** — ultima fase, dipende da PatternIndex esteso (8 dim)

---

## File da creare/modificare

| File                                 | Tipo     | Note                                                              |
| ------------------------------------ | -------- | ----------------------------------------------------------------- |
| `cell/core/db.py`                    | modifica | aggiungi `create_patterns_table`, `save_pattern`, `load_patterns` |
| `cell/memory/pattern_index.py`       | modifica | `load_from_db`, `persist_to_db`, vettore 8-dim                    |
| `cell/sensors/database_sensor.py`    | nuovo    | legge body `/health`                                              |
| `cell/sensors/qdrant_sensor.py`      | nuovo    | legge body `/health`                                              |
| `cell/sensors/error_rate_sensor.py`  | nuovo    | chiama `/api/cell/metrics`                                        |
| `cell/core/pulse.py`                 | modifica | aggrega multi-sensor, passa metadata a reasoner                   |
| `cell/main.py`                       | modifica | `await pattern_index.load_from_db()` al boot                      |
| `backend/app/routers/cell_status.py` | modifica | aggiungi endpoint `/api/cell/metrics`                             |
| `tests/test_reasoner_red.py`         | nuovo    | 2 test async, nessun mock                                         |
