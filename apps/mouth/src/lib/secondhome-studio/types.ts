/**
 * Second Home Studio — Phase B core loop types.
 *
 * FROZEN CONTRACT — verbatim from SPEC-secondhome-studio-phaseB.md §2. Do not
 * reshape without re-freezing the spec; every other module in this package
 * (rules.ts, timeline.ts, checklist.ts, plan-codec.ts, copy.ts) is built
 * against these exact shapes.
 */

export type AgeBand = "under_55" | "55_59" | "60_plus";
export type RouteIntent = "deposit" | "property" | "unsure";
export type CapitalBand = "ready_130k" | "close_100k_130k" | "below_100k";
export type SeniorFunding =
  "deposit_50k_income" | "income_only_3k" | "neither" | "not_applicable";
export type PropertyStatus =
  | "owns_qualifying_strata"
  | "buying_completed_strata"
  | "villa_land_leasehold"
  | "none";
export type FamilyPlan = { spouse: boolean; children: number; parents: number };
export type TimelineHorizon = "asap" | "this_quarter" | "exploring";
export type Location = "in_indonesia" | "abroad";

export interface PlanState {
  v: 1; // codec schema version
  age: AgeBand | null;
  route: RouteIntent | null;
  capital: CapitalBand | null; // deposit route only
  seniorFunding: SeniorFunding | null; // 55+ only
  property: PropertyStatus | null; // property route only
  family: FamilyPlan;
  horizon: TimelineHorizon | null;
  location: Location | null;
  checklist: Record<string, boolean>; // checklist item id -> done
  updatedAt: string; // ISO date
}

export type VerdictBand =
  "strong_fit" | "likely_fit" | "edge_case" | "not_eligible";

export interface Verdict {
  band: VerdictBand;
  product: "E33" | "E33E" | "E33F" | null; // null when not_eligible/edge without product
  reasons: string[]; // copy KEYS from copy.ts, never free strings
  humanReviewNote: string | null; // copy KEY
}
