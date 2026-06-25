"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Theme =
  | "dark"
  | "light"
  | "editorial"
  | "operative-light"
  | "operative-dark";
export type Funnel = "visa" | "kbli" | "tax" | "property" | null;

interface ThemeContextValue {
  theme: Theme;
  setTheme: (t: Theme) => void;
  funnel: Funnel;
  setFunnel: (f: Funnel) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

interface ThemeProviderProps {
  children: ReactNode;
  defaultTheme?: Theme;
  defaultFunnel?: Funnel;
}

/**
 * ThemeProvider — writes data-theme and data-funnel onto <html>.
 *
 * Theme precedence on mount:
 *   1. localStorage.theme (user choice wins)
 *   2. defaultTheme prop
 *
 * An inline script in <head> sets data-theme before React hydrates,
 * preventing FOUC — see design §5 "Toggle mechanism". Without that script,
 * SSR will flash the server default before this component runs.
 */
export function ThemeProvider({
  children,
  defaultTheme = "dark",
  defaultFunnel = null,
}: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(defaultTheme);
  const [funnel, setFunnelState] = useState<Funnel>(defaultFunnel);

  // On mount: reconcile React state with the DOM/localStorage source of truth.
  //
  // Precedence (matches the pre-paint themeInitScript in app/layout.tsx):
  //   1. localStorage('theme')  — explicit user choice, wins everywhere
  //   2. the data-theme the pre-paint script ALREADY set, persona-aware by
  //      hostname (my./zantara. → operative-light, kita./prime. → operative-dark,
  //      public → editorial). We must NOT clobber it with `defaultTheme`.
  //   3. defaultTheme prop — only when neither of the above is present.
  //
  // The previous code wrote `defaultTheme` whenever localStorage was empty,
  // which silently overrode the persona-aware decision after hydration (the
  // portal showed navy instead of paper). Reading the pre-paint value back
  // keeps the provider hostname-aware for free.
  useEffect(() => {
    const isTheme = (v: string | null | undefined): v is Theme =>
      v === "dark" ||
      v === "light" ||
      v === "editorial" ||
      v === "operative-light" ||
      v === "operative-dark";

    const stored =
      typeof window !== "undefined" ? localStorage.getItem("theme") : null;
    const prePaint =
      typeof document !== "undefined"
        ? document.documentElement.dataset.theme
        : null;

    const resolved: Theme = isTheme(stored)
      ? stored
      : isTheme(prePaint)
        ? prePaint
        : defaultTheme;

    setThemeState(resolved);
    document.documentElement.dataset.theme = resolved;
  }, [defaultTheme]);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    if (typeof window !== "undefined") {
      localStorage.setItem("theme", next);
      document.documentElement.dataset.theme = next;
    }
  }, []);

  const setFunnel = useCallback((next: Funnel) => {
    setFunnelState(next);
    if (typeof document !== "undefined") {
      if (next) {
        document.documentElement.dataset.funnel = next;
      } else {
        delete document.documentElement.dataset.funnel;
      }
    }
  }, []);

  const value = useMemo(
    () => ({ theme, setTheme, funnel, setFunnel }),
    [theme, setTheme, funnel, setFunnel],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used inside a <ThemeProvider>");
  }
  return ctx;
}

/**
 * ThemeScope — server-safe wrapper that sets data-funnel on a div.
 * Use in route-group layouts (e.g., /kbli/layout.tsx) so all descendant
 * components read var(--accent-funnel) → gold automatically.
 */
export function ThemeScope({
  funnel,
  children,
  className,
}: {
  funnel: Exclude<Funnel, null>;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div data-funnel={funnel} className={className}>
      {children}
    </div>
  );
}
