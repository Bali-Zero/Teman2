import { readdirSync, readFileSync } from "node:fs";
import { basename, dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { describe, expect, it } from "vitest";

const APP_DIR = dirname(fileURLToPath(import.meta.url));
const FORBIDDEN = "NEXT_PUBLIC_API_URL";

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const file = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(file);
    return /\.[jt]sx?$/.test(file) && !/\.(test|spec|d)\.[jt]sx?$/.test(file)
      ? [file]
      : [];
  });
}

function inspect(
  file: string,
  source: string,
): { browser: boolean; hits: string[] } {
  const tree = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  // Next's client boundary is a module directive, not a directory property:
  // route.ts and Server Components in the same segment still run on the server.
  const directives: string[] = [];
  for (const statement of tree.statements) {
    if (
      !ts.isExpressionStatement(statement) ||
      !ts.isStringLiteral(statement.expression)
    )
      break;
    directives.push(statement.expression.text);
  }
  const browser =
    basename(file) === "api-client.ts" || directives.includes("use client");
  const hits: string[] = [];
  if (browser) {
    const visit = (node: ts.Node): void => {
      // Match the exact name regardless of receiver, excluding comments.
      // StringLiteralLike also covers env[`NAME`].
      if (
        (ts.isIdentifier(node) || ts.isStringLiteralLike(node)) &&
        node.text === FORBIDDEN
      ) {
        const { line } = tree.getLineAndCharacterOfPosition(
          node.getStart(tree),
        );
        hits.push(
          `${file}:${line + 1}: browser API calls must use the same-origin /api proxy`,
        );
      }
      ts.forEachChild(node, visit);
    };
    visit(tree);
  }
  return { browser, hits };
}

describe("browser API clients stay on the same-origin proxy", () => {
  it("checks the real app, including all three GARUDA API clients", () => {
    const inspected = sourceFiles(APP_DIR).map((file) => ({
      file: relative(APP_DIR, file),
      ...inspect(relative(APP_DIR, file), readFileSync(file, "utf8")),
    }));
    const browserFiles = inspected
      .filter((entry) => entry.browser)
      .map((entry) => entry.file);
    expect(browserFiles.length).toBeGreaterThan(100);
    expect(browserFiles).toEqual(
      expect.arrayContaining([
        "(workspace)/garuda-voa/api-client.ts",
        "visa/voa/orders/api-client.ts",
        "visa/voa/upload/api-client.ts",
      ]),
    );
    expect(inspected.flatMap((entry) => entry.hits)).toEqual([]);
  });

  it.each([
    [
      "visa/example/api-client.ts",
      "export const base = process.env.NEXT_PUBLIC_API_URL;",
    ],
    [
      "visa/example/page.tsx",
      '"use client"; const base = process.env.NEXT_PUBLIC_API_URL;',
    ],
    [
      "visa/example/page.tsx",
      '"use client"; const base = process.env["NEXT_PUBLIC_API_URL"];',
    ],
    [
      "visa/example/page.tsx",
      '"use client"; const base = process.env[`NEXT_PUBLIC_API_URL`];',
    ],
  ])("rejects executable browser references in %s", (file, source) => {
    expect(inspect(file, source).hits).toEqual([
      expect.stringContaining(`${file}:1:`),
    ]);
  });

  it("does not turn explanatory comments into violations or client directives", () => {
    expect(
      inspect(
        "visa/example/api-client.ts",
        `// ${FORBIDDEN} caused the incident\n/* ${FORBIDDEN} */\nexport const base = "/api";`,
      ).hits,
    ).toEqual([]);
    expect(
      inspect(
        "visa/example/page.tsx",
        `// "use client"\nconst base = process.env.${FORBIDDEN};`,
      ).browser,
    ).toBe(false);
  });

  it.each([
    "api/auth/login/route.ts",
    "api/portal/deadlines/ical/route.ts",
    "visa/voa/auth/continue/page.tsx",
  ])("preserves legitimate server-side configuration in %s", (file) => {
    // Login and calendar proxy upstream requests; continue renders a server-only
    // magic-link preview. None is browser code, so none needs a blanket exemption.
    const source = readFileSync(join(APP_DIR, file), "utf8");
    expect(source).toContain(`process.env.${FORBIDDEN}`);
    expect(inspect(file, source)).toEqual({ browser: false, hits: [] });
  });
});
