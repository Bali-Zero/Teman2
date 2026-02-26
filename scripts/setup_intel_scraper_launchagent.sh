#!/bin/bash
# Setup Intel Scraper con LaunchAgent (macOS)
# Alternativa più affidabile a cron su macOS

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCH_AGENT="$HOME/Library/LaunchAgents/com.balizero.intel-scraper.plist"

echo "🚀 Setting up Intel Scraper with LaunchAgent..."
echo ""

# Creare directory LaunchAgents se non esiste
mkdir -p "$HOME/Library/LaunchAgents"

# Rimuovere LaunchAgent esistente se presente
if [ -f "$LAUNCH_AGENT" ]; then
    echo "⚠️  Found existing LaunchAgent, unloading..."
    launchctl unload "$LAUNCH_AGENT" 2>/dev/null || true
fi

# Creare file LaunchAgent
echo "📝 Creating LaunchAgent plist..."
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
echo "🔄 Loading LaunchAgent..."
launchctl load "$LAUNCH_AGENT"

# Verificare stato
echo ""
echo "✅ LaunchAgent creato e caricato!"
echo ""
echo "📋 Verifica stato:"
launchctl list | grep intel-scraper || echo "   ⚠️  LaunchAgent non trovato (potrebbe essere normale)"

echo ""
echo "📋 Comandi utili:"
echo "   Verifica stato: launchctl list | grep intel-scraper"
echo "   Test manuale: launchctl start com.balizero.intel-scraper"
echo "   Rimuovere: launchctl unload $LAUNCH_AGENT"
echo "   Log: tail -f $PROJECT_DIR/logs/intel_scraper.log"
echo ""
echo "⏰ Prossime esecuzioni programmate:"
echo "   4:00 AM (mattina)"
echo "   4:00 PM (pomeriggio)"
echo ""
