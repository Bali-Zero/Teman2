"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
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
 * Ties framer-motion transition duration to prefers-reduced-motion, in the
 * same spirit as the `@media (prefers-reduced-motion: reduce)` block in
 * visa-oracle-v2.css that zeroes --vo2-dur-*. framer-motion transitions
 * are JS values, not CSS, so this mirrors the token's intent (350ms /
 * --vo2-dur-flow, ease matching --vo2-ease-out) rather than reading the
 * CSS custom property directly.
 */
function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mql.matches);
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return reduced;
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
  const prefersReducedMotion = usePrefersReducedMotion();

  const stage = deriveStage(began, interview);
  const laneEntry = interview.lane ? LANE_COPY[interview.lane] : null;
  const categoryKey = interview.answers[Q1_CATEGORY.id];
  const selectedCategory = CATEGORIES.find((c) => c.key === categoryKey);

  // Mirrors --vo2-dur-flow (350ms) / --vo2-ease-out; zeroed under
  // prefers-reduced-motion, matching the CSS token block.
  const transition = prefersReducedMotion
    ? { duration: 0 }
    : { duration: 0.35, ease: [0.16, 1, 0.3, 1] as const };
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
            <motion.div key="intro" {...motionProps} className="mt-4 space-y-4">
              <section aria-labelledby="vo2-framing-heading">
                <p
                  id="vo2-framing-heading"
                  className="text-base leading-relaxed"
                  style={{ color: "var(--text-secondary)" }}
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
                    background: "var(--vo2-branch-active)",
                    color: "var(--text-on-accent)",
                    outlineColor: "var(--vo2-branch-active)",
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
                  className="text-lg font-medium"
                  style={{ color: "var(--text-primary)" }}
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
            <motion.div key="date" {...motionProps} className="mt-4 space-y-3">
              <label
                htmlFor="vo2-expiry-date"
                className="block text-lg font-medium"
                style={{ color: "var(--text-primary)" }}
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
              <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
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
                className="rounded-xl border px-4 py-3 text-sm font-medium"
                style={{
                  borderColor: LANE_TONE_VAR[laneEntry.tone],
                  color: LANE_TONE_VAR[laneEntry.tone],
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
                className="mb-3 text-lg font-medium"
                style={{ color: "var(--text-primary)" }}
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
                  className="text-sm"
                  style={{ color: "var(--text-secondary)" }}
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
  );
}
