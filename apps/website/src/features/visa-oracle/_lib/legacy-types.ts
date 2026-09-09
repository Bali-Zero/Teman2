export interface QuizAnswers {
  nationality: string;
  purpose:
    | "visit"
    | "work"
    | "invest"
    | "retire"
    | "digital_nomad"
    | "family"
    | "study";
  duration: "short" | "medium" | "long" | "permanent";
  family: "solo" | "spouse" | "children" | "spouse_children";
}

export interface VisaRecommendation {
  visa_name: string;
  category: string;
  price: string;
  duration: string;
  validity: string;
  notes: string;
  score: number;
}

// PR0 safety freeze (2026-07-17, round2 spec §9 row PR0 / §6.2): additive
// five-state contract on /recommend. `visas` is guaranteed [] for every
// state except SUPPORTED_CANDIDATES.
export type RecommendState =
  | "NEEDS_INPUT"
  | "SUPPORTED_CANDIDATES"
  | "HUMAN_REVIEW_REQUIRED"
  | "NO_SUPPORTED_PATH"
  | "TEMPORARILY_UNAVAILABLE";

export interface RecommendResponse {
  success: boolean;
  visas: VisaRecommendation[];
  session_id: string;
  // Optional: absent on legacy backend responses that predate PR0. Treat
  // absence as "unknown state" — NOT as an implicit SUPPORTED_CANDIDATES.
  state?: RecommendState;
  missing_facts?: string[];
  review_reasons?: string[];
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  confidence?: "ABSTAIN" | "CAUTIOUS" | "NORMAL";
  sources?: string[];
}

export interface ChatResponse {
  success: boolean;
  answer: string;
  confidence: "ABSTAIN" | "CAUTIOUS" | "NORMAL";
  sources: string[];
  session_id: string;
  // Optional: absent on legacy backend responses. PR0 safety freeze W2.
  review_reasons?: string[];
}

export interface HandoffResponse {
  success: boolean;
  whatsapp_url: string;
  telegram_sent: boolean;
}

export interface Nationality {
  code: string;
  name: string;
  flag: string;
}
