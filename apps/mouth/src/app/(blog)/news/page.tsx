'use client';

import * as React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { ArrowRight, Sparkles, Play, ChevronRight } from 'lucide-react';
import type { ArticleListItem } from '@/lib/blog/types';
import { HomepageSEOSchemas } from '@/components/seo/HomepageFAQ';

// App domain for internal routes
const APP_DOMAIN = process.env.NEXT_PUBLIC_APP_DOMAIN || 'https://zantara.balizero.com';

/**
 * News Page - "The Chronicle"
 * McKinsey-inspired asymmetric editorial layout with 5-article collage
 */
export default function NewsPage() {
  const [articles] = React.useState<ArticleListItem[]>(MOCK_ARTICLES);

  // Get specific articles for the asymmetric collage
  const mainNews1 = articles.find(a => a.slug === 'global-citizenship-indonesia'); // RIGHT - large
  const mainNews2 = articles.find(a => a.slug === 'bali-tourist-savings-check-2026'); // LEFT top - NO MONEY NO BALI
  const mainNews3 = articles.find(a => a.slug === 'indonesia-zero-tax-foreign-income-2026'); // MIDDLE top - 0% Tax Foreign Income
  const mainNews4 = articles.find(a => a.slug === 'gemini-3-native-intelligence'); // MIDDLE bottom - Gemini 3
  const mainNews5 = articles.find(a => a.slug === 'coretax-npwp-problems-2026'); // LEFT bottom - Coretax

  // Get IDs of main news articles to exclude them from other sections
  const mainNewsIds = new Set([
    mainNews1?.id, mainNews2?.id, mainNews3?.id, mainNews4?.id, mainNews5?.id
  ].filter(Boolean));

  // Other articles for sections below
  const otherArticles = articles.filter(a => !mainNewsIds.has(a.id));

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
                      alt=""
                      fill
                      className="object-cover opacity-30"
                      style={{
                        mixBlendMode: 'screen',
                        transform: 'scale(1.3) rotate(-5deg)',
                        transformOrigin: 'center center'
                      }}
                      priority
                    />
                  </div>
                  <div className="relative z-10">
                    <h1 className="font-serif text-4xl lg:text-5xl xl:text-6xl text-white leading-[1.1] mb-4">
                      Decode Indonesia.{' '}
                      <span className="text-red-500">Thrive</span>{' '}
                      here
                    </h1>
                    <p className="text-lg text-white/70">
                      Legal, immigration, fiscal & business intelligence for Indonesia.{' '}
                      <span className="text-[#2251ff]">Forged by Zantara AI.</span>
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
                  <CollageCard article={mainNews1} className="flex-[2.4]" showCTA />
                )}

                {/* Newsletter Box */}
                <div className="bg-[#0a2540] p-6 flex-[0.6]">
                  <p className="text-white font-medium mb-2">
                    Subscribe to the latest Indonesia Insights
                  </p>
                  <p className="text-white/60 text-sm mb-4">
                    Expert analysis delivered to your inbox
                  </p>
                  <form className="flex gap-2">
                    <input
                      type="email"
                      placeholder="Email address"
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
                    <span className="text-white/40 text-xs">Or continue with</span>
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

        {/* Latest Insights Grid */}
        <section className="border-b border-white/10">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
            <div className="flex items-center justify-between mb-10">
              <h2 className="text-2xl font-serif text-white">Latest Insights</h2>
              <Link
                href="/immigration"
                className="flex items-center gap-2 text-[#2251ff] hover:text-[#4d73ff] text-sm font-medium transition-colors"
              >
                View all
                <ChevronRight className="w-4 h-4" />
              </Link>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {otherArticles.slice(0, 3).map((article, index) => (
                <div key={article.id} className="animate-in fade-in slide-in-from-bottom-4 duration-500" style={{ animationDelay: `${index * 100}ms` }}>
                  <Link href={`/${article.category}/${article.slug}`}>
                    <article className="group">
                      <div className="aspect-[16/10] relative overflow-hidden rounded-lg mb-5">
                        <Image
                          src={article.coverImage}
                          alt={article.title}
                          fill
                          className="object-cover group-hover:scale-105 transition-transform duration-700"
                          style={{ objectPosition: 'center 25%' }}
                        />
                        {article.aiGenerated && (
                          <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#2251ff] text-white text-xs font-medium">
                            <Sparkles className="w-3 h-3" />
                            AI
                          </div>
                        )}
                      </div>

                      <span className="text-[#2251ff] text-xs font-semibold uppercase tracking-wider mb-2 block">
                        {formatCategory(article.category)}
                      </span>

                      <h3 className="font-serif text-xl text-white mb-3 leading-snug group-hover:text-[#2251ff] transition-colors line-clamp-2">
                        {article.title}
                      </h3>

                      <p className="text-white/60 text-sm leading-relaxed mb-4 line-clamp-2">
                        {article.excerpt}
                      </p>

                      <div className="flex items-center gap-3 text-white/40 text-sm">
                        <span>{article.readingTime} min read</span>
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

        {/* Featured Collection */}
        <section className="border-b border-white/10">
          <div className="max-w-[1400px] mx-auto">
            <div className="grid grid-cols-1 lg:grid-cols-2">
              <div className="bg-gradient-to-br from-[#e85c41] to-[#d14832] p-10 lg:p-16 flex flex-col justify-center">
                <span className="text-white/80 text-xs font-semibold uppercase tracking-wider mb-4">
                  Featured Collection
                </span>
                <h2 className="font-serif text-3xl lg:text-4xl text-white mb-4 leading-tight">
                  The Complete Guide to Living in Bali
                </h2>
                <p className="text-white/80 text-lg mb-8 leading-relaxed max-w-md">
                  Everything you need: visas, banking, housing, healthcare, community, and insider tips.
                </p>
                <Link
                  href="/lifestyle"
                  className="inline-flex items-center gap-3 text-white group w-fit"
                >
                  <span className="text-lg font-medium">Explore the guide</span>
                  <span className="w-10 h-10 rounded-full border-2 border-white/40 flex items-center justify-center group-hover:bg-white group-hover:text-[#e85c41] transition-all duration-300">
                    <ArrowRight className="w-4 h-4" />
                  </span>
                </Link>
              </div>

              <div className="divide-y divide-white/10">
                {otherArticles.slice(3, 6).map((article) => (
                  <Link key={article.id} href={`/${article.category}/${article.slug}`}>
                    <article className="group flex gap-5 p-6 lg:p-8 hover:bg-white/5 transition-colors">
                      <div className="w-24 h-24 flex-shrink-0 rounded-lg overflow-hidden relative">
                        <Image src={article.coverImage} alt={article.title} fill className="object-cover group-hover:scale-105 transition-transform duration-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="text-[#2251ff] text-xs font-semibold uppercase tracking-wider mb-1 block">
                          {formatCategory(article.category)}
                        </span>
                        <h3 className="font-serif text-lg text-white mb-2 leading-snug group-hover:text-[#2251ff] transition-colors line-clamp-2">
                          {article.title}
                        </h3>
                        <div className="flex items-center gap-3 text-white/40 text-sm">
                          <span>{article.readingTime} min</span>
                          <span>•</span>
                          <span>{formatViewCount(article.viewCount)} views</span>
                        </div>
                      </div>
                    </article>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Podcast/Video Section */}
        <section className="border-b border-white/10">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
            <div className="flex items-center justify-between mb-10">
              <h2 className="text-2xl font-serif text-white">Watch & Listen</h2>
              <Link href="/lifestyle" className="flex items-center gap-2 text-[#2251ff] hover:text-[#4d73ff] text-sm font-medium transition-colors">
                All media
                <ChevronRight className="w-4 h-4" />
              </Link>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="group relative rounded-xl overflow-hidden">
                <div className="aspect-video relative">
                  <Image src="/assets/blog/golden-visa.jpg" alt="Video thumbnail" fill className="object-cover group-hover:scale-105 transition-transform duration-700" />
                  <div className="absolute inset-0 bg-black/40 group-hover:bg-black/50 transition-colors" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-16 h-16 rounded-full bg-white flex items-center justify-center group-hover:scale-110 transition-transform">
                      <Play className="w-6 h-6 text-[#051C2C] ml-1" fill="currentColor" />
                    </div>
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 p-6">
                    <span className="text-[#2251ff] text-xs font-semibold uppercase tracking-wider mb-2 block">Video • 12 min</span>
                    <h3 className="font-serif text-xl text-white leading-snug">Golden Visa Explained: Is It Right for You?</h3>
                  </div>
                </div>
              </div>

              <div className="group relative rounded-xl overflow-hidden bg-gradient-to-br from-[#0a2540] to-[#0d3347] border border-white/10">
                <div className="p-8">
                  <div className="flex items-start gap-5">
                    <div className="w-20 h-20 rounded-lg bg-[#2251ff] flex items-center justify-center flex-shrink-0">
                      <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                        <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                      </svg>
                    </div>
                    <div>
                      <span className="text-[#e85c41] text-xs font-semibold uppercase tracking-wider mb-2 block">Podcast • Episode 24</span>
                      <h3 className="font-serif text-xl text-white mb-3 leading-snug">Tax Strategies for Digital Nomads in Indonesia</h3>
                      <p className="text-white/60 text-sm mb-4">Our tax experts discuss the latest regulations and how to stay compliant.</p>
                      <div className="flex items-center gap-4">
                        <button className="flex items-center gap-2 text-white text-sm font-medium hover:text-[#2251ff] transition-colors">
                          <Play className="w-4 h-4" fill="currentColor" />
                          Play now
                        </button>
                        <span className="text-white/40 text-sm">45 min</span>
                      </div>
                    </div>
                  </div>
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
                <h2 className="font-serif text-3xl text-white mb-4">Our Services</h2>
                <p className="text-white/60 mb-6">Expert assistance for your Indonesia journey</p>
                <Link href="/services" className="inline-flex items-center gap-2 text-[#2251ff] hover:text-[#4d73ff] font-medium transition-colors">
                  View all services
                  <ChevronRight className="w-4 h-4" />
                </Link>
              </div>

              <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-6">
                {SERVICES.map((service) => (
                  <Link key={service.slug} href={`/services/${service.slug}`}>
                    <div className="group p-6 rounded-xl border border-white/10 hover:border-[#2251ff]/50 hover:bg-white/5 transition-all h-full">
                      <div className="w-12 h-12 rounded-lg bg-[#2251ff]/10 flex items-center justify-center mb-4 group-hover:bg-[#2251ff]/20 transition-colors">
                        <service.icon className="w-6 h-6 text-[#2251ff]" />
                      </div>
                      <h3 className="font-serif text-lg text-white mb-2 group-hover:text-[#2251ff] transition-colors">{service.name}</h3>
                      <p className="text-white/60 text-sm">{service.description}</p>
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
  className = '',
  showCTA = false
}: {
  article: ArticleListItem;
  className?: string;
  showCTA?: boolean;
}) {
  return (
    <Link href={`/${article.category}/${article.slug}`} className={`block group relative overflow-hidden ${className}`}>
      <article className="relative w-full h-full min-h-[220px]">
        <Image
          src={article.coverImage}
          alt={article.title}
          fill
          className="object-cover group-hover:scale-105 transition-transform duration-700"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent" />

        <div className="absolute inset-0 p-5 lg:p-6 flex flex-col justify-end">
          <span className="text-[#2251ff] text-[10px] font-bold uppercase tracking-wider mb-2">
            {formatCategory(article.category)}
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

function formatCategory(category: string): string {
  const categoryMap: Record<string, string> = {
    'immigration': 'Immigration',
    'business': 'Business',
    'tax-legal': 'Tax & Legal',
    'property': 'Property',
    'lifestyle': 'Lifestyle',
    'tech': 'Tech & AI',
  };
  return categoryMap[category] || category.replace('-', ' & ');
}

const TOPICS = [
  { id: 'ai-tech', name: 'AI & Tech', slug: 'tech' },
  { id: 'gci', name: 'GCI', slug: 'immigration' },
  { id: 'golden-visa', name: 'Golden Visa', slug: 'immigration' },
  { id: 'pt-pma', name: 'PT PMA', slug: 'business' },
  { id: 'tax-2026', name: 'Tax 2026', slug: 'tax-legal' },
  { id: 'kitas', name: 'KITAS', slug: 'immigration' },
  { id: 'digital-nomad', name: 'Digital Nomad', slug: 'lifestyle' },
  { id: 'property', name: 'Property', slug: 'property' },
  { id: 'work-permits', name: 'Work Permits', slug: 'immigration' },
];

function formatViewCount(count: number): string {
  return new Intl.NumberFormat('en-US').format(count);
}

import { Plane, Building2, Calculator } from 'lucide-react';

const SERVICES = [
  { name: 'Visa & Immigration', slug: 'visa', description: 'KITAS, KITAP, Golden Visa, and all permit types', icon: Plane },
  { name: 'Company Setup', slug: 'company', description: 'PT PMA, PT Local, and business licensing', icon: Building2 },
  { name: 'Tax & Compliance', slug: 'tax', description: 'Personal and corporate tax services', icon: Calculator },
];

const MOCK_ARTICLES: ArticleListItem[] = [
  {
    id: '19',
    slug: 'indonesia-zero-tax-foreign-income-2026',
    title: "Indonesia's 0% Tax on Foreign Income: The Expat Advantage Most Don't Know",
    excerpt: "Living in Indonesia while earning abroad? Under PMK 18/2021, your foreign income may be taxed at 0%.",
    coverImage: '/static/news/indonesia-zero-tax-expat.jpg',
    category: 'tax-legal',
    author: { id: 'editorial', name: 'Bali Zero Editorial', avatar: '/static/team/editorial.jpg', role: 'Editorial', isAI: false },
    publishedAt: new Date('2026-01-04'),
    readingTime: 6,
    viewCount: 15320,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: '1',
    slug: 'global-citizenship-indonesia',
    title: "Global Citizenship of Indonesia: The Long-Awaited Embrace",
    excerpt: 'After decades of "choose us or them," Indonesia finally opens its arms.',
    coverImage: '/static/blog/global-citizenship.jpg',
    category: 'immigration',
    author: { id: 'editorial', name: 'Bali Zero Editorial', avatar: '/static/team/editorial.jpg', role: 'Editorial', isAI: false },
    publishedAt: new Date('2026-01-01'),
    readingTime: 8,
    viewCount: 24150,
    featured: true,
    trending: true,
    aiGenerated: false,
  },
  {
    id: '16',
    slug: 'coretax-npwp-problems-2026',
    title: "Coretax Chaos: Indonesia's New Tax System Is Breaking NPWP Registrations",
    excerpt: "Indonesia's new Coretax system launched January 1st — and it's causing headaches.",
    coverImage: '/static/news/coretax-kpp-queue.jpg',
    category: 'tax-legal',
    author: { id: 'editorial', name: 'Bali Zero Editorial', avatar: '/static/team/editorial.jpg', role: 'Editorial', isAI: false },
    publishedAt: new Date('2026-01-03'),
    readingTime: 6,
    viewCount: 12450,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: '11',
    slug: 'claude-opus-revolutionizes-ai',
    title: "Claude 4.5 Opus: How Anthropic Just Redefined What AI Can Do",
    excerpt: "Claude 4.5 Opus sets a new benchmark for AI. Extended thinking, deeper reasoning.",
    coverImage: '/static/insights/tech/claude-opus-revolutionizes-ai.jpg',
    category: 'tech',
    author: { id: 'editorial', name: 'Bali Zero Editorial', avatar: '/static/team/editorial.jpg', role: 'Editorial', isAI: false },
    publishedAt: new Date('2026-01-02'),
    readingTime: 6,
    viewCount: 18420,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: '18',
    slug: 'gemini-3-native-intelligence',
    title: "Gemini 3: Google Redefines AI with Native Intelligence",
    excerpt: "Gemini 3 doesn't answer: it anticipates. It doesn't assist: it acts. The first AI that thinks like a human.",
    coverImage: '/static/news/gemini-3-ai.jpg',
    category: 'tech',
    author: { id: 'editorial', name: 'Bali Zero Editorial', avatar: '/static/team/editorial.jpg', role: 'Editorial', isAI: false },
    publishedAt: new Date('2026-01-04'),
    readingTime: 5,
    viewCount: 28540,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: '15',
    slug: 'bali-tourist-savings-check-2026',
    title: "NO MONEY, NO BALI: Tourist Bank Account Checks Coming in 2026",
    excerpt: "Governor Koster announces financial screening for tourists entering Bali.",
    coverImage: '/static/news/bank-screening-clean.jpg',
    category: 'immigration',
    author: { id: 'editorial', name: 'Bali Zero Editorial', avatar: '/static/team/editorial.jpg', role: 'Editorial', isAI: false },
    publishedAt: new Date('2026-01-02'),
    readingTime: 8,
    viewCount: 45230,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: '17',
    slug: 'immigration-lounge-bali-malls-2026',
    title: "Immigration Lounges Coming to Bali Malls in 2026",
    excerpt: "No more queuing at Kantor Imigrasi? Bali plans to open immigration service lounges in shopping malls.",
    coverImage: '/static/news/immigration-lounge-mall.jpg',
    category: 'immigration',
    author: { id: 'editorial', name: 'Bali Zero Editorial', avatar: '/static/team/editorial.jpg', role: 'Editorial', isAI: false },
    publishedAt: new Date('2026-01-03'),
    readingTime: 5,
    viewCount: 8920,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: '2',
    slug: 'bali-rules-respect',
    title: "Bali Is Not a Playground: The Rules You Must Respect",
    excerpt: "Bali welcomes visitors. What it doesn't welcome is arrogance.",
    coverImage: '/static/blog/bali-rules-behavior.jpg',
    category: 'lifestyle',
    author: { id: 'editorial', name: 'Bali Zero Editorial', avatar: '/static/team/editorial.jpg', role: 'Editorial', isAI: false },
    publishedAt: new Date('2026-01-01'),
    readingTime: 5,
    viewCount: 31200,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: '3',
    slug: 'kerobokan-traffic-trial',
    title: "Bali Takes Bold Action: The Kerobokan Kelod Traffic Trial",
    excerpt: "With 2.8M tourists arriving for Christmas and New Year, Bali experiments with radical traffic changes.",
    coverImage: '/static/blog/kerobokan-traffic.jpg',
    category: 'lifestyle',
    author: { id: 'editorial', name: 'Bali Zero Editorial', avatar: '/static/team/editorial.jpg', role: 'Editorial', isAI: false },
    publishedAt: new Date('2026-01-01'),
    readingTime: 4,
    viewCount: 8920,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: '10',
    slug: 'golden-visa-2026-updates',
    title: "Golden Visa 2026: One Year Later – What We've Learned",
    excerpt: 'After 12 months of Indonesia\'s Golden Visa program, we analyze approval rates.',
    coverImage: '/static/blog/golden-visa.jpg',
    category: 'immigration',
    author: { id: 'zantara-ai', name: 'Zantara AI', avatar: '/static/zantara-lotus.png', role: 'AI Research', isAI: true },
    publishedAt: new Date('2025-12-30'),
    readingTime: 12,
    viewCount: 15420,
    featured: false,
    trending: false,
    aiGenerated: true,
  },
  {
    id: '9',
    slug: 'tax-deadlines-2026',
    title: 'Tax Deadlines 2026: What Every Expat Needs to Know',
    excerpt: 'Key dates for personal and corporate tax filings.',
    coverImage: '/static/blog/tax-calendar.jpg',
    category: 'tax-legal',
    author: { id: 'zantara-ai', name: 'Zantara AI', avatar: '/static/zantara-lotus.png', role: 'AI Research', isAI: true },
    publishedAt: new Date('2025-12-28'),
    readingTime: 8,
    viewCount: 6234,
    featured: false,
    trending: false,
    aiGenerated: true,
  },
  {
    id: '4',
    slug: 'airbnb-bali-ban-truth',
    title: "Is Airbnb Really Banned in Bali? Here's What's Actually Happening",
    excerpt: "Panic spread online: 'Bali banned Airbnb!' But that's not true.",
    coverImage: '/static/blog/airbnb-bali-rules.jpg',
    category: 'property',
    author: { id: 'editorial', name: 'Bali Zero Editorial', avatar: '/static/team/editorial.jpg', role: 'Editorial', isAI: false },
    publishedAt: new Date('2026-01-01'),
    readingTime: 5,
    viewCount: 18750,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: '6',
    slug: 'north-bali-airport-2026',
    title: 'North Bali Airport 2026: Construction Finally Begins?',
    excerpt: 'After years of delays, ground-breaking ceremonies scheduled for Q2 2026.',
    coverImage: '/static/blog/north-bali.jpg',
    category: 'property',
    author: { id: '2', name: 'Property Team', avatar: '/static/team/property.jpg', role: 'Property Specialist', isAI: false },
    publishedAt: new Date('2025-12-22'),
    readingTime: 10,
    viewCount: 4521,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: '7',
    slug: 'digital-nomad-visa-2026',
    title: 'Digital Nomad Visa 2026: Indonesia Finally Gets Serious',
    excerpt: 'The long-awaited Digital Nomad Visa is here.',
    coverImage: '/static/blog/nomad-comparison.jpg',
    category: 'lifestyle',
    author: { id: 'zantara-ai', name: 'Zantara AI', avatar: '/static/zantara-lotus.png', role: 'AI Research', isAI: true },
    publishedAt: new Date('2025-12-18'),
    readingTime: 14,
    viewCount: 7845,
    featured: false,
    trending: false,
    aiGenerated: true,
  },
  {
    id: '8',
    slug: 'kitas-application-2026',
    title: 'KITAS Application 2026: New Digital System Finally Works',
    excerpt: 'The real story of getting your stay permit.',
    coverImage: '/static/blog/kitas-guide.jpg',
    category: 'immigration',
    author: { id: '1', name: 'Immigration Team', avatar: '/static/team/immigration.jpg', role: 'Immigration Specialist', isAI: false },
    publishedAt: new Date('2025-12-20'),
    readingTime: 18,
    viewCount: 12340,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: '12',
    slug: 'ai-agents-autonomous-era',
    title: "The Rise of AI Agents: When Software Does Your Job (For Real)",
    excerpt: "AI agents now book travel, manage emails, file permits, and run businesses.",
    coverImage: '/static/insights/tech/ai-agents-autonomous-era.jpg',
    category: 'tech',
    author: { id: 'zantara-ai', name: 'Zantara AI', avatar: '/static/zantara-lotus.png', role: 'AI Research', isAI: true },
    publishedAt: new Date('2026-01-02'),
    readingTime: 6,
    viewCount: 3890,
    featured: false,
    trending: false,
    aiGenerated: true,
  },
  {
    id: '13',
    slug: 'midjourney-v7-photorealism',
    title: "Midjourney v7: Photorealism So Perfect It's Breaking Reality",
    excerpt: "Midjourney v7's photorealism is so precise that professional photographers are pivoting to AI.",
    coverImage: '/static/insights/tech/midjourney-v7-photorealism.jpg',
    category: 'tech',
    author: { id: 'editorial', name: 'Bali Zero Editorial', avatar: '/static/team/editorial.jpg', role: 'Editorial', isAI: false },
    publishedAt: new Date('2026-01-02'),
    readingTime: 5,
    viewCount: 4210,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: '14',
    slug: 'sora-video-generation',
    title: "Sora Has Arrived: OpenAI's Video Generator Changes Everything",
    excerpt: "Sora creates cinematic videos from text prompts.",
    coverImage: '/static/insights/tech/sora-video-generation.jpg',
    category: 'tech',
    author: { id: 'zantara-ai', name: 'Zantara AI', avatar: '/static/zantara-lotus.png', role: 'AI Research', isAI: true },
    publishedAt: new Date('2026-01-02'),
    readingTime: 5,
    viewCount: 6120,
    featured: false,
    trending: false,
    aiGenerated: true,
  },
];
