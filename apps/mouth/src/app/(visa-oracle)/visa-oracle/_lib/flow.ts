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
  daysRemaining,
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
  /**
   * The question id pushed onto the interview by `ASK_FOLLOW_UP` and not
   * yet answered (2026-09-06). It exists for exactly one reason: once that
   * question IS answered, the next node must be the verdict — a follow-up
   * is a detour taken FROM the verdict to satisfy one engine
   * `missing_facts` entry, not a re-entry into the spine. Without it,
   * `computeNextNode` would route by id and walk the applicant forward
   * through questions they already passed. Cleared by every action.
   */
  pendingFollowUp: string | null;
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
  /**
   * Fed to `restoreInterviewSnapshot` as its `today` argument, which that
   * function uses only as a defensive fallback (see its docstring) — NOT to
   * replay date-sensitive routing, which is keyed on the snapshot's own
   * save-time (`updatedAtIso`) instead. This is the resume-moment wall
   * clock, not an "as-of" override for replay.
   */
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
  /**
   * The NEEDS_INPUT follow-up (2026-09-06): the engine named a fact whose
   * question exists in `QUESTIONS` but was never asked on this walk, so the
   * interview ASKS it — appending the node, keeping every answer already
   * given. Deliberately NOT routed through `EDIT`: `EDIT` truncates history
   * back to its target and `pruneFacts` then discards everything after it,
   * which for a never-asked target means `resetFlow` — the whole interview
   * thrown away to collect one fact. Append, never truncate.
   */
  | { type: "ASK_FOLLOW_UP"; questionId: string }
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
    pendingFollowUp: null,
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
 * Any impossible node, invalid answer, or branch whose real graph has since
 * changed (e.g. a live deploy between save and resume) is truncated at the
 * last valid frontier; descendants are discarded by construction. Completely
 * malformed payloads return `null`.
 *
 * Date-sensitive routing during replay (`computeNextNode`'s `today` —
 * currently only `shouldAskRenewalPaid`, F4 2026-08-24) is evaluated
 * against the snapshot's OWN `updatedAtIso` — the moment it was SAVED —
 * never against the `today` parameter below/the caller's resume-time clock.
 * `updatedAtIso` is required and parse-validated earlier in this function,
 * so it is always available by the time replay runs; `today` is kept only
 * as an unreachable-in-practice defensive fallback for that parse. Replaying
 * against wall-clock-at-resume instead would make a SAVED answer's routing
 * depend on WHEN the browser tab happens to be reopened: a stay permit that
 * was still current the moment `overstay_days` was answered and saved, but
 * has since expired by the time the user resumes days later, would
 * recompute `shouldAskRenewalPaid` as `true`, diverge from the saved next
 * node, and TRUNCATE history right there — silently dropping every
 * already-answered fact past that point (`overstay_days` included), even
 * though nothing about the saved answers was ever invalid. `today` stays
 * real wall-clock for every NEW answer recorded from here on — `ANSWER`/
 * `SKIP` still default their own `today` to `new Date()` in `flowReducer`.
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
  // Date-sensitive routing replays against the moment this snapshot was
  // SAVED, never against `today` (the resume-time clock) — see this
  // function's docstring. The parse is guaranteed finite by the check just
  // above; `today` is kept only as a defensive fallback for the
  // unreachable case where it were not.
  const savedAtMs = Date.parse(value.updatedAtIso);
  const savedAt = Number.isFinite(savedAtMs) ? new Date(savedAtMs) : today;
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
    const expected = computeNextNode(current, facts, savedAt);
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
    // A snapshot is replayed through `computeNextNode`, which stops at the
    // verdict — so a follow-up node saved AFTER the verdict is never
    // restored and its fact is pruned with it. That is fail-closed on
    // purpose: the restored interview re-evaluates, the engine names the
    // same missing fact again, and the interview asks again. It never
    // resumes holding an answer whose question it cannot show.
    pendingFollowUp: null,
  };
}

/**
 * The reducer's ONE reset primitive: a full wipe back to
 * `initialFlowState`, with `attempt` incremented so every consumer that
 * needs to know "is this a genuinely new interview" (OracleShell's
 * evaluation-lease cache key, which now covers every engine mode — SHADOW,
 * internal preview and the rendered REAL verdict — not just SHADOW) can
 * key off `state.attempt` instead of enumerating which actions perform a
 * reset. Called from RESTART and the EDIT / SELECT_CATEGORY defensive
 * fallbacks below — all discard the ENTIRE interview (facts + history),
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
 * experience; it closes nothing at the API.
 *
 * The rulepack-side gap — `hf.d12-onshore-conversion-excluded` reads only
 * `process.wants_onshore_conversion` — is real, but the correct fix for
 * it is NOT yet determined (as of 2026-08-23; under adjudication whether
 * D12's affected eligibility rule is missing a conjunct its siblings
 * correctly carry, or its siblings wrongly carry one D12 was never
 * supposed to gate on). Do not read this guard's existence as evidence
 * that gap is closed, and do not assume any specific rulepack edit is
 * already agreed — the mechanism is undetermined, not merely unlanded.
 * Any such fix is out of this PR's scope (apps/mouth only) regardless.
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
 * Gate for the `renewal_paid` question (F4, 2026-08-24): asked only when
 * the applicant holds a stay permit (`holds_stay_permit === "yes"`, the
 * only route that reaches `stay_permit_code`) AND `permit_expiry` is
 * either KNOWN-and-in-the-past or itself UNKNOWN — a known-current permit
 * skips it. Reuses `daysRemaining` (tree.ts) so "in the past" and "unknown"
 * share the exact same parsing/validity rules the rest of the interview
 * already relies on: an invalid/missing/"unsure" `permit_expiry` yields
 * `null`, which this treats as unknown (ask), never as current (skip).
 */
export function shouldAskRenewalPaid(
  facts: OracleFacts,
  today: Date = new Date(),
): boolean {
  if (facts.holds_stay_permit !== "yes") return false;
  const remaining = daysRemaining(facts.permit_expiry ?? "", today);
  return remaining === null || remaining < 0;
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
      // Fixed 2026-08-24 (Kimi refuter P0 finding on the D12
      // offshore-reachability gap, then re-fixed same day after a
      // team-lead funnel-cost review rejected the first version): before
      // the P0 fix, `"no"` skipped straight to `overstay_days`, so
      // `permit_expiry`/`holds_stay_permit`/`stay_permit_code`/
      // `current_status_code` were structurally unreachable for every
      // offshore applicant — D12's own target population, including the
      // exact person the owner's D12 ruling names (someone abroad holding
      // an unlapsed KITAS). #4695 fixed the codes on offer but never the
      // reachability of the gate itself.
      //
      // The FIRST fix mirrored the onshore chain unconditionally (ask
      // `permit_expiry` first, same as onshore) — team-lead measured that
      // as a flat 3-question cost added to EVERY offshore applicant of
      // EVERY product (~38), to serve exactly one product's rule (grepped
      // the live signed pack: no product other than D12 reads these facts
      // for an offshore applicant — the only other consumer, `BRIDGING`,
      // is itself onshore-only). This version instead asks
      // `holds_stay_permit` FIRST for offshore — a single gate question —
      // and only expands into the full `permit_expiry`/`stay_permit_code`
      // chain on "yes". A "no" answer converges straight to
      // `overstay_days`: `fact-mapper.ts::mapCurrentStatusCode` derives
      // `immigration.current_status_code` directly from that "no" (the
      // synthesized `NO_STAY_PERMIT` sentinel — see its docstring and
      // `fact_registry.py`'s `_VISIT_CLASS_STATUS_CODES`), so the fact
      // still resolves definitely without a redundant extra question.
      // Onshore is completely unchanged — see the `permit_expiry` and
      // `holds_stay_permit` cases below for how the two orders coexist
      // without looping.
      return facts.in_indonesia === "yes"
        ? { kind: "question", questionId: "permit_expiry" }
        : { kind: "question", questionId: "holds_stay_permit" };
    }
    case "permit_expiry":
      // Onshore always arrives here FIRST (before `holds_stay_permit`,
      // the pre-existing order — deliberately not redesigned by this fix).
      // Offshore arrives here ONLY after `holds_stay_permit === "yes"`
      // (see that case below), so routing offshore straight to
      // `stay_permit_code` here — instead of back to `holds_stay_permit` —
      // is required to avoid an infinite loop, not an inconsistency.
      return facts.in_indonesia === "yes"
        ? { kind: "question", questionId: "holds_stay_permit" }
        : { kind: "question", questionId: "stay_permit_code" };
    case "holds_stay_permit": {
      if (facts.in_indonesia === "yes") {
        // Onshore: unchanged pre-existing behavior.
        return facts.holds_stay_permit === "yes"
          ? { kind: "question", questionId: "stay_permit_code" }
          : { kind: "question", questionId: "current_status_code" };
      }
      // Offshore: this is the gate question itself (asked before
      // `permit_expiry`, unlike onshore). "yes" still needs the real
      // code+expiry chain; "no" converges directly — see the
      // `fact-mapper.ts` comment above for why no further question is
      // needed to resolve the fact.
      return facts.holds_stay_permit === "yes"
        ? { kind: "question", questionId: "permit_expiry" }
        : { kind: "question", questionId: "overstay_days" };
    }
    case "stay_permit_code":
      return shouldAskRenewalPaid(facts, today)
        ? { kind: "question", questionId: "renewal_paid" }
        : { kind: "question", questionId: "overstay_days" };
    case "renewal_paid":
      return { kind: "question", questionId: "overstay_days" };
    case "current_status_code":
      return { kind: "question", questionId: "overstay_days" };
    case "overstay_days":
      return facts.in_indonesia === "yes"
        ? { kind: "question", questionId: "wants_onshore_conversion" }
        : { kind: "question", questionId: "nationalities" };
    case "wants_onshore_conversion":
      // Two call sites since 2026-09-06. ONSHORE it is a spine question
      // (asked right after `overstay_days`, see that case above) and leads
      // into `application_channel`. OFFSHORE the spine skips it entirely
      // and the invest branch asks it as a CATEGORY question
      // (`getCategoryQuestionIds` below) — routing that occurrence to
      // `application_channel` would splice the applicant back into the
      // onshore spine mid-branch and re-ask questions they already passed.
      // Fall through to the category sequence instead.
      return facts.in_indonesia === "yes"
        ? { kind: "question", questionId: "application_channel" }
        : nextCategoryQuestion(current.questionId, facts);
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
    default:
      return nextCategoryQuestion(current.questionId, facts);
  }
}

/**
 * The step after `questionId` inside the current category's own sequence,
 * or `review_gate` when the sequence is finished (or does not contain the
 * question at all). Extracted from `computeNextNode`'s `default` arm so the
 * offshore `wants_onshore_conversion` occurrence — which the switch above
 * matches by id before ever reaching `default` — can reuse the identical
 * rule rather than a hand-copied one.
 */
function nextCategoryQuestion(
  questionId: string,
  facts: OracleFacts,
): OracleNode {
  const sequence = getCategoryQuestionIds(facts);
  const index = sequence.indexOf(questionId);
  if (index === -1 || index === sequence.length - 1) {
    return { kind: "question", questionId: "review_gate" };
  }
  return { kind: "question", questionId: sequence[index + 1] };
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
    // `work_role` removed 2026-09-06 (owner ruling 6) — see the deletion
    // note where it used to sit in tree.ts.
    "stay_days",
  ],
  remote: [
    "sponsor_category",
    "remote_clients",
    "remote_compensation",
    // `work_payer` added 2026-09-06. It is the ONLY input to
    // `work.employer_is_indonesian_entity` (fact-mapper.ts's
    // `mapEmployerIsIndonesianEntity`), and `hf.e33g.indonesian-employer`
    // is `on_unknown: NEEDS_INPUT` — so before this, every remote-work
    // interview dead-ended on a fact it was never offered a way to answer.
    // NOT derived from `remote_employer_country` (asked next, and read by
    // no rule in the pack): "the employer's country is not ID" does not
    // entail "the employer is not an Indonesian entity" — an ID-registered
    // branch of a foreign group is both.
    "work_payer",
    "remote_employer_country",
    "remote_pt_pma",
    "stay_days",
  ],
  family: [],
  invest: [],
  retirement: [],
  second_home: [],
  study: [
    "sponsor_category",
    "study_level",
    "study_admission_confirmed",
    "study_sponsor_confirmed",
    "stay_days",
  ],
  diaspora: [],
  other: [
    "other_purpose",
    "other_paid_activity",
    // `family_sponsor_confirmed` added 2026-09-06: `el.c6.social` is the
    // one rule that covers the `OTHER` purpose and it requires
    // `family.sponsor_confirmed == true`, so this branch could not reach a
    // candidate without it.
    "family_sponsor_confirmed",
    "stay_days",
    "entry_pattern",
  ],
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
      // `family_sponsor_confirmed` added 2026-09-06: `el.c2.business` is
      // the rule that covers a declared INVESTMENT purpose and it requires
      // `family.sponsor_confirmed == true`. Already asked in the family
      // and retirement branches — same question, same fact, new branch.
      "family_sponsor_confirmed",
      // `wants_onshore_conversion` added 2026-09-06, OFFSHORE ONLY. Onshore
      // the spine already asks it (`computeNextNode`'s `overstay_days`
      // case), so adding it here would ask it twice. Offshore it was
      // structurally unaskable, which is exactly where
      // `hf.d12-onshore-conversion-excluded`
      // (`on_unknown: NEEDS_INPUT`, `safety_critical`) bites: D12's own
      // target population is offshore. Measured 2026-09-06 on signed
      // seq-19: with the answer supplied, offshore/invest/PT-PMA returns
      // `SUPPORTED_CANDIDATES [D12]` on "no" and `NO_SUPPORTED_PATH` on
      // "yes" — decisive both ways.
      //
      // ASKED, never derived. Deriving `false` from "offshore and holding
      // no permit" was measured as a fail-open on this exact persona: the
      // fact is forward-looking INTENT ("are you asking to change status
      // without leaving Indonesia?"), so an investor planning "enter on
      // D12, then alih status onshore" answers TRUE, and a derived `false`
      // returns a confident D12 recommendation with zero review reasons
      // for a visa that by regulation cannot be converted onshore.
      ...(facts.in_indonesia === "no" ? ["wants_onshore_conversion"] : []),
      "stay_days",
    ];
  }

  // Second Home (owner ruling 3, 2026-09-06). No `sponsor_category`: no
  // E33 rule reads `sponsor.type`, and every extra question carries
  // `notSure: { mode: "human-review" }`, so a ceremonial one can only add
  // review volume without ever changing an outcome.
  if (category === "second_home") {
    const branch = facts.secondhome_basis;
    const branchQuestions =
      branch === "bank_deposit"
        ? [
            "secondhome_deposit_usd",
            "secondhome_state_bank",
            "secondhome_own_name",
          ]
        : branch === "property"
          ? ["secondhome_property_value_usd"]
          : [];
    return ["secondhome_basis", ...branchQuestions, "stay_days"];
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
    return familyQuestionIds(facts);
  }

  // Diaspora reuses the FAMILY question set (owner ruling 4, 2026-09-06).
  // `CATEGORY_TO_PURPOSE` now maps `diaspora → FAMILY` (fact-mapper.ts),
  // and the products a diaspora applicant actually reaches — E31C/E31F —
  // are family-reunification products whose rules read
  // `family.relation_to_sponsor`, `family.sponsor_nationalities` and
  // `family.sponsor_confirmed`. Asking the diaspora context first keeps the
  // two questions that make this tile distinct; everything after them is
  // the identical family branch, so a future family-branch change cannot
  // silently diverge here.
  if (category === "diaspora") {
    return [
      "diaspora_connection",
      "diaspora_documents",
      ...familyQuestionIds(facts),
    ];
  }

  return FIXED_CATEGORY_QUESTIONS[category];
}

/** The FAMILY branch sequence, shared verbatim by the `family` and
 * `diaspora` tiles (owner ruling 4) so the two can never drift apart. */
function familyQuestionIds(facts: OracleFacts): readonly string[] {
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
    // `family_sponsor_permit_basis` rides the same condition as
    // `family_sponsor_status_code` (2026-08-23 owner ruling): the
    // Permenkumham 11/2024 Pasal 33 ayat (7) family-reunification-chaining
    // exclusion only matters when the sponsor itself is a foreign
    // ITAS/ITAP holder, not an Indonesian citizen.
    ...(needsPermitCode
      ? ["family_sponsor_status_code", "family_sponsor_permit_basis"]
      : []),
    // PARENT added 2026-08-19 (seq-10 companion change, Kimi refuter
    // finding 1): E31C's engine rules require the PARENTS' registered
    // marriage (`family.marriage_registered`), but this question only
    // fired for SPOUSE — so every PARENT-relation interview shipped the
    // fact UNKNOWN by construction and the seq-10 HARD_FILTER would
    // dead-end those applicants in NEEDS_INPUT with no way to answer.
    ...(facts.family_relation === "SPOUSE" || facts.family_relation === "PARENT"
      ? ["family_marriage_registered"]
      : []),
    // STEPCHILD added 2026-08-23 (owner ruling — E31D vocabulary
    // extension): both evidence facts the ruling named, marriage
    // certificate of the WNA-WNI parents and birth certificate of the
    // stepchild, asked together whenever the relation is STEPCHILD.
    ...(facts.family_relation === "STEPCHILD"
      ? [
          "family_stepchild_marriage_certificate_confirmed",
          "family_stepchild_birth_certificate_confirmed",
        ]
      : []),
    "family_sponsor_confirmed",
    "stay_days",
  ];
}

/**
 * Hard bound on the replay below. The spine plus the longest branch is far
 * short of it; the cap exists so that a future routing mistake degrades
 * into a truncated list instead of a frozen tab.
 */
const WALK_REPLAY_LIMIT = 64;

/**
 * Every question this walk WOULD ask, replayed from the framing screen
 * against `facts` as they stand — the same `computeNextNode` the interview
 * itself runs, so the list can never disagree with the routing.
 */
export function walkQuestionIds(
  facts: OracleFacts,
  today?: Date,
): readonly string[] {
  const ids: string[] = [];
  let node: OracleNode = { kind: "framing" };
  for (let step = 0; step < WALK_REPLAY_LIMIT; step += 1) {
    node = computeNextNode(node, facts, today);
    if (node.kind !== "question") break;
    // Defensive only: `computeNextNode` is acyclic today, and a cycle
    // introduced later must not hang the verdict screen.
    if (ids.includes(node.questionId)) break;
    ids.push(node.questionId);
  }
  return ids;
}

/**
 * Whether the NEEDS_INPUT follow-up may append `questionId` to THIS
 * interview (adversarial review 2026-09-06, finding 1 — accepted,
 * narrowed).
 *
 * Many questions appear in their branch only under a condition on the
 * facts: `family_marriage_registered` exists for a SPOUSE or PARENT
 * relation, the Second Home evidence questions for one documented basis,
 * `renewal_paid` for one permit shape. Splicing such a question in when
 * its condition is unmet asks the applicant something their own earlier
 * answer has already ruled out — the tree's prerequisite ordering
 * bypassed, which is exactly the blocker the review raised.
 *
 * The test is structural, not a hand-maintained table of gates, so it
 * cannot drift from the routing: hold every answer given so far fixed and
 * replay the walk once per category. If ANY category's walk asks the
 * question, its prerequisites are satisfied (a question that "declares no
 * gate" is asked by its own branch for any facts, so choosing that branch
 * surfaces it). If NO category can reach it, the only thing standing in
 * the way is a fact the applicant has already answered the other way, and
 * the interview keeps today's behaviour: the human-handoff row.
 */
export function followUpPrerequisitesMet(
  questionId: string,
  facts: OracleFacts,
  today?: Date,
): boolean {
  if (walkQuestionIds(facts, today).includes(questionId)) return true;
  return CATEGORY_KEYS.some((category) =>
    walkQuestionIds({ ...facts, category }, today).includes(questionId),
  );
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

/**
 * Where a just-recorded answer leads. `computeNextNode` in every case but
 * one: when the answered question IS a follow-up (a node appended from the
 * verdict to satisfy one engine `missing_facts` entry), the answer goes
 * straight back to the verdict for re-evaluation. Routing it by id instead
 * would splice the applicant into whatever sequence that question normally
 * belongs to and re-ask what they have already answered.
 *
 * Two ways to recognise it, because `pendingFollowUp` alone is not enough.
 * It is cleared by BACK, so an applicant who answers the follow-up, steps
 * BACK onto it and answers again holds no pending id — and would fall
 * through to `nextCategoryQuestion`, landing on `review_gate` instead of
 * the verdict they came from. A verdict already sitting EARLIER in history
 * is the durable signal: `EDIT`, `BACK`, `REVIEW_ANSWERS` and
 * `SELECT_CATEGORY` all truncate, so no other action can leave a question
 * node standing after a verdict.
 */
function nextAfterAnswer(
  state: FlowState,
  questionId: string,
  facts: OracleFacts,
  today?: Date,
): OracleNode {
  if (state.pendingFollowUp === questionId) return { kind: "verdict" };
  const precedingNodes = state.history.slice(0, -1);
  if (precedingNodes.some((node) => node.kind === "verdict")) {
    return { kind: "verdict" };
  }
  return computeNextNode(state.history[state.history.length - 1], facts, today);
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
      const next = nextAfterAnswer(
        state,
        action.questionId,
        facts,
        action.today,
      );
      return {
        ...state,
        facts,
        history: [...state.history, next],
        blockedAnswer: null,
        pendingFollowUp: null,
      };
    }
    case "SKIP": {
      const facts = pruneFacts(
        { ...state.facts, [action.questionId]: "unsure" },
        state.history,
      );
      const next = nextAfterAnswer(
        state,
        action.questionId,
        facts,
        action.today,
      );
      return {
        ...state,
        facts,
        history: [...state.history, next],
        blockedAnswer: null,
        pendingFollowUp: null,
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
        pendingFollowUp: null,
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
        pendingFollowUp: null,
      };
    }
    case "EDIT": {
      const target: OracleNode = {
        kind: "question",
        questionId: action.questionId,
      };
      if (!state.history.some((node) => sameNode(node, target))) {
        // An absent target cannot safely reopen this interview's branch.
        return resetFlow(state);
      }
      const history = truncateToNode(state.history, target);
      return {
        ...state,
        history,
        facts: pruneFacts(state.facts, history),
        blockedAnswer: null,
        pendingFollowUp: null,
      };
    }
    case "ASK_FOLLOW_UP": {
      const question = QUESTIONS[action.questionId];
      // Two refusals, both no-ops rather than guesses. An unregistered id
      // could not be rendered. An id ALREADY in history is not a follow-up
      // at all — reopening it is `EDIT`'s job, and silently redirecting
      // here would append a duplicate node for a question the user can
      // already see on the confirmation card.
      if (!question) return state;
      const target: OracleNode = {
        kind: "question",
        questionId: action.questionId,
      };
      if (state.history.some((node) => sameNode(node, target))) return state;
      return {
        ...state,
        // Append. `facts` is untouched — nothing the applicant already
        // answered is discarded to collect this one fact, which is the
        // whole difference from `EDIT`.
        history: [...state.history, target],
        blockedAnswer: null,
        pendingFollowUp: action.questionId,
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
        pendingFollowUp: null,
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
        pendingFollowUp: null,
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
  /** NEEDS_INPUT follow-up — appends a never-asked question, keeps every
   * answer. See the `ASK_FOLLOW_UP` action's doc comment for why this is
   * not `edit`. */
  const askFollowUp = useCallback(
    (questionId: string) => dispatch({ type: "ASK_FOLLOW_UP", questionId }),
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
    askFollowUp,
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
  // The permit-status chain has TWO distinct shapes depending on
  // `in_indonesia` (fixed 2026-08-24 — see `computeNextNode`'s
  // `in_indonesia`/`permit_expiry`/`holds_stay_permit` cases for the
  // routing this mirrors, and the funnel-cost review that produced it).
  // Onshore always shows the full 3-node chain in the pre-existing order
  // (`permit_expiry` → `holds_stay_permit` → one of the two code
  // questions) the moment `in_indonesia` has a value. Offshore shows
  // `holds_stay_permit` FIRST, alone, until it too has a value — a "no"
  // answer converges with NO further permit-chain steps (the fact
  // resolves from that answer alone, see `fact-mapper.ts`), a "yes"
  // answer then adds `permit_expiry` + `stay_permit_code`.
  const renewalPaidStep: { id: string; labelI18nKey: string }[] =
    facts.holds_stay_permit === "yes" && shouldAskRenewalPaid(facts)
      ? [{ id: "renewal_paid", labelI18nKey: "tree.renewal_paid" }]
      : [];

  const permitChainSteps: { id: string; labelI18nKey: string }[] =
    facts.in_indonesia === "yes"
      ? [
          { id: "permit_expiry", labelI18nKey: "tree.permit_expiry" },
          { id: "holds_stay_permit", labelI18nKey: "tree.holds_stay_permit" },
          facts.holds_stay_permit === "yes"
            ? { id: "stay_permit_code", labelI18nKey: "tree.stay_permit_code" }
            : {
                id: "current_status_code",
                labelI18nKey: "tree.current_status_code",
              },
          ...renewalPaidStep,
        ]
      : facts.in_indonesia === "no"
        ? [
            {
              id: "holds_stay_permit",
              labelI18nKey: "tree.holds_stay_permit",
            },
            ...(facts.holds_stay_permit === "yes"
              ? [
                  {
                    id: "permit_expiry",
                    labelI18nKey: "tree.permit_expiry",
                  },
                  {
                    id: "stay_permit_code",
                    labelI18nKey: "tree.stay_permit_code",
                  },
                  ...renewalPaidStep,
                ]
              : []),
          ]
        : [];

  const order = [
    { id: "framing", labelI18nKey: "tree.framing" },
    { id: "in_indonesia", labelI18nKey: "tree.in_indonesia" },
    ...permitChainSteps,
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
    // tap-to-edit button for a question absent from history. EDIT now
    // resets the flow when its target is absent. Ground truth
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
 * action requires a matching `{ kind: "question" }` history entry and
 * resets the flow when its target is absent.
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
