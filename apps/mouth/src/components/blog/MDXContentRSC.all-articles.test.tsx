// Two-tier MDX article compilation guard:
// - Tier 1 compiles every en+id article using `serialize` from "next-mdx-remote/serialize"
//   (compile-only, no evaluation) with the production mdxOptions.
// - Tier 2 evaluates the dangerous-identifier files with the production `renderMDXBody`,
//   because compiling+evaluating all ~1,700 files took ~100 s (over the 60 s CI budget).
import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";
import { serialize } from "next-mdx-remote/serialize";
import remarkGfm from "remark-gfm";
import { describe, expect, it } from "vitest";
import { renderMDXBody } from "./MDXContentRSC";

function stripImports(content: string): string {
  return content
    .replace(/^import\s+[\s\S]*?from\s+['"][^'"]+['"];?\s*$/gm, "")
    .replace(/^import\s*{[\s\S]*?}\s*from\s*['"][^'"]+['"];?\s*$/gm, "")
    .trim();
}

const ARTICLES_ROOT = path.join(process.cwd(), "src/content/articles");

const DANGEROUS_IDENTIFIER_RE =
  /\b(Function|constructor|eval|__proto__|prototype)\b/;

const TIER1_SERIALIZE_OPTIONS = {
  mdxOptions: {
    remarkPlugins: [remarkGfm],
    development: false,
  },
};

const CURE_MESSAGE =
  "Cure: a bare '<' before a digit/space/'=' is parsed by MDX as the start of a JSX tag - write &lt; (renders '<') or words ('kurang dari'); an unbalanced </InfoCard> or an unclosed JSX tag must be closed on its own line after a blank line; an unescaped { } in prose must be written as \\{ \\}.";

interface CompileFailure {
  file: string;
  message: string;
}

function extractErrorLine(err: unknown): number | null {
  if (err && typeof err === "object") {
    const maybeLine = (err as { line?: unknown }).line;
    if (
      typeof maybeLine === "number" &&
      Number.isFinite(maybeLine) &&
      maybeLine > 0
    ) {
      return maybeLine;
    }
    const maybePlace = (
      err as {
        place?: { line?: unknown; start?: { line?: unknown } };
      }
    ).place;
    if (
      typeof maybePlace?.start?.line === "number" &&
      Number.isFinite(maybePlace.start.line) &&
      maybePlace.start.line > 0
    ) {
      return maybePlace.start.line;
    }
    if (
      typeof maybePlace?.line === "number" &&
      Number.isFinite(maybePlace.line) &&
      maybePlace.line > 0
    ) {
      return maybePlace.line;
    }
    const maybePosLine = (err as { position?: { start?: { line?: unknown } } })
      .position?.start?.line;
    if (
      typeof maybePosLine === "number" &&
      Number.isFinite(maybePosLine) &&
      maybePosLine > 0
    ) {
      return maybePosLine;
    }
  }
  const text = err instanceof Error ? err.message : String(err);
  const gutterMatch = text.match(/^>\s*(\d+)\s*\|/m);
  if (gutterMatch) {
    return Number(gutterMatch[1]);
  }
  const posMatch = text.match(/(?:^|[\s(])(\d+):\d+(?:$|[\s)-])/);
  if (posMatch) {
    return Number(posMatch[1]);
  }
  return null;
}

function findFirstDangerousLine(body: string): number | null {
  const lines = body.split("\n");
  for (let i = 0; i < lines.length; i++) {
    if (DANGEROUS_IDENTIFIER_RE.test(lines[i])) {
      return i + 1;
    }
  }
  return null;
}

async function compileOne(
  source: string,
  lineOffset = 0,
): Promise<string | null> {
  const cleaned = stripImports(source);
  // Line-offset strategy: when `cleaned` (after stripImports + trim) is a suffix of
  // `source.trimEnd()` (true whenever there are no mid-body imports, including when
  // top-of-body imports or leading blank lines after frontmatter were removed),
  // `(sourceTrimmed lines) - (cleaned lines)` is the exact additional top-of-body
  // line offset. Combined with the caller's `lineOffset` (frontmatter lines),
  // `bodyLine + effectiveOffset` equals the exact 1-based line in the raw file.
  // If mid-body imports were removed so `cleaned` is not a suffix, we report the
  // 1-based stripped body line with "(body line, imports/frontmatter stripped)".
  const sourceTrimmed = source.trimEnd();
  const isSuffix = cleaned.length === 0 || sourceTrimmed.endsWith(cleaned);
  const effectiveOffset = isSuffix
    ? lineOffset +
      (sourceTrimmed.split("\n").length - cleaned.split("\n").length)
    : 0;
  const formatLine = (bodyLine: number, note?: string): string => {
    if (isSuffix) {
      const fileLine = bodyLine + effectiveOffset;
      return note ? `line ${fileLine} (${note})` : `line ${fileLine}`;
    }
    return note
      ? `line ${bodyLine} (${note}, body line, imports/frontmatter stripped)`
      : `line ${bodyLine} (body line, imports/frontmatter stripped)`;
  };

  try {
    await serialize(cleaned, TIER1_SERIALIZE_OPTIONS);
    if (DANGEROUS_IDENTIFIER_RE.test(cleaned)) {
      await renderMDXBody(cleaned);
    }
    return null;
  } catch (err) {
    const rawMessage = err instanceof Error ? err.message : String(err);
    const snippet = rawMessage.replace(/\s+/g, " ").trim().slice(0, 160);

    // next-mdx-remote wraps MDX errors in a plain Error with no .line/.place/.cause.
    // Re-compile the same stripped source with raw @mdx-js/mdx to read VFileMessage
    // position fields (`err.line` or `err.place?.start?.line` / `err.place?.line`).
    let bodyLine: number | null = extractErrorLine(err);
    let rawCompileSucceeded = false;

    if (bodyLine === null) {
      try {
        const { compile } = await import("@mdx-js/mdx");
        try {
          await compile(cleaned, {
            remarkPlugins: [remarkGfm],
            development: false,
          });
          rawCompileSucceeded = true;
        } catch (rawErr) {
          bodyLine = extractErrorLine(rawErr);
        }
      } catch {
        // Dynamic import of @mdx-js/mdx failed; degrade gracefully to "line unknown".
      }
    }

    let lineLabel: string;
    if (bodyLine !== null) {
      lineLabel = formatLine(bodyLine);
    } else if (rawCompileSucceeded) {
      const dangerousLine = /security/i.test(rawMessage)
        ? findFirstDangerousLine(cleaned)
        : null;
      if (dangerousLine !== null) {
        lineLabel = formatLine(dangerousLine, "first dangerous identifier");
      } else {
        lineLabel = `line unknown (evaluation: ${snippet.slice(0, 120)})`;
      }
    } else {
      lineLabel = "line unknown";
    }

    return `${lineLabel}: ${snippet}`;
  }
}

function walkMdxFiles(dir: string): string[] {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const results: string[] = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkMdxFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith(".mdx")) {
      results.push(fullPath);
    }
  }
  return results.sort();
}

async function compileArticlesInChunks(
  files: string[],
  chunkSize = 8,
): Promise<CompileFailure[]> {
  const failures: CompileFailure[] = [];
  for (let i = 0; i < files.length; i += chunkSize) {
    const batch = files.slice(i, i + chunkSize);
    const batchResults = await Promise.all(
      batch.map(async (absPath): Promise<CompileFailure | null> => {
        const relFile = path.relative(process.cwd(), absPath);
        const raw = fs.readFileSync(absPath, "utf8");
        const parsed = matter(raw);
        const offset =
          raw.split("\n").length - parsed.content.split("\n").length;
        const errMessage = await compileOne(parsed.content, offset);
        if (errMessage !== null) {
          return { file: relFile, message: errMessage };
        }
        return null;
      }),
    );
    for (const item of batchResults) {
      if (item !== null) {
        failures.push(item);
      }
    }
  }
  return failures;
}

function formatFailureAssertionMessage(
  localeLabel: string,
  failures: CompileFailure[],
): string {
  const details = failures.map((f) => `${f.file} (${f.message})`).join("\n");
  return details
    ? `${localeLabel} MDX compilation failed:\n${details}\n${CURE_MESSAGE}`
    : CURE_MESSAGE;
}

const allMdxFiles = walkMdxFiles(ARTICLES_ROOT);
const englishFiles = allMdxFiles.filter(
  (file) => !/\.(id|it|fr|ru)\.mdx$/.test(path.basename(file)),
);
const indonesianFiles = allMdxFiles.filter((file) => file.endsWith(".id.mdx"));

describe("MDXContentRSC article compilation guard", () => {
  it("detects unescaped '<' before a digit and unquoted dangerous keys (guilt) and passes escaped/quoted forms (innocence)", async () => {
    const guilt = await compileOne("- Habiskan <183 hari/tahun di Indonesia");
    expect(guilt).not.toBeNull();
    expect(guilt).toMatch(/^line 1:/);

    const innocence = await compileOne(
      "- Habiskan &lt;183 hari/tahun di Indonesia",
    );
    expect(innocence).toBeNull();

    const tier2Guilt = await compileOne('<Box items={[{ Function: "x" }]} />');
    expect(tier2Guilt).not.toBeNull();
    expect(tier2Guilt).toMatch(/^line 1 \(first dangerous identifier\):/);
    expect(tier2Guilt).toContain("Security");

    const tier2Innocence = await compileOne(
      '<Box items={[{ "Function": "x" }]} />',
    );
    expect(tier2Innocence).toBeNull();
  });

  it("every English article compiles", async () => {
    const failures = await compileArticlesInChunks(englishFiles, 8);
    expect(
      failures,
      formatFailureAssertionMessage("English", failures),
    ).toEqual([]);
  }, 180000);

  it("every Indonesian article compiles", async () => {
    const failures = await compileArticlesInChunks(indonesianFiles, 8);
    expect(
      failures,
      formatFailureAssertionMessage("Indonesian", failures),
    ).toEqual([]);
  }, 180000);
});
