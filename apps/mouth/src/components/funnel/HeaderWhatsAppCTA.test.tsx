import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { HeaderWhatsAppCTA } from "./HeaderWhatsAppCTA";

describe("HeaderWhatsAppCTA", () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    } as Response);
    document.cookie =
      "bz_session=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  });

  afterEach(() => vi.restoreAllMocks());

  it("renders WA anchor with canonical number", () => {
    render(<HeaderWhatsAppCTA funnel="visa" />);
    const link = screen.getByRole("link", {
      name: /WhatsApp/i,
    }) as HTMLAnchorElement;
    expect(link.href).toBe("https://wa.me/628213107363");
  });

  it.each([
    ["visa", "visa_whatsapp_cta"],
    ["kbli", "kbli_whatsapp_cta"],
    ["tax", "tax_whatsapp_cta"],
    ["property", "property_whatsapp_cta"],
  ] as const)(
    "fires trackFunnelEvent '%s_whatsapp_cta' on click",
    (funnel, expectedEvent) => {
      render(<HeaderWhatsAppCTA funnel={funnel} />);
      fireEvent.click(screen.getByRole("link", { name: /WhatsApp/i }));
      // Allow microtask for getOrCreateSessionId + fetch scheduling
      const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(call[0]).toBe("/api/analytics/funnel-event");
      const body = JSON.parse(call[1].body);
      expect(body.event).toBe(expectedEvent);
      expect(body.payload.trigger).toBe("header");
      expect(body.session_id).toMatch(/^[0-9a-f-]+$/i);
    },
  );
});
