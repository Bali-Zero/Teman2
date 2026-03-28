#!/bin/bash
# Worker: processes one batch of companies
# Usage: ./extract_worker.sh <batch_number>
set -uo pipefail

BATCH=$1
BATCH_FILE="/tmp/batches/batch_${BATCH}.json"
WORK_DIR="/Users/nuzantara/Desktop/nuzantara/.gemini/tmp/worker_${BATCH}"
RESULT_DIR="/tmp/results"
SA_KEY="/Users/nuzantara/Desktop/codexyz/nuzantara-google-drive-sa-key-20260312.json"
DB_URL="postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag"

mkdir -p "$WORK_DIR" "$RESULT_DIR"

PROMPT='Read this PDF. Return ONLY valid JSON, no markdown, no explanation:
{"total_authorized_capital":<IDR>,"share_nominal_value":<IDR per share>,"kbli_codes":"<comma-sep>","shareholders":[{"name":"<NAME>","role":"<direktur/komisaris/pemegang_saham>","shares_count":<number>,"ownership_percentage":<0-100>}]}
Indonesian numbers: 10.001.000.000=10001000000. Not found=null.'

cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate

COUNT=$(python3 -c "import json; print(len(json.load(open('$BATCH_FILE'))))")
echo "[W$BATCH] Starting $COUNT companies"

python3 -c "
import json, sys
batch = json.load(open('$BATCH_FILE'))
for c in batch:
    print(json.dumps(c))
" | while IFS= read -r line; do
    CID=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['company_id'])")
    NAME=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['company_name'])")
    FID=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['file_id'])")

    PDF="$WORK_DIR/${CID}.pdf"

    # Download
    python3 -c "
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
creds = service_account.Credentials.from_service_account_file('$SA_KEY', scopes=['https://www.googleapis.com/auth/drive.readonly'])
service = build('drive', 'v3', credentials=creds)
req = service.files().get_media(fileId='$FID')
fh = io.BytesIO()
dl = MediaIoBaseDownload(fh, req)
done = False
while not done: _, done = dl.next_chunk()
with open('$PDF', 'wb') as f: f.write(fh.getvalue())
print(len(fh.getvalue()))
" 2>/dev/null

    if [ ! -s "$PDF" ]; then
        echo "[W$BATCH] ✗ $NAME — download failed"
        continue
    fi

    # Extract with gemini CLI
    OUTPUT=$(cd "$WORK_DIR" && gemini -m gemini-2.5-flash --approval-mode yolo -p "Read ${CID}.pdf. Company: $NAME. $PROMPT" 2>/dev/null)

    # Parse and save to DB
    python3 -c "
import json, sys, asyncio, re

raw = '''$OUTPUT'''
# Extract JSON
parsed = None
try:
    parsed = json.loads(raw.strip())
except:
    if '\`\`\`json' in raw:
        raw = raw.split('\`\`\`json')[1].split('\`\`\`')[0].strip()
    elif '\`\`\`' in raw:
        raw = raw.split('\`\`\`')[1].split('\`\`\`')[0].strip()
    try:
        parsed = json.loads(raw)
    except:
        m = re.search(r'\{.*\"shareholders\".*\}', raw, re.DOTALL)
        if m:
            try: parsed = json.loads(m.group())
            except: pass

if not parsed:
    print('PARSE_FAIL')
    sys.exit(1)

async def save():
    import asyncpg
    conn = await asyncpg.connect('$DB_URL')
    nominal = parsed.get('share_nominal_value')
    kbli = parsed.get('kbli_codes')
    if kbli:
        await conn.execute('UPDATE companies SET kbli_code = \$1 WHERE id = \$2 AND (kbli_code IS NULL OR kbli_code = \'\')', str(kbli), $CID)
    for sh in parsed.get('shareholders', []):
        name = (sh.get('name') or '').strip().upper()
        shares = sh.get('shares_count')
        pct = sh.get('ownership_percentage')
        if not name or (not shares and not pct): continue
        link = None
        for part in [p for p in name.split() if len(p) > 2]:
            link = await conn.fetchrow('SELECT ccl.id, ccl.shares_count, ccl.share_nominal_value, ccl.ownership_percentage FROM client_company_links ccl JOIN clients cl ON cl.id = ccl.client_id WHERE ccl.company_id = \$1 AND UPPER(cl.full_name) LIKE \'%\' || \$2 || \'%\' LIMIT 1', $CID, part)
            if link: break
        if not link: continue
        sets, params, idx = [], [], 1
        if shares and (link['shares_count'] is None or link['shares_count'] == 0):
            sets.append(f'shares_count = \${idx}'); params.append(int(shares)); idx += 1
        if nominal and (link['share_nominal_value'] is None or float(link['share_nominal_value'] or 0) == 0):
            sets.append(f'share_nominal_value = \${idx}'); params.append(float(nominal)); idx += 1
        if pct and (link['ownership_percentage'] is None or float(link['ownership_percentage'] or 0) == 0):
            sets.append(f'ownership_percentage = \${idx}'); params.append(float(pct)); idx += 1
        if sets:
            params.append(link['id'])
            await conn.execute(f'UPDATE client_company_links SET {\", \".join(sets)} WHERE id = \${idx}', *params)
    await conn.close()
    cap = parsed.get('total_authorized_capital')
    sh_count = len(parsed.get('shareholders', []))
    print(f'OK {sh_count} shareholders capital={cap}')

asyncio.run(save())
" 2>/dev/null

    RESULT=$?
    if [ $RESULT -eq 0 ]; then
        echo "[W$BATCH] ✓ $NAME"
    else
        echo "[W$BATCH] ✗ $NAME — parse/save failed"
    fi

    rm -f "$PDF"
done

echo "[W$BATCH] DONE"
