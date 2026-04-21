import type { Metadata } from "next";
import Link from "next/link";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import {
  ArrowRight,
  IdCard,
  Building2,
  TrendingUp,
  MapPinned,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { GoogleReviewsBlock } from "../_components/GoogleReviewsBlock";

export const metadata: Metadata = {
  title: "Services · Bali Zero",
  description:
    "Visa, PT PMA, tax, property — handled in Bali by a licensed Indonesian team since 2006.",
};

interface Service {
  slug: string;
  name: string;
  tagline: string;
  description: string;
  accent: string;
  icon: typeof IdCard;
  bullets: string[];
  cta: { label: string; href: string };
  priceLabel: string;
  priceFrom: string;
}

const SERVICES: Service[] = [
  {
    slug: "immigration",
    name: "Visa & Immigration",
    tagline: "KITAS, KITAP, Golden Visa, Digital Nomad",
    description:
      "24+ visa categories. AI narrows the options; licensed konsultan imigrasi files.",
    accent: "#c8102e",
    icon: IdCard,
    bullets: [
      "Tourist, Business, KITAS, KITAP, Golden Visa, E33G",
      "Sponsored and self-sponsored paths",
      "Dependent family visa packaging",
      "Overstay & obsolete-status recovery",
    ],
    cta: { label: "Open Visa Check", href: "/visa" },
    priceLabel: "From",
    priceFrom: "$350 / visa",
  },
  {
    slug: "business",
    name: "Company Setup",
    tagline: "PT PMA, PT Local, KBLI, OSS, licenses",
    description:
      "From KBLI fit to the live NIB: one team, one price list, audit-grade paperwork.",
    accent: "#d4a017",
    icon: Building2,
    bullets: [
      "1,563 KBLI 2025 codes · 4-level risk mapping",
      "PT PMA minimum capital & classified sectors",
      "OSS, SKK, operational licenses",
      "Shareholder structures, nominee-free",
    ],
    cta: { label: "Open KBLI Navigator", href: "/kbli" },
    priceLabel: "From",
    priceFrom: "$1,850 / company",
  },
  {
    slug: "tax",
    name: "Tax & Accounting",
    tagline: "CoreTax 2026, PPh, PPN, BPJS, LKPM",
    description:
      "Corporate and personal tax compliance under CoreTax 2026 — filed, not guessed.",
    accent: "#38bdf8",
    icon: TrendingUp,
    bullets: [
      "12+ filing types · monthly + annual",
      "CoreTax native integration",
      "BPJS and LKPM quarterly reporting",
      "Cross-border tax residency analysis",
    ],
    cta: { label: "See Tax Calendar", href: "/tax-calendar" },
    priceLabel: "From",
    priceFrom: "$220 / month",
  },
  {
    slug: "property",
    name: "Property & Zoning",
    tagline: "Hak Pakai, HGB via PMA, leasehold, DD",
    description:
      "Plot-level zoning, legal vehicle, tax exposure and risk score before you sign.",
    accent: "#22c55e",
    icon: MapPinned,
    bullets: [
      "RTRW / RDTR overlay per plot",
      "Sertifikat verification & NJOP check",
      "Tsunami, flooding, erosion risk score",
      "7-day due diligence turnaround",
    ],
    cta: { label: "Check a plot", href: "/property/eligibility" },
    priceLabel: "From",
    priceFrom: "$850 / report",
  },
];

const TRUST_STRIP = [
  { value: "5,000+", label: "Cases handled since 2019" },
  { value: "4.9 ★", label: "627 Google reviews" },
  { value: "18+", label: "Licensed specialists" },
  { value: "2006", label: "Year founded" },
];

export default function ServicesPage() {
  return (
    <div
      className="min-h-screen"
      style={{
        background: "var(--surface-base)",
        color: "var(--text-primary)",
      }}
    >
      {/* Hero */}
      <section
        style={{
          padding: "clamp(64px, 8vw, 120px) clamp(24px, 4vw, 40px) 40px",
        }}
      >
        <div className="max-w-[1400px] mx-auto">
          <div
            className="text-[11px] font-semibold uppercase tracking-[0.28em] mb-5"
            style={{ color: "var(--accent-funnel-text, #5c8aff)" }}
          >
            Services · AI drafts · Licensed team signs
          </div>
          <h1
            className="font-extrabold tracking-tight mb-5"
            style={{
              fontSize: "clamp(34px, 5vw, 60px)",
              lineHeight: 1.05,
              color: "var(--text-primary)",
              maxWidth: "22ch",
            }}
          >
            Four missions.
            <br />
            <span style={{ color: "var(--text-secondary)" }}>
              One licensed Indonesian team.
            </span>
          </h1>
          <p
            className="text-[16px] leading-[1.6] mb-8"
            style={{ color: "var(--text-secondary)", maxWidth: "64ch" }}
          >
            Visa, company setup, tax compliance, property due diligence. Each
            product is fronted by an AI that reads Indonesian primary sources —
            but the filings are signed by licensed konsultan imigrasi, konsultan
            pajak and registered notaries. Since 2006.
          </p>
        </div>
      </section>

      {/* Trust strip */}
      <section
        style={{
          borderBottom: "1px solid var(--border-subtle)",
          borderTop: "1px solid var(--border-subtle)",
          padding: "clamp(24px, 3vw, 36px) clamp(24px, 4vw, 40px)",
          background:
            "color-mix(in srgb, var(--accent-funnel, #3a6dff) 5%, transparent)",
        }}
      >
        <div className="max-w-[1400px] mx-auto">
          <div
            className="grid gap-6"
            style={{
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            }}
          >
            {TRUST_STRIP.map((t) => (
              <div key={t.label} className="text-center md:text-left">
                <div
                  className="font-extrabold tracking-tight"
                  style={{
                    fontSize: "clamp(24px, 2.2vw, 32px)",
                    color: "var(--text-primary)",
                  }}
                >
                  {t.value}
                </div>
                <div
                  className="text-[12px] mt-1 uppercase tracking-wider"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {t.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Services grid */}
      <section
        style={{
          padding: "clamp(48px, 6vw, 80px) clamp(24px, 4vw, 40px)",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <div className="max-w-[1100px] mx-auto">
          <div className="grid gap-6 grid-cols-1 md:grid-cols-2">
            {SERVICES.map((s) => (
              <div
                key={s.slug}
                className="relative rounded-2xl p-6 overflow-hidden"
                style={{
                  background: `color-mix(in srgb, ${s.accent} 22%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${s.accent} 60%, transparent)`,
                  boxShadow: `0 16px 48px color-mix(in srgb, ${s.accent} 32%, transparent), inset 0 1px 0 rgba(255,255,255,0.08)`,
                  backdropFilter: "blur(20px) saturate(180%)",
                  WebkitBackdropFilter: "blur(20px) saturate(180%)",
                }}
              >
                <div
                  className="absolute inset-0 pointer-events-none"
                  style={{
                    background: `radial-gradient(ellipse 70% 50% at 20% 10%, color-mix(in srgb, ${s.accent} 42%, transparent) 0%, transparent 65%)`,
                  }}
                  aria-hidden="true"
                />

                <div className="relative">
                  <div className="flex items-start gap-3 mb-4">
                    <div
                      className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0"
                      style={{
                        background: `color-mix(in srgb, ${s.accent} 20%, transparent)`,
                        border: `1px solid color-mix(in srgb, ${s.accent} 50%, transparent)`,
                        color: s.accent,
                      }}
                    >
                      <s.icon size={20} strokeWidth={2} />
                    </div>
                    <div>
                      <h2
                        className="text-[22px] font-extrabold tracking-tight"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {s.name}
                      </h2>
                      <div
                        className="text-[12px] font-semibold mt-1"
                        style={{ color: s.accent }}
                      >
                        {s.tagline}
                      </div>
                    </div>
                  </div>

                  <p
                    className="text-[14px] leading-[1.6] mb-5"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {s.description}
                  </p>

                  <ul
                    className="space-y-2 mb-6"
                    style={{ listStyle: "none", padding: 0, margin: 0 }}
                  >
                    {s.bullets.map((b) => (
                      <li
                        key={b}
                        className="flex items-start gap-2.5 text-[13px]"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        <span
                          className="mt-1.5 shrink-0 rounded-full"
                          style={{
                            width: 6,
                            height: 6,
                            background: s.accent,
                            boxShadow: `0 0 8px ${s.accent}`,
                          }}
                        />
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>

                  <div className="flex items-center justify-between gap-4 flex-wrap">
                    <div>
                      <div
                        className="text-[10px] font-semibold uppercase tracking-[0.2em]"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        {s.priceLabel}
                      </div>
                      <div
                        className="text-[18px] font-bold"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {s.priceFrom}
                      </div>
                    </div>
                    <Link
                      href={s.cta.href}
                      className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md text-[13px] font-semibold"
                      style={{
                        background: s.accent,
                        color: "#ffffff",
                        boxShadow: `0 8px 24px color-mix(in srgb, ${s.accent} 45%, transparent)`,
                      }}
                    >
                      {s.cta.label}
                      <ArrowRight size={13} strokeWidth={2.2} />
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <GoogleReviewsBlock limit={6} />

      {/* How we work */}
      <section
        style={{ padding: "clamp(48px, 6vw, 80px) clamp(24px, 4vw, 40px)" }}
      >
        <div className="max-w-[1400px] mx-auto">
          <div className="mb-10">
            <div
              className="text-[11px] font-semibold uppercase tracking-[0.28em] mb-3"
              style={{ color: "var(--accent-funnel-text, #5c8aff)" }}
            >
              How we work
            </div>
            <h2
              className="font-extrabold tracking-tight"
              style={{
                fontSize: "clamp(26px, 2.4vw, 34px)",
                color: "var(--text-primary)",
              }}
            >
              Four moves, no guesswork
            </h2>
          </div>

          <ol
            className="grid gap-4"
            style={{
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              listStyle: "none",
              padding: 0,
              margin: 0,
            }}
          >
            {[
              {
                n: "01",
                title: "Scope it",
                body: "WhatsApp or Visa Check for a first read — free, under 15 min.",
                accent: "#c8102e",
              },
              {
                n: "02",
                title: "AI drafts",
                body: "The AI reads your case against every primary source we track.",
                accent: "#d4a017",
              },
              {
                n: "03",
                title: "Licensed sign-off",
                body: "A konsultan imigrasi, konsultan pajak or notary reviews and signs.",
                accent: "#38bdf8",
              },
              {
                n: "04",
                title: "Filed + cited",
                body: "Every filing comes with a source trail — no black-box guidance.",
                accent: "#22c55e",
              },
            ].map(({ n, title, body, accent }) => (
              <li
                key={n}
                className="rounded-2xl p-5"
                style={{
                  background: `color-mix(in srgb, ${accent} 8%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${accent} 28%, transparent)`,
                  boxShadow: `0 10px 24px color-mix(in srgb, ${accent} 14%, transparent)`,
                }}
              >
                <div
                  className="text-[11px] font-bold tracking-[0.18em]"
                  style={{ color: accent }}
                >
                  {n}
                </div>
                <div
                  className="text-[16px] font-bold tracking-tight mt-1.5"
                  style={{ color: "var(--text-primary)" }}
                >
                  {title}
                </div>
                <div
                  className="text-[13px] leading-[1.55] mt-2"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {body}
                </div>
              </li>
            ))}
          </ol>

          <div className="mt-12 flex flex-wrap items-center gap-3">
            <Link
              href={buildWhatsAppLink("home")}
              target="_blank"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-md text-[14px] font-semibold"
              style={{
                background: "var(--accent-funnel, #3a6dff)",
                color: "var(--text-on-accent, #fff)",
                boxShadow: "0 10px 32px rgba(0,0,0,0.25)",
              }}
            >
              <Sparkles size={14} strokeWidth={2.2} />
              Talk to the team
            </Link>
            <Link
              href="/team"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-md text-[14px] font-semibold"
              style={{
                background: "transparent",
                color: "var(--text-secondary)",
                border: "1px solid var(--border-default)",
              }}
            >
              <ShieldCheck size={14} strokeWidth={2.2} />
              Meet the 18+ specialists
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
