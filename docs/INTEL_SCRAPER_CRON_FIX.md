# Intel Scraper Cron Fix - Problema "Operation not permitted"

**Data Analisi:** 2026-01-24  
**Problema:** Cron job Intel Scraper non viene eseguito su macOS

---

## 🔍 PROBLEMA IDENTIFICATO

### Errore nei Log

```
/bin/bash: /Users/antonellosiano/Desktop/nuzantara/scripts/auto_intel_scraper.sh: Operation not permitted
```

Questo errore si ripete ogni volta che il cron tenta di eseguire lo script.

### Cause Identificate

1. **macOS Security Restrictions**
   - macOS Gatekeeper blocca l'esecuzione di script da cron
   - Attributo `com.apple.provenance` presente sul file
   - macOS richiede permessi espliciti per eseguire script da cron

2. **Cron Job Duplicati**
   - 6 entry duplicate nel crontab per `auto_intel_scraper.sh`
   - Stesso script schedulato più volte alle stesse ore

3. **Environment Variables Mancanti**
   - Cron non carica automaticamente `.zshrc` o `.bashrc`
   - PATH non include pyenv
   - Variabili d'ambiente Python non disponibili

4. **Path Issues**
   - Script usa path assoluto hardcoded
   - Non funziona se il progetto viene spostato

---

## ✅ SOLUZIONE

### 1. Rimuovere Attributi macOS Bloccanti

```bash
# Rimuovere attributi di quarantena
xattr -d com.apple.quarantine /Users/antonellosiano/Desktop/nuzantara/scripts/auto_intel_scraper.sh 2>/dev/null || true
xattr -d com.apple.provenance /Users/antonellosiano/Desktop/nuzantara/scripts/auto_intel_scraper.sh 2>/dev/null || true

# Verificare permessi
chmod +x /Users/antonellosiano/Desktop/nuzantara/scripts/auto_intel_scraper.sh
```

### 2. Pulire Crontab Duplicati

```bash
# Backup crontab corrente
crontab -l > crontab.backup.$(date +%Y%m%d-%H%M%S)

# Rimuovere tutte le entry duplicate di auto_intel_scraper.sh
crontab -l | grep -v "auto_intel_scraper.sh" | crontab -

# Aggiungere solo UNA entry pulita
(crontab -l 2>/dev/null; echo "0 4 * * * /Users/antonellosiano/Desktop/nuzantara/scripts/auto_intel_scraper.sh >> /Users/antonellosiano/Desktop/nuzantara/logs/intel_scraper.log 2>&1"; echo "0 16 * * * /Users/antonellosiano/Desktop/nuzantara/scripts/auto_intel_scraper.sh >> /Users/antonellosiano/Desktop/nuzantara/logs/intel_scraper.log 2>&1") | crontab -
```

### 3. Migliorare Script con Environment Setup

Creare uno script wrapper migliorato che carica correttamente l'ambiente:

```bash
#!/bin/bash
# Intel Scraper Cron Wrapper - macOS Compatible
# Fixes: Environment variables, PATH, Python path

# Load shell environment
export HOME="/Users/antonellosiano"
[ -f "$HOME/.zshrc" ] && source "$HOME/.zshrc" 2>/dev/null
[ -f "$HOME/.bashrc" ] && source "$HOME/.bashrc" 2>/dev/null

# Set PATH with pyenv
export PATH="$HOME/.pyenv/shims:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Project directory (auto-detect from script location)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRAPER_DIR="$PROJECT_DIR/apps/bali-intel-scraper"
LOG_FILE="$PROJECT_DIR/logs/intel_scraper.log"

# Ensure logs directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Log start
DATE=$(date "+%Y-%m-%d %H:%M:%S")
echo "[$DATE] Starting Intel Scraper (Mode: Full)..." >> "$LOG_FILE"
echo "[$DATE] PATH: $PATH" >> "$LOG_FILE"
echo "[$DATE] Python: $(which python3)" >> "$LOG_FILE"

# Change to scraper directory
cd "$SCRAPER_DIR" || {
    echo "[$DATE] ❌ Failed to cd to $SCRAPER_DIR" >> "$LOG_FILE"
    exit 1
}

# Load .env.local if exists
if [ -f "$SCRAPER_DIR/.env.local" ]; then
    export $(grep -v '^#' "$SCRAPER_DIR/.env.local" | xargs)
    echo "[$DATE] Loaded .env.local" >> "$LOG_FILE"
fi

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_DIR/apps/backend-rag/backend:$PYTHONPATH"

# Find Python executable
PYTHON_EXEC=$(which python3)
if [ -z "$PYTHON_EXEC" ]; then
    echo "[$DATE] ❌ Python3 not found in PATH" >> "$LOG_FILE"
    exit 1
fi

# Run the pipeline
echo "[$DATE] Executing: $PYTHON_EXEC scripts/run_intel_feed.py --mode full" >> "$LOG_FILE"
"$PYTHON_EXEC" scripts/run_intel_feed.py --mode full >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

# Log result
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$DATE] ✅ Scraper completed successfully." >> "$LOG_FILE"
else
    echo "[$DATE] ❌ Scraper FAILED with exit code $EXIT_CODE." >> "$LOG_FILE"
fi

echo "----------------------------------------" >> "$LOG_FILE"
exit $EXIT_CODE
```

### 4. Alternativa: Usare LaunchAgent invece di Cron

Su macOS, `launchd` è più affidabile di `cron`:

**File:** `~/Library/LaunchAgents/com.balizero.intel-scraper.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.balizero.intel-scraper</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/antonellosiano/Desktop/nuzantara/scripts/auto_intel_scraper.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>4</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/antonellosiano/Desktop/nuzantara/logs/intel_scraper.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/antonellosiano/Desktop/nuzantara/logs/intel_scraper_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/antonellosiano/.pyenv/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>/Users/antonellosiano</string>
    </dict>
</dict>
</plist>
```

**Comandi:**

```bash
# Caricare LaunchAgent
launchctl load ~/Library/LaunchAgents/com.balizero.intel-scraper.plist

# Verificare stato
launchctl list | grep intel-scraper

# Rimuovere (se necessario)
launchctl unload ~/Library/LaunchAgents/com.balizero.intel-scraper.plist
```

---

## 🛠️ SCRIPT DI FIX AUTOMATICO

Creare `scripts/fix_intel_scraper_cron.sh`:

```bash
#!/bin/bash
# Fix Intel Scraper Cron Issues on macOS

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INTEL_SCRIPT="$SCRIPT_DIR/auto_intel_scraper.sh"

echo "🔧 Fixing Intel Scraper Cron Issues..."

# 1. Rimuovere attributi macOS
echo "1. Removing macOS security attributes..."
xattr -d com.apple.quarantine "$INTEL_SCRIPT" 2>/dev/null || true
xattr -d com.apple.provenance "$INTEL_SCRIPT" 2>/dev/null || true

# 2. Verificare permessi
echo "2. Setting executable permissions..."
chmod +x "$INTEL_SCRIPT"

# 3. Backup crontab
BACKUP_FILE="$PROJECT_DIR/crontab.backup.$(date +%Y%m%d-%H%M%S)"
echo "3. Backing up crontab to $BACKUP_FILE..."
crontab -l > "$BACKUP_FILE" 2>/dev/null || echo "# Empty crontab" > "$BACKUP_FILE"

# 4. Pulire entry duplicate
echo "4. Removing duplicate cron entries..."
crontab -l 2>/dev/null | grep -v "auto_intel_scraper.sh" | crontab - || true

# 5. Aggiungere entry pulita
echo "5. Adding clean cron entries..."
(crontab -l 2>/dev/null; cat <<EOF

# Intel Scraper - Daily at 4:00 AM and 4:00 PM
0 4 * * * $INTEL_SCRIPT >> $PROJECT_DIR/logs/intel_scraper.log 2>&1
0 16 * * * $INTEL_SCRIPT >> $PROJECT_DIR/logs/intel_scraper.log 2>&1
EOF
) | crontab -

# 6. Verificare
echo "6. Verifying crontab..."
crontab -l | grep "auto_intel_scraper.sh"

echo ""
echo "✅ Fix completed!"
echo ""
echo "To test manually:"
echo "  $INTEL_SCRIPT"
echo ""
echo "To verify cron:"
echo "  crontab -l | grep intel"
```

---

## 📋 CHECKLIST IMPLEMENTAZIONE

- [ ] Eseguire `scripts/fix_intel_scraper_cron.sh`
- [ ] Verificare che lo script sia eseguibile: `chmod +x scripts/auto_intel_scraper.sh`
- [ ] Testare manualmente: `./scripts/auto_intel_scraper.sh`
- [ ] Verificare crontab: `crontab -l | grep intel`
- [ ] Controllare log dopo il prossimo cron: `tail -f logs/intel_scraper.log`
- [ ] (Opzionale) Configurare LaunchAgent invece di cron

---

## 🔍 VERIFICA POST-FIX

Dopo aver applicato il fix, verificare:

```bash
# 1. Verificare attributi macOS
xattr -l scripts/auto_intel_scraper.sh
# Dovrebbe essere vuoto o non mostrare com.apple.quarantine

# 2. Verificare permessi
ls -la scripts/auto_intel_scraper.sh
# Dovrebbe mostrare -rwxr-xr-x

# 3. Verificare crontab
crontab -l | grep intel
# Dovrebbe mostrare solo 2 entry (4:00 e 16:00)

# 4. Test manuale
./scripts/auto_intel_scraper.sh
# Dovrebbe eseguire senza errori

# 5. Verificare log
tail -20 logs/intel_scraper.log
# Dovrebbe mostrare esecuzione riuscita
```

---

## 🚨 PROBLEMI NOTI

### macOS Ventura+ e Permessi

Su macOS Ventura e successivi, potrebbe essere necessario:

1. **Grant Full Disk Access** a Terminal/Cron:
   - System Settings → Privacy & Security → Full Disk Access
   - Aggiungere Terminal o il processo cron

2. **Disabilitare SIP** (non raccomandato):
   - Solo per testing avanzato
   - Richiede riavvio in Recovery Mode

### Alternativa: Eseguire su Server Linux

Se il problema persiste su macOS, considerare:

- Eseguire Intel Scraper su server Linux (Fly.io, Railway, etc.)
- Usare GitHub Actions per scheduling
- Usare Cloud Scheduler (Google Cloud) o EventBridge (AWS)

---

**Last Updated:** 2026-01-24  
**Status:** Problema identificato, soluzione proposta
