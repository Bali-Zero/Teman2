import { test, expect } from "@playwright/test";
import { installNoWriteGuard } from "./_support/no-write-context";

/**
 * REGRESSION GUARD for the "dream ejection" defect (#5181/#5189, cured
 * 2026-06/2026-08 via `d6556a75b` + `fcf3bf7e5`) — replayed and confirmed
 * CURED against live production 2026-08-29 before this file was written
 * (research/operations/2026-08-28-beyond-sota-product-ux-visual-design.md
 * discovery: `discovery_five_measured_defects_on_public_surfaces_2026_08_28.md`).
 *
 * The bug: `/dream` is reachable anonymously, but every keystroke in the
 * article composer triggers a debounced (2s) autosave to
 * `POST /api/dream/state`, which requires auth. Before the cure, ANY 401 on
 * that call (i.e. every anonymous visitor's first keystroke) was read by
 * `client.ts`'s global 401 handler as "your session expired" and the
 * visitor was hard-redirected to `login?expired=true&reason=token_expired`
 * — ejecting someone who was never asked to log in. The cure
 * (`dream.api.ts` passes `{ redirectOnUnauthorized: false }`, `client.ts`
 * only redirects when that flag is not explicitly false) makes the 401
 * classify-and-swallow instead of ejecting.
 *
 * This test is kept as a PERMANENT regression guard, not deleted just
 * because the defect is currently cured (guilt+innocence needs both
 * states — L11-PR1 spec, PR-1 acceptance criteria). Guilt case: on a
 * scratch branch reverting #5181/#5189, this test goes red naming the
 * `login?expired=true` ejection; run against current prod it is green.
 *
 * PROVE THE GUARDED PATH WAS ACTUALLY EXERCISED (refutation round 2). The
 * original version of this test only checked the URL after a fixed wait —
 * with dead hydration (React never attached to the SSR'd `<input>`, so the
 * debounced autosave `useEffect` never fires) `pressSequentially` still
 * types into the raw DOM node, the URL never changes, and this test PASSED
 * having exercised nothing. It now `waitForResponse`s the real
 * `POST .../api/dream/state` and asserts it is 401 — if that response never
 * arrives within the timeout, `waitForResponse` throws and the test FAILS,
 * which is the correct outcome for "the guard was never exercised".
 *
 * `/api/dream/state` is explicitly allowlisted in `installNoWriteGuard`
 * (not blocked like the rest of the write surface): a 401 means the
 * backend's auth gate rejected the request BEFORE any handler ran, so
 * nothing is persisted — observing the real 401 is the entire point of
 * this test, not a side effect to suppress.
 */
test("typing on /dream never ejects an anonymous visitor to the login page", async ({
  page,
}) => {
  // Sentry fires on every keystroke's console.error here (see dream/page.tsx
  // — "a visitor merely typing... produced one such event every 2 seconds").
  // /api/dream/state itself is the one write this test needs to observe for
  // real, so it's allowlisted rather than blocked.
  const guard = await installNoWriteGuard(page, {
    allowedWritePathPrefixes: ["/api/dream/state"],
  });

  await page.goto("/dream");

  // The composer hydrates client-side from localStorage/initial state — wait
  // for the real editable field, not a fixed sleep.
  const titleInput = page.getByPlaceholder("Titolo dell'articolo...");
  await titleInput.waitFor({ state: "visible", timeout: 20_000 });

  // Real typing (not `.fill()`), matching the spec's "real typing where the
  // defect involved autosave/debounce" requirement — the autosave effect is
  // keyed off React state changes driven by actual input events.
  const autosavePromise = page.waitForResponse(
    (resp) =>
      resp.url().includes("/api/dream/state") &&
      resp.request().method() === "POST",
    { timeout: 15_000 },
  );
  await titleInput.pressSequentially("S", { delay: 50 });

  // If hydration is dead this throws (timeout) instead of silently passing
  // — that IS the failure mode this guard exists to catch.
  const autosaveResponse = await autosavePromise;
  expect(
    autosaveResponse.status(),
    "autosave did not answer 401 for an anonymous visitor — either auth " +
      "state changed or the endpoint stopped gating correctly",
  ).toBe(401);

  // Give the (expected-401, classify-and-swallow) catch handler + a
  // (would-be) redirect's navigation time to actually land.
  await page.waitForTimeout(1_000);

  const url = page.url();
  expect(url, `visitor was ejected — landed on ${url}`).not.toContain(
    "login?expired=true",
  );
  expect(url, `visitor was ejected — landed on ${url}`).not.toContain(
    "reason=token_expired",
  );
  // Positive assertion, not just "didn't eject": still on /dream.
  expect(new URL(url).pathname).toBe("/dream");

  expect(
    guard.unexpectedWrites().map((r) => `${r.method()} ${r.url()}`),
    "an unblocked write (other than the allowlisted autosave 401) reached " +
      "production — see _support/no-write-context.ts",
  ).toEqual([]);
});
