# Prompt 7/8: Audit Crontab Air (DEDUP URGENTE)

**Macchina:** Air (`antonellosiano@Nuzantara-9`, via `ssh air`)
**Scope:** ~40 righe crontab, 13 job unici, massiccia duplicazione
**Durata stimata:** 20-25 minuti
**Rischio:** MEDIO (eliminare entry duplicate, verificare script)

---

## MISSIONE

Il crontab Air è un disastro — quasi ogni job appare 2 volte (una entry manuale + una dal blocco "NUZANTARA AUTOMATION" generato il 2026-01-18). Devi:

1. Verificare ogni script referenziato
2. Eliminare i duplicati
3. Identificare overlap con Pro/OpenClaw
4. Fixare o eliminare job rotti
5. Produrre un crontab pulito

## CRONTAB ATTUALE (raw)

Esegui su Air:

```bash
ssh air 'crontab -l'
```

### Duplicati Confermati

| Job                   | Entry 1 (manuale) | Entry 2 (automation block)   | Note                |
| --------------------- | ----------------- | ---------------------------- | ------------------- |
| scribe_cron.sh        | `0 2 * * *`       | `0 2 * * *` (block)          | IDENTICA            |
| auto_sentinel.sh      | `0 3 * * *`       | `0 3 * * *` (block)          | IDENTICA            |
| backup-db.sh          | `0 1 * * *`       | `0 1 * * *` (block)          | IDENTICA            |
| daily-monitoring.sh   | `0 8 * * *`       | `0 8 * * *` (block)          | IDENTICA            |
| auto_kb_ingest.sh     | `0 5 * * *`       | `0 5 * * *` (block)          | IDENTICA            |
| auto_judgement_day.sh | `0 16 * * 0`      | `0 16 * * 0` (block)         | IDENTICA            |
| ollama start          | `0 1 * * *`       | `0 2 * * *` (block)          | DUE ORARI DIVERSI!  |
| ollama stop           | `0 4 * * *`       | —                            | + `5 6 * * *` extra |
| auto_test_force.sh    | `15 2 * * *`      | unified_test_force.sh `15 2` | DUE SCRIPT DIVERSI  |
| auto_agent_test.sh    | `30 3 * * *`      | `30 3 * * *` (block)         | IDENTICA            |
| unified_scraper.py    | 04:00 + 16:00     | 04:00 + 16:00 (block)        | IDENTICA            |
| visa_agent.py         | 04:00 + 16:00     | 04:00 + 16:00 (block)        | IDENTICA            |

### Job Unico Rotto

| Job                  | Schedule            | Problema                   |
| -------------------- | ------------------- | -------------------------- |
| run_news_enricher.sh | `0 0,6,12,18 * * *` | **Script MANCANTE** su Air |

### Job Senza Duplicato

| Job                   | Schedule      | Note           |
| --------------------- | ------------- | -------------- |
| auto_intel_scraper.sh | 04:00 + 16:00 | Solo nel block |

## ANALISI PER OGNI JOB UNICO

Per ognuno dei 13 job unici, esegui su Air:

### 1. backup-db.sh (01:00)

```bash
ssh air 'cat ~/Projects/nuzantara/scripts/backup-db.sh'
ssh air 'tail -20 ~/Projects/nuzantara/logs/backup.log'
```

- Cosa backuppa? DB locale Air? O DB Fly.io?
- Overlap con `fly-pg-backup.sh` su Pro?
- Se backuppa il DB locale Air → serve? Air ha un DB locale significativo?

### 2. ollama_cron_window.sh (start 01:00, stop 04:00)

```bash
ssh air 'cat ~/Projects/nuzantara/scripts/ollama_cron_window.sh'
```

- Apre finestra Ollama per task notturni (test, sentinel)
- Start a 01:00 (manuale) E 02:00 (block) → il secondo è ridondante
- Stop a 04:00 (manuale) E 06:05 (block) → il secondo è un safety net
- Proposta: KEEP solo start 01:00 + stop 06:05

### 3. scribe_cron.sh (02:00)

```bash
ssh air 'cat ~/Projects/nuzantara/scripts/scribe_cron.sh'
ssh air 'tail -20 ~/Projects/nuzantara/logs/scribe_cron.log'
```

- Documentazione automatica — cosa documenta? È utile?
- Ultimo run riuscito?

### 4. auto_test_force.sh vs unified_test_force.sh (02:15)

```bash
ssh air 'cat ~/Projects/nuzantara/scripts/auto_test_force.sh'
ssh air 'cat ~/Projects/nuzantara/scripts/unified_test_force.sh'
ssh air 'tail -20 ~/Projects/nuzantara/logs/test_force.log'
ssh air 'tail -20 ~/Projects/nuzantara/logs/unified_test_force.log'
```

- Due script diversi per lo stesso slot → quale è quello giusto?
- Overlap con OpenClaw `nightly-code-quality` e `nightly-autofix-loop`?

### 5. auto_sentinel.sh (03:00)

```bash
ssh air 'cat ~/Projects/nuzantara/scripts/auto_sentinel.sh'
ssh air 'tail -20 ~/Projects/nuzantara/logs/sentinel_nightly.log'
```

- Quality control — cosa controlla?
- Overlap con OpenClaw `nightly-code-quality`?

### 6. auto_agent_test.sh (03:30)

```bash
ssh air 'cat ~/Projects/nuzantara/scripts/auto_agent_test.sh'
ssh air 'tail -20 ~/Projects/nuzantara/logs/agent_test.log'
```

- Testa gli agenti — quali? Come?
- Ha senso su Air o dovrebbe girare su Pro?

### 7. unified_scraper.py (04:00 + 16:00)

```bash
ssh air 'head -50 ~/Projects/nuzantara/apps/bali-intel-scraper/scripts/unified_scraper.py'
ssh air 'tail -20 ~/Projects/nuzantara/logs/scrapers/unified_scraper.log'
```

- Intel scraper — funziona?
- Overlap con LaunchAgent `intel.nightly` su Pro?
- **CRITICO:** Se Pro E Air scrapano → articoli duplicati

### 8. intelligent_visa_agent.py (04:00 + 16:00)

```bash
ssh air 'head -50 ~/Projects/nuzantara/apps/kb/intelligent_visa_agent.py'
ssh air 'tail -20 ~/Projects/nuzantara/logs/scrapers/visa_agent.log'
```

- Scraper dati visa — funziona? Produce output?
- Dove salva i dati?

### 9. auto_intel_scraper.sh (04:00 + 16:00)

```bash
ssh air 'cat ~/Projects/nuzantara/scripts/auto_intel_scraper.sh'
ssh air 'tail -20 ~/Projects/nuzantara/logs/intel_scraper.log'
```

- TERZO scraper allo stesso orario! Overlap con unified_scraper?
- Forse è un wrapper del unified_scraper?

### 10. auto_kb_ingest.sh (05:00)

```bash
ssh air 'cat ~/Projects/nuzantara/scripts/auto_kb_ingest.sh'
ssh air 'tail -20 ~/Projects/nuzantara/logs/kb_ingest.log'
```

- Ingestione KB — cosa ingerisce? Da dove?

### 11. run_news_enricher.sh (ogni 6h) — ROTTO

```bash
ssh air 'ls -la ~/Projects/nuzantara/apps/bali-intel-scraper/scripts/run_news_enricher.sh'
ssh air 'tail -20 ~/Projects/nuzantara/logs/news_enricher.log'
```

- Script MANCANTE — eliminare la entry crontab
- Controllare il log — ha mai funzionato? Cos'era?

### 12. daily-monitoring.sh (08:00)

```bash
ssh air 'cat ~/Projects/nuzantara/scripts/daily-monitoring.sh'
ssh air 'tail -20 ~/Projects/nuzantara/logs/daily_monitoring.log'
```

- Report giornaliero — cosa monitora?
- Overlap con OpenClaw `daily-ops-autopilot`?

### 13. auto_judgement_day.sh (domenica 16:00)

```bash
ssh air 'cat ~/Projects/nuzantara/scripts/auto_judgement_day.sh'
ssh air 'tail -20 ~/Projects/nuzantara/logs/judgement_day.log'
```

- Review settimanale — cosa review?
- Overlap con OpenClaw `weekly-report`?

## AZIONI FINALI

### 1. Genera crontab pulito (SENZA duplicati)

```bash
ssh air 'crontab -l' > /tmp/air-crontab-backup.txt
```

Poi scrivi il nuovo crontab con:

- Solo 1 entry per job
- Nessun job rotto (news_enricher eliminato)
- Commenti chiari per ogni entry
- Orari ottimizzati (nessun conflitto)

```bash
# Genera e applica
ssh air 'cat > /tmp/new-crontab.txt << "EOF"
# === NUZANTARA AIR CRONTAB (cleaned 2026-03-16) ===
# ... contenuto pulito ...
EOF
crontab /tmp/new-crontab.txt'
```

### 2. Verifica

```bash
ssh air 'crontab -l'
```

## OUTPUT RICHIESTO

### Tabella Pre/Post

| Job          | Stato Pre       | Overlap Con       | Decisione | Stato Post    |
| ------------ | --------------- | ----------------- | --------- | ------------- |
| backup-db    | 2x duplicato    | fly-pg-backup Pro | ?         | ?             |
| ollama start | 2 orari diversi | —                 | MERGE     | 1x alle 01:00 |
| scribe       | 2x duplicato    | —                 | DEDUP     | 1x            |
| ...          |                 |                   |           |               |

### Crontab finale pulito (mostra in chat)

### Conteggio: X entry prima → Y entry dopo (riduzione Z%)
