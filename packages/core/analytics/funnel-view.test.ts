import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  trackFunnelEvent,
  FUNNEL_EVENTS,
  type FunnelEventName,
} from "./funnel-view";

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

  it("whitelist derives from the FUNNEL_EVENTS source — no hardcoded count", () => {
    // Representative events (one per funnel) that must always exist.
    // Containment is asserted per-event off this array — never off a magic number.
    const representative: FunnelEventName[] = [
      "visa_quiz_completed",
      "kbli_code_viewed",
      "tax_dashboard_viewed",
      "property_cta_clicked",
    ];
    for (const event of representative) {
      expect(FUNNEL_EVENTS).toContain(event);
    }

    // Structural invariants derived from the source array itself
    // (mirrors the backend funnel-parity philosophy: assert against
    // FUNNEL_EVENTS.length, not a count that goes stale on every addition).
    expect(FUNNEL_EVENTS.length).toBeGreaterThanOrEqual(representative.length);
    expect(new Set(FUNNEL_EVENTS).size).toBe(FUNNEL_EVENTS.length); // no duplicates
    for (const event of FUNNEL_EVENTS) {
      expect(event).toMatch(/^[a-z0-9]+(?:_[a-z0-9]+)+$/); // snake_case naming
    }
  });
});
