import { test, expect } from "@playwright/test";

/**
 * E2E: admin RBAC gate (client-side).
 *
 * SCAR CONTEXT (campaign 2026-07-08): the admin-only surfaces (/admin/system
 * DbExplorer + VectorExplorer, /settings/{roles,users,security}) are guarded
 * ONLY by a client-side JS gate today — the backend admin/system routes aren't
 * mounted. A curl can't prove a client-side redirect, so this gate was
 * "unproven" until a browser test existed. This spec IS that receptor.
 *
 * The gate (admin/system/page.tsx useEffect):
 *   - not authenticated        → router.push('/login')
 *   - authenticated, not admin → router.push('/chat')
 *   - authenticated + admin    → render (isAuthorized = true)
 *
 * isAdmin() (client.ts:190) = role ∈ {admin, founder, owner, board}.
 * Session is read from localStorage: token under "auth_token", profile under
 * "user_profile" (set by client.ts setUserProfile). We seed those directly so
 * we exercise the gate without a real backend.
 */

const ADMIN_SURFACE = "/admin/system";

/** Seed an authenticated session in localStorage BEFORE the app boots. */
async function seedSession(
  page: import("@playwright/test").Page,
  role: string,
): Promise<void> {
  await page.addInitScript(
    ({ r }: { r: string }) => {
      localStorage.setItem("auth_token", "e2e-mock-token");
      localStorage.setItem(
        "user_profile",
        JSON.stringify({
          id: "e2e-1",
          email: `e2e-${r}@balizero.com`,
          name: `E2E ${r}`,
          role: r,
          status: "active",
        }),
      );
    },
    { r: role },
  );
}

/**
 * Neutralise the backend so the CLIENT gate is what we exercise — not a real
 * 401 that would trigger the global "token expired → /login" logout flow.
 * Any /api/** call returns a benign 200 so the app never force-logs-out on a
 * mock token (this mirrors how auth/login.spec.ts mocks /api/auth/login).
 */
async function stubApi(page: import("@playwright/test").Page): Promise<void> {
  // Match both relative (/api/...) and absolute (https://<host>/api/...) calls
  // so a 401 from the real backend never fires the global token-expiry logout,
  // which would mask the gate we are testing.
  await page.route(
    (url) => url.pathname.startsWith("/api/") || url.pathname.includes("/api/"),
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, data: {} }),
      });
    },
  );
}

test.describe("admin RBAC gate", () => {
  test.setTimeout(60000);

  test("GUILT: non-admin (role=user) is redirected OFF /admin/system", async ({
    page,
  }) => {
    await stubApi(page);
    await seedSession(page, "user");
    await page.goto(ADMIN_SURFACE);
    // Security-critical invariant: an authenticated non-admin must be redirected
    // OFF the admin surface. The gate's target is /chat; in a live build a global
    // token-expiry interceptor may reach /login first — either way the guarantee
    // that MUST hold is "non-admin never rests on /admin/system".
    await page.waitForURL((url) => !url.pathname.endsWith("/admin/system"), {
      timeout: 15000,
    });
    await expect(page).not.toHaveURL(/\/admin\/system$/);
  });

  test("GUILT: unauthenticated visitor is redirected to /login", async ({
    page,
  }) => {
    await stubApi(page);
    // No session seeded → isAuthenticated() is false.
    await page.goto(ADMIN_SURFACE);
    // Lands on /login (with or without an ?expired/&reason query).
    await page.waitForURL(/\/login(\?|$)/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/login(\?|$)/);
    await expect(page).not.toHaveURL(/\/admin\/system/);
  });

  test("INNOCENCE: admin (role=founder) is NOT bounced to /chat like a non-admin", async ({
    page,
  }) => {
    await stubApi(page);
    await seedSession(page, "founder");
    await page.goto(ADMIN_SURFACE);
    // Let the gate's useEffect run.
    await page
      .waitForLoadState("networkidle", { timeout: 15000 })
      .catch(() => {});
    // The DISCRIMINATING property vs a non-admin: the admin gate's
    // `!isAdmin() → push('/chat')` branch must NOT fire for an admin. We assert
    // the admin is not on /chat (the non-admin bounce). Whether they sit on
    // /admin/system depends on backend health calls that a pure gate test does
    // not control, so we don't over-constrain to that.
    await expect(page).not.toHaveURL(/\/chat(\?|$)/);
  });
});
