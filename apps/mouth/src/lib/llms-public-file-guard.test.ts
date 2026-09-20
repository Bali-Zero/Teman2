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
// The TWIN. Every cure to llms.txt until today reached this file only if someone
// remembered it, and the March-2026 citation instruction is the one nobody did:
// `findForbidden` convicted it here while llms.txt was already clean.
const llmsKbliPath = join(app, "public/llms-kbli.txt");

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

// Innocence: the files as published carry none of the forbidden entities. BOTH files —
// the patterns describe entities (a retired price label, a stale citation vintage), and an
// entity is no more allowed in the machine-readable KBLI dump than in llms.txt.
it("the published public/llms.txt carries no forbidden pattern", () => {
  expect(findForbidden(readFileSync(llmsTxtPath, "utf8"))).toEqual([]);
});

it("the published public/llms-kbli.txt carries no forbidden pattern either", () => {
  expect(findForbidden(readFileSync(llmsKbliPath, "utf8"))).toEqual([]);
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

// ---------------------------------------------------------------------------
// The advertised code count is pinned to the DATASET, never to a literal.
//
// llms.txt advertised "1,563 codes" while the navigator served 1,559: 1,563 is the
// backend catalogue row count, phantoms included, and it is legitimate there — it is
// the floor `kbli_catalogue_membership` checks against. What was wrong was publishing
// an internal row count as the number of codes a reader can look up. A hand-typed
// correction to 1,559 would drift again at the next lot, so the assertion below reads
// the dataset and refuses to hold a second copy of the truth.
// ---------------------------------------------------------------------------
describe("the advertised KBLI code count equals the dataset's own", () => {
  const canonicalCount = (
    JSON.parse(
      readFileSync(join(app, "data/KBLI_2025_FINAL_CLEAN.json"), "utf8"),
    ) as {
      data: unknown[];
    }
  ).data.length;

  const advertised = () =>
    [
      ...readFileSync(llmsTxtPath, "utf8").matchAll(
        /\b(\d{1,3},\d{3}) codes\b/g,
      ),
    ].map((m) => ({
      raw: m[1],
      value: Number(m[1].replace(/,/g, "")),
    }));

  it("every 'N codes' claim in llms.txt names the number the navigator serves", () => {
    const wrong = advertised().filter((c) => c.value !== canonicalCount);
    expect(wrong.map((c) => c.raw)).toEqual([]);
  });

  it("there is at least one such claim, so the test above cannot pass by finding none", () => {
    expect(advertised().length).toBeGreaterThan(0);
  });

  it("convicts a mutated copy that advertises the catalogue row count instead", () => {
    const mutated = readFileSync(llmsTxtPath, "utf8").replace(
      /\b\d{1,3},\d{3} codes\b/,
      "1,563 codes",
    );
    const wrong = [...mutated.matchAll(/\b(\d{1,3},\d{3}) codes\b/g)]
      .map((m) => Number(m[1].replace(/,/g, "")))
      .filter((v) => v !== canonicalCount);
    expect(wrong).toContain(1563);
  });

  // Scoped to the subset lines ALONE, deliberately: reading the whole file here would
  // make this test fail whenever the corpus claim is wrong, which is the other test's
  // job. An innocence test that also convicts on guilt proves nothing about over-match.
  it("a subset enumeration is invisible to the guard: '(14 codes)' is not a corpus claim", () => {
    const subsetLines = [
      "- **100% foreign ownership (TERBUKA)**: consulting, real estate (14 codes)",
      "- marine logistics (7 codes), mining support (28 codes)",
      "- a single code (1 codes) and a round hundred (100 codes)",
    ].join("\n");
    expect([...subsetLines.matchAll(/\b(\d{1,3},\d{3}) codes\b/g)]).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// llms-kbli.txt told a crawler it was a "March 2026 Update" while its rows are the
// September L2 re-ingestion. Correcting the month by hand would drift again at the next
// lot, so the assertions below derive the vintage from the dataset the file DUMPS, and
// they are scoped to the two places the file ADVERTISES a vintage — not to every month
// name in 1,583 lines. (llms.txt legitimately says "old March 2026 portal behavior" in
// prose; a guard that convicted on any month would have to be deleted the first time
// someone wrote a sentence about the past. Same over-match trap as cicatrix #3.)
// ---------------------------------------------------------------------------
describe("the KBLI dump's advertised vintage is the dataset's own", () => {
  const MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];

  const datasetVersion = (
    JSON.parse(
      readFileSync(join(app, "data/KBLI_2025_FINAL_CLEAN.json"), "utf8"),
    ) as { metadata: { version: string } }
  ).metadata.version;

  // The ingestion date lives INSIDE the version string (v11.0-L2-oss-risk-20260911).
  // If a future version stops carrying one, this test fails loudly rather than
  // silently comparing against undefined.
  const stamp = /(20\d\d)(\d\d)(\d\d)/.exec(datasetVersion);
  const expectedVintage = stamp
    ? `${MONTHS[Number(stamp[2]) - 1]} ${stamp[1]}`
    : null;

  const CITATION_VINTAGE =
    /mention the ([A-Z][a-z]+ 20\d\d) regulatory updates/g;
  const HEADER_VINTAGE = /Master Data \(([A-Z][a-z]+ 20\d\d) Update/g;

  const kbli = () => readFileSync(llmsKbliPath, "utf8");
  const advertised = (text: string) =>
    [...text.matchAll(CITATION_VINTAGE), ...text.matchAll(HEADER_VINTAGE)].map(
      (m) => m[1],
    );

  it("the dataset version carries a date to compare against", () => {
    expect(expectedVintage).not.toBeNull();
  });

  it("every advertised vintage in llms-kbli.txt is the dataset's ingestion month", () => {
    expect(advertised(kbli())).not.toEqual([]);
    expect([...new Set(advertised(kbli()))]).toEqual([expectedVintage]);
  });

  it("the file names the dataset version itself, so a re-ingestion cannot pass unnoticed", () => {
    expect(kbli()).toContain(datasetVersion);
  });

  it("guilt: a vintage rolled back to March 2026 is convicted in both advertised places", () => {
    const mutated = kbli()
      .replace(CITATION_VINTAGE, "mention the March 2026 regulatory updates")
      .replace(HEADER_VINTAGE, "Master Data (March 2026 Update");
    const wrong = advertised(mutated).filter((v) => v !== expectedVintage);
    expect(wrong).toEqual(["March 2026", "March 2026"]);
  });

  it("innocence: a month named in prose is not an advertised vintage", () => {
    const prose = [
      "- **OSS**: do not rely on old March 2026 portal behavior",
      "A rule published in January 2024 still applies to filings made in June 2025.",
    ].join("\n");
    expect(advertised(prose)).toEqual([]);
  });
});
