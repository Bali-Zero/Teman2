import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Regression test, same shape as the GARUDA VOA staff client (PR #5605,
 * 2026-09-03): `NEXT_PUBLIC_API_URL` is baked to the Fly backend host
 * (`https://nuzantara-rag.fly.dev`) in production. This upload lane
 * authenticates with the `garuda_session` cookie, `Domain=.balizero.com`
 * (`get_cookie_domain()`, `garuda_portal_auth.py`) — a request built from
 * that env var goes cross-origin and the browser never attaches a cookie
 * scoped to `.balizero.com` to a `nuzantara-rag.fly.dev` request, same class
 * of live 401 as the staff client. The fix hardcodes the same-origin `/api`
 * base, so the client must never read `NEXT_PUBLIC_API_URL` again, even when
 * it is set.
 */
describe("garuda-voa upload api-client base URL", () => {
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

  it("routes uploadIntakeDocument through the same-origin /api proxy, not NEXT_PUBLIC_API_URL", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ status: "PROCESSING", document_id: "d1" }),
          { status: 202, headers: { "content-type": "application/json" } },
        ),
      );
    global.fetch = fetchMock as unknown as typeof fetch;

    const { uploadIntakeDocument } = await import("./api-client");
    const file = new File(["fake-bytes"], "passport.jpg", {
      type: "image/jpeg",
    });
    await uploadIntakeDocument({
      resultId: "r1",
      file,
      idempotencyKey: "key-1",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [calledUrl, calledInit] = fetchMock.mock.calls[0];
    expect(calledUrl).toBe("/api/visa/voa/eligibility-checks/r1/documents");
    expect(calledUrl).not.toContain("nuzantara-rag.fly.dev");
    expect((calledInit as RequestInit).credentials).toBe("same-origin");
  });
});
