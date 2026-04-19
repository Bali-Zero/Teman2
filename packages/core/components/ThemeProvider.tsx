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

  // On mount: read localStorage and sync to state + DOM.
  useEffect(() => {
    const stored =
      typeof window !== "undefined" ? localStorage.getItem("theme") : null;
    if (
      stored === "dark" ||
      stored === "light" ||
      stored === "editorial" ||
      stored === "operative-light" ||
      stored === "operative-dark"
    ) {
      setThemeState(stored as Theme);
      document.documentElement.dataset.theme = stored;
    } else {
      document.documentElement.dataset.theme = defaultTheme;
    }
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
