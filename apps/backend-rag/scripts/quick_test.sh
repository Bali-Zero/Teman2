#!/bin/bash
# Quick production test with token from .env

set -e
cd "$(dirname "$0")/.."

# Load JWT_SECRET_KEY from .env
if [ -f .env ]; then
    export $(grep JWT_SECRET_KEY .env | xargs)
fi

# Generate token
echo "Generating JWT token..."
python3 << EOF
import jwt
from datetime import datetime, timedelta

secret = "$JWT_SECRET_KEY"
payload = {
    "sub": "test@nuzantara.com",
    "email": "test@nuzantara.com",
    "iat": datetime.utcnow(),
    "exp": datetime.utcnow() + timedelta(hours=24),
    "type": "access"
}
token = jwt.encode(payload, secret, algorithm="HS256")
print(token)
EOF

echo ""
echo "Testing /webhook/chat endpoint..."
echo ""

# Get token
TOKEN=$(python3 << EOF
import jwt
from datetime import datetime, timedelta
secret = "$JWT_SECRET_KEY"
payload = {
    "sub": "test@nuzantara.com",
    "email": "test@nuzantara.com",
    "iat": datetime.utcnow(),
    "exp": datetime.utcnow() + timedelta(hours=24),
    "type": "access"
}
token = jwt.encode(payload, secret, algorithm="HS256")
print(token)
EOF
)

# Test endpoint
curl -X POST https://nuzantara-rag.fly.dev/webhook/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "Ciao, come ti chiami?",
    "session_id": "quick-test-'$(date +%s)'",
    "metadata": {"test": true}
  }' | jq '.'
