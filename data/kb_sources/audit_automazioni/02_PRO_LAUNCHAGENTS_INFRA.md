# Prompt 2/8: Audit LaunchAgents Infrastrutturali Pro

**Macchina:** Pro (`nuzantara@Nuzantara`)
**Scope:** 13 LaunchAgents infrastrutturali (KeepAlive / RunAtLoad)
**Durata stimata:** 15-20 minuti
**Rischio:** ALTO (servizi core — non spegnere niente senza conferma)

---

## MISSIONE

Verifica la salute dei 13 servizi infrastrutturali che girano H24 su Pro. NON fermare o eliminare niente — solo verificare e riportare.

## LISTA SERVIZI

### Gruppo A: OpenClaw (4 servizi)

1. **ai.openclaw.gateway** — Gateway API porta 18789
   - Verifica: `curl -sf http://localhost:18789/health`
   - PID: `launchctl list | grep openclaw.gateway`
   - Log: `tail -20 ~/.openclaw/logs/gateway.log`
   - Plist: `cat ~/Library/LaunchAgents/ai.openclaw.gateway.plist`

2. **ai.openclaw.node** — Node worker
   - Verifica: `launchctl list | grep openclaw.node`
   - Log: `tail -20 ~/.openclaw/logs/node.log`
   - Nota: exit code -15 (SIGTERM) è NORMALE per cycling

3. **ai.openclaw.tunnel** — Reverse tunnel Pro:18789 → Air:18790
   - Verifica: `launchctl list | grep openclaw.tunnel`
   - Test: `ssh air 'curl -sf http://localhost:18790/health'` — funziona il tunnel?
   - Domanda: serve ancora? Air ha il suo gateway locale

4. **ai.openclaw.watchdog** — Auto-restart gateway+node ogni 60s
   - Verifica: `launchctl list | grep openclaw.watchdog`
   - Script: `cat` il script referenziato nel plist
   - Domanda: il watchdog ha mai riavviato qualcosa? Controlla i log

### Gruppo B: Database & Cache (3 servizi)

5. **homebrew.mxcl.postgresql@17** — PostgreSQL 17 porta 5432
   - Verifica: `pg_isready -h localhost -p 5432`
   - Status: `launchctl list | grep postgresql`
   - Nota: c'è anche postgresql@16 ROTTO — da rimuovere

6. **homebrew.mxcl.redis** — Redis porta 6379
   - Verifica: `redis-cli ping` (deve rispondere PONG)
   - Status: `launchctl list | grep redis`

7. **homebrew.mxcl.ollama** — Ollama LLM server
   - Verifica: `curl -sf http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d.get(\"models\",[]))} models loaded')"`
   - Modelli: lista modelli caricati
   - VRAM: `ollama ps` — quanta VRAM usano?

### Gruppo C: Applicazioni (4 servizi)

8. **com.n8n.server** — n8n workflow automation porta 5678
   - Verifica: `curl -sf http://localhost:5678 -o /dev/null -w "%{http_code}"`
   - Domanda CRITICA: n8n è effettivamente USATO? Quanti workflow attivi? O è un residuo?
   - Se non usato → candidato ELIMINAZIONE (risparmia RAM)

9. **com.claude-max-api** — Claude Max API proxy
   - Verifica: `launchctl list | grep claude-max-api`
   - Plist: leggi per capire cosa fa e su che porta gira
   - Domanda: serve ancora? È il proxy per OpenClaw o è superato?

10. **com.nuzantara.prime-dashboard** — Streamlit dashboard porta 8501
    - Verifica: `curl -sf http://localhost:8501 -o /dev/null -w "%{http_code}"`
    - Domanda: Prime Intelligence è attivamente usato? O è in standby?

11. **com.nuzantara.prime-tunnel** — Cloudflare tunnel per prime.balizero.com
    - Verifica: `curl -sf https://prime.balizero.com -o /dev/null -w "%{http_code}"`
    - Se il dashboard non è usato, anche il tunnel è inutile

### Gruppo D: Monitor (2 servizi)

12. **ai.openclaw.monitor-air** — Monitora Air da Pro ogni 5 min
    - Verifica: `launchctl list | grep monitor-air`
    - Log: `tail -20 ~/.openclaw/logs/monitor-air.log`
    - Ultimo alert? Funziona?

13. **com.nuzantara.zombie-hunter** — Killa processi zombie Claude ogni 60s
    - Verifica: `launchctl list | grep zombie-hunter`
    - Script: leggi per capire cosa killa e quando
    - Ha mai killato qualcosa? Log?
    - Domanda: serve ancora o era per un problema specifico risolto?

### BONUS: Servizio ROTTO da rimuovere

14. **homebrew.mxcl.postgresql@16** — PG16 residuo, conflitto con PG17
    - Status: `launchctl list | grep postgresql@16`
    - AZIONE: `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/homebrew.mxcl.postgresql@16.plist`
    - Poi: `rm ~/Library/LaunchAgents/homebrew.mxcl.postgresql@16.plist`
    - Verifica che PG17 funziona ancora dopo

## OUTPUT RICHIESTO

Tabella:

| Servizio         | PID | Porta | Salute | RAM MB | Decisione | Note |
| ---------------- | --- | ----- | ------ | ------ | --------- | ---- |
| openclaw.gateway | ?   | 18789 | ?      | ?      | KEEP/?    |      |
| ...              |     |       |        |        |           |      |

Per servizi candidati all'eliminazione (n8n, claude-max-api, prime-\*), fornisci motivazione e impatto.

**NON ELIMINARE NIENTE** senza prima riportare in chat e aspettare conferma.
