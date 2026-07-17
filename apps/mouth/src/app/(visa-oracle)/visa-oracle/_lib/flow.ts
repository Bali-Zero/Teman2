/**
 * Visa Oracle v2 — interview state machine.
 *
 * A pure reducer (`flowReducer`) plus a thin `useOracleFlow` hook wrapping
 * it in `useReducer`. History is a real stack (spec item 35 / GOV.UK
 * "mandatory Back link, real history") so Back and the confirmation card's
 * "Edit" both fall out of the same mechanism: truncate the stack.
 */
"use client";

import { useCallback, useMemo, useReducer } from "react";
import {
  BEHAVIORAL_CATEGORIES,
  CATEGORY_KEYS,
  QUESTIONS,
  getLane,
  type CategoryKey,
  type OracleFacts,
} from "./tree";
import { evaluate, type Assumption, type EvaluateResult } from "./mock-engine";

export type Language = "en" | "id";

export type OracleNode =
  | { kind: "framing" }
  | { kind: "question"; questionId: string }
  | { kind: "confirmation" }
  | { kind: "verdict" };

export interface FlowState {
  history: OracleNode[];
  facts: OracleFacts;
  language: Language;
}

export type FlowAction =
  | { type: "ANSWER"; questionId: string; value: string; today?: Date }
  | { type: "SKIP"; questionId: string; today?: Date }
  /** Leaves a non-question screen (framing's "Start", confirmation's "See
   * my options") without recording a fact — both are plain forward moves
   * through `computeNextNode`, never an answer. */
  | { type: "ADVANCE" }
  | { type: "BACK" }
  | { type: "EDIT"; questionId: string }
  /** Finding #15 (adversarial review 2026-07-17): "what instead" is never
   * a dead end — jumps back to the category question and immediately
   * re-answers it with the chosen alternative, re-deriving the forward
   * path from there (same mechanism as EDIT + ANSWER composed). */
  | { type: "SELECT_CATEGORY"; category: string; today?: Date }
  /** Jumps back to the confirmation screen without discarding any facts
   * ahead of it — the verdict screen's "Edit answers" link. */
  | { type: "REVIEW_ANSWERS" }
  | { type: "RESTART" }
  | { type: "SET_LANGUAGE"; language: Language };

export function initialFlowState(language: Language = "en"): FlowState {
  return { history: [{ kind: "framing" }], facts: {}, language };
}

function sameNode(a: OracleNode, b: OracleNode): boolean {
  if (a.kind !== b.kind) return false;
  if (a.kind === "question" && b.kind === "question")
    return a.questionId === b.questionId;
  return true;
}

/**
 * The flow graph, pure function of the current node + facts so far. This
 * is the single source of truth for "what comes next" — used by the
 * reducer, by tests, and by `getTreeSteps` below to project the path.
 */
export function computeNextNode(
  current: OracleNode,
  facts: OracleFacts,
  today: Date = new Date(),
): OracleNode {
  if (current.kind === "framing") {
    return { kind: "question", questionId: "in_indonesia" };
  }
  if (current.kind === "confirmation") {
    return { kind: "verdict" };
  }
  if (current.kind === "verdict") {
    return current;
  }

  switch (current.questionId) {
    case "in_indonesia": {
      if (facts.in_indonesia === "yes" || facts.in_indonesia === "unsure") {
        return { kind: "question", questionId: "permit_expiry" };
      }
      return { kind: "question", questionId: "category" };
    }
    case "permit_expiry": {
      // Finding #7 (adversarial review 2026-07-17): an unsure compliance
      // deadline is exactly as load-bearing as an unsure payer/clients/
      // income — never guess, go straight to human review. `getLane`
      // already returns null for an unsure/missing date, so without this
      // explicit check the switch below would silently fall through to
      // "category" instead of flagging review.
      if (facts.permit_expiry === "unsure") {
        return { kind: "question", questionId: "review_gate" };
      }
      const lane = getLane(facts, today);
      if (lane === "expired" || lane === "urgent") {
        return { kind: "question", questionId: "review_gate" };
      }
      return { kind: "question", questionId: "category" };
    }
    case "category": {
      const category = facts.category as CategoryKey | undefined;
      if (category === "work")
        return { kind: "question", questionId: "work_payer" };
      if (category === "remote")
        return { kind: "question", questionId: "remote_clients" };
      if (category === "tourism")
        return { kind: "question", questionId: "tourism_duration" };
      return { kind: "question", questionId: "review_gate" };
    }
    case "work_payer":
      return { kind: "question", questionId: "review_gate" };
    case "remote_clients":
      return { kind: "question", questionId: "remote_income" };
    case "remote_income":
      return { kind: "question", questionId: "review_gate" };
    case "tourism_duration":
      return { kind: "question", questionId: "review_gate" };
    case "review_gate":
      return { kind: "confirmation" };
    default:
      return { kind: "confirmation" };
  }
}

function truncateToNode(
  history: OracleNode[],
  target: OracleNode,
): OracleNode[] {
  const idx = history.findIndex((n) => sameNode(n, target));
  if (idx === -1) return history;
  return history.slice(0, idx + 1);
}

/**
 * Finding #1 (adversarial review 2026-07-17): Back/Edit truncate the
 * history stack but previously left every fact ever answered in place —
 * so re-answering a branch-determining question (e.g. `category`) down a
 * DIFFERENT path left stale facts from the abandoned branch (e.g.
 * `work_payer`) sitting in `state.facts`, silently feeding the mock
 * engine's candidate matching and completeness check with answers to
 * questions the user never reached on their current path.
 *
 * Facts are pruned to exactly the set of question ids present in the
 * (already-truncated) history — anything beyond the new frontier is
 * dropped, so the next `computeNextNode`/`evaluate` call only ever sees
 * facts for questions actually on the current path.
 */
function pruneFacts(facts: OracleFacts, history: OracleNode[]): OracleFacts {
  const reachable = new Set(
    history
      .filter((n) => n.kind === "question")
      .map((n) => (n as { questionId: string }).questionId),
  );
  const out: OracleFacts = {};
  for (const [id, value] of Object.entries(facts)) {
    if (reachable.has(id)) out[id] = value;
  }
  return out;
}

export function flowReducer(state: FlowState, action: FlowAction): FlowState {
  switch (action.type) {
    case "ANSWER": {
      const facts = pruneFacts(
        { ...state.facts, [action.questionId]: action.value },
        state.history,
      );
      const current = state.history[state.history.length - 1];
      const next = computeNextNode(current, facts, action.today);
      return { ...state, facts, history: [...state.history, next] };
    }
    case "SKIP": {
      const facts = pruneFacts(
        { ...state.facts, [action.questionId]: "unsure" },
        state.history,
      );
      const current = state.history[state.history.length - 1];
      const next = computeNextNode(current, facts, action.today);
      return { ...state, facts, history: [...state.history, next] };
    }
    case "ADVANCE": {
      const current = state.history[state.history.length - 1];
      if (current.kind !== "framing" && current.kind !== "confirmation")
        return state;
      const next = computeNextNode(current, state.facts);
      return { ...state, history: [...state.history, next] };
    }
    case "BACK": {
      if (state.history.length <= 1) return state;
      const history = state.history.slice(0, -1);
      return { ...state, history, facts: pruneFacts(state.facts, history) };
    }
    case "EDIT": {
      const target: OracleNode = {
        kind: "question",
        questionId: action.questionId,
      };
      const history = truncateToNode(state.history, target);
      return { ...state, history, facts: pruneFacts(state.facts, history) };
    }
    case "SELECT_CATEGORY": {
      // Finding #15: NO_SUPPORTED_PATH's "what instead" alternatives are
      // never a dead end — jump back to the category question (dropping
      // every fact from the abandoned branch via pruneFacts) and
      // immediately re-answer it with the chosen alternative, exactly as
      // if the user had used Back + a different tap.
      const target: OracleNode = { kind: "question", questionId: "category" };
      if (!state.history.some((n) => sameNode(n, target))) {
        // Defensive fallback: "category" isn't in this session's history
        // (should be unreachable — SELECT_CATEGORY is only ever offered
        // from NO_SUPPORTED_PATH, which requires a completed interview
        // that passed through "category"). Restart rather than risk
        // dispatching into an inconsistent mid-flow state.
        return initialFlowState(state.language);
      }
      const truncated = truncateToNode(state.history, target);
      const prunedFacts = pruneFacts(state.facts, truncated);
      const facts = { ...prunedFacts, category: action.category };
      const next = computeNextNode(target, facts, action.today);
      return { ...state, facts, history: [...truncated, next] };
    }
    case "REVIEW_ANSWERS": {
      // Verdict screen's "Edit answers" link — jump back to the
      // confirmation screen without discarding any facts ahead of it.
      const target: OracleNode = { kind: "confirmation" };
      const history = truncateToNode(state.history, target);
      return { ...state, history, facts: pruneFacts(state.facts, history) };
    }
    case "RESTART":
      return initialFlowState(state.language);
    case "SET_LANGUAGE":
      // Facts are keys, never localized strings — switching languages
      // never touches them (design doc §3 "instant, no lost history").
      return { ...state, language: action.language };
    default:
      return state;
  }
}

/**
 * @param today Finding #9 (adversarial review 2026-07-17): overrides the
 * clock used for this hook's internal `evaluate()` call. `undefined` (the
 * default) lets `evaluate()`'s own `new Date()` default apply — the
 * during-interview behavior, unchanged. Callers that need the
 * verdict/outcome screens to stop drifting against wall-clock time once
 * reached (OracleShell) pass a value captured once and held in state.
 */
export function useOracleFlow(initialLanguage: Language = "en", today?: Date) {
  const [state, dispatch] = useReducer(
    flowReducer,
    initialLanguage,
    initialFlowState,
  );

  const answer = useCallback(
    (questionId: string, value: string) =>
      dispatch({ type: "ANSWER", questionId, value }),
    [],
  );
  const skip = useCallback(
    (questionId: string) => dispatch({ type: "SKIP", questionId }),
    [],
  );
  const advance = useCallback(() => dispatch({ type: "ADVANCE" }), []);
  const back = useCallback(() => dispatch({ type: "BACK" }), []);
  const edit = useCallback(
    (questionId: string) => dispatch({ type: "EDIT", questionId }),
    [],
  );
  // Finding #15: NO_SUPPORTED_PATH's "what instead" alternatives and the
  // verdict screen's "Edit answers" link, both wired through the same
  // history-truncation + fact-pruning mechanism as EDIT/BACK.
  const selectCategory = useCallback(
    (category: string) => dispatch({ type: "SELECT_CATEGORY", category }),
    [],
  );
  const reviewAnswers = useCallback(
    () => dispatch({ type: "REVIEW_ANSWERS" }),
    [],
  );
  const restart = useCallback(() => dispatch({ type: "RESTART" }), []);
  const setLanguage = useCallback(
    (language: Language) => dispatch({ type: "SET_LANGUAGE", language }),
    [],
  );

  const current = state.history[state.history.length - 1];
  const result: EvaluateResult = useMemo(
    () => evaluate(state.facts, today),
    [state.facts, today],
  );
  const assumptions: Assumption[] = result.assumptions;

  return {
    state,
    current,
    result,
    assumptions,
    canGoBack: state.history.length > 1,
    answer,
    skip,
    advance,
    back,
    edit,
    selectCategory,
    reviewAnswers,
    restart,
    setLanguage,
  };
}

// ─── Living-tree projection ──────────────────────────────────────────────

export type TreeStepStatus = "done" | "current" | "pending" | "pruned";

export interface TreeStep {
  id: string;
  labelI18nKey: string;
  status: TreeStepStatus;
}

export interface TreeCategoryLeaf {
  key: CategoryKey;
  status: TreeStepStatus;
}

/**
 * Project the trunk of the tree (framing → location → category → the
 * chosen behavioral branch → review → confirmation → verdict) from the
 * current node + facts, and — only while at/after the category step — the
 * 10 category leaves fanning out from it, so `LivingTree` can render both
 * without re-deriving the flow graph itself.
 */
export function getTreeSteps(
  current: OracleNode,
  facts: OracleFacts,
): { trunk: TreeStep[]; categoryLeaves: TreeCategoryLeaf[] | null } {
  const order = [
    { id: "framing", labelI18nKey: "tree.framing" },
    { id: "in_indonesia", labelI18nKey: "tree.in_indonesia" },
    ...(facts.in_indonesia === "yes" || facts.in_indonesia === "unsure"
      ? [{ id: "permit_expiry", labelI18nKey: "tree.permit_expiry" }]
      : []),
    { id: "category", labelI18nKey: "tree.category" },
    ...behavioralSteps(facts),
    { id: "review_gate", labelI18nKey: "tree.review_gate" },
    { id: "confirmation", labelI18nKey: "tree.confirmation" },
    { id: "verdict", labelI18nKey: "tree.verdict" },
  ];

  const currentId =
    current.kind === "question" ? current.questionId : current.kind;
  const currentIdx = order.findIndex((s) => s.id === currentId);

  const trunk: TreeStep[] = order.map((step, idx) => ({
    id: step.id,
    labelI18nKey: step.labelI18nKey,
    status:
      currentIdx === -1
        ? "pending"
        : idx < currentIdx
          ? "done"
          : idx === currentIdx
            ? "current"
            : "pending",
  }));

  const category = facts.category as CategoryKey | undefined;
  const atOrPastCategory =
    currentId === "category" ||
    (currentIdx !== -1 &&
      order.findIndex((s) => s.id === "category") < currentIdx);

  const categoryLeaves: TreeCategoryLeaf[] | null = atOrPastCategory
    ? CATEGORY_KEYS.map((key) => ({
        key,
        status: category
          ? key === category
            ? ("done" as const)
            : ("pruned" as const)
          : ("pending" as const),
      }))
    : null;

  return { trunk, categoryLeaves };
}

/**
 * Tree tap-to-edit (design doc §3 interaction #6): a trunk step is a valid
 * `EDIT` jump target only if it is BOTH a completed answer ("done") AND an
 * actual question node. "framing"/"confirmation"/"verdict" can reach
 * "done" status too (they're plain forward moves through the trunk, not
 * questions) and must never render as editable — `flowReducer`'s EDIT
 * action only knows how to truncate history to a `{ kind: "question" }`
 * node, so dispatching EDIT with one of those ids would silently no-op
 * (`truncateToNode` finds no match and returns the history unchanged).
 * Current/pending/pruned steps are never editable either — you can't jump
 * forward to an answer that doesn't exist yet. Pure, so `LivingTree` never
 * has to re-derive this rule itself.
 */
export function isEditableTreeStep(step: TreeStep): boolean {
  return (
    step.status === "done" &&
    Object.prototype.hasOwnProperty.call(QUESTIONS, step.id)
  );
}

function behavioralSteps(
  facts: OracleFacts,
): { id: string; labelI18nKey: string }[] {
  const category = facts.category as CategoryKey | undefined;
  if (!category || !BEHAVIORAL_CATEGORIES.has(category)) return [];
  if (category === "work")
    return [{ id: "work_payer", labelI18nKey: "tree.work_payer" }];
  if (category === "remote") {
    return [
      { id: "remote_clients", labelI18nKey: "tree.remote_clients" },
      { id: "remote_income", labelI18nKey: "tree.remote_income" },
    ];
  }
  if (category === "tourism") {
    return [{ id: "tourism_duration", labelI18nKey: "tree.tourism_duration" }];
  }
  return [];
}

export { QUESTIONS };
