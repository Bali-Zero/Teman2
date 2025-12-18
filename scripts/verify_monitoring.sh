#!/bin/bash
# Script per verificare che il monitoring stack funzioni correttamente
# Usage: ./scripts/verify_monitoring.sh

set -e

echo "🔍 Verifying Monitoring Stack"
echo "============================="
echo ""

# Colori per output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funzione per testare endpoint
test_endpoint() {
    local name=$1
    local url=$2
    local expected_status=${3:-200}

    echo -n "Testing ${name}... "
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "${url}" || echo "000")

    if [ "${http_code}" = "${expected_status}" ]; then
        echo -e "${GREEN}✅ OK${NC} (${http_code})"
        return 0
    else
        echo -e "${RED}❌ FAILED${NC} (${http_code})"
        return 1
    fi
}

# Test Prometheus
echo "📊 Prometheus Tests"
echo "-------------------"
test_endpoint "Prometheus Health" "http://localhost:9090/-/healthy"
test_endpoint "Prometheus UI" "http://localhost:9090"
test_endpoint "Prometheus API" "http://localhost:9090/api/v1/status/config"

# Verifica targets
echo ""
echo "📋 Prometheus Targets:"
targets=$(curl -s "http://localhost:9090/api/v1/targets" | jq -r '.data.activeTargets[] | "\(.labels.job): \(.health)"' 2>/dev/null || echo "Error parsing targets")
if [ -n "${targets}" ]; then
    echo "${targets}"
else
    echo -e "${YELLOW}⚠️  No targets found or error parsing${NC}"
fi

# Verifica rules
echo ""
echo "📋 Alerting Rules:"
rules=$(curl -s "http://localhost:9090/api/v1/rules" | jq -r '.data.groups[] | "\(.name): \(.rules | length) rules"' 2>/dev/null || echo "Error parsing rules")
if [ -n "${rules}" ]; then
    echo "${rules}"
else
    echo -e "${YELLOW}⚠️  No rules found or error parsing${NC}"
fi

# Test Alertmanager
echo ""
echo "🚨 Alertmanager Tests"
echo "---------------------"
test_endpoint "Alertmanager Health" "http://localhost:9093/-/healthy"
test_endpoint "Alertmanager UI" "http://localhost:9093"

# Verifica alerts
echo ""
echo "📋 Active Alerts:"
alerts=$(curl -s "http://localhost:9093/api/v2/alerts" | jq -r 'length' 2>/dev/null || echo "0")
echo "Active alerts: ${alerts}"

# Test JSON Exporter
echo ""
echo "📡 JSON Exporter Tests"
echo "----------------------"
test_endpoint "JSON Exporter Health" "http://localhost:7979/"

# Test backend endpoint (se disponibile)
echo ""
echo "🔌 Backend Endpoint Tests"
echo "-------------------------"
if curl -s -f "http://localhost:8000/health/metrics/qdrant" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend metrics endpoint raggiungibile${NC}"

    # Test JSON exporter probe
    echo -n "Testing JSON Exporter probe... "
    probe_result=$(curl -s "http://localhost:7979/probe?module=qdrant_metrics&target=http://host.docker.internal:8000" 2>/dev/null || echo "error")
    if echo "${probe_result}" | grep -q "qdrant"; then
        echo -e "${GREEN}✅ OK${NC}"
    else
        echo -e "${YELLOW}⚠️  Probe non funziona correttamente${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Backend non raggiungibile (http://localhost:8000)${NC}"
fi

# Summary
echo ""
echo "============================="
echo "✅ Verification Complete"
echo ""
echo "Access URLs:"
echo "  Prometheus:    http://localhost:9090"
echo "  Alertmanager: http://localhost:9093"
echo "  JSON Exporter: http://localhost:7979"
echo ""


















