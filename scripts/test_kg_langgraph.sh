#!/bin/bash
# KG LangGraph A/B Test Script
# Tests 5 multi-domain queries and records results

TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3ZGZlNTZiMi1mZjYzLTRkNDAtYjc4Yi05MGMwMTgxMjdhMDIiLCJlbWFpbCI6Inplcm9AYmFsaXplcm8uY29tIiwicm9sZSI6IkZvdW5kZXIiLCJleHAiOjE3NzA2ODMwMjR9.CQzaEYL4PrHrznxR8y0aIDSurao4sPIcdi0-EaZgnb0"
BASE_URL="https://nuzantara-rag.fly.dev/api/agentic-rag/query"
MODE="${1:-OFF}"
OUTDIR="/tmp/kg_test_${MODE}"
mkdir -p "$OUTDIR"

queries=(
  "Voglio aprire un ristorante a Bali come straniero. Quali sono tutti i requisiti: PT PMA, capitale, visto, KBLI, licenze?"
  "Qual è il codice KBLI per ristorante? Posso avere 100% proprietà straniera? Quanto capitale serve?"
  "Voglio comprare villa a Bali. Serve visto? Che tipo di proprietà posso avere?"
  "Ho PT PMA ristorante. Quali tasse devo pagare? Quando? Come assumo camerieri indonesiani?"
  "Voglio portare mia moglie a Bali con visto dipendente. Serve cosa? Quanto costa?"
)

echo "========================================="
echo "KG LangGraph Test - Mode: $MODE"
echo "========================================="

for i in "${!queries[@]}"; do
  qnum=$((i+1))
  query="${queries[$i]}"
  outfile="$OUTDIR/q${qnum}.json"
  
  echo ""
  echo "--- Query $qnum ---"
  echo "Q: ${query:0:80}..."
  
  START_TIME=$(python3 -c "import time; print(time.time())")
  
  curl -s -X POST "$BASE_URL" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"query\": \"$query\", \"session_id\": \"test_${MODE}_q${qnum}_$(date +%s)\"}" \
    -o "$outfile" \
    --max-time 30
  
  END_TIME=$(python3 -c "import time; print(time.time())")
  
  python3 -c "
import json, sys
try:
    with open('$outfile') as f:
        d = json.load(f)
    ans = d.get('answer', '')
    elapsed = $END_TIME - $START_TIME
    has_workflow = 'SUGGESTED WORKFLOW' in ans
    # Count domains covered
    domains = []
    for kw, dom in [('PT PMA', 'company'), ('KBLI', 'kbli'), ('visto', 'visa'), ('visa', 'visa'), 
                     ('tasse', 'tax'), ('tax', 'tax'), ('villa', 'property'), ('proprietà', 'property'),
                     ('capitale', 'capital'), ('licenz', 'license'), ('camerier', 'hiring')]:
        if kw.lower() in ans.lower() and dom not in domains:
            domains.append(dom)
    sources = d.get('sources', [])
    if not sources:
        meta = d.get('metadata', {})
        sources = meta.get('sources', meta.get('context_sources', []))
    print(f'  Time: {elapsed:.1f}s')
    print(f'  Answer length: {len(ans)} chars')
    print(f'  Has workflow section: {has_workflow}')
    print(f'  Domains covered: {domains} ({len(domains)})')
    print(f'  Sources count: {len(sources) if isinstance(sources, list) else \"N/A\"}')
    print(f'  Under 5s: {\"YES\" if elapsed < 5 else \"NO\"}')
except Exception as e:
    print(f'  ERROR: {e}')
    with open('$outfile') as f:
        print(f'  Raw: {f.read()[:200]}')
"
done

echo ""
echo "========================================="
echo "Test complete. Results in $OUTDIR"
echo "========================================="
