import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

/**
 * Brand-suffix guard for page titles (2026-07-28).
 *
 * TRAUMA: the root layout sets `title.template = "%s | Bali Zero"`, so Next.js
 * appends the brand to every page title automatically. Eleven pages appended it
 * a second time by hand, and shipped a stutter to production:
 *
 *   <title>Careers — Bali Zero | Bali Zero</title>
 *   <title>Zoning Check — Verifikasi Zonasi Properti Bali Anda | Bali Zero | Bali Zero</title>
 *
 * Measured live on 5 of 5 pages sampled before the fix. Nobody noticed because
 * each page looks right in isolation — the defect only exists in the COMPOSITION
 * of the page's title with a template declared in a different file. It cost real
 * estate too: Google shows ~60 characters, and the repeat burned twelve of them.
 *
 * The guard checks the composition, so the twelfth page cannot repeat it.
 *
 * Deliberately NOT flagged: a title that mentions the brand mid-string (e.g.
 * "Terms of Service — Bali Zero — Visa"). That is editorial phrasing, not the
 * mechanical stutter — the innocence case below pins that it stays legal.
 */

const APP_DIR = path.dirname(fileURLToPath(import.meta.url));

/** Trailing `| Bali Zero`, `— Bali Zero`, `- Bali Zero` — with any spacing. */
const TRAILING_BRAND = /\s*[|—–-]\s*Bali Zero\s*$/;

function tsxFiles(dir: string): string[] {
  const out: string[] = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...tsxFiles(p));
    else if (e.name.endsWith(".tsx")) out.push(p);
  }
  return out;
}

/** Top-level static `title:` string literals from `export const metadata` objects. */
function staticTitles(): { file: string; title: string }[] {
  const found: { file: string; title: string }[] = [];
  for (const file of tsxFiles(APP_DIR)) {
    const src = fs.readFileSync(file, "utf8");
    const decl = /export const metadata[^=]*=\s*\{/.exec(src);
    if (!decl) continue;
    const tail = src.slice(decl.index + decl[0].length);
    // two-space indent = first level of the metadata object; a nested
    // openGraph/twitter title is indented deeper and is NOT templated by Next.
    const m =
      /^ {2}title:\s*("(?:[^"\\]|\\.)*")/m.exec(tail) ??
      /^ {2}title:\s*\n\s+("(?:[^"\\]|\\.)*")/m.exec(tail);
    if (!m) continue;
    found.push({
      file: path.relative(APP_DIR, file),
      title: JSON.parse(m[1]) as string,
    });
  }
  return found;
}

describe("page titles vs the root title template", () => {
  it("finds titles to check (the probe can produce a positive)", () => {
    // An empty scan would make the assertion below vacuously true — the
    // failure mode where a guard passes because it looked at nothing.
    expect(staticTitles().length).toBeGreaterThanOrEqual(8);
  });

  it("no page appends the brand the template already appends", () => {
    const offenders = staticTitles()
      .filter((t) => TRAILING_BRAND.test(t.title))
      .map((t) => `${t.file}: ${t.title}`);
    expect(offenders).toEqual([]);
  });

  it("a brand mention mid-title is left alone (innocence)", () => {
    expect(TRAILING_BRAND.test("Terms of Service — Bali Zero — Visa")).toBe(
      false,
    );
    expect(TRAILING_BRAND.test("Bali Zero is here to help")).toBe(false);
  });

  it("catches every separator the codebase actually used (guilt)", () => {
    for (const bad of [
      "Careers — Bali Zero",
      "Visa Oracle — Prototype | Bali Zero",
      "Login - Bali Zero",
      "Something | Bali Zero ",
    ]) {
      expect(TRAILING_BRAND.test(bad)).toBe(true);
    }
  });
});
