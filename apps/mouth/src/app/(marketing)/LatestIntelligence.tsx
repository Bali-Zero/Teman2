"use client";

import { useEffect, useState } from "react";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "https://nuzantara-rag.fly.dev";

const CATEGORY_LABELS: Record<string, string> = {
  visas: "VISAS",
  business: "BUSINESS",
  taxes: "TAXES",
  property: "PROPERTY",
  living: "LIVING",
  trends: "TRENDS",
};

interface Article {
  id: string;
  slug: string;
  title: string;
  excerpt: string;
  coverImage: string;
  category: string;
  readingTime: number;
  viewCount: number;
}

function cleanExcerpt(text: string | null): string {
  if (!text) return "";
  return text
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/\[(.*?)\]\(.*?\)/g, "$1")
    .replace(/`(.*?)`/g, "$1")
    .trim();
}

export function LatestIntelligence() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/news?status=approved&limit=5`)
      .then((r) => r.json())
      .then((data) => {
        const items = (data.data || []).slice(0, 5).map(
          (item: {
            id: string;
            slug: string;
            title: string;
            summary: string | null;
            ai_summary: string | null;
            image_url: string | null;
            category: string;
            content: string | null;
            view_count: number;
          }) => ({
            id: item.id,
            slug: item.slug,
            title: item.title,
            excerpt: cleanExcerpt(item.summary || item.ai_summary),
            coverImage:
              item.image_url ||
              `/static/blog/${item.category || "business"}-cover.jpg`,
            category: item.category || "business",
            readingTime: item.content
              ? Math.ceil(item.content.split(/\s+/).length / 200)
              : 5,
            viewCount: item.view_count || 0,
          }),
        );
        setArticles(items);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="glass-section">
        <div className="section-header">
          <h2 className="section-title">Latest Intelligence</h2>
          <a href="/news" className="section-link">
            View all →
          </a>
        </div>
        <div className="li-grid">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className={`li-card${i === 0 ? " li-featured" : i >= 3 ? " li-compact" : ""}`}
              style={{ background: "rgba(255,255,255,0.03)" }}
            >
              <div className="li-img-wrap" style={{ background: "rgba(255,255,255,0.05)" }} />
              <div className="li-body">
                <div style={{ height: 8, width: "40%", background: "rgba(255,255,255,0.08)", borderRadius: 4, marginBottom: 8 }} />
                <div style={{ height: 14, width: "80%", background: "rgba(255,255,255,0.06)", borderRadius: 4, marginBottom: 6 }} />
                <div style={{ height: 14, width: "60%", background: "rgba(255,255,255,0.04)", borderRadius: 4 }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (articles.length === 0) return null;

  return (
    <div className="glass-section">
      <div className="section-header">
        <h2 className="section-title">Latest Intelligence</h2>
        <a href="/news" className="section-link">
          View all →
        </a>
      </div>
      <div className="li-grid">
        {articles.map((article, i) => (
          <a
            key={article.id}
            href={`/news/${article.slug}`}
            className={`li-card${i === 0 ? " li-featured" : i >= 3 ? " li-compact" : ""}`}
          >
            <div className="li-img-wrap">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={article.coverImage}
                alt={article.title}
                style={{
                  position: "absolute",
                  inset: 0,
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                }}
              />
              <div className="li-img-grad" />
              {i === 0 && (
                <span className="li-badge">Latest Intelligence</span>
              )}
            </div>
            <div className="li-body">
              <span className="li-cat">
                {CATEGORY_LABELS[article.category] ??
                  article.category.toUpperCase()}
              </span>
              <h3 className="li-title">{article.title}</h3>
              {i < 3 && article.excerpt && (
                <p className="li-desc">{article.excerpt}</p>
              )}
              <span className="li-meta">
                {article.readingTime} min read · {article.viewCount} views
              </span>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
