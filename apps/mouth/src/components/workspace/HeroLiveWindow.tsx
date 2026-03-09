"use client";

import React from "react";
import Link from "next/link";
import useSWR from "swr";

interface HeroArticle {
  slug: string;
  title: string;
  category?: string;
  cover_image?: string;
}

const CARD_GRADIENTS = [
  "linear-gradient(160deg, #3d1f08 0%, #5c2f10 40%, #0a0806 100%)",
  "linear-gradient(160deg, #07132a 0%, #0e2040 50%, #060e1a 100%)",
  "linear-gradient(160deg, #0e2410 0%, #183820 50%, #080f09 100%)",
  "linear-gradient(160deg, #250a14 0%, #3d1020 50%, #120408 100%)",
  "linear-gradient(160deg, #1c1a06 0%, #302e10 50%, #0c0b02 100%)",
];

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export function HeroLiveWindow() {
  const { data } = useSWR<{ articles?: HeroArticle[] }>(
    "/api/blog/articles?limit=5&featured=true",
    fetcher,
    { refreshInterval: 5 * 60 * 1000 }
  );

  const articles: (HeroArticle | undefined)[] = data?.articles?.slice(0, 5) ?? Array(5).fill(undefined);
  const [main, ...rest] = articles;

  return (
    <div
      className="group relative rounded-[12px] overflow-hidden mb-4"
      style={{
        height: 264,
        border: "1px solid var(--bz-border-accent)",
        boxShadow: "0 0 0 1px var(--bz-border-accent), 0 4px 24px rgba(0,0,0,0.5)",
      }}
    >
      {/* Background */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 120% 80% at 20% 50%, rgba(40,22,10,0.9) 0%, transparent 60%), radial-gradient(ellipse 80% 100% at 80% 50%, rgba(12,18,30,0.8) 0%, transparent 60%), #0c0c0e",
        }}
      />

      {/* Batik texture */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          opacity: 0.028,
          backgroundImage: "var(--bz-batik-texture)",
          backgroundSize: "20px 20px",
        }}
      />

      {/* Live badge */}
      <div
        className="absolute top-2.5 right-2.5 z-20 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9.5px] font-semibold"
        style={{
          background: "rgba(10,10,12,0.72)",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(255,255,255,0.08)",
          color: "var(--bz-text-2)",
        }}
      >
        <span
          className="w-[5px] h-[5px] rounded-full animate-pulse"
          style={{ background: "var(--bz-green)" }}
        />
        balizero.com · live
      </div>

      {/* Edit hint on hover */}
      <Link
        href="/intelligence/news-room"
        className="absolute bottom-2.5 left-2.5 z-20 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9.5px] font-medium opacity-0 group-hover:opacity-100 transition-opacity"
        style={{
          background: "rgba(10,10,12,0.72)",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(255,255,255,0.08)",
          color: "var(--bz-text-2)",
        }}
      >
        ✎ Edit homepage layout
      </Link>

      {/* Grid */}
      <div
        className="absolute inset-0 grid gap-[2px]"
        style={{
          gridTemplateColumns: "1.5fr 1fr 1fr",
          gridTemplateRows: "1fr 1fr",
          background: "rgba(0,0,0,0.3)",
        }}
      >
        <HeroCard article={main} gradient={CARD_GRADIENTS[0]} isMain style={{ gridRow: "1 / 3" }} />
        {rest.slice(0, 4).map((article, i) => (
          <HeroCard key={i} article={article} gradient={CARD_GRADIENTS[i + 1]} />
        ))}
      </div>
    </div>
  );
}

function HeroCard({
  article,
  gradient,
  isMain = false,
  style,
}: {
  article?: HeroArticle;
  gradient: string;
  isMain?: boolean;
  style?: React.CSSProperties;
}) {
  return (
    <div className="relative overflow-hidden" style={{ ...style, background: gradient }}>
      {/* Grain */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.06]"
           style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")" }} />

      {/* Cover image */}
      {article?.cover_image && (
        <div className="absolute inset-0 bg-cover bg-center"
             style={{ backgroundImage: `url(${article.cover_image})`, opacity: 0.4 }} />
      )}

      {/* Gradient overlay */}
      <div className="absolute inset-0"
           style={{ background: "linear-gradient(to top, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.3) 50%, transparent 100%)" }} />

      {/* Content */}
      <div className={`absolute bottom-0 left-0 right-0 ${isMain ? "p-3.5" : "p-2.5"}`}>
        {article?.category && (
          <span className={`block font-bold uppercase tracking-[1px] mb-1 ${isMain ? "text-[9px]" : "text-[7.5px]"}`}
                style={{ color: "var(--bz-accent-warm)" }}>
            {article.category}
          </span>
        )}
        {article?.title && (
          <div style={{
            fontSize: isMain ? 15 : 10.5,
            fontWeight: isMain ? 700 : 600,
            lineHeight: 1.35,
            color: "rgba(237,234,228,0.92)",
          }}>
            {article.title}
          </div>
        )}
        {!article && (
          <div className="h-3 rounded animate-pulse" style={{ background: "rgba(255,255,255,0.06)", width: "70%" }} />
        )}
      </div>
    </div>
  );
}
