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
}

/**
 * "12 paths → 3 → 1" — a fact, not a celebration (microcopy rule: the
 * counter is a fact, never gamification). `aria-live="polite"` announces
 * every change; ticking tabular-nums pairs the numeric + visual narrowing
 * with the tree prune (design doc §3 "dual visual+numeric encoding, an
 * accessibility win too").
 */
export function PathsCounter({ language, count, visible }: PathsCounterProps) {
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

  return (
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
  );
}
