"use client";

import { useEffect, useRef, useState, type Ref } from "react";
import { ConsentBanner } from "@/components/visa/ConsentBanner";
import { usePricingData } from "@/hooks/usePricingData";
import { getCopy } from "@/lib/secondhome-studio/copy";
import { evaluatePlan } from "@/lib/secondhome-studio/rules";
import {
  computeSequence,
  type QuestionId,
} from "@/lib/secondhome-studio/sequence";
import {
  E33_LIVE_PRICE_CATEGORY,
  resolveSecondHomePriceKey,
} from "@/lib/secondhome-studio/pricing-key";
import {
  clearPlan,
  decodePlanFragment,
  emptyPlan,
  loadPlan,
  savePlan,
} from "@/lib/secondhome-studio/plan-codec";
import type {
  AgeBand,
  CapitalBand,
  Location as LocationAnswer,
  PlanState,
  PropertyStatus,
  RouteIntent,
  SeniorFunding,
  TimelineHorizon,
} from "@/lib/secondhome-studio/types";

import { MemoPreview } from "./components/MemoPreview";
import { OptionButton, QuestionCard } from "./components/QuestionCard";
import { ProgressRail } from "./components/ProgressRail";
import { VerdictPanel } from "./components/VerdictPanel";
import { CustodyMap } from "./components/CustodyMap";
import { RouteComparator } from "./components/RouteComparator";
import { TimelineView } from "./components/TimelineView";
import { ReadinessChecklist } from "./components/ReadinessChecklist";
import { WhatsAppHandoff } from "./components/WhatsAppHandoff";
import { SavePlanBar } from "./components/SavePlanBar";
import { ScenarioToggle } from "./components/ScenarioToggle";
import { StudioAtmosphere } from "./components/StudioAtmosphere";

/**
 * Second Home Studio — the wizard state machine (spec §4).
 *
 * Question order: age -> route -> [deposit/unsure? capital] ->
 * [55+? seniorFunding] -> [property? property] -> family -> horizon ->
 * location -> VERDICT. The sequence (computeSequence, hoisted to
 * `lib/secondhome-studio/sequence.ts` — P2-6) is recomputed from the
 * CURRENT plan on every render (never cached against a stale branch), so
 * answering an earlier question (e.g. switching route from deposit to
 * property, or seniorFunding from "neither" to "income_only_3k")
 * immediately changes what the NEXT step is — no dangling questions from
 * an abandoned branch.
 */

/** "family" has no null representation in PlanState (default is a real,
 *  valid "no family members" answer) — treated as always-answered so
 *  resume-from-load never gets stuck deciding whether it was visited.
 *  Forward interactive navigation never consults this function — it's
 *  index-based (see `continueStep`). */
function isAnswered(p: PlanState, q: QuestionId): boolean {
  switch (q) {
    case "age":
      return p.age !== null;
    case "route":
      return p.route !== null;
    case "capital":
      return p.capital !== null;
    case "seniorFunding":
      return p.seniorFunding !== null;
    case "property":
      return p.property !== null;
    case "family":
      return true;
    case "horizon":
      return p.horizon !== null;
    case "location":
      return p.location !== null;
  }
}

function initialStepIndex(p: PlanState): number {
  const seq = computeSequence(p);
  const idx = seq.findIndex((q) => !isAnswered(p, q));
  return idx === -1 ? seq.length : idx;
}

function canContinue(p: PlanState, q: QuestionId): boolean {
  if (q === "family") return true;
  return isAnswered(p, q);
}

function nowIso(): string {
  return new Date().toISOString();
}

const eyebrowStyle: React.CSSProperties = {
  fontSize: "0.68rem",
  letterSpacing: "0.24em",
  textTransform: "uppercase",
  color: "var(--color-text-muted)",
  margin: 0,
};

const mastheadHeadingStyle: React.CSSProperties = {
  margin: 0,
  fontFamily: "var(--font-serif, Georgia, serif)",
  fontSize: "clamp(3.4rem, 8vw, 6.6rem)",
  fontWeight: 500,
  letterSpacing: "-0.035em",
  lineHeight: 0.92,
  maxWidth: "11ch",
  textWrap: "balance",
  color: "var(--text-primary)",
};

/** S13 verdict-crown: on the verdict stage the masthead recedes to a quiet,
 *  PRESENTATIONAL label (paired with the "Second Home Studio" eyebrow as one
 *  identifier block) so it stops competing with VerdictPanel's <h1>, which
 *  becomes the page's sole <h1> at that point (INVARIANT — exactly one <h1>
 *  at every stage). Words unchanged ("Check your fit") — demoted, never
 *  deleted or reworded; not a heading tag, so heading-rank navigation never
 *  sees it here. */
const mastheadLabelStyle: React.CSSProperties = {
  margin: 0,
  fontFamily: "var(--font-serif, Georgia, serif)",
  fontSize: "1.05rem",
  fontWeight: 500,
  letterSpacing: "-0.01em",
  color: "var(--text-secondary, var(--color-text-muted))",
};

const navButtonStyle: React.CSSProperties = {
  padding: "var(--space-2, 0.5rem) var(--space-4, 1.2rem)",
  borderRadius: 8,
  border: "1px solid var(--color-border-subtle)",
  background: "transparent",
  color: "var(--text-primary)",
  cursor: "pointer",
  minHeight: 44,
};

const primaryNavButtonStyle: React.CSSProperties = {
  ...navButtonStyle,
  marginLeft: "auto",
  border: "none",
  background: "var(--accent-funnel)",
  color: "var(--text-on-accent, #fff)",
  fontWeight: 600,
};

interface NavRowProps {
  canGoBack: boolean;
  canGoNext: boolean;
  onBack: () => void;
  onNext: () => void;
  nextLabel?: string;
}

function NavRow({
  canGoBack,
  canGoNext,
  onBack,
  onNext,
  nextLabel = "Continue",
}: NavRowProps) {
  return (
    <div
      style={{
        display: "flex",
        gap: "var(--space-3, 1rem)",
        marginTop: "var(--space-2, 0.5rem)",
      }}
    >
      <button
        type="button"
        onClick={onBack}
        disabled={!canGoBack}
        style={{
          ...navButtonStyle,
          cursor: canGoBack ? "pointer" : "not-allowed",
          opacity: canGoBack ? 1 : 0.5,
        }}
      >
        Back
      </button>
      <button
        type="button"
        onClick={onNext}
        disabled={!canGoNext}
        style={{
          ...primaryNavButtonStyle,
          cursor: canGoNext ? "pointer" : "not-allowed",
          opacity: canGoNext ? 1 : 0.6,
        }}
      >
        {nextLabel}
      </button>
    </div>
  );
}

interface QuestionStageProps {
  question: QuestionId;
  plan: PlanState;
  onSelect: (patch: Partial<PlanState>) => void;
  onBack: () => void;
  onContinue: () => void;
  canGoBack: boolean;
  /** Forwarded to QuestionCard's stage heading so StudioApp can move focus
   *  to it on step transitions (P2-3). */
  headingRef: Ref<HTMLHeadingElement>;
}

function QuestionStage({
  question,
  plan,
  onSelect,
  onBack,
  onContinue,
  canGoBack,
  headingRef,
}: QuestionStageProps) {
  const nav = (
    <NavRow
      canGoBack={canGoBack}
      canGoNext={canContinue(plan, question)}
      onBack={onBack}
      onNext={onContinue}
      nextLabel={
        question === "location" ? "See your fit-check result" : "Continue"
      }
    />
  );

  switch (question) {
    case "age": {
      const base = "wizard.age";
      const options: AgeBand[] = ["under_55", "55_59", "60_plus"];
      return (
        <QuestionCard
          heading={getCopy(`${base}.heading`)}
          body={getCopy(`${base}.body`)}
          why={getCopy(`${base}.why`)}
          headingRef={headingRef}
          options={options.map((opt) => (
            <OptionButton
              key={opt}
              variant="radio"
              label={getCopy(`${base}.options.${opt}`)}
              selected={plan.age === opt}
              onSelect={() => onSelect({ age: opt })}
            />
          ))}
        >
          {nav}
        </QuestionCard>
      );
    }
    case "route": {
      const base = "wizard.route";
      const options: RouteIntent[] = ["deposit", "property", "unsure"];
      return (
        <QuestionCard
          heading={getCopy(`${base}.heading`)}
          body={getCopy(`${base}.body`)}
          why={getCopy(`${base}.why`)}
          headingRef={headingRef}
          options={options.map((opt) => (
            <OptionButton
              key={opt}
              variant="radio"
              label={getCopy(`${base}.options.${opt}`)}
              selected={plan.route === opt}
              onSelect={() => onSelect({ route: opt })}
            />
          ))}
        >
          {nav}
        </QuestionCard>
      );
    }
    case "capital": {
      const base = "wizard.capital";
      const options: CapitalBand[] = [
        "ready_130k",
        "close_100k_130k",
        "below_100k",
      ];
      return (
        <QuestionCard
          heading={getCopy(`${base}.heading`)}
          body={getCopy(`${base}.body`)}
          why={getCopy(`${base}.why`)}
          headingRef={headingRef}
          options={options.map((opt) => (
            <OptionButton
              key={opt}
              variant="radio"
              label={getCopy(`${base}.options.${opt}`)}
              selected={plan.capital === opt}
              onSelect={() => onSelect({ capital: opt })}
            />
          ))}
        >
          {nav}
        </QuestionCard>
      );
    }
    case "seniorFunding": {
      const base = "wizard.seniorFunding";
      // "not_applicable" has no wizard button (copy.ts's own comment: it's
      // a valid PlanState value but never offered as a choice here).
      const options: SeniorFunding[] = [
        "deposit_50k_income",
        "income_only_3k",
        "neither",
      ];
      return (
        <QuestionCard
          heading={getCopy(`${base}.heading`)}
          body={getCopy(`${base}.body`)}
          why={getCopy(`${base}.why`)}
          headingRef={headingRef}
          options={options.map((opt) => (
            <OptionButton
              key={opt}
              variant="radio"
              label={getCopy(`${base}.options.${opt}`)}
              selected={plan.seniorFunding === opt}
              onSelect={() => onSelect({ seniorFunding: opt })}
            />
          ))}
        >
          {nav}
        </QuestionCard>
      );
    }
    case "property": {
      const base = "wizard.property";
      const options: PropertyStatus[] = [
        "owns_qualifying_strata",
        "buying_completed_strata",
        "villa_land_leasehold",
        "none",
      ];
      return (
        <QuestionCard
          heading={getCopy(`${base}.heading`)}
          body={getCopy(`${base}.body`)}
          why={getCopy(`${base}.why`)}
          headingRef={headingRef}
          options={options.map((opt) => (
            <OptionButton
              key={opt}
              variant="radio"
              label={getCopy(`${base}.options.${opt}`)}
              selected={plan.property === opt}
              onSelect={() => onSelect({ property: opt })}
            />
          ))}
        >
          {nav}
        </QuestionCard>
      );
    }
    case "family": {
      const base = "wizard.family";
      const isNone =
        !plan.family.spouse &&
        plan.family.children === 0 &&
        plan.family.parents === 0;
      return (
        <QuestionCard
          heading={getCopy(`${base}.heading`)}
          body={getCopy(`${base}.body`)}
          why={getCopy(`${base}.why`)}
          headingRef={headingRef}
        >
          {/* Multi-select (P2-4): stays a plain group of toggle buttons —
             aria-pressed, no radiogroup/radio roles — since this is the
             only step where more than one option can be true at once. */}
          <OptionButton
            label={getCopy(`${base}.options.spouse`)}
            selected={plan.family.spouse}
            onSelect={() =>
              onSelect({
                family: { ...plan.family, spouse: !plan.family.spouse },
              })
            }
          />
          <OptionButton
            label={getCopy(`${base}.options.children`)}
            selected={plan.family.children > 0}
            onSelect={() =>
              onSelect({
                family: {
                  ...plan.family,
                  children: plan.family.children > 0 ? 0 : 1,
                },
              })
            }
          />
          <OptionButton
            label={getCopy(`${base}.options.parents`)}
            selected={plan.family.parents > 0}
            onSelect={() =>
              onSelect({
                family: {
                  ...plan.family,
                  parents: plan.family.parents > 0 ? 0 : 1,
                },
              })
            }
          />
          <OptionButton
            label={getCopy(`${base}.options.none`)}
            selected={isNone}
            onSelect={() =>
              onSelect({ family: { spouse: false, children: 0, parents: 0 } })
            }
          />
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-sm, 0.85rem)",
              color: "var(--color-text-muted)",
            }}
          >
            {getCopy(`${base}.dependentsNote`)}
          </p>
          {nav}
        </QuestionCard>
      );
    }
    case "horizon": {
      const base = "wizard.horizon";
      const options: TimelineHorizon[] = ["asap", "this_quarter", "exploring"];
      return (
        <QuestionCard
          heading={getCopy(`${base}.heading`)}
          body={getCopy(`${base}.body`)}
          why={getCopy(`${base}.why`)}
          headingRef={headingRef}
          options={options.map((opt) => (
            <OptionButton
              key={opt}
              variant="radio"
              label={getCopy(`${base}.options.${opt}`)}
              selected={plan.horizon === opt}
              onSelect={() => onSelect({ horizon: opt })}
            />
          ))}
        >
          {nav}
        </QuestionCard>
      );
    }
    case "location": {
      const base = "wizard.location";
      const options: LocationAnswer[] = ["in_indonesia", "abroad"];
      return (
        <QuestionCard
          heading={getCopy(`${base}.heading`)}
          body={getCopy(`${base}.body`)}
          why={getCopy(`${base}.why`)}
          headingRef={headingRef}
          options={options.map((opt) => (
            <OptionButton
              key={opt}
              variant="radio"
              label={getCopy(`${base}.options.${opt}`)}
              selected={plan.location === opt}
              onSelect={() => onSelect({ location: opt })}
            />
          ))}
        >
          {nav}
        </QuestionCard>
      );
    }
    default:
      return null;
  }
}

export function StudioApp() {
  const [plan, setPlan] = useState<PlanState>(emptyPlan);
  const [stepIndex, setStepIndex] = useState(0);
  const hydratedOnce = useRef(false);

  const sequence = computeSequence(plan);
  const isVerdictStage = stepIndex >= sequence.length;
  const currentQuestion = isVerdictStage ? null : sequence[stepIndex];
  const verdict = isVerdictStage ? evaluatePlan(plan) : null;
  const priceKey = resolveSecondHomePriceKey(
    verdict?.product ?? null,
    plan.location,
  );
  const { price } = usePricingData(priceKey, E33_LIVE_PRICE_CATEGORY);

  // P2-3: the stage heading (QuestionCard's <h2> or VerdictPanel's <h1> —
  // only one is ever mounted at a time) is focused on a user-driven step
  // transition. `userNavigatedRef` gates it so neither the initial mount
  // NOR the hydration jump below (which can land straight on the verdict
  // page from a saved link) steals focus on page load — only an explicit
  // Continue/Back click does.
  const stageHeadingRef = useRef<HTMLHeadingElement>(null);
  const userNavigatedRef = useRef(false);

  useEffect(() => {
    if (!userNavigatedRef.current) return;
    stageHeadingRef.current?.focus();
  }, [stepIndex]);

  // Client-only hydration: a PRESENT URL fragment always wins over
  // localStorage — even when it fails to decode (P1-C6): a
  // malformed/invalid fragment must resolve to a FRESH plan, never
  // silently fall back to an old saved plan (which could show a stale
  // verdict the URL never asked for). localStorage is consulted ONLY when
  // there is no fragment at all. Runs once — SSR/first client render both
  // use the fresh-plan default so there is no hydration mismatch.
  useEffect(() => {
    if (hydratedOnce.current) return;
    hydratedOnce.current = true;
    if (typeof window === "undefined") return;

    const rawHash = window.location.hash.startsWith("#")
      ? window.location.hash.slice(1)
      : window.location.hash;

    const hasFragment = rawHash.startsWith("p=");
    const resolved = hasFragment
      ? decodePlanFragment(rawHash.slice(2))
      : loadPlan();

    const finalPlan = resolved ?? emptyPlan();
    setPlan(finalPlan);
    setStepIndex(initialStepIndex(finalPlan));
  }, []);

  function selectAnswer(patch: Partial<PlanState>) {
    setPlan((prev) => {
      const next: PlanState = { ...prev, ...patch, updatedAt: nowIso() };
      savePlan(next);
      return next;
    });
  }

  function continueStep() {
    userNavigatedRef.current = true;
    setStepIndex((idx) => Math.min(idx + 1, computeSequence(plan).length));
  }

  function goBack() {
    userNavigatedRef.current = true;
    setStepIndex((idx) => Math.max(0, idx - 1));
  }

  function toggleChecklistItem(id: string) {
    selectAnswer({
      checklist: { ...plan.checklist, [id]: !plan.checklist[id] },
    });
  }

  function handleClear() {
    clearPlan();
    setPlan(emptyPlan());
    setStepIndex(0);
  }

  // P1-C9: CustodyMap only makes sense for deposit-holding routes — a
  // property or E33F (income-only, no deposit) verdict never shows it.
  const showCustodyMap =
    verdict !== null &&
    (verdict.product === "E33" || verdict.product === "E33E");

  return (
    <div
      // data-funnel="visa" (2026-08-20 design pass): without this attribute
      // --accent-funnel falls through to the site's default `editorial`
      // theme value (#3a6dff, McKinsey blue — packages/core/tokens/themes/
      // editorial.css) instead of the visa funnel's own red identity
      // (semantic.css [data-theme="editorial"] [data-funnel="visa"]). Every
      // accent in this tree already reads var(--accent-funnel) correctly —
      // the token was never hardcoded, it was just never scoped. Matches
      // the other /visa funnel pages, which get this via AppFrame's
      // `funnel="visa"` prop (packages/core/components/apps/AppFrame.tsx);
      // this route has no AppFrame ancestor, so it sets the attribute here.
      data-funnel="visa"
      className="bz-shs-studio"
    >
      <StudioAtmosphere />
      <div
        className="bz-shs-content"
        style={{
          display: "grid",
          gap: "var(--space-5, 2rem)",
          maxWidth: "1120px",
          margin: "0 auto",
          padding: "var(--space-5, 2rem) var(--space-4, 1.5rem)",
        }}
      >
        <header
          style={{
            display: "grid",
            gap: isVerdictStage
              ? "var(--space-1, 0.3rem)"
              : "var(--space-3, 0.75rem)",
            padding: isVerdictStage
              ? "clamp(1rem, 3vw, 1.75rem) 0 clamp(0.5rem, 1vw, 0.75rem)"
              : "clamp(2rem, 7vw, 5rem) 0 clamp(1rem, 2vw, 1.5rem)",
          }}
        >
          <p style={eyebrowStyle}>Second Home Studio</p>
          {isVerdictStage ? (
            <p style={mastheadLabelStyle}>Check your fit</p>
          ) : (
            <h1 style={mastheadHeadingStyle}>Check your fit</h1>
          )}
        </header>

        {!isVerdictStage ? (
          <ProgressRail step={stepIndex + 1} total={sequence.length} />
        ) : null}

        {isVerdictStage && verdict ? (
          <div
            className="bz-shs-verdict-stack"
            style={{ display: "grid", gap: "var(--space-4, 1.5rem)" }}
          >
            <div>
              <button
                type="button"
                onClick={goBack}
                style={{ ...navButtonStyle, padding: "6px 14px" }}
              >
                ← Back to your answers
              </button>
            </div>
            <VerdictPanel verdict={verdict} headingRef={stageHeadingRef} />
            {showCustodyMap ? <CustodyMap /> : null}
            <RouteComparator highlight={plan.route === "unsure"} />
            <ScenarioToggle plan={plan} />
            <TimelineView
              horizon={plan.horizon ?? "exploring"}
              location={plan.location ?? "in_indonesia"}
              route={plan.route}
              product={verdict.product}
            />
            <ReadinessChecklist plan={plan} onToggle={toggleChecklistItem} />
            {price ? (
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
                  {price}
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
            <WhatsAppHandoff plan={plan} verdict={verdict} />
            <SavePlanBar plan={plan} onClear={handleClear} />
          </div>
        ) : currentQuestion ? (
          <div className="bz-shs-layout">
            <main>
              <QuestionStage
                question={currentQuestion}
                plan={plan}
                onSelect={selectAnswer}
                onBack={goBack}
                onContinue={continueStep}
                canGoBack={stepIndex > 0}
                headingRef={stageHeadingRef}
              />
            </main>
            <aside>
              <MemoPreview plan={plan} />
            </aside>
          </div>
        ) : null}

        <ConsentBanner />

        <style>{`
        .bz-shs-layout {
          display: grid;
          gap: var(--space-4, 1.5rem);
          grid-template-columns: 1fr;
          align-items: start;
        }
        @media (min-width: 900px) {
          .bz-shs-layout {
            grid-template-columns: minmax(0, 1fr) 320px;
          }
          /* Desktop layout balance (2026-08-20 design pass): the memo rail
           * used to sit static at the top of its column and scroll away as
           * a tall question card grew below it, leaving a "dead" empty
           * column on wide viewports. align-items:start above already
           * keeps the rail from stretching to the main column's height —
           * required for sticky to have room to move within. */
          .bz-shs-layout > aside {
            position: sticky;
            top: var(--space-5, 2rem);
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .bz-shs-layout * {
            transition: none !important;
            animation: none !important;
          }
        }
      `}</style>
      </div>
    </div>
  );
}
