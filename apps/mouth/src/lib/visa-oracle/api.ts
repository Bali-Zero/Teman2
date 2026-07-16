import type {
  QuizAnswers,
  RecommendResponse,
  RecommendState,
  ChatMessage,
  ChatResponse,
  HandoffResponse,
  VisaRecommendation,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "https://nuzantara-rag.fly.dev";

async function apiFetchRaw(
  path: string,
  body: Record<string, unknown>,
  extraHeaders: Record<string, string> = {},
): Promise<unknown> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...extraHeaders,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${text}`);
  }

  return res.json();
}

async function apiFetch<T>(
  path: string,
  body: Record<string, unknown>,
  extraHeaders: Record<string, string> = {},
): Promise<T> {
  return (await apiFetchRaw(path, body, extraHeaders)) as T;
}

const RECOMMEND_STATES: readonly RecommendState[] = [
  "NEEDS_INPUT",
  "SUPPORTED_CANDIDATES",
  "HUMAN_REVIEW_REQUIRED",
  "NO_SUPPORTED_PATH",
  "TEMPORARILY_UNAVAILABLE",
];

function isRecommendState(value: unknown): value is RecommendState {
  return (
    typeof value === "string" &&
    (RECOMMEND_STATES as readonly string[]).includes(value)
  );
}

function isVisaRecommendation(value: unknown): value is VisaRecommendation {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.visa_name === "string" &&
    typeof v.category === "string" &&
    typeof v.price === "string" &&
    typeof v.duration === "string" &&
    typeof v.validity === "string" &&
    typeof v.notes === "string" &&
    typeof v.score === "number"
  );
}

function isStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((item) => typeof item === "string")
  );
}

/**
 * Runtime-validate a raw `/recommend` JSON payload into a RecommendResponse
 * rather than blind TS-casting `res.json()` (PR0 safety freeze W4; round2
 * spec §6.5 "Runtime-validate API responses rather than TypeScript-casting
 * JSON").
 *
 * Tolerates the absence of `state`/`missing_facts`/`review_reasons` — a
 * legacy backend response that predates PR0 — and in that case trusts
 * `visas` exactly as before PR0 (no safety invariant existed to enforce).
 *
 * For any response that DOES carry a (recognized) `state`, this enforces
 * the safety invariant defensively even if the backend itself violates it:
 * `visas` is [] unless `state === "SUPPORTED_CANDIDATES"`. An unrecognized
 * `state` value is treated as absent (untrusted), not as an implicit
 * SUPPORTED_CANDIDATES.
 */
export function parseRecommendResponse(raw: unknown): RecommendResponse {
  if (typeof raw !== "object" || raw === null) {
    throw new Error("recommendVisas: malformed response (not an object)");
  }
  const obj = raw as Record<string, unknown>;

  if (typeof obj.success !== "boolean" || typeof obj.session_id !== "string") {
    throw new Error(
      "recommendVisas: malformed response (missing success/session_id)",
    );
  }

  const rawVisas = Array.isArray(obj.visas)
    ? obj.visas.filter(isVisaRecommendation)
    : [];

  // Distinguish "no `state` field at all" (true legacy backend, predates
  // PR0 — no invariant ever existed to enforce, trust `visas` as before)
  // from "a `state` field is present but not one of the five known values"
  // (a NEWER/unknown contract we don't understand — strictly less
  // trustworthy than legacy, so we do NOT fall back to trusting `visas`).
  const hasStateField =
    Object.prototype.hasOwnProperty.call(obj, "state") &&
    obj.state !== undefined;
  const state = isRecommendState(obj.state) ? obj.state : undefined;
  const missing_facts = isStringArray(obj.missing_facts)
    ? obj.missing_facts
    : undefined;
  const review_reasons = isStringArray(obj.review_reasons)
    ? obj.review_reasons
    : undefined;

  const visas = !hasStateField
    ? rawVisas
    : state === "SUPPORTED_CANDIDATES"
      ? rawVisas
      : [];

  return {
    success: obj.success,
    session_id: obj.session_id,
    visas,
    state,
    missing_facts,
    review_reasons,
  };
}

export interface RecommendOutcome {
  headline: string;
  detail: string;
  showWhatsAppEscape: boolean;
}

/**
 * Derive an honest, non-crashing display outcome from a RecommendResponse.
 * PR0 safety freeze W4: never render a fabricated candidate; when `visas`
 * is empty, always surface an honest "need more info" / "talk to a human"
 * message with the existing WhatsApp/contact escape hatch — never a crash,
 * never an undefined render.
 */
export function describeRecommendOutcome(
  response: RecommendResponse,
): RecommendOutcome {
  if (response.visas.length > 0) {
    const n = response.visas.length;
    return {
      headline: "Here's what fits",
      detail: `${n} visa option${n === 1 ? "" : "s"} matched your answers.`,
      showWhatsAppEscape: false,
    };
  }

  switch (response.state) {
    case "NEEDS_INPUT":
      return {
        headline: "We need a bit more information",
        detail:
          response.missing_facts && response.missing_facts.length > 0
            ? `Please confirm: ${response.missing_facts.join(", ")}.`
            : "Your answers weren't specific enough for a confident match — try again with a bit more detail.",
        showWhatsAppEscape: true,
      };
    case "HUMAN_REVIEW_REQUIRED":
    case "NO_SUPPORTED_PATH":
      return {
        headline: "This case needs a human specialist",
        detail:
          "Your situation doesn't match a standard path — our team can look at it directly.",
        showWhatsAppEscape: true,
      };
    case "TEMPORARILY_UNAVAILABLE":
      return {
        headline: "Recommendations are temporarily unavailable",
        detail: "Please try again shortly, or talk to our team now.",
        showWhatsAppEscape: true,
      };
    default:
      // Absent/unrecognized state with empty visas — still honest, never a
      // fabricated candidate.
      return {
        headline: "We couldn't find a confident match",
        detail: "Talk to our team and we'll help you find the right visa.",
        showWhatsAppEscape: true,
      };
  }
}

export async function recommendVisas(
  answers: QuizAnswers,
): Promise<RecommendResponse> {
  const raw = await apiFetchRaw("/api/v1/visa-oracle/recommend", {
    ...answers,
  });
  return parseRecommendResponse(raw);
}

function detectBrowserLanguage(): string {
  if (typeof navigator === "undefined") return "en";
  const raw = (navigator.language || "en").toLowerCase();
  // Take first 2 chars (en-US → en, it-IT → it)
  const code = raw.slice(0, 2);
  const supported = [
    "en",
    "it",
    "id",
    "fr",
    "es",
    "de",
    "ru",
    "zh",
    "ko",
    "ja",
  ];
  return supported.includes(code) ? code : "en";
}

export async function sendChatMessage(
  sessionId: string,
  message: string,
  quizAnswers?: QuizAnswers,
  conversationHistory?: ChatMessage[],
  checkHash?: string,
  sessionJwt?: string,
): Promise<ChatResponse> {
  const body: Record<string, unknown> = {
    session_id: sessionId,
    message,
    language: detectBrowserLanguage(),
    ...(quizAnswers ? { quiz_answers: quizAnswers } : {}),
    ...(conversationHistory
      ? { conversation_history: conversationHistory }
      : {}),
    ...(checkHash ? { check_hash: checkHash } : {}),
  };
  const headers: Record<string, string> = {};
  if (checkHash && sessionJwt) {
    headers["Authorization"] = `Bearer ${sessionJwt}`;
  }
  return apiFetch<ChatResponse>("/api/v1/visa-oracle/chat", body, headers);
}

export async function triggerHandoff(
  sessionId: string,
  quizAnswers: QuizAnswers,
  recommendedVisas: VisaRecommendation[],
  messages: ChatMessage[],
  language?: string,
): Promise<HandoffResponse> {
  return apiFetch<HandoffResponse>("/api/v1/visa-oracle/handoff", {
    session_id: sessionId,
    quiz_answers: quizAnswers,
    recommended_visas: recommendedVisas,
    messages,
    ...(language ? { language } : {}),
  });
}
