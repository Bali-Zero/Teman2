"use client";

import Image from "next/image";
import { Star, MapPin, ArrowUpRight, BadgeCheck } from "lucide-react";

// Google reviews link — the public Maps URL you shared.
// When you have the Google Place API key wired, we can swap the static
// stats + placeholder reviews for a live fetch. For now this is a
// hand-curated snapshot.
const GOOGLE_MAPS_URL = "https://maps.app.goo.gl/whiMUTNchcDR5naz8";

// Top 5 team members selected from /team (see team-scrape result).
// Photos live at /static/team/*.{png,jpg}
// When a face isn't available we show initials on a gradient disc.
interface TeamMember {
  name: string;
  role: string;
  department: string;
  photo?: string;
  initials: string;
  accent: string;
}

// Founders — shown first and larger. The two men who started Bali Zero
// and still run it. Friends for 30 years, partners in the business.
const FOUNDERS: TeamMember[] = [
  {
    name: "Zainal Abidin",
    role: "CEO",
    department: "Founder · Since the beginning",
    photo: "/static/team/heru-komisaris.jpg",
    initials: "ZA",
    accent: "#ff2d4c",
  },
  {
    name: "Pak Heru",
    role: "Komisaris",
    department: "Founder · Partner for 30 years",
    photo: "/static/team/zainal-ceo.jpg",
    initials: "PH",
    accent: "#a78bfa",
  },
];

const TEAM: TeamMember[] = [
  {
    name: "Ruslana",
    role: "Special Advisory",
    department: "Leadership",
    photo: "/static/team/ruslana.jpg",
    initials: "RU",
    accent: "#a78bfa",
  },
  {
    name: "Veronika",
    role: "Manager",
    department: "Leadership",
    initials: "VE",
    accent: "#06b6d4",
  },
  {
    name: "Adit",
    role: "Supervisor Lead",
    department: "Setup",
    photo: "/static/team/adit.png",
    initials: "AD",
    accent: "#f59e0b",
  },
  {
    name: "Angel",
    role: "Supervisor",
    department: "Tax",
    initials: "AN",
    accent: "#22c55e",
  },
];

// Curated review snippets — canonical across homepage + (blog)/_components/GoogleReviewsBlock.
const REVIEWS = [
  {
    text: "Smooth KITAS renewal in three weeks. They handled everything and updated me daily. No nasty surprises at Imigrasi.",
    author: "Marco R.",
    country: "Italy · Investor KITAS",
  },
  {
    text: "Set up my PT PMA for a tech startup. Their KBLI guidance saved us from two risky codes. Clear, fast, priced fairly.",
    author: "Ben H.",
    country: "USA · Founder",
  },
  {
    text: "Golden Visa in 11 weeks, every step documented in English. I had one point of contact from start to finish. Rare in Bali.",
    author: "Sergey K.",
    country: "Russia · Golden Visa",
  },
  {
    text: "Bought land through a PT PMA. They flagged a zoning risk the notary missed. That alone paid for the whole service.",
    author: "Laura F.",
    country: "Spain · Property · PT PMA",
  },
  {
    text: "Digital Nomad visa, fully remote, all documents handled over email. They actually replied on weekends when my flight moved.",
    author: "Tom W.",
    country: "Australia · E33G",
  },
  {
    text: "We had three PT PMAs with three different agents. Moved everything to Bali Zero. One team, one price list, no more surprises.",
    author: "Andreas M.",
    country: "Germany · Group investor",
  },
  {
    text: "First agent who actually explained CoreTax to me instead of just filing. Now I sleep at night during SPT season.",
    author: "Claudia M.",
    country: "Germany · Expat resident",
  },
];

export function SocialProof() {
  return (
    <section
      className="py-12 md:py-20 px-5 md:px-10"
      style={{ background: "var(--surface-base)" }}
    >
      <div className="max-w-[1400px] mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <div
            className="inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.15em] mb-5"
            style={{
              color: "#22c55e",
              background: "color-mix(in srgb, #22c55e 12%, transparent)",
              border: "1px solid color-mix(in srgb, #22c55e 30%, transparent)",
            }}
          >
            <BadgeCheck size={12} strokeWidth={2} />
            5,000+ expats and founders · since 2019
          </div>
          <h2
            className="font-black tracking-tight mb-4"
            style={{
              color: "var(--text-primary)",
              fontSize: "clamp(32px, 3.2vw, 48px)",
              lineHeight: 1.05,
            }}
          >
            A licensed Indonesian team,
            <br />
            <span style={{ color: "var(--text-secondary)" }}>
              behind every AI answer.
            </span>
          </h2>
          <p
            className="text-[14px] max-w-xl mx-auto"
            style={{ color: "var(--text-secondary)" }}
          >
            Real consultants handling real cases in Bali since 2019. AI drafts
            the analysis. Our licensed Indonesian team signs the filings.
          </p>
        </div>

        {/* 2-column split — left: Google reviews · right: team faces */}
        <div className="socialproof-grid grid gap-4 md:gap-6 mb-12">
          {/* Google Reviews block */}
          <div
            className="bz-glass bz-glass--strong p-8 flex flex-col"
            data-funnel="visa"
          >
            <div className="flex items-center gap-3 mb-6">
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center"
                style={{ background: "#ffffff" }}
              >
                {/* Google G logo — 4-color official brand mark */}
                <svg
                  viewBox="0 0 48 48"
                  width="22"
                  height="22"
                  aria-label="Google"
                  role="img"
                >
                  <path
                    fill="#4285F4"
                    d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
                  />
                  <path
                    fill="#34A853"
                    d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238C29.211 35.091 26.715 36 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"
                  />
                  <path
                    fill="#EA4335"
                    d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571.001-.001.002-.001.003-.002l6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
                  />
                </svg>
              </div>
              <div>
                <div
                  className="text-[11px] font-semibold uppercase tracking-[0.15em]"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  Google Reviews
                </div>
                <div className="flex items-baseline gap-2">
                  <span
                    className="text-[32px] font-extrabold tracking-tight"
                    style={{ color: "var(--text-primary)" }}
                  >
                    4.9
                  </span>
                  <div className="flex gap-0.5">
                    {[0, 1, 2, 3, 4].map((i) => (
                      <Star key={i} size={16} strokeWidth={0} fill="#fbbf24" />
                    ))}
                  </div>
                  <span
                    className="text-[12px]"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    · 627 reviews
                  </span>
                </div>
              </div>
            </div>

            <div className="space-y-4 flex-1">
              {REVIEWS.map((r) => (
                <blockquote
                  key={r.author}
                  className="pl-4"
                  style={{
                    borderLeft:
                      "2px solid color-mix(in srgb, var(--accent-funnel) 40%, transparent)",
                  }}
                >
                  <p
                    className="text-[13.5px] leading-relaxed mb-1.5"
                    style={{ color: "var(--text-primary)" }}
                  >
                    “{r.text}”
                  </p>
                  <footer
                    className="text-[11px]"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    — {r.author} · {r.country}
                  </footer>
                </blockquote>
              ))}
            </div>

            <a
              href={GOOGLE_MAPS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-6 inline-flex items-center gap-2 text-[12px] font-semibold self-start transition-colors"
              style={{ color: "var(--accent-funnel-text)" }}
            >
              <MapPin size={13} strokeWidth={2} />
              See all reviews on Google Maps
              <ArrowUpRight size={13} strokeWidth={2} />
            </a>
          </div>

          {/* Team block — founders on top, then team list */}
          <div
            className="bz-glass bz-glass--strong p-8 flex flex-col"
            data-funnel="kbli"
          >
            <div className="flex items-center justify-between gap-3 mb-5">
              <div>
                <div
                  className="text-[11px] font-semibold uppercase tracking-[0.15em] mb-1"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  The founders
                </div>
                <div
                  className="text-[22px] font-extrabold tracking-tight"
                  style={{ color: "var(--text-primary)" }}
                >
                  Zainal & Heru
                </div>
              </div>
              <a
                href="/team"
                className="inline-flex items-center gap-1.5 text-[12px] font-semibold"
                style={{ color: "var(--accent-funnel-text)" }}
              >
                All 18+
                <ArrowUpRight size={13} strokeWidth={2} />
              </a>
            </div>

            {/* Founders — portraits side by side, prominent */}
            <div className="grid grid-cols-2 gap-3 mb-5">
              {FOUNDERS.map((f) => (
                <div
                  key={f.name}
                  className="relative rounded-2xl overflow-hidden"
                  style={{
                    aspectRatio: "3 / 4",
                    background: `linear-gradient(135deg, ${f.accent} 0%, color-mix(in srgb, ${f.accent} 40%, #000) 100%)`,
                    border: `1px solid color-mix(in srgb, ${f.accent} 35%, transparent)`,
                  }}
                >
                  {f.photo && (
                    <Image
                      src={f.photo}
                      alt={`${f.name} — ${f.role}`}
                      fill
                      sizes="(max-width: 768px) 50vw, 200px"
                      style={{ objectFit: "cover" }}
                    />
                  )}
                  {/* Bottom gradient for caption legibility */}
                  <div
                    className="absolute inset-x-0 bottom-0 pt-8 pb-3 px-3"
                    style={{
                      background:
                        "linear-gradient(180deg, transparent 0%, rgba(0,0,0,0.75) 100%)",
                    }}
                  >
                    <div
                      className="text-[13px] font-extrabold tracking-tight leading-tight"
                      style={{ color: "#fff" }}
                    >
                      {f.name}
                    </div>
                    <div
                      className="text-[10px] mt-0.5"
                      style={{ color: "rgba(255,255,255,0.75)" }}
                    >
                      {f.role} · {f.department.replace("Founder · ", "")}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div
              className="text-[10px] font-semibold uppercase tracking-[0.15em] mb-2.5"
              style={{ color: "var(--text-tertiary)" }}
            >
              The team behind them
            </div>

            <ul className="flex flex-col gap-3 flex-1 list-none p-0 m-0">
              {TEAM.map((m) => (
                <li
                  key={m.name}
                  className="flex items-center gap-4 rounded-xl px-3 py-2.5 transition-colors"
                  style={{
                    background:
                      "color-mix(in srgb, var(--accent-funnel) 5%, transparent)",
                    border:
                      "1px solid color-mix(in srgb, var(--accent-funnel) 14%, transparent)",
                  }}
                >
                  {/* Photo or initials disc */}
                  <div
                    className="relative w-11 h-11 rounded-full overflow-hidden shrink-0 flex items-center justify-center"
                    style={{
                      background: `linear-gradient(135deg, ${m.accent} 0%, color-mix(in srgb, ${m.accent} 50%, #000) 100%)`,
                    }}
                  >
                    {m.photo ? (
                      <Image
                        src={m.photo}
                        alt={m.name}
                        fill
                        sizes="44px"
                        style={{ objectFit: "cover" }}
                      />
                    ) : (
                      <span
                        className="text-[13px] font-extrabold"
                        style={{ color: "#ffffff" }}
                      >
                        {m.initials}
                      </span>
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div
                      className="text-[14px] font-bold tracking-tight truncate"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {m.name}
                    </div>
                    <div
                      className="text-[11px] truncate"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      {m.role} · {m.department}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Trust strip bottom */}
        <div
          className="flex items-center justify-center gap-10 flex-wrap py-5 rounded-2xl"
          style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px solid var(--border-default)",
          }}
        >
          <TrustItem
            icon={<BadgeCheck size={14} strokeWidth={2} />}
            label="5,000+ Clients since 2019"
          />
          <TrustItem
            icon={<Star size={14} strokeWidth={0} fill="currentColor" />}
            label="4.9 ★ · 627 Google reviews"
          />
          <TrustItem
            icon={<MapPin size={14} strokeWidth={2} />}
            label="Licensed notaries & tax agents"
          />
          <TrustItem
            icon={<BadgeCheck size={14} strokeWidth={2} />}
            label="KBLI 2025 · CoreTax 2025 compliant"
          />
        </div>
      </div>
    </section>
  );
}

function TrustItem({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div
      className="inline-flex items-center gap-2 text-[12px] font-semibold"
      style={{ color: "var(--text-secondary)" }}
    >
      <span style={{ color: "var(--accent-zantara)" }}>{icon}</span>
      {label}
    </div>
  );
}
