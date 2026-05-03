import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PrivacySettings } from "./PrivacySettings";

describe("PrivacySettings", () => {
  it("renders data-export mailto link with correct subject", () => {
    render(<PrivacySettings />);
    const link = screen.getByRole("link", { name: /request data export/i });
    const href = link.getAttribute("href") ?? "";
    expect(href.startsWith("mailto:team@balizero.com")).toBe(true);
    expect(href).toContain(
      `subject=${encodeURIComponent("Data export request")}`,
    );
  });

  it("renders account-deletion mailto link with correct subject", () => {
    render(<PrivacySettings />);
    const link = screen.getByRole("link", {
      name: /request account deletion/i,
    });
    const href = link.getAttribute("href") ?? "";
    expect(href.startsWith("mailto:team@balizero.com")).toBe(true);
    expect(href).toContain(
      `subject=${encodeURIComponent("Account deletion request")}`,
    );
  });
});
