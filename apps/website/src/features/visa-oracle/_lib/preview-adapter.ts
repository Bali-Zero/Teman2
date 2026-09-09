import { NEXT_STEPS as ENGINE_NEXT_STEPS } from "./engine-adapter";
import {
  findGoldOraclePersona,
  goldOracleReviewReasonCode,
  type GoldOraclePersona,
} from "./gold-oracle-baseline";
import type {
  HumanReviewOutcome,
  OutcomeNextSteps,
  OutcomeReason,
  TemporarilyUnavailableOutcome,
} from "./outcome-view-model";
import type { OracleFacts } from "./tree";

const NEXT_STEPS: OutcomeNextSteps = [
  {
    id: "preview-review",
    title: { en: "Review the preview inputs", id: "Tinjau input pratinjau" },
  },
  {
    id: "preview-no-filing",
    title: {
      en: "Do not use this preview to file an application",
      id: "Jangan gunakan pratinjau ini untuk mengajukan permohonan",
    },
  },
  {
    id: "preview-engine",
    title: {
      en: "Run the verified engine before taking action",
      id: "Jalankan mesin terverifikasi sebelum mengambil tindakan",
    },
  },
];

function unavailablePreviewOutcome(): TemporarilyUnavailableOutcome {
  return {
    state: "TEMPORARILY_UNAVAILABLE",
    provenance: "PREVIEW",
    assessment: null,
    candidates: [],
    pathsRemaining: 0,
    assumptions: [],
    sources: [],
    nextSteps: NEXT_STEPS,
    outage: {
      code: "PREVIEW_FIXTURE_ONLY",
      message: {
        en: "Developer preview mode cannot issue or display a visa recommendation.",
        id: "Mode pratinjau pengembang tidak dapat menerbitkan atau menampilkan rekomendasi visa.",
      },
      retryable: false,
    },
  };
}

const GOLD_ORACLE_REVIEW_REASON: OutcomeReason = {
  code: goldOracleReviewReasonCode(),
  // `semanticProjection` never looks at `message` (only `code`/`sourceIds`),
  // so this copy is honest display text, not a parity input. It is NOT the
  // frontend's own `REVIEW_REASON_COPY` (engine-adapter.ts) fallback string:
  // that map has no entry for `DISCLOSED_UNCERTAINTY_REVIEW` yet, so a real
  // ENGINE render of this same reason currently falls back to
  // engine-adapter.ts's `GENERIC_REVIEW_REASON` — unrelated to parity, this
  // baseline's own copy is free to be specific.
  message: {
    en: "You marked one answer as “not sure”, so a person will review this case by hand.",
    id: "Anda menandai satu jawaban sebagai “tidak yakin”, sehingga kasus ini akan ditinjau langsung oleh seseorang.",
  },
  sourceIds: [],
};

/**
 * The gold-oracle baseline's rendering for a matched persona (see
 * `gold-oracle-baseline.ts`): every pinned persona predicts
 * `HUMAN_REVIEW_REQUIRED` with exactly one review reason,
 * `DISCLOSED_UNCERTAINTY_REVIEW` — the disclosed-review-flags policy's own
 * verbatim, pack-independent outcome for "exactly one SKIP answer, no other
 * disclosed-flag trigger" (empirically verified, see that file's doc
 * comment).
 */
function buildGoldOraclePreviewOutcome(
  _persona: GoldOraclePersona,
): HumanReviewOutcome {
  return {
    state: "HUMAN_REVIEW_REQUIRED",
    provenance: "PREVIEW",
    assessment: null,
    candidates: [],
    pathsRemaining: 1,
    assumptions: [],
    sources: [],
    // Real engine copy, not the developer-preview NEXT_STEPS above — see the
    // export site's doc comment in engine-adapter.ts for why this must match.
    nextSteps: ENGINE_NEXT_STEPS,
    reviewReasons: [GOLD_ORACLE_REVIEW_REASON],
  };
}

/**
 * Developer/test-only display boundary. `assessmentClock` is accepted for
 * interface parity with the engine adapters (a caller may need it for a
 * future dated persona) but is never read: this baseline is a documented,
 * pinned snapshot (see `gold-oracle-baseline.ts`), never a live clock read.
 *
 * QW-2 (2026-08): when `facts` matches one of the pinned gold-oracle
 * personas, this returns that persona's independently-verified
 * `HUMAN_REVIEW_REQUIRED` expectation — the real SHADOW-parity baseline. For
 * every other interview (not yet curated into the pinned subset), it falls
 * back to the original zero-candidate `TEMPORARILY_UNAVAILABLE` hold: an
 * honest "no independent baseline available" signal, never a fabricated
 * match.
 *
 * Non-tautology invariant (pinned by `preview-adapter.test.ts` and
 * `shadow-parity.test.ts`): this function's ENTIRE input is `(facts, clock)`
 * — it has no `VisaOracleEvaluateResponse` parameter to read from, so it is
 * structurally incapable of deriving its answer from the response under
 * test.
 */
export function buildPreviewOutcome(
  facts: OracleFacts,
  _assessmentClock: Date,
): TemporarilyUnavailableOutcome | HumanReviewOutcome {
  const persona = findGoldOraclePersona(facts);
  if (persona) return buildGoldOraclePreviewOutcome(persona);
  return unavailablePreviewOutcome();
}
