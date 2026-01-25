#!/bin/bash
# Fix Intel Scraper Cron Issues on macOS
# Solves "Operation not permitted" error

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INTEL_SCRIPT="$SCRIPT_DIR/auto_intel_scraper.sh"

echo "🔧 Fixing Intel Scraper Cron Issues..."
echo ""

# 1. Rimuovere attributi macOS
echo "1. Removing macOS security attributes..."
xattr -d com.apple.quarantine "$INTEL_SCRIPT" 2>/dev/null || true
xattr -d com.apple.provenance "$INTEL_SCRIPT" 2>/dev/null || true
echo "   ✅ Removed security attributes"

# 2. Verificare permessi
echo "2. Setting executable permissions..."
chmod +x "$INTEL_SCRIPT"
echo "   ✅ Set executable permissions"

# 3. Backup crontab
BACKUP_FILE="$PROJECT_DIR/crontab.backup.$(date +%Y%m%d-%H%M%S)"
echo "3. Backing up crontab to $BACKUP_FILE..."
crontab -l > "$BACKUP_FILE" 2>/dev/null || echo "# Empty crontab" > "$BACKUP_FILE"
echo "   ✅ Backup saved"

# 4. Pulire entry duplicate
echo "4. Removing duplicate cron entries..."
TEMP_CRON=$(mktemp)
crontab -l 2>/dev/null | grep -v "auto_intel_scraper.sh" > "$TEMP_CRON" || echo "" > "$TEMP_CRON"
crontab "$TEMP_CRON"
rm "$TEMP_CRON"
echo "   ✅ Removed duplicates"

# 5. Aggiungere entry pulita
echo "5. Adding clean cron entries..."
(crontab -l 2>/dev/null; cat <<EOF

# Intel Scraper - Daily at 4:00 AM and 4:00 PM
0 4 * * * $INTEL_SCRIPT >> $PROJECT_DIR/logs/intel_scraper.log 2>&1
0 16 * * * $INTEL_SCRIPT >> $PROJECT_DIR/logs/intel_scraper.log 2>&1
EOF
) | crontab -
echo "   ✅ Added clean entries"

# 6. Verificare
echo ""
echo "6. Verifying crontab..."
echo "   Current Intel Scraper cron entries:"
crontab -l | grep "auto_intel_scraper.sh" || echo "   ⚠️  No entries found (this is unexpected)"

echo ""
echo "✅ Fix completed!"
echo ""
echo "📋 Next steps:"
echo "   1. Test manually: $INTEL_SCRIPT"
echo "   2. Check logs: tail -f $PROJECT_DIR/logs/intel_scraper.log"
echo "   3. Wait for next cron run (4:00 AM or 4:00 PM)"
echo ""
echo "🔍 To verify:"
echo "   crontab -l | grep intel"
echo "   xattr -l $INTEL_SCRIPT"
