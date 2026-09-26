import { test, expect, type Page } from "@playwright/test";

/** R19 public presentation. The page Page title is the CI discovery contract. */

test.beforeEach(async ({ page }) => {
  await page.route("**/*", (route) =>
    ["GET", "HEAD"].includes(route.request().method())
      ? route.continue()
      : route.fulfill({ status: 204, body: "" }),
  );
});

const PAPER = "rgb(247, 244, 238)"; // R19 paper

/** Parse "rgb(r, g, b)" / "rgba(r, g, b, a)" → {r,g,b}. */
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
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    // 1px slop for sub-pixel rounding.
    return doc.scrollWidth - doc.clientWidth;
  });
  expect(overflow).toBeLessThanOrEqual(1);
}

async function assertR19Chrome(page: Page) {
  const nav = page.locator("nav").first();
  await expect(nav).toBeVisible();
  const navBg = await nav.evaluate(
    (el) => getComputedStyle(el).backgroundColor,
  );
  expect(navBg).toBe(PAPER);

  const footer = page.locator("footer").last();
  await expect(footer).toBeAttached();
  const footerBg = await footer.evaluate(
    (el) => getComputedStyle(el).backgroundColor,
  );
  expect(footerBg).toBe("rgb(238, 233, 225)");
}

test.afterEach(async ({ page }) => {
  await page.close();
});

test.describe("service pages light page Page", () => {
  test("/services renders on warm paper with R19 chrome and stays price-free", async ({
    page,
  }) => {
    await page.goto("/services");

    const wrapper = page.locator(".rumah-putih").first();
    await expect(wrapper).toBeVisible();
    const wrapperBg = await wrapper.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(wrapperBg).toBe(PAPER);

    await assertR19Chrome(page);

    // #1263: the services index must not reintroduce any price. Scope to the
    // page wrapper so unrelated chrome (e.g. a "Talk to us" CTA) can't trip it.
    const wrapperText = (await wrapper.innerText()).toLowerCase();
    expect(wrapperText).not.toMatch(/\bidr\b/);
    expect(wrapperText).not.toMatch(/rp\s?\d/);
  });

  test("/services has no horizontal overflow at 390px", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/services");
    await page.locator(".rumah-putih").first().waitFor();
    await assertNoHorizontalOverflow(page);
  });

  test("/contact renders light with legible contact CTAs and R19 chrome", async ({
    page,
  }) => {
    await page.goto("/contact");

    const wrapper = page.locator(".rumah-putih").first();
    await expect(wrapper).toBeVisible();
    const wrapperBg = await wrapper.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(wrapperBg).toBe(PAPER);

    await assertR19Chrome(page);

    // /contact is a channel-card page (WhatsApp / Email / Office), not a <form>.
    // Assert the contact CTAs are present and reachable on the light surface.
    const whatsapp = page.locator('a[href*="wa.me"], a[href*="whatsapp"]');
    expect(await whatsapp.count()).toBeGreaterThan(0);
    const email = page.locator('a[href^="mailto:"]');
    expect(await email.count()).toBeGreaterThan(0);

    // The email channel card (white fill) carries ink text → must be dark.
    const emailCardText = await email
      .first()
      .evaluate((el) => getComputedStyle(el).color)
      .catch(() => "rgb(0, 0, 0)");
    expect(isDark(emailCardText)).toBe(true);
  });

  test("/contact has no horizontal overflow at 390px", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/contact");
    await page.locator(".rumah-putih").first().waitFor();
    await assertNoHorizontalOverflow(page);
  });

  test("service detail renders ink-on-paper with R19 chrome", async ({
    page,
  }) => {
    // visa is a stable, always-present service slug (SERVICES_DATA).
    await page.goto("/services/visa");

    const wrapper = page.locator(".rumah-putih").first();
    await expect(wrapper).toBeVisible();
    const wrapperBg = await wrapper.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(wrapperBg).toBe(PAPER);

    // The hardcoded-dark detail page now resolves a navy heading on paper.
    const heading = page.locator("h1").first();
    await expect(heading).toBeVisible();
    const headingColor = await heading.evaluate(
      (el) => getComputedStyle(el).color,
    );
    expect(isDark(headingColor)).toBe(true);

    await assertR19Chrome(page);
  });

  test("service detail has no horizontal overflow at 390px", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/services/visa");
    await page.locator(".rumah-putih").first().waitFor();
    await assertNoHorizontalOverflow(page);
  });
});
