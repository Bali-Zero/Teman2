import {
  expect,
  test,
  type BrowserContext,
  type Page,
  type Route,
} from "@playwright/test";

const profileData = {
  id: 321,
  full_name: "Ari Test Client",
  email: "client@example.test",
  phone: "+628000000000",
  whatsapp: "+628000000000",
  nationality: "Italy",
  passport_number: "YA0000000",
  passport_expiry: "2028-10-12",
  date_of_birth: "1987-07-01",
  gender: "M",
  address: "Canggu, Bali",
  member_since: "2026-01-15",
  assigned_to: {
    name: "Bali Zero Team",
    email: "team@balizero.com",
    avatar_url: null,
  },
};

const dashboardSummary = {
  open_actions: [
    {
      id: 501,
      title: "Upload passport renewal scan",
      type: "visa",
      pending_from_client: "Passport renewal scan",
      status: "waiting_documents",
    },
  ],
  upcoming_deadlines: [
    {
      id: "visa-expiry",
      label: "KITAS renewal decision",
      due_date: "2026-08-18",
      kind: "immigration",
    },
  ],
  unread_messages: 2,
  recap: {
    text: "Since your last visit: your KITAS renewal is waiting on one passport scan; tax status remains clear.",
    polished: false,
    disclaimer: "Operational snapshot, not legal advice.",
  },
};

const dashboardData = {
  visa: {
    status: "warning",
    type: "Investor KITAS",
    expiryDate: "2026-08-18",
    daysRemaining: 54,
  },
  company: {
    status: "active",
    primaryCompanyName: "PT Bali Zero Demo",
    totalCompanies: 1,
  },
  taxes: {
    status: "attention",
    nextDeadline: "2026-07-20",
    daysToDeadline: 25,
  },
  documents: {
    total: 3,
    pending: 1,
  },
  messages: {
    unread: 2,
  },
  actions: [
    {
      id: "upload-passport",
      title: "Passport renewal scan needed",
      description:
        "Upload the latest passport scan to keep the KITAS renewal moving.",
      priority: "high",
      type: "document",
      href: "/portal/process",
    },
  ],
};

const requiredDocuments = [
  {
    id: 901,
    practice_id: 501,
    process_name: "Investor KITAS Renewal",
    process_status: "waiting_documents",
    document_type: "passport",
    document_label: "Passport renewal scan",
    description: "Latest passport scan with at least 18 months validity.",
    is_required: true,
    uploaded_by_client: false,
    status: "pending",
    client_notes: null,
    team_member_notes: "Please upload the renewed passport scan.",
  },
  {
    id: 902,
    practice_id: 501,
    process_name: "Investor KITAS Renewal",
    process_status: "waiting_documents",
    document_type: "photo",
    document_label: "Recent passport photo",
    description: "White background digital photo.",
    is_required: true,
    uploaded_by_client: true,
    status: "verified",
    client_notes: null,
    team_member_notes: null,
  },
];

const vaultFiles = [
  {
    id: 77,
    type: "passport",
    name: "passport-renewal.pdf",
    status: "verified",
    expiry_date: "2028-10-12",
    size_kb: 240,
    practice_id: 501,
    practice_name: "Investor KITAS Renewal",
    downloadable: true,
    created_at: "2026-06-20T09:00:00Z",
    purpose: "Identity evidence for KITAS renewal.",
  },
];

const companyDetail = {
  id: 42,
  name: "PT Bali Zero Demo",
  type: "PT PMA",
  status: "active",
  isPrimary: true,
  address: "Canggu, Bali",
  nib: "0000000000001",
  npwp: "00.000.000.0-000.000",
  kbli: "70209",
  akta_pendirian_no: "01",
  akta_pendirian_date: "2026-01-10",
  directors: ["Kaiser Test"],
  shareholders: [{ name: "Kaiser Test", pct: 100 }],
  compliance: [
    {
      id: "lkpm-q2",
      name: "LKPM Q2",
      dueDate: "2026-07-20",
      status: "upcoming",
    },
  ],
};

const taxOverview = {
  summary: {
    status: "attention",
    totalDue: 0,
    nextDeadline: "2026-07-20",
    daysToDeadline: 25,
    pendingCount: 1,
    overdueCount: 0,
  },
  obligations: [
    {
      id: "tax-1",
      name: "Monthly tax review",
      type: "PPh",
      period: "June 2026",
      dueDate: "2026-07-20",
      status: "pending",
      amount: 0,
    },
  ],
};

const billingData = {
  summary: {
    total_invoiced: 12500000,
    total_paid: 7500000,
    total_pending: 5000000,
    count: 1,
  },
  invoices: [
    {
      id: 801,
      invoice_number: "BZ-INV-2026-001",
      amount_idr: 5000000,
      invoice_source: "portal",
      has_pdf: false,
      drive_web_link: null,
      email_sent: true,
      generated_at: "2026-06-20T09:00:00Z",
      created_at: "2026-06-20T09:00:00Z",
      practice_id: 501,
      practice_name: "Investor KITAS Renewal",
      practice_category: "visa",
      payment_status: "pending",
    },
  ],
};

const lkpmHistory = [
  {
    id: 701,
    quarter: "Q2",
    year: 2026,
    status: "client_review",
    realized_total: 350000000,
    oss_submitted: false,
    oss_receipt_number: null,
    client_approved: false,
    lkpm_assigned_to: "Bali Zero Team",
    days_to_deadline: 25,
    created_at: "2026-06-01T09:00:00Z",
    updated_at: "2026-06-24T09:00:00Z",
  },
];

const lkpmDeadlines = [
  {
    quarter: "Q2",
    year: 2026,
    deadline: "2026-07-20",
    days_remaining: 25,
    is_overdue: false,
  },
];

const familyData = {
  adults: [
    {
      id: 1,
      full_name: "Kaiser Test",
      relationship: "Self",
      date_of_birth: "1987-07-01",
      is_adult: true,
      nationality: "Italy",
      passport_number: "YA0000000",
      passport_expiry: "2028-10-12",
      visa_type: "Investor KITAS",
      visa_expiry: "2026-08-18",
      email: "client@example.test",
      phone: "+628000000000",
    },
  ],
  minors: [],
};

const articles = [
  {
    id: "article-kitas-renewal",
    slug: "kitas-renewal-checklist",
    category: "visas",
    title: "KITAS renewal checklist for Bali residents",
    excerpt: "The practical checks before a renewal deadline.",
    date: "2026-06-20",
    readingTime: 4,
  },
  {
    id: "article-lkpm",
    slug: "lkpm-quarterly-filing",
    category: "taxes",
    title: "LKPM quarterly filing checkpoints",
    excerpt: "What PMA shareholders should prepare before reporting.",
    date: "2026-06-18",
    readingTime: 3,
  },
];

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function seedClientSession(context: BrowserContext) {
  await context.addInitScript(() => {
    window.localStorage.setItem("auth_token", "portal-e2e-token");
    window.localStorage.setItem(
      "user_profile",
      JSON.stringify({
        id: "portal-e2e-client",
        name: "Ari Test Client",
        email: "client@example.test",
        role: "client",
      }),
    );
  });
}

async function mockPortalApi(
  context: BrowserContext,
  unhandledApiCalls: string[],
) {
  await context.route(/.*\/api\/.*/, async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path === "/api/portal/profile") {
      return json(route, { success: true, data: profileData });
    }

    if (path === "/api/auth/profile") {
      return json(route, {
        id: "portal-e2e-client",
        name: profileData.full_name,
        email: profileData.email,
        role: "client",
      });
    }

    if (path === "/api/analytics/funnel-event") {
      return json(route, { success: true });
    }

    if (path === "/api/portal/admin/me") {
      return json(route, { is_superuser: false });
    }

    if (path === "/api/portal/dashboard/summary") {
      return json(route, dashboardSummary);
    }

    if (path === "/api/portal/dashboard") {
      return json(route, { success: true, data: dashboardData });
    }

    if (path === "/api/portal/timeline") {
      return json(route, {
        success: true,
        data: {
          scope: "portal",
          entries: [
            {
              id: "tl-1",
              type: "practice",
              occurredAt: "2026-06-24T09:30:00Z",
              title: "KITAS renewal moved to waiting documents",
              description: "Bali Zero is waiting for one client upload.",
              status: "waiting_documents",
              entity: { practiceId: 501, practiceCategory: "visa" },
            },
          ],
          lastUpdated: Date.now(),
        },
      });
    }

    if (path === "/api/portal/visa") {
      return json(route, {
        success: true,
        data: {
          current: {
            visa_type: "Investor KITAS",
            status: "warning",
            issue_date: "2025-08-18",
            expiry_date: "2026-08-18",
            days_remaining: 54,
            visa_number: "ITAS-TEST",
            sponsor_name: "PT Bali Zero Demo",
          },
          history: [],
          documents: [],
        },
      });
    }

    if (path === "/api/portal/process/required-documents") {
      return json(route, { success: true, data: requiredDocuments });
    }

    if (path === "/api/portal/process/501/timeline") {
      return json(route, {
        success: true,
        data: {
          practice_id: 501,
          practice_name: "Investor KITAS Renewal",
          practice_category: "visa",
          current_status: "waiting_documents",
          assigned_to: "Bali Zero Team",
          start_date: "2026-06-01",
          completion_date: null,
          expiry_date: "2026-08-18",
          steps: [
            {
              status: "in_progress",
              label: "Case opened",
              completed: true,
              is_current: false,
              changed_at: "2026-06-01T09:00:00Z",
              changed_by: "Bali Zero Team",
            },
            {
              status: "waiting_documents",
              label: "Waiting for Documents",
              completed: false,
              is_current: true,
              changed_at: "2026-06-24T09:30:00Z",
              changed_by: "Bali Zero Team",
            },
          ],
        },
      });
    }

    if (path === "/api/portal/documents") {
      return json(route, { success: true, data: vaultFiles });
    }

    if (path === "/api/portal/matters") {
      return json(route, {
        matters: [
          {
            id: 101,
            title: "Investor KITAS Renewal",
            type: "visa",
            progress: 66,
            pending_docs: ["Passport renewal scan"],
            next_deadline: "2026-08-18",
            next_step: "Upload passport scan",
          },
        ],
      });
    }

    if (path === "/api/portal/matters/101") {
      return json(route, {
        matter: {
          id: 101,
          title: "Investor KITAS Renewal",
          type: "visa",
          progress: 66,
          pending_docs: ["Passport renewal scan"],
          next_deadline: "2026-08-18",
          next_step: "Upload passport scan",
          status_label: "Waiting for Documents",
          description: "Renewal preparation for the current Investor KITAS.",
          approved_intelligence: {
            available: true,
            status: "approved",
            company_name: "PT Bali Zero Demo",
            summary: "Approved operational context for this renewal.",
            last_reviewed_at: "2026-06-20T09:00:00Z",
            facts: [],
            missing_items: [],
            next_steps: ["Upload passport scan"],
          },
        },
      });
    }

    if (path === "/api/portal/messages") {
      return json(route, {
        success: true,
        data: {
          messages: [
            {
              id: "m-1",
              content: "Please upload the renewed passport scan.",
              direction: "team_to_client",
              sentBy: "Bali Zero Team",
              subject: "KITAS renewal document",
              practiceId: 501,
              practiceName: "Investor KITAS Renewal",
              createdAt: "2026-06-24T10:00:00Z",
            },
          ],
          total: 1,
          unreadCount: 2,
        },
      });
    }

    if (/^\/api\/portal\/messages\/[^/]+\/read$/.test(path)) {
      return json(route, { success: true, data: null });
    }

    if (path === "/api/portal/notifications") {
      return json(route, {
        success: true,
        data: {
          notifications: [
            {
              id: 1,
              type: "deadline_approaching",
              title: "KITAS renewal decision is upcoming",
              body: "Review your next deadline.",
              data: null,
              read: false,
              created_at: "2026-06-24T09:30:00Z",
            },
          ],
          unread_count: 1,
        },
      });
    }

    if (path === "/api/portal/settings") {
      return json(route, {
        success: true,
        data: {
          emailNotifications: true,
          whatsappNotifications: true,
          language: "en",
          timezone: "Asia/Makassar",
        },
      });
    }

    if (path === "/api/portal/notifications/prefs") {
      return json(route, {
        success: true,
        prefs: {
          email_enabled: true,
          whatsapp_enabled: true,
          deadline_days: [7, 30],
        },
      });
    }

    if (path === "/api/portal/companies") {
      return json(route, {
        success: true,
        data: [
          {
            id: 11,
            company_id: 42,
            name: "PT Bali Zero Demo",
            type: "PT PMA",
            status: "active",
            isPrimary: true,
            nib: "0000000000001",
            npwp: "00.000.000.0-000.000",
            kbli: "70209",
            compliance: [
              {
                id: "lkpm-q2",
                name: "LKPM Q2",
                dueDate: "2026-07-20",
                status: "upcoming",
              },
            ],
          },
        ],
      });
    }

    if (path === "/api/portal/company/42") {
      return json(route, { success: true, data: companyDetail });
    }

    if (path === "/api/portal/taxes") {
      return json(route, { success: true, data: taxOverview });
    }

    if (path === "/api/portal/billing") {
      return json(route, { success: true, data: billingData });
    }

    if (path === "/api/portal/family") {
      return json(route, familyData);
    }

    if (path === "/api/v1/lkpm/history/me") {
      return json(route, { success: true, items: lkpmHistory });
    }

    if (path === "/api/v1/lkpm/deadlines") {
      return json(route, { success: true, deadlines: lkpmDeadlines });
    }

    if (path === "/api/v1/lkpm/receipts/me") {
      return json(route, { success: true, items: [] });
    }

    if (path === "/api/blog/articles") {
      return json(route, { articles });
    }

    unhandledApiCalls.push(`${route.request().method()} ${path}`);
    return json(
      route,
      { success: false, error: `Unhandled test API route: ${path}` },
      404,
    );
  });
}

function collectBrowserErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (
      /favicon|Failed to load resource: the server responded with a status of 404/i.test(
        text,
      )
    ) {
      return;
    }
    errors.push(text);
  });
  return errors;
}

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return doc.scrollWidth - doc.clientWidth;
  });
  expect(overflow).toBeLessThanOrEqual(1);
}

test.describe("portal client ready smoke", () => {
  test.beforeEach(async ({ context }) => {
    await seedClientSession(context);
  });

  test("dashboard is matter-first and company card opens companies", async ({
    context,
    page,
  }) => {
    const errors = collectBrowserErrors(page);
    const unhandledApiCalls: string[] = [];
    await mockPortalApi(context, unhandledApiCalls);

    await page.goto("/portal");

    await expect(
      page.getByRole("heading", { name: "Welcome Back" }),
    ).toBeVisible();
    await expect(page.getByText("Upload passport renewal scan")).toBeVisible();
    await expect(page.getByText("KITAS renewal decision")).toBeVisible();
    await expect(page.getByText("Passport renewal scan needed")).toBeVisible();

    await page
      .locator("button")
      .filter({ hasText: "PT Bali Zero Demo" })
      .click();
    await page.waitForURL("**/portal/companies");
    await expect(
      page.getByRole("heading", { name: "Your Companies" }),
    ).toBeVisible();
    await expect(page.getByText("PT Bali Zero Demo")).toBeVisible();

    await assertNoHorizontalOverflow(page);
    expect(unhandledApiCalls).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("overview combines bureaucracy recap with Bali Zero Dispatch", async ({
    context,
    page,
  }) => {
    const errors = collectBrowserErrors(page);
    const unhandledApiCalls: string[] = [];
    await mockPortalApi(context, unhandledApiCalls);

    await page.goto("/portal/dashboard");

    await expect(
      page.getByRole("heading", { name: "My Overview" }),
    ).toBeVisible();
    await expect(
      page.getByRole("main").getByText("Ari Test Client"),
    ).toBeVisible();
    await expect(page.getByText(/Since your last visit/)).toBeVisible();
    await expect(page.getByLabel("The Bali Zero Dispatch")).toBeVisible();
    await expect(
      page.getByRole("link", { name: /KITAS renewal checklist/i }),
    ).toHaveAttribute(
      "href",
      "https://balizero.com/visas/kitas-renewal-checklist",
    );

    await assertNoHorizontalOverflow(page);
    expect(unhandledApiCalls).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("process page makes the client's next document action explicit", async ({
    context,
    page,
  }) => {
    const errors = collectBrowserErrors(page);
    const unhandledApiCalls: string[] = [];
    await mockPortalApi(context, unhandledApiCalls);

    await page.goto("/portal/process");

    await expect(
      page.getByRole("heading", { name: "My Processes" }),
    ).toBeVisible();
    await expect(
      page.getByText("Active Processes", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Documents Required").first()).toBeVisible();
    await expect(page.getByText("Investor KITAS Renewal")).toBeVisible();
    await expect(
      page.getByText("Passport renewal scan", { exact: true }).last(),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Upload/ }).first(),
    ).toBeVisible();

    await assertNoHorizontalOverflow(page);
    expect(unhandledApiCalls).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("vault exposes client documents with search", async ({
    context,
    page,
  }) => {
    const errors = collectBrowserErrors(page);
    const unhandledApiCalls: string[] = [];
    await mockPortalApi(context, unhandledApiCalls);

    await page.goto("/portal/vault");

    await expect(
      page.getByRole("heading", { name: "Document Vault" }),
    ).toBeVisible();
    await expect(page.getByText("passport-renewal.pdf")).toBeVisible();
    await expect(
      page.getByText("Identity evidence for KITAS renewal."),
    ).toBeVisible();

    await page
      .getByRole("searchbox", { name: "Search vault files" })
      .fill("passport");
    await expect(page.getByText("passport-renewal.pdf")).toBeVisible();

    await assertNoHorizontalOverflow(page);
    expect(unhandledApiCalls).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("all primary portal sections render without runtime errors", async ({
    context,
    page,
  }) => {
    test.setTimeout(120_000);

    const errors = collectBrowserErrors(page);
    const unhandledApiCalls: string[] = [];
    await mockPortalApi(context, unhandledApiCalls);

    const sections = [
      { path: "/portal", text: "Welcome Back" },
      { path: "/portal/dashboard", text: "My Overview" },
      { path: "/portal/matters", text: "Your matters" },
      { path: "/portal/matters/101", text: "Investor KITAS Renewal" },
      { path: "/portal/process", text: "My Processes" },
      { path: "/portal/vault", text: "Document Vault" },
      { path: "/portal/messages", text: "Messages" },
      { path: "/portal/chat", text: "Messages" },
      { path: "/portal/companies", text: "Your Companies" },
      { path: "/portal/company/42", text: "PT Bali Zero Demo" },
      { path: "/portal/visa", text: "Immigration Status" },
      { path: "/portal/taxes", text: "Tax Overview" },
      { path: "/portal/lkpm", text: "LKPM Reports" },
      { path: "/portal/billing", text: "Billing" },
      { path: "/portal/family", text: "Family" },
      { path: "/portal/profile", text: "Your Profile" },
      { path: "/portal/settings", text: "Settings" },
    ];

    for (const section of sections) {
      await test.step(section.path, async () => {
        await page.goto(section.path);
        await expect(
          page.getByRole("main").getByText(section.text).first(),
        ).toBeVisible();
        await assertNoHorizontalOverflow(page);
      });
    }

    expect(unhandledApiCalls).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("mobile portal keeps primary client navigation visible", async ({
    context,
    page,
  }) => {
    const errors = collectBrowserErrors(page);
    const unhandledApiCalls: string[] = [];
    await page.setViewportSize({ width: 390, height: 844 });
    await mockPortalApi(context, unhandledApiCalls);

    await page.goto("/portal");

    await expect(page.getByRole("link", { name: "Home" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Vault" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Chat" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Profile" })).toBeVisible();
    await expect(page.getByText("Upload passport renewal scan")).toBeVisible();

    await assertNoHorizontalOverflow(page);
    expect(unhandledApiCalls).toEqual([]);
    expect(errors).toEqual([]);
  });
});
