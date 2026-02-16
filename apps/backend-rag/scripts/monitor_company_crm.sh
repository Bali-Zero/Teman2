#!/bin/bash
# Monitoraggio Company-Centric CRM
# Usage: ./monitor_company_crm.sh [interval_seconds]

INTERVAL=${1:-300}  # Default 5 minuti
API_URL="https://nuzantara-rag.fly.dev/api/crm/companies"
FRONTEND_URL="https://balizero.com"

echo "🔁 MONITORAGGIO COMPANY-CENTRIC CRM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Intervallo: $INTERVAL secondi"
echo "API: $API_URL"
echo "Frontend: $FRONTEND_URL"
echo ""

cycle=1
while true; do
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "📊 CICLO #$cycle - $timestamp"
    echo "────────────────────────────────────────────────────"
    
    # Backend Status
    echo "1️⃣ Backend Status:"
    fly status --app nuzantara-rag 2>&1 | grep -E "(State|Checks)" | head -2
    
    # API Test
    echo ""
    echo "2️⃣ API Test:"
    api_status=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL" 2>&1)
    api_time=$(curl -s -o /dev/null -w "%{time_total}" "$API_URL" 2>&1)
    echo "   /api/crm/companies: $api_status (${api_time}s)"
    
    if [ "$api_status" = "401" ]; then
        echo "   ✅ Auth required (expected)"
    elif [ "$api_status" = "200" ]; then
        echo "   ✅ API responding"
    else
        echo "   ⚠️  Unexpected status: $api_status"
    fi
    
    # Frontend Test
    echo ""
    echo "3️⃣ Frontend Test:"
    frontend_status=$(curl -sL -o /dev/null -w "%{http_code}" "$FRONTEND_URL" 2>&1)
    frontend_time=$(curl -sL -o /dev/null -w "%{time_total}" "$FRONTEND_URL" 2>&1)
    echo "   balizero.com: $frontend_status (${frontend_time}s)"
    
    # Error Check
    echo ""
    echo "4️⃣ Recent Errors:"
    errors=$(fly logs --app nuzantara-rag -n 2>&1 | grep -iE "error|exception" | grep -v "401\|warning" | tail -3)
    if [ -z "$errors" ]; then
        echo "   ✅ No errors"
    else
        echo "$errors"
    fi
    
    echo ""
    echo "✅ CICLO #$cycle COMPLETATO"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    cycle=$((cycle + 1))
    sleep $INTERVAL
done
