/**
 * E2E scenarios for the consolidated visa funnel (spec
 * 2026-04-21-visa-funnel-fusion.md).
 *
 * 2026-09-13 — RULING Zero 2026-08-25 («Due porte: 301 → `/visa-oracle`
 * subito»): the two happy-path scenarios that drove the legacy free-text quiz
 * are gone with the quiz. What replaces them is the guard the defect actually
 * needed — the legacy doors must answer a PERMANENT REDIRECT, and the
 * already-shared result links must keep answering 200.
 *
 * The status code is asserted on the HTTP response with redirects disabled, not
 * on a rendered heading and not on the final URL. That is deliberate: the first
 * attempt at this fix used a page-level `permanentRedirect()`, which Next 16
 * prerenders into a 200 HTML document that only redirects client-side after
 * hydration. It would have satisfied any DOM assertion, and any assertion that
 * followed redirects, while shipping nothing.
 *
 * Tests run against the base URL configured in playwright.config.ts.
 * The subdomain-redirect test requires the deployed preview; when running
 * locally it is skipped unless the redirect path is explicitly reachable.
 */

import { expect, test } from "@playwright/test";

const RETIRED_DOORS = ["/visa", "/visa/match"];

test.describe("Visa funnel fusion", () => {
  for (const door of RETIRED_DOORS) {
    test(`retired door: ${door} answers a permanent redirect to /visa-oracle`, async ({
      request,
    }) => {
      const res = await request.get(door, { maxRedirects: 0 });
      expect([301, 308]).toContain(res.status());
      expect(res.headers()["location"]).toMatch(/\/visa-oracle$/);
    });

    test(`retired door: ${door} serves no quiz body`, async ({ request }) => {
      const res = await request.get(door);
      expect(new URL(res.url()).pathname).toBe("/visa-oracle");
      const body = await res.text();
      // The legacy quiz's own copy — present on neither door once retired.
      expect(body).not.toContain("Are you already in Indonesia?");
      expect(body).not.toContain("Budget band for Indonesia setup?");
    });
  }

  test("already-shared result links still resolve (/visa/match/<hash>)", async ({
    request,
  }) => {
    // A hash that cannot exist: the page must still be SERVED (200 + its own
    // "could not find this recommendation" state), never redirected away with
    // the door. Losing these URLs would break every link a visitor saved.
    const res = await request.get("/visa/match/e2e0000000000000", {
      maxRedirects: 0,
    });
    expect(res.status()).toBe(200);
  });

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
