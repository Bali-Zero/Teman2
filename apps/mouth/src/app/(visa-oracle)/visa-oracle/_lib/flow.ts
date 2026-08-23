/**
 * Visa Oracle v2 — interview state machine.
 *
 * A pure reducer (`flowReducer`) plus a thin `useOracleFlow` hook wrapping
 * it in `useReducer`. History is a real stack (spec item 35 / GOV.UK
 * "mandatory Back link, real history") so Back and the confirmation card's
 * "Edit" both fall out of the same mechanism: truncate the stack.
 */
"use client";

import { useCallback, useEffect, useMemo, useReducer } from "react";
import {
  CATEGORY_KEYS,
  QUESTIONS,
  REVIEW_GATE_ITEMS,
  parseIsoDateUtc,
  type CategoryKey,
  type OracleFacts,
} from "./tree";
import type { InterviewAssumption } from "./outcome-view-model";
import { canonicalCountryCodes } from "./countries";

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
  /**
   * Identifies the current INTERVIEW ATTEMPT — a counter bumped ONLY by
   * `resetFlow` below, never by any other action. Every action that returns
   * the user to "verdict" via history-truncation (REVIEW_ANSWERS,
   * SELECT_CATEGORY's happy path, and whatever gets added next) leaves
   * `attempt` untouched by construction: none of them call
   * `resetFlow`/`initialFlowState`, so there is nothing to enumerate and
   * nothing for a future action to accidentally break. Only a TRUE reset —
   * full history + facts wipe, back to "framing" — is a new attempt, and
   * `resetFlow` is the one place that happens. Added 2026-07-27 to dedupe a
   * SHADOW-only fire-and-forget POST; OracleShell's evaluation effect now
   * keys its request-lease cache on `attempt` for every engine mode
   * (SHADOW, internal preview, and the rendered REAL verdict alike), not
   * SHADOW specifically — the response is awaited and rendered today, no
   * longer fired-and-forgotten.
   */
  attempt: number;
  /**
   * Set when `flowReducer` refused to record an ANSWER because it
   * contradicts an already-known fact (see
   * `channelConflictsWithOnshoreIntent` below) — never derived from the
   * conflicting facts, never silently dropped. The UI reads this to show a
   * "these two answers disagree" message and lets the user correct either
   * one themselves; the interface never guesses which side is right.
   * Cleared by every action except the conflicting ANSWER itself, so it can
   * never outlive the screen that produced it.
   */
  blockedAnswer: BlockedAnswer | null;
}

/** See `FlowState.blockedAnswer`. */
export interface BlockedAnswer {
  questionId: string;
  conflictsWithQuestionId: string;
}

export const INTERVIEW_SNAPSHOT_SCHEMA_VERSION = 1 as const;

/**
 * Language-neutral, JSON-serializable resume payload. Storage, TTL and any
 * encryption policy belong to the integration layer; the flow only owns a
 * versioned representation and deterministic, pruning-aware restoration.
 */
export interface InterviewSnapshot {
  schemaVersion: typeof INTERVIEW_SNAPSHOT_SCHEMA_VERSION;
  attempt: number;
  history: readonly OracleNode[];
  facts: Readonly<OracleFacts>;
  updatedAtIso: string;
}

export interface UseOracleFlowOptions {
  initialLanguage?: Language;
  /** May come from untrusted browser storage; invalid snapshots fail closed
   * to a fresh interview. */
  initialSnapshot?: unknown;
  onSnapshot?: (snapshot: InterviewSnapshot) => void;
  /** Clock injection for deterministic tests and storage adapters. */
  snapshotNow?: () => Date;
  /** Replays date-sensitive routing against this clock during hydration. */
  restoreToday?: Date;
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

export function initialFlowState(
  language: Language = "en",
  attempt = 0,
): FlowState {
  return {
    history: [{ kind: "framing" }],
    facts: {},
    language,
    attempt,
    blockedAnswer: null,
  };
}

export function createInterviewSnapshot(
  state: Pick<FlowState, "attempt" | "history" | "facts">,
  now: Date = new Date(),
): InterviewSnapshot {
  return {
    schemaVersion: INTERVIEW_SNAPSHOT_SCHEMA_VERSION,
    attempt: state.attempt,
    history: state.history.map((node) => ({ ...node })),
    facts: { ...state.facts },
    updatedAtIso: now.toISOString(),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isOracleNode(value: unknown): value is OracleNode {
  if (!isRecord(value) || typeof value.kind !== "string") return false;
  if (
    value.kind === "framing" ||
    value.kind === "confirmation" ||
    value.kind === "verdict"
  ) {
    return Object.keys(value).length === 1;
  }
  return (
    value.kind === "question" &&
    typeof value.questionId === "string" &&
    Object.prototype.hasOwnProperty.call(QUESTIONS, value.questionId)
  );
}

function isValidFactValue(questionId: string, value: string): boolean {
  const question = QUESTIONS[questionId];
  if (!question || value.length === 0 || value.length > 256) return false;
  if (value === "unsure") return question.notSure !== undefined;
  if (question.kind === "date") return parseIsoDateUtc(value) !== null;
  if (question.kind === "country-codes") {
    const codes = value.split(",");
    return (
      question.codeInput !== undefined &&
      canonicalCountryCodes(codes, question.codeInput.multiple) === value &&
      codes.length <= (question.codeInput.maxSelections ?? 1)
    );
  }
  if (question.kind === "status-code") {
    return (
      value.length <= (question.codeInput?.maxLength ?? 32) &&
      /^[A-Z][A-Z0-9-]*$/.test(value)
    );
  }
  if (question.kind === "number") {
    const parsed = Number(value);
    return (
      question.numberInput !== undefined &&
      /^\d+$/.test(value) &&
      Number.isSafeInteger(parsed) &&
      parsed >= question.numberInput.min &&
      parsed <= question.numberInput.max &&
      (parsed - question.numberInput.min) % question.numberInput.step === 0
    );
  }
  if (question.kind === "review-gate") {
    const items = value.split(",").filter(Boolean);
    if (items.length === 0 || new Set(items).size !== items.length)
      return false;
    if (items.includes("none") && items.length !== 1) return false;
    return items.every((item) =>
      (REVIEW_GATE_ITEMS as readonly string[]).includes(item),
    );
  }
  return question.options.some((option) => option.key === value);
}

/**
 * Hydrate by replaying the saved path, not by trusting its history/facts.
 * Any impossible node, invalid answer or branch that changed with the current
 * assessment clock is truncated at the last valid frontier; descendants are
 * discarded by construction. Completely malformed payloads return `null`.
 */
export function restoreInterviewSnapshot(
  value: unknown,
  language: Language = "en",
  today: Date = new Date(),
): FlowState | null {
  if (!isRecord(value)) return null;
  if (value.schemaVersion !== INTERVIEW_SNAPSHOT_SCHEMA_VERSION) return null;
  if (
    typeof value.attempt !== "number" ||
    !Number.isSafeInteger(value.attempt) ||
    value.attempt < 0
  ) {
    return null;
  }
  if (
    typeof value.updatedAtIso !== "string" ||
    !Number.isFinite(Date.parse(value.updatedAtIso))
  ) {
    return null;
  }
  if (
    !Array.isArray(value.history) ||
    value.history.length === 0 ||
    value.history.length > 64 ||
    !value.history.every(isOracleNode) ||
    value.history[0].kind !== "framing"
  ) {
    return null;
  }
  if (!isRecord(value.facts)) return null;

  const savedFacts: OracleFacts = {};
  for (const [questionId, factValue] of Object.entries(value.facts)) {
    if (
      typeof factValue !== "string" ||
      !Object.prototype.hasOwnProperty.call(QUESTIONS, questionId)
    ) {
      return null;
    }
    savedFacts[questionId] = factValue;
  }

  const history: OracleNode[] = [{ kind: "framing" }];
  let facts: OracleFacts = {};
  for (let index = 1; index < value.history.length; index += 1) {
    const current = history[history.length - 1];
    if (current.kind === "verdict") break;
    if (current.kind === "question") {
      const answer = savedFacts[current.questionId];
      if (
        answer === undefined ||
        !isValidFactValue(current.questionId, answer)
      ) {
        break;
      }
      // Defense-in-depth: a snapshot saved before this guard existed (or
      // tampered with in storage) could hold a self-contradictory
      // wants_onshore_conversion/application_channel pair. Treat it exactly
      // like any other impossible answer — truncate at this frontier rather
      // than resume into a state the live interview could never produce.
      if (
        current.questionId === "application_channel" &&
        channelConflictsWithOnshoreIntent(
          facts.wants_onshore_conversion,
          answer,
        )
      ) {
        break;
      }
      facts = { ...facts, [current.questionId]: answer };
    }
    const expected = computeNextNode(current, facts, today);
    const savedNext = value.history[index];
    history.push(expected);
    if (!sameNode(expected, savedNext)) break;
  }

  return {
    history,
    facts: pruneFacts(facts, history),
    language,
    attempt: value.attempt,
    blockedAnswer: null,
  };
}

/**
 * The reducer's ONE reset primitive: a full wipe back to
 * `initialFlowState`, with `attempt` incremented so every consumer that
 * needs to know "is this a genuinely new interview" (OracleShell's
 * evaluation-lease cache key, which now covers every engine mode — SHADOW,
 * internal preview and the rendered REAL verdict — not just SHADOW) can
 * key off `state.attempt` instead of enumerating which actions perform a
 * reset. Called from RESTART and from SELECT_CATEGORY's defensive
 * fallback below — both discard the ENTIRE interview (facts + history),
 * which is exactly what makes them resets rather than ordinary
 * forward/backward navigation.
 */
function resetFlow(state: FlowState): FlowState {
  return initialFlowState(state.language, state.attempt + 1);
}

function sameNode(a: OracleNode, b: OracleNode): boolean {
  if (a.kind !== b.kind) return false;
  if (a.kind === "question" && b.kind === "question")
    return a.questionId === b.questionId;
  return true;
}

/** `application_channel` values that only exist while the applicant stays
 * in Indonesia through the whole process — a status-bridging permit exists
 * solely to cover someone already onshore whose conversion is pending
 * (created by Permenkumham 11/2024, inserting Ps. 80(3)(f), 80(4)(d), 86A,
 * 94A, 94B into Permenkumham 22/2023 — the bridging articles are
 * unaffected by the later Permen Imipas 3/2025 partial revocation, which
 * touches only Ps. 43/45/52/53/54/55; see
 * `research/visa/2026-07-24-w2-factbase-bridging.md:21,37`); an onshore
 * conversion is, by definition, done without leaving. `OFFSHORE` is the
 * only channel that requires leaving. */
const ONSHORE_APPLICATION_CHANNELS = new Set([
  "ONSHORE_CONVERSION",
  "STATUS_BRIDGING",
]);

/**
 * `wants_onshore_conversion` and `application_channel` ask the SAME
 * real-world question — will this proceed while the applicant stays in
 * Indonesia? — from two different angles: a plain yes/no, and a
 * closed-enum channel pick. Neither is ever derived from the other here:
 * `why.wants_onshore_conversion` (i18n.ts) promises the boolean is "sent
 * without choosing a conversion path", and `why.application_channel`
 * promises the channel is "sent unchanged ... the interface never assigns
 * a channel from your dates". This only recognizes when the two answers
 * can never both be true, so `flowReducer` can refuse to record the second
 * one instead of sending a self-contradictory pair.
 *
 * This is the exact pairing that, left unchecked, let a `false` answer
 * here disarm the safety-critical hard filter
 * `hf.d12-onshore-conversion-excluded` (which reads only
 * `process.wants_onshore_conversion`) while `ONSHORE_CONVERSION` sat
 * unread by every rule in the pack — D12 ("Visit Visa Pre-Investment —
 * Multiple Entry", `names.en` in rulepack-prod-012.source.json:1583-1586;
 * NOT the pricing-catalog `item_key` "D12 Business Investigation (1
 * Year)" at line 1622, a price-list label, not the product's regulatory
 * identity) got recommended as if the applicant were applying from
 * offshore.
 *
 * "unsure" on either side is never a disagreement — it is the tri-state
 * safety net the engine already relies on (NEEDS_INPUT) — so it is
 * deliberately excluded here, as is an as-yet-unanswered
 * `wantsOnshoreConversion`.
 *
 * LIMITATION — this is a browser-side courtesy, not an API boundary.
 * `ApplicantFactsData` in `models.py` has no cross-field validator between
 * `process.application_channel` and `process.wants_onshore_conversion`
 * (verified by reading the model: no `model_validator` sits on that
 * class), so a request built outside this interview can still POST the
 * exact contradictory pair straight to `/api/visa-oracle/evaluate` and
 * have it accepted. This guard improves the honest interview user's
 * experience; it closes nothing at the API. The rulepack-side defense for
 * `hf.d12-onshore-conversion-excluded` reading only one of the two facts
 * is a separate, not-yet-landed fix out of this PR's scope (apps/mouth
 * only) — do not read this guard's existence as evidence that gap is
 * closed.
 */
export function channelConflictsWithOnshoreIntent(
  wantsOnshoreConversion: string | undefined,
  applicationChannel: string,
): boolean {
  if (
    wantsOnshoreConversion === undefined ||
    wantsOnshoreConversion === "unsure" ||
    applicationChannel === "unsure"
  ) {
    return false;
  }
  const channelIsOnshore = ONSHORE_APPLICATION_CHANNELS.has(applicationChannel);
  return (wantsOnshoreConversion === "yes") !== channelIsOnshore;
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
  void today; // kept injectable for snapshot/API compatibility
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
      if (facts.in_indonesia === "yes") {
        return { kind: "question", questionId: "permit_expiry" };
      }
      return { kind: "question", questionId: "overstay_days" };
    }
    case "permit_expiry":
      return { kind: "question", questionId: "current_status_code" };
    case "current_status_code":
      return { kind: "question", questionId: "overstay_days" };
    case "overstay_days":
      return facts.in_indonesia === "yes"
        ? { kind: "question", questionId: "wants_onshore_conversion" }
        : { kind: "question", questionId: "nationalities" };
    case "wants_onshore_conversion":
      return { kind: "question", questionId: "application_channel" };
    case "application_channel":
      return { kind: "question", questionId: "nationalities" };
    case "nationalities":
      return { kind: "question", questionId: "birth_date" };
    case "birth_date":
      return { kind: "question", questionId: "category" };
    case "category":
      return { kind: "question", questionId: "trip_scope" };
    case "trip_scope": {
      const first = getCategoryQuestionIds(facts)[0] ?? "stay_days";
      return { kind: "question", questionId: first };
    }
    case "review_gate":
      return { kind: "confirmation" };
    default: {
      const sequence = getCategoryQuestionIds(facts);
      const index = sequence.indexOf(current.questionId);
      if (index === -1 || index === sequence.length - 1) {
        return { kind: "question", questionId: "review_gate" };
      }
      return { kind: "question", questionId: sequence[index + 1] };
    }
  }
}

const FIXED_CATEGORY_QUESTIONS: Record<CategoryKey, readonly string[]> = {
  tourism: ["stay_days", "entry_pattern"],
  business: [
    "business_activity",
    "work_indonesia_compensation",
    "stay_days",
    "entry_pattern",
  ],
  work: [
    "sponsor_category",
    "work_payer",
    "work_indonesia_compensation",
    "work_sponsor_confirmed",
    "work_role",
    "stay_days",
  ],
  remote: [
    "sponsor_category",
    "remote_clients",
    "remote_compensation",
    "remote_employer_country",
    "remote_pt_pma",
    "stay_days",
  ],
  family: [],
  invest: [],
  retirement: [],
  study: [
    "sponsor_category",
    "study_level",
    "study_admission_confirmed",
    "study_sponsor_confirmed",
    "stay_days",
  ],
  diaspora: ["diaspora_connection", "diaspora_documents", "stay_days"],
  other: ["other_purpose", "other_paid_activity", "stay_days", "entry_pattern"],
};

/**
 * The behavioral question sequence for the selected interview category.
 * This is navigation only. It never interprets answers as eligibility and
 * never selects, orders, adds, or removes a visa candidate.
 */
export function getCategoryQuestionIds(facts: OracleFacts): readonly string[] {
  const category = facts.category as CategoryKey | undefined;
  if (!category || !CATEGORY_KEYS.includes(category)) return ["stay_days"];

  if (category === "invest") {
    const branch = facts.investment_vehicle;
    const branchQuestions =
      branch === "pt_pma"
        ? [
            "investment_pt_pma",
            "investment_capital_idr",
            "investment_paid_up_capital_idr",
            "investment_role",
          ]
        : branch === "property"
          ? ["secondhome_property_value_usd"]
          : branch === "bank_deposit"
            ? [
                "secondhome_deposit_usd",
                "secondhome_state_bank",
                "secondhome_own_name",
              ]
            : [];
    return [
      "sponsor_category",
      "investment_vehicle",
      ...branchQuestions,
      "stay_days",
    ];
  }

  if (category === "retirement") {
    const branch = facts.retirement_basis;
    const branchQuestions =
      branch === "bank_deposit"
        ? [
            "secondhome_deposit_usd",
            "secondhome_state_bank",
            "secondhome_own_name",
            "secondhome_passive_income_usd",
          ]
        : branch === "property"
          ? ["secondhome_property_value_usd"]
          : branch === "passive_income"
            ? ["secondhome_passive_income_usd", "family_sponsor_confirmed"]
            : branch === "family_sponsor"
              ? ["secondhome_passive_income_usd", "family_sponsor_confirmed"]
              : [];
    return [
      "sponsor_category",
      "retirement_basis",
      ...branchQuestions,
      "stay_days",
    ];
  }

  if (category === "family") {
    const sponsorCodes = facts.family_sponsor_nationalities?.split(",") ?? [];
    const needsPermitCode =
      facts.family_sponsor_nationalities !== undefined &&
      facts.family_sponsor_nationalities !== "unsure" &&
      !sponsorCodes.includes("ID");
    return [
      "sponsor_category",
      "family_relation",
      "marital_status",
      "family_sponsor_nationalities",
      ...(needsPermitCode ? ["family_sponsor_status_code"] : []),
      // PARENT added 2026-08-19 (seq-10 companion change, Kimi refuter
      // finding 1): E31C's engine rules require the PARENTS' registered
      // marriage (`family.marriage_registered`), but this question only
      // fired for SPOUSE — so every PARENT-relation interview shipped the
      // fact UNKNOWN by construction and the seq-10 HARD_FILTER would
      // dead-end those applicants in NEEDS_INPUT with no way to answer.
      ...(facts.family_relation === "SPOUSE" ||
      facts.family_relation === "PARENT"
        ? ["family_marriage_registered"]
        : []),
      "family_sponsor_confirmed",
      "stay_days",
    ];
  }

  return FIXED_CATEGORY_QUESTIONS[category];
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
 * `work_payer`) sitting in `state.facts`, silently feeding later evaluation
 * with answers to questions the user never reached on their current path.
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
      if (
        action.questionId === "application_channel" &&
        channelConflictsWithOnshoreIntent(
          state.facts.wants_onshore_conversion,
          action.value,
        )
      ) {
        // Refuse to record it: neither fact is derived from the other or
        // silently overwritten (see `channelConflictsWithOnshoreIntent`).
        // History/facts stay exactly where they were — the user is still
        // on `application_channel` and can pick a different, coherent
        // channel, or use Back to correct `wants_onshore_conversion`
        // instead. The UI reads `blockedAnswer` to explain why.
        return {
          ...state,
          blockedAnswer: {
            questionId: "application_channel",
            conflictsWithQuestionId: "wants_onshore_conversion",
          },
        };
      }
      const facts = pruneFacts(
        { ...state.facts, [action.questionId]: action.value },
        state.history,
      );
      const current = state.history[state.history.length - 1];
      const next = computeNextNode(current, facts, action.today);
      return {
        ...state,
        facts,
        history: [...state.history, next],
        blockedAnswer: null,
      };
    }
    case "SKIP": {
      const facts = pruneFacts(
        { ...state.facts, [action.questionId]: "unsure" },
        state.history,
      );
      const current = state.history[state.history.length - 1];
      const next = computeNextNode(current, facts, action.today);
      return {
        ...state,
        facts,
        history: [...state.history, next],
        blockedAnswer: null,
      };
    }
    case "ADVANCE": {
      const current = state.history[state.history.length - 1];
      if (current.kind !== "framing" && current.kind !== "confirmation")
        return state;
      const next = computeNextNode(current, state.facts);
      return {
        ...state,
        history: [...state.history, next],
        blockedAnswer: null,
      };
    }
    case "BACK": {
      if (state.history.length <= 1) return state;
      const history = state.history.slice(0, -1);
      return {
        ...state,
        history,
        facts: pruneFacts(state.facts, history),
        blockedAnswer: null,
      };
    }
    case "EDIT": {
      const target: OracleNode = {
        kind: "question",
        questionId: action.questionId,
      };
      const history = truncateToNode(state.history, target);
      return {
        ...state,
        history,
        facts: pruneFacts(state.facts, history),
        blockedAnswer: null,
      };
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
        return resetFlow(state);
      }
      const truncated = truncateToNode(state.history, target);
      const prunedFacts = pruneFacts(state.facts, truncated);
      const facts = { ...prunedFacts, category: action.category };
      const next = computeNextNode(target, facts, action.today);
      return {
        ...state,
        facts,
        history: [...truncated, next],
        blockedAnswer: null,
      };
    }
    case "REVIEW_ANSWERS": {
      // Verdict screen's "Edit answers" link — jump back to the
      // confirmation screen without discarding any facts ahead of it.
      const target: OracleNode = { kind: "confirmation" };
      const history = truncateToNode(state.history, target);
      return {
        ...state,
        history,
        facts: pruneFacts(state.facts, history),
        blockedAnswer: null,
      };
    }
    case "RESTART":
      return resetFlow(state);
    case "SET_LANGUAGE":
      // Facts are keys, never localized strings — switching languages
      // never touches them (design doc §3 "instant, no lost history").
      return { ...state, language: action.language };
    default:
      return state;
  }
}

export function useOracleFlow(options: UseOracleFlowOptions = {}) {
  const {
    initialLanguage = "en",
    initialSnapshot,
    onSnapshot,
    snapshotNow,
    restoreToday,
  } = options;
  const [state, dispatch] = useReducer(
    flowReducer,
    { initialLanguage, initialSnapshot, restoreToday },
    ({
      initialLanguage: language,
      initialSnapshot: snapshot,
      restoreToday: hydrationClock,
    }) =>
      restoreInterviewSnapshot(snapshot, language, hydrationClock) ??
      initialFlowState(language),
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
  const assumptions = useMemo<InterviewAssumption[]>(
    () =>
      Object.entries(state.facts)
        .filter(([, value]) => value === "unsure")
        .map(([questionId]) => ({
          id: `unsure:${questionId}`,
          questionId,
          editable: true,
        })),
    [state.facts],
  );
  const selectedCategory = state.facts.category as CategoryKey | undefined;
  const interviewBranchesRemaining =
    selectedCategory && CATEGORY_KEYS.includes(selectedCategory)
      ? 1
      : CATEGORY_KEYS.length;
  const getSnapshot = useCallback(
    () =>
      createInterviewSnapshot(
        {
          attempt: state.attempt,
          history: state.history,
          facts: state.facts,
        },
        snapshotNow?.() ?? new Date(),
      ),
    [snapshotNow, state.attempt, state.facts, state.history],
  );

  useEffect(() => {
    if (!onSnapshot) return;
    onSnapshot(getSnapshot());
  }, [getSnapshot, onSnapshot]);

  return {
    state,
    current,
    assumptions,
    interviewBranchesRemaining,
    canGoBack: state.history.length > 1,
    getSnapshot,
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
    ...(facts.in_indonesia === "yes"
      ? [
          { id: "permit_expiry", labelI18nKey: "tree.permit_expiry" },
          {
            id: "current_status_code",
            labelI18nKey: "tree.current_status_code",
          },
        ]
      : []),
    { id: "overstay_days", labelI18nKey: "tree.overstay_days" },
    ...(facts.in_indonesia === "yes"
      ? [
          {
            id: "wants_onshore_conversion",
            labelI18nKey: "tree.wants_onshore_conversion",
          },
          {
            id: "application_channel",
            labelI18nKey: "tree.application_channel",
          },
        ]
      : []),
    { id: "nationalities", labelI18nKey: "tree.nationalities" },
    { id: "birth_date", labelI18nKey: "tree.birth_date" },
    { id: "category", labelI18nKey: "tree.category" },
    { id: "trip_scope", labelI18nKey: "tree.trip_scope" },
    ...behavioralSteps(facts),
    { id: "review_gate", labelI18nKey: "tree.review_gate" },
    { id: "confirmation", labelI18nKey: "tree.confirmation" },
    { id: "verdict", labelI18nKey: "tree.verdict" },
  ];

  const currentId =
    current.kind === "question" ? current.questionId : current.kind;
  const currentIdx = order.findIndex((s) => s.id === currentId);

  const trunk: TreeStep[] = order.map((step, idx) => {
    if (currentIdx === -1) {
      return {
        id: step.id,
        labelI18nKey: step.labelI18nKey,
        status: "pending",
      };
    }
    if (idx === currentIdx) {
      return {
        id: step.id,
        labelI18nKey: step.labelI18nKey,
        status: "current",
      };
    }
    if (idx > currentIdx) {
      return {
        id: step.id,
        labelI18nKey: step.labelI18nKey,
        status: "pending",
      };
    }
    // idx < currentIdx — structurally "passed" in `order`, but ordinal
    // position alone is a LIE for a real question step (P0, Codex
    // GPT-5.6-terra xhigh adversarial review 2026-07-18): the onshore
    // urgent/expired/unsure permit_expiry lane (computeNextNode above,
    // "permit_expiry" case) jumps straight to "review_gate", skipping
    // "category" entirely — yet "category" still sits earlier in `order`
    // than "review_gate", so the old `idx < currentIdx → "done"` rule
    // marked it "done" even though it was never asked, exposing a
    // tap-to-edit button whose EDIT dispatch was a silent no-op
    // (`truncateToNode` finds no matching history entry). Ground truth
    // for any REAL question step is the fact itself — `pruneFacts`
    // already guarantees `facts` only ever holds keys for questions
    // actually answered on the current path, so a question step is
    // "done" only if its fact is present. Non-question trunk items
    // (framing/review_gate/confirmation) have no fact key and are never
    // skippable the way category is — every path passes through them in
    // order — so ordinal position stays correct for those.
    const isQuestionStep = Object.prototype.hasOwnProperty.call(
      QUESTIONS,
      step.id,
    );
    const status: TreeStepStatus =
      isQuestionStep && facts[step.id] === undefined ? "pending" : "done";
    return { id: step.id, labelI18nKey: step.labelI18nKey, status };
  });

  const category = facts.category as CategoryKey | undefined;
  const hasSelectedCategory =
    category !== undefined && CATEGORY_KEYS.includes(category);
  const atOrPastCategory =
    currentId === "category" ||
    (currentIdx !== -1 &&
      order.findIndex((s) => s.id === "category") < currentIdx);

  const categoryLeaves: TreeCategoryLeaf[] | null = atOrPastCategory
    ? CATEGORY_KEYS.map((key) => ({
        key,
        status: hasSelectedCategory
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
  // Trunk entries only make sense once "category" has an answer at all —
  // before that, computeNextNode can't have routed past it either. But the
  // answer doesn't have to be a real `CategoryKey`: the category question
  // has `notSure: { mode: "human-review" }` (tree.ts), so a real interview
  // can leave `facts.category === "unsure"` (flowReducer's SKIP action,
  // reachable from any language's "Not sure?" affordance). `getCategoryQuestionIds`
  // is already the graph's single source of truth for "what comes next" in
  // that case too — it falls back to `["stay_days"]` for any category that
  // isn't a recognized `CategoryKey` (tree.ts, same fallback `computeNextNode`'s
  // "trip_scope" case relies on). The old `BEHAVIORAL_CATEGORIES.has(category)`
  // guard here duplicated that check and disagreed with it: for "unsure" it
  // returned `[]` while `getCategoryQuestionIds` still returns `["stay_days"]`,
  // so the live node (e.g. "stay_days") was absent from `order` in
  // `getTreeSteps` above — `currentIdx` came back -1, every trunk entry read
  // "pending", and the sr-only nav rendered a completely empty `<ol>` for
  // that step (and every step after it) — language-independent; the same
  // empty nav reproduces in English under the identical fact-state. Delegate
  // to `getCategoryQuestionIds` unconditionally instead of re-deciding here.
  if (facts.category === undefined) return [];
  return getCategoryQuestionIds(facts).map((id) => ({
    id,
    labelI18nKey: `tree.${id}`,
  }));
}

export { QUESTIONS };
