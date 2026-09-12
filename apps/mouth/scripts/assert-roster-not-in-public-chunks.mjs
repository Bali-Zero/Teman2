// Assert that no JS chunk loaded by a PUBLIC route contains a roster member who
// is excluded from public pages.
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
// NOT YET WIRED INTO `npm run build`. Doing that edits package.json, which the
// PR introducing this file is forbidden to touch (it is on the frozen list).
// Named as a remainder in the evidence pack rather than left implicit — the
// script is useless if nothing runs it, and saying so is the honest state.

import fs from "node:fs";
import path from "node:path";

const CHUNK_DIR = path.join(".next", "static", "chunks");
// The public surfaces. (workspace)/* is deliberately absent: those are
// authenticated internal pages and the roster is what they exist to show.
const PUBLIC_ROUTE_CHUNK_PREFIXES = [
  "app/(blog)",
  "app/(marketing)",
  "app/(book)",
  "app/v2",
  "app/page",
  "app/layout",
];
const FORBIDDEN = /faisha|faysha|sahira/i;

function walk(dir, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const entry of fs.readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (fs.statSync(full).isDirectory()) walk(full, out);
    else if (entry.endsWith(".js")) out.push(full);
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

const rel = (f) => path.relative(CHUNK_DIR, f).split(path.sep).join("/");
const isInternalRoute = (r) => r.startsWith("app/(workspace)");
// A shared chunk (no `app/` prefix) is loaded by everything, so it counts as public.
const isPublic = (r) =>
  !isInternalRoute(r) &&
  (!r.startsWith("app/") ||
    PUBLIC_ROUTE_CHUNK_PREFIXES.some((p) => r.startsWith(p)));

const offenders = [];
for (const file of all) {
  const r = rel(file);
  if (!isPublic(r)) continue;
  const body = fs.readFileSync(file, "utf8");
  const hit = body.match(FORBIDDEN);
  if (hit) offenders.push(`${r} (matched ${JSON.stringify(hit[0])})`);
}

if (offenders.length > 0) {
  console.error(
    "ROSTER_CHUNK_ASSERT FAILED — a public chunk carries an excluded roster member:",
  );
  for (const o of offenders) console.error("  " + o);
  console.error(
    "\nCause is almost always a `use client` module importing the roster graph " +
      "(directly, or through team-public-listing / a server resolver). See " +
      "src/lib/client-roster-boundary.test.ts.",
  );
  process.exit(1);
}

const internal = all.filter((f) => isInternalRoute(rel(f))).length;
console.log(
  `ROSTER_CHUNK_ASSERT OK: scanned ${all.length} chunks, ` +
    `${all.length - internal} public — none carries an excluded roster member ` +
    `(${internal} internal (workspace) chunks skipped by design).`,
);
