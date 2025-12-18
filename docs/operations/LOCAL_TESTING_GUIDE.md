# BALI ZERO JOURNAL - Local Testing Guide

**Guida completa per testare il sistema localmente**

---

## 🚀 QUICK START (5 Passi)

### 1. Verifica Requisiti

```bash
# Python 3.11+
python --version

# PostgreSQL running
psql --version

# tmux (opzionale, per multi-window)
tmux -V

# curl o httpie
curl --version
```

---

### 2. Setup Database

```bash
# Export DATABASE_URL
export DATABASE_URL="postgresql://user:pass@localhost:5432/nuzantara_db"

# Applica migration
cd apps/backend-rag/backend/db/migrations
psql $DATABASE_URL -f 017_zantara_media_content.sql

# Verifica tabelle create
psql $DATABASE_URL -c "\dt zantara_*"
```

**Output atteso:**
```
zantara_content
intel_signals
content_distributions
media_assets
content_versions
automation_runs
content_analytics_daily
```

---

### 3. Installa Dipendenze

```bash
# Backend RAG (se non già fatto)
cd apps/backend-rag
pip install -r backend/requirements.txt

# Bali Intel Scraper
cd ../bali-intel-scraper
pip install -r requirements.txt
pip install fastapi uvicorn httpx

# Zantara Media
cd ../zantara-media/backend
pip install -r requirements.txt

# Test dependencies
pip install -r tests/requirements-test.txt
```

---

### 4. Configura Environment Variables

```bash
# Crea .env per zantara-media
cat > apps/zantara-media/backend/.env << 'EOF'
# Database
DATABASE_URL=postgresql://localhost:5432/nuzantara_db
REDIS_URL=redis://localhost:6379

# NUZANTARA Integration
NUZANTARA_API_URL=http://localhost:8080
NUZANTARA_API_KEY=test-key-local

# Intel Scraper Integration
INTEL_API_URL=http://localhost:8002
INTEL_API_KEY=test-key-local

# AI Providers (REQUIRED)
OPENROUTER_API_KEY=sk-or-v1-your-key-here
GOOGLE_API_KEY=your-google-api-key
IMAGINEART_API_KEY=your-imagineart-api-key

# Optional: Social Media
TWITTER_API_KEY=
LINKEDIN_CLIENT_ID=
TELEGRAM_BOT_TOKEN=
EOF

# Crea .env per bali-intel-scraper
cat > apps/bali-intel-scraper/.env << 'EOF'
NUZANTARA_API_URL=http://localhost:8080
NUZANTARA_API_KEY=test-key-local
OPENROUTER_API_KEY=sk-or-v1-your-key-here
GOOGLE_API_KEY=your-google-api-key
ANTHROPIC_API_KEY=your-anthropic-key (optional)
EOF

# Load variables
cd apps/zantara-media/backend
set -a && source .env && set +a
```

---

### 5. Run Tests

```bash
# Torna alla root
cd /Users/antonellosiano/Desktop/nuzantara

# Run all tests
./scripts/run_tests.sh
```

**Output atteso:**
```
============================================
NUZANTARA - Running All Tests
============================================

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Testing: ZANTARA MEDIA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

test_content_repository.py::TestContentRepository::test_create_content PASSED
test_content_repository.py::TestContentRepository::test_get_content_by_id PASSED
test_content_orchestrator.py::TestContentOrchestrator::test_fetch_intel_signals_from_db PASSED
test_api.py::TestAutomationAPI::test_health_check PASSED

✓ ZANTARA MEDIA tests PASSED

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Testing: BALI INTEL SCRAPER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

test_api.py::TestScraperAPI::test_health_check PASSED
test_api.py::TestScraperAPI::test_trigger_scrape PASSED

✓ BALI INTEL SCRAPER tests PASSED

============================================
TEST SUMMARY
============================================
✓ All tests PASSED!
```

---

## 🖥️ START LOCAL SERVICES

### Opzione A: Automatic (Tmux) - CONSIGLIATO

```bash
# Start all services in tmux
./scripts/start_local_services.sh

# Attach to see logs
tmux attach -t nuzantara

# Switch between windows:
#   Ctrl+b then 0 = Backend RAG
#   Ctrl+b then 1 = Scraper API
#   Ctrl+b then 2 = Zantara Media
#   Ctrl+b then 3 = Commands

# Detach (keeps running):
#   Ctrl+b then d

# Stop all:
tmux kill-session -t nuzantara
```

### Opzione B: Manual (3 Terminali)

**Terminal 1: Backend RAG**
```bash
cd apps/backend-rag
uvicorn backend.app.main:app --port 8080 --reload
```

**Terminal 2: Bali Intel Scraper API**
```bash
cd apps/bali-intel-scraper
python -m uvicorn api.main:app --port 8002 --reload
```

**Terminal 3: Zantara Media**
```bash
cd apps/zantara-media/backend
uvicorn app.main:app --port 8001 --reload
```

---

## ✅ VERIFY SERVICES

```bash
# Health checks
curl http://localhost:8080/health  # Backend RAG
curl http://localhost:8002/health  # Scraper API
curl http://localhost:8001/health  # Zantara Media

# API Docs (open in browser)
open http://localhost:8001/docs  # Zantara Media
open http://localhost:8002/docs  # Scraper API
open http://localhost:8080/docs  # Backend RAG

# Check scheduler
curl http://localhost:8001/api/automation/status | jq
```

**Expected output:**
```json
{
  "status": "healthy",
  "service": "ZANTARA MEDIA",
  "version": "1.0.0",
  "environment": "development"
}
```

---

## 🧪 TEST PIPELINE END-TO-END

### Step 1: Create Test Intel Signals

```bash
# Insert test signals into database
psql $DATABASE_URL << 'EOF'
INSERT INTO intel_signals (title, summary, category, source_name, priority, confidence_score, tags)
VALUES
  ('New Digital Nomad Visa Program',
   'Indonesia launches new visa program for remote workers with extended stay',
   'IMMIGRATION',
   'Immigration Office Indonesia',
   9,
   0.95,
   ARRAY['visa', 'digital-nomad', 'immigration']),

  ('Tax Changes for Expats in 2025',
   'New tax regulations affect foreign residents in Indonesia',
   'TAX',
   'Directorate General of Taxes',
   8,
   0.90,
   ARRAY['tax', 'expat', 'regulation']),

  ('Bali Property Market Update',
   'Real estate trends and regulations for foreign property buyers',
   'PROPERTY',
   'Bali Property Association',
   7,
   0.85,
   ARRAY['property', 'real-estate', 'bali']);
EOF

# Verify signals created
psql $DATABASE_URL -c "SELECT id, title, priority FROM intel_signals WHERE processed = FALSE;"
```

### Step 2: Trigger Content Generation

```bash
# Trigger the automated pipeline
curl -X POST http://localhost:8001/api/automation/trigger

# Response:
{
  "success": true,
  "message": "Pipeline triggered successfully. Check logs for progress."
}
```

### Step 3: Monitor Progress

**Watch logs in Zantara Media terminal:**
```
INFO - BALI ZERO JOURNAL - Daily Content Pipeline Starting
INFO - [Step 1] Fetching intel signals...
INFO - ✓ Fetched 3 high-priority intel signals
INFO - [Step 2] Generating 3 articles...
INFO -   → Article 1/3: New Digital Nomad Visa Program...
INFO -     Generating article with AI...
INFO -     ✓ Article generated: New Digital Nomad Visa Program...
INFO -   → Article 2/3: Tax Changes for Expats in 2025...
...
INFO - [Step 3] Generating cover images...
INFO -   → Image 1/3: New Digital Nomad Visa Program...
INFO -     Trying Google Imagen...
INFO -     ✓ Image generated
...
INFO - [Step 4] Publishing articles...
INFO -   ✓ Published: New Digital Nomad Visa Program...
...
INFO - ✓ Generated 3 articles
INFO - ✓ Generated 3 images
INFO - ✓ Published 3 articles
INFO - Duration: 180.45s
```

### Step 4: Verify Results

```bash
# Check automation status
curl http://localhost:8001/api/automation/status | jq

# List generated content
curl http://localhost:8001/api/content | jq

# Get content statistics
curl http://localhost:8001/api/dashboard/stats | jq

# Check database
psql $DATABASE_URL << 'EOF'
-- View generated articles
SELECT id, title, status, word_count, ai_model, created_at
FROM zantara_content
ORDER BY created_at DESC
LIMIT 5;

-- View processed signals
SELECT id, title, processed, action_taken, content_id
FROM intel_signals
WHERE processed = TRUE;

-- View media assets
SELECT id, content_id, asset_type, generated_by, width, height
FROM media_assets;
EOF
```

**Expected output:**
```
                  id                  |            title             | status    | word_count |    ai_model
--------------------------------------+------------------------------+-----------+------------+----------------
 a1b2c3d4-e5f6-...                   | New Digital Nomad Visa...    | PUBLISHED |        756 | gemini-2.0-flash
 b2c3d4e5-f6a7-...                   | Tax Changes for Expats...    | PUBLISHED |        689 | gemini-2.0-flash
 c3d4e5f6-a7b8-...                   | Bali Property Market...      | PUBLISHED |        712 | llama-3.3-70b
```

---

## 🔬 TEST INDIVIDUAL COMPONENTS

### Test Content Repository

```bash
cd apps/zantara-media/backend
pytest tests/test_content_repository.py -v
```

### Test Content Orchestrator

```bash
pytest tests/test_content_orchestrator.py -v
```

### Test API Endpoints

```bash
pytest tests/test_api.py -v
```

### Test Scraper API

```bash
cd ../../bali-intel-scraper
pytest tests/test_api.py -v
```

---

## 🐛 TROUBLESHOOTING

### Problem: "No intel signals found"

**Solution 1:** Create test signals (see Step 1 above)

**Solution 2:** Lower priority threshold
```python
# Edit apps/zantara-media/backend/app/services/content_orchestrator.py
self.min_priority = 1  # Was 7
```

### Problem: "AI generation failed"

**Check API keys:**
```bash
echo $OPENROUTER_API_KEY
echo $GOOGLE_API_KEY

# Test OpenRouter
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"

# Test Google AI
curl "https://generativelanguage.googleapis.com/v1beta/models?key=$GOOGLE_API_KEY"
```

### Problem: "Database connection failed"

```bash
# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Check if migration was applied
psql $DATABASE_URL -c "\dt zantara_*"

# Check database logs
tail -f /usr/local/var/log/postgresql@15.log  # macOS
tail -f /var/log/postgresql/postgresql-15-main.log  # Linux
```

### Problem: "Image generation failed"

Both services failed → Using placeholder is expected behavior.

To fix:
```bash
# Verify Google API key
curl -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key=$GOOGLE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"instances":[{"prompt":"test"}]}'

# Check ImagineArt key
echo $IMAGINEART_API_KEY
```

### Problem: "Scheduler not running"

```bash
# Check status
curl http://localhost:8001/api/automation/status

# Manually start if needed
curl -X POST http://localhost:8001/api/automation/start
```

### Problem: Tests failing

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock httpx

# Run with verbose output
pytest -vv --tb=long

# Run specific test
pytest tests/test_content_repository.py::TestContentRepository::test_create_content -vv
```

---

## 📊 PERFORMANCE TESTING

### Test Pipeline Performance

```bash
# Time the pipeline
time curl -X POST http://localhost:8001/api/automation/trigger-sync

# Expected: 3-5 minutes for 5 articles
```

### Monitor Resource Usage

```bash
# CPU/Memory usage (macOS)
top -pid $(pgrep -f "uvicorn")

# Linux
htop -p $(pgrep -f "uvicorn")

# Database connections
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## ✅ SUCCESS CRITERIA

Your local setup is working if:

- [x] All tests pass (`./scripts/run_tests.sh`)
- [x] All 3 services start without errors
- [x] Health checks return 200 OK
- [x] Scheduler status shows "running: true"
- [x] Manual trigger generates articles
- [x] Articles appear in database
- [x] Images are generated (or placeholder used)
- [x] No critical errors in logs

---

## 🎯 NEXT STEPS

Once local testing works:

1. **Deploy to Fly.io** - See `DEPLOYMENT.md`
2. **Setup social media APIs** - Twitter, LinkedIn, Telegram
3. **Build dashboard UI** - Content management interface
4. **Monitor first automated run** - 6:00 AM Bali time

---

## 📚 DOCUMENTATION LINKS

- Complete system: `BALI_ZERO_JOURNAL_COMPLETE_SYSTEM.md`
- Zantara Media: `apps/zantara-media/QUICKSTART.md`
- Deployment: `apps/zantara-media/DEPLOYMENT.md`
- API Docs: http://localhost:8001/docs

---

**Happy Testing! 🚀**
