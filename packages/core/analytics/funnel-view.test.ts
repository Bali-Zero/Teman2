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

  it("captures the emitting hostname in the backend POST (D3/D9)", async () => {
    await trackFunnelEvent("kbli_code_viewed", {
      sessionId: "abc",
      payload: { code: "47111" },
    });
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse((init as RequestInit).body as string);
    // jsdom default location is http://localhost — what matters is that the
    // field is present and mirrors window.location.hostname.
    expect(body.hostname).toBe(window.location.hostname);
    expect(body.session_id).toBe("abc");
    expect(body.event).toBe("kbli_code_viewed");
  });

  it("whitelist derives from the FUNNEL_EVENTS source — no hardcoded count", () => {
    // Representative events (one per funnel) that must always exist.
    // Containment is asserted per-event off this array — never off a magic number.
    const representative: FunnelEventName[] = [
      "visa_quiz_completed",
      "kbli_code_viewed",
      "tax_dashboard_viewed",
      "property_cta_clicked",
      "book_viewed", // MYTHOS IA-3 scaffolding (emission ships in B4)
      "persona_door_click", // MYTHOS B2 (IA-1) homepage persona doors
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
