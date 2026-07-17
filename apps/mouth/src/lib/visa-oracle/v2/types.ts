/**
 * Visa Oracle v2 — typed mock interview model (Track C PR C1, foundation only)
 *
 * MOCK DATA ONLY. The real deterministic engine (`visa_engine`, see
 * docs/plans/2026-07-17-visa-oracle-v2/00-product-design.md §5) is not on
 * main yet. Nothing here calls a backend — every function downstream of
 * these types is pure, and every candidate/price is synthetic. Real prices
 * come from PricingTool at wiring time (CLAUDE.md §8 rule 11).
 *
 * Owner ruling R1 (2026-07-17, design doc §0): client-facing pricing is ONE
 * all-inclusive price — never a split of official/PNBP fee vs. Bali Zero
 * fee. `MockCandidate.priceAllInclusive` is the only price field a
 * candidate may carry; never add `officialFee` / `serviceFee` / `pnbpFee`
 * or any other split field, here or downstream.
 */

/**
 * Five-state contract (design doc §1 "Zero unsupported recommendations" /
 * §5.3). An LLM may explain a persisted decision; it may never select, add,
 * remove, or rank paths — the engine (mocked here) is the sole authority.
 */
export type DecisionState =
  | "NEEDS_INPUT"
  | "SUPPORTED_CANDIDATES"
  | "HUMAN_REVIEW_REQUIRED"
  | "NO_SUPPORTED_PATH"
  | "TEMPORARILY_UNAVAILABLE";

/**
 * Outcome-page anatomy (design doc §3): eligibility is never binary — 4
 * states, color+icon+text, never color-alone. See visa-oracle-v2.css
 * `--vo2-eligible|likely|conditional|unlikely`.
 */
export type EligibilityLevel =
  | "eligible"
  | "likely"
  | "conditional"
  | "unlikely";

/**
 * Language-agnostic answer key (design doc §3: "Answers persist in a
 * language-agnostic shape (keys, never localized strings) so a mid-funnel
 * language switch is instant, no lost history."). Every stored answer —
 * including dates, stored as ISO `YYYY-MM-DD` — is a plain key string,
 * never a display string in either language.
 */
export type AnswerValue = string;

/** A bilingual copy pair. EN is authoritative for now (see `t()` below). */
export interface I18nText {
  en: string;
  id: string;
}

/**
 * "Why we ask" disclosure (design doc §3: "a disclosure glyph revealing one
 * sentence + the mapped regulation... the government-demo armor").
 */
export interface WhyWeAsk extends I18nText {
  regulationRef: string;
}

export interface QuestionOption {
  key: string;
  label: I18nText;
}

export interface InterviewQuestion {
  id: string;
  categoryId: string;
  kind: "single" | "date" | "category";
  prompt: I18nText;
  hint?: I18nText;
  whyWeAsk: WhyWeAsk;
  options: QuestionOption[];
  /**
   * "Not sure?" affordance (design doc §3: "Skip-with-assumptions → the
   * honesty receipt... takes the conservative branch and visibly flags the
   * assumption on the outcome page"). Deliberately OMITTED on questions
   * covered by the §4 load-bearing rule — "on 'not sure,' never guess on
   * money, payer, or clients — hold for a human" — those instead carry an
   * explicit in-band "not sure" option that routes to human review, never
   * a silently-assumed branch. See mock-tree.ts RW_WHO_PAYS / RW_INCOME_BAND.
   */
  skipAssumption?: QuestionOption;
}

export interface Assumption {
  qid: string;
  assumedKey: string;
}

/**
 * Q0 date-driven onshore lanes (design doc §4 table). `plan` covers the
 * "60+ days" row (named for its "Convert / Extend (planned)" UI tone).
 */
export type Lane =
  | "overstay-help"
  | "urgent-review"
  | "bridging-urgent"
  | "extend-convert"
  | "plan";

export interface InterviewState {
  answers: Record<string, AnswerValue>;
  assumptions: Assumption[];
  currentQuestionId: string | null;
  lane?: Lane;
}

export interface MockPrice {
  amountIDR: number;
  /** Always `true` — a compile-time + runtime tripwire that this is a
   * placeholder, never a real PricingTool figure. */
  mock: true;
}

export interface MockCandidate {
  code: string;
  name: I18nText;
  eligibility: EligibilityLevel;
  /**
   * Owner ruling R1: exactly ONE all-inclusive price per candidate. NEVER
   * add officialFee/serviceFee/pnbpFee or any other split field — a single
   * price is not dishonest; splitting confuses (design doc §0/§3). Real
   * prices are sourced from PricingTool at wiring time; this is an
   * obviously-fake placeholder amount for the prototype.
   */
  priceAllInclusive: MockPrice;
}

export interface MockOutcome {
  state: DecisionState;
  candidates?: MockCandidate[];
}

/**
 * Renders an {en,id} pair. Defaults to `en` — all copy is EN-only for this
 * PR (design doc content-finals for ID await an NB-INTEL Immigration
 * grounding pass, per §4's ⚑ note); the `id` field is populated with
 * plausible-but-non-final copy so the shape is exercised end-to-end ahead
 * of that pass.
 */
export function t(pair: I18nText): string {
  return pair.en;
}
