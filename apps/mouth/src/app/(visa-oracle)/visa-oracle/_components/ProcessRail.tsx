"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  getProcessModel,
  PROCESS_PHASES,
  type Language,
  type OracleNode,
  type ProcessModel,
} from "../_lib/flow";
import type { OracleFacts } from "../_lib/tree";
import type { LocalizedText, OutcomeState } from "../_lib/outcome-view-model";
import { localized } from "../_lib/outcome-view-model";
import { translate, type I18nKey } from "../_lib/i18n";

/** The engine's own answer, passed down ONLY at the terminal node. The rail
 * never computes, ranks or filters a product: it names what the engine
 * returned, or says plainly that the engine has not been asked yet. */
export interface ProcessOutcomeSummary {
  state: OutcomeState;
  candidates: readonly { code: string; name: LocalizedText }[];
}

export interface ProcessRailProps {
  language: Language;
  current: OracleNode;
  facts: OracleFacts;
  /** Rendered twice (mobile sheet + desktop column); the marker lets a test
   * address one copy without ambiguity. */
  variant: "mobile" | "desktop";
  outcome?: ProcessOutcomeSummary | null;
  reducedMotion?: boolean;
}

const S = {
  block: {
    display: "flex",
    flexDirection: "column",
    gap: "var(--space-2)",
    marginBottom: "var(--space-3)",
  },
  headline: {
    margin: 0,
    fontSize: "var(--text-sm)",
    fontWeight: 700,
    color: "var(--oracle-ink)",
  },
  label: {
    margin: 0,
    fontSize: "var(--text-xs)",
    fontWeight: 600,
    letterSpacing: "0.04em",
    textTransform: "uppercase" as const,
    color: "var(--oracle-ink-faint)",
  },
  body: {
    margin: 0,
    fontSize: "var(--text-xs)",
    lineHeight: 1.5,
    color: "var(--oracle-ink-muted)",
    overflowWrap: "anywhere" as const,
  },
  list: {
    listStyle: "none",
    margin: 0,
    padding: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.15rem",
  },
  phaseRow: {
    display: "flex",
    justifyContent: "space-between",
    gap: "var(--space-2)",
    fontSize: "var(--text-xs)",
    lineHeight: 1.5,
  },
  fact: {
    fontFamily: "var(--font-mono, ui-monospace, monospace)",
    fontSize: "var(--text-xs)",
    color: "var(--oracle-ink-muted)",
    overflowWrap: "anywhere" as const,
  },
  divider: {
    marginTop: "var(--space-3)",
    paddingTop: "var(--space-3)",
    borderTop: "1px dashed var(--oracle-border)",
  },
} as const;

function phaseTone(status: string): string {
  if (status === "current") return "var(--oracle-ink)";
  if (status === "done") return "var(--oracle-ink-muted)";
  return "var(--oracle-ink-faint)";
}

/**
 * The top of the rail: how far along this interview is, which stage is
 * open, and what the question on screen decides — in the engine's own
 * fact vocabulary, because "we ask this to set THIS fact" is the honest
 * answer to "why am I being asked that".
 */
export function ProcessProgress({
  language,
  current,
  facts,
  variant,
}: ProcessRailProps) {
  const model = getProcessModel(current, facts);
  const stepOf = translate(language, "process.step_of", {
    current: model.answeredQuestions,
    total: model.totalQuestions,
  });

  return (
    <div
      data-process-rail={variant}
      data-process-part="progress"
      style={S.block}
    >
      <p style={S.headline} className="oracle-tabular-nums">
        {stepOf}
        {model.currentPhase !== null && (
          <>
            {" · "}
            <span style={{ fontWeight: 500 }}>
              {translate(
                language,
                `process.phase.${model.currentPhase}` as I18nKey,
              )}
            </span>
          </>
        )}
      </p>

      <p style={S.label}>{translate(language, "process.phases_label")}</p>
      <ol style={S.list}>
        {PROCESS_PHASES.map((key) => {
          const phase = model.phases.find((entry) => entry.key === key);
          if (!phase || phase.total === 0) return null;
          return (
            <li
              key={key}
              data-process-phase={key}
              data-status={phase.status}
              style={{ ...S.phaseRow, color: phaseTone(phase.status) }}
            >
              <span
                style={{ fontWeight: phase.status === "current" ? 700 : 400 }}
              >
                {translate(language, `process.phase.${key}` as I18nKey)}
              </span>
              <span className="oracle-tabular-nums">
                {translate(
                  language,
                  `process.phase_status.${phase.status}` as I18nKey,
                )}
              </span>
            </li>
          );
        })}
      </ol>

      <div style={S.divider}>
        <p style={S.label}>{translate(language, "process.decides_title")}</p>
        {model.decision === null ? (
          <p style={S.body}>{translate(language, "process.decides_none")}</p>
        ) : model.decision.mapping === "HUMAN_CONTEXT" ? (
          <p style={S.body}>{translate(language, "process.decides_context")}</p>
        ) : (
          <>
            <p style={S.body}>
              {translate(
                language,
                model.decision.mapping === "REVIEW_ONLY"
                  ? "process.decides_review"
                  : "process.decides_fact",
                { count: model.decision.factPaths.length },
              )}
            </p>
            <ul style={{ ...S.list, marginTop: "var(--space-1)" }}>
              {model.decision.factPaths.map((path) => (
                <li key={path} style={S.fact}>
                  <code>{path}</code>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}

/**
 * The bottom of the rail: the eleven purpose branches with the one that is
 * open, the ones the visitor's own answer closed and the sentence that says
 * WHY they closed — and, at the terminal node, the product codes the engine
 * named. Before that node it states plainly that no product is named yet.
 */
export function ProcessBranches({
  language,
  current,
  facts,
  variant,
  outcome,
  reducedMotion = false,
}: ProcessRailProps) {
  const model: ProcessModel = getProcessModel(current, facts);
  if (!model.showCategories) return null;

  const chosenLabel =
    model.chosenCategory === null
      ? ""
      : translate(
          language,
          `q.category.opt.${model.chosenCategory}` as I18nKey,
        );

  return (
    <div
      data-process-rail={variant}
      data-process-part="branches"
      style={S.divider}
    >
      <p style={S.label}>{translate(language, "process.categories_title")}</p>
      <div
        className="oracle-tree__leaves"
        style={{ marginTop: 0, borderTop: 0, paddingTop: "var(--space-2)" }}
      >
        <AnimatePresence initial={false}>
          {model.categories.map((leaf) => {
            const pruned = leaf.status === "pruned";
            return (
              <motion.span
                key={leaf.key}
                className="oracle-tree__leaf"
                data-status={leaf.status === "current" ? "done" : leaf.status}
                data-process-category={leaf.key}
                layout={!reducedMotion}
                animate={
                  reducedMotion
                    ? undefined
                    : { opacity: pruned ? 0.55 : 1, scale: pruned ? 0.94 : 1 }
                }
                transition={{
                  duration: reducedMotion ? 0 : 0.3,
                  ease: [0.4, 0, 0.2, 1],
                }}
                style={
                  pruned
                    ? { textDecoration: "line-through", opacity: 0.55 }
                    : undefined
                }
              >
                {translate(language, `q.category.opt.${leaf.key}` as I18nKey)}
                <span className="oracle-sr-only">
                  {" — "}
                  {translate(
                    language,
                    `process.category_status.${leaf.status}` as I18nKey,
                  )}
                </span>
              </motion.span>
            );
          })}
        </AnimatePresence>
      </div>

      <p style={{ ...S.body, marginTop: "var(--space-2)" }}>
        {model.chosenCategory === null
          ? translate(language, "process.pruned_none")
          : translate(language, "process.pruned_because", {
              count: model.prunedCount,
              category: chosenLabel,
            })}
      </p>

      <div style={S.divider}>
        <p style={S.label}>{translate(language, "process.candidates_title")}</p>
        {!model.atOutcome || !outcome ? (
          <p style={S.body}>
            {translate(language, "process.candidates_pending")}
          </p>
        ) : outcome.candidates.length === 0 ? (
          <p style={S.body}>{translate(language, "process.candidates_none")}</p>
        ) : (
          <ul style={{ ...S.list, marginTop: "var(--space-1)" }}>
            {outcome.candidates.map((candidate) => (
              <li
                key={candidate.code}
                data-process-candidate={candidate.code}
                style={S.body}
              >
                <strong className="oracle-tabular-nums">
                  {candidate.code}
                </strong>
                {" — "}
                {localized(candidate.name, language)}
              </li>
            ))}
          </ul>
        )}
        {model.atOutcome && (
          <p style={{ ...S.body, marginTop: "var(--space-2)" }}>
            {translate(language, "process.outcome_node")}
          </p>
        )}
      </div>
    </div>
  );
}
