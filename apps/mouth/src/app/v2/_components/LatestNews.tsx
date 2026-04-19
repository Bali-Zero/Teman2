import Link from "next/link";
import Image from "next/image";
import { Calendar, Clock, ArrowUpRight, type LucideIcon } from "lucide-react";

interface Article {
  tag: string;
  accent: string;
  href: string;
  date: string;
  readTime: string;
  title: string;
  excerpt: string;
  image: string;
}

// Color mapping (consistent with NewsHero):
//   red=Immigration, blue=Tax, green=Property, gold=Business,
//   orange=System, cyan=Tech, pink=Culture, white=Other.
const ARTICLES: Article[] = [
  {
    tag: "Visa",
    accent: "#ff2d4c", // red
    href: "/news/digital-nomad-visa-2026",
    date: "Apr 12, 2026",
    readTime: "4 min",
    title: "Digital Nomad Visa: Six Months Living and Working in Bali",
    excerpt: "The new category lets founders stay and bill clients abroad — what it actually covers.",
    image: "/assets/art/news/immigration-queue.jpg",
  },
  {
    tag: "Tax",
    accent: "#3b82f6", // blue
    href: "/news/pph-21-reform-2026",
    date: "Apr 10, 2026",
    readTime: "8 min",
    title: "PPh 21 Reform 2026: New Rates and Calculation Methods",
    excerpt: "The 2026 personal income tax structure is live. Bracket changes, deduction updates.",
    image: "/assets/art/news/expat-tax.jpg",
  },
  {
    tag: "Property",
    accent: "#22c55e", // green
    href: "/news/hak-pakai-vs-leasehold",
    date: "Apr 7, 2026",
    readTime: "6 min",
    title: "Hak Pakai vs Leasehold: A Foreigner's Decision Matrix",
    excerpt: "Which property right makes sense for which strategy — six real Bali cases.",
    image: "/assets/art/news/fisherman-beach.jpg",
  },
  {
    tag: "Business",
    accent: "#f59e0b", // gold
    href: "/news/pt-pma-minimum-capital-2026",
    date: "Apr 4, 2026",
    readTime: "5 min",
    title: "PT PMA Minimum Capital: What 10B IDR Actually Buys",
    excerpt: "The official threshold masks a different operational reality — sector by sector.",
    image: "/assets/art/news/entrepreneur-night.jpg",
  },
  {
    tag: "Immigration",
    accent: "#ff2d4c", // red (shared with Visa/immigration family)
    href: "/news/kitas-renewal-2026",
    date: "Apr 1, 2026",
    readTime: "7 min",
    title: "KITAS Renewal in 2026: The Paperwork That Actually Matters",
    excerpt: "Seven documents, three newly required this year. Sequence, timing, common rejections.",
    image: "/assets/art/news/officer-hands.jpg",
  },
];

export function LatestNews() {
  return (
    <section className="py-20 px-10" style={{ background: "var(--surface-base)" }}>
      <div className="flex items-end justify-between mb-10">
        <div>
          <div
            className="text-[11px] font-semibold uppercase tracking-widest mb-2"
            style={{ color: "var(--text-tertiary)" }}
          >
            Latest from Bali Zero
          </div>
          <h3
            className="text-[26px] font-extrabold tracking-tight"
            style={{ color: "var(--text-primary)" }}
          >
            Fresh intelligence for expats and investors
          </h3>
        </div>
        <a
          href="/v2/news"
          className="inline-flex items-center gap-2 text-[12px] font-semibold uppercase tracking-widest"
          style={{ color: "var(--text-secondary)" }}
        >
          View all <ArrowUpRight size={14} strokeWidth={2} />
        </a>
      </div>

      <div className="grid grid-cols-5 gap-4">
        {ARTICLES.map((a) => (
          <Link
            key={a.title}
            href={a.href}
            className="rounded-2xl p-0 overflow-hidden transition-all hover:-translate-y-1 block focus-visible:outline-none focus-visible:ring-2"
            style={{
              background: `linear-gradient(135deg, color-mix(in srgb, ${a.accent} 18%, transparent) 0%, rgba(255,255,255,0.04) 100%)`,
              border: `1px solid color-mix(in srgb, ${a.accent} 35%, transparent)`,
              backdropFilter: "blur(24px) saturate(160%)",
              WebkitBackdropFilter: "blur(24px) saturate(160%)",
              boxShadow: `0 10px 40px rgba(0,0,0,0.25), 0 0 30px color-mix(in srgb, ${a.accent} 15%, transparent)`,
            }}
          >
            <div className="h-36 relative overflow-hidden">
              <Image
                src={a.image}
                alt=""
                fill
                sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 320px"
                quality={75}
                loading="lazy"
                className="object-cover"
                aria-hidden="true"
              />
              <div
                className="absolute inset-0"
                style={{
                  background:
                    "linear-gradient(0deg, rgba(0,0,0,0.55) 0%, transparent 60%)",
                }}
              />
              <div
                className="absolute top-3 left-3 inline-flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full"
                style={{
                  background: `color-mix(in srgb, ${a.accent} 32%, rgba(0,0,0,0.55))`,
                  border: `1px solid color-mix(in srgb, ${a.accent} 55%, transparent)`,
                  color: "#ffffff",
                  backdropFilter: "blur(8px)",
                  WebkitBackdropFilter: "blur(8px)",
                  boxShadow: `0 0 12px color-mix(in srgb, ${a.accent} 40%, transparent)`,
                }}
              >
                <span
                  className="w-1 h-1 rounded-full"
                  style={{ background: a.accent, boxShadow: `0 0 6px ${a.accent}` }}
                />
                {a.tag}
              </div>
            </div>
            <div className="p-5">
              <h4
                className="text-[14px] font-bold leading-snug tracking-tight mb-2"
                style={{ color: "var(--text-primary)" }}
              >
                {a.title}
              </h4>
              <p
                className="text-[12px] leading-relaxed mb-4"
                style={{ color: "var(--text-tertiary)" }}
              >
                {a.excerpt}
              </p>
              <MetaRow date={a.date} readTime={a.readTime} />
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

function MetaRow({ date, readTime }: { date: string; readTime: string }) {
  return (
    <div
      className="flex items-center gap-3 text-[10px]"
      style={{ color: "var(--text-tertiary)" }}
    >
      <span className="inline-flex items-center gap-1">
        <MetaIcon Icon={Calendar} /> {date}
      </span>
      <span>·</span>
      <span className="inline-flex items-center gap-1">
        <MetaIcon Icon={Clock} /> {readTime}
      </span>
    </div>
  );
}

function MetaIcon({ Icon }: { Icon: LucideIcon }) {
  return <Icon width={11} height={11} strokeWidth={1.8} />;
}
