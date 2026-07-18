"use client";

import { HelpCircle } from "lucide-react";
import type { Language } from "../_lib/flow";
import { translate } from "../_lib/i18n";

export interface NotSureProps {
  language: Language;
  onSkip: () => void;
}

/**
 * "Not sure?" affordance (design doc §3): takes the question's conservative
 * branch (or holds for human review — the question decides which, in
 * `mock-engine.ts`) and visibly logs the assumption on the outcome page.
 * Momentum without hidden uncertainty.
 */
export function NotSure({ language, onSkip }: NotSureProps) {
  return (
    <button type="button" className="oracle-notsure" onClick={onSkip}>
      <HelpCircle aria-hidden="true" size={14} />
      {translate(language, "notsure.trigger")}
    </button>
  );
}
