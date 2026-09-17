import { test, expect } from "@playwright/test";

/**
 * GARUDA VOA — self-service deletion from the verdict screen
 * (`products/garuda-voa/journeys/self-service-deletion.feature`,
 * DELIBERA-fase2 lane S6, design-A §2).
 *
 * `/visa/voa/**` is gated server-side by `GARUDA_PUBLIC_ENABLED` (see
 * `src/app/visa/voa/flag.ts` / `layout.tsx`) — this webServer sets it so the
 * route renders instead of 404ing (matches `products/garuda-voa/product.yaml`
 * owner decision 5: the funnel is real, just not yet linked from nav).
 *
 * Backend calls are mocked with `page.route`, mirroring `theme-toggle.spec.ts`'s
 * `seedTheme` pattern — this proves the BROWSER round trip (request fired,
 * headers shaped right, UI reaches the terminal screen), not the FastAPI
 * contract itself (that's `backend/tests/`'s job).
 */

const RESULT_ID = "e2e-voa-delete-hash";

test.describe("GARUDA VOA verdict screen page Page — self-service deletion @offline", () => {
  test("a visitor deletes their own eligibility check and lands on the terminal Deleted screen", async ({
    page,
  }) => {
    let deleteRequestSeen = false;
    let idempotencyKeyHeader: string | undefined;

    await page.route(
      `**/api/visa/voa/eligibility-checks/${RESULT_ID}`,
      async (route) => {
        const method = route.request().method();
        if (method === "GET") {
          await route.fulfill({
            contentType: "application/json",
            body: JSON.stringify({
              verdict: "ACCEPT",
              reason_codes: [],
              price_idr: 790000,
              published_filing_deadline: "2026-09-08",
            }),
          });
          return;
        }
        if (method === "DELETE") {
          deleteRequestSeen = true;
          idempotencyKeyHeader = route.request().headers()["idempotency-key"];
          await route.fulfill({ status: 204 });
          return;
        }
        await route.continue();
      },
    );

    await page.goto(`/visa/voa/${RESULT_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("bz-stamp")).toBeVisible();

    // Tap 1: the quiet link.
    await page.getByRole("button", { name: /delete this check/i }).click();
    await expect(
      page.getByText(/delete this check\? this can't be undone/i),
    ).toBeVisible();

    // Tap 2: confirm.
    await page.getByRole("button", { name: /yes, delete/i }).click();

    // Tap count: 2 — inside the mandate's "≤ 3 taps" budget.
    await expect(page.getByText(/this check has been deleted/i)).toBeVisible();

    expect(deleteRequestSeen).toBe(true);
    expect(idempotencyKeyHeader).toBeTruthy();

    // The terminal screen offers exactly one way back — no dangling controls
    // from the deleted verdict.
    await expect(
      page.getByRole("button", { name: /yes, delete/i }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("link", { name: /start again/i }),
    ).toHaveAttribute("href", "/visa/voa");
  });

  test("Cancel returns to the quiet link without deleting anything", async ({
    page,
  }) => {
    let deleteRequestSeen = false;

    await page.route(
      `**/api/visa/voa/eligibility-checks/${RESULT_ID}`,
      async (route) => {
        const method = route.request().method();
        if (method === "GET") {
          await route.fulfill({
            contentType: "application/json",
            body: JSON.stringify({
              verdict: "ACCEPT",
              reason_codes: [],
              price_idr: 790000,
            }),
          });
          return;
        }
        if (method === "DELETE") {
          deleteRequestSeen = true;
          await route.fulfill({ status: 204 });
          return;
        }
        await route.continue();
      },
    );

    await page.goto(`/visa/voa/${RESULT_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("bz-stamp")).toBeVisible();

    await page.getByRole("button", { name: /delete this check/i }).click();
    await page.getByRole("button", { name: /cancel/i }).click();

    await expect(
      page.getByRole("button", { name: /delete this check/i }),
    ).toBeVisible();
    expect(deleteRequestSeen).toBe(false);
  });
});
