import {
  expect,
  test,
  type ConsoleMessage,
  type Page,
  type Response,
  type TestInfo,
} from "@playwright/test";

import {
  classifyPageError,
  isDisallowedNetworkRequest,
  isUnsafeWriteRequest,
  loadProdlikeEnvironment,
} from "./support/prodlike-preflight";

const environment = loadProdlikeEnvironment(process.env);
const SYNTHETIC_PDF = Buffer.from(
  "JVBERi0xLjMKJeLjz9MKMSAwIG9iago8PAovUHJvZHVjZXIgKHB5cGRmKQo+PgplbmRvYmoKMiAwIG9iago8PAovVHlwZSAvUGFnZXMKL0NvdW50IDEKL0tpZHMgWyA0IDAgUiBdCj4+CmVuZG9iagozIDAgb2JqCjw8Ci9UeXBlIC9DYXRhbG9nCi9QYWdlcyAyIDAgUgo+PgplbmRvYmoKNCAwIG9iago8PAovVHlwZSAvUGFnZQovUmVzb3VyY2VzIDw8Cj4+Ci9NZWRpYUJveCBbIDAuMCAwLjAgNzIgNzIgXQovUGFyZW50IDIgMCBSCj4+CmVuZG9iagp4cmVmCjAgNQowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMTUgMDAwMDAgbiAKMDAwMDAwMDA1NCAwMDAwMCBuIAowMDAwMDAwMTEzIDAwMDAwIG4gCjAwMDAwMDAxNjIgMDAwMDAgbiAKdHJhaWxlcgo8PAovU2l6ZSA1Ci9Sb290IDMgMCBSCi9JbmZvIDEgMCBSCj4+CnN0YXJ0eHJlZgoyNTQKJSVFT0YK",
  "base64",
);
const SYNTHETIC_PROFILE_ADDRESS = "Synthetic QA Address";
const SYNTHETIC_TEAM_MESSAGE = "Synthetic QA message from the Bali Zero team";
const SYNTHETIC_NOTIFICATION_TITLE = "Synthetic QA notification";
const SYNTHETIC_COMPANY_NAME = "Synthetic Portal Company";
const SYNTHETIC_INVOICE_NUMBER = "QA-INV-2026-0001";
const SYNTHETIC_ADULT_NAME = "Synthetic Adult Member";
const SYNTHETIC_MINOR_NAME = "Synthetic Minor Member";
const SYNTHETIC_LKPM_RECEIPT_NUMBER = "QA-LKPM-2026-0001";
const SYNTHETIC_MATTER_TITLE = "Synthetic Company Service";
const SYNTHETIC_WA_PHONE = "12025550123";
const SYNTHETIC_PARTNER_NAME = "Synthetic Portal Partner";
const SYNTHETIC_PARTNER_CLIENT_DISPLAY = "Synthetic C.";
const SYNTHETIC_PARTNER_SERVICE = "Visa / KITAS service";

function syntheticProfileSlug(testInfo: TestInfo): string {
  return testInfo.project.name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function syntheticLKPMSubmissionPeriod(testInfo: TestInfo): {
  quarter: "Q1" | "Q2" | "Q3" | "Q4";
  year: number;
  ordinal: number;
} {
  const periods = {
    "chromium-prodlike": { quarter: "Q1", year: 2024, ordinal: 1 },
    "firefox-prodlike": { quarter: "Q2", year: 2024, ordinal: 2 },
    "webkit-prodlike": { quarter: "Q3", year: 2024, ordinal: 3 },
    "mobile-chromium-prodlike": { quarter: "Q4", year: 2024, ordinal: 4 },
  } as const;
  const period = periods[testInfo.project.name as keyof typeof periods];
  if (!period) {
    throw new Error(
      "Prod-like LKPM period is missing for this browser profile",
    );
  }
  return period;
}

function collectSanitizedRuntimeFailures(
  page: Page,
  isExpectedServerFailure: (response: Response) => boolean = () => false,
  isExpectedConsoleError: (message: ConsoleMessage) => boolean = () => false,
): string[] {
  const failures: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error" && !isExpectedConsoleError(message)) {
      failures.push("browser console.error");
    }
  });
  page.on("pageerror", (error) => failures.push(classifyPageError(error)));
  page.on("response", (response) => {
    if (response.status() >= 500 && !isExpectedServerFailure(response)) {
      failures.push("HTTP 5xx response");
    }
  });

  return failures;
}

function collectUnsafeExternalWrites(
  page: Page,
  allowedOrigins: ReadonlySet<string>,
): string[] {
  const failures: string[] = [];
  page.on("request", (request) => {
    if (isUnsafeWriteRequest(request.method(), request.url(), allowedOrigins)) {
      failures.push(`external ${request.method()} request`);
    }
  });
  return failures;
}

function collectDisallowedNetworkRequests(
  page: Page,
  allowedOrigins: ReadonlySet<string>,
): string[] {
  const failures: string[] = [];
  page.on("request", (request) => {
    if (isDisallowedNetworkRequest(request.url(), allowedOrigins)) {
      failures.push("request to a non-QA origin");
    }
  });
  return failures;
}

interface SyntheticSession {
  readonly clientId: number;
  readonly token: string;
}

async function expectDashboardSettled(page: Page): Promise<void> {
  await expect(page).toHaveURL(/\/portal(?:\?.*)?$/);
  await expect(
    page.getByRole("heading", { name: "Welcome Back" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Immigration status" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Company status" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Tax status" })).toBeVisible();
  await expect(page.getByText("Your update", { exact: true })).toBeVisible();
  await expect(
    page.getByText("not legal advice", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("Unable to load dashboard")).toHaveCount(0);
  await expect(page.getByText("Client profile connection needed")).toHaveCount(
    0,
  );
}

async function loginViaPortalUi(
  page: Page,
  email: string,
  pin: string,
): Promise<SyntheticSession> {
  await page.goto("/portal/login-upgraded?redirect=%2Fportal", {
    waitUntil: "domcontentloaded",
  });
  const emailInput = page.getByRole("textbox", { name: "Corporate Email" });
  const emailSubmit = page.getByRole("button", { name: "Pass the Portal" });
  await expect(emailInput).toBeEnabled();
  await emailInput.fill(email);
  await expect(emailSubmit).toBeEnabled();
  await emailSubmit.click();
  await page.getByLabel("Access PIN").fill(pin);
  const loginResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/auth/login" &&
      response.request().method() === "POST"
    );
  });
  await page.getByRole("button", { name: "Verify Identity" }).click();
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.status()).toBe(200);
  const loginBody = (await loginResponse.json()) as {
    data?: {
      token?: unknown;
      user?: { client_id?: unknown };
    };
  };
  if (
    typeof loginBody.data?.token !== "string" ||
    typeof loginBody.data.user?.client_id !== "number"
  ) {
    throw new Error("Synthetic login did not return its session contract");
  }
  await expectDashboardSettled(page);
  return {
    clientId: loginBody.data.user.client_id,
    token: loginBody.data.token,
  };
}

async function loginPartnerViaPortalUi(
  page: Page,
  email: string,
  pin: string,
): Promise<string> {
  // Start with a client-only redirect on purpose: the role contract must win.
  await page.goto("/portal/login-upgraded?redirect=%2Fportal%2Fbilling", {
    waitUntil: "domcontentloaded",
  });
  await page.getByRole("textbox", { name: "Corporate Email" }).fill(email);
  await page.getByRole("button", { name: "Pass the Portal" }).click();
  await page.getByLabel("Access PIN").fill(pin);
  const loginResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/auth/login" &&
      response.request().method() === "POST"
    );
  });
  await page.getByRole("button", { name: "Verify Identity" }).click();
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.status()).toBe(200);
  const loginBody = (await loginResponse.json()) as {
    data?: {
      token?: unknown;
      redirectTo?: unknown;
      user?: { role?: unknown };
    };
  };
  if (
    typeof loginBody.data?.token !== "string" ||
    loginBody.data.user?.role !== "partner" ||
    loginBody.data.redirectTo !== "/portal/partner/dashboard"
  ) {
    throw new Error("Synthetic Partner login did not return its role contract");
  }
  await expect(page).toHaveURL(/\/portal\/partner\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Partner Dashboard" }),
  ).toBeVisible();
  return loginBody.data.token;
}

async function logoutViaPortalUi(
  page: Page,
  isMobile: boolean,
  variant: "client" | "partner" = "client",
): Promise<void> {
  if (isMobile) {
    await page.getByRole("button", { name: "Open menu" }).click();
    const mobileNavigation = page.getByRole("dialog", {
      name: `${variant === "partner" ? "Partner" : "Client"} portal navigation`,
    });
    await expect(mobileNavigation).toBeVisible();
    await mobileNavigation.getByRole("button", { name: "Logout" }).click();
  } else {
    await page.getByRole("button", { name: "Logout" }).click();
  }
  await expect(page).toHaveURL(/\/portal\/login-upgraded(?:\?|$)/);
}

async function takeMagicLinkFromSink(page: Page): Promise<string> {
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    const response = await page.request.get(environment.magicLinkInboxUrl, {
      headers: { "X-QA-Sink-Key": environment.magicLinkSinkKey },
    });
    if (response.status() === 404) {
      await page.waitForTimeout(100);
      continue;
    }
    if (response.status() !== 200) {
      throw new Error("Synthetic magic-link sink returned an invalid status");
    }
    const body = (await response.json()) as { magic_link?: unknown };
    if (typeof body.magic_link !== "string") {
      throw new Error("Synthetic magic-link sink returned an invalid contract");
    }
    return body.magic_link;
  }
  throw new Error("Synthetic magic-link sink did not receive the notification");
}

async function readSupportMailReceipt(page: Page): Promise<number> {
  const response = await page.request.get(environment.supportMailReceiptUrl, {
    headers: { "X-QA-Sink-Key": environment.magicLinkSinkKey },
  });
  if (response.status() !== 200) {
    throw new Error("Synthetic support-mail sink returned an invalid status");
  }
  const body = (await response.json()) as {
    document_upload_notifications?: unknown;
  };
  if (
    typeof body.document_upload_notifications !== "number" ||
    !Number.isInteger(body.document_upload_notifications) ||
    body.document_upload_notifications < 0
  ) {
    throw new Error("Synthetic support-mail sink returned an invalid receipt");
  }
  return body.document_upload_notifications;
}

interface DocumentSinkReceipt {
  readonly documents: number;
  readonly uploads: number;
  readonly downloads: number;
  readonly rejectedUploads: number;
}

async function readDocumentSinkReceipt(
  page: Page,
): Promise<DocumentSinkReceipt> {
  const response = await page.request.get(environment.documentSinkReceiptUrl, {
    headers: { "X-QA-Sink-Key": environment.documentSinkKey },
  });
  if (response.status() !== 200) {
    throw new Error("Synthetic document sink returned an invalid status");
  }
  const body = (await response.json()) as {
    documents?: unknown;
    uploads?: unknown;
    downloads?: unknown;
    rejected_uploads?: unknown;
  };
  const values = [
    body.documents,
    body.uploads,
    body.downloads,
    body.rejected_uploads,
  ];
  if (
    values.some(
      (value) =>
        typeof value !== "number" || !Number.isInteger(value) || value < 0,
    )
  ) {
    throw new Error("Synthetic document sink returned an invalid receipt");
  }
  return {
    documents: body.documents as number,
    uploads: body.uploads as number,
    downloads: body.downloads as number,
    rejectedUploads: body.rejected_uploads as number,
  };
}

async function armNextDocumentUploadFailure(page: Page): Promise<void> {
  const response = await page.request.post(environment.documentSinkFailureUrl, {
    headers: { "X-QA-Sink-Key": environment.documentSinkKey },
  });
  if (response.status() !== 204) {
    throw new Error("Synthetic document sink did not arm the upload failure");
  }
}

test("@qa-be-003 portal-disabled PIN credentials fail closed without a session", async ({
  page,
  baseURL,
}) => {
  if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

  const runtimeFailures = collectSanitizedRuntimeFailures(
    page,
    () => false,
    (message) =>
      message.text().startsWith("Failed to load resource:") &&
      message.text().includes("403"),
  );
  const allowedOrigins = new Set([
    new URL(baseURL).origin,
    environment.backendApiUrl,
  ]);
  const unsafeExternalWrites = collectUnsafeExternalWrites(
    page,
    allowedOrigins,
  );
  const disallowedNetworkRequests = collectDisallowedNetworkRequests(
    page,
    allowedOrigins,
  );

  await page.goto("/portal/login-upgraded", {
    waitUntil: "domcontentloaded",
  });
  const emailInput = page.getByRole("textbox", { name: "Corporate Email" });
  await emailInput.fill(environment.disabledClientEmail);
  await page.getByRole("button", { name: "Pass the Portal" }).click();
  await page.getByLabel("Access PIN").fill(environment.disabledClientPin);

  const loginResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/auth/login" &&
      response.request().method() === "POST"
    );
  });
  await page.getByRole("button", { name: "Verify Identity" }).click();
  const loginResponse = await loginResponsePromise;

  expect(loginResponse.status()).toBe(403);
  expect(await loginResponse.json()).toMatchObject({
    detail: "Portal access is not available for this account",
  });
  await expect(
    page.getByRole("alert").filter({ hasText: "Access Denied" }),
  ).toContainText(
    "Portal access is not available for this account. Contact team@balizero.com.",
  );
  await expect(page).toHaveURL(/\/portal\/login-upgraded$/);

  const profileResponse = await page.request.get(
    `${environment.backendApiUrl}/api/auth/profile`,
  );
  expect(profileResponse.status()).toBe(401);

  await page.goto("/portal/process?source=synthetic-qa", {
    waitUntil: "domcontentloaded",
  });
  await expect(page).toHaveURL((url) => {
    return (
      url.origin === new URL(baseURL).origin &&
      url.pathname === "/portal/login-upgraded" &&
      url.searchParams.get("redirect") === "/portal/process?source=synthetic-qa"
    );
  });

  expect(unsafeExternalWrites).toEqual([]);
  expect(disallowedNetworkRequests).toEqual([]);
  expect(runtimeFailures).toEqual([]);
});

test("@qa-e2e-001 real auth, restore, deep link, and logout smoke", async ({
  page,
  baseURL,
  isMobile,
}) => {
  if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

  const runtimeFailures = collectSanitizedRuntimeFailures(page);
  const allowedOrigins = new Set([
    new URL(baseURL).origin,
    environment.backendApiUrl,
  ]);
  const unsafeExternalWrites = collectUnsafeExternalWrites(
    page,
    allowedOrigins,
  );
  const disallowedNetworkRequests = collectDisallowedNetworkRequests(
    page,
    allowedOrigins,
  );
  let presentedAccessToken: string | undefined;

  await test.step("real synthetic login", async () => {
    const session = await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );
    presentedAccessToken = session.token;

    const protectedResponse = await page.request.get(
      `${environment.backendApiUrl}/api/portal/dashboard`,
      { headers: { Authorization: `Bearer ${presentedAccessToken}` } },
    );
    expect(protectedResponse.status()).toBe(200);
  });

  await test.step("session survives refresh", async () => {
    await page.reload({ waitUntil: "domcontentloaded" });
    await expectDashboardSettled(page);
  });

  await test.step("authenticated deep link resolves", async () => {
    await page.goto("/portal/process", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/portal\/process$/);
    await expect(
      page.getByRole("main").getByRole("heading", { name: "My Processes" }),
    ).toBeVisible();
  });

  await test.step("logout revokes the presented JWT and protected session", async () => {
    await logoutViaPortalUi(page, isMobile);

    if (!presentedAccessToken) {
      throw new Error(
        "Synthetic access token was unavailable for logout replay",
      );
    }
    const revokedResponse = await page.request.get(
      `${environment.backendApiUrl}/api/portal/dashboard`,
      { headers: { Authorization: `Bearer ${presentedAccessToken}` } },
    );
    expect(revokedResponse.status()).toBe(401);

    await page.goto("/portal/process", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL((url) => {
      return (
        url.origin === new URL(baseURL).origin &&
        url.pathname === "/portal/login-upgraded" &&
        url.searchParams.get("redirect") === "/portal/process"
      );
    });
    await expect(
      page.getByRole("textbox", { name: "Corporate Email" }),
    ).toBeVisible();
  });

  expect(unsafeExternalWrites).toEqual([]);
  expect(disallowedNetworkRequests).toEqual([]);
  expect(runtimeFailures).toEqual([]);
});

test.describe("Partner portal prod-like role contract", () => {
  test.use({ serviceWorkers: "block" });

  test("@qa-partner-001 real Partner journey, isolation, and recovery", async ({
    page,
    baseURL,
    isMobile,
  }) => {
    if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

    let expectedCommissionFailures = 0;
    let partnerFailureWindow = false;
    let partnerClientPortalRequests = 0;
    const runtimeFailures = collectSanitizedRuntimeFailures(
      page,
      (response) => {
        const url = new URL(response.url());
        const expected =
          response.status() === 503 &&
          url.pathname === "/api/partners/me/commissions" &&
          expectedCommissionFailures === 0;
        if (expected) expectedCommissionFailures += 1;
        return expected;
      },
      () => partnerFailureWindow,
    );
    const allowedOrigins = new Set([
      new URL(baseURL).origin,
      environment.backendApiUrl,
    ]);
    const unsafeExternalWrites = collectUnsafeExternalWrites(
      page,
      allowedOrigins,
    );
    const disallowedNetworkRequests = collectDisallowedNetworkRequests(
      page,
      allowedOrigins,
    );
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.pathname.startsWith("/api/portal/")) {
        partnerClientPortalRequests += 1;
      }
    });

    const partnerToken = await loginPartnerViaPortalUi(
      page,
      environment.partnerEmail,
      environment.partnerPin,
    );

    await test.step("dashboard renders canonical commission values", async () => {
      const main = page.locator("#portal-main-content");
      await expect(
        main.getByText(`Welcome, ${SYNTHETIC_PARTNER_NAME}`),
      ).toBeVisible();
      const totalEarnedCard = main
        .getByText("Total Earned", { exact: true })
        .locator("..");
      const pendingCard = main
        .getByText("Pending", { exact: true })
        .locator("..");
      const referralCountCard = main
        .getByText("Referral Count", { exact: true })
        .locator("..");
      await expect(totalEarnedCard).toContainText(/Rp\s*1\.800\.000/);
      await expect(pendingCard).toContainText(/Rp\s*900\.000/);
      await expect(referralCountCard).toContainText("1");
      await expect(page.locator('a[href="/portal/billing"]')).toHaveCount(0);
      await expect(page.locator('a[href="/portal/messages"]')).toHaveCount(0);
    });

    await test.step("referrals are data-minimized", async () => {
      await page.goto("/portal/partner/referrals", {
        waitUntil: "domcontentloaded",
      });
      await expect(
        page.getByRole("heading", { name: "My Referrals" }),
      ).toBeVisible();
      await expect(
        page.getByText(SYNTHETIC_PARTNER_CLIENT_DISPLAY),
      ).toBeVisible();
      await expect(page.getByText(SYNTHETIC_PARTNER_SERVICE)).toBeVisible();
      await expect(
        page.getByText("Synthetic Active Portal Client"),
      ).toHaveCount(0);
      await expect(page.getByText("KITAS E33G")).toHaveCount(0);
    });

    await test.step("commissions and profile render real Partner rows", async () => {
      await page.goto("/portal/partner/commissions", {
        waitUntil: "domcontentloaded",
      });
      await expect(
        page.getByRole("heading", { name: "My Commissions" }),
      ).toBeVisible();
      await expect(page.getByText(/^Rp\s*2\.000\.000$/)).toBeVisible();
      await expect(page.getByText(/^Rp\s*1\.800\.000$/)).toBeVisible();
      const commissionTable = page.getByRole("table");
      await expect(
        commissionTable.getByText("Paid", { exact: true }),
      ).toBeVisible();
      await expect(
        commissionTable.getByText("Accrued", { exact: true }),
      ).toBeVisible();

      await page.goto("/portal/partner/profile", {
        waitUntil: "domcontentloaded",
      });
      await expect(
        page.getByRole("heading", { name: "My Profile" }),
      ).toBeVisible();
      const profileMain = page.locator("#portal-main-content");
      const fullNameField = profileMain
        .getByText("Full Name", { exact: true })
        .locator("..");
      const bankNameField = profileMain
        .getByText("Bank Name", { exact: true })
        .locator("..");
      await expect(fullNameField).toContainText(SYNTHETIC_PARTNER_NAME);
      await expect(bankNameField).toContainText("Synthetic QA Bank");
    });

    await test.step("a transient commission outage is safe and retryable", async () => {
      let failNextCommissionRead = true;
      await page.route("**/api/partners/me/commissions", async (route) => {
        if (!failNextCommissionRead) {
          await route.continue();
          return;
        }
        failNextCommissionRead = false;
        partnerFailureWindow = true;
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({
            detail: "synthetic private partner storage detail",
          }),
        });
      });
      await page.goto("/portal/partner/commissions", {
        waitUntil: "domcontentloaded",
      });
      const alert = page
        .getByRole("alert")
        .filter({ hasText: "Commissions are temporarily unavailable" });
      await expect(alert).toContainText(
        "Commissions are temporarily unavailable",
      );
      await expect(alert).not.toContainText(
        "synthetic private partner storage detail",
      );
      partnerFailureWindow = false;
      await page.getByRole("button", { name: "Try Again" }).click();
      await expect(
        page.getByRole("heading", { name: "My Commissions" }),
      ).toBeVisible();
      await expect(page.getByText(/^Rp\s*1\.800\.000$/)).toBeVisible();
      await page.unroute("**/api/partners/me/commissions");
    });

    await test.step("Partner cannot enter client tenant routes", async () => {
      const clientDashboardResponse = await page.request.get(
        `${environment.backendApiUrl}/api/portal/dashboard`,
        { headers: { Authorization: `Bearer ${partnerToken}` } },
      );
      expect(clientDashboardResponse.status()).toBe(403);
      await page.goto("/portal/billing", { waitUntil: "domcontentloaded" });
      await expect(page).toHaveURL(/\/portal\/partner\/dashboard$/);
    });

    expect(partnerClientPortalRequests).toBe(0);
    await logoutViaPortalUi(page, isMobile, "partner");

    const clientSession = await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );
    const partnerProfileResponse = await page.request.get(
      `${environment.backendApiUrl}/api/partners/me`,
      { headers: { Authorization: `Bearer ${clientSession.token}` } },
    );
    expect(partnerProfileResponse.status()).toBe(403);
    await logoutViaPortalUi(page, isMobile);

    expect(expectedCommissionFailures).toBe(1);
    expect(unsafeExternalWrites).toEqual([]);
    expect(disallowedNetworkRequests).toEqual([]);
    expect(runtimeFailures).toEqual([]);
  });
});

test.describe("message inbox outage recovery", () => {
  test.use({ serviceWorkers: "block" });

  test("@qa-be-003 message inbox distinguishes an outage from empty and recovers", async ({
    page,
    baseURL,
    isMobile,
  }) => {
    if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

    const allowedOrigins = new Set([
      new URL(baseURL).origin,
      environment.backendApiUrl,
    ]);
    const unsafeExternalWrites = collectUnsafeExternalWrites(
      page,
      allowedOrigins,
    );
    const disallowedNetworkRequests = collectDisallowedNetworkRequests(
      page,
      allowedOrigins,
    );
    let injectedMessageFailures = 0;
    const messagesPattern = "**/api/portal/messages**";

    await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );

    await page.context().route(messagesPattern, async (route) => {
      if (route.request().method() === "GET") {
        injectedMessageFailures += 1;
        await route.abort("failed");
        return;
      }
      await route.continue();
    });
    await page.goto("/portal/messages", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("heading", { name: "Unable to load messages" }),
    ).toBeVisible();
    await expect(
      page.getByText("No messages yet", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText(
        "Your messages are still safe. Check your connection and try again.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(injectedMessageFailures).toBeGreaterThan(0);

    await page.context().unroute(messagesPattern);
    const recoveryRuntimeFailures = collectSanitizedRuntimeFailures(page);
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(
      page
        .locator("#portal-main-content")
        .getByRole("heading", { name: "Messages" }),
    ).toBeVisible();
    await expect(page.getByText(SYNTHETIC_TEAM_MESSAGE)).toBeVisible();

    await logoutViaPortalUi(page, isMobile);
    expect(unsafeExternalWrites).toEqual([]);
    expect(disallowedNetworkRequests).toEqual([]);
    expect(recoveryRuntimeFailures).toEqual([]);
  });
});

test.describe("company list outage recovery", () => {
  test.use({ serviceWorkers: "block" });

  test("@qa-be-003 company list distinguishes an outage from no records and recovers", async ({
    page,
    baseURL,
    isMobile,
  }) => {
    if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

    const allowedOrigins = new Set([
      new URL(baseURL).origin,
      environment.backendApiUrl,
    ]);
    const unsafeExternalWrites = collectUnsafeExternalWrites(
      page,
      allowedOrigins,
    );
    const disallowedNetworkRequests = collectDisallowedNetworkRequests(
      page,
      allowedOrigins,
    );
    let injectedCompanyFailures = 0;
    const companiesPattern = "**/api/portal/companies**";

    await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );

    await page.context().route(companiesPattern, async (route) => {
      if (route.request().method() === "GET") {
        injectedCompanyFailures += 1;
        await route.abort("failed");
        return;
      }
      await route.continue();
    });
    await page.goto("/portal/companies", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("heading", { name: "Unable to load companies" }),
    ).toBeVisible();
    await expect(
      page.getByText("No companies yet", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText(
        "We couldn't verify your company records. Check your connection and try again.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(injectedCompanyFailures).toBeGreaterThan(0);

    await page.context().unroute(companiesPattern);
    const recoveryRuntimeFailures = collectSanitizedRuntimeFailures(page);
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(
      page.getByRole("button", {
        name: `View ${SYNTHETIC_COMPANY_NAME} details`,
      }),
    ).toBeVisible();

    await logoutViaPortalUi(page, isMobile);
    expect(unsafeExternalWrites).toEqual([]);
    expect(disallowedNetworkRequests).toEqual([]);
    expect(recoveryRuntimeFailures).toEqual([]);
  });
});

test.describe("notification preferences outage recovery", () => {
  test.use({ serviceWorkers: "block" });

  test("@qa-be-003 notification settings tab keeps an outage client-safe and recovers real preferences", async ({
    page,
    baseURL,
    isMobile,
  }) => {
    if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

    const allowedOrigins = new Set([
      new URL(baseURL).origin,
      environment.backendApiUrl,
    ]);
    const unsafeExternalWrites = collectUnsafeExternalWrites(
      page,
      allowedOrigins,
    );
    const disallowedNetworkRequests = collectDisallowedNetworkRequests(
      page,
      allowedOrigins,
    );
    let injectedPreferenceFailures = 0;
    const preferencesPattern = "**/api/portal/notifications/prefs";

    await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );

    await page.context().route(preferencesPattern, async (route) => {
      if (route.request().method() === "GET") {
        injectedPreferenceFailures += 1;
        await route.abort("failed");
        return;
      }
      await route.continue();
    });
    await page.goto("/portal/settings?tab=notifications", {
      waitUntil: "domcontentloaded",
    });
    const settingsAlert = page
      .locator("#portal-main-content")
      .getByRole("alert");
    await expect(settingsAlert).toContainText("Unable to load preferences");
    await expect(settingsAlert).toContainText(
      "Your saved choices have not been changed",
    );
    await expect(
      page.getByRole("checkbox", { name: "Email notifications" }),
    ).toHaveCount(0);
    expect(injectedPreferenceFailures).toBeGreaterThan(0);

    await page.context().unroute(preferencesPattern);
    const recoveryRuntimeFailures = collectSanitizedRuntimeFailures(page);
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(
      page.getByRole("checkbox", { name: "Email notifications" }),
    ).toBeChecked();
    await expect(
      page.getByRole("checkbox", { name: "WhatsApp notifications" }),
    ).not.toBeChecked();

    await logoutViaPortalUi(page, isMobile);
    expect(unsafeExternalWrites).toEqual([]);
    expect(disallowedNetworkRequests).toEqual([]);
    expect(recoveryRuntimeFailures).toEqual([]);
  });

  test("@qa-be-003 standalone notification settings keeps an outage client-safe and recovers real preferences", async ({
    page,
    baseURL,
    isMobile,
  }) => {
    if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

    const allowedOrigins = new Set([
      new URL(baseURL).origin,
      environment.backendApiUrl,
    ]);
    const unsafeExternalWrites = collectUnsafeExternalWrites(
      page,
      allowedOrigins,
    );
    const disallowedNetworkRequests = collectDisallowedNetworkRequests(
      page,
      allowedOrigins,
    );
    let injectedPreferenceFailures = 0;
    const preferencesPattern = "**/api/portal/notifications/prefs";

    await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );

    await page.context().route(preferencesPattern, async (route) => {
      if (route.request().method() === "GET") {
        injectedPreferenceFailures += 1;
        await route.abort("failed");
        return;
      }
      await route.continue();
    });
    await page.goto("/portal/settings/notifications", {
      waitUntil: "domcontentloaded",
    });
    await expect(
      page.getByRole("heading", { name: "Unable to load preferences" }),
    ).toBeVisible();
    await expect(
      page.locator("#portal-main-content").getByRole("alert"),
    ).toContainText("We could not verify your saved notification choices");
    await expect(
      page.getByText(/notification_prefs|internal-host/i),
    ).toHaveCount(0);
    expect(injectedPreferenceFailures).toBeGreaterThan(0);

    await page.context().unroute(preferencesPattern);
    const recoveryRuntimeFailures = collectSanitizedRuntimeFailures(page);
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(
      page.getByRole("heading", { name: "Notification preferences" }),
    ).toBeVisible();
    await expect(page.getByRole("checkbox", { name: "Email" })).toBeChecked();

    await logoutViaPortalUi(page, isMobile);
    expect(unsafeExternalWrites).toEqual([]);
    expect(disallowedNetworkRequests).toEqual([]);
    expect(recoveryRuntimeFailures).toEqual([]);
  });
});

test.describe("matters outage recovery", () => {
  test.use({ serviceWorkers: "block" });

  test("@qa-be-003 matters list keeps an outage client-safe and recovers real matters", async ({
    page,
    baseURL,
    isMobile,
  }) => {
    if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

    const allowedOrigins = new Set([
      new URL(baseURL).origin,
      environment.backendApiUrl,
    ]);
    const unsafeExternalWrites = collectUnsafeExternalWrites(
      page,
      allowedOrigins,
    );
    const disallowedNetworkRequests = collectDisallowedNetworkRequests(
      page,
      allowedOrigins,
    );
    let injectedMattersFailures = 0;
    const mattersPattern = "**/api/portal/matters";

    await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );

    await page.context().route(mattersPattern, async (route) => {
      if (route.request().method() === "GET") {
        injectedMattersFailures += 1;
        await route.abort("failed");
        return;
      }
      await route.continue();
    });
    await page.goto("/portal/matters", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("heading", { name: "Unable to load matters" }),
    ).toBeVisible();
    await expect(
      page.getByText("No open matters", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText(
        "We could not verify your matters. Check your connection and try again.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(injectedMattersFailures).toBeGreaterThan(0);

    await page.context().unroute(mattersPattern);
    const recoveryRuntimeFailures = collectSanitizedRuntimeFailures(page);
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(
      page.getByText(SYNTHETIC_MATTER_TITLE, { exact: true }),
    ).toBeVisible();

    await logoutViaPortalUi(page, isMobile);
    expect(unsafeExternalWrites).toEqual([]);
    expect(disallowedNetworkRequests).toEqual([]);
    expect(recoveryRuntimeFailures).toEqual([]);
  });

  test("@qa-be-003 matter detail keeps an outage client-safe and recovers the real matter", async ({
    page,
    baseURL,
    isMobile,
  }) => {
    if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

    const allowedOrigins = new Set([
      new URL(baseURL).origin,
      environment.backendApiUrl,
    ]);
    const unsafeExternalWrites = collectUnsafeExternalWrites(
      page,
      allowedOrigins,
    );
    const disallowedNetworkRequests = collectDisallowedNetworkRequests(
      page,
      allowedOrigins,
    );

    await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );
    await page.goto("/portal/matters", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByText(SYNTHETIC_MATTER_TITLE, { exact: true }),
    ).toBeVisible();
    const matterHref = await page
      .getByRole("link", { name: /Open/ })
      .first()
      .getAttribute("href");
    if (!matterHref || !/^\/portal\/matters\/\d+$/.test(matterHref)) {
      throw new Error("Synthetic matter link did not expose its safe route");
    }

    let injectedMatterDetailFailures = 0;
    const matterDetailPattern = `**${matterHref.replace("/portal", "/api/portal")}`;
    await page.context().route(matterDetailPattern, async (route) => {
      if (route.request().method() === "GET") {
        injectedMatterDetailFailures += 1;
        await route.abort("failed");
        return;
      }
      await route.continue();
    });
    await page.goto(matterHref, { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("heading", { name: "Unable to load matter" }),
    ).toBeVisible();
    await expect(
      page.getByText("No approved summary yet", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText(
        "We could not verify this matter. Check your connection and try again.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(injectedMatterDetailFailures).toBeGreaterThan(0);

    await page.context().unroute(matterDetailPattern);
    const recoveryRuntimeFailures = collectSanitizedRuntimeFailures(page);
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(
      page.getByRole("heading", { name: SYNTHETIC_MATTER_TITLE }),
    ).toBeVisible();

    await logoutViaPortalUi(page, isMobile);
    expect(unsafeExternalWrites).toEqual([]);
    expect(disallowedNetworkRequests).toEqual([]);
    expect(recoveryRuntimeFailures).toEqual([]);
  });
});

test.describe("billing outage recovery", () => {
  test.use({ serviceWorkers: "block" });

  test("@qa-be-003 billing keeps an outage client-safe and recovers real invoices", async ({
    page,
    baseURL,
    isMobile,
  }) => {
    if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

    const allowedOrigins = new Set([
      new URL(baseURL).origin,
      environment.backendApiUrl,
    ]);
    const unsafeExternalWrites = collectUnsafeExternalWrites(
      page,
      allowedOrigins,
    );
    const disallowedNetworkRequests = collectDisallowedNetworkRequests(
      page,
      allowedOrigins,
    );
    let injectedBillingFailures = 0;
    const billingPattern = "**/api/portal/billing";

    await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );

    await page.context().route(billingPattern, async (route) => {
      if (route.request().method() === "GET") {
        injectedBillingFailures += 1;
        await route.abort("failed");
        return;
      }
      await route.continue();
    });
    await page.goto("/portal/billing", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("heading", { name: "Unable to load billing" }),
    ).toBeVisible();
    await expect(
      page.getByText("No invoices yet", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText(
        "We could not verify your invoices. Check your connection and try again.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(injectedBillingFailures).toBeGreaterThan(0);

    await page.context().unroute(billingPattern);
    const recoveryRuntimeFailures = collectSanitizedRuntimeFailures(page);
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(
      page.getByText(SYNTHETIC_INVOICE_NUMBER, { exact: true }),
    ).toBeVisible();

    await logoutViaPortalUi(page, isMobile);
    expect(unsafeExternalWrites).toEqual([]);
    expect(disallowedNetworkRequests).toEqual([]);
    expect(recoveryRuntimeFailures).toEqual([]);
  });
});

test.describe("family outage recovery", () => {
  test.use({ serviceWorkers: "block" });

  test("@qa-be-003 family keeps an outage client-safe and recovers real members", async ({
    page,
    baseURL,
    isMobile,
  }) => {
    if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

    const allowedOrigins = new Set([
      new URL(baseURL).origin,
      environment.backendApiUrl,
    ]);
    const unsafeExternalWrites = collectUnsafeExternalWrites(
      page,
      allowedOrigins,
    );
    const disallowedNetworkRequests = collectDisallowedNetworkRequests(
      page,
      allowedOrigins,
    );
    let injectedFamilyFailures = 0;
    const familyPattern = "**/api/portal/family";

    await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );

    await page.context().route(familyPattern, async (route) => {
      if (route.request().method() === "GET") {
        injectedFamilyFailures += 1;
        await route.abort("failed");
        return;
      }
      await route.continue();
    });
    await page.goto("/portal/family", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("heading", { name: "Unable to load family" }),
    ).toBeVisible();
    await expect(
      page.getByText("No family members on file", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText(
        "We could not verify your family records. Check your connection and try again.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(injectedFamilyFailures).toBeGreaterThan(0);

    await page.context().unroute(familyPattern);
    const recoveryRuntimeFailures = collectSanitizedRuntimeFailures(page);
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(page.getByText(SYNTHETIC_ADULT_NAME)).toBeVisible();
    await expect(page.getByText(SYNTHETIC_MINOR_NAME)).toBeVisible();

    await logoutViaPortalUi(page, isMobile);
    expect(unsafeExternalWrites).toEqual([]);
    expect(disallowedNetworkRequests).toEqual([]);
    expect(recoveryRuntimeFailures).toEqual([]);
  });
});

test.describe("tax overview outage recovery", () => {
  test.use({ serviceWorkers: "block" });

  test("@qa-be-003 tax overview distinguishes an outage from no records and recovers", async ({
    page,
    baseURL,
    isMobile,
  }) => {
    if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

    const allowedOrigins = new Set([
      new URL(baseURL).origin,
      environment.backendApiUrl,
    ]);
    const unsafeExternalWrites = collectUnsafeExternalWrites(
      page,
      allowedOrigins,
    );
    const disallowedNetworkRequests = collectDisallowedNetworkRequests(
      page,
      allowedOrigins,
    );
    let injectedTaxFailures = 0;
    const taxesPattern = "**/api/portal/taxes**";

    await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );

    await page.context().route(taxesPattern, async (route) => {
      if (route.request().method() === "GET") {
        injectedTaxFailures += 1;
        await route.abort("failed");
        return;
      }
      await route.continue();
    });
    await page.goto("/portal/taxes", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("heading", { name: "Unable to load tax information" }),
    ).toBeVisible();
    await expect(
      page.getByText("No tax data available", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText(
        "We couldn't verify your tax records. Check your connection and try again.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(injectedTaxFailures).toBeGreaterThan(0);

    await page.context().unroute(taxesPattern);
    const recoveryRuntimeFailures = collectSanitizedRuntimeFailures(page);
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(
      page.getByRole("heading", { name: "Tax Status" }),
    ).toBeVisible();

    await logoutViaPortalUi(page, isMobile);
    expect(unsafeExternalWrites).toEqual([]);
    expect(disallowedNetworkRequests).toEqual([]);
    expect(recoveryRuntimeFailures).toEqual([]);
  });
});

test.describe("LKPM outage recovery", () => {
  test.use({ serviceWorkers: "block" });

  test("@qa-be-003 LKPM history distinguishes an outage from no reports and recovers", async ({
    page,
    baseURL,
    isMobile,
  }) => {
    if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

    const allowedOrigins = new Set([
      new URL(baseURL).origin,
      environment.backendApiUrl,
    ]);
    const unsafeExternalWrites = collectUnsafeExternalWrites(
      page,
      allowedOrigins,
    );
    const disallowedNetworkRequests = collectDisallowedNetworkRequests(
      page,
      allowedOrigins,
    );
    let injectedHistoryFailures = 0;
    const historyPattern = "**/api/v1/lkpm/history/me**";

    await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );

    await page.context().route(historyPattern, async (route) => {
      if (route.request().method() === "GET") {
        injectedHistoryFailures += 1;
        await route.abort("failed");
        return;
      }
      await route.continue();
    });
    await page.goto("/portal/lkpm", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("heading", { name: "Unable to load LKPM reports" }),
    ).toBeVisible();
    await expect(page.getByText(/No LKPM reports yet/)).toHaveCount(0);
    await expect(
      page.getByText(
        "We couldn't verify your LKPM records. Check your connection and try again.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(injectedHistoryFailures).toBeGreaterThan(0);

    await page.context().unroute(historyPattern);
    const recoveryRuntimeFailures = collectSanitizedRuntimeFailures(page);
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(page.getByText("Perlu persetujuan Anda")).toBeVisible();

    await logoutViaPortalUi(page, isMobile);
    expect(unsafeExternalWrites).toEqual([]);
    expect(disallowedNetworkRequests).toEqual([]);
    expect(recoveryRuntimeFailures).toEqual([]);
  });

  test("@qa-be-003 LKPM keeps reports visible during a receipt outage and recovers", async ({
    page,
    baseURL,
    isMobile,
  }) => {
    if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

    const allowedOrigins = new Set([
      new URL(baseURL).origin,
      environment.backendApiUrl,
    ]);
    const unsafeExternalWrites = collectUnsafeExternalWrites(
      page,
      allowedOrigins,
    );
    const disallowedNetworkRequests = collectDisallowedNetworkRequests(
      page,
      allowedOrigins,
    );
    let injectedReceiptFailures = 0;
    const receiptsPattern = "**/api/v1/lkpm/receipts/me**";

    await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );

    await page.context().route(receiptsPattern, async (route) => {
      if (route.request().method() === "GET") {
        injectedReceiptFailures += 1;
        await route.abort("failed");
        return;
      }
      await route.continue();
    });
    await page.goto("/portal/lkpm", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Perlu persetujuan Anda")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Unable to load OSS receipts" }),
    ).toBeVisible();
    await expect(
      page.getByText(SYNTHETIC_LKPM_RECEIPT_NUMBER, { exact: true }),
    ).toHaveCount(0);
    expect(injectedReceiptFailures).toBeGreaterThan(0);

    await page.context().unroute(receiptsPattern);
    const recoveryRuntimeFailures = collectSanitizedRuntimeFailures(page);
    await page.getByRole("button", { name: "Retry receipts" }).click();
    await expect(
      page.getByRole("heading", { name: "OSS Tanda Terima" }),
    ).toBeVisible();
    await expect(
      page.getByText(SYNTHETIC_LKPM_RECEIPT_NUMBER, { exact: true }),
    ).toBeVisible();

    await logoutViaPortalUi(page, isMobile);
    expect(unsafeExternalWrites).toEqual([]);
    expect(disallowedNetworkRequests).toEqual([]);
    expect(recoveryRuntimeFailures).toEqual([]);
  });

  test("@qa-be-003 LKPM draft detail distinguishes an outage from a missing report and recovers", async ({
    page,
    baseURL,
    isMobile,
  }) => {
    if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

    const allowedOrigins = new Set([
      new URL(baseURL).origin,
      environment.backendApiUrl,
    ]);
    const unsafeExternalWrites = collectUnsafeExternalWrites(
      page,
      allowedOrigins,
    );
    const disallowedNetworkRequests = collectDisallowedNetworkRequests(
      page,
      allowedOrigins,
    );
    let injectedDraftFailures = 0;
    const draftPattern = "**/api/v1/lkpm/draft/0/Q2?year=2026**";

    await loginViaPortalUi(
      page,
      environment.clientEmail,
      environment.clientPin,
    );

    await page.context().route(draftPattern, async (route) => {
      if (route.request().method() === "GET") {
        injectedDraftFailures += 1;
        await route.abort("failed");
        return;
      }
      await route.continue();
    });
    await page.goto("/portal/lkpm/Q2?year=2026", {
      waitUntil: "domcontentloaded",
    });
    await expect(
      page.getByRole("heading", { name: "Unable to load LKPM draft" }),
    ).toBeVisible();
    await expect(page.getByText(/No draft found for/)).toHaveCount(0);
    await expect(
      page.getByText(
        "We couldn't verify this report. Check your connection and try again.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(injectedDraftFailures).toBeGreaterThan(0);

    await page.context().unroute(draftPattern);
    const recoveryRuntimeFailures = collectSanitizedRuntimeFailures(page);
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(
      page.getByRole("heading", { name: "Q2 2026 — LKPM Draft" }),
    ).toBeVisible();
    await expect(page.getByText("Validated", { exact: true })).toBeVisible();

    await logoutViaPortalUi(page, isMobile);
    expect(unsafeExternalWrites).toEqual([]);
    expect(disallowedNetworkRequests).toEqual([]);
    expect(recoveryRuntimeFailures).toEqual([]);
  });
});

test("@qa-be-003 LKPM submits a real tenant draft and protects the submitted period", async ({
  page,
  baseURL,
  isMobile,
}, testInfo) => {
  if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

  let conflictFailureWindow = false;
  const runtimeFailures = collectSanitizedRuntimeFailures(
    page,
    () => false,
    (message) => {
      const locationUrl = message.location().url;
      let hasExpectedLocation = locationUrl === "";
      if (locationUrl !== "") {
        try {
          hasExpectedLocation =
            new URL(locationUrl).pathname === "/api/v1/lkpm/submit-data";
        } catch {
          hasExpectedLocation = false;
        }
      }
      return (
        conflictFailureWindow &&
        hasExpectedLocation &&
        message.text().startsWith("Failed to load resource:") &&
        message.text().includes("409")
      );
    },
  );
  const allowedOrigins = new Set([
    new URL(baseURL).origin,
    environment.backendApiUrl,
  ]);
  const unsafeExternalWrites = collectUnsafeExternalWrites(
    page,
    allowedOrigins,
  );
  const disallowedNetworkRequests = collectDisallowedNetworkRequests(
    page,
    allowedOrigins,
  );
  const period = syntheticLKPMSubmissionPeriod(testInfo);
  const land = 1_200_000 + period.ordinal;
  const workingCapital = 2_300_000 + period.ordinal;
  const expectedTotal = land + workingCapital;

  await loginViaPortalUi(page, environment.clientEmail, environment.clientPin);

  await test.step("submit synthetic data through the client form", async () => {
    await page.goto("/portal/lkpm/submit", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("heading", { name: "Submit LKPM Data" }),
    ).toBeVisible();
    await page
      .getByRole("combobox", { name: "Quarter" })
      .selectOption(period.quarter);
    await page
      .getByRole("combobox", { name: "Year" })
      .selectOption(String(period.year));
    await page
      .getByRole("textbox", { name: "Land Acquisition / Preparation" })
      .fill(String(land));
    await page
      .getByRole("textbox", { name: "Working Capital — 1 Turnover (IDR)" })
      .fill(String(workingCapital));
    await page
      .getByRole("spinbutton", { name: /Indonesian Workers/ })
      .fill(String(2 + period.ordinal));
    await page.getByRole("spinbutton", { name: /Foreign Workers/ }).fill("1");
    await page
      .getByRole("textbox", { name: "Challenges Encountered" })
      .fill(`Synthetic QA obstacle ${syntheticProfileSlug(testInfo)}`);
    await page
      .getByRole("textbox", { name: "Plans for Next Period" })
      .fill(`Synthetic QA plan ${syntheticProfileSlug(testInfo)}`);

    const submissionResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        url.pathname === "/api/v1/lkpm/submit-data" &&
        response.request().method() === "POST"
      );
    });
    await page.getByRole("button", { name: "Submit Data" }).click();
    const submissionResponse = await submissionResponsePromise;
    expect(submissionResponse.status()).toBe(200);
    const submission = (await submissionResponse.json()) as {
      success?: unknown;
      quarter?: unknown;
      year?: unknown;
      realized_total?: unknown;
    };
    expect(submission).toMatchObject({
      success: true,
      quarter: period.quarter,
      year: period.year,
      realized_total: expectedTotal,
    });
  });

  await test.step("render the persisted draft from the real backend", async () => {
    await expect(page).toHaveURL(
      new RegExp(`/portal/lkpm/${period.quarter}\\?year=${period.year}$`),
    );
    await expect(
      page.getByRole("heading", {
        name: `${period.quarter} ${period.year} — LKPM Draft`,
      }),
    ).toBeVisible();
    const landRow = page.getByRole("row").filter({ hasText: "Land" });
    const workingCapitalRow = page
      .getByRole("row")
      .filter({ hasText: "Working Capital" });
    await expect(landRow).toContainText(
      new Intl.NumberFormat("id-ID").format(land),
    );
    await expect(workingCapitalRow).toContainText(
      new Intl.NumberFormat("id-ID").format(workingCapital),
    );
    await expect(page.getByText("Draft", { exact: true })).toBeVisible();
  });

  await test.step("refuse replacement of the already submitted Q1 report", async () => {
    await page.goto("/portal/lkpm/submit", { waitUntil: "domcontentloaded" });
    await page.getByRole("combobox", { name: "Quarter" }).selectOption("Q1");
    await page.getByRole("combobox", { name: "Year" }).selectOption("2026");
    const conflictResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        url.pathname === "/api/v1/lkpm/submit-data" &&
        response.request().method() === "POST"
      );
    });
    conflictFailureWindow = true;
    try {
      await page.getByRole("button", { name: "Submit Data" }).click();
      expect((await conflictResponsePromise).status()).toBe(409);
      await expect(page.getByText("Report already locked")).toBeVisible();
      await expect(
        page.getByText(
          "Approved or submitted reports cannot be replaced. Contact your Bali Zero team if a correction is needed.",
          { exact: true },
        ),
      ).toBeVisible();
      await expect(page).toHaveURL(/\/portal\/lkpm\/submit$/);
    } finally {
      conflictFailureWindow = false;
    }
  });

  await logoutViaPortalUi(page, isMobile);
  expect(unsafeExternalWrites).toEqual([]);
  expect(disallowedNetworkRequests).toEqual([]);
  expect(runtimeFailures).toEqual([]);
});

test("@qa-be-003 empty tenant and cross-tenant document denial", async ({
  page,
  baseURL,
  isMobile,
}) => {
  if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

  const runtimeFailures = collectSanitizedRuntimeFailures(page);
  const allowedOrigins = new Set([
    new URL(baseURL).origin,
    environment.backendApiUrl,
  ]);
  const unsafeExternalWrites = collectUnsafeExternalWrites(
    page,
    allowedOrigins,
  );
  const disallowedNetworkRequests = collectDisallowedNetworkRequests(
    page,
    allowedOrigins,
  );

  const activeSession =
    await test.step("resolve the active tenant sentinel", async () => {
      const session = await loginViaPortalUi(
        page,
        environment.clientEmail,
        environment.clientPin,
      );
      const documentsResponse = await page.request.get(
        `${environment.backendApiUrl}/api/portal/documents`,
        { headers: { Authorization: `Bearer ${session.token}` } },
      );
      expect(documentsResponse.status()).toBe(200);
      const documentsBody = (await documentsResponse.json()) as {
        data?: Array<{ id?: unknown; name?: unknown }>;
      };
      const sentinel = documentsBody.data?.find(
        (document) => document.name === environment.documentFixtureName,
      );
      if (typeof sentinel?.id !== "number") {
        throw new Error("Synthetic tenant-isolation document was unavailable");
      }
      const messagesResponse = await page.request.get(
        `${environment.backendApiUrl}/api/portal/messages`,
        { headers: { Authorization: `Bearer ${session.token}` } },
      );
      expect(messagesResponse.status()).toBe(200);
      const messagesBody = (await messagesResponse.json()) as {
        data?: { messages?: Array<{ id?: unknown; content?: unknown }> };
      };
      const message = messagesBody.data?.messages?.find(
        (candidate) => candidate.content === SYNTHETIC_TEAM_MESSAGE,
      );
      if (typeof message?.id !== "number") {
        throw new Error("Synthetic tenant-isolation message was unavailable");
      }

      const notificationsResponse = await page.request.get(
        `${environment.backendApiUrl}/api/portal/notifications`,
        { headers: { Authorization: `Bearer ${session.token}` } },
      );
      expect(notificationsResponse.status()).toBe(200);
      const notificationsBody = (await notificationsResponse.json()) as {
        data?: { notifications?: Array<{ id?: unknown; title?: unknown }> };
      };
      const notification = notificationsBody.data?.notifications?.find(
        (candidate) => candidate.title === SYNTHETIC_NOTIFICATION_TITLE,
      );
      if (typeof notification?.id !== "number") {
        throw new Error(
          "Synthetic tenant-isolation notification was unavailable",
        );
      }

      const companiesResponse = await page.request.get(
        `${environment.backendApiUrl}/api/portal/companies`,
        { headers: { Authorization: `Bearer ${session.token}` } },
      );
      expect(companiesResponse.status()).toBe(200);
      const companiesBody = (await companiesResponse.json()) as {
        data?: Array<{ company_id?: unknown; name?: unknown }>;
      };
      const company = companiesBody.data?.find(
        (candidate) => candidate.name === SYNTHETIC_COMPANY_NAME,
      );
      if (typeof company?.company_id !== "number") {
        throw new Error("Synthetic tenant-isolation company was unavailable");
      }

      const billingResponse = await page.request.get(
        `${environment.backendApiUrl}/api/portal/billing`,
        { headers: { Authorization: `Bearer ${session.token}` } },
      );
      expect(billingResponse.status()).toBe(200);
      const billingBody = (await billingResponse.json()) as {
        data?: { invoices?: Array<{ id?: unknown; invoice_number?: unknown }> };
      };
      const invoice = billingBody.data?.invoices?.find(
        (candidate) => candidate.invoice_number === SYNTHETIC_INVOICE_NUMBER,
      );
      if (typeof invoice?.id !== "number") {
        throw new Error("Synthetic tenant-isolation invoice was unavailable");
      }

      return {
        ...session,
        documentId: sentinel.id,
        messageId: message.id,
        notificationId: notification.id,
        companyId: company.company_id,
        invoiceId: invoice.id,
      };
    });

  await logoutViaPortalUi(page, isMobile);

  const emptySession =
    await test.step("empty account renders truthful zero-data states", async () => {
      const session = await loginViaPortalUi(
        page,
        environment.emptyClientEmail,
        environment.emptyClientPin,
      );
      expect(session.clientId).not.toBe(activeSession.clientId);
      await expect(page.getByText("No Visa", { exact: true })).toBeVisible();
      await expect(page.getByText("No Company", { exact: true })).toBeVisible();

      await page.goto("/portal/process", { waitUntil: "domcontentloaded" });
      await expect(
        page.getByRole("heading", { name: "No Active Processes" }),
      ).toBeVisible();

      await page.goto("/portal/companies", { waitUntil: "domcontentloaded" });
      await expect(
        page.getByText("No companies yet", { exact: true }),
      ).toBeVisible();

      await page.goto("/portal/billing", { waitUntil: "domcontentloaded" });
      await expect(
        page.getByText("No invoices yet", { exact: true }),
      ).toBeVisible();

      await page.goto("/portal/family", { waitUntil: "domcontentloaded" });
      await expect(
        page.getByText("No family members on file", { exact: true }),
      ).toBeVisible();

      const documentsResponse = await page.request.get(
        `${environment.backendApiUrl}/api/portal/documents`,
        { headers: { Authorization: `Bearer ${session.token}` } },
      );
      expect(documentsResponse.status()).toBe(200);
      const documentsBody = (await documentsResponse.json()) as {
        data?: unknown[];
      };
      expect(documentsBody.data).toEqual([]);
      return session;
    });

  await test.step("foreign identifiers are non-enumerable", async () => {
    const downloadResponse = await page.request.get(
      `${environment.backendApiUrl}/api/portal/documents/${activeSession.documentId}/download`,
      { headers: { Authorization: `Bearer ${emptySession.token}` } },
    );
    expect(downloadResponse.status()).toBe(404);
    expect(await downloadResponse.json()).toEqual({
      correlation_id: expect.any(String),
      detail: "Document not found or not downloadable",
    });

    const deleteResponse = await page.request.delete(
      `${environment.backendApiUrl}/api/portal/documents/${activeSession.documentId}`,
      { headers: { Authorization: `Bearer ${emptySession.token}` } },
    );
    expect(deleteResponse.status()).toBe(404);
    expect((await deleteResponse.json()).detail).toBe("Document not found");

    const restoreResponse = await page.request.post(
      `${environment.backendApiUrl}/api/portal/documents/${activeSession.documentId}/restore`,
      { headers: { Authorization: `Bearer ${emptySession.token}` } },
    );
    expect(restoreResponse.status()).toBe(404);
    expect((await restoreResponse.json()).detail).toBe(
      "Document not found or not eligible for restore",
    );

    const messageResponse = await page.request.post(
      `${environment.backendApiUrl}/api/portal/messages/${activeSession.messageId}/read`,
      { headers: { Authorization: `Bearer ${emptySession.token}` } },
    );
    expect(messageResponse.status()).toBe(404);
    expect((await messageResponse.json()).detail).toBe("Message not found");

    const notificationResponse = await page.request.post(
      `${environment.backendApiUrl}/api/portal/notifications/${activeSession.notificationId}/read`,
      { headers: { Authorization: `Bearer ${emptySession.token}` } },
    );
    expect(notificationResponse.status()).toBe(404);
    expect((await notificationResponse.json()).detail).toBe(
      "Notification not found",
    );

    const companyResponse = await page.request.get(
      `${environment.backendApiUrl}/api/portal/company/${activeSession.companyId}`,
      { headers: { Authorization: `Bearer ${emptySession.token}` } },
    );
    expect(companyResponse.status()).toBe(404);
    expect((await companyResponse.json()).detail).toBe("Company not found");

    const invoiceResponse = await page.request.get(
      `${environment.backendApiUrl}/api/portal/billing/${activeSession.invoiceId}/pdf-url`,
      { headers: { Authorization: `Bearer ${emptySession.token}` } },
    );
    expect(invoiceResponse.status()).toBe(404);
    expect((await invoiceResponse.json()).detail).toBe(
      "Invoice not found or PDF not available",
    );

    const invoiceDownloadResponse = await page.request.get(
      `${environment.backendApiUrl}/api/portal/billing/${activeSession.invoiceId}/pdf`,
      { headers: { Authorization: `Bearer ${emptySession.token}` } },
    );
    expect(invoiceDownloadResponse.status()).toBe(404);
    expect((await invoiceDownloadResponse.json()).detail).toBe(
      "Invoice not found or PDF not available",
    );
  });

  await logoutViaPortalUi(page, isMobile);
  expect(unsafeExternalWrites).toEqual([]);
  expect(disallowedNetworkRequests).toEqual([]);
  expect(runtimeFailures).toEqual([]);
});

test("@qa-be-003 expired synthetic session is denied", async ({
  page,
  baseURL,
}) => {
  if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

  const runtimeFailures = collectSanitizedRuntimeFailures(page);
  const allowedOrigins = new Set([
    new URL(baseURL).origin,
    environment.backendApiUrl,
  ]);
  const unsafeExternalWrites = collectUnsafeExternalWrites(
    page,
    allowedOrigins,
  );
  const disallowedNetworkRequests = collectDisallowedNetworkRequests(
    page,
    allowedOrigins,
  );

  const response = await page.request.get(
    `${environment.backendApiUrl}/api/portal/dashboard`,
    {
      headers: {
        Authorization: `Bearer ${environment.expiredSessionToken}`,
      },
    },
  );
  expect(response.status()).toBe(401);

  expect(unsafeExternalWrites).toEqual([]);
  expect(disallowedNetworkRequests).toEqual([]);
  expect(runtimeFailures).toEqual([]);
});

test("@qa-be-003 real magic-link login is tenant-bound and single-use", async ({
  page,
  baseURL,
  isMobile,
}) => {
  if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

  const frontendOrigin = new URL(baseURL).origin;
  const sinkOrigin = new URL(environment.magicLinkInboxUrl).origin;
  const runtimeFailures = collectSanitizedRuntimeFailures(page);
  const allowedOrigins = new Set([
    frontendOrigin,
    environment.backendApiUrl,
    sinkOrigin,
  ]);
  const unsafeExternalWrites = collectUnsafeExternalWrites(
    page,
    allowedOrigins,
  );
  const disallowedNetworkRequests = collectDisallowedNetworkRequests(
    page,
    allowedOrigins,
  );

  await page.goto("/portal/magic-link", { waitUntil: "domcontentloaded" });
  const submitButton = page.getByRole("button", { name: "Email me a link" });
  await expect(submitButton).toBeEnabled();
  await page
    .getByRole("textbox", { name: "Email address" })
    .fill(environment.clientEmail);
  const requestResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/auth/request-magic-link" &&
      response.request().method() === "POST"
    );
  });
  await submitButton.click();
  expect((await requestResponsePromise).status()).toBe(200);
  await expect(page.getByRole("status")).toContainText("If an account exists");

  const magicLink = await takeMagicLinkFromSink(page);
  const parsedMagicLink = new URL(magicLink);
  const token = parsedMagicLink.searchParams.get("token");
  if (
    parsedMagicLink.origin !== frontendOrigin ||
    parsedMagicLink.pathname !== "/portal/magic" ||
    parsedMagicLink.hash ||
    [...parsedMagicLink.searchParams.keys()].some((key) => key !== "token") ||
    !token ||
    !/^[A-Za-z0-9_-]{32,256}$/.test(token)
  ) {
    throw new Error("Synthetic sink returned an unsafe magic-link target");
  }

  const verifyResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname.startsWith("/api/auth/verify-magic/") &&
      response.request().method() === "GET"
    );
  });
  await page.goto(magicLink, { waitUntil: "domcontentloaded" });
  const verifyResponse = await verifyResponsePromise;
  expect(verifyResponse.status()).toBe(200);
  const verifyBody = (await verifyResponse.json()) as {
    data?: { user?: { client_id?: unknown; portal_access?: unknown } };
  };
  expect(typeof verifyBody.data?.user?.client_id).toBe("number");
  expect(verifyBody.data?.user?.portal_access).toBe(true);
  await expectDashboardSettled(page);

  const replayResponse = await page.request.get(
    `${environment.backendApiUrl}/api/auth/verify-magic/${encodeURIComponent(token)}`,
  );
  expect(replayResponse.status()).toBe(401);

  await logoutViaPortalUi(page, isMobile);
  expect(unsafeExternalWrites).toEqual([]);
  expect(disallowedNetworkRequests).toEqual([]);
  expect(runtimeFailures).toEqual([]);
});

test("@qa-be-003 messages, profile, and notification settings mutate real synthetic state", async ({
  page,
  baseURL,
}, testInfo) => {
  if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

  const runtimeFailures = collectSanitizedRuntimeFailures(page);
  const allowedOrigins = new Set([
    new URL(baseURL).origin,
    environment.backendApiUrl,
  ]);
  const unsafeExternalWrites = collectUnsafeExternalWrites(
    page,
    allowedOrigins,
  );
  const disallowedNetworkRequests = collectDisallowedNetworkRequests(
    page,
    allowedOrigins,
  );
  const profileSlug = syntheticProfileSlug(testInfo);
  const messageText = `Synthetic portal message ${profileSlug}`;
  const temporaryAddress = `Synthetic QA Address ${profileSlug}`;

  const session = await loginViaPortalUi(
    page,
    environment.clientEmail,
    environment.clientPin,
  );

  await test.step("message send and read use the real client-scoped API", async () => {
    await page.goto("/portal/messages", { waitUntil: "domcontentloaded" });
    await expect(
      page
        .locator("#portal-main-content")
        .getByRole("heading", { name: "Messages" }),
    ).toBeVisible();
    await expect(page.getByText(SYNTHETIC_TEAM_MESSAGE)).toBeVisible();

    const sendResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        url.pathname === "/api/portal/messages" &&
        response.request().method() === "POST"
      );
    });
    await page
      .getByRole("textbox", { name: "Type a message to Bali Zero team" })
      .fill(messageText);
    await page.getByRole("button", { name: "Send message" }).click();
    const sendResponse = await sendResponsePromise;
    expect(sendResponse.status()).toBe(200);
    const sendBody = (await sendResponse.json()) as {
      data?: { id?: unknown };
    };
    if (typeof sendBody.data?.id !== "number") {
      throw new Error("Synthetic message mutation returned no identifier");
    }
    await expect(page.getByText(messageText, { exact: true })).toBeVisible();

    const readResponse = await page.request.post(
      `${environment.backendApiUrl}/api/portal/messages/${sendBody.data.id}/read`,
      { headers: { Authorization: `Bearer ${session.token}` } },
    );
    expect(readResponse.status()).toBe(200);
  });

  await test.step("profile address round-trip persists and restores", async () => {
    await page.goto("/portal/profile", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("heading", { name: "Your Profile" }),
    ).toBeVisible();

    for (const address of [temporaryAddress, SYNTHETIC_PROFILE_ADDRESS]) {
      await page.getByRole("button", { name: "Edit Profile" }).click();
      await page.getByRole("textbox", { name: "Address" }).fill(address);
      const updateResponsePromise = page.waitForResponse((response) => {
        const url = new URL(response.url());
        return (
          url.pathname === "/api/portal/profile" &&
          response.request().method() === "PATCH"
        );
      });
      await page.getByRole("button", { name: "Save Changes" }).click();
      expect((await updateResponsePromise).status()).toBe(200);
      await expect(page.getByText(address, { exact: true })).toBeVisible();
    }
  });

  await test.step("notification preference round-trip persists and restores", async () => {
    await page.goto("/portal/settings?tab=notifications", {
      waitUntil: "domcontentloaded",
    });
    await expect(
      page
        .locator("#portal-main-content")
        .getByRole("heading", { name: "Settings" }),
    ).toBeVisible();
    const emailToggle = page.getByRole("checkbox", {
      name: "Email notifications",
    });
    const waToggle = page.getByRole("checkbox", {
      name: "WhatsApp notifications",
    });
    const waPhone = page.getByRole("textbox", {
      name: "WhatsApp number",
    });
    await expect(emailToggle).toBeChecked();
    await expect(waToggle).not.toBeChecked();
    await expect(waPhone).toHaveValue("");

    await waToggle.click();
    await expect(waToggle).not.toBeChecked();
    await expect(
      page.getByText(
        "Enter a valid WhatsApp number before enabling notifications.",
        { exact: true },
      ),
    ).toBeVisible();

    for (const expectedChecked of [false, true]) {
      const updateResponsePromise = page.waitForResponse((response) => {
        const url = new URL(response.url());
        return (
          url.pathname === "/api/portal/notifications/prefs" &&
          response.request().method() === "PUT"
        );
      });
      await emailToggle.click();
      expect((await updateResponsePromise).status()).toBe(200);
      if (expectedChecked) {
        await expect(emailToggle).toBeChecked();
      } else {
        await expect(emailToggle).not.toBeChecked();
      }
    }

    const phoneResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        url.pathname === "/api/portal/notifications/prefs" &&
        response.request().method() === "PUT"
      );
    });
    await waPhone.fill(SYNTHETIC_WA_PHONE);
    await waPhone.press("Tab");
    expect((await phoneResponsePromise).status()).toBe(200);
    await expect(waToggle).toBeEnabled();

    const enableWaResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        url.pathname === "/api/portal/notifications/prefs" &&
        response.request().method() === "PUT"
      );
    });
    await waToggle.click();
    expect((await enableWaResponsePromise).status()).toBe(200);
    await expect(waToggle).toBeChecked();

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(waToggle).toBeChecked();
    await expect(waPhone).toHaveValue(SYNTHETIC_WA_PHONE);

    const disableWaResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        url.pathname === "/api/portal/notifications/prefs" &&
        response.request().method() === "PUT"
      );
    });
    await waToggle.click();
    expect((await disableWaResponsePromise).status()).toBe(200);
    await expect(waToggle).not.toBeChecked();
    await expect(waPhone).toBeEnabled();

    const clearPhoneResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        url.pathname === "/api/portal/notifications/prefs" &&
        response.request().method() === "PUT"
      );
    });
    await waPhone.fill("");
    await waPhone.press("Tab");
    expect((await clearPhoneResponsePromise).status()).toBe(200);

    const prefsResponse = await page.request.get(
      `${environment.backendApiUrl}/api/portal/notifications/prefs`,
      { headers: { Authorization: `Bearer ${session.token}` } },
    );
    expect(prefsResponse.status()).toBe(200);
    expect(await prefsResponse.json()).toEqual({
      email_enabled: true,
      wa_enabled: false,
      wa_phone: null,
    });

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(emailToggle).toBeChecked();
    await expect(waToggle).not.toBeChecked();
    await expect(waPhone).toHaveValue("");
  });

  await test.step("language preference persists across reload and restores", async () => {
    await page.goto("/portal/settings?tab=language", {
      waitUntil: "domcontentloaded",
    });
    const english = page.getByRole("radio", { name: "English" });
    const italian = page.getByRole("radio", { name: "Italiano" });
    await expect(english).toBeChecked();

    for (const [control, expectedLanguage] of [
      [italian, "it"],
      [english, "en"],
    ] as const) {
      const updateResponsePromise = page.waitForResponse((response) => {
        const url = new URL(response.url());
        return (
          url.pathname === "/api/portal/settings" &&
          response.request().method() === "PATCH"
        );
      });
      await control.click();
      expect((await updateResponsePromise).status()).toBe(200);
      await expect(control).toBeChecked();
      await expect(page.getByText("Language preference saved.")).toBeVisible();

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(
        page.getByRole("radio", {
          name: expectedLanguage === "it" ? "Italiano" : "English",
        }),
      ).toBeChecked();

      const persistedResponse = await page.request.get(
        `${environment.backendApiUrl}/api/portal/settings`,
        { headers: { Authorization: `Bearer ${session.token}` } },
      );
      expect(persistedResponse.status()).toBe(200);
      const persisted = (await persistedResponse.json()) as {
        data?: { language?: unknown };
      };
      expect(persisted.data?.language).toBe(expectedLanguage);
    }

    const invalidResponse = await page.request.patch(
      `${environment.backendApiUrl}/api/portal/settings`,
      {
        headers: { Authorization: `Bearer ${session.token}` },
        data: { language: "fr" },
      },
    );
    expect(invalidResponse.status()).toBe(422);
  });

  await test.step("security control revokes the current session and redirects to sign in", async () => {
    await page.goto("/portal/settings?tab=security", {
      waitUntil: "domcontentloaded",
    });
    await expect(
      page.getByText("including this one", { exact: false }),
    ).toBeVisible();

    const revokeResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        url.pathname === "/api/auth/revoke-all" &&
        response.request().method() === "POST"
      );
    });
    await page.getByRole("button", { name: "Log out all sessions" }).click();
    expect((await revokeResponsePromise).status()).toBe(200);
    await expect(page).toHaveURL(/\/portal\/login-upgraded(?:\?|$)/);
    await expect(
      page.getByRole("textbox", { name: "Corporate Email" }),
    ).toBeVisible();

    const revokedResponse = await page.request.get(
      `${environment.backendApiUrl}/api/portal/dashboard`,
      { headers: { Authorization: `Bearer ${session.token}` } },
    );
    expect(revokedResponse.status()).toBe(401);
  });

  expect(unsafeExternalWrites).toEqual([]);
  expect(disallowedNetworkRequests).toEqual([]);
  expect(runtimeFailures).toEqual([]);
});

test("@qa-be-003 companies, billing, and family render real tenant-scoped records", async ({
  page,
  baseURL,
  isMobile,
}) => {
  if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

  const runtimeFailures = collectSanitizedRuntimeFailures(page);
  const allowedOrigins = new Set([
    new URL(baseURL).origin,
    environment.backendApiUrl,
  ]);
  const unsafeExternalWrites = collectUnsafeExternalWrites(
    page,
    allowedOrigins,
  );
  const disallowedNetworkRequests = collectDisallowedNetworkRequests(
    page,
    allowedOrigins,
  );

  await loginViaPortalUi(page, environment.clientEmail, environment.clientPin);

  await test.step("company list opens the tenant-owned detail", async () => {
    await page.goto("/portal/companies", { waitUntil: "domcontentloaded" });
    const companyCard = page.getByRole("button", {
      name: `View ${SYNTHETIC_COMPANY_NAME} details`,
    });
    await expect(companyCard).toBeVisible();
    await companyCard.click();
    await expect(page).toHaveURL(/\/portal\/company\/\d+$/);
    await expect(
      page.getByRole("heading", { name: SYNTHETIC_COMPANY_NAME }),
    ).toBeVisible();
    await expect(page.getByText("Synthetic Company Service")).toBeVisible();
  });

  await test.step("billing downloads the owned synthetic invoice byte-for-byte", async () => {
    await page.goto("/portal/billing", { waitUntil: "domcontentloaded" });
    await expect(
      page
        .locator("#portal-main-content")
        .getByRole("heading", { name: "Billing" }),
    ).toBeVisible();
    await expect(
      page.getByText(SYNTHETIC_INVOICE_NUMBER, { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("1 invoice", { exact: true })).toBeVisible();
    const downloadButton = page.getByRole("button", {
      name: `Download invoice ${SYNTHETIC_INVOICE_NUMBER}`,
    });
    await expect(downloadButton).toBeVisible();
    const downloadPromise = page.waitForEvent("download");
    await downloadButton.click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(
      `${SYNTHETIC_INVOICE_NUMBER}.pdf`,
    );
    const stream = await download.createReadStream();
    if (!stream)
      throw new Error("Synthetic invoice download stream was unavailable");
    const chunks: Buffer[] = [];
    for await (const chunk of stream) {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    }
    expect(Buffer.concat(chunks).equals(SYNTHETIC_PDF)).toBe(true);
  });

  await test.step("family splits the tenant records into adult and minor", async () => {
    await page.goto("/portal/family", { waitUntil: "domcontentloaded" });
    await expect(
      page
        .locator("#portal-main-content")
        .getByRole("heading", { name: "Family" }),
    ).toBeVisible();
    await expect(page.getByText(SYNTHETIC_ADULT_NAME)).toBeVisible();
    await expect(page.getByText(SYNTHETIC_MINOR_NAME)).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Adults (1)" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Minors (1)" }),
    ).toBeVisible();
  });

  await logoutViaPortalUi(page, isMobile);
  expect(unsafeExternalWrites).toEqual([]);
  expect(disallowedNetworkRequests).toEqual([]);
  expect(runtimeFailures).toEqual([]);
});

test("@qa-be-003 real vault upload and browser download round-trip", async ({
  page,
  baseURL,
}, testInfo) => {
  if (!baseURL) throw new Error("Prod-like frontend base URL is unavailable");

  let expectedUploadFailures = 0;
  let expectedUploadConsoleErrors = 0;
  let uploadFailureWindow = false;
  const runtimeFailures = collectSanitizedRuntimeFailures(
    page,
    (response) => {
      const url = new URL(response.url());
      const isExpected =
        response.status() === 500 &&
        response.request().method() === "POST" &&
        url.pathname === "/api/portal/documents/upload" &&
        expectedUploadFailures === 0;
      if (isExpected) expectedUploadFailures += 1;
      return isExpected;
    },
    (message) => {
      const locationUrl = message.location().url;
      let hasExpectedLocation = locationUrl === "";
      if (locationUrl !== "") {
        try {
          hasExpectedLocation =
            new URL(locationUrl).pathname === "/api/portal/documents/upload";
        } catch {
          hasExpectedLocation = false;
        }
      }
      const isExpected =
        uploadFailureWindow &&
        hasExpectedLocation &&
        expectedUploadConsoleErrors === 0;
      if (isExpected) expectedUploadConsoleErrors += 1;
      return isExpected;
    },
  );
  const allowedOrigins = new Set([
    new URL(baseURL).origin,
    environment.backendApiUrl,
  ]);
  const unsafeExternalWrites = collectUnsafeExternalWrites(
    page,
    allowedOrigins,
  );
  const disallowedNetworkRequests = collectDisallowedNetworkRequests(
    page,
    allowedOrigins,
  );
  const profileSlug = syntheticProfileSlug(testInfo);
  const fileName = `synthetic-portal-upload-${profileSlug}.pdf`;

  const session = await loginViaPortalUi(
    page,
    environment.clientEmail,
    environment.clientPin,
  );
  const initialSupportMailCount = await readSupportMailReceipt(page);
  const initialDocumentReceipt = await readDocumentSinkReceipt(page);
  await page.goto("/portal/vault", { waitUntil: "domcontentloaded" });
  await expect(
    page.getByRole("heading", { name: "Document Vault" }),
  ).toBeVisible();
  await page
    .getByLabel("What is this document for? (optional)")
    .fill("Synthetic portal storage round-trip");

  await armNextDocumentUploadFailure(page);
  uploadFailureWindow = true;
  const rejectedUploadResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/portal/documents/upload" &&
      response.request().method() === "POST"
    );
  });
  await page.getByLabel("Choose file to upload").setInputFiles({
    name: fileName,
    mimeType: "application/pdf",
    buffer: SYNTHETIC_PDF,
  });
  const rejectedUploadResponse = await rejectedUploadResponsePromise;
  expect(rejectedUploadResponse.status()).toBe(500);
  await expect(
    page.getByRole("alert").filter({ hasText: "Upload failed (500)" }),
  ).toBeVisible();
  const retryButton = page.getByRole("button", { name: "Retry upload" });
  await expect(retryButton).toBeVisible();
  expect(await readSupportMailReceipt(page)).toBe(initialSupportMailCount);
  expect(await readDocumentSinkReceipt(page)).toEqual({
    ...initialDocumentReceipt,
    rejectedUploads: initialDocumentReceipt.rejectedUploads + 1,
  });
  await expect(
    page
      .getByRole("list", { name: "Vault files" })
      .getByRole("listitem")
      .filter({ hasText: fileName }),
  ).toHaveCount(0);
  uploadFailureWindow = false;

  const uploadResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/portal/documents/upload" &&
      response.request().method() === "POST"
    );
  });
  await retryButton.click();
  const uploadResponse = await uploadResponsePromise;
  expect(uploadResponse.status()).toBe(200);
  const uploadBody = (await uploadResponse.json()) as {
    data?: { id?: unknown; name?: unknown; processing?: unknown };
  };
  const uploadedDocumentId = uploadBody.data?.id;
  if (typeof uploadedDocumentId !== "number") {
    throw new Error("Synthetic document mutation returned no identifier");
  }
  expect(uploadBody.data?.name).toBe(fileName);
  expect(uploadBody.data?.processing).toBeUndefined();
  await expect(page.getByRole("status")).toContainText(`Uploaded: ${fileName}`);
  await expect
    .poll(() => readSupportMailReceipt(page), { timeout: 10_000 })
    .toBe(initialSupportMailCount + 1);
  const acceptedDocumentReceipt = {
    documents: initialDocumentReceipt.documents + 1,
    uploads: initialDocumentReceipt.uploads + 1,
    downloads: initialDocumentReceipt.downloads,
    rejectedUploads: initialDocumentReceipt.rejectedUploads + 1,
  };
  await expect
    .poll(() => readDocumentSinkReceipt(page), { timeout: 10_000 })
    .toEqual(acceptedDocumentReceipt);

  const fileRow = page
    .getByRole("list", { name: "Vault files" })
    .getByRole("listitem")
    .filter({ hasText: fileName });
  await expect(fileRow).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await fileRow.getByRole("button", { name: "Download" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(fileName);
  const stream = await download.createReadStream();
  if (!stream)
    throw new Error("Synthetic browser download stream was unavailable");
  const chunks: Buffer[] = [];
  for await (const chunk of stream) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  expect(Buffer.concat(chunks).equals(SYNTHETIC_PDF)).toBe(true);
  await expect
    .poll(() => readDocumentSinkReceipt(page), { timeout: 10_000 })
    .toEqual({
      ...acceptedDocumentReceipt,
      downloads: acceptedDocumentReceipt.downloads + 1,
    });

  const deleteResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === `/api/portal/documents/${uploadedDocumentId}` &&
      response.request().method() === "DELETE"
    );
  });
  await fileRow.getByRole("button", { name: `Remove ${fileName}` }).click();
  expect((await deleteResponsePromise).status()).toBe(200);
  const recentlyRemoved = page.getByRole("list", { name: "Recently removed" });
  await expect(recentlyRemoved).toContainText(fileName);

  const restoreResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === `/api/portal/documents/${uploadedDocumentId}/restore` &&
      response.request().method() === "POST"
    );
  });
  await recentlyRemoved.getByRole("button", { name: "Undo" }).click();
  expect((await restoreResponsePromise).status()).toBe(200);
  await expect(fileRow).toBeVisible();

  const timelineResponse = await page.request.get(
    `${environment.backendApiUrl}/api/portal/timeline?limit=100`,
    { headers: { Authorization: `Bearer ${session.token}` } },
  );
  expect(timelineResponse.status()).toBe(200);
  const timelineBody = (await timelineResponse.json()) as {
    data?: {
      entries?: Array<{ title?: unknown; description?: unknown }>;
    };
  };
  expect(timelineBody.data?.entries).toEqual(
    expect.arrayContaining(
      ["Document received", "Document removed", "Document restored"].map(
        (title) =>
          expect.objectContaining({
            title,
            description: expect.stringContaining(fileName),
          }),
      ),
    ),
  );

  expect(unsafeExternalWrites).toEqual([]);
  expect(disallowedNetworkRequests).toEqual([]);
  expect(expectedUploadFailures).toBe(1);
  expect(expectedUploadConsoleErrors).toBeLessThanOrEqual(1);
  expect(runtimeFailures).toEqual([]);
});
