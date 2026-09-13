"use client";

import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ChevronDown, TreePine } from "lucide-react";
import {
  getProcessModel,
  getTreeSteps,
  isEditableTreeStep,
  type OracleNode,
} from "../_lib/flow";
import type { Language } from "../_lib/flow";
import type { OracleFacts } from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
import { formatFactDisplay } from "./ConfirmationCard";
import {
  ProcessBranches,
  ProcessProgress,
  type ProcessOutcomeSummary,
} from "./ProcessRail";

export interface LivingTreeProps {
  language: Language;
  current: OracleNode;
  facts: OracleFacts;
  /** Tree tap-to-edit (design doc §3 interaction #6): dispatches the
   * existing `EDIT` action (flow.ts) to jump back to a completed
   * question — same history-truncation + fact-pruning mechanism the
   * confirmation card's own Edit buttons already use. Only ever called
   * for a step `isEditableTreeStep` accepts. */
  onEditQuestion: (questionId: string) => void;
  /** Present only at the terminal node, and only once the engine has
   * answered: the rail names the products the ENGINE returned and never
   * derives one of its own. */
  outcome?: ProcessOutcomeSummary | null;
}

/** The answer already on record for a completed step, rendered next to its
 * jump target so the trunk reads as a list of decisions, not of labels. */
function answerFor(
  language: Language,
  stepId: string,
  facts: OracleFacts,
): string | null {
  const value = facts[stepId];
  if (value === undefined) return null;
  if (value === "unsure") return translate(language, "process.answer_unsure");
  return formatFactDisplay(language, stepId, value);
}

/**
 * THE centerpiece (design doc §3): the product's data structure, rendered
 * honestly — not decoration. Vertical trunk of the interview so far;
 * unselected behavioural branches retract when the user chooses a category.
 * This is interview navigation only, never an eligibility decision.
 * Idle "breathe" on the current step is pure CSS, gated by the
 * `prefers-reduced-motion` media query in oracle.css — this component
 * additionally gates its own JS-driven prune animation via
 * `useReducedMotion()` so both paths honor the setting.
 */
export function LivingTree({
  language,
  current,
  facts,
  onEditQuestion,
  outcome = null,
}: LivingTreeProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const reducedMotion = useReducedMotion();
  const { trunk } = getTreeSteps(current, facts);
  const model = getProcessModel(current, facts);
  const visitedSteps = trunk.filter((step) => step.status !== "pending");
  const breadcrumbSteps = visitedSteps.slice(-4);
  const hasEarlierSteps = visitedSteps.length > breadcrumbSteps.length;

  const srPath = trunk
    .filter((s) => s.status !== "pending")
    .map(
      (s) =>
        `${translate(language, s.labelI18nKey as I18nKey)}: ${translate(
          language,
          `tree.sr_status.${s.status}` as I18nKey,
        )}`,
    );

  // The one live region for the whole rail — rendered ONCE, outside the two
  // `TreePanel` copies (mobile sheet + desktop column), so a prune is
  // announced a single time.
  const pruneAnnouncement =
    model.chosenCategory === null
      ? ""
      : translate(language, "process.announce_prune", {
          count: model.prunedCount,
          category: translate(
            language,
            `q.category.opt.${model.chosenCategory}` as I18nKey,
          ),
        });

  return (
    <>
      {/* Non-visual equivalent — always present, independent of viewport. */}
      <nav
        aria-label={translate(language, "tree.sr_path_label")}
        className="oracle-sr-only"
      >
        <ol>
          {srPath.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ol>
      </nav>

      <p className="oracle-sr-only" role="status" data-process-announce>
        {pruneAnnouncement}
      </p>

      <nav
        className="oracle-breadcrumb"
        aria-label={translate(language, "tree.breadcrumb_label")}
      >
        <ol>
          {hasEarlierSteps && (
            <li className="oracle-breadcrumb__ellipsis" aria-hidden="true">
              …
            </li>
          )}
          {breadcrumbSteps.map((step) => {
            const label = translate(language, step.labelI18nKey as I18nKey);
            return (
              <li key={step.id}>
                {isEditableTreeStep(step) ? (
                  <button
                    type="button"
                    onClick={() => onEditQuestion(step.id)}
                    aria-label={translate(
                      language,
                      "tree.edit_aria" as I18nKey,
                      { question: label },
                    )}
                  >
                    {label}
                  </button>
                ) : (
                  <span
                    aria-current={
                      step.status === "current" ? "step" : undefined
                    }
                  >
                    {label}
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      </nav>

      <button
        type="button"
        className="oracle-tree-minimap-trigger"
        aria-expanded={mobileOpen}
        onClick={() => setMobileOpen((v) => !v)}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "0.4rem",
            minWidth: 0,
            textAlign: "left",
          }}
        >
          <TreePine aria-hidden="true" size={16} />
          {translate(language, "tree.sr_path_label")}
          {" · "}
          <span className="oracle-tabular-nums">
            {translate(language, "process.step_of", {
              current: model.answeredQuestions,
              total: model.totalQuestions,
            })}
          </span>
          {model.chosenCategory !== null && (
            <>
              {" · "}
              {translate(
                language,
                `q.category.opt.${model.chosenCategory}` as I18nKey,
              )}
            </>
          )}
        </span>
        <ChevronDown
          aria-hidden="true"
          size={16}
          style={{
            transform: mobileOpen ? "rotate(180deg)" : "none",
            transition:
              "transform var(--motion-duration-fast) var(--motion-ease-standard)",
          }}
        />
      </button>
      <AnimatePresence initial={false}>
        {mobileOpen && (
          <motion.div
            initial={reducedMotion ? undefined : { height: 0, opacity: 0 }}
            animate={reducedMotion ? undefined : { height: "auto", opacity: 1 }}
            exit={reducedMotion ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: reducedMotion ? 0 : 0.2 }}
            style={{ overflow: "hidden" }}
          >
            <TreePanel
              language={language}
              current={current}
              facts={facts}
              trunk={trunk}
              variant="mobile"
              outcome={outcome}
              reducedMotion={!!reducedMotion}
              onEditQuestion={onEditQuestion}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <div className="oracle-tree--desktop">
        <TreePanel
          language={language}
          current={current}
          facts={facts}
          trunk={trunk}
          variant="desktop"
          outcome={outcome}
          reducedMotion={!!reducedMotion}
          onEditQuestion={onEditQuestion}
        />
      </div>
    </>
  );
}

function TreePanel({
  language,
  current,
  facts,
  trunk,
  variant,
  outcome,
  reducedMotion,
  onEditQuestion,
}: {
  language: Language;
  current: OracleNode;
  facts: OracleFacts;
  trunk: ReturnType<typeof getTreeSteps>["trunk"];
  variant: "mobile" | "desktop";
  outcome: ProcessOutcomeSummary | null;
  reducedMotion: boolean;
  onEditQuestion: (questionId: string) => void;
}) {
  return (
    <div className="oracle-tree">
      <ProcessProgress
        language={language}
        current={current}
        facts={facts}
        variant={variant}
      />

      <div className="oracle-tree__trunk">
        {trunk.map((step) => {
          const label = translate(language, step.labelI18nKey as I18nKey);
          if (isEditableTreeStep(step)) {
            const answer = answerFor(language, step.id, facts);
            return (
              <button
                key={step.id}
                type="button"
                className="oracle-tree__step oracle-tree__step--editable"
                data-status={step.status}
                data-process-jump={step.id}
                onClick={() => onEditQuestion(step.id)}
                aria-label={
                  answer === null
                    ? translate(language, "tree.edit_aria" as I18nKey, {
                        question: label,
                      })
                    : translate(language, "process.jump_aria" as I18nKey, {
                        question: label,
                        answer,
                      })
                }
              >
                <span className="oracle-tree__dot" aria-hidden="true" />
                <span aria-hidden="true" style={{ minWidth: 0 }}>
                  {label}
                  {answer !== null && (
                    <span
                      style={{
                        display: "block",
                        fontSize: "var(--text-xs)",
                        color: "var(--oracle-ink-faint)",
                        overflowWrap: "anywhere",
                      }}
                    >
                      {answer}
                    </span>
                  )}
                </span>
              </button>
            );
          }

          return (
            <div
              key={step.id}
              className="oracle-tree__step"
              data-status={step.status}
              aria-hidden="true"
            >
              <span className="oracle-tree__dot" />
              <span>{label}</span>
            </div>
          );
        })}
      </div>

      <ProcessBranches
        language={language}
        current={current}
        facts={facts}
        variant={variant}
        outcome={outcome}
        reducedMotion={reducedMotion}
      />
    </div>
  );
}
