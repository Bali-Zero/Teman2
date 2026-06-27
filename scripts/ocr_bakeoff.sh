#!/bin/bash
# OCR model bake-off — local, sovereign (Law 2), Indonesian ID documents.
#
# EMPIRICAL RESULT (2026-06-27, run on Mini-Pro2 GPU idle, warm, real docs):
#   model         KTP latency   doc_type   fields   verdict
#   qwen2.5vl:7b  5-16s         correct    5-12     ✅ WINNER (6-10x faster, +fields, classifies right)
#   qwen3-vl:8b   40-53s        correct    3-5      slower, no accuracy gain
#   glm-ocr       42-80s        WRONG      0-5      OCR-text only, mis-classifies doc_type
#
# VERDICT: STAY on qwen2.5vl:7b. The deep-research candidate (qwen3-vl:8b) lost
# the empirical bake-off. Run mass re-OCR on the MINI (GPU idle), NOT the Pro
# (the live intake worker keeps SEA-LION 32B resident → contention; suspend it
# for a clean window). Full analysis:
#   research/operations/2026-06-27-local-ocr-model-bakeoff-indonesian-id-docs.md
#
# Usage (on the Ollama host): edit GOLD + models, run. Outputs PII-safe aggregate
# metrics only; full extractions stay in a LOCAL file for hand-scoring. bash 3.2
# compatible (no assoc arrays — macOS legacy bash).
# bash 3.2 compatible (NO assoc arrays). Clean warm bake-off on idle Mini GPU.
OUT=/Users/nuzantara/bakeoff-mini-result.txt
: > "$OUT"
GOLD=/Users/nuzantara/bakeoff-m5
PROMPT='You are an OCR + structured-extraction engine for Indonesian official documents (KTP, passport, NPWP, NIB, KITAS, akta). Read the image and return ONLY one JSON object, no prose. Keys when present: doc_type, nama, nik, no_passport, npwp, no_kitas, tanggal_lahir, masa_berlaku. Transcribe EXACTLY. Unreadable=null. Do not invent digits.'
PJSON=$(python3 -c "import json,sys;print(json.dumps(sys.argv[1]))" "$PROMPT")

run_one() { # $1=model $2=image
  local M="$1" IMG="$2"
  local B64; B64=$(base64 -i "$IMG")
  local S E RESP; S=$(date +%s)
  RESP=$(curl -s -m 180 http://127.0.0.1:11434/api/generate -d "{\"model\":\"$M\",\"prompt\":$PJSON,\"images\":[\"$B64\"],\"stream\":false,\"think\":false,\"options\":{\"temperature\":0}}" 2>&1)
  E=$(date +%s)
  echo "$RESP" | T=$((E-S)) M="$M" D="$(basename "$IMG")" python3 -c "
import sys,json,os
try: r=json.load(sys.stdin).get('response','')
except: r=''
a,b=r.find('{'),r.rfind('}'); p=None
if a!=-1 and b!=-1:
    try: p=json.loads(r[a:b+1])
    except: p=None
D=os.environ['D']; T=os.environ['T']
if p:
    nn=sum(1 for v in p.values() if v not in (None,'','null'))
    crit=sum(1 for k in ('nik','no_passport','npwp','no_kitas','tanggal_lahir','masa_berlaku') if p.get(k) not in (None,'','null'))
    print(f'  {D:<20} {T:>3}s  json=OK   fields={nn:<2} crit={crit}  doc_type={p.get(\"doc_type\")}')
else:
    print(f'  {D:<20} {T:>3}s  json=FAIL raw_len={len(r)}')
" >> "$OUT"
}

for M in qwen2.5vl:7b qwen3-vl:8b; do
  echo "===== MODEL: $M =====" >> "$OUT"
  FIRST=$(ls "$GOLD"/* | head -1)
  curl -s -m 180 http://127.0.0.1:11434/api/generate -d "{\"model\":\"$M\",\"prompt\":$PJSON,\"images\":[\"$(base64 -i "$FIRST")\"],\"stream\":false,\"think\":false}" >/dev/null 2>&1
  echo "  (warm-up done)" >> "$OUT"
  for IMG in "$GOLD"/*; do run_one "$M" "$IMG"; done
done
echo "===== DONE =====" >> "$OUT"
