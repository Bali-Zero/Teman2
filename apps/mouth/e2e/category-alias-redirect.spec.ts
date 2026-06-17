import { test, expect } from "@playwright/test";

/**
 * Category-alias canonicalization (MYTHOS ledger item 2).
 *
 * The blog route (blog)/[category]/[slug] historically served the same
 * article under alias categories (e.g. /immigration/X AND /visas/X both 200,
 * duplicate content relying on the canonical <meta> alone). The page now
 * issues permanentRedirect() (308) from a known alias to the canonical URL.
 *
 * STREAMING CAVEAT: the route tree has loading.tsx, so the page is streamed.
 * When redirect() fires after the shell has been flushed, Next.js cannot
 * change the status code anymore — it emits a 200 whose body carries the
 * redirect marker (a <meta http-equiv="refresh"> tag / NEXT_REDIRECT) and
 * the browser performs the hop client-side. Tests therefore accept EITHER
 * a real 307/308 OR a 200 whose body contains the redirect marker, and
 * assert the browser lands on the canonical URL in both cases.
 *
 * Describe title contains "page Page" — required by the CI grep
 * (.github/workflows/tests.yml runs `npx playwright test --grep "page Page"`).
 */

// MDX article that exists on disk:
// apps/mouth/src/content/articles/immigration/e23-employee-kitas-guide.mdx
// Folder "immigration" is an alias of canonical category "visas".
const SLUG = "e23-employee-kitas-guide";
const ALIAS_URL = `/immigration/${SLUG}`;
const CANONICAL_URL = `/visas/${SLUG}`;

test.describe("category alias redirect page Page", () => {
  test("alias URL redirects to the canonical category URL", async ({
    page,
  }) => {
    await page.goto(ALIAS_URL, { waitUntil: "domcontentloaded" });
    // Server 308: goto already follows the redirect chain.
    // Streamed 200 + meta refresh: the hop happens client-side shortly after.
    await page.waitForURL(`**${CANONICAL_URL}`, { timeout: 20_000 });
    expect(page.url()).toContain(CANONICAL_URL);
  });

  test("alias URL responds 307/308 or 200 with redirect marker", async ({
    request,
  }) => {
    const response = await request.get(ALIAS_URL, { maxRedirects: 0 });
    const status = response.status();
    expect([200, 307, 308]).toContain(status);
    if (status === 200) {
      // Streamed response — body must carry the redirect marker
      const body = await response.text();
      expect(body).toMatch(
        new RegExp(
          `NEXT_REDIRECT|http-equiv="refresh"[^>]*${CANONICAL_URL.replace(/\//g, "\\/")}`,
          "i",
        ),
      );
    } else {
      const location = response.headers()["location"] ?? "";
      expect(location).toContain(CANONICAL_URL);
    }
  });

  test("canonical URL does not redirect (no loop)", async ({ page }) => {
    await page.goto(CANONICAL_URL, { waitUntil: "domcontentloaded" });
    // Give a potential (buggy) client-side hop a moment, then re-check.
    await page.waitForTimeout(1_500);
    expect(page.url()).toContain(CANONICAL_URL);
  });
});
