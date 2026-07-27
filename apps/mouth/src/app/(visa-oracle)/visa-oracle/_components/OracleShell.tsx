"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { ArrowRight, Sparkles } from "lucide-react";
import { useReducedMotion } from "framer-motion";
import { useOracleFlow } from "../_lib/flow";
import { QUESTIONS, getLane } from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
import { sendShadowEvaluation } from "../_lib/shadow-client";
import {
  mapOracleFactsToApplicantFacts,
  stableFactsKey,
} from "../_lib/fact-mapper";
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
  const reducedMotion = useReducedMotion();

  /**
   * "Oracle deals your card" (design doc §3 interaction #4): the ONLY call
   * site that ever moves confirmation → verdict. Where the browser
   * supports the View Transitions API and motion isn't reduced, the
   * `advance()` dispatch (and the DOM update it causes) runs inside
   * `document.startViewTransition()` — `flushSync` forces React to apply
   * the resulting re-render synchronously inside that callback, which the
   * API requires to capture an accurate "after" snapshot. LivingTree's
   * "verdict" trunk row and VerdictReveal's hero card share a
   * `view-transition-name`, so the browser morphs geometry between them.
   * Every other environment (no API support, or `prefers-reduced-motion`)
   * falls through to a plain `advance()` — an instant swap, with
   * VerdictReveal's own spring reveal (unaffected by any of this) as the
   * craft fallback either way.
   */
  const revealVerdict = useCallback(() => {
    const startViewTransition =
      typeof document !== "undefined"
        ? (
            document as Document & {
              startViewTransition?: (callback: () => void) => unknown;
            }
          ).startViewTransition
        : undefined;
    if (reducedMotion || !startViewTransition) {
      advance();
      return;
    }
    startViewTransition.call(document, () => {
      flushSync(() => advance());
    });
  }, [advance, reducedMotion]);

  useEffect(() => {
    if (current.kind === "verdict" && frozenToday === null) {
      setFrozenToday(new Date());
    }
  }, [current.kind, frozenToday]);

  /**
   * SHADOW wiring (2026-07-27, dedup corrected same day — TWO independent
   * defects fixed, both traced to the same root cause: the dedupe key was
   * wrong in BOTH of its dimensions). An invisible, fire-and-forget POST
   * to the LIVE `visa_engine` endpoint, fired once per DISTINCT completed
   * interview — the moment a verdict is shown for a wire payload that
   * hasn't already been shadow-posted THIS attempt. Sibling to the
   * `frozenToday` effect above (its own `useRef`, so this effect's own
   * re-runs never double-fire independently of that one), and reads
   * `frozenToday` rather than reaching for `new Date()` itself, for the
   * SAME reason `frozenToday` exists at all (Finding #9, above): a second
   * independent clock read here could disagree with the verdict/lane
   * computation across a UTC-midnight boundary. Gated on
   * `frozenToday !== null` so this never fires on the render where
   * `current.kind` first becomes "verdict" but `frozenToday` is still
   * `null` — it fires on the FOLLOWING render, once frozenToday's own
   * effect has committed a value, guaranteeing both effects always agree
   * on "today".
   *
   * THE ONE INVARIANT: `sendShadowEvaluation` is synchronous (`void`,
   * never a `Promise`), never throws, and its result is never read — see
   * `shadow-client.ts`'s docstring for the full contract. During SHADOW
   * this call has ZERO observable effect on anything this component
   * renders, by construction, not by convention: no state it returns is
   * ever stored, no error it could throw is ever allowed to escape.
   *
   * THE SEMANTIC CONTRACT: exactly one SHADOW POST per (interview attempt
   * x distinct wire payload). Two dimensions, two independent fixes:
   *
   *  - DEDUPE ON CONTENT, not mount (first correction): the original
   *    "fire once per mount, never reset" latch was wrong — this route
   *    ships affordances (REVIEW_ANSWERS "Edit answers", SELECT_CATEGORY
   *    "what instead") that legitimately return the user from "verdict"
   *    to "confirmation" and then to a SECOND verdict in the SAME mount
   *    with DIFFERENT facts. A mount-scoped latch fired on the first
   *    verdict and silently ate every honest re-verdict after an edit.
   *
   *  - DEDUPE ON THE WIRE PAYLOAD, not raw UI facts (second correction,
   *    same day): `state.facts` is the raw interview answers — but
   *    `remote_income` (and every other UI-only field with no
   *    `FactPath` — see `fact-mapper.ts`'s module docstring) has NO
   *    representation in what the engine actually receives. Keying on
   *    raw facts meant editing an answer with no wire effect (change
   *    `remote_income` from "above" to "below", re-confirm) produced a
   *    SECOND POST whose `facts` object was byte-identical to the
   *    first — a duplicate row the engine cannot tell apart from a
   *    retry. The key below is computed from
   *    `mapOracleFactsToApplicantFacts(...).facts` (`stableFactsKey`,
   *    `fact-mapper.ts`) — the SAME transform `shadow-client.ts` applies
   *    before POSTing — so "distinct" means what the docstring always
   *    claimed it meant: distinct in what actually goes over the wire.
   *
   *  - DEDUPE SCOPED TO THE ATTEMPT, not the component lifetime (third
   *    correction, same day): a `useRef` that is NEVER cleared survives
   *    RESTART, which is a real, user-visible "throw everything away and
   *    start over" — `flow.ts`'s RESTART wipes `history`/`facts` back to
   *    "framing" but the component itself never remounts. A user who
   *    completes an interview, clicks "Start over", and retraces the
   *    EXACT SAME answers is running a second, genuinely independent
   *    interview — and got silently swallowed as a "duplicate" of the
   *    first, because the ref never forgot what it had already sent.
   *    Two honest interviews became one row — missing evidence, worse
   *    than a wrong one.
   *
   * ATTEMPT IDENTITY — the design choice this fix had to make, and why it
   * survives a NEW way of reaching "verdict" added next year without
   * being touched: `flow.ts`'s `FlowState.attempt` is a counter bumped
   * ONLY by the reducer's own `resetFlow` primitive (RESTART, and the
   * SELECT_CATEGORY defensive fallback — both a full wipe back to
   * "framing", which is what a reset structurally IS). Every action that
   * returns to "verdict" by TRUNCATING history instead of wiping it
   * (REVIEW_ANSWERS today, SELECT_CATEGORY's happy path today, and
   * whatever gets added later) never touches `attempt`, because none of
   * them call `resetFlow`. This effect therefore never has to enumerate
   * "which actions count as a new attempt" — the same trap that bit this
   * bug's first-ever fix, which enumerated REVIEW_ANSWERS/SELECT_CATEGORY
   * for the CONTENT dimension and was right to avoid enumerating them
   * again here for the LIFETIME dimension. `attempt` changing is
   * SUFFICIENT AND NECESSARY evidence of a reset, by construction, not by
   * a list this effect has to keep in sync with `flow.ts`.
   *
   * `shadowSentRef` holds the CURRENT attempt's set of already-posted
   * wire-payload keys (`{ attempt, keys: Set<string> }`). Each arrival at
   * "verdict": if `state.attempt` has moved on from what the ref
   * remembers, the set is reset empty (a new attempt starts with a clean
   * slate — the SAME retraced answers in a new attempt must still post,
   * scenario D of the shipped truth table); then the current wire-facts
   * key is looked up in that set — already present means this exact
   * payload was already shadow-posted THIS attempt (no new row, whether
   * that's a pure re-render or an edit-and-revert with no material wire
   * change), absent means fire and remember it.
   */
  const shadowSentRef = useRef<{ attempt: number; keys: Set<string> } | null>(
    null,
  );
  useEffect(() => {
    if (current.kind !== "verdict" || frozenToday === null) return;

    // Same transform `shadow-client.ts` applies before POSTing — the
    // dedupe key must be computed from what the engine actually receives,
    // never from raw `state.facts`. `assessmentId` here is a fixed
    // placeholder: this call exists only to derive `.facts` for the key,
    // its `assessment_id`/`collected_at` are never read, and the REAL
    // POST (inside `sendShadowEvaluation`) generates its own fresh
    // `crypto.randomUUID()` — this placeholder never reaches the network.
    const wireFacts = mapOracleFactsToApplicantFacts(state.facts, {
      assessmentId: "shadow-dedupe-key",
      collectedAt: frozenToday,
    }).facts;
    const factsKey = stableFactsKey(wireFacts);

    if (
      shadowSentRef.current === null ||
      shadowSentRef.current.attempt !== state.attempt
    ) {
      shadowSentRef.current = { attempt: state.attempt, keys: new Set() };
    }
    if (shadowSentRef.current.keys.has(factsKey)) return;
    shadowSentRef.current.keys.add(factsKey);
    sendShadowEvaluation(state.facts, frozenToday);
  }, [current.kind, frozenToday, state.facts, state.attempt]);

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
              onEditQuestion={edit}
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
                onConfirm={revealVerdict}
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
                  className="oracle-no-print"
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
