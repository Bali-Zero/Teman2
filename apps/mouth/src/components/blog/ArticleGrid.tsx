'use client';

import * as React from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { ArticleCard, FeaturedCard } from './ArticleCard';
import type { ArticleGridProps, ArticleListItem } from '@/lib/blog/types';

// Masonry-style grid layout
function MasonryGrid({
  articles,
  showFeatured = true,
}: {
  articles: ArticleListItem[];
  showFeatured?: boolean;
}) {
  // Separate featured article if requested
  const featuredArticle = showFeatured ? articles.find((a) => a.featured) : null;
  const regularArticles = featuredArticle
    ? articles.filter((a) => a.id !== featuredArticle.id)
    : articles;

  // Split into columns for masonry effect
  const leftColumn = regularArticles.filter((_, i) => i % 2 === 0);
  const rightColumn = regularArticles.filter((_, i) => i % 2 === 1);

  return (
    <div className="space-y-8">
      {/* Featured article */}
      {featuredArticle && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <FeaturedCard article={featuredArticle} index={0} />
        </motion.div>
      )}

      {/* Masonry grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">
        {/* Left column */}
        <div className="space-y-6 md:space-y-8">
          {leftColumn.map((article, index) => (
            <ArticleCard
              key={article.id}
              article={article}
              index={index}
              variant={index === 0 && !featuredArticle ? 'default' : 'default'}
            />
          ))}
        </div>

        {/* Right column - offset for masonry effect */}
        <div className="space-y-6 md:space-y-8 md:mt-12">
          {rightColumn.map((article, index) => (
            <ArticleCard
              key={article.id}
              article={article}
              index={index + leftColumn.length}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// Standard grid layout
function StandardGrid({
  articles,
  columns = 3,
  showFeatured = true,
}: {
  articles: ArticleListItem[];
  columns?: 2 | 3 | 4;
  showFeatured?: boolean;
}) {
  const featuredArticle = showFeatured ? articles.find((a) => a.featured) : null;
  const regularArticles = featuredArticle
    ? articles.filter((a) => a.id !== featuredArticle.id)
    : articles;

  const gridCols = {
    2: 'md:grid-cols-2',
    3: 'md:grid-cols-2 lg:grid-cols-3',
    4: 'md:grid-cols-2 lg:grid-cols-4',
  };

  return (
    <div className="space-y-8">
      {/* Featured article */}
      {featuredArticle && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <FeaturedCard article={featuredArticle} index={0} />
        </motion.div>
      )}

      {/* Grid */}
      <div className={cn('grid grid-cols-1 gap-6 md:gap-8', gridCols[columns])}>
        {regularArticles.map((article, index) => (
          <ArticleCard
            key={article.id}
            article={article}
            index={index}
          />
        ))}
      </div>
    </div>
  );
}

// List layout
function ListLayout({
  articles,
  showFeatured = true,
}: {
  articles: ArticleListItem[];
  showFeatured?: boolean;
}) {
  const featuredArticle = showFeatured ? articles.find((a) => a.featured) : null;
  const regularArticles = featuredArticle
    ? articles.filter((a) => a.id !== featuredArticle.id)
    : articles;

  return (
    <div className="space-y-8">
      {/* Featured article */}
      {featuredArticle && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <FeaturedCard article={featuredArticle} index={0} />
        </motion.div>
      )}

      {/* List */}
      <div className="space-y-6">
        {regularArticles.map((article, index) => (
          <ArticleCard
            key={article.id}
            article={article}
            index={index}
            variant="horizontal"
          />
        ))}
      </div>
    </div>
  );
}

// Main ArticleGrid component
export function ArticleGrid({
  articles,
  variant = 'masonry',
  columns = 3,
  showFeatured = true,
  className,
}: ArticleGridProps) {
  if (articles.length === 0) {
    return (
      <div className={cn('text-center py-12', className)}>
        <p className="text-white/50">No articles found</p>
      </div>
    );
  }

  return (
    <div className={className}>
      {variant === 'masonry' && (
        <MasonryGrid articles={articles} showFeatured={showFeatured} />
      )}
      {variant === 'grid' && (
        <StandardGrid
          articles={articles}
          columns={columns}
          showFeatured={showFeatured}
        />
      )}
      {variant === 'list' && (
        <ListLayout articles={articles} showFeatured={showFeatured} />
      )}
    </div>
  );
}

// Skeleton loader for ArticleGrid
export function ArticleGridSkeleton({
  count = 6,
  variant = 'grid',
}: {
  count?: number;
  variant?: 'masonry' | 'grid' | 'list';
}) {
  const items = Array.from({ length: count }, (_, i) => i);

  if (variant === 'list') {
    return (
      <div className="space-y-6">
        {items.map((i) => (
          <div key={i} className="flex gap-6 animate-pulse">
            <div className="w-48 aspect-[4/3] bg-white/5 rounded-xl" />
            <div className="flex-1 space-y-3">
              <div className="h-4 w-20 bg-white/5 rounded" />
              <div className="h-6 w-3/4 bg-white/5 rounded" />
              <div className="h-4 w-full bg-white/5 rounded" />
              <div className="h-4 w-2/3 bg-white/5 rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8">
      {items.map((i) => (
        <div key={i} className="animate-pulse">
          <div className="aspect-[16/10] bg-white/5 rounded-xl mb-4" />
          <div className="h-4 w-20 bg-white/5 rounded mb-2" />
          <div className="h-6 w-full bg-white/5 rounded mb-2" />
          <div className="h-4 w-3/4 bg-white/5 rounded mb-3" />
          <div className="h-4 w-1/2 bg-white/5 rounded" />
        </div>
      ))}
    </div>
  );
}

export { MasonryGrid, StandardGrid, ListLayout };
