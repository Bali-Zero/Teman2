import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppSidebar } from "./AppSidebar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

describe("AppSidebar", () => {
  it("uses the accessible active-fill token for the current navigation item", () => {
    render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={[
          {
            items: [{ title: "Dashboard", href: "/dashboard", icon: "Home" }],
          },
        ]}
      />,
    );

    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveStyle({
      background: "var(--bz-sidebar-active-fill)",
      color: "#fff",
    });
  });
});
