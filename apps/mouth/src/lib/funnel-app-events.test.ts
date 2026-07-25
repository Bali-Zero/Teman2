import { APP_EVENTS, createFunnelAppTracker } from "@balizero/core/analytics";

/**
 * CI enforcement (W0b, 2026-07-23): the module-local copy of these
 * assertions lives in packages/core/analytics/funnel-app.test.ts, but the
 * CI frontend matrix only runs apps/mouth's vitest (include: `src/**`) —
 * packages/core has no CI job and its own vitest config cannot resolve
 * `@vitejs/plugin-react` (pre-existing). This file makes the Law-2 payload
 * shape of `app_form_submit_failed` enforced where CI actually runs, via
 * the same `@balizero/core/analytics` alias the pages import.
 */

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

describe("app_form_submit_failed — Law 2 payload shape (CI guard)", () => {
  beforeEach(() => {
    vi.stubGlobal("gtag", vi.fn());
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({ ok: true });
    document.cookie = "bz_session=; Max-Age=0; path=/";
  });

  it("is registered in APP_EVENTS (backend allowlist parity anchor)", () => {
    // The backend FUNNEL_APP_EVENTS frozenset mirrors APP_EVENTS — enforced
    // bidirectionally by test_analytics_funnel_parity.py.
    expect(APP_EVENTS).toContain("app_form_submit_failed");
  });

  it("emits exactly {type, app, endpoint, status} — nothing else", async () => {
    const tracker = createFunnelAppTracker("visa_match");
    await tracker.formSubmitFailed("/api/visa/match", 503);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.event).toBe("app_form_submit_failed");
    expect(body.payload).toEqual({
      type: "app_form_submit_failed",
      app: "visa_match",
      endpoint: "/api/visa/match",
      status: 503,
    });
    // Law 2 canaries: nothing that resembles an answer value may appear
    // anywhere in the serialized request (payload, session, or hostname).
    const wire = (init as RequestInit).body as string;
    expect(wire).not.toContain("ITA");
    expect(wire).not.toContain("nationality");
    expect(wire).not.toContain("2026-07-01");
  });

  it("network-failure status is null (distinct from any HTTP status)", async () => {
    const tracker = createFunnelAppTracker("visa_clock");
    await tracker.formSubmitFailed("/api/visa/clock", null);

    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.payload.status).toBeNull();
  });
});
