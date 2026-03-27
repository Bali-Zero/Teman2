'use client';

import * as React from 'react';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { Plane, Building2, Scale, Home, Sun, Cpu, Newspaper } from 'lucide-react';
import {
  ArticleGrid,
  ArticleGridSkeleton,
  CategoryNav,
  NewsletterSidebar,
} from '@/components/blog';
import type { ArticleCategory, ArticleListItem } from '@/lib/blog/types';
import { logger } from '@/lib/logger';
import { useTranslation } from '@/i18n';

// Category visual metadata (non-translated)
const CATEGORY_VISUAL: Record<
  ArticleCategory,
  {
    icon: React.ElementType;
    gradient: string;
    titleKey: string;
    descKey: string;
  }
> = {
  visas: {
    icon: Plane,
    gradient: 'from-blue-500/20 via-cyan-500/10 to-transparent',
    titleKey: 'news.categories.visas',
    descKey: 'news.categoryDescriptions.visas',
  },
  business: {
    icon: Building2,
    gradient: 'from-emerald-500/20 via-teal-500/10 to-transparent',
    titleKey: 'news.categories.business',
    descKey: 'news.categoryDescriptions.business',
  },
  taxes: {
    icon: Scale,
    gradient: 'from-amber-500/20 via-orange-500/10 to-transparent',
    titleKey: 'news.categories.taxes',
    descKey: 'news.categoryDescriptions.taxes',
  },
  property: {
    icon: Home,
    gradient: 'from-rose-500/20 via-pink-500/10 to-transparent',
    titleKey: 'news.categories.property',
    descKey: 'news.categoryDescriptions.property',
  },
  living: {
    icon: Sun,
    gradient: 'from-violet-500/20 via-purple-500/10 to-transparent',
    titleKey: 'news.categories.living',
    descKey: 'news.categoryDescriptions.living',
  },
  trends: {
    icon: Cpu,
    gradient: 'from-fuchsia-500/20 via-pink-500/10 to-transparent',
    titleKey: 'news.categories.trends',
    descKey: 'news.categoryDescriptions.trends',
  },
};

export default function CategoryPage() {
  const params = useParams();
  const category = (params?.category ?? '') as ArticleCategory;
  const [articles, setArticles] = React.useState<ArticleListItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const { t } = useTranslation();

  // Reserved workspace paths - redirect to workspace if accessed
  const RESERVED_PATHS = [
    'cases',
    'clients',
    'dashboard',
    'documents',
    'knowledge',
    'team',
    'analytics',
    'intelligence',
    'whatsapp',
    'email',
    'chat',
  ];

  React.useEffect(() => {
    if (RESERVED_PATHS.includes(category)) {
      window.location.href = `/${category}`;
    }
  }, [category]);

  const visual = CATEGORY_VISUAL[category];
  const Icon = visual?.icon || Plane;

  // Fetch articles for category
  React.useEffect(() => {
    async function fetchArticles() {
      setLoading(true);
      try {
        const response = await fetch(
          `/api/blog/articles?category=${category}&status=published&limit=20`
        );
        if (response.ok) {
          const data = await response.json();
          setArticles(data.articles || []);
        }
      } catch (error) {
        logger.error(
          'Failed to fetch articles',
          {},
          error instanceof Error ? error : new Error(String(error))
        );
      } finally {
        setLoading(false);
      }
    }

    if (category && visual) {
      fetchArticles();
    }
  }, [category, visual]);

  // Handle invalid category
  if (!visual) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-white mb-4">Category not found</h1>
          <a href="/insights" className="text-violet-400 hover:text-violet-300">
            Back to Insights
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Hero section */}
      <section className={`relative py-16 md:py-20 bg-gradient-to-b ${visual.gradient}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            {/* Icon */}
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-white/5 border border-white/10 mb-6">
              <Icon className="w-8 h-8 text-white" />
            </div>

            {/* Title */}
            <h1 className="font-serif text-4xl md:text-5xl font-bold text-white mb-4">
              {t(visual.titleKey)}
            </h1>

            {/* Description */}
            <p className="text-lg text-white/60 max-w-2xl mb-8">{t(visual.descKey)}</p>

            {/* Category nav */}
            <CategoryNav
              activeCategory={category}
              onCategoryChange={(cat) => {
                if (cat) {
                  window.location.href = `/insights/${cat}`;
                } else {
                  window.location.href = '/insights';
                }
              }}
            />
          </motion.div>
        </div>
      </section>

      {/* Content section */}
      <section className="py-12 md:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 lg:gap-12">
            {/* Main content */}
            <div className="lg:col-span-3">
              {loading ? (
                <ArticleGridSkeleton count={6} />
              ) : articles.length > 0 ? (
                <ArticleGrid articles={articles} variant="grid" columns={2} showFeatured={true} />
              ) : (
                <div className="text-center py-12">
                  <p className="text-white/50">No articles in this category yet.</p>
                </div>
              )}
            </div>

            {/* Sidebar */}
            <div className="lg:col-span-1 space-y-8">
              {/* Newsletter */}
              <NewsletterSidebar defaultCategories={[category]} />

              {/* Popular in category */}
              <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
                <h3 className="font-medium text-white mb-4">Popular in {t(visual.titleKey)}</h3>
                <div className="space-y-4">
                  {articles.slice(0, 3).map((article) => (
                    <a
                      key={article.id}
                      href={`/insights/${article.category}/${article.slug}`}
                      className="block group"
                    >
                      <h4 className="text-sm text-white/80 group-hover:text-violet-400 transition-colors line-clamp-2">
                        {article.title}
                      </h4>
                      <p className="text-xs text-white/40 mt-1">
                        {article.viewCount.toLocaleString('en-US')} views
                      </p>
                    </a>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
