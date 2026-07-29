import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const E2E_PORT = process.env.BZ_E2E_PORT ?? "3000";
const KITA_ORIGIN = `http://kita.localhost:${E2E_PORT}`;
const MY_ORIGIN = `http://my.localhost:${E2E_PORT}`;
const GALLERY_DIR = resolve(
  process.cwd(),
  "../..",
  "output/playwright/bz-product-family-draft",
);

const syntheticProfile = {
  id: "visual-review-user",
  email: "reviewer@example.test",
  name: "Bali Zero Review",
  role: "admin",
  team: "Operations",
};

const syntheticClients = [
  {
    id: 101,
    full_name: "Ayu Sample",
    email: "ayu@example.test",
    status: "active",
    nationality: "Indonesia",
    assigned_to: "Team Alpha",
    passport_number: "SYNTHETIC-101",
    passport_expiry: "2027-08-12",
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-07-28T00:00:00Z",
  },
  {
    id: 102,
    full_name: "Marco Sample",
    email: "marco@example.test",
    status: "lead",
    nationality: "Italy",
    assigned_to: "Team Beta",
    passport_number: "SYNTHETIC-102",
    passport_expiry: "2026-10-24",
    created_at: "2026-06-12T00:00:00Z",
    updated_at: "2026-07-27T00:00:00Z",
  },
  {
    id: 103,
    full_name: "Noor Sample",
    email: "noor@example.test",
    status: "prospect",
    nationality: "Singapore",
    assigned_to: "Team Alpha",
    passport_number: "SYNTHETIC-103",
    passport_expiry: "2028-02-02",
    created_at: "2026-07-02T00:00:00Z",
    updated_at: "2026-07-26T00:00:00Z",
  },
];

const syntheticPractices = [
  {
    id: 701,
    client_id: 101,
    client_name: "Ayu Sample",
    practice_type_code: "visa",
    practice_type_name: "KITAS Renewal",
    status: "waiting_documents",
    priority: "high",
    payment_status: "paid",
    created_at: "2026-07-10T00:00:00Z",
    updated_at: "2026-07-28T00:00:00Z",
  },
  {
    id: 702,
    client_id: 102,
    client_name: "Marco Sample",
    practice_type_code: "company",
    practice_type_name: "PT PMA Setup",
    status: "waiting_payment",
    priority: "normal",
    payment_status: "unpaid",
    created_at: "2026-07-12T00:00:00Z",
    updated_at: "2026-07-27T00:00:00Z",
  },
  {
    id: 703,
    client_id: 103,
    client_name: "Noor Sample",
    practice_type_code: "tax",
    practice_type_name: "Annual Tax Return",
    status: "in_progress",
    priority: "normal",
    payment_status: "paid",
    created_at: "2026-07-14T00:00:00Z",
    updated_at: "2026-07-29T00:00:00Z",
  },
];

async function seedSyntheticReviewData(page: Page): Promise<void> {
  await page.addInitScript((profile) => {
    localStorage.setItem("auth_token", "synthetic-visual-review-token");
    localStorage.setItem("user_profile", JSON.stringify(profile));
    localStorage.removeItem("bz-theme");
  }, syntheticProfile);

  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const { pathname } = url;
    let body: unknown = {};

    if (pathname === "/api/dashboard/summary") {
      body = {
        user: { email: syntheticProfile.email, role: "admin", is_admin: true },
        stats: {
          activeCases: 18,
          criticalDeadlines: 3,
          pendingInvoices: 4,
          whatsappUnread: 7,
          emailUnread: 2,
          hoursWorked: "6h 20m",
        },
        data: {
          practices: [
            {
              id: 701,
              title: "KITAS Renewal",
              client: "Ayu Sample",
              status: "documents",
              daysRemaining: 2,
            },
            {
              id: 702,
              title: "PT PMA Setup",
              client: "Marco Sample",
              status: "in_progress",
              daysRemaining: 12,
            },
          ],
          interactions: [],
          email: { connected: true, unread_count: 2 },
        },
        system_status: "healthy",
        total_clients: 126,
        total_practices: 18,
        revenue: { total_revenue: 185000000 },
        revenue_growth: 8.4,
        last_updated: Date.now(),
      };
    } else if (pathname === "/api/crm/clients") {
      body = syntheticClients;
    } else if (pathname === "/api/crm/practices") {
      body = syntheticPractices;
    } else if (pathname.includes("/api/crm/clients/stats")) {
      body = {
        total: 126,
        active: 82,
        leads: 19,
        passportExpired: 0,
        passportExpiringSoon: 2,
        silent30d: 4,
      };
    } else if (pathname === "/api/admin/system-health") {
      body = {
        overall_status: "healthy",
        timestamp: "2026-07-29T08:00:00Z",
        checks: {
          Database: {
            name: "Database",
            status: "ok",
            message: "Connected",
            latency_ms: 18,
          },
          Qdrant: {
            name: "Qdrant",
            status: "ok",
            message: "Index ready",
            latency_ms: 24,
          },
          Redis: {
            name: "Redis",
            status: "ok",
            message: "Cache ready",
            latency_ms: 11,
          },
          API: {
            name: "API",
            status: "ok",
            message: "Serving requests",
            latency_ms: 32,
          },
          "CRM Models": {
            name: "CRM Models",
            status: "ok",
            message: "Models loaded",
            latency_ms: null,
          },
          "Collection Manager": {
            name: "Collection Manager",
            status: "warning",
            message: "Sync queued",
            latency_ms: null,
          },
        },
        system_metrics: {},
        service_registry: [],
      };
    } else if (pathname === "/api/compliance/alerts") {
      body = { items: [], limit: 6, offset: 0 };
    } else if (pathname === "/api/admin/team-activity/team-stats") {
      body = {
        team_stats: [
          {
            email: "team.alpha@example.test",
            name: "Team Alpha",
            role: "Operations",
            days_worked: 18,
            crm_actions: 64,
          },
          {
            email: "team.beta@example.test",
            name: "Team Beta",
            role: "Client Services",
            days_worked: 16,
            crm_actions: 48,
          },
        ],
      };
    } else if (pathname === "/api/admin/team-activity/overview") {
      body = { active_today: 2 };
    } else if (pathname === "/api/admin/team-activity/practice-stats") {
      body = {
        practice_stats: [
          {
            email: "team.alpha@example.test",
            completed: 12,
            active: 7,
            revenue: 92000000,
          },
          {
            email: "team.beta@example.test",
            completed: 9,
            active: 5,
            revenue: 71000000,
          },
        ],
      };
    } else if (pathname.includes("assignee") || pathname.includes("team")) {
      body = [];
    } else if (pathname === "/api/portal/dashboard") {
      body = {
        data: {
          visa: {
            status: "active",
            type: "Investor KITAS",
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
          documents: { total: 14, pending: 2 },
          messages: { unread: 3 },
          actions: [],
        },
      };
    } else if (pathname === "/api/portal/dashboard/summary") {
      body = {
        open_actions: [],
        upcoming_deadlines: [],
        unread_messages: 3,
      };
    } else if (pathname === "/api/portal/timeline") {
      body = { data: { entries: [], total: 0 } };
    } else if (pathname === "/api/portal/messages") {
      body = { data: { messages: [], total: 0, unreadCount: 0 } };
    } else if (pathname === "/api/portal/documents") {
      body = { success: true, data: [] };
    } else if (pathname === "/api/portal/notifications") {
      body = { data: { notifications: [], unread_count: 0 } };
    } else if (pathname.includes("/api/blog")) {
      body = pathname.includes("homepage-hero")
        ? { articles: [] }
        : { articles: [] };
    }

    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

async function capture(
  page: Page,
  url: string,
  fileName: string,
): Promise<void> {
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await expect(page.locator("body")).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(1_200);
  await page.screenshot({
    path: resolve(GALLERY_DIR, fileName),
    fullPage: true,
  });
}

test.describe("Bali Zero product-family visual gallery", () => {
  test.skip(
    !process.env.BZ_VISUAL_GALLERY,
    "Run only for design-review output",
  );
  test.setTimeout(240_000);

  test.beforeAll(() => mkdirSync(GALLERY_DIR, { recursive: true }));

  test("captures the definitive day-first draft", async ({ page }) => {
    await seedSyntheticReviewData(page);

    await page.setViewportSize({ width: 1440, height: 960 });
    await capture(page, `${KITA_ORIGIN}/dashboard`, "01-kita-dashboard.png");
    await capture(page, `${KITA_ORIGIN}/clients`, "02-kita-clients.png");
    await capture(page, `${KITA_ORIGIN}/process`, "03-kita-process.png");
    await capture(page, `${MY_ORIGIN}/portal`, "04-my-home.png");
    await capture(page, `${MY_ORIGIN}/portal/messages`, "05-my-messages.png");
    await capture(page, `${MY_ORIGIN}/portal/vault`, "06-my-vault.png");

    await page.setViewportSize({ width: 390, height: 844 });
    await capture(page, `${KITA_ORIGIN}/process`, "07-kita-process-mobile.png");
    await capture(page, `${MY_ORIGIN}/portal`, "08-my-home-mobile.png");
  });
});
