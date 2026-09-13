import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { Phone, ArrowRight, ArrowUpRight } from "lucide-react";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { GoogleReviewsBlock } from "../_components/GoogleReviewsBlock";
import { RUMAH_VARS, RUMAH_CLASS } from "@/lib/theme/rumahVars";
import { rosterBySlug } from "@/data/team-roster";
import { initialsOf } from "@/lib/team-initials";
import { publicEntries } from "@/lib/team-public-listing";
import { GOOGLE_RATING, reviewsLabel } from "@/lib/trust-figures";
import styles from "./team.module.css";

export const metadata: Metadata = {
  title: "Team",
  description:
    "The Bali Zero team — licensed founders, consultants, tax specialists, notaries and marketing. Real people handling real cases in Bali since 2006.",
};

// ─── Editorial layout for this page ─────────────────────────────────────────
// NAME / ROLE / PHOTO are pulled from the roster SSOT (apps/mouth/src/data/team-roster.ts)
// by `slug`. This page keeps only its EDITORIAL choices: which section a person appears
// in and the per-person gradient. To change a photo/role → edit the roster, not here.
// `nameOverride`/`roleOverride` exist for page-specific labels (e.g. Zero "SOTA Marketing")
// and for people not in the public roster.
//
// WHO IS SHOWN is decided by `publicEntries()` (src/lib/team-public-listing.ts): the roster
// keeps every record, this page publishes only the people the owner lists publicly. The
// filter runs over the editorial entries of EVERY section — adding a person to a section
// below is never enough to publish them.

interface TeamMember {
  name: string;
  initials: string;
  role: string;
  gradient: string;
  photo?: string;
  project?: { label: string; href: string };
}

interface EditorialEntry {
  slug?: string; // → roster SSOT for name/role/photo
  gradient: string;
  nameOverride?: string; // page-specific display name (or for non-roster people)
  roleOverride?: string; // page-specific role label
  photoOverride?: string;
  project?: { label: string; href: string }; // the tool this person owns
}

// Merge an editorial entry with the roster SSOT. Roster wins for name/role/photo unless
// an explicit *Override is given. Members not in the roster MUST supply name+role here.
function resolve(e: EditorialEntry): TeamMember {
  const r = e.slug ? rosterBySlug(e.slug) : undefined;
  const name = e.nameOverride ?? r?.name ?? "";
  return {
    name,
    initials: initialsOf(name),
    role: e.roleOverride ?? r?.role ?? "",
    gradient: e.gradient,
    photo: e.photoOverride ?? r?.photo,
    project: e.project,
  };
}

/** Public composition: the owner's exclusions first, then the roster merge. */
function compose(entries: EditorialEntry[]): TeamMember[] {
  return publicEntries(entries).map(resolve);
}

// Each section keeps its EDITORIAL composition + gradients; name/role/photo come from
// the roster SSOT via resolve(). Role overrides preserve this page's curated labels.
const LEADERSHIP: TeamMember[] = compose([
  {
    slug: "heru",
    roleOverride: "Komisaris · Founder (30 years)",
    gradient: "linear-gradient(135deg, #a78bfa 0%, #6d28d9 100%)",
  },
  {
    slug: "zainal",
    gradient: "linear-gradient(135deg, #ff2d4c 0%, #c8102e 100%)",
  },
  {
    slug: "ruslana",
    roleOverride: "Special Advisory",
    gradient: "linear-gradient(135deg, #e85c41 0%, #d14832 100%)",
  },
  {
    slug: "veronika",
    roleOverride: "Manager",
    gradient: "linear-gradient(135deg, #2251ff 0%, #1a41cc 100%)",
  },
]);

const SETUP_TEAM: TeamMember[] = compose([
  {
    slug: "adit",
    gradient: "linear-gradient(135deg, #06b6d4 0%, #2563eb 100%)",
  },
  {
    slug: "ari",
    roleOverride: "Supervisor",
    gradient: "linear-gradient(135deg, #f43f5e 0%, #db2777 100%)",
    // The tool Ari is responsible for, on its real page.
    project: { label: "Second Home Studio", href: "/visa/second-home/studio" },
  },
  {
    slug: "krisna",
    roleOverride: "Specialist Consultant",
    gradient: "linear-gradient(135deg, #f97316 0%, #d97706 100%)",
  },
  {
    slug: "dea",
    gradient: "linear-gradient(135deg, #6366f1 0%, #2563eb 100%)",
  },
  {
    slug: "candra",
    gradient: "linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%)",
  },
  {
    slug: "vino",
    gradient: "linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)",
  },
  {
    slug: "sahira",
    roleOverride: "Executive Consultant",
    gradient: "linear-gradient(135deg, #a855f7 0%, #8b5cf6 100%)",
  },
]);

const TAX_TEAM: TeamMember[] = compose([
  {
    slug: "angel",
    roleOverride: "Tax Supervisor",
    gradient: "linear-gradient(135deg, #f43f5e 0%, #dc2626 100%)",
  },
  {
    slug: "kadek",
    roleOverride: "Tax Consultant",
    gradient: "linear-gradient(135deg, #10b981 0%, #16a34a 100%)",
  },
  {
    slug: "dewaayu",
    roleOverride: "Tax Consultant",
    gradient: "linear-gradient(135deg, #8b5cf6 0%, #4f46e5 100%)",
  },
  {
    slug: "faisha",
    gradient: "linear-gradient(135deg, #f59e0b 0%, #ca8a04 100%)",
  },
]);

const ACCOUNTING_TEAM: TeamMember[] = compose([
  {
    slug: "asya",
    roleOverride: "Accountant",
    gradient: "linear-gradient(135deg, #10b981 0%, #0d9488 100%)",
  },
  {
    slug: "rina",
    gradient: "linear-gradient(135deg, #ec4899 0%, #db2777 100%)",
  },
]);

// Marketing is an editorial grouping unique to this page (Zero is not in the public roster;
// Surya/Subhi live under setup/support in the SSOT but are presented here as marketing).
const MARKETING_TEAM: TeamMember[] = compose([
  {
    nameOverride: "Zero",
    roleOverride: "SOTA Marketing",
    photoOverride: "/static/team/zero.jpg",
    gradient: "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
  },
  {
    slug: "surya",
    roleOverride: "Marketing Specialist",
    gradient: "linear-gradient(135deg, #f59e0b 0%, #ea580c 100%)",
    // The tool Surya is responsible for, on its real page.
    project: { label: "E-VOA", href: "/visa/voa" },
  },
  {
    slug: "damar",
    roleOverride: "Marketing Junior",
    gradient: "linear-gradient(135deg, #14b8a6 0%, #10b981 100%)",
  },
  {
    slug: "subhi",
    gradient: "linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)",
  },
]);

// The responsibility groups of the directory, in reading order. Titles and
// descriptions are this page's existing section copy.
const GROUPS = [
  {
    id: "setup",
    eyebrow: "Setup · Visa & Company",
    title: "Your Indonesia operation, end-to-end",
    description:
      "Visa intake, PT PMA incorporation, KBLI due diligence, OSS filings.",
    people: SETUP_TEAM,
  },
  {
    id: "tax",
    eyebrow: "Tax",
    title: "Licensed konsultan pajak",
    description: "Corporate and personal tax compliance under CoreTax 2026.",
    people: TAX_TEAM,
  },
  {
    id: "accounting",
    eyebrow: "Accounting & Reception",
    title: "The backbone of every month-end",
    description: null,
    people: ACCOUNTING_TEAM,
  },
  {
    id: "marketing",
    eyebrow: "Marketing",
    title: "The intelligence arm",
    description:
      "Editorial, content, the Zantara AI layer that keeps the site alive.",
    people: MARKETING_TEAM,
  },
] as const;

// ─── UI helpers ────────────────────────────────────────────────────────────

function Portrait({ member, sizes }: { member: TeamMember; sizes: string }) {
  return (
    <div className={styles.portrait} style={{ background: member.gradient }}>
      {member.photo ? (
        <Image
          src={member.photo}
          alt={`${member.name} — ${member.role}`}
          fill
          sizes={sizes}
          style={{ objectFit: "cover", objectPosition: "center 30%" }}
        />
      ) : (
        <span className={styles.portraitInitials} aria-hidden="true">
          {member.initials}
        </span>
      )}
    </div>
  );
}

function PersonCard({
  member,
  variant,
}: {
  member: TeamMember;
  variant: "leader" | "person";
}) {
  const isLeader = variant === "leader";
  return (
    <article className={isLeader ? styles.leader : styles.person}>
      <Portrait
        member={member}
        sizes={
          isLeader
            ? "(max-width: 700px) 45vw, (max-width: 1000px) 30vw, 400px"
            : "(max-width: 700px) 45vw, (max-width: 1000px) 30vw, 280px"
        }
      />
      <h3>{member.name}</h3>
      <p>{member.role}</p>
      {member.project ? (
        <Link className={styles.projectLink} href={member.project.href}>
          {member.project.label}
          <ArrowUpRight size={13} strokeWidth={2} aria-hidden="true" />
        </Link>
      ) : null}
    </article>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────

export default function TeamPage() {
  return (
    // MYTHOS Stage-B Batch 1: Rumah Putih light, scoped per-page (NEVER on
    // the shared (blog)/layout.tsx). NavShell + Footer stay navy anchors.
    <div
      className={`min-h-screen ${RUMAH_CLASS}`}
      style={{
        ...RUMAH_VARS,
        background: "var(--surface-base)",
        color: "var(--text-primary)",
      }}
    >
      <div className={styles.page}>
        {/* Page intro */}
        <div className={styles.pageIntro}>
          <span className={styles.eyebrow}>
            The Team · 18+ specialists · Kerobokan, Bali
          </span>
          <h1>
            Real people.
            <br />
            <span>Real licenses. Real files.</span>
          </h1>
          <p className={styles.standfirst}>
            Started in Kerobokan in 2006 — two friends, one office, a lot of
            immigration paperwork. Today the team handles 47 KITAS and 9 PT PMAs
            every month. AI drafts; licensed Indonesians sign.
          </p>
          <div className={styles.introActions}>
            <Link
              href={buildWhatsAppLink("home")}
              target="_blank"
              className={styles.ctaPrimary}
            >
              <Phone size={14} strokeWidth={2.2} aria-hidden="true" />
              Talk to the team
            </Link>
            <Link href="/services" className={styles.ctaSecondary}>
              See services
              <ArrowRight size={14} strokeWidth={2.2} aria-hidden="true" />
            </Link>
          </div>

          {/* Aggregate trust — Rumah Putih: white card + hairline border. */}
          <div className={styles.trustPill}>
            <span>
              <span className={styles.stars}>★★★★★</span> {GOOGLE_RATING}{" "}
              <span className={styles.trustMuted}>{`· ${reviewsLabel()}`}</span>
            </span>
            <span className={styles.trustDivider} />
            <span>5,000+ cases</span>
            <span className={styles.trustDivider} />
            <span>Licensed since 2006</span>
          </div>

          <nav aria-label="Team sections" className={styles.groupNav}>
            <a href="#leadership">Leadership</a>
            {GROUPS.map((group) => (
              <a href={`#${group.id}`} key={group.id}>
                {group.eyebrow}
              </a>
            ))}
          </nav>
        </div>

        {/* Leadership */}
        <section aria-labelledby="leadership" className={styles.section}>
          <div className={styles.leadershipIntro}>
            <span className={styles.eyebrow}>Leadership</span>
            <h2 id="leadership">The founders, the advisors, the manager</h2>
            <p className={styles.sectionSubtitle}>
              The four people who set direction and sign off on every high-risk
              file.
            </p>
          </div>
          <div className={styles.leadershipGrid}>
            {LEADERSHIP.map((m) => (
              <PersonCard key={m.name} member={m} variant="leader" />
            ))}
          </div>
        </section>

        {/* Responsibility groups */}
        {GROUPS.map((group) => (
          <section
            aria-labelledby={group.id}
            className={styles.responsibilityGroup}
            key={group.id}
          >
            <div className={styles.groupIntro}>
              <span className={styles.eyebrow}>{group.eyebrow}</span>
              <h2 id={group.id}>{group.title}</h2>
              {group.description ? <p>{group.description}</p> : null}
            </div>
            <div className={styles.groupDirectory}>
              {group.people.map((m) => (
                <PersonCard key={m.name} member={m} variant="person" />
              ))}
            </div>
          </section>
        ))}

        {/* Closing invitation */}
        <aside className={styles.invitation}>
          <div>
            <h2>Not sure who to speak to?</h2>
            <p>Tell us what you are planning. We will start from there.</p>
          </div>
          <Link
            href={buildWhatsAppLink("home")}
            target="_blank"
            className={styles.ctaPrimary}
          >
            <Phone size={14} strokeWidth={2.2} aria-hidden="true" />
            Talk to the team
          </Link>
        </aside>
      </div>

      <GoogleReviewsBlock limit={6} />
    </div>
  );
}
