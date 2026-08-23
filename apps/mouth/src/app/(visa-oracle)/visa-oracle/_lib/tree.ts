/**
 * Visa Oracle v2 — language-neutral interview registry.
 *
 * Pure, typed, deterministic. No fetch, no side effects. Every answer is an
 * option KEY (language-agnostic by construction — spec §hard-constraint 3),
 * never localized/free text. Mirrors design doc §4 "The interview" and
 * spec item 26.
 *
 * The question registry collects exact engine facts or explicitly labelled
 * human context. It does not evaluate, rank, add, or remove visa paths. No
 * price, timeline, document, or visa-candidate catalog belongs in this file.
 */

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

export type QuestionDecisionMapping =
  | {
      kind: "FACT";
      factPaths: readonly string[];
      /** UI values which intentionally serialize as UNKNOWN, never KNOWN. */
      unknownValues?: readonly string[];
    }
  | { kind: "HUMAN_CONTEXT" }
  | { kind: "REVIEW_ONLY"; factPaths: readonly string[] };

export type QuestionGroup =
  "location" | "identity" | "intent" | "details" | "review";

export interface OracleQuestion {
  id: string;
  i18nKey: string;
  kind:
    | "branch"
    | "date"
    | "number"
    | "country-codes"
    | "status-code"
    | "tiles"
    | "choice"
    | "review-gate";
  options: OracleOption[];
  group: QuestionGroup;
  /** Explicit decision boundary. HUMAN_CONTEXT values may be shown to a
   * person but must never be mapped into an engine FactPath. */
  decisionMapping: QuestionDecisionMapping;
  /** Input-sanity bounds only. They are never legal thresholds and are not
   * used to select, rank, or remove a visa path. */
  numberInput?: {
    min: number;
    max: number;
    step: number;
    labelI18nKey: string;
    unitI18nKey: string;
  };
  dateInput?: {
    labelI18nKey: string;
    maxToday?: boolean;
  };
  codeInput?: {
    labelI18nKey: string;
    multiple: boolean;
    maxLength?: number;
    maxSelections?: number;
  };
  /** Present only on sensitive questions (design doc §3 "why we ask" — the
   * gov-demo armor). Optional by construction: not every question is
   * sensitive enough to warrant a disclosure glyph. */
  whyWeAsk?: { i18nKey: string };
  sensitive?: boolean;
  notSure?: NotSureBehavior;
}

/** Answers, keyed by question id. Values are option keys OR, for the one
 * `kind: "date"` question, an ISO-8601 date string (still not free text —
 * a date picker's value, not typed prose). The reserved value `"unsure"`
 * means the NotSure affordance was used on that question. */
export type OracleFacts = Record<string, string>;

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

/** Every category has a finite interview branch. This set describes UI
 * coverage only; it never means a visa path is legally supported. */
export const BEHAVIORAL_CATEGORIES = new Set<CategoryKey>(CATEGORY_KEYS);

export const QUESTIONS: Record<string, OracleQuestion> = {
  in_indonesia: {
    id: "in_indonesia",
    i18nKey: "q.in_indonesia",
    kind: "branch",
    group: "location",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["immigration.currently_in_indonesia"],
    },
    sensitive: false,
    options: [
      { key: "yes", labelI18nKey: "q.in_indonesia.opt.yes" },
      { key: "no", labelI18nKey: "q.in_indonesia.opt.no" },
    ],
    whyWeAsk: { i18nKey: "why.in_indonesia" },
    notSure: { mode: "human-review" },
  },
  permit_expiry: {
    id: "permit_expiry",
    i18nKey: "q.permit_expiry",
    kind: "date",
    group: "location",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["immigration.current_status_expiry"],
    },
    sensitive: false,
    options: [],
    dateInput: { labelI18nKey: "q.permit_expiry.label" },
    whyWeAsk: { i18nKey: "why.permit_expiry" },
    notSure: { mode: "human-review" },
  },
  current_status_code: {
    id: "current_status_code",
    i18nKey: "q.current_status_code",
    kind: "choice",
    group: "location",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["immigration.current_status_code"],
    },
    sensitive: true,
    options: [
      { key: "A1", labelI18nKey: "q.current_status_code.opt.A1" },
      { key: "C1", labelI18nKey: "q.current_status_code.opt.C1" },
      { key: "C2", labelI18nKey: "q.current_status_code.opt.C2" },
      { key: "C6", labelI18nKey: "q.current_status_code.opt.C6" },
      {
        key: "ITK_FROM_BVK",
        labelI18nKey: "q.current_status_code.opt.ITK_FROM_BVK",
      },
      {
        key: "ITK_FROM_VISIT_C",
        labelI18nKey: "q.current_status_code.opt.ITK_FROM_VISIT_C",
      },
      {
        key: "ITK_FROM_VISIT_D",
        labelI18nKey: "q.current_status_code.opt.ITK_FROM_VISIT_D",
      },
      {
        key: "ITK_PERALIHAN",
        labelI18nKey: "q.current_status_code.opt.ITK_PERALIHAN",
      },
      { key: "other", labelI18nKey: "q.current_status_code.opt.other" },
    ],
    whyWeAsk: { i18nKey: "why.current_status_code" },
    notSure: { mode: "human-review" },
  },
  overstay_days: {
    id: "overstay_days",
    i18nKey: "q.overstay_days",
    kind: "number",
    group: "location",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["immigration.overstay_days"],
    },
    sensitive: true,
    options: [],
    numberInput: {
      min: 0,
      max: 36_500,
      step: 1,
      labelI18nKey: "q.overstay_days.label",
      unitI18nKey: "q.stay_days.unit",
    },
    whyWeAsk: { i18nKey: "why.overstay_days" },
    notSure: { mode: "human-review" },
  },
  wants_onshore_conversion: {
    id: "wants_onshore_conversion",
    i18nKey: "q.wants_onshore_conversion",
    kind: "branch",
    group: "location",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["process.wants_onshore_conversion"],
    },
    sensitive: false,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.wants_onshore_conversion" },
    notSure: { mode: "human-review" },
  },
  application_channel: {
    id: "application_channel",
    i18nKey: "q.application_channel",
    kind: "choice",
    group: "location",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["process.application_channel"],
    },
    sensitive: false,
    options: [
      { key: "OFFSHORE", labelI18nKey: "q.application_channel.opt.OFFSHORE" },
      {
        key: "ONSHORE_CONVERSION",
        labelI18nKey: "q.application_channel.opt.ONSHORE_CONVERSION",
      },
      {
        key: "STATUS_BRIDGING",
        labelI18nKey: "q.application_channel.opt.STATUS_BRIDGING",
      },
    ],
    whyWeAsk: { i18nKey: "why.application_channel" },
    notSure: { mode: "human-review" },
  },
  nationalities: {
    id: "nationalities",
    i18nKey: "q.nationalities",
    kind: "country-codes",
    group: "identity",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["person.nationalities"],
    },
    sensitive: true,
    options: [],
    codeInput: {
      labelI18nKey: "q.nationalities.label",
      multiple: true,
      maxSelections: 4,
    },
    whyWeAsk: { i18nKey: "why.nationalities" },
    notSure: { mode: "human-review" },
  },
  birth_date: {
    id: "birth_date",
    i18nKey: "q.birth_date",
    kind: "date",
    group: "identity",
    decisionMapping: { kind: "FACT", factPaths: ["person.birth_date"] },
    sensitive: true,
    options: [],
    dateInput: { labelI18nKey: "q.birth_date.label", maxToday: true },
    whyWeAsk: { i18nKey: "why.birth_date" },
    notSure: { mode: "human-review" },
  },
  category: {
    id: "category",
    i18nKey: "q.category",
    kind: "tiles",
    group: "intent",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["intent.purposes"],
      unknownValues: ["diaspora"],
    },
    sensitive: false,
    whyWeAsk: { i18nKey: "why.category" },
    options: CATEGORY_KEYS.map((key) => ({
      key,
      labelI18nKey: `q.category.opt.${key}`,
    })),
    notSure: { mode: "human-review" },
  },
  trip_scope: {
    id: "trip_scope",
    i18nKey: "q.trip_scope",
    kind: "branch",
    group: "intent",
    decisionMapping: { kind: "HUMAN_CONTEXT" },
    sensitive: false,
    options: [
      { key: "single", labelI18nKey: "q.trip_scope.opt.single" },
      { key: "multiple", labelI18nKey: "q.trip_scope.opt.multiple" },
    ],
    whyWeAsk: { i18nKey: "why.trip_scope" },
    notSure: { mode: "human-review" },
  },
  entry_pattern: {
    id: "entry_pattern",
    i18nKey: "q.entry_pattern",
    kind: "choice",
    group: "details",
    decisionMapping: { kind: "FACT", factPaths: ["intent.entry_pattern"] },
    sensitive: false,
    options: [
      { key: "SINGLE", labelI18nKey: "q.entry_pattern.opt.SINGLE" },
      { key: "MULTIPLE", labelI18nKey: "q.entry_pattern.opt.MULTIPLE" },
    ],
    whyWeAsk: { i18nKey: "why.entry_pattern" },
    notSure: { mode: "human-review" },
  },
  /** WHO sponsors the stay, as a category. This is distinct from the
   * family/work/study "is the sponsor confirmed?" booleans elsewhere in
   * this file, and it is not the sponsor's identity either — just the
   * category. Maps to the single optional `sponsor.type`
   * FactPath (spec staged-rollout field). No rule in the currently
   * active pack reads it yet; the question exists to collect the fact
   * ahead of the rules that will (design doc §4, category-conditional
   * questions). Asked only where the category makes the sponsor
   * discriminating — see `FIXED_CATEGORY_QUESTIONS`/`getCategoryQuestionIds`
   * in flow.ts for exactly which categories include it. */
  sponsor_category: {
    id: "sponsor_category",
    i18nKey: "q.sponsor_category",
    kind: "choice",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["sponsor.type"],
    },
    sensitive: false,
    options: [
      { key: "NONE", labelI18nKey: "q.sponsor_category.opt.NONE" },
      {
        key: "INDIVIDUAL",
        labelI18nKey: "q.sponsor_category.opt.INDIVIDUAL",
      },
      { key: "EMPLOYER", labelI18nKey: "q.sponsor_category.opt.EMPLOYER" },
      {
        key: "EDUCATION",
        labelI18nKey: "q.sponsor_category.opt.EDUCATION",
      },
      {
        key: "INVESTMENT",
        labelI18nKey: "q.sponsor_category.opt.INVESTMENT",
      },
      {
        key: "GOVERNMENT",
        labelI18nKey: "q.sponsor_category.opt.GOVERNMENT",
      },
    ],
    whyWeAsk: { i18nKey: "why.sponsor_category" },
    notSure: { mode: "human-review" },
  },
  business_activity: {
    id: "business_activity",
    i18nKey: "q.business_activity",
    kind: "choice",
    group: "details",
    decisionMapping: { kind: "HUMAN_CONTEXT" },
    sensitive: false,
    options: [
      { key: "meetings", labelI18nKey: "q.business_activity.opt.meetings" },
      {
        key: "negotiation",
        labelI18nKey: "q.business_activity.opt.negotiation",
      },
      {
        key: "conference",
        labelI18nKey: "q.business_activity.opt.conference",
      },
      { key: "training", labelI18nKey: "q.business_activity.opt.training" },
      { key: "other", labelI18nKey: "q.business_activity.opt.other" },
    ],
    whyWeAsk: { i18nKey: "why.business_activity" },
    notSure: { mode: "human-review" },
  },
  work_payer: {
    id: "work_payer",
    i18nKey: "q.work_payer",
    kind: "branch",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["work.employer_is_indonesian_entity"],
    },
    sensitive: true,
    whyWeAsk: { i18nKey: "why.work_payer" },
    options: [
      { key: "yes", labelI18nKey: "q.work_payer.opt.yes" },
      { key: "no", labelI18nKey: "q.work_payer.opt.no" },
    ],
    notSure: { mode: "human-review" },
  },
  work_indonesia_compensation: {
    id: "work_indonesia_compensation",
    i18nKey: "q.work_indonesia_compensation",
    kind: "branch",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["work.indonesia_source_compensation"],
    },
    sensitive: true,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.work_indonesia_compensation" },
    notSure: { mode: "human-review" },
  },
  work_sponsor_confirmed: {
    id: "work_sponsor_confirmed",
    i18nKey: "q.work_sponsor_confirmed",
    kind: "branch",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["work.indonesian_work_sponsor_confirmed"],
    },
    sensitive: false,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.work_sponsor_confirmed" },
    notSure: { mode: "human-review" },
  },
  work_role: {
    id: "work_role",
    i18nKey: "q.work_role",
    kind: "choice",
    group: "details",
    decisionMapping: { kind: "HUMAN_CONTEXT" },
    sensitive: false,
    options: [
      { key: "executive", labelI18nKey: "q.work_role.opt.executive" },
      { key: "manager", labelI18nKey: "q.work_role.opt.manager" },
      { key: "specialist", labelI18nKey: "q.work_role.opt.specialist" },
      { key: "performer", labelI18nKey: "q.work_role.opt.performer" },
      { key: "other", labelI18nKey: "q.work_role.opt.other" },
    ],
    whyWeAsk: { i18nKey: "why.work_role" },
    notSure: { mode: "human-review" },
  },
  remote_clients: {
    id: "remote_clients",
    i18nKey: "q.remote_clients",
    kind: "choice",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["work.serves_indonesian_clients"],
    },
    sensitive: true,
    whyWeAsk: { i18nKey: "why.remote_clients" },
    options: [
      { key: "foreign", labelI18nKey: "q.remote_clients.opt.foreign" },
      { key: "indonesian", labelI18nKey: "q.remote_clients.opt.indonesian" },
      { key: "mixed", labelI18nKey: "q.remote_clients.opt.mixed" },
    ],
    notSure: { mode: "human-review" },
  },
  remote_compensation: {
    id: "remote_compensation",
    i18nKey: "q.remote_compensation",
    kind: "branch",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["work.indonesia_source_compensation"],
    },
    sensitive: true,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.remote_compensation" },
    notSure: { mode: "human-review" },
  },
  remote_employer_country: {
    id: "remote_employer_country",
    i18nKey: "q.remote_employer_country",
    kind: "country-codes",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["work.employer_country_code"],
    },
    sensitive: true,
    options: [],
    codeInput: {
      labelI18nKey: "q.remote_employer_country.label",
      multiple: false,
    },
    whyWeAsk: { i18nKey: "why.remote_employer_country" },
    notSure: { mode: "human-review" },
  },
  remote_pt_pma: {
    id: "remote_pt_pma",
    i18nKey: "q.remote_pt_pma",
    kind: "branch",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["investment.pt_pma_committed"],
    },
    sensitive: false,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.remote_pt_pma" },
    notSure: { mode: "human-review" },
  },
  investment_vehicle: {
    id: "investment_vehicle",
    i18nKey: "q.investment_vehicle",
    kind: "choice",
    group: "details",
    decisionMapping: { kind: "HUMAN_CONTEXT" },
    sensitive: false,
    options: [
      { key: "pt_pma", labelI18nKey: "q.investment_vehicle.opt.pt_pma" },
      { key: "property", labelI18nKey: "q.investment_vehicle.opt.property" },
      {
        key: "bank_deposit",
        labelI18nKey: "q.investment_vehicle.opt.bank_deposit",
      },
      { key: "merit", labelI18nKey: "q.investment_vehicle.opt.merit" },
      { key: "family", labelI18nKey: "q.investment_vehicle.opt.family" },
      {
        key: "undecided",
        labelI18nKey: "q.investment_vehicle.opt.undecided",
      },
    ],
    whyWeAsk: { i18nKey: "why.investment_vehicle" },
    notSure: { mode: "human-review" },
  },
  investment_pt_pma: {
    id: "investment_pt_pma",
    i18nKey: "q.investment_pt_pma",
    kind: "branch",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["investment.pt_pma_committed"],
    },
    sensitive: false,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.investment_pt_pma" },
    notSure: { mode: "human-review" },
  },
  investment_capital_idr: {
    id: "investment_capital_idr",
    i18nKey: "q.investment_capital_idr",
    kind: "number",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["investment.investment_capital_idr"],
    },
    sensitive: true,
    options: [],
    numberInput: {
      min: 0,
      max: Number.MAX_SAFE_INTEGER,
      step: 1,
      labelI18nKey: "q.investment_capital_idr.label",
      unitI18nKey: "q.unit.idr",
    },
    whyWeAsk: { i18nKey: "why.investment_capital_idr" },
    notSure: { mode: "human-review" },
  },
  investment_paid_up_capital_idr: {
    id: "investment_paid_up_capital_idr",
    i18nKey: "q.investment_paid_up_capital_idr",
    kind: "number",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["investment.paid_up_capital_idr"],
    },
    sensitive: true,
    options: [],
    numberInput: {
      min: 0,
      max: Number.MAX_SAFE_INTEGER,
      step: 1,
      labelI18nKey: "q.investment_paid_up_capital_idr.label",
      unitI18nKey: "q.unit.idr",
    },
    whyWeAsk: { i18nKey: "why.investment_paid_up_capital_idr" },
    notSure: { mode: "human-review" },
  },
  investment_role: {
    id: "investment_role",
    i18nKey: "q.investment_role",
    kind: "choice",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["investment.proposed_role"],
    },
    sensitive: false,
    options: [
      {
        key: "SHAREHOLDER_DIRECTOR",
        labelI18nKey: "q.investment_role.opt.SHAREHOLDER_DIRECTOR",
      },
      {
        key: "SHAREHOLDER_COMMISSIONER",
        labelI18nKey: "q.investment_role.opt.SHAREHOLDER_COMMISSIONER",
      },
      { key: "EMPLOYEE", labelI18nKey: "q.investment_role.opt.EMPLOYEE" },
      {
        key: "NO_OPERATIONAL_ROLE",
        labelI18nKey: "q.investment_role.opt.NO_OPERATIONAL_ROLE",
      },
      { key: "OTHER", labelI18nKey: "q.investment_role.opt.OTHER" },
    ],
    whyWeAsk: { i18nKey: "why.investment_role" },
    notSure: { mode: "human-review" },
  },
  family_relation: {
    id: "family_relation",
    i18nKey: "q.family_relation",
    kind: "choice",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["family.relation_to_sponsor"],
    },
    sensitive: true,
    options: [
      { key: "SPOUSE", labelI18nKey: "q.family_relation.opt.SPOUSE" },
      { key: "CHILD", labelI18nKey: "q.family_relation.opt.CHILD" },
      { key: "PARENT", labelI18nKey: "q.family_relation.opt.PARENT" },
      { key: "SIBLING", labelI18nKey: "q.family_relation.opt.SIBLING" },
      { key: "DEPENDENT", labelI18nKey: "q.family_relation.opt.DEPENDENT" },
      { key: "OTHER", labelI18nKey: "q.family_relation.opt.OTHER" },
    ],
    whyWeAsk: { i18nKey: "why.family_relation" },
    notSure: { mode: "human-review" },
  },
  marital_status: {
    id: "marital_status",
    i18nKey: "q.marital_status",
    kind: "choice",
    group: "details",
    decisionMapping: { kind: "FACT", factPaths: ["person.marital_status"] },
    sensitive: true,
    options: [
      { key: "SINGLE", labelI18nKey: "q.marital_status.opt.SINGLE" },
      { key: "MARRIED", labelI18nKey: "q.marital_status.opt.MARRIED" },
      { key: "DIVORCED", labelI18nKey: "q.marital_status.opt.DIVORCED" },
      { key: "WIDOWED", labelI18nKey: "q.marital_status.opt.WIDOWED" },
      { key: "OTHER", labelI18nKey: "q.marital_status.opt.OTHER" },
    ],
    whyWeAsk: { i18nKey: "why.marital_status" },
    notSure: { mode: "human-review" },
  },
  family_sponsor_nationalities: {
    id: "family_sponsor_nationalities",
    i18nKey: "q.family_sponsor_nationalities",
    kind: "country-codes",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["family.sponsor_nationalities"],
    },
    sensitive: true,
    options: [],
    codeInput: {
      labelI18nKey: "q.family_sponsor_nationalities.label",
      multiple: true,
      maxSelections: 4,
    },
    whyWeAsk: { i18nKey: "why.family_sponsor_nationalities" },
    notSure: { mode: "human-review" },
  },
  family_sponsor_status_code: {
    id: "family_sponsor_status_code",
    i18nKey: "q.family_sponsor_status_code",
    kind: "status-code",
    group: "details",
    decisionMapping: { kind: "HUMAN_CONTEXT" },
    sensitive: true,
    options: [],
    codeInput: {
      labelI18nKey: "q.family_sponsor_status_code.label",
      multiple: false,
      maxLength: 64,
    },
    whyWeAsk: { i18nKey: "why.family_sponsor_status_code" },
    notSure: { mode: "human-review" },
  },
  family_marriage_registered: {
    id: "family_marriage_registered",
    i18nKey: "q.family_marriage_registered",
    kind: "choice",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["family.marriage_registered"],
      unknownValues: ["not_applicable"],
    },
    sensitive: true,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
      {
        key: "not_applicable",
        labelI18nKey: "q.boolean.not_applicable",
      },
    ],
    whyWeAsk: { i18nKey: "why.family_marriage_registered" },
    notSure: { mode: "human-review" },
  },
  family_sponsor_confirmed: {
    id: "family_sponsor_confirmed",
    i18nKey: "q.family_sponsor_confirmed",
    kind: "branch",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["family.sponsor_confirmed"],
    },
    sensitive: false,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.family_sponsor_confirmed" },
    notSure: { mode: "human-review" },
  },
  // Stepchild route (2026-08-23 owner ruling — the E31D stepchild-of-a-
  // mixed-marriage product exists in the catalog, but every one of its
  // rules could previously only read `intent.purposes ∩ FAMILY`; the
  // contract had no way to say "stepchild" at all. Both evidence facts
  // follow `family_marriage_registered`'s branch idiom exactly — two plain
  // yes/no confirmations, sensitive (documentary evidence of a personal
  // relationship), NotSure → human-review same as every sibling in this
  // group. See `research/visa/2026-08-15-gold-family-refuter.md`.
  family_stepchild_marriage_certificate_confirmed: {
    id: "family_stepchild_marriage_certificate_confirmed",
    i18nKey: "q.family_stepchild_marriage_certificate_confirmed",
    kind: "branch",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["family.stepchild_marriage_certificate_confirmed"],
    },
    sensitive: true,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: {
      i18nKey: "why.family_stepchild_marriage_certificate_confirmed",
    },
    notSure: { mode: "human-review" },
  },
  family_stepchild_birth_certificate_confirmed: {
    id: "family_stepchild_birth_certificate_confirmed",
    i18nKey: "q.family_stepchild_birth_certificate_confirmed",
    kind: "branch",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["family.stepchild_birth_certificate_confirmed"],
    },
    sensitive: true,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.family_stepchild_birth_certificate_confirmed" },
    notSure: { mode: "human-review" },
  },
  // Sponsor permit basis (2026-08-23 owner ruling — Permenkumham 11/2024
  // Pasal 33 ayat (7) blocks family-reunification chaining for four
  // specific ayat (2) huruf h categories; `family.sponsor_status_code` is
  // free-form STRING and can only express validity, never purpose. Options
  // mirror the closed `SponsorPermitBasis` enum 1:1 — 13 values grounded in
  // Pasal 33 ayat (2) huruf a-l, verbatim quote in `why.family_sponsor_permit_basis`.
  family_sponsor_permit_basis: {
    id: "family_sponsor_permit_basis",
    i18nKey: "q.family_sponsor_permit_basis",
    kind: "choice",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["family.sponsor_permit_basis"],
    },
    sensitive: true,
    options: [
      {
        key: "EXPERT",
        labelI18nKey: "q.family_sponsor_permit_basis.opt.EXPERT",
      },
      {
        key: "WORKER",
        labelI18nKey: "q.family_sponsor_permit_basis.opt.WORKER",
      },
      {
        key: "MARITIME_CREW",
        labelI18nKey: "q.family_sponsor_permit_basis.opt.MARITIME_CREW",
      },
      {
        key: "CLERGY",
        labelI18nKey: "q.family_sponsor_permit_basis.opt.CLERGY",
      },
      {
        key: "FOREIGN_INVESTMENT",
        labelI18nKey: "q.family_sponsor_permit_basis.opt.FOREIGN_INVESTMENT",
      },
      {
        key: "SCIENTIFIC_RESEARCH",
        labelI18nKey: "q.family_sponsor_permit_basis.opt.SCIENTIFIC_RESEARCH",
      },
      {
        key: "EDUCATION",
        labelI18nKey: "q.family_sponsor_permit_basis.opt.EDUCATION",
      },
      {
        key: "FAMILY_REUNIFICATION",
        labelI18nKey: "q.family_sponsor_permit_basis.opt.FAMILY_REUNIFICATION",
      },
      {
        key: "REPATRIATION",
        labelI18nKey: "q.family_sponsor_permit_basis.opt.REPATRIATION",
      },
      {
        key: "SECOND_HOME",
        labelI18nKey: "q.family_sponsor_permit_basis.opt.SECOND_HOME",
      },
      {
        key: "MEDICAL_TREATMENT",
        labelI18nKey: "q.family_sponsor_permit_basis.opt.MEDICAL_TREATMENT",
      },
      {
        key: "WORKING_HOLIDAY",
        labelI18nKey: "q.family_sponsor_permit_basis.opt.WORKING_HOLIDAY",
      },
      { key: "OTHER", labelI18nKey: "q.family_sponsor_permit_basis.opt.OTHER" },
    ],
    whyWeAsk: { i18nKey: "why.family_sponsor_permit_basis" },
    notSure: { mode: "human-review" },
  },
  retirement_basis: {
    id: "retirement_basis",
    i18nKey: "q.retirement_basis",
    kind: "choice",
    group: "details",
    decisionMapping: { kind: "HUMAN_CONTEXT" },
    sensitive: false,
    options: [
      {
        key: "bank_deposit",
        labelI18nKey: "q.retirement_basis.opt.bank_deposit",
      },
      { key: "property", labelI18nKey: "q.retirement_basis.opt.property" },
      {
        key: "passive_income",
        labelI18nKey: "q.retirement_basis.opt.passive_income",
      },
      {
        key: "family_sponsor",
        labelI18nKey: "q.retirement_basis.opt.family_sponsor",
      },
      {
        key: "undecided",
        labelI18nKey: "q.retirement_basis.opt.undecided",
      },
    ],
    whyWeAsk: { i18nKey: "why.retirement_basis" },
    notSure: { mode: "human-review" },
  },
  secondhome_deposit_usd: {
    id: "secondhome_deposit_usd",
    i18nKey: "q.secondhome_deposit_usd",
    kind: "number",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["secondhome.bank_deposit_usd"],
    },
    sensitive: true,
    options: [],
    numberInput: {
      min: 0,
      max: Number.MAX_SAFE_INTEGER,
      step: 1,
      labelI18nKey: "q.secondhome_deposit_usd.label",
      unitI18nKey: "q.unit.usd",
    },
    whyWeAsk: { i18nKey: "why.secondhome_deposit_usd" },
    notSure: { mode: "human-review" },
  },
  secondhome_state_bank: {
    id: "secondhome_state_bank",
    i18nKey: "q.secondhome_state_bank",
    kind: "branch",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["secondhome.bank_deposit_at_state_bank"],
    },
    sensitive: true,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.secondhome_state_bank" },
    notSure: { mode: "human-review" },
  },
  secondhome_own_name: {
    id: "secondhome_own_name",
    i18nKey: "q.secondhome_own_name",
    kind: "branch",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["secondhome.bank_deposit_in_own_name"],
    },
    sensitive: true,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.secondhome_own_name" },
    notSure: { mode: "human-review" },
  },
  secondhome_property_value_usd: {
    id: "secondhome_property_value_usd",
    i18nKey: "q.secondhome_property_value_usd",
    kind: "number",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["secondhome.qualifying_property_value_usd"],
    },
    sensitive: true,
    options: [],
    numberInput: {
      min: 0,
      max: Number.MAX_SAFE_INTEGER,
      step: 1,
      labelI18nKey: "q.secondhome_property_value_usd.label",
      unitI18nKey: "q.unit.usd",
    },
    whyWeAsk: { i18nKey: "why.secondhome_property_value_usd" },
    notSure: { mode: "human-review" },
  },
  secondhome_passive_income_usd: {
    id: "secondhome_passive_income_usd",
    i18nKey: "q.secondhome_passive_income_usd",
    kind: "number",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["secondhome.passive_monthly_income_usd"],
    },
    sensitive: true,
    options: [],
    numberInput: {
      min: 0,
      max: Number.MAX_SAFE_INTEGER,
      step: 1,
      labelI18nKey: "q.secondhome_passive_income_usd.label",
      unitI18nKey: "q.unit.usd_month",
    },
    whyWeAsk: { i18nKey: "why.secondhome_passive_income_usd" },
    notSure: { mode: "human-review" },
  },
  study_level: {
    id: "study_level",
    i18nKey: "q.study_level",
    kind: "choice",
    group: "details",
    decisionMapping: { kind: "FACT", factPaths: ["study.level"] },
    sensitive: false,
    options: [
      { key: "PRIMARY", labelI18nKey: "q.study_level.opt.PRIMARY" },
      { key: "SECONDARY", labelI18nKey: "q.study_level.opt.SECONDARY" },
      { key: "VOCATIONAL", labelI18nKey: "q.study_level.opt.VOCATIONAL" },
      {
        key: "UNDERGRADUATE",
        labelI18nKey: "q.study_level.opt.UNDERGRADUATE",
      },
      {
        key: "POSTGRADUATE",
        labelI18nKey: "q.study_level.opt.POSTGRADUATE",
      },
      { key: "RESEARCH", labelI18nKey: "q.study_level.opt.RESEARCH" },
      { key: "OTHER", labelI18nKey: "q.study_level.opt.OTHER" },
    ],
    whyWeAsk: { i18nKey: "why.study_level" },
    notSure: { mode: "human-review" },
  },
  study_admission_confirmed: {
    id: "study_admission_confirmed",
    i18nKey: "q.study_admission_confirmed",
    kind: "branch",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["study.admission_confirmed"],
    },
    sensitive: false,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.study_admission_confirmed" },
    notSure: { mode: "human-review" },
  },
  study_sponsor_confirmed: {
    id: "study_sponsor_confirmed",
    i18nKey: "q.study_sponsor_confirmed",
    kind: "branch",
    group: "details",
    decisionMapping: {
      kind: "FACT",
      factPaths: ["study.sponsor_confirmed"],
    },
    sensitive: false,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.study_sponsor_confirmed" },
    notSure: { mode: "human-review" },
  },
  diaspora_connection: {
    id: "diaspora_connection",
    i18nKey: "q.diaspora_connection",
    kind: "choice",
    group: "details",
    decisionMapping: { kind: "HUMAN_CONTEXT" },
    sensitive: true,
    options: [
      {
        key: "former_wni",
        labelI18nKey: "q.diaspora_connection.opt.former_wni",
      },
      {
        key: "descendant",
        labelI18nKey: "q.diaspora_connection.opt.descendant",
      },
      { key: "dual", labelI18nKey: "q.diaspora_connection.opt.dual" },
      { key: "family", labelI18nKey: "q.diaspora_connection.opt.family" },
      { key: "other", labelI18nKey: "q.diaspora_connection.opt.other" },
    ],
    whyWeAsk: { i18nKey: "why.diaspora_connection" },
    notSure: { mode: "human-review" },
  },
  diaspora_documents: {
    id: "diaspora_documents",
    i18nKey: "q.diaspora_documents",
    kind: "branch",
    group: "details",
    decisionMapping: { kind: "HUMAN_CONTEXT" },
    sensitive: true,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.diaspora_documents" },
    notSure: { mode: "human-review" },
  },
  other_purpose: {
    id: "other_purpose",
    i18nKey: "q.other_purpose",
    kind: "choice",
    group: "details",
    decisionMapping: { kind: "HUMAN_CONTEXT" },
    sensitive: false,
    options: [
      { key: "transit", labelI18nKey: "q.other_purpose.opt.transit" },
      { key: "medical", labelI18nKey: "q.other_purpose.opt.medical" },
      { key: "volunteer", labelI18nKey: "q.other_purpose.opt.volunteer" },
      { key: "religious", labelI18nKey: "q.other_purpose.opt.religious" },
      { key: "arts_sport", labelI18nKey: "q.other_purpose.opt.arts_sport" },
      { key: "journalism", labelI18nKey: "q.other_purpose.opt.journalism" },
      { key: "crew", labelI18nKey: "q.other_purpose.opt.crew" },
      { key: "other", labelI18nKey: "q.other_purpose.opt.other" },
    ],
    whyWeAsk: { i18nKey: "why.other_purpose" },
    notSure: { mode: "human-review" },
  },
  other_paid_activity: {
    id: "other_paid_activity",
    i18nKey: "q.other_paid_activity",
    kind: "branch",
    group: "details",
    decisionMapping: { kind: "HUMAN_CONTEXT" },
    sensitive: true,
    options: [
      { key: "yes", labelI18nKey: "q.boolean.yes" },
      { key: "no", labelI18nKey: "q.boolean.no" },
    ],
    whyWeAsk: { i18nKey: "why.other_paid_activity" },
    notSure: { mode: "human-review" },
  },
  stay_days: {
    id: "stay_days",
    i18nKey: "q.stay_days",
    kind: "number",
    group: "details",
    decisionMapping: { kind: "FACT", factPaths: ["intent.stay_days"] },
    sensitive: false,
    options: [],
    numberInput: {
      min: 1,
      max: 36_500,
      step: 1,
      labelI18nKey: "q.stay_days.label",
      unitI18nKey: "q.stay_days.unit",
    },
    whyWeAsk: { i18nKey: "why.stay_days" },
    notSure: { mode: "human-review" },
  },
  review_gate: {
    id: "review_gate",
    i18nKey: "q.review_gate",
    kind: "review-gate",
    group: "review",
    decisionMapping: {
      kind: "REVIEW_ONLY",
      factPaths: ["immigration.violation_history"],
    },
    sensitive: true,
    whyWeAsk: { i18nKey: "why.review_gate" },
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
  "overstay",
  "blacklist",
  "immigration_investigation",
  "pep_or_sanctions",
  "source_of_funds_unclear",
  "diplomatic_passport",
  "ambiguous_sponsor",
  "activity_boundary",
  "not_certain",
] as const;
export type ReviewGateItem = (typeof REVIEW_GATE_ITEMS)[number];

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
 * UNKNOWN location never becomes a KNOWN onshore fact. A visual lane is
 * available only after an explicit onshore answer and an exact expiry date.
 */
export function getLane(
  facts: OracleFacts,
  today: Date = new Date(),
): Lane | null {
  if (facts.in_indonesia !== "yes") return null;
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
