import { test, expect } from "@playwright/test";

/**
 * Owner ruling #4 (2026-08-25, docs/plans/2026-08-24-visa-oracle-live/
 * OWNER-RULINGS-2026-08-25.md §4, verbatim): "la vecchia porta si ritira
 * con 301 -> /visa-oracle — mai un motore non verificato indicizzato col
 * nostro nome sopra." TWO-DOORS.md measured `/visa` and `/visa/match` as
 * the `index, follow` legacy funnel (versus `/visa-oracle`'s
 * `noindex, nofollow`, which this change does NOT touch — that comes off
 * only after a separate lane lands the T2-copy fix, ruling §1).
 *
 * These are next.config.ts `redirects()` entries, not a page-level
 * `redirect()` call — unlike category-alias-redirect.spec.ts's target,
 * there is no streaming/client-hop ambiguity: Next.js serves a real HTTP
 * redirect with a Location header before any React tree renders.
 *
 * DEV-VS-PROD STATUS CODE, measured directly (not assumed): `permanent:
 * true` serves as **308** under `next dev` (empirically confirmed here via
 * both a raw `curl` and this very spec, `--webpack` mode, this worktree,
 * 2026-08-25) and as **301** under `next build && next start` — the mode
 * CI's e2e job and Vercel production both actually run (playwright.config.ts
 * `webServer.command`). Next.js deliberately downgrades to 308 in dev so a
 * redirect-config edit mid-iteration doesn't get permanently cached by the
 * browser; the destination is identical either way. Accepting both keeps
 * this spec meaningful when run locally against `next dev`, not only in CI.
 *
 * Describe title contains "page Page" — required by the CI grep
 * (.github/workflows/tests.yml runs `npx playwright test --grep "page Page"`).
 */

const PERMANENT_REDIRECT_STATUSES = [301, 308];

test.describe("visa old-funnel retirement redirect page Page", () => {
  test("GET /visa responds 301 (308 in dev) -> /visa-oracle", async ({
    request,
  }) => {
    const response = await request.get("/visa", { maxRedirects: 0 });
    expect(PERMANENT_REDIRECT_STATUSES).toContain(response.status());
    expect(response.headers()["location"]).toContain("/visa-oracle");
  });

  test("GET /visa/match responds 301 (308 in dev) -> /visa-oracle", async ({
    request,
  }) => {
    const response = await request.get("/visa/match", { maxRedirects: 0 });
    expect(PERMANENT_REDIRECT_STATUSES).toContain(response.status());
    expect(response.headers()["location"]).toContain("/visa-oracle");
  });

  test("browser navigation to /visa lands on /visa-oracle", async ({
    page,
  }) => {
    await page.goto("/visa", { waitUntil: "domcontentloaded" });
    expect(page.url()).toContain("/visa-oracle");
  });

  test("/visa/match/{hash} result pages are NOT caught by the redirect (exact-match only)", async ({
    request,
  }) => {
    // Any hash — the assertion is about routing, not about a real result
    // existing. A caught-by-redirect bug would 301 this too; the real
    // route 404s honestly instead (VisaCheckRepository finds no row).
    const response = await request.get("/visa/match/doesnotexist12", {
      maxRedirects: 0,
    });
    expect(PERMANENT_REDIRECT_STATUSES).not.toContain(response.status());
  });

  test("/visa-oracle itself still responds 200 (not further redirected) and stays noindex", async ({
    request,
  }) => {
    // Ruling §4's binding order: 301 now, noindex comes off only after a
    // separate T2-copy lane (ruling §1). This guards the "leave the
    // noindex exactly as it is" half of that order.
    const response = await request.get("/visa-oracle", { maxRedirects: 0 });
    expect(response.status()).toBe(200);
    const body = await response.text();
    expect(body).toContain('name="robots" content="noindex, nofollow"');
  });
});
