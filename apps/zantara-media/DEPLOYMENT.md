# ZANTARA MEDIA - Deployment Guide

## Quick Start

### 1. Run Database Migration

First, apply the database schema to your PostgreSQL database:

```bash
# Using psql
psql $DATABASE_URL -f ../backend-rag/backend/db/migrations/017_zantara_media_content.sql

# Or using Fly.io postgres proxy
fly postgres connect -a your-postgres-app-name
\i /path/to/017_zantara_media_content.sql
```

### 2. Set Environment Variables

For local development, create `.env` file in `backend/` directory:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/nuzantara_db
REDIS_URL=redis://localhost:6379

# NUZANTARA Integration
NUZANTARA_API_URL=https://nuzantara-rag.fly.dev
NUZANTARA_API_KEY=your-api-key

# AI Providers (Required)
OPENROUTER_API_KEY=sk-or-v1-...
GOOGLE_API_KEY=...
IMAGINEART_API_KEY=...

# Social Media (Optional)
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...

LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...

TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=...
```

### 3. Run Locally

```bash
cd apps/zantara-media/backend

# Install dependencies
pip install -r requirements.txt

# Run the server
python -m app.main

# Or with uvicorn directly
uvicorn app.main:app --reload --port 8001
```

The server will start at http://localhost:8001

**API Documentation**: http://localhost:8001/docs

### 4. Test the Pipeline

Trigger a manual run of the content generation pipeline:

```bash
# Using curl
curl -X POST http://localhost:8001/api/automation/trigger

# Using httpie
http POST localhost:8001/api/automation/trigger

# Check status
curl http://localhost:8001/api/automation/status
```

### 5. Deploy to Fly.io

```bash
cd apps/zantara-media

# Login to Fly.io
fly auth login

# Create the app (first time only)
fly apps create zantara-media --org your-org

# Set secrets
fly secrets set \
  DATABASE_URL="postgresql://..." \
  NUZANTARA_API_KEY="..." \
  OPENROUTER_API_KEY="sk-or-v1-..." \
  GOOGLE_API_KEY="..." \
  IMAGINEART_API_KEY="..."

# Deploy
fly deploy

# Check status
fly status

# View logs
fly logs

# SSH into the machine
fly ssh console
```

## Architecture

### Automated Daily Pipeline

The system runs automatically every day at **6:00 AM Bali time** (Asia/Makassar):

1. **Fetch Intel Signals** - Gets high-priority signals from database or scraper API
2. **Generate Articles** - Uses AI (OpenRouter free models → Google Gemini → Claude) to write articles
3. **Generate Images** - Creates cover images using Google Imagen or ImagineArt
4. **Publish** - Saves to database with status PUBLISHED
5. **Schedule Distribution** - Prepares for multi-platform distribution

### Manual Triggers

You can manually trigger the pipeline via API:

```bash
# Trigger in background (returns immediately)
POST /api/automation/trigger

# Trigger and wait for completion (can take 5-10 minutes)
POST /api/automation/trigger-sync

# Check scheduler status
GET /api/automation/status
```

### API Endpoints

**Automation**:
- `GET /api/automation/status` - Scheduler status
- `POST /api/automation/trigger` - Manual trigger (background)
- `POST /api/automation/trigger-sync` - Manual trigger (sync)
- `POST /api/automation/start` - Start scheduler
- `POST /api/automation/stop` - Stop scheduler

**Content**:
- `GET /api/content` - List content
- `GET /api/content/{id}` - Get single content
- `POST /api/content` - Create content manually
- `PUT /api/content/{id}` - Update content
- `POST /api/content/{id}/publish` - Publish content
- `DELETE /api/content/{id}` - Delete content

**Dashboard**:
- `GET /api/dashboard/stats` - Content statistics
- `GET /api/dashboard/recent` - Recent content

**Media**:
- `POST /api/media/generate-image` - Generate image
- `POST /api/media/generate-video` - Generate video

## Configuration

### Scheduler Configuration

Edit `app/services/scheduler.py` to change schedule:

```python
# Change the time (currently 6:00 AM)
self.scheduler.add_job(
    self._run_daily_pipeline,
    trigger=CronTrigger(hour=6, minute=0),  # Change hour/minute
    ...
)
```

### Content Generation Settings

Edit `app/services/content_orchestrator.py`:

```python
class ContentOrchestrator:
    def __init__(self):
        self.daily_target_articles = 5  # Change this
        self.min_priority = 7  # Minimum signal priority
```

## Monitoring

### Health Check

```bash
curl http://localhost:8001/health
```

### View Logs

```bash
# Local
tail -f logs/app.log

# Fly.io
fly logs
```

### Database Queries

```sql
-- Check recent content
SELECT id, title, status, created_at
FROM zantara_content
ORDER BY created_at DESC
LIMIT 10;

-- Check pending intel signals
SELECT id, title, priority, created_at
FROM intel_signals
WHERE processed = FALSE
ORDER BY priority DESC, created_at DESC;

-- Check content stats
SELECT
    status,
    COUNT(*) as count,
    AVG(word_count) as avg_words
FROM zantara_content
GROUP BY status;
```

## Troubleshooting

### Pipeline Not Running

1. Check scheduler status: `GET /api/automation/status`
2. Manually trigger: `POST /api/automation/trigger`
3. Check logs for errors
4. Verify environment variables are set

### No Content Generated

1. Check if intel signals exist: `SELECT * FROM intel_signals WHERE processed = FALSE`
2. Verify AI API keys are valid
3. Check logs for API errors
4. Reduce `min_priority` in content_orchestrator.py

### Database Connection Issues

1. Verify DATABASE_URL is correct
2. Check database is accessible
3. Run migrations if not applied
4. Check database user has correct permissions

### AI Generation Failures

The system has a fallback chain:
1. OpenRouter (Google Gemini 2.0 Flash) - FREE
2. OpenRouter (Llama 3.3 70B) - FREE
3. OpenRouter (Qwen 3 235B) - FREE
4. Google Gemini API (fallback)

If all fail, check:
1. API keys are valid
2. Rate limits not exceeded
3. Network connectivity

## Production Checklist

- [ ] Database migration applied
- [ ] Environment variables set
- [ ] Fly.io secrets configured
- [ ] Health check passing
- [ ] Manual pipeline test successful
- [ ] Scheduler running (check `/api/automation/status`)
- [ ] Logs showing no errors
- [ ] First automated run completed
- [ ] Content appears in database
- [ ] Images generated successfully

## Support

For issues, check:
1. Application logs
2. Database connection
3. API keys validity
4. Network connectivity
5. Fly.io machine resources

Contact: Bali Zero team
