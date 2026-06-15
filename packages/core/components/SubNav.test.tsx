import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { SubNav, type SubNavItem } from "./SubNav";

const Dot = ({ size, className }: { size?: number; className?: string }) => (
  <svg data-testid="dot" width={size} height={size} className={className} />
);

const items: SubNavItem[] = [
  { label: "Dashboard", href: "/hr" },
  { label: "Payroll", href: "/hr/payroll", icon: Dot },
  { label: "Leave", href: "/hr/leave" },
];

describe("SubNav", () => {
  it("renders every item as a link with its href and label", () => {
    const { getByRole } = render(
      <SubNav items={items} pathname="/hr" variant="sidebar" rootHref="/hr" />,
    );
    expect(getByRole("link", { name: "Dashboard" })).toHaveAttribute(
      "href",
      "/hr",
    );
    expect(getByRole("link", { name: "Payroll" })).toHaveAttribute(
      "href",
      "/hr/payroll",
    );
    expect(getByRole("link", { name: "Leave" })).toHaveAttribute(
      "href",
      "/hr/leave",
    );
  });

  it("marks the exact-match item active with aria-current=page", () => {
    const { getByRole } = render(
      <SubNav
        items={items}
        pathname="/hr/payroll"
        variant="sidebar"
        rootHref="/hr"
      />,
    );
    expect(getByRole("link", { name: "Payroll" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(getByRole("link", { name: "Leave" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("treats the rootHref item as active on exact match only", () => {
    const { getByRole } = render(
      <SubNav
        items={items}
        pathname="/hr/leave"
        variant="sidebar"
        rootHref="/hr"
      />,
    );
    // "/hr/leave" startsWith "/hr" but the root item must NOT be active.
    expect(getByRole("link", { name: "Dashboard" })).not.toHaveAttribute(
      "aria-current",
    );
    expect(getByRole("link", { name: "Leave" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("activates non-root items on deep paths via startsWith", () => {
    const { getByRole } = render(
      <SubNav
        items={items}
        pathname="/hr/payroll/2026-06"
        variant="sidebar"
        rootHref="/hr"
      />,
    );
    expect(getByRole("link", { name: "Payroll" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("applies the variant's active/inactive classes and styles", () => {
    const { getByRole } = render(
      <SubNav items={items} pathname="/hr/payroll" variant="tabs" />,
    );
    const active = getByRole("link", { name: "Payroll" });
    const inactive = getByRole("link", { name: "Leave" });
    expect(active.className).toContain("shadow-sm");
    expect(active).toHaveStyle({ color: "var(--bz-accent)" });
    expect(inactive.className).toContain("hover:bg-white/[0.04]");
    expect(inactive).toHaveStyle({ color: "var(--bz-text-2)" });
  });

  it("renders the item icon with the variant icon size", () => {
    const { getByTestId } = render(
      <SubNav items={items} pathname="/hr" variant="sidebar" rootHref="/hr" />,
    );
    expect(getByTestId("dot")).toHaveAttribute("width", "18");
  });

  it("renders through a custom link element via linkAs", () => {
    const CustomLink = ({
      href,
      children,
      ...rest
    }: {
      href: string;
      children?: React.ReactNode;
    }) => (
      <a data-testid="custom" href={href} {...rest}>
        {children}
      </a>
    );
    const { getAllByTestId } = render(
      <SubNav
        items={items}
        pathname="/hr"
        variant="chips"
        linkAs={CustomLink}
      />,
    );
    expect(getAllByTestId("custom")).toHaveLength(3);
  });

  it("marks nothing active when pathname is null", () => {
    const { queryAllByRole } = render(
      <SubNav items={items} pathname={null} variant="chips" rootHref="/hr" />,
    );
    for (const link of queryAllByRole("link")) {
      expect(link).not.toHaveAttribute("aria-current");
    }
  });
});
