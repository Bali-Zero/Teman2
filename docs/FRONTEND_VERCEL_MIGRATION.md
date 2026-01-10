# Frontend Migration to Vercel

**Date:** 2026-01-09  
**Status:** ✅ Completed

## Overview

The frontend (`apps/mouth`) has been migrated from Fly.io to **Vercel** for improved performance, global CDN, and better Next.js Edge Runtime support.

## Changes Made

### 1. Documentation Updates

Updated all documentation to reflect Vercel deployment:

- ✅ `docs/AI_ONBOARDING.md` - Deployment section
- ✅ `docs/SYSTEM_MAP_4D.md` - Deployment architecture diagram
- ✅ `docs/README.md` - Deployment info
- ✅ `docs/CRM_SYSTEM_DOCUMENTATION.md` - Frontend URL
- ✅ `docs/ai/AI_HANDOVER_PROTOCOL.md` - URL patterns
- ✅ `docs/operations/DEPLOY_CHECKLIST.md` - Access URLs
- ✅ `docs/INTEL_SCRAPER_ANALYSIS_REPORT.md` - Deployment note

### 2. Backend Configuration Updates

Updated backend CORS and auth middleware to allow Vercel origin:

- ✅ `apps/backend-rag/backend/app/setup/cors_config.py` - Added Vercel URL to allowed origins
- ✅ `apps/backend-rag/backend/middleware/hybrid_auth.py` - Added Vercel URL to defaults
- ✅ `apps/backend-rag/fly.toml` - Updated `ZANTARA_ALLOWED_ORIGINS` env var
- ✅ `apps/backend-rag/backend/app/routers/portal_invite.py` - Updated default frontend URL

### 3. Legacy Support

Kept Fly.io URL in allowed origins for backward compatibility during migration period.

## New Frontend URL

**Primary:** `https://nuzantara-mouth.vercel.app`  
**Legacy (deprecated):** `https://nuzantara-mouth.fly.dev`

## Deployment

### Frontend (Vercel)

```bash
cd apps/mouth
vercel deploy --prod
```

Or use Vercel dashboard/GitHub integration for automatic deployments.

### Backend (Fly.io)

Backend remains on Fly.io:

```bash
cd apps/backend-rag
./scripts/fly-backend.sh deploy
```

## Environment Variables

### Vercel Environment Variables

Set in Vercel dashboard:
- `NEXT_PUBLIC_API_URL` - Backend API URL (https://nuzantara-rag.fly.dev)
- `NEXT_PUBLIC_FRONTEND_URL` - Frontend URL (https://nuzantara-mouth.vercel.app)
- Other Next.js public env vars

### Backend Environment Variables

Updated `ZANTARA_ALLOWED_ORIGINS` in Fly.io secrets to include Vercel URL:

```bash
fly secrets set ZANTARA_ALLOWED_ORIGINS="https://zantara.balizero.com,https://www.zantara.balizero.com,https://nuzantara-mouth.vercel.app,https://nuzantara-mouth.fly.dev" -a nuzantara-rag
```

## Benefits

1. **Global CDN** - Faster loading worldwide
2. **Edge Runtime** - Better Next.js 16 Server Components support
3. **Auto-scaling** - Automatic scaling based on traffic
4. **Zero-config** - Simpler deployment process
5. **Better DX** - Integrated with Vercel dashboard and analytics

## Migration Checklist

- [x] Update documentation
- [x] Update backend CORS configuration
- [x] Update backend auth middleware
- [x] Update Fly.io secrets
- [x] Update portal invite default URL
- [ ] Verify Vercel deployment is working
- [ ] Test CORS from Vercel frontend
- [ ] Update any hardcoded URLs in scripts (optional)
- [ ] Remove Fly.io frontend app (after verification period)

## Notes

- Legacy Fly.io URL kept in allowed origins for backward compatibility
- Can be removed after verification period (suggested: 30 days)
- All new deployments should use Vercel URL
