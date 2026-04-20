import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { AppStampReveal } from "./AppStampReveal";

describe("AppStampReveal", () => {
  it("renders the code as its text content", () => {
    const { getByText } = render(<AppStampReveal code="E33G" />);
    expect(getByText("E33G")).toBeTruthy();
  });

  it("applies a -4deg rotation by default", () => {
    const { getByTestId } = render(<AppStampReveal code="C1" />);
    const stamp = getByTestId("bz-stamp");
    expect(stamp.style.transform).toContain("rotate(-4deg)");
  });

  it("accepts a flat variant that removes rotation", () => {
    const { getByTestId } = render(
      <AppStampReveal code="E33G" variant="flat" />,
    );
    const stamp = getByTestId("bz-stamp");
    expect(stamp.style.transform).not.toContain("rotate(-4deg)");
  });

  it("sets aria-label so screen readers announce the visa code", () => {
    const { getByTestId } = render(<AppStampReveal code="E33G" />);
    const stamp = getByTestId("bz-stamp");
    expect(stamp.getAttribute("aria-label")).toBe("Visa code E33G");
  });
});
