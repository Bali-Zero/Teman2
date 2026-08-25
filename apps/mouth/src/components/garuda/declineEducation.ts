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

const PURPOSE_LABEL: Record<Purpose, string> = {
  tourism: "tourism",
  family: "visiting family",
  transit: "transit",
  "business-meeting": "a business meeting",
};

/**
 * Precedence when the engine returns more than one code: the first entry of the
 * response array is treated as primary. The engine, not this file, decides that
 * order (see file header) — this is not a second precedence table, only a read.
 */
export function primaryDeclineCode(codes: DeclineCode[]): DeclineCode | null {
  return codes[0] ?? null;
}

export function buildDeclineEducation(
  code: DeclineCode,
  answers: EligibilitySubmission,
): DeclineEducation {
  const purposeLabel = PURPOSE_LABEL[answers.purpose];
  const caseLabel =
    answers.case_type === "extension"
      ? "extend a Visa on Arrival you already hold"
      : "get a new Visa on Arrival";

  switch (code) {
    case "NATIONALITY_NOT_ELIGIBLE":
      return {
        code,
        mirror: `You told us you hold a passport from ${answers.nationality}.`,
        forbids:
          "The Visa on Arrival is not issued to your nationality — no online form changes that.",
        alternative:
          "Our Visa Match tool checks your case against every Bali Zero visa route in under a minute and tells you which one fits.",
        routeKind: "oracle",
      };
    case "PURPOSE_NOT_ELIGIBLE":
      return {
        code,
        mirror: `You told us you're coming for ${purposeLabel}.`,
        forbids: "The Visa on Arrival doesn't cover that purpose of travel.",
        alternative:
          "Here's what does: our Visa Match tool matches your real purpose to the right visa and its cost.",
        routeKind: "oracle",
      };
    case "GROUP_CASE":
      return {
        code,
        mirror: `You told us you're travelling with ${answers.travellers} people on this application.`,
        forbids:
          "This online form only files one passport at a time — it can't submit a group together.",
        alternative:
          "A consultant can open and track every passport in your group side by side.",
        routeKind: "whatsapp",
      };
    case "PASSPORT_TYPE":
      return {
        code,
        mirror: "You told us about the passport you're travelling on.",
        forbids:
          "That passport type needs a manual check before we can confirm the Visa on Arrival applies.",
        alternative: "A consultant can verify it with you directly.",
        routeKind: "whatsapp",
      };
    case "PASSPORT_VALIDITY":
      return {
        code,
        mirror: "You told us your passport's expiry date.",
        forbids:
          "The Visa on Arrival needs more validity left on the passport than yours currently has.",
        alternative:
          "Renew the passport and this same online check will clear — or a consultant can confirm the exact margin you need.",
        routeKind: "whatsapp",
      };
    case "NOT_SELF_PAY":
      return {
        code,
        mirror: "You told us someone else is paying for this application.",
        forbids:
          "The online checkout only accepts payment from the traveller's own card.",
        alternative: "A consultant can take a third-party payment for you.",
        routeKind: "whatsapp",
      };
    case "EXTENSION_ALREADY_USED":
      return {
        code,
        mirror: `You told us you want to ${caseLabel}.`,
        forbids:
          "A Visa on Arrival can only be extended once, and yours already has been.",
        alternative:
          "Our Visa Match tool can find the visa that fits a longer stay from here.",
        routeKind: "oracle",
      };
    case "EXTENSION_EXCEEDS_MAX_STAY":
      return {
        code,
        mirror: `You told us you want to ${caseLabel}.`,
        forbids:
          "That extension would take your stay past the maximum the Visa on Arrival allows.",
        alternative:
          "Our Visa Match tool can find the right visa for the length of stay you actually need.",
        routeKind: "oracle",
      };
    case "FEEDBACK_REQUIRED":
      return {
        code,
        mirror: "Something in your answers needs a closer look.",
        forbids: "We can't confirm eligibility automatically for this case.",
        alternative: "A consultant can review it with you directly.",
        routeKind: "whatsapp",
      };
    case "URGENT_CASE":
      return {
        code,
        mirror: "You told us this case is time-sensitive.",
        forbids:
          "The standard online timeline can't be safely compressed further.",
        alternative: "A consultant can work an urgent case by hand.",
        routeKind: "whatsapp",
      };
    case "SPECIAL_PASSPORT":
      return {
        code,
        mirror: "You told us about the passport you're travelling on.",
        forbids:
          "Diplomatic and service passports are handled outside the standard Visa on Arrival flow.",
        alternative: "A consultant can route it correctly.",
        routeKind: "whatsapp",
      };
    case "PRIOR_ISSUE":
      return {
        code,
        mirror: "You told us about your prior visit to Indonesia.",
        forbids:
          "That history needs a case review before the Visa on Arrival can be confirmed.",
        alternative: "A consultant can review it with you directly.",
        routeKind: "whatsapp",
      };
    case "FASTLANE_REQUEST":
      return {
        code,
        mirror: "You asked about the airport fast-lane service.",
        forbids: "That's a separate service from the Visa on Arrival itself.",
        alternative: "A consultant can set up both for you together.",
        routeKind: "whatsapp",
      };
    case "EXPIRY_UNKNOWN":
      return {
        code,
        mirror: "We didn't get a clear passport expiry date from your answer.",
        forbids: "We can't confirm eligibility without that date.",
        alternative:
          "Check your passport's data page and try again, or send it to a consultant.",
        routeKind: "whatsapp",
      };
    case "EXPIRES_TOO_SOON":
      return {
        code,
        mirror: "You told us your passport's expiry date.",
        forbids:
          "It expires too soon for the Visa on Arrival to be issued against it.",
        alternative:
          "Renew the passport and this same online check will clear.",
        routeKind: "whatsapp",
      };
    case "ARRIVAL_TOO_SOON":
      return {
        code,
        mirror: "You told us your arrival date.",
        forbids:
          "It's too close for this online check to confirm eligibility yet.",
        alternative: "A consultant can fast-track the same case by hand.",
        routeKind: "whatsapp",
      };
    case "ARRIVAL_TOO_FAR":
      return {
        code,
        mirror: "You told us your arrival date.",
        forbids:
          "It's too far out for us to quote a price we can stand behind today.",
        alternative:
          "Come back closer to your travel date, or ask a consultant to watch it for you.",
        routeKind: "whatsapp",
      };
    case "ARRIVAL_DATE_UNCONFIRMED":
      return {
        code,
        mirror: "You told us your arrival date.",
        forbids:
          "It falls outside the period we've currently confirmed with the authorities.",
        alternative:
          "A consultant can tell you as soon as that period is confirmed.",
        routeKind: "whatsapp",
      };
    case "ELIGIBILITY_UNCONFIRMED":
      return {
        code,
        mirror: "We tried to confirm your eligibility just now.",
        forbids:
          "Our records for this check aren't fresh enough for us to promise a price or a date.",
        alternative: "A consultant can confirm your case by hand right away.",
        routeKind: "whatsapp",
      };
  }
}
