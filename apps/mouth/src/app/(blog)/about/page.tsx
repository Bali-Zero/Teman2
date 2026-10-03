import type { Metadata } from "next";
import Image from "next/image";
import { MapPin, Users, BadgeCheck, Calendar } from "lucide-react";
import { rosterBySlug } from "@/data/team-roster";
import { publicEntries } from "@/lib/team-public-listing";

export const metadata: Metadata = {
  alternates: {
    canonical: "https://balizero.com/about",
  },
  title: { absolute: "About Bali Zero" },
};

const STATS = [
  { value: "5,000+", label: "Clients served", icon: Users },
  { value: "2019", label: "Founded", icon: Calendar },
  { value: "18+", label: "Team members", icon: BadgeCheck },
  { value: "Bali", label: "Headquartered", icon: MapPin },
];

// Curated subset for the About page; name/role/photo from the roster SSOT.
// WHO IS SHOWN goes through publicEntries() (src/lib/team-public-listing.ts):
// the roster keeps every record, this page publishes only the people the owner
// lists publicly, so adding a slug below is never enough to publish them.
const TEAM_MEMBERS = publicEntries([
  { slug: "zainal", roleOverride: "CEO · Founder" },
  { slug: "heru", roleOverride: "Komisaris · Founder" },
  { slug: "ruslana" },
  { slug: "krisna", roleOverride: "Setup Lead" },
  { slug: "asya", roleOverride: "Accountant" },
]).map((e) => {
  const r = rosterBySlug(e.slug);
  return {
    name: r?.name ?? e.slug,
    role: e.roleOverride ?? r?.role ?? "",
    photo: r?.photo,
  };
});

export default function AboutPage() {
  return (
    <div>
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
          className="font-extrabold tracking-tight mb-6"
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
            Bali Zero started in 2019 when Zainal Abidin and Pak Heru — friends
            for 30 years, partners in business — decided that expats and
            founders in Bali deserved better than the opaque, overpriced agency
            model. One staffed with licensed professionals. One that tells you
            the truth about Indonesian regulation, even when it's inconvenient.
          </p>
          <p>
            Today we are a team of 18+ across visa processing, company setup,
            tax compliance, and property due diligence. We file about 50 KITAS
            and 8-10 PT PMAs per month. We also built Zantara, an AI assistant
            trained on every regulation we've read, every edge case we've
            solved, every filing we've made. It drafts. Our licensed team signs.
          </p>
          <p>
            We write about what we see — regulatory changes, tax traps, property
            pitfalls — because transparency is how trust is built. Not with
            slogans.
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
                background: "var(--surface-raised)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              <s.icon
                size={20}
                strokeWidth={2}
                className="mx-auto mb-2"
                style={{ color: "var(--text-tertiary)" }}
              />
              <div
                className="text-[28px] font-extrabold tracking-tight"
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
            <figure key={m.name} className="m-0">
              <div
                className="overflow-hidden relative"
                style={{
                  aspectRatio: "3 / 4",
                  background: "var(--r19-wash)",
                  border: "1px solid var(--r19-line)",
                }}
              >
                {m.photo ? (
                  <Image
                    src={m.photo}
                    alt={m.name}
                    fill
                    sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 200px"
                    quality={78}
                    loading="lazy"
                    className="object-cover"
                  />
                ) : (
                  <div
                    className="absolute inset-0 flex items-center justify-center text-2xl"
                    style={{
                      fontFamily: "var(--font-serif)",
                      color: "var(--r19-muted)",
                    }}
                  >
                    {m.name
                      .split(" ")
                      .map((w) => w[0])
                      .slice(0, 2)
                      .join("")
                      .toUpperCase()}
                  </div>
                )}
              </div>
              <figcaption className="pt-3">
                <div
                  className="text-[17px] leading-tight"
                  style={{
                    fontFamily: "var(--font-serif)",
                    color: "var(--r19-ink)",
                  }}
                >
                  {m.name}
                </div>
                <div
                  className="text-[12px] mt-1"
                  style={{ color: "var(--r19-muted)" }}
                >
                  {m.role}
                </div>
              </figcaption>
            </figure>
          ))}
        </div>
      </section>
    </div>
  );
}
