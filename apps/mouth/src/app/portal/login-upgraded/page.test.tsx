import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockLogin, mockLoggerError, mockLoggerInfo, mockRouterReplace } =
  vi.hoisted(() => ({
    mockLogin: vi.fn(),
    mockLoggerError: vi.fn(),
    mockLoggerInfo: vi.fn(),
    mockRouterReplace: vi.fn(),
  }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: mockRouterReplace,
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
}));

vi.mock("@/lib/api/public-auth", () => ({
  publicAuth: { login: mockLogin },
}));

vi.mock("@/lib/logger", () => ({
  logger: {
    error: mockLoggerError,
    info: mockLoggerInfo,
    warn: vi.fn(),
    debug: vi.fn(),
  },
}));

import UpgradedLoginPage from "./page";

describe("UpgradedLoginPage (R19 concept F sign-in)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/portal/login-upgraded");
  });

  it("renders the split gate and no illustration survives", () => {
    const { container } = render(<UpgradedLoginPage />);

    expect(container.querySelector(".r19-gate")).not.toBeNull();
    expect(container.querySelector(".r19-hero")).not.toBeNull();
    // The candi-bentar gate scene, its starfield and its re-light class are gone.
    expect(container.querySelector(".gate-scene")).toBeNull();
    expect(container.querySelector("svg circle")).toBeNull();
  });

  it("the forest panel carries the brand mark and the hero sentence", () => {
    const { container } = render(<UpgradedLoginPage />);

    const hero = container.querySelector(".r19-hero");
    expect(hero).not.toBeNull();
    // The logo asset carries the wordmark; the hero does not repeat it in text.
    expect(hero?.textContent).not.toContain("Bali Zero");
    expect(hero?.textContent).toContain("Client portal");
    expect(hero?.querySelector("h2")?.textContent).toBe(
      "Your Bali file,kept in order.",
    );
    // Zero's order: the real logo, never cropped into a circle.
    const mark = hero?.querySelector("img");
    expect(mark).not.toBeNull();
    expect(mark?.getAttribute("alt")).toBe("Bali Zero");
    expect(mark?.className ?? "").not.toContain("rounded-full");
  });

  it("the email field is the paper form control with a copper focus ring", () => {
    render(<UpgradedLoginPage />);

    const email = screen.getByPlaceholderText("client@company.com");
    expect(email.className).toContain("r19-input");

    const eyebrow = screen.getByText("Sign in · step 1 of 2");
    expect(eyebrow.className).toContain("r19-eyebrow");
  });

  it("the primary CTA is filled forest — copper never fills a button", () => {
    render(<UpgradedLoginPage />);

    const cta = screen.getByRole("button", { name: /Continue/ });
    expect(cta.style.background).toBe("var(--r19-forest)");
    expect(cta.style.color).toBe("var(--r19-paper)");
  });

  it("email step advances to the PIN step with the R19 controls", async () => {
    render(<UpgradedLoginPage />);

    fireEvent.change(screen.getByPlaceholderText("client@company.com"), {
      target: { value: "synthetic.user@example.test" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Continue/ }));

    const pin = await screen.findByLabelText("Access PIN");
    expect(pin.className).toContain("r19-input");
    expect(pin.className).toContain("r19-pin");
    expect(screen.getByText("Sign in · step 2 of 2")).toBeTruthy();

    const verify = screen.getByRole("button", { name: /Verify Identity/ });
    expect(verify.style.background).toBe("var(--r19-forest)");
    expect(verify.style.color).toBe("var(--r19-paper)");

    const magicLink = screen.getByRole("link", {
      name: /Sign in with an email link instead/,
    });
    expect(magicLink.className).toContain("r19-link");
  });

  it("exposes durable labels and password-manager semantics", async () => {
    render(<UpgradedLoginPage />);

    const email = screen.getByRole("textbox", { name: "Corporate Email" });
    expect(email).toHaveAttribute("name", "email");
    expect(email).toHaveAttribute("autocomplete", "username");

    fireEvent.change(email, {
      target: { value: "  synthetic.user@example.test  " },
    });
    fireEvent.submit(email.closest("form")!);

    const pin = await screen.findByLabelText("Access PIN");
    expect(pin).toHaveAttribute("name", "password");
    expect(pin).toHaveAttribute("autocomplete", "current-password");
    expect(pin).toHaveAttribute("minlength", "4");
    expect(pin).toHaveAttribute("maxlength", "8");
  });

  it.each([
    ["/portal/matters?tab=open", "/portal/matters?tab=open"],
    ["https://attacker.example/collect", "/portal"],
    ["//attacker.example/collect", "/portal"],
  ])(
    "routes redirect %s only through the allowlisted same-origin sanitizer",
    async (redirect, expected) => {
      window.history.replaceState(
        {},
        "",
        `/portal/login-upgraded?redirect=${encodeURIComponent(redirect)}`,
      );
      mockLogin.mockResolvedValue({
        access_token: "synthetic-token",
        token_type: "Bearer",
        user: {
          id: "client-1",
          email: "synthetic.user@example.test",
          name: "Synthetic Client",
          role: "client",
        },
        redirectTo: "/portal",
      });
      render(<UpgradedLoginPage />);

      const email = screen.getByRole("textbox", { name: "Corporate Email" });
      fireEvent.change(email, {
        target: { value: "synthetic.user@example.test" },
      });
      fireEvent.submit(email.closest("form")!);

      const pin = await screen.findByLabelText("Access PIN");
      fireEvent.change(pin, { target: { value: "1234" } });

      vi.useFakeTimers();
      try {
        await act(async () => {
          const form = pin.closest("form")!;
          fireEvent.submit(form);
          fireEvent.submit(form);
          await Promise.resolve();
        });

        expect(mockLogin).toHaveBeenCalledTimes(1);
        expect(mockLogin).toHaveBeenCalledWith(
          "synthetic.user@example.test",
          "1234",
        );

        act(() => {
          vi.advanceTimersByTime(1500);
        });
        expect(mockRouterReplace).toHaveBeenCalledWith(expected);
      } finally {
        vi.useRealTimers();
      }
    },
  );

  it("routes a partner to the dedicated portal and rejects a client-only redirect", async () => {
    window.history.replaceState(
      {},
      "",
      "/portal/login-upgraded?redirect=%2Fportal%2Fbilling",
    );
    mockLogin.mockResolvedValue({
      access_token: "synthetic-token",
      token_type: "Bearer",
      user: {
        id: "partner-user-1",
        email: "synthetic.partner@example.test",
        name: "Synthetic Partner",
        role: "partner",
      },
      redirectTo: "/portal/partner/dashboard",
    });
    render(<UpgradedLoginPage />);

    const email = screen.getByRole("textbox", { name: "Corporate Email" });
    fireEvent.change(email, {
      target: { value: "synthetic.partner@example.test" },
    });
    fireEvent.submit(email.closest("form")!);
    const pin = await screen.findByLabelText("Access PIN");
    fireEvent.change(pin, { target: { value: "1234" } });

    vi.useFakeTimers();
    try {
      await act(async () => {
        fireEvent.submit(pin.closest("form")!);
        await Promise.resolve();
      });
      act(() => vi.advanceTimersByTime(1500));
      expect(mockRouterReplace).toHaveBeenCalledWith(
        "/portal/partner/dashboard",
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it("never forwards credentials, email, current URL, or raw auth errors to telemetry", async () => {
    const rawError = Object.assign(new Error("synthetic auth failure"), {
      response: {
        status: 401,
        config: {
          data: {
            email: "synthetic.user@example.test",
            pin: "1234",
          },
        },
      },
    });
    mockLogin.mockRejectedValue(rawError);
    render(<UpgradedLoginPage />);

    const email = screen.getByRole("textbox", { name: "Corporate Email" });
    fireEvent.change(email, {
      target: { value: "synthetic.user@example.test" },
    });
    fireEvent.submit(email.closest("form")!);

    const pin = await screen.findByLabelText("Access PIN");
    fireEvent.change(pin, { target: { value: "1234" } });
    fireEvent.submit(pin.closest("form")!);

    await waitFor(() => {
      expect(mockLoggerInfo).toHaveBeenCalledWith("Login denied", {
        component: "UpgradedLoginPage",
        action: "handleLogin",
        code: 401,
        reason: "portal.login.errors.invalid_credentials",
      });
    });
    expect(mockLoggerInfo).toHaveBeenCalledWith("Login process started", {
      component: "UpgradedLoginPage",
      action: "handleLogin",
    });

    const telemetryPayload = JSON.stringify([
      mockLoggerInfo.mock.calls,
      mockLoggerError.mock.calls,
    ]);
    expect(telemetryPayload).not.toContain("synthetic.user@example.test");
    expect(telemetryPayload).not.toContain("1234");
    expect(telemetryPayload).not.toContain("currentUrl");
    expect(telemetryPayload).not.toContain("config");
  });

  it("renders a generic portal-unavailable denial for an eligible-credential 403", async () => {
    const rawError = Object.assign(
      new Error("private portal eligibility state"),
      { status: 403 },
    );
    mockLogin.mockRejectedValue(rawError);
    render(<UpgradedLoginPage />);

    const email = screen.getByRole("textbox", { name: "Corporate Email" });
    fireEvent.change(email, {
      target: { value: "synthetic.disabled@example.test" },
    });
    fireEvent.submit(email.closest("form")!);

    const pin = await screen.findByLabelText("Access PIN");
    fireEvent.change(pin, { target: { value: "1234" } });
    fireEvent.submit(pin.closest("form")!);

    const denial = await screen.findByRole("alert");
    expect(denial).toHaveTextContent(
      "Portal access is not available for this account. Contact team@balizero.com.",
    );
    expect(denial).not.toHaveTextContent("private portal eligibility state");
    expect(mockRouterReplace).not.toHaveBeenCalled();
    expect(mockLoggerInfo).toHaveBeenCalledWith("Login denied", {
      component: "UpgradedLoginPage",
      action: "handleLogin",
      code: 403,
      reason: "portal.login.errors.portal_unavailable",
    });
  });

  it("drain guard: no forced-dark UI utilities or gold hexes outside the scene", () => {
    const { container } = render(<UpgradedLoginPage />);
    const html = container.innerHTML;

    expect(html).not.toContain("text-white");
    expect(html).not.toContain("bg-white/5");
    expect(html).not.toContain("bg-white/10");
    expect(html).not.toContain("from-[#d9bd7a]"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(html).not.toContain("to-[#a07838]"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(html).not.toContain("text-[#f0ece4]"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(html).not.toContain("text-[#f8e89a]"); // token-lint-ok: drain-guard assertion string, not a color use
    expect(html).not.toContain("accent-gold-muted");
    expect(html).not.toContain("starDrift");
    expect(html).not.toContain("passageGlow");
  });
});
