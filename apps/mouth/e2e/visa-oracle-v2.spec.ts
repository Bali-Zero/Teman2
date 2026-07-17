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

  test("tree tap-to-edit: tapping a completed trunk step jumps back to that question and prunes later facts (interaction #6)", async ({
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
    await page
      .getByRole("button", { name: /yes, an indonesian entity pays me/i })
      .click();
    await expect(
      page.getByRole("heading", { name: /honest questions/i }),
    ).toBeVisible();

    // The living tree's "category" trunk step is now a completed step —
    // a real, accessible `<button>` (not the aria-hidden decorative div
    // every other trunk step renders as). Tapping it dispatches the same
    // EDIT action as the confirmation card's Edit link.
    const editCategory = page.getByRole("button", {
      name: /edit answer: category/i,
    });
    await expect(editCategory).toBeVisible();
    await editCategory.click();
    await expect(
      page.getByRole("heading", { name: /what brings you to indonesia/i }),
    ).toBeVisible();

    // Take a DIFFERENT branch that never asks work_payer, and prove the
    // fact from the abandoned branch was pruned (same technique as the
    // existing Back-navigation test above).
    await page.getByRole("button", { name: /tourism & short visit/i }).click();
    await expect(
      page.getByRole("heading", { name: /how long are you planning to stay/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /up to 30 days/i }).click();
    await page
      .getByRole("checkbox", { name: /none of these apply to me/i })
      .check();
    await page.getByRole("button", { name: /see my options/i }).click();

    await expect(
      page.getByRole("heading", { name: /here.s what you told us/i }),
    ).toBeVisible();
    await expect(
      page.getByText(/will an indonesian-registered company/i),
    ).toHaveCount(0);
  });

  test("tree tap-to-edit: current/pending/framing/confirmation/verdict trunk steps never render as buttons", async ({
    page,
  }) => {
    await page.goto("/visa-oracle");
    await page.getByRole("button", { name: /^start$/i }).click();

    // On the very first question, nothing in the tree has been answered
    // yet — no completed-step edit buttons should exist at all.
    await expect(
      page.getByRole("button", { name: /^edit answer:/i }),
    ).toHaveCount(0);
  });

  test("outcome document checklist items are real, independently toggleable checkboxes (item 4)", async ({
    page,
  }) => {
    await page.goto("/visa-oracle");
    await page.getByRole("button", { name: /^start$/i }).click();
    await page.getByRole("button", { name: /no, i.m planning ahead/i }).click();
    await page.getByRole("button", { name: /tourism & short visit/i }).click();
    await page.getByRole("button", { name: /up to 30 days/i }).click();
    await page
      .getByRole("checkbox", { name: /none of these apply to me/i })
      .check();
    await page.getByRole("button", { name: /see my options/i }).click();
    await page.getByRole("button", { name: /see my options/i }).click();
    await expect(
      page.getByRole("heading", { name: /strongest fit/i }),
    ).toBeVisible();

    const docCheckbox = page.getByRole("checkbox", {
      name: /passport valid 6\+ months/i,
    });
    await expect(docCheckbox).toBeVisible();
    await expect(docCheckbox).not.toBeChecked();
    await docCheckbox.check();
    await expect(docCheckbox).toBeChecked();
    await docCheckbox.uncheck();
    await expect(docCheckbox).not.toBeChecked();
  });

  test("QR handoff is a real, accessible, non-decorative element carrying the WhatsApp link (item 3)", async ({
    page,
  }) => {
    await page.goto("/visa-oracle");
    await page.getByRole("button", { name: /^start$/i }).click();
    await page.getByRole("button", { name: /no, i.m planning ahead/i }).click();
    await page.getByRole("button", { name: /tourism & short visit/i }).click();
    await page.getByRole("button", { name: /up to 30 days/i }).click();
    await page
      .getByRole("checkbox", { name: /none of these apply to me/i })
      .check();
    await page.getByRole("button", { name: /see my options/i }).click();
    await page.getByRole("button", { name: /see my options/i }).click();
    await expect(
      page.getByRole("heading", { name: /strongest fit/i }),
    ).toBeVisible();

    // Real, accessible role="img" with a descriptive aria-label — never
    // aria-hidden, unlike the decorative placeholder it replaced.
    const qr = page.getByRole("img", { name: /qr code/i });
    await expect(qr).toBeVisible();
    await expect(qr).not.toHaveAttribute("aria-hidden", "true");

    // The link stays the text alternative right beside it — visible and
    // clickable, encoding the exact same wa.me URL the QR carries.
    const whatsappLink = page.getByRole("link", {
      name: /continue on whatsapp/i,
    });
    await expect(whatsappLink).toBeVisible();
    await expect(whatsappLink).toHaveAttribute("href", /^https:\/\/wa\.me\//);
  });
});
