// apps/mouth/src/components/book/book-team.ts
// ─────────────────────────────────────────────────────────────────────────────
// SERVER-ONLY: the book's team grid, derived from the roster SSOT.
//
// WHY IT IS NOT IN `book-data.ts`. This derivation used to live there, and
// `book-data` is imported by seven `"use client"` components — BookPage,
// BookShell, BookNav, TeamGrid, TeamModal, StatsCounter, ServicePricingCard —
// for CHAPTERS, CONTACTS, TRANSLATIONS and the shared types. Each of them wanted
// something else entirely, but the module scope came along with the import, and
// with it `publicRoster()` → the whole roster. Measured on the built output:
// chunk `94651-*.js`, loaded by /book and /book/team, carried the names of the
// two people the owner excluded from public pages.
//
// So the rule: `book-data.ts` holds no roster, and the members reach the client
// components as PROPS from the two server routes. A client module importing this
// file would put them straight back.
//
// To change a member, a photo or a role → edit the roster, not this file.
// ─────────────────────────────────────────────────────────────────────────────

import { publicRoster } from "@/lib/team-public-listing";
import type { TeamMember } from "./book-data";

/**
 * The people the book may publish. `publicRoster()` and not `PUBLIC_ROSTER`: the
 * book is a PUBLIC surface, and `PUBLIC_ROSTER` reads only the roster's
 * `publicListed` flag, which no member carries — so it published the two the
 * owner excluded. The roster itself is unchanged.
 */
export function bookTeamMembers(): TeamMember[] {
  return publicRoster().map((m) => ({
    name: m.name,
    role: m.role,
    department: m.dept,
    photo: m.photo,
  }));
}
