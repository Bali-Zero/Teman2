"use client";

import { useState } from "react";
import { ArrowLeft, GitCompare } from "lucide-react";

import { usePricingData } from "@/hooks/usePricingData";
import { getCopy } from "@/lib/secondhome-studio/copy";
import {
  E33_LIVE_PRICE_CATEGORY,
  resolveSecondHomePriceKey,
} from "@/lib/secondhome-studio/pricing-key";
import { evaluatePlan } from "@/lib/secondhome-studio/rules";
import {
  computeSequence,
  relevantPlan,
  type QuestionId,
} from "@/lib/secondhome-studio/sequence";
import type {
  PlanState,
  RouteIntent,
  Verdict,
} from "@/lib/secondhome-studio/types";

import { TimelineView } from "./TimelineView";
import { VerdictPanel } from "./VerdictPanel";

type RestingScenarioTriggerStyle = {
  borderColor: "var(--color-border-subtle)";
  color: "var(--text-secondary)";
};

// Compile-time guard: the exploratory control stays neutral until the user
// points to it or focuses it, preserving the funnel accent for the price box.
// These values belong to the class rule only; putting them on the element's
// inline style would prevent the interaction selectors below from winning.
const restingScenarioTriggerStyle = {
  borderColor: "var(--color-border-subtle)",
  color: "var(--text-secondary)",
} satisfies RestingScenarioTriggerStyle;

const SCENARIO_TRIGGER_STYLES = `
  .bz-shs-scenario-toggle-trigger {
    border: 1px solid ${restingScenarioTriggerStyle.borderColor};
    background: transparent;
    color: ${restingScenarioTriggerStyle.color};
    transition:
      border-color var(--motion-duration-fast, 150ms) ease,
      color var(--motion-duration-fast, 150ms) ease,
      background-color var(--motion-duration-fast, 150ms) ease,
      box-shadow var(--motion-duration-fast, 150ms) ease;
  }

  .bz-shs-scenario-toggle-trigger:is(:hover, :focus-visible) {
    border-color: var(--accent-funnel);
    background: color-mix(
      in srgb,
      var(--accent-funnel) 8%,
      transparent
    );
    box-shadow: inset 0 0 0 1px currentColor;
    /* This button's label is 16px/600 — WCAG "normal text" (large-text
       exemption needs >=24px, or >=18.66px bold), so the floor is 4.5:1.
       MERAH PUTIH DAY (2026-08-31): this read
       color-mix(var(--accent-funnel) 70%, white), and the measurements
       that justified it (full accent 4.13:1, the mix 5.59:1) were taken on
       the retired NAVY ground, where lightening a colour moves it AWAY
       from the backdrop. On carta the same gesture runs backwards: mixed
       toward white the label lands ~#D8586D and measures 3.07:1 against
       this rule's own 8%-tinted hover backdrop (~#f3e4e2) — a fail. The
       flat token is what passes here: #C8102E measures 4.77:1 on that same
       backdrop (5.44:1 on untinted carta). Do NOT re-introduce a mix
       toward white — on a light ground that is the direction of failure. */
    color: var(--accent-funnel);
    text-decoration-line: underline;
    text-decoration-thickness: 2px;
    text-underline-offset: 0.2em;
  }

  .bz-shs-scenario-toggle-trigger:focus-visible {
    outline: 3px solid var(--accent-funnel);
    outline-offset: 3px;
  }

  @media (prefers-reduced-motion: reduce) {
    .bz-shs-scenario-toggle-trigger {
      transition: none;
    }
  }
`;

export function otherRoute(route: RouteIntent): RouteIntent {
  return route === "property" ? "deposit" : "property";
}

function isQuestionMissing(p: PlanState, q: QuestionId): boolean {
  switch (q) {
    case "age":
      return p.age == null;
    case "route":
      return p.route == null;
    case "capital":
      return p.capital == null;
    case "seniorFunding":
      return p.seniorFunding == null;
    case "property":
      return p.property == null;
    case "family":
      return false;
    case "horizon":
      return p.horizon == null;
    case "location":
      return p.location == null;
  }
}

export interface ScenarioPreview {
  previewPlan: PlanState;
  previewVerdict: Verdict;
  missingQuestions: QuestionId[];
}

/**
 * Build a temporary preview of `plan` evaluated on a different `route`.
 *
 * The copy is run through `relevantPlan()` BEFORE evaluation so that answers
 * from an abandoned branch (e.g. `capital` left over from a deposit route)
 * are nulled when the preview switches to the property route. This keeps the
 * preview honest: it only ever evaluates states the wizard sequence could
 * actually produce.
 */
export function buildScenarioPreview(
  plan: PlanState,
  route: RouteIntent,
): ScenarioPreview {
  const draft: PlanState = { ...plan, route };
  const previewPlan = relevantPlan(draft);
  const previewVerdict = evaluatePlan(previewPlan);
  const reachable = computeSequence(previewPlan);
  const missingQuestions = reachable.filter((q) =>
    isQuestionMissing(previewPlan, q),
  );
  return { previewPlan, previewVerdict, missingQuestions };
}

interface ScenarioToggleProps {
  plan: PlanState;
}

/**
 * Second Home Studio — temporary "what if I took the other route?" preview.
 *
 * Purely client-side and state-only: the saved plan (`localStorage`, URL
 * fragment, and parent `plan` state) is never mutated. The preview copy is
 * sanitized through `relevantPlan()` before evaluation so the verdict is
 * always computed on a reachable wizard state, and any unreachable answers
 * are surfaced as "we would need to know X" instead of being invented.
 */
export function ScenarioToggle({ plan }: ScenarioToggleProps) {
  const [isOpen, setIsOpen] = useState(false);
  const route = plan.route;
  const altRoute = route ? otherRoute(route) : null;

  // Hooks must run before any early return.
  const preview =
    isOpen && altRoute ? buildScenarioPreview(plan, altRoute) : null;
  const previewPriceKey = preview
    ? resolveSecondHomePriceKey(
        preview.previewVerdict.product,
        preview.previewPlan.location,
      )
    : null;
  const { price: previewPrice } = usePricingData(
    previewPriceKey,
    E33_LIVE_PRICE_CATEGORY,
  );

  if (!route) return null;

  if (!isOpen) {
    return (
      <>
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="bz-shs-scenario-toggle-trigger"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "var(--space-2, 0.5rem)",
            padding: "var(--space-2, 0.5rem) var(--space-4, 1.2rem)",
            borderRadius: 12,
            cursor: "pointer",
            fontWeight: 600,
            minHeight: 44,
          }}
        >
          <GitCompare size={18} strokeWidth={1.5} aria-hidden />
          {getCopy("scenarioToggle.controlLabel")}
        </button>
        <style>{SCENARIO_TRIGGER_STYLES}</style>
      </>
    );
  }

  const { previewPlan, previewVerdict, missingQuestions } = preview!;
  const horizon = previewPlan.horizon ?? "exploring";
  const location = previewPlan.location ?? "in_indonesia";

  return (
    <section
      aria-label={getCopy("scenarioToggle.previewEyebrow")}
      data-testid="scenario-toggle-preview"
      className="bz-shs-scenario-toggle-preview"
      style={{
        display: "grid",
        gap: "var(--space-4, 1.5rem)",
        background: "var(--surface-raised)",
        border: "2px dashed var(--color-border-subtle)",
        borderRadius: 12,
        padding: "var(--space-4, 1.5rem)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2, 0.5rem)",
          padding: "var(--space-2, 0.5rem) var(--space-3, 0.75rem)",
          borderLeft: "3px solid var(--state-info)",
          background: "color-mix(in srgb, var(--state-info) 8%, transparent)",
          color: "var(--text-primary)",
          fontSize: "var(--text-sm, 0.88rem)",
        }}
      >
        <GitCompare
          size={16}
          strokeWidth={1.5}
          aria-hidden
          style={{ flexShrink: 0 }}
        />
        {getCopy("scenarioToggle.banner")}
      </div>

      <button
        type="button"
        onClick={() => setIsOpen(false)}
        className="bz-shs-scenario-toggle-back"
        style={{
          justifySelf: "start",
          display: "inline-flex",
          alignItems: "center",
          gap: "var(--space-2, 0.5rem)",
          padding: "6px 14px",
          borderRadius: 12,
          border: "1px solid var(--color-border-subtle)",
          background: "transparent",
          color: "var(--text-primary)",
          cursor: "pointer",
          minHeight: 44,
        }}
      >
        <ArrowLeft size={16} strokeWidth={1.5} aria-hidden />
        {getCopy("scenarioToggle.back")}
      </button>

      <VerdictPanel verdict={previewVerdict} />

      {missingQuestions.length > 0 ? (
        <div
          style={{
            display: "grid",
            gap: "var(--space-2, 0.5rem)",
            padding: "var(--space-3, 0.75rem)",
            border: "1px solid var(--color-border-subtle)",
            borderRadius: 12,
            background:
              "color-mix(in srgb, var(--state-warning) 6%, transparent)",
          }}
        >
          <p
            style={{
              margin: 0,
              fontWeight: 600,
              color: "var(--text-primary)",
            }}
          >
            {getCopy("scenarioToggle.missingAnswer.heading")}
          </p>
          <ul
            style={{
              margin: 0,
              paddingLeft: "1.2rem",
              color: "var(--text-primary)",
            }}
          >
            {missingQuestions.map((q) => (
              <li key={q}>{getCopy(`scenarioToggle.missingAnswer.${q}`)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <TimelineView
        horizon={horizon}
        location={location}
        route={previewPlan.route}
        product={previewVerdict.product}
      />

      {previewPrice ? (
        <section
          style={{
            display: "grid",
            gap: "var(--space-1, 0.3rem)",
            background: "var(--surface-raised)",
            border: "1px solid var(--accent-funnel)",
            borderRadius: 12,
            padding: "var(--space-4, 1.5rem)",
            textAlign: "center",
            justifyItems: "center",
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: "0.7rem",
              letterSpacing: "0.15em",
              textTransform: "uppercase",
              color: "var(--color-text-muted)",
            }}
          >
            {getCopy("price.label")}
          </p>
          <div
            style={{
              fontFamily: "var(--font-serif, Georgia, serif)",
              fontSize: "clamp(1.8rem, 4.5vw, 2.4rem)",
              color: "var(--accent-funnel-text, var(--accent-funnel))",
            }}
          >
            {previewPrice}
          </div>
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-sm, 0.88rem)",
              color: "var(--color-text-muted)",
            }}
          >
            {getCopy("price.note")}
          </p>
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-sm, 0.85rem)",
              color: "var(--color-text-muted)",
            }}
          >
            {getCopy("price.dependentsNote")}
          </p>
        </section>
      ) : null}

      <style>{`
        .bz-shs-scenario-toggle-trigger,
        .bz-shs-scenario-toggle-back {
          transition: transform 120ms ease, box-shadow 120ms ease;
        }
        @media (prefers-reduced-motion: reduce) {
          .bz-shs-scenario-toggle-preview *,
          .bz-shs-scenario-toggle-trigger,
          .bz-shs-scenario-toggle-back {
            transition: none !important;
            animation: none !important;
          }
        }
      `}</style>
    </section>
  );
}
