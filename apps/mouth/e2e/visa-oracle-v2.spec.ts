/**
 * E2E scenarios for Visa Oracle v2 (TRACK C PR1 "Oracle Experience
 * Foundation"). Modeled on `visa-funnel-fusion.spec.ts` — getByRole-driven,
 * runs against the base URL configured in playwright.config.ts.
 *
 * CI runs `--grep "page Page"`; the describe block below carries that
 * literal string on purpose.
 */
import { expect, test } from "@playwright/test";

test.describe("Visa Oracle v2 — page Page", () => {
  test("happy path: framing → offshore tourism → verdict with a supported candidate", async ({
    page,
  }) => {
    await page.goto("/visa-oracle");

    await expect(
      page.getByRole("heading", { name: /a map, not an application/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /^start$/i }).click();

    await expect(
      page.getByRole("heading", { name: /are you in indonesia right now/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /no, i.m planning ahead/i }).click();

    await expect(
      page.getByRole("heading", { name: /what brings you to indonesia/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /tourism & short visit/i }).click();

    await expect(
      page.getByRole("heading", { name: /how long are you planning to stay/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /up to 30 days/i }).click();

    await expect(
      page.getByRole("heading", { name: /honest questions/i }),
    ).toBeVisible();
    // Finding #5 (adversarial review 2026-07-17): Continue is disabled
    // until an explicit checklist choice is made — the old test relied on
    // the removed "press Continue with nothing checked = none" default.
    await page
      .getByRole("checkbox", { name: /none of these apply to me/i })
      .check();
    await page.getByRole("button", { name: /see my options/i }).click();

    await expect(
      page.getByRole("heading", { name: /here.s what you told us/i }),
    ).toBeVisible();
    // Finding #12: the confirmation ("honesty receipt") heading receives
    // focus on mount, same as every question screen and the verdict card.
    await expect(
      page.getByRole("heading", { name: /here.s what you told us/i }),
    ).toBeFocused();
    await page.getByRole("button", { name: /see my options/i }).click();

    await expect(
      page.getByRole("heading", { name: /strongest fit/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: /continue on whatsapp/i }),
    ).toBeVisible();
  });

  test("back link restores the previous question, and re-answering down a different branch drops stale facts from the abandoned branch (finding #1)", async ({
    page,
  }) => {
    await page.goto("/visa-oracle");
    await page.getByRole("button", { name: /^start$/i }).click();
    await page.getByRole("button", { name: /no, i.m planning ahead/i }).click();
    await expect(
      page.getByRole("heading", { name: /what brings you to indonesia/i }),
    ).toBeVisible();

    await page.getByRole("button", { name: /^back$/i }).click();
    await expect(
      page.getByRole("heading", { name: /are you in indonesia right now/i }),
    ).toBeVisible();

    // Proceed down the "work" branch far enough to answer work_payer.
    await page.getByRole("button", { name: /no, i.m planning ahead/i }).click();
    await page.getByRole("button", { name: /work & employment/i }).click();
    await expect(
      page.getByRole("heading", {
        name: /will an indonesian-registered company/i,
      }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: /yes, an indonesian entity pays me/i })
      .click();
    await expect(
      page.getByRole("heading", { name: /honest questions/i }),
    ).toBeVisible();

    // Back past review_gate, back past work_payer, back to category —
    // then take a DIFFERENT branch that never asks work_payer.
    await page.getByRole("button", { name: /^back$/i }).click();
    await expect(
      page.getByRole("heading", {
        name: /will an indonesian-registered company/i,
      }),
    ).toBeVisible();
    await page.getByRole("button", { name: /^back$/i }).click();
    await expect(
      page.getByRole("heading", { name: /what brings you to indonesia/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /tourism & short visit/i }).click();
    await expect(
      page.getByRole("heading", { name: /how long are you planning to stay/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /up to 30 days/i }).click();
    await expect(
      page.getByRole("heading", { name: /honest questions/i }),
    ).toBeVisible();
    await page
      .getByRole("checkbox", { name: /none of these apply to me/i })
      .check();
    await page.getByRole("button", { name: /see my options/i }).click();

    // The confirmation screen shows the NEW branch's answer, and never
    // shows the abandoned branch's work_payer question — proof the stale
    // fact was pruned, not just visually skipped (finding #1). Scoped to
    // the answers group specifically — the living tree's category leaf
    // renders the same label text elsewhere on the page.
    await expect(
      page.getByRole("heading", { name: /here.s what you told us/i }),
    ).toBeVisible();
    const answersGroup = page.locator(".oracle-confirmation__group").first();
    await expect(
      answersGroup.getByText(/tourism & short visit/i),
    ).toBeVisible();
    await expect(
      page.getByText(/will an indonesian-registered company/i),
    ).toHaveCount(0);
  });

  test("not-sure on the work payer question routes to human review, never a guess", async ({
    page,
  }) => {
    await page.goto("/visa-oracle");
    await page.getByRole("button", { name: /^start$/i }).click();
    await page.getByRole("button", { name: /no, i.m planning ahead/i }).click();
    await page.getByRole("button", { name: /work & employment/i }).click();

    await expect(
      page.getByRole("heading", {
        name: /will an indonesian-registered company/i,
      }),
    ).toBeVisible();
    await page.getByRole("button", { name: /not sure/i }).click();

    await expect(
      page.getByRole("heading", { name: /honest questions/i }),
    ).toBeVisible();
    await page
      .getByRole("checkbox", { name: /none of these apply to me/i })
      .check();
    await page.getByRole("button", { name: /see my options/i }).click();
    await page.getByRole("button", { name: /see my options/i }).click();

    await expect(
      page.getByRole("heading", { name: /needs a human/i }),
    ).toBeVisible();
  });

  test("language toggle switches copy instantly without resetting the interview", async ({
    page,
  }) => {
    await page.goto("/visa-oracle");
    await page.getByRole("button", { name: /^start$/i }).click();
    await page.getByRole("button", { name: /no, i.m planning ahead/i }).click();

    await page.getByRole("button", { name: "Indonesia" }).click();
    await expect(
      page.getByRole("heading", { name: /apa tujuan anda ke indonesia/i }),
    ).toBeVisible();
  });

  test("prototype badge and footer disclaimer are always visible", async ({
    page,
  }) => {
    await page.goto("/visa-oracle");
    await expect(page.getByText(/prototype — sample data/i)).toBeVisible();
    await expect(page.getByText(/ditjen imigrasi decides/i)).toBeVisible();
  });
});
