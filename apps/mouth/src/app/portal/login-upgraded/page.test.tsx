import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockLogin } = vi.hoisted(() => ({ mockLogin: vi.fn() }));

vi.mock("@/lib/api", () => ({
  api: { login: mockLogin },
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

import UpgradedLoginPage from "./page";

describe("UpgradedLoginPage (WS3 day pass)", () => {
  it("shell reads --bz-base and the gate scene carries its re-light class", () => {
    const { container } = render(<UpgradedLoginPage />);

    const shell = container.querySelector(".min-h-screen");
    expect(shell?.className).toContain("bg-[var(--bz-base)]");
    expect(shell?.className).not.toContain("bg-black");

    // The day re-light is scoped to this class via attribute-selector CSS.
    expect(container.querySelector(".gate-scene")).not.toBeNull();
  });

  it("masthead slogan reads day tokens (copper headline: AA on the gate passage)", () => {
    render(<UpgradedLoginPage />);

    // The headline spans the sky AND the dark gate passage: copper-text
    // keeps ≥3:1 large-text contrast on both (3.28:1 on the passage,
    // 5.05:1 on paper) where ink would drop to ~1.2:1 on the passage.
    const h1 = screen.getByText("Your Bali Life.");
    expect(h1.className).toContain("text-[var(--bz-copper-text)]");

    const kicker = screen.getByText("Turn On");
    expect(kicker.className).toContain("text-[var(--bz-copper-text)]");
  });

  it("spotlight card is the token surface; inputs are warm paper with copper focus", () => {
    const { container } = render(<UpgradedLoginPage />);

    const card = container.querySelector(".bg-\\[var\\(--bz-card\\)\\]\\/95");
    expect(card).not.toBeNull();
    expect(card?.className).toContain("border-[var(--bz-border)]");

    const email = screen.getByPlaceholderText("client@company.com");
    expect(email.className).toContain("bg-[var(--bz-base)]");
    expect(email.className).toContain("border-[var(--bz-border)]");
    expect(email.className).toContain("text-[var(--tx-primary)]");
    expect(email.className).toContain("focus:border-[var(--bz-copper)]");
  });

  it("CTA uses the darker copper step + --bz-on-warm (AA pair)", () => {
    render(<UpgradedLoginPage />);

    const cta = screen.getByRole("button", { name: /Pass the Portal/ });
    expect(cta.style.background).toBe("var(--bz-copper-text)");
    expect(cta.style.color).toBe("var(--bz-on-warm)");
  });

  it("email step advances to the PIN step with token-styled controls", async () => {
    render(<UpgradedLoginPage />);

    fireEvent.change(screen.getByPlaceholderText("client@company.com"), {
      target: { value: "made@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Pass the Portal/ }));

    const pin = await screen.findByLabelText("PIN");
    expect(pin.className).toContain("bg-[var(--bz-base)]");
    expect(pin.className).toContain("border-[var(--bz-border)]");

    const verify = screen.getByRole("button", { name: /Verify Identity/ });
    expect(verify.style.background).toBe("var(--bz-copper-text)");
    expect(verify.style.color).toBe("var(--bz-on-warm)");

    const magicLink = screen.getByRole("link", {
      name: /Sign in with an email link instead/,
    });
    expect(magicLink.className).toContain("text-[var(--bz-accent-warm)]");
  });

  it("drain guard: no forced-dark UI utilities or gold hexes outside the scene", () => {
    const { container } = render(<UpgradedLoginPage />);
    const html = container.innerHTML;

    expect(html).not.toContain("text-white");
    expect(html).not.toContain("bg-white/5");
    expect(html).not.toContain("bg-white/10");
    expect(html).not.toContain("from-[#d9bd7a]");
    expect(html).not.toContain("to-[#a07838]");
    expect(html).not.toContain("text-[#f0ece4]");
    expect(html).not.toContain("text-[#f8e89a]");
    expect(html).not.toContain("accent-gold-muted");
  });
});
