import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";

import { trackLeadCreated, trackLeadWhatsAppCTA } from "@/lib/analytics";
import { WhatsAppLeadButton, FALLBACK_WA_URL } from "./WhatsAppLeadButton";

vi.mock("@/lib/analytics", () => ({
  trackLeadCreated: vi.fn(),
  trackLeadWhatsAppCTA: vi.fn(),
}));

describe("WhatsAppLeadButton", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    // vi.restoreAllMocks() in afterEach restores spies; it does NOT clear the
    // call history of a vi.fn() from a vi.mock factory (measured: the analytics
    // mock arrived here holding 3 calls from earlier tests). Every pre-existing
    // assertion is toHaveBeenCalledWith, which tolerates leftovers, so nothing
    // caught it until an exact-count assertion was added.
    vi.clearAllMocks();
    global.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        lead_intent_id: "li_1",
        whatsapp_url: "https://wa.me/628213454721?text=tracked",
      }),
    })) as unknown as typeof fetch;
    // stub window.location.href assignment
    Object.defineProperty(window, "location", {
      value: { ...window.location, href: "" },
      writable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    global.fetch = originalFetch;
  });

  function renderButton(source = "kbli_navigator") {
    return render(
      <WhatsAppLeadButton
        source={source}
        resultHash="56303"
        context={{ code: "56303" }}
        whatsappContext={[{ label: "KBLI", value: "56303" }]}
        utm={{ page: "/kbli/56303" }}
      >
        Get started on WhatsApp
      </WhatsAppLeadButton>,
    );
  }

  it("renders children inside an anchor with the bare-link fallback href", () => {
    const { getByRole } = renderButton();
    const link = getByRole("link", { name: /get started on whatsapp/i });
    expect(link.getAttribute("href")).toBe(FALLBACK_WA_URL);
  });

  it("posts the capture payload and navigates to the tracked deeplink", async () => {
    const { getByRole } = renderButton();
    fireEvent.click(getByRole("link"));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/lead/capture",
        expect.objectContaining({ method: "POST" }),
      );
    });
    const body = JSON.parse(
      (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1]
        .body as string,
    );
    expect(body.source).toBe("kbli_navigator");
    expect(body.result_hash).toBe("56303");
    expect(body.whatsapp_context).toEqual([{ label: "KBLI", value: "56303" }]);

    await waitFor(() => {
      expect(window.location.href).toBe(
        "https://wa.me/628213454721?text=tracked",
      );
    });
  });

  it("falls back to the bare wa.me link when capture fails", async () => {
    global.fetch = vi.fn(async () => ({
      ok: false,
      status: 401,
      json: async () => ({}),
    })) as unknown as typeof fetch;

    const { getByRole } = renderButton();
    fireEvent.click(getByRole("link"));

    await waitFor(() => {
      expect(window.location.href).toBe(FALLBACK_WA_URL);
    });
  });

  it("tracks GA4 lead_whatsapp_cta with the intent id on successful capture", async () => {
    const { getByRole } = renderButton();
    fireEvent.click(getByRole("link"));

    await waitFor(() => {
      expect(trackLeadWhatsAppCTA).toHaveBeenCalledWith("kbli_navigator", {
        captured: true,
        lead_intent_id: "li_1",
        result_ref: "56303",
      });
    });
  });

  it("tracks GA4 lead_whatsapp_cta with captured=false on fallback", async () => {
    global.fetch = vi.fn(async () => ({
      ok: false,
      status: 401,
      json: async () => ({}),
    })) as unknown as typeof fetch;

    const { getByRole } = renderButton();
    fireEvent.click(getByRole("link"));

    await waitFor(() => {
      expect(trackLeadWhatsAppCTA).toHaveBeenCalledWith("kbli_navigator", {
        captured: false,
        result_ref: "56303",
      });
    });
  });

  it("fires trackLeadCreated once with the prop source on a captured lead", async () => {
    // "article" rather than the helper default: a component that hardcoded a
    // source instead of forwarding the prop would still pass with the default.
    const { getByRole } = renderButton("article");
    fireEvent.click(getByRole("link"));

    await waitFor(() => {
      expect(trackLeadCreated).toHaveBeenCalledWith("article");
    });
    expect(trackLeadCreated).toHaveBeenCalledTimes(1);
  });

  it("does not fire trackLeadCreated when capture fails", async () => {
    global.fetch = vi.fn(async () => ({
      ok: false,
      status: 401,
      json: async () => ({}),
    })) as unknown as typeof fetch;

    const { getByRole } = renderButton();
    fireEvent.click(getByRole("link"));

    // Anchored to the fallback navigation, not to a bare assertion: without a
    // point the handoff has demonstrably finished, "not called" would also be
    // true of a click that never ran.
    await waitFor(() => {
      expect(window.location.href).toBe(FALLBACK_WA_URL);
    });
    expect(trackLeadCreated).not.toHaveBeenCalled();
  });
});
