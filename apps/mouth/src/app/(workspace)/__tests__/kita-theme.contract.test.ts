import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const globalsCss = readFileSync(
  join(__dirname, "..", "..", "globals.css"),
  "utf8",
);

const kitaTheme = globalsCss.match(
  /\[data-theme="operative-light"\]\[data-product="kita"\]\s*\{([^}]*)\}/,
)?.[1];

describe("Kita day-mode theme", () => {
  it("uses a warm-white canvas while keeping cards white", () => {
    expect(kitaTheme).toBeDefined();
    expect(kitaTheme).toContain("--bz-base: var(--bz-kita-canvas);");
    expect(kitaTheme).toContain("--background: var(--bz-kita-canvas);");
    expect(kitaTheme).toContain("--kbli-bg-base: var(--bz-kita-canvas);");
    expect(kitaTheme).toContain("--bz-card: var(--bz-kita-card);");
    expect(kitaTheme).toContain("--bz-card-hover: var(--bz-kita-card-hover);");
    expect(kitaTheme).toContain("--nav-bg: var(--bz-kita-nav);");
  });
});
