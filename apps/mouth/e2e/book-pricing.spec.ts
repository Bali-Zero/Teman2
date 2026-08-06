import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

import { getExactSnapshotPrice } from "../src/lib/pricing-snapshot";

const SCREENSHOT_DIR = path.resolve(
  process.cwd(),
  "../../docs/audits/screenshots/visa-oracle-v2",
);

test("book visa cards use exact PricingTool identities without overflow", async ({
  page,
}, testInfo) => {
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
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true);

  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  await cards.screenshot({
    path: path.join(
      SCREENSHOT_DIR,
      `book-pricing-${testInfo.project.name.toLowerCase().replace(/\s+/g, "-")}.png`,
    ),
  });
});
