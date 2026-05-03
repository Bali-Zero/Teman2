# Gemini AI Studio Batch Processing Guide

Guida step-by-step per generare variazioni massicce (1,500-3,000) usando Google AI Studio con Gemini 2.5 Pro.

**Author:** Nuzantara Team
**Date:** 2026-02-09
**Reference:** [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md) - Phase 2

---

## Overview

**Goal:** Generare 50-150 variazioni per ciascun golden seed usando Gemini 2.5 Pro batch prompts.

**Input:** Golden seeds da Phase 1 (JSON file con 20-30 seeds)
**Output:** 1,500-3,000 conversation variations (CSV export)
**Cost:** €0 (free tier: 1,500 requests/day)
**Timeline:** 2-3 giorni

---

## Prerequisites

### 1. Google AI Studio Account

- Vai a [aistudio.google.com](https://aistudio.google.com)
- Login con account Google
- Verifica free tier attivo: 1,500 requests/day

### 2. Golden Seeds File

Assicurati di avere `data/golden_seeds.json` da Phase 1:

```json
{
  "metadata": {...},
  "seeds": [
    {
      "id": "seed_001_pt_pma_setup",
      "query": "Come si apre una PT PMA...",
      "response": "## Procedura PT PMA...",
      ...
    }
  ]
}
```

---

## Step 1: Prepare Batch Prompts

Usa lo script `master_pipeline.py` per generare batch prompts da golden seeds:

```bash
cd /Users/antonellosiano/Projects/nuzantara

python scripts/caching/master_pipeline.py phase2 \
  --seeds data/golden_seeds.json \
  --variations-per-seed 50 \
  --output-dir data/gemini_batches
```

**Output:**

```
data/gemini_batches/
├── batch_001_pt_pma_setup.txt (50 prompts)
├── batch_002_kitas_investor.txt (50 prompts)
├── batch_003_tax_compliance.txt (50 prompts)
└── ...
```

Ogni file contiene 50 prompts come questo:

```
Create a conversation variation based on this golden seed.

GOLDEN SEED:
Query: Come si apre una PT PMA a Bali?
Response: [full response with citations]

YOUR TASK:
Generate a NEW conversation with:
1. Different query phrasing (same intent)
2. Response restructured but citing SAME sources
3. Maintain citation format: [Source: Document, Article]

Output format:
## Query
[new query]

## Response
[new response with citations]
```

---

## Step 2: Upload to Gemini AI Studio

### 2.1 Open Batch Prompts Interface

1. Go to [aistudio.google.com/prompts/batches](https://aistudio.google.com/prompts/batches)
2. Click **"New batch"**
3. Select **Gemini 2.5 Pro** model

### 2.2 Upload Prompt File

1. Click **"Upload file"**
2. Select `batch_001_pt_pma_setup.txt`
3. Configure settings:
   - **Temperature**: 0.8 (creative variations)
   - **Max output tokens**: 2048
   - **Safety settings**: None (business content)

### 2.3 Submit Batch

1. Review prompt count: 50 prompts
2. Click **"Run batch"**
3. Wait for completion (5-10 minutes for 50 prompts)

---

## Step 3: Download Results

### 3.1 Export to CSV

1. When batch completes, click **"Download CSV"**
2. Save as `batch_001_results.csv`

**CSV Format:**

| Prompt                   | Response                                                |
| ------------------------ | ------------------------------------------------------- |
| Create a conversation... | ## Query<br>Come aprire PT PMA...<br>## Response<br>... |
| Create a conversation... | ## Query<br>Procedura PT PMA...<br>## Response<br>...   |

### 3.2 Parse CSV to JSON

```bash
python scripts/caching/parse_gemini_responses.py parse-csv \
  data/gemini_batches/batch_001_results.csv \
  --output-dir data/variations \
  --seed-id seed_001_pt_pma_setup
```

**Output:** `data/variations/seed_001_pt_pma_setup_variations.json`

```json
{
  "metadata": {
    "seed_id": "seed_001_pt_pma_setup",
    "total_variations": 48,
    "skipped_rows": 2
  },
  "variations": [
    {
      "variation_id": "seed_001_pt_pma_setup_var_001",
      "query": "Come aprire una PT PMA a Bali?",
      "response": "## Procedura...",
      "citations_count": 10,
      "status": "pending_verification"
    }
  ]
}
```

---

## Step 4: Repeat for All Seeds

### 4.1 Daily Quota Management

**Free tier limits:** 1,500 requests/day

**Strategy:**

- Day 1: Process 30 batches × 50 prompts = 1,500 variations
- Day 2: Process next 30 batches
- Day 3: Remaining batches

### 4.2 Batch Processing Loop

```bash
# Day 1: Batches 1-30
for i in {1..30}; do
  batch_file="data/gemini_batches/batch_$(printf %03d $i)*.txt"

  # Manual upload to AI Studio (no API available)
  echo "Upload $batch_file to AI Studio"

  # Wait for user to download CSV
  read -p "Press enter when CSV downloaded..."

  # Parse results
  seed_id=$(basename $batch_file .txt | sed 's/batch_[0-9]*_//')
  python scripts/caching/parse_gemini_responses.py parse-csv \
    "data/gemini_batches/batch_$(printf %03d $i)_results.csv" \
    --seed-id "$seed_id"
done
```

### 4.3 Track Progress

```bash
python scripts/caching/master_pipeline.py status
```

**Output:**

```
📊 CACHING PIPELINE STATUS
==================================================

Phase 1: Golden Seeds
✅ Complete: 30 seeds generated

Phase 2: Variation Generation
🔄 In Progress: 1,200/1,500 variations (80%)
   Day 1: 1,500 ✅
   Day 2: 0 ⏳

Phase 3: Verification
⏸️ Not Started
```

---

## Step 5: Quality Checks

### 5.1 Validate Variations

```bash
python scripts/caching/parse_gemini_responses.py stats \
  data/all_variations.json
```

**Output:**

```
📊 Statistics for all_variations.json
======================================

📚 Citations:
   Total: 15,200
   Average: 10.1
   Min: 2
   Max: 18

❓ Query Length (words):
   Average: 12.5
   Min: 5
   Max: 25

💬 Response Length (words):
   Average: 450.3
   Min: 280
   Max: 680
```

### 5.2 Filter Low-Quality Variations

Variations with <2 citations will be flagged for Phase 3 verification.

---

## Troubleshooting

### Issue 1: Batch Upload Fails

**Symptom:** "File too large" error

**Solution:** Split batch file into smaller chunks (25 prompts each)

```bash
split -l 25 batch_001.txt batch_001_part_
```

### Issue 2: Quota Exceeded

**Symptom:** "Rate limit exceeded" error

**Solution:** Wait 24 hours for quota reset

Check quota status:

```bash
python scripts/utils/rate_limiter.py status
```

### Issue 3: Poor Citation Quality

**Symptom:** Variations missing citations or citing wrong sources

**Solution:** Update batch prompt template to emphasize citation preservation:

```
CRITICAL: You MUST cite the EXACT SAME sources as the golden seed.
Do NOT invent new sources. Do NOT cite from memory.
```

---

## Best Practices

### 1. Monitor Output Quality

Check first 5 variations from each batch:

```bash
python scripts/caching/parse_gemini_responses.py stats \
  data/variations/seed_001_variations.json
```

If average citations <2, regenerate batch with stricter prompt.

### 2. Preserve Citation Format

Gemini sometimes changes citation format. Validate with:

```bash
grep -E "\[Source:" data/variations/*.json | wc -l
```

Expected: ~10 citations per variation × 1,500 = ~15,000 total

### 3. Backup Raw CSV Files

AI Studio doesn't persist batch results forever. Download and backup:

```bash
mkdir -p data/gemini_batches/raw_csv
cp batch_*_results.csv data/gemini_batches/raw_csv/
```

---

## Next Phase

When all variations generated and parsed:

```bash
# Consolidate all variation files
python scripts/caching/parse_gemini_responses.py consolidate \
  data/variations \
  --output data/all_variations.json

# Proceed to Phase 3: ChatGPT Verification
python scripts/caching/master_pipeline.py phase3 \
  --variations data/all_variations.json
```

---

## Cost Analysis

### Gemini AI Studio Free Tier

**Limits:**

- 1,500 requests/day
- No monetary cost

**Capacity:**

- 1,500 variations/day × 3 days = 4,500 total
- Enough for 30 golden seeds × 150 variations each

**Alternative (if free tier insufficient):**

Upgrade to Gemini API paid tier:

- Cost: $0.00125/request (Gemini 2.5 Pro)
- 3,000 variations × $0.00125 = **$3.75 total**

Still 98% cheaper than OpenAI Batch API ($150).

---

## Summary

**Inputs:**

- 30 golden seeds (from Phase 1)

**Outputs:**

- 1,500-3,000 conversation variations
- Average 50-100 variations per seed
- ~10 citations per variation

**Timeline:**

- 2-3 days (limited by 1,500 requests/day quota)

**Cost:**

- €0 (free tier)

**Next Step:**

- Phase 3: ChatGPT verification (15% sample = ~300 verifications)

---

**Questions?** See [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md) for complete pipeline overview.
