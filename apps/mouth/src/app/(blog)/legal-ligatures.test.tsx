import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Cookies from "./cookies/page";
import Privacy from "./privacy/page";
import Terms from "./terms/page";

describe("legal pages: ligatures off, so (c) never renders ©", () => {
  it.each([Privacy, Terms, Cookies])("keep ligatures off (%#)", (Page) => {
    const { container } = render(<Page />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.style.fontVariantLigatures).toBe("none");
  });
});
