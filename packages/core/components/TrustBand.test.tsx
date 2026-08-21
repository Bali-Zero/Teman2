import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { TrustBand } from "./TrustBand";

describe("TrustBand", () => {
  it("renders three stat tiles with labels", () => {
    const { getByText } = render(
      <TrustBand clientCount={5000} rating="4.9" reviewCount={1234} />,
    );
    expect(getByText(/5,?000\+|5k\+/)).toBeTruthy();
    expect(getByText(/4\.9/)).toBeTruthy();
    // 1234, not 693: the real count has no thousands separator yet, so a
    // literal 693 here would let `toLocaleString` be deleted without failing.
    expect(getByText("1,234")).toBeTruthy();
  });
});
