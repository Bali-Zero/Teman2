"use client";

import { useEffect, useRef, useState, type Ref } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { ConsentBanner } from "@/components/visa/ConsentBanner";
import { usePricingData } from "@/hooks/usePricingData";
import { getCopy } from "@/lib/secondhome-studio/copy";
import { evaluatePlan } from "@/lib/secondhome-studio/rules";
import {
  computeSequence,
  type QuestionId,
} from "@/lib/secondhome-studio/sequence";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { R19_CLASS, R19_DIRECTION_A_VARS } from "@/lib/theme/r19Vars";
import { r19FontClassName } from "@/lib/theme/r19Fonts";
import "@/styles/r19-direction-a.css";
import "./room/studio-room.css";
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
import { Wall } from "./room/Wall";
import { Shelf } from "./room/Shelf";
import { ROOM_STATE_VARS } from "./room/bandTones";

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

/** Short step names for the labelled progress rail — the same words the
 *  "Your plan so far" memo uses for its rows, so the two read as one list. */
const STEP_LABELS: Record<QuestionId, string> = {
  age: "Age",
  route: "Route",
  capital: "Capital",
  seniorFunding: "Senior funding",
  property: "Property",
  family: "Family",
  horizon: "Timeline",
  location: "Location",
};

/** Identity lockup — family layer §2.1 (BRIEF-v2, R-1): the BZLogo MARK
 *  beside the wordmark (never set as a letter, design SKILL §3.6), "BALI
 *  ZERO" in Manrope 750 and the product name in Fraunces 450, via the
 *  foundation's `.r19-lockup` roles. Replaces the 2026-09-24 merah flag. */
function Lockup() {
  return (
    <p className="r19-lockup bz-shs-lockup">
      <BZLogo variant="mark" size={28} className="r19-lockup__mark" />
      <span className="r19-lockup__wordmark">
        {getCopy("room.lockup.wordmark")}
      </span>
      <span aria-hidden="true" className="bz-shs-lockup-rule" />
      <span className="r19-lockup__product">
        {getCopy("room.lockup.product")}
      </span>
    </p>
  );
}

/** R19 paper under the whole route: <body> is an ancestor of the wrapper and
 *  keeps the editorial ground otherwise (measured 88px of it on the day set). */
const R19_BODY_CSS = `
body:has(.bz-shs-room) {
  background: ${(R19_DIRECTION_A_VARS as Record<string, string>)["--surface-base"]};
  color: ${(R19_DIRECTION_A_VARS as Record<string, string>)["--text-primary"]};
}
@media print {
  body:has(.bz-shs-room) {
    background: #ffffff;
  }
}
`;

const mastheadHeadingStyle: React.CSSProperties = {
  margin: 0,
  fontFamily: "var(--font-serif, Georgia, serif)",
  // 2026-09-24: was clamp(3.4rem, 8vw, 6.6rem) — a poster title that pushed
  // the first question below the fold at 390x844. The question is the peak
  // of this viewport (R3); the masthead names the page and gets out of the way.
  fontSize: "clamp(2rem, 4.2vw, 3.25rem)",
  letterSpacing: "-0.03em",
  lineHeight: 1.02,
  textWrap: "balance",
  color: "var(--text-primary)",
};

/** One plain outcome line under the masthead — what the visitor gets for
 *  answering. No count, no promise: the rail already shows the steps. */
const mastheadLedeStyle: React.CSSProperties = {
  margin: 0,
  fontSize: "1.0625rem",
  lineHeight: 1.45,
  color: "var(--text-secondary)",
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
  // R4 §3 24px floor: at 1.05rem (16.8px) Cormorant would sit below the
  // display-only floor — low-DPI Android antialiasing shreds the serif — so
  // this demoted label uses the UI/body face at Inter 600 instead, per R4
  // §3's own remedy ("smaller headings are Inter 600"). Size/hierarchy
  // unchanged — only the face and weight move.
  fontFamily: "var(--font-sans, ui-sans-serif, system-ui, sans-serif)",
  fontSize: "1.05rem",
  fontWeight: 600,
  letterSpacing: "-0.01em",
  color: "var(--text-secondary, var(--color-text-muted))",
};

/** WCAG contrast fix (2026-08-24): `--color-border-subtle` composites to
 *  ~1.2:1 against the editorial card backdrop — invisible, and below the
 *  3.0:1 floor for non-text UI boundaries (WCAG 1.4.11). No shipped border
 *  token cleared that floor on the editorial theme (`--border-strong` topped
 *  out at ~1.9:1 there), so this derived an opaque-enough value from
 *  `--text-primary`: `color-mix(--text-primary 45%, transparent)`, which
 *  composited to ~3.5:1 against the editorial backdrop.
 *
 *  MERAH PUTIH DAY (2026-08-31): that mix claimed to "stay theme-adaptive",
 *  and it does not. A FIXED percentage is tuned to one ground: composited over
 *  the day palette it lands #969ba6 on the white QuestionCard (2.79:1) and
 *  #92969f on carta (2.74:1) — under the same 3:1 floor the comment invokes.
 *  This is the Back button, rendered on EVERY question step and again at the
 *  verdict stage, so it is not an edge case. On a light ground the shipped
 *  token finally works: `--border-strong` (#7a8093) measures 3.94:1 on the
 *  card and 3.64:1 on carta. Mixing a token toward transparent is safe for a
 *  TINT, but a boundary's contrast has to be re-measured whenever the ground
 *  flips — the percentage is not the invariant, the ratio is. */
const navButtonStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 8,
  padding: "0 18px",
  borderRadius: "var(--r19-radius-control, 3px)",
  border: "1px solid var(--border-strong)",
  background: "transparent",
  color: "var(--text-primary)",
  cursor: "pointer",
  minHeight: 48,
  fontSize: "1rem",
  fontWeight: 500,
  fontFamily: "inherit",
};

/** The primary CTA takes the ACTION red, `--cta-bg` (#D01033 under the Merah
 *  Putih DAY set): white on it measures 5.52:1, clearing the 4.5:1 floor for
 *  this 16px/600 normal-size text (the large-text carve-out needs >=24px, or
 *  >=18.66px at weight>=700 — never a reason to stretch a label instead of
 *  fixing the fill, least of all on a funnel selling senior visas to a 55+
 *  audience whose contrast tolerance skews lower, not higher).
 *
 *  This REPLACES a 2026-08-24 fix that read
 *  `color-mix(in srgb, var(--accent-funnel) 85%, black)`. That was correct for
 *  the dark theme it was written under — white on the then-current `#ff3344`
 *  measured 3.62:1, so the fill was darkened until it cleared. Under the DAY
 *  palette the premise is gone (white on #D01033 already clears), and the
 *  workaround had two costs worth removing: it painted a colour that exists in
 *  no token (measured live as rgb(170, 14, 39)), and it built the CTA out of the
 *  STRUCTURE red when R4 §3 assigns primary CTAs to the ACTION red — the two
 *  duties red is allowed to have, and the whole point of keeping them apart. */
const primaryNavButtonStyle: React.CSSProperties = {
  ...navButtonStyle,
  marginLeft: "auto",
  padding: "0 22px",
  border: "1px solid transparent",
  background: "var(--cta-bg, var(--accent-funnel-text))",
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

/** Disabled = "not yet", never an alarm (R4 §3 interactive states: ink-soft
 *  on carta, no opacity tricks). The old `opacity: 0.6` over the action red
 *  composited to a washed pink that read as an error state. */
const disabledPrimaryNavButtonStyle: React.CSSProperties = {
  ...primaryNavButtonStyle,
  border: "1px solid var(--border-default)",
  background: "var(--surface-sunken)",
  color: "var(--text-secondary)",
  cursor: "not-allowed",
};

function NavRow({
  canGoBack,
  canGoNext,
  onBack,
  onNext,
  nextLabel = "Continue",
}: NavRowProps) {
  return (
    <div className="bz-shs-nav">
      <button
        type="button"
        className="bz-shs-back"
        onClick={onBack}
        disabled={!canGoBack}
        style={{
          ...navButtonStyle,
          border: canGoBack
            ? navButtonStyle.border
            : "1px solid var(--border-default)",
          color: canGoBack ? "var(--text-primary)" : "var(--text-secondary)",
          cursor: canGoBack ? "pointer" : "not-allowed",
        }}
      >
        <ArrowLeft size={16} aria-hidden />
        Back
      </button>
      {!canGoNext ? (
        <p className="bz-shs-nav-hint">Choose an answer to continue</p>
      ) : null}
      <button
        type="button"
        className="bz-shs-cta"
        onClick={onNext}
        disabled={!canGoNext}
        style={
          canGoNext ? primaryNavButtonStyle : disabledPrimaryNavButtonStyle
        }
      >
        {nextLabel}
        <ArrowRight size={18} aria-hidden />
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
          actions={nav}
        />
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
          actions={nav}
        />
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
          actions={nav}
        />
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
          actions={nav}
        />
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
          actions={nav}
        />
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
          actions={nav}
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
          actions={nav}
        />
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
          actions={nav}
        />
      );
    }
    default:
      return null;
  }
}

export function StudioApp() {
  const [plan, setPlan] = useState<PlanState>(emptyPlan);
  const [stepIndex, setStepIndex] = useState(0);
  // The plan as it stood when the current screen opened. The answer being
  // chosen here can reshape LATER steps (60+ adds senior funding; income-only
  // drops capital), so the rail's "of M" moves when the visitor moves on —
  // never while they are still choosing on the same screen. A snapshot, not
  // the plan with this answer blanked: Back onto an answered step opens on
  // the branch that answer already chose. The prefix up to the current
  // question depends only on earlier answers, so step N is the same in both.
  const [openedWith, setOpenedWith] = useState<PlanState>(emptyPlan);
  // "No family members" has no null in PlanState, so only the wizard knows
  // the family step was answered: once it is passed, the memo lists it.
  const [familyPassed, setFamilyPassed] = useState(false);
  const hydratedOnce = useRef(false);
  const consentSpaceRef = useRef<HTMLDivElement>(null);
  const [consentHeight, setConsentHeight] = useState(0);

  useEffect(() => {
    const host = consentSpaceRef.current;
    if (!host) return;

    // The fixed banner contributes no document height. Reserve its measured
    // size here so recovery controls can scroll fully above it at any width.
    const measure = () =>
      setConsentHeight(
        host.firstElementChild?.getBoundingClientRect().height ?? 0,
      );
    const resizeObserver =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(measure);
    const observeBanner = () => {
      resizeObserver?.disconnect();
      if (host.firstElementChild)
        resizeObserver?.observe(host.firstElementChild);
      measure();
    };
    const mutationObserver = new MutationObserver(observeBanner);
    mutationObserver.observe(host, { childList: true });
    observeBanner();
    window.addEventListener("resize", measure);

    return () => {
      resizeObserver?.disconnect();
      mutationObserver.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);

  const sequence = computeSequence(plan);
  const isVerdictStage = stepIndex >= sequence.length;
  const currentQuestion = isVerdictStage ? null : sequence[stepIndex];
  const railSequence = currentQuestion ? computeSequence(openedWith) : sequence;
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
    const resumeAt = initialStepIndex(finalPlan);
    setPlan(finalPlan);
    setOpenedWith(finalPlan);
    setFamilyPassed(resumeAt > computeSequence(finalPlan).indexOf("family"));
    setStepIndex(resumeAt);
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
    if (currentQuestion === "family") setFamilyPassed(true);
    setOpenedWith(plan);
    setStepIndex((idx) => Math.min(idx + 1, computeSequence(plan).length));
  }

  function goBack() {
    userNavigatedRef.current = true;
    setOpenedWith(plan);
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
    setOpenedWith(emptyPlan());
    setFamilyPassed(false);
    setStepIndex(0);
  }

  // P1-C9: CustodyMap only makes sense for deposit-holding routes — a
  // property or E33F (income-only, no deposit) verdict never shows it.
  const showCustodyMap =
    verdict !== null &&
    (verdict.product === "E33" || verdict.product === "E33E");

  const railChart = !isVerdictStage ? (
    <ProgressRail
      step={stepIndex + 1}
      total={railSequence.length}
      labels={railSequence.map((q) => STEP_LABELS[q])}
    />
  ) : null;

  return (
    <div
      // «Lo studiolo di Ari» (BRIEF-v2 §3.2, 2026-09-26). The ROOM is this
      // wrapper: R19 Direction A (R-1) replaces the Merah Putih day set on
      // this route only — the /visa/second-home landing keeps Merah Putih
      // (R-6 seam). data-funnel="visa" stays so nothing falls through to the
      // editorial theme's McKinsey blue (2026-08-20 design pass).
      data-funnel="visa"
      className={`bz-shs-studio bz-shs-room ${R19_CLASS} ${r19FontClassName}`}
      style={
        {
          ...R19_DIRECTION_A_VARS,
          ...ROOM_STATE_VARS,
          // Inside the Studio every existing `--border-strong` consumer is an
          // interactive boundary (options, Back, checklist, save bar, WhatsApp);
          // R19's #A8ACA9 is 2.09:1 there, so the room restates it to R19's own
          // control border (#7B817F, 3.62:1 on paper — r19Vars.ts FLAG 1).
          "--border-strong": (R19_DIRECTION_A_VARS as Record<string, string>)[
            "--r19-control-border"
          ],
          // Read by QuestionCard's sticky action row so it rides above the
          // fixed consent banner instead of under it.
          ...({
            "--bz-shs-consent-h": `${consentHeight}px`,
          } as React.CSSProperties),
          background: "var(--surface-base)",
          color: "var(--text-primary)",
          minHeight: "100vh",
          // The site root declares a dark color-scheme for the editorial theme;
          // on this paper ground it painted every native checkbox (the readiness
          // checklist) as a solid black square that read as "already ticked".
          colorScheme: "light",
          accentColor: "var(--text-primary)",
        } as React.CSSProperties
      }
    >
      <style>{R19_BODY_CSS}</style>
      <StudioAtmosphere />
      <div className="bz-shs-content bz-shs-room-grid">
        <header className="bz-shs-door">
          <Lockup />
        </header>

        <div
          className="bz-shs-desk-head"
          data-stage={isVerdictStage ? "verdict" : "question"}
        >
          {isVerdictStage ? (
            <p style={mastheadLabelStyle}>Check your fit</p>
          ) : (
            <>
              <h1 className="bz-shs-masthead" style={mastheadHeadingStyle}>
                Check your fit
              </h1>
              <p style={mastheadLedeStyle}>
                See which Second Home route fits you.
              </p>
            </>
          )}
        </div>

        <Wall
          chart={railChart}
          map={showCustodyMap ? <CustodyMap /> : null}
          ledger={
            currentQuestion ? (
              <MemoPreview
                plan={plan}
                total={railSequence.length}
                familyAnswered={familyPassed}
              />
            ) : null
          }
        />

        {isVerdictStage && verdict ? (
          <div
            className="bz-shs-desk bz-shs-verdict-stack"
            style={{ display: "grid", gap: "var(--space-4, 1.5rem)" }}
          >
            <div className="bz-shs-back-to-answers">
              <button
                type="button"
                onClick={goBack}
                style={{ ...navButtonStyle, padding: "0 16px" }}
              >
                <ArrowLeft size={16} aria-hidden />
                Back to your answers
              </button>
            </div>
            <VerdictPanel verdict={verdict} headingRef={stageHeadingRef} />
            {price ? (
              <section className="bz-shs-price-slip">
                <p className="bz-shs-price-label">{getCopy("price.label")}</p>
                <div className="bz-shs-figure bz-shs-price-figure">{price}</div>
                <p className="bz-shs-price-note">{getCopy("price.note")}</p>
                <p className="bz-shs-price-note">
                  {getCopy("price.dependentsNote")}
                </p>
              </section>
            ) : null}
            <WhatsAppHandoff plan={plan} verdict={verdict} />
            <ReadinessChecklist
              plan={plan}
              verdict={verdict}
              onToggle={toggleChecklistItem}
            />
            <TimelineView
              horizon={plan.horizon ?? "exploring"}
              location={plan.location ?? "in_indonesia"}
              route={plan.route}
              product={verdict.product}
            />
            <RouteComparator highlight={plan.route === "unsure"} />
            <section
              className="bz-shs-second-chair"
              aria-label={getCopy("room.desk.secondChair")}
            >
              <p className="bz-shs-second-chair-label">
                {getCopy("room.desk.secondChair")}
              </p>
              <ScenarioToggle plan={plan} />
            </section>
            <SavePlanBar plan={plan} onClear={handleClear} />
          </div>
        ) : currentQuestion ? (
          <main className="bz-shs-desk" aria-label={getCopy("room.desk.label")}>
            <div className="bz-shs-layout">
              <div className="bz-shs-sheet">
                <QuestionStage
                  question={currentQuestion}
                  plan={plan}
                  onSelect={selectAnswer}
                  onBack={goBack}
                  onContinue={continueStep}
                  canGoBack={stepIndex > 0}
                  headingRef={stageHeadingRef}
                />
              </div>
            </div>
          </main>
        ) : null}

        <Shelf plan={plan} verdict={verdict} />

        <div
          ref={consentSpaceRef}
          className="bz-shs-consent-space"
          style={{
            height: consentHeight,
            display: consentHeight > 0 ? "block" : "contents",
            // Red hierarchy (2026-09-24), kept under R19: inside this wrapper
            // the banner's own accent token turns ink, so Continue owns the
            // only copper on screen. ConsentBanner itself and every other
            // route are untouched.
            ...({
              "--bz-accent": "var(--text-primary)",
            } as React.CSSProperties),
          }}
        >
          <ConsentBanner />
        </div>

        <style>{`
        .bz-shs-content {
          padding: 8px 16px 32px;
        }
        @media (min-width: 640px) {
          .bz-shs-content {
            padding: 16px 24px 48px;
          }
        }
        /* Step transitions focus the stage heading (P2-3); the browser then
         * scrolls it to the viewport's top edge — under the fixed site nav.
         * The margin lands it just below the nav instead. */
        .bz-shs-studio h1[tabindex="-1"],
        .bz-shs-studio h2[tabindex="-1"] {
          scroll-margin-top: 96px;
        }
        .bz-shs-nav {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .bz-shs-nav-hint {
          display: none;
          margin: 0 0 0 auto;
          font-size: 0.875rem;
          color: var(--text-secondary);
        }
        @media (min-width: 520px) {
          .bz-shs-nav-hint {
            display: block;
          }
          .bz-shs-nav-hint + .bz-shs-cta {
            margin-left: 0 !important;
          }
        }
        /* At 320px the footer gets 214px (the /visa layout's px-4 plus this
         * page's own gutter plus the card's) and Back + Continue need 254px:
         * the row's min-content widened the whole column and the page
         * scrolled sideways. At 360 it fits with zero margin. Below 375 the
         * CTA takes its own full-width row instead. */
        @media (max-width: 374px) {
          .bz-shs-nav {
            flex-wrap: wrap;
          }
          .bz-shs-cta {
            flex-grow: 1;
          }
        }
        .bz-shs-back:not(:disabled):hover {
          background: var(--surface-base) !important;
          border-color: var(--text-primary) !important;
        }
        .bz-shs-cta:not(:disabled):hover {
          background: var(--cta-bg-hover) !important;
        }
        /* Family layer §2.2: a 3px copper focus ring, offset 3px. */
        .bz-shs-nav button:focus-visible,
        .bz-shs-back-to-answers button:focus-visible {
          outline: 3px solid var(--r19-copper, var(--text-primary));
          outline-offset: 3px;
        }
        .bz-shs-layout {
          display: grid;
          gap: var(--space-4, 1.5rem);
          grid-template-columns: 1fr;
          align-items: start;
        }
        /* Side-by-side sheet + ledger is decided by the desk's own width:
         * see the container query in room/studio-room.css. */
        @media (prefers-reduced-motion: reduce) {
          .bz-shs-layout * {
            transition: none !important;
            animation: none !important;
          }
        }
        @media print {
          .bz-shs-consent-space {
            display: none !important;
          }
        }
      `}</style>
      </div>
    </div>
  );
}
