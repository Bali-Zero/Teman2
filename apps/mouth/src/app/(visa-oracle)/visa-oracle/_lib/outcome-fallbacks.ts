import type {
  InterviewAssumption,
  LocalizedText,
  OutcomeNextSteps,
  TemporarilyUnavailableOutcome,
} from "./outcome-view-model";

const NEXT_STEPS: OutcomeNextSteps = [
  {
    id: "review-answers",
    title: {
      en: "Review the answers and assumptions",
      id: "Tinjau jawaban dan asumsi",
    },
  },
  {
    id: "save-receipt",
    title: {
      en: "Save or print this safety receipt",
      id: "Simpan atau cetak tanda terima keamanan ini",
    },
  },
  {
    id: "consented-contact",
    title: {
      en: "Contact an advisor only if you choose to share it",
      id: "Hubungi konsultan hanya jika Anda memilih untuk membagikannya",
    },
  },
];

const OUTAGE_MESSAGES: Record<
  "CLIENT_GUARD" | "NETWORK_FAILURE" | "SHADOW",
  LocalizedText
> = {
  CLIENT_GUARD: {
    en: "This interview contains information the verified API cannot represent safely. No evaluation was submitted.",
    id: "Wawancara ini berisi informasi yang tidak dapat direpresentasikan dengan aman oleh API terverifikasi. Tidak ada evaluasi yang dikirim.",
  },
  NETWORK_FAILURE: {
    en: "The verified decision service did not return a usable response. No visa path is shown.",
    id: "Layanan keputusan terverifikasi tidak memberikan respons yang dapat digunakan. Tidak ada jalur visa yang ditampilkan.",
  },
  SHADOW: {
    en: "Your assessment was submitted for verification. Public engine enforcement is disabled, so no visa path is shown.",
    id: "Asesmen Anda telah dikirim untuk verifikasi. Penegakan mesin publik dinonaktifkan, sehingga tidak ada jalur visa yang ditampilkan.",
  },
};

interface FallbackOptions {
  code: string;
  assumptions?: readonly InterviewAssumption[];
  retryable?: boolean;
}

function buildFallback(
  provenance: "CLIENT_GUARD" | "NETWORK_FAILURE" | "SHADOW",
  options: FallbackOptions,
): TemporarilyUnavailableOutcome {
  return {
    state: "TEMPORARILY_UNAVAILABLE",
    provenance,
    assessment: null,
    candidates: [],
    pathsRemaining: 0,
    assumptions: options.assumptions ?? [],
    sources: [],
    nextSteps: NEXT_STEPS,
    outage: {
      code: options.code,
      message: OUTAGE_MESSAGES[provenance],
      retryable: options.retryable ?? provenance === "NETWORK_FAILURE",
    },
  };
}

/** A local operational hold, visibly not an engine decision. */
export function buildClientGuardOutcome(
  options: FallbackOptions,
): TemporarilyUnavailableOutcome {
  return buildFallback("CLIENT_GUARD", { ...options, retryable: false });
}

/** A transport/parser failure, visibly not an engine decision. */
export function buildNetworkFailureOutcome(
  options: FallbackOptions,
): TemporarilyUnavailableOutcome {
  return buildFallback("NETWORK_FAILURE", options);
}

/** SHADOW submits and compares, but never exposes backend or preview paths. */
export function buildShadowOutcome(
  options: Omit<FallbackOptions, "retryable">,
): TemporarilyUnavailableOutcome {
  return buildFallback("SHADOW", { ...options, retryable: false });
}
