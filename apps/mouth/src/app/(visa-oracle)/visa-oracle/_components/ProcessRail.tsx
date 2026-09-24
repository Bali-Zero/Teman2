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
  onSelectCategory?: (category: string) => void;
  previews?: Record<string, { labels: string[]; remainder: number }>;
}

const S = {
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
      className="oracle-rail-progress"
    >
      <p className="oracle-rail-progress__headline oracle-tabular-nums">
        {translate(language, "process.step_of", {
          current: model.answeredQuestions,
          total: model.totalQuestions,
        })}
        {model.currentPhase !== null && (
          <>
            {" · "}
            <span>
              {translate(
                language,
                `process.phase.${model.currentPhase}` as I18nKey,
              )}
            </span>
          </>
        )}
      </p>

      {/* The stages read as one segmented meter, labelled by the headline
          above it; each stage's name and status stay in the DOM for
          assistive tech and surface as a tooltip on pointer devices. */}
      <p className="oracle-sr-only">
        {translate(language, "process.phases_label")}
      </p>
      <ol className="oracle-rail-meter" role="list">
        {PROCESS_PHASES.map((key) => {
          const phase = model.phases.find((entry) => entry.key === key);
          if (!phase || phase.total === 0) return null;
          const name = translate(language, `process.phase.${key}` as I18nKey);
          const status = translate(
            language,
            `process.phase_status.${phase.status}` as I18nKey,
          );
          return (
            <li
              key={key}
              data-process-phase={key}
              data-status={phase.status}
              className="oracle-rail-meter__stage"
              title={`${name} — ${status}`}
            >
              <span className="oracle-sr-only">{name}</span>
              <span className="oracle-sr-only">{status}</span>
            </li>
          );
        })}
      </ol>

      <div className="oracle-rail-decides">
        <p className="oracle-rail-label">
          {translate(language, "process.decides_title")}
        </p>
        {model.decision === null ? (
          // Four truths, not one sentence: at the door nothing is
          // answered; at the confirmation card the request has NOT been
          // made; at the verdict node the reply may still be in flight,
          // failed or disabled — `outcome` is the only evidence the engine
          // actually answered, so the "the engine has your answers" line is
          // spoken only when that evidence is on screen.
          <p className="oracle-rail-body">
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
          <p className="oracle-rail-body">
            {translate(language, "process.decides_context")}
          </p>
        ) : (
          <>
            <p className="oracle-rail-body">
              {translate(
                language,
                model.decision.mapping === "REVIEW_ONLY"
                  ? "process.decides_review"
                  : "process.decides_fact",
                { count: model.decision.factPaths.length },
              )}
            </p>
            <ul className="oracle-rail-list" role="list">
              {model.decision.factPaths.map((path) => (
                <li key={path} className="oracle-rail-fact">
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
  onSelectCategory,
  previews = {},
}: ProcessRailProps) {
  if (!model.showCategories) return null;

  // C2-2 re-entry is for viewing a pruned branch from a LATER question —
  // never while the category picker itself is the open question. `BACK`
  // (flow.ts:1386) truncates history but `pruneFacts` (flow.ts:1269) keeps
  // a fact whenever its questionId is still anywhere in history, INCLUDING
  // the current node: landing back on "category" after a prior answer
  // leaves `facts.category` (and so `model.chosenCategory`) stale until
  // it is re-answered. Without this check every OTHER category still
  // reads "pruned" and its rail chip would promote to a `<button>` right
  // next to the category question's own identically-named answer button —
  // two elements sharing one accessible name (measured: PR #7081,
  // `visa-oracle-v2.spec.ts:567`'s `getByRole("button", { name:
  // /tourism & short visit/i })` resolving to 2 elements, strict-mode
  // violation). `model.trunk` already carries this: `getTreeSteps`
  // (flow.ts:1720-1758) sets the "category" step's own status to
  // "current" exactly when it is the open question — no new prop needed.
  const categoryQuestionOpen = model.trunk.some(
    (step) => step.id === "category" && step.status === "current",
  );

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
      className="oracle-rail-section"
    >
      <p className="oracle-rail-label">
        {translate(language, "process.categories_title")}
      </p>
      <div
        className="oracle-tree__leaves"
        style={{ marginTop: 0, borderTop: 0, paddingTop: "var(--space-2)" }}
      >
        <AnimatePresence initial={false}>
          {model.categories.map((leaf) => {
            const pruned = leaf.status === "pruned";
            const preview = previews[leaf.key];
            const chipProps = {
              className: "oracle-tree__leaf",
              "data-status": leaf.status,
              "data-process-category": leaf.key,
              layout: !reducedMotion,
              animate: reducedMotion ? undefined : { scale: pruned ? 0.96 : 1 },
              transition: {
                duration: reducedMotion ? 0 : 0.3,
                ease: [0.4, 0, 0.2, 1] as [number, number, number, number],
              },
              style: pruned
                ? S.prunedLeaf
                : leaf.status === "current"
                  ? S.openLeaf
                  : undefined,
            };
            const chipLabel = (
              <>
                {translate(language, `q.category.opt.${leaf.key}` as I18nKey)}
                <span className="oracle-sr-only">
                  {" — "}
                  {translate(
                    language,
                    `process.category_status.${leaf.status}` as I18nKey,
                  )}
                </span>
              </>
            );
            return (
              <div key={leaf.key} className="oracle-process-branch">
                {onSelectCategory &&
                model.chosenCategory !== null &&
                pruned &&
                !categoryQuestionOpen ? (
                  <motion.button
                    type="button"
                    onClick={() => onSelectCategory(leaf.key)}
                    aria-label={translate(
                      language,
                      "process.branch_reopen_aria",
                      {
                        category: translate(
                          language,
                          `q.category.opt.${leaf.key}` as I18nKey,
                        ),
                      },
                    )}
                    {...chipProps}
                  >
                    {chipLabel}
                  </motion.button>
                ) : (
                  <motion.span {...chipProps}>{chipLabel}</motion.span>
                )}
                {pruned && preview && (
                  <ul data-process-branch-preview={leaf.key}>
                    {preview.labels.map((key) => (
                      <li key={key}>{translate(language, key as I18nKey)}</li>
                    ))}
                    {preview.remainder > 0 && (
                      <li>
                        {translate(language, "process.branch_preview_more", {
                          count: preview.remainder,
                        })}
                      </li>
                    )}
                  </ul>
                )}
              </div>
            );
          })}
        </AnimatePresence>
      </div>

      <p className="oracle-rail-body" style={{ marginTop: "var(--space-2)" }}>
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
      className="oracle-rail-section"
    >
      <p className="oracle-rail-label">
        {translate(language, "process.candidates_title")}
      </p>
      {!decided ? (
        <p className="oracle-rail-body">
          {translate(
            language,
            model.atFollowUp
              ? "process.candidates_follow_up"
              : "process.candidates_pending",
          )}
        </p>
      ) : outcome.candidates.length > 0 ? (
        <ul className="oracle-rail-list" role="list">
          {outcome.candidates.map((candidate) => (
            <li
              key={candidate.code}
              data-process-candidate={candidate.code}
              className="oracle-rail-body"
            >
              <strong className="oracle-tabular-nums">{candidate.code}</strong>
              {" — "}
              {localized(candidate.name, language)}
            </li>
          ))}
        </ul>
      ) : (
        <p
          className="oracle-rail-body"
          data-process-outcome-state={outcome.state}
        >
          {translate(
            language,
            outcome.state === "NO_SUPPORTED_PATH"
              ? "process.candidates_none"
              : "process.candidates_undecided",
          )}
        </p>
      )}
      {model.atOutcome && (
        <p className="oracle-rail-body" style={{ marginTop: "var(--space-2)" }}>
          {translate(language, "process.outcome_node")}
        </p>
      )}
    </div>
  );
}
