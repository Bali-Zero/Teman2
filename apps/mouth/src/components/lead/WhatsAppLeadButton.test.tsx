import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import { WhatsAppLeadButton, FALLBACK_WA_URL } from "./WhatsAppLeadButton";

describe("WhatsAppLeadButton", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        lead_intent_id: "li_1",
        whatsapp_url: "https://wa.me/6282264599868?text=tracked",
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

  function renderButton() {
    return render(
      <WhatsAppLeadButton
        source="kbli_navigator"
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
        "https://wa.me/6282264599868?text=tracked",
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
});
