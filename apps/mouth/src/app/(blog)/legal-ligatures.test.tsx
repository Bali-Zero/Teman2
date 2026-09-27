import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Cookies from "./cookies/page";
import Privacy from "./privacy/page";
import Terms from "./terms/page";

// R19 Manrope's default ligatures render "Art. 20(c)" as "Art. 20©".
describe("legal pages", () => {
  it.each([Privacy, Terms, Cookies])("keep ligatures off (%#)", (Page) => {
    const { container } = render(<Page />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.style.fontVariantLigatures).toBe("none");
  });
});
