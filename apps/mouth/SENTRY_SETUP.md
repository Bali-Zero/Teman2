# Sentry Error Tracking - Quick Test

## Quick Verification Checklist

### ✅ Files Created

- [x] `apps/mouth/sentry.client.config.ts`
- [x] `apps/mouth/sentry.server.config.ts`
- [x] `apps/mouth/sentry.edge.config.ts`
- [x] `apps/mouth/src/instrumentation.ts`

### ✅ Files Updated

- [x] `apps/mouth/.env.example` - Added `SENTRY_AUTH_TOKEN`
- [x] `apps/mouth/src/app/global-error.tsx` - Already had Sentry integration

### ✅ Verification

- [x] TypeScript compilation successful
- [x] Production build successful
- [x] No Sentry blocking in development

## Next Steps for Production Deployment

### 1. Create Sentry Project

```bash
# Go to: https://sentry.io
# Create project → Select "Next.js" → Name: "mouth"
```

### 2. Get Credentials

```bash
# Add to apps/mouth/.env.local:

NEXT_PUBLIC_SENTRY_DSN=https://xxx@o123456.ingest.sentry.io/123456
SENTRY_DSN=https://xxx@o123456.ingest.sentry.io/123456
SENTRY_ORG=your-org-slug
SENTRY_PROJECT=mouth
SENTRY_AUTH_TOKEN=your-auth-token
```

### 3. Add to Vercel Environment Variables

**Via Vercel Dashboard (Recommended):**

1. Go to: https://vercel.com/dashboard
2. Select project: **"mouth"**
3. Go to **Settings → Environment Variables**
4. Add these 5 variables for Production, Preview, and Development:

| Variable                 | Value Example                                 |
| ------------------------ | --------------------------------------------- |
| `NEXT_PUBLIC_SENTRY_DSN` | `https://xxx@o123456.ingest.sentry.io/123456` |
| `SENTRY_DSN`             | `https://xxx@o123456.ingest.sentry.io/123456` |
| `SENTRY_ORG`             | `your-org-slug`                               |
| `SENTRY_PROJECT`         | `mouth`                                       |
| `SENTRY_AUTH_TOKEN`      | `your-auth-token`                             |

**Via Vercel CLI:**

```bash
cd apps/mouth

vercel env add NEXT_PUBLIC_SENTRY_DSN production
vercel env add SENTRY_DSN production
vercel env add SENTRY_ORG production
vercel env add SENTRY_PROJECT production
vercel env add SENTRY_AUTH_TOKEN production
```

### 4. Deploy

**Auto-deploy (recommended):**

```bash
git push origin main
```

**Manual deploy:**

```bash
vercel --prod
```

### 5. Test in Production

Visit: `https://balizero.com`

Trigger test error:

```typescript
// Add to any page temporarily
useEffect(() => {
  throw new Error('[TEST] Sentry production tracking');
}, []);
```

Check Sentry dashboard:

```
https://sentry.io/organizations/[your-org]/issues/
```

### 6. Verify Source Maps

After deployment, check that stack traces show:

- Original TypeScript file names (not minified)
- Correct line numbers
- Readable code snippets

## Performance Expectations

### Sample Rates

- **Production Traces:** 10% of requests
- **Session Replays:** 10% of sessions
- **Error Replays:** 100% of error sessions

### Cost Estimate

For ~1,000 users/day:

- ~100 traced requests/day (10% sample)
- ~100 session replays/day (10% sample)
- All errors captured with replay

Sentry Free Plan: 5,000 errors/month, 50 replays/month
Sentry Team Plan ($26/mo): 50,000 errors/month, 500 replays/month

## Success Metrics

Once deployed, you should see in Sentry:

1. **Errors Dashboard:**
   - Real-time error tracking
   - Stack traces with source maps
   - User context (if authenticated)

2. **Performance Monitoring:**
   - Page load times
   - API response times
   - Slow transactions alerts

3. **Session Replays:**
   - Video replay of error sessions
   - User journey before error
   - DOM mutations and console logs

## Troubleshooting Commands

```bash
# Check build output for Sentry
cd apps/mouth
pnpm build 2>&1 | grep -i sentry

# Test local build
pnpm build && pnpm start

# Check Fly.io secrets
flyctl secrets list -a mouth

# Check Fly.io logs for Sentry
flyctl logs -a mouth | grep -i sentry
```

## Documentation

Full documentation: `docs/SENTRY_CONFIGURATION.md`
