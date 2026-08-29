import { test, expect, type Route } from "@playwright/test";
import { installNoWriteGuard } from "./_support/no-write-context";

/**
 * REGRESSION GUARD for the visa-clock overstay defect (#5170, cured via
 * `10ba83473`). Before the cure, `[hash]/page.tsx` computed
 * `daysLeft = Math.max(0, daysToExpiry)` — clamping a negative
 * (already-overstayed) value to 0 and rendering "Valid until <date>" / a
 * "0 days" countdown to someone who had, in reality, overstayed for months.
 * The cure keeps `daysToExpiry` signed and branches on `isOverstay` before
 * ever reaching the "Valid until" render path.
 *
 * DESIGN CHOICE — why this test does NOT drive a real
 * `POST /api/visa/clock` with an old entry date, and instead mocks the
 * network boundary. Read this before changing it.
 *
 *   `POST /api/visa/clock` (backend/app/routers/visa_check.py) has NO
 *   sandbox/probe-tenancy column on its target table (migration
 *   124_visa_checks.sql — no `is_probe_sandbox`, unlike `intel_items`
 *   which got one in migration 187) and NO public DELETE endpoint. Every
 *   real submission is a DURABLE row with no cleanup path — the exact
 *   shape of concern the squad ledger already flagged as NR-1 for the VOA
 *   probe ("the VOA tables have no probe-tenancy column... any analytics
 *   counting checks created will silently include probe traffic"). Here
 *   it's worse: an overstay case is fabricated CLIENT DATA (a visa type +
 *   dates implying a real person is 370+ days overstayed), not just an
 *   idempotency-ledger row.
 *
 *   So this test drives the REAL, deployed production page and REAL,
 *   deployed production JavaScript bundle (the actual regression surface
 *   for #5170 — a pure client-side `Math.max` bug in `[hash]/page.tsx`,
 *   unrelated to backend/DB behavior), but intercepts the two network
 *   calls the journey makes and returns a synthetic overstay `ClockResponse`
 *   payload — matching the PR-1 spec's own framing of this acceptance
 *   criterion: "an overstay-date PAYLOAD renders an overstay branch, never
 *   'Valid until'". Zero rows written to production.
 *
 *   CORRECTED (refutation round 1, cicatrix-superscar.md family #6): the
 *   original version of this comment claimed "zero analytics pollution" on
 *   the strength of reading THIS component's source. That was false —
 *   watching the actual network traffic this page issues (not just the
 *   visa-clock component) showed `apps/mouth/src/app/visa/layout.tsx`
 *   mounts `<SessionInit funnel="visa">`, which POSTs
 *   `/api/funnel/session/touch` (a real `funnel_sessions` row, 90-day
 *   retention, carrying THIS run's IP hash) on every load, and GA/Sentry
 *   beacons fire independently of anything this spec stubs. `_support/
 *   no-write-context.ts` (`installNoWriteGuard`, installed below, BEFORE
 *   `page.goto`) blocks that whole class and self-proves nothing else
 *   unblocked reached our own origins — a claim earned by a running
 *   assertion, not by re-reading source a second time.
 *
 *   UNRESOLVED (reported, not guessed): a true full-stack regression guard
 *   (real POST, real DB round-trip) would need either (a) a probe-sandbox
 *   column on `visa_checks` mirroring `intel_items.is_probe_sandbox` plus a
 *   retention/cleanup job, or (b) one operator-approved synthetic fixture
 *   row created out-of-band with a documented, stable hash for a read-only
 *   GET-based regression guard. Neither exists today; this is a decision
 *   for whoever owns `visa_checks` retention, not something to assume here.
 */

const SENTINEL_HASH = "sentineloverstay";

function isoDaysAgo(days: number): string {
  return new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
}

function buildOverstayPayload() {
  const entryDate = isoDaysAgo(400);
  const expiryDate = isoDaysAgo(370); // 370 days in the past -> definitely overstay
  return {
    hash: SENTINEL_HASH,
    visa_type: "C1",
    entry_date: entryDate,
    expiry_date: expiryDate,
    extensions_possible: 1,
    extension_days: 30,
    checkpoints: [
      {
        label: "D-60",
        at: isoDaysAgo(430),
        title: "Start paperwork",
        body: "",
      },
      {
        label: "D-30",
        at: isoDaysAgo(400),
        title: "Documents ready",
        body: "",
      },
      {
        label: "D-14",
        at: isoDaysAgo(384),
        title: "Kantor Imigrasi visit",
        body: "",
      },
      { label: "D-7", at: isoDaysAgo(377), title: "Pickup window", body: "" },
      { label: "D-1", at: isoDaysAgo(371), title: "Final check", body: "" },
    ],
    result_url: `/visa/clock/${SENTINEL_HASH}`,
    session_jwt: null,
    daysOverstayedForAssertion: 370, // not part of the real API shape; used below only
  };
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test("an overstay payload on /visa/clock/[hash] renders the overstay branch, never 'Valid until'", async ({
  page,
}) => {
  const payload = buildOverstayPayload();
  const { daysOverstayedForAssertion, ...clockResponseShape } = payload;

  // Blocks funnel-session/analytics/Sentry/GA before the first navigation —
  // see file header + _support/no-write-context.ts for what this replaced
  // (a false "zero analytics pollution" claim) and why it's a route, not a
  // sentence in a commit message. `/api/visa/clock` is allowlisted here
  // (NOT left to fail the self-proving check below) because the two
  // `page.route` calls right after this ARE the block for it — a spec's
  // own mock intercepting a URL is exactly as safe as the guard's generic
  // ones, and pretending otherwise would make this assertion cry wolf on
  // every run (found empirically: the first version of this test failed
  // its own `unexpectedWrites()` check on the mocked POST it was already
  // fulfilling itself).
  const guard = await installNoWriteGuard(page, {
    allowedWritePathPrefixes: ["/api/visa/clock"],
  });

  // Intercept BOTH network calls the journey makes. Never let either reach
  // the real backend (see file header for why). The guard above already
  // fulfills `/api/analytics/funnel-event` generically; these two are the
  // visa-clock-specific calls it does NOT know about.
  await page.route("**/api/visa/clock", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await fulfillJson(route, clockResponseShape, 201);
  });
  await page.route(`**/api/visa/clock/${SENTINEL_HASH}`, async (route) => {
    await fulfillJson(route, clockResponseShape, 200);
  });

  await page.goto("/visa/clock", { waitUntil: "load" });
  // HYDRATION GOTCHA (found empirically running this suite against real
  // production, not assumed): `domcontentloaded` — or even `load` alone —
  // fires before Next.js finishes hydrating this client component. Filling
  // the fields and clicking submit too early operates on the raw SSR HTML,
  // whose <form> has no React onSubmit attached yet: the browser performs a
  // NATIVE full-page GET submission to the same URL (visible as a second
  // full page load with no `/api/visa/clock` request at all), silently
  // resetting every field. `page.waitForLoadState("networkidle")` does NOT
  // work as a substitute here — this page never goes network-idle within
  // 30s (Sentry/GA beacons keep firing) — so a short fixed wait for
  // hydration is the honest, verified-empirically fix, not a guess.
  await page.waitForTimeout(2_500);

  await page.getByLabel("Entry date").fill(isoDaysAgo(400));
  await page.getByLabel("Visa type").selectOption("C1");
  await page.getByRole("button", { name: /Show my timeline/i }).click();

  // Client-side router.push to /visa/clock/{hash} after the (mocked) POST.
  await page.waitForURL(`**/visa/clock/${SENTINEL_HASH}`, { timeout: 15_000 });

  // The overstay branch's own heading — never "Valid until".
  await expect(
    page.getByRole("heading", { name: /stay has already ended/i }),
  ).toBeVisible();

  const bodyText = await page.locator("body").innerText();
  expect(bodyText).not.toContain("Valid until");
  expect(bodyText).toContain(`${daysOverstayedForAssertion} days ago`);

  // Self-proving "leaves no trace": not "we blocked the known list", but
  // "nothing non-idempotent reached our own origins during this run" —
  // derived from the actual request stream, not the blocklist's say-so.
  expect(
    guard.unexpectedWrites().map((r) => `${r.method()} ${r.url()}`),
    "an unblocked write reached production — see _support/no-write-context.ts",
  ).toEqual([]);
});
