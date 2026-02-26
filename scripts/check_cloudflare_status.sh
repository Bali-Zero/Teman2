#!/bin/bash
# CloudFlare Status Check Script
# Verifica lo stato DNS e CDN per i domini Nuzantara

echo "=========================================="
echo "  CLOUDFLARE STATUS CHECK"
echo "=========================================="
echo ""

# Domini da verificare
DOMAINS=(
    "balizero.com"
    "mo.balizero.com"
    "nuzantara.com"
)

echo "🔍 Verifica DNS e CloudFlare..."
echo ""

for domain in "${DOMAINS[@]}"; do
    echo "----------------------------------------"
    echo "📍 Dominio: $domain"
    echo "----------------------------------------"
    
    # Check DNS resolution
    echo "DNS Resolution:"
    dig +short "$domain" | head -3 | sed 's/^/  /'
    
    # Check nameservers
    echo "Nameservers:"
    dig +short NS "$domain" | sed 's/^/  /'
    
    # Check if CloudFlare
    NS=$(dig +short NS "$domain" | head -1)
    if [[ "$NS" == *"cloudflare"* ]]; then
        echo "  ✅ CloudFlare nameservers rilevati"
    else
        echo "  ⚠️  Non utilizza CloudFlare nameservers"
    fi
    
    # Check headers
    echo "HTTP Headers:"
    curl -sI "https://$domain" 2>/dev/null | grep -E "(CF-|Server|Status)" | sed 's/^/  /' || echo "  ❌ Non raggiungibile via HTTPS"
    
    echo ""
done

echo "=========================================="
echo "Verifica completata!"
echo "=========================================="
