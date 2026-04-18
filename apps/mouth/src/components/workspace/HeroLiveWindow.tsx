"use client";

import React, { useEffect, useRef, useState } from "react";
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

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export function HeroLiveWindow() {
  const { data } = useSWR<{ articles?: HeroArticle[] }>(
    "/api/blog/homepage-hero",
    fetcher,
    { refreshInterval: 5 * 60 * 1000 },
  );

  const articles: (HeroArticle | undefined)[] =
    data?.articles?.slice(0, 5) ?? Array(4).fill(undefined);

  const [current, setCurrent] = useState(0);
  const [leaving, setLeaving] = useState<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function goTo(n: number) {
    if (n === current || articles.length === 0) return;
    setLeaving(current);
    setCurrent(n);
    setTimeout(() => setLeaving(null), 850);
  }

  function startTimer() {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setCurrent((prev) => {
        const next = (prev + 1) % articles.length;
        setLeaving(prev);
        setTimeout(() => setLeaving(null), 850);
        return next;
      });
    }, 5000);
  }

  useEffect(() => {
    startTimer();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [articles.length]);

  const article = articles[current];
  const rawHref =
    article?.href ||
    (article
      ? `https://balizero.com/articles/${article.category}/${article.slug}`
      : "#");
  const href = rawHref.startsWith("/")
    ? `https://balizero.com${rawHref}`
    : rawHref;

  return (
    <div className="group relative mb-2" style={{ height: 420 }}>
      {/* Slides */}
      {articles.map((a, i) => {
        const isActive = i === current;
        const isLeaving = i === leaving;
        if (!isActive && !isLeaving) return null;
        const slideHref =
          a?.href ||
          (a ? `https://balizero.com/articles/${a.category}/${a.slug}` : "#");
        const finalHref = slideHref.startsWith("/")
          ? `https://balizero.com${slideHref}`
          : slideHref;

        return (
          <a
            key={i}
            href={a ? finalHref : undefined}
            target={a ? "_blank" : undefined}
            rel={a ? "noopener noreferrer" : undefined}
            className="absolute inset-0 block overflow-hidden"
            style={{
              borderRadius: "14px",
              background: CARD_GRADIENTS[i % CARD_GRADIENTS.length],
              boxShadow:
                "0 4px 32px rgba(0,0,0,0.7), inset 0 0 0 1px rgba(255,255,255,0.09)",
              border: "1px solid rgba(255,255,255,0.07)",
              opacity: isLeaving ? 0 : 1,
              transform: isLeaving
                ? "scale(1.015)"
                : isActive
                  ? "scale(1)"
                  : "scale(0.985)",
              transition:
                "opacity 850ms cubic-bezier(0.4,0,0.2,1), transform 850ms cubic-bezier(0.4,0,0.2,1)",
              zIndex: isActive ? 1 : 0,
              pointerEvents: isLeaving ? "none" : "auto",
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

            {/* Highlight */}
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
            {a?.cover_image && (
              <div
                className="absolute inset-0 bg-cover bg-center"
                style={{
                  backgroundImage: `url(${a.cover_image})`,
                  opacity: 0.68,
                  transition: "opacity 850ms ease",
                }}
              />
            )}

            {/* Gradient overlay */}
            <div
              className="absolute inset-0"
              style={{
                background:
                  "linear-gradient(to top, rgba(0,0,0,0.96) 0%, rgba(0,0,0,0.3) 55%, transparent 100%)",
              }}
            />

            {/* Content */}
            <div
              className="absolute bottom-0 left-0 right-0"
              style={{ padding: "20px 24px" }}
            >
              {a?.category && (
                <span
                  className="block font-bold uppercase tracking-[1.5px] mb-1.5"
                  style={{ fontSize: 9, color: "var(--bz-accent-warm)" }}
                >
                  {a.category}
                </span>
              )}
              {a?.title ? (
                <div
                  style={{
                    fontSize: 20,
                    fontWeight: 700,
                    lineHeight: 1.3,
                    color: "rgba(237,234,228,0.94)",
                    maxWidth: "70%",
                  }}
                >
                  {a.title}
                </div>
              ) : (
                <>
                  <div
                    className="h-4 rounded animate-pulse mb-2"
                    style={{
                      background: "rgba(255,255,255,0.06)",
                      width: "55%",
                    }}
                  />
                  <div
                    className="h-4 rounded animate-pulse"
                    style={{
                      background: "rgba(255,255,255,0.04)",
                      width: "38%",
                    }}
                  />
                </>
              )}
            </div>
          </a>
        );
      })}

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

      {/* Edit hint */}
      <Link
        href="/intelligence/news-room"
        className="absolute top-3 left-3 z-20 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9.5px] font-medium opacity-0 group-hover:opacity-100 transition-opacity"
        style={{
          background: "rgba(10,10,12,0.72)",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(255,255,255,0.08)",
          color: "var(--bz-text-2)",
        }}
      >
        ✎ Edit homepage layout
      </Link>

      {/* Dots navigation */}
      <div
        role="tablist"
        aria-label="Live homepage articles"
        className="absolute bottom-5 right-6 z-20 flex items-center gap-2"
        onClick={(e) => e.preventDefault()}
      >
        {articles.map((_, i) => (
          <button
            key={i}
            role="tab"
            aria-selected={i === current}
            aria-label={`Go to article ${i + 1} of ${articles.length}`}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              goTo(i);
              startTimer();
            }}
            style={{
              width: i === current ? 20 : 6,
              height: 6,
              borderRadius: 3,
              background:
                i === current
                  ? "rgba(212,132,90,0.9)"
                  : "rgba(255,255,255,0.25)",
              border: "none",
              cursor: "pointer",
              padding: 0,
              transition: "width 300ms ease, background 300ms ease",
            }}
          />
        ))}
      </div>

      {/* Article counter */}
      <div
        className="absolute bottom-5 left-6 z-20 text-[9px] font-semibold tabular-nums"
        style={{ color: "rgba(255,255,255,0.3)" }}
      >
        {current + 1} / {articles.filter(Boolean).length || "—"}
      </div>
    </div>
  );
}
