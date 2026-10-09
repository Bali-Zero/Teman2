import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The Select dropdown (SelectContent) rendered with NO background on
 * kita.balizero.com: the options of "Add Required Document" (process page)
 * were drawn straight over the form fields behind them. Cause: shadcn colour
 * utilities that this app never defines. Tailwind v4 only emits `bg-X` when a
 * `--color-X` token exists, and packages/core/tailwind/theme.css defines no
 * --color-popover, --color-popover-foreground or --color-accent-foreground;
 * --color-accent exists but is the red funnel accent, so a hovered option
 * turned red. Dialog (dialog.tsx) already uses the app's own CSS variables;
 * the dropdown now does the same.
 *
 * Declared limits: reads select.tsx as text; does not render Radix Select
 * (portal + pointer APIs) and does not measure contrast.
 */
const SRC = readFileSync(join(__dirname, "select.tsx"), "utf8");
const THEME = readFileSync(
  join(__dirname, "../../../../../packages/core/tailwind/theme.css"),
  "utf8",
);

describe("Select dropdown uses colours that exist in this app", () => {
  it("positive control: the scan reaches SelectContent and SelectItem, and the theme file", () => {
    expect(SRC).toContain("SelectPrimitive.Content");
    expect(SRC).toContain("SelectPrimitive.Item");
    expect(THEME).toContain("@theme");
    expect(THEME).toContain("--color-accent:");
  });

  it("the undefined shadcn tokens are really undefined in the theme", () => {
    for (const token of [
      "popover",
      "popover-foreground",
      "accent-foreground",
    ]) {
      expect(THEME).not.toContain(`--color-${token}:`);
    }
  });

  it("GUILT: no dropdown class depends on an undefined token or the red accent", () => {
    for (const cls of [
      "bg-popover",
      "text-popover-foreground",
      "focus:bg-accent",
      "focus:text-accent-foreground",
    ]) {
      expect(SRC).not.toMatch(new RegExp(`(?<![\\w-])${cls}(?![\\w-])`));
    }
  });

  it("the dropdown panel and the focused option use the app's CSS variables", () => {
    expect(SRC).toContain("bg-[var(--background)]");
    expect(SRC).toContain("text-[var(--foreground)]");
    expect(SRC).toContain("border-[var(--border)]");
    expect(SRC).toContain("focus:bg-[var(--background-hover)]");
  });
});
