// Single-tier MDX article compilation guard:
// Compiles every en+id article using `serialize` from "next-mdx-remote/serialize"
// (compile-only, `skipRender: true`) with the exact production compileMDX options
// (`blockJS: false`, `blockDangerousJS: true`, `remarkGfm`, `development: false`).
import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";
import { serialize } from "next-mdx-remote/serialize";
import remarkGfm from "remark-gfm";
import { stripImports } from "@/lib/blog/strip-imports";

// Anchored to this file (vite-node provides __dirname), never to process.cwd().
export const ARTICLES_ROOT = path.resolve(__dirname, "../../content/articles");

const SECURITY_KEY_RE =
  /(?:^\s*|[{,]\s*)(Function|constructor|eval|__proto__|prototype|module|process|global|globalThis|exports|require|fs|http|https|net|vm|Reflect|child_process|Buffer|window|document)\s*:/;

const SECURITY_MEMBER_RE =
  /\b(process|global|globalThis|module|exports|require|Function|constructor|eval|__proto__|prototype|fs|http|https|net|vm|Reflect|child_process|Buffer|window|document)\s*(?:\.[A-Za-z_$]|\[)/;

export const CURE_MESSAGE =
  "Cure: a bare '<' before a digit/space/'=' is parsed by MDX as the start of a JSX tag - write &lt; (renders '<') or words ('kurang dari'); an unbalanced </InfoCard> or an unclosed JSX tag must be closed on its own line after a blank line; an unescaped { } in prose must be written as \\{ \\}; an object key named like a JS global (Function, module, process, global, ...) must be quoted: \"Function\": ...";

export interface CompileFailure {
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

function findSecurityErrorLine(body: string): number | null {
  const lines = body.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (SECURITY_KEY_RE.test(line) || SECURITY_MEMBER_RE.test(line)) {
      return i + 1;
    }
  }
  return null;
}

export async function compileOne(
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
  const formatLine = (bodyLine: number): string => {
    if (isSuffix) {
      const fileLine = bodyLine + effectiveOffset;
      return `line ${fileLine}`;
    }
    return `line ${bodyLine} (body line, imports/frontmatter stripped)`;
  };

  try {
    await serialize(
      cleaned,
      {
        blockJS: false,
        blockDangerousJS: true,
        mdxOptions: {
          remarkPlugins: [remarkGfm],
          development: false,
        },
      },
      true,
    );
    return null;
  } catch (err) {
    const rawMessage = err instanceof Error ? err.message : String(err);
    const snippet = rawMessage.replace(/\s+/g, " ").trim().slice(0, 160);

    // next-mdx-remote wraps MDX errors in a plain Error with no .line/.place/.cause.
    // Re-compile the same stripped source with raw @mdx-js/mdx to read VFileMessage
    // position fields (`err.line` or `err.place?.start?.line` / `err.place?.line`).
    let bodyLine: number | null = extractErrorLine(err);

    if (bodyLine === null && !/security/i.test(rawMessage)) {
      try {
        const { compile } = await import("@mdx-js/mdx");
        try {
          await compile(cleaned, {
            remarkPlugins: [remarkGfm],
            development: false,
          });
        } catch (rawErr) {
          bodyLine = extractErrorLine(rawErr);
        }
      } catch {
        // Dynamic import of @mdx-js/mdx failed; degrade gracefully to "line unknown".
      }
    }

    if (bodyLine === null && /security/i.test(rawMessage)) {
      bodyLine = findSecurityErrorLine(cleaned);
    }

    const lineLabel = bodyLine !== null ? formatLine(bodyLine) : "line unknown";
    return `${lineLabel}: ${snippet}`;
  }
}

export function walkMdxFiles(dir: string): string[] {
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

export async function compileArticlesInChunks(
  files: string[],
  chunkSize = 8,
): Promise<CompileFailure[]> {
  const failures: CompileFailure[] = [];
  for (let i = 0; i < files.length; i += chunkSize) {
    const batch = files.slice(i, i + chunkSize);
    const batchResults = await Promise.all(
      batch.map(async (absPath): Promise<CompileFailure | null> => {
        const relFile = path.relative(ARTICLES_ROOT, absPath);
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

export function formatFailureAssertionMessage(
  localeLabel: string,
  failures: CompileFailure[],
): string {
  const details = failures.map((f) => `${f.file} (${f.message})`).join("\n");
  return details
    ? `${localeLabel} MDX compilation failed:\n${details}\n${CURE_MESSAGE}`
    : CURE_MESSAGE;
}
