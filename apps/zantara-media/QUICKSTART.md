# ZANTARA MEDIA - Quick Start Guide

Get Bali Zero Journal's automated content pipeline running in 5 minutes!

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- OpenRouter API key (FREE models)
- Google API key (for Imagen)

## Step 1: Database Setup (2 minutes)

```bash
cd apps/zantara-media

# Set your database URL
export DATABASE_URL="postgresql://user:pass@localhost:5432/nuzantara_db"

# Run migration
./scripts/migrate.sh
```

This creates 7 tables for content management, intel signals, and analytics.

## Step 2: Environment Variables (1 minute)

Create `backend/.env`:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/nuzantara_db

# NUZANTARA Integration
NUZANTARA_API_URL=https://nuzantara-rag.fly.dev
NUZANTARA_API_KEY=your-api-key-here

# AI Providers (REQUIRED)
OPENROUTER_API_KEY=sk-or-v1-your-key-here
GOOGLE_API_KEY=your-google-api-key

# Image Generation (REQUIRED)
IMAGINEART_API_KEY=your-imagineart-key

# Optional: Social Media
TWITTER_API_KEY=...
LINKEDIN_CLIENT_ID=...
TELEGRAM_BOT_TOKEN=...
```

**Where to get API keys:**

- **OpenRouter**: https://openrouter.ai (FREE tier available!)
- **Google AI**: https://ai.google.dev (FREE tier available!)
- **ImagineArt**: https://www.imagineart.ai

## Step 3: Install Dependencies (1 minute)

```bash
cd backend
pip install -r requirements.txt
```

## Step 4: Start the Server (30 seconds)

```bash
uvicorn app.main:app --reload --port 8001
```

Server starts at: http://localhost:8001

## Step 5: Test the Pipeline (30 seconds)

Open a new terminal:

```bash
# Check health
curl http://localhost:8001/health

# Check scheduler status
curl http://localhost:8001/api/automation/status

# Trigger a manual pipeline run (this will generate 5 articles!)
curl -X POST http://localhost:8001/api/automation/trigger

# Watch the logs in the server terminal to see progress
```

The pipeline will:
1. Fetch intel signals (or use test data if none available)
2. Generate 5 articles using AI (takes 2-5 minutes)
3. Generate cover images for each article
4. Publish to database
5. Return statistics

## View Results

### API Documentation

Visit: http://localhost:8001/docs

Interactive API docs with all endpoints.

### Check Content in Database

```sql
-- View generated articles
SELECT id, title, status, word_count, created_at
FROM zantara_content
ORDER BY created_at DESC;

-- View intel signals
SELECT id, title, processed, priority
FROM intel_signals
ORDER BY priority DESC;

-- View media assets
SELECT id, content_id, asset_type, generated_by
FROM media_assets;
```

### Check Logs

The server terminal will show detailed logs of the pipeline execution:
- Intel signals fetched
- Articles being generated
- Images being created
- Final statistics

## What Happens Daily?

Once running, the system automatically:

**Every day at 6:00 AM Bali time**:
1. Fetches high-priority intel signals
2. Generates 5 articles
3. Creates cover images
4. Publishes everything
5. Prepares for distribution

**No manual intervention needed!**

## Common Commands

```bash
# Start server
uvicorn app.main:app --reload --port 8001

# Run migration
./scripts/migrate.sh

# Deploy to Fly.io
./scripts/deploy.sh

# Check status
curl http://localhost:8001/api/automation/status

# Trigger pipeline
curl -X POST http://localhost:8001/api/automation/trigger

# Get recent content
curl http://localhost:8001/api/content

# Get statistics
curl http://localhost:8001/api/dashboard/stats
```

## API Endpoints Quick Reference

### Automation
- `GET /api/automation/status` - Scheduler status
- `POST /api/automation/trigger` - Run pipeline now (background)
- `POST /api/automation/trigger-sync` - Run pipeline now (wait for completion)

### Content
- `GET /api/content` - List all content
- `GET /api/content?status=PUBLISHED` - Filter by status
- `GET /api/content/{id}` - Get single article
- `POST /api/content` - Create article manually
- `PUT /api/content/{id}` - Update article

### Dashboard
- `GET /api/dashboard/stats` - Overall statistics
- `GET /api/dashboard/recent` - Recent content

### Media
- `POST /api/media/generate-image` - Generate an image
- `POST /api/media/generate-video` - Generate a video

## Troubleshooting

### "No intel signals found"

**Solution 1**: Create test signals manually

```sql
INSERT INTO intel_signals (title, summary, category, source_name, priority)
VALUES
    ('New Visa Regulations for Digital Nomads', 'Indonesia introduces new visa types for remote workers', 'IMMIGRATION', 'Immigration Office', 8),
    ('Tax Changes for Foreigners in Bali', 'Updated tax requirements for expats', 'TAX', 'DJP Bali', 9),
    ('Property Market Update', 'Real estate trends in Bali 2025', 'PROPERTY', 'Bali Property News', 7);
```

**Solution 2**: Lower the priority threshold

Edit `backend/app/services/content_orchestrator.py`:
```python
self.min_priority = 1  # Was 7, now accepts all
```

### "AI generation failed"

Check your API keys:
```bash
# Test OpenRouter
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"

# Test Google AI
curl "https://generativelanguage.googleapis.com/v1beta/models?key=$GOOGLE_API_KEY"
```

### "Database connection failed"

```bash
# Test connection
psql "$DATABASE_URL" -c "SELECT 1"

# Check if tables exist
psql "$DATABASE_URL" -c "\dt zantara_*"
```

### Pipeline runs but no content

Check logs for errors. Common issues:
- No intel signals in database
- AI API keys invalid or rate limited
- Database permissions issues

### Scheduler not running

```bash
# Check status
curl http://localhost:8001/api/automation/status

# Manually start (if stopped)
curl -X POST http://localhost:8001/api/automation/start
```

## Next Steps

1. **Deploy to Production**
   ```bash
   cd apps/zantara-media
   ./scripts/deploy.sh
   ```

2. **Set up Social Media Integration**
   - Add Twitter/LinkedIn API keys to `.env`
   - Test distribution endpoints

3. **Customize Settings**
   - Change daily article count
   - Adjust schedule timing
   - Configure content preferences

4. **Monitor Performance**
   - Check logs daily
   - Review generated content quality
   - Adjust AI prompts if needed

## Support

- Full documentation: [README.md](./README.md)
- Deployment guide: [DEPLOYMENT.md](./DEPLOYMENT.md)
- API docs: http://localhost:8001/docs

---

**You're all set!** 🚀

The automated content pipeline is now running. Check back tomorrow morning to see your first batch of AI-generated articles!
