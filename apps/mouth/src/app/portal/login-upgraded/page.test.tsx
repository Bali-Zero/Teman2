import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { ReactNode } from "react";
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

// Login behaviour does not depend on animation timing. Keeping this unit test
// on semantic DOM elements also prevents motion's RAF loop from obscuring the
// submit and accessibility assertions.
vi.mock("framer-motion", async () => {
  const React = await vi.importActual<typeof import("react")>("react");
  const makeMotionElement = (tag: "button" | "div" | "form" | "p") =>
    React.forwardRef<
      HTMLElement,
      Record<string, unknown> & { children?: ReactNode }
    >(function MotionElement(
      {
        animate: _animate,
        exit: _exit,
        initial: _initial,
        transition: _transition,
        whileHover: _whileHover,
        whileTap: _whileTap,
        children,
        ...domProps
      },
      ref,
    ) {
      return React.createElement(
        tag,
        { ...domProps, ref },
        children as ReactNode,
      );
    });

  return {
    AnimatePresence: ({ children }: { children?: ReactNode }) => children,
    motion: {
      button: makeMotionElement("button"),
      div: makeMotionElement("div"),
      form: makeMotionElement("form"),
      p: makeMotionElement("p"),
    },
  };
});

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

describe("UpgradedLoginPage (WS3 day pass)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/portal/login-upgraded");
  });

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
      target: { value: "synthetic.user@example.test" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Pass the Portal/ }));

    const pin = await screen.findByLabelText("Access PIN");
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
  });
});
