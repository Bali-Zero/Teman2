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

/**
 * Human-readable copy for the pack's SUPPORT reason codes — the "why this
 * path is supported" line. Without it the UI printed the bare machine code
 * (`Verified reason: B1_VOA_ELIGIBLE`) on every candidate of every product.
 *
 * Each sentence is derived from the rule's own `when` clause and may claim
 * NOTHING the rule did not test. `PURPOSE_PRODUCT_MATCH` is deliberately
 * generic: 16 rules share that one code — employment, six family relations,
 * D1/D2/D12 multi-entry and study — so any specific sentence would be false
 * for fifteen of them.
 *
 * Unknown codes keep the existing `Verified reason: <code>` form rather than
 * degrading to a generic sentence: a code we have not written copy for is
 * still information, and silently blanking it would hide a new rule instead
 * of surfacing it. (The REVIEW map above chooses the opposite fallback on
 * purpose — there, a wrong-sounding specific is worse than a safe generic.)
 */
export const SUPPORT_REASON_COPY: Record<string, LocalizedText> = {
  A1_BVK_ELIGIBLE: text(
    "Your nationality is on the visa-free (BVK) list for tourism or transit, and your stay is 30 days or less.",
    "Kewarganegaraan Anda ada dalam daftar bebas visa (BVK) untuk wisata atau transit, dan masa tinggal Anda 30 hari atau kurang.",
  ),
  B1_VOA_ELIGIBLE: text(
    "Your nationality is on the Visa on Arrival list for tourism, and your stay is 30 days or less.",
    "Kewarganegaraan Anda ada dalam daftar Visa on Arrival untuk wisata, dan masa tinggal Anda 30 hari atau kurang.",
  ),
  C1_VISIT_ELIGIBLE: text(
    "A tourism or family visit with a stay of 60 days or less.",
    "Kunjungan wisata atau keluarga dengan masa tinggal 60 hari atau kurang.",
  ),
  C2_BUSINESS_ELIGIBLE: text(
    "Business meetings or investment, with a confirmed sponsor and a stay of 60 days or less.",
    "Pertemuan bisnis atau investasi, dengan penjamin terkonfirmasi dan masa tinggal 60 hari atau kurang.",
  ),
  C6_SOCIAL_ELIGIBLE: text(
    "A social or other stated purpose, with a confirmed sponsor and a stay of 60 days or less.",
    "Tujuan sosial atau lainnya, dengan penjamin terkonfirmasi dan masa tinggal 60 hari atau kurang.",
  ),
  E28A_INVESTMENT_ELIGIBLE: text(
    "You committed to a PT PMA as shareholder-director or shareholder-commissioner, with paid-up capital of IDR 2.5 billion or more.",
    "Anda berkomitmen pada PT PMA sebagai pemegang saham-direktur atau pemegang saham-komisaris, dengan modal disetor minimal Rp 2,5 miliar.",
  ),
  E33E_RETIREMENT_ELIGIBLE: text(
    "Retirement, age 55 or over, with a deposit of USD 50,000 or more held in your own name at a state bank.",
    "Pensiun, usia 55 tahun ke atas, dengan deposito minimal USD 50.000 atas nama sendiri di bank BUMN.",
  ),
  E33F_RETIREMENT_ELIGIBLE: text(
    "Retirement with passive income of USD 3,000 per month or more and a confirmed sponsor.",
    "Pensiun dengan penghasilan pasif minimal USD 3.000 per bulan dan penjamin terkonfirmasi.",
  ),
  E33_DEPOSIT_BASIS_ELIGIBLE: text(
    "Second Home on the deposit basis: USD 130,000 or more held in your own name at a state bank.",
    "Rumah Kedua berbasis deposito: minimal USD 130.000 atas nama sendiri di bank BUMN.",
  ),
  E33_PROPERTY_BASIS_ELIGIBLE: text(
    "Second Home on the property basis: qualifying property valued at USD 1,000,000 or more.",
    "Rumah Kedua berbasis properti: properti memenuhi syarat senilai minimal USD 1.000.000.",
  ),
  REMOTE_WORK_ELIGIBLE: text(
    "You work remotely for a non-Indonesian employer, serve no Indonesian clients, and take no Indonesian-source compensation.",
    "Anda bekerja jarak jauh untuk pemberi kerja non-Indonesia, tidak melayani klien Indonesia, dan tidak menerima kompensasi dari sumber Indonesia.",
  ),
  BRIDGING_DESTINATION_STATED: text(
    "You named a destination status other than the bridging permit itself, so a bridging route can be assessed.",
    "Anda menyebut status tujuan selain izin peralihan itu sendiri, sehingga jalur peralihan dapat dinilai.",
  ),
  PURPOSE_PRODUCT_MATCH: text(
    "Your stated purpose and the circumstances you confirmed match what this visa covers.",
    "Tujuan yang Anda nyatakan dan keadaan yang Anda konfirmasi sesuai dengan cakupan visa ini.",
  ),
};

function reasonMessage(code: string): LocalizedText {
  return (
    SUPPORT_REASON_COPY[code] ??
    text(`Verified reason: ${code}`, `Alasan terverifikasi: ${code}`)
  );
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
    // These two feed a line that reads "Effective X · observed Y" ABOUT THE
    // SOURCE, so they must carry the document's own dates.
    //
    // They used to read `source.applicability.*`, which is not a property of
    // the document at all: the backend writes the decision's evaluation clock
    // into every cited source's applicability block (`_build_sources_dto` in
    // evaluate_path.py sets effective_at/observed_at from `decision.*`, itself
    // `now`). The result on screen was every source claiming it took legal
    // effect at the instant the reader pressed the button — a date that reads
    // as a freshness guarantee while carrying no information about the source.
    //
    // `verified_at` rather than `retrieved_at` for "observed": the only
    // freshness policy the schema can express is MAX_AGE_SINCE_VERIFIED_AT,
    // so this is the date that explains the freshness badge rendered beside
    // it. Narrower than it sounds — `freshness_policy` is optional for packs
    // signed under the older schema, and a source without one is reported
    // UNKNOWN; there the badge has no rule to explain, and `verified_at` is
    // simply the better of two dates rather than the one the policy names.
    effectiveAtIso: source.legal_period_from,
    observedAtIso: source.verified_at,
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

/**
 * INTERNAL PIN-GATED PREVIEW — a deliberately separate rendering boundary
 * from `buildEngineOutcome`, which stays the public one ("CURATED can never
 * become visible authority").
 *
 * Callers MUST have proven server-side PIN possession first (the `vo_internal`
 * httpOnly cookie, set only by `/api/visa-oracle-unlock` after a timing-safe
 * comparison). It exists so the Bali Zero team can exercise the real engine
 * while `VISA_ENGINE_EVALUATE_MODE` is still SHADOW: the backend already
 * computes and returns the full decision in that mode (`evaluate_path.py`
 * fills `decision`/`sources`/`display` unconditionally and only varies the
 * `mode` string), so nothing here reaches past what the response already
 * carries — no backend change, and NO durable ENFORCE write, which keys off
 * the global `engine_mode`, never off this string.
 *
 * A CURATED response rendered through here is comparison-grade, NOT
 * authoritative: the caller is responsible for labelling it as an internal
 * preview in the UI. Never call this for anonymous public traffic.
 */
export function buildInternalPreviewOutcome(
  input: VisaOracleEvaluateResponse,
  options: BuildEngineOutcomeOptions = {},
): OutcomeViewModel {
  if (input.mode !== "ENGINE" && input.mode !== "CURATED") {
    throw new VisaOracleResponseError("MALFORMED_RESPONSE");
  }
  return buildValidatedOutcome(input, options);
}
