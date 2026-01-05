'use client';

import * as React from 'react';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  Plane,
  Building2,
  Scale,
  Home,
  Sun,
  Cpu,
} from 'lucide-react';
import {
  ArticleGrid,
  ArticleGridSkeleton,
  CategoryNav,
  NewsletterSidebar,
} from '@/components/blog';
import type { ArticleCategory, ArticleListItem } from '@/lib/blog/types';

// Category metadata
const CATEGORY_META: Record<ArticleCategory, {
  title: string;
  description: string;
  icon: React.ElementType;
  gradient: string;
}> = {
  immigration: {
    title: 'Immigration',
    description: 'Visas, permits, and everything you need to know about relocating to Indonesia.',
    icon: Plane,
    gradient: 'from-blue-500/20 via-cyan-500/10 to-transparent',
  },
  business: {
    title: 'Business',
    description: 'Company setup, licensing, KBLI codes, and doing business in Indonesia.',
    icon: Building2,
    gradient: 'from-emerald-500/20 via-teal-500/10 to-transparent',
  },
  'tax-legal': {
    title: 'Tax & Legal',
    description: 'Tax obligations, legal compliance, and regulatory updates.',
    icon: Scale,
    gradient: 'from-amber-500/20 via-orange-500/10 to-transparent',
  },
  property: {
    title: 'Property',
    description: 'Real estate, property ownership, and investment opportunities in Bali.',
    icon: Home,
    gradient: 'from-rose-500/20 via-pink-500/10 to-transparent',
  },
  lifestyle: {
    title: 'Lifestyle',
    description: 'Living in Bali, culture, community, and quality of life.',
    icon: Sun,
    gradient: 'from-violet-500/20 via-purple-500/10 to-transparent',
  },
  tech: {
    title: 'Tech',
    description: 'Digital nomad life, tech industry, and remote work in Indonesia.',
    icon: Cpu,
    gradient: 'from-fuchsia-500/20 via-pink-500/10 to-transparent',
  },
};

export default function CategoryPage() {
  const params = useParams();
  const category = params.category as ArticleCategory;
  const [articles, setArticles] = React.useState<ArticleListItem[]>([]);
  const [loading, setLoading] = React.useState(true);

  // Reserved workspace paths - redirect to workspace if accessed
  const RESERVED_PATHS = ['cases', 'clients', 'dashboard', 'documents', 'knowledge', 'team', 'analytics', 'intelligence', 'whatsapp', 'email', 'chat'];

  React.useEffect(() => {
    if (RESERVED_PATHS.includes(category)) {
      window.location.href = `/${category}`;
    }
  }, [category]);

  const meta = CATEGORY_META[category];
  const Icon = meta?.icon || Plane;

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
        console.error('Failed to fetch articles:', error);
      } finally {
        setLoading(false);
      }
    }

    if (category && meta) {
      fetchArticles();
    }
  }, [category, meta]);

  // Handle invalid category
  if (!meta) {
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
      <section className={`relative py-16 md:py-20 bg-gradient-to-b ${meta.gradient}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {/* Icon */}
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-white/5 border border-white/10 mb-6">
              <Icon className="w-8 h-8 text-white" />
            </div>

            {/* Title */}
            <h1 className="font-serif text-4xl md:text-5xl font-bold text-white mb-4">
              {meta.title}
            </h1>

            {/* Description */}
            <p className="text-lg text-white/60 max-w-2xl mb-8">
              {meta.description}
            </p>

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
                <ArticleGrid
                  articles={articles}
                  variant="grid"
                  columns={2}
                  showFeatured={true}
                />
              ) : (
                <div className="text-center py-12">
                  <p className="text-white/50">No articles in this category yet.</p>
                </div>
              )}
            </div>

            {/* Sidebar */}
            <div className="lg:col-span-1 space-y-8">
              {/* Newsletter */}
              <NewsletterSidebar
                defaultCategories={[category]}
              />

              {/* Popular in category */}
              <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
                <h3 className="font-medium text-white mb-4">
                  Popular in {meta.title}
                </h3>
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
                        {article.viewCount.toLocaleString()} views
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
