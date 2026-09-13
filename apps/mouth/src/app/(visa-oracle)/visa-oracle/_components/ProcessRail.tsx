"use client";

import { AnimatePresence, motion } from "framer-motion";
import { PROCESS_PHASES, type Language, type ProcessModel } from "../_lib/flow";
import type { LocalizedText, OutcomeState } from "../_lib/outcome-view-model";
import { localized } from "../_lib/outcome-view-model";
import { translate, type I18nKey } from "../_lib/i18n";

/** The engine's own answer, passed down ONLY at the terminal node. The rail
 * never computes, ranks or filters a product: it names what the engine
 * returned, or says plainly that the engine has not been asked yet. */
export interface ProcessOutcomeSummary {
  state: OutcomeState;
  /** `OutcomeViewModel.provenance`. Only "ENGINE" is an engine reply: a
   * client guard, a network failure, a shadow comparison and a developer
   * preview all produce a non-null outcome with zero candidates, and
   * reading any of them as "the engine answered" would be the interface
   * speaking for an engine it never reached. */
  provenance:
    "ENGINE" | "CLIENT_GUARD" | "NETWORK_FAILURE" | "SHADOW" | "PREVIEW";
  candidates: readonly { code: string; name: LocalizedText }[];
}

export interface ProcessRailProps {
  language: Language;
  /** Projected ONCE by `LivingTree` and passed down, so the two rendered
   * copies (mobile sheet + desktop column) and the trunk between them can
   * never disagree about the same interview. */
  model: ProcessModel;
  /** Rendered twice; the marker lets a test address one copy without
   * ambiguity. */
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
    gap: "var(--space-1)",
  },
  phaseRow: {
    display: "flex",
    justifyContent: "space-between",
    gap: "var(--space-2)",
    fontSize: "var(--text-xs)",
    lineHeight: 1.5,
  },
  fact: {
    fontFamily: "ui-monospace, monospace",
    fontSize: "var(--text-xs)",
    color: "var(--oracle-ink-muted)",
    overflowWrap: "anywhere" as const,
  },
  divider: {
    marginTop: "var(--space-3)",
    paddingTop: "var(--space-3)",
    borderTop: "1px dashed var(--oracle-border)",
  },
  /** `oracle.css` styles `.oracle-tree__leaf[data-status="done"]` but has no
   * rule for a chosen-and-still-open branch, and the file is READ-ONLY by
   * ruling. Painting "current" as "done" in the attribute would make the
   * chip say one thing to the eye and another to a screen reader, so the
   * open state is expressed here instead, in the same values the done rule
   * uses. */
  openLeaf: {
    color: "var(--oracle-bg-elevated)",
    background: "var(--oracle-leaf-active)",
    borderColor: "var(--oracle-leaf-active)",
    fontWeight: 600,
  },
  prunedLeaf: {
    textDecoration: "line-through" as const,
    borderStyle: "dashed" as const,
  },
} as const;

function phaseTone(status: string): string {
  if (status === "current") return "var(--oracle-ink)";
  if (status === "done" || status === "partial")
    return "var(--oracle-ink-muted)";
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
  model,
  variant,
  outcome,
}: ProcessRailProps) {
  return (
    <div
      data-process-rail={variant}
      data-process-part="progress"
      style={S.block}
    >
      <p style={S.headline} className="oracle-tabular-nums">
        {translate(language, "process.step_of", {
          current: model.answeredQuestions,
          total: model.totalQuestions,
        })}
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
      <ol style={S.list} role="list">
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
          // Four truths, not one sentence: at the door nothing is
          // answered; at the confirmation card the request has NOT been
          // made; at the verdict node the reply may still be in flight,
          // failed or disabled — `outcome` is the only evidence the engine
          // actually answered, so the "the engine has your answers" line is
          // spoken only when that evidence is on screen.
          <p style={S.body}>
            {translate(
              language,
              model.node === "framing"
                ? "process.decides_framing"
                : model.node === "confirmation"
                  ? "process.decides_confirmation"
                  : outcome?.provenance === "ENGINE"
                    ? "process.decides_none"
                    : "process.decides_awaiting",
            )}
          </p>
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
            <ul style={{ ...S.list, marginTop: "var(--space-1)" }} role="list">
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
 * The eleven purpose branches: the one that is open, the ones the visitor's
 * own answer closed, and the sentence that says WHY they closed. Rendered
 * only while the purpose question is on screen or already answered — past
 * that, and before it, there is no branch state to state.
 */
export function ProcessBranches({
  language,
  model,
  variant,
  reducedMotion = false,
}: ProcessRailProps) {
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
                data-status={leaf.status}
                data-process-category={leaf.key}
                layout={!reducedMotion}
                // A closed branch is marked by a line through it and a
                // dashed edge, never by fading it: dimming the text is what
                // took these chips below the 4.5:1 contrast floor (axe,
                // measured on this rail before the fix).
                animate={
                  reducedMotion ? undefined : { scale: pruned ? 0.96 : 1 }
                }
                transition={{
                  duration: reducedMotion ? 0 : 0.3,
                  ease: [0.4, 0, 0.2, 1],
                }}
                style={
                  pruned
                    ? S.prunedLeaf
                    : leaf.status === "current"
                      ? S.openLeaf
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
    </div>
  );
}

/**
 * The end of the rail: what the ENGINE named. Deliberately NOT behind the
 * branch fan's guard — the terminal node must state its products on every
 * lane, including one that never answered a purpose question. The state is
 * read, not inferred: only a NO_SUPPORTED_PATH decision may be rendered as
 * "no product", because every other empty candidate list means the engine
 * did not decide, which is a different sentence.
 */
export function ProcessOutcome({
  language,
  model,
  variant,
  outcome,
}: ProcessRailProps) {
  // Only an ENGINE outcome is a decision. Every other provenance carries
  // zero candidates by contract, and rendering it as "the engine named no
  // product" would put an eligibility claim in the engine's mouth.
  const decided = model.atOutcome && outcome?.provenance === "ENGINE";

  return (
    <div
      data-process-rail={variant}
      data-process-part="outcome"
      style={S.divider}
    >
      <p style={S.label}>{translate(language, "process.candidates_title")}</p>
      {!decided ? (
        <p style={S.body}>
          {translate(
            language,
            model.atFollowUp
              ? "process.candidates_follow_up"
              : "process.candidates_pending",
          )}
        </p>
      ) : outcome.candidates.length > 0 ? (
        <ul style={{ ...S.list, marginTop: "var(--space-1)" }} role="list">
          {outcome.candidates.map((candidate) => (
            <li
              key={candidate.code}
              data-process-candidate={candidate.code}
              style={S.body}
            >
              <strong className="oracle-tabular-nums">{candidate.code}</strong>
              {" — "}
              {localized(candidate.name, language)}
            </li>
          ))}
        </ul>
      ) : (
        <p style={S.body} data-process-outcome-state={outcome.state}>
          {translate(
            language,
            outcome.state === "NO_SUPPORTED_PATH"
              ? "process.candidates_none"
              : "process.candidates_undecided",
          )}
        </p>
      )}
      {model.atOutcome && (
        <p style={{ ...S.body, marginTop: "var(--space-2)" }}>
          {translate(language, "process.outcome_node")}
        </p>
      )}
    </div>
  );
}
