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

export interface RecommendResponse {
  success: boolean;
  visas: VisaRecommendation[];
  session_id: string;
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
