import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const E2E_PORT = process.env.BZ_E2E_PORT ?? "3000";
const KITA_ORIGIN = `http://kita.localhost:${E2E_PORT}`;
const MY_ORIGIN = `http://my.localhost:${E2E_PORT}`;

const syntheticPortalProfile = {
  id: "ui-test-client",
  email: "client@example.test",
  name: "Portal Test",
  role: "admin",
};

async function seedSyntheticPortalSession(page: Page): Promise<void> {
  await page.addInitScript((profile) => {
    localStorage.setItem("auth_token", "synthetic-ui-test-token");
    localStorage.setItem("user_profile", JSON.stringify(profile));
  }, syntheticPortalProfile);

  await page.route("**/api/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;

    if (pathname === "/api/dashboard/summary") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          user: { email: syntheticPortalProfile.email, role: "admin" },
          stats: {},
          data: { practices: [], interactions: [] },
          system_status: "healthy",
          total_clients: 0,
          total_practices: 0,
        }),
      });
      return;
    }

    if (pathname === "/api/portal/dashboard") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            visa: {
              status: "active",
              type: "Sample KITAS",
              expiryDate: "2027-04-18",
              daysRemaining: 263,
            },
            company: {
              status: "active",
              primaryCompanyName: "Sample Indonesia PT",
              totalCompanies: 1,
            },
            taxes: {
              status: "compliant",
              nextDeadline: "2026-09-30",
              daysToDeadline: 63,
            },
            documents: { total: 3, pending: 0 },
            messages: { unread: 0 },
            actions: [],
          },
        }),
      });
      return;
    }

    if (pathname === "/api/portal/dashboard/summary") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          activePractices: 1,
          pendingDocuments: 0,
          unreadMessages: 0,
        }),
      });
      return;
    }

    if (pathname === "/api/portal/messages") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          data: { messages: [], total: 0, unreadCount: 0 },
        }),
      });
      return;
    }

    if (pathname === "/api/portal/notifications") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          data: { notifications: [], unread_count: 0 },
        }),
      });
      return;
    }

    if (pathname === "/api/team/members") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify([]),
      });
      return;
    }

    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: {} }),
    });
  });
}

async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
}

async function expectNoBlockingA11y(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blocking = results.violations.filter(
    (violation) =>
      violation.impact === "serious" || violation.impact === "critical",
  );

  expect(
    blocking.map(({ id, impact, help, nodes }) => ({
      id,
      impact,
      help,
      nodes: nodes.map(({ target, html, failureSummary }) => ({
        target,
        html,
        failureSummary,
      })),
    })),
  ).toEqual([]);
}

const syntheticPractice = {
  id: 707,
  client_id: 17,
  client_name: "UI Contract",
  practice_type_code: "visa",
  practice_type_name: "Visa Extension",
  status: "waiting_payment",
  priority: "normal",
  payment_status: "unpaid",
  created_at: "2026-01-01T00:00:00.000Z",
  updated_at: "2026-01-02T00:00:00.000Z",
};

const syntheticUnknownPractice = {
  ...syntheticPractice,
  id: 708,
  status: "legacy_manual_review",
};

async function seedSyntheticProcessBoard(page: Page): Promise<void> {
  await seedSyntheticPortalSession(page);
  await page.route("**/api/crm/practices**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([syntheticPractice, syntheticUnknownPractice]),
    });
  });
}

test.describe("Bali Zero product-family shells page Page", () => {
  test("Kita mobile shell stays within the viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await seedSyntheticPortalSession(page);

    await page.goto(`${KITA_ORIGIN}/dashboard`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.locator("#bz-page-title")).toBeVisible({
      timeout: 30000,
    });

    await expectNoHorizontalOverflow(page);
    await expectNoBlockingA11y(page);
  });

  test("Kita desktop shell shows the canonical Bali Zero logo", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 960 });
    await seedSyntheticPortalSession(page);

    await page.goto(`${KITA_ORIGIN}/dashboard`, {
      waitUntil: "domcontentloaded",
    });
    const logo = page
      .getByRole("link", { name: "Bali Zero — workspace home" })
      .locator("img");

    await expect(logo).toBeVisible({ timeout: 30000 });
    await expect(logo).toHaveAttribute("src", /balizero-logo-clean\.png/);
    await expectNoBlockingA11y(page);
  });

  test("Process keeps a horizontally scannable board and keyboard-accessible cards on mobile", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await seedSyntheticProcessBoard(page);

    await page.goto(`${KITA_ORIGIN}/process`, {
      waitUntil: "domcontentloaded",
    });

    const board = page.getByLabel("Process board");
    const card = page.getByRole("button", {
      name: "Open process 707: Visa Extension",
    });
    const cardSurface = page.getByTestId("process-card-707");

    await expect(board).toBeVisible({ timeout: 30000 });
    await expect(card).toBeVisible();
    await card.focus();
    await expect(card).toBeFocused();
    await expectNoHorizontalOverflow(page);
    await expect(cardSurface).toContainText("Waiting Payment");
    await expect(page.getByTestId("process-card-708")).toContainText(
      "Needs review · Legacy Manual Review",
    );
    await expectNoBlockingA11y(page);
  });

  test("My mobile shell stays within the viewport and labels Messages canonically", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await seedSyntheticPortalSession(page);

    await page.goto(`${MY_ORIGIN}/portal/messages`, {
      waitUntil: "domcontentloaded",
    });
    const messages = page.getByRole("link", { name: "Messages" });

    await expect(messages).toBeVisible({ timeout: 30000 });
    await expect(messages).toHaveAttribute("href", "/portal/messages");
    await expectNoHorizontalOverflow(page);
    await expectNoBlockingA11y(page);
  });
});
