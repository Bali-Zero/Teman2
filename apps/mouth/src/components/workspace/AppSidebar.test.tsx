import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppSidebar } from "./AppSidebar";
import { navigation } from "@/types/navigation";

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
  it("marks the active workspace item with the R19 copper left rule, not a fill", () => {
    // Was: a --bz-sidebar-active-fill background with color "#fff". On R19
    // paper that is white text on a copper fill, and copper is never a fill
    // (concept-K §3). The rule moved to the left border; the assertion moved
    // with it rather than being deleted.
    //
    // Re-pinned for K1c-bis v2: the workspace rail itself is now the fixed
    // ink background (--nav-rail-bg), so the active marker's tokens moved
    // from the warm-paper set (--bz-copper / --bz-card / --tx-pure) to the
    // rail set (--nav-rule / --nav-active-wash / --nav-fg) — same shape
    // (left rule + wash + brighter text), different palette.
    render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={[
          {
            items: [
              { title: "Dashboard", href: "/dashboard", icon: "Home" },
              { title: "Clients", href: "/clients", icon: "Home" },
            ],
          },
        ]}
      />,
    );

    const active = screen.getByRole("link", { name: "Dashboard" });
    expect(active.className).toContain("border-[var(--nav-rule)]");
    expect(active.className).toContain("bg-[var(--nav-active-wash)]");
    expect(active).toHaveStyle({ color: "var(--nav-fg)" });
    // The fill it replaces must not come back.
    expect(active.className).not.toContain("--bz-sidebar-active-fill");
    expect(active.getAttribute("style") ?? "").not.toContain("#fff");
  });

  it("does not give an inactive workspace item the copper rule (innocence)", () => {
    // Re-pinned alongside the active-marker test above: the token moved
    // from --bz-copper to --nav-rule, so the innocence check follows it.
    render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={[
          {
            items: [
              { title: "Dashboard", href: "/dashboard", icon: "Home" },
              { title: "Clients", href: "/clients", icon: "Home" },
            ],
          },
        ]}
      />,
    );

    const inactive = screen.getByRole("link", { name: "Clients" });
    expect(inactive.className).toContain("border-transparent");
    expect(inactive.className).not.toContain("border-[var(--nav-rule)]");
    expect(inactive).toHaveStyle({ color: "var(--nav-fg-muted)" });
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

  // K1c-bis v2 rail: six titled groups, a running 01..13 ordinal instead of
  // an icon, a visible external-link glyph pairing a hidden "new tab" note,
  // and an ink rail background that only the workspace branch paints.

  it("renders the six rail group labels in order (the probe can produce a positive)", () => {
    const { container } = render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={navigation}
      />,
    );
    const labels = [
      "DESK",
      "CLIENT WORK",
      "OPERATIONS",
      "INTELLIGENCE",
      "PEOPLE",
      "SYSTEM",
    ];
    const text = container.textContent ?? "";
    const positions = labels.map((label) => text.indexOf(label));
    expect(positions.every((pos) => pos >= 0)).toBe(true);
    expect(positions).toEqual([...positions].sort((a, b) => a - b));
  });

  it("does not render the six rail labels for a config that doesn't carry them (innocence)", () => {
    render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={[
          {
            title: "Custom Group",
            items: [{ title: "Thing", href: "/thing", icon: "Home" }],
          },
        ]}
      />,
    );
    for (const label of [
      "DESK",
      "CLIENT WORK",
      "OPERATIONS",
      "INTELLIGENCE",
      "PEOPLE",
      "SYSTEM",
    ]) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }
  });

  it("numbers visible items 01..13 across groups without restarting per group", () => {
    const { container } = render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={navigation}
      />,
    );
    // Asserting only that "01".."13" exist SOMEWHERE would also pass with the
    // ordinals out of order, duplicated, or attached to the wrong rows — an
    // adversarial review of this window caught exactly that weakness. So read
    // the rail in DOM order and pin the whole map.
    const rows = [...container.querySelectorAll("nav a[href]")];
    const seen = rows
      .map((a) => {
        const glyph = a.querySelector('[aria-hidden="true"]');
        const n = glyph?.textContent?.trim() ?? "";
        return /^\d\d$/.test(n) ? { n, href: a.getAttribute("href") } : null;
      })
      .filter((x): x is { n: string; href: string | null } => x !== null);

    expect(seen).toEqual([
      { n: "01", href: "/dashboard" },
      { n: "02", href: "/intelligence" },
      { n: "03", href: "/clients" },
      { n: "04", href: "/process" },
      { n: "05", href: "/second-home" },
      { n: "06", href: "/review" },
      { n: "07", href: "/obligations" },
      { n: "08", href: "/lkpm" },
      { n: "09", href: "https://knowledge.balizero.com" },
      { n: "10", href: "/hr" },
      { n: "11", href: "/partners" },
      { n: "12", href: "https://mail.zoho.com/zm/" },
      { n: "13", href: "/settings" },
    ]);
    // Every ordinal is used once — a duplicate would still satisfy the length.
    expect(new Set(seen.map((x) => x.n)).size).toBe(13);
    // "14" would be the first ordinal into the owner-only Da fare section if
    // numbering leaked past 13 — it must not exist.
    expect(screen.queryByText("14")).not.toBeInTheDocument();
  });

  it("the ordinal REPLACES the icon on the workspace rail, it does not join it", () => {
    const { container } = render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={navigation}
      />,
    );
    const rows = [...container.querySelectorAll("nav a[href]")];
    expect(rows.length).toBeGreaterThan(0);
    for (const a of rows) expect(a.querySelector("svg")).toBeNull();
  });

  it("the portal rail keeps its lucide icon and takes no ordinal (innocence)", () => {
    const { container } = render(
      <AppSidebar
        user={{ name: "Portal User", email: "portal@example.test" }}
        onLogout={() => undefined}
        isPortal
        navigationConfig={[
          {
            title: "Services",
            items: [
              { title: "Visa", href: "/portal/visa", icon: "Briefcase" },
              {
                title: "Billing",
                href: "/portal/billing",
                icon: "Receipt",
                badge: 4,
              },
            ],
          },
        ]}
      />,
    );
    const visa = screen.getByRole("link", { name: "Visa" });
    // The icon is the portal's row glyph and it is still there.
    expect(visa.querySelector("svg")).not.toBeNull();
    // And no row carries a two-digit ordinal.
    for (const a of container.querySelectorAll("nav a[href]"))
      expect(/^\d\d$/.test(a.textContent?.trim().slice(0, 2) ?? "")).toBe(
        false,
      );
    // The portal badge keeps its own copper, not the rail's --nav-rule.
    const billing = screen.getByRole("link", { name: /Billing/ });
    expect(billing.innerHTML).toContain("text-[var(--bz-copper)]");
    expect(billing.innerHTML).not.toContain("--nav-rule");
    // The portal group label keeps the portal's own type, not the rail's.
    expect(screen.getByText("Services").className).toContain(
      "text-[var(--tx-secondary)]",
    );
  });

  it("gives the owner-only Da fare items no ordinal at all (innocence)", () => {
    render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={navigation}
      />,
    );
    // "Accounting" is the first Da fare item: its row carries no
    // aria-hidden ordinal glyph at all, not even an empty one.
    const accounting = screen.getByRole("link", { name: "Accounting" });
    expect(accounting.querySelector('[aria-hidden="true"]')).toBeNull();
  });

  it("the active row takes the copper rule and the active wash", () => {
    render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={[
          {
            items: [
              { title: "Dashboard", href: "/dashboard", icon: "Home" },
              { title: "Clients", href: "/clients", icon: "Home" },
            ],
          },
        ]}
      />,
    );
    const active = screen.getByRole("link", { name: "Dashboard" });
    expect(active.className).toContain("bg-[var(--nav-active-wash)]");
    expect(active.className).toContain("border-[var(--nav-rule)]");
  });

  it("an inactive row takes neither the rule nor the wash (innocence)", () => {
    render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={[
          {
            items: [
              { title: "Dashboard", href: "/dashboard", icon: "Home" },
              { title: "Clients", href: "/clients", icon: "Home" },
            ],
          },
        ]}
      />,
    );
    const inactive = screen.getByRole("link", { name: "Clients" });
    // Split into exact class tokens: a substring check would also match the
    // legitimate hover:bg-[var(--nav-active-wash)] class every inactive row
    // carries, which is not the same as the wash applying at rest.
    const classes = inactive.className.split(/\s+/);
    expect(classes).not.toContain("bg-[var(--nav-active-wash)]");
    expect(classes).not.toContain("border-[var(--nav-rule)]");
  });

  it("an external item carries the visible arrow and the hidden new-tab text", () => {
    render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={[
          {
            items: [
              {
                title: "Knowledge",
                href: "https://knowledge.balizero.com",
                icon: "BookOpen",
                external: true,
              },
              { title: "Dashboard", href: "/dashboard", icon: "Home" },
            ],
          },
        ]}
      />,
    );
    const external = screen.getByRole("link", { name: /Knowledge/ });
    // Both this row and "Dashboard" below carry an aria-hidden ordinal glyph
    // too, so the arrow is picked out by its own text, not by "first
    // aria-hidden node".
    const arrow = Array.from(
      external.querySelectorAll('[aria-hidden="true"]'),
    ).find((el) => el.textContent === "↗");
    expect(arrow).toBeDefined();
    expect(external.querySelector(".sr-only")?.textContent).toContain(
      "opens in a new tab",
    );
  });

  it("an internal item carries neither the arrow nor the hidden text (innocence)", () => {
    render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={[
          {
            items: [
              {
                title: "Knowledge",
                href: "https://knowledge.balizero.com",
                icon: "BookOpen",
                external: true,
              },
              { title: "Dashboard", href: "/dashboard", icon: "Home" },
            ],
          },
        ]}
      />,
    );
    const internal = screen.getByRole("link", { name: "Dashboard" });
    // Dashboard still carries its own aria-hidden ordinal glyph (it is not
    // ownerOnly) — the innocence claim is specifically about the arrow.
    const arrow = Array.from(
      internal.querySelectorAll('[aria-hidden="true"]'),
    ).find((el) => el.textContent === "↗");
    expect(arrow).toBeUndefined();
    expect(internal.querySelector(".sr-only")).toBeNull();
  });

  it("the workspace rail paints var(--nav-rail-bg)", () => {
    const { container } = render(
      <AppSidebar
        user={{ name: "Zero", email: "zero@balizero.com" }}
        onLogout={() => undefined}
        navigationConfig={[
          { items: [{ title: "Dashboard", href: "/dashboard", icon: "Home" }] },
        ]}
      />,
    );
    expect(container.querySelector("aside")?.className).toContain(
      "bg-[var(--nav-rail-bg)]",
    );
  });

  it("the portal rail still paints var(--bz-base), proving the portal branch was not dragged along (innocence)", () => {
    const { container } = render(
      <AppSidebar
        user={{ name: "Portal User", email: "portal@example.test" }}
        onLogout={() => undefined}
        isPortal
        navigationConfig={[
          { items: [{ title: "Dashboard", href: "/portal", icon: "Home" }] },
        ]}
      />,
    );
    const asideClassName = container.querySelector("aside")?.className ?? "";
    expect(asideClassName).toContain("bg-[var(--bz-base)]");
    expect(asideClassName).not.toContain("nav-rail-bg");
  });
});
