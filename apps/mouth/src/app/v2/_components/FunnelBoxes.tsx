import type { Funnel } from "@balizero/core/components/ThemeProvider";

interface Box {
  funnel: Exclude<Funnel, null>;
  status: "Live" | "Beta";
  title: string;
  desc: string;
  stats: { l: string; v: string }[];
  cta: string;
}

const BOXES: Box[] = [
  {
    funnel: "visa",
    status: "Live",
    title: "Visa Oracle",
    desc: "AI immigration assistant covering all Bali visa types, requirements, and processing paths.",
    stats: [
      { l: "Visa types", v: "24+" },
      { l: "Avg response", v: "<3s" },
      { l: "Accuracy", v: "96.4%" },
    ],
    cta: "Open Oracle →",
  },
  {
    funnel: "kbli",
    status: "Live",
    title: "KBLI Navigator",
    desc: "Complete Indonesian business classification with PMA eligibility and risk scoring.",
    stats: [
      { l: "Categories", v: "1,563" },
      { l: "PMA eligible", v: "847" },
      { l: "Updated", v: "KBLI 2025" },
    ],
    cta: "Search KBLI →",
  },
  {
    funnel: "tax",
    status: "Beta",
    title: "Tax Intelligence",
    desc: "End-to-end Indonesian tax compliance. Monthly PPh 21, PPN, annual SPT — handled by experts.",
    stats: [
      { l: "Filing types", v: "12+" },
      { l: "CoreTax", v: "Integrated" },
      { l: "Support", v: "24/7 AI" },
    ],
    cta: "Explore Tax →",
  },
  {
    funnel: "property",
    status: "Beta",
    title: "Property Map",
    desc: "AI zoning analysis, land due diligence, and property intelligence across all of Bali.",
    stats: [
      { l: "Zones mapped", v: "Bali-wide" },
      { l: "Due diligence", v: "7-day" },
      { l: "Certificates", v: "Verified" },
    ],
    cta: "Check Zoning →",
  },
];

export function FunnelBoxes() {
  return (
    <section
      className="py-20 px-10"
      style={{ background: "var(--surface-raised)" }}
      id="services"
    >
      <div
        className="text-[11px] font-semibold uppercase tracking-widest mb-10"
        style={{ color: "var(--text-tertiary)" }}
      >
        Our Platforms
      </div>
      <div className="grid grid-cols-4 gap-5">
        {BOXES.map((b) => (
          <article
            key={b.funnel}
            data-funnel={b.funnel}
            id={b.funnel}
            className="bz-glass bz-glass--strong p-7 transition-transform hover:-translate-y-1"
          >
            <div
              className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest mb-4"
              style={{ color: "var(--accent-funnel-text)" }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  background: "var(--accent-funnel)",
                  boxShadow: "0 0 6px var(--accent-funnel)",
                }}
              />
              {b.status}
            </div>
            <h3
              className="text-[22px] font-extrabold tracking-tight mb-2"
              style={{ color: "var(--text-primary)" }}
            >
              {b.title}
            </h3>
            <p
              className="text-[13px] leading-relaxed mb-5"
              style={{ color: "var(--text-secondary)" }}
            >
              {b.desc}
            </p>
            <div
              className="space-y-1.5 pt-4"
              style={{ borderTop: "1px solid var(--border-default)" }}
            >
              {b.stats.map((s) => (
                <div key={s.l} className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-tertiary)" }}>{s.l}</span>
                  <span
                    className="font-semibold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {s.v}
                  </span>
                </div>
              ))}
            </div>
            <button
              className="mt-5 inline-flex items-center px-4 py-2 rounded-lg text-xs font-bold"
              style={{
                color: "var(--accent-funnel-text)",
                border:
                  "1px solid color-mix(in srgb, var(--accent-funnel) 25%, transparent)",
              }}
            >
              {b.cta}
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
