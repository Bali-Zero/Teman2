import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect } from "vitest";
import { PILL_TONE } from "./r19";

/**
 * The R19 "no red" law for the Portal Champion widget on the kita dashboard.
 *
 * Unlike the GARUDA VOA console (garuda-voa/r19.test.tsx), the dashboard
 * folder is NOT entirely R19 — page.tsx keeps its existing `--state-danger`
 * read for the "living" intel category, unrelated to this widget. So this
 * scanner is scoped to the widget's OWN files by name, not the whole
 * directory: a directory-wide scan here would fail on code this widget never
 * touched, which is the "guard judges substring, not entity" failure mode.
 *
 * `import.meta.url` is not a file URL under this runner's environment, so the
 * folder is located from the working directory instead — which is the app in
 * a focused run and can be the repo root in CI. Both are tried; neither
 * existing throws here rather than silently scanning an empty list.
 */
const DASHBOARD_DIR = (() => {
  const suffix = join("src", "app", "(workspace)", "dashboard");
  for (const base of [process.cwd(), join(process.cwd(), "apps", "mouth")]) {
    const candidate = join(base, suffix);
    if (existsSync(candidate)) return candidate + "/";
  }
  throw new Error(
    `dashboard folder not found from ${process.cwd()} — the no-red scan cannot run`,
  );
})();

/** The widget's own rendered sources — test files excluded on purpose. */
const WIDGET_FILES = [
  "r19.tsx",
  "PortalChallengeWidget.tsx",
  "ChampionArena.tsx",
];

/**
 * The scanner. Two shapes only: a read of the danger token, and a literal
 * brand hex. Comment lines are exempt.
 */
export function redViolation(line: string): string | null {
  const code = line.trimStart();
  if (
    code.startsWith("//") ||
    code.startsWith("*") ||
    code.startsWith("/*") ||
    code.startsWith("{/*")
  ) {
    return null;
  }
  if (code.includes("--state-danger")) return "reads --state-danger";
  if (/#[0-9a-fA-F]{3,8}\b/.test(code)) return "hardcoded hex";
  return null;
}

const FIXTURE = {
  dangerToken: '  className="text-[var(--state-danger)]"',
  hexInStyle: '  style={{ color: "#b91c1c" }}', // token-lint-ok: scanner fixture
  copperClass: '  className="text-[var(--bz-copper-text)]"',
  successClass: '  className="border-[var(--state-success)]"',
};

describe("the widget's no-red scanner", () => {
  it("is GUILTY on the two shapes that put red back", () => {
    expect(redViolation(FIXTURE.dangerToken)).toBe("reads --state-danger");
    expect(redViolation(FIXTURE.hexInStyle)).toBe("hardcoded hex");
  });

  it("is INNOCENT on the copper/success idiom", () => {
    expect(redViolation(FIXTURE.copperClass)).toBeNull();
    expect(redViolation(FIXTURE.successClass)).toBeNull();
  });
});

describe("the Portal Champion widget carries no red", () => {
  it("finds its own source files", () => {
    for (const name of WIDGET_FILES) {
      expect(existsSync(join(DASHBOARD_DIR, name)), name).toBe(true);
    }
  });

  it("has no danger-token read and no hardcoded hex in any of them", () => {
    const offences: string[] = [];
    for (const name of WIDGET_FILES) {
      const file = join(DASHBOARD_DIR, name);
      const lines = readFileSync(file, "utf8").split("\n");
      lines.forEach((line, i) => {
        const why = redViolation(line);
        if (why) offences.push(`${name}:${i + 1} — ${why}`);
      });
    }
    expect(offences).toEqual([]);
  });
});

describe("the four pill tones read as four meanings, never danger", () => {
  it("maps ok/ours/you/wait and none of them touch --state-danger", () => {
    for (const tone of Object.keys(PILL_TONE) as (keyof typeof PILL_TONE)[]) {
      expect(PILL_TONE[tone]).not.toContain("--state-danger");
    }
    expect(PILL_TONE.you).toContain("--bz-copper");
  });
});
