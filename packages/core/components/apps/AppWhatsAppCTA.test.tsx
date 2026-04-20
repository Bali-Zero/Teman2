import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import { AppWhatsAppCTA } from "./AppWhatsAppCTA";

describe("AppWhatsAppCTA", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.stubGlobal("navigator", { vibrate: vi.fn(() => true) });
    window.matchMedia = vi.fn().mockImplementation((q: string) => ({
      matches: false,
      media: q,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    global.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        lead_intent_id: "li_1",
        whatsapp_url: "https://wa.me/628213107363?text=hi",
      }),
    })) as any;
    // jsdom has no IntersectionObserver — stub it
    class MockIO {
      constructor(_cb: any) { /* noop */ }
      observe() {}
      unobserve() {}
      disconnect() {}
    }
    vi.stubGlobal("IntersectionObserver", MockIO as any);
    // stub window.location.href assignment
    Object.defineProperty(window, "location", {
      value: { ...window.location, href: "" },
      writable: true,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    global.fetch = originalFetch;
  });

  it("renders the default label before scroll-past", () => {
    const { getByRole } = render(
      <AppWhatsAppCTA
        source="visa_match"
        headline="H"
        description="D"
        whatsappContext={[]}
        defaultLabel="Start on WhatsApp →"
      />,
    );
    expect(getByRole("button").textContent).toContain("Start on WhatsApp");
  });

  it("fires onCaptured after successful lead/capture POST", async () => {
    const onCaptured = vi.fn();
    const { getByRole } = render(
      <AppWhatsAppCTA
        source="visa_match"
        headline="H"
        description="D"
        whatsappContext={[{ label: "V", value: "E33G" }]}
        onCaptured={onCaptured}
      />,
    );
    fireEvent.click(getByRole("button"));
    await waitFor(() => {
      expect(onCaptured).toHaveBeenCalledWith({
        leadIntentId: "li_1",
        whatsappUrl: "https://wa.me/628213107363?text=hi",
      });
    });
  });

  it("calls haptic on click", () => {
    const { getByRole } = render(
      <AppWhatsAppCTA
        source="visa_match"
        headline="H"
        description="D"
        whatsappContext={[]}
      />,
    );
    fireEvent.click(getByRole("button"));
    expect(navigator.vibrate).toHaveBeenCalled();
  });
});
