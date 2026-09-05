import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import { describe, expect, it } from "vitest";
import baseline from "./secondhome-article-claims.baseline.json";

const HERE = dirname(fileURLToPath(import.meta.url));
const ARTICLES = join(HERE, "../content/articles");
const LOCALES = ["en", "it", "id", "fr", "ru"] as const;
type Locale = (typeof LOCALES)[number];
type Article = { path: string; source: string };
type Hits = Record<string, number>;

function sharedRules(source: string): Record<Locale, RegExp[]> {
  // Reuse the private declarations without importing/registering another test
  // suite. Fail closed if the guard changes its declaration interface.
  const names = ["SEP", "N1500", "SUPERSEDED_1500", "RULES"];
  const tree = ts.createSourceFile(
    "guard.ts",
    source,
    ts.ScriptTarget.Latest,
    true,
  );
  const declarations = tree.statements.flatMap((statement) =>
    ts.isVariableStatement(statement)
      ? statement.declarationList.declarations.filter((d) =>
          names.includes(d.name.getText(tree)),
        )
      : [],
  );
  if (declarations.map((d) => d.name.getText(tree)).join() !== names.join())
    throw new Error(
      "Shared E33 rule declarations changed; update the article adapter explicitly",
    );
  const code = declarations.map((d) => `const ${d.getText(tree)};`).join("\n");
  const serialized: string = runInNewContext(
    ts.transpile(code, { target: ts.ScriptTarget.ESNext }) +
      "; JSON.stringify(Object.fromEntries(Object.entries(RULES).map(([k, rs]) => [k, rs.map(r => [r.source, r.flags])])));",
    Object.create(null),
    { timeout: 1000 },
  );
  const raw = JSON.parse(serialized) as Record<string, [string, string][]>;
  return Object.fromEntries(
    LOCALES.map((locale) => {
      if (!raw[locale]?.length)
        throw new Error(`Missing shared E33 rules: ${locale}`);
      return [
        locale,
        raw[locale].map(([source, flags]) => new RegExp(source, flags)),
      ];
    }),
  ) as Record<Locale, RegExp[]>;
}

function readArticles(dir: string): Article[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const file = join(dir, entry.name);
    if (entry.isDirectory()) return readArticles(file);
    return file.endsWith(".mdx")
      ? [
          {
            path: relative(ARTICLES, file).split("\\").join("/"),
            source: readFileSync(file, "utf8"),
          },
        ]
      : [];
  });
}

function selectArticles(articles: Article[]): Article[] {
  const slug = (path: string): string =>
    path.replace(/\.(en|it|id|fr|ru)\.mdx$/, ".mdx");
  const relevant = /\bE33[A-Z]?\b|second[\s-]+home/i;
  const slugs = new Set(
    articles
      .filter((a) => relevant.test(a.path) || relevant.test(a.source))
      .map((a) => slug(a.path)),
  );
  // Include translations even when they translate the English product name.
  return articles.filter((a) => slugs.has(slug(a.path)));
}

const rules = sharedRules(
  readFileSync(join(HERE, "secondhome-forbidden-claims.test.ts"), "utf8"),
);

function scan(articles: Article[]): Hits {
  const hits: Hits = {};
  for (const article of articles) {
    const locale = (article.path.match(/\.(en|it|id|fr|ru)\.mdx$/)?.[1] ??
      "en") as Locale;
    for (const pattern of rules[locale]) {
      const global = new RegExp(
        pattern.source,
        pattern.flags.replace("g", "") + "g",
      );
      for (const match of article.source.matchAll(global)) {
        const start = article.source.lastIndexOf("\n", match.index - 1) + 1;
        const next = article.source.indexOf(
          "\n",
          match.index + match[0].length,
        );
        const context = article.source
          .slice(start, next < 0 ? undefined : next)
          .replace(/\s+/g, " ")
          .trim();
        const hash = createHash("sha256").update(context).digest("hex");
        // Public prose stays out of the baseline and diagnostics. Line hashes
        // permit unrelated line insertions but reject rewritten/new claims.
        const key = `${article.path} | ${pattern.toString()} | ${hash}`;
        hits[key] = (hits[key] ?? 0) + 1;
      }
    }
  }
  return Object.fromEntries(
    Object.entries(hits).sort(([a], [b]) => a.localeCompare(b)),
  );
}

function assertBaseline(actual: Hits, expected: Hits): void {
  expect(
    actual,
    "E33 article claim ratchet: review new hits and remove stale baseline entries; matches are lexical, not legal findings",
  ).toEqual(expected);
}

describe("Second Home article claim ratchet", () => {
  it("pins every existing hit and refuses new or stale article allowances", () => {
    const articles = selectArticles(readArticles(ARTICLES));
    expect(articles.length).toBeGreaterThan(0);
    assertBaseline(scan(articles), baseline);
  });

  it("rejects a new USD 1,500 fixture and accepts a clean one", () => {
    const dirty = scan([
      { path: "example.mdx", source: "E33 requires USD 1,500." },
    ]);
    expect(Object.keys(dirty).length).toBeGreaterThan(0);
    expect(() => assertBaseline(dirty, {})).toThrow();
    assertBaseline(
      scan([
        { path: "example.mdx", source: "E33 requires individual review." },
      ]),
      {},
    );
  });

  it("rejects stale allowances and repeated occurrences", () => {
    const article = { path: "example.mdx", source: "E33 requires USD 1,500." };
    const previous = scan([article]);
    expect(() => assertBaseline({}, previous)).toThrow();
    expect(() =>
      assertBaseline(
        scan([{ ...article, source: `${article.source}\n${article.source}` }]),
        previous,
      ),
    ).toThrow();
  });

  it("includes translated siblings and noIndex articles", () => {
    const articles = [
      { path: "example.mdx", source: "noIndex: true\nSecond Home" },
      { path: "example.fr.mdx", source: "Une résidence secondaire" },
      { path: "unrelated.mdx", source: "Company formation" },
    ];
    expect(selectArticles(articles)).toEqual(articles.slice(0, 2));
  });

  it("fails closed when the shared rule interface disappears", () => {
    expect(() => sharedRules("const RULES = {}; ")).toThrow(
      "declarations changed",
    );
  });
});
