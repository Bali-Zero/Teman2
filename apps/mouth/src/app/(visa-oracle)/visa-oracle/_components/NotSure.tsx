"use client";

import { HelpCircle } from "lucide-react";
import type { Language } from "../_lib/flow";
import { translate } from "../_lib/i18n";

export interface NotSureProps {
  language: Language;
  onSkip: () => void;
}

/**
 * Records explicit uncertainty as an interview fact. The deterministic engine,
 * never this affordance, decides whether more input or human review is needed.
 */
export function NotSure({ language, onSkip }: NotSureProps) {
  return (
    <button type="button" className="oracle-notsure" onClick={onSkip}>
      <HelpCircle aria-hidden="true" size={14} />
      {translate(language, "notsure.trigger")}
    </button>
  );
}
