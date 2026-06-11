import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { StatChips } from "./StatChips";

describe("StatChips", () => {
  it("renders buttons for clickable chips and spans for static ones", () => {
    const onClick = vi.fn();
    const { getByRole, getByText } = render(
      <StatChips
        items={[
          { key: "static", content: "12 active" },
          { key: "click", content: "3 unpaid", onClick },
        ]}
      />,
    );
    expect(getByText("12 active").tagName).toBe("SPAN");
    const button = getByRole("button", { name: "3 unpaid" });
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("skips falsy items (inline conditional chips)", () => {
    const { queryByText } = render(
      <StatChips
        items={[false, { key: "kept", content: "kept" }, null, undefined]}
      />,
    );
    expect(queryByText("kept")).toBeTruthy();
    expect(document.querySelectorAll("span").length).toBe(1);
  });

  it("appends per-chip classes to the shared chip base", () => {
    const { getByText } = render(
      <StatChips
        chipClassName="base-chip"
        items={[{ key: "a", content: "chip", className: "extra-class" }]}
      />,
    );
    const el = getByText("chip");
    expect(el.className).toContain("base-chip");
    expect(el.className).toContain("extra-class");
  });
});
