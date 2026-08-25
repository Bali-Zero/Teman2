import { render, screen } from "@testing-library/react";
import { EmptyStampReveal } from "./EmptyStampReveal";

describe("EmptyStampReveal", () => {
  it("renders an accessible role=img with a non-rejecting default label", () => {
    render(<EmptyStampReveal />);
    const stamp = screen.getByRole("img");
    expect(stamp).toBeInTheDocument();
    // Bite: the default label must never use "not for you" / "rejected" language.
    const label = stamp.getAttribute("aria-label") ?? "";
    expect(label).not.toMatch(/not for you/i);
    expect(label).not.toMatch(/rejected/i);
  });

  it("accepts a custom aria-label override", () => {
    render(<EmptyStampReveal ariaLabel="Custom label" />);
    expect(
      screen.getByRole("img", { name: "Custom label" }),
    ).toBeInTheDocument();
  });

  it("carries no visa code or price text — it is wordless by design", () => {
    render(<EmptyStampReveal />);
    // Bite: if a future edit stuffs a price or code into the stamp body,
    // this fails — the stamp must stay a plain dash-glyph placeholder.
    const label = screen.getByTestId("bz-empty-stamp-label");
    expect(label.textContent?.trim()).toBe("— no stamp —");
  });
});
