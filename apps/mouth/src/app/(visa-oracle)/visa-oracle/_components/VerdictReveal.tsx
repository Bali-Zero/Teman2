"use client";

import { useEffect, useRef } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { CheckCircle2, CircleAlert, HelpCircle, Info } from "lucide-react";
import type { Language } from "../_lib/flow";
import type {
  LegalSupportStatus,
  OutcomeState,
  OutcomeViewModel,
} from "../_lib/outcome-view-model";
import { translate, BODY_FIRST, type I18nKey } from "../_lib/i18n";

export interface VerdictRevealProps {
  language: Language;
  state: OutcomeState;
  provenance: OutcomeViewModel["provenance"];
  /** Only meaningful for SUPPORTED_CANDIDATES — the strongest candidate's
   * legal support status. Operational and Bali Zero service availability
   * remain separate in OutcomeSheet. */
  legalStatus?: LegalSupportStatus;
}

const STATE_ICON: Record<OutcomeState, typeof CheckCircle2> = {
  SUPPORTED_CANDIDATES: CheckCircle2,
  HUMAN_REVIEW_REQUIRED: HelpCircle,
  NO_SUPPORTED_PATH: CircleAlert,
  TEMPORARILY_UNAVAILABLE: Info,
  NEEDS_INPUT: Info,
};

// Finding #14 (adversarial review 2026-07-17): exported so OutcomeSheet's
// comparison-table eligibility chips use the SAME icon set as the hero
// verdict chip above them — previously OutcomeSheet rendered eligibility
// as color+text only in that table, a spec hard-constraint-4 violation
// (never color-alone) that this module already solved once, locally.
export const LEGAL_STATUS_ICON: Record<
  LegalSupportStatus,
  typeof CheckCircle2
> = {
  SUPPORTED: CheckCircle2,
  CONDITIONAL: HelpCircle,
  NOT_SUPPORTED: CircleAlert,
  UNKNOWN: HelpCircle,
};

/** A restrained state reveal. Motion never carries decision meaning and is
 * removed entirely for people who prefer reduced motion. */
export function VerdictReveal({
  language,
  state,
  provenance,
  legalStatus,
}: VerdictRevealProps) {
  const reducedMotion = useReducedMotion();
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, [state]);

  const StateIcon = STATE_ICON[state] ?? Info;
  const bodyFirst = BODY_FIRST[language];
  const headlineKey =
    provenance === "ENGINE"
      ? (`verdict.headline.${state}` as I18nKey)
      : (`verdict.provenance_headline.${provenance}` as I18nKey);
  const descriptionKey =
    provenance === "ENGINE"
      ? (`verdict.state_description.${state}` as I18nKey)
      : (`verdict.provenance_description.${provenance}` as I18nKey);

  const heading = (
    <h1
      className="oracle-headline"
      style={{
        marginTop: bodyFirst ? "var(--space-2)" : "var(--space-3)",
        display: "flex",
        alignItems: "center",
        gap: "var(--space-2)",
      }}
      tabIndex={-1}
      ref={headingRef}
    >
      <StateIcon aria-hidden="true" size={28} />
      {translate(language, headlineKey)}
    </h1>
  );
  const body = (
    <p
      className="oracle-subhead"
      style={{ marginTop: bodyFirst ? "var(--space-3)" : "var(--space-2)" }}
    >
      {translate(language, descriptionKey)}
    </p>
  );

  return (
    <motion.div
      className="oracle-verdict-card"
      initial={reducedMotion ? undefined : { y: 6 }}
      animate={reducedMotion ? undefined : { y: 0 }}
      transition={{
        duration: reducedMotion ? 0 : 0.2,
        ease: [0.4, 0, 0.2, 1],
      }}
    >
      {legalStatus && (
        <span
          className="oracle-verdict-chip"
          data-state={legalStatus.toLowerCase()}
        >
          {(() => {
            const Icon = LEGAL_STATUS_ICON[legalStatus];
            return <Icon aria-hidden="true" size={16} />;
          })()}
          {translate(language, `outcome.status.${legalStatus}` as I18nKey)}
        </span>
      )}
      {/* Finding #16: design doc §3's ID register is body-first — swap
          render order per language rather than hardcoding EN's
          headline-then-body convention. */}
      {bodyFirst ? (
        <>
          {body}
          {heading}
        </>
      ) : (
        <>
          {heading}
          {body}
        </>
      )}
    </motion.div>
  );
}
