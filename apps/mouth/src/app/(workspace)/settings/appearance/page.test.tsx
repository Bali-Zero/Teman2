import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ThemeProvider } from "@balizero/core/components/ThemeProvider";
import AppearanceSettingsPage from "./page";

// useToast throws outside a ToastProvider; the toast itself is not under test.
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  }),
}));

function stubPrefersDark(prefersDark: boolean) {
  // jsdom ships no matchMedia — the page guards on its absence, so a test that
  // wants the "System" branch has to provide one.
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      matches: query.includes("dark") ? prefersDark : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
      onchange: null,
    }),
  });
}

function mount(prePaintTheme?: string) {
  if (prePaintTheme) document.documentElement.dataset.theme = prePaintTheme;
  return render(
    <ThemeProvider defaultTheme="operative-dark">
      <AppearanceSettingsPage />
    </ThemeProvider>,
  );
}

function choose(label: string) {
  act(() => {
    screen.getByText(label).closest("button")!.click();
  });
}

function save() {
  act(() => {
    screen.getByText("Save Changes").closest("button")!.click();
  });
}

describe("Appearance settings — theme persistence (WS4)", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    delete (window as { matchMedia?: unknown }).matchMedia;
  });

  it("GUILT: saving a theme persists it under the canonical key and applies it", () => {
    // Before WS4 this page wrote a `theme` key nobody reads and toggled a
    // `.dark` class no selector consults, then reported "Appearance saved".
    // Both assertions below failed against that version.
    mount("operative-dark");
    choose("Light");
    save();

    expect(localStorage.getItem("bz-theme")).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("GUILT: saving never writes the retired `theme` key", () => {
    mount("operative-dark");
    choose("Light");
    save();

    expect(localStorage.getItem("theme")).toBeNull();
  });

  it("resolves 'System' to a real theme and never persists the literal", () => {
    // `data-theme="system"` matches no file in tokens/themes/, and the
    // pre-paint script writes whatever it reads straight onto the attribute.
    stubPrefersDark(true);
    mount("operative-light");
    choose("System");
    save();

    expect(localStorage.getItem("bz-theme")).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("resolves 'System' to light when the OS prefers light", () => {
    stubPrefersDark(false);
    mount("operative-dark");
    choose("System");
    save();

    expect(localStorage.getItem("bz-theme")).toBe("light");
  });

  it("reflects the theme actually in force, not a hardcoded default", () => {
    // my./portal persona: the pre-paint script chose operative-light. The
    // radio must show Light even though the component's initial state is dark.
    mount("operative-light");

    expect(screen.getByText("Light").closest("button")!.className).toContain(
      "border-[var(--accent)]",
    );
  });

  it("INNOCENCE: merely opening the page persists nothing", () => {
    mount("operative-dark");

    expect(localStorage.getItem("bz-theme")).toBeNull();
    expect(localStorage.getItem("theme")).toBeNull();
    expect(document.documentElement.dataset.theme).toBe("operative-dark");
  });
});
