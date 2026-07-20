"use client";

import { useEffect, useRef } from "react";
import { ArrowRight } from "lucide-react";
import type { Assumption } from "../_lib/mock-engine";
import {
  QUESTIONS,
  formatIsoDateForDisplay,
  type OracleFacts,
} from "../_lib/tree";
import type { Language } from "../_lib/flow";
import { translate, type I18nKey } from "../_lib/i18n";

export interface ConfirmationCardProps {
  language: Language;
  facts: OracleFacts;
  assumptions: Assumption[];
  pathsRemaining: number;
  onEdit: (questionId: string) => void;
  onConfirm: () => void;
}

/** Exported so OutcomeSheet's print-only "your answers" recap (design doc
 * §3 print anatomy) can render the exact same rows in the exact same
 * order without duplicating this list — the printed verdict page is the
 * one place besides this screen the facts summary ever appears. */
export const DISPLAY_ORDER = [
  "in_indonesia",
  "permit_expiry",
  "category",
  "work_payer",
  "remote_clients",
  "remote_income",
  "tourism_duration",
  "review_gate",
];

function localeFor(language: Language): string {
  return language === "id" ? "id-ID" : "en-GB";
}

/** Finding #5 consequence: `review_gate` now persists "none" or a sorted
 * CSV of item keys, never the old binary "flagged" sentinel — render each
 * selected item's own label instead of trying (and failing) to resolve a
 * `q.review_gate.opt.<csv>` key that was never defined. */
export function reviewGateDisplay(language: Language, value: string): string {
  const items = value.split(",").filter(Boolean);
  if (items.length === 0 || (items.length === 1 && items[0] === "none")) {
    return translate(language, "q.review_gate.item.none" as I18nKey);
  }
  return items
    .map((item) => translate(language, `q.review_gate.item.${item}` as I18nKey))
    .join(", ");
}

/**
 * "Here's what you told us" — the honesty receipt (Stripe-onboarding
 * pattern, design doc §3): grouped, editable answers before any verdict.
 * Kills the Typeform "I can't see what I said" trap.
 */
export function ConfirmationCard({
  language,
  facts,
  assumptions,
  pathsRemaining,
  onEdit,
  onConfirm,
}: ConfirmationCardProps) {
  // Finding #12 (adversarial review 2026-07-17): every other screen in the
  // interview (QuestionScreen, VerdictReveal) shifts focus to its heading
  // on mount for screen-reader users — the confirmation screen was the one
  // gap in that pattern, silently leaving focus wherever the previous
  // screen left it.
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const rows = DISPLAY_ORDER.filter(
    (id) => facts[id] !== undefined && facts[id] !== "unsure",
  ).map((id) => {
    const question = QUESTIONS[id];
    const value = facts[id];
    // Finding #8: strict, timezone-safe display via tree.ts's shared
    // helper — the old `new Date(value)` + local-zone `.format()` could
    // roll an ISO date back a day for a viewer west of UTC.
    const display =
      id === "permit_expiry"
        ? formatIsoDateForDisplay(value, localeFor(language))
        : id === "review_gate"
          ? reviewGateDisplay(language, value)
          : translate(language, `${question.i18nKey}.opt.${value}` as I18nKey);
    return {
      id,
      label: translate(language, question.i18nKey as I18nKey),
      value: display,
    };
  });

  return (
    <div className="oracle-question">
      <h1 className="oracle-headline" tabIndex={-1} ref={headingRef}>
        {translate(language, "confirmation.title")}
      </h1>

      <section>
        <h2 className="oracle-outcome__section-title">
          {translate(language, "confirmation.your_answers")}
        </h2>
        <div className="oracle-confirmation__group">
          {rows.map((row) => (
            <div key={row.id} className="oracle-confirmation__row">
              <span className="oracle-confirmation__label">{row.label}</span>
              <span className="oracle-confirmation__value">{row.value}</span>
              <button
                type="button"
                className="oracle-confirmation__edit"
                onClick={() => onEdit(row.id)}
              >
                {translate(language, "confirmation.edit")}
              </button>
            </div>
          ))}
        </div>
      </section>

      {assumptions.length > 0 && (
        <section>
          <h2 className="oracle-outcome__section-title">
            {translate(language, "confirmation.assumptions_title")}
          </h2>
          <div className="oracle-confirmation__group">
            {assumptions.map((a) => (
              <div
                key={a.questionId}
                className="oracle-confirmation__assumption"
              >
                <span>
                  {translate(language, `assumption.${a.questionId}` as I18nKey)}
                </span>
                <button
                  type="button"
                  className="oracle-confirmation__edit"
                  onClick={() => onEdit(a.questionId)}
                >
                  {translate(language, "confirmation.edit")}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      <p className="oracle-question__hint">
        {translate(language, "confirmation.price_preview")}
      </p>
      <p
        className="oracle-tabular-nums"
        style={{ margin: 0, color: "var(--oracle-ink-muted)" }}
      >
        {translate(language, "confirmation.paths_remaining", {
          count: pathsRemaining,
        })}
      </p>

      <button
        type="button"
        className="oracle-option-card"
        style={{ width: "fit-content" }}
        onClick={onConfirm}
      >
        {translate(language, "confirmation.cta")}
        <ArrowRight aria-hidden="true" size={18} />
      </button>
    </div>
  );
}
