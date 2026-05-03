import { Star, MapPin, ArrowUpRight } from "lucide-react";

// Canonical Google reviews — same source as homepage SocialProof.
// If you edit here, also edit apps/mouth/src/app/v2/_components/SocialProof.tsx.
const GOOGLE_MAPS_URL = "https://maps.app.goo.gl/whiMUTNchcDR5naz8";

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
];

export function GoogleReviewsBlock({
  limit = 7,
  eyebrow = "What clients say",
  title = "4.9 ★ · 627 Google reviews",
}: {
  limit?: number;
  eyebrow?: string;
  title?: string;
}) {
  const items = REVIEWS.slice(0, limit);

  return (
    <section
      className="relative"
      style={{
        padding: "clamp(48px, 6vw, 80px) clamp(24px, 4vw, 40px)",
        borderBottom: "1px solid var(--border-subtle)",
        borderTop: "1px solid var(--border-subtle)",
      }}
    >
      <div className="max-w-[1400px] mx-auto">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-10">
          <div>
            <div
              className="text-[11px] font-semibold uppercase tracking-[0.2em] mb-2"
              style={{ color: "var(--accent-funnel-text, #5c8aff)" }}
            >
              {eyebrow}
            </div>
            <h2
              className="font-extrabold tracking-tight flex items-center gap-3 flex-wrap"
              style={{
                color: "var(--text-primary)",
                fontSize: "clamp(26px, 2.4vw, 34px)",
              }}
            >
              <span>{title}</span>
              <span
                className="inline-flex gap-0.5"
                style={{ color: "#fbbf24" }}
              >
                {[0, 1, 2, 3, 4].map((i) => (
                  <Star key={i} size={18} strokeWidth={0} fill="#fbbf24" />
                ))}
              </span>
            </h2>
          </div>
          <a
            href={GOOGLE_MAPS_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-[12px] font-semibold uppercase tracking-widest"
            style={{ color: "var(--accent-funnel-text, #5c8aff)" }}
          >
            <MapPin size={13} strokeWidth={2} /> See all on Google Maps
            <ArrowUpRight size={13} strokeWidth={2} />
          </a>
        </div>

        <div
          className="grid gap-4"
          style={{
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          }}
        >
          {items.map((r) => (
            <blockquote
              key={r.author}
              className="rounded-2xl p-5"
              style={{
                background:
                  "color-mix(in srgb, var(--accent-funnel, #3a6dff) 6%, transparent)",
                border:
                  "1px solid color-mix(in srgb, var(--accent-funnel, #3a6dff) 18%, transparent)",
                backdropFilter: "blur(20px) saturate(160%)",
                WebkitBackdropFilter: "blur(20px) saturate(160%)",
              }}
            >
              <p
                className="text-[14px] leading-[1.55] mb-3"
                style={{ color: "var(--text-primary)" }}
              >
                “{r.text}”
              </p>
              <footer
                className="text-[11.5px]"
                style={{ color: "var(--text-tertiary)" }}
              >
                — {r.author} · {r.country}
              </footer>
            </blockquote>
          ))}
        </div>
      </div>
    </section>
  );
}
