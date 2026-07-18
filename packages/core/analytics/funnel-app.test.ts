import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  APP_EVENTS,
  emitFunnelAppEvent,
  createFunnelAppTracker,
  type FunnelAppEvent,
} from "./funnel-app";

describe("funnel-app", () => {
  beforeEach(() => {
    vi.stubGlobal("gtag", vi.fn());
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    document.cookie = "bz_session=; Max-Age=0; path=/";
  });

  it("POSTs session_id (≥32 chars), hostname and the event to the backend", async () => {
    await emitFunnelAppEvent({ type: "app_viewed", app: "visa_clock" });
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/analytics/funnel-event",
      expect.objectContaining({ method: "POST" }),
    );
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse((init as RequestInit).body as string);
    // The backend FunnelEvent model requires session_id (min 32 chars):
    // without it every app_* POST was a silent 422.
    expect(typeof body.session_id).toBe("string");
    expect(body.session_id.length).toBeGreaterThanOrEqual(32);
    expect(body.hostname).toBe(window.location.hostname); // D3/D9
    expect(body.event).toBe("app_viewed");
    expect(body.payload).toMatchObject({
      type: "app_viewed",
      app: "visa_clock",
    });
  });

  it("suppresses the network POST in local mode but keeps gtag", async () => {
    await emitFunnelAppEvent(
      { type: "app_pdf_downloaded", app: "tax_gap" },
      { local: true },
    );
    expect(globalThis.fetch).not.toHaveBeenCalled();
    const gtag = globalThis.gtag as unknown as ReturnType<typeof vi.fn>;
    expect(gtag).toHaveBeenCalledWith(
      "event",
      "app_pdf_downloaded",
      expect.any(Object),
    );
  });

  it("does not block the user flow when analytics delivery fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    await expect(
      emitFunnelAppEvent({ type: "app_viewed", app: "visa_clock" }),
    ).resolves.toBeUndefined();
  });

  it("APP_EVENTS is the exact event-name source of truth for the tracker", async () => {
    // No duplicates, snake_case naming — mirrors funnel-view.test.ts.
    expect(new Set(APP_EVENTS).size).toBe(APP_EVENTS.length);
    for (const event of APP_EVENTS) {
      expect(event).toMatch(/^app(?:_[a-z0-9]+)+$/);
    }

    // Every tracker helper emits an event whose type is in APP_EVENTS.
    const tracker = createFunnelAppTracker("kbli_decoder");
    await tracker.viewed();
    await tracker.branchSelected("pma");
    await tracker.formStarted("sector");
    await tracker.formSubmitted(["sector"]);
    await tracker.wizardStep(1, 3);
    await tracker.wizardAbandoned(2);
    await tracker.resultViewed("abc123");
    await tracker.ctaClicked("Talk to us", "/contact");
    await tracker.whatsappHandoff("lead-1");
    await tracker.shareClicked("copy");
    await tracker.pdfDownloaded();
    await tracker.emailSubscribed("exit_intent");

    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    const emitted = fetchMock.mock.calls.map(
      ([, init]) =>
        (JSON.parse((init as RequestInit).body as string) as { event: string })
          .event,
    );
    expect(emitted).toHaveLength(APP_EVENTS.length);
    expect(new Set(emitted)).toEqual(
      new Set(APP_EVENTS as readonly FunnelAppEvent["type"][]),
    );
  });
});
