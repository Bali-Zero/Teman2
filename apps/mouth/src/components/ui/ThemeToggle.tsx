"use client";

import { useTheme } from "@balizero/core/components/ThemeProvider";
import { Sun, Moon } from "lucide-react";
import { useEffect, useState } from "react";

/** Themes whose surfaces are dark (drive the sun/moon icon choice). */
const DARK_THEMES = new Set(["dark", "operative-dark", "editorial"]);

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <button
        className="p-1.5 rounded-lg transition-colors"
        style={{ color: "var(--bz-text-2)" }}
        aria-label="Toggle theme"
      >
        <Moon size={15} />
      </button>
    );
  }

  const isDark = DARK_THEMES.has(theme);

  return (
    <button
      onClick={() => setTheme(isDark ? "operative-light" : "operative-dark")}
      className="p-1.5 rounded-lg transition-colors hover:bg-white/[0.06]"
      style={{ color: "var(--bz-text-2)" }}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Light mode" : "Dark mode"}
    >
      {isDark ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}
