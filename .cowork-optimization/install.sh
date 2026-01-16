#!/bin/bash
# Cowork Optimization Installer
# Installa e configura tutte le ottimizzazioni

set -e

OPTIM_DIR="$HOME/Desktop/nuzantara/.cowork-optimization"
LOG_FILE="$OPTIM_DIR/logs/install.log"

mkdir -p "$OPTIM_DIR/logs"

echo "========================================" | tee -a "$LOG_FILE"
echo "Cowork Optimization Installer v1.0" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 1. Verifica dipendenze
echo "[1/6] Checking dependencies..." | tee -a "$LOG_FILE"
command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js not found" | tee -a "$LOG_FILE"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm not found" | tee -a "$LOG_FILE"; exit 1; }
echo "  ✓ Node.js and npm found" | tee -a "$LOG_FILE"

# 2. Crea directory necessarie
echo "[2/6] Creating directories..." | tee -a "$LOG_FILE"
mkdir -p "$OPTIM_DIR"/{logs,backups/{sessions,auto},scripts}
mkdir -p "$HOME/Documents/Downloads-Organized"/{Documents,Images,Videos,Archives,Code,Other}
echo "  ✓ Directories created" | tee -a "$LOG_FILE"

# 3. Rende eseguibili gli script
echo "[3/6] Making scripts executable..." | tee -a "$LOG_FILE"
chmod +x "$OPTIM_DIR"/scripts/*.sh
echo "  ✓ Scripts are now executable" | tee -a "$LOG_FILE"

# 4. Test script
echo "[4/6] Testing automation scripts..." | tee -a "$LOG_FILE"
"$OPTIM_DIR/scripts/backup-cowork-sessions.sh" && echo "  ✓ Backup script works" | tee -a "$LOG_FILE"
"$OPTIM_DIR/scripts/cleanup-old-sessions.sh" && echo "  ✓ Cleanup script works" | tee -a "$LOG_FILE"

# 5. Configura cron (opzionale)
echo "[5/6] Cron configuration..." | tee -a "$LOG_FILE"
echo "  → To enable automated tasks, run:" | tee -a "$LOG_FILE"
echo "    crontab $OPTIM_DIR/cowork-crontab.txt" | tee -a "$LOG_FILE"

# 6. Summary
echo "[6/6] Installation complete!" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "Next steps:" | tee -a "$LOG_FILE"
echo "1. Restart Claude Desktop app" | tee -a "$LOG_FILE"
echo "2. Test Cowork with expanded folders" | tee -a "$LOG_FILE"
echo "3. (Optional) Enable cron jobs for automation" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
