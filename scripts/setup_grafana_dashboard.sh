#!/bin/bash
# Setup Grafana Dashboard per Article Composer

set -e

GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-admin}"
DASHBOARD_FILE="config/grafana/dashboards/article-composer.json"

echo "📊 Setup Grafana Dashboard per Article Composer"
echo "==============================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if dashboard file exists
if [ ! -f "$DASHBOARD_FILE" ]; then
    echo -e "${RED}❌ Dashboard file non trovato: $DASHBOARD_FILE${NC}"
    exit 1
fi

echo "📋 Dashboard file: $DASHBOARD_FILE"
echo "🌐 Grafana URL: $GRAFANA_URL"
echo ""

# Check if Grafana is accessible
echo "🔍 Verificando connessione a Grafana..."
if ! curl -s -f "$GRAFANA_URL/api/health" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Grafana non raggiungibile su $GRAFANA_URL${NC}"
    echo ""
    echo "📋 Setup manuale:"
    echo "   1. Apri Grafana: $GRAFANA_URL"
    echo "   2. Vai a Dashboards → Import"
    echo "   3. Clicca 'Upload JSON file'"
    echo "   4. Seleziona: $DASHBOARD_FILE"
    echo "   5. Seleziona datasource Prometheus"
    echo "   6. Clicca Import"
    exit 0
fi

echo -e "${GREEN}✅ Grafana raggiungibile${NC}"
echo ""

# Get API key or create one
echo "🔑 Ottenendo API key..."
API_KEY_RESPONSE=$(curl -s -X POST \
    "$GRAFANA_URL/api/auth/keys" \
    -H "Content-Type: application/json" \
    -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
    -d '{
        "name": "article-composer-setup",
        "role": "Admin",
        "secondsToLive": 3600
    }' 2>/dev/null || echo "")

if [ -z "$API_KEY_RESPONSE" ]; then
    echo -e "${YELLOW}⚠️  Impossibile creare API key automaticamente${NC}"
    echo ""
    echo "📋 Setup manuale:"
    echo "   1. Apri Grafana: $GRAFANA_URL"
    echo "   2. Vai a Configuration → API Keys"
    echo "   3. Crea nuova API key"
    echo "   4. Usa questo script con GRAFANA_API_KEY=your_key"
    exit 0
fi

API_KEY=$(echo "$API_KEY_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('key', ''))" 2>/dev/null || echo "")

if [ -z "$API_KEY" ]; then
    echo -e "${YELLOW}⚠️  Impossibile ottenere API key${NC}"
    echo ""
    echo "📋 Setup manuale:"
    echo "   1. Apri Grafana: $GRAFANA_URL"
    echo "   2. Vai a Dashboards → Import"
    echo "   3. Carica: $DASHBOARD_FILE"
    exit 0
fi

echo -e "${GREEN}✅ API key ottenuta${NC}"
echo ""

# Import dashboard
echo "📥 Importando dashboard..."
DASHBOARD_JSON=$(cat "$DASHBOARD_FILE")
IMPORT_RESPONSE=$(curl -s -X POST \
    "$GRAFANA_URL/api/dashboards/db" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_KEY" \
    -d "{
        \"dashboard\": $DASHBOARD_JSON,
        \"overwrite\": true
    }" 2>/dev/null || echo "")

if [ -z "$IMPORT_RESPONSE" ]; then
    echo -e "${YELLOW}⚠️  Impossibile importare dashboard automaticamente${NC}"
    echo ""
    echo "📋 Setup manuale:"
    echo "   1. Apri Grafana: $GRAFANA_URL"
    echo "   2. Vai a Dashboards → Import"
    echo "   3. Carica: $DASHBOARD_FILE"
else
    DASHBOARD_URL=$(echo "$IMPORT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('url', ''))" 2>/dev/null || echo "")
    if [ -n "$DASHBOARD_URL" ]; then
        echo -e "${GREEN}✅ Dashboard importato con successo!${NC}"
        echo ""
        echo "🔗 Dashboard URL: $GRAFANA_URL$DASHBOARD_URL"
    else
        echo -e "${GREEN}✅ Dashboard importato${NC}"
    fi
fi

echo ""
echo "📋 Prossimi step:"
echo "   1. Verifica che il datasource Prometheus sia configurato"
echo "   2. Apri il dashboard e verifica che i panel mostrino dati"
echo "   3. Configura refresh interval se necessario"
