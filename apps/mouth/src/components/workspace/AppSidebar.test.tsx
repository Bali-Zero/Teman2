import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppSidebar } from "./AppSidebar";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    prefetch,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    children: React.ReactNode;
    href: string;
    prefetch?: boolean;
  }) => (
    <a
      href={href}
      data-prefetch={prefetch === false ? "false" : undefined}
      {...props}
    >
      {children}
    </a>
  ),
}));

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

  it("disables speculative prefetch for protected portal navigation", () => {
    render(
      <AppSidebar
        user={{ name: "Portal User", email: "portal@example.test" }}
        onLogout={() => undefined}
        isPortal
        navigationConfig={[
          {
            items: [
              { title: "Processes", href: "/portal/process", icon: "Home" },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByRole("link", { name: "Processes" })).toHaveAttribute(
      "data-prefetch",
      "false",
    );
    expect(
      screen.getByRole("link", { name: "Bali Zero — workspace home" }),
    ).toHaveAttribute("data-prefetch", "false");
  });
});
