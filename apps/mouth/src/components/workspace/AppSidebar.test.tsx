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

  it("shows the owner-only 'Da fare' section to the owner", () => {
    render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={[
          {
            title: "Da fare",
            note: "Pagine vive senza link — da rivedere",
            ownerOnly: true,
            items: [
              { title: "Accounting", href: "/accounting", icon: "Banknote" },
              {
                title: "Funnel Analytics",
                href: "/analytics/funnel",
                icon: "BarChart3",
              },
              {
                title: "GARUDA VOA",
                href: "/garuda-voa",
                icon: "ClipboardCheck",
              },
              {
                title: "Team Activity",
                href: "/admin/team-activity",
                icon: "Activity",
              },
              { title: "Agents", href: "/agents", icon: "BotMessageSquare" },
              {
                title: "Intelligence Analytics",
                href: "/intelligence/analytics",
                icon: "BarChart3",
              },
              {
                title: "Reports",
                href: "/reports",
                icon: "Receipt",
              },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByText("Da fare")).toBeInTheDocument();
    expect(
      screen.getByText("Pagine vive senza link — da rivedere"),
    ).toBeInTheDocument();
    for (const label of [
      "Accounting",
      "Funnel Analytics",
      "GARUDA VOA",
      "Team Activity",
      "Agents",
      "Intelligence Analytics",
      "Reports",
    ]) {
      expect(screen.getByRole("link", { name: label })).toHaveAttribute(
        "href",
        expect.any(String),
      );
    }
  });

  it("hides the owner-only 'Da fare' section from a non-owner admin", () => {
    render(
      <AppSidebar
        user={{ name: "Admin", email: "asya@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={[
          {
            title: "Da fare",
            note: "Pagine vive senza link — da rivedere",
            ownerOnly: true,
            items: [
              { title: "Accounting", href: "/accounting", icon: "Banknote" },
            ],
          },
          {
            title: "Work",
            items: [{ title: "Clients", href: "/clients", icon: "Users" }],
          },
        ]}
      />,
    );

    expect(screen.queryByText("Da fare")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Pagine vive senza link — da rivedere"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Accounting" }),
    ).not.toBeInTheDocument();
    // Innocence: a sibling non-owner-only section on the same navigationConfig
    // still renders — the filter drops only the flagged section, not everything.
    expect(screen.getByRole("link", { name: "Clients" })).toBeInTheDocument();
  });
});
