import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import MagicLinkRequestPage from "./page";

function mockFetchOnce(status: number) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status } as Response));
}

describe("MagicLinkRequestPage (WS3 day pass)", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the day card: paper shell, token card, serif ink headline", () => {
    const { container } = render(<MagicLinkRequestPage />);

    const shell = container.querySelector(".min-h-screen");
    expect(shell?.className).toContain("bg-[var(--bz-base)]");

    const card = container.querySelector(".rounded-2xl.border");
    expect((card as HTMLElement).style.background).toBe("var(--bz-card)");
    expect((card as HTMLElement).style.boxShadow).toContain(
      "rgba(22, 33, 58, 0.07)",
    );

    const h1 = screen.getByText("Sign in with a link");
    expect(h1.className).toContain("text-[var(--tx-pure)]");
  });

  it("input is warm paper with a copper focus ring; CTA is the copper pair", () => {
    render(<MagicLinkRequestPage />);

    const input = screen.getByLabelText("Email address");
    expect(input.className).toContain("bg-[var(--bz-base)]");
    expect(input.className).toContain("border-[var(--bz-border)]");
    expect(input.className).toContain("focus:border-[var(--bz-copper)]");

    const cta = screen.getByRole("button", { name: "Email me a link" });
    expect(cta.style.background).toBe("var(--bz-copper-text)");
    expect(cta.style.color).toBe("var(--bz-on-warm)");
  });

  it("submits and shows the enumeration-safe confirmation", async () => {
    mockFetchOnce(200);
    render(<MagicLinkRequestPage />);

    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "made@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Email me a link" }));

    const confirmation = await screen.findByRole("status");
    expect(confirmation.textContent).toContain("made@example.com");

    expect(fetch).toHaveBeenCalledWith(
      "/api/auth/request-magic-link",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("5xx shows the --state-danger alert", async () => {
    mockFetchOnce(500);
    render(<MagicLinkRequestPage />);

    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "made@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Email me a link" }));

    const alert = await screen.findByRole("alert");
    expect(alert.style.color).toBe("var(--state-danger)");
  });

  it("drain guard: no forced-dark shell or gold hexes remain", () => {
    const { container } = render(<MagicLinkRequestPage />);
    const html = container.innerHTML;

    expect(html).not.toContain("bg-black");
    expect(html).not.toContain("#c9a96e");
    expect(html).not.toContain("#d9bd7a");
    expect(html).not.toContain("#a07838");
    expect(html).not.toContain("#f0ece4");
    expect(html).not.toContain("#c94a4a");
    expect(html).not.toContain("border-white/15");
    expect(html).not.toContain("bg-white/5");
  });
});
