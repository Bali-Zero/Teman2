# Sentry Error Tracking Configuration

## Overview

Sentry error tracking is fully configured for production error monitoring in `apps/mouth/`.

## Configuration Files

### 1. Client-Side Configuration (`sentry.client.config.ts`)

**Location:** `apps/mouth/sentry.client.config.ts`

**Features:**

- Session replay (10% sample rate)
- Error replay (100% sample rate)
- Masks all text and media for privacy
- Blocks error sending in development
- Performance tracing (10% in production, 100% in dev)

**Environment Variables Required:**

- `NEXT_PUBLIC_SENTRY_DSN` - Client-side DSN (publicly visible)
- `NODE_ENV` - Automatically set by Next.js

### 2. Server-Side Configuration (`sentry.server.config.ts`)

**Location:** `apps/mouth/sentry.server.config.ts`

**Features:**

- Server-side error tracking
- Performance tracing (10% in production)
- Source map upload support

**Environment Variables Required:**

- `SENTRY_DSN` - Server-side DSN (secret)
- `NODE_ENV` - Automatically set by Next.js

### 3. Edge Runtime Configuration (`sentry.edge.config.ts`)

**Location:** `apps/mouth/sentry.edge.config.ts`

**Features:**

- Edge function error tracking
- Performance tracing

**Environment Variables Required:**

- `SENTRY_DSN` - Edge runtime DSN (secret)

### 4. Instrumentation Hook (`src/instrumentation.ts`)

**Location:** `apps/mouth/src/instrumentation.ts`

Automatically loads the correct Sentry configuration based on runtime:

- Node.js runtime → loads `sentry.server.config.ts`
- Edge runtime → loads `sentry.edge.config.ts`
- Client-side → loaded via `next.config.ts` automatically

### 5. Global Error Handler (`src/app/global-error.tsx`)

**Location:** `apps/mouth/src/app/global-error.tsx`

- Already configured to capture all unhandled errors
- Sends errors to Sentry automatically
- Shows user-friendly error UI

## Environment Variables Setup

Add these to your `.env.local` (not committed):

```bash
# Sentry - Get these from https://sentry.io/settings/projects/
NEXT_PUBLIC_SENTRY_DSN=https://your-public-key@o123456.ingest.sentry.io/123456
SENTRY_DSN=https://your-secret-key@o123456.ingest.sentry.io/123456
SENTRY_ORG=your-org-name
SENTRY_PROJECT=mouth
SENTRY_AUTH_TOKEN=your-auth-token-for-source-maps
```

### How to Get These Values:

1. **Create Sentry Project:**
   - Go to https://sentry.io
   - Create a new project (select Next.js)
   - Name it "mouth"

2. **Get DSN:**
   - Go to Settings → Projects → mouth → Client Keys (DSN)
   - Copy the DSN URL
   - Use the same DSN for both `NEXT_PUBLIC_SENTRY_DSN` and `SENTRY_DSN`

3. **Get Organization Name:**
   - Go to Settings → General Settings
   - Copy your Organization Slug

4. **Get Auth Token:**
   - Go to Settings → Developer Settings → Auth Tokens
   - Create new token with "Project: Read & Write" and "Release: Admin" permissions
   - Copy the token

## Source Maps Upload

Source maps are automatically uploaded during production builds when:

- `SENTRY_DSN` or `NEXT_PUBLIC_SENTRY_DSN` is set
- `SENTRY_AUTH_TOKEN` is set
- Build runs with `NODE_ENV=production`

Configuration in `next.config.ts`:

```typescript
const sentryWebpackPluginOptions = {
  silent: true,
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  disableServerWebpackPlugin: !process.env.SENTRY_DSN,
  disableClientWebpackPlugin: !process.env.NEXT_PUBLIC_SENTRY_DSN,
};
```

## Testing

### Local Testing (Development):

1. Start dev server:

   ```bash
   cd apps/mouth
   pnpm dev
   ```

2. Errors are **NOT** sent to Sentry (blocked by `beforeSend`)
3. Check console for Sentry initialization logs

### Production Testing:

1. Build and start:

   ```bash
   cd apps/mouth
   pnpm build
   pnpm start
   ```

2. Trigger test error:
   - Add this to any page component:
     ```typescript
     useEffect(() => {
       throw new Error('[TEST] Sentry error tracking');
     }, []);
     ```

3. Check Sentry dashboard:
   - Go to https://sentry.io/organizations/[your-org]/issues/
   - Should see the test error appear within seconds

### Verify in Fly.io:

After deployment:

```bash
flyctl logs -a mouth
# Should see Sentry initialization logs
```

## Error Context Captured

Sentry automatically captures:

- **User context:** User ID, email (if authenticated)
- **Request context:** URL, headers, query params
- **Browser context:** User agent, viewport, browser version
- **Performance:** Page load time, API response times
- **Session replay:** 10% of sessions, 100% of error sessions
- **Stack traces:** With source maps for readable error locations

## Performance Monitoring

**Traces Sample Rates:**

- Production: 10% (cost-effective)
- Development: 100% (full visibility)

**Monitored Operations:**

- Page loads
- API calls
- Database queries (if configured)
- Custom transactions (via `Sentry.startTransaction()`)

## Privacy & Security

**Client-side privacy protections:**

- All text is masked in session replays (`maskAllText: true`)
- All media is blocked in session replays (`blockAllMedia: true`)
- No sensitive data (passwords, tokens) sent to Sentry
- Development errors are not sent to Sentry

**Server-side security:**

- `SENTRY_DSN` is kept secret (not exposed to browser)
- Source maps uploaded but not served to users
- Auth token stored securely in environment variables

## Troubleshooting

### No errors appearing in Sentry:

1. Check environment variables are set:

   ```bash
   echo $NEXT_PUBLIC_SENTRY_DSN
   echo $SENTRY_DSN
   ```

2. Check Sentry initialization:
   - Open browser DevTools → Console
   - Should see Sentry init messages (in dev mode)

3. Test manually:
   ```typescript
   import * as Sentry from '@sentry/nextjs';
   Sentry.captureException(new Error('Test error'));
   ```

### Source maps not uploading:

1. Verify auth token is set:

   ```bash
   echo $SENTRY_AUTH_TOKEN
   ```

2. Check build logs for Sentry upload messages

3. Verify token has correct permissions:
   - Project: Read & Write
   - Release: Admin

### Build fails with Sentry errors:

1. Check `next.config.ts` conditional wrapping:

   ```typescript
   // Only wraps with Sentry if DSN is set
   export default process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN
     ? withSentryConfig(configWithAnalyzer, sentryWebpackPluginOptions)
     : configWithAnalyzer;
   ```

2. Build without Sentry temporarily:
   ```bash
   unset SENTRY_DSN NEXT_PUBLIC_SENTRY_DSN
   pnpm build
   ```

## Related Files

- `apps/mouth/next.config.ts` - Sentry webpack plugin configuration
- `apps/mouth/.env.example` - Environment variable template
- `apps/mouth/src/app/global-error.tsx` - Global error boundary
- `apps/mouth/package.json` - Sentry package version

## References

- [Sentry Next.js Docs](https://docs.sentry.io/platforms/javascript/guides/nextjs/)
- [Sentry Session Replay](https://docs.sentry.io/product/session-replay/)
- [Sentry Source Maps](https://docs.sentry.io/platforms/javascript/sourcemaps/)

## Status

✅ Configuration complete
✅ TypeScript compilation successful
✅ Production build successful
✅ Ready for deployment
