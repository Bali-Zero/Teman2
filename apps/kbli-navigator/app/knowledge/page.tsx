import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";

export const metadata: Metadata = {
  title: "KBLI 2025 Knowledge Hub — Bali Zero Insights",
  description:
    "In-depth articles on KBLI 2025 compliance, PT PMA setup, foreign investment rules, and business strategy in Indonesia. Powered by Bali Zero Editorial.",
};

const ARTICLES = [
  {
    slug: "slow-paralysis-kbli-2025",
    title:
      "Slow Paralysis: Why Your PT PMA Won't Crash — It Will Just Stop Moving",
    description:
      "OSS still runs KBLI 2020. Coretax is watching. June 2026 looms. The strategic playbook for the transition period.",
    image:
      "https://balizero.com/static/insights/business/slow-paralysis-kbli-2025.jpg",
    tag: "Must Read",
    tagColor: "#dc2626",
  },
  {
    slug: "kbli-2025-bali-transformation",
    title: "KBLI 2025 and Bali's Business Transformation",
    description:
      "How KBLI 2025 impacts Bali-based businesses — from hospitality and F&B to digital agencies and villa operators.",
    image:
      "https://balizero.com/static/insights/business/kbli-2025-bali-transformation.jpg",
    tag: "Bali Focus",
    tagColor: "#7c3aed",
  },
  {
    slug: "kbli-2025-great-transition",
    title: "The Great Transition: KBLI 2020 → 2025",
    description:
      "Everything that changed. What it means for your NIB, your licenses, and your foreign ownership structure.",
    image:
      "https://balizero.com/static/insights/business/kbli-2025-great-transition.jpg",
    tag: "Essential",
    tagColor: "#0077b6",
  },
  {
    slug: "art-of-strategic-patience",
    title: "The Art of Strategic Patience",
    description:
      "OSS isn't ready. The deadline is June 2026. Every move you make is visible to DJP. Here's how to navigate.",
    image:
      "https://balizero.com/static/insights/business/art-of-strategic-patience.jpg",
    tag: "Strategy",
    tagColor: "#059669",
  },
  {
    slug: "kbli-2025-hospitality-villa-hotel-bali-investment-guide",
    title: "KBLI 2025 Hospitality & Accommodation in Bali",
    description:
      "Villa, hotel, homestay, and management codes. PMA ownership rules and Pondok Wisata licensing explained.",
    image:
      "https://balizero.com/static/insights/business/kbli-2025-hospitality-villa-hotel-bali-investment-guide.jpg",
    tag: "Hospitality",
    tagColor: "#d97706",
  },
  {
    slug: "kbli-2025-it-tech-software-cloud-bali-2026",
    title: "KBLI 2025 IT & Tech in Bali",
    description:
      "Software development, AI, cloud infrastructure, and digital platforms. What foreign tech founders need to know.",
    image:
      "https://balizero.com/static/insights/business/kbli-2025-it-tech-software-cloud-bali-2026.jpg",
    tag: "Tech",
    tagColor: "#7c3aed",
  },
  {
    slug: "kbli-2025-foreign-ownership-pma-guide",
    title: "Foreign Ownership & PT PMA: Complete Guide",
    description:
      "Which codes allow 100% foreign ownership? Which are restricted or closed? The full PMA investment matrix.",
    image:
      "https://balizero.com/static/insights/business/kbli-2025-foreign-ownership-pma-guide.jpg",
    tag: "Foreign Investors",
    tagColor: "#dc2626",
  },
  {
    slug: "kbli-2025-location-restrictions-bali",
    title: "KBLI 2025 Location Restrictions in Bali",
    description:
      "Green zones, zoning laws, and where your business can legally operate in Bali under KBLI 2025.",
    image:
      "https://balizero.com/static/insights/business/kbli-2025-location-restrictions-bali.jpg",
    tag: "Zoning",
    tagColor: "#059669",
  },
  {
    slug: "kbli-2025-regulatory-convergence",
    title: "PP 28/2025 & BKPM 5/2025: Regulatory Convergence",
    description:
      "How two major regulations converge to reshape foreign investment in Indonesia. What changed, what stayed.",
    image:
      "https://balizero.com/static/insights/business/kbli-2025-regulatory-convergence.jpg",
    tag: "Regulation",
    tagColor: "#0077b6",
  },
  {
    slug: "kbli-2025-future-proofing-flexibility",
    title: "Future-Proofing: Choose Flexible Business Codes",
    description:
      "How to pick KBLI codes that give you maximum pivot room without triggering additional licensing requirements.",
    image:
      "https://balizero.com/static/insights/business/kbli-2025-future-proofing-flexibility.jpg",
    tag: "Strategy",
    tagColor: "#059669",
  },
  {
    slug: "starting-a-business-in-indonesia-complete-guide",
    title: "Starting a Business in Indonesia: Complete Guide 2026",
    description:
      "From choosing your entity type to getting your NIB. The full step-by-step for foreign founders.",
    image: "/kbli-navigator/kbli-grid-bg.jpg",
    tag: "Beginner",
    tagColor: "#6b7280",
  },
  {
    slug: "kbli-2025-environmental-permits-amdal",
    title: "KBLI 2025 Environmental Permits: AMDAL & UKL-UPL",
    description:
      "Which KBLI codes trigger environmental impact requirements? The complete guide to AMDAL and SPPL.",
    image: "/kbli-navigator/kbli-grid-bg.jpg",
    tag: "Permits",
    tagColor: "#d97706",
  },
];

const BALIZERO_BASE = "https://balizero.com/business";

export default function KnowledgePage() {
  return (
    <div className="space-y-10">
      {/* Header */}
      <div className="relative -mx-4 overflow-hidden rounded-2xl sm:-mx-6 lg:-mx-8">
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)",
          }}
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(circle at 80% 20%, rgba(124,58,237,0.15) 0%, transparent 50%), radial-gradient(circle at 20% 80%, rgba(220,38,38,0.08) 0%, transparent 50%)",
          }}
        />
        <div className="relative px-6 pb-10 pt-16 text-center sm:px-8 sm:pt-20">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-white/60">
            Bali Zero Editorial
          </div>
          <h1 className="text-3xl font-black tracking-tight text-white sm:text-4xl lg:text-5xl">
            KBLI 2025 Knowledge Hub
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base text-white/60 sm:text-lg">
            In-depth analysis, compliance guides, and strategic insights on
            Indonesia&apos;s new business classification system.
          </p>
        </div>
      </div>

      {/* Featured article */}
      <div>
        <div className="mb-4 flex items-center gap-3">
          <span className="text-xs font-bold uppercase tracking-wider text-[var(--kbli-accent)]">
            Featured
          </span>
          <div className="h-px flex-1 bg-[var(--border)]" />
        </div>
        <Link
          href={`${BALIZERO_BASE}/${ARTICLES[0].slug}`}
          target="_blank"
          rel="noopener noreferrer"
          className="group relative flex overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--kbli-bg-card)] transition-all hover:border-[var(--kbli-accent)]/30"
        >
          <div className="relative hidden h-56 w-72 flex-shrink-0 sm:block">
            <Image
              src={ARTICLES[0].image}
              alt={ARTICLES[0].title}
              fill
              className="object-cover transition-transform duration-500 group-hover:scale-105"
              unoptimized
            />
          </div>
          <div className="flex flex-col justify-center p-6 sm:p-8">
            <span
              className="mb-3 inline-block self-start rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider"
              style={{
                background: `${ARTICLES[0].tagColor}20`,
                border: `1px solid ${ARTICLES[0].tagColor}40`,
                color: ARTICLES[0].tagColor,
              }}
            >
              {ARTICLES[0].tag}
            </span>
            <h2 className="mb-2 text-xl font-bold leading-snug text-[var(--foreground)] transition-colors group-hover:text-[var(--kbli-accent)] sm:text-2xl">
              {ARTICLES[0].title}
            </h2>
            <p className="text-sm leading-relaxed text-[var(--foreground-muted)]">
              {ARTICLES[0].description}
            </p>
            <div className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-[var(--kbli-accent)]">
              Read on Bali Zero
              <svg
                className="h-4 w-4 transition-transform group-hover:translate-x-1"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 8l4 4m0 0l-4 4m4-4H3"
                />
              </svg>
            </div>
          </div>
        </Link>
      </div>

      {/* Articles grid */}
      <div>
        <div className="mb-4 flex items-center gap-3">
          <span className="text-xs font-bold uppercase tracking-wider text-[var(--foreground-muted)]">
            All Articles
          </span>
          <div className="h-px flex-1 bg-[var(--border)]" />
          <span className="text-xs text-[var(--foreground-muted)]">
            {ARTICLES.length - 1} guides
          </span>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {ARTICLES.slice(1).map((article) => (
            <Link
              key={article.slug}
              href={`${BALIZERO_BASE}/${article.slug}`}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--kbli-bg-card)] transition-all hover:border-[var(--kbli-accent)]/25 hover:bg-[var(--kbli-bg-card-hover)]"
            >
              <div className="relative h-56 w-full overflow-hidden">
                <Image
                  src={article.image}
                  alt={article.title}
                  fill
                  className="object-cover transition-transform duration-500 group-hover:scale-105"
                  unoptimized
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
                <span
                  className="absolute bottom-3 left-3 rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider backdrop-blur-sm"
                  style={{
                    background: `${article.tagColor}25`,
                    border: `1px solid ${article.tagColor}50`,
                    color: article.tagColor,
                  }}
                >
                  {article.tag}
                </span>
              </div>
              <div className="flex flex-1 flex-col p-4">
                <h3 className="mb-1.5 text-sm font-semibold leading-snug text-[var(--foreground)] transition-colors group-hover:text-[var(--kbli-accent)]">
                  {article.title}
                </h3>
                <p className="flex-1 text-xs leading-relaxed text-[var(--foreground-muted)]">
                  {article.description}
                </p>
                <div className="mt-3 flex items-center gap-1 text-xs font-medium text-[var(--kbli-accent)] opacity-0 transition-opacity group-hover:opacity-100">
                  Read article
                  <svg
                    className="h-3 w-3"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M17 8l4 4m0 0l-4 4m4-4H3"
                    />
                  </svg>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* CTA to blog */}
      <div className="rounded-xl border border-[var(--kbli-accent)]/15 bg-[var(--kbli-accent)]/5 p-6 text-center">
        <p className="mb-3 text-sm text-[var(--foreground-muted)]">
          More in-depth analysis on Indonesia&apos;s regulatory landscape
        </p>
        <Link
          href="https://balizero.com/business"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-lg border border-[var(--kbli-accent)]/30 bg-[var(--kbli-accent)]/10 px-5 py-2.5 text-sm font-semibold text-[var(--kbli-accent)] transition-all hover:bg-[var(--kbli-accent)]/20"
        >
          All Business Articles on Bali Zero
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
        </Link>
      </div>
    </div>
  );
}
