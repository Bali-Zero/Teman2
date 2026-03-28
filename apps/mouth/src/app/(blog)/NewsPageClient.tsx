"use client";

import * as React from "react";
import { Suspense, lazy } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  ArrowRight,
  Sparkles,
  Play,
  ChevronRight,
  Search,
  Building2,
  Activity,
  Plane,
  Calculator,
} from "lucide-react";
import type { ArticleListItem } from "@/lib/blog/types";
import { HomepageSEOSchemas } from "@/components/seo/HomepageFAQ";
import { useTranslation } from "@/i18n";
import homepageLayout from "@/content/homepage-layout.json";

// Lazy load non-critical sections
const KBLINavigatorSection = lazy(
  () => import("./components/KBLINavigatorSection"),
);

// Skeleton for lazy-loaded sections
const SectionSkeleton = () => (
  <div className="animate-pulse bg-[rgba(10,22,40,0.6)] backdrop-blur-md border border-[rgba(255,255,255,0.05)] rounded-2xl h-[400px] lg:h-[500px]" />
);

// App domain for internal routes
const APP_DOMAIN =
  process.env.NEXT_PUBLIC_APP_DOMAIN || "https://kita.balizero.com";

interface NewsPageClientProps {
  articles: ArticleListItem[];
}

/**
 * News Page Client Component - "The Chronicle"
 * McKinsey-inspired asymmetric editorial layout with 5-article collage
 */
export default function NewsPageClient({
  articles: serverArticles,
}: NewsPageClientProps) {
  const { t } = useTranslation();

  // Fallback a MOCK_ARTICLES se il server non fornisce articoli
  const articles = serverArticles?.length > 0 ? serverArticles : MOCK_ARTICLES;

  // Get articles for hero collage from homepage-layout.json config
  const mainNews1 = articles.find((a) => a.slug === homepageLayout.hero_main);
  const mainNews2 = articles.find((a) => a.slug === homepageLayout.hero_2);
  const mainNews3 = articles.find((a) => a.slug === homepageLayout.hero_3);
  const mainNews4 = articles.find((a) => a.slug === homepageLayout.hero_4);
  const mainNews5 = articles.find((a) => a.slug === homepageLayout.hero_5);

  // Get insight articles from layout config
  const kbliInsight1 = articles.find(
    (a) => a.slug === homepageLayout.insight_1,
  );
  const kbliInsight2 = articles.find(
    (a) => a.slug === homepageLayout.insight_2,
  );
  const kbliInsight3 = articles.find(
    (a) => a.slug === homepageLayout.insight_3,
  );
  const kbliInsights = [kbliInsight1, kbliInsight2, kbliInsight3].filter(
    Boolean,
  ) as ArticleListItem[];

  // Get IDs of main news articles to exclude them from other sections
  const mainNewsIds = new Set(
    [
      mainNews1?.id,
      mainNews2?.id,
      mainNews3?.id,
      mainNews4?.id,
      mainNews5?.id,
    ].filter(Boolean),
  );

  // Other articles for sections below
  const otherArticles = articles.filter((a) => !mainNewsIds.has(a.id));

  return (
    <>
      <HomepageSEOSchemas />

      <div className="min-h-screen bg-[#051C2C]">
        {/* McKinsey-Style Asymmetric Hero Collage */}
        <section className="border-b border-white/10">
          <div className="max-w-[1400px] mx-auto px-4 lg:px-6">
            {/* Asymmetric Grid Layout - Enlarged for strong first impression */}
            <div className="grid grid-cols-12 gap-3 min-h-[850px] lg:min-h-[950px]">
              {/* LEFT COLUMN: Headline + News 2 + News 5 */}
              <div className="col-span-12 lg:col-span-4 flex flex-col gap-3">
                {/* Headline Area with Indonesian Flag Drape */}
                <div className="py-8 lg:py-12 relative overflow-hidden">
                  {/* Indonesian Flag Drape - Actual Image */}
                  <div className="absolute inset-0 pointer-events-none overflow-hidden">
                    <Image
                      src="/assets/static/indonesian-flag-drape.jpg"
                      alt="Indonesian flag background"
                      fill
                      className="object-cover opacity-30"
                      style={{
                        mixBlendMode: "screen",
                        transform: "scale(1.3) rotate(-5deg)",
                        transformOrigin: "center center",
                      }}
                      priority
                      fetchPriority="high"
                      sizes="(max-width: 1024px) 100vw, 40vw"
                    />
                  </div>
                  <div className="relative z-10">
                    <h1 className="font-serif text-4xl lg:text-5xl xl:text-6xl text-white leading-[1.1] mb-4">
                      {t("home.hero.title")}{" "}
                      <span className="text-red-500">
                        {t("home.hero.titleAccent")}
                      </span>{" "}
                      {t("home.hero.titleSuffix")}
                    </h1>
                    <p className="text-lg text-white/70">
                      {t("home.hero.subtitle")}{" "}
                      <span className="text-[#2251ff]">
                        {t("home.hero.subtitleAccent")}
                      </span>
                    </p>
                  </div>
                </div>

                {/* Main News 2 - Taller - NO MONEY NO BALI */}
                {mainNews2 && (
                  <CollageCard article={mainNews2} className="flex-[1.4]" />
                )}

                {/* Main News 5 - Under News 2, shorter than News 4 */}
                {mainNews5 && (
                  <CollageCard article={mainNews5} className="flex-[1.1]" />
                )}
              </div>

              {/* MIDDLE COLUMN: News 3 (offset top) + News 4 (extends down) */}
              <div className="col-span-12 lg:col-span-4 flex flex-col gap-3 lg:pt-28">
                {/* Main News 3 - Gemini 3, offset from top */}
                {mainNews3 && (
                  <CollageCard article={mainNews3} className="flex-[1]" />
                )}

                {/* Main News 4 - Coretax, extends down past newsletter */}
                {mainNews4 && (
                  <CollageCard article={mainNews4} className="flex-[1.6]" />
                )}
              </div>

              {/* RIGHT COLUMN: News 1 (large) + Newsletter */}
              <div className="col-span-12 lg:col-span-4 flex flex-col gap-3">
                {/* Main News 1 - Large, Global Citizenship - extends to headline height */}
                {mainNews1 && (
                  <CollageCard
                    article={mainNews1}
                    className="flex-[2.4]"
                    showCTA
                  />
                )}

                {/* Newsletter Box */}
                <div className="bg-[rgba(10,37,64,0.6)] backdrop-blur-md border border-[rgba(255,255,255,0.05)] p-6 flex-[0.6] rounded-xl shadow-[0_8px_32px_rgba(0,0,0,0.3)]">
                  <p className="text-white font-medium mb-2">
                    {t("home.newsletter.title")}
                  </p>
                  <p className="text-white/60 text-sm mb-4">
                    {t("home.newsletter.subtitle")}
                  </p>
                  <form className="flex gap-2">
                    <input
                      type="email"
                      placeholder={t("home.newsletter.placeholder")}
                      aria-label="Email address"
                      className="flex-1 px-4 py-2.5 rounded bg-white/10 border border-white/20 text-white placeholder-white/50 focus:outline-none focus:border-[#2251ff] transition-colors text-sm"
                    />
                    <button
                      type="submit"
                      className="px-4 py-2.5 rounded bg-[#2251ff] text-white hover:bg-[#1a3fcc] transition-colors"
                    >
                      <ArrowRight className="w-4 h-4" />
                    </button>
                  </form>
                  <div className="flex items-center gap-3 mt-4 pt-4 border-t border-white/10">
                    <span className="text-white/40 text-xs">
                      {t("home.newsletter.orContinueWith")}
                    </span>
                    <div className="flex gap-2">
                      <button className="px-3 py-1.5 rounded bg-white/10 text-white/70 text-xs hover:bg-white/20 transition-colors">
                        Google
                      </button>
                      <button className="px-3 py-1.5 rounded bg-white/10 text-white/70 text-xs hover:bg-white/20 transition-colors">
                        LinkedIn
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Topics Grid */}
        <section className="border-b border-white/10">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-10">
            <div className="flex flex-wrap items-center justify-center gap-3">
              {TOPICS.map((topic) => (
                <Link
                  key={topic.id}
                  href={`/${topic.slug}`}
                  className="px-5 py-2.5 rounded-full border border-white/20 text-white/80 text-sm font-medium hover:bg-white/10 hover:border-white/40 transition-all"
                >
                  {topic.name}
                </Link>
              ))}
            </div>
          </div>
        </section>

        {/* Featured Tool - KBLI Navigator - Lazy Loaded */}
        <Suspense fallback={<SectionSkeleton />}>
          <KBLINavigatorSection />
        </Suspense>

        {/* Latest Insights Grid */}
        <section className="border-b border-white/10">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
            <div className="flex items-center justify-between mb-10">
              <h2 className="text-2xl font-serif text-white">
                {t("home.insights.latestTitle")}
              </h2>
              <Link
                href="/immigration"
                className="flex items-center gap-2 text-[#2251ff] hover:text-[#4d73ff] text-sm font-medium transition-colors"
              >
                View all
                <ChevronRight className="w-4 h-4" />
              </Link>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {kbliInsights.map((article, index) => (
                <div
                  key={article.id}
                  className="animate-in fade-in slide-in-from-bottom-4 duration-500"
                  style={{ animationDelay: `${index * 100}ms` }}
                >
                  <Link href="/kbli">
                    <article className="group">
                      <div className="aspect-[16/10] relative overflow-hidden rounded-lg mb-5 bg-[rgba(10,22,40,0.6)] backdrop-blur-sm border border-[rgba(255,255,255,0.03)]">
                        {article.coverImage &&
                        typeof article.coverImage === "string" ? (
                          <Image
                            src={article.coverImage}
                            alt={article.title || ""}
                            fill
                            className="object-cover group-hover:scale-[1.05] transition-transform duration-700"
                            style={{
                              objectPosition: "center 25%", // Show only top portion with graphs
                              transform: "scale(1.8)", // Zoom in to crop out text at bottom
                              transformOrigin: "center 25%",
                            }}
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-white/20">
                            <Building2 className="w-12 h-12" />
                          </div>
                        )}
                      </div>

                      <span className="text-[#2251ff] text-xs font-semibold uppercase tracking-wider mb-2 block">
                        {formatCategory(article.category, t)}
                      </span>

                      <h3 className="font-serif text-xl text-white mb-3 leading-snug group-hover:text-[#2251ff] transition-colors line-clamp-2">
                        {article.title}
                      </h3>

                      <p className="text-white/60 text-sm leading-relaxed mb-4 line-clamp-2">
                        {article.excerpt}
                      </p>

                      <div className="flex items-center gap-3 text-white/40 text-sm">
                        <span>
                          {article.readingTime} {t("news.minuteRead")}
                        </span>
                        <span>•</span>
                        <span>{formatViewCount(article.viewCount)} views</span>
                      </div>
                    </article>
                  </Link>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Podcast/Video Section */}
        <section className="border-b border-white/10">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
            <div className="flex items-center justify-between mb-10">
              <h2 className="text-2xl font-serif text-white">Watch & Listen</h2>
              <Link
                href="/kbli"
                className="flex items-center gap-2 text-[#2251ff] hover:text-[#4d73ff] text-sm font-medium transition-colors"
              >
                Explore Navigator
                <ChevronRight className="w-4 h-4" />
              </Link>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
              {/* Podcast Cover */}
              <Link href="/kbli" className="group">
                <div className="relative aspect-square rounded-xl overflow-hidden">
                  <Image
                    src="/images/podcast-kbli-2025.png"
                    alt="KBLI 2025 Deep Dive Podcast"
                    fill
                    className="object-cover group-hover:scale-105 transition-transform duration-700"
                  />
                </div>
              </Link>

              {/* Podcast Details */}
              <div className="podcast-content">
                <span className="inline-block px-3 py-1 rounded-md text-xs font-semibold uppercase bg-[#2251ff]/10 text-[#2251ff] mb-4">
                  Podcast Series
                </span>

                <h3 className="font-serif text-3xl text-white mb-3 leading-tight">
                  KBLI 2025 Deep Dive
                </h3>

                <p className="text-lg text-white/70 mb-6 leading-relaxed">
                  Expert analysis of Indonesia's new business classification
                  system. Everything foreign investors need to know about the
                  1,562 codes, risk levels, PMA restrictions, and practical
                  implementation strategies.
                </p>

                <div className="space-y-3 mb-6 text-sm text-white/60">
                  <div className="flex items-center gap-2">
                    <svg
                      className="w-5 h-5 text-[#2251ff]"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" />
                    </svg>
                    <span>28 minutes of expert insights</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <svg
                      className="w-5 h-5 text-[#2251ff]"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z" />
                    </svg>
                    <span>
                      Visas consultants, tax specialists, business
                      advisors
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <svg
                      className="w-5 h-5 text-[#2251ff]"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <span>Real-world case studies and practical guidance</span>
                  </div>
                </div>

                <div className="flex gap-4">
                  <Link
                    href="/kbli"
                    className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[#2251ff] text-white font-semibold hover:bg-[#1a3fcc] transition-colors"
                  >
                    <Play className="w-5 h-5" fill="currentColor" />
                    Explore Navigator
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Services CTA */}
        <section>
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-20">
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
              <div className="lg:col-span-1">
                <h2 className="font-serif text-3xl text-white mb-4">
                  Our Services
                </h2>
                <p className="text-white/60 mb-6">
                  Expert assistance for your Indonesia journey
                </p>
                <Link
                  href="/services"
                  className="inline-flex items-center gap-2 text-[#2251ff] hover:text-[#4d73ff] font-medium transition-colors"
                >
                  View all services
                  <ChevronRight className="w-4 h-4" />
                </Link>
              </div>

              <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-6">
                {SERVICES.map((service) => (
                  <Link key={service.slug} href={`/services/${service.slug}`}>
                    <div className="group p-6 rounded-xl border border-[rgba(255,255,255,0.1)] bg-[rgba(10,37,64,0.3)] backdrop-blur-md hover:border-[#2251ff]/50 hover:bg-[rgba(10,37,64,0.6)] hover:-translate-y-1 transition-all h-full shadow-[0_4px_24px_rgba(0,0,0,0.2)]">
                      <div className="w-12 h-12 rounded-lg bg-[#2251ff]/10 flex items-center justify-center mb-4 group-hover:bg-[#2251ff]/20 transition-colors">
                        <service.icon className="w-6 h-6 text-[#2251ff]" />
                      </div>
                      <h3 className="font-serif text-lg text-white mb-2 group-hover:text-[#2251ff] transition-colors">
                        {service.name}
                      </h3>
                      <p className="text-white/60 text-sm">
                        {service.description}
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}

/**
 * Collage Card Component - McKinsey asymmetric style
 */
function CollageCard({
  article,
  className = "",
  showCTA = false,
  imagePosition = "center",
}: {
  article: ArticleListItem;
  className?: string;
  showCTA?: boolean;
  imagePosition?: "center" | "top" | "bottom";
}) {
  const { t } = useTranslation();
  const positionClass =
    imagePosition === "top"
      ? "object-top"
      : imagePosition === "bottom"
        ? "object-bottom"
        : "object-center";
  return (
    <Link
      href={`/${article.category}/${article.slug}`}
      className={`block group relative overflow-hidden ${className}`}
    >
      <article className="relative w-full h-full min-h-[220px]">
        <Image
          src={article.coverImage}
          alt={article.title}
          fill
          className={`object-cover ${positionClass} group-hover:scale-105 transition-transform duration-700`}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent" />

        <div className="absolute inset-0 p-5 lg:p-6 flex flex-col justify-end">
          <span className="text-[#2251ff] text-[10px] font-bold uppercase tracking-wider mb-2">
            {formatCategory(article.category, t)}
          </span>
          <h3 className="font-serif text-white leading-tight group-hover:text-[#2251ff] transition-colors text-base lg:text-lg">
            {article.title}
            <ChevronRight className="inline-block w-4 h-4 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
          </h3>

          {showCTA && (
            <div className="mt-4">
              <span className="inline-flex items-center gap-2 px-4 py-2 bg-white text-[#051C2C] text-sm font-medium rounded hover:bg-white/90 transition-colors">
                Read the case study
                <ArrowRight className="w-4 h-4" />
              </span>
            </div>
          )}
        </div>

        {article.aiGenerated && (
          <div className="absolute top-4 left-4 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#2251ff] text-white text-[10px] font-medium">
            <Sparkles className="w-3 h-3" />
            AI
          </div>
        )}
      </article>
    </Link>
  );
}

function formatCategory(category: string, t?: (key: string) => string): string {
  if (t) {
    const keyMap: Record<string, string> = {
      immigration: "home.categories.immigration",
      business: "home.categories.business",
      "taxes": "home.categories.taxLegal",
      property: "home.categories.property",
      lifestyle: "home.categories.lifestyle",
    };
    if (keyMap[category]) {
      return t(keyMap[category]);
    }
  }
  const categoryMap: Record<string, string> = {
    visas: "Visas",
    business: "Business",
    "taxes": "Taxes",
    property: "Property",
    living: "Living",
    trends: "Tech & AI",
  };
  return categoryMap[category] || category.replace("-", " & ");
}

const TOPICS = [
  { id: "ai-tech", name: "AI & Tech", slug: "tech" },
  { id: "gci", name: "GCI", slug: "visas" },
  { id: "golden-visa", name: "Golden Visa", slug: "visas" },
  { id: "pt-pma", name: "PT PMA", slug: "business" },
  { id: "tax-2026", name: "Tax 2026", slug: "taxes" },
  { id: "kitas", name: "KITAS", slug: "visas" },
  { id: "digital-nomad", name: "Digital Nomad", slug: "living" },
  { id: "property", name: "Property", slug: "property" },
  { id: "work-permits", name: "Work Permits", slug: "visas" },
];

function formatViewCount(count: number): string {
  return new Intl.NumberFormat("en-US").format(count);
}

const SERVICES = [
  {
    name: "Visa & Visas",
    slug: "visa",
    description: "KITAS, KITAP, Golden Visa, and all permit types",
    icon: Plane,
  },
  {
    name: "Company Setup",
    slug: "company",
    description: "PT PMA, PT Local, and business licensing",
    icon: Building2,
  },
  {
    name: "Tax & Compliance",
    slug: "tax",
    description: "Personal and corporate tax services",
    icon: Calculator,
  },
];

// Fallback articles se il server non ne fornisce (mantenuto per sicurezza)
const MOCK_ARTICLES: ArticleListItem[] = [
  // === CONSTITUTIONAL CLASH - MAIN FEATURE (Jan 2026) ===
  {
    id: "200",
    slug: "constitutional-clash-bank-statements",
    title:
      "The Constitutional Clash: Can Bali Legally Demand Your Bank Statements?",
    excerpt:
      "Governor Koster wants 'quality tourists' to prove their wealth. But Jakarta might have the final say.",
    coverImage: "/static/news/constitutional-clash-koster.jpg",
    category: "visas",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-19"),
    readingTime: 7,
    viewCount: 12580,
    featured: true,
    trending: true,
    aiGenerated: false,
  },
  // === OTA TAX CRACKDOWN - SECOND FEATURE (Jan 2026) ===
  {
    id: "201",
    slug: "ota-data-crackdown-bali-2026",
    title: "Villa Owners Tremble: OTAs Will Share Tax Data Next March",
    excerpt:
      "Governor Koster demands Airbnb share tax data. 39,000+ unlicensed listings could be delisted by March 2026.",
    coverImage: "/static/news/villa_pererenan.jpg",
    category: "business",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-18"),
    readingTime: 9,
    viewCount: 15420,
    featured: true,
    trending: true,
    aiGenerated: false,
  },
  // === KBLI 2025 ARTICLES (Feb 2026) ===
  {
    id: "300",
    slug: "kbli-2025-bali-transformation",
    title:
      "KBLI 2025 and Bali's Business Transformation: Strategic Compliance for Local Operators",
    excerpt:
      "Bali's economy runs on tourism, hospitality, and digital services. KBLI 2025 reshuffles the classification deck. Here's what Bali businesses need to do before June 2026.",
    coverImage: "/static/insights/business/kbli-bali-transformation.jpg",
    category: "business",
    author: {
      id: "zantara-ai",
      name: "Zantara AI",
      avatar: "/static/zantara-avatar.png",
      role: "AI Business Advisor",
      isAI: true,
    },
    publishedAt: new Date("2026-02-12"),
    readingTime: 14,
    viewCount: 1240,
    featured: false,
    trending: true,
    aiGenerated: true,
  },
  {
    id: "301",
    slug: "art-of-strategic-patience",
    title:
      "The Art of Strategic Patience: Navigating Indonesia's KBLI 2025 Transition Without Getting Burned",
    excerpt:
      "The OSS system isn't ready. The deadline is June 2026. And every move you make is now visible to the tax authority. Here's the strategic playbook for the transition period.",
    coverImage: "/static/insights/business/strategic-patience-editorial.jpg",
    category: "business",
    author: {
      id: "zantara-ai",
      name: "Zantara AI",
      avatar: "/static/zantara-avatar.png",
      role: "AI Business Advisor",
      isAI: true,
    },
    publishedAt: new Date("2026-02-12"),
    readingTime: 13,
    viewCount: 980,
    featured: false,
    trending: true,
    aiGenerated: true,
  },
  // === KBLI Navigator Articles (Feb 2025) - Homepage Featured ===
  {
    id: "kbli-insight-1",
    slug: "capital-evolution-bkpm-5-2025",
    title: "Capital Evolution: How BKPM 5/2025 Saved Property Investors",
    excerpt:
      "The 10B IDR rule is no longer a barrier. Learn how your villa's physical value now secures your 100% ownership.",
    coverImage: "/static/insights/property/unnamed-4.jpg",
    category: "property",
    author: {
      id: "zantara-ai",
      name: "Zantara AI",
      avatar: "/static/zantara-lotus.png",
      role: "AI Business Advisor",
      isAI: true,
    },
    publishedAt: new Date("2026-02-23"),
    readingTime: 8,
    viewCount: 12450,
    featured: true,
    trending: true,
    aiGenerated: true,
  },
  {
    id: "kbli-insight-2",
    slug: "ota-delisting-bali-2026",
    title: "Digital Darwinism: The March 31 OTA Cut-off",
    excerpt:
      "Airbnb and Booking.com are syncing with the NIB database. Wrong code? Your listing goes dark with no warning.",
    coverImage: "/static/insights/property/unnamed-3.jpg",
    category: "property",
    author: {
      id: "zantara-ai",
      name: "Zantara AI",
      avatar: "/static/zantara-lotus.png",
      role: "AI Research",
      isAI: true,
    },
    publishedAt: new Date("2026-02-24"),
    readingTime: 10,
    viewCount: 18920,
    featured: true,
    trending: true,
    aiGenerated: true,
  },
  {
    id: "kbli-insight-3",
    slug: "glamping-trap-kbli-55209",
    title: "The Glamping Trap: Why 55209 is a Compliance Minefield",
    excerpt:
      "KBLI 55209 strictly prohibits daily housekeeping. Using it for luxury resorts is an invitation for NIB revocation.",
    coverImage: "/static/insights/property/unnamed-5.jpg",
    category: "property",
    author: {
      id: "zantara-ai",
      name: "Zantara AI",
      avatar: "/static/zantara-lotus.png",
      role: "AI Business Advisor",
      isAI: true,
    },
    publishedAt: new Date("2026-02-25"),
    readingTime: 7,
    viewCount: 9420,
    featured: true,
    trending: true,
    aiGenerated: true,
  },
  // === PERFECT STORM SERIES (Jan 2026) ===
  {
    id: "100",
    slug: "perfect-storm-bali-2026",
    title: "Bali's Perfect Storm: Why 2026 Demands a New Playbook",
    excerpt:
      "Waste crisis, dengue surge, maritime blockade, tax shock, property crackdown — all hitting at once. Here's how to navigate.",
    coverImage: "/static/news/perfect-storm-bali.jpg",
    category: "living",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-13"),
    readingTime: 5,
    viewCount: 8420,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: "101",
    slug: "suwung-landfill-crisis",
    title:
      "Suwung Landfill Closure: The Waste Crisis Hitting Bali's Tourist Zones",
    excerpt:
      "Bali's main landfill is closing. No clear Plan B. If you're in hospitality or events, this affects you.",
    coverImage: "/static/news/suwung-landfill.jpg",
    category: "living",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-13"),
    readingTime: 4,
    viewCount: 5230,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: "102",
    slug: "dengue-alert-2026",
    title: "Dengue Alert 2026: 636 Cases and Rising — What Expats Need to Know",
    excerpt:
      "Dengue cases are up 636 in Bali this year. Know the symptoms, get insurance, and protect your family.",
    coverImage: "/static/news/dengue-alert.jpg",
    category: "living",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-13"),
    readingTime: 4,
    viewCount: 7150,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: "103",
    slug: "maritime-chaos-komodo",
    title:
      "Maritime Chaos: Komodo Blockade Strands Thousands — Plan Your Buffer",
    excerpt:
      "Fishermen blocked Labuan Bajo port for 3 days. If you're planning East Indonesia travel, build in buffer days.",
    coverImage: "/static/news/maritime-chaos.jpg",
    category: "living",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-13"),
    readingTime: 3,
    viewCount: 4320,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: "104",
    slug: "pajak-hiburan-tax-shock",
    title:
      "The 40-75% Tax Shock: What Pajak Hiburan Means for Beach Clubs and Nightlife",
    excerpt:
      "Indonesia's new entertainment tax hits 40-75%. Beach clubs, bars, and karaoke venues are scrambling.",
    coverImage: "/static/news/pajak-hiburan.jpg",
    category: "taxes",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-13"),
    readingTime: 5,
    viewCount: 6890,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: "105",
    slug: "property-green-zone-alert",
    title:
      "Property Alert: Green Zone Crackdown and the End of Easy Villa Permits",
    excerpt:
      "Building permits frozen in green zones. If you're eyeing land in Canggu or Ubud outskirts, read this first.",
    coverImage: "/static/news/property-green-zone.jpg",
    category: "property",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-13"),
    readingTime: 5,
    viewCount: 9120,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  // === END PERFECT STORM SERIES ===
  {
    id: "19",
    slug: "indonesia-zero-tax-foreign-income-2026",
    title:
      "Indonesia's 0% Tax on Foreign Income: The Expat Advantage Most Don't Know",
    excerpt:
      "Living in Indonesia while earning abroad? Under PMK 18/2021, your foreign income may be taxed at 0%.",
    coverImage: "/static/news/indonesia-zero-tax-expat.jpg",
    category: "taxes",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-04"),
    readingTime: 6,
    viewCount: 15320,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: "1",
    slug: "global-citizenship-indonesia",
    title: "Global Citizenship of Indonesia: The Long-Awaited Embrace",
    excerpt:
      'After decades of "choose us or them," Indonesia finally opens its arms.',
    coverImage: "/static/blog/global-citizenship.jpg",
    category: "visas",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-01"),
    readingTime: 8,
    viewCount: 24150,
    featured: true,
    trending: true,
    aiGenerated: false,
  },
  {
    id: "16",
    slug: "coretax-npwp-problems-2026",
    title:
      "Coretax Chaos: Indonesia's New Tax System Is Breaking NPWP Registrations",
    excerpt:
      "Indonesia's new Coretax system launched January 1st — and it's causing headaches.",
    coverImage: "/static/news/coretax-kpp-queue.jpg",
    category: "taxes",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-03"),
    readingTime: 6,
    viewCount: 12450,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: "11",
    slug: "claude-opus-revolutionizes-ai",
    title: "Claude 4.5 Opus: How Anthropic Just Redefined What AI Can Do",
    excerpt:
      "Claude 4.5 Opus sets a new benchmark for AI. Extended thinking, deeper reasoning.",
    coverImage: "/static/insights/tech/claude-opus-revolutionizes-ai.jpg",
    category: "trends",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-02"),
    readingTime: 6,
    viewCount: 18420,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: "18",
    slug: "gemini-3-native-intelligence",
    title: "Gemini 3: Google Redefines AI with Native Intelligence",
    excerpt:
      "Gemini 3 doesn't answer: it anticipates. It doesn't assist: it acts. The first AI that thinks like a human.",
    coverImage: "/static/news/gemini-3-ai.jpg",
    category: "trends",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-04"),
    readingTime: 5,
    viewCount: 28540,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: "15",
    slug: "bali-tourist-savings-check-2026",
    title: "NO MONEY, NO BALI: Tourist Bank Account Checks Coming in 2026",
    excerpt:
      "Governor Koster announces financial screening for tourists entering Bali.",
    coverImage: "/static/news/bank-screening-clean.jpg",
    category: "visas",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-02"),
    readingTime: 8,
    viewCount: 45230,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: "17",
    slug: "immigration-lounge-bali-malls-2026",
    title: "Visas Lounges Coming to Bali Malls in 2026",
    excerpt:
      "No more queuing at Kantor Imigrasi? Bali plans to open immigration service lounges in shopping malls.",
    coverImage: "/static/news/immigration-lounge-mall.jpg",
    category: "visas",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-03"),
    readingTime: 5,
    viewCount: 8920,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: "2",
    slug: "bali-rules-respect",
    title: "Bali Is Not a Playground: The Rules You Must Respect",
    excerpt: "Bali welcomes visitors. What it doesn't welcome is arrogance.",
    coverImage: "/static/blog/bali-rules-behavior.jpg",
    category: "living",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-01"),
    readingTime: 5,
    viewCount: 31200,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: "3",
    slug: "kerobokan-traffic-trial",
    title: "Bali Takes Bold Action: The Kerobokan Kelod Traffic Trial",
    excerpt:
      "With 2.8M tourists arriving for Christmas and New Year, Bali experiments with radical traffic changes.",
    coverImage: "/static/blog/kerobokan-traffic.jpg",
    category: "living",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-01"),
    readingTime: 4,
    viewCount: 8920,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: "10",
    slug: "golden-visa-2026-updates",
    title: "Golden Visa 2026: One Year Later – What We've Learned",
    excerpt:
      "After 12 months of Indonesia's Golden Visa program, we analyze approval rates.",
    coverImage: "/static/blog/golden-visa.jpg",
    category: "visas",
    author: {
      id: "zantara-ai",
      name: "Zantara AI",
      avatar: "/static/zantara-lotus.png",
      role: "AI Research",
      isAI: true,
    },
    publishedAt: new Date("2025-12-30"),
    readingTime: 12,
    viewCount: 15420,
    featured: false,
    trending: false,
    aiGenerated: true,
  },
  {
    id: "9",
    slug: "tax-deadlines-2026",
    title: "Tax Deadlines 2026: What Every Expat Needs to Know",
    excerpt: "Key dates for personal and corporate tax filings.",
    coverImage: "/static/blog/tax-calendar.jpg",
    category: "taxes",
    author: {
      id: "zantara-ai",
      name: "Zantara AI",
      avatar: "/static/zantara-lotus.png",
      role: "AI Research",
      isAI: true,
    },
    publishedAt: new Date("2025-12-28"),
    readingTime: 8,
    viewCount: 6234,
    featured: false,
    trending: false,
    aiGenerated: true,
  },
  {
    id: "4",
    slug: "airbnb-bali-ban-truth",
    title: "Is Airbnb Really Banned in Bali? Here's What's Actually Happening",
    excerpt: "Panic spread online: 'Bali banned Airbnb!' But that's not true.",
    coverImage: "/static/blog/airbnb-bali-rules.jpg",
    category: "property",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-01"),
    readingTime: 5,
    viewCount: 18750,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: "6",
    slug: "north-bali-airport-2026",
    title: "North Bali Airport 2026: Construction Finally Begins?",
    excerpt:
      "After years of delays, ground-breaking ceremonies scheduled for Q2 2026.",
    coverImage: "/static/blog/north-bali.jpg",
    category: "property",
    author: {
      id: "2",
      name: "Property Team",
      avatar: "/static/team/property.jpg",
      role: "Property Specialist",
      isAI: false,
    },
    publishedAt: new Date("2025-12-22"),
    readingTime: 10,
    viewCount: 4521,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: "7",
    slug: "digital-nomad-visa-2026",
    title: "Digital Nomad Visa 2026: Indonesia Finally Gets Serious",
    excerpt: "The long-awaited Digital Nomad Visa is here.",
    coverImage: "/static/blog/nomad-comparison.jpg",
    category: "living",
    author: {
      id: "zantara-ai",
      name: "Zantara AI",
      avatar: "/static/zantara-lotus.png",
      role: "AI Research",
      isAI: true,
    },
    publishedAt: new Date("2025-12-18"),
    readingTime: 14,
    viewCount: 7845,
    featured: false,
    trending: false,
    aiGenerated: true,
  },
  {
    id: "8",
    slug: "kitas-application-2026",
    title: "KITAS Application 2026: New Digital System Finally Works",
    excerpt: "The real story of getting your stay permit.",
    coverImage: "/static/blog/kitas-guide.jpg",
    category: "visas",
    author: {
      id: "1",
      name: "Visas Team",
      avatar: "/static/team/immigration.jpg",
      role: "Visas Specialist",
      isAI: false,
    },
    publishedAt: new Date("2025-12-20"),
    readingTime: 18,
    viewCount: 12340,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: "12",
    slug: "ai-agents-autonomous-era",
    title: "The Rise of AI Agents: When Software Does Your Job (For Real)",
    excerpt:
      "AI agents now book travel, manage emails, file permits, and run businesses.",
    coverImage: "/static/insights/tech/ai-agents-autonomous-era.jpg",
    category: "trends",
    author: {
      id: "zantara-ai",
      name: "Zantara AI",
      avatar: "/static/zantara-lotus.png",
      role: "AI Business Advisor",
      isAI: true,
    },
    publishedAt: new Date("2026-01-02"),
    readingTime: 6,
    viewCount: 3890,
    featured: false,
    trending: false,
    aiGenerated: true,
  },
  {
    id: "13",
    slug: "midjourney-v7-photorealism",
    title: "Midjourney v7: Photorealism So Perfect It's Breaking Reality",
    excerpt:
      "Midjourney v7's photorealism is so precise that professional photographers are pivoting to AI.",
    coverImage: "/static/insights/tech/midjourney-v7-photorealism.jpg",
    category: "trends",
    author: {
      id: "editorial",
      name: "Bali Zero Editorial",
      avatar: "/static/team/editorial.jpg",
      role: "Editorial",
      isAI: false,
    },
    publishedAt: new Date("2026-01-02"),
    readingTime: 5,
    viewCount: 4210,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: "14",
    slug: "sora-video-generation",
    title: "Sora Has Arrived: OpenAI's Video Generator Changes Everything",
    excerpt: "Sora creates cinematic videos from text prompts.",
    coverImage: "/static/insights/tech/sora-video-generation.jpg",
    category: "trends",
    author: {
      id: "zantara-ai",
      name: "Zantara AI",
      avatar: "/static/zantara-lotus.png",
      role: "AI Business Advisor",
      isAI: true,
    },
    publishedAt: new Date("2026-01-02"),
    readingTime: 5,
    viewCount: 6120,
    featured: false,
    trending: false,
    aiGenerated: true,
  },
];
