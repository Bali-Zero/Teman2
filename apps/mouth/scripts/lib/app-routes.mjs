// The App Router's directory grammar, in ONE place.
//
// WHY THIS MODULE EXISTS, and it is not tidiness.
//
// Three consumers needed to know which routes live under a route group: the chunk
// guard's prerender baseline, and the test that proves every workspace page is an
// internal route. Each one derived the grammar from memory, and each one got the same
// edges wrong — a one-level walk, and route groups treated as URL segments. The same
// two bugs were fixed in the guard and then written again, from scratch, in a new test
// about an hour later, by the same author. A review seat called that structural rather
// than careless and predicted a third consumer would repeat it.
//
// So the rules live here, with their own tests, and every consumer imports them. The
// prediction is what this module is answering: not "be more careful", but "there is
// only one copy to be careful about".
//
// WHAT THE GRAMMAR IS (App Router):
//   (group)      organises files, contributes NO URL segment
//   [param]      a dynamic segment; it is a real segment but not a literal path
//   @slot        a parallel-route slot — NOT a group, NOT a segment
//   (..)name     an intercepting-route marker — also neither
//   page.*       what makes a directory an actual route

import nodeFs from "node:fs";
import nodePath from "node:path";

/** Page filenames Next resolves. Listed, so an unknown one is a visible omission. */
// .mjs/.cjs are included deliberately, though the App Router docs enumerate only
// js/jsx/ts/tsx/mdx: over-inclusion can only name a route the prerender manifest does
// not contain, which is silent and harmless, while under-inclusion hides a route from
// every consumer. A seat asked why; this is the answer, written where it is read.
export const PAGE_FILES = [
  "page.tsx",
  "page.ts",
  "page.jsx",
  "page.js",
  "page.mjs",
  "page.cjs",
  "page.mdx",
];

/** True for a route group directory: `(marketing)`, `(workspace)`. */
export function isRouteGroup(name) {
  return (
    name.startsWith("(") && name.endsWith(")") && !/^\(\.{1,3}\)/.test(name)
  );
}

/**
 * True for the two conventions this walk deliberately does not model: parallel-route
 * slots (`@modal`) and intercepting-route markers (`(..)photos`, `(...)photos`).
 * They are refused loudly rather than guessed at — a phantom route in a coverage
 * check reads as a coverage failure and sends the next reader hunting the wrong bug.
 */
export function isUnmodelledConvention(name) {
  return name.startsWith("@") || /^\(\.{1,3}\)/.test(name);
}

/** Strip route-group segments: `(admin)/settings` is served at `settings`. */
export function urlRoute(route) {
  return route
    .split("/")
    .filter((seg) => !isRouteGroup(seg))
    .join("/");
}

/**
 * Every route under `dir` that renders a page, as the URL path (no leading slash,
 * route groups already removed).
 *
 * Recursive; descends INTO groups; follows symlinked directories, which
 * `Dirent.isDirectory()` reports as false and which would otherwise take every page
 * behind them out of the census in silence.
 *
 * @param {string} dir
 * @param {{ fs?: typeof import("node:fs"), path?: typeof import("node:path") }} [io]
 * @returns {string[]} URL paths (the root route is ""), deduplicated and sorted
 */
export function walkAppRoutes(dir, io = {}) {
  const fs = io.fs ?? nodeFs;
  const path = io.path ?? nodePath;

  const out = [];
  // A symlink pointing at an ancestor resolves cleanly every time, so ELOOP never fires
  // and the walk simply deepens until the stack goes. No such link exists in this repo;
  // the guard costs one Set and removes the failure mode from the MODULE rather than
  // from the single tree it happens to be pointed at today.
  const seen = new Set();
  // The ROOT route, written as "". A page directly inside `dir`, or inside a route group
  // directly under it, is served at the parent's own path — `(workspace)/page.tsx` is `/`.
  // The guard that used to own this walk carried that case as a special line; the first
  // extraction dropped it and a refuter caught the loss. It belongs in the walk, not in
  // one caller, or the next consumer inherits the same hole.
  const visit = (current, segments) => {
    if (
      segments.length === 0 &&
      PAGE_FILES.some((f) => fs.existsSync(path.join(current, f)))
    ) {
      out.push("");
    }
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const name = entry.name;
      const full = path.join(current, name);

      let isDir = entry.isDirectory();
      if (!isDir && entry.isSymbolicLink()) {
        try {
          isDir = fs.statSync(full).isDirectory();
        } catch {
          continue; // a broken symlink is not a route
        }
      }
      if (!isDir) continue;

      let real = full;
      try {
        real = fs.realpathSync ? fs.realpathSync(full) : full;
      } catch {
        continue;
      }
      if (seen.has(real)) continue;
      seen.add(real);

      if (isUnmodelledConvention(name)) {
        throw new Error(
          `${name} is a parallel-route slot or an intercepting-route marker, which ` +
            `walkAppRoutes does not model. Teach it the convention before adding one, ` +
            `or every consumer of this walk will report a route that does not exist.`,
        );
      }

      const next = isRouteGroup(name) ? segments : [...segments, name];
      // next.join("/") is "" for a page inside a top-level group — the root route,
      // which is a real route and not an absence.
      if (PAGE_FILES.some((f) => fs.existsSync(path.join(full, f)))) {
        out.push(next.join("/"));
      }
      visit(full, next);
    }
  };
  visit(dir, []);
  return [...new Set(out)].sort();
}
