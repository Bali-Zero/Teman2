// apps/mouth/src/lib/team-public-listing.ts
// ─────────────────────────────────────────────────────────────────────────────
// WHO IS SHOWN ON PUBLIC PAGES — the presentation half of the roster decision.
//
// WHY THIS FILE EXISTS:
//   `src/data/team-roster.ts` is the SSOT for WHO WORKS HERE. It is an internal
//   record: nobody is deleted from it, and `rosterBySlug()` deliberately returns
//   every member (team-roster.ts:242) because internal surfaces need to resolve a
//   person by slug whether or not that person is on the marketing site.
//
//   The owner's instruction "these people do not appear on public pages" is a
//   PRESENTATION decision, so it lives here, and every PUBLIC consumer of the
//   roster routes through this module. That is the whole mechanism: no record is
//   removed, no role is rewritten, no photo is deleted.
//
//   `publicListed: false` on a roster member means the same thing and is honoured
//   here as well — this filter is a superset of it, never a replacement. Today no
//   member carries the flag, which is exactly why filtering on the flag alone
//   would exclude nobody (and why `PUBLIC_ROSTER`, which only reads the flag,
//   still publishes everyone).
//
// HOW TO USE IT:
//   - a list of roster members            → `publicRoster()`
//   - a list of editorial entries by slug → `publicEntries(ENTRIES)`
//   - a single member or slug             → `isPubliclyListed(m)` / `isPublicSlug(s)`
//   An editorial entry WITHOUT a slug (a person who is not in the roster) is kept
//   — the "Zero" entry on /team is exactly that. It is kept only if its own name
//   is not an excluded person's: a hand-written entry must not be able to
//   re-publish somebody by spelling their name instead of their slug.
// ─────────────────────────────────────────────────────────────────────────────

import {
  PUBLIC_ROSTER,
  rosterBySlug,
  type RosterMember,
} from "@/data/team-roster";

/**
 * Roster slugs the owner has excluded from PUBLIC marketing surfaces.
 * Recorded instruction, 2026-09-11 (SHWEB-20260911 / W2). The people stay in the
 * roster, in the CRM and on internal surfaces; only the public pages drop them.
 * NOTE the spelling: the roster slug is `faisha` (the email prefix is `faysha.tax`),
 * and `team-public-listing.test.ts` pins every slug here to a real roster slug so a
 * rename or a misspelling cannot turn this list into a silent no-op.
 */
export const PUBLIC_EXCLUDED_SLUGS = ["faisha", "sahira"] as const;

/**
 * One spelling for every comparison in this module. NFKC folds the fullwidth and
 * compatibility forms, so `Ｆａｉｓｈａ` and `Faisha` are the same key; trim and
 * lowercase do the rest. Every `has()` below goes through it, on BOTH sides —
 * a set built from raw values and probed with a normalised one would be a guard
 * that only works when the caller is already careful.
 */
const norm = (value: string): string =>
  value.normalize("NFKC").trim().toLowerCase();

const EXCLUDED: ReadonlySet<string> = new Set(PUBLIC_EXCLUDED_SLUGS.map(norm));

/**
 * The same instruction, keyed by the NAME the roster carries for those people
 * (plus the slug itself). Derived from the roster — not a second list to keep in
 * step — so that an editorial entry written by hand cannot publish an excluded
 * person by spelling their name.
 */
const EXCLUDED_NAMES: ReadonlySet<string> = new Set(
  PUBLIC_EXCLUDED_SLUGS.flatMap((slug) => {
    const member = rosterBySlug(slug);
    return member ? [norm(slug), norm(member.name)] : [norm(slug)];
  }),
);

/** True when this roster member may appear on a public page. */
export function isPubliclyListed(
  member: Pick<RosterMember, "slug"> & { publicListed?: boolean },
): boolean {
  return member.publicListed !== false && !EXCLUDED.has(norm(member.slug));
}

/**
 * True when this slug may appear on a public page. An unknown slug is allowed:
 * this module decides about roster people, and a page that renders someone who is
 * not in the roster supplies that person's own name and role.
 */
export function isPublicSlug(slug: string): boolean {
  if (EXCLUDED.has(norm(slug))) return false;
  const member = rosterBySlug(slug);
  return member ? member.publicListed !== false : true;
}

/** The roster members a public page may list. */
export function publicRoster(): RosterMember[] {
  return PUBLIC_ROSTER.filter(isPubliclyListed);
}

/**
 * The editorial entries a public page may render. Entries are kept in order; an
 * entry with no `slug` (e.g. the "Zero" entry, a person outside the roster) is
 * kept unless its `nameOverride` names one of the excluded people — and that name
 * check applies to entries WITH a slug too.
 */
export function publicEntries<
  T extends { slug?: string; nameOverride?: string },
>(entries: readonly T[]): T[] {
  return entries.filter((e) => {
    // The name is checked whether or not the entry also carries a slug: an entry
    // like `{ slug: "kadek", nameOverride: "Faisha" }` renders the override, so a
    // slug-first short-circuit would publish the excluded person under a slug
    // that is perfectly allowed.
    if (e.nameOverride && EXCLUDED_NAMES.has(norm(e.nameOverride)))
      return false;
    if (e.slug) return isPublicSlug(e.slug);
    return true;
  });
}
