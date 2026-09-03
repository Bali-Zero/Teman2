import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Regression test, same shape as the GARUDA VOA staff client (PR #5605,
 * 2026-09-03): `NEXT_PUBLIC_API_URL` is baked to the Fly backend host
 * (`https://nuzantara-rag.fly.dev`) in production. The order/checkout lane
 * authenticates with the `garuda_session` cookie, `Domain=.balizero.com`
 * (`get_cookie_domain()`, `garuda_portal_auth.py`) — a request built from
 * that env var goes cross-origin and the browser never attaches a cookie
 * scoped to `.balizero.com` to a `nuzantara-rag.fly.dev` request, same class
 * of live 401 as the staff client. The fix hardcodes the same-origin `/api`
 * base, so the client must never read `NEXT_PUBLIC_API_URL` again, even when
 * it is set.
 */
describe("garuda-voa orders api-client base URL", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://nuzantara-rag.fly.dev");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("routes createOrder through the same-origin /api proxy, not NEXT_PUBLIC_API_URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          order_id: "o1",
          state: "awaiting_payment",
          checkout_url: "https://pay.example/checkout/o1",
        }),
        { status: 201, headers: { "content-type": "application/json" } },
      ),
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    const { createOrder } = await import("./api-client");
    await createOrder({
      request: {
        result_id: "r1",
        applicant: {
          full_name: "Jane Doe",
          email: "jane@example.com",
          phone: "+6281234567890",
          passport_number: "X1234567",
        },
        review_confirmed: true,
      },
      idempotencyKey: "key-1",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [calledUrl, calledInit] = fetchMock.mock.calls[0];
    expect(calledUrl).toBe("/api/visa/voa/orders");
    expect(calledUrl).not.toContain("nuzantara-rag.fly.dev");
    expect((calledInit as RequestInit).credentials).toBe("same-origin");
  });

  it("routes getOrderAndPractice through the same-origin /api proxy", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ order_id: "o1", state: "paid", practice: null }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );
    global.fetch = fetchMock as unknown as typeof fetch;

    const { getOrderAndPractice } = await import("./api-client");
    await getOrderAndPractice({ orderId: "o1" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [calledUrl, calledInit] = fetchMock.mock.calls[0];
    expect(calledUrl).toBe("/api/visa/voa/orders/o1");
    expect(calledUrl).not.toContain("nuzantara-rag.fly.dev");
    expect((calledInit as RequestInit).credentials).toBe("same-origin");
  });
});
