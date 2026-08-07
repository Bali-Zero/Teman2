import type {
  OutcomeNextSteps,
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

/**
 * Developer/test-only display boundary. The retired fixture evaluator cannot
 * select even a preview candidate, so PREVIEW is an explicit zero-candidate
 * hold. Production coerces this mode to ENGINE in `runtime-mode.ts`.
 */
export function buildPreviewOutcome(
  _facts: OracleFacts,
  _assessmentClock: Date,
): TemporarilyUnavailableOutcome {
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
