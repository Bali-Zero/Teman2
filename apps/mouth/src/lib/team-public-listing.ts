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
 * Spellings of the same people that are NOT roster slugs, so they cannot live in
 * the list above (`team-public-listing.test.ts` pins every entry there to a real
 * roster slug, which is what stops a rename turning that list into a silent
 * no-op). "faysha" is the owner's own spelling and the prefix of the email in the
 * roster record — a hand-written editorial entry is exactly where it would show
 * up, so the NAME guard has to know it even though the SLUG guard must not.
 */
export const PUBLIC_EXCLUDED_NAME_ALIASES = ["faysha"] as const;

/**
 * One spelling for every comparison in this module. NFKC folds the fullwidth and
 * compatibility forms, so `Ｆａｉｓｈａ` and `Faisha` are the same key; trim and
 * lowercase do the rest. Every `has()` below goes through it, on BOTH sides —
 * a set built from raw values and probed with a normalised one would be a guard
 * that only works when the caller is already careful.
 */
const norm = (value: string): string =>
  value
    .normalize("NFKC")
    // Format characters (Cf: zero-width space/joiner, RTL marks, BOM) survive
    // NFKC and are invisible on the page, so "Fai<ZWSP>sha" would read as the
    // excluded person to a visitor and as a different string to a Set.
    .replace(/\p{Cf}/gu, "")
    .trim()
    .toLowerCase();

const EXCLUDED: ReadonlySet<string> = new Set(PUBLIC_EXCLUDED_SLUGS.map(norm));

/**
 * The same instruction, keyed by the NAME the roster carries for those people
 * (plus the slug itself, and the alternate spellings above). Derived from the
 * roster — not a second list to keep in step — so that an editorial entry written
 * by hand cannot publish an excluded person by spelling their name.
 */
const EXCLUDED_NAMES: ReadonlySet<string> = new Set([
  ...PUBLIC_EXCLUDED_SLUGS.flatMap((slug) => {
    const member = rosterBySlug(slug);
    return member ? [norm(slug), norm(member.name)] : [norm(slug)];
  }),
  ...PUBLIC_EXCLUDED_NAME_ALIASES.map(norm),
]);

/**
 * Every value that IDENTIFIES an excluded person — slug, name, alias, portrait
 * path and email — all derived from the roster record, never hand-listed.
 *
 * A name is not the only way to publish somebody. An editorial entry carrying a
 * PERFECTLY ALLOWED slug can still point at an excluded person through another
 * field: `{ slug: "kadek", photoOverride: "/static/team/faisha.jpg" }` publishes
 * the face, and an email-shaped field publishes the address. So the filter judges
 * every string an entry carries, not only the fields it knows by name.
 */
const EXCLUDED_MARKERS: ReadonlySet<string> = new Set([
  ...EXCLUDED_NAMES,
  ...PUBLIC_EXCLUDED_SLUGS.flatMap((slug) => {
    const member = rosterBySlug(slug);
    if (!member) return [];
    return [member.photo, member.email]
      .filter((value): value is string => Boolean(value))
      .map(norm);
  }),
]);

/** True when any string this entry carries identifies an excluded person. */
function carriesExcludedMarker(entry: object): boolean {
  return Object.values(entry).some(
    (value) => typeof value === "string" && EXCLUDED_MARKERS.has(norm(value)),
  );
}

/** True when this roster member may appear on a public page. */
export function isPubliclyListed(
  member: Pick<RosterMember, "slug"> & { publicListed?: boolean },
): boolean {
  return member.publicListed !== false && !EXCLUDED.has(norm(member.slug));
}

/**
 * True when this slug may appear on a public page. An unknown slug is allowed —
 * this module decides about roster people, and a page that renders someone from
 * outside the roster supplies that person's own name and role.
 *
 * But an unknown slug is NOT anonymous. Two consumers resolve a name as
 * `rosterBySlug(slug)?.name ?? slug` (`v2/company/about/page.tsx`,
 * `v2/_components/SocialProof.tsx`), so an entry spelled `{ slug: "faysha" }`
 * would miss the roster, fall back to printing the SLUG, and publish the excluded
 * person as visible text with every test green. So the slug is checked against
 * the excluded NAMES and aliases too, not only against the exact slug list.
 */
export function isPublicSlug(slug: string): boolean {
  const key = norm(slug);
  if (EXCLUDED.has(key) || EXCLUDED_NAMES.has(key)) return false;
  // The lookup gets the NORMALISED key too. Normalising only for the excluded set
  // while looking the roster up with the raw string is how `publicListed: false`
  // stayed reachable: " HIDDEN " or a fullwidth spelling misses the roster,
  // resolves to undefined, and the `true` branch publishes the person anyway.
  const member = rosterBySlug(key) ?? rosterBySlug(slug);
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
    // Checked BEFORE the slug, and whatever the slug says: an entry like
    // `{ slug: "kadek", nameOverride: "Faisha" }` or
    // `{ slug: "kadek", photoOverride: "/static/team/faisha.jpg" }` carries a
    // perfectly allowed slug, so a slug-first short-circuit would publish the
    // excluded person's name or face under a clean one.
    if (carriesExcludedMarker(e)) return false;
    if (e.slug) return isPublicSlug(e.slug);
    return true;
  });
}
