#!/bin/bash
# Setup Prometheus per Article Composer

set -e

PROMETHEUS_DIR="${PROMETHEUS_DIR:-./prometheus}"
RULES_DIR="${RULES_DIR:-config/prometheus}"

echo "🔧 Setup Prometheus per Article Composer"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if prometheus.yml exists
if [ -f "$PROMETHEUS_DIR/prometheus.yml" ]; then
    echo -e "${YELLOW}⚠️  prometheus.yml già esistente${NC}"
    echo "   Backup creato: prometheus.yml.backup"
    cp "$PROMETHEUS_DIR/prometheus.yml" "$PROMETHEUS_DIR/prometheus.yml.backup"
fi

# Create prometheus directory if it doesn't exist
mkdir -p "$PROMETHEUS_DIR"

# Copy example config
echo "📋 Copiando configurazione esempio..."
cp config/prometheus/prometheus.yml.example "$PROMETHEUS_DIR/prometheus.yml"

# Copy rules file
echo "📋 Copiando regole alert..."
mkdir -p "$PROMETHEUS_DIR/rules"
cp "$RULES_DIR/article_composer_alerts.yml" "$PROMETHEUS_DIR/rules/"

# Update prometheus.yml to use correct rules path
echo "📝 Aggiornando percorso regole in prometheus.yml..."
sed -i.bak "s|config/prometheus/article_composer_alerts.yml|rules/article_composer_alerts.yml|g" "$PROMETHEUS_DIR/prometheus.yml"
rm -f "$PROMETHEUS_DIR/prometheus.yml.bak"

echo ""
echo -e "${GREEN}✅ Configurazione Prometheus completata!${NC}"
echo ""
echo "📋 File creati:"
echo "   - $PROMETHEUS_DIR/prometheus.yml"
echo "   - $PROMETHEUS_DIR/rules/article_composer_alerts.yml"
echo ""
echo "🔍 Verifica configurazione:"
echo "   promtool check config $PROMETHEUS_DIR/prometheus.yml"
echo "   promtool check rules $PROMETHEUS_DIR/rules/article_composer_alerts.yml"
echo ""
echo "🚀 Avvia Prometheus:"
echo "   prometheus --config.file=$PROMETHEUS_DIR/prometheus.yml"
