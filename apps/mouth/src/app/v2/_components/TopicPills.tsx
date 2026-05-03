// Topic pills strip — editorial discovery layer.
// Copied in spirit from live balizero.com: 9 quick filters that answer
// "what are you expert in?" in 2 seconds. Each pill carries its own accent
// so the strip doubles as a color legend for the rest of the home.

interface Topic {
  label: string;
  href: string;
  accent: string;
}

const TOPICS: Topic[] = [
  { label: "AI & Tech", accent: "#a78bfa", href: "/news?category=trends" },
  { label: "Visas", accent: "#ff2d4c", href: "/news?category=visas" },
  { label: "Golden Visa", accent: "#f59e0b", href: "/news?q=golden+visa" },
  { label: "PT PMA", accent: "#fb923c", href: "/news?q=pt+pma" },
  { label: "Tax 2026", accent: "#3b82f6", href: "/news?category=taxes" },
  { label: "KITAS", accent: "#ff2d4c", href: "/news?q=kitas" },
  { label: "Digital Nomad", accent: "#22d3ee", href: "/news?q=digital+nomad" },
  { label: "Property", accent: "#22c55e", href: "/news?category=property" },
  { label: "Work Permits", accent: "#ec4899", href: "/news?q=work+permit" },
];

export function TopicPills() {
  return (
    <section
      className="py-8 px-10"
      style={{
        background: "var(--surface-base)",
        borderTop: "1px solid var(--border-subtle)",
        borderBottom: "1px solid var(--border-subtle)",
      }}
    >
      <div className="flex items-center gap-4 flex-wrap">
        <span
          className="text-[10px] font-bold uppercase tracking-[0.2em] shrink-0"
          style={{ color: "var(--text-tertiary)" }}
        >
          Read the news on
        </span>
        <div className="flex items-center gap-2 flex-wrap flex-1">
          {TOPICS.map((t) => (
            <a
              key={t.label}
              href={t.href}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[11.5px] font-semibold transition-all"
              style={{
                background: `color-mix(in srgb, ${t.accent} 10%, transparent)`,
                border: `1px solid color-mix(in srgb, ${t.accent} 28%, transparent)`,
                color: t.accent,
              }}
            >
              <span
                className="w-1 h-1 rounded-full"
                style={{
                  background: t.accent,
                  boxShadow: `0 0 6px ${t.accent}`,
                }}
              />
              {t.label}
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}
