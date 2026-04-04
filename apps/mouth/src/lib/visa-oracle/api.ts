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
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
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

export async function sendChatMessage(
  sessionId: string,
  message: string,
  quizAnswers?: QuizAnswers,
  conversationHistory?: ChatMessage[],
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/api/v1/visa-oracle/chat", {
    session_id: sessionId,
    message,
    ...(quizAnswers ? { quiz_answers: quizAnswers } : {}),
    ...(conversationHistory
      ? { conversation_history: conversationHistory }
      : {}),
  });
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
