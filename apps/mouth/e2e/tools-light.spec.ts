import { test, expect, type Page } from "@playwright/test";

/**
 * MYTHOS Stage-B Batch 3 — Rumah Putih LIGHT theme for the TWO real client
 * tools: the KBLI Navigator (/kbli) and the Visa Oracle funnel (/visa).
 *
 * Pins:
 *   - the tool page's top-level wrapper carries the warm-paper surface
 *     (--surface-base #f7f6f2 → rgb(247, 246, 242)) via RUMAH_VARS / the
 *     re-pointed --kbli-* tokens;
 *   - NavShell (the fixed masthead) stays its dark navy anchor (the tool shell
 *     has no Footer, unlike the blog/service pages);
 *   - the KBLI ZantaraChat widget is present (a dark island), and the visa
 *     funnel entry buttons are present + clickable (funnel logic intact);
 *   - no horizontal overflow at 390px (mobile) on either tool;
 *   - the homepage persona doors: tax + property carry a Soon badge and do NOT
 *     navigate; visa + kbli still navigate.
 *
 * Describe title contains "page Page" — required by the CI grep
 * (.github/workflows/tests.yml runs `npx playwright test --grep "page Page"`).
 */

const PAPER = "rgb(247, 246, 242)"; // --surface-base #f7f6f2 under Rumah Putih

function parseRgb(value: string): { r: number; g: number; b: number } | null {
  const m = value.match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const [r, g, b] = m[1].split(",").map((n) => parseInt(n.trim(), 10));
  return { r, g, b };
}

/** A color is "dark" when its luminance is low (navy/charcoal masthead). */
function isDark(value: string): boolean {
  const rgb = parseRgb(value);
  if (!rgb) return false;
  const lum = 0.2126 * rgb.r + 0.7152 * rgb.g + 0.0722 * rgb.b;
  return lum < 90; // navy #1e3863 ≈ 49, #0e1a30 ≈ 26
}

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

/**
 * The KBLI + visa TOOL pages render NavShell as their only dark chrome anchor
 * (the FunnelFrame/AppFrame tool shell has no Footer — unlike the blog/service
 * pages). Assert the masthead stays dark.
 */
async function assertNavDark(page: Page) {
  const nav = page.locator("nav").first();
  await expect(nav).toBeVisible();
  const navBg = await nav.evaluate(
    (el) => getComputedStyle(el).backgroundColor,
  );
  expect(isDark(navBg)).toBe(true);
}

test.describe("client tools light page Page", () => {
  test("/kbli renders on warm paper with navy chrome", async ({ page }) => {
    await page.goto("/kbli");

    const wrapper = page.locator(".rumah-putih").first();
    await expect(wrapper).toBeVisible();
    const wrapperBg = await wrapper.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(wrapperBg).toBe(PAPER);

    await assertNavDark(page);

    // The ZantaraChat widget is present (kept as a dark island, but reachable).
    const chatInput = page
      .locator(".rp-dark-island textarea, textarea")
      .first();
    await expect(chatInput).toBeAttached();
  });

  test("/kbli has no horizontal overflow at 390px", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/kbli");
    await page.locator(".rumah-putih").first().waitFor();
    await assertNoHorizontalOverflow(page);
  });

  test("/kbli/[code] renders ink-on-paper and keeps the consult CTA dark island", async ({
    page,
  }) => {
    await page.goto("/kbli/55101");

    const wrapper = page.locator("article.rumah-putih").first();
    await expect(wrapper).toBeVisible();
    const wrapperBg = await wrapper.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(wrapperBg).toBe(PAPER);

    // The editorial body is ink on paper.
    const bodyColor = await wrapper.evaluate(
      (el) => getComputedStyle(el).color,
    );
    expect(isDark(bodyColor)).toBe(true);

    // The consultation CTA stays a dark island (its gradient can't be CSS-flipped).
    await expect(page.locator("section.rp-dark-island").first()).toBeAttached();

    await assertNavDark(page);
  });

  test("/visa entry renders light and the funnel branch buttons are clickable", async ({
    page,
  }) => {
    await page.goto("/visa");

    const wrapper = page.locator(".rumah-putih").first();
    await expect(wrapper).toBeVisible();

    // The AppFrame title resolves to ink on the light surface.
    const heading = page.locator("h1").first();
    await expect(heading).toBeVisible();
    const headingColor = await heading.evaluate(
      (el) => getComputedStyle(el).color,
    );
    expect(isDark(headingColor)).toBe(true);

    await assertNavDark(page);

    // The two branch buttons are present + navigate (funnel logic intact).
    const clock = page.locator('a[href="/visa/clock"]');
    const match = page.locator('a[href="/visa/match"]');
    await expect(clock).toBeVisible();
    await expect(match).toBeVisible();
    await match.click();
    await expect(page).toHaveURL(/\/visa\/match$/);
  });

  test("/visa has no horizontal overflow at 390px", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/visa");
    await page.locator(".rumah-putih").first().waitFor();
    await assertNoHorizontalOverflow(page);
  });

  test("/visa/match quiz wizard is light and interactive", async ({ page }) => {
    await page.goto("/visa/match");
    // The wizard persists its step to localStorage — clear it so this test
    // always starts on step 1 (independent of prior runs in the same context).
    await page.evaluate(() => localStorage.removeItem("bz.visa_match.wizard"));
    await page.reload();

    await expect(page.locator(".rumah-putih").first()).toBeVisible();
    // Step 1 (Nationality) renders on the light surface with its wizard chrome.
    await expect(page.getByText("Step 1 of 4")).toBeVisible();
    await expect(page.getByText("What's your nationality?")).toBeVisible();
    await assertNavDark(page);

    // The nationality <select> is legible (ink on white) AND accepts input —
    // funnel logic intact (the full cross-step advance is exercised live in the
    // interactivity QA, this pins the on-light interactive surface).
    const select = page.locator("select").first();
    await expect(select).toBeVisible();
    const selectColor = await select.evaluate(
      (el) => getComputedStyle(el).color,
    );
    expect(isDark(selectColor)).toBe(true);
    await select.selectOption("ITA");
    await expect(select).toHaveValue("ITA");
  });

  test("homepage persona doors: tax+property are Soon (no nav), visa+kbli navigate", async ({
    page,
  }) => {
    await page.goto("/");
    const doors = page.getByTestId("persona-doors");
    await expect(doors).toBeVisible();

    // Real tools navigate.
    await expect(doors.locator('a[data-door="visa"]')).toHaveAttribute(
      "href",
      "/visa",
    );
    await expect(doors.locator('a[data-door="company"]')).toHaveAttribute(
      "href",
      "/kbli",
    );

    // Soon doors: Soon badge present, no <a> CTA, no <a> tool deep-link.
    for (const persona of ["tax", "property"]) {
      const article = doors.locator(
        `article#${persona}[data-coming-soon="true"]`,
      );
      await expect(article).toHaveCount(1);
      await expect(article.getByText("Soon", { exact: true })).toBeVisible();
      await expect(doors.locator(`a[data-door="${persona}"]`)).toHaveCount(0);
      await expect(doors.locator(`a[data-tool="${persona}"]`)).toHaveCount(0);
    }
  });
});
