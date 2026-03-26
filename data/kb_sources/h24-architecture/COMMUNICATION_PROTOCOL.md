# COMMUNICATION PROTOCOL — Come parlano i Generali

**Version:** 2.0 (2026-02-14)

---

## Architettura: Hub & Spoke + Event Bus

```
                         ┌──────────────────────────┐
                         │     PostgreSQL (Fly.io)   │
                         │  generals_tasks           │
                         │  generals_memory          │
                         │  generals_activity        │
                         │  generals_locks           │
                         └──────────┬───────────────┘
                                    │ (shared state)
                                    │
     ┌──────────┐          ┌────────┴────────┐          ┌──────────┐
     │ Pro Mac  │◄────────►│   ZAN (Hub)     │◄────────►│ Fly.io   │
     │ Ollama   │ SSH/Node │   Air Gateway   │  HTTPS   │ Backend  │
     │ Cursor   │          │                 │          │ Qdrant   │
     └──────────┘          └───┬──┬──┬──┬────┘          └──────────┘
                               │  │  │  │
                    ┌──────────┘  │  │  └──────────┐
                    ▼             ▼  ▼             ▼
              ┌──────────┐ ┌──────┐ ┌──────┐ ┌──────────┐
              │  KODEX   │ │GRAV. │ │SENT. │ │   VOX    │
              │ (coding) │ │(ops) │ │(intel)│ │(content) │
              └──────────┘ └──────┘ └──────┘ └──────────┘
                                                    │
                                              ┌─────┘
                                              ▼
                                        ┌──────────┐
                                        │  FLASH   │
                                        │ (triage) │
                                        └──────────┘
```

---

## 3 Canali di Comunicazione

### Canale 1: OpenClaw Sub-Agent Sessions (Primario)

**Come funziona:** Zan spawna un generale come sub-agent isolato. Il generale ha il suo contesto, i suoi tool, la sua sessione. Quando finisce, il risultato torna a Zan.

```
Zan: sessions_spawn(agentId="coding-general", prompt="Fix bug in search.py")
  → Kodex esegue in sessione isolata
  → Kodex restituisce risultato
  → Zan riceve e processa
```

**Quando usare:** Per task diretti, sincroni, con risultato atteso.

**Pro:**

- Isolamento completo (un generale non puo corrompere l'altro)
- Contesto separato (non inquina la sessione Zan)
- Max 6 sub-agent concorrenti (configurato in openclaw.json)

**Contro:**

- Sincrono: Zan aspetta il risultato
- Non persiste tra sessioni OpenClaw

---

### Canale 2: PostgreSQL Task Queue (Asincrono)

**Come funziona:** Un generale inserisce un task nel database. Un altro generale lo prende e lo esegue. Il risultato viene scritto nel database.

```sql
-- Zan inserisce task per Kodex
INSERT INTO generals_tasks (task_type, title, payload, priority)
VALUES ('code', 'Fix IndexError in search.py', '{"file": "search.py", "error": "IndexError"}', 8);

-- Kodex fa polling e prende il task
UPDATE generals_tasks SET status='assigned', assigned_to='coding_general'
WHERE task_type='code' AND status='pending'
ORDER BY priority DESC
LIMIT 1;

-- Kodex completa
UPDATE generals_tasks SET status='completed', result='{"commit": "abc123"}'
WHERE id = 42;
```

**Quando usare:** Task asincroni, batch processing, task che possono aspettare.

**Pro:**

- Persistente (sopravvive a restart)
- Prioritizzato (priority 1-10)
- Auditabile (ogni task e tracciato)
- Lock-safe (`FOR UPDATE SKIP LOCKED`)

**Contro:**

- Richiede polling (attualmente 30s interval)
- Latenza minima 30s

---

### Canale 3: Filesystem Bus (Syncthing)

**Come funziona:** File markdown condivisi tra Air e Pro via Syncthing. Usato per comunicazione persistente, task delegation cross-Mac, e memory condivisa.

```
~/.openclaw/workspace/
├── messages/          # Messaggi tra gateway Air e Pro
│   ├── air-to-pro/    # Zan → Pro Gateway
│   └── pro-to-air/    # Pro Gateway → Zan
├── tasks/             # Task delegation
│   ├── TASK-001.md    # Task definition
│   └── TASK-001-result.md  # Result
└── memory/            # Shared memory
    ├── CORE_MEMORY.md
    ├── reports/
    └── daily/
```

**Quando usare:**

- Comunicazione Air ↔ Pro
- Task che il Pro deve eseguire autonomamente
- Reports e documenti da condividere

**Pro:**

- Sopravvive a restart di entrambi i Mac
- Leggibile da umani
- Versionabile
- Zero latency per file locali

**Contro:**

- Syncthing ha ~2-5 secondi di propagation delay
- No real-time (va bene per task asincroni)
- Richiede convenzioni di naming

---

## Protocollo Anti-Conflitto

### Regola 1: Un Task, Un Generale

```sql
-- Lock atomico: solo un generale prende il task
SELECT id FROM generals_tasks
WHERE status = 'pending' AND task_type = 'code'
ORDER BY priority DESC
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

Se due generali fanno polling nello stesso momento, `SKIP LOCKED` garantisce che solo uno prende il task. L'altro passa al prossimo.

### Regola 2: Resource Locking per File

```python
# Prima di editare un file:
locked = await coordinator.acquire_lock(
    resource_key="file:backend/main.py",
    owner_general="coding_general",
    ttl_seconds=120  # Max 2 minuti
)

if not locked:
    # Qualcun altro sta editando. Skip o aspetta.
    logger.warning("file:backend/main.py locked by another general")
    return

# Edita il file...

# Quando finito:
await coordinator.release_lock("file:backend/main.py", "coding_general")
```

**TTL automatico:** Se un generale crasha senza rilasciare il lock, il lock scade dopo 60-120 secondi. Gravity li pulisce ogni 5 minuti.

### Regola 3: Git Branch Isolation

| Generale | Branch Pattern         | Esempio                       |
| -------- | ---------------------- | ----------------------------- |
| Kodex    | `feat/kodex-{issue}`   | `feat/kodex-fix-search`       |
| Gravity  | `fix/gravity-{desc}`   | `fix/gravity-deploy-rollback` |
| Sentinel | `data/sentinel-{desc}` | `data/sentinel-kb-update`     |
| Vox      | `content/vox-{desc}`   | `content/vox-blog-visa-guide` |

**Mai push diretto su `main`.** Sempre branch + PR (tranne Level 1: typo fix).

### Regola 4: Gerarchia di Priorita

```
GRAVITY (stop-the-line authority)
  > KODEX (code changes)
    > SENTINEL (data changes)
      > VOX (content changes)
        > FLASH (read-only, mai conflitti)
```

Se Gravity dice "stop", tutti si fermano. Perche: un sistema down e peggio di un bug non fixato o un articolo non pubblicato.

---

## Inter-Agent Communication Patterns

### Pattern A: Request-Response (Sincrono)

```
Zan: "Sentinel, quanto costa un KITAS investor?"
  → sessions_spawn("intelligence-general", "Verifica prezzo KITAS investor da PRICING_REFERENCE.md")
  → Sentinel: "KITAS Investor 2Y Offshore: IDR 17,000,000 (~$1,105)"
  → Zan: risponde al cliente
```

**Latenza:** 3-10 secondi

### Pattern B: Fire-and-Forget (Asincrono)

```
Zan: "Kodex, c'e un bug in search.py"
  → INSERT INTO generals_tasks (task_type='code', title='Fix search.py bug', priority=8)
  → Zan continua a rispondere ai clienti
  → Kodex prende il task quando libero
  → Kodex completa e logga il risultato
  → Gravity deploia se test passano
```

**Latenza:** 30s-10min (dipende da complessita)

### Pattern C: Pipeline (Multi-step)

```
Sentinel: genera report competitor
  → Salva in generals_memory(key="competitor_report_2026_02_14")
  → Vox: legge da generals_memory
  → Vox: genera social post basato sul report
  → Vox: salva draft in memory/drafts/
  → Zero: approva via Telegram
  → Vox: pubblica
```

### Pattern D: Cross-Mac Delegation

```
Zan (Air): "Kodex, questo task richiede Cursor IDE"
  → Zan scrive ~/.openclaw/workspace/tasks/TASK-042.md
  → Syncthing propaga al Pro (~3 sec)
  → Pro Gateway legge il task
  → Pro: cursor agent --model cursor-ultra "contenuto di TASK-042.md"
  → Pro scrive tasks/TASK-042-result.md
  → Syncthing propaga all'Air (~3 sec)
  → Zan legge il risultato
```

**Alternativa piu veloce (webhooks):**

```bash
# Air → Pro (immediato)
curl -X POST http://192.168.0.17:18789/hooks/agent \
  -H "Authorization: Bearer a5981c7f..." \
  -d '{"prompt": "Esegui cursor agent su search.py", "agentId": "coding"}'
```

---

## Scaling Futuro

### Oggi (2 Mac)

- Hub & Spoke con Zan su Air
- Pro come nodo compute
- Sufficiente per <100 lead/giorno

### Domani (3+ Mac o VPS)

- **Aggiungere nodo:** Installare OpenClaw, registrare come node dell'Air
- **Load balancing:** Zan distribuisce task al nodo meno carico (via heartbeat)
- **Database condiviso:** Tutti i nodi usano lo stesso PostgreSQL su Fly.io
- **Zero cambio architettura:** Hub & Spoke scala naturalmente

### Dopodomani (Kubernetes/Cloud)

- Migrare generali in container
- OpenClaw Gateway come servizio cloud
- Database gia su Fly.io (nessun cambiamento)
- Eliminare dipendenza da Mac fisici
