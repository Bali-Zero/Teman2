#!/bin/bash
# Script per deploy monitoring stack (Prometheus + Alertmanager)
# Usage: ./scripts/deploy_monitoring.sh [environment]
#
# Environment: local|production
# Default: local

set -e

ENVIRONMENT="${1:-local}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 Deploying Monitoring Stack"
echo "=============================="
echo "Environment: ${ENVIRONMENT}"
echo ""

# Verifica prerequisiti
echo "📋 Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker non trovato. Installa Docker prima di continuare."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose non trovato. Installa Docker Compose prima di continuare."
    exit 1
fi

echo "✅ Prerequisiti OK"
echo ""

# Verifica file di configurazione
echo "📋 Verifying configuration files..."
CONFIG_FILES=(
    "${PROJECT_ROOT}/config/prometheus/prometheus.yml"
    "${PROJECT_ROOT}/config/prometheus/alerts.yml"
    "${PROJECT_ROOT}/config/alertmanager/alertmanager.yml"
    "${PROJECT_ROOT}/docker-compose.monitoring.yml"
)

for file in "${CONFIG_FILES[@]}"; do
    if [ ! -f "${file}" ]; then
        echo "❌ File mancante: ${file}"
        exit 1
    fi
done

echo "✅ Configuration files OK"
echo ""

# Test endpoint (se backend è disponibile)
if [ "${ENVIRONMENT}" = "local" ]; then
    echo "🔍 Testing backend endpoint..."
    if curl -s -f "http://localhost:8000/health/metrics/qdrant" > /dev/null 2>&1; then
        echo "✅ Backend endpoint raggiungibile"
    else
        echo "⚠️  Backend endpoint non raggiungibile (http://localhost:8000)"
        echo "   Assicurati che il backend sia in esecuzione"
    fi
    echo ""
fi

# Deploy
echo "🚀 Starting monitoring stack..."
cd "${PROJECT_ROOT}"

# Usa docker compose o docker-compose
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

${COMPOSE_CMD} -f docker-compose.monitoring.yml up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Verifica servizi
echo ""
echo "🔍 Verifying services..."

# Prometheus
if curl -s -f "http://localhost:9090/-/healthy" > /dev/null 2>&1; then
    echo "✅ Prometheus: http://localhost:9090"
else
    echo "❌ Prometheus non risponde"
fi

# Alertmanager
if curl -s -f "http://localhost:9093/-/healthy" > /dev/null 2>&1; then
    echo "✅ Alertmanager: http://localhost:9093"
else
    echo "❌ Alertmanager non risponde"
fi

# JSON Exporter
if curl -s -f "http://localhost:7979/" > /dev/null 2>&1; then
    echo "✅ JSON Exporter: http://localhost:7979"
else
    echo "❌ JSON Exporter non risponde"
fi

echo ""
echo "📊 Monitoring Stack Deployed!"
echo ""
echo "Access URLs:"
echo "  Prometheus:    http://localhost:9090"
echo "  Alertmanager: http://localhost:9093"
echo "  JSON Exporter: http://localhost:7979"
echo ""
echo "Verifica targets Prometheus:"
echo "  curl http://localhost:9090/api/v1/targets"
echo ""
echo "Verifica alerting rules:"
echo "  curl http://localhost:9090/api/v1/rules"
echo ""
echo "Verifica alerts:"
echo "  curl http://localhost:9093/api/v2/alerts"
echo ""


















