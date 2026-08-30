"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, X } from "lucide-react";
import type { Language } from "../_lib/flow";
import { REVIEW_GATE_ITEMS, type OracleQuestion } from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
import {
  canonicalCountryCodes,
  getCountryOptions,
  isIsoAlpha2Code,
} from "../_lib/countries";
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
  /** Optional context note that is never interpreted as an eligibility gate. */
  courtesyNoteI18nKey?: I18nKey;
  /** Set when the flow reducer refused the last answer to THIS question
   * because it contradicts an already-known fact (`FlowState.blockedAnswer`
   * — see flow.ts). Rendered as an assertive, visually distinct banner:
   * this is a block, not a courtesy note. */
  conflictI18nKey?: I18nKey;
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
  conflictI18nKey,
  currentAnswer,
}: QuestionScreenProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [dateValue, setDateValue] = useState("");
  const [numberValue, setNumberValue] = useState("");
  const [codeValue, setCodeValue] = useState("");
  const [countryCodes, setCountryCodes] = useState<readonly string[]>([]);
  const [inputError, setInputError] = useState<I18nKey | null>(null);
  const [flaggedItems, setFlaggedItems] = useState<Set<string>>(() =>
    parseReviewGateAnswer(currentAnswer),
  );

  useEffect(() => {
    headingRef.current?.focus();
  }, [question.id]);

  useEffect(() => {
    setDateValue(
      question.kind === "date" && currentAnswer !== "unsure"
        ? (currentAnswer ?? "")
        : "",
    );
    setNumberValue(
      question.kind === "number" && currentAnswer !== "unsure"
        ? (currentAnswer ?? "")
        : "",
    );
    setCodeValue(
      question.kind === "status-code" && currentAnswer !== "unsure"
        ? (currentAnswer ?? "")
        : "",
    );
    setCountryCodes(
      question.kind === "country-codes" && currentAnswer !== "unsure"
        ? (currentAnswer ?? "")
            .split(",")
            .filter((code) => isIsoAlpha2Code(code))
        : [],
    );
    setInputError(null);
    setFlaggedItems(parseReviewGateAnswer(currentAnswer));
  }, [currentAnswer, question.id, question.kind]);

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

      {conflictI18nKey && (
        <p
          className="oracle-question__notice oracle-question__notice--conflict"
          role="alert"
        >
          {translate(language, conflictI18nKey)}
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
          decisionMapping={question.decisionMapping}
        />
      )}

      {question.decisionMapping.kind === "HUMAN_CONTEXT" && (
        <p className="oracle-decision-boundary">
          {translate(language, "question.human_context_notice")}
        </p>
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
              {translate(
                language,
                (question.dateInput?.labelI18nKey ??
                  "q.permit_expiry.label") as I18nKey,
              )}
            </span>
            <input
              type="date"
              required
              max={question.dateInput?.maxToday ? localIsoDate() : undefined}
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

      {question.kind === "country-codes" && question.codeInput && (
        <CountryPicker
          language={language}
          questionId={question.id}
          labelI18nKey={question.codeInput.labelI18nKey as I18nKey}
          multiple={question.codeInput.multiple}
          maxSelections={question.codeInput.maxSelections ?? 1}
          selectedCodes={countryCodes}
          onChange={setCountryCodes}
          onSubmit={(codes) => onAnswer(codes)}
          onNotListed={onSkip}
        />
      )}

      {question.kind === "status-code" && question.codeInput && (
        <form
          className="oracle-input-form"
          onSubmit={(event) => {
            event.preventDefault();
            const normalized = normalizeStatusCode(
              codeValue,
              question.codeInput!.maxLength ?? 32,
            );
            if (normalized === null) {
              setInputError("question.invalid_status_code");
              return;
            }
            setInputError(null);
            onAnswer(normalized);
          }}
        >
          <label className="oracle-input-label">
            <span className="oracle-eyebrow">
              {translate(language, question.codeInput.labelI18nKey as I18nKey)}
            </span>
            <input
              type="text"
              required
              autoCapitalize="characters"
              autoCorrect="off"
              spellCheck={false}
              maxLength={question.codeInput.maxLength ?? 32}
              value={codeValue}
              onChange={(event) => {
                setCodeValue(event.target.value.toUpperCase());
                setInputError(null);
              }}
              placeholder={"E31"}
              aria-describedby={inputError ? `${question.id}-error` : undefined}
              aria-invalid={inputError !== null}
              className="oracle-form-control"
            />
          </label>
          {inputError && (
            <p
              id={`${question.id}-error`}
              className="oracle-input-error"
              role="alert"
            >
              {translate(language, inputError)}
            </p>
          )}
          <button type="submit" className="oracle-option-card oracle-submit">
            {translate(language, "question.continue")}
            <ArrowRight aria-hidden="true" size={18} />
          </button>
        </form>
      )}

      {question.kind === "number" && question.numberInput && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const value = Number(numberValue);
            if (
              !Number.isSafeInteger(value) ||
              value < question.numberInput!.min ||
              value > question.numberInput!.max
            ) {
              return;
            }
            onAnswer(String(value));
          }}
          className="oracle-input-form"
        >
          <label className="oracle-input-label">
            <span className="oracle-eyebrow">
              {translate(
                language,
                question.numberInput.labelI18nKey as I18nKey,
              )}
            </span>
            <span className="oracle-number-input">
              <input
                type="number"
                inputMode="numeric"
                required
                min={question.numberInput.min}
                max={question.numberInput.max}
                step={question.numberInput.step}
                value={numberValue}
                onChange={(event) => setNumberValue(event.target.value)}
                className="oracle-form-control"
              />
              <span>
                {translate(
                  language,
                  question.numberInput.unitI18nKey as I18nKey,
                )}
              </span>
            </span>
          </label>
          <button type="submit" className="oracle-option-card oracle-submit">
            {translate(language, "question.continue")}
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

function CountryPicker({
  language,
  questionId,
  labelI18nKey,
  multiple,
  maxSelections,
  selectedCodes,
  onChange,
  onSubmit,
  onNotListed,
}: {
  language: Language;
  questionId: string;
  labelI18nKey: I18nKey;
  multiple: boolean;
  maxSelections: number;
  selectedCodes: readonly string[];
  onChange: (codes: readonly string[]) => void;
  onSubmit: (codes: string) => void;
  onNotListed: () => void;
}) {
  const [pendingCode, setPendingCode] = useState("");
  const [countryQuery, setCountryQuery] = useState("");
  const options = useMemo(() => getCountryOptions(language), [language]);
  const nameByCode = useMemo(
    () =>
      new Map<string, string>(options.map(({ code, name }) => [code, name])),
    [options],
  );
  // Predictive filter (D-V5): 190+ countries in a plain <select> forces
  // scroll-and-scan. This narrows the <option> list client-side by name or
  // code — no new dependency, no change to how a selection is committed.
  const filteredOptions = useMemo(() => {
    const query = countryQuery.trim().toLowerCase();
    if (!query) return options;
    return options.filter(
      ({ code, name }) =>
        name.toLowerCase().includes(query) ||
        code.toLowerCase().includes(query),
    );
  }, [options, countryQuery]);
  const selectId = `${questionId}-country`;
  const searchId = `${questionId}-country-search`;
  const maxReached = selectedCodes.length >= maxSelections;

  useEffect(() => {
    setPendingCode("");
    setCountryQuery("");
  }, [language, questionId]);

  const addPendingCountry = () => {
    if (!isIsoAlpha2Code(pendingCode)) return;
    if (selectedCodes.length >= maxSelections) return;
    onChange(
      multiple
        ? Array.from(new Set([...selectedCodes, pendingCode])).sort()
        : [pendingCode],
    );
    setPendingCode("");
  };

  const canonical = canonicalCountryCodes(selectedCodes, multiple);

  return (
    <form
      className="oracle-input-form oracle-country-picker"
      onSubmit={(event) => {
        event.preventDefault();
        if (canonical) onSubmit(canonical);
      }}
    >
      <label className="oracle-input-label" htmlFor={selectId}>
        <span className="oracle-eyebrow">
          {translate(language, labelI18nKey)}
        </span>
      </label>
      <label className="oracle-input-label" htmlFor={searchId}>
        <span className="oracle-sr-only">
          {translate(language, "question.country_picker.search")}
        </span>
        <input
          id={searchId}
          type="text"
          className="oracle-form-control"
          value={countryQuery}
          onChange={(event) => setCountryQuery(event.target.value)}
          placeholder={translate(
            language,
            "question.country_picker.search_placeholder",
          )}
          autoComplete="off"
        />
      </label>
      <div className="oracle-country-picker__control">
        <select
          id={selectId}
          className="oracle-form-control"
          value={pendingCode}
          onChange={(event) => {
            const value = event.target.value;
            if (value === "not-listed") {
              onChange([]);
              onNotListed();
              return;
            }
            setPendingCode(value);
            if (!multiple && isIsoAlpha2Code(value)) {
              onChange([value]);
            }
          }}
        >
          <option value="">
            {translate(language, "question.country_picker.placeholder")}
          </option>
          {filteredOptions.map(({ code, name }) => (
            <option
              key={code}
              value={code}
              disabled={selectedCodes.includes(code)}
            >
              {name} ({code})
            </option>
          ))}
          <option value="not-listed">
            {translate(language, "question.country_picker.not_listed")}
          </option>
        </select>
        {multiple && (
          <button
            type="button"
            className="oracle-country-picker__add"
            onClick={addPendingCountry}
            disabled={!isIsoAlpha2Code(pendingCode) || maxReached}
          >
            {translate(language, "question.country_picker.add")}
          </button>
        )}
      </div>

      {multiple && maxReached && (
        <p className="oracle-input-error" role="status" aria-live="polite">
          {translate(language, "question.country_picker.max", {
            count: maxSelections,
          })}
        </p>
      )}

      {selectedCodes.length > 0 && (
        <ul
          className="oracle-country-picker__chips"
          aria-label={translate(language, "question.country_picker.selected")}
          aria-live="polite"
        >
          {selectedCodes.map((code) => {
            const name = nameByCode.get(code) ?? code;
            return (
              <li key={code} className="oracle-country-picker__chip">
                <span>
                  {name} ({code})
                </span>
                <button
                  type="button"
                  onClick={() =>
                    onChange(selectedCodes.filter((item) => item !== code))
                  }
                  aria-label={translate(
                    language,
                    "question.country_picker.remove",
                    { country: name },
                  )}
                >
                  <X aria-hidden="true" size={15} />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <button
        type="submit"
        className="oracle-option-card oracle-submit"
        disabled={canonical === null}
      >
        {translate(language, "question.continue")}
        <ArrowRight aria-hidden="true" size={18} />
      </button>
    </form>
  );
}

function localIsoDate(today: Date = new Date()): string {
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function normalizeStatusCode(value: string, maxLength: number): string | null {
  const normalized = value.trim().toUpperCase();
  return normalized.length <= maxLength && /^[A-Z][A-Z0-9-]*$/.test(normalized)
    ? normalized
    : null;
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
