import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockGetProfile, mockUpdateProfile, mockToastError } = vi.hoisted(
  () => ({
    mockGetProfile: vi.fn(),
    mockUpdateProfile: vi.fn(),
    mockToastError: vi.fn(),
  }),
);

vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getProfile: mockGetProfile,
      updateProfile: mockUpdateProfile,
    },
  },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ error: mockToastError }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn() },
}));

import type { PortalProfile } from "@/lib/api/portal/portal.types";
import ProfilePage from "./page";

const daysFromNow = (days: number) =>
  new Date(Date.now() + days * 86400000).toISOString();

const PROFILE: PortalProfile = {
  id: 7,
  fullName: "Andreas Example",
  email: "andreas@example.com",
  phone: "+6281200000000",
  whatsapp: "6281200000000",
  nationality: "German",
  passportNumber: "C01X00T47",
  passportExpiry: daysFromNow(360), // ~12 months → warning tier
  dateOfBirth: "1985-03-10",
  gender: "M" as const,
  address: "Jl. Example No. 1, Canggu",
  memberSince: "2024-06-01T00:00:00Z",
};

async function renderLoaded(profile = PROFILE) {
  mockGetProfile.mockResolvedValue(profile);
  const utils = render(<ProfilePage />);
  await screen.findByText("Andreas Example");
  return utils;
}

describe("ProfilePage (WS3 day pass)", () => {
  it("renders the day masthead: copper rule + Cormorant serif in --tx-pure", async () => {
    const { container } = await renderLoaded();

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Your Profile");
    expect(heading.style.fontFamily).toBe("var(--font-serif)");
    expect(heading.className).toContain("text-[var(--tx-pure)]");
    expect(
      container.querySelector(
        '[aria-hidden="true"].bg-\\[var\\(--bz-copper\\)\\]',
      ),
    ).not.toBeNull();
  });

  it("renders the profile card on theme surfaces, not the dark glass", async () => {
    const { container } = await renderLoaded();

    expect(container.innerHTML).toContain("var(--bz-card)");
    expect(container.innerHTML).toContain("var(--bz-border)");
    expect(container.innerHTML).not.toContain("rgba(30,30,35,0.7)");
    expect(container.innerHTML).not.toContain("rgba(255,255,255,0.05)");
    expect(container.innerHTML).not.toContain("rgba(255,255,255,0.03)");
  });

  it("colors the passport expiry panel with the semantic state tokens", async () => {
    await renderLoaded(); // 360 days → warning tier

    const label = screen.getByText("Passport Expiry");
    const panel = label.closest("div.rounded-lg") as HTMLElement;
    expect(panel.style.background).toContain("var(--state-warning)");
    expect(panel.style.background).toContain("color-mix");
    expect(panel.style.borderColor).toContain("var(--state-warning)");

    // Alert copy reads the warning state token (was text-yellow-400).
    const alert = screen.getByText(/expires in less than 14 months/);
    expect(alert.style.color).toBe("var(--state-warning)");
  });

  it("escalates to the danger token when the passport is critical", async () => {
    await renderLoaded({ ...PROFILE, passportExpiry: daysFromNow(180) });

    const alert = screen.getByText(/URGENT: Your passport expires/);
    expect(alert.style.color).toBe("var(--state-danger)");

    const label = screen.getByText("Passport Expiry");
    const panel = label.closest("div.rounded-lg") as HTMLElement;
    expect(panel.style.borderColor).toContain("var(--state-danger)");
  });

  it("marks muted fields with the AA text token + italic (not --bz-text-3)", async () => {
    await renderLoaded({ ...PROFILE, phone: undefined, whatsapp: undefined });

    // --bz-text-3 (#7a8aa6) is 3.49:1 on the card — below the 4.5:1 floor
    // for small text — so muted values read --bz-text-2 with italic.
    const muted = screen.getAllByText("Not provided")[0];
    expect(muted.style.color).toBe("var(--bz-text-2)");
    expect(muted.className).toContain("italic");
  });

  it("renders the edit form on tokens and saves via the portal API", async () => {
    await renderLoaded();

    fireEvent.click(screen.getByRole("button", { name: "Edit Profile" }));

    const phoneInput = screen.getByLabelText("Phone");
    expect(phoneInput.style.background).toBe("var(--glass-rim)");
    expect(phoneInput.style.borderColor).toBe("var(--bz-border)");
    expect(phoneInput.style.color).toBe("var(--bz-text-1)");
    expect(phoneInput.className).toContain(
      "focus-visible:ring-[var(--bz-copper)]",
    );

    mockUpdateProfile.mockResolvedValue(PROFILE);
    fireEvent.change(phoneInput, { target: { value: "+628999" } });
    // act() flush: the save handler is async (await api → setState/toast).
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
    });
    expect(mockUpdateProfile).toHaveBeenCalledWith(
      expect.objectContaining({ phone: "+628999" }),
    );
  });

  it("drain guard: no hardcoded hex colors anywhere in the page output", async () => {
    const { container } = await renderLoaded();
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it("renders the unable-to-load empty state on token surfaces", async () => {
    mockGetProfile.mockResolvedValue(null);
    const { container } = render(<ProfilePage />);
    expect(
      await screen.findByText("Unable to load profile"),
    ).toBeInTheDocument();
    expect(container.innerHTML).not.toContain("rgba(30,30,35,0.7)");
    // Masthead survives the empty state.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Your Profile",
    );
  });
});
