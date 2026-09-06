"use client";

import { useEffect, useRef } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import {
  localized,
  type InterviewAssumption,
} from "../_lib/outcome-view-model";
import {
  QUESTIONS,
  formatIsoDateForDisplay,
  questionPromptI18nKey,
  type OracleFacts,
} from "../_lib/tree";
import type { Language } from "../_lib/flow";
import { translate, type I18nKey } from "../_lib/i18n";

export interface ConfirmationCardProps {
  language: Language;
  facts: OracleFacts;
  assumptions: readonly InterviewAssumption[];
  interviewBranchesRemaining: number;
  onBack: () => void;
  onEdit: (questionId: string) => void;
  onConfirm: () => void;
}

/** Exported so OutcomeSheet's print-only "your answers" recap (design doc
 * §3 print anatomy) can render the exact same rows in the exact same
 * order without duplicating this list — the printed verdict page is the
 * one place besides this screen the facts summary ever appears. */
export const DISPLAY_ORDER = Object.keys(QUESTIONS);

const GROUP_ORDER = [
  "location",
  "identity",
  "intent",
  "details",
  "review",
] as const;

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

function countryCodesDisplay(language: Language, value: string): string {
  const codes = value.split(",");
  try {
    const names = new Intl.DisplayNames([localeFor(language)], {
      type: "region",
    });
    return codes
      .map((code) => `${names.of(code) ?? code} (${code})`)
      .join(", ");
  } catch {
    return codes.join(", ");
  }
}

export function formatFactDisplay(
  language: Language,
  id: string,
  value: string,
): string {
  const question = QUESTIONS[id];
  if (!question) return value;
  if (question.kind === "date") {
    return formatIsoDateForDisplay(value, localeFor(language));
  }
  if (question.kind === "country-codes") {
    return countryCodesDisplay(language, value);
  }
  if (question.kind === "status-code") return value;
  if (question.kind === "number" && question.numberInput) {
    return `${Number(value).toLocaleString(localeFor(language))} ${translate(
      language,
      question.numberInput.unitI18nKey as I18nKey,
    )}`;
  }
  if (question.kind === "review-gate") {
    return reviewGateDisplay(language, value);
  }
  const option = question.options.find((candidate) => candidate.key === value);
  return option ? translate(language, option.labelI18nKey as I18nKey) : value;
}

function assumptionDisplay(language: Language, questionId: string): string {
  const key = `assumption.${questionId}` as I18nKey;
  const specific = translate(language, key);
  if (specific !== key) return specific;
  const question = QUESTIONS[questionId];
  return translate(language, "assumption.generic", {
    question: question
      ? translate(language, question.i18nKey as I18nKey)
      : questionId,
  });
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
  interviewBranchesRemaining,
  onBack,
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
    return {
      id,
      group: question.group,
      label: translate(
        language,
        questionPromptI18nKey(question, facts) as I18nKey,
      ),
      value: formatFactDisplay(language, id, value),
    };
  });

  return (
    <div className="oracle-question">
      <button type="button" className="oracle-question__back" onClick={onBack}>
        <ArrowLeft aria-hidden="true" size={16} />
        {translate(language, "back.button")}
      </button>
      <h1 className="oracle-headline" tabIndex={-1} ref={headingRef}>
        {translate(language, "confirmation.title")}
      </h1>

      <section>
        <h2 className="oracle-outcome__section-title">
          {translate(language, "confirmation.your_answers")}
        </h2>
        {GROUP_ORDER.map((group) => {
          const groupedRows = rows.filter((row) => row.group === group);
          if (groupedRows.length === 0) return null;
          return (
            <div key={group} className="oracle-confirmation__section">
              <h3 className="oracle-confirmation__group-title">
                {translate(language, `confirmation.group.${group}` as I18nKey)}
              </h3>
              <div className="oracle-confirmation__group">
                {groupedRows.map((row) => (
                  <div key={row.id} className="oracle-confirmation__row">
                    <span className="oracle-confirmation__label">
                      {row.label}
                    </span>
                    <span className="oracle-confirmation__value">
                      {row.value}
                    </span>
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
            </div>
          );
        })}
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
                  {a.message
                    ? localized(a.message, language)
                    : assumptionDisplay(language, a.questionId)}
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
          count: interviewBranchesRemaining,
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
