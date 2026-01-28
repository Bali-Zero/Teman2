#!/bin/bash
set -e

# Define paths
INPUT_CSV="/Users/antonellosiano/Desktop/nuzantara/2.7 Lampiran I.G PP Nomor 28 Tahun 2025 (I.G.1-341)_consolidated.csv"
RAW_JSON="reports/kbli_extraction/kbli_masterpiece_v5_raw.json"
ENRICHED_JSON="reports/kbli_extraction/kbli_masterpiece_v5_enriched.json"
QDRANT_JSON="reports/kbli_extraction/kbli_platinum_ready_for_qdrant_v5.json"

echo "🚀 Starting Vision Factory V5 Verification Pipeline..."

# 1. MinerU Parsing
echo "-----------------------------------"
echo "step 1: MinerU Parsing (CSV -> JSON)"
python3 scripts/vision_factory/mineru_to_masterpiece.py "$INPUT_CSV" "$RAW_JSON"

# 2. Enrichment & Schema Normalization
echo "-----------------------------------"
echo "step 2: Enrichment (JSON -> Enriched JSON V5)"
python3 scripts/vision_factory/enrich_masterpiece.py "$RAW_JSON" "$ENRICHED_JSON"

# 3. Serialization
echo "-----------------------------------"
echo "step 3: Qdrant Serialization (Enriched V5 -> Qdrant Ready)"
python3 scripts/vision_factory/masterpiece_to_qdrant.py "$ENRICHED_JSON" "$QDRANT_JSON"

echo "-----------------------------------"
echo "✅ Verification Complete!"
echo "Outputs:"
echo "1. $RAW_JSON"
echo "2. $ENRICHED_JSON"
echo "3. $QDRANT_JSON"
