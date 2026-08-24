"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { ArrowRight } from "lucide-react";
import { useReducedMotion } from "framer-motion";
import {
  restoreInterviewSnapshot,
  useOracleFlow,
  type BlockedAnswer,
  type InterviewSnapshot,
} from "../_lib/flow";
import { QUESTIONS, getLane, type CategoryKey } from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
import { productBreakdownForCategory } from "../_lib/product-purpose-counts";
import { prepareEvaluationRequest } from "../_lib/evaluation-request";
import {
  evaluateVisaOracle,
  isVisaOracleRetryableHttpStatus,
  VisaOracleClientError,
} from "../_lib/evaluation-client";
import {
  browserEvaluationIdentityStorage,
  clearEvaluationIdentities,
  createMemoryEvaluationIdentityStorage,
  type EvaluationIdentityStorage,
} from "../_lib/evaluation-identity-store";
import { EvaluationRunCache } from "../_lib/evaluation-run-cache";
import {
  buildEngineOutcome,
  buildInternalPreviewOutcome,
} from "../_lib/engine-adapter";
import { VisaOracleResponseError } from "../_lib/engine-response";
import { buildPreviewOutcome } from "../_lib/preview-adapter";
import {
  buildClientGuardOutcome,
  buildDegradedHumanReviewOutcome,
  buildNetworkFailureOutcome,
  buildShadowOutcome,
} from "../_lib/outcome-fallbacks";
import {
  VISA_ORACLE_RESUME_TTL_MS,
  clearInterviewResume,
  loadInterviewResumeWithExpiry,
  saveInterviewResume,
  scheduleInterviewResumeCleanup,
} from "../_lib/resume-store";
import {
  emitVisaOracleTelemetry,
  nonReversibleHash,
  resolveFrontendVersion,
  type VisaOracleTelemetryState,
} from "../_lib/telemetry";
import { GOLD_ORACLE_PACK_HASH } from "../_lib/gold-oracle-baseline";
import {
  resolveVisaOracleMode,
  type VisaOracleMode,
} from "../_lib/runtime-mode";
import { shadowParityMatches } from "../_lib/shadow-parity";
import type { OutcomeViewModel } from "../_lib/outcome-view-model";
import type { VisaOracleEvaluateResponse } from "../_lib/visa-oracle-contract";
import { LivingTree } from "./LivingTree";
import { PathsCounter } from "./PathsCounter";
import { QuestionScreen } from "./QuestionScreen";
import { ConfirmationCard } from "./ConfirmationCard";
import { VerdictReveal } from "./VerdictReveal";
import { OutcomeSheet } from "./OutcomeSheet";
import { ConsentHandoff } from "./ConsentHandoff";
import { ConsultantAccess } from "./ConsultantAccess";
import { ThemeToggle, type OracleTheme } from "./ThemeToggle";
import { LanguageToggle } from "./LanguageToggle";

const HIDE_COUNTER_ON = new Set(["in_indonesia", "permit_expiry"]);

/**
 * Shown whenever a real engine decision is rendered from a non-authoritative
 * (SHADOW/`CURATED`) response. Intentionally English-only and unlocalised:
 * it addresses the internal Bali Zero tester, never a client.
 */
const INTERNAL_PREVIEW_NOTICE =
  "INTERNAL PREVIEW — engine output shown for testing. Not an authoritative answer and not cleared for a client.";

function isMinorForHandoff(
  birthDateValue: string | undefined,
  evaluatedAtIso: string | undefined,
): boolean {
  if (!birthDateValue || !evaluatedAtIso) return false;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(birthDateValue);
  const evaluatedAt = new Date(evaluatedAtIso);
  if (!match || Number.isNaN(evaluatedAt.valueOf())) return false;
  const birthYear = Number(match[1]);
  const birthMonth = Number(match[2]);
  const birthDay = Number(match[3]);
  let age = evaluatedAt.getUTCFullYear() - birthYear;
  const month = evaluatedAt.getUTCMonth() + 1;
  const day = evaluatedAt.getUTCDate();
  if (month < birthMonth || (month === birthMonth && day < birthDay)) age -= 1;
  return age >= 0 && age < 18;
}

const SESSION_COPY = {
  en: {
    loading: "Restoring your private browser session…",
    evaluating: "Checking the verified Visa Oracle engine…",
    resume:
      "Optional: save the full interview, including sensitive immigration, nationality and family answers, in this browser session for up to 2 hours. It expires while this tab stays open and can be cleared at any time.",
    resumeOptIn: "Save my interview on this device for 2 hours",
    clear: "Clear saved interview",
    retry: "Retry verified evaluation",
  },
  id: {
    loading: "Memulihkan sesi browser privat Anda…",
    evaluating: "Memeriksa mesin Visa Oracle terverifikasi…",
    resume:
      "Opsional: simpan wawancara lengkap, termasuk jawaban sensitif tentang imigrasi, kewarganegaraan, dan keluarga, dalam sesi browser ini hingga 2 jam. Data kedaluwarsa saat tab ini tetap terbuka dan dapat dihapus kapan saja.",
    resumeOptIn: "Simpan wawancara saya di perangkat ini selama 2 jam",
    clear: "Hapus wawancara tersimpan",
    retry: "Coba lagi evaluasi terverifikasi",
  },
} as const;

interface HydratedShell {
  snapshot: InterviewSnapshot | null;
  restoredAt: Date;
  resumeExpiresAtIso: string | null;
}

function validateStoredSnapshot(
  value: unknown,
  restoredAt: Date,
): InterviewSnapshot | null {
  return restoreInterviewSnapshot(value, "en", restoredAt) === null
    ? null
    : (value as InterviewSnapshot);
}

export interface OracleShellProps {
  /**
   * True only when the server has verified the signed `vo_internal` cookie
   * (see `_lib/internal-access.ts`). Decided on the server and passed down —
   * never probed from the client — so there is no window in which an unlocked
   * tester renders (and caches) the public, decision-hidden outcome.
   * Defaults to the public experience.
   */
  internalMode?: boolean;
}

/** Hydrate sessionStorage after mount so server and first client render match. */
export function OracleShell({ internalMode = false }: OracleShellProps = {}) {
  const [hydrated, setHydrated] = useState<HydratedShell | null>(null);

  useEffect(() => {
    const restoredAt = new Date();
    const restored = loadInterviewResumeWithExpiry((value) =>
      validateStoredSnapshot(value, restoredAt),
    );
    if (restored === null) clearEvaluationIdentities();
    setHydrated({
      snapshot: restored?.snapshot ?? null,
      restoredAt,
      resumeExpiresAtIso: restored?.expiresAtIso ?? null,
    });
  }, []);

  if (hydrated === null) {
    return (
      <div className="oracle-root" data-oracle-theme="light" data-funnel="visa">
        <p className="oracle-subhead" role="status" aria-live="polite">
          {SESSION_COPY.en.loading}
        </p>
      </div>
    );
  }

  return (
    <OracleShellRuntime
      initialSnapshot={hydrated.snapshot}
      restoreToday={hydrated.restoredAt}
      initialResumeExpiresAtIso={hydrated.resumeExpiresAtIso}
      internalMode={internalMode}
    />
  );
}

interface OracleShellRuntimeProps {
  initialSnapshot: InterviewSnapshot | null;
  restoreToday: Date;
  initialResumeExpiresAtIso: string | null;
  internalMode: boolean;
}

/**
 * The server unambiguously asserted `decision.state: "HUMAN_REVIEW_REQUIRED"`
 * with `outage: null` — either because we hold the fully validated response
 * (an adapter-level invariant rejected some other field) or because a
 * best-effort peek of the raw payload read it directly (strict parsing
 * rejected the payload before we could fully trust it). Either way, an
 * evaluation genuinely happened and must never be reported as "no
 * evaluation was submitted".
 */
function isKnownHumanReviewDecision(
  knownDecision: { state: string; outageIsNull: boolean } | undefined,
): boolean {
  return (
    knownDecision?.state === "HUMAN_REVIEW_REQUIRED" &&
    knownDecision.outageIsNull === true
  );
}

function fallbackForError(
  error: unknown,
  assumptions: OutcomeViewModel["assumptions"],
  knownDecision?: { state: string; outageIsNull: boolean },
): OutcomeViewModel {
  const resolvedKnownDecision =
    knownDecision ??
    (error instanceof VisaOracleClientError && error.knownDecisionState
      ? {
          state: error.knownDecisionState,
          outageIsNull: error.knownOutageIsNull === true,
        }
      : undefined);
  const degradedHumanReview = isKnownHumanReviewDecision(resolvedKnownDecision);

  if (error instanceof VisaOracleClientError) {
    const clientGuard =
      error.code === "INVALID_REQUEST" ||
      error.code === "MALFORMED_RESPONSE" ||
      (error.code === "HTTP_ERROR" &&
        error.status !== undefined &&
        error.status >= 400 &&
        error.status < 500 &&
        !isVisaOracleRetryableHttpStatus(error.status));
    if (clientGuard) {
      if (degradedHumanReview) {
        return buildDegradedHumanReviewOutcome({ assumptions });
      }
      return buildClientGuardOutcome({
        code:
          error.code === "HTTP_ERROR"
            ? `ENGINE_HTTP_${error.status ?? "ERROR"}`
            : error.code,
        assumptions,
      });
    }
    return buildNetworkFailureOutcome({
      code: error.code,
      assumptions,
      retryable: true,
    });
  }
  if (error instanceof VisaOracleResponseError) {
    if (degradedHumanReview) {
      return buildDegradedHumanReviewOutcome({ assumptions });
    }
    return buildClientGuardOutcome({ code: error.code, assumptions });
  }
  return buildClientGuardOutcome({
    code: "CLIENT_INTEGRATION_GUARD",
    assumptions,
  });
}

function telemetryForFallback(
  outcome: OutcomeViewModel,
  correlationHash: string | undefined,
): void {
  if (outcome.provenance === "CLIENT_GUARD") {
    emitVisaOracleTelemetry({
      event: "visa_oracle_v2_client_guard",
      state: outcome.state,
      correlationHash,
    });
  } else if (outcome.provenance === "NETWORK_FAILURE") {
    emitVisaOracleTelemetry({
      event: "visa_oracle_v2_network_failure",
      state: outcome.state,
      correlationHash,
    });
  }
}

function OracleShellRuntime({
  initialSnapshot,
  restoreToday,
  initialResumeExpiresAtIso,
  internalMode,
}: OracleShellRuntimeProps) {
  const [theme, setTheme] = useState<OracleTheme>("light");
  const [frozenToday, setFrozenToday] = useState<Date | null>(null);
  const [outcome, setOutcome] = useState<OutcomeViewModel | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [retryNonce, setRetryNonce] = useState(0);
  const [hasLocalResume, setHasLocalResume] = useState(
    initialSnapshot !== null,
  );
  const [resumeEnabled, setResumeEnabled] = useState(initialSnapshot !== null);
  const resumeEnabledRef = useRef(initialSnapshot !== null);
  const skipInitialResumeWriteRef = useRef(initialSnapshot !== null);
  const cancelResumeCleanupRef = useRef<(() => void) | null>(null);
  const activeControllerRef = useRef<AbortController | null>(null);
  const activeReleaseRef = useRef<(() => void) | null>(null);
  const evaluationGenerationRef = useRef(0);
  const evaluationCacheRef = useRef(new EvaluationRunCache<OutcomeViewModel>());
  const lastEvaluationKeyRef = useRef<string | null>(null);
  const memoryIdentityStorageRef = useRef<EvaluationIdentityStorage | null>(
    null,
  );
  if (memoryIdentityStorageRef.current === null) {
    memoryIdentityStorageRef.current = createMemoryEvaluationIdentityStorage();
  }
  const memoryIdentityStorage = memoryIdentityStorageRef.current;
  const mode = useMemo<VisaOracleMode>(() => resolveVisaOracleMode(), []);
  const reducedMotion = useReducedMotion();

  const clearAllEvaluationIdentities = useCallback(() => {
    clearEvaluationIdentities(memoryIdentityStorage);
    clearEvaluationIdentities();
  }, [memoryIdentityStorage]);

  const expireResumePersistence = useCallback(() => {
    cancelResumeCleanupRef.current = null;
    clearAllEvaluationIdentities();
    resumeEnabledRef.current = false;
    setResumeEnabled(false);
    setHasLocalResume(false);
  }, [clearAllEvaluationIdentities]);

  const scheduleResumeCleanup = useCallback(
    (expiresAtIso: string) => {
      cancelResumeCleanupRef.current?.();
      cancelResumeCleanupRef.current = scheduleInterviewResumeCleanup(
        expiresAtIso,
        { onExpired: expireResumePersistence },
      );
    },
    [expireResumePersistence],
  );

  const disableResumePersistence = useCallback(() => {
    cancelResumeCleanupRef.current?.();
    cancelResumeCleanupRef.current = null;
    clearInterviewResume();
    clearAllEvaluationIdentities();
    resumeEnabledRef.current = false;
    setResumeEnabled(false);
    setHasLocalResume(false);
  }, [clearAllEvaluationIdentities]);

  const saveSnapshot = useCallback(
    (snapshot: InterviewSnapshot) => {
      if (skipInitialResumeWriteRef.current) {
        skipInitialResumeWriteRef.current = false;
        return;
      }
      if (!resumeEnabledRef.current) return;
      const savedAt = new Date();
      if (!saveInterviewResume(snapshot, { now: savedAt })) {
        disableResumePersistence();
        return;
      }
      setHasLocalResume(true);
      scheduleResumeCleanup(
        new Date(savedAt.getTime() + VISA_ORACLE_RESUME_TTL_MS).toISOString(),
      );
    },
    [disableResumePersistence, scheduleResumeCleanup],
  );

  const flow = useOracleFlow({
    initialSnapshot: initialSnapshot ?? undefined,
    onSnapshot: saveSnapshot,
    restoreToday,
  });
  const {
    state,
    current,
    assumptions,
    interviewBranchesRemaining,
    canGoBack,
    answer,
    skip,
    advance,
    back,
    edit,
    selectCategory,
    reviewAnswers,
    restart,
    setLanguage,
  } = flow;
  const language = state.language;
  const sessionCopy = SESSION_COPY[language];

  useEffect(() => {
    if (initialResumeExpiresAtIso !== null) {
      scheduleResumeCleanup(initialResumeExpiresAtIso);
    }
    return () => cancelResumeCleanupRef.current?.();
  }, [initialResumeExpiresAtIso, scheduleResumeCleanup]);

  const cancelEvaluation = useCallback(() => {
    evaluationGenerationRef.current += 1;
    activeControllerRef.current?.abort();
    activeControllerRef.current = null;
    activeReleaseRef.current?.();
    activeReleaseRef.current = null;
  }, []);

  const leaveOutcome = useCallback(() => {
    cancelEvaluation();
    const key = lastEvaluationKeyRef.current;
    if (key) evaluationCacheRef.current.invalidate(key);
    lastEvaluationKeyRef.current = null;
    clearAllEvaluationIdentities();
    setEvaluating(false);
    setOutcome(null);
    setFrozenToday(null);
  }, [cancelEvaluation, clearAllEvaluationIdentities]);

  const startInterview = useCallback(() => {
    advance();
  }, [advance]);

  const clearSavedInterview = useCallback(() => {
    disableResumePersistence();
  }, [disableResumePersistence]);

  const handleResumeOptIn = useCallback(
    (enabled: boolean) => {
      if (!enabled) {
        disableResumePersistence();
        return;
      }
      resumeEnabledRef.current = true;
      setResumeEnabled(true);
    },
    [disableResumePersistence],
  );

  const handleEdit = useCallback(
    (questionId: string) => {
      leaveOutcome();
      edit(questionId);
    },
    [edit, leaveOutcome],
  );

  const handleSelectCategory = useCallback(
    (category: string) => {
      leaveOutcome();
      selectCategory(category);
    },
    [leaveOutcome, selectCategory],
  );

  const handleReviewAnswers = useCallback(() => {
    leaveOutcome();
    reviewAnswers();
  }, [leaveOutcome, reviewAnswers]);

  const handleRestart = useCallback(() => {
    leaveOutcome();
    disableResumePersistence();
    evaluationCacheRef.current.clear();
    lastEvaluationKeyRef.current = null;
    restart();
  }, [disableResumePersistence, leaveOutcome, restart]);

  const revealVerdict = useCallback(() => {
    const assessmentClock = new Date();
    setFrozenToday(assessmentClock);
    setOutcome(null);
    const startViewTransition = (
      document as Document & {
        startViewTransition?: (callback: () => void) => unknown;
      }
    ).startViewTransition;
    if (reducedMotion || !startViewTransition) {
      advance();
      return;
    }
    startViewTransition.call(document, () => {
      flushSync(() => advance());
    });
  }, [advance, reducedMotion]);

  useEffect(() => {
    if (current.kind === "verdict" && frozenToday === null) {
      setFrozenToday(new Date());
    }
  }, [current.kind, frozenToday]);

  useEffect(() => {
    if (current.kind !== "verdict" || frozenToday === null) return;

    const generation = evaluationGenerationRef.current + 1;
    evaluationGenerationRef.current = generation;
    const controller = new AbortController();
    activeControllerRef.current?.abort();
    activeControllerRef.current = controller;
    setEvaluating(true);
    setOutcome(null);

    if (mode === "OFF") {
      setOutcome(
        buildClientGuardOutcome({
          code: "ENGINE_MODE_OFF",
          assumptions,
        }),
      );
      setEvaluating(false);
      return () => controller.abort();
    }
    if (mode === "PREVIEW") {
      setOutcome(buildPreviewOutcome(state.facts, frozenToday));
      setEvaluating(false);
      return () => controller.abort();
    }

    let cacheKey: string | null = null;
    let releaseLease: (() => void) | null = null;
    const run = async () => {
      try {
        const browserIdentityStorage = resumeEnabledRef.current
          ? browserEvaluationIdentityStorage()
          : null;
        const prepared = await prepareEvaluationRequest({
          facts: state.facts,
          attempt: state.attempt,
          now: frozenToday,
          storage: browserIdentityStorage ?? memoryIdentityStorage,
        });
        if (controller.signal.aborted) return;
        let telemetryCorrelationHash: string | undefined;
        try {
          telemetryCorrelationHash = await nonReversibleHash(
            prepared.identity.assessmentId,
          );
        } catch {
          // A missing correlator is safer than hashing structured applicant data.
        }
        // `internalMode` is part of the key: the same interview renders a
        // different outcome for an unlocked tester, so a cached public result
        // must never be replayed into the internal preview (or vice versa).
        cacheKey = `${mode}:${internalMode ? "internal" : "public"}:${state.attempt}:${prepared.evaluationHash}`;
        lastEvaluationKeyRef.current = cacheKey;
        const lease = evaluationCacheRef.current.acquire(
          cacheKey,
          async (requestSignal) => {
            // Hoisted so the catch block below can read the already-validated
            // decision.state/outage when a LATER step (buildEngineOutcome)
            // throws — needed to tell "no evaluation was submitted" apart
            // from "an evaluation was submitted and flagged for human
            // review, but we couldn't render every detail safely".
            let response: VisaOracleEvaluateResponse | undefined;
            try {
              response = await evaluateVisaOracle({
                request: prepared.request,
                idempotencyKey: prepared.identity.idempotencyKey,
                signal: requestSignal,
              });
              // Internal (PIN-unlocked) tester: show the REAL engine decision
              // even while the backend answers SHADOW/`mode:"CURATED"`, which
              // already carries the full decision. Checked BEFORE the
              // frontend's own SHADOW branch, which would otherwise swallow
              // the decision the tester unlocked specifically to see. The
              // public paths below are deliberately left untouched — their
              // fail-closed behaviour on a mode mismatch is an invariant, not
              // an accident, and is pinned by OracleShell.test.tsx.
              if (internalMode) {
                const previewOutcome = buildInternalPreviewOutcome(response, {
                  assumptions,
                  facts: state.facts,
                  interviewBranchesRemaining,
                });
                emitVisaOracleTelemetry({
                  event: "visa_oracle_v2_engine_result",
                  state: previewOutcome.state,
                  correlationHash: telemetryCorrelationHash,
                });
                return previewOutcome;
              }

              if (mode === "SHADOW") {
                const preview = buildPreviewOutcome(state.facts, frozenToday);
                emitVisaOracleTelemetry({
                  event: shadowParityMatches(response, preview)
                    ? "visa_oracle_v2_parity_match"
                    : "visa_oracle_v2_parity_mismatch",
                  state: response.decision.state,
                  correlationHash: telemetryCorrelationHash,
                  packHash: GOLD_ORACLE_PACK_HASH,
                  frontendVersion: resolveFrontendVersion(),
                });
                return buildShadowOutcome({
                  code: "SHADOW_VERIFICATION_ONLY",
                  assumptions,
                });
              }

              const engineOutcome = buildEngineOutcome(response, {
                assumptions,
                facts: state.facts,
                interviewBranchesRemaining,
              });
              emitVisaOracleTelemetry({
                event: "visa_oracle_v2_engine_result",
                state: engineOutcome.state,
                correlationHash: telemetryCorrelationHash,
              });
              return engineOutcome;
            } catch (error) {
              if (
                requestSignal.aborted ||
                (error instanceof VisaOracleClientError &&
                  error.code === "ABORTED")
              ) {
                throw error;
              }
              if (mode === "SHADOW") {
                return buildShadowOutcome({
                  code: "SHADOW_VERIFICATION_UNAVAILABLE",
                  assumptions,
                });
              }
              const knownDecision =
                response !== undefined
                  ? {
                      state: response.decision.state,
                      outageIsNull: response.decision.outage === null,
                    }
                  : undefined;
              const fallback = fallbackForError(
                error,
                assumptions,
                knownDecision,
              );
              telemetryForFallback(fallback, telemetryCorrelationHash);
              return fallback;
            }
          },
        );
        releaseLease = lease.release;
        activeReleaseRef.current = releaseLease;

        const nextOutcome = await lease.promise;
        if (
          controller.signal.aborted ||
          evaluationGenerationRef.current !== generation
        ) {
          return;
        }
        setOutcome(nextOutcome);
        setEvaluating(false);
      } catch (error) {
        if (
          controller.signal.aborted ||
          evaluationGenerationRef.current !== generation ||
          (error instanceof VisaOracleClientError && error.code === "ABORTED")
        ) {
          return;
        }
        const fallback = fallbackForError(error, assumptions);
        setOutcome(fallback);
        setEvaluating(false);
      }
    };
    void run();

    return () => {
      controller.abort();
      releaseLease?.();
      if (activeReleaseRef.current === releaseLease) {
        activeReleaseRef.current = null;
      }
      if (activeControllerRef.current === controller) {
        activeControllerRef.current = null;
      }
    };
  }, [
    assumptions,
    current.kind,
    frozenToday,
    internalMode,
    interviewBranchesRemaining,
    mode,
    memoryIdentityStorage,
    retryNonce,
    state.attempt,
    state.facts,
  ]);

  useEffect(() => {
    if (!outcome) return;
    const retryable =
      outcome.state === "TEMPORARILY_UNAVAILABLE" && outcome.outage.retryable;
    if (retryable) return;
    disableResumePersistence();
  }, [disableResumePersistence, outcome]);

  useEffect(
    () => () => {
      activeControllerRef.current?.abort();
    },
    [],
  );

  const retryEvaluation = useCallback(() => {
    const key = lastEvaluationKeyRef.current;
    if (key) evaluationCacheRef.current.invalidate(key);
    // An explicit product retry is a new evaluation, not an HTTP replay of a
    // cached TEMP response. Automatic transport retries stay inside the client
    // and preserve their original body/key.
    clearAllEvaluationIdentities();
    setOutcome(null);
    setRetryNonce((value) => value + 1);
  }, [clearAllEvaluationIdentities]);

  const lane = useMemo(() => getLane(state.facts), [state.facts]);
  // The real, pack-and-tier-sourced breakdown for the selected category
  // (`product-purpose-counts.ts`) — `undefined` while no category is chosen
  // yet or the NotSure affordance left it `"unsure"` (matches the same
  // undefined/"unsure" guard `fact-mapper.ts` uses for this field), `null`
  // when the category has no honest breakdown (diaspora). PathsCounter only
  // renders it once the interview has narrowed to a single branch.
  const productBreakdown = useMemo(() => {
    const category = state.facts.category;
    if (category === undefined || category === "unsure") return undefined;
    return productBreakdownForCategory(category as CategoryKey);
  }, [state.facts.category]);
  const outcomeAssessmentReference =
    outcome?.provenance === "ENGINE" ? outcome.assessment.publicId : undefined;
  const guardianConsentRequired = isMinorForHandoff(
    state.facts.birth_date,
    outcome?.provenance === "ENGINE"
      ? outcome.assessment.evaluatedAtIso
      : restoreToday.toISOString(),
  );

  return (
    <div
      className="oracle-root"
      data-oracle-theme={theme}
      data-funnel="visa"
      data-internal-preview={internalMode ? "true" : undefined}
    >
      <div className="oracle-shell">
        {internalMode && (
          // Anyone shown a real engine decision must be told, on the same
          // screen, that it is an internal preview and not an answer that has
          // been cleared for a client.
          <p
            className="oracle-question__hint"
            role="status"
            style={{ fontWeight: 600 }}
          >
            {INTERNAL_PREVIEW_NOTICE}
          </p>
        )}
        <header className="oracle-topbar">
          <span
            className="oracle-badge"
            title={translate(language, "prototype.badge.detail")}
          >
            {translate(language, "prototype.badge")}
          </span>
          <div className="oracle-topbar__actions">
            {/* Contract C3 (FROZEN.md): present on every screen, invokable
             * at any moment. Mounted once here rather than once per screen
             * type — `oracle-topbar` already renders unconditionally for
             * every `current.kind` below, so "ever-present" holds by
             * construction. `outcome?.state` is undefined on every screen
             * before a verdict exists (framing, every question,
             * confirmation); `ConsultantAccess` reports that honestly as
             * "IN_PROGRESS" rather than reusing a stale or guessed state. */}
            <ConsultantAccess
              language={language}
              state={outcome?.state as VisaOracleTelemetryState | undefined}
              assessmentReference={outcomeAssessmentReference}
              guardianConsentRequired={guardianConsentRequired}
            />
            {hasLocalResume && (
              <button
                type="button"
                className="oracle-question__back"
                onClick={clearSavedInterview}
              >
                {sessionCopy.clear}
              </button>
            )}
            <LanguageToggle language={language} onChange={setLanguage} />
            <ThemeToggle
              language={language}
              theme={theme}
              onChange={setTheme}
            />
          </div>
        </header>

        <main className="oracle-main">
          <div className="oracle-main__tree">
            <LivingTree
              language={language}
              current={current}
              facts={state.facts}
              onEditQuestion={handleEdit}
            />
          </div>

          <div className="oracle-main__content">
            {current.kind === "question" &&
              !HIDE_COUNTER_ON.has(current.questionId) && (
                <div style={{ marginBottom: "var(--space-4)" }}>
                  <PathsCounter
                    language={language}
                    count={interviewBranchesRemaining}
                    visible
                    productBreakdown={productBreakdown}
                  />
                </div>
              )}

            {current.kind === "framing" && (
              <div className="oracle-question">
                <h1 className="oracle-headline" tabIndex={-1}>
                  {translate(language, "framing.title")}
                </h1>
                <p className="oracle-subhead">
                  {translate(language, "framing.body")}
                </p>
                <p className="oracle-question__hint">{sessionCopy.resume}</p>
                <label className="oracle-checklist__item">
                  <input
                    type="checkbox"
                    checked={resumeEnabled}
                    onChange={(event) =>
                      handleResumeOptIn(event.currentTarget.checked)
                    }
                  />
                  {sessionCopy.resumeOptIn}
                </label>
                <button
                  type="button"
                  className="oracle-option-card"
                  style={{ width: "fit-content" }}
                  onClick={startInterview}
                >
                  {translate(language, "framing.cta")}
                  <ArrowRight aria-hidden="true" size={18} />
                </button>
              </div>
            )}

            {current.kind === "question" && (
              <QuestionScreen
                key={current.questionId}
                language={language}
                question={QUESTIONS[current.questionId]}
                onAnswer={(value) => answer(current.questionId, value)}
                onSkip={() => skip(current.questionId)}
                onBack={back}
                canGoBack={canGoBack}
                noticeI18nKey={noticeFor(current.questionId, lane)}
                conflictI18nKey={conflictNoticeFor(
                  current.questionId,
                  state.blockedAnswer,
                )}
                currentAnswer={state.facts[current.questionId]}
              />
            )}

            {current.kind === "confirmation" && (
              <ConfirmationCard
                language={language}
                facts={state.facts}
                assumptions={assumptions}
                interviewBranchesRemaining={interviewBranchesRemaining}
                onBack={back}
                onEdit={handleEdit}
                onConfirm={revealVerdict}
              />
            )}

            {current.kind === "verdict" &&
              (evaluating || outcome === null ? (
                <div
                  className="oracle-verdict-card"
                  role="status"
                  aria-live="polite"
                >
                  <p className="oracle-subhead">{sessionCopy.evaluating}</p>
                </div>
              ) : (
                <>
                  <VerdictReveal
                    language={language}
                    state={outcome.state}
                    provenance={outcome.provenance}
                    legalStatus={outcome.candidates[0]?.legal.status}
                  />
                  <OutcomeSheet
                    language={language}
                    outcome={outcome}
                    facts={state.facts}
                    onSelectCategory={handleSelectCategory}
                    onEditMissingInput={handleEdit}
                    handoffSlot={
                      <ConsentHandoff
                        language={language}
                        state={outcome.state as VisaOracleTelemetryState}
                        assessmentReference={outcomeAssessmentReference}
                        guardianConsentRequired={guardianConsentRequired}
                      />
                    }
                  />
                  <div
                    className="oracle-no-print"
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: "var(--space-4)",
                      marginTop: "var(--space-6)",
                    }}
                  >
                    {outcome.state === "TEMPORARILY_UNAVAILABLE" &&
                      outcome.outage.retryable && (
                        <button
                          type="button"
                          className="oracle-option-card"
                          onClick={retryEvaluation}
                        >
                          {sessionCopy.retry}
                        </button>
                      )}
                    <button
                      type="button"
                      className="oracle-question__back"
                      onClick={handleReviewAnswers}
                    >
                      {translate(language, "verdict.edit_answers" as I18nKey)}
                    </button>
                    <button
                      type="button"
                      className="oracle-question__back"
                      onClick={handleRestart}
                    >
                      {translate(language, "restart.button")}
                    </button>
                  </div>
                </>
              ))}
          </div>
        </main>

        <footer className="oracle-footer">
          <p>{translate(language, "footer.disclaimer")}</p>
          <a href="/visa-oracle/privacy">
            {translate(language, "footer.privacy")}
          </a>
        </footer>
      </div>
    </div>
  );
}

function noticeFor(
  questionId: string,
  lane: ReturnType<typeof getLane>,
): I18nKey | undefined {
  if (questionId === "category" && lane)
    return `lane.${lane}.notice` as I18nKey;
  if (
    questionId === "review_gate" &&
    (lane === "expired" || lane === "urgent")
  ) {
    return `lane.${lane}.notice` as I18nKey;
  }
  return undefined;
}

/** Surfaces `FlowState.blockedAnswer` on the exact question screen it
 * blocked — `q.<questionId>.conflict` follows the same `q.<id>.hint` /
 * `q.<id>.why` naming convention every other question-scoped key uses. */
function conflictNoticeFor(
  questionId: string,
  blockedAnswer: BlockedAnswer | null,
): I18nKey | undefined {
  if (blockedAnswer?.questionId !== questionId) return undefined;
  return `q.${questionId}.conflict` as I18nKey;
}
