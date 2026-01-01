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
 * Insights Homepage - "The Chronicle"
 * McKinsey-inspired editorial layout
 */
export default function InsightsPage() {
  const [articles] = React.useState<ArticleListItem[]>(MOCK_ARTICLES);

  // MAIN NEWS 1: Featured article (left column)
  const mainNews1 = articles.find(a => a.featured);

  // MAIN NEWS 2 & 3: Trending articles for right column (excluding featured)
  const mainNews2and3 = articles.filter(a => a.trending && !a.featured).slice(0, 2);

  // Get IDs of main news articles to exclude them from other sections
  const mainNewsIds = new Set([
    mainNews1?.id,
    ...mainNews2and3.map(a => a.id)
  ].filter(Boolean));

  // Other articles: Everything else (for sections below)
  const otherArticles = articles.filter(a => !mainNewsIds.has(a.id));

  return (
    <>
      {/* SEO Schemas for AI and Search Engines */}
      <HomepageSEOSchemas />

      <div className="min-h-screen bg-[#0c1f3a]">
      {/* Hero Section - 3 Column Grid */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-3">
            {/* Column 1: MAIN NEWS 1 - Featured Article - extends 1.5cm into Column 2 */}
            {mainNews1 && (
              <div className="lg:col-span-1 border-b lg:border-b-0 border-white/10 animate-in fade-in duration-500 relative z-10">
                <Link href={`/${mainNews1.category}/${mainNews1.slug}`}>
                  <article className="group h-full">
                    {/* Image - extends 56px (1.5cm) into next column */}
                    <div className="aspect-[4/4] relative overflow-visible lg:mr-[-56px]">
                      <Image
                        src={mainNews1.coverImage}
                        alt={mainNews1.title}
                        fill
                        className="object-cover group-hover:scale-105 transition-transform duration-700"
                      />
                      {/* Gradient removed for GCI image */}

                      {/* AI Badge */}
                      {mainNews1.aiGenerated && (
                        <div className="absolute top-4 left-4 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#2251ff] text-white text-xs font-medium">
                          <Sparkles className="w-3 h-3" />
                          AI Insight
                        </div>
                      )}
                    </div>

                    {/* Content */}
                    <div className="p-6 lg:p-8">
                      <span className="text-[#2251ff] text-xs font-semibold uppercase tracking-wider mb-3 block">
                        {formatCategory(mainNews1.category)}
                      </span>

                      <h2 className="font-serif text-2xl lg:text-3xl text-white mb-4 leading-tight group-hover:text-[#2251ff] transition-colors">
                        {mainNews1.title}
                      </h2>

                      <p className="text-white/60 text-sm leading-relaxed mb-6 line-clamp-3">
                        {mainNews1.excerpt}
                      </p>

                      <div className="flex items-center gap-2 text-white/40 text-sm">
                        <span>{mainNews1.readingTime} min read</span>
                      </div>
                    </div>
                  </article>
                </Link>
              </div>
            )}

            {/* Column 2: Main Headline - shifted right 2.5cm (~100px) */}
            <div className="lg:col-span-1 border-b lg:border-b-0 lg:border-r border-white/10 flex flex-col justify-center p-8 lg:p-12 lg:pl-28 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-100">
              <div className="max-w-md">
                <h1 className="font-serif text-4xl lg:text-5xl xl:text-6xl text-white leading-[1.1] mb-6">
                  Decode Indonesia.{' '}
                  <span className="text-[#e85c41]">Thrive</span>{' '}
                  here.
                </h1>

                <p className="text-lg text-white/70 mb-8 leading-relaxed">
                  Navigate Indonesia with confidence. Expert insights on visas, business setup, and building your life in Bali.
                </p>

                <a
                  href={`${APP_DOMAIN}/chat`}
                  className="inline-flex items-center gap-3 text-white group"
                >
                  <span className="text-lg font-medium">Start your journey</span>
                  <span className="w-12 h-12 rounded-full border-2 border-white/30 flex items-center justify-center group-hover:bg-[#2251ff] group-hover:border-[#2251ff] transition-all duration-300">
                    <ArrowRight className="w-5 h-5" />
                  </span>
                </a>
              </div>
            </div>

            {/* Column 3: MAIN NEWS 2 & 3 - Stacked Articles with Overlapping Images */}
            <div className="lg:col-span-1 p-6 lg:p-8 animate-in fade-in duration-500 delay-200 overflow-visible">
              <div className="relative h-full flex flex-col gap-4">
                {mainNews2and3.map((article, index) => (
                  <Link
                    key={article.id}
                    href={`/${article.category}/${article.slug}`}
                    className="group relative"
                    style={{
                      // MAIN NEWS 2 (index 0): extends 0.5cm left into Column 2
                      // MAIN NEWS 3 (index 1): offset right and overlaps upward
                      marginLeft: index === 0 ? '-38px' : '20px',
                      marginTop: index === 1 ? '-24px' : '0',
                      zIndex: index === 0 ? 2 : 1,
                    }}
                  >
                    <article className="relative bg-[#0a2a3d] rounded-xl overflow-hidden border border-white/10 hover:border-white/20 transition-all shadow-lg hover:shadow-xl">
                      {/* Image - no gradient/blur */}
                      <div className="aspect-[16/9] relative overflow-hidden">
                        <Image
                          src={article.coverImage}
                          alt={article.title}
                          fill
                          className="object-cover group-hover:scale-105 transition-transform duration-500"
                        />
                      </div>

                      {/* Content */}
                      <div className="p-4">
                        <span className="text-[#2251ff] text-xs font-semibold uppercase tracking-wider mb-1 block">
                          {formatCategory(article.category)}
                        </span>

                        <h3 className="font-serif text-base lg:text-lg text-white leading-snug group-hover:text-[#2251ff] transition-colors line-clamp-2">
                          {article.title}
                        </h3>

                        <div className="flex items-center gap-2 text-white/40 text-xs mt-2">
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
        </div>
      </section>

      {/* Newsletter Banner */}
      <section className="bg-[#2251ff]">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <p className="text-white font-medium">Weekly Indonesia Insights</p>
                <p className="text-white/70 text-sm">Expert analysis delivered to your inbox</p>
              </div>
            </div>

            <form className="flex gap-3 w-full md:w-auto">
              <input
                type="email"
                placeholder="Email address"
                className="flex-1 md:w-64 px-4 py-2.5 rounded-lg bg-white/10 border border-white/20 text-white placeholder-white/50 focus:outline-none focus:border-white/40 transition-colors"
              />
              <button
                type="submit"
                className="px-6 py-2.5 rounded-lg bg-white text-[#2251ff] font-semibold hover:bg-white/90 transition-colors"
              >
                Subscribe
              </button>
            </form>
          </div>
        </div>
      </section>

      {/* Topics Grid */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-12">
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
                    {/* Image */}
                    <div className="aspect-[16/10] relative overflow-hidden rounded-lg mb-5">
                      <Image
                        src={article.coverImage}
                        alt={article.title}
                        fill
                        className="object-cover group-hover:scale-105 transition-transform duration-700"
                      />
                      {article.aiGenerated && (
                        <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#2251ff] text-white text-xs font-medium">
                          <Sparkles className="w-3 h-3" />
                          AI
                        </div>
                      )}
                    </div>

                    {/* Content */}
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
            {/* Left: Collection Promo */}
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

            {/* Right: More Articles */}
            <div className="divide-y divide-white/10">
              {otherArticles.slice(3, 6).map((article) => (
                <Link
                  key={article.id}
                  href={`/${article.category}/${article.slug}`}
                >
                  <article className="group flex gap-5 p-6 lg:p-8 hover:bg-white/5 transition-colors">
                    {/* Thumbnail */}
                    <div className="w-24 h-24 flex-shrink-0 rounded-lg overflow-hidden relative">
                      <Image
                        src={article.coverImage}
                        alt={article.title}
                        fill
                        className="object-cover group-hover:scale-105 transition-transform duration-500"
                      />
                    </div>

                    {/* Content */}
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
            <Link
              href="/lifestyle"
              className="flex items-center gap-2 text-[#2251ff] hover:text-[#4d73ff] text-sm font-medium transition-colors"
            >
              All media
              <ChevronRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Video Card */}
            <div className="group relative rounded-xl overflow-hidden">
              <div className="aspect-video relative">
                <Image
                  src="/images/blog/golden-visa.jpg"
                  alt="Video thumbnail"
                  fill
                  className="object-cover group-hover:scale-105 transition-transform duration-700"
                />
                <div className="absolute inset-0 bg-black/40 group-hover:bg-black/50 transition-colors" />

                {/* Play Button */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-16 h-16 rounded-full bg-white flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Play className="w-6 h-6 text-[#051C2C] ml-1" fill="currentColor" />
                  </div>
                </div>

                {/* Content */}
                <div className="absolute bottom-0 left-0 right-0 p-6">
                  <span className="text-[#2251ff] text-xs font-semibold uppercase tracking-wider mb-2 block">
                    Video • 12 min
                  </span>
                  <h3 className="font-serif text-xl text-white leading-snug">
                    Golden Visa Explained: Is It Right for You?
                  </h3>
                </div>
              </div>
            </div>

            {/* Podcast Card */}
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
                    <span className="text-[#e85c41] text-xs font-semibold uppercase tracking-wider mb-2 block">
                      Podcast • Episode 24
                    </span>
                    <h3 className="font-serif text-xl text-white mb-3 leading-snug">
                      Tax Strategies for Digital Nomads in Indonesia
                    </h3>
                    <p className="text-white/60 text-sm mb-4">
                      Our tax experts discuss the latest regulations and how to stay compliant.
                    </p>
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
                  <div className="group p-6 rounded-xl border border-white/10 hover:border-[#2251ff]/50 hover:bg-white/5 transition-all h-full">
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

// Helper function to format category names
function formatCategory(category: string): string {
  const categoryMap: Record<string, string> = {
    'immigration': 'Immigration',
    'business': 'Business',
    'tax-legal': 'Tax & Legal',
    'property': 'Property',
    'lifestyle': 'Lifestyle',
  };
  return categoryMap[category] || category.replace('-', ' & ');
}

// Topics for filter pills - each needs unique id for React keys
const TOPICS = [
  { id: 'gci', name: 'GCI', slug: 'immigration' },
  { id: 'golden-visa', name: 'Golden Visa', slug: 'immigration' },
  { id: 'pt-pma', name: 'PT PMA', slug: 'business' },
  { id: 'tax-2026', name: 'Tax 2026', slug: 'tax-legal' },
  { id: 'kitas', name: 'KITAS', slug: 'immigration' },
  { id: 'digital-nomad', name: 'Digital Nomad', slug: 'lifestyle' },
  { id: 'property', name: 'Property', slug: 'property' },
  { id: 'work-permits', name: 'Work Permits', slug: 'immigration' },
];

// Stable number formatter to avoid hydration mismatch
function formatViewCount(count: number): string {
  // Using 'en-US' explicitly to ensure consistent formatting between server/client
  return new Intl.NumberFormat('en-US').format(count);
}

// Services with icons
import { Plane, Building2, Calculator } from 'lucide-react';

const SERVICES = [
  {
    name: 'Visa & Immigration',
    slug: 'visa',
    description: 'KITAS, KITAP, Golden Visa, and all permit types',
    icon: Plane,
  },
  {
    name: 'Company Setup',
    slug: 'company',
    description: 'PT PMA, PT Local, and business licensing',
    icon: Building2,
  },
  {
    name: 'Tax & Compliance',
    slug: 'tax',
    description: 'Personal and corporate tax services',
    icon: Calculator,
  },
];

// Mock data
const MOCK_ARTICLES: ArticleListItem[] = [
  {
    id: '1',
    slug: 'global-citizenship-indonesia',
    title: "Global Citizenship of Indonesia: The Long-Awaited Embrace",
    excerpt: 'After decades of "choose us or them," Indonesia finally opens its arms. GCI offers permanent residence to the diaspora — with some important caveats.',
    coverImage: '/images/blog/global-citizenship.jpg',
    category: 'immigration',
    author: {
      id: 'editorial',
      name: 'Bali Zero Editorial',
      avatar: '/images/team/editorial.jpg',
      role: 'Editorial',
      isAI: false,
    },
    publishedAt: new Date('2026-01-01'),
    readingTime: 8,
    viewCount: 24150,
    featured: true,
    trending: true,
    aiGenerated: false,
  },
  {
    id: '2',
    slug: 'bali-rules-respect',
    title: "Bali Is Not a Playground: The Rules You Must Respect",
    excerpt: "Bali welcomes visitors. What it doesn't welcome is arrogance. Here are the rules that too many people ignore — until they don't.",
    coverImage: '/images/blog/bali-rules-behavior.jpg',
    category: 'lifestyle',
    author: {
      id: 'editorial',
      name: 'Bali Zero Editorial',
      avatar: '/images/team/editorial.jpg',
      role: 'Editorial',
      isAI: false,
    },
    publishedAt: new Date('2026-01-01'),
    readingTime: 5,
    viewCount: 31200,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: '3',
    slug: 'kerobokan-traffic-trial',
    title: "Bali Takes Bold Action: The Kerobokan Kelod Traffic Trial",
    excerpt: "With 2.8M tourists arriving for Christmas and New Year, Bali experiments with radical traffic changes. One-month trial in Kerobokan.",
    coverImage: '/images/blog/kerobokan-traffic.jpg',
    category: 'lifestyle',
    author: {
      id: 'editorial',
      name: 'Bali Zero Editorial',
      avatar: '/images/team/editorial.jpg',
      role: 'Editorial',
      isAI: false,
    },
    publishedAt: new Date('2026-01-01'),
    readingTime: 4,
    viewCount: 8920,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: '10',
    slug: 'golden-visa-2026-updates',
    title: "Golden Visa 2026: One Year Later – What We've Learned",
    excerpt: 'After 12 months of Indonesia\'s Golden Visa program, we analyze approval rates, processing times, and whether the $350K investment is worth it.',
    coverImage: '/images/blog/golden-visa.jpg',
    category: 'immigration',
    author: {
      id: 'zantara-ai',
      name: 'Zantara AI',
      avatar: '/images/zantara-lotus.png',
      role: 'AI Research',
      isAI: true,
    },
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
    excerpt: 'Key dates for personal and corporate tax filings. New Coretax system fully operational. Miss these and face penalties up to 200%.',
    coverImage: '/images/blog/tax-calendar.jpg',
    category: 'tax-legal',
    author: {
      id: 'zantara-ai',
      name: 'Zantara AI',
      avatar: '/images/zantara-lotus.png',
      role: 'AI Research',
      isAI: true,
    },
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
    excerpt: "Panic spread online: 'Bali banned Airbnb!' But that's not true. The rules are just being enforced. What property owners need to know.",
    coverImage: '/images/blog/airbnb-bali-rules.jpg',
    category: 'property',
    author: {
      id: 'editorial',
      name: 'Bali Zero Editorial',
      avatar: '/images/team/editorial.jpg',
      role: 'Editorial',
      isAI: false,
    },
    publishedAt: new Date('2026-01-01'),
    readingTime: 5,
    viewCount: 18750,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: '5',
    slug: 'kerobokan-traffic-trial',
    title: "Bali Takes Bold Action: The Kerobokan Kelod Traffic Trial",
    excerpt: "With 2.8M tourists arriving for Christmas and New Year, Bali experiments with radical traffic changes. One-month trial in Kerobokan.",
    coverImage: '/images/blog/kerobokan-traffic.jpg',
    category: 'lifestyle',
    author: {
      id: 'editorial',
      name: 'Bali Zero Editorial',
      avatar: '/images/team/editorial.jpg',
      role: 'Editorial',
      isAI: false,
    },
    publishedAt: new Date('2026-01-01'),
    readingTime: 4,
    viewCount: 8920,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: '6',
    slug: 'north-bali-airport-2026',
    title: 'North Bali Airport 2026: Construction Finally Begins?',
    excerpt: 'After years of delays, ground-breaking ceremonies scheduled for Q2 2026. What this means for Buleleng property values.',
    coverImage: '/images/blog/north-bali.jpg',
    category: 'property',
    author: {
      id: '2',
      name: 'Property Team',
      avatar: '/images/team/property.jpg',
      role: 'Property Specialist',
      isAI: false,
    },
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
    excerpt: 'The long-awaited Digital Nomad Visa is here. 5-year stay, tax incentives, and what it means for remote workers in Bali.',
    coverImage: '/images/blog/nomad-comparison.jpg',
    category: 'lifestyle',
    author: {
      id: 'zantara-ai',
      name: 'Zantara AI',
      avatar: '/images/zantara-lotus.png',
      role: 'AI Research',
      isAI: true,
    },
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
    excerpt: 'The real story of getting your stay permit. Online booking now available, biometric centers expanded. Here\'s the updated process.',
    coverImage: '/images/blog/kitas-guide.jpg',
    category: 'immigration',
    author: {
      id: '1',
      name: 'Immigration Team',
      avatar: '/images/team/immigration.jpg',
      role: 'Immigration Specialist',
      isAI: false,
    },
    publishedAt: new Date('2025-12-20'),
    readingTime: 18,
    viewCount: 12340,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
];
