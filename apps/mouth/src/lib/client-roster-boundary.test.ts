import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * THE BOUNDARY THIS FILE GUARDS
 *
 * The staff roster is an internal record. It is allowed on internal,
 * authenticated surfaces and it is allowed on the server. What it must not do is
 * cross into a `"use client"` module, because everything a client module imports
 * is shipped to the browser as JavaScript — including the records of the people
 * the owner excluded from public pages.
 *
 * This is not hypothetical. Measured on the built output before the fix this test
 * accompanies: chunk `75947-*.js` carried both excluded names and was loaded by
 * all six public routes, and `94651-*.js` added the two book routes. The rendered
 * HTML was already clean — the exclusion worked — so nothing a page test or a
 * browser walk could see was wrong. Only the bundle was.
 *
 * Three imports put it there and none looked like a mistake: SocialProof.tsx was
 * `"use client"` and resolved its own people; a workspace page imported the
 * four-line `initialsOf` helper from the module that also holds the roster array;
 * and `book-data.ts` derived the book grid at module scope while seven client
 * components imported it for other exports. The bundler follows imports, not
 * intentions.
 *
 * So the rule is structural and this test is its tripwire. Deleting it, or
 * emptying ROSTER_GRAPH_MODULES, is the only way to make a regression legal — and
 * both are visible in review, which a silently re-grown chunk is not.
 */

const SRC = join(__dirname, "..");

/**
 * Every module whose graph reaches the roster — not only the roster itself.
 *
 * The direct edge is the obvious one and it is NOT the one that caused the
 * incident: `book-data.ts` imported `team-public-listing`, never `team-roster`,
 * and shipped the whole roster to /book and /book/team regardless. A tripwire
 * watching only `@/data/team-roster` would have stayed green through the entire
 * original defect. So the filter module and the two new server resolvers are
 * listed here too.
 *
 * The airtight version of this rule is `import "server-only"` in each of these
 * modules, which makes the BUILD refuse rather than a test. That package is not
 * installed in this app and adding it edits package.json, which this PR may not
 * touch — recorded as a named remainder in the evidence pack.
 */
const ROSTER_GRAPH_MODULES = [
  "data/team-roster",
  "lib/team-public-listing",
  "socialProofRoster",
  "book-team",
  // The workspace directory module: it reads the roster to build the internal
  // photo map, so a "use client" page importing it would put the records back in
  // that route's chunk — exactly the defect the module exists to fix, and the
  // reason the three workspace pages now have server wrappers.
  "workspace/roster-directory",
];

/**
 * The guard script's chunk exception list, pinned from here — and now EMPTY.
 *
 * C4 carried one time-boxed entry, `app/(workspace)/clients/`, while that route
 * still hardcoded the tax-consultant table. C4b removed the hardcoding (the table
 * is resolved server-side and passed as a prop), so the entry is gone from
 * ALLOWED_CHUNK_PREFIXES in scripts/assert-roster-not-in-public-chunks.mjs and
 * gone from here.
 *
 * This test fails if the list grows, shrinks to something else, or is quietly
 * reworded: an exception that can be added without a red test is not an
 * exception, it is a hole with a comment.
 */
const EXPECTED_CHUNK_EXCEPTIONS: readonly string[] = [];

/**
 * EMPTY, and that is the assertion.
 *
 * There used to be one declared exception: `book-data.ts` derived the book team
 * grid from the roster at module scope. It is closed — the derivation moved to
 * `book-team.ts` (server) and the members reach `TeamGrid` as props from the two
 * book routes. Adding an entry back is how a regression becomes legal, and
 * pinning the list at empty makes that a visible decision.
 */
const KNOWN_CLIENT_ROSTER_PATHS: readonly string[] = [];

/**
 * Source with comments removed — block AND line. The line-comment arm is not
 * decoration: every module in this repo opens with a `// path` header, so a rule
 * that skipped only block comments would miss the house style it polices.
 */
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
}

/**
 * True when `"use client"` is the module's first statement.
 *
 * Comments are stripped FIRST. An earlier version of this helper allowed one
 * optional block comment before the directive and nothing else, so a client
 * component carrying the ordinary `// path` header on line 1 was not recognised
 * as a client module at all and could import the roster with this suite green —
 * a tripwire reporting the absence of the files it could not see.
 */
function isClientModule(source: string): boolean {
  return /^\s*["'`]use client["'`]/.test(stripComments(source));
}

/**
 * Which roster-graph modules this source pulls in, by ANY import shape.
 *
 * `from "…"` is only one of them. A side-effect import has no `from`; neither
 * does `import()` or `require()`; and `import{x}from"y"` has no whitespace at
 * all. Each carries the module just as effectively and each was invisible to the
 * first version of this check. Comments are stripped so a line like "never
 * import from @/data/team-roster here" cannot false-trip it either.
 */
function importsRosterGraph(source: string): string[] {
  // `import type { X } from "…"` is erased by the compiler and carries nothing
  // at runtime, so it is NOT a boundary crossing — SocialProof legitimately
  // takes its row type from the server resolver that way. Dropping the `type`
  // keyword is a one-word change that compiles clean and ships the module, so
  // the erasure is applied here and nowhere else: remove the type-only
  // statements, then judge what is left.
  const code = stripComments(source)
    .replace(/import\s+type\s+[^;]*;/g, "")
    .replace(/export\s+type\s+[^;]*;/g, "");
  return ROSTER_GRAPH_MODULES.filter((mod) =>
    new RegExp(
      "(?:from|import|require)\\s*\\(?\\s*[\"'`][^\"'`]*" + mod + "[\"'`]",
    ).test(code),
  );
}

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry.startsWith(".")) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(entry) && !/\.test\.tsx?$/.test(entry))
      out.push(full);
  }
  return out;
}

const files = walk(SRC);

describe("the roster does not cross the client boundary", () => {
  it("finds the files it is supposed to be scanning", () => {
    // A walker that silently returned nothing would make every assertion below
    // pass while checking absolutely nothing.
    expect(files.length).toBeGreaterThan(200);
    expect(
      files.some((f) => f.endsWith("app/v2/_components/SocialProof.tsx")),
    ).toBe(true);
    expect(files.some((f) => f.endsWith("data/team-roster.ts"))).toBe(true);
  });

  it("recognises a client module whatever precedes the directive", () => {
    // The detector's own guilt probe. Each of these IS a client module.
    expect(isClientModule('"use client";\n')).toBe(true);
    expect(isClientModule('// apps/mouth/src/x.tsx\n"use client";\n')).toBe(
      true,
    );
    expect(isClientModule('/* header */\n"use client";\n')).toBe(true);
    expect(isClientModule("'use client';\n")).toBe(true);
    // and these are not
    expect(isClientModule('import x from "y";\n"use client";\n')).toBe(false);
    expect(
      isClientModule('// a comment mentioning "use client"\nexport {};\n'),
    ).toBe(false);
  });

  it("catches every import shape that carries the roster graph", () => {
    // The other half of the detector's guilt probe: `from` is not the only way.
    for (const src of [
      'import { rosterBySlug } from "@/data/team-roster";',
      'import "@/data/team-roster";',
      'const m = await import("@/data/team-roster");',
      'const m = require("@/data/team-roster");',
      'import{rosterBySlug}from"@/data/team-roster";',
      'import { publicRoster } from "@/lib/team-public-listing";',
      'import { socialProofRoster } from "./socialProofRoster";',
      'import { bookTeamMembers } from "./book-team";',
      'import { teamPhotoMap } from "@/lib/workspace/roster-directory";',
    ]) {
      expect(importsRosterGraph(src), src).not.toEqual([]);
    }
    // `import type` is erased — allowed. Dropping the keyword is not.
    expect(
      importsRosterGraph('import type { M } from "./socialProofRoster";'),
    ).toEqual([]);
    expect(
      importsRosterGraph('import { M } from "./socialProofRoster";'),
    ).not.toEqual([]);
    // a comment must not trip it, and an unrelated import must not either
    expect(
      importsRosterGraph('// never import from "@/data/team-roster" here'),
    ).toEqual([]);
    expect(
      importsRosterGraph('import { x } from "@/lib/trust-figures";'),
    ).toEqual([]);
  });

  it("no 'use client' module imports the roster graph — no exceptions left", () => {
    const offenders = files
      .filter((f) => {
        const src = readFileSync(f, "utf8");
        return isClientModule(src) && importsRosterGraph(src).length > 0;
      })
      .map((f) => f.slice(SRC.length + 1));

    expect(offenders).toEqual([]);
    expect(KNOWN_CLIENT_ROSTER_PATHS).toEqual([]);
  });

  it("book-data holds no roster, so its seven client importers carry none", () => {
    const bookData = readFileSync(
      join(SRC, "components/book/book-data.ts"),
      "utf8",
    );
    expect(importsRosterGraph(bookData)).toEqual([]);
    // Identifiers are checked on the RAW source: stripping comments first can
    // only ever delete evidence and make an absence assertion easier to pass.
    const bookCode = stripComments(bookData);
    expect(bookCode).not.toContain("publicRoster(");
    expect(bookCode).not.toContain("export const TEAM_MEMBERS");

    // and the derivation still exists, on the server, with the filter in it
    const bookTeam = readFileSync(
      join(SRC, "components/book/book-team.ts"),
      "utf8",
    );
    expect(isClientModule(bookTeam)).toBe(false);
    expect(bookTeam).toContain("publicRoster");
  });

  it("SocialProof stays a CLIENT component and imports no roster graph", () => {
    const src = readFileSync(
      join(SRC, "app/v2/_components/SocialProof.tsx"),
      "utf8",
    );
    // It must STAY client: it hands `next/image` an `onError` fallback, and a
    // server component cannot pass an event handler to a client component.
    // Deleting the directive to get the roster out of the bundle looked like the
    // minimal fix and was measured wrong — /v2 threw "Event handlers cannot be
    // passed to Client Component props" on every portrait and rendered an error
    // boundary. The directive was never the problem; the import was.
    expect(isClientModule(src)).toBe(true);
    expect(src).toContain("onError");
    // `import type` is erased, so the type-only edge to the resolver is allowed
    // and is the ONLY thing that may reference it here.
    // type-only edge to the resolver is fine and is the only reference allowed
    expect(importsRosterGraph(src)).toEqual([]);
    expect(src).toContain("import type { SocialProofMember }");
    expect(src).toContain("founders");
    expect(src).toContain("team");
  });

  it("the server resolver is not a client module and owns the exclusion", () => {
    const src = readFileSync(
      join(SRC, "app/v2/_components/socialProofRoster.ts"),
      "utf8",
    );
    expect(isClientModule(src)).toBe(false);
    // The filter has to be here, or the exclusion is applied nowhere for these
    // two surfaces.
    expect(src).toContain("publicEntries");
  });

  it("the guard's chunk exception is exactly the one declared, time-boxed entry", () => {
    // Read the guard's source rather than importing it: the script exits the
    // process on failure, which a test runner should never invite.
    const guard = readFileSync(
      join(SRC, "..", "scripts", "assert-roster-not-in-public-chunks.mjs"),
      "utf8",
    );
    const m = guard.match(/const ALLOWED_CHUNK_PREFIXES = (\[[^\]]*\]);/);
    expect(m, "ALLOWED_CHUNK_PREFIXES not found in the guard").toBeTruthy();
    const listed: string[] = JSON.parse(m![1].replace(/'/g, '"'));
    expect(listed).toEqual(EXPECTED_CHUNK_EXCEPTIONS);
    // and the entry has to carry its closing PR, or it is not time-boxed
    expect(guard).toContain("C4b");
  });

  it("the initials helper carries no roster data of its own", () => {
    const helper = readFileSync(join(SRC, "lib/team-initials.ts"), "utf8");
    expect(importsRosterGraph(helper)).toEqual([]);
    // Judge the CODE, not the prose: this file's comment explains the mechanism
    // by naming TEAM_ROSTER, and a raw substring check would flag the
    // explanation as the offence. (It did, the first time this test ran.)
    expect(stripComments(helper)).not.toContain("TEAM_ROSTER");
    expect(stripComments(helper)).not.toContain("rosterBySlug");
  });
});
