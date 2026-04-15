import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

function countVars(path: string): number {
  const content = readFileSync(resolve(__dirname, path), "utf-8");
  const matches = content.match(/^\s+--[a-z][a-z0-9-]*:/gm);
  return matches?.length ?? 0;
}

function declaredVarNames(path: string): Set<string> {
  const content = readFileSync(resolve(__dirname, path), "utf-8");
  const matches = content.match(/--[a-z][a-z0-9-]*(?=:)/g) ?? [];
  return new Set(matches);
}

describe("design tokens — surface area caps (success criterion §10.1)", () => {
  it("primitives.css declares ≤80 vars", () => {
    expect(countVars("./primitives.css")).toBeLessThanOrEqual(80);
  });

  it("semantic.css declares ≤60 vars", () => {
    expect(countVars("./semantic.css")).toBeLessThanOrEqual(60);
  });

  it("themes/dark.css declares ≤40 vars", () => {
    expect(countVars("./themes/dark.css")).toBeLessThanOrEqual(40);
  });

  it("themes/light.css declares ≤40 vars", () => {
    expect(countVars("./themes/light.css")).toBeLessThanOrEqual(40);
  });

  it("themes/editorial.css declares ≤40 vars", () => {
    expect(countVars("./themes/editorial.css")).toBeLessThanOrEqual(40);
  });
});

describe("design tokens — namespace discipline", () => {
  it("primitives and semantic layers do not share variable names", () => {
    const primitives = declaredVarNames("./primitives.css");
    const semantic = declaredVarNames("./semantic.css");
    const overlap = [...primitives].filter((name) => semantic.has(name));
    expect(overlap).toEqual([]);
  });

  it("no primitive var starts with semantic prefixes (--surface/--text/--border/--accent/--nav/--footer/--cta/--state)", () => {
    const primitives = declaredVarNames("./primitives.css");
    const semanticPrefixes = ["--surface", "--text", "--border", "--accent", "--nav", "--footer", "--cta", "--state"];
    const violations = [...primitives].filter((name) =>
      // Allow --text-xs etc. (font-size primitives) but flag --text-primary etc.
      semanticPrefixes.some((p) => name.startsWith(p) && !name.match(/^--text-(xs|sm|base|lg|xl|\dxl)$/))
    );
    expect(violations).toEqual([]);
  });
});
