"use client";

import { Moon, Sun } from "lucide-react";
import type { Language } from "../_lib/flow";
import { translate } from "../_lib/i18n";

export type OracleTheme = "light" | "dark";

export interface ThemeToggleProps {
  language: Language;
  theme: OracleTheme;
  onChange: (theme: OracleTheme) => void;
}

/**
 * Local to the route — never touches the global `data-theme` (spec hard
 * constraint). Light is the default (design doc §3: "default light for
 * the Jakarta demo"); dark reads premium/oracle. Both are AA-contrast.
 */
export function ThemeToggle({ language, theme, onChange }: ThemeToggleProps) {
  const next: OracleTheme = theme === "light" ? "dark" : "light";
  return (
    <button
      type="button"
      className="oracle-toggle"
      aria-label={translate(language, "theme.toggle.aria")}
      onClick={() => onChange(next)}
    >
      {theme === "light" ? (
        <Moon aria-hidden="true" size={18} />
      ) : (
        <Sun aria-hidden="true" size={18} />
      )}
    </button>
  );
}
