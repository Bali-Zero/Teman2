"use client";

import { useId, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { HelpCircle } from "lucide-react";
import type { Language } from "../_lib/flow";
import type { QuestionDecisionMapping } from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";

export interface WhyWeAskProps {
  language: Language;
  i18nKey: I18nKey;
  decisionMapping: QuestionDecisionMapping;
}

/**
 * The "gov-demo armor" (design doc §3): a disclosure glyph on every
 * sensitive question. Until a claim-level source ledger is frozen, it shows
 * the exact engine fact boundary (or clearly labels human-only context)
 * instead of presenting a historical regulation as proof of a live claim.
 */
export function WhyWeAsk({
  language,
  i18nKey,
  decisionMapping,
}: WhyWeAskProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const reducedMotion = useReducedMotion();

  return (
    <div className="oracle-whyweask">
      <button
        type="button"
        className="oracle-whyweask__trigger"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={translate(language, "whyweask.trigger.aria")}
        onClick={() => setOpen((v) => !v)}
      >
        <HelpCircle aria-hidden="true" size={16} />
        {translate(language, "whyweask.trigger")}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={panelId}
            className="oracle-whyweask__panel"
            initial={reducedMotion ? undefined : { height: 0, opacity: 0 }}
            animate={reducedMotion ? undefined : { height: "auto", opacity: 1 }}
            exit={reducedMotion ? undefined : { height: 0, opacity: 0 }}
            transition={{
              duration: reducedMotion ? 0 : 0.2,
              ease: [0.4, 0, 0.2, 1],
            }}
          >
            <p style={{ margin: 0 }}>{translate(language, i18nKey)}</p>
            <span className="oracle-whyweask__regulation">
              {decisionMapping.kind === "FACT"
                ? translate(language, "whyweask.fact_prefix", {
                    facts: decisionMapping.factPaths.join(", "),
                  })
                : decisionMapping.kind === "REVIEW_ONLY"
                  ? translate(language, "whyweask.review_only", {
                      facts: decisionMapping.factPaths.join(", "),
                    })
                  : translate(language, "whyweask.human_context")}
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
