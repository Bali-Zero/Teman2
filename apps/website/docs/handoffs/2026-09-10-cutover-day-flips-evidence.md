# Cutover-day flips — implementation evidence

Date: 10 September 2026  
Scope: `apps/website` only  
Branch state: working tree only; no commit, push, merge or deploy performed.

## Verification summaries

Final `npm test` run, exit 0:

```text
 Test Files  109 passed | 1 skipped (110)
      Tests  1361 passed | 1 skipped (1362)
```

Final `npm run typecheck` run, exit 0:

```text
> @balizero/website-development@0.1.0 typecheck
> tsc --noEmit
```

Formatting:

```text
npx prettier --write <all changed TypeScript, TSX and Markdown files>
```

`git diff --check -- apps/website` also exited 0 with no output.

## Flip status

1. **PASS — permanent redirects.** Every redirect returned by
   `next.config.ts` is now permanent. The legacy Services, KBLI Navigator,
   Journal and About pages use `permanentRedirect()`. The Tax Gap, Visa V2 and
   bare Visa route handlers return 308. The cross-host `retainedHandoff()`
   remains 307 and its existing test still asserts that status.
2. **PASS — indexability.** Root metadata no longer contains a robots noindex
   directive and uses the approved title. The now-empty global `headers()`
   function was removed, so the config emits no global `X-Robots-Tag`. All six
   prep-slice routes and the eight previously explicit private/dynamic routes
   remain covered by per-route noindex assertions.
3. **PASS — public Visa Oracle selector.** `/visa-oracle` retains its
   self-canonical metadata with no robots noindex directive and is now included
   in the sitemap. `/visa`, `/visa-oracle/unlock` and
   `/visa-oracle/privacy` remain excluded from the sitemap.

## Files changed

Production configuration and routes:

- `next.config.ts`
- `src/app/layout.tsx`
- `src/app/sitemap.ts`
- `src/app/services/visa/page.tsx`
- `src/app/services/company/page.tsx`
- `src/app/kbli-navigator/[[...retainedPath]]/page.tsx`
- `src/app/journal/page.tsx`
- `src/app/v2/company/about/page.tsx`
- `src/app/tax/gap/route.ts`
- `src/app/visa-v2/route.ts`
- `src/app/visa/[[...retainedPath]]/route.ts`

Tests:

- `src/app/cutover-metadata.test.ts`
- `src/app/sitemap.test.ts`
- `src/lib/retained-routes.test.ts`
- `src/features/visa-oracle/routes.test.ts`
- `src/app/services/services.test.tsx`
- `src/app/journal/page.test.tsx`
- `src/app/v2/company/about/page.test.tsx`
- `src/app/kbli-navigator/[[...retainedPath]]/page.test.tsx`
- `src/app/tax/gap/route.test.ts`

Evidence:

- `docs/handoffs/2026-09-10-cutover-day-flips-evidence.md`

## Deviations and reasons

- No localhost HTTP smoke test was run because the implementation order
  explicitly prohibited network calls. The deterministic route, metadata,
  sitemap and config tests cover the requested flip contracts; the separate
  verifier can perform the handoff's HTTP checks.
- No root `title.template` was added. Existing child page titles already use the
  `| Bali Zero` suffix, so applying `%s | Bali Zero` would double it.
- The final test total is five higher than the 1,356-test baseline because the
  handoff-required root metadata, config header, KBLI Navigator and Tax Gap
  cases were added. Existing assertions were otherwise changed only where the
  contract moved from 307/`redirect()` to 308/`permanentRedirect()` or where
  `/visa-oracle` became sitemap-visible.
