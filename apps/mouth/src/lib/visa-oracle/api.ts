import type {
  QuizAnswers,
  RecommendResponse,
  ChatMessage,
  ChatResponse,
  HandoffResponse,
  VisaRecommendation,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "https://nuzantara-rag.fly.dev";

async function apiFetch<T>(
  path: string,
  body: Record<string, unknown>,
  extraHeaders: Record<string, string> = {},
): Promise<T> {
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

  return res.json() as Promise<T>;
}

export async function recommendVisas(
  answers: QuizAnswers,
): Promise<RecommendResponse> {
  return apiFetch<RecommendResponse>("/api/v1/visa-oracle/recommend", {
    ...answers,
  });
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
