import { test, expect } from "@playwright/test";

/**
 * KBLI sector off-canvas — the intercepted `@panel` slot on `/kbli`.
 *
 * The load-bearing property is not "a panel opens": it is that the panel is an
 * ENHANCEMENT of `/kbli/sectors/[id]` and never a replacement. So the suite
 * pins both halves — the soft-navigation panel AND the untouched full page —
 * plus the history semantics that make the URL shareable.
 *
 * Describe title contains "page Page" — required by the CI grep
 * (.github/workflows/tests.yml runs `npx playwright test --grep "page Page"`).
 */

const panel = "kbli-sector-panel";

/**
 * Interception only happens on a SOFT navigation, so every test here must
 * click after React has claimed the anchor — before that, the same click is a
 * plain browser navigation and legitimately renders the full page. Waiting for
 * the fiber key on the very anchor under test is that precondition itself,
 * rather than a sleep that happens to be long enough.
 */
async function gotoKbli(page: import("@playwright/test").Page, path = "/kbli") {
  await page.goto(path);
  await page.waitForFunction(() => {
    const el = document.querySelector('a[href="/kbli/sectors/A"]');
    return !!el && Object.keys(el).some((k) => k.startsWith("__reactFiber$"));
  });
}

test.describe("KBLI sector off-canvas page Page", () => {
  test("card click opens the panel without leaving /kbli", async ({ page }) => {
    await gotoKbli(page);
    const card = page.locator('a[href="/kbli/sectors/A"]').first();
    await card.click();

    const sheet = page.getByTestId(panel);
    await expect(sheet).toBeVisible();
    await expect(page).toHaveURL(/\/kbli\/sectors\/A$/);
    // The grid page is still mounted underneath — that is the whole point.
    await expect(page.locator("h1").first()).toHaveText("KBLI 2025");
    await expect(sheet).toHaveAttribute("aria-modal", "true");
    await expect(sheet).toHaveAttribute("role", "dialog");
  });

  test("Escape, X and the overlay all close it back to /kbli", async ({
    page,
  }) => {
    for (const close of ["escape", "button", "overlay"] as const) {
      await gotoKbli(page);
      await page.locator('a[href="/kbli/sectors/A"]').first().click();
      await expect(page.getByTestId(panel)).toBeVisible();

      if (close === "escape") await page.keyboard.press("Escape");
      if (close === "button")
        await page.getByRole("button", { name: "Close sector panel" }).click();
      if (close === "overlay")
        await page
          .getByTestId("kbli-sector-panel-overlay")
          .click({ position: { x: 10, y: 10 } });

      await expect(page.getByTestId(panel)).toBeHidden();
      await expect(page).toHaveURL(/\/kbli$/);
    }
  });

  test("browser Back closes the panel instead of leaving /kbli", async ({
    page,
  }) => {
    await gotoKbli(page);
    await page.locator('a[href="/kbli/sectors/A"]').first().click();
    await expect(page.getByTestId(panel)).toBeVisible();

    await page.goBack();
    await expect(page.getByTestId(panel)).toBeHidden();
    await expect(page).toHaveURL(/\/kbli$/);

    // ...and Forward re-opens it.
    await page.goForward();
    await expect(page.getByTestId(panel)).toBeVisible();
  });

  test("the section strip swaps sections without closing the panel", async ({
    page,
  }) => {
    await gotoKbli(page);
    await page.locator('a[href="/kbli/sectors/A"]').first().click();
    const sheet = page.getByTestId(panel);
    await expect(sheet).toBeVisible();

    await sheet.getByTestId("kbli-panel-next").click();
    await expect(page).toHaveURL(/\/kbli\/sectors\/B$/);
    await expect(sheet).toBeVisible();
    await expect(sheet.getByTestId("kbli-panel-section-eyebrow")).toHaveText(
      "Section B",
    );

    await sheet
      .getByTestId("kbli-panel-strip")
      .getByText("G", { exact: true })
      .click();
    await expect(page).toHaveURL(/\/kbli\/sectors\/G$/);
    await expect(sheet).toBeVisible();
  });

  test("a code drills down inside the panel and comes back", async ({
    page,
  }) => {
    await gotoKbli(page);
    await page.locator('a[href="/kbli/sectors/A"]').first().click();
    const sheet = page.getByTestId(panel);
    await expect(sheet.getByTestId("kbli-panel-code-grid")).toBeVisible();

    await sheet
      .locator('[data-testid="kbli-panel-code-grid"] a')
      .first()
      .click();
    await expect(sheet.getByTestId("kbli-panel-code-detail")).toBeVisible();
    await expect(page).toHaveURL(/\/kbli\/sectors\/A\?code=\d{5}$/);
    // Still a panel, still on top of /kbli — no page navigation happened.
    await expect(page.locator("h1").first()).toHaveText("KBLI 2025");

    await sheet.getByTestId("kbli-panel-detail-back").click();
    await expect(sheet.getByTestId("kbli-panel-code-grid")).toBeVisible();
    await expect(page).toHaveURL(/\/kbli\/sectors\/A$/);
  });

  test("the card keeps its canonical href for new-tab / no-JS use", async ({
    page,
  }) => {
    await gotoKbli(page);
    await page.locator('a[href="/kbli/sectors/A"]').first().click();
    const first = page
      .locator('[data-testid="kbli-panel-code-grid"] a')
      .first();
    // Only a plain left click is taken over; the href itself is untouched, so
    // cmd-click, middle-click and a JS-less browser still reach the real page.
    await expect(first).toHaveAttribute("href", /^\/kbli\/\d{5}$/);
  });

  test("closing from a drill-down lands back on /kbli, not on the sector URL", async ({
    page,
  }) => {
    await gotoKbli(page);
    await page.locator('a[href="/kbli/sectors/A"]').first().click();
    const sheet = page.getByTestId(panel);
    await sheet
      .locator('[data-testid="kbli-panel-code-grid"] a')
      .first()
      .click();
    await expect(sheet.getByTestId("kbli-panel-code-detail")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.getByTestId(panel)).toBeHidden();
    await expect(page).toHaveURL(/\/kbli$/);
  });

  test("browser Back from a drill-down returns to the grid, panel still open", async ({
    page,
  }) => {
    await gotoKbli(page);
    await page.locator('a[href="/kbli/sectors/A"]').first().click();
    const sheet = page.getByTestId(panel);
    await sheet
      .locator('[data-testid="kbli-panel-code-grid"] a')
      .first()
      .click();
    await expect(sheet.getByTestId("kbli-panel-code-detail")).toBeVisible();

    await page.goBack();
    await expect(sheet.getByTestId("kbli-panel-code-grid")).toBeVisible();
    await expect(sheet).toBeVisible();
    await expect(page).toHaveURL(/\/kbli\/sectors\/A$/);
  });

  test("keyboard: focus is trapped in the panel and restored on close", async ({
    page,
  }) => {
    await gotoKbli(page);
    const card = page.locator('a[href="/kbli/sectors/A"]').first();
    // press() targets the element itself. A bare keyboard.press would go to
    // whatever holds focus, and the page's search input takes it on hydration
    // (KBLISearch autoFocus).
    await card.press("Enter");

    const sheet = page.getByTestId(panel);
    await expect(sheet).toBeVisible();

    // Every stop of a Tab cycle stays inside the dialog.
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press("Tab");
      expect(
        await sheet.evaluate((el) => el.contains(document.activeElement)),
      ).toBe(true);
    }

    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();
    await expect(card).toBeFocused();
  });

  test("body scroll is locked while the panel is open", async ({ page }) => {
    // Radix locks scroll through react-remove-scroll, which marks the body
    // with data-scroll-locked rather than setting style.overflow. Asserting
    // the mechanism it actually uses, measured on this version.
    const locked = () =>
      page.evaluate(() => document.body.hasAttribute("data-scroll-locked"));

    await gotoKbli(page);
    expect(await locked()).toBe(false);

    await page.locator('a[href="/kbli/sectors/A"]').first().click();
    await expect(page.getByTestId(panel)).toBeVisible();
    expect(await locked()).toBe(true);

    await page.keyboard.press("Escape");
    await expect(page.getByTestId(panel)).toBeHidden();
    await expect.poll(locked).toBe(false);
  });

  test("the Cards/Table toggle is untouched and survives the panel", async ({
    page,
  }) => {
    await gotoKbli(page);
    await page.getByRole("tab", { name: /Table/ }).click();
    await expect(page.getByRole("tab", { name: /Table/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    await page.locator('a[href="/kbli/sectors/A"]').first().click();
    await expect(page.getByTestId(panel)).toBeVisible();
    // The open dialog aria-hides the rest of the page (correct modal
    // behaviour), so the toggle is no longer reachable by role — assert on the
    // DOM instead: its state must survive untouched behind the panel.
    expect(
      await page.evaluate(() =>
        [...document.querySelectorAll('[role="tab"]')]
          .find((t) => /Table/.test(t.textContent ?? ""))
          ?.getAttribute("aria-selected"),
      ),
    ).toBe("true");

    await page.keyboard.press("Escape");
    await expect(page.getByTestId(panel)).toBeHidden();
    await expect(page.getByRole("tab", { name: /Table/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  test("mobile viewport renders a bottom sheet, desktop a side panel", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await gotoKbli(page);
    await page.locator('a[href="/kbli/sectors/A"]').first().click();
    const sheet = page.getByTestId(panel);
    await expect(sheet).toBeVisible();
    const mobile = (await sheet.boundingBox())!;
    expect(mobile.width).toBeGreaterThan(380);

    await page.setViewportSize({ width: 1280, height: 900 });
    const desktop = (await sheet.boundingBox())!;
    expect(desktop.width).toBeLessThan(700);
    expect(desktop.x).toBeGreaterThan(500);
  });

  // ── The half that must NOT change ──────────────────────────────────────

  test("REGRESSION: /kbli/sectors/A hard-loads as a full page, no panel", async ({
    page,
  }) => {
    await page.goto("/kbli/sectors/A");
    await expect(page.getByTestId(panel)).toHaveCount(0);
    await expect(page.locator("h1").first()).toHaveText(
      "Agriculture, Forestry & Fishing",
    );
    await expect(page.locator('a[href="/kbli/01111"]').first()).toBeVisible();
  });

  test("REGRESSION: a drill-down URL hard-loads as the sector page", async ({
    page,
  }) => {
    await page.goto("/kbli/sectors/A?code=01111");
    await expect(page.getByTestId(panel)).toHaveCount(0);
    await expect(page.locator("h1").first()).toHaveText(
      "Agriculture, Forestry & Fishing",
    );
  });

  test("DOCUMENTED: interception also applies from the /kbli/sectors index", async ({
    page,
  }) => {
    // Not an accident: the @panel slot lives in the /kbli layout, so every
    // soft navigation to a sector URL from anywhere under /kbli is
    // intercepted. Pinned so the behaviour is a decision, not a surprise.
    await gotoKbli(page, "/kbli/sectors");
    await page.locator('a[href="/kbli/sectors/A"]').first().click();
    await expect(page.getByTestId(panel)).toBeVisible();
    await expect(page.locator("h1").first()).toHaveText("KBLI 2025 Sectors");
  });
});
