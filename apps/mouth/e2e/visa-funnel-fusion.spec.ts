/**
 * E2E scenarios for the consolidated visa funnel (spec
 * 2026-04-21-visa-funnel-fusion.md).
 *
 * Tests run against the live base URL configured in playwright.config.ts.
 * The subdomain-redirect test requires the deployed preview; when running
 * locally it is skipped unless the redirect path is explicitly reachable.
 *
 * RETIRED 2026-08-25 (Owner ruling #4, docs/plans/2026-08-24-visa-oracle-
 * live/OWNER-RULINGS-2026-08-25.md §4): this file used to carry two
 * interactive-flow tests ("match happy path" and "wizard_abstained path")
 * that `page.goto("/visa")` and drove the AppWizard at /visa/match end to
 * end. Both `/visa` and `/visa/match` now 301 to /visa-oracle
 * (next.config.ts redirects()) — neither URL renders that wizard anymore,
 * so a browser navigation to either one never reaches the UI those tests
 * exercised. The wizard component and its backend
 * (apps/backend-rag/backend/app/routers/visa_check.py) are UNTOUCHED and
 * still serve already-shared /visa/match/{hash} result links; there is
 * simply no reachable door left to drive the flow from a cold navigation.
 * Removed rather than left to rot red (neither test was actually collected
 * by CI's `--grep "page Page|@offline"` filter, so this was silent
 * staleness, not a caught regression — the same failure-mode class this
 * repo's own scars warn about). Redirect coverage for the retired doors
 * lives in e2e/visa-old-funnel-retirement.spec.ts.
 */

import { expect, test } from "@playwright/test";

test.describe("Visa funnel fusion", () => {
  test("subdomain 302: visa.balizero.com/privacy redirects to /visa/privacy", async ({
    request,
  }) => {
    // Only meaningful against the deployed preview where DNS resolves the
    // subdomain. Skip when running against localhost.
    const baseURL = test.info().project.use?.baseURL ?? "";
    if (!baseURL.includes("balizero.com") && !baseURL.includes("vercel.app")) {
      test.skip(true, "Subdomain redirect test requires deployed preview");
    }

    const res = await request.get("https://visa.balizero.com/privacy", {
      maxRedirects: 0,
    });
    expect(res.status()).toBe(302);
    const location = res.headers()["location"];
    expect(location).toMatch(/balizero\.com\/visa\/privacy$/);
  });
});
