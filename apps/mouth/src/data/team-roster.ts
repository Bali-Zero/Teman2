// apps/mouth/src/data/team-roster.ts
// ─────────────────────────────────────────────────────────────────────────────
// SINGLE SOURCE OF TRUTH for the Bali Zero team roster (photos, roles, depts).
//
// WHY THIS FILE EXISTS:
//   Team photos + roles used to be hardcoded in FOUR independent frontend lists
//   (book-data.ts, (blog)/team/page.tsx, v2/company/about, v2/_components/SocialProof)
//   PLUS the Postgres team_members.avatar column — all diverging (different members,
//   different roles, Heru/Zainal photos swapped in 2 files, 11 members on batik
//   placeholders). Updating "all the team photos" meant editing 5 places by hand.
//
//   This is now the ONE place. Every frontend list derives from TEAM_ROSTER. The DB
//   team_members.avatar column is aligned to the same /static/team/<slug>.<ext> paths
//   (see migration / scripts/sync_team_avatars.sql) so site + CRM portal stay coherent.
//
// HOW TO UPDATE A PHOTO:
//   1. Drop the file in apps/mouth/public/static/team/<slug>.<ext> (compress to ~<100KB,
//      ≤800px long edge — see scripts/process_team_photos.sh).
//   2. Set `photo` below. Done — all public surfaces pick it up.
//   3. For the CRM portal avatar, also run the avatar-sync (DB) step.
//
// CONVENTIONS:
//   - `slug`     : stable key = email prefix (used for photo filename + DB join).
//   - `photo`    : "/static/team/<slug>.<ext>" or undefined → UI falls back to initials.
//   - `email`    : canonical @balizero.com address (matches team_members.email; some
//                  prefixes differ from slug, e.g. ari→ari.firda, veronika→tax — see `email`).
//   - `dept`     : coarse public grouping. `liveDept` mirrors the DB department when it
//                  differs (kept for reference; public pages use `dept`).
//   - `publicListed` : false = real teammate but NOT shown on public marketing pages.
// ─────────────────────────────────────────────────────────────────────────────

export type TeamDept =
  | "leadership"
  | "setup"
  | "tax"
  | "accounting"
  | "support";

export interface RosterMember {
  slug: string;
  name: string;
  role: string; // public-facing role label
  dept: TeamDept; // public grouping
  email: string;
  photo?: string; // /static/team/<slug>.<ext>; undefined → initials fallback
  publicListed?: boolean; // default true; false hides from public marketing pages
}

// Helper: initials from a display name (max 2).
export function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0] ?? "")
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

// ── THE ROSTER ───────────────────────────────────────────────────────────────
// Verified 2026-06-15 against team_members DB + founder confirmation.
// Photos delivered by Antonello 2026-06-15; batik placeholders removed where a real
// photo now exists. Members still without a real photo render the initials fallback.
export const TEAM_ROSTER: RosterMember[] = [
  // ── Leadership ──────────────────────────────────────────────────────────
  {
    slug: "zainal",
    name: "Zainal Abidin",
    role: "Chief Executive Officer · Founder",
    dept: "leadership",
    email: "zainal@balizero.com",
    photo: "/static/team/zainal-ceo.jpg",
  },
  {
    slug: "heru",
    name: "Pak Heru",
    role: "Komisaris · Founder",
    dept: "leadership",
    email: "heru@balizero.com",
    photo: "/static/team/heru-komisaris.jpg",
  },
  {
    slug: "ruslana",
    name: "Ruslana",
    role: "Board Member",
    dept: "leadership",
    email: "ruslana@balizero.com",
    photo: "/static/team/ruslana.jpg",
  },

  // ── Setup ───────────────────────────────────────────────────────────────
  {
    slug: "adit",
    name: "Adit",
    role: "Supervisor · Lead Setup",
    dept: "setup",
    email: "adit@balizero.com",
    photo: "/static/team/adit.jpg",
  },
  {
    slug: "ari",
    name: "Ari",
    role: "Team Leader",
    dept: "setup",
    email: "ari.firda@balizero.com",
    photo: "/static/team/ari.jpg",
  },
  {
    slug: "krisna",
    name: "Krisna",
    role: "Executive Consultant",
    dept: "setup",
    email: "krisna@balizero.com",
    photo: "/static/team/krisna.jpg",
  },
  {
    slug: "dea",
    name: "Dea",
    role: "Executive Consultant",
    dept: "setup",
    email: "dea@balizero.com",
    photo: "/static/team/dea.jpg",
  },
  {
    slug: "surya",
    name: "Surya",
    role: "Team Leader",
    dept: "setup",
    email: "surya@balizero.com",
    photo: "/static/team/surya.jpg",
  },
  {
    slug: "candra",
    name: "Candra",
    role: "Consultant",
    dept: "setup",
    email: "candra@balizero.com",
    photo: "/static/team/candra.jpg",
  },
  {
    slug: "damar",
    name: "Damar",
    role: "Junior Consultant",
    dept: "setup",
    email: "damar@balizero.com",
    photo: "/static/team/damar.jpg",
  },
  {
    slug: "vino",
    name: "Vino",
    role: "Junior Consultant",
    dept: "setup",
    email: "vino@balizero.com",
    photo: "/static/team/vino.jpg",
  },

  // ── Tax ─────────────────────────────────────────────────────────────────
  {
    slug: "veronika",
    name: "Veronika",
    role: "Tax Manager",
    dept: "tax",
    email: "tax@balizero.com",
    photo: "/static/team/veronika.jpg",
  },
  {
    slug: "angel",
    name: "Angel",
    role: "Tax Lead",
    dept: "tax",
    email: "angel.tax@balizero.com",
    photo: "/static/team/angel.jpg",
  },
  {
    slug: "kadek",
    name: "Kadek",
    role: "Tax Lead",
    dept: "tax",
    email: "kadek.tax@balizero.com",
  },
  {
    slug: "dewaayu",
    name: "Dewa Ayu",
    role: "Tax Lead",
    dept: "tax",
    email: "dewaayu.tax@balizero.com",
    photo: "/static/team/dewaayu.jpg",
  },
  {
    slug: "faisha",
    name: "Faisha",
    role: "Tax Care",
    dept: "tax",
    email: "faysha.tax@balizero.com",
    photo: "/static/team/faisha.jpg",
  },

  // ── Accounting ──────────────────────────────────────────────────────────
  {
    slug: "asya",
    name: "Asya Nadia",
    role: "Accounting",
    dept: "accounting",
    email: "asya@balizero.com",
    photo: "/static/team/asya.jpg",
  },

  // ── Support ─────────────────────────────────────────────────────────────
  {
    slug: "rina",
    name: "Rina",
    role: "Reception",
    dept: "support",
    email: "rina@balizero.com",
  },
  {
    slug: "sahira",
    name: "Sahira",
    role: "Marketing Specialist",
    dept: "support",
    email: "sahira@balizero.com",
    photo: "/static/team/sahira.jpg",
  },
  {
    slug: "subhi",
    name: "Subhi",
    role: "AI",
    dept: "support",
    email: "subhi@balizero.com",
    photo: "/static/team/subhi.jpg",
  },
];

// ── Derived helpers (consumed by the page components) ─────────────────────────
export const PUBLIC_ROSTER: RosterMember[] = TEAM_ROSTER.filter(
  (m) => m.publicListed !== false,
);

export function rosterByDept(dept: TeamDept): RosterMember[] {
  return PUBLIC_ROSTER.filter((m) => m.dept === dept);
}

export function rosterBySlug(slug: string): RosterMember | undefined {
  return TEAM_ROSTER.find((m) => m.slug === slug);
}

/** Photo path for an email (matches the DB team_members.email join). */
export function photoForEmail(email: string): string | undefined {
  const prefix = email.split("@")[0].toLowerCase();
  const m =
    TEAM_ROSTER.find((r) => r.email.toLowerCase() === email.toLowerCase()) ??
    TEAM_ROSTER.find((r) => r.slug === prefix);
  return m?.photo;
}
