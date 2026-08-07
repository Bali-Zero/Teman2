import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { ORACLE_THEME_STORAGE_KEY, ThemeToggle } from "./ThemeToggle";

function setSystemDark(matches: boolean) {
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches }));
}

describe("ThemeToggle", () => {
  beforeEach(() => {
    localStorage.clear();
    setSystemDark(false);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("hydrates from the saved local route preference", async () => {
    localStorage.setItem(ORACLE_THEME_STORAGE_KEY, "dark");
    document.documentElement.setAttribute(
      "data-oracle-theme-bootstrap",
      "dark",
    );
    const onChange = vi.fn();
    const view = render(
      <div className="oracle-root" data-oracle-theme="light">
        <ThemeToggle language="en" theme="light" onChange={onChange} />
      </div>,
    );
    await waitFor(() => expect(onChange).toHaveBeenCalledWith("dark"));
    const root = view.container.querySelector(".oracle-root");
    expect(root).toHaveAttribute("data-oracle-theme", "dark");
    await waitFor(() =>
      expect(root).toHaveAttribute("data-oracle-theme-ready", "true"),
    );

    view.unmount();
    expect(document.documentElement).not.toHaveAttribute(
      "data-oracle-theme-bootstrap",
    );
  });

  it("falls back to system dark and persists an explicit toggle", async () => {
    setSystemDark(true);
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <div className="oracle-root">
        <ThemeToggle language="en" theme="dark" onChange={onChange} />
      </div>,
    );

    await user.click(
      screen.getByRole("button", { name: "Switch between light and dark" }),
    );
    expect(localStorage.getItem(ORACLE_THEME_STORAGE_KEY)).toBe("light");
    expect(onChange).toHaveBeenCalledWith("light");
  });
});
