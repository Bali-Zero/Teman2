# Intel Scraper Cron - macOS Permissions Guide

**Data:** 2026-01-24  
**Problema:** Cron job non viene eseguito nonostante Terminal/iTerm abbiano Full Disk Access

---

## 🔍 ANALISI SITUAZIONE ATTUALE

### ✅ Già Configurato

- ✅ Terminal.app → Full Disk Access **ENABLED**
- ✅ iTerm.app → Full Disk Access **ENABLED**

### ⚠️ Problema Potenziale

Su macOS, i cron job vengono eseguiti dal **cron daemon** (`/usr/sbin/cron`), che è un processo di sistema separato da Terminal/iTerm.

**Il cron daemon potrebbe non avere i permessi necessari anche se Terminal li ha.**

---

## ✅ SOLUZIONE RACCOMANDATA: LaunchAgent

Su macOS, `launchd` (LaunchAgent) è più affidabile di `cron` perché:

1. ✅ Ha accesso completo all'ambiente utente
2. ✅ Carica automaticamente `.zshrc` / `.bashrc`
3. ✅ Non ha problemi con attributi macOS
4. ✅ Migliore gestione errori e logging
5. ✅ Può essere monitorato con `launchctl`

### Setup LaunchAgent

**1. Creare file LaunchAgent:**

```bash
cat > ~/Library/LaunchAgents/com.balizero.intel-scraper.plist << 'EOF'
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
    <array>
        <dict>
            <key>Hour</key>
            <integer>4</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>16</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
    </array>
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
        <key>SHELL</key>
        <string>/bin/zsh</string>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
EOF
```

**2. Caricare LaunchAgent:**

```bash
launchctl load ~/Library/LaunchAgents/com.balizero.intel-scraper.plist
```

**3. Verificare stato:**

```bash
launchctl list | grep intel-scraper
```

**4. Test immediato (opzionale):**

```bash
# Eseguire manualmente
launchctl start com.balizero.intel-scraper

# Verificare log
tail -f ~/Desktop/nuzantara/logs/intel_scraper.log
```

**5. Rimuovere cron job vecchio:**

```bash
# Backup
crontab -l > crontab.backup.before-launchagent.$(date +%Y%m%d)

# Rimuovere entry Intel Scraper
crontab -l | grep -v "auto_intel_scraper.sh" | crontab -
```

---

## 🔄 ALTERNATIVA: Fix Cron Permissions

Se preferisci continuare con cron, prova:

### Opzione 1: Eseguire Script con `zsh -l`

Modifica il cron per usare una shell login:

```bash
# Nel crontab, invece di:
0 4 * * * /path/to/script.sh

# Usa:
0 4 * * * /bin/zsh -l -c '/path/to/script.sh'
```

### Opzione 2: Wrapper Script con Environment Completo

Crea `scripts/run_intel_scraper_cron.sh`:

```bash
#!/bin/zsh -l
# Wrapper per cron che carica tutto l'ambiente

cd /Users/antonellosiano/Desktop/nuzantara
exec ./scripts/auto_intel_scraper.sh
```

Poi nel crontab:

```bash
0 4 * * * /Users/antonellosiano/Desktop/nuzantara/scripts/run_intel_scraper_cron.sh >> /Users/antonellosiano/Desktop/nuzantara/logs/intel_scraper.log 2>&1
```

---

## 📊 CONFRONTO: Cron vs LaunchAgent

| Feature                   | Cron            | LaunchAgent         |
| ------------------------- | --------------- | ------------------- |
| **macOS Compatibility**   | ⚠️ Limitata     | ✅ Nativa           |
| **Environment Variables** | ❌ Non caricate | ✅ Caricate         |
| **Full Disk Access**      | ⚠️ Problemi     | ✅ Funziona         |
| **Logging**               | ⚠️ Limitato     | ✅ Completo         |
| **Monitoring**            | ❌ Difficile    | ✅ `launchctl list` |
| **Error Handling**        | ⚠️ Base         | ✅ Avanzato         |
| **Reliability**           | ⚠️ Media        | ✅ Alta             |

**Raccomandazione:** Usa LaunchAgent su macOS.

---

## 🛠️ SCRIPT AUTOMATICO: Setup LaunchAgent

Creare `scripts/setup_intel_scraper_launchagent.sh`:

```bash
#!/bin/bash
# Setup Intel Scraper con LaunchAgent (macOS)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCH_AGENT="$HOME/Library/LaunchAgents/com.balizero.intel-scraper.plist"

echo "🚀 Setting up Intel Scraper with LaunchAgent..."

# Creare directory LaunchAgents se non esiste
mkdir -p "$HOME/Library/LaunchAgents"

# Creare file LaunchAgent
cat > "$LAUNCH_AGENT" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.balizero.intel-scraper</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/scripts/auto_intel_scraper.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>4</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>16</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
    </array>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/intel_scraper.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/intel_scraper_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$HOME/.pyenv/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>$HOME</string>
        <key>SHELL</key>
        <string>/bin/zsh</string>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
EOF

# Caricare LaunchAgent
launchctl load "$LAUNCH_AGENT" 2>/dev/null || launchctl unload "$LAUNCH_AGENT" && launchctl load "$LAUNCH_AGENT"

echo "✅ LaunchAgent creato e caricato!"
echo ""
echo "📋 Comandi utili:"
echo "   Verifica stato: launchctl list | grep intel-scraper"
echo "   Test manuale: launchctl start com.balizero.intel-scraper"
echo "   Rimuovere: launchctl unload $LAUNCH_AGENT"
echo "   Log: tail -f $PROJECT_DIR/logs/intel_scraper.log"
```

---

## ✅ CHECKLIST MIGRAZIONE

- [ ] Creare LaunchAgent con script sopra
- [ ] Caricare LaunchAgent: `launchctl load ~/Library/LaunchAgents/com.balizero.intel-scraper.plist`
- [ ] Verificare stato: `launchctl list | grep intel-scraper`
- [ ] Test manuale: `launchctl start com.balizero.intel-scraper`
- [ ] Rimuovere cron job vecchio: `crontab -l | grep -v auto_intel_scraper.sh | crontab -`
- [ ] Verificare log dopo prossima esecuzione (4:00 AM o 4:00 PM)

---

**Raccomandazione Finale:** Usa LaunchAgent invece di cron su macOS per massima affidabilità.
