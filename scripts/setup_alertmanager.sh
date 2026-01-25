#!/bin/bash
# Setup Alertmanager per Article Composer

set -e

ALERTMANAGER_DIR="${ALERTMANAGER_DIR:-./alertmanager}"

echo "🔔 Setup Alertmanager per Article Composer"
echo "==========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Create alertmanager directory if it doesn't exist
mkdir -p "$ALERTMANAGER_DIR"

# Check if alertmanager.yml exists
if [ -f "$ALERTMANAGER_DIR/alertmanager.yml" ]; then
    echo -e "${YELLOW}⚠️  alertmanager.yml già esistente${NC}"
    echo "   Backup creato: alertmanager.yml.backup"
    cp "$ALERTMANAGER_DIR/alertmanager.yml" "$ALERTMANAGER_DIR/alertmanager.yml.backup"
fi

# Copy example config
echo "📋 Copiando configurazione esempio..."
cp config/alertmanager/alertmanager.yml.example "$ALERTMANAGER_DIR/alertmanager.yml"

echo ""
echo -e "${GREEN}✅ Configurazione Alertmanager creata!${NC}"
echo ""
echo "📋 File creato: $ALERTMANAGER_DIR/alertmanager.yml"
echo ""
echo "⚙️  Configurazione richiesta:"
echo ""
echo "1️⃣  Email (SMTP):"
echo "   Modifica smtp_smarthost, smtp_from, smtp_auth_username, smtp_auth_password"
echo ""
echo "2️⃣  Slack:"
echo "   - Crea Slack App: https://api.slack.com/apps"
echo "   - Abilita Incoming Webhooks"
echo "   - Crea webhook per canale #alerts-article-composer"
echo "   - Aggiorna api_url in alertmanager.yml"
echo ""
echo "3️⃣  PagerDuty (opzionale):"
echo "   - Ottieni service key da PagerDuty"
echo "   - Decommenta pagerduty_configs in alertmanager.yml"
echo ""
echo "🔍 Verifica configurazione:"
echo "   amtool check-config $ALERTMANAGER_DIR/alertmanager.yml"
echo ""
echo "🚀 Avvia Alertmanager:"
echo "   alertmanager --config.file=$ALERTMANAGER_DIR/alertmanager.yml"
echo ""
echo "🧪 Test alert:"
echo "   curl -X POST http://alertmanager:9093/api/v2/alerts \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '[{\"labels\":{\"alertname\":\"ArticleComposerHighErrorRate\",\"severity\":\"critical\"}}]'"
