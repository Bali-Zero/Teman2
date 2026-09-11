import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { KBLISectorBrowser } from "./KBLISectorBrowser";
import type { KBLISection } from "@/lib/kbli-types";

const sections: KBLISection[] = [
  {
    id: "A",
    nameEn: "Agriculture",
    nameId: "Pertanian",
    icon: "",
    codeCount: 10,
    description: "",
  },
  {
    id: "C",
    nameEn: "Manufacturing",
    nameId: "Industri",
    icon: "",
    codeCount: 50,
    description: "",
  },
];

describe("KBLISectorBrowser", () => {
  beforeEach(() => window.localStorage.clear());

  it("defaults to the card view (unchanged first paint)", () => {
    render(<KBLISectorBrowser sections={sections} />);
    expect(screen.getByRole("tab", { name: /cards/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    // Cards render the "N codes" label; the table does not.
    expect(screen.getByText("50 codes")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("switches to the table view and keeps every sector reachable", () => {
    render(<KBLISectorBrowser sections={sections} />);
    fireEvent.click(screen.getByRole("tab", { name: /table/i }));

    expect(screen.getByRole("table")).toBeInTheDocument();
    for (const s of sections) {
      expect(screen.getByRole("link", { name: s.nameEn })).toHaveAttribute(
        "href",
        `/kbli/sectors/${s.id}`,
      );
    }
  });

  it("remembers the chosen view across mounts", () => {
    const { unmount } = render(<KBLISectorBrowser sections={sections} />);
    fireEvent.click(screen.getByRole("tab", { name: /table/i }));
    unmount();

    render(<KBLISectorBrowser sections={sections} />);
    expect(screen.getByRole("tab", { name: /table/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("sorts the table by codes, highest first, and reverses on click", () => {
    render(<KBLISectorBrowser sections={sections} />);
    fireEvent.click(screen.getByRole("tab", { name: /table/i }));

    const names = () =>
      screen
        .getAllByRole("row")
        .slice(1)
        .map((r) => (r as HTMLTableRowElement).cells[1].textContent);

    expect(names()).toEqual(["Manufacturing", "Agriculture"]);
    fireEvent.click(screen.getByRole("button", { name: /sort by number/i }));
    expect(names()).toEqual(["Agriculture", "Manufacturing"]);
  });
});
