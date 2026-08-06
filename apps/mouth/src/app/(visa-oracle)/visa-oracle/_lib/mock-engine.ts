/**
 * Visa Oracle v2 — non-authoritative preview state harness.
 *
 * The real deterministic endpoint is the only candidate authority. This file
 * deliberately accepts no applicant facts, has no rules, and never emits a
 * candidate. It exists only so component previews/tests can exercise the five
 * state shells without inventing a visa, price, calendar, or document list.
 */
import type { RecommendState } from "@/lib/visa-oracle/types";

export const PREVIEW_STATES = [
  "SUPPORTED_CANDIDATES",
  "NEEDS_INPUT",
  "HUMAN_REVIEW_REQUIRED",
  "NO_SUPPORTED_PATH",
  "TEMPORARILY_UNAVAILABLE",
] as const satisfies readonly RecommendState[];

export interface PreviewContentBoundary {
  readonly price: { readonly status: "UNAVAILABLE" };
  readonly timeline: { readonly status: "UNAVAILABLE" };
  readonly documents: {
    readonly status: "UNKNOWN";
    readonly items: readonly [];
  };
}

export interface PreviewHarnessResult {
  readonly provenance: "PREVIEW";
  readonly assessment: null;
  readonly state: RecommendState;
  readonly candidates: readonly [];
  readonly content: PreviewContentBoundary;
}

const PREVIEW_CONTENT_BOUNDARY: PreviewContentBoundary = Object.freeze({
  price: Object.freeze({ status: "UNAVAILABLE" }),
  timeline: Object.freeze({ status: "UNAVAILABLE" }),
  documents: Object.freeze({
    status: "UNKNOWN",
    items: Object.freeze([]) as readonly [],
  }),
});

/** Creates display-state scaffolding only; it cannot evaluate or recommend. */
export function createPreviewHarnessState(
  state: RecommendState,
): PreviewHarnessResult {
  return {
    provenance: "PREVIEW",
    assessment: null,
    state,
    candidates: [],
    content: PREVIEW_CONTENT_BOUNDARY,
  };
}
