import type { Page, Request } from "@playwright/test";

/**
 * Shared "leaves no trace" guard for every production journey sentinel.
 *
 * WHY THIS FILE EXISTS (measured, not assumed). L11-PR1's own commit
 * message claimed visa-clock.spec.ts "does not POST" and "zero analytics
 * pollution" because the source it drove (`/visa/clock`) never itself calls
 * `fetch`. Instrumenting the ACTUAL network traffic the page issues (not the
 * source of the one component under test) showed that claim was false:
 *
 *   https://balizero.com/api/funnel/session/touch   -> INSERT INTO
 *     funnel_sessions (backend/app/routers/funnel.py), a NEW durable row
 *     PER RUN carrying the probe's IP hash, 90-day retention — fired by
 *     <SessionInit funnel="visa"> mounted in apps/mouth/src/app/visa/layout.tsx,
 *     nothing to do with the visa-clock component itself.
 *   https://balizero.com/api/analytics/funnel-event  -> a funnel_events row.
 *   https://o<id>.ingest.us.sentry.io/api/.../envelope/  -> a real Sentry event.
 *   3 GA/GTM beacons, fired by packages/core/analytics/funnel-app.ts's
 *     `gtag(...)` call, which runs BEFORE the first-party POST above.
 *
 * "This probe leaves no trace" is therefore never accepted again on source
 * reading alone (cicatrix-superscar.md family #6 — reading code proves what
 * *can* happen, not what a real browser *does*). This helper (a) blocks the
 * known write surface before it can reach production, and (b) is
 * SELF-PROVING: it independently records every request the page issues and
 * lets a spec assert that nothing non-idempotent reached one of our own
 * origins UNBLOCKED — so a future write path this list didn't anticipate
 * fails the spec loudly instead of silently writing to prod forever on an
 * hourly cron.
 */

/**
 * Glob patterns matched against the FULL request URL (Playwright's
 * `page.route`), applied BEFORE any spec-specific `page.route` call and
 * BEFORE the first `page.goto` — every caller installs this first thing in
 * the test body. Each pattern here is a surface actually observed firing
 * from these journeys (see the header above) plus adjacent analytics/ad
 * vendors that share the same "third-party write, zero UX value to a
 * probe" shape.
 */
const BLOCKED_PATTERNS: readonly string[] = [
  "**/api/funnel/session/**",
  "**/api/analytics/**",
  "**/*sentry.io/**",
  "**/google-analytics.com/**",
  "**/googletagmanager.com/**",
  "**/doubleclick.net/**",
  "**/*/g/collect*",
];

const WRITE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/**
 * Hosts this suite treats as "our own production infrastructure" — a write
 * landing on any of these, unblocked, is a real durable side effect. Covers
 * the apex + every subdomain of balizero.com (mouth on the apex, the portal
 * app on my.balizero.com) plus the Fly backend the frontend calls directly
 * (apps/mouth/next.config.ts CSP `connect-src` names it explicitly — e.g.
 * dream.spec.ts's POST /api/dream/state resolves to
 * https://nuzantara-rag.fly.dev/api/dream/state, a DIFFERENT host than the
 * page the browser is on).
 */
const OWN_ORIGIN_RE = /(^|\.)balizero\.com$|(^|\.)nuzantara-rag\.fly\.dev$/;

export interface NoWriteGuardOptions {
  /**
   * Path prefixes on our own origins that THIS spec is deliberately allowed
   * to hit unblocked, because observing the real response is the entire
   * point of the test — e.g. dream.spec.ts needs the genuine 401 from
   * `POST /api/dream/state` to prove the auth gate runs (and therefore
   * nothing is persisted) BEFORE the redirect-suppression fix is trusted.
   * The guard still records every such request; it is on the spec to
   * assert something concrete about its response (status, body) rather
   * than silently trusting the allowlist entry is safe.
   */
  allowedWritePathPrefixes?: string[];
}

export interface NoWriteGuard {
  /** Every request Playwright observed on this page, blocked or not. */
  allRequests: Request[];
  /**
   * Non-idempotent (POST/PUT/PATCH/DELETE) requests that reached one of our
   * own production origins WITHOUT being intercepted by the blocklist above
   * and WITHOUT matching an explicitly declared `allowedWritePathPrefixes`
   * entry. A spec asserts this is empty. It is derived from the same
   * request stream a spec's own `page.route` stubs observe — not from a
   * separate "trust the blocklist" claim — so a write path nobody
   * anticipated still shows up here even though nothing blocked it.
   */
  unexpectedWrites(): Request[];
}

export async function installNoWriteGuard(
  page: Page,
  options: NoWriteGuardOptions = {},
): Promise<NoWriteGuard> {
  const allowedWritePathPrefixes = options.allowedWritePathPrefixes ?? [];
  const allRequests: Request[] = [];
  const interceptedByGuard = new Set<Request>();

  // Registered before any spec-specific listener/route: this call itself
  // happens before `page.goto` in every caller.
  page.on("request", (req) => {
    allRequests.push(req);
  });

  for (const pattern of BLOCKED_PATTERNS) {
    // eslint-disable-next-line no-await-in-loop -- registration order across
    // these patterns doesn't matter (all take the identical action), but
    // each must be armed before the loop returns control to the caller.
    await page.route(pattern, async (route) => {
      interceptedByGuard.add(route.request());
      // `fulfill`, never `abort`: at least one caller
      // (packages/core/auth/session-bridge.ts `attachToServerSession`, used
      // by <SessionInit>) awaits its fetch with NO `.catch` — an aborted
      // request there raises an unhandled promise rejection in the page,
      // not just "no bytes sent". A fake 200 keeps every caller's own
      // success path exactly as happy as a real beacon endpoint would,
      // with zero bytes ever reaching production.
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "{}",
      });
    });
  }

  return {
    allRequests,
    unexpectedWrites() {
      return allRequests.filter((req) => {
        if (interceptedByGuard.has(req)) return false;
        if (!WRITE_METHODS.has(req.method())) return false;
        let url: URL;
        try {
          url = new URL(req.url());
        } catch {
          return false; // not a real absolute URL — can't be "our origin"
        }
        if (!OWN_ORIGIN_RE.test(url.hostname)) return false;
        return !allowedWritePathPrefixes.some((prefix) =>
          url.pathname.startsWith(prefix),
        );
      });
    },
  };
}
