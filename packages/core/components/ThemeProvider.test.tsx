import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, act } from "@testing-library/react";
import { ThemeProvider, useTheme, ThemeScope } from "./ThemeProvider";

function Probe() {
  const { theme, setTheme, funnel, setFunnel } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="funnel">{funnel ?? "none"}</span>
      <button data-testid="set-light" onClick={() => setTheme("light")} />
      <button data-testid="set-kbli" onClick={() => setFunnel("kbli")} />
    </div>
  );
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.removeAttribute("data-funnel");
  });

  it("sets data-theme on <html> when wrapped", () => {
    render(
      <ThemeProvider defaultTheme="dark">
        <Probe />
      </ThemeProvider>,
    );
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("persists theme to localStorage on change", () => {
    const { getByTestId } = render(
      <ThemeProvider defaultTheme="dark">
        <Probe />
      </ThemeProvider>,
    );
    act(() => {
      getByTestId("set-light").click();
    });
    expect(localStorage.getItem("theme")).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("reads theme from localStorage on mount if present", () => {
    localStorage.setItem("theme", "light");
    render(
      <ThemeProvider defaultTheme="dark">
        <Probe />
      </ThemeProvider>,
    );
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("useTheme exposes funnel state and setter", () => {
    const { getByTestId } = render(
      <ThemeProvider defaultTheme="dark">
        <Probe />
      </ThemeProvider>,
    );
    expect(getByTestId("funnel").textContent).toBe("none");
    act(() => {
      getByTestId("set-kbli").click();
    });
    expect(getByTestId("funnel").textContent).toBe("kbli");
    expect(document.documentElement.dataset.funnel).toBe("kbli");
  });
});

describe("ThemeScope", () => {
  it("sets data-funnel on a wrapper div", () => {
    const { container } = render(
      <ThemeScope funnel="kbli">
        <span>content</span>
      </ThemeScope>,
    );
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.getAttribute("data-funnel")).toBe("kbli");
  });
});
