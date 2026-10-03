"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  Plane,
  Building2,
  Scale,
  Home,
  Sun,
  Cpu,
  Newspaper,
} from "lucide-react";
import {
  ArticleGrid,
  ArticleGridSkeleton,
  CategoryNav,
  NewsletterSidebar,
} from "@/components/blog";
import type { ArticleCategory, ArticleListItem } from "@/lib/blog/types";
import { articleHref } from "@/lib/blog/article-href";
import { useTranslation } from "@/i18n";
import { RUMAH_VARS, RUMAH_CLASS } from "@/lib/theme/rumahVars";

// Category visual metadata (non-translated)
const CATEGORY_VISUAL: Record<
  ArticleCategory,
  {
    icon: React.ElementType;
    titleKey: string;
    descKey: string;
  }
> = {
  visas: {
    icon: Plane,
    titleKey: "news.categories.visas",
    descKey: "news.categoryDescriptions.visas",
  },
  business: {
    icon: Building2,
    titleKey: "news.categories.business",
    descKey: "news.categoryDescriptions.business",
  },
  taxes: {
    icon: Scale,
    titleKey: "news.categories.taxes",
    descKey: "news.categoryDescriptions.taxes",
  },
  property: {
    icon: Home,
    titleKey: "news.categories.property",
    descKey: "news.categoryDescriptions.property",
  },
  living: {
    icon: Sun,
    titleKey: "news.categories.living",
    descKey: "news.categoryDescriptions.living",
  },
  trends: {
    icon: Cpu,
    titleKey: "news.categories.trends",
    descKey: "news.categoryDescriptions.trends",
  },
};

interface CategoryContentProps {
  articles: ArticleListItem[];
  category: ArticleCategory;
}

export default function CategoryContent({
  articles,
  category,
}: CategoryContentProps): React.JSX.Element {
  const { t } = useTranslation();

  const visual = CATEGORY_VISUAL[category];
  const Icon = visual?.icon ?? Plane;
  const eyebrow = category.charAt(0).toUpperCase() + category.slice(1);

  // Handle invalid category (should not reach here — server notFound() guards first)
  if (!visual) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1
            className="text-2xl mb-4"
            style={{
              fontFamily: "var(--font-serif)",
              fontWeight: 500,
              color: "var(--r19-ink)",
            }}
          >
            Category not found
          </h1>
          <a
            href="/news"
            className="text-[var(--accent-funnel-text,#5c8aff)] hover:opacity-80"
          >
            Back to Insights
          </a>
        </div>
      </div>
    );
  }

  return (
    // MYTHOS Stage-B Batch 1: Rumah Putih light, scoped per-page (NEVER on
    // the shared (blog)/layout.tsx). The .rumah-putih class hooks the scoped
    // re-tint in globals.css for NewsletterSidebar's hardcoded-dark text —
    // this page's OWN markup below reads --r19-* tokens directly and no
    // longer depends on that retint (kept only for the untouched sibling).
    <div
      className={`min-h-screen ${RUMAH_CLASS}`}
      style={{
        ...RUMAH_VARS,
        background: "var(--surface-base)",
        color: "var(--text-primary)",
      }}
    >
      {/* Hero section — R19 editorial header: copper eyebrow, Fraunces h1,
          lead, hairline. No per-category gradient wash. */}
      <section
        className="relative py-14 md:py-20 border-b"
        style={{ borderColor: "var(--r19-line)" }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {/* Icon */}
            <div
              className="inline-flex items-center justify-center w-14 h-14 rounded-lg mb-6"
              style={{
                background: "var(--r19-wash)",
                border: "1px solid var(--r19-line)",
              }}
            >
              <Icon
                className="w-6 h-6"
                style={{ color: "var(--r19-copper)" }}
              />
            </div>

            {/* Eyebrow */}
            <div
              className="text-[11px] font-semibold uppercase tracking-[0.28em] mb-4"
              style={{ color: "var(--r19-copper)" }}
            >
              {eyebrow}
            </div>

            {/* Title */}
            <h1
              className="mb-4"
              style={{
                fontFamily: "var(--font-serif)",
                fontWeight: 500,
                fontSize: "clamp(30px, 4.5vw, 48px)",
                lineHeight: 1.1,
                color: "var(--r19-ink)",
              }}
            >
              {t(visual.titleKey)}
            </h1>

            {/* Description */}
            <p
              className="text-lg max-w-2xl mb-8"
              style={{ color: "var(--r19-muted)" }}
            >
              {t(visual.descKey)}
            </p>

            {/* Category nav */}
            <CategoryNav
              activeCategory={category}
              onCategoryChange={(cat) => {
                if (cat) {
                  window.location.href = `/news/${cat}`;
                } else {
                  window.location.href = "/news";
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
              {articles.length > 0 ? (
                <ArticleGrid
                  articles={articles}
                  variant="grid"
                  columns={2}
                  showFeatured={true}
                />
              ) : (
                <div className="text-center py-12">
                  <p style={{ color: "var(--r19-muted)" }}>
                    No articles in this category yet.
                  </p>
                </div>
              )}
            </div>

            {/* Sidebar */}
            <div className="lg:col-span-1 space-y-8">
              {/* Newsletter — not restyled here, out of this lane's scope */}
              <NewsletterSidebar defaultCategories={[category]} />

              {/* Popular in category */}
              <div
                className="p-6 rounded-lg"
                style={{
                  background: "var(--r19-surface)",
                  border: "1px solid var(--r19-line)",
                }}
              >
                <h3
                  className="mb-4"
                  style={{
                    fontFamily: "var(--font-serif)",
                    fontWeight: 500,
                    color: "var(--r19-ink)",
                  }}
                >
                  Popular in {t(visual.titleKey)}
                </h3>
                <div className="space-y-4">
                  {articles.slice(0, 3).map((article) => (
                    <a
                      key={article.id}
                      href={articleHref(article)}
                      className="block group"
                    >
                      <h4
                        className="text-sm line-clamp-2 transition-colors"
                        style={{ color: "var(--r19-ink)" }}
                      >
                        <span className="group-hover:text-[var(--r19-copper)]">
                          {article.title}
                        </span>
                      </h4>
                      <p
                        className="text-xs mt-1"
                        style={{ color: "var(--r19-muted)" }}
                      >
                        {article.viewCount.toLocaleString("en-US")} views
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
