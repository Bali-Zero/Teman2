import { expect, test, type Page } from "@playwright/test";

const LOGIN_ENDPOINT = "**/api/auth/login";

async function openLogin(page: Page, path = "/login"): Promise<void> {
  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });

  await page.goto(path);
  await expect(
    page.getByRole("button", { name: "Authenticate" }),
  ).toBeVisible();
}

async function submitCredentials(page: Page): Promise<void> {
  await page.getByLabel("Identity").fill("operator@balizero.com");
  await page.getByLabel("Security Key").fill("123456");
  await page.getByRole("button", { name: "Authenticate" }).click();
}

test.describe("@offline critical authentication journey", () => {
  test("rejects invalid credentials without creating a browser session", async ({
    page,
  }) => {
    let submittedCredentials: unknown;
    await page.route(LOGIN_ENDPOINT, async (route) => {
      submittedCredentials = route.request().postDataJSON();
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid email or PIN" }),
      });
    });

    await openLogin(page);
    await submitCredentials(page);

    await expect(
      page.getByRole("heading", { name: "Access Denied" }),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
    expect(submittedCredentials).toEqual({
      email: "operator@balizero.com",
      pin: "123456",
    });

    const storedSession = await page.evaluate(() => ({
      token: localStorage.getItem("auth_token"),
      profile: localStorage.getItem("user_profile"),
    }));
    expect(storedSession).toEqual({ token: null, profile: null });

    // The denied overlay is temporary: the operator must be able to retry
    // without refreshing the page.
    await expect(
      page.getByRole("button", { name: "Authenticate" }),
    ).toBeEnabled({
      timeout: 4_000,
    });
  });

  test("persists a successful session and follows the requested local redirect", async ({
    context,
    page,
  }) => {
    await page.route(LOGIN_ENDPOINT, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: {
          "Set-Cookie":
            "nz_access_token=offline-http-only-token; Path=/; HttpOnly; SameSite=Lax",
        },
        body: JSON.stringify({
          success: true,
          message: "Login successful",
          data: {
            token: "offline-browser-token",
            token_type: "Bearer",
            expiresIn: 3_600,
            csrfToken: "offline-csrf-token",
            user: {
              id: "offline-operator",
              email: "operator@balizero.com",
              name: "Offline Operator",
              role: "user",
              status: "active",
            },
          },
        }),
      });
    });

    await openLogin(page, "/login?redirect=/news");
    await submitCredentials(page);

    await expect(
      page.getByRole("heading", { name: "Access Granted" }),
    ).toBeVisible();

    const storedSession = await page.evaluate(() => ({
      token: localStorage.getItem("auth_token"),
      profile: JSON.parse(localStorage.getItem("user_profile") || "null"),
    }));
    expect(storedSession).toMatchObject({
      token: "offline-browser-token",
      profile: {
        id: "offline-operator",
        email: "operator@balizero.com",
        role: "user",
      },
    });

    const cookies = await context.cookies();
    expect(cookies).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          name: "nz_access_token",
          value: "offline-http-only-token",
          httpOnly: true,
        }),
      ]),
    );

    await expect(page).toHaveURL(/\/news$/, { timeout: 5_000 });
  });
});
