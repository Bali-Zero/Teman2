import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PILL_TONE, PRACTICE_TONE, PracticeStatePill, StatePill } from "./r19";
import type { PracticeState } from "./types";

/**
 * The R19 "no red" law for the GARUDA VOA staff console, as a test.
 *
 * Concept F re-aliases danger to copper and makes every alarming state carry a
 * WORD. On the kita daylight theme --state-danger resolves to #b91c1c, so a
 * single read of that token would put red back on this surface — and a hand-
 * written hex would do it without even naming the token. Both are refused
 * here, over the console's real source files.
 */

/**
 * `import.meta.url` is not a file URL under this runner's environment, so the
 * console is located from the working directory instead — which is the app in
 * a focused run and can be the repo root in CI. Both are tried; neither
 * existing throws here rather than silently scanning an empty list, which is
 * how a scanner turns into a rubber stamp.
 */
const CONSOLE_DIR = (() => {
  const suffix = join("src", "app", "(workspace)", "garuda-voa");
  for (const base of [process.cwd(), join(process.cwd(), "apps", "mouth")]) {
    const candidate = join(base, suffix);
    if (existsSync(candidate)) return candidate + "/";
  }
  throw new Error(
    `GARUDA VOA console sources not found from ${process.cwd()} — the no-red scan cannot run`,
  );
})();

/** Every one of the seven contract states, spelled out rather than derived. */
const ALL_STATES: PracticeState[] = [
  "Received",
  "In review",
  "Blocked",
  "Submitted",
  "Approved",
  "Rejected",
  "Delivered",
];

/**
 * The scanner. It judges a single source line and returns the reason it is
 * guilty, or null. Two shapes only: a read of the danger token, and a literal
 * brand hex. Comment lines are exempt — this file's own doc block names both.
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

/**
 * Every `.ts`/`.tsx` the console renders from, one level of nesting deep
 * (`[practiceId]/`). Test files are NOT rendered and are excluded on purpose:
 * their fixtures have to spell the guilty shapes out loud — this file's own
 * guilt case is a `--state-danger` string literal.
 */
function sourceFiles(): string[] {
  const here = readdirSync(CONSOLE_DIR, { withFileTypes: true });
  const rendered = (name: string) =>
    /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name);
  const files: string[] = [];
  for (const entry of here) {
    if (entry.isFile() && rendered(entry.name)) {
      files.push(join(CONSOLE_DIR, entry.name));
    }
    if (entry.isDirectory()) {
      for (const nested of readdirSync(join(CONSOLE_DIR, entry.name))) {
        if (rendered(nested)) {
          files.push(join(CONSOLE_DIR, entry.name, nested));
        }
      }
    }
  }
  return files;
}

/**
 * The lines the scanner is asked to judge. They are FIXTURES, not styling — the
 * `token-lint-ok` markers say so to the CI gate, which judges added lines and
 * cannot tell a fixture from a rule on its own.
 */
const FIXTURE = {
  dangerToken: '  className="text-[var(--state-danger)]"',
  hexInStyle: '  style={{ color: "#b91c1c" }}', // token-lint-ok: scanner fixture
  hexInLineComment: "  // danger is #b91c1c here", // token-lint-ok: scanner fixture
  hexInBlockComment: " * no red: #b91c1c here", // token-lint-ok: scanner fixture
  copperClass: '  className="text-[var(--bz-copper-text)]"',
  successClass: '  className="border-[var(--state-success)]"',
};

describe("the console's no-red scanner", () => {
  it("is GUILTY on the two shapes that put red back", () => {
    expect(redViolation(FIXTURE.dangerToken)).toBe("reads --state-danger");
    expect(redViolation(FIXTURE.hexInStyle)).toBe("hardcoded hex");
  });

  it("is INNOCENT on the copper idiom and on prose that merely names red", () => {
    expect(redViolation(FIXTURE.copperClass)).toBeNull();
    expect(redViolation(FIXTURE.successClass)).toBeNull();
    expect(redViolation(FIXTURE.hexInLineComment)).toBeNull();
    expect(redViolation(FIXTURE.hexInBlockComment)).toBeNull();
  });
});

describe("the GARUDA VOA staff console carries no red", () => {
  it("finds its own source files", () => {
    const names = sourceFiles().map((f) => f.replace(CONSOLE_DIR, ""));
    expect(names).toContain("page.tsx");
    expect(names).toContain("r19.tsx");
    expect(names).toContain(join("[practiceId]", "page.tsx"));
  });

  it("has no danger-token read and no hardcoded hex in any of them", () => {
    const offences: string[] = [];
    for (const file of sourceFiles()) {
      const lines = readFileSync(file, "utf8").split("\n");
      lines.forEach((line, i) => {
        const why = redViolation(line);
        if (why) {
          offences.push(`${file.replace(CONSOLE_DIR, "")}:${i + 1} — ${why}`);
        }
      });
    }
    expect(offences).toEqual([]);
  });
});

describe("the seven practice states read as four meanings and seven words", () => {
  it("maps every contract state, and never to a danger class", () => {
    for (const state of ALL_STATES) {
      const tone = PRACTICE_TONE[state];
      expect(tone, `${state} has no tone`).toBeTruthy();
      expect(PILL_TONE[tone]).not.toContain("--state-danger");
    }
    expect(Object.keys(PRACTICE_TONE).sort()).toEqual([...ALL_STATES].sort());
  });

  it("gives the two formerly-red states copper AND their word", () => {
    expect(PRACTICE_TONE.Blocked).toBe("you");
    expect(PRACTICE_TONE.Rejected).toBe("you");
    expect(PILL_TONE.you).toContain("--bz-copper");

    render(<PracticeStatePill state="Rejected" />);
    expect(screen.getByText("Rejected")).toBeVisible();
  });

  it("renders an outlined pill, never a filled one", () => {
    const { container } = render(<StatePill tone="ok" label="Delivered" />);
    const pill = container.firstElementChild as HTMLElement;
    expect(pill.className).toContain("border");
    expect(pill.className).not.toContain("bg-[var(--state-");
  });
});
