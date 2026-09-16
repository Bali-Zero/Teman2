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
 * These `value`s are constrained by the backend: a CHECK constraint on
 * `clients.tax_consultant` gates exactly this set, and the form submits the
 * value verbatim.
 *
 * WHICH RECORD WAS WRONG, SETTLED (migration 319, 2026-09-16). This list used
 * to carry `veronika.tax@…` and `faisha.tax@…` — the spelling the old CHECK
 * constraint happened to hold — while the roster carried `tax@balizero.com`
 * and `faysha.tax@…`. The comment here said the disagreement was "a question
 * for the owner". It has been answered: `team_members` is canonical, neither
 * of the two old values matches any staff record, and migration 319 moved the
 * production rows and both CHECK lists onto the real addresses. So this list
 * now agrees with the roster — and, because it does, with the API responses
 * the form reads back.
 */
export const TAX_CONSULTANTS: readonly TaxConsultantOption[] = [
  { value: "tax@balizero.com", label: "Veronika" },
  { value: "kadek.tax@balizero.com", label: "Kadek" },
  { value: "dewaayu.tax@balizero.com", label: "Dewa Ayu" },
  { value: "angel.tax@balizero.com", label: "Angel" },
  { value: "faysha.tax@balizero.com", label: "Faisha" },
];

/**
 * The LKPM assignment dropdown is the tax team PLUS Krisna.
 *
 * Krisna is the Executive Consultant who owns four PTs in the Q1 2026 handover
 * ("Handle BY: Krisna") and has no `.tax@` sub-alias, so the backend whitelists
 * his main inbox for LKPM assignment only (110_lkpm_allowlist_krisna.sql, and
 * `TaxConsultantConstants.LKPM_ASSIGNEES`). The batch screen offered the five
 * tax addresses only, so the one person the backend added for this exact
 * screen could not be picked on it — his reports had to be assigned somewhere
 * else or left unassigned.
 */
export const LKPM_ASSIGNEES: readonly TaxConsultantOption[] = [
  ...TAX_CONSULTANTS,
  { value: "krisna@balizero.com", label: "Krisna" },
];

// The read-side alias resolution lives in `./tax-consultant-alias`, NOT here:
// this module imports the roster, and a "use client" module may not reach the
// roster graph (client-roster-boundary.test.ts). Re-exported for server-side
// callers that already import from this module.
export { normalizeTaxConsultant } from "./tax-consultant-alias";

/** A copy the client can hold: plain rows, no roster type crosses over. */
export function taxConsultants(): TaxConsultantOption[] {
  return TAX_CONSULTANTS.map((c) => ({ ...c }));
}

/** Same, for the LKPM batch screen (tax team + Krisna). */
export function lkpmAssignees(): TaxConsultantOption[] {
  return LKPM_ASSIGNEES.map((c) => ({ ...c }));
}
