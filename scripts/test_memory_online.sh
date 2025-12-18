#!/bin/bash
# Test Memory Persistence Online

TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3ZGZlNTZiMi1mZjYzLTRkNDAtYjc4Yi05MGMwMTgxMjdhMDIiLCJlbWFpbCI6Inplcm9AYmFsaXplcm8uY29tIiwicm9sZSI6IkZvdW5kZXIiLCJleHAiOjE3NjU5NjM4Mjh9.RdNItwYaBuS2KMPmLr3qewahkotbxn9NXDqc670Gy1I"
BASE_URL="https://nuzantara-rag.fly.dev"

echo "=== 1. Memoria PRIMA del test ==="
curl -s "$BASE_URL/api/bali-zero/conversations/memory/context" \
  -H "Authorization: Bearer $TOKEN" | jq '.profile_facts'

echo ""
echo "=== 2. Invio messaggio con NUOVE info personali ==="
curl -s "$BASE_URL/api/agentic-rag/query" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Ciao! Sono Lucia, ho 35 anni, vengo da Milano e lavoro come designer. Vorrei comprare una villa a Ubud.",
    "user_id": "zero@balizero.com",
    "enable_vision": false
  }' | jq -r '.answer' | head -5

echo ""
echo "=== 3. Aspetto salvataggio memoria (5 sec) ==="
sleep 5

echo ""
echo "=== 4. Memoria DOPO il messaggio ==="
curl -s "$BASE_URL/api/bali-zero/conversations/memory/context" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "=== 5. Test PERSISTENZA: invio nuovo messaggio senza info personali ==="
curl -s "$BASE_URL/api/agentic-rag/query" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Quali sono i passi per acquistare una proprietà?",
    "user_id": "zero@balizero.com",
    "enable_vision": false
  }' | jq -r '.answer' | head -8

echo ""
echo "=== 6. Verifica che la risposta usi il contesto memoria ==="
echo "(L'AI dovrebbe ricordare Lucia, designer, Milano, Ubud)"
