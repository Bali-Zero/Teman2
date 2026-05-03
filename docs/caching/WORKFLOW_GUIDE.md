# Complete Caching Pipeline Workflow Guide

**Goal:** Generate 2,000-5,000 high-quality cached conversations using existing subscriptions

**Total Cost:** $0 (uses flat-rate subscriptions)
**Total Time:** 7-10 days
**Coverage:** 95-98% of query space

---

## Overview

This pipeline uses a **multi-tool orchestration** strategy to generate thousands of conversations without API costs:

```
NotebookLM → Claude Max → Gemini AI Studio → ChatGPT Plus → Claude Max → Redis
  (Seeds)    (Polish)      (Variations)       (Verify)      (Review)     (Cache)
```

**Tools Used:**

- ✅ NotebookLM - Grounded seed generation
- ✅ Claude Max (20x/day) - Polish & review
- ✅ Gemini 2.0 Pro (AI Studio) - Bulk variations
- ✅ ChatGPT Plus - Quality verification
- ✅ Cursor Ultra - Automation scripts
- ✅ Windsurf Pro - Review dashboard

---

## Phase 1: Golden Seeds (2-3 days)

### Goal: 30 Perfect Seed Conversations

**Input:** KB source documents (PDFs)
**Output:** 30 polished conversations (1-2 per route × 3 languages)
**Quality Target:** >90% quality score

### Step 1.1: NotebookLM Setup

1. **Prepare KB Sources**

   ```bash
   mkdir -p data/kb_sources
   cd data/kb_sources

   # Add source PDFs:
   # - PP 34/2021 (Work permits)
   # - Permenkumham 28/2024 (E-Visa)
   # - OSS 2025 Guidelines
   # - Tax regulations
   # - Property law docs
   # - KBLI classifications
   ```

2. **Upload to NotebookLM**
   - Go to https://notebooklm.google.com
   - Click "New notebook"
   - Upload all KB source PDFs
   - Wait for indexing (2-5 minutes)

3. **Generate for Each Golden Route**

   For route: **kitas_work**

   ```
   Query to NotebookLM:
   "Generate a comprehensive guide for obtaining a work KITAS in Indonesia.
   Include all steps, requirements, costs, timeline, and recent regulatory changes.
   Focus on 2026 procedures."

   → Read the generated text response
   → Click "Generate Audio Overview"
   → Wait 3-5 minutes for podcast generation
   → Download MP3 file as "kitas_work_it.mp3"
   ```

   **Repeat for all 18 golden routes × 3 languages = 54 notebooks**

   Route IDs:
   - kitas_work, pt_pma_setup, nib_oss
   - restaurant_foreigner, import_export_business, tech_company_digital
   - investor_kitas_retirement, hire_foreign_worker
   - villa_rental_business, hotel_business, real_estate_developer, property_management
   - buy_property_foreigner
   - visa_tourism_c1_d1, visa_business_c2_d2, visa_pre_investment_d12
   - visa_digital_nomad_e33g, visa_retirement_e33e

4. **Save Podcasts**
   ```bash
   mkdir -p data/notebooklm_podcasts
   # Move all MP3 files to this directory
   ```

### Step 1.2: Transcription

**Option A: Whisper API (if available)**

```bash
python scripts/caching/transcribe_podcasts.py --method whisper
```

**Option B: Manual (Otter.ai)**

1. Go to https://otter.ai
2. Upload MP3 files
3. Download transcriptions as TXT
4. Save to `data/transcriptions/`

### Step 1.3: Polish with Claude Max

**Daily Quota:** 20 conversations/day

**Process:**

1. Open Claude.ai (use Claude Max account)
2. Copy template from `prompts/claude_max_polish.txt`
3. For each transcription:
   - Paste template
   - Insert transcription
   - Submit to Claude
   - Copy polished response
   - Save to `data/golden_seeds/seed_NNN.json`

**JSON Format:**

```json
{
  "id": "seed_001",
  "route_id": "kitas_work",
  "language": "it",
  "query": "Come funziona il KITAS per lavoro?",
  "response": "[Polished response from Claude]",
  "quality_score": 95,
  "citations_count": 5,
  "generated_at": "2026-02-09T10:00:00Z",
  "source": "notebooklm_kitas_work_it_claude_polished"
}
```

**Timeline:**

- Day 1-2: NotebookLM generation (54 podcasts)
- Day 2: Transcription (batch process)
- Day 3-4: Claude polish (20/day = 3 days for 54)
- Output: 30-40 high-quality seeds

### Step 1.4: Consolidate Seeds

```bash
# Merge all individual seed files
python scripts/caching/consolidate_seeds.py \
  --input data/golden_seeds/ \
  --output data/golden_seeds.json
```

**Verify Quality:**

```bash
python scripts/caching/validate_seeds.py \
  --file data/golden_seeds.json \
  --min-score 90 \
  --min-citations 3
```

✅ **Phase 1 Complete** → Proceed to Phase 2

---

## Phase 2: Variation Generation (2-3 days)

### Goal: 1,500-3,000 Conversation Variations

**Input:** 30 golden seeds
**Output:** 50 variations per seed = 1,500 total
**Tool:** Google AI Studio (free tier: 1,500 requests/day)

### Step 2.1: Generate Batch Prompts

```bash
python master_pipeline.py phase2 \
  --seeds data/golden_seeds.json \
  --variations-per-seed 50
```

**Output:** 1,500 prompt files in `data/variations/prompts/`

**File Structure:**

```
data/variations/prompts/
├── seed_001_var_001.txt
├── seed_001_var_002.txt
...
├── seed_030_var_050.txt
```

### Step 2.2: Batch Processing in AI Studio

**Google AI Studio Free Tier:**

- 1,500 requests/day
- Resets at midnight PT
- Can run multiple prompts in web UI

**Method A: Manual Batch (Day 1)**

1. Open https://aistudio.google.com/prompts/new_chat
2. Open 10 browser tabs
3. In each tab:
   - Copy 5 prompts from `prompts/` folder
   - Paste one per "Freeform prompt"
   - Click "Run" (not "Get code")
4. Wait 5-10 minutes for all to complete
5. For each response:
   - Copy output text
   - Save as `data/variations/responses/seed_XXX_var_YYY_response.txt`

**Repeat:** 10 tabs × 5 prompts × 30 rounds = 1,500 prompts

**Method B: Semi-Automated (with Cursor)**

Use Cursor to build a script that:

1. Reads prompt files
2. Opens AI Studio URLs with prompt pre-filled
3. Waits for user to click "Run" and copy response
4. Auto-saves responses

```bash
cursor compose "Build a semi-automated Gemini AI Studio batch processor"
```

### Step 2.3: Parse Responses

```bash
python scripts/caching/parse_gemini_responses.py \
  --responses data/variations/responses/ \
  --output data/variations/conversations.json
```

**Output Format:**

```json
{
  "conversations": [
    {
      "id": "var_00001",
      "seed_id": "seed_001",
      "route_id": "kitas_work",
      "language": "it",
      "query": "[Variation of seed query]",
      "response": "[Generated response]",
      "variation_type": "phrasing_change",
      "user_context": "investor",
      "generated_at": "2026-02-10T14:30:00Z"
    }
  ]
}
```

### Step 2.4: Deduplication

```bash
python scripts/caching/deduplicate_conversations.py \
  --input data/variations/conversations.json \
  --threshold 0.85 \
  --output data/variations/conversations_unique.json
```

**Removes:** Near-duplicate conversations (>85% similarity)

✅ **Phase 2 Complete** → Proceed to Phase 3

---

## Phase 3: Quality Verification (1 day)

### Goal: Verify 15% Sample, Approve All if Pass Rate >90%

**Input:** 1,500 conversations
**Sample:** 225 conversations (15%)
**Tool:** ChatGPT Plus (300 msgs/day)

### Step 3.1: Generate Verification Prompts

```bash
python master_pipeline.py phase3
```

**Output:** 225 verification prompts in `data/verification_prompts/`

### Step 3.2: Batch Verification with ChatGPT

**ChatGPT Plus Rate Limit:**

- 40 messages per 3 hours
- ~300 messages per day
- Day 1: 225 verifications ✅

**Process:**

1. Open https://chat.openai.com
2. For each prompt file (225 total):
   - Copy prompt
   - Paste to ChatGPT
   - Wait for JSON response
   - Copy JSON
   - Save as `data/verification_responses/verify_NNN.json`
3. Process in batches of 40 (every 3 hours)

**Timeline:**

- Batch 1 (0-40): 9am-12pm
- Batch 2 (41-80): 12pm-3pm
- Batch 3 (81-120): 3pm-6pm
- Batch 4 (121-160): 6pm-9pm
- Batch 5 (161-200): 9pm-12am
- Batch 6 (201-225): next day 9am

### Step 3.3: Analyze Verification Results

```bash
python scripts/caching/analyze_verification.py \
  --responses data/verification_responses/ \
  --output data/verifications.json \
  --report data/verification_report.txt
```

**Report Output:**

```
📊 Verification Report

Total conversations verified: 225 (15% sample)
Pass rate (score ≥0.85): 205/225 (91.1%) ✅

Quality Distribution:
- Excellent (≥0.95): 89 (39.6%)
- Good (0.85-0.95): 116 (51.6%)
- Needs review (0.75-0.85): 15 (6.7%)
- Reject (<0.75): 5 (2.2%)

Common Issues:
1. Missing citations: 12 conversations
2. Incomplete workflow: 8 conversations
3. Vague timeline info: 6 conversations

RECOMMENDATION: Pass rate >90% → APPROVE ALL 1,500 conversations ✅
```

**If pass rate <90%:**

- Use Claude Max (20x/day) to fix flagged conversations
- Re-verify fixed conversations
- Iterate until pass rate >90%

✅ **Phase 3 Complete** → Proceed to Phase 4

---

## Phase 4: Human Review (2-3 days)

### Goal: Manually Review Top 50 High-Value Conversations

**Input:** 1,500 approved conversations
**Review:** Top 50 (sorted by importance)
**Tools:** Windsurf dashboard + Claude Max

### Step 4.1: Build Review Dashboard

**Use Windsurf Cascade:**

```
@windsurf-cascade

Build a conversation review dashboard:

Tech:
- Single HTML file (index.html)
- Inline CSS and vanilla JavaScript
- No frameworks, no build process

Features:
- Load data/conversations.json
- Load data/verifications.json
- Display top 50 conversations sorted by:
  * Route importance (high-traffic routes first)
  * Verification score
  * User context diversity
- For each conversation show:
  * Route ID, Language, User context
  * Query (in card header)
  * Response (collapsible markdown)
  * Verification scores (badges)
  * Action buttons: ✅ Approve | ✏️ Edit | ❌ Reject
- Inline markdown editor for edits
- Export approved to data/approved_conversations.json
- Progress counter (X/50 reviewed)

Style:
- Dark mode UI
- Card-based layout
- Responsive (works on tablet)
- Syntax highlighting for markdown
```

Save to `data/review_dashboard.html`

### Step 4.2: Manual Review Process

1. **Open Dashboard**

   ```bash
   open data/review_dashboard.html
   # or: python -m http.server 8000
   ```

2. **For Each Conversation (50 total):**
   - Read query + response
   - Check verification scores
   - Look for issues:
     - Missing citations
     - Hallucinations
     - Obsolete procedures
     - Pricing errors
   - Decision: Approve / Edit / Reject

3. **For Top 20 (High-Value Routes):**
   - Use Claude Max for detailed review
   - Open `prompts/claude_max_review.txt`
   - Paste conversation + verification
   - Get comprehensive review report
   - Apply suggestions

**Claude Max Quota:** 20 reviews/day

- Day 1: Review conversations 1-20
- Day 2: Review conversations 21-40
- Day 3: Review conversations 41-50

### Step 4.3: Export Approved

Click "Export Approved" in dashboard → saves to `data/approved_conversations.json`

**Expected Output:** 45-50 approved (90-100% approval rate)

✅ **Phase 4 Complete** → Proceed to Phase 5

---

## Phase 5: Cache Upload (1 hour)

### Goal: Upload to Redis Production Cache

**Input:** 1,500 approved conversations
**Output:** Cached and ready for production

### Step 5.1: Generate Redis Script

```bash
python master_pipeline.py phase5
```

**Output:** `data/redis_upload.sh`

**Script Preview:**

```bash
#!/bin/bash
REDIS_HOST=localhost
REDIS_PORT=6379

# Upload 1,500 conversations with 24h TTL
redis-cli SET "cache:conv:kitas_work:it:1" '{"query":"...","response":"..."}' EX 86400
redis-cli SET "cache:conv:kitas_work:it:2" '{"query":"...","response":"..."}' EX 86400
...
```

### Step 5.2: Upload to Redis

**Option A: Local Redis**

```bash
bash data/redis_upload.sh
```

**Option B: Production Redis (Fly.io)**

```bash
# Connect to Fly.io Redis
fly ssh console -a nuzantara-rag

# Copy script to server
scp data/redis_upload.sh fly:/tmp/

# Run upload
bash /tmp/redis_upload.sh
```

### Step 5.3: Verify Upload

```bash
redis-cli
> KEYS "cache:conv:*" | wc -l
1500

> GET "cache:conv:kitas_work:it:1"
"{\"query\":\"Come funziona...\",\"response\":\"...\"}"

> TTL "cache:conv:kitas_work:it:1"
86392  # ~24 hours remaining
```

✅ **Pipeline Complete!** 🎉

---

## Monitoring & Maintenance

### Cache Hit Rate Tracking

**Add to backend:**

```python
# backend/services/caching/cache_monitor.py

@app.middleware("http")
async def cache_metrics(request, call_next):
    if request.url.path.startswith("/api/chat"):
        cache_key = generate_cache_key(request.query)

        if cache_hit := await redis.get(cache_key):
            CACHE_HIT_COUNTER.inc()
            return JSONResponse(json.loads(cache_hit))
        else:
            CACHE_MISS_COUNTER.inc()
            response = await call_next(request)
            await redis.setex(cache_key, 86400, response.body)
            return response
```

**Grafana Query:**

```promql
# Cache hit rate
rate(cache_hit_total[5m]) /
  (rate(cache_hit_total[5m]) + rate(cache_miss_total[5m]))

# Target: 40-60% hit rate
```

### Monthly Refresh

**Schedule:** Re-run pipeline monthly to refresh with KB updates

```bash
# Cron job (1st of every month)
0 0 1 * * cd /path/to/nuzantara && python master_pipeline.py phase2
```

**Incremental Update:**

- Don't regenerate all seeds
- Only generate variations for updated routes
- Merge with existing cache

---

## Troubleshooting

### Issue: NotebookLM Audio Not Generating

**Symptoms:** "Audio Overview" button grayed out or errors

**Solutions:**

1. Ensure notebook has 3+ source documents
2. Wait 5 minutes after upload for full indexing
3. Try generating text summary first
4. Use different browser (Chrome recommended)
5. Check NotebookLM status: https://status.google.com

### Issue: Gemini AI Studio Rate Limit

**Symptoms:** "Rate limit exceeded" error

**Solutions:**

1. Wait until midnight PT (quota resets)
2. Use multiple Google accounts (3-4 accounts = 6,000 requests/day)
3. Spread work across 2-3 days
4. Reduce variations-per-seed from 50 to 30

### Issue: ChatGPT Not Returning Valid JSON

**Symptoms:** Malformed JSON in verification responses

**Solutions:**

1. Add to prompt: "Return ONLY valid JSON, no markdown formatting"
2. Strip markdown code fences: `json.loads(response.strip('```json\n').strip('\n```'))`
3. Use GPT-4 instead of GPT-3.5 for better JSON compliance

### Issue: Claude Max Daily Limit Reached

**Symptoms:** "You've reached your daily message limit"

**Solutions:**

1. Wait until midnight PT (quota resets)
2. Use multiple Claude accounts if available
3. Prioritize: Review top routes first, lower priority routes can wait
4. Spread review across 3-4 days instead of rushing

### Issue: Low Verification Pass Rate (<80%)

**Symptoms:** Too many conversations flagged for rejection

**Root Causes:**

1. Seed quality too low (fix in Phase 1)
2. Gemini generating off-topic variations (adjust prompts)
3. Verification criteria too strict (relax thresholds)

**Solutions:**

1. Re-generate seeds with better NotebookLM prompts
2. Add more constraints to variation prompts
3. Lower quality threshold from 0.85 to 0.80
4. Manual fix: Use Claude Max to repair failed conversations

---

## Cost Comparison

### This Pipeline (Multi-Tool)

- **Cost:** $0 (flat-rate subscriptions)
- **Time:** 7-10 days (human time: ~20 hours)
- **Output:** 1,500-3,000 conversations
- **Quality:** High (multiple review layers)

### Alternative: Pure API (OpenAI/Anthropic)

- **Cost:** $1,500-3,000 for 3,000 conversations
  - Generation: 3,000 × $0.50 = $1,500
  - Verification: 3,000 × $0.20 = $600
  - Review: 3,000 × $0.30 = $900
- **Time:** 1-2 days (faster but expensive)
- **Output:** 3,000 conversations
- **Quality:** Medium (less human review)

**Savings:** $3,000 by using subscriptions! ✅

---

## Next Steps

1. **Start Phase 1:**

   ```bash
   python master_pipeline.py phase1
   ```

2. **Read NotebookLM Guide:**

   ```bash
   cat docs/caching/NOTEBOOKLM_GUIDE.md
   ```

3. **Prepare KB Sources:**
   - Gather all PDF source documents
   - Place in `data/kb_sources/`

4. **Set Up Tools:**
   - Verify Claude Max access
   - Verify Gemini AI Studio access
   - Verify ChatGPT Plus access

**Questions?** See `docs/caching/FAQ.md`

---

**Author:** Nuzantara Team
**Version:** 1.0
**Last Updated:** 2026-02-09
**Pipeline Status:** Ready to deploy ✅
