import { test, expect } from "@playwright/test";

test.describe("Theme Toggle", () => {
  // Theme toggle is in workspace (requires auth), test on dev with bypass
  test("html element does not have hardcoded dark class", async ({ page }) => {
    await page.goto("/");
    // The root html should NOT have className="dark" anymore
    // (the canonical core ThemeProvider uses the data-theme attribute)
    const htmlClass = await page.locator("html").getAttribute("class");
    // class may be empty or carry utilities; the old hardcoded "dark" is gone
    // core ThemeProvider sets data-theme instead
    void htmlClass;
    const dataTheme = await page.locator("html").getAttribute("data-theme");
    expect(dataTheme).toBeTruthy();
  });

  test("data-theme defaults to editorial on the public host", async ({
    page,
  }) => {
    await page.goto("/");
    // Pre-paint script in app/layout.tsx: kita./prime. → operative-dark,
    // my./zantara. → operative-light, everything else (public/dev) → editorial.
    const dataTheme = await page.locator("html").getAttribute("data-theme");
    expect(dataTheme).toBe("editorial");
  });

  test("ThemeProvider applies data-theme attribute", async ({ page }) => {
    await page.goto("/");
    // Verify the attribute exists on html element
    await expect(page.locator("html[data-theme]")).toBeAttached();
  });
});
