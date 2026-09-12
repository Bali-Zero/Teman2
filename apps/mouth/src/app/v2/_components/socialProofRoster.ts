// apps/mouth/src/app/v2/_components/socialProofRoster.ts
// ─────────────────────────────────────────────────────────────────────────────
// SERVER-ONLY resolution of the people SocialProof shows.
//
// WHY THIS FILE EXISTS. `SocialProof.tsx` must stay `"use client"` — it passes an
// `onError` fallback to `next/image`, which a server component cannot do. But
// everything a client module imports is shipped to the browser, so while it
// resolved its own people it dragged `team-roster.ts` — every staff record,
// including the two the owner excluded from public pages — into a JS chunk that
// every public route loads. Measured on the built output before this change:
// chunk `75947-*.js`, all six public routes, both names present. The rendered
// HTML was already clean; only the bundle was not.
//
// So the roster is read HERE, on the server, and the component receives plain
// rows as props. The editorial half — who is featured, in what order, with which
// caption and accent — stays here too, because it is the same decision as the
// resolution and splitting them would put the slugs back in the client module.
//
// The exclusion still runs through `publicEntries()`: adding a slug below is
// never enough to publish somebody.
// ─────────────────────────────────────────────────────────────────────────────

import { rosterBySlug } from "@/data/team-roster";
import { initialsOf } from "@/lib/team-initials";
import { publicEntries } from "@/lib/team-public-listing";

/** One person as the client component needs them — no roster type crosses over. */
export interface SocialProofMember {
  name: string;
  role: string;
  department: string;
  photo?: string;
  initials: string;
  accent: string;
}

interface SPEntry {
  slug: string;
  department: string;
  accent: string;
  roleOverride?: string;
}

function resolveSP(e: SPEntry): SocialProofMember {
  const r = rosterBySlug(e.slug);
  const name = r?.name ?? e.slug;
  return {
    name,
    role: e.roleOverride ?? r?.role ?? "",
    department: e.department,
    photo: r?.photo,
    initials: initialsOf(name),
    accent: e.accent,
  };
}

// Founders — shown first and larger. The two men who started Bali Zero
// and still run it. Friends for 30 years, partners in the business.
const FOUNDERS_SPEC: SPEntry[] = [
  {
    slug: "zainal",
    roleOverride: "CEO",
    department: "Founder · Since the beginning",
    accent: "#ff2d4c",
  },
  {
    slug: "heru",
    roleOverride: "Komisaris",
    department: "Founder · Partner for 30 years",
    accent: "#a78bfa",
  },
];

const TEAM_SPEC: SPEntry[] = [
  {
    slug: "ruslana",
    roleOverride: "Special Advisory",
    department: "Leadership",
    accent: "#a78bfa",
  },
  {
    slug: "veronika",
    roleOverride: "Manager",
    department: "Leadership",
    accent: "#06b6d4",
  },
  {
    slug: "adit",
    roleOverride: "Supervisor Lead",
    department: "Setup",
    accent: "#f59e0b",
  },
  {
    slug: "angel",
    roleOverride: "Supervisor",
    department: "Tax",
    accent: "#22c55e",
  },
];

// Resolved ONCE, at module load, not per render. The inputs are static — the
// roster, the specs and the exclusion are all compile-time constants — so
// rebuilding the arrays on every request only produced fresh object identities
// for no new information. (Identity does not survive the RSC boundary anyway,
// since the rows are serialised into the flight payload; this is about not
// redoing constant work, and about there being one answer rather than one per
// call.)
const RESOLVED: { founders: SocialProofMember[]; team: SocialProofMember[] } = {
  founders: publicEntries(FOUNDERS_SPEC).map(resolveSP),
  team: publicEntries(TEAM_SPEC).map(resolveSP),
};

/** The rows `<SocialProof>` renders. Call from a SERVER component only. */
export function socialProofRoster(): {
  founders: SocialProofMember[];
  team: SocialProofMember[];
} {
  return RESOLVED;
}
