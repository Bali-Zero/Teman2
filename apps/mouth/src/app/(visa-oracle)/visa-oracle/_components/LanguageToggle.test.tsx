import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { LanguageToggle } from "./LanguageToggle";

describe("LanguageToggle", () => {
  it("updates document language immediately, keeps compact labels, and restores it on unmount", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    document.documentElement.lang = "fr";
    const view = render(<LanguageToggle language="en" onChange={onChange} />);

    expect(document.documentElement.lang).toBe("en");
    expect(screen.getByText("EN")).toBeInTheDocument();
    expect(screen.getByText("ID")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Switch to Bahasa Indonesia" }),
    );
    expect(document.documentElement.lang).toBe("id");
    expect(onChange).toHaveBeenCalledWith("id");

    view.rerender(<LanguageToggle language="id" onChange={onChange} />);
    expect(document.documentElement.lang).toBe("id");
    view.unmount();
    expect(document.documentElement.lang).toBe("fr");
  });
});
