#!/bin/bash
# Parallel Gemini extraction of company data from Profil Perseroan
# Launches 20 Gemini sessions, each processing ~48 companies
# Each session reads the PDF from Drive and extracts structured data

set -euo pipefail
cd "$(dirname "$0")/.."

BATCH_DIR="/tmp"
OUTPUT_DIR="ai-dispatch-output/company-extraction"
mkdir -p "$OUTPUT_DIR"

BATCH_ID="${1:-all}"  # "all" or specific batch number like "03"

extract_batch() {
    local batch_num="$1"
    local batch_file="$BATCH_DIR/company_batch_${batch_num}.json"

    if [ ! -f "$batch_file" ]; then
        echo "[batch-$batch_num] No file found, skipping"
        return
    fi

    local count=$(python3 -c "import json; print(len(json.load(open('$batch_file'))))")
    echo "[batch-$batch_num] Processing $count companies..."

    # Build the prompt with all companies in this batch
    local company_list=$(python3 -c "
import json
batch = json.load(open('$batch_file'))
lines = []
for c in batch:
    lines.append(f\"- Company ID {c['company_id']}: {c['company_name']} — Drive file: https://drive.google.com/file/d/{c['profile_file_id']}/view\")
print('\n'.join(lines))
")

    local prompt="You are a data extraction specialist. I need you to extract structured company data from Indonesian company documents (Profil Perseroan / Detail Transaksi Perseroan).

For each company below, open the Google Drive link, read the document, and extract:
1. **shares_count**: Total number of shares (lembar saham) for each shareholder
2. **share_nominal_value**: Nominal value per share in IDR (nilai nominal)
3. **total_authorized_capital**: Modal dasar in IDR
4. **total_placed_capital**: Modal ditempatkan/disetor in IDR
5. **kbli_codes**: All KBLI codes listed (comma-separated)
6. **shareholders**: Array of {name, role (direktur/komisaris/pemegang_saham), shares_count, ownership_percentage}
7. **notaris_name**: Name of the notary
8. **akta_date**: Date of the deed
9. **sk_number**: SK Kemenkumham number if visible

Output ONLY valid JSON array. One object per company. Use company_id as key.
If you cannot access a document or data is not found, set fields to null.

COMPANIES TO PROCESS (batch $batch_num):
$company_list

OUTPUT FORMAT (JSON array):
[
  {
    \"company_id\": 123,
    \"company_name\": \"PT Example\",
    \"total_authorized_capital\": 10000000000,
    \"total_placed_capital\": 2500000000,
    \"share_nominal_value\": 50000,
    \"kbli_codes\": \"46326,47914\",
    \"notaris_name\": \"Notaris Name S.H.\",
    \"shareholders\": [
      {\"name\": \"John Doe\", \"role\": \"direktur\", \"shares_count\": 25000, \"ownership_percentage\": 50}
    ]
  }
]"

    gemini -m gemini-3.1-pro-preview \
        --sandbox \
        --approval-mode plan \
        "$prompt" \
        > "$OUTPUT_DIR/batch_${batch_num}_result.json" 2>"$OUTPUT_DIR/batch_${batch_num}_stderr.log" || true

    echo "[batch-$batch_num] Done → $OUTPUT_DIR/batch_${batch_num}_result.json"
}

if [ "$BATCH_ID" = "all" ]; then
    echo "=== Launching 20 parallel Gemini extraction sessions ==="
    echo "=== Each processes ~48 companies from Profil Perseroan ==="
    echo ""

    for i in $(seq -w 0 19); do
        extract_batch "$i" &
        # Stagger by 3 seconds to avoid API rate limits
        sleep 3
    done

    echo ""
    echo "All 20 sessions launched. Waiting for completion..."
    wait
    echo ""
    echo "=== All batches complete ==="
    echo "Results in: $OUTPUT_DIR/"
    ls -la "$OUTPUT_DIR"/batch_*_result.json 2>/dev/null | wc -l
else
    extract_batch "$BATCH_ID"
fi
