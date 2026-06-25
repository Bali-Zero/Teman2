import React from "react";
import { Newspaper, ArrowUpRight } from "lucide-react";
import type { ArticleListItem, ArticleCategory } from "@/lib/blog/types";

/**
 * PortalNewsRail — "The Bali Zero Dispatch" (FASE 4, blueprint §3.3 Tier-3).
 *
 * News from our world, projected into the portal as CONTEXT, never the hero.
 * The red-team (DeepSeek AP4) is explicit: a client doesn't open the portal for
 * news — so this is a calm side rail, filtered to what's relevant to the
 * client's active practices, with a "why am I seeing this" honesty.
 *
 * Reuses the EXISTING newsroom (getAllArticles / ArticleListItem) — no second
 * CMS. Relevance is deterministic (category match), no LLM in the request path.
 */

/** Map a client's practice domains to the matching article categories. */
const PRACTICE_TO_CATEGORY: Record<string, ArticleCategory> = {
  visa: "visas",
  kitas: "visas",
  immigration: "visas",
  company: "business",
  pma: "business",
  pt: "business",
  tax: "taxes",
  lkpm: "taxes",
  property: "property",
};

const MARKETING_ORIGIN = "https://balizero.com";

export function relevantCategories(
  practiceKinds: string[] | undefined,
): ArticleCategory[] {
  const cats = new Set<ArticleCategory>();
  for (const k of practiceKinds ?? []) {
    const key = k.toLowerCase();
    for (const [needle, cat] of Object.entries(PRACTICE_TO_CATEGORY)) {
      if (key.includes(needle)) cats.add(cat);
    }
  }
  return [...cats];
}

export interface PortalNewsRailProps {
  articles: ArticleListItem[];
  /** the client's active practice kinds, used to filter for relevance */
  practiceKinds?: string[];
  /** max items to show in the rail */
  limit?: number;
  className?: string;
}

export function PortalNewsRail({
  articles,
  practiceKinds,
  limit = 4,
  className,
}: PortalNewsRailProps) {
  const cats = relevantCategories(practiceKinds);

  // Prefer articles in the client's relevant categories; backfill with the most
  // recent so the rail is never empty (but never let it dominate — capped).
  const relevant = cats.length
    ? articles.filter((a) => cats.includes(a.category))
    : [];
  const backfill = articles.filter((a) => !relevant.includes(a));
  const shown = [...relevant, ...backfill].slice(0, limit);

  if (shown.length === 0) return null;

  return (
    <aside
      className={`rounded-2xl border p-4 ${className ?? ""}`}
      style={{
        background: "var(--bz-elevated)",
        borderColor: "var(--bz-border)",
      }}
      aria-label="The Bali Zero Dispatch"
    >
      <div className="flex items-center gap-2 mb-3">
        <Newspaper
          className="w-4 h-4"
          style={{ color: "var(--bz-accent-warm)" }}
          aria-hidden
        />
        <h2
          className="text-xs font-bold uppercase tracking-wider"
          style={{ color: "var(--bz-accent-warm)" }}
        >
          The Bali Zero Dispatch
        </h2>
      </div>

      <ul className="flex flex-col gap-3">
        {shown.map((a) => (
          <li key={a.id}>
            <a
              href={`${MARKETING_ORIGIN}/${a.category}/${a.slug}`}
              target="_blank"
              rel="noreferrer"
              className="group flex items-start gap-3 rounded-lg p-2 -m-2 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p
                  className="text-sm font-medium leading-snug line-clamp-2 group-hover:underline"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  {a.title}
                </p>
                <p
                  className="mt-1 text-xs"
                  style={{ color: "var(--bz-text-3)" }}
                >
                  {cats.includes(a.category) ? (
                    <span>Relevant to your {a.category}</span>
                  ) : (
                    <span>{a.readingTime} min read</span>
                  )}
                </p>
              </div>
              <ArrowUpRight
                className="w-4 h-4 mt-0.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-60"
                style={{ color: "var(--bz-text-2)" }}
                aria-hidden
              />
            </a>
          </li>
        ))}
      </ul>

      <a
        href={`${MARKETING_ORIGIN}/news`}
        target="_blank"
        rel="noreferrer"
        className="mt-3 inline-flex items-center gap-1 text-xs font-semibold"
        style={{ color: "var(--bz-accent)" }}
      >
        More from Bali Zero
        <ArrowUpRight className="w-3 h-3" aria-hidden />
      </a>
    </aside>
  );
}

export default PortalNewsRail;
