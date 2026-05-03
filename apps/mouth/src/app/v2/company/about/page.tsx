import type { Metadata } from "next";
import Image from "next/image";
import { NavShell } from "@balizero/core/components/NavShell";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { MapPin, Users, BadgeCheck, Calendar } from "lucide-react";
import { Footer } from "../../_components/Footer";

export const metadata: Metadata = {
  title: "About Bali Zero",
  robots: { index: false, follow: false },
};

const STATS = [
  { value: "5,000+", label: "Clients served", icon: Users },
  { value: "2019", label: "Founded", icon: Calendar },
  { value: "18+", label: "Team members", icon: BadgeCheck },
  { value: "Bali", label: "Headquartered", icon: MapPin },
];

const TEAM_MEMBERS = [
  {
    name: "Zainal Abidin",
    role: "CEO · Founder",
    photo: "/static/team/zainal-ceo.jpg",
    accent: "#ff2d4c",
  },
  {
    name: "Pak Heru",
    role: "Komisaris · Founder",
    photo: "/static/team/heru-komisaris.jpg",
    accent: "#a78bfa",
  },
  {
    name: "Ruslana",
    role: "Board Member",
    photo: "/static/team/ruslana.jpg",
    accent: "#f59e0b",
  },
  {
    name: "Krisna",
    role: "Setup Lead",
    photo: "/static/team/krisna.png",
    accent: "#22c55e",
  },
  {
    name: "Asya Nadia",
    role: "Accountant",
    photo: "/static/team/asya.jpg",
    accent: "#06b6d4",
  },
];

export default function AboutPage() {
  return (
    <div
      style={{
        background: "var(--surface-base)",
        color: "var(--text-primary)",
        minHeight: "100vh",
      }}
    >
      <NavShell
        logo={<BZLogo variant="full" size={36} />}
        items={[
          { label: "Home", href: "/v2" },
          { label: "About", href: "/v2/company/about" },
        ]}
        actions={null}
      />

      <main className="pt-20">
        {/* Hero band — team photo wide */}
        <section
          className="relative overflow-hidden"
          style={{ aspectRatio: "21/7" }}
        >
          <Image
            src="/assets/art/hero-team.jpeg"
            alt="The Bali Zero team at a working session in a Balinese bale pavilion"
            fill
            priority
            sizes="100vw"
            quality={78}
            className="object-cover"
          />
          <div
            className="absolute inset-0"
            style={{
              background:
                "linear-gradient(0deg, var(--surface-base) 0%, rgba(18,16,22,0.4) 50%, rgba(18,16,22,0.2) 100%)",
            }}
          />
        </section>

        {/* Copy */}
        <section className="max-w-3xl mx-auto px-6 md:px-10 -mt-16 relative z-10 pb-16">
          <div
            className="text-[10px] font-semibold uppercase tracking-[0.2em] mb-4"
            style={{ color: "var(--text-tertiary)" }}
          >
            Company · Kerobokan, Bali
          </div>

          <h1
            className="font-black tracking-tight mb-6"
            style={{ fontSize: "clamp(28px, 4vw, 48px)", lineHeight: 1.1 }}
          >
            We spend our days{" "}
            <span style={{ color: "var(--text-secondary)" }}>
              fixing what most people get wrong in their first month in Bali.
            </span>
          </h1>

          <div
            className="text-[15px] leading-relaxed space-y-5"
            style={{ color: "var(--text-secondary)" }}
          >
            <p>
              Bali Zero started in 2019 when Zainal Abidin and Pak Heru —
              friends for 30 years, partners in business — decided that expats
              and founders in Bali deserved better than the opaque, overpriced
              agency model. One staffed with licensed professionals. One that
              tells you the truth about Indonesian regulation, even when it's
              inconvenient.
            </p>
            <p>
              Today we are a team of 18+ across visa processing, company setup,
              tax compliance, and property due diligence. We file about 50 KITAS
              and 8-10 PT PMAs per month. We also built Zantara, an AI assistant
              trained on every regulation we've read, every edge case we've
              solved, every filing we've made. It drafts. Our licensed team
              signs.
            </p>
            <p>
              We write about what we see — regulatory changes, tax traps,
              property pitfalls — because transparency is how trust is built.
              Not with slogans.
            </p>
          </div>
        </section>

        {/* Stats */}
        <section className="max-w-4xl mx-auto px-6 md:px-10 pb-16">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {STATS.map((s) => (
              <div
                key={s.label}
                className="rounded-2xl p-5 text-center"
                style={{
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid var(--border-default)",
                }}
              >
                <s.icon
                  size={20}
                  strokeWidth={2}
                  className="mx-auto mb-2"
                  style={{ color: "var(--text-tertiary)" }}
                />
                <div
                  className="text-[28px] font-black tracking-tight"
                  style={{ color: "var(--text-primary)" }}
                >
                  {s.value}
                </div>
                <div
                  className="text-[12px] mt-1"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Team grid */}
        <section className="max-w-4xl mx-auto px-6 md:px-10 pb-20">
          <h2
            className="text-[12px] font-bold uppercase tracking-[0.15em] mb-6"
            style={{ color: "var(--text-tertiary)" }}
          >
            The team
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
            {TEAM_MEMBERS.map((m) => (
              <div
                key={m.name}
                className="rounded-2xl overflow-hidden relative"
                style={{
                  aspectRatio: "3 / 4",
                  background: `linear-gradient(135deg, ${m.accent} 0%, color-mix(in srgb, ${m.accent} 40%, #000) 100%)`,
                  border: `1px solid color-mix(in srgb, ${m.accent} 25%, transparent)`,
                }}
              >
                <Image
                  src={m.photo}
                  alt={m.name}
                  fill
                  sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 200px"
                  quality={78}
                  loading="lazy"
                  className="object-cover"
                />
                <div
                  className="absolute inset-x-0 bottom-0 pt-10 pb-3 px-3"
                  style={{
                    background:
                      "linear-gradient(180deg, transparent 0%, rgba(0,0,0,0.75) 100%)",
                  }}
                >
                  <div
                    className="text-[13px] font-bold"
                    style={{ color: "#fff" }}
                  >
                    {m.name}
                  </div>
                  <div
                    className="text-[10px] mt-0.5"
                    style={{ color: "rgba(255,255,255,0.7)" }}
                  >
                    {m.role}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
