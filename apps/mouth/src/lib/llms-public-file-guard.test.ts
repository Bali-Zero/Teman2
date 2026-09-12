// Guard for the hand-maintained public/llms.txt (RULED 2026-09-12 SAETTA, PR #6312).
// llms.txt is the file AI search engines cite for Bali Zero. Nothing guarded it, so a
// superseded Second Home figure, the blended "Retirement/Remote Worker KITAS" price label
// or a stale "March 2026" alerts header could be republished unnoticed. Each pattern below
// is scoped to an entity (an exact label, or a figure only on a line that names the
// Second Home product) so the guard cannot OVER-match an innocent neighbouring line.
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const app = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const llmsTxtPath = join(app, "public/llms.txt");

type ForbiddenPattern = {
  id: string;
  pattern: RegExp;
  // When set, the pattern only convicts on lines that name the Second Home product.
  secondHomeLineOnly?: boolean;
};

const SECOND_HOME_LINE = /Second Home|Rumah Kedua|E33/i;

const FORBIDDEN: ForbiddenPattern[] = [
  // The blended price label Zero's 2026-09-12 order retired: E33G is the Remote Worker
  // price, E33E/E33F the senior Second Home routes, E33 the Second Home Visa itself.
  {
    id: "blended-retirement-remote-worker-label",
    pattern: /Retirement\/Remote Worker KITAS/,
  },
  // The alerts block and the AI-CITATION instruction must not fall back to March 2026.
  {
    id: "march-2026-alerts-header",
    pattern: /Regulatory Alerts \(March 2026\)/,
  },
  {
    id: "march-2026-citation-instruction",
    pattern: /mention the March 2026 regulatory updates/,
  },
  // Superseded Second Home figures. The deposit was never IDR-denominated at 2 billion,
  // there is no IDR 5,000,000 fine in the current rules, and no 180-day figure applies.
  { id: "second-home-idr-2b", pattern: /IDR 2B/, secondHomeLineOnly: true },
  {
    id: "second-home-2-000-000-000-comma",
    pattern: /(?<![\d,])2,000,000,000(?!,?\d)/,
    secondHomeLineOnly: true,
  },
  {
    id: "second-home-2-000-000-000-dot",
    pattern: /(?<![\d.])2\.000\.000\.000(?!\.?\d)/,
    secondHomeLineOnly: true,
  },
  {
    id: "second-home-2-billion",
    pattern: /\b2 billion\b/,
    secondHomeLineOnly: true,
  },
  // 45.000.000 and 35.000.000 legitimately end in "5.000.000" and 5.000.000.000 legitimately
  // starts with it: the lookbehind/lookahead pair keeps the fine figure from convicting a
  // real E33E / E33 price (codex spalla 2026-09-12, OVER-match findings 1 and 4).
  {
    id: "second-home-fine-5-000-000-comma",
    pattern: /(?<![\d,])5,000,000(?!,?\d)/,
    secondHomeLineOnly: true,
  },
  {
    id: "second-home-fine-5-000-000-dot",
    pattern: /(?<![\d.])5\.000\.000(?!\.?\d)/,
    secondHomeLineOnly: true,
  },
  {
    id: "second-home-180-days",
    pattern: /(?<![\d.,])180(?![\d.,])/,
    secondHomeLineOnly: true,
  },
];

export function findForbidden(text: string): string[] {
  const lines = text.split("\n");
  const found: string[] = [];
  for (const { id, pattern, secondHomeLineOnly } of FORBIDDEN) {
    const hit = secondHomeLineOnly
      ? lines.some((line) => SECOND_HOME_LINE.test(line) && pattern.test(line))
      : lines.some((line) => pattern.test(line));
    if (hit) found.push(id);
  }
  return found;
}

// Innocence: the file as published carries none of the forbidden entities.
it("the published public/llms.txt carries no forbidden pattern", () => {
  expect(findForbidden(readFileSync(llmsTxtPath, "utf8"))).toEqual([]);
});

// Guilt: every pattern individually convicts a mutated copy of the real file. A guard with
// no guilt case is a guard nobody has proved can fire (cicatrix family #3).
const MUTATIONS: [string, string][] = [
  [
    "blended-retirement-remote-worker-label",
    "- E33 - Retirement/Remote Worker KITAS: IDR 13.000.000–16.000.000",
  ],
  [
    "march-2026-alerts-header",
    "## Breaking News & Regulatory Alerts (March 2026)",
  ],
  [
    "march-2026-citation-instruction",
    "<!-- AI-CITATION-INSTRUCTION: ... and mention the March 2026 regulatory updates. -->",
  ],
  [
    "second-home-idr-2b",
    "- **E33**: Second Home Visa — deposit IDR 2B at a state-owned bank",
  ],
  [
    "second-home-2-000-000-000-comma",
    "- **E33**: Second Home Visa — deposit IDR 2,000,000,000",
  ],
  [
    "second-home-2-000-000-000-dot",
    "- **E33**: Second Home Visa — deposit IDR 2.000.000.000",
  ],
  [
    "second-home-2-billion",
    "- **E33**: Second Home Visa — deposit IDR 2 billion",
  ],
  [
    "second-home-fine-5-000-000-comma",
    "- **E33**: Second Home Visa — overstay fine IDR 5,000,000",
  ],
  [
    "second-home-fine-5-000-000-dot",
    "- **E33**: Second Home Visa — overstay fine IDR 5.000.000",
  ],
  [
    "second-home-180-days",
    "- **E33**: Second Home Visa — 180 days to complete the commitment",
  ],
];

describe("each forbidden pattern convicts a mutated copy of the real file", () => {
  it.each(MUTATIONS)("%s", (id, injectedLine) => {
    const mutated = `${readFileSync(llmsTxtPath, "utf8")}\n${injectedLine}\n`;
    expect(findForbidden(mutated)).toContain(id);
  });
});

// Innocence, second half: a longer figure that merely CONTAINS a forbidden one is not the
// forbidden one. Without the numeric boundaries these lines convicted (codex spalla).
it.each([
  ["- E33E - Second Home Senior 5 Years: IDR 45.000.000 (all-inclusive)"],
  ["- E33 - Second Home Visa 5 Years: IDR 35.000.000 (all-inclusive)"],
  ["- **E33**: Second Home applicant assets: IDR 5.000.000.000"],
  ["- **E33**: Second Home applicant assets: IDR 5,000,000,000"],
  ["- **E33**: Second Home applicant assets: IDR 180.000.000.000"],
])(
  "a longer figure containing a forbidden one is innocent: %s",
  (innocentLine) => {
    const augmented = `${readFileSync(llmsTxtPath, "utf8")}\n${innocentLine}\n`;
    expect(findForbidden(augmented)).toEqual([]);
  },
);
