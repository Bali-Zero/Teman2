import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from "vitest";

const coreMocks = vi.hoisted(() => ({
  trackFunnelEvent: vi.fn(),
  getOrCreateSessionId: vi.fn(() => "core-session-id"),
}));

const loggerMock = vi.hoisted(() => ({
  debug: vi.fn(),
  warn: vi.fn(),
}));

vi.mock("@balizero/core/analytics", () => ({
  trackFunnelEvent: coreMocks.trackFunnelEvent,
}));

vi.mock("@balizero/core/auth", () => ({
  getOrCreateSessionId: coreMocks.getOrCreateSessionId,
}));

vi.mock("./logger", () => ({
  logger: loggerMock,
}));

const fetchMock = global.fetch as Mock;

async function loadAnalytics(): Promise<typeof import("./analytics")> {
  vi.resetModules();
  return import("./analytics");
}

describe("analytics session and event transport", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    coreMocks.trackFunnelEvent.mockReset();
    coreMocks.getOrCreateSessionId.mockReset();
    coreMocks.getOrCreateSessionId.mockReturnValue("core-session-id");
    loggerMock.debug.mockReset();
    loggerMock.warn.mockReset();
    vi.spyOn(Date, "now").mockReturnValue(1_700_000_000_000);
    vi.spyOn(Math, "random").mockReturnValue(0.123456789);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("creates one stable browser session id", async () => {
    const { getSessionId, initializeAnalytics } = await loadAnalytics();

    initializeAnalytics();
    const first = getSessionId();
    const second = getSessionId();

    expect(first).toMatch(/^session-1700000000000-/);
    expect(second).toBe(first);
  });

  it("posts analytics events to the configured endpoint with keepalive", async () => {
    vi.stubEnv("NEXT_PUBLIC_ANALYTICS_ENDPOINT", "https://analytics.test/events");
    fetchMock.mockResolvedValueOnce({ ok: true });
    const { trackEvent } = await loadAnalytics();

    trackEvent("case_opened", { case_id: 42 }, "user-1");

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock).toHaveBeenCalledWith(
      "https://analytics.test/events",
      expect.objectContaining({
        method: "POST",
        keepalive: true,
        body: expect.stringContaining('"event_name":"case_opened"'),
      }),
    );
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body).toMatchObject({
      event_name: "case_opened",
      user_id: "user-1",
      properties: { case_id: 42 },
    });
    expect(body.session_id).toMatch(/^session-1700000000000-/);
  });

  it("does not call fetch when no analytics endpoint is configured", async () => {
    const { trackSearch } = await loadAnalytics();

    trackSearch("villa", 7);

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("logs a warning instead of throwing when event transport rejects", async () => {
    vi.stubEnv("NEXT_PUBLIC_ANALYTICS_ENDPOINT", "https://analytics.test/events");
    fetchMock.mockRejectedValueOnce(new Error("network down"));
    const { trackEvent } = await loadAnalytics();

    trackEvent("case_opened");

    await vi.waitFor(() => expect(loggerMock.warn).toHaveBeenCalledTimes(1));
    expect(loggerMock.warn).toHaveBeenCalledWith(
      "Failed to send analytics event",
      expect.objectContaining({ action: "sendAnalyticsEvent" }),
      expect.any(Error),
    );
  });

  it("tracks CRM helper events with behavior-focused payloads", async () => {
    vi.stubEnv("NEXT_PUBLIC_ANALYTICS_ENDPOINT", "https://analytics.test/events");
    fetchMock.mockResolvedValue({ ok: true });
    const { trackViewModeChange, trackFilterApplied, trackPaginationChange } =
      await loadAnalytics();

    trackViewModeChange("kanban");
    trackFilterApplied("status", "open");
    trackPaginationChange(3, 25);

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const events = fetchMock.mock.calls.map((call) =>
      JSON.parse(call[1].body as string),
    );
    expect(events).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          event_name: "view_mode_changed",
          properties: expect.objectContaining({ view_mode: "kanban" }),
        }),
        expect.objectContaining({
          event_name: "filter_applied",
          properties: expect.objectContaining({
            filter_type: "status",
            filter_value: "open",
          }),
        }),
        expect.objectContaining({
          event_name: "pagination_changed",
          properties: expect.objectContaining({
            page_number: 3,
            items_per_page: 25,
          }),
        }),
      ]),
    );
  });
});

describe("analytics GA4 and funnel events", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    coreMocks.trackFunnelEvent.mockReset();
    coreMocks.getOrCreateSessionId.mockReset();
    coreMocks.getOrCreateSessionId.mockReturnValue("core-session-id");
    loggerMock.debug.mockReset();
    loggerMock.warn.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    delete (window as typeof window & { gtag?: unknown }).gtag;
  });

  it("sends Visa Oracle quiz completion to GA4, local analytics, and funnel tracking", async () => {
    const gtag = vi.fn();
    (window as typeof window & { gtag?: typeof gtag }).gtag = gtag;
    const { trackVisaQuizCompleted } = await loadAnalytics();
    const answers = {
      nationality: "IT",
      purpose: "business",
      duration: "long",
      family: "yes",
    };

    trackVisaQuizCompleted(answers);

    expect(gtag).toHaveBeenCalledWith(
      "event",
      "visa_quiz_completed",
      expect.objectContaining({
        event_category: "VisaOracle",
        nationality: "IT",
      }),
    );
    expect(coreMocks.trackFunnelEvent).toHaveBeenCalledWith(
      "visa_quiz_completed",
      {
        sessionId: "core-session-id",
        payload: answers,
      },
    );
  });

  it("tracks KBLI search funnel payload without exposing the raw query", async () => {
    const gtag = vi.fn();
    (window as typeof window & { gtag?: typeof gtag }).gtag = gtag;
    const { trackKBLISearch } = await loadAnalytics();

    trackKBLISearch("restaurant bali", 12);

    expect(gtag).toHaveBeenCalledWith(
      "event",
      "kbli_search",
      expect.objectContaining({
        event_category: "KBLI",
        query_length: 15,
        result_count: 12,
      }),
    );
    expect(coreMocks.trackFunnelEvent).toHaveBeenCalledWith("kbli_search", {
      sessionId: "core-session-id",
      payload: { query_length: 15, result_count: 12 },
    });
  });

  it("no-ops GA4 when gtag is absent but still records local and funnel events", async () => {
    const { trackPropertyAnalyzeCTA } = await loadAnalytics();

    expect(() => trackPropertyAnalyzeCTA(-8.65, 115.22)).not.toThrow();
    expect(coreMocks.trackFunnelEvent).toHaveBeenCalledWith(
      "property_cta_clicked",
      {
        sessionId: "core-session-id",
        payload: { cta_type: "analyze", lat: -8.65, lng: 115.22 },
      },
    );
  });

  it("tracks property WhatsApp CTA as the property chat funnel event", async () => {
    const gtag = vi.fn();
    (window as typeof window & { gtag?: typeof gtag }).gtag = gtag;
    const { trackPropertyWACTA } = await loadAnalytics();

    trackPropertyWACTA();

    expect(gtag).toHaveBeenCalledWith(
      "event",
      "property_chat_question",
      expect.objectContaining({
        event_category: "Property",
        cta_type: "whatsapp",
      }),
    );
    expect(coreMocks.trackFunnelEvent).toHaveBeenCalledWith(
      "property_chat_question",
      {
        sessionId: "core-session-id",
        payload: { cta_type: "whatsapp" },
      },
    );
  });
});
