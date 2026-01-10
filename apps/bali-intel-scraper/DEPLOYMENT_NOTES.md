# Intel Scraper Deployment Notes

**Last Updated:** 2026-01-09

## Architecture Overview

The Intel Scraper interacts with multiple services:

### Backend (Fly.io)
- **URL:** `https://nuzantara-rag.fly.dev`
- **Purpose:** API endpoints for article submission, preview hosting
- **Endpoints Used:**
  - `/api/intel/scraper/submit` - Submit articles to News Room
  - `/preview/{article_id}` - Preview HTML hosting (optional)

### Frontend (Vercel)
- **URL:** `https://nuzantara-mouth.vercel.app`
- **Custom Domains:** 
  - `https://zantara.balizero.com` (via DNS)
  - `https://balizero.com` (via DNS)
- **Purpose:** News Room UI for team review
- **Note:** Frontend migrated from Fly.io to Vercel (2026-01-09)

## Configuration

### Environment Variables

```bash
# Backend API (Fly.io)
BACKEND_API_URL=https://nuzantara-rag.fly.dev

# Preview URL Base (can be backend or frontend)
PREVIEW_BASE_URL=https://nuzantara-rag.fly.dev/preview
# OR
PREVIEW_BASE_URL=https://nuzantara-mouth.vercel.app/preview

# Telegram Approval
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_APPROVAL_CHAT_ID=8290313965

# Claude API
ANTHROPIC_API_KEY=your_anthropic_key
```

### Fly.io Secrets (Backend)

Secrets are configured on the backend Fly.io app (`nuzantara-rag`):

```bash
# View secrets
fly secrets list -a nuzantara-rag

# Set Telegram approval chat ID
fly secrets set TELEGRAM_APPROVAL_CHAT_ID=8290313965 -a nuzantara-rag
```

## Deployment

### Backend (Fly.io)
```bash
cd apps/backend-rag
./scripts/fly-backend.sh deploy
```

### Frontend (Vercel)
```bash
cd apps/mouth
vercel deploy --prod
```

## Important Notes

1. **Backend stays on Fly.io** - Only frontend migrated to Vercel
2. **Custom domains** (`zantara.balizero.com`, `balizero.com`) point to Vercel frontend via DNS
3. **Preview URLs** can be served by either backend or frontend (configurable)
4. **API endpoints** remain on backend Fly.io

## Migration Impact

- ✅ No changes needed to backend API URLs
- ✅ Preview URLs configurable via `PREVIEW_BASE_URL`
- ✅ Custom domains automatically route to Vercel frontend
- ✅ News Room UI accessible via custom domain or Vercel URL
