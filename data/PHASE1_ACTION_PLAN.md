# Phase 1: Golden Seeds - Action Plan

**Goal:** Generate 20-30 high-quality seed conversations using NotebookLM + Claude Max

**Timeline:** 2-3 days
**Cost:** €0
**Quality Target:** 8-12 citations per seed, 400-600 words, >90 quality score

---

## Current Status: STARTED ✅

- [x] Directory structure created
- [ ] KB sources uploaded to NotebookLM
- [ ] NotebookLM podcasts generated
- [ ] Transcriptions completed
- [ ] Claude Max polishing done
- [ ] Golden seeds validated

---

## Step-by-Step Instructions

### Step 1: Select Golden Routes (20-30 routes)

**Priority Routes for Phase 1:**

1. **Business Setup (5 routes)**
   - PT PMA setup (foreign investment company)
   - NIB/OSS registration
   - Restaurant with foreign ownership
   - Import/export business
   - Tech/digital company

2. **Work & Immigration (5 routes)**
   - KITAS Work Permit (employee)
   - KITAS Investor (PT PMA owner)
   - Hire foreign worker (IMTA/SPKP)
   - E-Visa business (C2/D2)
   - Digital nomad visa (E33G)

3. **Property & Real Estate (4 routes)**
   - Buy property as foreigner (Hak Pakai)
   - Villa rental business
   - Hotel/hospitality business
   - Real estate developer

4. **Tax & Compliance (3 routes)**
   - NPWP registration
   - PPh corporate tax
   - PPN/VAT compliance

5. **Visa Tourism (3 routes)**
   - Tourism visa (C1/D1)
   - Pre-investment visa (D12)
   - Retirement visa (E33E)

**Total: 20 routes** (start with these, expand to 30 later if needed)

---

### Step 2: Upload KB Sources to NotebookLM

**Sources needed (PDFs):**

1. **Work Permits:**
   - PP 34/2021 (IMTA/SPKP system)
   - Permenkumham 28/2024 (E-Visa)

2. **Business Setup:**
   - OSS 2025 Guidelines (NIB)
   - PP 5/2021 (Investment Law)
   - UU 6/2023 (Job Creation)

3. **Property:**
   - PP 18/2021 (Hak Pakai for foreigners)
   - Property acquisition guides

4. **Tax:**
   - UU 7/2021 (Tax Law Harmonization)
   - PP 55/2022 (Income Tax)
   - DJP 2026 guidelines

5. **Visa:**
   - Permenkumham 28/2024 (E-Visa)
   - Immigration Law (PP 31/2013)

**Action:**

```bash
# 1. Check existing KB sources
ls data/kb_sources/

# 2. If missing, download from:
# - apps/backend-rag/backend/data/pdfs/
# - Or from official government sites

# 3. Upload to NotebookLM:
# Go to: https://notebooklm.google.com
# Create new notebook: "Nuzantara Golden Seeds"
# Upload all PDFs
```

---

### Step 3: Generate NotebookLM Podcasts (20 podcasts)

**For each golden route, create a NotebookLM podcast:**

#### Example: PT PMA Setup

**Prompt to NotebookLM:**

```
Create a comprehensive audio overview about setting up a PT PMA (foreign investment company) in Indonesia.

Focus on:
1. Legal requirements and minimum capital
2. Step-by-step registration process (OSS, NIB, notary)
3. Work permit requirements (IMTA, KITAS Investor)
4. Timeline and costs
5. Tax obligations (PPh, PPN, NPWP)
6. 2026 regulatory updates

Make it practical and cite specific regulations (PP numbers, articles).
Target audience: Foreign entrepreneurs looking to invest in Bali/Indonesia.
```

**Action:**

1. Paste prompt into NotebookLM notebook
2. Read generated text response (review for accuracy)
3. Click "Generate Audio Overview"
4. Wait 3-5 minutes
5. Download MP3 as `pt_pma_setup.mp3`
6. Save to `data/notebooklm_podcasts/`

**Repeat for all 20 routes** (estimated: 1-2 hours total)

---

### Step 4: Transcribe Podcasts

**Option A: Manual (Free, Recommended)**

Use NotebookLM's built-in transcript feature:

1. In NotebookLM, click on the audio overview
2. Click "Show transcript" button
3. Copy full transcript text
4. Save to `data/transcriptions/pt_pma_setup.txt`

**OR**

Use Chrome Live Captions:

1. Enable Live Captions in Chrome settings
2. Play podcast audio
3. Copy live caption text
4. Save to `data/transcriptions/pt_pma_setup.txt`

**Option B: Whisper API (if OPENAI_API_KEY available)**

```bash
python scripts/caching/transcribe_podcasts.py transcribe \
  data/notebooklm_podcasts \
  --method whisper
```

**Validate transcriptions:**

```bash
python scripts/caching/transcribe_podcasts.py validate \
  data/transcriptions
```

Expected output:

- 20 transcript files
- Average 2,000-4,000 words per transcript
- Total: 40,000-80,000 words

---

### Step 5: Polish with Claude Max (20 conversations × 1-2 iterations)

**Prepare batch file:**

```bash
python scripts/caching/transcribe_podcasts.py prepare-batch \
  data/transcriptions \
  --output data/golden_seeds_batch.json
```

**Polish with Claude Max:**

1. Open Claude Max: https://claude.ai
2. Load prompt template: `prompts/claude_max_polish.txt`
3. For each transcript:

   **Prompt:**

   ```
   POLISH THIS NOTEBOOKLM TRANSCRIPT INTO A GOLDEN SEED CONVERSATION

   [Copy prompts/claude_max_polish.txt content]

   TRANSCRIPT:
   [Paste transcript from data/transcriptions/pt_pma_setup.txt]
   ```

4. Review Claude Max output
5. If quality score <90, iterate:

   ```
   POLISH AGAIN - Focus on:
   - Add more specific citations ([Source: PP 5/2021, Article 12])
   - Improve structure (add headings, bullets)
   - Verify all facts against source documents
   ```

6. Save final polished output to `data/golden_seeds/seed_001_pt_pma_setup.json`:

```json
{
  "id": "seed_001_pt_pma_setup",
  "query": "Come si apre una PT PMA a Bali come straniero?",
  "response": "[polished response with 8-12 citations]",
  "citations_count": 11,
  "quality_score": 92,
  "status": "ready_for_variations"
}
```

**Claude Max Capacity:**

- Limit: ~20 conversations/day (rolling 5-hour window)
- Strategy: Polish 10 seeds/day × 2 days = 20 seeds

---

### Step 6: Validate Golden Seeds

**Run validation:**

```bash
python scripts/utils/quality_checker.py check \
  "Come si apre una PT PMA?" \
  "$(jq -r '.response' data/golden_seeds/seed_001_pt_pma_setup.json)"
```

**Expected output:**

```
✅ QUALITY CHECK RESULTS
📊 Overall Score: 92/100
🎯 Status: PASSED

📚 Citations: 100/100
   Count: 11 (min: 8)

📝 Completeness: 95/100
   Words: 520

🗣️ Language: 90/100
   Avg sentence: 18.5 words

🔍 Factual: 100/100
   Hedge words: 2
   Hallucination risk: False
```

**Quality Gates:**

- [x] ≥8 citations per seed
- [x] 400-600 words
- [x] Quality score ≥90
- [x] No hallucination indicators

---

### Step 7: Consolidate Golden Seeds

**Create final golden seeds file:**

```bash
# Merge all individual seed files
python scripts/caching/master_pipeline.py phase1 --consolidate
```

**Output:** `data/golden_seeds.json`

```json
{
  "metadata": {
    "total_seeds": 20,
    "created_at": "2026-02-09",
    "status": "ready_for_phase2"
  },
  "seeds": [
    {
      "id": "seed_001_pt_pma_setup",
      "query": "Come si apre una PT PMA?",
      "response": "...",
      "citations_count": 11,
      "quality_score": 92
    },
    ...
  ]
}
```

---

## Progress Tracking

**Current Status:**

```bash
python scripts/caching/master_pipeline.py status
```

**Expected timeline:**

- Day 1: Upload KB sources + Generate 20 podcasts (2-3 hours)
- Day 1-2: Transcribe 20 podcasts (3-4 hours)
- Day 2-3: Polish with Claude Max (2 days, 10 seeds/day)
- Day 3: Validate and consolidate (1 hour)

**Total: 2-3 days**

---

## Next Phase

When golden seeds complete:

```bash
python scripts/caching/master_pipeline.py phase2 \
  --seeds data/golden_seeds.json \
  --variations-per-seed 50
```

This will generate 1,000 variations (20 seeds × 50 variations).

---

## Troubleshooting

**Issue:** NotebookLM podcast quality poor

**Solution:** Improve prompt with more specific instructions:

```
Focus on practical implementation steps, not theory.
Cite specific regulation numbers (PP X/YEAR, Article Y).
Include real-world examples and timelines.
```

**Issue:** Claude Max hitting rate limits

**Solution:** Spread polishing across 2 days (10 seeds/day)

**Issue:** Quality score <90

**Solution:** Add iteration:

```
POLISH AGAIN:
1. Add 2-3 more citations per section
2. Break long paragraphs into bullet points
3. Verify all numbers (costs, timelines) against sources
```

---

**Ready to start Phase 1!** 🚀

Begin with Step 2: Upload KB sources to NotebookLM.
