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
  "dark" | "light" | "editorial" | "operative-light" | "operative-dark";
export type Funnel = "visa" | "kbli" | "tax" | "property" | null;

interface ThemeContextValue {
  theme: Theme;
  setTheme: (t: Theme) => void;
  funnel: Funnel;
  setFunnel: (f: Funnel) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

/** The ONE key the theme is persisted under. Matches the pre-paint script. */
export const THEME_STORAGE_KEY = "bz-theme";
/** Retired mirror key, read once at mount for migration, then deleted (WS4). */
const LEGACY_THEME_STORAGE_KEY = "theme";

function isTheme(v: string | null | undefined): v is Theme {
  return (
    v === "dark" ||
    v === "light" ||
    v === "editorial" ||
    v === "operative-light" ||
    v === "operative-dark"
  );
}

function normalizeThemeForProduct(
  theme: Theme,
  product: string | undefined,
): Theme {
  if (product !== "kita" && product !== "my") return theme;
  if (theme === "light") return "operative-light";
  if (theme === "dark") return "operative-dark";
  return theme;
}

/**
 * One-time migration off the legacy `theme` key (WS4 theme-key reconciliation).
 *
 * Idempotent, and deliberately VALIDATING: only a value this token system can
 * actually render is carried over. The retired appearance-settings page
 * persisted `'system'` under the legacy key, and the pre-paint script in
 * app/layout.tsx does NOT validate what it reads — it writes the stored string
 * straight onto `data-theme`. Copying `'system'` across would yield
 * `data-theme="system"`, which matches no file in tokens/themes/, i.e. an
 * unstyled page on the next reload. An unreadable legacy value is dropped, and
 * the user falls back to the hostname persona, which is a working theme.
 */
function migrateLegacyThemeKey(): void {
  if (typeof window === "undefined") return;
  const legacy = localStorage.getItem(LEGACY_THEME_STORAGE_KEY);
  if (legacy === null) return;
  if (localStorage.getItem(THEME_STORAGE_KEY) === null && isTheme(legacy)) {
    localStorage.setItem(THEME_STORAGE_KEY, legacy);
  }
  localStorage.removeItem(LEGACY_THEME_STORAGE_KEY);
}

interface ThemeProviderProps {
  children: ReactNode;
  defaultTheme?: Theme;
  defaultFunnel?: Funnel;
}

/**
 * ThemeProvider — writes data-theme and data-funnel onto <html>.
 *
 * Theme precedence on mount:
 *   1. localStorage (bz-theme — the only theme key; a legacy `theme` value is
 *      migrated once at mount and the legacy key removed)
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
  //   1. localStorage('bz-theme') — explicit user choice, wins everywhere
  //   2. the data-theme the pre-paint script ALREADY set, persona-aware by
  //      hostname (kita./my./zantara. → operative-light, prime. →
  //      operative-dark, public → editorial). We must NOT clobber it with
  //      `defaultTheme`.
  //   3. defaultTheme prop — only when neither of the above is present.
  //
  // The previous code wrote `defaultTheme` whenever localStorage was empty,
  // which silently overrode the persona-aware decision after hydration (the
  // portal showed navy instead of paper). Reading the pre-paint value back
  // keeps the provider hostname-aware for free.
  useEffect(() => {
    migrateLegacyThemeKey();

    const stored =
      typeof window !== "undefined"
        ? localStorage.getItem(THEME_STORAGE_KEY)
        : null;
    const prePaint =
      typeof document !== "undefined"
        ? document.documentElement.dataset.theme
        : null;

    const rawResolved: Theme = isTheme(stored)
      ? stored
      : isTheme(prePaint)
        ? prePaint
        : defaultTheme;
    const resolved = normalizeThemeForProduct(
      rawResolved,
      document.documentElement.dataset.product,
    );

    setThemeState(resolved);
    document.documentElement.dataset.theme = resolved;
    if (isTheme(stored) && stored !== resolved) {
      localStorage.setItem(THEME_STORAGE_KEY, resolved);
    }
  }, [defaultTheme]);

  const setTheme = useCallback((next: Theme) => {
    const resolved = normalizeThemeForProduct(
      next,
      typeof document !== "undefined"
        ? document.documentElement.dataset.product
        : undefined,
    );
    setThemeState(resolved);
    if (typeof window !== "undefined") {
      // `bz-theme` is the ONLY theme key — same key the pre-paint script in
      // app/layout.tsx reads, so a reload repaints without FOUC. The legacy
      // `theme` mirror was dropped in WS4: it had no readers left, and while
      // it lived, a writer that touched only one of the two keys made the
      // applied theme depend on which writer ran last.
      localStorage.setItem(THEME_STORAGE_KEY, resolved);
      document.documentElement.dataset.theme = resolved;
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
