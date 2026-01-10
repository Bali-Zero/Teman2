# Frontend Migration to Vercel

**Date:** 2026-01-09
**DNS Migration Completed:** 2026-01-10
**Status:** ✅ Fully Completed (DNS migrated, Fly.io app stopped)

## Overview

The frontend (`apps/mouth`) has been fully migrated from Fly.io to **Vercel** for improved performance, global CDN, and better Next.js Edge Runtime support.

## Production URLs

| Domain | Points To | Status |
|--------|-----------|--------|
| `https://www.balizero.com` | Vercel (cname.vercel-dns.com) | ✅ Primary |
| `https://balizero.com` | Redirects to www | ✅ Active |
| `https://nuzantara-mouth.vercel.app` | Vercel | ✅ Active |
| `https://nuzantara-mouth.fly.dev` | - | ❌ Deprecated (app stopped) |

## DNS Configuration (Cloudflare)

DNS records migrated on 2026-01-10:

| Record | Name | Value |
|--------|------|-------|
| CNAME | balizero.com | cname.vercel-dns.com |
| CNAME | www | cname.vercel-dns.com |
| TXT | _vercel | vc-domain-verify=www.balizero.com,5f9ca2917d1baaafe5af |
| TXT | _vercel | vc-domain-verify=balizero.com,b2db6436cf8719534754 |

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
- `NEXT_PUBLIC_FRONTEND_URL` - Frontend URL (https://www.balizero.com)
- Other Next.js public env vars

### Backend Environment Variables

`ZANTARA_ALLOWED_ORIGINS` includes all active frontend origins:

```bash
fly secrets set ZANTARA_ALLOWED_ORIGINS="https://balizero.com,https://www.balizero.com,https://zantara.balizero.com,https://www.zantara.balizero.com,https://nuzantara-mouth.vercel.app" -a nuzantara-rag
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
- [x] Verify Vercel deployment is working
- [x] Test CORS from Vercel frontend
- [x] Migrate DNS to Vercel (Cloudflare)
- [x] Add Vercel domain verification TXT records
- [x] Stop Fly.io frontend app (nuzantara-mouth)
- [x] Update hardcoded URLs in scripts
- [x] Delete apps/mouth/fly.toml

## Cleanup Completed

- `apps/mouth/fly.toml` - Deleted (no longer needed)
- Fly.io app `nuzantara-mouth` - Stopped (can be destroyed after 30 days)
