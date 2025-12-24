# Fly Logs - Tail Logs Fly.io

Visualizza i log in tempo reale di un'app Fly.io.

## Argomenti

- `$ARGUMENTS`: Nome app (opzionale, default: `nuzantara-rag`)
  - `backend` o `rag` → nuzantara-rag
  - `frontend` o `mouth` → nuzantara-mouth
  - `scraper` o `intel` → bali-intel-scraper
  - `media` → zantara-media

## Istruzioni

1. **Determina app target**:
   - Se `$ARGUMENTS` vuoto o `backend` o `rag` → `nuzantara-rag`
   - Se `frontend` o `mouth` → `nuzantara-mouth`
   - Se `scraper` o `intel` → `bali-intel-scraper`
   - Se `media` → `zantara-media`

2. **Fetch logs**:
   ```bash
   fly logs -a <app-name> -n 100
   ```

3. **Analisi automatica**:
   - Cerca pattern di errore: `ERROR`, `Exception`, `Traceback`, `500`
   - Cerca warning: `WARNING`, `WARN`
   - Evidenzia errori critici

4. **Suggerimenti**:
   - Se trovi errori, suggerisci possibili cause
   - Se trovi pattern ripetuti, segnalalo

## Apps disponibili

| Alias | App Fly.io | Descrizione |
|-------|------------|-------------|
| `backend`, `rag` | nuzantara-rag | Backend FastAPI |
| `frontend`, `mouth` | nuzantara-mouth | Frontend Next.js |
| `scraper`, `intel` | bali-intel-scraper | Intel scraper |
| `media` | zantara-media | Media service |

## Output atteso

```
## Fly Logs: nuzantara-rag

### Ultimi 100 log

[timestamp] INFO: Application started
[timestamp] INFO: Health check passed
[timestamp] ERROR: Connection refused to Qdrant
...

### Analisi

#### Errori trovati (2)
1. **Connection refused to Qdrant** (3 occorrenze)
   - Causa probabile: Qdrant cloud timeout
   - Suggerimento: Verificare status Qdrant dashboard

2. **TypeError in agentic_rag.py:142**
   - Causa: NoneType in response
   - Suggerimento: Aggiungere null check

#### Warning (5)
- Rate limit approaching: 3 occorrenze
- Slow query detected: 2 occorrenze

### Status attuale
App: healthy
Machines: 1 running
```
