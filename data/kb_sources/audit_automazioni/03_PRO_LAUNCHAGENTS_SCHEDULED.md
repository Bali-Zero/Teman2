# Prompt 3/8: Audit LaunchAgents Scheduled/Non Caricati Pro

**Macchina:** Pro (`nuzantara@Nuzantara`)
**Scope:** 13 LaunchAgents schedulati, rotti, o non caricati
**Durata stimata:** 20-25 minuti
**Rischio:** BASSO (la maggior parte non è caricata)

---

## MISSIONE

Questi sono i LaunchAgents "di secondo livello" — scheduled task, servizi rotti, plist orfani. Per ognuno devi decidere: caricare, fixare, o eliminare il plist.

## LISTA

### Gruppo A: Attivi ma da verificare (2)

1. **com.balizero.intel.nightly** — Intel scraper pipeline (01:00 daily)
   - Plist: `cat ~/Library/LaunchAgents/com.balizero.intel.nightly.plist`
   - Verifica: `launchctl list | grep intel.nightly`
   - Log: trova il log file referenziato nel plist, `tail -30`
   - Domanda: funziona? Ultimo run riuscito? Overlap con cron Air `auto_intel_scraper.sh`?
   - **CRITICO:** Se sia Pro che Air scrapano → duplicazione di articoli

2. **com.nuzantara.nightly-sync** — Pro↔Air repo sync (03:00 daily)
   - Plist: `cat ~/Library/LaunchAgents/com.nuzantara.nightly-sync.plist`
   - Verifica: `launchctl list | grep nightly-sync`
   - Script: `cat ~/scripts/nuzantara-sync.sh`
   - Domanda: c'è già un post-commit hook che fa git push → Air? Il nightly sync è ridondante?

### Gruppo B: Rotti (3)

3. **com.nuzantara.db-backup** — Backup DB locale (schedule?)
   - Plist: `cat ~/Library/LaunchAgents/com.nuzantara.db-backup.plist`
   - Status: exit code 1
   - Script: `cat ~/scripts/db-backup.sh`
   - Diagnosi: probabilmente usa `pg_dump` da path PG16 → fixare con PG17 path
   - Verifica overlap: c'è già `fly-pg-backup.sh` nel crontab (backup PRODUCTION), questo fa backup LOCALE
   - Decisione: serve un backup locale se abbiamo il backup Fly.io? Se sì, fixare. Se no, eliminare.

4. **com.peekaboo.bridge** — Bridge server Peekaboo
   - Plist: `cat ~/Library/LaunchAgents/com.peekaboo.bridge.plist`
   - Script mancante: `~/.openclaw/peekaboo-server.sh`
   - NON CARICATO — innocuo
   - Ricerca: cos'era Peekaboo? Un bridge per screenshot? Browser? Se è legacy → ELIMINARE plist

5. **homebrew.mxcl.postgresql@16** — PG16 residuo
   - **AZIONE:** Vedi Prompt 02 per la rimozione (gestita lì)
   - Se non gestita nel Prompt 02, falla qui

### Gruppo C: Non Caricati — Valutare se attivare (5)

6. **com.balizero.translate.hourly** — Traduzione articoli ogni ora
   - Plist: `cat ~/Library/LaunchAgents/com.balizero.translate.hourly.plist`
   - Script referenziato: esiste? Cosa fa?
   - Contesto: la sessione precedente ha implementato i18n IT per il blog
   - Domanda: serve tradurre automaticamente ogni ora? O è meglio on-demand?
   - Se lo script funziona → valuta se CARICARE o ELIMINARE basandoti su utilità

7. **com.balizero.warroom.morning** — War Room mattutino (07:30)
   - Plist: `cat ~/Library/LaunchAgents/com.balizero.warroom.morning.plist`
   - Script: esiste? Cosa fa?
   - Contesto: il War Room era un sistema di content production pipeline
   - Domanda: è sostituito dai workflow chains OpenClaw (chain_daily_ops_autopilot)?

8. **com.nuzantara.full-test-suite** — Test suite domenicale (08:00)
   - Plist: `cat ~/Library/LaunchAgents/com.nuzantara.full-test-suite.plist`
   - Script: `cat ~/scripts/full-test-suite.sh`
   - Domanda: è sostituito dal cron OpenClaw `nightly-autofix-loop`? Se sì → ELIMINARE
   - Se diverso → valuta CARICARE

9. **com.nuzantara.qwen-code-review** — Code review con Qwen/Ollama (10:00 daily)
   - Plist: `cat ~/Library/LaunchAgents/com.nuzantara.qwen-code-review.plist`
   - Script: `cat ~/scripts/qwen-code-review.sh`
   - Domanda: funziona? Produce output utile? O è un esperimento abbandonato?
   - Se funziona → potenzialmente UTILE (review locale gratuita)

10. **com.nuzantara.vector-reindex-check** — Verifica reindex vettori (lunedì 09:00)
    - Plist: `cat ~/Library/LaunchAgents/com.nuzantara.vector-reindex-check.plist`
    - Script: `cat ~/scripts/vector-reindex-check.py`
    - Domanda: controlla la coerenza delle collection Qdrant? È importante per data integrity?

### Gruppo D: Google residui (3 — probabilmente SKIP)

11. **com.google.GoogleUpdater.wake** — Auto-update Google
12. **com.google.keystone.agent** — Keystone
13. **com.google.keystone.xpcservice** — Keystone XPC

- Questi sono di sistema Google, probabilmente per Chrome
- SKIP — non toccare

## DECISIONI GUIDATE

Per ogni servizio non caricato, valuta:

- **C'è overlap con OpenClaw cron?** → ELIMINARE il LaunchAgent (OpenClaw è il runtime principale)
- **È un esperimento abbandonato?** (script non aggiornato da >30 giorni) → ELIMINARE
- **Ha valore unico?** (nessun equivalente altrove) → CARICARE o POTENZIARE
- **Script mancante o rotto?** → ELIMINARE il plist

## OUTPUT RICHIESTO

Tabella:

| Servizio      | Script Esiste | Ultimo Run | Overlap Con       | Decisione | Azione |
| ------------- | ------------- | ---------- | ----------------- | --------- | ------ |
| intel.nightly | ?             | ?          | Air scraper?      | ?         | ?      |
| nightly-sync  | ?             | ?          | post-commit hook? | ?         | ?      |
| db-backup     | ?             | exit 1     | fly-pg-backup?    | ?         | ?      |
| ...           |               |            |                   |           |        |

Per ogni ELIMINAZIONE, fornisci il comando:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/NOME.plist
rm ~/Library/LaunchAgents/NOME.plist
```

Per ogni CARICAMENTO:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/NOME.plist
```
