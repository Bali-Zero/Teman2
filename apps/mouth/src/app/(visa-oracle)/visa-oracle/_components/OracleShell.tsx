"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Sparkles } from "lucide-react";
import { useOracleFlow } from "../_lib/flow";
import { QUESTIONS, getLane } from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
import { LivingTree } from "./LivingTree";
import { PathsCounter } from "./PathsCounter";
import { QuestionScreen } from "./QuestionScreen";
import { ConfirmationCard } from "./ConfirmationCard";
import { VerdictReveal } from "./VerdictReveal";
import { OutcomeSheet } from "./OutcomeSheet";
import { ThemeToggle, type OracleTheme } from "./ThemeToggle";
import { LanguageToggle } from "./LanguageToggle";

const HIDE_COUNTER_ON = new Set(["in_indonesia", "permit_expiry"]);

/**
 * Layout scaffold + orchestrator (spec item 9): constellation backdrop,
 * theme + language toggles, prototype badge, footer disclaimer — and the
 * one place that owns `useOracleFlow`, wiring every screen to it.
 */
export function OracleShell() {
  const [theme, setTheme] = useState<OracleTheme>("light");

  // Finding #9 (adversarial review 2026-07-17): before this fix, the
  // verdict/outcome screens read TWO independently-instantiated `new
  // Date()` snapshots (one inside `useOracleFlow`'s `evaluate()` memo, one
  // inside `OutcomeSheet`'s own `today` default) — close in time but never
  // guaranteed identical, so a render right at a UTC-midnight lane
  // boundary could disagree with itself about `result.state` vs. the
  // freshness stamp / overstay-lane check. `frozenToday` is captured once,
  // the first render that reaches "verdict", and held for the rest of
  // that visit — every date-sensitive computation downstream (the hook's
  // `evaluate()`, OutcomeSheet's freshness stamp and lane check) reads the
  // SAME Date object from then on, not a fresh "now" per call.
  const [frozenToday, setFrozenToday] = useState<Date | null>(null);
  const flow = useOracleFlow("en", frozenToday ?? undefined);
  const {
    state,
    current,
    result,
    assumptions,
    canGoBack,
    answer,
    skip,
    advance,
    back,
    edit,
    selectCategory,
    reviewAnswers,
    restart,
    setLanguage,
  } = flow;
  const language = state.language;

  useEffect(() => {
    if (current.kind === "verdict" && frozenToday === null) {
      setFrozenToday(new Date());
    }
  }, [current.kind, frozenToday]);

  const lane = useMemo(() => getLane(state.facts), [state.facts]);

  return (
    <div className="oracle-root" data-oracle-theme={theme} data-funnel="visa">
      <Constellation />
      <div className="oracle-shell">
        <header className="oracle-topbar">
          <span
            className="oracle-badge"
            title={translate(language, "prototype.badge.detail")}
          >
            <Sparkles aria-hidden="true" />
            {translate(language, "prototype.badge")}
          </span>
          <div className="oracle-topbar__actions">
            <LanguageToggle language={language} onChange={setLanguage} />
            <ThemeToggle
              language={language}
              theme={theme}
              onChange={setTheme}
            />
          </div>
        </header>

        <main className="oracle-main">
          <div className="oracle-main__tree">
            <LivingTree
              language={language}
              current={current}
              facts={state.facts}
            />
          </div>

          <div className="oracle-main__content">
            {current.kind === "question" &&
              !HIDE_COUNTER_ON.has(current.questionId) && (
                <div style={{ marginBottom: "var(--space-4)" }}>
                  <PathsCounter
                    language={language}
                    count={result.pathsRemaining}
                    visible
                  />
                </div>
              )}

            {current.kind === "framing" && (
              <div className="oracle-question">
                <h1 className="oracle-headline" tabIndex={-1}>
                  {translate(language, "framing.title")}
                </h1>
                <p className="oracle-subhead">
                  {translate(language, "framing.body")}
                </p>
                <button
                  type="button"
                  className="oracle-option-card"
                  style={{ width: "fit-content" }}
                  onClick={advance}
                >
                  {translate(language, "framing.cta")}
                  <ArrowRight aria-hidden="true" size={18} />
                </button>
              </div>
            )}

            {current.kind === "question" && (
              <QuestionScreen
                key={current.questionId}
                language={language}
                question={QUESTIONS[current.questionId]}
                onAnswer={(value) => answer(current.questionId, value)}
                onSkip={() => skip(current.questionId)}
                onBack={back}
                canGoBack={canGoBack}
                noticeI18nKey={noticeFor(current.questionId, lane)}
                courtesyNoteI18nKey={
                  current.questionId === "remote_income"
                    ? ("q.remote_income.courtesy_note" as I18nKey)
                    : undefined
                }
                currentAnswer={state.facts[current.questionId]}
              />
            )}

            {current.kind === "confirmation" && (
              <ConfirmationCard
                language={language}
                facts={state.facts}
                assumptions={assumptions}
                pathsRemaining={result.pathsRemaining}
                onEdit={edit}
                onConfirm={advance}
              />
            )}

            {current.kind === "verdict" && (
              <>
                <VerdictReveal
                  language={language}
                  state={result.state}
                  eligibility={result.candidates[0]?.eligibility}
                />
                <OutcomeSheet
                  language={language}
                  result={result}
                  facts={state.facts}
                  today={frozenToday ?? undefined}
                  onSelectCategory={selectCategory}
                />
                {/* Finding #15: the verdict screen is never a dead end —
                    both a full restart and a scoped jump back to the
                    confirmation screen (to tweak one answer without
                    re-answering everything) are one click away. */}
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "var(--space-4)",
                    marginTop: "var(--space-6)",
                  }}
                >
                  <button
                    type="button"
                    className="oracle-question__back"
                    onClick={reviewAnswers}
                  >
                    {translate(language, "verdict.edit_answers" as I18nKey)}
                  </button>
                  <button
                    type="button"
                    className="oracle-question__back"
                    onClick={restart}
                  >
                    {translate(language, "restart.button")}
                  </button>
                </div>
              </>
            )}
          </div>
        </main>

        <footer className="oracle-footer">
          <p>{translate(language, "footer.disclaimer")}</p>
        </footer>
      </div>
    </div>
  );
}

function noticeFor(
  questionId: string,
  lane: ReturnType<typeof getLane>,
): I18nKey | undefined {
  if (questionId === "category" && lane)
    return `lane.${lane}.notice` as I18nKey;
  if (
    questionId === "review_gate" &&
    (lane === "expired" || lane === "urgent")
  ) {
    return `lane.${lane}.notice` as I18nKey;
  }
  return undefined;
}

/** Fixed, static SVG stars — mood only, never re-rendered per interaction. */
function Constellation() {
  const stars = useMemo(
    () =>
      Array.from({ length: 18 }, (_, i) => ({
        cx: (i * 53) % 100,
        cy: (i * 37) % 100,
        r: (i % 3) + 0.4,
      })),
    [],
  );
  return (
    <div className="oracle-constellation" aria-hidden="true">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none">
        {stars.map((s, i) => (
          <circle key={i} cx={s.cx} cy={s.cy} r={s.r} />
        ))}
      </svg>
    </div>
  );
}
