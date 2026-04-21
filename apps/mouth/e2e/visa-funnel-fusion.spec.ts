/**
 * E2E scenarios for the consolidated visa funnel (spec
 * 2026-04-21-visa-funnel-fusion.md).
 *
 * Tests run against the live base URL configured in playwright.config.ts.
 * The subdomain-redirect test requires the deployed preview; when running
 * locally it is skipped unless the redirect path is explicitly reachable.
 */

import { expect, test } from "@playwright/test";

test.describe("Visa funnel fusion", () => {
  test("match happy path: wizard → accordion visible on result", async ({ page }) => {
    await page.goto("/visa");
    await page.getByRole("link", { name: /no, i'm planning/i }).click();

    // Step 1 — nationality
    await page.getByRole("combobox").selectOption("USA");
    await page.getByRole("button", { name: /next/i }).click();

    // Step 2 — purpose
    await page.getByRole("button", { name: /work remotely/i }).click();
    await page.getByRole("button", { name: /next/i }).click();

    // Step 3 — duration (default)
    await page.getByRole("button", { name: /next/i }).click();

    // Step 4 — budget
    await page.getByRole("button", { name: /idr 50m/i }).click();
    await page.getByRole("button", { name: /see result/i }).click();

    // Result page renders
    await expect(page.getByText(/your visa:/i)).toBeVisible();

    // Accordion is visible (closed by default)
    const accordion = page.getByRole("button", { name: /ask 3 free questions/i });
    await expect(accordion).toBeVisible();

    // WhatsApp CTA is still visible and unaffected
    await expect(page.getByRole("link", { name: /whatsapp/i }).first()).toBeVisible();
  });

  test("wizard_abstained path: investor + under-50M → HandoffWaLink, no accordion", async ({
    page,
  }) => {
    await page.goto("/visa");
    await page.getByRole("link", { name: /no, i'm planning/i }).click();

    await page.getByRole("combobox").selectOption("ITA");
    await page.getByRole("button", { name: /next/i }).click();

    await page.getByRole("button", { name: /invest/i }).click();
    await page.getByRole("button", { name: /next/i }).click();

    await page.getByRole("button", { name: /next/i }).click();

    await page.getByRole("button", { name: /under idr 50m/i }).click();
    await page.getByRole("button", { name: /see result/i }).click();

    // Accordion MUST NOT appear
    await expect(
      page.getByRole("button", { name: /ask 3 free questions/i }),
    ).toHaveCount(0);

    // HandoffWaLink is visible with pre-compiled summary
    const wa = page.getByRole("link", { name: /start on whatsapp/i }).first();
    await expect(wa).toBeVisible();
    const href = await wa.getAttribute("href");
    expect(href).toBeTruthy();
    expect(href).toContain("wa.me/");
    const decoded = decodeURIComponent(href!);
    expect(decoded).toContain("investor");
    expect(decoded).toContain("ITA");
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
