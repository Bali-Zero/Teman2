# REPORT-RB — SAETTA-20260915 / W-C, slice R-B

D6 (2026-09-15): the two portraits excluded from public marketing surfaces
(`PUBLIC_EXCLUDED_SLUGS = ["faisha","sahira"]`) are REMOVED from `public/`,
not gated — a file under `public/` never passes through `src/proxy.ts` (its
matcher excludes any path containing a dot), so "behind the session gate"
would have needed a new authenticated route handler plus Next
`outputFileTracingIncludes` wiring, unprovable end-to-end in this window.
Removal is provable with one anonymous curl returning 404 and has no failure
mode.

All commands below were run from `apps/mouth` inside this worktree, just now.

---

## 1. Diff

### Binary files removed (git rm, not part of the text diff)

```
D  apps/mouth/public/static/team/faisha.jpg   (69,448 bytes)
D  apps/mouth/public/static/team/sahira.jpg   (66,303 bytes)
```

### New file

```
apps/mouth/src/lib/public-team-portraits.test.ts   (new, full content below §2)
```

### Unified diff — text files

```diff
diff --git a/apps/mouth/scripts/assert-roster-not-in-public-chunks.mjs b/apps/mouth/scripts/assert-roster-not-in-public-chunks.mjs
index 42b1c87b44..54e8fd99ee 100644
--- a/apps/mouth/scripts/assert-roster-not-in-public-chunks.mjs
+++ b/apps/mouth/scripts/assert-roster-not-in-public-chunks.mjs
@@ -138,25 +138,28 @@ const ALLOWED_CHUNK_PREFIX_CLOSERS = {};
 const PUBLIC_DIR = "public";

 /**
- * Portraits under `public/` whose FILENAME is an excluded person's name.
+ * EMPTY, and being empty is the point.
  *
- * These are a real, currently-accepted public exposure, listed here so that it is a
- * DECISION and not an omission: `curl https://balizero.com/static/team/sahira.jpg`
- * returns 200 today, and the URL itself is the name. No page links them any more —
- * that was the earlier work — but the bytes stay fetchable by anyone who guesses
- * the path.
+ * Until D6 (2026-09-15) this list carried `static/team/faisha.jpg` and
+ * `static/team/sahira.jpg` as a real, owner-acknowledged exposure: no page linked
+ * them any more, but `curl https://balizero.com/static/team/sahira.jpg` returned
+ * 200 — the bytes stayed fetchable by anyone who guessed the URL, because the
+ * filename IS the name.
  *
- * They are not deleted here because internal surfaces still use them, so removing
- * them or moving them behind an authenticated route handler is the owner's call,
- * not a presentation change's. It is already with the owner.
+ * D6 closed it by REMOVAL, not a gated route handler: a file under `public/`
+ * never passes through `src/proxy.ts` at all (its matcher excludes any path
+ * containing a dot), so "behind the session gate" would have needed a new
+ * authenticated route handler plus Next `outputFileTracingIncludes` wiring —
+ * machinery whose authenticated success path was not provable end-to-end in the
+ * window that made the call. Removal is provable with one anonymous curl
+ * returning 404, and it has no failure mode.
  *
- * The point of the list: a THIRD excluded person's portrait added to `public/` will
- * fail this build instead of quietly joining them.
+ * An entry here is how a leak becomes legal, so the list is pinned at empty by
+ * `src/lib/client-roster-boundary.test.ts` (EXPECTED_ACCEPTED_PUBLIC_FILES).
+ * Adding one back means editing that test in the same commit — a visible
+ * decision, never a quiet one.
  */
-const ACCEPTED_PUBLIC_FILES = [
-  "static/team/faisha.jpg",
-  "static/team/sahira.jpg",
-];
+const ACCEPTED_PUBLIC_FILES = [];

 function walk(dir, out = []) {
   if (!fs.existsSync(dir)) return out;
diff --git a/apps/mouth/src/data/team-roster.ts b/apps/mouth/src/data/team-roster.ts
index dad83d2c26..f3f7d7dd31 100644
--- a/apps/mouth/src/data/team-roster.ts
+++ b/apps/mouth/src/data/team-roster.ts
@@ -184,7 +184,10 @@ export const TEAM_ROSTER: RosterMember[] = [
     role: "Tax Care",
     dept: "tax",
     email: "faysha.tax@balizero.com",
-    photo: "/static/team/faisha.jpg",
+    // Portrait withdrawn from public/ under D6 (2026-09-15, owner ruling: default
+    // privacy for the two people excluded from public marketing surfaces — see
+    // PUBLIC_EXCLUDED_SLUGS in src/lib/team-public-listing.ts). No `photo` → this
+    // member renders the initials fallback per the `photo?` contract above.
   },

   // ── Accounting ──────────────────────────────────────────────────────────
@@ -211,7 +214,10 @@ export const TEAM_ROSTER: RosterMember[] = [
     role: "Marketing Specialist",
     dept: "support",
     email: "sahira@balizero.com",
-    photo: "/static/team/sahira.jpg",
+    // Portrait withdrawn from public/ under D6 (2026-09-15, owner ruling: default
+    // privacy for the two people excluded from public marketing surfaces — see
+    // PUBLIC_EXCLUDED_SLUGS in src/lib/team-public-listing.ts). No `photo` → this
+    // member renders the initials fallback per the `photo?` contract above.
   },
   {
     slug: "subhi",
diff --git a/apps/mouth/src/lib/client-roster-boundary.test.ts b/apps/mouth/src/lib/client-roster-boundary.test.ts
index 924958e193..e31ee92a6c 100644
--- a/apps/mouth/src/lib/client-roster-boundary.test.ts
+++ b/apps/mouth/src/lib/client-roster-boundary.test.ts
@@ -73,6 +73,24 @@ const ROSTER_GRAPH_MODULES = [
  */
 const EXPECTED_CHUNK_EXCEPTIONS: readonly string[] = [];

+/**
+ * The guard's accepted-public-files list, pinned from here — and now EMPTY.
+ *
+ * Until D6 (2026-09-15) this list carried `static/team/faisha.jpg` and
+ * `static/team/sahira.jpg`: real portrait files under `public/`, unlinked from
+ * every page but still fetchable by anyone who guessed the URL, since a file
+ * under `public/` is served from the sessionless CDN with no session and no
+ * page in between. D6 removed the files instead of gating them (a gate would
+ * need a new authenticated route handler plus Next `outputFileTracingIncludes`
+ * wiring — unprovable end-to-end in the window that made the call — while
+ * removal is provable with one anonymous curl returning 404).
+ *
+ * This test fails if the guard's list grows, shrinks to something else, or is
+ * quietly reworded: an entry that can be added without a red test here is not a
+ * declared exception, it is a hole with a comment.
+ */
+const EXPECTED_ACCEPTED_PUBLIC_FILES: readonly string[] = [];
+
 /**
  * EMPTY, and that is the assertion.
  *
@@ -330,6 +348,20 @@ describe("the roster does not cross the client boundary", () => {
     ).toContain('from "./lib/app-routes.mjs"');
   });

+  it("the guard's accepted-public-files list matches this suite's pin", () => {
+    // Same reasoning as the exception-list test above, same reason for reading
+    // source instead of importing it: the guard script exits the process on
+    // failure.
+    const guard = readFileSync(
+      join(SRC, "..", "scripts", "assert-roster-not-in-public-chunks.mjs"),
+      "utf8",
+    );
+    const m = guard.match(/const ACCEPTED_PUBLIC_FILES = (\[[^\]]*\]);/);
+    expect(m, "ACCEPTED_PUBLIC_FILES not found in the guard").toBeTruthy();
+    const listed: string[] = JSON.parse(m![1].replace(/'/g, '"'));
+    expect(listed).toEqual(EXPECTED_ACCEPTED_PUBLIC_FILES);
+  });
+
   it("the initials helper carries no roster data of its own", () => {
     const helper = readFileSync(join(SRC, "lib/team-initials.ts"), "utf8");
     expect(importsRosterGraph(helper)).toEqual([]);
diff --git a/apps/mouth/src/lib/team-public-listing.test.ts b/apps/mouth/src/lib/team-public-listing.test.ts
index 5b381d57fc..454f23192c 100644
--- a/apps/mouth/src/lib/team-public-listing.test.ts
+++ b/apps/mouth/src/lib/team-public-listing.test.ts
@@ -151,22 +151,35 @@ describe("team public listing filter", () => {
     expect(publicEntries([{ slug: "someone-new" }])).toHaveLength(1);
   });

-  it("drops an allowed slug that carries an excluded person's PHOTO or EMAIL", () => {
-    // Codex finding #3: a name is not the only way to publish somebody. These two
-    // entries carry a perfectly allowed slug, so a name-only guard keeps them —
-    // and then the consumer renders the excluded person's face, or their address.
-    const photoOfExcluded = rosterBySlug("faisha")?.photo;
+  it("drops an allowed slug that carries an excluded person's EMAIL", () => {
+    // Codex finding #3: a name is not the only way to publish somebody. This
+    // entry carries a perfectly allowed slug, so a name-only guard would keep
+    // it — and then the consumer renders the excluded person's address.
     const emailOfExcluded = rosterBySlug("sahira")?.email;
-    expect(photoOfExcluded).toBeTruthy();
     expect(emailOfExcluded).toBeTruthy();

-    expect(
-      publicEntries([{ slug: "kadek", photoOverride: photoOfExcluded }]),
-    ).toEqual([]);
     expect(publicEntries([{ slug: "kadek", email: emailOfExcluded }])).toEqual(
       [],
     );
     // the same shape pointing at somebody who IS public stays
+    expect(
+      publicEntries([{ slug: "kadek", email: rosterBySlug("adit")?.email }]),
+    ).toHaveLength(1);
+  });
+
+  it("the PHOTO marker path is dormant since D6 — the file is gone, not just unlisted", () => {
+    // HONEST LIMIT, stated rather than dressed up: before D6 (2026-09-15) this
+    // test exercised the photo half of Codex finding #3 by pointing a
+    // photoOverride at an excluded person's real photo path and proving it got
+    // filtered. D6 deleted both excluded members' `photo` field along with the
+    // files themselves (owner ruling: default privacy — see team-roster.ts),
+    // so there is no longer a truthy photo to build that fixture from, and no
+    // mutant on EXCLUDED_MARKERS' photo branch can turn this suite red today.
+    // What stays checkable: the two excluded members carry no photo at all
+    // (the escape hatch this test used to probe has no live data left to
+    // escape through), and a still-public member's photo is unaffected.
+    expect(rosterBySlug("faisha")?.photo).toBeUndefined();
+    expect(rosterBySlug("sahira")?.photo).toBeUndefined();
     expect(
       publicEntries([
         { slug: "kadek", photoOverride: rosterBySlug("adit")?.photo },
```

**Note on `team-public-listing.test.ts`** — NOT in the original task list (items 1–5 named
`team-roster.ts`, the guard script, and `client-roster-boundary.test.ts` only). Removing
`photo` from both roster entries made the pre-existing test
`"drops an allowed slug that carries an excluded person's PHOTO or EMAIL"` false on its own
premise: it asserted `rosterBySlug("faisha")?.photo` is truthy, which is no longer true by
design. This is a necessary, disclosed consequence of the mandated change (not scope creep):
left alone it would fail `npx vitest run ... team-public-listing.test.ts`, one of the
explicitly required verify commands. Split into two tests — the EMAIL-marker check (still
live, both excluded members keep their email) and an explicit "PHOTO marker is dormant"
test documenting why, with the same honest-limit register the file already uses elsewhere
in it (see the pre-existing "normalises the slug on both sides" test).

---

## 2. Test files added/changed and what each new assertion pins

- **`src/lib/client-roster-boundary.test.ts`** (changed) — added
  `EXPECTED_ACCEPTED_PUBLIC_FILES: readonly string[] = []` and a new `it` that reads
  `scripts/assert-roster-not-in-public-chunks.mjs`'s source, extracts
  `ACCEPTED_PUBLIC_FILES` via the same regex shape already used for
  `ALLOWED_CHUNK_PREFIXES`/`EXPECTED_CHUNK_EXCEPTIONS`, and asserts it equals the pin.
  Mirrors the file's existing shape exactly, as instructed. Pins: **the guard's
  accepted-public-files list must stay empty; re-adding a portrait means editing this
  test in the same commit.**

- **`src/lib/team-public-listing.test.ts`** (changed, see note in §1) — pins: **neither
  excluded member carries a `photo` field any more**, and the EMAIL-marker defense
  (Codex finding #3) still works for the field that remains.

- **`src/lib/public-team-portraits.test.ts`** (new — a SIBLING file, per the task's "same
  file or a sibling — state which"; kept separate from `client-roster-boundary.test.ts`
  because that file parses SOURCE STRINGS from the guard script while this one walks the
  REAL FILESYSTEM under `public/` — different instruments, different failure modes, worth
  keeping apart). Full content:

  ```ts
  import { describe, it, expect } from "vitest";
  import { readdirSync, statSync } from "node:fs";
  import { join, sep } from "node:path";

  const PUBLIC_DIR = join(__dirname, "..", "..", "public");
  const FORBIDDEN = /faisha|faysha|sahira/i;

  function walk(dir: string, out: string[] = []): string[] {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) walk(full, out);
      else out.push(full);
    }
    return out;
  }

  function relPublicPaths(): string[] {
    return walk(PUBLIC_DIR).map((f) =>
      f.slice(PUBLIC_DIR.length + 1).split(sep).join("/"),
    );
  }

  describe("no public/ file is named after an excluded person, of any shape", () => {
    it("finds files to scan — refuses to pass on an empty walk", () => { ... });
    it("the detector catches shapes nobody has written yet (guilt control)", () => { ... });
    it("the detector does not flag an unrelated real public file (innocence control)", () => { ... });
    it("no path under public/ matches an excluded person's name, in any shape", () => { ... });
  });
  ```

  Pins: **no path anywhere under `public/` may match `/faisha|faysha|sahira/i`, in any
  casing, any extension, any directory** — the class-closer the per-entry
  `ACCEPTED_PUBLIC_FILES` list cannot provide. Guilt control: three synthetic paths
  (`faisha_card.jpg`, `team/Sahira.JPG`, `static/news/faysha-portrait.webp`) that the
  regex MUST catch. Innocence control: the real `static/team/adit.jpg` file, which must
  NOT be flagged. Refuses an empty walk (mirrors the guard script's own rule for its
  chunk/public-file scans).

---

## 3. Real command output

### Targeted vitest

```
$ npx vitest run src/lib/client-roster-boundary.test.ts src/lib/team-public-listing.test.ts src/lib/public-team-portraits.test.ts
 Test Files  3 passed (3)
      Tests  31 passed (31)
   Duration  434ms
```

### Broad vitest (`src/lib src/__tests__`, as specified)

```
$ npx vitest run src/lib src/__tests__
 ❯ src/lib/workspace/roster-directory.test.ts (6 tests | 1 failed)
     × still answers for every key the hand-written photo map had
   AssertionError: expected [ 'sahira', 'faisha' ] to deeply equal []
 Test Files  1 failed | 148 passed (149)
      Tests  1 failed | 2085 passed (2086)
   Duration  18.17s
```

1 failure, and it is caused by this diff but sits in a file I am forbidden to touch —
detailed in §5. `"Not implemented: navigation to another Document"` jsdom console lines
are pre-existing environment noise from an unrelated test's `window.location` use, not
failures.

### tsc

```
$ npx tsc --noEmit -p tsconfig.json
EXIT_CODE=0
```

No output, clean exit. No type errors anywhere in the tree, including every file this
diff touches.

---

## 4. Mutation proof

```
$ cp /Users/nuzantara/nuzantara/apps/mouth/public/static/team/faisha.jpg public/static/team/faisha.jpg
$ npx vitest run src/lib/public-team-portraits.test.ts
 ❯ src/lib/public-team-portraits.test.ts (4 tests | 1 failed)
     × no path under public/ matches an excluded person's name, in any shape
   AssertionError: expected [ 'static/team/faisha.jpg' ] to deeply equal []
 Test Files  1 failed (1)
      Tests  1 failed | 3 passed (4)
```

RED, naming the exact file (`static/team/faisha.jpg`) — 1 failed / 4 total, the other 3
(empty-walk guard, guilt control, innocence control) unaffected.

```
$ mv public/static/team/faisha.jpg /tmp/mutation-proof-trash/faisha.jpg   # mv not rm, per operator rule
$ npx vitest run src/lib/public-team-portraits.test.ts
 Test Files  1 passed (1)
      Tests  4 passed (4)
$ git status --porcelain public/static/team/
D  apps/mouth/public/static/team/faisha.jpg
D  apps/mouth/public/static/team/sahira.jpg
```

GREEN, 4/4. `git status` afterward shows only the two intended deletions — no leftover
copy in the tree.

---

## 5. Remaining references to the two removed paths — full list, in/out-of-perimeter verdicts

`grep -rn "static/team/faisha\|static/team/sahira"`, tree-wide, excluding
`node_modules/.next/.worktrees`:

| Location                                                                                                                                      | What it is                                                                                                                                                         | 404 now?                                                                                                                                               | Verdict                                                                                                                                                                                                                                                                                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `apps/mouth/scripts/assert-roster-not-in-public-chunks.mjs` (4 hits)                                                                          | My own edited doc-comment, narrating the closed D6 history                                                                                                         | N/A — prose                                                                                                                                            | **In perimeter, correct by design.** No fix needed.                                                                                                                                                                                                                                                                                                                                                           |
| `apps/mouth/src/lib/client-roster-boundary.test.ts` (2 hits)                                                                                  | My own added doc-comment, same narration                                                                                                                           | N/A — prose                                                                                                                                            | **In perimeter, correct by design.**                                                                                                                                                                                                                                                                                                                                                                          |
| `apps/mouth/src/lib/team-public-listing.ts` (2 hits)                                                                                          | Pre-existing illustrative code comments showing the shape of a `photoOverride` leak (`{ slug: "kadek", photoOverride: "/static/team/faisha.jpg" }`)                | N/A — illustrative example of an attack shape, not a live asset claim                                                                                  | **In perimeter (file not forbidden), not touched** — outside the task's 5 named edits, and the example is still conceptually accurate (it documents the CLASS of leak the code defends against, independent of whether that literal file exists today). No fix needed.                                                                                                                                        |
| `apps/mouth/e2e/shweb-team.spec.ts` (URL-encoded form `%2Fstatic%2Fteam%2Ffaisha.jpg`, not caught by the literal grep — checked separately)   | Playwright e2e asserting NO rendered `<img>` decodes to a `/static/team/` path for an excluded name                                                                | Assertion of absence — still true, more strongly so now                                                                                                | **In perimeter, unaffected.** Not part of the required vitest/tsc commands (needs a live/built server); confirmed by reading it that it tests an invariant my change does not break.                                                                                                                                                                                                                          |
| **`apps/backend-rag/backend/db/migrations_v2/229_team_avatars_align_roster.sql`** (2 hits, lines 30/32)                                       | Historical, already-applied migration (2026-06-15) that wrote `team_members.avatar = '/static/team/faisha.jpg'` / `'/static/team/sahira.jpg'` for these two emails | **Yes, if that DB row's value is unchanged** — the CRM/portal (`portal.py` → `avatar_url`) would render a broken image to authenticated internal users | **OUT OF PERIMETER, confirmed as the task expected.** `apps/backend-rag/` is explicitly forbidden for this slice. The migration file itself is inert history (no rollback will re-run it); the live consequence, if any, is a `team_members.avatar` column value in Postgres that now points at a 404 — a DB data fix, not a code fix, and squarely another slice's / the owner's call. Flagged, not touched. |
| **`apps/mouth/src/lib/workspace/roster-directory.ts` + `.test.ts`** (0 literal `static/team/...` hits, but a DIRECT consequence via `.photo`) | Internal (workspace, authenticated) roster consumer — `teamPhotoMap()` derives `slug → photo` straight from `TEAM_ROSTER[...].photo`                               | The internal directory now shows the initials fallback for `sahira`/`faisha` instead of a photo — not a 404, a quiet UI degradation                    | **OUT OF PERIMETER, explicitly forbidden to touch, and it is RED** (see §3/§6) — the one place this diff broke a passing test outside its own files.                                                                                                                                                                                                                                                          |
| `evidence/2026-09/.../{brief,pack}.yml`, `.../reviews/*.txt` (12 hits)                                                                        | This mission's own evidence-pack artifacts from EARLIER turns, narrating the pre-D6 state as history                                                               | N/A — static record of a past measurement                                                                                                              | **Out of perimeter (evidence archive, not code); not touched.** Rewriting past evidence-pack turns to match a later decision would falsify the record of what was actually measured at the time.                                                                                                                                                                                                              |
| `docs/archive/2026-07-orphans/superpowers/plans/2026-03-27-balizero-brand-book.md`                                                            | Archived orphan planning doc, references `/static/team/sahira.png` (note: `.png`, a different, already-defunct path — this file predates the `.jpg` refresh)       | Already dead before this change                                                                                                                        | **Out of perimeter, archived doc, not touched.**                                                                                                                                                                                                                                                                                                                                                              |

---

## 6. Contradictions / collateral found on disk

**`apps/mouth/src/lib/workspace/roster-directory.test.ts`** pins
`KEYS_THE_HANDWRITTEN_MAP_HAD` to include `"sahira"` and `"faisha"`, asserting
`teamPhotoMap()` (which derives `slug → photo` from `TEAM_ROSTER[...].photo`) must answer
for every one of those 16 keys. Removing `photo` from those two roster entries — exactly
what this mandate specifies, and exactly what the mandate's own text anticipates
("internal surfaces degrade by a path the code already supports") — makes that assertion
false: `teamPhotoMap()` now has no entry for either slug, so the internal/authenticated
workspace directory silently falls back to initials for these two people too, not only the
public site. This is the one test failure in the broad suite (§3). The file is on this
slice's explicit forbidden list (`apps/mouth/src/lib/workspace/roster-directory.ts` —
"other slices own [it]"), so it is reported here rather than fixed: whoever owns that file
needs to drop `"sahira"`/`"faisha"` from `KEYS_THE_HANDWRITTEN_MAP_HAD` (or otherwise adjust
the assertion) in a follow-up, now that those two keys are a deliberate, permanent gap
rather than a regression to catch.

No other contradiction found. `photo?: string | undefined` and the "undefined → initials
fallback" contract documented at the top of `team-roster.ts` (line 41) match what I relied
on; `RosterMember.photo` is optional in the type, so dropping the field compiles clean
(confirmed by the zero-error `tsc` run in §3).
