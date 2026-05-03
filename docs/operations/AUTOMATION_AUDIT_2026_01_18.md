# Automation Audit - 2026-01-18

## Stato Attuale Automatismi

### ✅ Già Configurati (Cron Jobs Attivi)

| Tool                | Schedule                 | Script                      | Status    |
| ------------------- | ------------------------ | --------------------------- | --------- |
| **Scribe**          | 6:00, 16:00 daily        | `auto_scribe.sh`            | ✅ Attivo |
| **Sentinel**        | 3:00 daily               | `auto_sentinel.sh`          | ✅ Attivo |
| **Intel Scraper**   | 4:00, 16:00 daily        | `auto_intel_scraper.sh`     | ✅ Attivo |
| **Judgement Day**   | 16:00 Sunday             | `auto_judgement_day.sh`     | ✅ Attivo |
| **KB Ingest**       | 5:00 daily               | `auto_kb_ingest.sh`         | ✅ Attivo |
| **News Enricher**   | 0:00, 6:00, 12:00, 18:00 | `run_news_enricher.sh`      | ✅ Attivo |
| **Unified Scraper** | 4:00, 16:00 daily        | `unified_scraper.py`        | ✅ Attivo |
| **Visa Agent**      | 4:00, 16:00 daily        | `intelligent_visa_agent.py` | ✅ Attivo |

### ⚠️ Duplicati/Conflitti

**Scribe:**

- ❌ `auto_scribe.sh` già schedulato (6:00, 16:00)
- ⚠️ `setup_scribe_cron.sh` crea nuovo cron (2:00) → **DUPLICATO**

**Raccomandazione:** Rimuovere `auto_scribe.sh` dai cron esistenti e usare solo `scribe_cron.sh` alle 2:00 AM.

### ❌ Non Automatizzati (Ma Disponibili)

| Tool                 | Script                | Raccomandazione                       |
| -------------------- | --------------------- | ------------------------------------- |
| **DB Backup**        | `backup-db.sh`        | ⚠️ Dovrebbe essere schedulato (daily) |
| **Daily Monitoring** | `daily-monitoring.sh` | ⚠️ Dovrebbe essere schedulato (daily) |
| **Health Checks**    | Sentinel Phase 3      | ✅ Già incluso in Sentinel            |

## Raccomandazioni

### 1. Consolidare Scribe Cron

**Problema:** Due cron job per Scribe (6:00/16:00 e nuovo 2:00)

**Soluzione:**

```bash
# Rimuovere vecchi cron
crontab -e
# Elimina le righe con auto_scribe.sh

# Usare solo il nuovo
./scripts/setup_scribe_cron.sh
```

### 2. Aggiungere DB Backup Automatico

**Script:** `scripts/backup-db.sh`

**Raccomandazione:** Daily backup alle 1:00 AM (prima di Scribe)

```bash
# Aggiungere a crontab
0 1 * * * /Users/antonellosiano/Projects/nuzantara/scripts/backup-db.sh
```

### 3. Aggiungere Daily Monitoring

**Script:** `scripts/daily-monitoring.sh`

**Raccomandazione:** Daily alle 8:00 AM (dopo tutti i processi notturni)

```bash
# Aggiungere a crontab
0 8 * * * /Users/antonellosiano/Projects/nuzantara/scripts/daily-monitoring.sh
```

### 4. Verificare Sentinel Coverage

**Status:** ✅ Già schedulato alle 3:00 AM

**Verifica:** Assicurarsi che Sentinel controlli:

- ✅ Linting (Ruff)
- ✅ Testing (Pytest)
- ✅ Health checks (Qdrant, DB)
- ⚠️ Security audit (pip-audit) - verificare se attivo

## Cron Job Schedule Ottimizzato

**Timeline Giornaliera Consigliata:**

| Time  | Tool                       | Purpose                    |
| ----- | -------------------------- | -------------------------- |
| 0:00  | News Enricher              | Process news articles      |
| 1:00  | **DB Backup**              | Backup database (NEW)      |
| 2:00  | **Scribe**                 | Update documentation       |
| 3:00  | Sentinel                   | Quality control            |
| 4:00  | Intel Scraper + Visa Agent | Fetch new data             |
| 5:00  | KB Ingest                  | Knowledge base updates     |
| 6:00  | News Enricher              | Process news articles      |
| 8:00  | **Daily Monitoring**       | Health check summary (NEW) |
| 12:00 | News Enricher              | Process news articles      |
| 16:00 | Intel Scraper + Visa Agent | Fetch new data             |
| 18:00 | News Enricher              | Process news articles      |

**Sunday Only:**

- 16:00 | Judgement Day | Weekly evaluation

## Script di Setup Completo

Creare `scripts/setup_all_cron.sh` per configurare tutti gli automatismi:

```bash
#!/bin/bash
# Setup All Automation Cron Jobs
# Configures all recommended cron jobs for Nuzantara

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Backup existing crontab
crontab -l > "$PROJECT_ROOT/crontab.backup.$(date +%Y%m%d)" 2>/dev/null || true

# Remove old Scribe cron (if exists)
crontab -l 2>/dev/null | grep -v "auto_scribe.sh" | crontab - || true

# Add all cron jobs
(crontab -l 2>/dev/null; cat <<EOF
# ==========================================
# NUZANTARA AUTOMATION CRON JOBS
# ==========================================

# Documentation (Scribe) - Daily at 2:00 AM
0 2 * * * $PROJECT_ROOT/scripts/scribe_cron.sh

# Quality Control (Sentinel) - Daily at 3:00 AM
0 3 * * * $PROJECT_ROOT/scripts/auto_sentinel.sh

# Database Backup - Daily at 1:00 AM
0 1 * * * $PROJECT_ROOT/scripts/backup-db.sh

# Daily Monitoring - Daily at 8:00 AM
0 8 * * * $PROJECT_ROOT/scripts/daily-monitoring.sh

# Intel Scraper - Daily at 4:00 AM and 4:00 PM
0 4 * * * $PROJECT_ROOT/scripts/auto_intel_scraper.sh
0 16 * * * $PROJECT_ROOT/scripts/auto_intel_scraper.sh

# KB Ingest - Daily at 5:00 AM
0 5 * * * $PROJECT_ROOT/scripts/auto_kb_ingest.sh

# News Enricher - Every 6 hours
0 0,6,12,18 * * * $PROJECT_ROOT/apps/bali-intel-scraper/scripts/run_news_enricher.sh

# Judgement Day - Sunday at 4:00 PM
0 16 * * 0 $PROJECT_ROOT/scripts/auto_judgement_day.sh

# Unified Scraper - Daily at 4:00 AM and 4:00 PM
0 4 * * * cd $PROJECT_ROOT/apps/bali-intel-scraper/scripts && /usr/bin/python3 unified_scraper.py >> $PROJECT_ROOT/logs/scrapers/unified_scraper.log 2>&1
0 16 * * * cd $PROJECT_ROOT/apps/bali-intel-scraper/scripts && /usr/bin/python3 unified_scraper.py >> $PROJECT_ROOT/logs/scrapers/unified_scraper.log 2>&1

# Visa Agent - Daily at 4:00 AM and 4:00 PM
0 4 * * * cd $PROJECT_ROOT/apps/kb && /usr/bin/python3 intelligent_visa_agent.py >> $PROJECT_ROOT/logs/scrapers/visa_agent.log 2>&1
0 16 * * * cd $PROJECT_ROOT/apps/kb && /usr/bin/python3 intelligent_visa_agent.py >> $PROJECT_ROOT/logs/scrapers/visa_agent.log 2>&1
EOF
) | crontab -

echo "✅ All automation cron jobs configured!"
echo "📋 View with: crontab -l"
```

## Conclusione

**Non serve solo Scribe!** Il sistema ha bisogno di:

1. ✅ **Scribe** - Documentazione (già automatizzato)
2. ✅ **Sentinel** - Quality control (già automatizzato)
3. ⚠️ **DB Backup** - Backup automatico (MANCA)
4. ⚠️ **Daily Monitoring** - Health checks (MANCA)
5. ✅ **Intel Scraper** - News processing (già automatizzato)
6. ✅ **KB Ingest** - Knowledge base (già automatizzato)

**Prossimi Step:**

1. Consolidare cron Scribe (rimuovere duplicati)
2. Aggiungere DB Backup cron
3. Aggiungere Daily Monitoring cron
4. Creare script di setup completo
