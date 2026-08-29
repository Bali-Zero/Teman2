import { test, expect } from "@playwright/test";
import { installNoWriteGuard } from "./_support/no-write-context";

/**
 * REGRESSION GUARD for the "magic-link dead end" defect. Measured cured
 * live 2026-08-29: `https://balizero.com/portal/magic-link` now 301s to
 * `https://my.balizero.com/portal/magic-link`, which renders the real
 * passwordless sign-in form ("Sign in with a link").
 *
 * This test targets the FINAL host explicitly, on purpose — a sentinel that
 * only asserted `page.goto("https://balizero.com/portal/magic-link")`
 * resolved without throwing would follow the 301 silently and never notice
 * if the REAL host (my.balizero.com) started serving a dead end again
 * (spec: "a sentinel written only against balizero.com would follow a 301
 * and never notice if the real host broke").
 *
 * DOES NOT SUBMIT THE FORM. Submitting `POST /api/auth/request-magic-link`
 * sends a real, enumeration-safe-but-real email — out of scope for a
 * read-only journey probe. This test asserts the entry point is reachable
 * and interactive; the redemption leg (magic/page.tsx, token exchange) is
 * not exercised here.
 */
test("magic-link entry point is reachable on its real host and renders the sign-in form", async ({
  page,
}) => {
  // Measured: this page fires Sentry + GA4 beacons on load like every other
  // page in the suite, even without any form interaction. See
  // _support/no-write-context.ts for why source-reading alone is never
  // trusted for this claim again.
  const guard = await installNoWriteGuard(page);

  const response = await page.goto("https://balizero.com/portal/magic-link", {
    waitUntil: "domcontentloaded",
  });
  expect(
    response?.ok(),
    `navigation failed: status ${response?.status()}`,
  ).toBe(true);

  const finalUrl = new URL(page.url());
  expect(
    finalUrl.hostname,
    `did not land on my.balizero.com — got ${page.url()}`,
  ).toBe("my.balizero.com");
  expect(finalUrl.pathname).toBe("/portal/magic-link");

  // The real, current copy of the page (not a paraphrase) — read off
  // production, not assumed from a report.
  await expect(
    page.getByRole("heading", { name: "Sign in with a link" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Enter your registered email and we'll send you a one-time link",
      { exact: false },
    ),
  ).toBeVisible();

  // Form is genuinely interactive (hydrated), not a static/broken shell —
  // the submit button is enabled once React hydration completes.
  const emailInput = page.getByLabel("Email address");
  await expect(emailInput).toBeVisible();
  const submitButton = page.getByRole("button", { name: /Email me a link/i });
  await expect(submitButton).toBeEnabled({ timeout: 15_000 });

  // Explicitly NOT calling submitButton.click() / form submit — no real
  // email is sent by this sentinel.

  expect(
    guard.unexpectedWrites().map((r) => `${r.method()} ${r.url()}`),
    "an unblocked write reached production — see _support/no-write-context.ts",
  ).toEqual([]);
});
