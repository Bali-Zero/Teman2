'use client';

import React from 'react';
import Image from 'next/image';
import { ArrowRight } from 'lucide-react';

interface FeaturedArticle {
  id: string;
  title: string;
  category: string;
  categoryColor: string;
  imageUrl: string;
  href: string;
  isFeatured?: boolean;
}

const featuredArticles: FeaturedArticle[] = [
  {
    id: '1',
    title: 'Suwung Landfill Closure: The Waste Crisis Hitting Bali\'s Tourist Zones',
    category: 'LIFESTYLE',
    categoryColor: 'text-red-400',
    imageUrl: 'https://balizero.com/_next/image?url=https%3A%2F%2Fwww.datocms-assets.com%2F155584%2F1736428006-dump_burn_bali_suwung.jpg&w=1920&q=75',
    href: 'https://balizero.com/lifestyle/suwung-landfill-closure-waste-crisis-bali',
  },
  {
    id: '2',
    title: 'Property Alert: Green Zone Crackdown and the End of Easy Villa Permits',
    category: 'PROPERTY',
    categoryColor: 'text-amber-400',
    imageUrl: 'https://balizero.com/_next/image?url=https%3A%2F%2Fwww.datocms-assets.com%2F155584%2F1736337413-green-zone-crackdown-bali-villas.jpg&w=1920&q=75',
    href: 'https://balizero.com/property/green-zone-crackdown-end-easy-villa-permits',
  },
  {
    id: '3',
    title: 'Dengue Alert 2026: 636 Cases and Rising — What Expats Need to Know',
    category: 'LIFESTYLE',
    categoryColor: 'text-red-400',
    imageUrl: 'https://balizero.com/_next/image?url=https%3A%2F%2Fwww.datocms-assets.com%2F155584%2F1736424131-dengue-mosquito-bali.jpg&w=1920&q=75',
    href: 'https://balizero.com/lifestyle/dengue-alert-2026-636-cases-rising-expats',
  },
  {
    id: '4',
    title: 'The 40-75% Tax Shock: What Pajak Hiburan Means for Beach Clubs and Nightlife',
    category: 'TAX & LEGAL',
    categoryColor: 'text-cyan-400',
    imageUrl: 'https://balizero.com/_next/image?url=https%3A%2F%2Fwww.datocms-assets.com%2F155584%2F1736336893-pajak-hiburan-beach-clubs-bali.jpg&w=1920&q=75',
    href: 'https://balizero.com/tax-legal/pajak-hiburan-40-75-tax-beach-clubs-nightlife',
  },
  {
    id: '5',
    title: 'Bali\'s Perfect Storm: Why 2026 Demands a New Playbook',
    category: 'LIFESTYLE',
    categoryColor: 'text-red-400',
    imageUrl: 'https://balizero.com/_next/image?url=https%3A%2F%2Fwww.datocms-assets.com%2F155584%2F1736335520-bali-storm-rice-fields.jpg&w=1920&q=75',
    href: 'https://balizero.com/lifestyle/bali-perfect-storm-2026-new-playbook',
    isFeatured: true,
  },
];

function ArticleCard({ article, className = '', size = 'normal' }: {
  article: FeaturedArticle;
  className?: string;
  size?: 'normal' | 'large';
}) {
  return (
    <a
      href={article.href}
      target="_blank"
      rel="noopener noreferrer"
      className={`group relative block overflow-hidden rounded-xl ${className}`}
    >
      <div className="absolute inset-0">
        <Image
          src={article.imageUrl}
          alt={article.title}
          fill
          className="object-cover transition-transform duration-500 group-hover:scale-105"
          sizes="(max-width: 768px) 100vw, 33vw"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent" />
      </div>

      <div className={`relative flex flex-col justify-end p-4 ${size === 'large' ? 'min-h-[400px] md:min-h-full' : 'min-h-[200px]'}`}>
        <span className={`text-xs font-semibold uppercase tracking-wider ${article.categoryColor} mb-2`}>
          {article.category}
        </span>
        <h3 className={`font-semibold text-white leading-tight group-hover:text-[var(--accent)] transition-colors ${
          size === 'large' ? 'text-xl md:text-2xl' : 'text-sm md:text-base'
        }`}>
          {article.title}
        </h3>

        {article.isFeatured && (
          <button className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-white text-black text-sm font-medium rounded-lg w-fit hover:bg-gray-100 transition-colors">
            Read the case study
            <ArrowRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </a>
  );
}

export function FeaturedArticlesWidget() {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[#0a1628] p-6 overflow-hidden">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl md:text-3xl font-bold text-white">
          Decode Indonesia.
        </h2>
        <h2 className="text-2xl md:text-3xl font-bold">
          <span className="text-red-500">Thrive</span>{' '}
          <span className="text-white">here</span>
        </h2>
        <p className="text-gray-400 mt-2 text-sm md:text-base">
          Legal, immigration, fiscal & business intelligence for Indonesia.{' '}
          <a
            href="https://balizero.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-400 hover:text-blue-300 transition-colors"
          >
            Forged by Zantara AI.
          </a>
        </p>
      </div>

      {/* Articles Grid - matching balizero.com layout */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Left Column - 2 stacked articles */}
        <div className="flex flex-col gap-4">
          <ArticleCard
            article={featuredArticles[0]}
            className="flex-1"
          />
          <ArticleCard
            article={featuredArticles[1]}
            className="flex-1"
          />
        </div>

        {/* Middle Column - 2 stacked articles */}
        <div className="flex flex-col gap-4">
          <ArticleCard
            article={featuredArticles[2]}
            className="flex-1"
          />
          <ArticleCard
            article={featuredArticles[3]}
            className="flex-1"
          />
        </div>

        {/* Right Column - 1 tall featured article */}
        <div className="flex flex-col">
          <ArticleCard
            article={featuredArticles[4]}
            className="flex-1"
            size="large"
          />
        </div>
      </div>
    </div>
  );
}

export default FeaturedArticlesWidget;
