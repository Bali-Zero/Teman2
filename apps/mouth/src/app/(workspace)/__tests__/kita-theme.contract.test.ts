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
    expect(kitaTheme).toContain("--bz-base: #f8f6f2;"); // token-lint-ok: theme contract assertion string, not a color use
    expect(kitaTheme).toContain("--background: #f8f6f2;"); // token-lint-ok: theme contract assertion string, not a color use
    expect(kitaTheme).toContain("--kbli-bg-base: #f8f6f2;"); // token-lint-ok: theme contract assertion string, not a color use
    expect(kitaTheme).toContain("--bz-card: #ffffff;"); // token-lint-ok: theme contract assertion string, not a color use
    expect(kitaTheme).toContain("--bz-card-hover: #fbf8f3;"); // token-lint-ok: theme contract assertion string, not a color use
    expect(kitaTheme).toContain("--nav-bg: rgba(255, 253, 249, 0.92);");
  });
});
