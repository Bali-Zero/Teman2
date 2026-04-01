"use client";

import React from "react";
import Link from "next/link";
import useSWR from "swr";

interface HeroArticle {
  slug: string;
  title: string;
  category?: string;
  cover_image?: string;
  href?: string;
}

const CARD_GRADIENTS = [
  "linear-gradient(160deg, #3d1f08 0%, #5c2f10 40%, #0a0806 100%)",
  "linear-gradient(160deg, #07132a 0%, #0e2040 50%, #060e1a 100%)",
  "linear-gradient(160deg, #0e2410 0%, #183820 50%, #080f09 100%)",
  "linear-gradient(160deg, #250a14 0%, #3d1020 50%, #120408 100%)",
  "linear-gradient(160deg, #1c1a06 0%, #302e10 50%, #0c0b02 100%)",
];

// Each card has its own border-radius for liquid asymmetry
const CARD_RADII = [
  "14px 6px 18px 8px",   // hero1 main — asimmetrico
  "8px 16px 6px 20px",   // hero2
  "18px 8px 12px 6px",   // hero3
  "6px 20px 8px 14px",   // hero4
];

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export function HeroLiveWindow() {
  const { data } = useSWR<{ articles?: HeroArticle[] }>(
    "/api/blog/homepage-hero",
    fetcher,
    { refreshInterval: 5 * 60 * 1000 },
  );

  const articles: (HeroArticle | undefined)[] =
    data?.articles?.slice(0, 4) ?? Array(4).fill(undefined);
  const [hero1, hero2, hero3, hero4] = articles;

  return (
    <div
      className="group relative mb-2"
      style={{ height: 420 }}
    >
      {/* Live badge */}
      <div
        className="absolute top-3 right-3 z-20 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9.5px] font-semibold"
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
        className="absolute bottom-3 left-3 z-20 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9.5px] font-medium opacity-0 group-hover:opacity-100 transition-opacity"
        style={{
          background: "rgba(10,10,12,0.72)",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(255,255,255,0.08)",
          color: "var(--bz-text-2)",
        }}
      >
        ✎ Edit homepage layout
      </Link>

      {/*
        Layout asimmetrico a 4 card:
        - Colonna sinistra: hero1 piccolo (50% ridotto) in alto + spazio vuoto sotto
        - Colonna destra: hero2 (tall, +15%) + hero3 + hero4 impilati
        - Gap variabile, bordi non allineati
      */}
      <div
        className="absolute inset-0"
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1.1fr",
          gridTemplateRows: "1fr 1fr 1fr",
          gap: "0",
          padding: "0",
        }}
      >
        {/* Hero 1 — ridotto ~50%, occupa solo le prime 2 righe della col sinistra */}
        <div
          style={{
            gridColumn: "1",
            gridRow: "1 / 3",
            padding: "0 5px 3px 0",
          }}
        >
          <HeroCard
            article={hero1}
            gradient={CARD_GRADIENTS[0]}
            isMain
            borderRadius={CARD_RADII[0]}
          />
        </div>

        {/* Spazio sotto hero1 — vuoto con glassmorphism sottile */}
        <div
          style={{
            gridColumn: "1",
            gridRow: "3",
            padding: "3px 5px 0 0",
          }}
        >
          <div
            style={{
              height: "100%",
              borderRadius: "10px 4px 12px 6px",
              background: "rgba(255,255,255,0.015)",
              backdropFilter: "blur(8px)",
              border: "1px solid rgba(255,255,255,0.04)",
            }}
          />
        </div>

        {/* Hero 2 — più alto (+15%), occupa 2 righe */}
        <div
          style={{
            gridColumn: "2",
            gridRow: "1 / 3",
            padding: "0 0 3px 5px",
          }}
        >
          <HeroCard
            article={hero2}
            gradient={CARD_GRADIENTS[1]}
            borderRadius={CARD_RADII[1]}
            fontSize={12}
          />
        </div>

        {/* Hero 3 — piccolo, col destra riga 3 metà sinistra */}
        <div
          style={{
            gridColumn: "2",
            gridRow: "3",
            padding: "3px 0 0 5px",
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "4px",
          }}
        >
          <HeroCard
            article={hero3}
            gradient={CARD_GRADIENTS[2]}
            borderRadius={CARD_RADII[2]}
            fontSize={9}
          />
          <HeroCard
            article={hero4}
            gradient={CARD_GRADIENTS[3]}
            borderRadius={CARD_RADII[3]}
            fontSize={9}
          />
        </div>
      </div>
    </div>
  );
}

function HeroCard({
  article,
  gradient,
  isMain = false,
  borderRadius,
  fontSize,
  style,
}: {
  article?: HeroArticle;
  gradient: string;
  isMain?: boolean;
  borderRadius?: string;
  fontSize?: number;
  style?: React.CSSProperties;
}) {
  const rawHref =
    article?.href ||
    (article
      ? `https://balizero.com/articles/${article.category}/${article.slug}`
      : "#");
  const href = rawHref.startsWith("/")
    ? `https://balizero.com${rawHref}`
    : rawHref;

  const cardFontSize = fontSize ?? (isMain ? 14 : 10.5);

  return (
    <a
      href={article ? href : undefined}
      target={article ? "_blank" : undefined}
      rel={article ? "noopener noreferrer" : undefined}
      className="relative overflow-hidden block h-full"
      style={{
        ...style,
        background: gradient,
        borderRadius: borderRadius ?? "8px",
        // Liquid glassmorphism border
        boxShadow:
          "0 4px 24px rgba(0,0,0,0.6), inset 0 0 0 1px rgba(255,255,255,0.09), inset 0 1px 0 rgba(255,255,255,0.13)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(255,255,255,0.07)",
      }}
    >
      {/* Grain */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.06]"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        }}
      />

      {/* Liquid glass highlight — bordo superiore luminoso */}
      <div
        className="absolute inset-x-0 top-0 pointer-events-none"
        style={{
          height: "40%",
          background:
            "linear-gradient(to bottom, rgba(255,255,255,0.06) 0%, transparent 100%)",
          borderRadius: "inherit",
        }}
      />

      {/* Cover image */}
      {article?.cover_image && (
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage: `url(${article.cover_image})`,
            opacity: 0.62,
          }}
        />
      )}

      {/* Gradient overlay */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(to top, rgba(0,0,0,0.94) 0%, rgba(0,0,0,0.25) 55%, transparent 100%)",
        }}
      />

      {/* Content */}
      <div
        className="absolute bottom-0 left-0 right-0"
        style={{ padding: isMain ? "12px 14px" : "8px 10px" }}
      >
        {article?.category && (
          <span
            className="block font-bold uppercase tracking-[1px] mb-0.5"
            style={{
              fontSize: isMain ? 8.5 : 7,
              color: "var(--bz-accent-warm)",
            }}
          >
            {article.category}
          </span>
        )}
        {article?.title && (
          <div
            style={{
              fontSize: cardFontSize,
              fontWeight: isMain ? 700 : 600,
              lineHeight: 1.32,
              color: "rgba(237,234,228,0.92)",
            }}
          >
            {article.title}
          </div>
        )}
        {!article && (
          <div
            className="h-3 rounded animate-pulse"
            style={{ background: "rgba(255,255,255,0.06)", width: "70%" }}
          />
        )}
      </div>
    </a>
  );
}
