import {
  requireEngineResponse,
  VisaOracleResponseError,
} from "./engine-response";
import { QUESTIONS, type OracleFacts } from "./tree";
import { trustedPrimarySourceUrl } from "./trusted-source-url";
import type {
  InterviewAssumption,
  LocalizedText,
  OperationalAvailabilityStatus,
  OutcomeCandidate,
  OutcomeDocument,
  OutcomeNextSteps,
  OutcomePrice,
  OutcomeReason,
  OutcomeSource,
  OutcomeTimeline,
  OutcomeViewModel,
  ServiceAvailabilityStatus,
} from "./outcome-view-model";
import type {
  VisaOracleCandidateDisplay,
  VisaOracleEvaluateResponse,
  VisaOracleSourceRecord,
} from "./visa-oracle-contract";

const text = (en: string, id: string): LocalizedText => ({ en, id });

const NEXT_STEPS: OutcomeNextSteps = [
  {
    id: "review-decision",
    title: text(
      "Review the verified decision and its assumptions",
      "Tinjau keputusan terverifikasi dan asumsinya",
    ),
  },
  {
    id: "prepare-verified-items",
    title: text(
      "Prepare only documents marked as verified",
      "Siapkan hanya dokumen yang ditandai terverifikasi",
    ),
  },
  {
    id: "consented-advice",
    title: text(
      "Choose whether to contact a Bali Zero advisor",
      "Pilih apakah akan menghubungi konsultan Bali Zero",
    ),
  },
];

const PUBLIC_ID = /^[a-z0-9]{16,20}$/;

function reasonMessage(code: string): LocalizedText {
  return text(`Verified reason: ${code}`, `Alasan terverifikasi: ${code}`);
}

function reason(
  code: string,
  sourceIds: readonly string[],
  trustedIds: ReadonlySet<string>,
): OutcomeReason {
  return {
    code,
    message: reasonMessage(code),
    sourceIds: sourceIds.filter((id) => trustedIds.has(id)),
  };
}

// Curated, human-readable copy for the rule pack's HUMAN_REVIEW reason
// codes (source: services/visa_engine/contracts/packs/rulepack-prod-*.json
// `effect.reason_code` on REQUIRE_REVIEW rules). A code missing from this
// map falls back to an honest generic sentence — never a raw code dump —
// so a new rule can ship without breaking this UI, and this map can grow
// independently of a rule pack release.
const REVIEW_REASON_COPY: Record<string, LocalizedText> = {
  CALLING_VISA_REVIEW: text(
    "Your nationality is on the Calling Visa list, which always requires manual review before a visa can be confirmed.",
    "Kewarganegaraan Anda termasuk dalam daftar Calling Visa, yang selalu memerlukan peninjauan manual sebelum visa dapat dikonfirmasi.",
  ),
  ACTIVE_OVERSTAY: text(
    "An active overstay on record needs a person to review before any path can be confirmed.",
    "Overstay aktif yang tercatat memerlukan peninjauan oleh seseorang sebelum jalur apa pun dapat dikonfirmasi.",
  ),
  CITIZENSHIP_EVIDENCE_CONFLICT: text(
    "Your answers about citizenship do not fully agree with each other and need a person to confirm.",
    "Jawaban Anda tentang kewarganegaraan tidak sepenuhnya cocok satu sama lain dan memerlukan konfirmasi dari seseorang.",
  ),
  MINOR_WITHOUT_CONFIRMED_GUARDIAN: text(
    "This case involves a minor without a confirmed guardian on file and needs a person to review it.",
    "Kasus ini melibatkan anak di bawah umur tanpa wali yang terkonfirmasi dan memerlukan peninjauan oleh seseorang.",
  ),
  STATUS_BRIDGING_REVIEW: text(
    "Bridging between immigration statuses needs a person to check the timing and conditions involved.",
    "Peralihan antar status keimigrasian memerlukan pemeriksaan oleh seseorang atas waktu dan ketentuan yang berlaku.",
  ),
  LOCAL_MARKET_ACTIVITY_REVIEW: text(
    "The activity you described needs a person to confirm it does not cross into locally reserved business.",
    "Aktivitas yang Anda jelaskan memerlukan konfirmasi oleh seseorang agar tidak melanggar bidang usaha yang dicadangkan untuk lokal.",
  ),
  DISCLOSED_ACTIVITY_BOUNDARY_REVIEW: text(
    "The activity you disclosed sits close to a legal boundary that needs a person to confirm.",
    "Aktivitas yang Anda ungkapkan berada dekat batas hukum yang memerlukan konfirmasi dari seseorang.",
  ),
};

const GENERIC_REVIEW_REASON: LocalizedText = text(
  "Some of your answers need a person's judgment before we can confirm a path.",
  "Beberapa jawaban Anda memerlukan penilaian dari seseorang sebelum kami dapat mengonfirmasi jalur.",
);

function reviewReason(
  code: string,
  sourceIds: readonly string[],
  trustedIds: ReadonlySet<string>,
): OutcomeReason {
  return {
    code,
    message: REVIEW_REASON_COPY[code] ?? GENERIC_REVIEW_REASON,
    sourceIds: sourceIds.filter((id) => trustedIds.has(id)),
  };
}

function outcomeSource(source: VisaOracleSourceRecord): OutcomeSource | null {
  const url = trustedPrimarySourceUrl(source.canonical_url);
  if (!url) return null;
  return {
    id: source.source_record_id,
    title: source.title,
    publisher: source.publisher,
    url,
    authority: source.authority_type,
    primary: source.is_primary_authority,
    effectiveAtIso: source.applicability.effective_at,
    observedAtIso: source.applicability.observed_at,
    freshness: source.freshness.status,
  };
}

function decisiveSource(
  source: VisaOracleSourceRecord | undefined,
  decisionEffectiveAt: string,
  decisionObservedAt: string,
): boolean {
  if (!source) return false;
  const effectiveAt = Date.parse(decisionEffectiveAt);
  const observedAt = Date.parse(decisionObservedAt);
  const legalFrom = Date.parse(source.legal_period_from);
  const legalTo = source.legal_period_to
    ? Date.parse(source.legal_period_to)
    : null;
  const recordedFrom = Date.parse(source.recorded_period_from);
  const retrievedAt = Date.parse(source.retrieved_at);
  const verifiedAt = Date.parse(source.verified_at);
  const applicabilityEffectiveAt = Date.parse(
    source.applicability.effective_at,
  );
  const applicabilityObservedAt = Date.parse(source.applicability.observed_at);
  const freshnessEvaluatedAt = Date.parse(source.freshness.evaluated_at);
  const freshnessVerifiedAt = Date.parse(source.freshness.verified_at);
  return (
    source.is_primary_authority &&
    source.status === "VERIFIED" &&
    source.applicability.status === "APPLICABLE" &&
    source.freshness.status === "CURRENT" &&
    trustedPrimarySourceUrl(source.canonical_url) !== null &&
    legalFrom <= effectiveAt &&
    (legalTo === null || effectiveAt < legalTo) &&
    recordedFrom <= observedAt &&
    retrievedAt <= verifiedAt &&
    verifiedAt <= observedAt &&
    applicabilityObservedAt <= observedAt &&
    freshnessEvaluatedAt <= observedAt &&
    freshnessVerifiedAt <= observedAt &&
    applicabilityEffectiveAt === effectiveAt &&
    applicabilityObservedAt === observedAt &&
    freshnessEvaluatedAt === observedAt &&
    freshnessVerifiedAt === verifiedAt
  );
}

function reviewHoldSource(source: VisaOracleSourceRecord | undefined): boolean {
  return (
    source !== undefined &&
    source.is_primary_authority &&
    trustedPrimarySourceUrl(source.canonical_url) !== null
  );
}

function operationalStatus(
  status: "AVAILABLE" | "UNAVAILABLE" | "UNKNOWN",
): OperationalAvailabilityStatus {
  if (status === "AVAILABLE") return "AVAILABLE";
  if (status === "UNAVAILABLE") return "TEMPORARILY_UNAVAILABLE";
  return "UNKNOWN";
}

function serviceStatus(
  status: "AVAILABLE" | "UNAVAILABLE" | "UNKNOWN",
): ServiceAvailabilityStatus {
  if (status === "AVAILABLE") return "AVAILABLE";
  if (status === "UNAVAILABLE") return "NOT_OFFERED";
  return "UNKNOWN";
}

function timeline(candidate: VisaOracleCandidateDisplay): OutcomeTimeline {
  const value = candidate.processing_timeline;
  if (
    value.status === "AVAILABLE" &&
    value.anchor_date &&
    value.estimated_completion_from &&
    value.estimated_completion_to
  ) {
    return {
      status: "AVAILABLE",
      basisDateIso: value.anchor_date,
      earliestDateIso: value.estimated_completion_from,
      latestDateIso: value.estimated_completion_to,
      note: reasonMessage(value.reason_code),
    };
  }
  return {
    status: "UNAVAILABLE",
    message: text(
      "A verified operational processing timeline is not available.",
      "Timeline proses operasional terverifikasi belum tersedia.",
    ),
  };
}

function documents(candidate: VisaOracleCandidateDisplay): OutcomeDocument[] {
  if (candidate.documentation.status !== "AVAILABLE") return [];
  const result: OutcomeDocument[] = [];
  const seen = new Set<string>();
  for (const [kind, items] of [
    ["requirement", candidate.documentation.requirements],
    ["checklist", candidate.documentation.checklist],
  ] as const) {
    for (const [index, label] of items.entries()) {
      const dedupe = `${label.en}\u0000${label.id}`;
      if (seen.has(dedupe)) continue;
      seen.add(dedupe);
      result.push({
        id: `${candidate.product_version_id}:${kind}:${index}`,
        label,
        status: "REQUIRED",
        sourceIds: [],
      });
    }
  }
  return result;
}

function price(
  candidate: VisaOracleCandidateDisplay,
  response: VisaOracleEvaluateResponse,
): OutcomePrice {
  const quote = response.decision.quotes.find(
    (item) => item.product_version_id === candidate.product_version_id,
  );
  if (
    candidate.pricing.status === "AVAILABLE" &&
    quote?.status === "AVAILABLE" &&
    quote.amount !== null
  ) {
    return {
      status: "AVAILABLE",
      currency: "IDR",
      amount: quote.amount,
      allInclusive: true,
      quotedAtIso: quote.quoted_at,
      ...(quote.valid_until ? { validUntilIso: quote.valid_until } : {}),
    };
  }
  if (candidate.pricing.status === "CONTACT_REQUIRED") {
    return {
      status: "CONTACT_REQUIRED",
      message: text(
        "An all-inclusive verified quote requires contact.",
        "Penawaran all-inclusive terverifikasi memerlukan kontak.",
      ),
    };
  }
  return {
    status: "UNAVAILABLE",
    message: text(
      "No verified all-inclusive price is available.",
      "Harga all-inclusive terverifikasi belum tersedia.",
    ),
  };
}

function questionForFact(path: string): string | undefined {
  for (const question of Object.values(QUESTIONS)) {
    if (
      question.decisionMapping.kind !== "HUMAN_CONTEXT" &&
      question.decisionMapping.factPaths.includes(path)
    ) {
      return question.id;
    }
  }
  return undefined;
}

function nonEmpty<T>(values: T[]): [T, ...T[]] {
  if (values.length === 0) {
    throw new VisaOracleResponseError("RESPONSE_INVARIANT");
  }
  return values as unknown as [T, ...T[]];
}

export interface BuildEngineOutcomeOptions {
  assumptions?: readonly InterviewAssumption[];
  facts?: OracleFacts;
  interviewBranchesRemaining?: number;
}

/**
 * Translate one already-validated authoritative response. Candidate order and
 * membership are copied verbatim; this adapter contains no ranking or rules.
 */
function buildValidatedOutcome(
  response: VisaOracleEvaluateResponse,
  options: BuildEngineOutcomeOptions = {},
): OutcomeViewModel {
  const sourcesById = new Map(
    response.sources.map((source) => [source.source_record_id, source]),
  );
  const sources = response.sources
    .map(outcomeSource)
    .filter((source): source is OutcomeSource => source !== null);
  const trustedIds = new Set(sources.map((source) => source.id));

  const requireDecisiveRefs = (sourceIds: readonly string[]) => {
    if (
      sourceIds.length === 0 ||
      sourceIds.some(
        (id) =>
          !decisiveSource(
            sourcesById.get(id),
            response.decision.effective_at,
            response.decision.observed_at,
          ),
      )
    ) {
      throw new VisaOracleResponseError("RESPONSE_INVARIANT");
    }
  };
  const requireReviewHoldRefs = (sourceIds: readonly string[]) => {
    if (sourceIds.some((id) => !reviewHoldSource(sourcesById.get(id)))) {
      throw new VisaOracleResponseError("RESPONSE_INVARIANT");
    }
  };

  const assessment = {
    ...(response.decision.public_id &&
    PUBLIC_ID.test(response.decision.public_id)
      ? { publicId: response.decision.public_id }
      : {}),
    effectiveAtIso: response.decision.effective_at,
    observedAtIso: response.decision.observed_at,
    evaluatedAtIso: response.decision.evaluated_at,
    ...(response.decision.rule_pack
      ? {
          ruleset: {
            id: response.decision.rule_pack.rule_pack_id,
            version: response.decision.rule_pack.version,
            sequence: response.decision.rule_pack.sequence,
          },
        }
      : {}),
  };
  const base = {
    provenance: "ENGINE" as const,
    assessment,
    assumptions: options.assumptions ?? [],
    sources,
    nextSteps: NEXT_STEPS,
  };

  switch (response.decision.state) {
    case "SUPPORTED_CANDIDATES": {
      const candidates = response.display.candidates.map((projected, index) => {
        const decisionCandidate = response.decision.candidates[index];
        requireDecisiveRefs(decisionCandidate.source_refs);
        const operational = projected.availability.operational_availability;
        const service = projected.availability.bali_zero_service_availability;
        if (operational.status !== "UNKNOWN") {
          requireDecisiveRefs(operational.source_refs);
        }
        if (service.status !== "UNKNOWN") {
          requireDecisiveRefs(service.source_refs);
        }
        return {
          id: projected.product_version_id,
          code: projected.product_code,
          rank: projected.rank,
          name: projected.name,
          ...(projected.tagline ? { tagline: projected.tagline } : {}),
          legal: {
            status: "SUPPORTED" as const,
            reasons: decisionCandidate.reason_codes.map((code) =>
              reason(code, decisionCandidate.source_refs, trustedIds),
            ),
          },
          operational: {
            status: operationalStatus(operational.status),
            reasons: [
              reason(
                operational.reason_code,
                operational.source_refs,
                trustedIds,
              ),
            ],
          },
          service: {
            status: serviceStatus(service.status),
            reasons: [
              reason(service.reason_code, service.source_refs, trustedIds),
            ],
          },
          decisionReasons: decisionCandidate.reason_codes.map((code) =>
            reason(code, decisionCandidate.source_refs, trustedIds),
          ),
          timeline: timeline(projected),
          price: price(projected, response),
          documents: documents(projected),
        } satisfies OutcomeCandidate;
      });
      if (candidates.length === 0) {
        throw new VisaOracleResponseError("RESPONSE_INVARIANT");
      }
      return {
        ...base,
        state: "SUPPORTED_CANDIDATES",
        pathsRemaining: candidates.length,
        candidates: nonEmpty(candidates),
      };
    }
    case "NEEDS_INPUT":
      return {
        ...base,
        state: "NEEDS_INPUT",
        candidates: [],
        pathsRemaining: Math.max(1, options.interviewBranchesRemaining ?? 1),
        missingInputs: nonEmpty(
          response.decision.missing_facts.map((path) => ({
            code: path,
            message: text(
              `Verified evaluation needs: ${path}`,
              `Evaluasi terverifikasi memerlukan: ${path}`,
            ),
            sourceIds: [],
            ...(questionForFact(path)
              ? { questionId: questionForFact(path) }
              : {}),
          })),
        ),
      };
    case "HUMAN_REVIEW_REQUIRED":
      return {
        ...base,
        state: "HUMAN_REVIEW_REQUIRED",
        candidates: [],
        pathsRemaining: Math.max(1, options.interviewBranchesRemaining ?? 1),
        reviewReasons: response.decision.review_reasons.map((item) => {
          requireReviewHoldRefs(item.source_refs);
          return reviewReason(item.code, item.source_refs, trustedIds);
        }) as [OutcomeReason, ...OutcomeReason[]],
      };
    case "NO_SUPPORTED_PATH":
      return {
        ...base,
        state: "NO_SUPPORTED_PATH",
        candidates: [],
        pathsRemaining: 0,
        noPathReasons: response.decision.no_path_reasons.map((item) => {
          requireDecisiveRefs(item.source_refs);
          return reason(item.code, item.source_refs, trustedIds);
        }) as [OutcomeReason, ...OutcomeReason[]],
        alternatives: [],
      };
    case "TEMPORARILY_UNAVAILABLE":
      return {
        ...base,
        state: "TEMPORARILY_UNAVAILABLE",
        candidates: [],
        pathsRemaining: 0,
        outage: {
          code: response.decision.outage?.code ?? "ENGINE_UNAVAILABLE",
          message: text(
            "The verified decision service is temporarily unavailable. No visa path is shown.",
            "Layanan keputusan terverifikasi sementara tidak tersedia. Tidak ada jalur visa yang ditampilkan.",
          ),
          retryable: response.decision.outage?.retryable ?? false,
        },
      };
  }
}

/** Public rendering boundary: CURATED can never become visible authority. */
export function buildEngineOutcome(
  input: VisaOracleEvaluateResponse,
  options: BuildEngineOutcomeOptions = {},
): OutcomeViewModel {
  return buildValidatedOutcome(requireEngineResponse(input), options);
}

/**
 * Shadow-only semantic adapter. The evaluation client has already applied
 * the runtime response guard; this entrypoint accepts either response mode
 * solely for parity comparison and must never feed a render path.
 */
export function buildShadowComparisonOutcome(
  input: VisaOracleEvaluateResponse,
  options: BuildEngineOutcomeOptions = {},
): OutcomeViewModel {
  if (input.mode !== "ENGINE" && input.mode !== "CURATED") {
    throw new VisaOracleResponseError("MALFORMED_RESPONSE");
  }
  return buildValidatedOutcome(input, options);
}
