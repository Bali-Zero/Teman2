'use client';

import * as React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { ArrowRight, Sparkles, Play, ChevronRight } from 'lucide-react';
import type { ArticleListItem } from '@/lib/blog/types';

/**
 * Insights Homepage - "The Chronicle"
 * McKinsey-inspired editorial layout
 */
export default function InsightsPage() {
  const [articles] = React.useState<ArticleListItem[]>(MOCK_ARTICLES);

  const featuredArticle = articles.find(a => a.featured);
  const trendingArticles = articles.filter(a => a.trending && !a.featured).slice(0, 3);
  const recentArticles = articles.filter(a => !a.featured).slice(0, 6);

  return (
    <div className="min-h-screen bg-[#051C2C]">
      {/* Hero Section - 3 Column Grid */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-3">
            {/* Column 1: Featured Article */}
            {featuredArticle && (
              <div className="lg:col-span-1 border-b lg:border-b-0 lg:border-r border-white/10 animate-in fade-in duration-500">
                <Link href={`/insights/${featuredArticle.category}/${featuredArticle.slug}`}>
                  <article className="group h-full">
                    {/* Image */}
                    <div className="aspect-[4/3] relative overflow-hidden">
                      <Image
                        src={featuredArticle.coverImage}
                        alt={featuredArticle.title}
                        fill
                        className="object-cover group-hover:scale-105 transition-transform duration-700"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-[#051C2C] via-transparent to-transparent" />

                      {/* AI Badge */}
                      {featuredArticle.aiGenerated && (
                        <div className="absolute top-4 left-4 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#2251ff] text-white text-xs font-medium">
                          <Sparkles className="w-3 h-3" />
                          AI Insight
                        </div>
                      )}
                    </div>

                    {/* Content */}
                    <div className="p-6 lg:p-8">
                      <span className="text-[#2251ff] text-xs font-semibold uppercase tracking-wider mb-3 block">
                        {formatCategory(featuredArticle.category)}
                      </span>

                      <h2 className="font-serif text-2xl lg:text-3xl text-white mb-4 leading-tight group-hover:text-[#2251ff] transition-colors">
                        {featuredArticle.title}
                      </h2>

                      <p className="text-white/60 text-sm leading-relaxed mb-6 line-clamp-3">
                        {featuredArticle.excerpt}
                      </p>

                      <div className="flex items-center gap-2 text-white/40 text-sm">
                        <span>{featuredArticle.readingTime} min read</span>
                      </div>
                    </div>
                  </article>
                </Link>
              </div>
            )}

            {/* Column 2: Main Headline */}
            <div className="lg:col-span-1 border-b lg:border-b-0 lg:border-r border-white/10 flex flex-col justify-center p-8 lg:p-12 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-100">
              <div className="max-w-md">
                <h1 className="font-serif text-4xl lg:text-5xl xl:text-6xl text-white leading-[1.1] mb-6">
                  What's your next{' '}
                  <span className="text-[#e85c41]">brilliant</span>{' '}
                  move?
                </h1>

                <p className="text-lg text-white/70 mb-8 leading-relaxed">
                  Navigate Indonesia with confidence. Expert insights on visas, business setup, and building your life in Bali.
                </p>

                <Link
                  href="/contact"
                  className="inline-flex items-center gap-3 text-white group"
                >
                  <span className="text-lg font-medium">Start your journey</span>
                  <span className="w-12 h-12 rounded-full border-2 border-white/30 flex items-center justify-center group-hover:bg-[#2251ff] group-hover:border-[#2251ff] transition-all duration-300">
                    <ArrowRight className="w-5 h-5" />
                  </span>
                </Link>
              </div>
            </div>

            {/* Column 3: Article List */}
            <div className="lg:col-span-1 divide-y divide-white/10 animate-in fade-in duration-500 delay-200">
              {trendingArticles.map((article, index) => (
                <Link
                  key={article.id}
                  href={`/insights/${article.category}/${article.slug}`}
                >
                  <article className="group p-6 lg:p-8 hover:bg-white/5 transition-colors">
                    <span className="text-[#2251ff] text-xs font-semibold uppercase tracking-wider mb-2 block">
                      {formatCategory(article.category)}
                    </span>

                    <h3 className="font-serif text-lg lg:text-xl text-white mb-3 leading-snug group-hover:text-[#2251ff] transition-colors line-clamp-2">
                      {article.title}
                    </h3>

                    <div className="flex items-center gap-3 text-white/40 text-sm">
                      <span>{article.readingTime} min</span>
                      <span>•</span>
                      <span>{article.viewCount.toLocaleString()} views</span>
                    </div>
                  </article>
                </Link>
              ))}
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
                key={topic.slug}
                href={`/insights/${topic.slug}`}
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
              href="/insights/all"
              className="flex items-center gap-2 text-[#2251ff] hover:text-[#4d73ff] text-sm font-medium transition-colors"
            >
              View all
              <ChevronRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {recentArticles.slice(0, 3).map((article, index) => (
              <div key={article.id} className="animate-in fade-in slide-in-from-bottom-4 duration-500" style={{ animationDelay: `${index * 100}ms` }}>
                <Link href={`/insights/${article.category}/${article.slug}`}>
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
                      <span>{article.viewCount.toLocaleString()} views</span>
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
                href="/insights/guides/bali-complete-guide"
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
              {recentArticles.slice(3, 6).map((article) => (
                <Link
                  key={article.id}
                  href={`/insights/${article.category}/${article.slug}`}
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
                        <span>{article.viewCount.toLocaleString()} views</span>
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
              href="/insights/media"
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
            <div className="group relative rounded-xl overflow-hidden bg-gradient-to-br from-[#0a2540] to-[#051C2C] border border-white/10">
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

// Topics for filter pills
const TOPICS = [
  { name: 'Golden Visa', slug: 'immigration' },
  { name: 'PT PMA', slug: 'business' },
  { name: 'Tax 2025', slug: 'tax-legal' },
  { name: 'KITAS', slug: 'immigration' },
  { name: 'Digital Nomad', slug: 'lifestyle' },
  { name: 'Property', slug: 'property' },
  { name: 'Work Permits', slug: 'immigration' },
  { name: 'Banking', slug: 'lifestyle' },
];

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
    slug: 'golden-visa-revolution',
    title: "The Golden Visa Revolution: Indonesia's $350K Bet on Global Talent",
    excerpt: 'Indonesia launches its Golden Visa program, offering 5-10 year stays for investors and high-net-worth individuals. What it means for you.',
    coverImage: '/images/blog/golden-visa.jpg',
    category: 'immigration',
    author: {
      id: 'zantara-ai',
      name: 'Zantara AI',
      avatar: '/images/zan_logo.png',
      role: 'AI Research',
      isAI: true,
    },
    publishedAt: new Date('2024-12-20'),
    readingTime: 12,
    viewCount: 15420,
    featured: true,
    trending: true,
    aiGenerated: true,
  },
  {
    id: '2',
    slug: 'oss-2-complete-guide',
    title: 'OSS 2.0: The Complete Guide to Indonesia Business Licensing',
    excerpt: 'Everything about the Online Single Submission system. From NIB to operational permits, we break down the bureaucracy.',
    coverImage: '/images/blog/oss-guide.jpg',
    category: 'business',
    author: {
      id: '1',
      name: 'Legal Team',
      avatar: '/images/team/legal.jpg',
      role: 'Legal Advisor',
      isAI: false,
    },
    publishedAt: new Date('2024-12-18'),
    readingTime: 15,
    viewCount: 8932,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: '3',
    slug: 'tax-deadlines-2025',
    title: 'Tax Deadlines 2025: What Every Expat Needs to Know',
    excerpt: 'Key dates for personal and corporate tax filings. Miss these and face penalties up to 200%.',
    coverImage: '/images/blog/tax-calendar.jpg',
    category: 'tax-legal',
    author: {
      id: 'zantara-ai',
      name: 'Zantara AI',
      avatar: '/images/zan_logo.png',
      role: 'AI Research',
      isAI: true,
    },
    publishedAt: new Date('2024-12-15'),
    readingTime: 8,
    viewCount: 6234,
    featured: false,
    trending: true,
    aiGenerated: true,
  },
  {
    id: '4',
    slug: 'north-bali-airport-update',
    title: 'North Bali Airport: Ten Years of Promises, Still No Runway',
    excerpt: 'The proposed Buleleng airport has been "coming soon" for a decade. We investigate what happened to the dream.',
    coverImage: '/images/blog/north-bali.jpg',
    category: 'property',
    author: {
      id: '2',
      name: 'Property Team',
      avatar: '/images/team/property.jpg',
      role: 'Property Specialist',
      isAI: false,
    },
    publishedAt: new Date('2024-12-12'),
    readingTime: 10,
    viewCount: 4521,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
  {
    id: '5',
    slug: 'digital-nomad-reality',
    title: 'The Digital Nomad Reality: Beyond the Instagram Fantasy',
    excerpt: 'Split-screen life: the coworking aesthetic vs calling mom to explain why you missed another Christmas.',
    coverImage: '/images/blog/nomad-comparison.jpg',
    category: 'lifestyle',
    author: {
      id: 'zantara-ai',
      name: 'Zantara AI',
      avatar: '/images/zan_logo.png',
      role: 'AI Research',
      isAI: true,
    },
    publishedAt: new Date('2024-12-10'),
    readingTime: 14,
    viewCount: 7845,
    featured: false,
    trending: false,
    aiGenerated: true,
  },
  {
    id: '6',
    slug: 'kitas-application-2025',
    title: 'KITAS Application 2025: A 5am Queue and Shared Coffee',
    excerpt: 'The real story of getting your stay permit. We spent three weeks in immigration offices so you know what to expect.',
    coverImage: '/images/blog/kitas-guide.jpg',
    category: 'immigration',
    author: {
      id: '1',
      name: 'Immigration Team',
      avatar: '/images/team/immigration.jpg',
      role: 'Immigration Specialist',
      isAI: false,
    },
    publishedAt: new Date('2024-12-08'),
    readingTime: 18,
    viewCount: 12340,
    featured: false,
    trending: false,
    aiGenerated: false,
  },
];
