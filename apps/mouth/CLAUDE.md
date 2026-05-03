# Mouth (Frontend) — Non-Inferable Knowledge

> Archive: `docs/sessions/CLAUDE-archive-2026-04-06.md`

---

## Critical Gotchas

### Middleware RSC Detection (CORS fix)
Next.js `<Link>` prefetches cause CORS errors when middleware redirects cross-origin.
Return 204 (No Content) for prefetch requests:

```typescript
const isRSC =
  request.nextUrl.searchParams.has("_rsc") ||
  request.headers.get("RSC") === "1" ||
  request.headers.get("Next-Router-Prefetch") === "1" ||
  request.headers.get("Purpose") === "prefetch";
if (isRSC) {
  return new NextResponse(null, { status: 204 });
}
```

### Console Logging — Never Log Full Arrays
The omnichannel page was logging 2,237+ messages (entire WhatsApp conversation arrays).
Log only: message count, first/last item summary. Never `console.log(fullArray)`.

### TypeScript Workarounds (band-aids in code)
- `(file as any).created_time` — GDrive file type missing `created_time`
- `ease: 'linear' as const` — Framer Motion type mismatch
- `String(error)` — unknown error type in catch blocks

---

## Test Infrastructure

- **LocalStorageMock**: Use `Map`-based storage, not `vi.fn()` (state must persist across calls)
- **Reset pattern**: `_resetForTesting()` method on singleton services
- **Request helper**: `createRequest()` for middleware tests with custom headers
- **Framework**: Vitest (unit) + Playwright (E2E)

---

## Non-Standard Patterns

- KBLI Navigator at `/kbli-navigator` → 301 → `/kbli` (rewrite in `next.config.ts`)
- SSO: `nz_access_token` httpOnly cookie on `.balizero.com` domain
- All subdomains share auth via cookie domain
