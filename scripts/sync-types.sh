#!/bin/bash
set -e

# Sync Types Script
# Purpose: Generate OpenAPI JSON from Backend and sync TypeScript interfaces to Frontend

echo "🔄 [1/2] Generating OpenAPI JSON from Backend..."
cd apps/backend-rag
source .venv/bin/activate
python -m backend.scripts.generate_openapi_json
deactivate
cd ../..

echo "🔄 [2/2] Generating TypeScript Interfaces for Frontend..."
npm run generate:api -w apps/mouth

echo "✅ Type Sync Complete!"
echo "📍 Definition: apps/backend-rag/openapi.json"
echo "📍 Interface:  apps/mouth/src/lib/api/schema.d.ts"
