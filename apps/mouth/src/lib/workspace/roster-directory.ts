// apps/mouth/src/lib/workspace/roster-directory.ts
// ─────────────────────────────────────────────────────────────────────────────
// SERVER-ONLY directory data for the internal (workspace) pages.
//
// WHY THIS FILE EXISTS. Three workspace pages are `"use client"` and each held a
// hardcoded table of staff — a photo map keyed by email prefix, and a tax-consultant
// dropdown of email + display name. Those tables named people the owner had excluded
// from public pages, and a `"use client"` module's constants are shipped to the
// browser, so the names sat in three route chunks. Measured on the built output:
// `app/(workspace)/clients/[id]/page-*.js`, `.../lkpm/page-*.js` and
// `.../team-management/page-*.js`.
//
// The pages themselves are behind auth. The CHUNKS are not: a Next static asset is
// served from the public CDN path with no session, so
// `curl https://balizero.com/_next/static/chunks/app/(workspace)/lkpm/page-*.js`
// returned 200 and both names to an anonymous caller. "Internal page" does not cover
// a public asset — that distinction is the whole reason for this file.
//
// So the tables live here, on the server, and reach the pages as props.
// ─────────────────────────────────────────────────────────────────────────────

import { TEAM_ROSTER } from "@/data/team-roster";

/** email-prefix → portrait path, for the workspace people directory. */
export type TeamPhotoMap = Record<string, string>;

/**
 * Aliases the roster does not carry: these are email prefixes in use that are not
 * roster slugs, mapped to the portrait of the person they belong to. Kept explicit
 * because they cannot be derived — and small enough to read.
 */
const EMAIL_PREFIX_ALIASES: Record<string, string> = {
  "ari.firda": "ari",
  "dewa.ayu": "dewaayu",
};

/**
 * DERIVED from the roster, so a photo changes in one place.
 *
 * The map this replaces listed 16 entries by hand: 14 matched the roster exactly,
 * 0 disagreed, and 2 were the email aliases above. Deriving also picks up four
 * people who have a portrait in the roster but were missing from the hand-written
 * map (zainal, heru, ruslana, vino) — they now render their photo on the internal
 * directory instead of a blank. That is a deliberate consequence of having one
 * source of truth, not an accident, and it is declared in the PR body.
 */
export function teamPhotoMap(): TeamPhotoMap {
  const out: TeamPhotoMap = {};
  for (const m of TEAM_ROSTER) {
    if (m.photo) out[m.slug] = m.photo;
  }
  for (const [alias, slug] of Object.entries(EMAIL_PREFIX_ALIASES)) {
    const photo = out[slug];
    if (photo) out[alias] = photo;
  }
  return out;
}

export interface TaxConsultantOption {
  value: string;
  label: string;
}

/**
 * The tax-consultant dropdown. NOT derived from the roster, deliberately.
 *
 * These `value`s are constrained by the backend: migration 093 carries a CHECK
 * constraint over exactly this set of addresses, and the form submits the value
 * verbatim. The roster's own emails DISAGREE with two of them — the roster has
 * `faysha.tax@…` (with a Y) where the constraint has `faisha.tax@…`, and
 * `tax@balizero.com` where the constraint has `veronika.tax@…`. Deriving the list
 * would therefore have silently changed what this form writes and broken the CHECK,
 * so the values are preserved here byte-for-byte and only MOVED off the client.
 *
 * The disagreement itself is real and is reported as a finding rather than papered
 * over: one of the two records is wrong, and which one is a question for the owner,
 * not for a presentation change.
 */
export const TAX_CONSULTANTS: readonly TaxConsultantOption[] = [
  { value: "veronika.tax@balizero.com", label: "Veronika" },
  { value: "kadek.tax@balizero.com", label: "Kadek" },
  { value: "dewaayu.tax@balizero.com", label: "Dewa Ayu" },
  { value: "angel.tax@balizero.com", label: "Angel" },
  { value: "faisha.tax@balizero.com", label: "Faisha" },
];

/** A copy the client can hold: plain rows, no roster type crosses over. */
export function taxConsultants(): TaxConsultantOption[] {
  return TAX_CONSULTANTS.map((c) => ({ ...c }));
}
