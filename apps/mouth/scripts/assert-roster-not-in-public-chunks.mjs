// Assert that NO JS chunk — public route, internal route or shared — contains a
// roster member the owner excluded from public pages.
//
// This started as a public-route check with the `(workspace)` routes skipped "by
// design", on the reasoning that those pages are authenticated and the roster is
// what they exist to show. That reasoning was wrong about one thing: the PAGE is
// behind auth, the CHUNK is not. A Next static asset is served from the public CDN
// path with no session, so
// `curl https://balizero.com/_next/static/chunks/app/(workspace)/lkpm/page-*.js`
// returned 200 and an excluded name to an anonymous caller. So the skip is gone and
// the scan covers everything.
//
// WHY A SCRIPT AND NOT A UNIT TEST. The defect this guards lived only in the
// BUILT output: the rendered HTML was clean, every page test and every browser
// walk passed, and both excluded names sat in `75947-*.js` on all six public
// routes. The static tripwire (src/lib/client-roster-boundary.test.ts) catches
// the import that puts them there; this catches the ARTIFACT, which is the thing
// that actually shipped. Both, because each misses what the other sees: a
// bundler change could reintroduce the leak with no import edit at all.
//
// HOW TO RUN
//   npm run build && node scripts/assert-roster-not-in-public-chunks.mjs
//
// WIRED INTO `npm run build` (apps/mouth/package.json, scripts.build), so every
// build runs it. It was introduced unwired, because the PR that added it could not
// touch package.json; a guard nothing runs is not a guard, and that gap is now closed.

// WHAT THIS GUARD DOES NOT SEE, said here rather than only in a PR body.
//
// It scans two surfaces: the built JS chunks, and the filenames under `public/`.
// It does NOT scan the prerendered server payloads in `.next/server/app` — and
// those DO contain staff data for the workspace routes, because those pages now
// receive it as server props. Both refuter seats raised it, correctly.
//
// It is deliberate. Those payloads are reachable only through the route, and the
// workspace routes are redirected off the public domain by `src/proxy.ts`
// (`INTERNAL_ROUTES`) — measured: an anonymous request for /lkpm, /team-management
// or /clients on the public host answers 301, including with the RSC and prefetch
// headers and with `?_rsc=`. What remains is that the app domain itself has no
// SERVER-side session gate: `(workspace)/layout.tsx` is "use client" and gates with
// GateScreen after the payload has already been sent. That is a security design
// question about the whole workspace, not about one table, and it is escalated as
// its own piece of work. Extending this guard to that surface before that decision
// would mean writing an allowlist that encodes the very thing under review.
//
// So: chunks and public files, absolutely. Server payloads, on purpose, not yet.
//
// THE ASSUMPTION UNDERNEATH, AND ITS MEASURED STATE — written here because the
// paragraph above rests on it and never said so.
//
// The reasoning "those payloads are per-request, so they are not files" holds only
// while a route is DYNAMIC. It is NOT true of this app today, and the first draft of
// this comment got that wrong by describing it as a future risk.
//
// MEASURED on this build, and the number C4c published was WRONG: SEVENTEEN
// `(workspace)` routes are statically prerendered, not five. Every workspace
// top-level route is — none is dynamic. C4c said five because the probe that
// produced it filtered the manifest against a hardcoded tuple of five names instead
// of enumerating `src/app/(workspace)/<route>/page.tsx`, so five was the most it
// could ever return. The correction is recorded here rather than quietly applied.
//
// The exposure is narrower than seventeen suggests, which is worth stating in the
// same breath: of the seventeen payloads, exactly ONE carries staff-name markers —
// `/lkpm`, 4 hits. The other sixteen are the client shell.
//
// `clients/[id]` is the exception that stays dynamic — 0 prerender artifacts,
// measured — which is why the fix that moved its table server-side genuinely removed
// the data from everything this guard can see.
//
// THE BOUNDARY IS NOW A FLOOR, not just a paragraph. `.next/prerender-manifest.json`
// is the mechanical test — if a `(workspace)` route is in it, its payload is a file —
// and the check below enforces a BASELINE rather than a blanket rule: the seventeen
// already-static routes are accepted with their measurement, and a NEW one fails.
// Asserting the blanket rule would fail every build today over an exposure that is
// already escalated and owner-held, which teaches people to bypass the guard rather
// than fixing anything. A route that becomes static tomorrow is a different matter:
// nobody has accepted it, and until now it landed in silence.

import fs from "node:fs";
import path from "node:path";
import { chunkExceptionViolations } from "./lib/chunk-exception-contract.mjs";
import { unacceptedPrerenderedWorkspaceRoutes } from "./lib/prerendered-workspace-baseline.mjs";

const CHUNK_DIR = path.join(".next", "static", "chunks");
// Keep in step with PUBLIC_EXCLUDED_SLUGS / PUBLIC_EXCLUDED_NAME_ALIASES in
// src/lib/team-public-listing.ts: a person added to the exclusion there and not
// here is a person this guard will not look for, and it will pass in silence.
const FORBIDDEN = /faisha|faysha|sahira/i;

/**
 * EMPTY, and keeping it empty is the point.
 *
 * C4 landed with ONE time-boxed entry, `app/(workspace)/clients/`, because that
 * PR had to be split: another window's #6329 and #6307 rewrote
 * `clients/[id]/page.tsx` and `components/TaxTab.tsx` while this lane had
 * relocated their contents, and by contract the merged work wins. The debt was
 * declared with a name and a closing PR rather than left implicit.
 *
 * C4b is that closing PR and this is where it closes: the tax-consultant table
 * no longer sits in `TaxTab.tsx` as a module constant. It is resolved on the
 * server in `clients/[id]/page.tsx` and handed to `ClientDetailClient` as a
 * prop, so the route's static chunk carries no excluded name and needs no
 * exception. Measured on the built artifact, not assumed.
 *
 * An entry here is how a leak becomes legal, so the list is pinned at empty by
 * `src/lib/client-roster-boundary.test.ts` (EXPECTED_CHUNK_EXCEPTIONS). Adding
 * one means editing the test in the same commit — a visible decision, never a
 * quiet one.
 */
const ALLOWED_CHUNK_PREFIXES = [];

/**
 * Every prefix in ALLOWED_CHUNK_PREFIXES must appear here as a key, mapped to the PR
 * that removes it. Empty, because the list above is empty.
 *
 * This exists because "the guard mentions a closing PR somewhere" is not a check. The
 * previous rule asked exactly that — `expect(guard).toContain("C4b")` — and a refuter
 * showed it was vacuous: this file already says "closing PR" twice while narrating
 * history, so a NEW un-timeboxed entry would have satisfied it and the suite would
 * have stayed green. Measured before fixing: an entry added to both lists with no
 * prose touched passed 9/9.
 *
 * Keying the promise to the ENTRY is what makes it enforceable — the repo's own scar
 * family for this is "a guard that judges a substring instead of an entity".
 */
const ALLOWED_CHUNK_PREFIX_CLOSERS = {};

/** Where the app's public static files live — served with no session, like chunks. */
const PUBLIC_DIR = "public";

/**
 * Portraits under `public/` whose FILENAME is an excluded person's name.
 *
 * These are a real, currently-accepted public exposure, listed here so that it is a
 * DECISION and not an omission: `curl https://balizero.com/static/team/sahira.jpg`
 * returns 200 today, and the URL itself is the name. No page links them any more —
 * that was the earlier work — but the bytes stay fetchable by anyone who guesses
 * the path.
 *
 * They are not deleted here because internal surfaces still use them, so removing
 * them or moving them behind an authenticated route handler is the owner's call,
 * not a presentation change's. It is already with the owner.
 *
 * The point of the list: a THIRD excluded person's portrait added to `public/` will
 * fail this build instead of quietly joining them.
 */
const ACCEPTED_PUBLIC_FILES = [
  "static/team/faisha.jpg",
  "static/team/sahira.jpg",
];

function walk(dir, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const entry of fs.readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (fs.statSync(full).isDirectory()) walk(full, out);
    else if (/\.[cm]?js$/.test(entry)) out.push(full);
  }
  return out;
}

const all = walk(CHUNK_DIR);
if (all.length === 0) {
  console.error(
    `ROSTER_CHUNK_ASSERT: no chunks found under ${CHUNK_DIR} — run \`npm run build\` first. ` +
      `Refusing to report success on an empty scan.`,
  );
  process.exit(1);
}

// THE PRERENDER BASELINE. Derived from the filesystem, never from a list of names —
// that is exactly how C4c's "five" happened.
{
  const WS_DIR = path.join("src", "app", "(workspace)");
  const MANIFEST = path.join(".next", "prerender-manifest.json");
  // Refuse to pass a check that did not run — the same rule this guard already applies
  // to an empty chunk scan. A missing manifest used to mean "silently green".
  if (!fs.existsSync(WS_DIR)) {
    console.error(
      `ROSTER_CHUNK_ASSERT FAILED: ${WS_DIR} does not exist, so the prerender baseline ` +
        `could not be checked. Refusing to report success on a check that did not run.`,
    );
    process.exit(1);
  }
  if (!fs.existsSync(MANIFEST)) {
    console.error(
      `ROSTER_CHUNK_ASSERT FAILED: ${MANIFEST} is missing — run \`npm run build\` first. ` +
        `Refusing to report success on a prerender baseline it could not check.`,
    );
    process.exit(1);
  }
  {
    // RECURSIVE. The first version read one level and only where a directory had its
    // own page.tsx, so every nested route was invisible — and 25 of them were already
    // prerendered. A shallow walk is not a smaller version of this check, it is a
    // different check that happens to pass.
    // Next resolves a page from several extensions, not just .tsx — a route added as
    // page.jsx would otherwise never enter this list and could never be flagged.
    const PAGE_FILES = [
      "page.tsx",
      "page.ts",
      "page.jsx",
      "page.js",
      "page.mdx",
    ];
    const hasPage = (dir) =>
      PAGE_FILES.some((f) => fs.existsSync(path.join(dir, f)));
    const walk = (dir, prefix = "") => {
      const out = [];
      for (const d of fs.readdirSync(dir, { withFileTypes: true })) {
        if (!d.isDirectory()) continue;
        const route = prefix ? `${prefix}/${d.name}` : d.name;
        if (hasPage(path.join(dir, d.name))) out.push(route);
        out.push(...walk(path.join(dir, d.name), route));
      }
      return out;
    };
    // A route with a dynamic segment cannot be prerendered without
    // generateStaticParams, and its manifest key is not the literal path.
    // A page.tsx directly inside (workspace) is the "/" route under that layout.
    const workspaceRoutes = [
      ...(hasPage(WS_DIR) ? [""] : []),
      ...walk(WS_DIR),
    ].filter((r) => !r.includes("["));
    let prerenderedPaths = [];
    try {
      prerenderedPaths = Object.keys(
        JSON.parse(fs.readFileSync(MANIFEST, "utf8")).routes ?? {},
      );
    } catch (err) {
      console.error(
        `ROSTER_CHUNK_ASSERT FAILED: could not read ${MANIFEST} (${err.message}). ` +
          `Refusing to report success on a baseline it could not check.`,
      );
      process.exit(1);
    }
    const unaccepted = unacceptedPrerenderedWorkspaceRoutes({
      workspaceRoutes,
      prerenderedPaths,
    });
    if (unaccepted.length > 0) {
      console.error(
        `ROSTER_CHUNK_ASSERT FAILED: ${unaccepted.length} (workspace) route(s) are now ` +
          `statically prerendered and are NOT in the accepted baseline: ` +
          `${unaccepted.join(", ")}. A prerendered route's payload is a FILE under ` +
          `.next/server/app, served without a session, and this guard does not scan it. ` +
          `Either keep the route dynamic, or add it to ` +
          `scripts/lib/prerendered-workspace-baseline.mjs with the measurement that ` +
          `says what its payload contains.`,
      );
      process.exit(1);
    }
  }
}

const rel = (f) => path.relative(CHUNK_DIR, f).split(path.sep).join("/");
const isAllowed = (r) => ALLOWED_CHUNK_PREFIXES.some((p) => r.startsWith(p));

// THE EXCEPTION CONTRACT. The decision lives in ./lib/chunk-exception-contract.mjs
// so that a TEST can execute it — see that file's header for why it is not inline.
// This site keeps what belongs to a build script: formatting and the exit code.
{
  const violations = chunkExceptionViolations({
    prefixes: ALLOWED_CHUNK_PREFIXES,
    closers: ALLOWED_CHUNK_PREFIX_CLOSERS,
  });
  if (violations.length > 0) {
    for (const v of violations) {
      console.error(`ROSTER_CHUNK_ASSERT FAILED: ${v}`);
    }
    process.exit(1);
  }
}

const offenders = [];
for (const file of all) {
  const r = rel(file);
  if (isAllowed(r)) continue;
  const body = fs.readFileSync(file, "utf8");
  const hit = body.match(FORBIDDEN);
  if (hit) offenders.push(`${r} (matched ${JSON.stringify(hit[0])})`);
}

if (offenders.length > 0) {
  console.error(
    "ROSTER_CHUNK_ASSERT FAILED — a chunk carries an excluded roster member:",
  );
  for (const o of offenders) console.error("  " + o);
  console.error(
    "\nCause is almost always a `use client` module importing the roster graph " +
      "(directly, or through team-public-listing / a server resolver). See " +
      "src/lib/client-roster-boundary.test.ts.",
  );
  process.exit(1);
}

// ── Second surface: public static FILES, whose names are also URLs ──────────
// The chunk scan above cannot see these: they are not chunks. But they sit on the
// same sessionless CDN path, so leaving them unexamined is how "no public asset
// carries these names" became an overstatement in an earlier PR body.
const publicFiles = [];
(function walkPublic(dir) {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (fs.statSync(full).isDirectory()) walkPublic(full);
    else
      publicFiles.push(
        path.relative(PUBLIC_DIR, full).split(path.sep).join("/"),
      );
  }
})(PUBLIC_DIR);

if (publicFiles.length === 0) {
  console.error(
    `ROSTER_CHUNK_ASSERT: no files found under ${PUBLIC_DIR} — refusing to report ` +
      `success on an empty scan.`,
  );
  process.exit(1);
}

const acceptedLower = ACCEPTED_PUBLIC_FILES.map((f) => f.toLowerCase());
const unexpectedPublic = publicFiles.filter(
  // Compared lowercased on BOTH sides: on a case-sensitive filesystem a
  // `Faisha.jpg` would match FORBIDDEN and miss the accepted list, failing the
  // build for a file that is in fact the declared one.
  (f) => FORBIDDEN.test(f) && !acceptedLower.includes(f.toLowerCase()),
);
if (unexpectedPublic.length > 0) {
  console.error(
    "ROSTER_CHUNK_ASSERT FAILED — a public static file is named after an excluded " +
      "roster member and is not on the accepted list:",
  );
  for (const f of unexpectedPublic) console.error("  " + f);
  console.error(
    "\nEither remove it, put it behind an authenticated route, or add it to " +
      "ACCEPTED_PUBLIC_FILES with the reason — so the exposure is a decision.",
  );
  process.exit(1);
}

const acceptedPresent = ACCEPTED_PUBLIC_FILES.filter((f) =>
  publicFiles.includes(f),
);

const skipped = all.filter((f) => isAllowed(rel(f))).length;
console.log(
  `ROSTER_CHUNK_ASSERT OK: scanned ${all.length} chunks, ${skipped} skipped by ` +
    `the declared time-boxed exception (${ALLOWED_CHUNK_PREFIXES.join(", ") || "none"}) — ` +
    `no other chunk carries an excluded roster member. ` +
    `Public files: ${publicFiles.length} scanned, ${acceptedPresent.length} named ` +
    `after an excluded member and ACCEPTED by declaration (${acceptedPresent.join(", ") || "none"}).`,
);
