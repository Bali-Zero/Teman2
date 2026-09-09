"use client";

import { useEffect, useRef } from "react";
import { Moon, Sun } from "lucide-react";
import type { Language } from "../_lib/flow";
import { translate } from "../_lib/i18n";

export type OracleTheme = "light" | "dark";

export interface ThemeToggleProps {
  language: Language;
  theme: OracleTheme;
  onChange: (theme: OracleTheme) => void;
}

export const ORACLE_THEME_STORAGE_KEY = "visa-oracle-theme";

function preferredTheme(): OracleTheme {
  try {
    const stored = localStorage.getItem(ORACLE_THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // Storage can be unavailable in hardened/private browser contexts.
  }
  return typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

/**
 * Local to the route — never touches the global `data-theme` (spec hard
 * constraint). The saved route preference wins, then the system preference.
 * Both palettes are designed for AA contrast.
 */
export function ThemeToggle({ language, theme, onChange }: ThemeToggleProps) {
  const next: OracleTheme = theme === "light" ? "dark" : "light";
  const bootstrap = useRef({ theme, onChange });

  useEffect(() => {
    const preferred = preferredTheme();
    const root = document.querySelector<HTMLElement>(".oracle-root");
    // Hydration has completed, so align the local DOM attribute immediately;
    // the parent state update below then reconciles to the same value.
    root?.setAttribute("data-oracle-theme", preferred);
    if (preferred !== bootstrap.current.theme) {
      bootstrap.current.onChange(preferred);
    }
    const frame = window.requestAnimationFrame(() => {
      root?.setAttribute("data-oracle-theme-ready", "true");
    });
    return () => {
      window.cancelAnimationFrame(frame);
      document.documentElement.removeAttribute("data-oracle-theme-bootstrap");
      root?.removeAttribute("data-oracle-theme-ready");
    };
  }, []);

  const changeTheme = () => {
    try {
      localStorage.setItem(ORACLE_THEME_STORAGE_KEY, next);
    } catch {
      // Theme still changes for the current visit when persistence fails.
    }
    onChange(next);
  };

  return (
    <button
      type="button"
      className="oracle-toggle"
      aria-label={translate(language, "theme.toggle.aria")}
      aria-pressed={theme === "dark"}
      title={next === "dark" ? (language === "en" ? "Switch to night" : "Mode gelap") : (language === "en" ? "Switch to day" : "Mode terang")}
      onClick={changeTheme}
    >
      {theme === "light" ? (
        <Sun aria-hidden="true" size={18} />
      ) : (
        <Moon aria-hidden="true" size={18} />
      )}
      <span>{theme === "dark" ? (language === "en" ? "Night" : "Gelap") : (language === "en" ? "Day" : "Terang")}</span>
    </button>
  );
}
