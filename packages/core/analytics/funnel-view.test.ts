import { describe, it, expect, vi, beforeEach } from "vitest";
import { trackFunnelEvent, FUNNEL_EVENTS } from "./funnel-view";

describe("funnel-view", () => {
  beforeEach(() => {
    vi.stubGlobal("gtag", vi.fn());
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  });

  it("emits gtag + backend dual-track", async () => {
    await trackFunnelEvent("visa_quiz_completed", {
      sessionId: "abc",
      payload: { score: 7 },
    });
    const gtag = globalThis.gtag as unknown as ReturnType<typeof vi.fn>;
    expect(gtag).toHaveBeenCalledWith(
      "event",
      "visa_quiz_completed",
      expect.any(Object),
    );
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/analytics/funnel-event",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("whitelist of events matches the 11 known from CLAUDE.md §473", () => {
    expect(FUNNEL_EVENTS).toContain("visa_quiz_completed");
    expect(FUNNEL_EVENTS).toContain("kbli_code_viewed");
    expect(FUNNEL_EVENTS).toContain("tax_dashboard_viewed");
    expect(FUNNEL_EVENTS).toContain("property_cta_clicked");
    expect(FUNNEL_EVENTS.length).toBe(11);
  });
});
