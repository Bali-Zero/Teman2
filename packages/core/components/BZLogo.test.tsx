import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { BZLogo } from "./BZLogo";

describe("BZLogo", () => {
  it("renders the full logo src when variant='full'", () => {
    const { getByRole } = render(<BZLogo variant="full" />);
    const img = getByRole("img") as HTMLImageElement;
    expect(img.src).toContain("balizero-logo-clean");
    expect(img.alt).toBe("Bali Zero");
  });

  it("renders the mark (3) src when variant='mark'", () => {
    const { getByRole } = render(<BZLogo variant="mark" />);
    const img = getByRole("img") as HTMLImageElement;
    expect(img.src).toContain("balizero-3-red");
  });

  it("renders the zantara lotus src when variant='zantara'", () => {
    const { getByRole } = render(<BZLogo variant="zantara" />);
    const img = getByRole("img") as HTMLImageElement;
    expect(img.src).toContain("zantara-lotus");
    expect(img.alt).toBe("Zantara");
  });

  it("applies size prop to height style", () => {
    const { getByRole } = render(<BZLogo variant="mark" size={32} />);
    const img = getByRole("img") as HTMLImageElement;
    expect(img.style.height).toBe("32px");
  });

  it("has an alt text on every variant (a11y)", () => {
    (["full", "mark", "zantara"] as const).forEach((variant) => {
      const { getByRole, unmount } = render(<BZLogo variant={variant} />);
      const img = getByRole("img") as HTMLImageElement;
      expect(img.alt).not.toBe("");
      unmount();
    });
  });
});
