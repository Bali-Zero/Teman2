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
  LayoutGrid,
  Newspaper,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useR19 } from "@/components/r19/R19Presentation";
import type { ArticleCategory, CategoryNavProps } from "@/lib/blog/types";

// Category icons mapping
const categoryIcons: Record<ArticleCategory | "all", React.ElementType> = {
  all: LayoutGrid,
  visas: Plane,
  business: Building2,
  taxes: Scale,
  property: Home,
  living: Sun,
  trends: Cpu,
};

// Category labels
const categoryLabels: Record<ArticleCategory | "all", string> = {
  all: "All",
  visas: "Visas",
  business: "Business",
  taxes: "Taxes",
  property: "Property",
  living: "Living",
  trends: "Trends",
};

// Category colors (pre-R19 surfaces: SearchBar's dark filter panel, /v2)
const categoryColors: Record<
  ArticleCategory | "all",
  {
    active: string;
    inactive: string;
    gradient: string;
  }
> = {
  all: {
    active: "bg-white/10 text-white",
    inactive: "text-white/50 hover:text-white/80 hover:bg-white/5",
    gradient: "from-white/20 to-white/10",
  },
  visas: {
    active: "bg-cyan-500/20 text-cyan-400",
    inactive: "text-white/50 hover:text-cyan-400 hover:bg-cyan-500/10",
    gradient: "from-blue-500/20 to-cyan-500/20",
  },
  business: {
    active: "bg-emerald-500/20 text-emerald-400",
    inactive: "text-white/50 hover:text-emerald-400 hover:bg-emerald-500/10",
    gradient: "from-emerald-500/20 to-teal-500/20",
  },
  taxes: {
    active: "bg-amber-500/20 text-amber-400",
    inactive: "text-white/50 hover:text-amber-400 hover:bg-amber-500/10",
    gradient: "from-amber-500/20 to-orange-500/20",
  },
  property: {
    active: "bg-rose-500/20 text-rose-400",
    inactive: "text-white/50 hover:text-rose-400 hover:bg-rose-500/10",
    gradient: "from-rose-500/20 to-pink-500/20",
  },
  living: {
    active: "bg-violet-500/20 text-violet-400",
    inactive: "text-white/50 hover:text-violet-400 hover:bg-violet-500/10",
    gradient: "from-violet-500/20 to-purple-500/20",
  },
  trends: {
    active: "bg-blue-500/20 text-blue-400",
    inactive: "text-white/50 hover:text-blue-400 hover:bg-blue-500/10",
    gradient: "from-indigo-500/20 to-blue-500/20",
  },
};

// All categories list
const ALL_CATEGORIES: (ArticleCategory | "all")[] = [
  "all",
  "visas",
  "business",
  "taxes",
  "property",
  "living",
  "trends",
];

/**
 * R19 pill: transparent surface, hairline border, ink/muted text, copper
 * active state. Only active on R19 routes — SearchBar's dark filter panel
 * (`/v2`, not an R19 route) keeps the pre-R19 dark pill classes above via
 * `categoryColors`, since that surface has no `--r19-*` tokens to read.
 */
function r19PillStyle(isActive: boolean): React.CSSProperties {
  return {
    color: isActive ? "var(--r19-ink)" : "var(--r19-muted)",
    background: isActive ? "var(--r19-active-bg)" : "transparent",
    borderColor: isActive ? "var(--r19-active-border)" : "var(--r19-line)",
  };
}

export function CategoryNav({
  categories = ALL_CATEGORIES.filter((c) => c !== "all") as ArticleCategory[],
  activeCategory,
  onCategoryChange,
  showCounts = false,
  categoryCounts,
  className,
}: CategoryNavProps) {
  const isR19 = useR19();
  const allCategories: (ArticleCategory | "all")[] = ["all", ...categories];

  return (
    <nav className={cn("relative", className)}>
      {/* Scrollable container */}
      <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
        {allCategories.map((category) => {
          const Icon = categoryIcons[category];
          const isActive =
            category === "all" ? !activeCategory : activeCategory === category;
          const colors = categoryColors[category];
          const count =
            category === "all"
              ? Object.values(categoryCounts || {}).reduce((a, b) => a + b, 0)
              : categoryCounts?.[category as ArticleCategory];

          return (
            <motion.button
              key={category}
              onClick={() => {
                if (category === "all") {
                  onCategoryChange?.(undefined);
                } else {
                  onCategoryChange?.(category as ArticleCategory);
                }
              }}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "relative flex min-h-11 items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all whitespace-nowrap",
                isR19 ? "border" : isActive ? colors.active : colors.inactive,
              )}
              style={isR19 ? r19PillStyle(isActive) : undefined}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              <Icon className="w-4 h-4" />
              <span>{categoryLabels[category]}</span>
              {showCounts && count !== undefined && (
                <span className="ml-1 text-xs opacity-60">({count})</span>
              )}

              {/* Active indicator (pre-R19 only — the R19 pill paints its own
                  background/border directly above, no extra layer needed) */}
              {isActive && !isR19 && (
                <motion.div
                  layoutId="activeCategoryIndicator"
                  className={cn(
                    "absolute inset-0 rounded-full bg-gradient-to-r -z-10",
                    colors.gradient,
                  )}
                  initial={false}
                  transition={{ type: "spring", stiffness: 500, damping: 30 }}
                />
              )}
            </motion.button>
          );
        })}
      </div>

      {/* Fade edge for scroll (pre-R19 only — flat R19 surfaces skip it) */}
      {!isR19 && (
        <div className="absolute right-0 top-0 bottom-2 w-12 bg-gradient-to-l from-black to-transparent pointer-events-none md:hidden" />
      )}
    </nav>
  );
}

// Compact version for sidebars
export function CategoryNavCompact({
  categories = ALL_CATEGORIES.filter((c) => c !== "all") as ArticleCategory[],
  activeCategory,
  onCategoryChange,
  showCounts = false,
  categoryCounts,
  className,
}: CategoryNavProps) {
  return (
    <div className={cn("space-y-1", className)}>
      {/* All button */}
      <button
        onClick={() => onCategoryChange?.(undefined)}
        className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-colors"
        style={{
          color: !activeCategory ? "var(--r19-ink)" : "var(--r19-muted)",
          background: !activeCategory ? "var(--r19-active-bg)" : "transparent",
        }}
      >
        <div className="flex items-center gap-2">
          <LayoutGrid className="w-4 h-4" />
          <span>All Categories</span>
        </div>
        {showCounts && (
          <span className="text-xs opacity-60">
            {Object.values(categoryCounts || {}).reduce((a, b) => a + b, 0)}
          </span>
        )}
      </button>

      {/* Category buttons */}
      {categories.map((category) => {
        const Icon = categoryIcons[category];
        const isActive = activeCategory === category;
        const count = categoryCounts?.[category];

        return (
          <button
            key={category}
            onClick={() => onCategoryChange?.(category)}
            className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            style={{
              color: isActive ? "var(--r19-ink)" : "var(--r19-muted)",
              background: isActive ? "var(--r19-active-bg)" : "transparent",
            }}
          >
            <div className="flex items-center gap-2">
              <Icon className="w-4 h-4" />
              <span>{categoryLabels[category]}</span>
            </div>
            {showCounts && count !== undefined && (
              <span className="text-xs opacity-60">{count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// Category chip for article tags
export function CategoryChip({
  category,
  size = "md",
  className,
}: {
  category: ArticleCategory;
  size?: "sm" | "md";
  className?: string;
}) {
  const Icon = categoryIcons[category];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-medium border",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm",
        className,
      )}
      style={{ color: "var(--r19-copper)", borderColor: "var(--r19-line)" }}
    >
      <Icon className={size === "sm" ? "w-3 h-3" : "w-4 h-4"} />
      {categoryLabels[category]}
    </span>
  );
}

export { categoryIcons, categoryLabels, categoryColors, ALL_CATEGORIES };
