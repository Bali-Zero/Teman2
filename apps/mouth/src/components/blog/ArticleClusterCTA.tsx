"use client";

import { useMemo } from "react";
import Link from "next/link";
import { findClusterBySlug, type ArticleRef } from "@/data/clusters";

interface ArticleClusterCTAProps {
  /** Slug of the currently rendered article (pillar or spoke). */
  slug: string;
}

/**
 * Picks up to `count` random items from `arr`.
 * Uses a seeded-enough shuffle to avoid hydration mismatches when wrapped
 * in useMemo (the result stabilises after the first render on the client).
 */
function sampleSpokes(arr: ArticleRef[], count: number): ArticleRef[] {
  if (arr.length <= count) return arr;
  // Fisher-Yates partial shuffle — stop after `count` picks
  const copy = [...arr];
  for (let i = 0; i < count; i++) {
    const j = i + Math.floor(Math.random() * (copy.length - i));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy.slice(0, count);
}

/** Maximum number of spoke links shown below the pillar. */
const MAX_SPOKES = 3;

export function ArticleClusterCTA({ slug }: ArticleClusterCTAProps) {
  const cluster = findClusterBySlug(slug);

  // Return nothing when the current article does not belong to any cluster
  if (!cluster) return null;

  // Randomise spokes once per mount — useMemo prevents re-shuffle on re-render
  // and avoids hydration mismatches (server renders nothing, client picks).
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const displayedSpokes = useMemo(
    () => sampleSpokes(cluster.spokes, MAX_SPOKES),
    // Depend on cluster.id so a different cluster resamples correctly
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [cluster.id],
  );

  const pillar = cluster.pillar;
  const pillarHref = `/${pillar.category}/${pillar.slug}`;

  return (
    <div className="my-8 rounded-xl border border-white/10 bg-white/5 p-6">
      {/* Section label */}
      <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-white/40">
        More in this series — {cluster.title}
      </p>

      {/* Pillar article link */}
      <div className="mb-4 flex items-start gap-2">
        <span className="mt-0.5 shrink-0 rounded bg-[#d4845a]/20 px-2 py-0.5 text-[10px] font-bold uppercase text-[#d4845a]">
          Pillar
        </span>
        <Link
          href={pillarHref}
          className="text-base font-semibold text-white transition-colors hover:text-[#d4845a]"
        >
          {pillar.title}
        </Link>
      </div>

      {/* Divider */}
      <hr className="mb-4 border-white/10" />

      {/* Spoke article links */}
      <ul>
        {displayedSpokes.map((spoke) => {
          const spokeHref = `/${spoke.category}/${spoke.slug}`;
          return (
            <li
              key={spoke.slug}
              className="border-b border-white/5 py-2 last:border-0"
            >
              <Link
                href={spokeHref}
                className="group flex items-center justify-between"
              >
                <span className="text-sm text-white/70 transition-colors group-hover:text-white">
                  {spoke.title}
                </span>
                <span className="text-white/30 transition-colors group-hover:text-[#d4845a]">
                  →
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
