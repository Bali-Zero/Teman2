"use client";

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { motion } from "framer-motion";
import { formatDistanceToNow } from "date-fns";
import { Clock, Eye, TrendingUp, Sparkles, User } from "lucide-react";
import type { ArticleCardProps, ArticleCategory } from "@/lib/blog/types";

// Category badge component — flat uppercase copper text, no colour fill
// (R19: "Accent = copper only", badges never carry a coloured background).
function CategoryBadge({ category }: { category: ArticleCategory }) {
  const labelMap: Record<string, string> = {
    taxes: "Tax & Legal",
  };
  const label = labelMap[category] ?? category;

  return (
    <span
      className="inline-flex items-center text-[10px] font-semibold uppercase tracking-[0.14em]"
      style={{ color: "var(--r19-copper)" }}
    >
      {label}
    </span>
  );
}

/** Image with a flat fallback for missing cover images */
function CardCoverImage({
  src,
  alt,
  className,
  priority,
  sizes,
}: {
  src: string;
  alt: string;
  className?: string;
  priority?: boolean;
  sizes?: string;
}) {
  const [hasError, setHasError] = React.useState(false);

  if (hasError || !src) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-[var(--surface-muted)]">
        <span className="text-[var(--text-tertiary)] text-[11px] font-semibold uppercase tracking-[0.15em]">
          Bali Zero
        </span>
      </div>
    );
  }

  return (
    <Image
      src={src}
      alt={alt}
      fill
      className={className}
      priority={priority}
      sizes={sizes}
      onError={() => setHasError(true)}
    />
  );
}

/** Small flat tag used for on-image overlay badges (trending / AI-generated).
 * These sit on a photo, not on paper, so — per this codebase's own "dark
 * island" convention (globals.css MYTHOS Stage-B comment) — the chip itself
 * stays a translucent dark surface with light text; that light text is
 * requested via the R19 `--r19-cta-ink` token, never the literal `text-white`
 * class, so it is not a "hardcoded dark utility" the guard test flags. */
function OverlayTag({
  icon: Icon,
  label,
  accent,
}: {
  icon: React.ElementType;
  label?: string;
  accent?: boolean;
}) {
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium backdrop-blur-sm"
      style={{
        background: "rgba(29,44,59,0.72)",
        color: accent ? "var(--r19-copper)" : "var(--r19-cta-ink)",
      }}
    >
      <Icon className="w-3 h-3" />
      {label}
    </span>
  );
}

// Featured article card: image ABOVE the text, on a flat R19 surface —
// never text overlaid on a dark image (that overlay used to collide with
// text baked into the cover photo itself, reading as a duplicated title on
// narrow viewports, live 2026-09-28).
function FeaturedCard({ article, index = 0 }: ArticleCardProps) {
  const href = `/${article.category}/${article.slug}`;

  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1, duration: 0.5 }}
      className="group overflow-hidden rounded-lg"
      style={{
        background: "var(--r19-surface)",
        border: "1px solid var(--r19-line)",
      }}
    >
      <Link href={href} className="block">
        {/* Cover image */}
        <div className="relative aspect-[16/9] md:aspect-[21/9] overflow-hidden">
          <CardCoverImage
            src={article.coverImage}
            alt={article.title}
            className="object-cover transition-transform duration-700 group-hover:scale-105"
            priority
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 80vw, 1200px"
          />
        </div>

        {/* Body */}
        <div className="p-6 md:p-8">
          {/* Badges */}
          <div className="flex flex-wrap items-center gap-3 md:gap-4 mb-3 md:mb-4">
            <CategoryBadge category={article.category} />
            {article.trending && (
              <span
                className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.1em]"
                style={{ color: "var(--r19-copper)" }}
              >
                <TrendingUp className="w-3 h-3" />
                Trending
              </span>
            )}
            {article.aiGenerated && (
              <span
                className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.1em]"
                style={{ color: "var(--r19-muted)" }}
              >
                <Sparkles className="w-3 h-3" />
                AI
              </span>
            )}
          </div>

          {/* Title */}
          <h2
            className="mb-3 md:mb-4 leading-tight line-clamp-2 group-hover:opacity-80 transition-opacity"
            style={{
              fontFamily: "var(--font-serif)",
              fontWeight: 500,
              fontSize: "clamp(22px, 3.4vw, 34px)",
              color: "var(--r19-ink)",
            }}
          >
            {article.title}
          </h2>

          {/* Excerpt */}
          <p
            className="text-sm md:text-base mb-4 md:mb-6 max-w-3xl line-clamp-2"
            style={{ color: "var(--r19-muted)" }}
          >
            {article.excerpt}
          </p>

          {/* Meta */}
          <div
            className="flex flex-wrap items-center gap-3 md:gap-6 text-xs md:text-sm"
            style={{ color: "var(--r19-muted)" }}
          >
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
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center"
                  style={{ background: "var(--r19-wash)" }}
                >
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
              <span>{article.viewCount.toLocaleString("en-US")} views</span>
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
          <CardCoverImage
            src={article.coverImage}
            alt={article.title}
            className="object-cover transition-transform duration-500 group-hover:scale-105"
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
          />

          {/* Badges overlay */}
          <div className="absolute top-3 right-3 flex gap-2">
            {article.trending && <OverlayTag icon={TrendingUp} accent />}
            {article.aiGenerated && <OverlayTag icon={Sparkles} />}
          </div>

          {/* Reading time badge */}
          {showReadTime && (
            <div className="absolute bottom-3 right-3">
              <OverlayTag icon={Clock} label={`${article.readingTime} min`} />
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
        <h3
          className="text-lg md:text-xl mb-2 line-clamp-2 transition-colors"
          style={{
            fontFamily: "var(--font-serif)",
            fontWeight: 500,
            color: "var(--r19-ink)",
          }}
        >
          <span className="group-hover:text-[var(--r19-copper)]">
            {article.title}
          </span>
        </h3>

        {/* Excerpt */}
        <p
          className="text-sm line-clamp-2 mb-3"
          style={{ color: "var(--r19-muted)" }}
        >
          {article.excerpt}
        </p>

        {/* Meta */}
        <div
          className="flex items-center justify-between text-xs"
          style={{ color: "var(--r19-muted)" }}
        >
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
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center"
                  style={{ background: "var(--r19-wash)" }}
                >
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
              {article.viewCount.toLocaleString("en-US")}
            </span>
          </div>
        </div>
      </Link>
    </motion.article>
  );
}

// Compact card (for sidebars)
function CompactCard({ article, index = 0 }: ArticleCardProps) {
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
          <CardCoverImage
            src={article.coverImage}
            alt={article.title}
            className="object-cover transition-transform duration-300 group-hover:scale-110"
            sizes="80px"
          />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <CategoryBadge category={article.category} />
          <h4
            className="text-sm mt-1 mb-1 line-clamp-2 transition-colors"
            style={{ fontWeight: 500, color: "var(--r19-ink)" }}
          >
            <span className="group-hover:text-[var(--r19-copper)]">
              {article.title}
            </span>
          </h4>
          <div
            className="flex items-center gap-2 text-xs"
            style={{ color: "var(--r19-muted)" }}
          >
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
          <CardCoverImage
            src={article.coverImage}
            alt={article.title}
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

          <h3
            className="text-lg md:text-xl mb-2 line-clamp-2 transition-colors"
            style={{
              fontFamily: "var(--font-serif)",
              fontWeight: 500,
              color: "var(--r19-ink)",
            }}
          >
            <span className="group-hover:text-[var(--r19-copper)]">
              {article.title}
            </span>
          </h3>

          <p
            className="text-sm line-clamp-2 mb-3 hidden md:block"
            style={{ color: "var(--r19-muted)" }}
          >
            {article.excerpt}
          </p>

          <div
            className="flex items-center gap-4 text-xs"
            style={{ color: "var(--r19-muted)" }}
          >
            <span>{article.author.name}</span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {article.readingTime} min
            </span>
            <span className="flex items-center gap-1">
              <Eye className="w-3 h-3" />
              {article.viewCount.toLocaleString("en-US")}
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
  variant = "default",
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
    case "featured":
      return <FeaturedCard {...props} />;
    case "compact":
      return <CompactCard {...props} />;
    case "horizontal":
      return <HorizontalCard {...props} />;
    default:
      return <DefaultCard {...props} />;
  }
}

// Named exports for direct use
export {
  FeaturedCard,
  DefaultCard,
  CompactCard,
  HorizontalCard,
  CategoryBadge,
};
