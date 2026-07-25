import {
  type BrowserContext,
  expect,
  test,
  type Page,
  type Route,
  type TestInfo,
} from "@playwright/test";

type Role = "admin" | "team";

interface RequestAudit {
  systemHealth: number;
  complianceUrls: string[];
}

const profileFor = (role: Role) => ({
  id: `e2e-${role}`,
  email: `${role}@example.test`,
  name: `E2E ${role}`,
  role,
  status: "active",
});

async function seedSession(page: Page, role: Role): Promise<void> {
  await page.addInitScript(
    ({ profile }) => {
      localStorage.setItem("auth_token", "e2e-mock-token");
      localStorage.setItem("user_profile", JSON.stringify(profile));
    },
    { profile: profileFor(role) },
  );
}

function dashboardSummary(role: Role) {
  const profile = profileFor(role);
  return {
    user: {
      email: profile.email,
      role: profile.role,
      is_admin: role === "admin",
    },
    stats: {
      activeCases: 3,
      criticalDeadlines: 1,
      pendingInvoices: 0,
      whatsappUnread: 2,
      emailUnread: 0,
      hoursWorked: "4h 20m",
    },
    data: {
      practices: [],
      interactions: [],
      email: { connected: true, unread_count: 0 },
    },
    system_status: "healthy",
    last_updated: Date.now(),
  };
}

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function stubDashboardApi(
  context: BrowserContext,
  role: Role,
): Promise<RequestAudit> {
  const audit: RequestAudit = { systemHealth: 0, complianceUrls: [] };
  const deadline = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);

  await context.route(
    (url) => url.pathname.startsWith("/api/"),
    async (route) => {
      const url = new URL(route.request().url());

      if (url.pathname === "/api/dashboard/summary") {
        await fulfillJson(route, dashboardSummary(role));
        return;
      }
      if (url.pathname === "/api/intake/gate/status") {
        await fulfillJson(route, {
          blocked: false,
          sections: {
            documents: { count: 0, blocking: false },
            late_note: { count: 0, blocking: false },
            deadlines: { count: 0, blocking: false },
          },
          as_of: new Date().toISOString(),
        });
        return;
      }
      if (url.pathname === "/api/intake/review/queue") {
        await fulfillJson(route, { items: [] });
        return;
      }
      if (url.pathname === "/api/blog/articles") {
        await fulfillJson(route, { articles: [] });
        return;
      }
      if (url.pathname === "/api/admin/system-health") {
        audit.systemHealth += 1;
        await fulfillJson(route, {
          overall_status: "ok",
          timestamp: new Date().toISOString(),
          checks: {
            Database: {
              name: "Database",
              status: "ok",
              message: "Connected",
              latency_ms: 12,
            },
            Qdrant: {
              name: "Qdrant",
              status: "ok",
              message: "Connected",
              latency_ms: 18,
            },
          },
          system_metrics: {},
          service_registry: {},
        });
        return;
      }
      if (url.pathname === "/api/compliance/alerts") {
        audit.complianceUrls.push(url.toString());
        await fulfillJson(route, {
          items: [
            {
              alert_id: `${role}-deadline`,
              client_id: 101,
              category: "renewal_deadline",
              severity: "critical",
              status: "pending",
              deadline,
              days_until: 999,
              message_en: "Test renewal deadline",
              message_it: null,
              suggested_action: null,
            },
          ],
          limit: 6,
          offset: 0,
        });
        return;
      }

      await fulfillJson(route, {});
    },
  );

  return audit;
}

async function captureEvidence(
  page: Page,
  testInfo: TestInfo,
  name: string,
): Promise<void> {
  const path = testInfo.outputPath(`${name}.png`);
  await page.getByTestId("dashboard-ops-panels").screenshot({ path });
  await testInfo.attach(name, { path, contentType: "image/png" });
}

test.describe("dashboard ops panels", () => {
  test.use({ serviceWorkers: "block" });
  test.setTimeout(90_000);

  test("admin sees live System Pulse and active Compliance Radar", async ({
    page,
    context,
  }, testInfo) => {
    await seedSession(page, "admin");
    const audit = await stubDashboardApi(context, "admin");
    await page.setViewportSize({ width: 1440, height: 1000 });

    await page.goto("/dashboard");

    await expect(page.getByText("System Pulse")).toBeVisible();
    await expect(page.getByText("Compliance Radar")).toBeVisible();
    await expect(page.getByText("PostgreSQL")).toBeVisible();
    await expect(page.getByText("Test renewal deadline")).toBeVisible();
    expect(audit.systemHealth).toBe(1);
    expect(audit.complianceUrls).toHaveLength(1);
    expect(audit.complianceUrls[0]).toContain("active_only=true");
    await captureEvidence(page, testInfo, "admin-dashboard-ops");
  });

  test("team member never fetches or renders System Pulse", async ({
    page,
    context,
  }, testInfo) => {
    await seedSession(page, "team");
    const audit = await stubDashboardApi(context, "team");
    await page.setViewportSize({ width: 390, height: 844 });

    await page.goto("/dashboard");

    await expect(page.getByText("Compliance Radar")).toBeVisible();
    await expect(page.getByText("Test renewal deadline")).toBeVisible();
    await expect(page.getByText("System Pulse")).toHaveCount(0);
    expect(audit.systemHealth).toBe(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await captureEvidence(page, testInfo, "team-dashboard-mobile");
  });
});
