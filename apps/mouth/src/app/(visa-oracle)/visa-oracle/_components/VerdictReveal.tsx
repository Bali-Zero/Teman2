"use client";

import { useEffect, useRef } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { CheckCircle2, CircleAlert, HelpCircle, Info } from "lucide-react";
import type { RecommendState } from "@/lib/visa-oracle/types";
import type { Language } from "../_lib/flow";
import type { EligibilityState } from "../_lib/tree";
import { translate, BODY_FIRST, type I18nKey } from "../_lib/i18n";

export interface VerdictRevealProps {
  language: Language;
  state: RecommendState;
  /** Only meaningful for SUPPORTED_CANDIDATES — the strongest candidate's
   * eligibility, shown as a 4-state chip (color+icon+text, never
   * color-alone — spec hard-constraint 4). */
  eligibility?: EligibilityState;
}

const STATE_ICON: Record<RecommendState, typeof CheckCircle2> = {
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
export const ELIGIBILITY_ICON: Record<EligibilityState, typeof CheckCircle2> = {
  eligible: CheckCircle2,
  likely: CheckCircle2,
  conditional: HelpCircle,
  "likely-not": CircleAlert,
};

/**
 * "The Oracle deals your card" (design doc §3 interaction #4): the
 * strongest path resolves into a hero verdict card. Two layers, feature-
 * detected in OracleShell:
 *
 * 1. Where the View Transitions API exists and motion isn't reduced,
 *    OracleShell wraps the confirmation→verdict `advance()` dispatch in
 *    `document.startViewTransition()`. The tree's "verdict" trunk row
 *    (LivingTree.tsx `TreePanel`) and this card share the CSS
 *    `view-transition-name: oracle-verdict-morph` — never on both at once,
 *    since the tree row only carries it before this card mounts — so the
 *    browser interpolates geometry between the small trunk line and this
 *    hero card: a real shared-element detach-and-grow, not a simulation.
 * 2. This component's own spring reveal below (`--motion-curve-reveal`,
 *    the overshoot curve made for this moment) is what actually plays
 *    inside that browser-native transition, AND is the full fallback on
 *    its own wherever the View Transitions API is unsupported. Reduced
 *    motion skips both: OracleShell never calls `startViewTransition`, and
 *    every animated prop below already resolves to `undefined` in that
 *    branch — an instant swap, per spec.
 */
export function VerdictReveal({
  language,
  state,
  eligibility,
}: VerdictRevealProps) {
  const reducedMotion = useReducedMotion();
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, [state]);

  const StateIcon = STATE_ICON[state] ?? Info;
  const bodyFirst = BODY_FIRST[language];

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
      {translate(language, `verdict.headline.${state}` as I18nKey)}
    </h1>
  );
  const body = (
    <p
      className="oracle-subhead"
      style={{ marginTop: bodyFirst ? "var(--space-3)" : "var(--space-2)" }}
    >
      {translate(language, `verdict.state_description.${state}` as I18nKey)}
    </p>
  );

  return (
    <motion.div
      className="oracle-verdict-card"
      // Shared-element morph target (see the class-level comment above) —
      // only while motion isn't reduced, so a reduced-motion visit never
      // even offers the browser a transition to interpolate.
      style={
        reducedMotion
          ? undefined
          : { viewTransitionName: "oracle-verdict-morph" }
      }
      initial={reducedMotion ? undefined : { opacity: 0, scale: 0.92, y: 12 }}
      animate={reducedMotion ? undefined : { opacity: 1, scale: 1, y: 0 }}
      transition={{
        duration: reducedMotion ? 0 : 0.5,
        ease: [0.5, 0, 0.3, 1.2], // var(--motion-curve-reveal)
      }}
    >
      {eligibility && (
        <span className="oracle-verdict-chip" data-state={eligibility}>
          {(() => {
            const Icon = ELIGIBILITY_ICON[eligibility];
            return <Icon aria-hidden="true" size={16} />;
          })()}
          {translate(language, `verdict.eligibility.${eligibility}` as I18nKey)}
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
