import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { describe, expect, it, vi } from "vitest";

const { mockRequest } = vi.hoisted(() => ({
  mockRequest: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    request: mockRequest,
  },
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn() },
}));

import NotificationsSettingsPage from "./page";

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

async function renderLoaded() {
  mockRequest.mockResolvedValue({
    email_enabled: true,
    wa_enabled: true,
    wa_phone: "628123456789",
  });
  const utils = renderWithClient(<NotificationsSettingsPage />);
  await screen.findByText("Email");
  return utils;
}

describe("NotificationsSettingsPage (WS3 day pass)", () => {
  it("renders the day masthead: copper rule + Cormorant serif in --tx-pure", async () => {
    const { container } = await renderLoaded();

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Notification preferences");
    expect(heading.style.fontFamily).toBe("var(--font-serif)");
    expect(heading.className).toContain("text-[var(--tx-pure)]");
    expect(
      container.querySelector(
        '[aria-hidden="true"].bg-\\[var\\(--bz-copper\\)\\]',
      ),
    ).not.toBeNull();
    expect(heading.className).not.toContain("lux-text-gradient");
  });

  it("renders channel rows on the warm-paper surface with copper checkboxes", async () => {
    await renderLoaded();

    const emailRow = screen.getByText("Email").closest("label") as HTMLElement;
    expect(emailRow.style.background).toBe("var(--bz-card)");
    expect(emailRow.style.borderColor).toBe("var(--bz-border)");

    const waRow = screen.getByText("WhatsApp").closest("label") as HTMLElement;
    expect(waRow.style.background).toBe("var(--bz-card)");

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(2);
    for (const box of checkboxes) {
      expect(box.className).toContain("accent-[var(--bz-copper)]");
    }
  });

  it("renders the phone input on tokens with a copper focus ring", async () => {
    await renderLoaded();

    const phone = screen.getByLabelText(/WhatsApp number/);
    expect(phone).toHaveValue("628123456789");
    expect(phone.style.background).toBe("var(--bz-card)");
    expect(phone.style.borderColor).toBe("var(--bz-border)");
    expect(phone.className).toContain("focus-visible:ring-[var(--bz-copper)]");
  });

  it("drain guard: no hardcoded hex colors and no legacy --neon-* reads", async () => {
    const { container } = await renderLoaded();
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(container.innerHTML).not.toContain("--neon-");
  });

  it("shows the destructive alert when prefs cannot be loaded", async () => {
    mockRequest.mockRejectedValue(new Error("boom"));
    renderWithClient(<NotificationsSettingsPage />);
    expect(
      await screen.findByText("Unable to load preferences"),
    ).toBeInTheDocument();
  });
});
