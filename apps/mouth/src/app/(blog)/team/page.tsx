import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { Phone, ArrowRight } from "lucide-react";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { GoogleReviewsBlock } from "../_components/GoogleReviewsBlock";
import { RUMAH_VARS, RUMAH_CLASS } from "@/lib/theme/rumahVars";
import { rosterBySlug, initialsOf } from "@/data/team-roster";

export const metadata: Metadata = {
  title: "Team · Bali Zero",
  description:
    "The Bali Zero team — licensed founders, consultants, tax specialists, notaries and marketing. Real people handling real cases in Bali since 2006.",
};

// ─── Editorial layout for this page ─────────────────────────────────────────
// NAME / ROLE / PHOTO are pulled from the roster SSOT (apps/mouth/src/data/team-roster.ts)
// by `slug`. This page keeps only its EDITORIAL choices: which section a person appears
// in and the per-person gradient. To change a photo/role → edit the roster, not here.
// `nameOverride`/`roleOverride` exist for page-specific labels (e.g. Zero "SOTA Marketing")
// and for people not in the public roster.

interface TeamMember {
  name: string;
  initials: string;
  role: string;
  gradient: string;
  photo?: string;
}

interface EditorialEntry {
  slug?: string; // → roster SSOT for name/role/photo
  gradient: string;
  nameOverride?: string; // page-specific display name (or for non-roster people)
  roleOverride?: string; // page-specific role label
  photoOverride?: string;
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
  };
}

// Each section keeps its EDITORIAL composition + gradients; name/role/photo come from
// the roster SSOT via resolve(). Role overrides preserve this page's curated labels.
const LEADERSHIP: TeamMember[] = [
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
].map(resolve);

const SETUP_TEAM: TeamMember[] = [
  {
    slug: "adit",
    gradient: "linear-gradient(135deg, #06b6d4 0%, #2563eb 100%)",
  },
  {
    slug: "ari",
    roleOverride: "Supervisor",
    gradient: "linear-gradient(135deg, #f43f5e 0%, #db2777 100%)",
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
].map(resolve);

const TAX_TEAM: TeamMember[] = [
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
].map(resolve);

const ACCOUNTING_TEAM: TeamMember[] = [
  {
    slug: "asya",
    roleOverride: "Accountant",
    gradient: "linear-gradient(135deg, #10b981 0%, #0d9488 100%)",
  },
  {
    slug: "rina",
    gradient: "linear-gradient(135deg, #ec4899 0%, #db2777 100%)",
  },
].map(resolve);

// Marketing is an editorial grouping unique to this page (Zero is not in the public roster;
// Surya/Subhi live under setup/support in the SSOT but are presented here as marketing).
const MARKETING_TEAM: TeamMember[] = [
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
].map(resolve);

// ─── UI helpers ────────────────────────────────────────────────────────────

function TeamCard({
  member,
  size = "small",
}: {
  member: TeamMember;
  size?: "large" | "small";
}) {
  const isLarge = size === "large";
  const avatar = isLarge ? 120 : 64;

  return (
    <div
      className="group rounded-2xl p-5 transition-all hover:-translate-y-0.5"
      style={{
        background:
          "color-mix(in srgb, var(--accent-funnel, #3a6dff) 6%, transparent)",
        border:
          "1px solid color-mix(in srgb, var(--accent-funnel, #3a6dff) 20%, transparent)",
        backdropFilter: "blur(20px) saturate(160%)",
        WebkitBackdropFilter: "blur(20px) saturate(160%)",
      }}
    >
      <div className="flex items-center gap-4">
        <div
          className="relative overflow-hidden rounded-full shrink-0 flex items-center justify-center"
          style={{
            width: avatar,
            height: avatar,
            background: member.gradient,
            boxShadow: "inset 0 1px 0 rgba(255,255,255,0.12)",
          }}
        >
          {member.photo ? (
            <Image
              src={member.photo}
              alt={`${member.name} — ${member.role}`}
              fill
              sizes={`${avatar}px`}
              style={{ objectFit: "cover" }}
            />
          ) : (
            <span
              className="font-extrabold text-white"
              style={{ fontSize: isLarge ? 38 : 20 }}
            >
              {member.initials}
            </span>
          )}
        </div>
        <div className="min-w-0">
          <div
            className={
              isLarge
                ? "text-[22px] font-extrabold tracking-tight"
                : "text-[15px] font-bold tracking-tight"
            }
            style={{ color: "var(--text-primary)" }}
          >
            {member.name}
          </div>
          <div
            className="text-[12px] mt-1"
            style={{ color: "var(--text-tertiary)" }}
          >
            {member.role}
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({
  eyebrow,
  title,
  subtitle,
  children,
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      style={{
        borderBottom: "1px solid var(--border-subtle)",
        padding: "clamp(48px, 6vw, 80px) clamp(24px, 4vw, 40px)",
      }}
    >
      <div className="max-w-[1400px] mx-auto">
        <div className="mb-8">
          <h2
            className="font-extrabold tracking-tight"
            style={{
              color: "var(--text-primary)",
              fontSize: "clamp(36px, 4.2vw, 56px)",
              lineHeight: 1.05,
            }}
          >
            {eyebrow}
          </h2>
          <div
            className="mt-3 text-[15px] font-semibold"
            style={{ color: "var(--text-secondary)" }}
          >
            {title}
          </div>
          {subtitle ? (
            <p
              className="mt-1.5 text-[12px] max-w-2xl"
              style={{ color: "var(--text-tertiary)" }}
            >
              {subtitle}
            </p>
          ) : null}
        </div>
        <div
          className="grid gap-4"
          style={{
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          }}
        >
          {children}
        </div>
      </div>
    </section>
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
      {/* Hero */}
      <section
        className="relative overflow-hidden"
        style={{ padding: "clamp(64px, 8vw, 120px) clamp(24px, 4vw, 40px)" }}
      >
        <div className="max-w-[1400px] mx-auto">
          <div className="flex flex-col lg:flex-row gap-10 items-end justify-between">
            <div className="max-w-[720px]">
              <div
                className="text-[11px] font-semibold uppercase tracking-[0.28em] mb-5"
                style={{ color: "var(--accent-funnel-text, #5c8aff)" }}
              >
                The Team · 18+ specialists · Kerobokan, Bali
              </div>
              <h1
                className="font-extrabold tracking-tight mb-5"
                style={{
                  fontSize: "clamp(34px, 5vw, 60px)",
                  lineHeight: 1.05,
                  color: "var(--text-primary)",
                }}
              >
                Real people.
                <br />
                <span style={{ color: "var(--text-secondary)" }}>
                  Real licenses. Real files.
                </span>
              </h1>
              <p
                className="text-[16px] leading-[1.6] mb-6"
                style={{ color: "var(--text-secondary)", maxWidth: "56ch" }}
              >
                Started in Kerobokan in 2006 — two friends, one office, a lot of
                immigration paperwork. Today the team handles 47 KITAS and 9 PT
                PMAs every month. AI drafts; licensed Indonesians sign.
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <Link
                  href={buildWhatsAppLink("home")}
                  target="_blank"
                  className="inline-flex items-center gap-2 px-5 py-3 rounded-md text-[13px] font-semibold"
                  style={{
                    background: "var(--accent-funnel, #3a6dff)",
                    color: "var(--text-on-accent, #fff)",
                    boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
                  }}
                >
                  <Phone size={14} strokeWidth={2.2} />
                  Talk to the team
                </Link>
                <Link
                  href="/services"
                  className="inline-flex items-center gap-2 px-5 py-3 rounded-md text-[13px] font-semibold"
                  style={{
                    background: "transparent",
                    color: "var(--text-secondary)",
                    border: "1px solid var(--border-default)",
                  }}
                >
                  See services
                  <ArrowRight size={14} strokeWidth={2.2} />
                </Link>
              </div>
            </div>

            {/* Aggregate trust — Rumah Putih: white card + hairline border,
                navy hairline dividers (was dark-glass on the editorial home). */}
            <div
              className="inline-flex items-center gap-4 px-4 py-2.5 rounded-full flex-wrap"
              style={{
                background: "var(--rp-card-bg, rgba(0,0,0,0.28))",
                boxShadow: "var(--rp-card-shadow, none)",
                border:
                  "1px solid var(--rp-card-border, rgba(255,255,255,0.14))",
              }}
            >
              <span
                className="inline-flex items-center gap-1.5 text-[12px] font-semibold"
                style={{ color: "var(--text-primary)" }}
              >
                <span style={{ color: "#d4a017" }}>★★★★★</span>
                <span>4.9</span>
                <span style={{ color: "var(--text-tertiary)" }}>
                  · 627 Google reviews
                </span>
              </span>
              <span
                className="h-3.5 w-px"
                style={{
                  background: "var(--border-default, rgba(255,255,255,0.18))",
                }}
              />
              <span
                className="text-[12px] font-semibold"
                style={{ color: "var(--text-primary)" }}
              >
                5,000+ cases
              </span>
              <span
                className="h-3.5 w-px"
                style={{
                  background: "var(--border-default, rgba(255,255,255,0.18))",
                }}
              />
              <span
                className="text-[12px] font-semibold"
                style={{ color: "var(--text-primary)" }}
              >
                Licensed since 2006
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Leadership */}
      <Section
        eyebrow="Leadership"
        title="The founders, the advisors, the manager"
        subtitle="The four people who set direction and sign off on every high-risk file."
      >
        {LEADERSHIP.map((m) => (
          <TeamCard key={m.initials} member={m} size="large" />
        ))}
      </Section>

      {/* Setup team */}
      <Section
        eyebrow="Setup · Visa & Company"
        title="Your Indonesia operation, end-to-end"
        subtitle="Visa intake, PT PMA incorporation, KBLI due diligence, OSS filings."
      >
        {SETUP_TEAM.map((m) => (
          <TeamCard key={m.initials} member={m} />
        ))}
      </Section>

      {/* Tax */}
      <Section
        eyebrow="Tax"
        title="Licensed konsultan pajak"
        subtitle="Corporate and personal tax compliance under CoreTax 2026."
      >
        {TAX_TEAM.map((m) => (
          <TeamCard key={m.initials} member={m} />
        ))}
      </Section>

      {/* Accounting & reception */}
      <Section
        eyebrow="Accounting & Reception"
        title="The backbone of every month-end"
      >
        {ACCOUNTING_TEAM.map((m) => (
          <TeamCard key={m.initials} member={m} />
        ))}
      </Section>

      {/* Marketing */}
      <Section
        eyebrow="Marketing"
        title="The intelligence arm"
        subtitle="Editorial, content, the Zantara AI layer that keeps the site alive."
      >
        {MARKETING_TEAM.map((m) => (
          <TeamCard key={m.initials} member={m} />
        ))}
      </Section>

      <GoogleReviewsBlock limit={6} />
    </div>
  );
}
