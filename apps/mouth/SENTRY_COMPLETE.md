# ✅ Sentry Error Tracking - Configuration Complete

## Summary

Sentry error tracking è stato completamente configurato per `apps/mouth/`.

## Files Created (7 files)

| File                                 | Purpose                                     | Status     |
| ------------------------------------ | ------------------------------------------- | ---------- |
| `sentry.client.config.ts`            | Client-side error tracking + session replay | ✅ Created |
| `sentry.server.config.ts`            | Server-side error tracking                  | ✅ Created |
| `sentry.edge.config.ts`              | Edge runtime error tracking                 | ✅ Created |
| `src/instrumentation.ts`             | Auto-load configs by runtime                | ✅ Created |
| `src/__tests__/sentry.test.ts`       | Unit tests for Sentry setup                 | ✅ Created |
| `SENTRY_SETUP.md`                    | Quick setup guide                           | ✅ Created |
| `../../docs/SENTRY_CONFIGURATION.md` | Full documentation                          | ✅ Created |

## Files Updated (2 files)

| File                       | Change                         | Status              |
| -------------------------- | ------------------------------ | ------------------- |
| `.env.example`             | Added `SENTRY_AUTH_TOKEN`      | ✅ Updated          |
| `src/app/global-error.tsx` | Already had Sentry integration | ✅ No change needed |

## Verification Status

| Check                      | Status        |
| -------------------------- | ------------- |
| TypeScript compilation     | ✅ Passed     |
| Production build           | ✅ Passed     |
| No blocking in development | ✅ Verified   |
| Source map upload config   | ✅ Configured |

## What's Working Now

### ✅ Client-Side Tracking

- Automatic error capture
- Session replay (10% sample rate)
- Error replay (100% sample rate)
- Performance tracing (10% in prod)
- Privacy: all text masked, all media blocked
- Development errors NOT sent to Sentry

### ✅ Server-Side Tracking

- API route errors captured
- Server component errors captured
- Performance tracing (10% in prod)

### ✅ Edge Runtime Tracking

- Edge function errors captured
- Middleware errors captured

### ✅ Source Maps

- Automatically uploaded during build
- Readable stack traces in production
- Original TypeScript file names preserved

## Next Steps for Production

### 1. Create Sentry Project

```bash
# Go to: https://sentry.io
# Create new project → Select "Next.js" → Name: "mouth"
```

### 2. Get Credentials from Sentry Dashboard

- **DSN:** Settings → Projects → mouth → Client Keys (DSN)
- **Org:** Settings → General Settings → Organization Slug
- **Auth Token:** Settings → Developer Settings → Auth Tokens
  - Create token with permissions: "Project: Read & Write", "Release: Admin"

### 3. Add to Local Environment

Create `apps/mouth/.env.local`:

```bash
NEXT_PUBLIC_SENTRY_DSN=https://xxx@o123456.ingest.sentry.io/123456
SENTRY_DSN=https://xxx@o123456.ingest.sentry.io/123456
SENTRY_ORG=your-org-slug
SENTRY_PROJECT=mouth
SENTRY_AUTH_TOKEN=your-auth-token
```

### 4. Add to Fly.io Production

```bash
cd apps/mouth

flyctl secrets set \
  NEXT_PUBLIC_SENTRY_DSN="https://xxx@o123456.ingest.sentry.io/123456" \
  SENTRY_DSN="https://xxx@o123456.ingest.sentry.io/123456" \
  SENTRY_ORG="your-org-slug" \
  SENTRY_PROJECT="mouth" \
  SENTRY_AUTH_TOKEN="your-auth-token"
```

### 5. Deploy

```bash
flyctl deploy
```

### 6. Verify Production

```bash
# Check logs
flyctl logs -a mouth | grep -i sentry

# Visit Sentry dashboard
# https://sentry.io/organizations/[your-org]/issues/
```

## Testing Locally

### 1. Start Dev Server

```bash
cd apps/mouth
pnpm dev
```

### 2. Verify No Errors

- Open http://localhost:3000
- Check browser console
- No Sentry errors should appear (development mode blocks sending)

### 3. Test Production Build

```bash
pnpm build
pnpm start
```

### 4. Trigger Test Error (Optional)

Add to any page temporarily:

```typescript
'use client';
import { useEffect } from 'react';

export default function TestPage() {
  useEffect(() => {
    throw new Error('[TEST] Sentry tracking');
  }, []);

  return <div>Test page</div>;
}
```

## Documentation

| Document                        | Description                      |
| ------------------------------- | -------------------------------- |
| `SENTRY_SETUP.md`               | Quick setup & verification guide |
| `docs/SENTRY_CONFIGURATION.md`  | Full technical documentation     |
| `docs/SENTRY_USAGE_EXAMPLES.md` | Code examples & best practices   |

## Configuration Details

### Sample Rates (Production)

- **Traces:** 10% (cost-effective performance monitoring)
- **Session Replays:** 10% of normal sessions
- **Error Replays:** 100% of error sessions

### Privacy & Security

- ✅ All text masked in replays
- ✅ All media blocked in replays
- ✅ Development errors not sent
- ✅ SENTRY_DSN kept secret (server-only)
- ✅ Source maps uploaded but not served to users

### Error Context Captured

- User ID, email (if authenticated)
- Request URL, headers, query params
- Browser version, user agent, viewport
- Page load time, API response times
- Session replay for error sessions
- Stack traces with source maps

## Troubleshooting

### Issue: No errors in Sentry dashboard

**Solution:** Check environment variables are set:

```bash
echo $NEXT_PUBLIC_SENTRY_DSN
echo $SENTRY_DSN
```

### Issue: Source maps not uploading

**Solution:** Verify auth token has correct permissions:

- Project: Read & Write
- Release: Admin

### Issue: Build fails with Sentry

**Solution:** Temporarily disable Sentry:

```bash
unset SENTRY_DSN NEXT_PUBLIC_SENTRY_DSN
pnpm build
```

## Cost Estimate

For ~1,000 users/day:

- ~100 traced requests/day (10% sample)
- ~100 session replays/day (10% sample)
- All errors captured with replay

**Sentry Plans:**

- **Free:** 5,000 errors/month, 50 replays/month
- **Team ($26/mo):** 50,000 errors/month, 500 replays/month

## Success Criteria

Once deployed, Sentry dashboard should show:

1. ✅ Real-time error tracking
2. ✅ Stack traces with source maps (readable file names)
3. ✅ User context (if authenticated)
4. ✅ Page load times
5. ✅ API response times
6. ✅ Session replays for error sessions

## Related Files

```
apps/mouth/
├── sentry.client.config.ts       # Client error tracking
├── sentry.server.config.ts       # Server error tracking
├── sentry.edge.config.ts         # Edge runtime tracking
├── src/
│   ├── instrumentation.ts        # Auto-load configs
│   ├── app/
│   │   └── global-error.tsx      # Global error boundary
│   └── __tests__/
│       └── sentry.test.ts        # Unit tests
├── next.config.ts                # Webpack plugin config
├── .env.example                  # Env var template
└── SENTRY_SETUP.md              # Quick guide

docs/
├── SENTRY_CONFIGURATION.md       # Full documentation
└── SENTRY_USAGE_EXAMPLES.md     # Code examples
```

## Production-Ready Standard ✅

Following `AI_ONBOARDING.md` pillars:

| Pillar             | Implementation                   | Status  |
| ------------------ | -------------------------------- | ------- |
| **Tests**          | Unit tests for all configs       | ✅ Done |
| **Logging**        | Sentry structured error tracking | ✅ Done |
| **Documentation**  | 3 comprehensive docs             | ✅ Done |
| **Error Handling** | Global error boundary + captures | ✅ Done |

## Final Checklist

- [x] 3 Sentry config files created
- [x] Instrumentation hook created
- [x] .env.example updated
- [x] TypeScript compilation successful
- [x] Production build successful
- [x] Unit tests created
- [x] Documentation created
- [x] Usage examples provided
- [x] Ready for production deployment

## 🚀 Ready for Production!

The Sentry error tracking system is fully configured and production-ready.

**Next action:** Add Sentry credentials to Fly.io secrets and deploy.
