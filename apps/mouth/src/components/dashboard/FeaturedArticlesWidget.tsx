"use client";

import React, { useEffect, useState } from "react";
import Image from "next/image";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

interface FeaturedArticle {
  id: string;
  title: string;
  category: string;
  categoryColor: string;
  imageUrl: string;
  href: string;
  isFeatured?: boolean;
}

// Fallback articles (used if API fails)
const fallbackArticles: FeaturedArticle[] = [
  {
    id: "1",
    title:
      "Suwung Landfill Closure: The Waste Crisis Hitting Bali's Tourist Zones",
    category: "LIFESTYLE",
    categoryColor: "text-red-400",
    imageUrl: "/static/news/suwung-landfill.jpg",
    href: "https://balizero.com/articles/lifestyle/suwung-landfill-crisis",
  },
  {
    id: "2",
    title:
      "Property Alert: Green Zone Crackdown and the End of Easy Villa Permits",
    category: "PROPERTY",
    categoryColor: "text-amber-400",
    imageUrl: "/static/news/property-green-zone.jpg",
    href: "https://balizero.com/articles/property/property-green-zone-alert",
  },
  {
    id: "3",
    title: "Dengue Alert 2026: 636 Cases and Rising — What Expats Need to Know",
    category: "LIFESTYLE",
    categoryColor: "text-red-400",
    imageUrl: "/static/news/dengue-alert.jpg",
    href: "https://balizero.com/articles/lifestyle/dengue-alert-2026",
  },
  {
    id: "4",
    title:
      "The 40-75% Tax Shock: What Pajak Hiburan Means for Beach Clubs and Nightlife",
    category: "TAX & LEGAL",
    categoryColor: "text-cyan-400",
    imageUrl: "/static/news/pajak-hiburan.jpg",
    href: "https://balizero.com/articles/tax-legal/pajak-hiburan-tax-shock",
  },
  {
    id: "5",
    title:
      "The Constitutional Clash: Can Bali Legally Demand Your Bank Statements?",
    category: "IMMIGRATION",
    categoryColor: "text-blue-400",
    imageUrl: "/static/news/constitutional-clash-koster.jpg",
    href: "https://balizero.com/articles/immigration/constitutional-clash-bank-statements",
    isFeatured: true,
  },
];

function ArticleCard({
  article,
  className = "",
  size = "normal",
}: {
  article: FeaturedArticle;
  className?: string;
  size?: "normal" | "large";
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

      <div
        className={`relative flex flex-col justify-end p-4 ${size === "large" ? "min-h-[400px] md:min-h-full" : "min-h-[200px]"}`}
      >
        <span
          className={`text-xs font-semibold uppercase tracking-wider ${article.categoryColor} mb-2`}
        >
          {article.category}
        </span>
        <h3
          className={`font-semibold text-white leading-tight group-hover:text-[var(--accent)] transition-colors ${
            size === "large" ? "text-xl md:text-2xl" : "text-sm md:text-base"
          }`}
        >
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
  const [articles, setArticles] = useState<FeaturedArticle[]>(fallbackArticles);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    const fetchArticles = async () => {
      try {
        const response = await api.get<{ articles: FeaturedArticle[] }>(
          "/api/dashboard/featured-articles",
        );
        if (mounted && response.articles && response.articles.length > 0) {
          setArticles(response.articles);
        }
      } catch (error) {
        logger.warn(
          "Failed to fetch featured articles, using fallback",
          {
            component: "FeaturedArticlesWidget",
            action: "fetchArticles",
          },
          error instanceof Error ? error : new Error(String(error)),
        );
        // Use fallback articles
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    };

    fetchArticles();

    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="rounded-xl border border-[#FFB347]/60 bg-[#FFB347]/25 p-6 overflow-hidden">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl md:text-3xl font-bold text-white">
          Decode Indonesia.
        </h2>
        <h2 className="text-2xl md:text-3xl font-bold">
          <span className="text-red-500">Thrive</span>{" "}
          <span className="text-white">here</span>
        </h2>
        <p className="text-gray-400 mt-2 text-sm md:text-base">
          Legal, immigration, fiscal & business intelligence for Indonesia.{" "}
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
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="animate-pulse bg-white/10 rounded-xl h-64"
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Left Column - 2 stacked articles */}
          <div className="flex flex-col gap-4">
            {articles[0] && (
              <ArticleCard article={articles[0]} className="flex-1" />
            )}
            {articles[1] && (
              <ArticleCard article={articles[1]} className="flex-1" />
            )}
          </div>

          {/* Middle Column - 2 stacked articles */}
          <div className="flex flex-col gap-4">
            {articles[2] && (
              <ArticleCard article={articles[2]} className="flex-1" />
            )}
            {articles[3] && (
              <ArticleCard article={articles[3]} className="flex-1" />
            )}
          </div>

          {/* Right Column - 1 tall featured article */}
          <div className="flex flex-col">
            {articles[4] && (
              <ArticleCard
                article={articles[4]}
                className="flex-1"
                size="large"
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default FeaturedArticlesWidget;
