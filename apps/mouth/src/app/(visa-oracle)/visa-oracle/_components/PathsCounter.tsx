"use client";

import { useEffect, useRef, useState } from "react";
import type { Language } from "../_lib/flow";
import { translate } from "../_lib/i18n";

export interface PathsCounterProps {
  language: Language;
  /** The count before this screen was reached — omit to hide the "from N". */
  count: number;
  /** Hidden through Q0-Q1, revealed once the user is committed (design doc
   * §3: "progress is hidden through Q1-Q2, revealed once committed"). */
  visible: boolean;
  /** The decomposed real breakdown for the selected category
   * (`productBreakdownForCategory()`, `product-purpose-counts.ts`) —
   * `null`/`undefined` before a category is chosen or when the category
   * has no honest breakdown (diaspora). Rendered only once `count === 1`
   * (the interview has narrowed to a single category). */
  productBreakdown?: {
    total: number;
    selfService: number;
    consultantRouted: number;
  } | null;
}

/**
 * "12 paths → 3 → 1" — a fact, not a celebration (microcopy rule: the
 * counter is a fact, never gamification). `aria-live="polite"` announces
 * every change; ticking tabular-nums pairs the numeric + visual narrowing
 * with the tree prune (design doc §3 "dual visual+numeric encoding, an
 * accessibility win too").
 */
export function PathsCounter({
  language,
  count,
  visible,
  productBreakdown,
}: PathsCounterProps) {
  const [announced, setAnnounced] = useState(count);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      setAnnounced(count);
      return;
    }
    setAnnounced(count);
  }, [count]);

  if (!visible) {
    // Still rendered for SR continuity, visually hidden — no fake linear
    // progress bar, and no layout jump when it appears.
    return <span className="oracle-sr-only" aria-live="polite" />;
  }

  // The interview has narrowed to a single category AND that category has
  // an honest breakdown (diaspora does not) — a local, narrowed reference
  // so the JSX below can read its fields without re-checking null/undefined.
  const revealedBreakdown =
    count === 1 && productBreakdown !== undefined && productBreakdown !== null
      ? productBreakdown
      : null;

  return (
    <div>
      <div className="oracle-paths-counter oracle-tabular-nums">
        <strong>{count}</strong>
        <span>
          {translate(language, "paths.counter.label", { count }).replace(
            /^\d+\s*/,
            "",
          )}
        </span>
        <span className="oracle-sr-only" aria-live="polite" role="status">
          {translate(language, "paths.counter.aria", { count: announced })}
        </span>
      </div>
      {revealedBreakdown && (
        <p
          className="oracle-paths-counter__products oracle-tabular-nums"
          role="status"
        >
          {revealedBreakdown.consultantRouted === 0
            ? translate(language, "paths.counter.products_all_selfservice", {
                total: revealedBreakdown.total,
              })
            : revealedBreakdown.selfService === 0
              ? translate(language, "paths.counter.products_all_consultant", {
                  total: revealedBreakdown.total,
                })
              : translate(language, "paths.counter.products_split", {
                  total: revealedBreakdown.total,
                  selfService: revealedBreakdown.selfService,
                  consultantRouted: revealedBreakdown.consultantRouted,
                })}
        </p>
      )}
    </div>
  );
}
