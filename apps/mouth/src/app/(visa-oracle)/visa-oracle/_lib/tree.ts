/**
 * Visa Oracle v2 — mock tree data model.
 *
 * Pure, typed, deterministic. No fetch, no side effects. Every answer is an
 * option KEY (language-agnostic by construction — spec §hard-constraint 3),
 * never localized/free text. Mirrors design doc §4 "The interview" and
 * spec item 26.
 *
 * PR1 scope note: this is a MOCK catalog/tree for the frontend experience
 * only. The real visa_engine (design doc §5) does not exist yet — nothing
 * here is wired to a backend, and nothing here should be read as a legal
 * source of truth. See the prototype badge in OracleShell.
 */

/** The four eligibility states a candidate visa can carry — never binary,
 * never color-alone (spec hard-constraint 4 / design doc §3). */
export type EligibilityState =
  | "eligible"
  | "likely"
  | "conditional"
  | "likely-not";

/** A single selectable option on a question. `key` is the only thing ever
 * persisted to facts/state — `labelI18nKey` looks up the display copy. */
export interface OracleOption {
  key: string;
  labelI18nKey: string;
  hintI18nKey?: string;
}

/** How a question's "Not sure?" affordance resolves (design doc §3/§4):
 * either it forces HUMAN_REVIEW_REQUIRED (money/payer/clients — the
 * load-bearing rule), or it takes a named conservative branch and the
 * assumption is visibly logged. Absent = no NotSure affordance rendered. */
export type NotSureBehavior =
  | { mode: "human-review" }
  | { mode: "conservative"; conservativeValue: string };

export interface OracleQuestion {
  id: string;
  i18nKey: string;
  kind: "branch" | "date" | "tiles" | "choice" | "review-gate";
  options: OracleOption[];
  /** Present only on sensitive questions (design doc §3 "why we ask" — the
   * gov-demo armor). Optional by construction: not every question is
   * sensitive enough to warrant a disclosure glyph. */
  whyWeAsk?: { i18nKey: string; regulation: string };
  sensitive?: boolean;
  notSure?: NotSureBehavior;
}

/** Answers, keyed by question id. Values are option keys OR, for the one
 * `kind: "date"` question, an ISO-8601 date string (still not free text —
 * a date picker's value, not typed prose). The reserved value `"unsure"`
 * means the NotSure affordance was used on that question. */
export type OracleFacts = Record<string, string>;

export interface MockVisaCard {
  code: string;
  nameI18nKey: string;
  taglineI18nKey: string;
  /** ONE all-inclusive number, IDR — owner ruling R1. Never a breakdown. */
  allInclusivePriceIDR: number;
  timelineDays: [min: number, max: number];
  eligibility: EligibilityState;
  requirementI18nKeys: string[];
  /** Which category tile(s) this card can ever apply to. */
  categories: string[];
  /** Additional gating: for each fact id, the allowed answer values. A
   * fact that hasn't been answered yet never excludes a card — this is
   * what makes pathsRemaining narrow monotonically as facts accumulate,
   * never reopen. */
  requiredFacts?: Record<string, string[]>;
  /** Finding #3 (adversarial review 2026-07-17): gate a card to specific
   * onshore lanes. Undefined = not lane-gated (offshore-eligible cards,
   * or cards that don't care about urgency). A lane that hasn't been
   * determined yet (null) never excludes — same monotonic-narrowing rule
   * as `requiredFacts`. */
  laneRestriction?: Lane[];
}

export const CATEGORY_KEYS = [
  "tourism",
  "business",
  "work",
  "invest",
  "remote",
  "family",
  "retirement",
  "study",
  "diaspora",
  "other",
] as const;
export type CategoryKey = (typeof CATEGORY_KEYS)[number];

/** The three categories with a drafted behavioral tree in PR1 (design doc
 * §4). The other seven route honestly to HUMAN_REVIEW_REQUIRED — never a
 * silent wrong answer, per §10.4 (lane-by-lane build is an open decision). */
export const BEHAVIORAL_CATEGORIES = new Set<CategoryKey>([
  "work",
  "remote",
  "tourism",
]);

export const QUESTIONS: Record<string, OracleQuestion> = {
  in_indonesia: {
    id: "in_indonesia",
    i18nKey: "q.in_indonesia",
    kind: "branch",
    sensitive: false,
    options: [
      { key: "yes", labelI18nKey: "q.in_indonesia.opt.yes" },
      { key: "no", labelI18nKey: "q.in_indonesia.opt.no" },
    ],
    notSure: { mode: "conservative", conservativeValue: "yes" },
  },
  permit_expiry: {
    id: "permit_expiry",
    i18nKey: "q.permit_expiry",
    kind: "date",
    sensitive: false,
    options: [],
    whyWeAsk: {
      i18nKey: "why.permit_expiry",
      regulation: "Permenkumham 11/2024",
    },
    // Finding #7 (adversarial review 2026-07-17): a date question offered
    // no honest "I don't know" — a user unsure of their own in_indonesia
    // status but forced onshore (conservative resolution) would otherwise
    // be stuck inventing a date. Unsure here always holds for a human,
    // same as money/payer/clients — never guess a compliance deadline.
    notSure: { mode: "human-review" },
  },
  category: {
    id: "category",
    i18nKey: "q.category",
    kind: "tiles",
    sensitive: false,
    whyWeAsk: {
      i18nKey: "why.category",
      regulation: "Kepmen M.IP-08.GR.01.01/2025",
    },
    options: CATEGORY_KEYS.map((key) => ({
      key,
      labelI18nKey: `q.category.opt.${key}`,
    })),
  },
  work_payer: {
    id: "work_payer",
    i18nKey: "q.work_payer",
    kind: "branch",
    sensitive: true,
    whyWeAsk: {
      i18nKey: "why.work_payer",
      regulation: "Permen Imipas 5/2025",
    },
    options: [
      { key: "yes", labelI18nKey: "q.work_payer.opt.yes" },
      { key: "no", labelI18nKey: "q.work_payer.opt.no" },
    ],
    notSure: { mode: "human-review" },
  },
  remote_clients: {
    id: "remote_clients",
    i18nKey: "q.remote_clients",
    kind: "choice",
    sensitive: true,
    whyWeAsk: {
      i18nKey: "why.remote_clients",
      regulation: "Permen Imipas 5/2025",
    },
    options: [
      { key: "foreign", labelI18nKey: "q.remote_clients.opt.foreign" },
      { key: "indonesian", labelI18nKey: "q.remote_clients.opt.indonesian" },
      { key: "mixed", labelI18nKey: "q.remote_clients.opt.mixed" },
    ],
    notSure: { mode: "human-review" },
  },
  remote_income: {
    id: "remote_income",
    i18nKey: "q.remote_income",
    kind: "branch",
    sensitive: true,
    whyWeAsk: {
      i18nKey: "why.remote_income",
      regulation: "Permen Imipas 5/2025",
    },
    options: [
      { key: "above", labelI18nKey: "q.remote_income.opt.above" },
      { key: "below", labelI18nKey: "q.remote_income.opt.below" },
    ],
    notSure: { mode: "human-review" },
  },
  tourism_duration: {
    id: "tourism_duration",
    i18nKey: "q.tourism_duration",
    kind: "choice",
    sensitive: false,
    options: [
      { key: "short", labelI18nKey: "q.tourism_duration.opt.short" },
      { key: "medium", labelI18nKey: "q.tourism_duration.opt.medium" },
      { key: "extended", labelI18nKey: "q.tourism_duration.opt.extended" },
    ],
    notSure: { mode: "conservative", conservativeValue: "short" },
  },
  review_gate: {
    id: "review_gate",
    i18nKey: "q.review_gate",
    kind: "review-gate",
    sensitive: true,
    whyWeAsk: {
      i18nKey: "why.review_gate",
      regulation: "UU 27/2022 (UU PDP) Art. 67-68",
    },
    options: [
      { key: "none", labelI18nKey: "q.review_gate.opt.none" },
      { key: "flagged", labelI18nKey: "q.review_gate.opt.flagged" },
    ],
  },
};

/** Sub-items shown inside the review-gate checklist (design doc §4 shared
 * review-gate). Finding #5 (adversarial review 2026-07-17): "None of
 * these" is now an EXPLICIT, mutually-exclusive item — the checklist can
 * no longer be silently defaulted to "none" by pressing Continue without
 * choosing anything. The persisted fact is the sorted, comma-joined set
 * of selected item keys (still option keys, never free text); "none" can
 * never co-occur with a real flag. */
export const REVIEW_GATE_ITEMS = [
  "none",
  "criminal_record",
  "health_flag",
  "prior_refusal",
  "overstay_or_blacklist",
  "not_certain",
] as const;
export type ReviewGateItem = (typeof REVIEW_GATE_ITEMS)[number];

export const MOCK_CATALOG: MockVisaCard[] = [
  {
    code: "A1",
    nameI18nKey: "visa.A1.name",
    taglineI18nKey: "visa.A1.tagline",
    allInclusivePriceIDR: 0,
    timelineDays: [0, 0],
    // Finding #4 (adversarial review 2026-07-17): BVK is nationality-only
    // (design doc §6) — the prototype never collects nationality (no new
    // question in PR1), so it cannot honestly claim "Eligible" for every
    // offshore tourist. Downgraded to "conditional" + an explicit
    // nationality-dependent requirement, never a silent guess.
    eligibility: "conditional",
    categories: ["tourism"],
    requiredFacts: { in_indonesia: ["no"] },
    requirementI18nKeys: [
      "req.passport_valid",
      "req.return_ticket",
      "req.nationality_dependent",
    ],
  },
  {
    code: "B1",
    nameI18nKey: "visa.B1.name",
    taglineI18nKey: "visa.B1.tagline",
    allInclusivePriceIDR: 500_000,
    timelineDays: [0, 1],
    eligibility: "conditional",
    categories: ["tourism"],
    requiredFacts: { in_indonesia: ["no"] },
    requirementI18nKeys: [
      "req.passport_valid",
      "req.return_ticket",
      "req.application_form",
      "req.nationality_dependent",
    ],
  },
  {
    code: "C1",
    nameI18nKey: "visa.C1.name",
    taglineI18nKey: "visa.C1.tagline",
    allInclusivePriceIDR: 2_500_000,
    timelineDays: [3, 7],
    eligibility: "eligible",
    categories: ["tourism"],
    requirementI18nKeys: [
      "req.passport_valid",
      "req.passport_photo",
      "req.sponsor_letter",
    ],
  },
  {
    code: "C2",
    nameI18nKey: "visa.C2.name",
    taglineI18nKey: "visa.C2.tagline",
    allInclusivePriceIDR: 3_200_000,
    timelineDays: [3, 7],
    eligibility: "likely",
    categories: ["business"],
    requirementI18nKeys: [
      "req.passport_valid",
      "req.sponsor_letter",
      "req.application_form",
    ],
  },
  {
    code: "D1",
    nameI18nKey: "visa.D1.name",
    taglineI18nKey: "visa.D1.tagline",
    allInclusivePriceIDR: 6_500_000,
    timelineDays: [7, 14],
    eligibility: "likely",
    categories: ["business"],
    requirementI18nKeys: [
      "req.passport_valid",
      "req.sponsor_letter",
      "req.proof_funds",
    ],
  },
  {
    code: "D2",
    nameI18nKey: "visa.D2.name",
    taglineI18nKey: "visa.D2.tagline",
    allInclusivePriceIDR: 6_500_000,
    timelineDays: [7, 14],
    eligibility: "conditional",
    categories: ["family"],
    requirementI18nKeys: [
      "req.passport_valid",
      "req.sponsor_letter",
      "req.marriage_certificate",
    ],
  },
  {
    code: "E23",
    nameI18nKey: "visa.E23.name",
    taglineI18nKey: "visa.E23.tagline",
    allInclusivePriceIDR: 14_500_000,
    timelineDays: [14, 30],
    eligibility: "eligible",
    categories: ["work"],
    requiredFacts: { work_payer: ["yes"] },
    requirementI18nKeys: [
      "req.passport_valid",
      "req.employment_contract",
      "req.sponsor_letter",
    ],
  },
  {
    code: "E28A",
    nameI18nKey: "visa.E28A.name",
    taglineI18nKey: "visa.E28A.tagline",
    allInclusivePriceIDR: 55_000_000,
    timelineDays: [21, 45],
    eligibility: "conditional",
    categories: ["invest"],
    requirementI18nKeys: [
      "req.passport_valid",
      "req.proof_funds",
      "req.application_form",
    ],
  },
  {
    code: "E31",
    nameI18nKey: "visa.E31.name",
    taglineI18nKey: "visa.E31.tagline",
    allInclusivePriceIDR: 12_000_000,
    timelineDays: [14, 30],
    eligibility: "conditional",
    categories: ["family"],
    requirementI18nKeys: [
      "req.passport_valid",
      "req.marriage_certificate",
      "req.sponsor_letter",
    ],
  },
  {
    code: "E33G",
    nameI18nKey: "visa.E33G.name",
    taglineI18nKey: "visa.E33G.tagline",
    allInclusivePriceIDR: 18_000_000,
    timelineDays: [14, 21],
    eligibility: "eligible",
    categories: ["remote"],
    // Finding #14: "mixed" clients is admitted here (not excluded) so the
    // mock engine can honestly rank it "likely-not" instead of hiding it —
    // only "indonesian" (a different lane entirely — employed here) is a
    // hard exclusion. See mock-engine.ts adjustEligibility().
    requiredFacts: { remote_clients: ["foreign", "mixed"] },
    requirementI18nKeys: [
      "req.passport_valid",
      "req.proof_funds",
      "req.application_form",
    ],
  },
  {
    code: "E33",
    nameI18nKey: "visa.E33.name",
    taglineI18nKey: "visa.E33.tagline",
    allInclusivePriceIDR: 35_000_000,
    timelineDays: [21, 45],
    eligibility: "likely",
    categories: ["retirement"],
    requirementI18nKeys: [
      "req.passport_valid",
      "req.proof_funds",
      "req.property_or_lease_proof",
    ],
  },
  {
    code: "BRIDGING",
    nameI18nKey: "visa.BRIDGING.name",
    taglineI18nKey: "visa.BRIDGING.tagline",
    allInclusivePriceIDR: 4_000_000,
    timelineDays: [1, 3],
    eligibility: "conditional",
    categories: [
      "tourism",
      "business",
      "work",
      "remote",
      "family",
      "study",
      "diaspora",
      "other",
    ],
    requiredFacts: { in_indonesia: ["yes"] },
    // Finding #3 (adversarial review 2026-07-17): Bridging Visa is a
    // 60-day onshore transition, active ONLY in the "bridging" lane
    // (3-7 days remaining) — never for someone with 60+ days (planning)
    // or 8-60 days (extend) still deciding. expired/urgent already never
    // reach candidate-listing (forced HUMAN_REVIEW_REQUIRED upstream).
    laneRestriction: ["bridging"],
    requirementI18nKeys: ["req.passport_valid", "req.application_form"],
  },
];

/** Onshore urgency lanes off the Q0 date question (design doc §4 table). */
export type Lane = "expired" | "urgent" | "bridging" | "extend" | "planning";

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Parse a strict `YYYY-MM-DD` string to a UTC-midnight epoch, or `null` if
 * the string isn't that exact shape OR doesn't round-trip to a real
 * calendar date (rejects `2026-02-30`, `2026-13-01`, etc.).
 *
 * Finding #8 (adversarial review 2026-07-17): the previous implementation
 * used `new Date(dateString)`, which (a) silently accepted non-ISO input
 * and produced `NaN` that downstream comparisons coerced into "planning"
 * rather than "unanswered", and (b) for a date-only string is parsed as
 * UTC midnight by spec — fine for arithmetic, but wrong for DISPLAY in a
 * western (negative-offset) timezone, where `.format()` in the viewer's
 * local zone rolls it back a day. This function owns validation +
 * canonical UTC-midnight parsing; `formatIsoDateForDisplay` below always
 * renders with an explicit `timeZone: "UTC"` so display never drifts.
 */
export function parseIsoDateUtc(iso: string): number | null {
  if (!ISO_DATE_RE.test(iso)) return null;
  const [y, m, d] = iso.split("-").map(Number);
  if (m < 1 || m > 12 || d < 1 || d > 31) return null;
  const ms = Date.UTC(y, m - 1, d);
  const roundTrip = new Date(ms);
  if (
    roundTrip.getUTCFullYear() !== y ||
    roundTrip.getUTCMonth() !== m - 1 ||
    roundTrip.getUTCDate() !== d
  ) {
    return null; // e.g. 2026-02-30 normalizes to 2026-03-02 — reject it.
  }
  return ms;
}

/**
 * `today`'s calendar date, taken from its LOCAL wall-clock components
 * (never `getUTC*`), then re-expressed as a UTC-midnight epoch. This is
 * the fix for the midnight-WITA edge (finding #8): reading `today` via
 * `getFullYear/getMonth/getDate` (local) instead of `getUTCFullYear/...`
 * means "which calendar day is it" no longer depends on the process's
 * timezone offset from UTC — 00:30 WITA on 17 July is unambiguously the
 * 17th, everywhere this runs, regardless of the host's configured TZ.
 */
function localCalendarUtcMidnight(d: Date): number {
  return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate());
}

/** Days remaining on the current permit, computed against `today` (default
 * `new Date()`, overridable for deterministic tests). `null` if
 * `permitExpiryIso` isn't a valid `YYYY-MM-DD` calendar date — callers
 * must treat that as "unanswered", never coerce to a lane. Pure. */
export function daysRemaining(
  permitExpiryIso: string,
  today: Date = new Date(),
): number | null {
  const expiryMs = parseIsoDateUtc(permitExpiryIso);
  if (expiryMs === null) return null;
  const msPerDay = 24 * 60 * 60 * 1000;
  return Math.round((expiryMs - localCalendarUtcMidnight(today)) / msPerDay);
}

/** Which onshore lane the user is in, or null if not yet determinable
 * (offshore, date not yet answered, unsure, or invalid). Pure.
 *
 * Finding #2 (adversarial review 2026-07-17): normalized ONCE, here —
 * `in_indonesia === "unsure"` resolves conservatively the same as "yes"
 * (its `notSure.conservativeValue`), so every caller (flow routing, the
 * mock engine, the outcome sheet) sees identical lane behavior without
 * having to remember to resolve facts first.
 */
export function getLane(
  facts: OracleFacts,
  today: Date = new Date(),
): Lane | null {
  if (facts.in_indonesia !== "yes" && facts.in_indonesia !== "unsure")
    return null;
  if (!facts.permit_expiry || facts.permit_expiry === "unsure") return null;
  const remaining = daysRemaining(facts.permit_expiry, today);
  if (remaining === null) return null;
  if (remaining < 0) return "expired";
  if (remaining <= 2) return "urgent";
  if (remaining <= 7) return "bridging";
  if (remaining <= 60) return "extend";
  return "planning";
}

/** Format an already-validated `YYYY-MM-DD` string for display, always in
 * UTC so the calendar date the user typed never shifts for viewers in a
 * negative-offset timezone (finding #8). Falls back to the raw string if
 * it isn't a valid date — display should never throw. */
export function formatIsoDateForDisplay(
  iso: string,
  locale: string,
  options: Intl.DateTimeFormatOptions = { dateStyle: "medium" },
): string {
  const ms = parseIsoDateUtc(iso);
  if (ms === null) return iso;
  return new Intl.DateTimeFormat(locale, {
    ...options,
    timeZone: "UTC",
  }).format(new Date(ms));
}
