"use client";

import { useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

import {
  CATEGORIES,
  LANE_COPY,
  Q0_EXPIRY_DATE,
  Q0_IN_INDONESIA,
  Q1_CATEGORY,
  answer,
  createInterview,
  skip,
} from "@/lib/visa-oracle/v2/mock-tree";
import type { LaneTone } from "@/lib/visa-oracle/v2/mock-tree";
import { t } from "@/lib/visa-oracle/v2/types";
import type { InterviewState } from "@/lib/visa-oracle/v2/types";

/**
 * Visa Oracle v2 — framing card + Q0 prototype (Track C PR C1, foundation
 * only). MOCK DATA ONLY — see src/lib/visa-oracle/v2/mock-tree.ts.
 *
 * This component intentionally stops right after (a) the onshore lane is
 * computed, or (b) a category is selected — it demonstrates the framing
 * card + Q0, per docs/plans/2026-07-17-visa-oracle-v2/00-product-design.md
 * §4. Deeper navigation (the living tree, the remote-worker sub-questions
 * mock-tree.ts already models, the outcome page) lands in PR C2.
 */

type Stage =
  | "intro"
  | "q0"
  | "date"
  | "onshore-done"
  | "categories"
  | "category-done";

function deriveStage(began: boolean, interview: InterviewState): Stage {
  if (!began) return "intro";

  const q0 = interview.answers[Q0_IN_INDONESIA.id];
  if (typeof q0 !== "string") return "q0";

  if (q0 === "yes") {
    const date = interview.answers[Q0_EXPIRY_DATE.id];
    return typeof date === "string" ? "onshore-done" : "date";
  }

  const category = interview.answers[Q1_CATEGORY.id];
  return typeof category === "string" ? "category-done" : "categories";
}

const LANE_TONE_VAR: Record<LaneTone, string> = {
  urgent: "var(--vo2-lane-urgent)",
  amber: "var(--vo2-lane-amber)",
  neutral: "var(--vo2-lane-neutral)",
};

/**
 * Reduced-motion (Codex sol review F7): framer-motion's own `MotionConfig
 * reducedMotion="user"` (wrapping the render below) now owns this — it
 * reads `prefers-reduced-motion` NATIVELY, including on first paint, so
 * there is no mount-then-correct gap for the hand-rolled matchMedia hook
 * that previously lived here to leave open. See the wrapping
 * `<MotionConfig>` in the component body.
 */

/**
 * Focus management (Codex sol review F5): stage transitions must move
 * focus to the new stage's heading, not leave it stranded on document
 * body or a control that just unmounted. Implemented as a STABLE
 * (module-scope, not re-created per render) ref callback rather than a
 * `useEffect` keyed on `stage` — AnimatePresence's `mode="wait"` delays
 * mounting the entering child until the exiting one's animation finishes,
 * so a parent-level effect keyed on the (derived, not stateful) `stage`
 * value would fire on the render where `stage` changes, BEFORE the new
 * heading node actually exists in the DOM, and never re-fire once it
 * does. A ref callback instead runs exactly when React attaches it to a
 * real DOM node — i.e. precisely on that node's mount — which is what we
 * want. Using the SAME function reference on every render (module scope,
 * not an inline arrow function) also means React only invokes it on
 * actual mount/unmount of the underlying element, never on incidental
 * re-renders while the same stage is still showing (e.g. typing in the
 * date input) — an inline `ref={(el) => el?.focus()}` would re-run on
 * every render and could steal focus back from that input mid-edit.
 */
function focusOnMount(el: HTMLElement | null) {
  el?.focus();
}

function PlaceholderCard() {
  return (
    <div
      className="rounded-xl border border-dashed px-4 py-3 text-sm"
      style={{
        borderColor: "var(--vo2-branch-pruned)",
        color: "var(--text-tertiary)",
      }}
    >
      The living tree arrives in the next iteration.
    </div>
  );
}

export function FramingCard() {
  const [began, setBegan] = useState(false);
  const [interview, setInterview] = useState<InterviewState>(() =>
    createInterview(),
  );

  const stage = deriveStage(began, interview);
  const laneEntry = interview.lane ? LANE_COPY[interview.lane] : null;
  const categoryKey = interview.answers[Q1_CATEGORY.id];
  const selectedCategory = CATEGORIES.find((c) => c.key === categoryKey);

  // Mirrors --vo2-dur-flow (350ms) / --vo2-ease-out. Reduced-motion is
  // handled natively by the wrapping <MotionConfig reducedMotion="user">
  // below (F7) — framer-motion itself skips/shortens transform animations
  // for prefers-reduced-motion users, so this component no longer computes
  // duration:0 by hand.
  const transition = { duration: 0.35, ease: [0.16, 1, 0.3, 1] as const };
  const motionProps = {
    initial: { opacity: 0, y: 8 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -8 },
    transition,
  };

  function handleQ0(key: string) {
    setInterview((prev) => answer(prev, Q0_IN_INDONESIA.id, key));
  }

  function handleDate(value: string) {
    if (!value) return;
    setInterview((prev) => answer(prev, Q0_EXPIRY_DATE.id, value));
  }

  function handleSkipDate() {
    setInterview((prev) => skip(prev, Q0_EXPIRY_DATE.id));
  }

  function handleCategory(key: string) {
    setInterview((prev) => answer(prev, Q1_CATEGORY.id, key));
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className="vo2" data-funnel="visa">
        <div
          className="mx-auto max-w-xl rounded-2xl border p-6 sm:p-8"
          style={{
            background: "var(--surface-raised)",
            borderColor: "var(--border-default)",
          }}
        >
          <h1
            className="text-2xl font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Visa Oracle
          </h1>

          <AnimatePresence mode="wait">
            {stage === "intro" && (
              <motion.div
                key="intro"
                {...motionProps}
                className="mt-4 space-y-4"
              >
                <section aria-labelledby="vo2-framing-heading">
                  <p
                    id="vo2-framing-heading"
                    ref={focusOnMount}
                    tabIndex={-1}
                    className="text-base leading-relaxed focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                    style={{
                      color: "var(--text-secondary)",
                      outlineColor: "var(--vo2-branch-active)",
                    }}
                  >
                    Visa Oracle is a map, not an application. Answer honestly,
                    including &ldquo;I don&apos;t know&rdquo; — nothing here is
                    filed, nothing decided for you.
                  </p>
                  <button
                    type="button"
                    onClick={() => setBegan(true)}
                    className="mt-4 inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                    style={{
                      // F4: token-based CTA (--vo2-cta/--vo2-cta-text), never
                      // the funnel-wide accent — under editorial that accent
                      // resolves to red, which is (a) reserved for the urgent
                      // lane tone and (b) fails AA for white 14px text. See
                      // visa-oracle-v2.css for the computed contrast ratio.
                      background: "var(--vo2-cta)",
                      color: "var(--vo2-cta-text)",
                      outlineColor: "var(--vo2-cta)",
                    }}
                  >
                    Begin
                    <ArrowRight size={16} aria-hidden />
                  </button>
                </section>
              </motion.div>
            )}

            {stage === "q0" && (
              <motion.div key="q0" {...motionProps} className="mt-4">
                <fieldset className="space-y-3 border-0 p-0">
                  <legend
                    ref={focusOnMount}
                    tabIndex={-1}
                    className="text-lg font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                    style={{
                      color: "var(--text-primary)",
                      outlineColor: "var(--vo2-branch-active)",
                    }}
                  >
                    {t(Q0_IN_INDONESIA.prompt)}
                  </legend>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    {Q0_IN_INDONESIA.options.map((opt) => (
                      <button
                        key={opt.key}
                        type="button"
                        onClick={() => handleQ0(opt.key)}
                        className="flex-1 rounded-xl border px-4 py-3 text-left text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                        style={{
                          borderColor: "var(--vo2-branch)",
                          color: "var(--text-primary)",
                          outlineColor: "var(--vo2-branch-active)",
                        }}
                      >
                        {t(opt.label)}
                      </button>
                    ))}
                  </div>
                  <p
                    className="text-xs"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    {t(Q0_IN_INDONESIA.whyWeAsk)}
                  </p>
                </fieldset>
              </motion.div>
            )}

            {stage === "date" && (
              <motion.div
                key="date"
                {...motionProps}
                className="mt-4 space-y-3"
              >
                <label
                  htmlFor="vo2-expiry-date"
                  ref={focusOnMount}
                  tabIndex={-1}
                  className="block text-lg font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                  style={{
                    color: "var(--text-primary)",
                    outlineColor: "var(--vo2-branch-active)",
                  }}
                >
                  {t(Q0_EXPIRY_DATE.prompt)}
                </label>
                {Q0_EXPIRY_DATE.hint && (
                  <p
                    className="text-xs"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    {t(Q0_EXPIRY_DATE.hint)}
                  </p>
                )}
                <input
                  id="vo2-expiry-date"
                  type="date"
                  onChange={(event) => handleDate(event.target.value)}
                  className="w-full rounded-xl border px-4 py-3 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                  style={{
                    borderColor: "var(--vo2-branch)",
                    color: "var(--text-primary)",
                    background: "var(--surface-sunken)",
                    outlineColor: "var(--vo2-branch-active)",
                  }}
                />
                {Q0_EXPIRY_DATE.skipAssumption && (
                  <button
                    type="button"
                    onClick={handleSkipDate}
                    className="text-xs underline underline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {t(Q0_EXPIRY_DATE.skipAssumption.label)}
                  </button>
                )}
                <p
                  className="text-xs"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {t(Q0_EXPIRY_DATE.whyWeAsk)}
                </p>
              </motion.div>
            )}

            {stage === "onshore-done" && laneEntry && (
              <motion.div
                key="onshore-done"
                {...motionProps}
                className="mt-4 space-y-4"
              >
                <div
                  role="status"
                  aria-live="polite"
                  ref={focusOnMount}
                  tabIndex={-1}
                  className="rounded-xl border px-4 py-3 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                  style={{
                    borderColor: LANE_TONE_VAR[laneEntry.tone],
                    color: LANE_TONE_VAR[laneEntry.tone],
                    outlineColor: LANE_TONE_VAR[laneEntry.tone],
                  }}
                >
                  {t(laneEntry.text)}
                </div>
                <PlaceholderCard />
              </motion.div>
            )}

            {stage === "categories" && (
              <motion.div key="categories" {...motionProps} className="mt-4">
                <h2
                  id="vo2-category-heading"
                  ref={focusOnMount}
                  tabIndex={-1}
                  className="mb-3 text-lg font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                  style={{
                    color: "var(--text-primary)",
                    outlineColor: "var(--vo2-branch-active)",
                  }}
                >
                  {t(Q1_CATEGORY.prompt)}
                </h2>
                <div
                  className="grid grid-cols-1 gap-3 sm:grid-cols-2"
                  role="group"
                  aria-labelledby="vo2-category-heading"
                >
                  {CATEGORIES.map((opt) => (
                    <button
                      key={opt.key}
                      type="button"
                      onClick={() => handleCategory(opt.key)}
                      className="rounded-xl border px-4 py-3 text-left text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                      style={{
                        borderColor: "var(--vo2-branch)",
                        color: "var(--text-primary)",
                        outlineColor: "var(--vo2-branch-active)",
                      }}
                    >
                      {t(opt.label)}
                    </button>
                  ))}
                </div>
                <p
                  className="mt-3 text-xs"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {t(Q1_CATEGORY.whyWeAsk)}
                </p>
              </motion.div>
            )}

            {stage === "category-done" && (
              <motion.div
                key="category-done"
                {...motionProps}
                className="mt-4 space-y-4"
              >
                {selectedCategory && (
                  <p
                    role="status"
                    aria-live="polite"
                    ref={focusOnMount}
                    tabIndex={-1}
                    className="text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                    style={{
                      color: "var(--text-secondary)",
                      outlineColor: "var(--vo2-branch-active)",
                    }}
                  >
                    Noted:{" "}
                    <strong style={{ color: "var(--text-primary)" }}>
                      {t(selectedCategory.label)}
                    </strong>
                    .
                  </p>
                )}
                <PlaceholderCard />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </MotionConfig>
  );
}
