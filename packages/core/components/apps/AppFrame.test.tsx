import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { AppFrame } from "./AppFrame";

describe("AppFrame", () => {
  it("renders title and children", () => {
    const { getByText } = render(
      <AppFrame title="Visa Check">
        <div>BODY</div>
      </AppFrame>,
    );
    expect(getByText("Visa Check")).toBeTruthy();
    expect(getByText("BODY")).toBeTruthy();
  });

  it("sets data-funnel when funnel prop provided", () => {
    const { getByRole } = render(
      <AppFrame title="t" funnel="visa">
        <div>x</div>
      </AppFrame>,
    );
    const section = getByRole("region");
    expect(section.getAttribute("data-funnel")).toBe("visa");
  });

  it("omits data-funnel when no funnel prop provided", () => {
    const { getByRole } = render(
      <AppFrame title="t">
        <div>x</div>
      </AppFrame>,
    );
    expect(getByRole("region").hasAttribute("data-funnel")).toBe(false);
  });
});
