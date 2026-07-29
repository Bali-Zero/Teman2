import fs from "fs";
import path from "path";

import { describe, expect, it } from "vitest";

import { buildClientsQuery } from "@/app/api/clients/route";

/**
 * The first draft of `/api/clients` scoped its query with
 * `assigned_to = request.headers.get("x-user-email")`. Measured before merge:
 * that header appeared exactly once in the entire app — in the line that read it.
 * The middleware sets `x-admin-email`, and it sets it on the RESPONSE, which a
 * route handler never sees. So the predicate was always `assigned_to = ''` and the
 * clients page returned zero rows in every environment.
 *
 * That is the failure this corpus exists to prevent, and it is why the assertions
 * below are POSITIVE (the exact SQL) rather than "does not contain X": an
 * absence-only assertion passes in both the broken and the fixed world whenever the
 * broken behaviour was silence.
 */

const EXPECTED_SQL =
  "SELECT id, full_name, email, phone, status, assigned_to, created_at " +
  "FROM clients WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT $1 OFFSET $2";

describe("buildClientsQuery — the query cannot be emptied by a caller", () => {
  it("GUILT: the SQL is fixed — there is no principal-derived predicate to empty", () => {
    // Exact-match, so re-adding any `WHERE assigned_to = $n` clause fails here
    // instead of silently shipping an always-empty page.
    expect(buildClientsQuery(null).text).toBe(EXPECTED_SQL);
    expect(buildClientsQuery("1").text).toBe(EXPECTED_SQL);
    expect(buildClientsQuery("7").text).toBe(EXPECTED_SQL);
  });

  it("GUILT: columns are an explicit allow-list, never SELECT *", () => {
    // The route this replaces was `SELECT * FROM "<table>"`, which returned every
    // column of the clients table. Naming them is the whole point.
    const { text } = buildClientsQuery(null);
    for (const col of [
      "id",
      "full_name",
      "email",
      "phone",
      "status",
      "assigned_to",
      "created_at",
    ]) {
      expect(text).toContain(col);
    }
    expect(text).not.toContain("*");
  });

  it("GUILT: soft-deleted rows stay out", () => {
    expect(buildClientsQuery(null).text).toContain("deleted_at IS NULL");
  });

  it("GUILT: a non-numeric page does not reach pg as a NaN OFFSET", () => {
    // `Math.max(1, parseInt("abc", 10))` is NaN, and NaN as a bind value makes pg
    // throw at query time — a 500 on a URL anyone can type.
    for (const bad of ["abc", "", "  ", "NaN", "1e", "null"]) {
      const q = buildClientsQuery(bad);
      expect(Number.isFinite(q.page), `page for ${JSON.stringify(bad)}`).toBe(
        true,
      );
      expect(q.values.every(Number.isFinite)).toBe(true);
      expect(q.page).toBe(1);
      expect(q.values).toEqual([100, 0]);
    }
  });

  it("GUILT: zero and negative pages clamp to the first page", () => {
    expect(buildClientsQuery("0").values).toEqual([100, 0]);
    expect(buildClientsQuery("-5").values).toEqual([100, 0]);
  });

  it("INNOCENCE: real pagination still paginates", () => {
    expect(buildClientsQuery("1").values).toEqual([100, 0]);
    expect(buildClientsQuery("2").values).toEqual([100, 100]);
    expect(buildClientsQuery("3").values).toEqual([100, 200]);
    expect(buildClientsQuery("3").page).toBe(3);
  });

  it("INNOCENCE: limit and offset travel as bind values, not interpolated text", () => {
    const { text, values } = buildClientsQuery("2");
    expect(text).toContain("LIMIT $1 OFFSET $2");
    expect(text).not.toContain("100");
    expect(values).toEqual([100, 100]);
  });
});

/**
 * Pattern-fix = class-audit. Curing only the route that bit us would leave the next
 * one free to invent the same phantom principal.
 *
 * The first version of this sweep matched the raw source and immediately failed on
 * `route.ts` — not on a read, but on the DOC COMMENT above it that quotes the
 * defect verbatim. It judged the form (a substring) instead of the entity (an
 * actual call), which is the same over-match the codebase keeps re-learning. So the
 * scan strips comments first, and the stripper gets its own guilt+innocence cases
 * below rather than being trusted.
 *
 * DECLARED LIMIT: only block comments and whole-line `//` comments are stripped. A
 * trailing `// … headers.get("x-user-email")` on a code line would still trip it —
 * deliberately, because stripping from any `//` would swallow the rest of a line
 * that legitimately contains `http://`, turning this guard's false positive into a
 * false negative, which is the worse of the two.
 */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[ \t]*\/\/.*$/gm, "");
}

const SPOOFABLE_EMAIL_HEADER_READ =
  /headers\s*\.\s*get\(\s*["'`]x-user-email["'`]\s*\)/;

function readsSpoofableEmailHeader(src: string): boolean {
  return SPOOFABLE_EMAIL_HEADER_READ.test(stripComments(src));
}

describe("the class defect: a route must not gate on a header nobody sets", () => {
  it("GUILT (the guard itself): a real read is caught", () => {
    expect(
      readsSpoofableEmailHeader(
        'const u = request.headers.get("x-user-email") ?? "";',
      ),
    ).toBe(true);
    expect(
      readsSpoofableEmailHeader(
        "const u = request.headers.get('x-user-email');",
      ),
    ).toBe(true);
  });

  it("INNOCENCE (the guard itself): merely describing the defect is not committing it", () => {
    // This is the exact case that failed the first draft of this sweep.
    expect(
      readsSpoofableEmailHeader(
        '/**\n * It used to call request.headers.get("x-user-email"), which nobody sets.\n */\nconst q = build();',
      ),
    ).toBe(false);
    expect(
      readsSpoofableEmailHeader(
        '// never do request.headers.get("x-user-email")\nconst q = build();',
      ),
    ).toBe(false);
    // …and a URL on a code line must not blind it (the under-match twin).
    expect(
      readsSpoofableEmailHeader(
        'const base = "http://x"; const u = request.headers.get("x-user-email");',
      ),
    ).toBe(true);
  });

  it("GUILT: no API route reads x-user-email", () => {
    // `x-admin-email` is the only email header this app ever produces, and it is a
    // RESPONSE header — no handler can read either one from an inbound request.
    const apiRoot = path.resolve(__dirname, "..", "app", "api");
    const files: string[] = [];
    const walk = (dir: string) => {
      for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, e.name);
        if (e.isDirectory()) walk(p);
        else if (p.endsWith(".ts") || p.endsWith(".tsx")) files.push(p);
      }
    };
    walk(apiRoot);

    // A zero-length list would pass the loop below and prove nothing — an empty set
    // disguises itself as both ALL and NOTHING.
    expect(files.length).toBeGreaterThan(5);

    for (const file of files) {
      const src = fs.readFileSync(file, "utf-8");
      expect(
        readsSpoofableEmailHeader(src),
        `${file} reads a header the middleware never sets`,
      ).toBe(false);
    }
  });
});
