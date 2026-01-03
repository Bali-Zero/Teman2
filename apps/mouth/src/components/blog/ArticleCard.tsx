'use client';

import * as React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { formatDistanceToNow } from 'date-fns';
import { Clock, Eye, TrendingUp, Sparkles, User } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ArticleCardProps, ArticleCategory } from '@/lib/blog/types';

// Category color mapping - McKinsey style with blue accent
const categoryStyles: Record<ArticleCategory, { bg: string; text: string; gradient: string }> = {
  immigration: {
    bg: 'bg-[#2251ff]/10',
    text: 'text-[#2251ff]',
    gradient: 'from-[#2251ff]/20 to-[#4d73ff]/20',
  },
  business: {
    bg: 'bg-emerald-500/10',
    text: 'text-emerald-400',
    gradient: 'from-emerald-500/20 to-teal-500/20',
  },
  'tax-legal': {
    bg: 'bg-amber-500/10',
    text: 'text-amber-400',
    gradient: 'from-amber-500/20 to-orange-500/20',
  },
  property: {
    bg: 'bg-[#e85c41]/10',
    text: 'text-[#e85c41]',
    gradient: 'from-[#e85c41]/20 to-[#d14832]/20',
  },
  lifestyle: {
    bg: 'bg-violet-500/10',
    text: 'text-violet-400',
    gradient: 'from-violet-500/20 to-purple-500/20',
  },
  tech: {
    bg: 'bg-fuchsia-500/10',
    text: 'text-fuchsia-400',
    gradient: 'from-fuchsia-500/20 to-pink-500/20',
  },
};

// Category badge component
function CategoryBadge({ category }: { category: ArticleCategory }) {
  const styles = categoryStyles[category];
  const label = category === 'tax-legal' ? 'Tax & Legal' : category;

  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium uppercase tracking-wider',
        'bg-gradient-to-r',
        styles.gradient,
        styles.text
      )}
    >
      {label}
    </span>
  );
}

// Featured article card (hero style)
function FeaturedCard({
  article,
  index = 0,
}: ArticleCardProps) {
  const href = `/${article.category}/${article.slug}`;

  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1, duration: 0.5 }}
      className="group relative overflow-hidden rounded-2xl bg-black/40"
    >
      <Link href={href} className="block">
        {/* Background Image */}
        <div className="relative aspect-[21/9] overflow-hidden">
          <Image
            src={article.coverImage}
            alt={article.title}
            fill
            className="object-cover transition-transform duration-700 group-hover:scale-105"
            priority
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 80vw, 1200px"
          />
          {/* Gradient Overlay */}
          <div className="absolute inset-0 bg-gradient-to-t from-black via-black/60 to-transparent" />

          {/* Content */}
          <div className="absolute bottom-0 left-0 right-0 p-6 md:p-8">
            {/* Badges */}
            <div className="flex flex-wrap items-center gap-2 md:gap-3 mb-3 md:mb-4">
              <CategoryBadge category={article.category} />
              {article.trending && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/20 text-red-400">
                  <TrendingUp className="w-3 h-3" />
                  Trending
                </span>
              )}
              {article.aiGenerated && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#2251ff]/20 text-[#2251ff]">
                  <Sparkles className="w-3 h-3" />
                  AI
                </span>
              )}
            </div>

            {/* Title */}
            <h2 className="font-serif text-2xl md:text-4xl lg:text-5xl font-bold text-white mb-3 md:mb-4 group-hover:text-[#2251ff] transition-colors leading-tight line-clamp-2">
              {article.title}
            </h2>

            {/* Excerpt */}
            <p className="text-white/70 text-sm md:text-lg mb-4 md:mb-6 max-w-3xl line-clamp-2">
              {article.excerpt}
            </p>

            {/* Meta */}
            <div className="flex flex-wrap items-center gap-3 md:gap-6 text-white/50 text-xs md:text-sm">
              <div className="flex items-center gap-2">
                {article.author.avatar ? (
                  <Image
                    src={article.author.avatar}
                    alt={article.author.name}
                    width={28}
                    height={28}
                    className="rounded-full"
                  />
                ) : (
                  <div className="w-7 h-7 rounded-full bg-white/10 flex items-center justify-center">
                    <User className="w-4 h-4" />
                  </div>
                )}
                <span>{article.author.name}</span>
              </div>
              <div className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                <span>{article.readingTime} min read</span>
              </div>
              <div className="flex items-center gap-1">
                <Eye className="w-4 h-4" />
                <span>{article.viewCount.toLocaleString()} views</span>
              </div>
            </div>
          </div>
        </div>
      </Link>
    </motion.article>
  );
}

// Default article card
function DefaultCard({
  article,
  index = 0,
  showCategory = true,
  showAuthor = true,
  showReadTime = true,
}: ArticleCardProps) {
  const href = `/${article.category}/${article.slug}`;

  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.4 }}
      className="group"
    >
      <Link href={href} className="block">
        {/* Image */}
        <div className="relative aspect-[16/10] overflow-hidden rounded-xl mb-4">
          <Image
            src={article.coverImage}
            alt={article.title}
            fill
            className="object-cover transition-transform duration-500 group-hover:scale-105"
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

          {/* Badges overlay */}
          <div className="absolute top-3 right-3 flex gap-2">
            {article.trending && (
              <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-red-500/80 backdrop-blur-sm text-white text-xs font-medium">
                <TrendingUp className="w-3 h-3" />
              </span>
            )}
            {article.aiGenerated && (
              <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[#2251ff]/80 backdrop-blur-sm text-white text-xs font-medium">
                <Sparkles className="w-3 h-3" />
              </span>
            )}
          </div>

          {/* Reading time badge */}
          {showReadTime && (
            <div className="absolute bottom-3 right-3 px-2 py-1 rounded-lg bg-black/70 backdrop-blur-sm text-white/80 text-xs flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {article.readingTime} min
            </div>
          )}
        </div>

        {/* Category */}
        {showCategory && (
          <div className="mb-2">
            <CategoryBadge category={article.category} />
          </div>
        )}

        {/* Title */}
        <h3 className="font-serif text-lg md:text-xl font-semibold text-white mb-2 group-hover:text-[#2251ff] transition-colors line-clamp-2">
          {article.title}
        </h3>

        {/* Excerpt */}
        <p className="text-white/60 text-sm line-clamp-2 mb-3">
          {article.excerpt}
        </p>

        {/* Meta */}
        <div className="flex items-center justify-between text-white/40 text-xs">
          {showAuthor && (
            <div className="flex items-center gap-2">
              {article.author.avatar ? (
                <Image
                  src={article.author.avatar}
                  alt={article.author.name}
                  width={20}
                  height={20}
                  className="rounded-full"
                />
              ) : (
                <div className="w-5 h-5 rounded-full bg-white/10 flex items-center justify-center">
                  <User className="w-3 h-3" />
                </div>
              )}
              <span>{article.author.name}</span>
            </div>
          )}
          <div className="flex items-center gap-3">
            <span>
              {formatDistanceToNow(new Date(article.publishedAt), {
                addSuffix: true,
              })}
            </span>
            <span className="flex items-center gap-1">
              <Eye className="w-3 h-3" />
              {article.viewCount.toLocaleString()}
            </span>
          </div>
        </div>
      </Link>
    </motion.article>
  );
}

// Compact card (for sidebars)
function CompactCard({
  article,
  index = 0,
}: ArticleCardProps) {
  const href = `/${article.category}/${article.slug}`;

  return (
    <motion.article
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      className="group"
    >
      <Link href={href} className="flex gap-3">
        {/* Thumbnail */}
        <div className="relative w-20 h-20 flex-shrink-0 overflow-hidden rounded-lg">
          <Image
            src={article.coverImage}
            alt={article.title}
            fill
            className="object-cover transition-transform duration-300 group-hover:scale-110"
            sizes="80px"
          />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <CategoryBadge category={article.category} />
          <h4 className="font-medium text-white text-sm mt-1 mb-1 group-hover:text-[#2251ff] transition-colors line-clamp-2">
            {article.title}
          </h4>
          <div className="flex items-center gap-2 text-white/40 text-xs">
            <Clock className="w-3 h-3" />
            <span>{article.readingTime} min</span>
          </div>
        </div>
      </Link>
    </motion.article>
  );
}

// Horizontal card (for lists)
function HorizontalCard({
  article,
  index = 0,
  showCategory = true,
}: ArticleCardProps) {
  const href = `/${article.category}/${article.slug}`;

  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      className="group"
    >
      <Link href={href} className="flex gap-4 md:gap-6">
        {/* Image */}
        <div className="relative w-32 md:w-48 aspect-[4/3] flex-shrink-0 overflow-hidden rounded-xl">
          <Image
            src={article.coverImage}
            alt={article.title}
            fill
            className="object-cover transition-transform duration-500 group-hover:scale-105"
            sizes="(max-width: 768px) 128px, 192px"
          />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 py-1">
          {showCategory && (
            <div className="mb-2">
              <CategoryBadge category={article.category} />
            </div>
          )}

          <h3 className="font-serif text-lg md:text-xl font-semibold text-white mb-2 group-hover:text-[#2251ff] transition-colors line-clamp-2">
            {article.title}
          </h3>

          <p className="text-white/60 text-sm line-clamp-2 mb-3 hidden md:block">
            {article.excerpt}
          </p>

          <div className="flex items-center gap-4 text-white/40 text-xs">
            <span>{article.author.name}</span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {article.readingTime} min
            </span>
            <span className="flex items-center gap-1">
              <Eye className="w-3 h-3" />
              {article.viewCount.toLocaleString()}
            </span>
          </div>
        </div>
      </Link>
    </motion.article>
  );
}

// Main ArticleCard component
export function ArticleCard({
  article,
  variant = 'default',
  index = 0,
  showCategory = true,
  showAuthor = true,
  showReadTime = true,
  className,
}: ArticleCardProps) {
  const props = {
    article,
    index,
    showCategory,
    showAuthor,
    showReadTime,
    className,
  };

  switch (variant) {
    case 'featured':
      return <FeaturedCard {...props} />;
    case 'compact':
      return <CompactCard {...props} />;
    case 'horizontal':
      return <HorizontalCard {...props} />;
    default:
      return <DefaultCard {...props} />;
  }
}

// Named exports for direct use
export { FeaturedCard, DefaultCard, CompactCard, HorizontalCard, CategoryBadge };
