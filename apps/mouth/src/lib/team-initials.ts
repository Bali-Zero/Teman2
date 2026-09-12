// apps/mouth/src/lib/team-initials.ts
// ─────────────────────────────────────────────────────────────────────────────
// `initialsOf` lives HERE and not next to the roster, and that is the whole
// point of the file.
//
// It is four lines of string handling with no data behind it, but it used to sit
// in `src/data/team-roster.ts` beside `TEAM_ROSTER` — 170 lines of real staff
// records. A `"use client"` component that wanted only the initials helper
// imported that module, and the bundler followed the import, not the intent: the
// entire roster landed in a client chunk that every public route loads. Measured
// on the built output before this change, chunk `75947-*.js` carried the names of
// the two people the owner had excluded from public pages, on all six public
// routes.
//
// So: anything a CLIENT component may need from the roster area belongs in a
// module that holds no roster. Keep it that way — importing a record type or a
// lookup here would undo the fix silently, and the only symptom would be a name
// in a JS chunk nobody reads.
// ─────────────────────────────────────────────────────────────────────────────

/** "Asya Nadia" → "AN". First letters of the first two words, uppercased. */
export function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0] ?? "")
    .slice(0, 2)
    .join("")
    .toUpperCase();
}
