import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

import { getExactSnapshotPrice } from "../src/lib/pricing-snapshot";
import { SERVICES_DATA } from "../src/data/services_data";

const SCREENSHOT_DIR = path.resolve(
  process.cwd(),
  "../../docs/audits/screenshots/visa-oracle-v2",
);

test("book visa cards use exact PricingTool identities without overflow", async ({
  page,
}, testInfo) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  if (testInfo.project.name === "Mobile Chrome") {
    await page.setViewportSize({ width: 320, height: 800 });
  }
  await page.goto("/book/services");
  const cards = page.getByTestId("book-service-cards");
  await cards.scrollIntoViewIfNeeded();

  for (const [category, key] of [
    ["single_entry_visas", "C1 Tourism"],
    ["single_entry_visas", "C2 Business"],
    ["multiple_entry_visas", "D1 Tourism (1 Year)"],
    ["kitas_permits", "E33G Remote Worker (Offshore)"],
    ["kitas_permits", "Retirement (Offshore)"],
  ] as const) {
    const price = getExactSnapshotPrice(category, key);
    expect(price).not.toBeNull();
    await expect(cards.getByRole("heading", { name: key })).toBeVisible();
    await expect(
      cards.getByText(price as string, { exact: true }),
    ).toBeVisible();
  }
  await expect(
    cards.getByText("C317 Single Entry", { exact: true }),
  ).toHaveCount(0);
  expect(
    await page.evaluate(
      () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
  ).toBe(true);

  const companyTab = page.getByRole("button", {
    name: "Company Setup",
    exact: true,
  });
  await companyTab.focus();
  await expect(companyTab).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("book-service-cards")).toBeVisible();
  const visaTab = page.getByRole("button", { name: "Visa", exact: true });
  await visaTab.focus();
  await page.keyboard.press("Enter");
  await expect(
    cards.getByRole("heading", { name: "C1 Tourism" }),
  ).toBeVisible();

  if (testInfo.project.name === "Mobile Chrome") {
    await cards.scrollIntoViewIfNeeded();
    const cardBoxes = await cards
      .locator(":scope > *")
      .evaluateAll((elements) =>
        elements.map((element) => {
          const box = element.getBoundingClientRect();
          return {
            left: box.left,
            top: box.top,
            right: box.right,
            bottom: box.bottom,
          };
        }),
      );
    for (const control of [
      page.getByTestId("book-locale-switcher"),
      page.getByTestId("book-mobile-nav"),
    ]) {
      const controlBox = await control.evaluate((element) => {
        const box = element.getBoundingClientRect();
        return {
          left: box.left,
          top: box.top,
          right: box.right,
          bottom: box.bottom,
        };
      });
      for (const cardBox of cardBoxes) {
        const overlapWidth = Math.max(
          0,
          Math.min(controlBox.right, cardBox.right) -
            Math.max(controlBox.left, cardBox.left),
        );
        const overlapHeight = Math.max(
          0,
          Math.min(controlBox.bottom, cardBox.bottom) -
            Math.max(controlBox.top, cardBox.top),
        );
        expect(overlapWidth * overlapHeight).toBe(0);
      }
    }
  }
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true);

  // Development-only controls are not part of the product UI.
  await page.addStyleTag({
    content: "nextjs-portal, .tsqd-open-btn { display: none !important; }",
  });
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  await cards.screenshot({
    path: path.join(
      SCREENSHOT_DIR,
      `book-pricing-${testInfo.project.name.toLowerCase().replace(/\s+/g, "-")}.png`,
    ),
  });
});

test("public visa service cards expose only exact all-inclusive PricingTool rows", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/services/visa");

  const cards = page.getByTestId("public-service-price-card");
  await expect(cards).toHaveCount(SERVICES_DATA.visa.packages.length);
  const rendered = await cards.evaluateAll((elements) =>
    elements.map((element) => ({
      category: element.getAttribute("data-pricing-category"),
      key: element.getAttribute("data-pricing-key"),
      text: element.textContent ?? "",
    })),
  );
  for (const card of rendered) {
    expect(card.category).toBeTruthy();
    expect(card.key).toBeTruthy();
    const exactPrice = getExactSnapshotPrice(
      card.category as string,
      card.key as string,
    );
    expect(exactPrice).not.toBeNull();
    expect(card.text).toContain(exactPrice as string);
    expect(card.text).not.toMatch(/Extension:\s*\d|Urgent\s*\+\s*\d/i);
  }
});
