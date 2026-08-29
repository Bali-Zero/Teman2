import { test, expect } from "@playwright/test";

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
 */
test("typing on /dream never ejects an anonymous visitor to the login page", async ({
  page,
}) => {
  await page.goto("/dream");

  // The composer hydrates client-side from localStorage/initial state — wait
  // for the real editable field, not a fixed sleep.
  const titleInput = page.getByPlaceholder("Titolo dell'articolo...");
  await titleInput.waitFor({ state: "visible", timeout: 20_000 });

  // Real typing (not `.fill()`), matching the spec's "real typing where the
  // defect involved autosave/debounce" requirement — the autosave effect is
  // keyed off React state changes driven by actual input events.
  await titleInput.pressSequentially("S", { delay: 50 });

  // The autosave fires 2000ms after the last keystroke (ArticleComposer's
  // `useEffect` debounce). Wait past it plus margin for the fetch+catch to
  // resolve and for a (would-be) redirect's navigation to actually land.
  await page.waitForTimeout(4_000);

  const url = page.url();
  expect(url, `visitor was ejected — landed on ${url}`).not.toContain(
    "login?expired=true",
  );
  expect(url, `visitor was ejected — landed on ${url}`).not.toContain(
    "reason=token_expired",
  );
  // Positive assertion, not just "didn't eject": still on /dream.
  expect(new URL(url).pathname).toBe("/dream");
});
