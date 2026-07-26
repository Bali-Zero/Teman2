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
    expect(localStorage.getItem("bz-theme")).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("writes ONLY bz-theme — the legacy `theme` mirror is never resurrected", () => {
    // WS4: two keys meant the applied theme depended on which writer ran last.
    const { getByTestId } = render(
      <ThemeProvider defaultTheme="dark">
        <Probe />
      </ThemeProvider>,
    );
    act(() => {
      getByTestId("set-light").click();
    });
    expect(localStorage.getItem("theme")).toBeNull();
  });

  it("reads theme from localStorage on mount if present", () => {
    localStorage.setItem("bz-theme", "light");
    render(
      <ThemeProvider defaultTheme="dark">
        <Probe />
      </ThemeProvider>,
    );
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("respects the pre-paint data-theme (persona-aware) over defaultTheme", () => {
    // Simulates the pre-paint themeInitScript on my.balizero.com: it set
    // data-theme=operative-light by hostname BEFORE React hydrated. The
    // provider must NOT clobber it with defaultTheme=editorial.
    document.documentElement.dataset.theme = "operative-light";
    const { getByTestId } = render(
      <ThemeProvider defaultTheme="editorial">
        <Probe />
      </ThemeProvider>,
    );
    expect(document.documentElement.dataset.theme).toBe("operative-light");
    expect(getByTestId("theme").textContent).toBe("operative-light");
  });

  it("localStorage('bz-theme') still wins over the pre-paint value", () => {
    // Explicit user choice beats the hostname default.
    document.documentElement.dataset.theme = "operative-light";
    localStorage.setItem("bz-theme", "dark");
    render(
      <ThemeProvider defaultTheme="editorial">
        <Probe />
      </ThemeProvider>,
    );
    expect(document.documentElement.dataset.theme).toBe("dark");
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

describe("ThemeProvider — legacy `theme` key migration (WS4)", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  function mount(defaultTheme: "dark" | "editorial" = "editorial") {
    return render(
      <ThemeProvider defaultTheme={defaultTheme}>
        <Probe />
      </ThemeProvider>,
    );
  }

  it("carries a saved legacy value over to bz-theme, then drops the old key", () => {
    // The whole point of the migration: nobody loses a saved preference.
    localStorage.setItem("theme", "operative-light");
    mount();
    expect(localStorage.getItem("bz-theme")).toBe("operative-light");
    expect(localStorage.getItem("theme")).toBeNull();
    expect(document.documentElement.dataset.theme).toBe("operative-light");
  });

  it("does NOT migrate a value this token system cannot render", () => {
    // GUILT: the retired appearance page persisted 'system' under the legacy
    // key. The pre-paint script does not validate what it reads, so copying
    // it across would produce data-theme="system" — no tokens/themes/ file
    // matches that, i.e. an unstyled page on the next reload.
    localStorage.setItem("theme", "system");
    document.documentElement.dataset.theme = "operative-dark";
    mount();
    expect(localStorage.getItem("bz-theme")).toBeNull();
    expect(localStorage.getItem("theme")).toBeNull();
    // Falls back to the persona the pre-paint script chose — a working theme.
    expect(document.documentElement.dataset.theme).toBe("operative-dark");
  });

  it("never lets the legacy value clobber an existing bz-theme", () => {
    localStorage.setItem("bz-theme", "operative-dark");
    localStorage.setItem("theme", "light");
    mount();
    expect(localStorage.getItem("bz-theme")).toBe("operative-dark");
    expect(localStorage.getItem("theme")).toBeNull();
    expect(document.documentElement.dataset.theme).toBe("operative-dark");
  });

  it("INNOCENCE: a clean install is untouched by the migration", () => {
    document.documentElement.dataset.theme = "editorial";
    mount();
    expect(localStorage.getItem("theme")).toBeNull();
    expect(localStorage.getItem("bz-theme")).toBeNull();
    expect(document.documentElement.dataset.theme).toBe("editorial");
  });

  it("is idempotent — a second mount changes nothing", () => {
    localStorage.setItem("theme", "light");
    mount().unmount();
    const afterFirst = {
      canonical: localStorage.getItem("bz-theme"),
      legacy: localStorage.getItem("theme"),
    };
    mount();
    expect(localStorage.getItem("bz-theme")).toBe(afterFirst.canonical);
    expect(localStorage.getItem("theme")).toBe(afterFirst.legacy);
    expect(localStorage.getItem("bz-theme")).toBe("light");
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
