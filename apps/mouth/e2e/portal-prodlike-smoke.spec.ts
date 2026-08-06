import { expect, test, type Page } from "@playwright/test";

import {
  isDisallowedNetworkRequest,
  isUnsafeWriteRequest,
  loadProdlikeEnvironment,
} from "./support/prodlike-preflight";

const environment = loadProdlikeEnvironment(process.env);

function collectSanitizedRuntimeFailures(page: Page): string[] {
  const failures: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") failures.push("browser console.error");
  });
  page.on("pageerror", () => failures.push("unhandled page error"));
  page.on("response", (response) => {
    if (response.status() >= 500) failures.push("HTTP 5xx response");
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

async function expectActiveDashboardSettled(page: Page): Promise<void> {
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
  await expect(page.getByText("Unable to load dashboard")).toHaveCount(0);
  await expect(page.getByText("Client profile connection needed")).toHaveCount(
    0,
  );
}

test("@qa-e2e-001 real auth, restore, deep link, and logout smoke", async ({
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

  await test.step("real synthetic login", async () => {
    await page.goto("/portal/login-upgraded?redirect=%2Fportal", {
      waitUntil: "domcontentloaded",
    });
    await page
      .getByRole("textbox", { name: "Corporate Email" })
      .fill(environment.clientEmail);
    await page.getByRole("button", { name: "Pass the Portal" }).click();
    await page.getByLabel("Access PIN").fill(environment.clientPin);
    await page.getByRole("button", { name: "Verify Identity" }).click();
    await expectActiveDashboardSettled(page);
  });

  await test.step("session survives refresh", async () => {
    await page.reload({ waitUntil: "domcontentloaded" });
    await expectActiveDashboardSettled(page);
  });

  await test.step("authenticated deep link resolves", async () => {
    await page.goto("/portal/process", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/portal\/process$/);
    await expect(
      page.getByRole("main").getByRole("heading", { name: "My Processes" }),
    ).toBeVisible();
  });

  await test.step("logout revokes the protected session", async () => {
    await page.getByRole("button", { name: "Logout" }).click();
    await expect(page).toHaveURL(/\/portal\/login-upgraded(?:\?|$)/);

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
