import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const { mockVerify, mockSearchParams } = vi.hoisted(() => ({
  mockVerify: vi.fn(),
  mockSearchParams: { current: new URLSearchParams("token=tok-1") },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/portal/magic",
  useSearchParams: () => mockSearchParams.current,
}));

vi.mock("@/lib/api", () => ({
  api: { verifyMagicLink: mockVerify },
}));

import MagicVerifyPage from "./page";

describe("MagicVerifyPage (WS3 day pass)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams.current = new URLSearchParams("token=tok-1");
  });

  it("verifying state sits on the day card with token text", () => {
    mockVerify.mockReturnValue(new Promise(() => {})); // never resolves
    const { container } = render(<MagicVerifyPage />);

    const shell = container.querySelector(".min-h-screen");
    expect(shell?.className).toContain("bg-[var(--bz-base)]");

    const card = container.querySelector(".rounded-2xl.border");
    expect((card as HTMLElement).style.background).toBe("var(--bz-card)");

    const status = screen.getByRole("status");
    expect(status.className).toContain("text-[var(--tx-secondary)]");
  });

  it("success state reads --state-success", async () => {
    mockVerify.mockResolvedValue(undefined);
    render(<MagicVerifyPage />);

    const ok = await screen.findByText(/Taking you to your portal/);
    expect(ok.className).toContain("text-[var(--state-success)]");
  });

  it("error state offers the copper CTA recovery path", async () => {
    mockSearchParams.current = new URLSearchParams(); // no token → error
    render(<MagicVerifyPage />);

    await screen.findByText("Link not valid");

    const cta = screen.getByRole("link", { name: "Send me a new link" });
    expect(cta.style.background).toBe("var(--bz-copper-text)");
    expect(cta.style.color).toBe("var(--bz-on-warm)");

    const back = screen.getByRole("link", {
      name: "← Sign in with PIN instead",
    });
    expect(back.className).toContain("text-[var(--bz-copper-text)]");
  });

  it("drain guard: no forced-dark shell or gold hexes remain", async () => {
    mockVerify.mockReturnValue(new Promise(() => {}));
    const { container } = render(<MagicVerifyPage />);
    const html = container.innerHTML;

    expect(html).not.toContain("bg-black");
    expect(html).not.toContain("#c9a96e");
    expect(html).not.toContain("#d9bd7a");
    expect(html).not.toContain("#f0ece4");
  });
});
