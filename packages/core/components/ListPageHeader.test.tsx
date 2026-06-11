import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ListPageHeader } from "./ListPageHeader";

describe("ListPageHeader", () => {
  it("renders title, subtitle and actions", () => {
    const { getByText, getByRole } = render(
      <ListPageHeader
        title="Clients"
        subtitle="42 clients"
        actions={<button>New Client</button>}
      />,
    );
    expect(getByRole("heading", { level: 1 }).textContent).toBe("Clients");
    expect(getByText("42 clients")).toBeTruthy();
    expect(getByRole("button", { name: "New Client" })).toBeTruthy();
  });

  it("omits subtitle and actions wrappers when not provided", () => {
    const { container } = render(<ListPageHeader title="Process" />);
    expect(container.querySelector("p")).toBeNull();
    expect(container.querySelectorAll(":scope > div > div").length).toBe(1);
  });
});
