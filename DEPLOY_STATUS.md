# Deployment Status

## Current Architecture

| Service | Platform | URL | Status |
|---------|----------|-----|--------|
| **Backend RAG** | Fly.io | https://nuzantara-rag.fly.dev | Active |
| **Frontend** | Vercel | https://www.balizero.com | Active |
| **Frontend (alt)** | Vercel | https://nuzantara-mouth.vercel.app | Active |

## Deployment Commands

### Backend (Fly.io)

```bash
cd apps/backend-rag
flyctl deploy
```

### Frontend (Vercel)

```bash
cd apps/mouth
vercel deploy --prod
```

Or use Vercel dashboard for automatic deployments on push.

## Health Checks

```bash
# Backend
curl https://nuzantara-rag.fly.dev/health | jq .

# Frontend
curl -I https://www.balizero.com
```

## Monitoring

- **Backend logs**: `flyctl logs --app nuzantara-rag`
- **Frontend**: Use Vercel dashboard (https://vercel.com/dashboard)

## Migration Notes (2026-01-10)

Frontend successfully migrated from Fly.io to Vercel:
- DNS migrated on Cloudflare
- Fly.io app `nuzantara-mouth` stopped
- See `docs/FRONTEND_VERCEL_MIGRATION.md` for full details
