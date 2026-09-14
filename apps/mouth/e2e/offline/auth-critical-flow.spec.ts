import { expect, test, type Page } from "@playwright/test";

const LOGIN_ENDPOINT = "**/api/auth/login";

/**
 * Re-pinned for concept-K "SIAP" (SAETTA-R19K K1d). The page no longer says
 * "Identity"/"Security Key"/"Authenticate" and no longer draws the ACCESS
 * GRANTED / ACCESS DENIED overlays, so the copy these tests read had to move.
 * What they PROVE is unchanged and, for the redirect, stronger: the request
 * body, the absence of a session after a refusal, the retry, the stored
 * session and cookie after a success, and the destination.
 */
async function openLogin(page: Page, path = "/login"): Promise<void> {
  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });

  await page.goto(path);
  await expect(page.getByRole("button", { name: "Enter" })).toBeVisible();
}

async function submitCredentials(page: Page): Promise<void> {
  await page.getByLabel("Email").fill("operator@balizero.com");
  await page.getByLabel("PIN").fill("123456");
  await page.getByRole("button", { name: "Enter" }).click();
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

    // The refusal is a sentence in copper, not a black overlay with a word.
    // (getByRole("alert") alone also matches Next's route announcer.)
    await expect(page.getByText(/were not accepted/)).toBeVisible();
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

    // The refusal never locks the form: the operator retries without a reload.
    await expect(page.getByRole("button", { name: "Enter" })).toBeEnabled({
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

    // The destination is reached FIRST and the session read there. The page no
    // longer waits 1500ms before redirecting, so reading storage on the login
    // document races the navigation — and "the session survives the trip" is
    // the stronger claim anyway.
    await expect(page).toHaveURL(/\/news$/, { timeout: 10_000 });

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
  });

  test("refuses a third-party ?redirect= and keeps the operator on this site", async ({
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

    await openLogin(page, "/login?redirect=https://evil.test/steal");
    await submitCredentials(page);

    // The role fallback takes over; the browser never leaves balizero.
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 5_000 });
    expect(new URL(page.url()).hostname).not.toBe("evil.test");
  });
});
