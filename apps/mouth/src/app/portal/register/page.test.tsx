import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const { mockValidate, mockComplete, mockSearchParams } = vi.hoisted(() => ({
  mockValidate: vi.fn(),
  mockComplete: vi.fn(),
  mockSearchParams: { current: new URLSearchParams("token=tok-1") },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/portal/register",
  useSearchParams: () => mockSearchParams.current,
}));

vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      validateInviteToken: mockValidate,
      completeRegistration: mockComplete,
    },
  },
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

import RegisterPage from "./page";

describe("RegisterPage (WS3 day pass)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams.current = new URLSearchParams("token=tok-1");
  });

  it("valid invite renders the day form: paper shell, card, copper CTA", async () => {
    mockValidate.mockResolvedValue({
      valid: true,
      clientName: "Made Example",
      email: "made@example.com",
    });
    const { container } = render(<RegisterPage />);
    await screen.findByText("Create Your PIN");

    // Shell is paper, not forced-dark.
    const shell = container.querySelector(".min-h-screen");
    expect(shell?.className).toContain("bg-[var(--bz-base)]");

    // Card surface + concept shadow.
    const card = container.querySelector(".rounded-2xl.border");
    expect((card as HTMLElement).style.background).toBe("var(--bz-card)");
    expect((card as HTMLElement).style.boxShadow).toContain(
      "rgba(22, 33, 58, 0.07)",
    );

    // Heading is ink on the card (regression guard: was near-white
    // #E6E7EB on a white slate-50 card — unreadable).
    const h1 = screen.getByText("Create Your PIN");
    expect(h1.className).toContain("text-[var(--tx-pure)]");

    // CTA starts disabled (empty PINs) on the neutral step…
    const cta = screen.getByRole("button", { name: "Activate My Portal" });
    expect(cta.style.background).toBe("var(--bz-border)");

    // …and flips to the darker copper step + theme-aware on-warm fg once
    // both PIN fields are filled.
    fireEvent.change(screen.getByPlaceholderText("Enter PIN"), {
      target: { value: "1234" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm PIN"), {
      target: { value: "1234" },
    });
    expect(cta.style.background).toBe("var(--bz-copper-text)");
    expect(cta.style.color).toBe("var(--bz-on-warm)");

    // Inputs: warm paper + token border.
    const pinInput = screen.getByPlaceholderText("Enter PIN");
    expect(pinInput.className).toContain("bg-[var(--bz-base)]");
    expect(pinInput.className).toContain("border-[var(--bz-border)]");
  });

  it("invalid token renders the danger-toned invalid screen", async () => {
    mockSearchParams.current = new URLSearchParams();
    const { container } = render(<RegisterPage />);
    await screen.findByText("Invalid Invitation");

    const icon = container.querySelector("svg");
    expect(icon?.getAttribute("style")).toContain("var(--state-danger)");

    // Contact support CTA uses the copper pair.
    const cta = screen.getByRole("link", { name: "Contact Support" });
    expect(cta.style.background).toBe("var(--bz-copper-text)");
    expect(cta.style.color).toBe("var(--bz-on-warm)");
  });

  it("PIN mismatch surfaces a --state-danger error box", async () => {
    mockValidate.mockResolvedValue({
      valid: true,
      clientName: "Made Example",
      email: "made@example.com",
    });
    render(<RegisterPage />);
    await screen.findByText("Create Your PIN");

    fireEvent.change(screen.getByPlaceholderText("Enter PIN"), {
      target: { value: "1234" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm PIN"), {
      target: { value: "9999" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Activate My Portal" }));

    const err = await screen.findByText("PINs do not match");
    expect(err.style.color).toBe("var(--state-danger)");
  });

  it("success screen keeps ink text on the card (AA regression guard)", async () => {
    mockValidate.mockResolvedValue({
      valid: true,
      clientName: "Made Example",
      email: "made@example.com",
    });
    mockComplete.mockResolvedValue({ success: true });
    render(<RegisterPage />);
    await screen.findByText("Create Your PIN");

    fireEvent.change(screen.getByPlaceholderText("Enter PIN"), {
      target: { value: "1234" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm PIN"), {
      target: { value: "1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Activate My Portal" }));

    const heading = await screen.findByText("Welcome to Bali Zero!");
    expect(heading.className).toContain("text-[var(--tx-pure)]");
  });

  it("drain guard: no teal, forced-dark or near-white utilities remain", async () => {
    mockValidate.mockResolvedValue({
      valid: true,
      clientName: "Made Example",
      email: "made@example.com",
    });
    const { container } = render(<RegisterPage />);
    await screen.findByText("Create Your PIN");
    const html = container.innerHTML;

    expect(html).not.toContain("#4FD1C5"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(html).not.toContain("#E6E7EB"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(html).not.toContain("#2a2a2a"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(html).not.toContain("#242424"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(html).not.toContain("#0B0E13"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(html).not.toContain("bg-slate-50");
    expect(html).not.toContain("text-muted-cool");
    expect(html).not.toContain("border-white/5");
  });
});
