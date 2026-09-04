import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Regression test for the live defect measured on kita.balizero.com
 * 2026-09-03: `NEXT_PUBLIC_API_URL` is baked to the Fly backend host
 * (`https://nuzantara-rag.fly.dev`) in production. When the staff client
 * built its URL from that env var, every request went cross-origin —
 * bypassing the Next.js same-origin proxy (`app/api/[...path]/route.ts`)
 * that forwards the `nz_access_token` httpOnly session cookie and promotes
 * `nz_csrf_token` into the `X-CSRF-Token` header for mutating calls — and
 * 401'd. The fix hardcodes the same-origin `/api` base (matching
 * `lib/api/index.ts`'s `API_BASE_URL = ""` and the literal `/api/...` fetch
 * in `(workspace)/review/page.tsx`), so the client must never read
 * `NEXT_PUBLIC_API_URL` again, even when it is set.
 */
describe("garuda-voa staff api-client base URL", () => {
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

  it("routes listStaffPractices through the same-origin /api proxy, not NEXT_PUBLIC_API_URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], next_cursor: null }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    const { listStaffPractices } = await import("./api-client");
    await listStaffPractices({ assigned: "all" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [calledUrl, calledInit] = fetchMock.mock.calls[0];
    expect(calledUrl).toBe("/api/visa/voa/staff/practices?assigned=all");
    expect(calledUrl).not.toContain("nuzantara-rag.fly.dev");
    expect((calledInit as RequestInit).credentials).toBe("same-origin");
  });

  it("routes transitionPractice (mutating call) through the same-origin /api proxy", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          practice_id: "p1",
          state: "assigned",
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    const { transitionPractice } = await import("./api-client");
    await transitionPractice({
      practiceId: "p1",
      request: { transition_id: "PR-02" },
      idempotencyKey: "key-1",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [calledUrl, calledInit] = fetchMock.mock.calls[0];
    expect(calledUrl).toBe("/api/visa/voa/staff/practices/p1/transitions");
    expect(calledUrl).not.toContain("nuzantara-rag.fly.dev");
    expect((calledInit as RequestInit).credentials).toBe("same-origin");
  });
});
