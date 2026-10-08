"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { flushSync } from "react-dom";
import { MessageCircle } from "lucide-react";
import { useReducedMotion } from "framer-motion";
import {
  restoreInterviewSnapshot,
  useOracleFlow,
  type BlockedAnswer,
  type InterviewSnapshot,
} from "../_lib/flow";
import { CATEGORY_KEYS, QUESTIONS, getLane } from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
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
  isSecondHomeStudioOnly,
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
import {
  ATLAS_ASSET_BASE,
  atlasCopy,
  isAtlasCategoryKey,
  projectAtlasScene,
} from "../_lib/atlas-scenes";
import { QuestionScreen } from "./QuestionScreen";
import { ConfirmationCard } from "./ConfirmationCard";
import { VerdictReveal } from "./VerdictReveal";
import { OutcomeSheet } from "./OutcomeSheet";
import { ConsentHandoff, type ConsentHandoffProps } from "./ConsentHandoff";
import { ThemeToggle, type OracleTheme } from "./ThemeToggle";
import { LanguageToggle } from "./LanguageToggle";
import { AtlasBranchCaption, AtlasGlyph, OracleScenery } from "./OracleScenery";
import { AtlasRoute, type AtlasRouteHandle } from "./AtlasRoute";

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
    consultant: "Talk to a consultant",
    loading: "Restoring your private browser session…",
    evaluating: "Checking the verified Visa Oracle engine…",
    resume:
      "Optional: save the full interview, including sensitive immigration, nationality and family answers, in this browser session for up to 2 hours. It expires while this tab stays open and can be cleared at any time.",
    resumeOptIn: "Save my interview on this device for 2 hours",
    clear: "Clear saved interview",
    retry: "Retry verified evaluation",
  },
  id: {
    consultant: "Bicara dengan konsultan",
    loading: "Memulihkan sesi browser privat Anda…",
    evaluating: "Memeriksa mesin Visa Oracle terverifikasi…",
    resume:
      "Opsional: simpan wawancara lengkap, termasuk jawaban sensitif tentang imigrasi, kewarganegaraan, dan keluarga, dalam sesi browser ini hingga 2 jam. Data kedaluwarsa saat tab ini tetap terbuka dan dapat dihapus kapan saja.",
    resumeOptIn: "Simpan wawancara saya di perangkat ini selama 2 jam",
    clear: "Hapus wawancara tersimpan",
    retry: "Coba lagi evaluasi terverifikasi",
  },
} as const;

function ConsultantContact(props: ConsentHandoffProps) {
  const [open, setOpen] = useState(props.context === "ASSESSMENT");
  const toggleRef = useRef<HTMLButtonElement>(null);

  return (
    <div
      className="oracle-consultant oracle-no-print"
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.preventDefault();
          setOpen(false);
          toggleRef.current?.focus();
        }
      }}
    >
      <button
        ref={toggleRef}
        id="oracle-consultant-toggle"
        type="button"
        className="oracle-question__back oracle-consultant__toggle"
        aria-expanded={open}
        aria-controls="oracle-consultant-panel"
        onClick={() => setOpen((value) => !value)}
      >
        <MessageCircle aria-hidden="true" size={18} />
        {SESSION_COPY[props.language].consultant}
      </button>
      <div
        id="oracle-consultant-panel"
        className="oracle-handoff-slot oracle-consultant__panel"
        role="region"
        aria-labelledby="oracle-consultant-toggle"
        hidden={!open}
      >
        <ConsentHandoff {...props} />
      </div>
    </div>
  );
}

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
      <div
        className="oracle-root oracle-atlas"
        data-oracle-theme="light"
        data-funnel="visa"
        data-scene="entry"
        data-scene-layout="stage"
      >
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
    // NON_ENGINE_MODE is not a guard failure and must not borrow the
    // guard's copy. It means the server answered normally with
    // `mode: "CURATED"` -- an evaluation genuinely happened, was sealed
    // and was persisted -- and `requireEngineResponse` declined to render
    // it as authority because public enforcement is off. Saying "No
    // evaluation was submitted" to that visitor states the opposite of
    // what occurred, and blames their interview for a server-side
    // configuration they cannot see or influence.
    //
    // This is the rule `buildDegradedHumanReviewOutcome`'s own comment in
    // outcome-fallbacks.ts already states: the "no evaluation was
    // submitted" claim "must stay reserved for
    // TEMPORARILY_UNAVAILABLE/network/parse failures" -- cases where the
    // evaluation really did not happen. NON_ENGINE_MODE is not one of
    // them; MALFORMED_RESPONSE and RESPONSE_INVARIANT are, because there
    // the payload could not be trusted at all.
    //
    // The public rendering boundary is untouched: buildShadowOutcome
    // returns TEMPORARILY_UNAVAILABLE with no candidates, exactly as the
    // guard outcome did. A CURATED decision still never becomes visible
    // authority. Only the sentence the visitor reads changes, from a
    // false one to a true one -- and to the same sentence the explicit
    // SHADOW branch below already shows for this identical situation.
    if (error.code === "NON_ENGINE_MODE") {
      return buildShadowOutcome({
        code: "SHADOW_VERIFICATION_ONLY",
        assumptions,
      });
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

  // Presentational-only state (BUILD-SPEC §6): never read by the reducer,
  // evaluation effect or any consent/telemetry logic below — scenery and its
  // controls never decide or gate anything the interview does.
  const [previewCategory, setPreviewCategory] = useState<string | null>(null);
  // FIX-ROUND-2 K2: the projection that actually swaps `OracleScenery`'s
  // asset (and therefore fires an image request) is debounced 150ms behind
  // the raw hover/focus signal above, so five rapid tile previews resolve
  // into at most one asset request/projection instead of one per tile.
  const [debouncedPreviewCategory, setDebouncedPreviewCategory] = useState<
    string | null
  >(null);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedPreviewCategory(previewCategory);
    }, 150);
    return () => window.clearTimeout(timer);
  }, [previewCategory]);
  const [motionPaused, setMotionPaused] = useState(false);
  const motion = !reducedMotion && !motionPaused;
  const routeDialogRef = useRef<AtlasRouteHandle>(null);
  const resumeDescriptionId = useId();
  const resumeCheckboxId = useId();

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
    askFollowUp,
    selectCategory,
    reviewAnswers,
    restart,
    setLanguage,
  } = flow;
  const language = state.language;
  const sessionCopy = SESSION_COPY[language];

  const scene = useMemo(
    () =>
      projectAtlasScene(
        current,
        state.facts,
        current.kind === "question" && current.questionId === "category"
          ? debouncedPreviewCategory
          : null,
      ),
    [current, state.facts, debouncedPreviewCategory],
  );

  // One question/step key (BUILD-SPEC §6): reset the watershed hover
  // preview and scroll to the top of the new screen. `document.
  // documentElement.scrollTop` (not `window.scrollTo`) because jsdom has no
  // layout and `window.scrollTo` is pure noise there (invariant §0.3 tests).
  const stepKey =
    current.kind + (current.kind === "question" ? current.questionId : "");
  useEffect(() => {
    setPreviewCategory(null);
    setDebouncedPreviewCategory(null);
    document.documentElement.scrollTop = 0;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepKey]);

  // "Your route" only once the interview has something to recap — mirrors
  // AtlasRoute's own ledger membership test (a question actually recorded a
  // fact, not merely visited in history).
  const hasAnsweredQuestion = useMemo(
    () =>
      state.history.some(
        (node) =>
          node.kind === "question" &&
          state.facts[node.questionId] !== undefined,
      ),
    [state.history, state.facts],
  );

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

  /**
   * NEEDS_INPUT follow-up (2026-09-06): the engine named a fact whose
   * question this interview never asked. Append it and re-evaluate —
   * `leaveOutcome` drops the cached decision so the answer produces a
   * fresh evaluation rather than replaying the one that asked for it.
   * Deliberately NOT `handleEdit`: `EDIT` on an absent target resets the
   * entire interview (flow.ts's `EDIT` case), which would throw away every
   * answer in order to collect one.
   */
  const handleAskFollowUp = useCallback(
    (questionId: string) => {
      leaveOutcome();
      askFollowUp(questionId);
    },
    [askFollowUp, leaveOutcome],
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
    // F3 fix (ORACLE-PROD-20260927 delta, gate finding 3): this used to
    // gate only on the OS's own `reducedMotion` signal, so pressing the
    // in-app Pause control (`motionPaused`) left the verdict transition
    // running anyway. `motion` is the SAME effective flag the rest of the
    // shell already reads (`!reducedMotion && !motionPaused`) — gating on
    // it here keeps Pause and the OS setting equally authoritative.
    if (!motion || !startViewTransition) {
      advance();
      return;
    }
    startViewTransition.call(document, () => {
      flushSync(() => advance());
    });
  }, [advance, motion]);

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
                  editableQuestionIds: state.history.flatMap((node) =>
                    node.kind === "question" ? [node.questionId] : [],
                  ),
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
                editableQuestionIds: state.history.flatMap((node) =>
                  node.kind === "question" ? [node.questionId] : [],
                ),
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
    state.history,
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
  // Leaving a verdict or starting/retrying evaluation clears outcome before contact renders.
  const outcomeAssessmentReference =
    outcome?.provenance === "ENGINE" ? outcome.assessment.publicId : undefined;
  const guardianConsentRequired = isMinorForHandoff(
    state.facts.birth_date,
    outcome?.provenance === "ENGINE"
      ? outcome.assessment.evaluatedAtIso
      : restoreToday.toISOString(),
  );

  const isStageQuestion =
    current.kind === "question" &&
    (current.questionId === "in_indonesia" ||
      current.questionId === "holds_stay_permit");
  const eyebrowText =
    current.kind === "question" && state.pendingFollowUp === current.questionId
      ? atlasCopy(language, "scene.follow_up")
      : scene.labelKey
        ? atlasCopy(language, scene.labelKey)
        : "";

  return (
    <div
      className="oracle-root oracle-atlas"
      data-oracle-theme={theme}
      data-funnel="visa"
      data-internal-preview={internalMode ? "true" : undefined}
      data-scene={scene.id}
      data-scene-layout={scene.layout}
      data-motion={motion ? "on" : "paused"}
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
        <header className="oracle-topbar oracle-atlas-header">
          <div className="oracle-atlas-brand">
            <img src={`${ATLAS_ASSET_BASE}logo.webp`} alt="" />
            <b>BALI ZERO</b>
          </div>
          {/* ENDING-ROUND scope extension: the `title` tooltip exposed
              "Only deterministic engine outcomes may appear as supported
              paths" — engine-jargon, on a badge whose own visible text
              ("Visa decision support") is unchanged. The i18n key stays
              (BUILD-SPEC keys-stay contract); only this attribute goes. */}
          <span className="oracle-badge">
            {translate(language, "prototype.badge")}
          </span>
          <div className="oracle-atlas-header__wordmark" aria-hidden="true">
            Visa <em>Oracle</em>
          </div>
          <div className="oracle-topbar__actions">
            {current.kind !== "framing" && hasAnsweredQuestion && (
              <button
                type="button"
                className="oracle-question__back"
                onClick={(event) =>
                  routeDialogRef.current?.open(event.currentTarget)
                }
              >
                {atlasCopy(language, "tools.route")}
              </button>
            )}
            {/* FIX-ROUND-2 S2: when the OS already asks for reduced motion,
                motion is already off — a Pause/Resume toggle over it is a
                no-op control. Otherwise the label itself communicates state
                (Pause motion ⇄ Resume motion), so no `aria-pressed`. */}
            {!reducedMotion && (
              <button
                type="button"
                className="oracle-question__back"
                onClick={() => setMotionPaused((value) => !value)}
              >
                {atlasCopy(
                  language,
                  motionPaused ? "tools.resume" : "tools.pause",
                )}
              </button>
            )}
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
          {/* D3: a compact floating tool anchored to the header itself (not
              a full-width strip in the document flow) so it never pushes
              the scene down. Same component/props as before — only the
              wrapper and its position are new. Once an outcome exists the
              "plan this with Bali Zero" card renders inline below instead
              (unchanged). */}
          {!outcome && (
            <div className="oracle-atlas-consult-float">
              <ConsultantContact
                key="consultation"
                language={language}
                guardianConsentRequired={guardianConsentRequired}
                context="CONSULTATION"
              />
            </div>
          )}
        </header>

        <main className="oracle-main oracle-atlas-main">
          <OracleScenery scene={scene} motion={motion} language={language} />

          <div className="oracle-main__content">
            {current.kind === "framing" && (
              <div className="oracle-atlas-entry">
                <h1
                  className="oracle-headline oracle-atlas-entry__title"
                  tabIndex={-1}
                >
                  Visa <em>Oracle</em>
                </h1>
                {/* Existing test pins `getByRole("heading", { name:
                    translate(lang,"framing.title") })` (OracleShell.test.tsx
                    "offers generic contact during framing…") — an h2 keeps
                    that accessible name AND role while the h1 above carries
                    the wordmark, per BUILD-SPEC §6. */}
                <h2 className="oracle-atlas-entry__subtitle">
                  {translate(language, "framing.title")}
                </h2>
                <p className="oracle-atlas-entry__body">
                  {translate(language, "framing.body")}
                </p>
                <button
                  type="button"
                  className="oracle-atlas-start"
                  onClick={startInterview}
                >
                  <span
                    className="oracle-atlas-start__dot"
                    aria-hidden="true"
                  />
                  {translate(language, "framing.cta")}
                  <span aria-hidden="true"> →</span>
                </button>
                {/* FIX-ROUND-2 S3: the checkbox's accessible name is ONLY
                    the short opt-in text — the full resume sentence is a
                    separate, always-visible description (`aria-describedby`)
                    rather than folded into the label, which used to make the
                    accessible name the whole paragraph. */}
                <div className="oracle-atlas-save">
                  <input
                    id={resumeCheckboxId}
                    type="checkbox"
                    checked={resumeEnabled}
                    aria-describedby={resumeDescriptionId}
                    onChange={(event) =>
                      handleResumeOptIn(event.currentTarget.checked)
                    }
                  />
                  <span>
                    <label htmlFor={resumeCheckboxId}>
                      {sessionCopy.resumeOptIn}
                    </label>
                    <small id={resumeDescriptionId}>{sessionCopy.resume}</small>
                  </span>
                </div>
              </div>
            )}

            {current.kind === "question" && isStageQuestion && (
              <div className="oracle-atlas-stage-wordmark" aria-hidden="true">
                Visa <em>Oracle</em>
              </div>
            )}

            {current.kind === "question" && !isStageQuestion && (
              <p className="oracle-atlas-eyebrow">{eyebrowText}</p>
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
                presentation={
                  current.questionId === "in_indonesia"
                    ? "world"
                    : current.questionId === "holds_stay_permit"
                      ? "permit"
                      : current.questionId === "category"
                        ? "watershed"
                        : "default"
                }
                onPreviewOption={
                  current.questionId === "category"
                    ? setPreviewCategory
                    : undefined
                }
                noticeI18nKey={noticeFor(current.questionId, lane)}
                conflictI18nKey={conflictNoticeFor(
                  current.questionId,
                  state.blockedAnswer,
                )}
                currentAnswer={state.facts[current.questionId]}
                facts={state.facts}
              />
            )}

            {current.kind === "confirmation" && (
              <>
                <p className="oracle-atlas-eyebrow">{eyebrowText}</p>
                <div className="oracle-atlas-ribbon" aria-hidden="true">
                  <span />
                  <AtlasGlyph category={state.facts.category ?? "other"} />
                  <span />
                </div>
                <ConfirmationCard
                  language={language}
                  facts={state.facts}
                  assumptions={assumptions}
                  interviewBranchesRemaining={interviewBranchesRemaining}
                  onBack={back}
                  onEdit={handleEdit}
                  onConfirm={revealVerdict}
                />
              </>
            )}

            {current.kind === "verdict" && (
              <>
                <p className="oracle-atlas-eyebrow">{eyebrowText}</p>
                {evaluating || outcome === null ? (
                  <div
                    className="oracle-verdict-card"
                    role="status"
                    aria-live="polite"
                  >
                    <p className="oracle-subhead">{sessionCopy.evaluating}</p>
                    <span className="oracle-atlas-orbit" aria-hidden="true" />
                  </div>
                ) : (
                  <>
                    <VerdictReveal
                      language={language}
                      state={outcome.state}
                      provenance={outcome.provenance}
                      legalStatus={outcome.candidates[0]?.legal.status}
                      isSecondHomeStudioOnly={isSecondHomeStudioOnly(outcome)}
                    />
                    <OutcomeSheet
                      language={language}
                      outcome={outcome}
                      facts={state.facts}
                      onSelectCategory={handleSelectCategory}
                      onEditMissingInput={handleEdit}
                      onAskMissingInput={handleAskFollowUp}
                    />
                    <ConsultantContact
                      key="assessment"
                      language={language}
                      guardianConsentRequired={guardianConsentRequired}
                      context="ASSESSMENT"
                      state={outcome.state as VisaOracleTelemetryState}
                      assessmentReference={outcomeAssessmentReference}
                    />
                    <div className="oracle-no-print oracle-atlas-actions">
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
                    <details className="oracle-atlas-alternatives oracle-no-print">
                      <summary>{atlasCopy(language, "tools.explore")}</summary>
                      <div>
                        {CATEGORY_KEYS.filter(
                          (category) => category !== state.facts.category,
                        ).map((category) => (
                          <button
                            type="button"
                            key={category}
                            onClick={() => handleSelectCategory(category)}
                          >
                            {translate(
                              language,
                              `q.category.opt.${category}` as I18nKey,
                            )}
                            <span aria-hidden="true"> ↗</span>
                          </button>
                        ))}
                      </div>
                    </details>
                  </>
                )}
              </>
            )}
          </div>

          {/* FIX-ROUND-2 A7: a direct child of `<main>`, not of
              `.oracle-main__content` — that column is `position:relative`
              in the landscape layout, so the caption's `right`/`top`
              percentages used to resolve against its ~610px width instead
              of the full-width stage/scene box. */}
          {current.kind === "question" &&
            !isStageQuestion &&
            (current.questionId === "category" ? (
              <AtlasBranchCaption
                category={previewCategory}
                language={language}
                hub
              />
            ) : (
              isAtlasCategoryKey(state.facts.category) && (
                <AtlasBranchCaption
                  category={state.facts.category}
                  language={language}
                />
              )
            ))}
        </main>

        <footer className="oracle-footer">
          <p>{translate(language, "footer.disclaimer")}</p>
          <a href="/visa-oracle/privacy">
            {translate(language, "footer.privacy")}
          </a>
        </footer>

        <AtlasRoute
          ref={routeDialogRef}
          language={language}
          history={state.history}
          facts={state.facts}
          onEdit={handleEdit}
          onSelectCategory={handleSelectCategory}
        />
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
