"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import type { Language } from "../_lib/flow";
import { REVIEW_GATE_ITEMS, type OracleQuestion } from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
import { WhyWeAsk } from "./WhyWeAsk";
import { NotSure } from "./NotSure";

export interface QuestionScreenProps {
  language: Language;
  question: OracleQuestion;
  onAnswer: (value: string) => void;
  onSkip: () => void;
  onBack: () => void;
  canGoBack: boolean;
  /** Lane-aware reassurance banner (e.g. expired/urgent onshore copy). */
  noticeI18nKey?: I18nKey;
  /** The remote-income courtesy note (183-day tax mention — never a gate). */
  courtesyNoteI18nKey?: I18nKey;
  /** Finding #5 (adversarial review 2026-07-17): the fact already recorded
   * for THIS question, if any — restores prior selections on re-visit
   * (Back/Edit). Only consumed by the review-gate checklist today (the
   * only `kind` whose local UI state doesn't already derive straight from
   * a single `onAnswer(key)` click). */
  currentAnswer?: string;
}

/**
 * One question per screen — the GOV.UK skeleton (design doc §3). Mandatory
 * Back link, heading receives focus on mount for screen readers, a
 * one-sentence hint, options as large tappable cards (min 44px targets).
 */
export function QuestionScreen({
  language,
  question,
  onAnswer,
  onSkip,
  onBack,
  canGoBack,
  noticeI18nKey,
  courtesyNoteI18nKey,
  currentAnswer,
}: QuestionScreenProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [dateValue, setDateValue] = useState("");
  const [flaggedItems, setFlaggedItems] = useState<Set<string>>(() =>
    parseReviewGateAnswer(currentAnswer),
  );

  useEffect(() => {
    headingRef.current?.focus();
  }, [question.id]);

  const hintKey = `${question.i18nKey}.hint` as I18nKey;
  const hasHint = translate(language, hintKey) !== hintKey;

  return (
    <div className="oracle-question">
      {canGoBack && (
        <button
          type="button"
          className="oracle-question__back"
          onClick={onBack}
        >
          <ArrowLeft aria-hidden="true" size={16} />
          {translate(language, "back.button")}
        </button>
      )}

      {noticeI18nKey && (
        <p className="oracle-question__notice">
          {translate(language, noticeI18nKey)}
        </p>
      )}

      <div>
        <h1 className="oracle-headline" tabIndex={-1} ref={headingRef}>
          {translate(language, question.i18nKey as I18nKey)}
        </h1>
        {hasHint && (
          <p className="oracle-question__hint">
            {translate(language, hintKey)}
          </p>
        )}
      </div>

      {question.whyWeAsk && (
        <WhyWeAsk
          language={language}
          i18nKey={question.whyWeAsk.i18nKey as I18nKey}
          regulation={question.whyWeAsk.regulation}
        />
      )}

      {question.kind === "tiles" && (
        <div
          className="oracle-tiles"
          role="group"
          aria-label={translate(language, question.i18nKey as I18nKey)}
        >
          {question.options.map((option) => (
            <button
              key={option.key}
              type="button"
              className="oracle-tile"
              onClick={() => onAnswer(option.key)}
            >
              {translate(language, option.labelI18nKey as I18nKey)}
            </button>
          ))}
        </div>
      )}

      {(question.kind === "branch" || question.kind === "choice") && (
        <div
          className="oracle-options"
          role="group"
          aria-label={translate(language, question.i18nKey as I18nKey)}
        >
          {question.options.map((option) => (
            <button
              key={option.key}
              type="button"
              className="oracle-option-card"
              onClick={() => onAnswer(option.key)}
            >
              <span>{translate(language, option.labelI18nKey as I18nKey)}</span>
              <ArrowRight aria-hidden="true" size={18} />
            </button>
          ))}
        </div>
      )}

      {courtesyNoteI18nKey && (
        <p className="oracle-question__notice">
          {translate(language, courtesyNoteI18nKey)}
        </p>
      )}

      {question.kind === "date" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (dateValue) onAnswer(dateValue);
          }}
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-4)",
          }}
        >
          <label
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-2)",
            }}
          >
            <span className="oracle-eyebrow">
              {translate(language, "q.permit_expiry.label")}
            </span>
            <input
              type="date"
              required
              value={dateValue}
              onChange={(e) => setDateValue(e.target.value)}
              style={{
                minHeight: 44,
                padding: "0.5rem 0.75rem",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--oracle-border-strong)",
                background: "var(--oracle-bg-elevated)",
                color: "var(--oracle-ink)",
                fontSize: "var(--text-base)",
                width: "fit-content",
              }}
            />
          </label>
          <button
            type="submit"
            className="oracle-option-card"
            style={{ width: "fit-content" }}
          >
            {translate(language, "confirmation.cta")}
            <ArrowRight aria-hidden="true" size={18} />
          </button>
        </form>
      )}

      {question.kind === "review-gate" && (
        <ReviewGateChecklist
          language={language}
          flagged={flaggedItems}
          onToggle={(item) =>
            setFlaggedItems((prev) => toggleReviewGateItem(prev, item))
          }
          onContinue={() => onAnswer(serializeReviewGateAnswer(flaggedItems))}
        />
      )}

      {question.notSure && <NotSure language={language} onSkip={onSkip} />}
    </div>
  );
}

/** Finding #5 (adversarial review 2026-07-17): parse the persisted CSV
 * review-gate answer back into a selection set — the inverse of
 * `serializeReviewGateAnswer` below, used to restore prior selections when
 * the question is re-visited via Back/Edit. */
function parseReviewGateAnswer(value: string | undefined): Set<string> {
  if (!value) return new Set();
  return new Set(value.split(",").filter(Boolean));
}

/** The persisted fact value: "none" alone, or the sorted comma-joined set
 * of flagged item keys — never both (mutual exclusivity is enforced by
 * `toggleReviewGateItem`, not here). Still option keys, never free text. */
function serializeReviewGateAnswer(items: Set<string>): string {
  return Array.from(items).sort().join(",");
}

/** "None of these apply to me" is mutually exclusive with every real flag:
 * picking it clears everything else, and picking any real flag drops
 * "none" if it was set. Toggling an already-selected item deselects it
 * (so the checklist can always return to its unanswered, Continue-disabled
 * state rather than silently falling back to a default). */
function toggleReviewGateItem(prev: Set<string>, item: string): Set<string> {
  if (item === "none") {
    return prev.has("none") ? new Set() : new Set(["none"]);
  }
  const next = new Set(prev);
  next.delete("none");
  if (next.has(item)) next.delete(item);
  else next.add(item);
  return next;
}

function ReviewGateChecklist({
  language,
  flagged,
  onToggle,
  onContinue,
}: {
  language: Language;
  flagged: Set<string>;
  onToggle: (item: string) => void;
  onContinue: () => void;
}) {
  // Finding #5: Continue stays disabled until an explicit choice is made —
  // no more silent "press Continue with nothing checked = none" default.
  const hasSelection = flagged.size > 0;
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-4)",
      }}
    >
      <fieldset
        className="oracle-checklist"
        style={{ border: "none", padding: 0, margin: 0 }}
      >
        <legend className="oracle-sr-only">
          {translate(language, "q.review_gate" as I18nKey)}
        </legend>
        {REVIEW_GATE_ITEMS.map((item) => (
          <label key={item} className="oracle-checklist__item">
            <input
              type="checkbox"
              checked={flagged.has(item)}
              onChange={() => onToggle(item)}
            />
            {translate(language, `q.review_gate.item.${item}` as I18nKey)}
          </label>
        ))}
      </fieldset>
      <button
        type="button"
        className="oracle-option-card"
        style={{ width: "fit-content" }}
        onClick={onContinue}
        disabled={!hasSelection}
        aria-disabled={!hasSelection}
      >
        {translate(language, "confirmation.cta")}
        <ArrowRight aria-hidden="true" size={18} />
      </button>
    </div>
  );
}
