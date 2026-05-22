import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const loggerMock = vi.hoisted(() => ({
  debug: vi.fn(),
  warn: vi.fn(),
}));

const trackFunnelEventMock = vi.hoisted(() => vi.fn());
const getOrCreateSessionIdMock = vi.hoisted(() =>
  vi.fn(() => "core-session-id"),
);

vi.mock("./logger", () => ({
  logger: loggerMock,
}));

vi.mock("@balizero/core/analytics", () => ({
  trackFunnelEvent: trackFunnelEventMock,
}));

vi.mock("@balizero/core/auth", () => ({
  getOrCreateSessionId: getOrCreateSessionIdMock,
}));

const fetchMock = vi.mocked(global.fetch);

async function loadAnalytics() {
  vi.resetModules();
  return import("./analytics");
}

describe("analytics", () => {
  const originalEndpoint = process.env.NEXT_PUBLIC_ANALYTICS_ENDPOINT;

  beforeEach(() => {
    fetchMock.mockReset();
    loggerMock.debug.mockReset();
    loggerMock.warn.mockReset();
    trackFunnelEventMock.mockReset();
    getOrCreateSessionIdMock.mockClear();
    delete process.env.NEXT_PUBLIC_ANALYTICS_ENDPOINT;
    vi.stubEnv("NODE_ENV", "test");
    delete (window as typeof window & { gtag?: unknown }).gtag;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    if (originalEndpoint === undefined) {
      delete process.env.NEXT_PUBLIC_ANALYTICS_ENDPOINT;
    } else {
      process.env.NEXT_PUBLIC_ANALYTICS_ENDPOINT = originalEndpoint;
    }
  });

  it("creates one browser session id and reuses it", async () => {
    vi.spyOn(Date, "now").mockReturnValue(12345);
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    const { getSessionId } = await loadAnalytics();

    const first = getSessionId();
    const second = getSessionId();

    expect(first).toMatch(/^session-12345-/);
    expect(second).toBe(first);
  });

  it("tracks generic events to the configured endpoint and logs in development", async () => {
    vi.stubEnv("NODE_ENV", "development");
    process.env.NEXT_PUBLIC_ANALYTICS_ENDPOINT = "/analytics";
    fetchMock.mockResolvedValueOnce({ ok: true } as Response);
    const { trackViewModeChange } = await loadAnalytics();

    trackViewModeChange("kanban");

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [, request] = fetchMock.mock.calls[0];
    const body = JSON.parse((request as RequestInit).body as string);

    expect(fetchMock).toHaveBeenCalledWith(
      "/analytics",
      expect.objectContaining({
        method: "POST",
        keepalive: true,
      }),
    );
    expect(body).toMatchObject({
      event_name: "view_mode_changed",
      properties: {
        view_mode: "kanban",
        timestamp: expect.any(Number),
      },
    });
    expect(loggerMock.debug).toHaveBeenCalledWith(
      "Analytics event",
      expect.objectContaining({
        component: "Analytics",
        action: "trackEvent",
      }),
    );
  });

  it("logs a warning without throwing when analytics delivery fails", async () => {
    process.env.NEXT_PUBLIC_ANALYTICS_ENDPOINT = "/analytics";
    fetchMock.mockRejectedValueOnce(new Error("offline"));
    const { trackSearch } = await loadAnalytics();

    expect(() => trackSearch("visa", 4)).not.toThrow();

    await vi.waitFor(() => {
      expect(loggerMock.warn).toHaveBeenCalledWith(
        "Failed to send analytics event",
        expect.objectContaining({
          component: "Analytics",
          action: "sendAnalyticsEvent",
        }),
        expect.any(Error),
      );
    });
  });

  it("dispatches Visa Oracle funnel events to GA4 and the core funnel bus", async () => {
    const gtag = vi.fn();
    (window as typeof window & { gtag?: typeof gtag }).gtag = gtag;
    const { trackVisaQuizCompleted } = await loadAnalytics();

    trackVisaQuizCompleted({
      nationality: "Italy",
      purpose: "business",
      duration: "12 months",
      family: "yes",
    });

    expect(gtag).toHaveBeenCalledWith("event", "visa_quiz_completed", {
      event_category: "VisaOracle",
      nationality: "Italy",
      purpose: "business",
      duration: "12 months",
      family: "yes",
    });
    expect(trackFunnelEventMock).toHaveBeenCalledWith("visa_quiz_completed", {
      sessionId: "core-session-id",
      payload: {
        nationality: "Italy",
        purpose: "business",
        duration: "12 months",
        family: "yes",
      },
    });
  });

  it("dispatches typed funnel CTA events with extra payload", async () => {
    const gtag = vi.fn();
    (window as typeof window & { gtag?: typeof gtag }).gtag = gtag;
    const { trackFunnelCTA, trackPropertyAnalyzeCTA } = await loadAnalytics();

    trackFunnelCTA("kbli", "search_submit", { query_length: 7 });
    trackPropertyAnalyzeCTA(-8.65, 115.22);

    expect(gtag).toHaveBeenCalledWith("event", "kbli_search_submit", {
      event_category: "FunnelCTA",
      funnel: "kbli",
      query_length: 7,
    });
    expect(trackFunnelEventMock).toHaveBeenCalledWith("kbli_search_submit", {
      sessionId: "core-session-id",
      payload: { funnel: "kbli", query_length: 7 },
    });
    expect(gtag).toHaveBeenCalledWith("event", "property_cta_clicked", {
      event_category: "Property",
      cta_type: "analyze",
      lat: -8.65,
      lng: 115.22,
    });
  });
});
