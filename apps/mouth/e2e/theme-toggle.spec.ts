import { test, expect, type Page } from "@playwright/test";

const KITA_ORIGIN = "http://kita.localhost:3000";
const MY_ORIGIN = "http://my.localhost:3000";

async function seedTheme(page: Page, theme?: string): Promise<void> {
  await page.addInitScript((storedTheme) => {
    localStorage.removeItem("bz-theme");
    localStorage.removeItem("theme");
    if (storedTheme) {
      localStorage.setItem("bz-theme", storedTheme);
    }
  }, theme);
}

test.describe("Bali Zero product-family theme contract", () => {
  test("Kita defaults to day mode without a stored preference", async ({
    page,
  }) => {
    await seedTheme(page);

    await page.goto(`${KITA_ORIGIN}/`);

    await expect(page.locator("html")).toHaveAttribute(
      "data-theme",
      "operative-light",
    );
  });

  test("My defaults to day mode without a stored preference", async ({
    page,
  }) => {
    await seedTheme(page);

    await page.goto(`${MY_ORIGIN}/portal/login-upgraded`);

    await expect(page.locator("html")).toHaveAttribute(
      "data-theme",
      "operative-light",
    );
  });

  test("an explicit dark preference wins over the product day default", async ({
    page,
  }) => {
    await seedTheme(page, "operative-dark");

    await page.goto(`${KITA_ORIGIN}/`);

    await expect(page.locator("html")).toHaveAttribute(
      "data-theme",
      "operative-dark",
    );
  });

  test("theme selection uses the data-theme contract instead of a dark class", async ({
    page,
  }) => {
    await seedTheme(page);

    await page.goto(`${KITA_ORIGIN}/`);

    const htmlClass = await page.locator("html").getAttribute("class");
    expect((htmlClass ?? "").split(/\s+/)).not.toContain("dark");
    await expect(page.locator("html[data-theme]")).toBeAttached();
  });
});
