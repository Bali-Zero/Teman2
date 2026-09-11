import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { TrustBand } from "./TrustBand";

describe("TrustBand", () => {
  // INNOCENCE: the two measured figures must keep rendering.
  it("renders the rating and the review count", () => {
    const { getByText } = render(<TrustBand rating="4.9" reviewCount={1234} />);
    expect(getByText(/4\.9/)).toBeTruthy();
    // 1234, not 693: the real count has no thousands separator today, so a
    // literal 693 here would let `toLocaleString` be deleted without failing.
    expect(getByText("1,234")).toBeTruthy();
  });

  // GUILT: red the moment a third tile comes back, whatever it holds.
  it("renders exactly two tiles", () => {
    const { container } = render(<TrustBand rating="4.9" reviewCount={1234} />);
    const band = container.querySelector('section[aria-label="Trust signals"]');
    expect(band).toBeTruthy();
    expect(band!.children.length).toBe(2);
  });

  // GUILT: the client-count claim must not reappear in any rendered form.
  it("renders no client count", () => {
    const { container } = render(<TrustBand rating="4.9" reviewCount={1234} />);
    expect(container.textContent).not.toMatch(/\bclients?\b/i);
    expect(container.textContent).not.toMatch(/\d[\d,.]*k\+/i);
  });
});
