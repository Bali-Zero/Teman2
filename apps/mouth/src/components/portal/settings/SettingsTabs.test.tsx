import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const replaceMock = vi.fn();
const searchParamsState = { current: new URLSearchParams() };

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: replaceMock,
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => "/portal/settings",
  useSearchParams: () => searchParamsState.current,
}));

// Stub the child panels so we only assert on the tabs themselves.
vi.mock("./AccountSettings", () => ({
  AccountSettings: () => <div data-testid="panel-account">account</div>,
}));
vi.mock("./SecuritySettings", () => ({
  SecuritySettings: () => <div data-testid="panel-security">security</div>,
}));
vi.mock("./NotificationSettings", () => ({
  NotificationSettings: () => (
    <div data-testid="panel-notifications">notifications</div>
  ),
}));
vi.mock("./PrivacySettings", () => ({
  PrivacySettings: () => <div data-testid="panel-privacy">privacy</div>,
}));
vi.mock("./LanguageSettings", () => ({
  LanguageSettings: () => <div data-testid="panel-language">language</div>,
}));

import { SettingsTabs } from "./SettingsTabs";

describe("SettingsTabs", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    searchParamsState.current = new URLSearchParams();
  });

  it("defaults to account when no tab param is present", () => {
    searchParamsState.current = new URLSearchParams();
    render(<SettingsTabs />);
    const account = screen.getByRole("tab", { name: "Account" });
    expect(account).toHaveAttribute("data-state", "active");
  });

  it("honours ?tab=security", () => {
    searchParamsState.current = new URLSearchParams("tab=security");
    render(<SettingsTabs />);
    const security = screen.getByRole("tab", { name: "Security" });
    expect(security).toHaveAttribute("data-state", "active");
  });

  it("falls back to account for unknown tab values", () => {
    searchParamsState.current = new URLSearchParams("tab=totally-bogus");
    render(<SettingsTabs />);
    const account = screen.getByRole("tab", { name: "Account" });
    expect(account).toHaveAttribute("data-state", "active");
  });
});
