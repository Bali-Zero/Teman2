/**
 * GARUDA VOA — decline education copy (owner decision 5, constraint 5b).
 *
 * Zero: "A DECLINE is positively educational, never rejecting." The shape is fixed:
 * mirror what the customer themselves declared -> name what the VOA does not permit
 * -> the alternative -> the consultant's open hand. Never "the VOA is not for you".
 *
 * Two things this file is deliberately built NOT to do:
 *  - It never asks the backend to echo the customer's answers back. The mirror text
 *    below is built from `EligibilitySubmission`, the answers this browser tab already
 *    holds from the wizard it just submitted — never from the API response, which
 *    (by design, migration 261) carries no PII and only coarse `reason_codes`.
 *  - It never names a specific alternative visa product. That mapping is the Visa
 *    Oracle's 38-product question (product.yaml owner decision 5, id 5b) — a second
 *    table here would be a duplicate authority on a client-facing recommendation. This
 *    file only decides WHERE to route: the Oracle's own "Visa Match" wizard, or a
 *    WhatsApp-assisted human, per `routeKind` below. It is a UI mapping over the
 *    contract's closed `DeclineCode` enum (reason-codes.yaml), pending any future
 *    signed accompaniment mapping from the engine (products/garuda-voa/journeys/
 *    declined-with-alternative.feature) — if one lands, this file adopts it rather
 *    than keeps guessing.
 */

import {
  voaCopy,
  type VoaCopyFn,
  type VoaCopyKey,
} from "../../app/visa/voa/voa-copy";

export type DeclineCode =
  | "NATIONALITY_NOT_ELIGIBLE"
  | "PURPOSE_NOT_ELIGIBLE"
  | "GROUP_CASE"
  | "PASSPORT_TYPE"
  | "PASSPORT_VALIDITY"
  | "NOT_SELF_PAY"
  | "FEEDBACK_REQUIRED"
  | "URGENT_CASE"
  | "SPECIAL_PASSPORT"
  | "PRIOR_ISSUE"
  | "ELIGIBILITY_UNCONFIRMED"
  | "FASTLANE_REQUEST"
  | "EXPIRY_UNKNOWN"
  | "EXPIRES_TOO_SOON"
  | "EXTENSION_ALREADY_USED"
  | "ARRIVAL_TOO_SOON"
  | "ARRIVAL_DATE_UNCONFIRMED"
  | "ARRIVAL_TOO_FAR"
  | "EXTENSION_EXCEEDS_MAX_STAY";

export type CaseType = "issuance" | "extension";
export type Purpose = "tourism" | "family" | "transit" | "business-meeting";

/** The customer's own answers, held client-side only — see file header. */
export interface EligibilitySubmission {
  case_type: CaseType;
  nationality: string; // ISO 3166-1 alpha-3
  purpose: Purpose;
  travellers: number;
  self_pay: boolean;
  extension_already_used: boolean;
}

export type RouteKind = "oracle" | "whatsapp";

export interface DeclineEducation {
  code: DeclineCode;
  /** Mirrors what the customer themselves declared. */
  mirror: string;
  /** Names what the VOA does not permit — never "the VOA is not for you". */
  forbids: string;
  /** The alternative path forward. */
  alternative: string;
  /** Where "the alternative" routes to. */
  routeKind: RouteKind;
}

const PURPOSE_KEY: Record<Purpose, VoaCopyKey> = {
  tourism: "decline.purpose.tourism",
  family: "decline.purpose.family",
  transit: "decline.purpose.transit",
  "business-meeting": "decline.purpose.business-meeting",
};

/**
 * WHERE each code routes. This was the only judgement buried in the old
 * nineteen-case switch that was not copy; lifting it out is what lets the
 * three sentences come from the register by key instead of from a literal.
 */
const ROUTE: Record<DeclineCode, RouteKind> = {
  NATIONALITY_NOT_ELIGIBLE: "oracle",
  PURPOSE_NOT_ELIGIBLE: "oracle",
  GROUP_CASE: "whatsapp",
  PASSPORT_TYPE: "whatsapp",
  PASSPORT_VALIDITY: "whatsapp",
  NOT_SELF_PAY: "whatsapp",
  FEEDBACK_REQUIRED: "whatsapp",
  URGENT_CASE: "whatsapp",
  SPECIAL_PASSPORT: "whatsapp",
  PRIOR_ISSUE: "whatsapp",
  ELIGIBILITY_UNCONFIRMED: "whatsapp",
  FASTLANE_REQUEST: "whatsapp",
  EXPIRY_UNKNOWN: "whatsapp",
  EXPIRES_TOO_SOON: "whatsapp",
  EXTENSION_ALREADY_USED: "oracle",
  ARRIVAL_TOO_SOON: "whatsapp",
  ARRIVAL_DATE_UNCONFIRMED: "whatsapp",
  ARRIVAL_TOO_FAR: "whatsapp",
  EXTENSION_EXCEEDS_MAX_STAY: "oracle",
};

/**
 * Precedence when the engine returns more than one code: the first entry of the
 * response array is treated as primary. The engine, not this file, decides that
 * order (see file header) — this is not a second precedence table, only a read.
 */
export function primaryDeclineCode(codes: DeclineCode[]): DeclineCode | null {
  return codes[0] ?? null;
}

/**
 * Every sentence this file renders, as a type. If a reason code is added to
 * `DeclineCode` and its three keys are not added to `voa-copy.ts`, this alias
 * stops being assignable to `VoaCopyKey` and `_ALL_SENTENCES_PRESENT` below
 * fails the BUILD — the same "a new code without copy is a compile error"
 * property the old literal switch had, kept while the copy moved out.
 */
type DeclineSentenceKey =
  `decline.${DeclineCode}.${"mirror" | "forbids" | "alternative"}`;

const _ALL_SENTENCES_PRESENT: DeclineSentenceKey extends VoaCopyKey
  ? true
  : never = true;
void _ALL_SENTENCES_PRESENT;

/**
 * `t` defaults to English so the existing two-argument callers — and the tests
 * that assert the English sentences — keep meaning exactly what they meant.
 * The verdict screen passes its own `t`, which is how a visitor who asked for
 * Bahasa reads the DECLINE education in Bahasa.
 */
export function buildDeclineEducation(
  code: DeclineCode,
  answers: EligibilitySubmission,
  t: VoaCopyFn = voaCopy("en"),
): DeclineEducation {
  const params = {
    nationality: answers.nationality,
    purpose: t(PURPOSE_KEY[answers.purpose]),
    travellers: answers.travellers,
    case: t(
      answers.case_type === "extension"
        ? "decline.case.extension"
        : "decline.case.issuance",
    ),
  };

  return {
    code,
    mirror: t(`decline.${code}.mirror`, params),
    forbids: t(`decline.${code}.forbids`, params),
    alternative: t(`decline.${code}.alternative`, params),
    routeKind: ROUTE[code],
  };
}
