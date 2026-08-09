import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ForgotPasswordPage from "./page";

describe("ForgotPasswordPage (WS3 day pass)", () => {
  it("renders the day card: paper shell, token card, serif ink headline", () => {
    const { container } = render(<ForgotPasswordPage />);

    const shell = container.querySelector(".min-h-screen");
    expect(shell?.className).toContain("bg-[var(--bz-base)]");

    const card = container.querySelector(".rounded-2xl.border");
    expect((card as HTMLElement).style.background).toBe("var(--bz-card)");
    expect((card as HTMLElement).style.boxShadow).toContain(
      "rgba(22, 33, 58, 0.07)",
    );

    const h1 = screen.getByText("Recover access");
    expect(h1.className).toContain("text-[var(--tx-pure)]");
  });

  it("mailto CTA uses the copper pair and carries the recovery subject", () => {
    render(<ForgotPasswordPage />);

    const cta = screen.getByRole("link", { name: "Write to the team" });
    expect(cta.style.background).toBe("var(--bz-copper-text)");
    expect(cta.style.color).toBe("var(--bz-on-warm)");
    expect(cta.getAttribute("href")).toContain("mailto:zantara@balizero.com");
    expect(cta.getAttribute("href")).toContain("Portal%20Access%20Recovery");
  });

  it("truthfully explains that recovery starts only after contacting the team", () => {
    render(<ForgotPasswordPage />);

    expect(
      screen.getByText(
        "Contact our team to recover access. No request has been sent yet.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(
        "We received your request. Our team will contact you.",
      ),
    ).not.toBeInTheDocument();
  });

  it("back link reads --bz-copper-text", () => {
    render(<ForgotPasswordPage />);

    const back = screen.getByRole("link", { name: "← Back to login" });
    expect(back.className).toContain("text-[var(--bz-copper-text)]");
    expect(back.getAttribute("href")).toBe("/portal/login-upgraded");
  });

  it("drain guard: no forced-dark shell or gold hexes remain", () => {
    const { container } = render(<ForgotPasswordPage />);
    const html = container.innerHTML;

    expect(html).not.toContain("bg-black");
    expect(html).not.toContain("#c9a96e"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(html).not.toContain("#d9bd7a"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(html).not.toContain("#a07838"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(html).not.toContain("#f0ece4"); // token-lint-ok: drain-guard assertion string, not a color use
  });
});
