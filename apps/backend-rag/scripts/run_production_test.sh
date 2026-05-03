#!/bin/bash
# Run production test with JWT token from .env
set -e

cd "$(dirname "$0")/.."

# Generate token from JWT_SECRET in .env
if [ -f .env ]; then
    source .env
    if [ -n "$JWT_SECRET_KEY" ]; then
        echo "Generating JWT token from .env..."
        TOKEN=$(python3 scripts/generate_test_token.py "$JWT_SECRET_KEY" "test@nuzantara.com" 24 | grep "export JWT_TOKEN" | cut -d"'" -f2)
        export JWT_TOKEN="$TOKEN"
        echo "Token generated successfully"
        echo ""
        
        # Run test
        ./scripts/test_production.sh
    else
        echo "❌ JWT_SECRET_KEY not found in .env"
        exit 1
    fi
else
    echo "❌ .env file not found"
    exit 1
fi
