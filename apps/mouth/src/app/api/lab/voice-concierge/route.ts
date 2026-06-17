import { NextResponse } from "next/server";

export const runtime = "nodejs";

type ConciergeIntent =
  | "visa"
  | "company"
  | "tax"
  | "property"
  | "operations"
  | "unknown";

type ConciergeRisk = "low" | "medium" | "high";

type ConciergeNextAction =
  | "answer_only"
  | "collect_non_pii_context"
  | "handoff_team"
  | "open_booking";

interface VoiceConciergeRequest {
  message?: string;
  locale?: "en" | "it" | "id" | "fr" | "ru";
  history?: { role: "user" | "assistant"; content: string }[];
}

interface VoiceConciergeResponse {
  answer: string;
  intent: ConciergeIntent;
  risk_level: ConciergeRisk;
  next_action: ConciergeNextAction;
  quick_replies: string[];
  safety_note: string;
  mode: "demo" | "gemini";
  provider: "local-demo" | "google-ai-studio";
  model?: string;
}

interface GeminiCandidate {
  content?: {
    parts?: { text?: string }[];
  };
}

interface GeminiResponse {
  candidates?: GeminiCandidate[];
}

const DEFAULT_MODEL = "gemini-2.5-flash";
const MAX_MESSAGE_LENGTH = 1200;
const MAX_HISTORY_ITEMS = 4;

const SYSTEM_PROMPT = [
  "You are the Bali Zero voice concierge prototype.",
  "Handle public, non-PII questions about Indonesian visas, PT PMA setup, tax basics, property due diligence, and operations.",
  "Do not ask for passports, KTP, NPWP, phone numbers, emails, exact client names, document numbers, or private WhatsApp/CRM details.",
  "If the user needs case-specific advice, collect only non-PII context and suggest a team handoff.",
  "Never quote prices. Tell the user that pricing must be checked through the Bali Zero pricing tool/team.",
  "Return only JSON that matches the requested schema.",
].join("\n");

const RESPONSE_SCHEMA = {
  type: "object",
  properties: {
    answer: { type: "string" },
    intent: {
      type: "string",
      enum: ["visa", "company", "tax", "property", "operations", "unknown"],
    },
    risk_level: { type: "string", enum: ["low", "medium", "high"] },
    next_action: {
      type: "string",
      enum: [
        "answer_only",
        "collect_non_pii_context",
        "handoff_team",
        "open_booking",
      ],
    },
    quick_replies: {
      type: "array",
      items: { type: "string" },
    },
  },
  required: [
    "answer",
    "intent",
    "risk_level",
    "next_action",
    "quick_replies",
  ],
};

function getApiKey(): string | undefined {
  return process.env.GOOGLE_AI_STUDIO_API_KEY || process.env.GEMINI_API_KEY;
}

function getModel(): string {
  return process.env.GOOGLE_AI_STUDIO_MODEL || DEFAULT_MODEL;
}

function isPrototypeEnabled(): boolean {
  return (
    process.env.NODE_ENV !== "production" ||
    process.env.VOICE_CONCIERGE_LAB_ENABLED === "true"
  );
}

function containsObviousPii(message: string): boolean {
  const patterns = [
    /\b[A-Z][0-9]{7,8}\b/i, // common passport-like format
    /\b\d{16}\b/, // KTP-like digit count
    /\b\d{15,16}\b/, // NPWP-like digit count
    /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i,
    /(?:\+?\d[\s.-]?){9,}/,
  ];
  return patterns.some((pattern) => pattern.test(message));
}

function inferIntent(message: string): ConciergeIntent {
  const normalized = message.toLowerCase();
  if (/\b(visa|kitas|kitap|e33|e28|golden visa|immigration)\b/.test(normalized))
    return "visa";
  if (/\b(pt pma|company|kbli|oss|business|cafe|restaurant)\b/.test(normalized))
    return "company";
  if (/\b(tax|npwp|ppn|vat|spt|coretax)\b/.test(normalized)) return "tax";
  if (/\b(property|villa|land|zoning|lease|hgb|hak pakai)\b/.test(normalized))
    return "property";
  if (/\b(bpjs|payroll|employee|permit|operations|compliance)\b/.test(normalized))
    return "operations";
  return "unknown";
}

function demoResponse(message: string): VoiceConciergeResponse {
  const intent = inferIntent(message);
  const byIntent: Record<ConciergeIntent, string> = {
    visa:
      "I can help triage the visa path, but keep this non-PII. Tell me your broad goal, nationality region, expected stay length, and whether this is work, investment, family, or retirement.",
    company:
      "For a PT PMA, the first useful checks are business activity, KBLI fit, foreign ownership limits, address/zoning, and whether the activity needs extra permits. Keep names and document numbers out for now.",
    tax:
      "For tax questions, we should separate personal residency, company obligations, VAT/PPN, payroll, and annual filing. Share only the scenario, not NPWP or client identifiers.",
    property:
      "For property, the first screen is legal title, zoning, access, building permits, lease/HGB structure, and buyer profile. Do not share parcel documents or owner names in this prototype.",
    operations:
      "For operations, I can classify the workflow and suggest the next Bali Zero team step. Keep employee names, phone numbers, and private case details out of the voice test.",
    unknown:
      "I can help route the question into visa, company, tax, property, or operations. Ask in plain language and avoid personal or document identifiers.",
  };

  return {
    answer: byIntent[intent],
    intent,
    risk_level: intent === "unknown" ? "low" : "medium",
    next_action:
      intent === "unknown" ? "answer_only" : "collect_non_pii_context",
    quick_replies: [
      "What context can I share safely?",
      "Route this to the team",
      "Try another question",
    ],
    safety_note:
      "Demo mode: no Gemini call was made because GOOGLE_AI_STUDIO_API_KEY or GEMINI_API_KEY is not configured.",
    mode: "demo",
    provider: "local-demo",
  };
}

function normalizeResponse(
  parsed: Partial<VoiceConciergeResponse>,
  model: string,
): VoiceConciergeResponse {
  const intent = parsed.intent ?? "unknown";
  const riskLevel = parsed.risk_level ?? "medium";
  const nextAction = parsed.next_action ?? "collect_non_pii_context";
  const quickReplies = Array.isArray(parsed.quick_replies)
    ? parsed.quick_replies.slice(0, 4).filter((reply) => reply.trim())
    : [];

  return {
    answer:
      parsed.answer ??
      "I can help, but I need a clearer non-PII question before routing this.",
    intent,
    risk_level: riskLevel,
    next_action: nextAction,
    quick_replies:
      quickReplies.length > 0
        ? quickReplies
        : ["Add non-PII context", "Handoff to team"],
    safety_note:
      "Prototype guardrail: do not share passports, KTP, NPWP, phone numbers, emails, client names, or private CRM/WhatsApp details.",
    mode: "gemini",
    provider: "google-ai-studio",
    model,
  };
}

function parseGeminiJson(text: string): Partial<VoiceConciergeResponse> {
  const trimmed = text
    .trim()
    .replace(/^```json\s*/i, "")
    .replace(/^```\s*/i, "")
    .replace(/```$/i, "")
    .trim();
  return JSON.parse(trimmed) as Partial<VoiceConciergeResponse>;
}

function buildContents(body: VoiceConciergeRequest, message: string) {
  const history = (body.history ?? []).slice(-MAX_HISTORY_ITEMS);
  return [
    ...history.map((turn) => ({
      role: turn.role === "assistant" ? "model" : "user",
      parts: [{ text: turn.content.slice(0, MAX_MESSAGE_LENGTH) }],
    })),
    {
      role: "user",
      parts: [
        {
          text: [
            `Locale preference: ${body.locale ?? "en"}`,
            "User voice turn:",
            message,
          ].join("\n"),
        },
      ],
    },
  ];
}

export async function POST(request: Request): Promise<NextResponse> {
  if (!isPrototypeEnabled()) {
    return NextResponse.json(
      { error: "voice_concierge_disabled" },
      { status: 404 },
    );
  }

  const body = (await request.json().catch(() => ({}))) as VoiceConciergeRequest;
  const message = body.message?.trim().slice(0, MAX_MESSAGE_LENGTH);

  if (!message) {
    return NextResponse.json({ error: "message required" }, { status: 400 });
  }

  if (containsObviousPii(message)) {
    return NextResponse.json(
      {
        error: "pii_not_allowed",
        safety_note:
          "Remove passports, KTP, NPWP, phone numbers, emails, names, and document identifiers before using the voice concierge prototype.",
      },
      { status: 400 },
    );
  }

  const apiKey = getApiKey();
  if (!apiKey) {
    return NextResponse.json(demoResponse(message));
  }

  const model = getModel();
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(
    model,
  )}:generateContent?key=${encodeURIComponent(apiKey)}`;

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
      contents: buildContents(body, message),
      generationConfig: {
        temperature: 0.4,
        maxOutputTokens: 700,
        responseMimeType: "application/json",
        responseSchema: RESPONSE_SCHEMA,
      },
    }),
  });

  if (!response.ok) {
    return NextResponse.json(
      {
        error: "gemini_request_failed",
        status: response.status,
      },
      { status: 502 },
    );
  }

  const data = (await response.json()) as GeminiResponse;
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) {
    return NextResponse.json(
      { error: "gemini_empty_response" },
      { status: 502 },
    );
  }

  try {
    return NextResponse.json(normalizeResponse(parseGeminiJson(text), model));
  } catch {
    return NextResponse.json(
      { error: "gemini_invalid_json" },
      { status: 502 },
    );
  }
}
