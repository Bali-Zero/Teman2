import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { TrustBand } from "./TrustBand";

describe("TrustBand", () => {
  it("renders three stat tiles with labels", () => {
    const { getByText } = render(
      <TrustBand clientCount={5000} rating={4.9} responseMinutes={15} />,
    );
    expect(getByText(/5,?000\+|5k\+/)).toBeTruthy();
    expect(getByText(/4\.9/)).toBeTruthy();
    expect(getByText(/15 min/)).toBeTruthy();
  });
});
