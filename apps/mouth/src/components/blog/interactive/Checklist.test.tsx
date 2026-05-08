import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { Checklist } from "./Checklist";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
}));

vi.mock("sonner", () => ({
  toast: {
    info: vi.fn(),
  },
}));

describe("Checklist", () => {
  const items = [
    {
      id: "akta",
      label: "Upload Akta",
      description: "Latest deed scan",
      required: true,
      group: "Documents",
    },
    {
      id: "npwp",
      label: "Confirm NPWP",
      required: true,
      group: "Documents",
    },
    {
      id: "address",
      label: "Verify address",
      group: "Operations",
    },
  ];

  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
    vi.spyOn(window, "print").mockImplementation(() => {});
  });

  it("renders grouped items, required counts, and completion state", () => {
    render(<Checklist id="company-vault" title="Company Vault" items={items} />);

    expect(screen.getByText("Company Vault")).toBeInTheDocument();
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("0 of 3 completed")).toBeInTheDocument();
    expect(screen.getByText("0/2 required")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /upload akta/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirm npwp/i }));
    fireEvent.click(screen.getByRole("button", { name: /verify address/i }));

    expect(screen.getByText("3 of 3 completed")).toBeInTheDocument();
    expect(screen.getByText("2/2 required")).toBeInTheDocument();
    expect(screen.getByText("All items completed!")).toBeInTheDocument();
  });

  it("persists checked items and can reset stored progress", () => {
    const { unmount } = render(
      <Checklist id="persisted" title="Persisted Checklist" items={items} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /upload akta/i }));
    expect(window.localStorage.getItem("checklist-persisted")).toContain("akta");

    unmount();
    render(<Checklist id="persisted" title="Persisted Checklist" items={items} />);
    expect(screen.getByText("1 of 3 completed")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /reset checklist/i }));

    expect(screen.getByText("0 of 3 completed")).toBeInTheDocument();
    expect(window.localStorage.getItem("checklist-persisted")).toBe("[]");
  });

  it("handles print, download, and invalid item configuration", () => {
    const { rerender } = render(
      <Checklist id="actions" title="Actions" items={items} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /print checklist/i }));
    expect(window.print).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: /download checklist as pdf/i }));
    expect(toast.info).toHaveBeenCalledWith(
      "Coming soon",
      expect.objectContaining({
        description: expect.stringContaining("PDF download"),
      }),
    );

    rerender(
      <Checklist
        id="invalid"
        title="Invalid"
        items={undefined as unknown as typeof items}
      />,
    );
    expect(screen.getByText("Configuration required: items array")).toBeInTheDocument();
  });
});
