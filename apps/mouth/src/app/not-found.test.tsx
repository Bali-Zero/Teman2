import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import NotFound from "./not-found";

// Mock Next.js Link component
vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    className,
  }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({ usePathname: () => "/a/b/c" }));
vi.mock("@balizero/core/analytics", () => ({ trackFunnelEvent: vi.fn() }));
vi.mock("@balizero/core/auth", () => ({
  getOrCreateSessionId: () => "test-session",
}));
vi.stubGlobal(
  "matchMedia",
  vi.fn(() => ({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })),
);

describe("NotFound", () => {
  it("renders the R19 404 body: eyebrow, heading and lead", () => {
    render(<NotFound />);

    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.getByText("This page doesn't exist")).toBeInTheDocument();
  });

  it("renders a Home link", () => {
    render(<NotFound />);

    const homeLinks = screen.getAllByRole("link", { name: "Home" });
    expect(homeLinks.some((link) => link.getAttribute("href") === "/")).toBe(
      true,
    );
  });

  it("does not render the old 'Go to Chat' escape hatch", () => {
    render(<NotFound />);

    expect(screen.queryByText("Go to Chat")).not.toBeInTheDocument();
  });

  it("forces the R19 presentation regardless of the (unmatched) pathname", () => {
    const { container } = render(<NotFound />);

    expect(container.querySelector('[data-presentation="r19"]')).not.toBeNull();
  });
});
